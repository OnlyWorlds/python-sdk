"""The lens profile (schema-dist ``profiles/lens.md``, serial 78): every conformance case in
``codegen/schema-dist/profiles/lens.fixture.json``, vendored with the distribution, replayed through
``is_lens``, ``is_template``, ``lenses_in_use`` and ``resolve_lens``, dispatched on the case's kind, and the
fixture's own tables (anchor fields, type order, date table, room pairs, defaults) read back through the reader.
The npm SDK's readers run the same cases."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from onlyworlds import ROOM_PAIRS, LensReading, is_lens, is_template, lenses_in_use, resolve_lens, world_graph

REPO = Path(__file__).resolve().parent.parent
FIXTURE = REPO / "codegen" / "schema-dist" / "profiles" / "lens.fixture.json"
KINDS = {"shape": 6, "keys": 23, "resolve": 51, "invariant": 4, "uses": 4, "graph": 34}
OWNER = {"rung": "owner"}


def load_fixture() -> dict[str, Any]:
    assert FIXTURE.exists(), f"no lens fixture at {FIXTURE}"
    doc: dict[str, Any] = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert doc["profile"] == "lens"
    return doc


def reader_of(world: Mapping[str, Any], name: str) -> dict[str, Any]:
    """A reader as the fixture writes it, its ``as`` (a reader's name) turned into that reader."""
    r: dict[str, Any] = dict(world["readers"][name])
    if r.get("as"):
        r["as"] = world["readers"][r["as"]]
    return r


def read(
    doc: Mapping[str, Any],
    world_name: str,
    lens: Any,
    reader: str,
    case: Mapping[str, Any] | None = None,
    world: Mapping[str, Any] | None = None,
) -> LensReading:
    c = case or {}
    return resolve_lens(
        world if world is not None else doc["worlds"][world_name],
        lens,
        reader_of(doc["worlds"][world_name], reader),
        as_of=c.get("as_of"),
        clock=c.get("clock"),
    )


def answer(c: Mapping[str, Any], doc: Mapping[str, Any]) -> dict[str, Any]:
    """One case's answer as the fixture writes it; an invariant answers with its broken parts."""
    kind = c["kind"]
    if kind == "shape":
        return {"is_lens": is_lens(c["element"]), "is_template": is_template(c["element"])}
    if kind == "keys":
        lens = {"id": "k", "type": "construct", "name": "k", "supertype": "Lens", "x_lens": c["x_lens"]}
        got = resolve_lens({"elements": []}, lens, OWNER)
        return {"legal": got["unreadable"] is None, "bad": got["unreadable"]}
    if kind == "resolve":
        got = read(doc, c["world"], c["lens"], c["reader"], c)
        out: dict[str, Any] = {"kept": got["kept"], "cut": got["cut"]}
        if "rows" in c:
            out["rows"] = got["rows"]
        if "notes_ignored" in c:
            out["notes_ignored"] = got["notes_ignored"]
        if "mail" in c:
            mail = got["mail"]
            out["mail"] = None if mail is None else {k: mail[k] for k in c["mail"]}  # type: ignore[literal-required]
        return out
    if kind == "invariant":
        world = doc["worlds"][c["world"]]
        broken: list[str] = []
        if c["claim"] == "subset":
            owner = read(doc, c["world"], c["lens"], "owner")
            names = [e["name"] for e in world["elements"] if e["id"] in c["secrets"]]
            for name in c["readers"]:
                got = read(doc, c["world"], c["lens"], name)
                if not set(got["kept"]) <= set(owner["kept"]):
                    broken.append(f"{name}: not a subset of the owner's")
                text = json.dumps(got, ensure_ascii=False)
                broken.extend(f"{name}: names {s}" for s in [*c["secrets"], *names] if s in text)
        elif c["claim"] == "same_without":
            without = {**world, "elements": [e for e in world["elements"] if e["id"] not in c["without"]]}
            for name in c["readers"]:
                if read(doc, c["world"], c["lens"], name, world=without) != read(doc, c["world"], c["lens"], name):
                    broken.append(f"{name}: moved without {', '.join(c['without'])}")
        elif c["claim"] == "unchanged":
            before = json.dumps(world, sort_keys=True)
            for name in c["readers"]:
                got = read(doc, c["world"], c["lens"], name)
                # A reading is the reader's own copy: changing it changes nothing in the world.
                for row in got["rows"]:
                    for v in row.values():
                        if isinstance(v, list):
                            v.append("planted")
                if json.dumps(world, sort_keys=True) != before:
                    broken.append(f"{name}: the world moved")
        else:
            broken.append(f"an invariant of unknown claim {c['claim']!r}")
        return {"broken": broken}
    if kind == "uses":
        return {"lenses": lenses_in_use(c["membership"], c["x_lens_uses"])}
    raise ValueError(f"a case of unknown kind {kind!r}")


def want(c: Mapping[str, Any]) -> dict[str, Any]:
    kind = c["kind"]
    if kind == "shape":
        return {"is_lens": c["is_lens"], "is_template": c["is_template"]}
    if kind == "keys":
        return {"legal": c["legal"], "bad": c["bad"]}
    if kind == "resolve":
        out = {"kept": c["kept"], "cut": c["cut"]}
        out.update({k: c[k] for k in ("rows", "notes_ignored", "mail") if k in c})
        return out
    if kind == "invariant":
        return {"broken": []}
    if kind == "uses":
        return {"lenses": c["lenses"]}
    return {"a reader for this kind": True}


def test_every_fixture_case_is_answered_as_the_fixture_says() -> None:
    doc = load_fixture()
    cases = doc["cases"]
    wrong: list[str] = []
    for c in cases:
        if c["kind"] == "graph":  # world_graph's, run with the section's invariants in test_graph.py
            continue
        try:
            got: dict[str, Any] = answer(c, doc)
        except Exception as err:  # a reader that throws disagrees, never skips
            got = {"threw": repr(err)}
        if got != want(c):
            wrong.append(f"{c['kind']}/{c['name']}: gave {got!r}, the fixture says {want(c)!r}")
    print(f"the lens fixture: {len(cases)} cases run, {len(wrong)} disagreeing, from {FIXTURE}")
    for line in wrong:
        print(line)
    assert wrong == []
    assert len(cases) == 122, f"the fixture holds {len(cases)} cases, serial 81 has 122"
    assert Counter(c["kind"] for c in cases) == KINDS


def _id(n: int) -> str:
    return f"019a7f00-0000-7000-8000-{n:012d}"


LENS: dict[str, Any] = {"id": _id(900), "type": "construct", "name": "L", "supertype": "Lens"}


def test_the_fixtures_tables_read_back_through_the_reader() -> None:
    doc = load_fixture()
    assert doc["pair"] == {"type": "construct", "supertype": "Lens"}
    assert is_template({"type": "construct", "supertype": "Lens", "subtype": doc["template_subtype"]})
    assert doc["field"] == "x_lens"
    # Anchor fields: one element per field, linked in the reverse order; the kept order is the field order.
    fields: list[str] = doc["anchor_fields"]
    elements: list[dict[str, Any]] = [{"id": _id(i + 1), "type": "object", "name": f} for i, f in enumerate(fields)]
    lens: dict[str, Any] = {**LENS, "x_lens": {"depth": 0}}
    for f in reversed(fields):
        lens[f] = [_id(fields.index(f) + 1)]
    lens["titles"] = [_id(99)]
    elements.append({"id": _id(99), "type": "title", "name": "not an anchor"})
    assert resolve_lens({"elements": elements}, lens, OWNER)["kept"] == [_id(i + 1) for i in range(len(fields))]
    # Type order: a filter over one element of each type, every one updated at the same time.
    every = [
        {"id": _id(200 + i), "type": t, "name": t, "updated_at": "2026-10-01T00:00:00Z"}
        for i, t in enumerate(reversed(doc["type_order"]))
    ]
    by_id = {e["id"]: e["type"] for e in every}
    assert [by_id[k] for k in resolve_lens({"elements": every}, LENS, OWNER)["kept"]] == doc["type_order"]
    # The date table: a dated type after as_of is cut, a timeless one is never fenced.
    for t in doc["type_order"]:
        field = doc["date_table"].get(t)
        el = {"id": _id(300), "type": t, "name": t, **({field: 10} if field else {})}
        got = resolve_lens({"elements": [el], "now": 5}, {**LENS, "x_lens": {"types": [t]}}, OWNER)
        assert got["cut"] == ({"after_as_of": 1} if field else {}), t
        undated = {"elements": [{"id": _id(301), "type": t, "name": t}], "now": 5}
        got = resolve_lens(undated, {**LENS, "x_lens": {"types": [t], "undated": "exclude"}}, OWNER)
        assert got["cut"] == ({"undated": 1} if field else {}), f"{t} undated"
    assert doc["room_pairs"] == [f"{t}/{s.lower()}" for t, s in ROOM_PAIRS]
    for pair in doc["room_pairs"]:
        assert (
            resolve_lens({"elements": []}, {**LENS, "x_lens": {"types": [pair.upper()]}}, OWNER)["unreadable"] is None
        )
    assert doc["cut_reasons"] == [
        "budget",
        "types",
        "window",
        "undated",
        "after_as_of",
        "anchor_not_visible",
        "not_visible",
        "hops_not_served",
    ]
    assert doc["owner_only_reasons"] == ["anchor_not_visible", "not_visible"]
    # Defaults: depth 1, budget 50, undated include, show full, mail none, thirty days of mail.
    assert doc["defaults"] == {
        "depth": 1,
        "budget": 50,
        "undated": "include",
        "show": "full",
        "mail": "none",
        "mail_days": 30,
    }
    many = [{"id": _id(400 + i), "type": "object", "name": f"o{i}"} for i in range(51)]
    filtered = resolve_lens({"elements": many}, LENS, OWNER)
    assert len(filtered["kept"]) == 50
    assert filtered["cut"] == {"budget": 1}
    assert filtered["rows"][0] == many[0]
    assert filtered["mail"] is None
    chain = [
        {"id": _id(1), "type": "object", "name": "a", "materials": [_id(2)]},
        {"id": _id(2), "type": "object", "name": "b", "materials": [_id(3)]},
        {"id": _id(3), "type": "object", "name": "c"},
    ]
    assert resolve_lens({"elements": chain}, {**LENS, "objects": [_id(1)]}, OWNER)["kept"] == [_id(1), _id(2)]


# The shared edge cases: inputs the fixture leaves open (a stub's links, the window's edge, the World's time_current
# as its now, no window without a now, a to after as_of, the
# fence on anchors, the members list in the mail rule, a message not repeated among the kept, the thirty days' edge,
# ties by id by code point), the same file byte for byte as the npm SDK's test/fixtures/lens-edges.json (both suites
# hold its sha256), answers written by hand.
EDGES_FILE = REPO / "tests" / "fixtures" / "lens-edges.json"
EDGES_SHA256 = "5ee70fe31868a36e1a97b516d8e65700a385fbc7212bbc87f5955e4441b038f6"


def test_the_shared_edge_cases() -> None:
    raw = EDGES_FILE.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == EDGES_SHA256
    edges = json.loads(raw.decode("utf-8"))
    wrong: list[str] = []
    for e in edges:
        try:
            r = resolve_lens(e["world"], e["lens"], e["reader"], as_of=e.get("as_of"), clock=e.get("clock"))
            got: dict[str, Any] = {}
            for k in e["want"]:
                v: Any = dict(r)[k]
                if k == "mail" and v is not None:
                    v = {m: v[m] for m in e["want"]["mail"]}
                got[k] = v
        except Exception as err:  # a reader that throws disagrees, never skips
            got = {"threw": repr(err)}
        if got != e["want"]:
            wrong.append(f"{e['name']}: gave {got!r}, want {e['want']!r}")
    for line in wrong:
        print(line)
    assert wrong == []
    assert len(edges) == 11


def test_a_lens_a_guest_knows_only_as_a_stub_reads_as_nothing() -> None:
    world: dict[str, Any] = {
        "elements": [
            {
                "id": "L",
                "type": "construct",
                "name": "Ada and hers",
                "supertype": "Lens",
                "characters": ["c1"],
                "x_lens": {"depth": 1},
            },
            {"id": "c1", "type": "character", "name": "Ada", "friends": ["c2"]},
            {"id": "c2", "type": "character", "name": "Bo"},
        ]
    }
    stub = {"rung": "guest", "whole": ["c1", "c2"], "known_of": ["L"]}
    r = resolve_lens(world, "L", stub)
    assert (r["kept"], r["cut"], r["unreadable"]) == ([], {}, None)
    assert world_graph(world, stub, lens="L")["nodes"] == []
    whole = {"rung": "guest", "whole": ["L", "c1", "c2"], "known_of": []}
    assert resolve_lens(world, "L", whole)["kept"] == ["c1", "c2"]


def test_resolve_lens_refuses_what_is_not_a_reading() -> None:
    with pytest.raises(TypeError):
        resolve_lens({"elements": []}, LENS, {"rung": "admin"})
    with pytest.raises(TypeError):
        resolve_lens({"elements": []}, LENS, {"rung": "owner", "as": {"rung": "x"}})
    with pytest.raises(TypeError):
        resolve_lens({}, LENS, OWNER)
    with pytest.raises(TypeError):
        resolve_lens({"elements": []}, 3, OWNER)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        resolve_lens({"elements": []}, LENS, OWNER, as_of=1.5)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        resolve_lens({"elements": []}, LENS, OWNER, clock="yesterday")
    # A lens id the reader cannot see, or that is not a lens, resolves to nothing.
    world = {"elements": [{**LENS, "hidden": True}, {"id": _id(1), "type": "object", "name": "o"}]}
    assert resolve_lens(world, LENS["id"], {"rung": "contributor"})["kept"] == []
    assert resolve_lens(world, _id(1), OWNER)["kept"] == []
    assert resolve_lens(world, LENS["id"], OWNER)["kept"] == [_id(1)]

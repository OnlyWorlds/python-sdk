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

from onlyworlds import (
    ROOM_PAIRS,
    LensReading,
    is_charter_element,
    is_lens,
    is_template,
    lenses_in_use,
    resolve_lens,
    world_graph,
)
from onlyworlds._schema import LINK_TARGETS

REPO = Path(__file__).resolve().parent.parent
FIXTURE = REPO / "codegen" / "schema-dist" / "profiles" / "lens.fixture.json"
KINDS = {"shape": 6, "keys": 25, "resolve": 99, "invariant": 4, "uses": 5, "graph": 47}
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
    assert len(cases) == 186, f"the fixture holds {len(cases)} cases, serial 94 has 186"
    assert Counter(c["kind"] for c in cases) == KINDS


def _id(n: int) -> str:
    return f"019a7f00-0000-7000-8000-{n:012d}"


LENS: dict[str, Any] = {"id": _id(900), "type": "construct", "name": "L", "supertype": "Lens"}


def test_the_fixtures_tables_read_back_through_the_reader() -> None:
    doc = load_fixture()
    assert doc["pair"] == {"type": "construct", "supertype": "Lens"}
    assert is_template({"type": "construct", "supertype": "Lens", "subtype": doc["template_subtype"]})
    assert doc["field"] == "x_lens"
    # Anchor fields: one element per field, of the field's target type, linked in the reverse order; the kept order
    # is the field order.
    fields: list[str] = doc["anchor_fields"]
    elements: list[dict[str, Any]] = [
        {"id": _id(i + 1), "type": LINK_TARGETS["construct"][f], "name": f} for i, f in enumerate(fields)
    ]
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
    # The reading aids: each pair word is a legal `types` word, and an element of the pair is an aid only with the mark.
    assert doc["reading_aid_pairs"] == ["law/charter", "construct/guide", "construct/domain"]
    assert doc["reading_aid_mark"]["field"] == "x_charter_of"
    for pair in doc["reading_aid_pairs"]:
        legal = resolve_lens({"elements": []}, {**LENS, "x_lens": {"types": [f" {pair.upper()} "]}}, OWNER)
        assert legal["unreadable"] is None, pair
        kind, supertype = pair.split("/")
        el = {"id": _id(500), "type": kind, "name": pair, "supertype": supertype.upper()}
        assert not is_charter_element(el), f"{pair} without the mark"
        assert is_charter_element({**el, doc["reading_aid_mark"]["field"]: "w1"}), f"{pair} with the mark"
    assert doc["cut_reasons"] == [
        "budget",
        "types",
        "window",
        "stale",
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
        {"id": _id(1), "type": "object", "name": "a", "parent_object": _id(2)},
        {"id": _id(2), "type": "object", "name": "b", "parent_object": _id(3)},
        {"id": _id(3), "type": "object", "name": "c"},
    ]
    assert resolve_lens({"elements": chain}, {**LENS, "objects": [_id(1)]}, OWNER)["kept"] == [_id(1), _id(2)]


# The shared edge cases: inputs the fixture leaves open (a stub's links, the window's edge, the World's time_current
# as its now, no window without a now, a to after as_of, the
# fence on anchors, the members list in the mail rule, a message not repeated among the kept, the thirty days' edge,
# ties by id by code point, an umbrella's child a guest knows only as a stub, a stub Message kept out of the mail
# part), the same file byte for byte as the npm SDK's test/fixtures/lens-edges.json (both suites hold its sha256),
# answers written by hand.
EDGES_FILE = REPO / "tests" / "fixtures" / "lens-edges.json"
EDGES_SHA256 = "4cb440cde85da877e2b5ba7129dd34be90a1e0bb109eefb56f0cae040a19b080"


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
    assert len(edges) == 15


# The reading aids and changed_within on the public calls (the npm SDK holds the same cases).
AIDS: dict[str, Any] = {
    "elements": [
        {"id": "desk", "type": "institution", "name": "The Desk", "constructs": ["domain", "guide"]},
        {
            "id": "rules",
            "type": "law",
            "name": "House Rules",
            "supertype": "Charter",
            "author": "desk",
            "x_charter_of": "w1",
        },
        {"id": "charter", "type": "law", "name": "Harbour Charter", "supertype": " charter ", "author": "desk"},
        {"id": "domain", "type": "construct", "name": "Reporting", "supertype": "Domain", "x_charter_of": "w1"},
        {
            "id": "guide",
            "type": "construct",
            "name": "How we work",
            "supertype": "GUIDE",
            "x_charter_of": "w1",
            "objects": ["ledger"],
        },
        {"id": "ledger", "type": "object", "name": "Ledger"},
    ]
}


def _lens_on(anchors: dict[str, list[str]], x_lens: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "id": "L",
        "type": "construct",
        "name": "L",
        "supertype": "Lens",
        **anchors,
        **({"x_lens": x_lens} if x_lens else {}),
    }


def test_is_charter_element_reads_the_pair_and_the_mark_both() -> None:
    els = AIDS["elements"]
    assert is_charter_element(els[1])
    assert not is_charter_element(els[2])  # the pair without the mark: lore
    assert is_charter_element(els[3])
    assert is_charter_element(els[4])  # GUIDE, folded
    assert not is_charter_element({"type": "law", "supertype": "Charters", "x_charter_of": "w1"})  # the whole word
    assert not is_charter_element({"type": "object", "supertype": "Charter", "x_charter_of": "w1"})
    assert not is_charter_element({"type": "law", "supertype": "Charter", "x_charter_of": ""})
    assert not is_charter_element({"type": "law", "supertype": "Charter", "x_charter_of": " " + chr(0x3000)})
    assert not is_charter_element({"type": "law", "supertype": "Charter", "x_charter_of": None})
    assert is_charter_element({"type": "law", "supertype": "Charter", "x_charter_of": 7})
    assert not is_charter_element(
        {"type": "law", "supertype": "Charter", "x_room_of": "w1"}
    )  # the room's mark is not it


def test_an_unmarked_charter_is_lore_kept_like_any_law() -> None:
    plain = resolve_lens(AIDS, _lens_on({"institutions": ["desk"]}), OWNER)
    assert plain["kept"] == ["desk", "charter"]
    assert plain["cut"] == {"types": 3}
    laws = resolve_lens(AIDS, _lens_on({"institutions": ["desk"]}, {"types": ["law"]}), OWNER)
    assert laws["kept"] == ["desk", "charter"]
    assert laws["cut"] == {"types": 3}


def test_a_marked_domain_a_hop_reaches_is_cut_unless_types_names_its_pair() -> None:
    none = resolve_lens(AIDS, _lens_on({"institutions": ["desk"]}, {"types": ["construct"]}), OWNER)
    assert none["kept"] == ["desk"]
    assert none["cut"] == {"types": 4}  # the three aids, and the lore Charter, a Law
    named = resolve_lens(AIDS, _lens_on({"institutions": ["desk"]}, {"types": [" Construct/Domain "]}), OWNER)
    assert named["kept"] == ["desk", "domain"]
    assert named["cut"] == {"types": 3}
    # A hop does not continue out of an aid whose pair is not named: the Ledger, behind the Guide, is never reached.
    deep = resolve_lens(AIDS, _lens_on({"institutions": ["desk"]}, {"depth": 2}), OWNER)
    assert deep["cut"] == {"types": 3}
    through_lens = _lens_on({"institutions": ["desk"]}, {"depth": 2, "types": ["construct/guide", "institution"]})
    assert resolve_lens(AIDS, through_lens, OWNER)["cut"] == {"types": 3, "hops_not_served": 1}
    # In an unlensed graph the aids are out, whatever flag is asked; a lens naming the pair keeps them as nodes.
    g = world_graph(AIDS, OWNER, rooms=True, hidden=True, proposed=True, map_space=True)
    assert [n["id"] for n in g["nodes"]] == ["charter", "desk", "ledger"]
    assert g["cut"] == {"reading_aid": 3}
    assert g["edges_cut"] == {"reading_aid": 2}  # the Desk's links to the Domain and the Guide
    assert g["edges"] == [{"source": "charter", "field": "author", "target": "desk", "index": 0}]
    lensed = world_graph(
        AIDS, OWNER, lens=_lens_on({"institutions": ["desk"]}, {"types": ["construct/domain", "institution"]})
    )
    assert [(n["id"], n.get("marks")) for n in lensed["nodes"]] == [("desk", None), ("domain", None)]


def test_an_anchor_that_is_a_marked_guide_is_kept_and_followed() -> None:
    r = resolve_lens(AIDS, _lens_on({"constructs": ["guide"]}, {"types": ["object", "institution"]}), OWNER)
    assert r["kept"] == ["guide", "desk", "ledger"]
    assert r["cut"] == {}
    public = resolve_lens(AIDS, _lens_on({"constructs": ["guide"]}), {"rung": "public"})
    assert public["kept"] == ["guide", "desk", "ledger"]  # an aid is no room element: a public reader sees it


def test_changed_within_keeps_its_exact_edge_and_never_cuts_an_anchor() -> None:
    clock = "2026-10-27T12:00:00Z"
    elements: list[dict[str, Any]] = [
        {
            "id": "a",
            "type": "institution",
            "name": "Anchor",
            "updated_at": "2020-01-01T00:00:00Z",
            "objects": ["edge", "past", "none", "bad"],
        },
        {"id": "edge", "type": "object", "name": "Seven days", "updated_at": "2026-10-20T12:00:00Z"},
        {"id": "past", "type": "object", "name": "Seven days and a second", "updated_at": "2026-10-20T11:59:59Z"},
        {"id": "none", "type": "object", "name": "No time"},
        {"id": "bad", "type": "object", "name": "Unreadable", "updated_at": "yesterday"},
    ]
    world = {"elements": elements}
    lens = _lens_on({"institutions": ["a"]}, {"changed_within": 7})
    r = resolve_lens(world, lens, OWNER, clock=clock)
    assert r["kept"] == ["a", "edge", "bad", "none"]  # no readable time: never cut, sorted last
    assert r["cut"] == {"stale": 1}
    # An offset is read: 13:00+01:00 is the same instant as the edge.
    elements[2]["updated_at"] = "2026-10-20T13:00:00+01:00"
    assert resolve_lens(world, lens, OWNER, clock=clock)["cut"] == {}
    # A filter is cut too, after the fence, types and the window.
    f = resolve_lens(world, _lens_on({}, {"types": ["object"], "changed_within": 1}), OWNER, clock=clock)
    assert (f["kept"], f["cut"]) == (["bad", "none"], {"stale": 2})
    for bad in (0, -1, 1.5, "7", True, [7]):
        got = resolve_lens(world, _lens_on({"institutions": ["a"]}, {"changed_within": bad}), OWNER)
        assert got["unreadable"] == "changed_within", bad
    null = _lens_on({"institutions": ["a"]}, {"changed_within": None})
    assert resolve_lens(world, null, OWNER, clock=clock)["unreadable"] is None


def test_changed_within_reads_a_folder_element_by_the_newer_sync_stamp() -> None:
    clock = "2026-10-27T12:00:00Z"
    lens = _lens_on({"institutions": ["a"]}, {"changed_within": 7})

    def kept(**stamps: str) -> bool:
        world = {
            "elements": [
                {"id": "a", "type": "institution", "name": "Anchor", "objects": ["o"]},
                {"id": "o", "type": "object", "name": "Folder copy", **stamps},
            ]
        }
        return "o" in resolve_lens(world, lens, OWNER, clock=clock)["kept"]

    assert kept(server_updated_at="2026-09-01T00:00:00Z", local_updated_at="2026-10-26T00:00:00Z")
    assert kept(server_updated_at="2026-10-26T00:00:00Z", local_updated_at="2026-09-01T00:00:00Z")
    assert not kept(server_updated_at="2026-09-01T00:00:00Z", local_updated_at="2026-09-02T00:00:00Z")
    # A folder stamp, where one reads, wins over updated_at; an unreadable one is no stamp.
    assert not kept(updated_at="2026-10-26T00:00:00Z", local_updated_at="2026-09-02T00:00:00Z")
    assert kept(updated_at="2026-10-26T00:00:00Z", local_updated_at="soon")


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


def test_an_anchor_of_another_type_than_its_field_is_one_the_reader_cannot_see() -> None:
    """lens.md (serial 93): an anchor id naming an element of another type than its field's is counted for the owner
    as ``anchor_not_visible``, as a dangling one is; it is never kept, and nothing hops from it."""
    world = {
        "elements": [
            {"id": "z1", "type": "location", "name": "Keep", "buildings": ["o1"]},
            {"id": "o1", "type": "object", "name": "Lamp"},
        ]
    }
    lens = _lens_on({"characters": ["z1"]})
    owner = resolve_lens(world, lens, OWNER)
    assert (owner["kept"], owner["cut"]) == ([], {"anchor_not_visible": 1})
    contributor = resolve_lens(world, lens, {"rung": "contributor"})
    assert (contributor["kept"], contributor["cut"]) == ([], {})
    assert resolve_lens(world, _lens_on({"locations": ["z1"]}), OWNER)["kept"] == ["z1", "o1"]


def test_an_anchor_the_reader_cannot_see_is_counted_before_the_visited_check() -> None:
    """lens.md rule 6 (serial 94): an anchor the reader cannot see is counted for the owner whatever it names, the
    lens itself included, for any anchor. A hidden lens in its own constructs, read as a body through a
    contributor's view; a visible lens under a field of another type than its own; a child lens pointing back at
    its hidden umbrella. The npm SDK holds the same three."""
    umbrella = {**LENS, "hidden": True, "constructs": [LENS["id"]], "x_lens": {}}
    as_contributor = {"rung": "owner", "as": {"rung": "contributor"}}
    assert resolve_lens({"elements": [umbrella]}, umbrella, as_contributor)["cut"] == {"anchor_not_visible": 1}
    misfiled = {**LENS, "characters": [LENS["id"]], "x_lens": {"depth": 0}}
    assert resolve_lens({"elements": [misfiled]}, LENS["id"], OWNER)["cut"] == {"anchor_not_visible": 1}
    ancestor = {**LENS, "hidden": True, "constructs": [_id(901)], "x_lens": {}}
    child = {
        "id": _id(901),
        "type": "construct",
        "name": "C",
        "supertype": "Lens",
        "constructs": [LENS["id"]],
        "objects": [_id(1)],
        "x_lens": {"depth": 0},
    }
    back = resolve_lens(
        {"elements": [ancestor, child, {"id": _id(1), "type": "object", "name": "o"}]}, ancestor, as_contributor
    )
    assert (back["kept"], back["cut"]) == ([_id(1)], {"anchor_not_visible": 1})


def test_a_full_row_of_a_hidden_element_carries_hidden_for_a_reader_that_sees_it() -> None:
    """lens.md (serial 94): a row is the body as the wire serves it, and keel's body of a hidden element carries
    ``hidden: true`` for a reader that sees it (keel elements/serialize.py:388-391, :492-493; elements/lens.py:454 and
    :904 serve the full row as that body). A world-level ``hidden`` list reads as the element's own mark; a ``name``
    or ``first_line`` row carries no ``hidden`` (:895-902); below the owner a hidden element is in no view but a
    guest's whose lists name it. The world is never written. The npm SDK holds the same case."""
    lamp = {"id": _id(1), "type": "object", "name": "Lamp", "description": "Brass.\nOld."}
    cup = {"id": _id(2), "type": "object", "name": "Cup", "hidden": True}
    world: dict[str, Any] = {"elements": [lamp, cup], "hidden": [_id(1)]}
    before = json.dumps(world, sort_keys=True)
    lens = _lens_on({"objects": [_id(1), _id(2)]}, {"depth": 0})
    want = [{**lamp, "hidden": True}, cup]
    for reader in (OWNER, {"rung": "owner", "as": {"rung": "owner"}}):
        assert resolve_lens(world, lens, reader)["rows"] == want, reader
    assert resolve_lens(world, _lens_on({"objects": [_id(1)]}, {"depth": 0, "show": "name"}), OWNER)["rows"] == [
        {"id": _id(1), "type": "object", "name": "Lamp"}
    ]
    first = resolve_lens(world, _lens_on({"objects": [_id(1)]}, {"depth": 0, "show": "first_line"}), OWNER)
    assert first["rows"] == [{"id": _id(1), "type": "object", "name": "Lamp", "description": "Brass."}]
    for reader in ({"rung": "contributor"}, {"rung": "owner", "as": {"rung": "contributor"}}, {"rung": "public"}):
        assert resolve_lens(world, lens, reader)["rows"] == [], reader
    # A guest is served a hidden element only as keel's view gives it one (its own making): then with the mark.
    guest = {"rung": "guest", "whole": [_id(1)], "known_of": []}
    assert resolve_lens(world, lens, guest)["rows"] == [{**lamp, "hidden": True}]
    assert json.dumps(world, sort_keys=True) == before


def test_only_a_served_body_of_a_hidden_element_carries_a_hidden_key() -> None:
    """lens.md (serial 94): keel's serialize sets ``hidden: true`` on a body of a hidden element after the stub is
    made (keel elements/serialize.py:463-464, :492-493), and no other body carries the key: a stored ``hidden: false``
    or null is dropped. A guest's stub of a hidden element its lists name carries the mark, and so does the owner's
    mail row of a hidden Message (keel elements/lens.py:955 serves it). The world is never written. The npm SDK
    holds the same cases."""
    lamp = {"id": _id(1), "type": "object", "name": "Lamp", "hidden": False}
    cup = {"id": _id(2), "type": "object", "name": "Cup", "hidden": None}
    vase = {"id": _id(3), "type": "object", "name": "Vase"}
    world: dict[str, Any] = {"elements": [lamp, cup, vase], "hidden": [_id(3)]}
    before = json.dumps(world, sort_keys=True)
    lens = _lens_on({"objects": [_id(1), _id(2), _id(3)]}, {"depth": 0})
    plain = [{"id": _id(1), "type": "object", "name": "Lamp"}, {"id": _id(2), "type": "object", "name": "Cup"}]
    assert resolve_lens(world, lens, OWNER)["rows"] == [*plain, {**vase, "hidden": True}]
    assert resolve_lens(world, lens, {"rung": "contributor"})["rows"] == plain
    guest = {"rung": "guest", "whole": [], "known_of": [_id(3)]}
    assert resolve_lens(world, lens, guest)["rows"] == [
        {"id": _id(3), "type": "object", "name": "Vase", "known_of": True, "hidden": True}
    ]
    ada = {"id": _id(4), "type": "character", "name": "Ada"}
    note = {
        "id": _id(5),
        "type": "narrative",
        "supertype": "Message",
        "name": "Hi",
        "characters": [_id(4)],
        "created_at": "2026-10-29T00:00:00Z",
    }
    post = {"elements": [ada, note], "hidden": [_id(5)]}
    mail = resolve_lens(
        post,
        _lens_on({"characters": [_id(4)]}, {"depth": 0, "mail": "all"}),
        {"rung": "owner", "character": _id(4)},
        clock="2026-10-30T00:00:00Z",
    )["mail"]
    assert mail is not None and mail["rows"] == [{**note, "hidden": True}]
    assert json.dumps(world, sort_keys=True) == before


def test_an_id_an_umbrella_and_its_child_anchor_under_two_wrong_types_is_one_element_counted_once() -> None:
    """lens.md (serial 94): an anchor reaches an element only through its field's target type and the id; the cut
    counts each element once, under its first reason. A Location the umbrella anchors under ``characters`` and its
    child under ``objects`` is one element the reader cannot see: ``anchor_not_visible`` once. The npm SDK holds the
    same case."""
    child = {**LENS, "id": _id(2), "name": "Child", "objects": [_id(1)], "x_lens": {"depth": 0}}
    umbrella = {**LENS, "id": _id(3), "name": "Umbrella", "characters": [_id(1)], "constructs": [_id(2)]}
    world = {"elements": [{"id": _id(1), "type": "location", "name": "Keep"}, child, umbrella]}
    got = resolve_lens(world, _id(3), OWNER)
    assert (got["kept"], got["cut"]) == ([], {"anchor_not_visible": 1})


def test_an_id_anchored_under_the_wrong_type_and_under_its_own_is_kept_and_never_cut() -> None:
    """lens.md (serial 94): an Object the umbrella anchors under ``characters`` and its child under ``objects`` is
    kept by the child, and a kept element is never also counted as cut. Within one lens the id is met once, under
    the first field in the anchor fields' order (keel elements/lens.py:604-609): with ``characters`` first it is
    met as no Character, so it is cut and not kept (:613-619); with ``objects`` first it is kept. The npm SDK holds
    the same cases."""
    child = {**LENS, "id": _id(2), "name": "Child", "objects": [_id(1)], "x_lens": {"depth": 0}}
    umbrella = {**LENS, "id": _id(3), "name": "Umbrella", "characters": [_id(1)], "constructs": [_id(2)]}
    world = {"elements": [{"id": _id(1), "type": "object", "name": "Lamp"}, child, umbrella]}
    got = resolve_lens(world, _id(3), OWNER)
    assert (got["kept"], got["cut"]) == ([_id(1)], {})
    wrong_first = resolve_lens(
        world, {**LENS, "characters": [_id(1)], "objects": [_id(1)], "x_lens": {"depth": 0}}, OWNER
    )
    assert (wrong_first["kept"], wrong_first["cut"]) == ([], {"anchor_not_visible": 1})
    own_first = resolve_lens(world, {**LENS, "objects": [_id(1)], "locations": [_id(1)], "x_lens": {"depth": 0}}, OWNER)
    assert (own_first["kept"], own_first["cut"]) == ([_id(1)], {})


def test_below_the_owner_an_anchor_it_cannot_see_is_recorded_under_no_reason_so_a_childs_cut_counts() -> None:
    """lens.md rule 6 (serial 94): keel records an anchor the reader cannot see for the owner's counts only (keel
    elements/lens.py:705-707); every other reader reads on as if the anchor were not there, so a child lens's cut of
    the same element by ``types`` stands (:758-759). The owner's ``anchor_not_visible`` comes first, the element
    counted once. The npm SDK holds the same case."""
    world = {
        "elements": [
            {**LENS, "id": "C", "name": "C", "objects": ["o"], "x_lens": {"types": ["object"]}},
            {"id": "o", "type": "object", "name": "Ledger", "location": "x"},
            {"id": "x", "type": "location", "name": "Harbour"},
        ]
    }
    lens = _lens_on({"characters": ["x"], "constructs": ["C"]}, {"depth": 0})
    got = resolve_lens(world, lens, {"rung": "contributor"})
    assert (got["kept"], got["cut"]) == (["o"], {"types": 1})
    owner = resolve_lens(world, lens, OWNER)
    assert (owner["kept"], owner["cut"]) == (["o"], {"anchor_not_visible": 1})


def test_a_note_goes_with_its_anchor_so_one_that_reaches_nothing_captions_no_row_and_is_not_counted() -> None:
    """lens.md rule 6 (serial 94): keel's anchor_ids hold the anchors it resolved only, and ``noted`` adds the unseen
    (keel elements/lens.py:792-793); a note captions a kept row only when its id is one of anchor_ids (:905), and
    _notes_ignored counts a note outside ``noted`` alone (:794, :807). A Language in ``constructs`` reaches nothing,
    so its note goes with it, though a child lens keeps the element. The npm SDK holds the same case."""
    world = {
        "elements": [
            {"id": "e08", "type": "language", "name": "Old Tongue"},
            {**LENS, "id": "L1", "name": "L1", "languages": ["e08"], "x_lens": {"depth": 0}},
        ]
    }
    lens = _lens_on(
        {"constructs": ["e08", "L1"]}, {"depth": 0, "show": "name", "notes": {"e08": "spoken in the hills"}}
    )
    for reader in (OWNER, {"rung": "contributor"}):
        got = resolve_lens(world, lens, reader)
        assert (got["kept"], got["rows"], got["cut"], got["notes_ignored"]) == (
            ["e08"],
            [{"id": "e08", "type": "language", "name": "Old Tongue"}],
            {},
            0,
        ), reader


def test_an_anchor_string_of_white_space_alone_is_no_anchor_so_the_lens_is_a_filter() -> None:
    """lens.md rule 7 (serial 94): an empty string, or one of White_Space alone, is no id and so no anchor; a lens whose
    anchor lists hold only such strings is a filter, nothing counted for them. A string of a character outside
    White_Space (a byte order mark, an information separator) is an id, one naming nothing, so the lens is anchored
    and the owner counts it. The npm SDK holds the same case."""
    world = {
        "elements": [
            {"id": "o1", "type": "object", "name": "Lamp"},
            {"id": "c1", "type": "character", "name": "Ada"},
        ]
    }
    blank = ["", "  ", chr(0xA0), chr(0x3000) + "\t", chr(0x2028)]
    lens = _lens_on({"characters": blank, "objects": [""]}, {"types": ["object"]})
    for reader in (OWNER, {"rung": "contributor"}):
        got = resolve_lens(world, lens, reader)
        assert (got["kept"], got["cut"]) == (["o1"], {}), reader
    for odd in (chr(0xFEFF), chr(0x1C)):
        got = resolve_lens(world, _lens_on({"characters": [odd]}, {"types": ["object"]}), OWNER)
        assert (got["kept"], got["cut"]) == ([], {"anchor_not_visible": 1}), hex(ord(odd))


def test_a_served_pins_pair_reads_its_type_key_exact() -> None:
    """lens.md (serial 93): a generic pair links only by one of the 22 slugs, compared exact as stored, so a reader
    below the owner is served a pair whose key is ``Character`` as ``""`` and null; ``character`` stays whole."""
    world = {
        "elements": [
            {"id": "c1", "type": "character", "name": "Ada"},
            {"id": "p1", "type": "pin", "name": "exact", "element_type": "character", "element_id": "c1"},
            {"id": "p2", "type": "pin", "name": "cased", "element_type": "Character", "element_id": "c1"},
        ]
    }
    guest = {"rung": "guest", "whole": ["c1", "p1", "p2"], "known_of": []}
    for reader in ({"rung": "contributor"}, guest):
        rows = resolve_lens(world, _lens_on({}, {"types": ["pin"]}), reader)["rows"]
        assert [(r["element_type"], r["element_id"]) for r in rows] == [("character", "c1"), ("", None)], reader


def test_an_empty_single_link_is_served_as_stored_and_never_marked_trimmed() -> None:
    """An empty single link names no id, so a reader below the owner is served it as stored, ``""``, and the field
    is never counted as trimmed: a Message's ``narrator`` of ``""`` gets no ``x_served_trimmed`` (keel's redact
    leaves a falsy value alone; the npm SDK's trim does too)."""
    world = {
        "elements": [
            {"id": "o1", "type": "object", "name": "Cup", "language": ""},
            {"id": "c1", "type": "character", "name": "Ada"},
            {
                "id": "m1",
                "type": "narrative",
                "supertype": "Message",
                "name": "Hi",
                "narrator": "",
                "characters": ["c1"],
            },
        ]
    }
    rows = resolve_lens(
        world, _lens_on({"objects": ["o1"], "narratives": ["m1"]}, {"depth": 0}), {"rung": "contributor"}
    )
    by_id = {r["id"]: r for r in rows["rows"]}
    assert by_id["o1"]["language"] == ""
    assert by_id["m1"]["narrator"] == ""
    assert "x_served_trimmed" not in by_id["m1"]


def test_a_stub_keeps_the_feeds_position() -> None:
    """A known-of stub keeps ``change_seq`` beside the base fields (the feed's position, not content)."""
    world = {"elements": [{"id": "c1", "type": "character", "name": "Ada", "change_seq": 7, "background": "x"}]}
    guest = {"rung": "guest", "whole": [], "known_of": ["c1"]}
    rows = resolve_lens(world, _lens_on({"characters": ["c1"]}, {"depth": 0}), guest)["rows"]
    assert rows == [
        {"id": "c1", "type": "character", "name": "Ada", "change_seq": 7, "background": "", "known_of": True}
    ]


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


def test_a_whole_number_key_reads_a_whole_float_and_a_date_field_reads_one_whole() -> None:
    """lens.md (serial 93): a whole float reads as its integer in every reader (``7.0`` is 7), a fraction and a
    boolean are refused, in an x_lens key as in a date field."""
    for key, value in [("depth", 1.5), ("budget", 7.5), ("window", 3.5), ("changed_within", 2.5), ("budget", True)]:
        got = resolve_lens({"elements": []}, {**LENS, "x_lens": {key: value}}, OWNER)
        assert got["unreadable"] == key, (key, value)
    for key, value in [("depth", 1.0), ("budget", 7.0), ("window", 3.0), ("changed_within", 2.0)]:
        got = resolve_lens({"elements": []}, {**LENS, "x_lens": {key: value}}, OWNER)
        assert got["unreadable"] is None, (key, value)
    raw = json.loads('{"from": 1.0, "to": 5}')
    assert resolve_lens({"elements": []}, {**LENS, "x_lens": raw}, OWNER)["unreadable"] is None
    # A budget of 7.0 keeps seven, as 7 does.
    many = {"elements": [{"id": _id(10 + i), "type": "object", "name": f"o{i}"} for i in range(9)]}
    assert len(resolve_lens(many, {**LENS, "x_lens": {"budget": 7.0}}, OWNER)["kept"]) == 7
    # A date field reading 7.0 is the whole number 7: fenced after an as_of of 6, kept at 7.
    world = {"elements": [{"id": _id(1), "type": "event", "name": "e", "start_date": 7.0}]}
    assert resolve_lens(world, LENS, OWNER, as_of=6)["cut"] == {"after_as_of": 1}
    assert resolve_lens(world, LENS, OWNER, as_of=7)["kept"] == [_id(1)]


# A row is the body as the reader is served it (lens.md, "Resolution"; keel elements/serialize.py and
# elements/visibility.py redact): a reader that is not the owner gets, in every link field, only ids it sees, a Pin's
# generic pair emptied when its target is unseen, and a lens's notes keyed to an unseen element left out;
# x_served_trimmed names only a Message's characters and narrator and a lens's anchor fields and notes, below
# co-builder and never on the public rung. The owner's rows are its bodies untouched. The same file byte for byte as
# the npm SDK's test/fixtures/row-trim-cases.json (both suites hold its sha256), answers written by hand.
ROW_TRIM_FILE = REPO / "tests" / "fixtures" / "row-trim-cases.json"
ROW_TRIM_SHA256 = "8365cf7c1364e8d04f2143824ba4cb19f275935d3a602178fb2ed497bf6fe140"


def test_a_readers_rows_carry_only_ids_it_sees() -> None:
    raw = ROW_TRIM_FILE.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == ROW_TRIM_SHA256
    cases = json.loads(raw.decode("utf-8"))
    wrong = []
    for c in cases:
        got = resolve_lens(c["world"], c["lens"], c["reader"])["rows"]
        if got != c["want_rows"]:
            wrong.append(f"{c['name']}: gave {got!r}, wants {c['want_rows']!r}")
    for line in wrong:
        print(line)
    assert wrong == []
    assert len(cases) == 28


def test_the_owners_row_keeps_a_link_to_a_proposed_element() -> None:
    """The owner reading as itself is served its bodies untouched, a link to an element written as proposed too; the
    proposed element is still in no reader's view, so nothing hops to it. A contributor is served the link too (keel's
    ``scoped`` leaves proposed elements out for the public rung alone); the public reader is not."""
    world: dict[str, list[dict[str, Any]]] = {
        "elements": [
            {"id": _id(1), "type": "location", "name": "Quay", "buildings": [_id(2)]},
            {"id": _id(2), "type": "object", "name": "Crane", "x_review_proposed": {"by": "seat"}},
        ]
    }
    lens = {**LENS, "locations": [_id(1)], "x_lens": {"depth": 1}}
    got = resolve_lens(world, lens, OWNER)
    assert got["kept"] == [_id(1)] and got["rows"] == [world["elements"][0]]
    seen = resolve_lens(world, lens, {"rung": "owner", "as": {"rung": "contributor"}})
    assert seen["kept"] == [_id(1)] and seen["rows"] == [world["elements"][0]]
    public = resolve_lens(world, lens, {"rung": "owner", "as": {"rung": "public"}})
    assert public["rows"] == [{**world["elements"][0], "buildings": []}]


def test_an_umbrellas_own_hop_keeps_a_child_lens_it_reaches() -> None:
    """Rule 3: what a hop never reaches is the lens read and every lens already entered; a child the umbrella has not
    entered yet is an element like any other when its own hop reaches it (keel's `known` holds the anchors, the
    unseen and the visited, never the children). The npm SDK's reader answers the same."""
    child = {**LENS, "id": _id(2), "name": "Child", "characters": [_id(1)], "x_lens": {"depth": 0}}
    umbrella = {**LENS, "id": _id(3), "name": "Umbrella", "characters": [_id(1)], "constructs": [_id(2)]}
    world = {"elements": [{"id": _id(1), "type": "character", "name": "Ada"}, child, umbrella]}
    assert resolve_lens(world, _id(3), OWNER)["kept"] == [_id(1), _id(2)]

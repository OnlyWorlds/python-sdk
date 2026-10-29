"""The lens profile's graph section: ``world_graph`` on the graph kind of
``codegen/schema-dist/profiles/lens.fixture.json`` (schema-dist serial 82, vendored with the pin; the MANIFEST holds
its sha256, the npm SDK runs the same cases), the section's invariants checked on every answer, and the fixture's graph
tables read back."""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

import pytest

from onlyworlds import FIELD_KINDS, WorldGraph, degree_of, out_degree_of, resolve_lens, world_graph

REPO = Path(__file__).resolve().parent.parent
FIXTURE = REPO / "codegen" / "schema-dist" / "profiles" / "lens.fixture.json"


def load_fixture() -> dict[str, Any]:
    doc: dict[str, Any] = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return doc


def load_cases() -> list[dict[str, Any]]:
    return [c for c in load_fixture()["cases"] if c["kind"] == "graph"]


def invariants(g: WorldGraph, c: Mapping[str, Any]) -> None:
    """The section's invariants on one answer."""
    name = c["name"]
    ids = [n["id"] for n in g["nodes"]]
    assert len(set(ids)) == len(ids), f"{name}: one node per id"
    nodes = set(ids)
    keys = [(e["source"], e["field"], e["target"], e["index"]) for e in g["edges"]]
    assert len(set(keys)) == len(keys), f"{name}: one edge per (source, field, target, index)"
    for e in g["edges"]:
        assert e["source"] in nodes and e["target"] in nodes, f"{name}: an edge between nodes only"
    for n in g["nodes"]:
        if n.get("known_of"):
            assert not any(e["source"] == n["id"] for e in g["edges"]), f"{name}: a known-of node has no edge out"
    reader = c["reader"]
    seen = reader["as"]["rung"] if reader["rung"] == "owner" and reader.get("as") else reader["rung"]
    if seen == "public":
        assert not any("marks" in n for n in g["nodes"]), (
            f"{name}: a public graph holds no room, hidden or proposed node"
        )
        for k in ("room", "hidden", "proposed"):
            assert k not in g["cut"] and k not in g["edges_cut"], f"{name}: a public graph has no count of {k}"
    if reader["rung"] != "owner":
        for k in ("hidden", "proposed", "not_visible", "anchor_not_visible"):
            assert k not in g["cut"] and k not in g["edges_cut"], f"{name}: no count of {k} for a reader not the owner"
    opts = c.get("options", {})
    again = world_graph(c["world"], reader, **opts)
    assert json.dumps(again) == json.dumps(g), f"{name}: the same input gives the same bytes"
    if opts.get("lens") is not None:
        r = resolve_lens(c["world"], opts["lens"], reader, as_of=opts.get("as_of"), clock=opts.get("clock"))
        assert sorted(ids) == sorted(r["kept"]), f"{name}: a lens's graph has exactly the lens's kept as its nodes"
        assert g["cut"] == r["cut"], f"{name}: the lens's cut rides along unchanged"
        assert g["unreadable"] == r["unreadable"], f"{name}: unreadable is the lens reading's"
        links_add_up(g, c)
    else:
        assert g["unreadable"] is None, f"{name}: unreadable is None without a lens"


_UNSEEN = ("not_visible", "anchor_not_visible")


def links_add_up(g: WorldGraph, c: Mapping[str, Any]) -> None:
    """Every link from a kept node to an element in the world is an edge or counted, read as the owner (the same
    view, the owner's counts); less the links the view leaves out, so is every link of the reader's own."""
    name, reader, opts = c["name"], c["reader"], c.get("options", {})
    owner_view = reader if reader["rung"] == "owner" else {"rung": "owner", "as": reader}
    go = world_graph(c["world"], owner_view, lens=opts["lens"], as_of=opts.get("as_of"), clock=opts.get("clock"))
    by_id = {el["id"]: el for el in reversed(c["world"]["elements"])}

    def linked(v: Any) -> int:
        return 1 if isinstance(v, str) and v in by_id else 0

    links = 0
    for n in go["nodes"]:
        if n.get("known_of"):
            continue
        el = by_id[n["id"]]
        for field, kind in FIELD_KINDS[n["type"]].items():
            v = el.get(field)
            if kind == "single_link":
                links += linked(v)
            elif kind == "multi_link" and isinstance(v, list):
                links += sum(linked(t) for t in v)
        for field in ("x_lens_leads_to", "x_spine_depends_on"):
            v = el.get(field)
            if isinstance(v, list):
                links += sum(linked(t) for t in v)
    assert len(go["edges"]) + sum(go["edges_cut"].values()) == links, (
        f"{name}: every link from a kept node is an edge or counted"
    )
    in_view = links - sum(v for k, v in go["edges_cut"].items() if k in _UNSEEN)
    assert len(g["edges"]) + sum(v for k, v in g["edges_cut"].items() if k not in _UNSEEN) == in_view, (
        f"{name}: every link from a kept node to an element the reader sees is an edge or counted"
    )


def test_the_fixtures_graph_cases() -> None:
    cases = load_cases()
    wrong: list[str] = []
    for c in cases:
        opts = c.get("options", {})
        refused = c["want"].get("refused")
        if refused is not None:
            try:
                world_graph(c["world"], c["reader"], **opts)
                wrong.append(f"{c['name']}: not refused")
            except ValueError as err:
                if refused not in str(err):
                    wrong.append(f"{c['name']}: refused as {err!r}, want one naming {refused}")
            continue
        got: dict[str, Any]
        try:
            g = world_graph(c["world"], c["reader"], **opts)
            invariants(g, c)
            got = dict(g)
        except Exception as err:  # a reader that throws disagrees, never skips
            got = {"threw": repr(err)}
        if got != c["want"]:
            wrong.append(f"{c['name']}: gave {got!r}, want {c['want']!r}")
    for line in wrong:
        print(line)
    assert wrong == []
    assert len(cases) == 37, f"the fixture holds {len(cases)} graph cases, serial 86 has 37"


def test_a_node_s_family_is_its_type_s_colour_word() -> None:
    """lens.md (serial 86): a node's ``family`` is the colour word presentation.json gives its type and nothing
    else, so Construct is pink and Ability amber; the fixture's wanted nodes carry the same words."""
    presentation = json.loads((FIXTURE.parent.parent / "presentation.json").read_text(encoding="utf-8"))
    words = {t: v["family"] for t, v in presentation["types"].items()}
    seen: set[str] = set()
    for c in load_cases():
        for n in c["want"].get("nodes", []):
            assert n["family"] == words[n["type"]], f"{c['name']}: the fixture's {n['type']} node"
        if c["want"].get("refused") is None:
            for n in world_graph(c["world"], c["reader"], **c.get("options", {}))["nodes"]:
                assert n["family"] == words[n["type"]], f"{c['name']}: {n['type']} node reads {n['family']!r}"
                seen.add(n["family"])
    assert seen == {"blue", "green", "pink", "amber"}
    g = world_graph(
        {"elements": [{"id": "c1", "type": "construct", "name": "C"}, {"id": "a1", "type": "ability", "name": "A"}]},
        {"rung": "owner"},
    )
    assert {n["type"]: n["family"] for n in g["nodes"]} == {"ability": "amber", "construct": "pink"}


def test_the_fixtures_graph_tables_read_back_through_the_reader() -> None:
    doc = load_fixture()
    assert doc["graph_flags"] == ["rooms", "hidden", "proposed", "map_space"]
    empty: dict[str, Any] = {"elements": []}
    for f in doc["graph_flags"]:
        flag: dict[str, Any] = {f: True}
        world_graph(empty, {"rung": "owner"}, **flag)
        if f in doc["owner_only_flags"]:
            with pytest.raises(ValueError, match="owner's alone"):
                world_graph(empty, {"rung": "contributor"}, **flag)
        else:
            world_graph(empty, {"rung": "contributor"}, **flag)
        with pytest.raises(ValueError):
            world_graph(empty, {"rung": "public"}, **flag)
    reasons = set(doc["edges_cut_reasons"])
    for c in load_cases():
        assert set(c["want"].get("edges_cut", {})) <= reasons, c["name"]
    for f in doc["graph_links"]:
        world = {
            "elements": [
                {"id": "a", "type": "construct", "name": "A", f: ["b"]},
                {"id": "b", "type": "construct", "name": "B"},
            ]
        }
        assert world_graph(world, {"rung": "owner"})["edges"] == [
            {"source": "a", "field": f, "target": "b", "index": 0}
        ], f
    other = {
        "elements": [
            {"id": "a", "type": "construct", "name": "A", "x_other_links": ["b"]},
            {"id": "b", "type": "construct", "name": "B"},
        ]
    }
    assert world_graph(other, {"rung": "owner"})["edges"] == []


class _Unread(list[Any]):
    """An elements list that fails the moment anything iterates it."""

    def __iter__(self) -> Iterator[Any]:
        raise AssertionError("read")


def test_a_refused_flag_is_refused_before_anything_is_read() -> None:
    world = {"elements": _Unread([{"id": "c1", "type": "character"}])}
    with pytest.raises(ValueError, match="hidden is the owner's alone"):
        world_graph(world, {"rung": "contributor"}, hidden=True)
    with pytest.raises(ValueError, match="proposed is the owner's alone"):
        world_graph(world, {"rung": "guest", "whole": []}, proposed=True)
    with pytest.raises(ValueError, match="public reader takes no flag; it asked rooms"):
        world_graph(world, {"rung": "public"}, rooms=True)
    with pytest.raises(ValueError, match="it asked map_space"):
        world_graph(world, {"rung": "public"}, map_space=True)
    with pytest.raises(ValueError, match="it asked rooms"):
        world_graph(world, {"rung": "owner", "as": {"rung": "public"}}, rooms=True)
    # The same world read without a refused flag does read the elements.
    with pytest.raises(AssertionError, match="read"):
        world_graph(world, {"rung": "owner"}, hidden=True)


def test_world_graph_refuses_what_is_not_a_reading() -> None:
    with pytest.raises(TypeError, match="rooms is a boolean"):
        world_graph({"elements": []}, {"rung": "owner"}, rooms="yes")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        world_graph({"elements": []}, {"rung": "admin"})
    with pytest.raises(TypeError):
        world_graph({}, {"rung": "owner"})
    with pytest.raises(TypeError):
        world_graph({"elements": []}, {"rung": "owner"}, lens=3)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        world_graph({"elements": []}, {"rung": "owner"}, as_of=1.5)  # type: ignore[arg-type]
    empty = world_graph({"elements": []}, {"rung": "public"}, rooms=False)
    assert empty == {"nodes": [], "edges": [], "edges_cut": {}, "cut": {}, "unreadable": None}


def test_degree_of_counts_each_node_s_edges_a_self_link_once() -> None:
    world: dict[str, Any] = {
        "elements": [
            {"id": "c1", "type": "character", "name": "Ada", "friends": ["c2", "c1"]},
            {"id": "c2", "type": "character", "name": "Bo", "friends": ["c1"]},
            {"id": "r1", "type": "relation", "name": "Pact", "characters": ["c1", "c2", "c3"]},
            {"id": "c3", "type": "character", "name": "Cy"},
            {"id": "o1", "type": "object", "name": "Lamp"},
            {"id": "constructor", "type": "object", "name": "An id like an inherited key"},
            {"id": "__proto__", "type": "character", "name": "Another", "objects": ["constructor"]},
        ]
    }
    g = world_graph(world, {"rung": "owner"})
    d = degree_of(g)
    assert list(d) == [n["id"] for n in g["nodes"]]
    assert (d["c1"], d["c2"], d["r1"], d["c3"], d["o1"], d["constructor"], d["__proto__"]) == (4, 3, 3, 1, 0, 1, 1)
    with pytest.raises(TypeError):
        degree_of({"nodes": []})


def test_out_degree_of_counts_distinct_targets_a_self_link_none() -> None:
    world: dict[str, Any] = {
        "elements": [
            {"id": "c1", "type": "character", "name": "Ada", "friends": ["c2", "c1"], "rivals": ["c2"]},
            {"id": "c2", "type": "character", "name": "Bo", "friends": ["c1"]},
            {"id": "r1", "type": "relation", "name": "Pact", "characters": ["c1", "c2", "c3"]},
            {"id": "c3", "type": "character", "name": "Cy"},
            {"id": "o1", "type": "object", "name": "Lamp"},
            {"id": "constructor", "type": "object", "name": "An id like an inherited key"},
            {"id": "__proto__", "type": "character", "name": "Another", "objects": ["constructor"]},
        ]
    }
    g = world_graph(world, {"rung": "owner"})
    d = out_degree_of(g)
    assert list(d) == [n["id"] for n in g["nodes"]]
    assert (d["c1"], d["c2"], d["r1"], d["c3"], d["o1"], d["constructor"], d["__proto__"]) == (1, 1, 3, 0, 0, 0, 1)
    with pytest.raises(TypeError):
        out_degree_of({"nodes": []})


def test_out_degree_of_on_every_fixture_graph_case_equals_a_direct_count() -> None:
    cases = 0
    for c in load_cases():
        want = c["want"]
        if "nodes" not in want:
            continue
        cases += 1
        d = out_degree_of({"nodes": want["nodes"], "edges": want["edges"]})
        for n in want["nodes"]:
            direct = len({e["target"] for e in want["edges"] if e["source"] == n["id"] and e["target"] != n["id"]})
            assert d[n["id"]] == direct, (c["name"], n["id"])
    assert cases > 0, "no fixture graph case was read"


def test_degree_of_on_every_fixture_graph_case_equals_a_direct_count() -> None:
    for c in load_cases():
        want = c["want"]
        if "nodes" not in want:
            continue
        d = degree_of({"nodes": want["nodes"], "edges": want["edges"]})
        for n in want["nodes"]:
            direct = sum(1 for e in want["edges"] if n["id"] in (e["source"], e["target"]))
            assert d[n["id"]] == direct, (c["name"], n["id"])

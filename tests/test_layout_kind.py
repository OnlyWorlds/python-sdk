"""by-kind and around, two layout methods: the npm SDK's shared fixture (``tests/fixtures/layout/by-kind.json``, the
same bytes, sha256 held here and there). Every ``cases`` entry compares exactly, float for float: the method is
chaotic, so a twin that is off by one unit in the last place draws another picture. Every ``around`` entry compares
within 1e-12: each of its points is one cosine and one sine, which runtimes round differently in the last place, and
nothing iterates on them. Then the baked anchor table and the group order against the fixture, and the refusals."""

from __future__ import annotations

import copy
import hashlib
import importlib
import json
import math
import random
import sys
from pathlib import Path
from typing import Any

import pytest

from onlyworlds import layout_around, layout_by_kind
from onlyworlds._anchors import ANCHORS, GROUP_ORDER
from onlyworlds._schema import ELEMENT_GROUPS

REPO = Path(__file__).resolve().parent.parent
FIXTURE = REPO / "tests" / "fixtures" / "layout" / "by-kind.json"
FIXTURE_SHA = "06a023eace0f906e"
BYTES = FIXTURE.read_bytes()
FX: dict[str, Any] = json.loads(BYTES.decode("utf-8"))
AROUND_TOLERANCE = 1e-12


def test_the_fixture_is_the_one_both_packages_hold() -> None:
    assert hashlib.sha256(BYTES).hexdigest()[:16] == FIXTURE_SHA


@pytest.mark.parametrize("case", FX["cases"], ids=[c["name"] for c in FX["cases"]])
def test_by_kind_case_exactly(case: dict[str, Any]) -> None:
    got = layout_by_kind(copy.deepcopy(case["graph"]))
    assert got["method"] == "by-kind"
    assert got["version"] == 1
    assert [p["id"] for p in got["points"]] == [x["id"] for x in case["graph"]["nodes"]]
    assert [[p["x"], p["y"]] for p in got["points"]] == case["want"]


@pytest.mark.parametrize("case", FX["around"], ids=[c["name"] for c in FX["around"]])
def test_around_case_within_1e_12(case: dict[str, Any]) -> None:
    got = layout_around(copy.deepcopy(case["graph"]), case["focus"], steps=case["steps"])
    assert got["method"] == "around"
    assert got["version"] == 1
    assert [(p["id"], p["depth"]) for p in got["points"]] == [(w[0], w[1]) for w in case["want"]]
    for p, w in zip(got["points"], case["want"], strict=True):
        assert abs(p["x"] - w[2]) <= AROUND_TOLERANCE, p["id"]
        assert abs(p["y"] - w[3]) <= AROUND_TOLERANCE, p["id"]


def test_the_baked_anchors_are_the_fixtures_table() -> None:
    assert len(ANCHORS) == 23 and ANCHORS[0] == ()
    assert sorted(FX["anchors"], key=int) == [str(k) for k in range(1, 23)]
    for k in range(1, 23):
        want = [(float(x), float(y)) for x, y in FX["anchors"][str(k)]]
        assert list(ANCHORS[k]) == want, k


def test_the_group_order_and_groups_are_the_fixtures() -> None:
    assert list(GROUP_ORDER) == FX["group_order"]
    assert dict(ELEMENT_GROUPS) == FX["groups"]


def test_the_generated_anchors_are_current() -> None:
    sys.path.insert(0, str(REPO / "codegen"))
    try:
        generate_anchors = importlib.import_module("generate_anchors")  # codegen/ is no package: found by path
    finally:
        sys.path.pop(0)
    assert (REPO / "src" / "onlyworlds" / "_anchors.py").read_text(encoding="utf-8") == generate_anchors.build()


def _id(k: int) -> str:
    return f"01a1d4ef-0000-7000-8000-{k:012x}"


def test_an_empty_graph_answers_no_points() -> None:
    assert layout_by_kind({"nodes": [], "edges": []}) == {"method": "by-kind", "version": 1, "points": []}


def test_one_element_stands_at_the_centre_and_extra_keys_are_read_past() -> None:
    node = {"id": _id(1), "type": "character", "name": None, "family": "blue", "icon": "person"}
    got = layout_by_kind({"nodes": [node], "edges": [], "edges_cut": {}, "cut": {}, "unreadable": None})
    assert got["points"] == [{"id": _id(1), "x": 0.0, "y": 0.0}]


def test_a_link_to_an_id_that_is_not_a_node_is_passed_over() -> None:
    case = next(c for c in FX["cases"] if c["name"] == "two-elements-linked")
    graph = copy.deepcopy(case["graph"])
    graph["edges"].append({"source": _id(1), "target": _id(99), "field": "friends", "index": 0})
    assert [[p["x"], p["y"]] for p in layout_by_kind(graph)["points"]] == case["want"]


def _shuffled(graph: dict[str, Any], seed: int) -> dict[str, Any]:
    out = copy.deepcopy(graph)
    rand = random.Random(seed)
    rand.shuffle(out["nodes"])
    rand.shuffle(out["edges"])
    return out


@pytest.mark.parametrize("name", ["hyperion", "moppetopia", "a-crowded-cell"])
def test_a_graph_handed_in_another_order_gives_the_same_points_by_id(name: str) -> None:
    case = next(c for c in FX["cases"] if c["name"] == name)
    want = {p["id"]: (p["x"], p["y"]) for p in layout_by_kind(copy.deepcopy(case["graph"]))["points"]}
    for seed in (1, 2, 3):
        graph = _shuffled(case["graph"], seed)
        got = layout_by_kind(graph)["points"]
        assert [p["id"] for p in got] == [x["id"] for x in graph["nodes"]]  # the caller's order
        assert {p["id"]: (p["x"], p["y"]) for p in got} == want


def test_around_a_graph_handed_in_another_order_gives_the_same_points_by_id() -> None:
    case = next(c for c in FX["around"] if c["name"] == "two-steps")
    want = {p["id"]: p for p in layout_around(copy.deepcopy(case["graph"]), case["focus"], steps=2)["points"]}
    for seed in (1, 2, 3):
        graph = _shuffled(case["graph"], seed)
        got = layout_around(graph, case["focus"], steps=2)["points"]
        order = [x["id"] for x in graph["nodes"] if x["id"] in want]
        assert [p["id"] for p in got] == order  # the caller's order, only the nodes within the steps
        assert {p["id"]: p for p in got} == want


def test_an_edge_with_no_field_or_index_sorts_as_the_empty_field_at_0() -> None:
    case = next(c for c in FX["cases"] if c["name"] == "hyperion")
    bare = copy.deepcopy(case["graph"])
    for e in bare["edges"]:
        e.pop("field")
        e.pop("index")
    named = copy.deepcopy(bare)
    for e in named["edges"]:
        e["field"], e["index"] = "", 0
    backwards = copy.deepcopy(bare)
    backwards["edges"].reverse()
    assert layout_by_kind(bare) == layout_by_kind(named) == layout_by_kind(backwards)
    around = layout_around(bare, case["graph"]["nodes"][0]["id"], steps=2)
    assert around == layout_around(named, case["graph"]["nodes"][0]["id"], steps=2)


def test_the_answer_does_not_touch_the_graph() -> None:
    case = next(c for c in FX["cases"] if c["name"] == "hyperion")
    graph = copy.deepcopy(case["graph"])
    layout_by_kind(graph)
    assert graph == case["graph"]


@pytest.mark.parametrize(
    ("graph", "message"),
    [
        (None, "the graph is {nodes, edges}, as world_graph answers it"),
        ({"nodes": []}, "the graph is {nodes, edges}, as world_graph answers it"),
        ({"nodes": [], "edges": {}}, "the graph is {nodes, edges}, as world_graph answers it"),
        ({"nodes": ["x"], "edges": []}, "node 0 is not an object"),
        ({"nodes": [{"type": "character"}], "edges": []}, "node 0 has no id"),
        ({"nodes": [{"id": "", "type": "character"}], "edges": []}, "node 0 has no id"),
        (
            {"nodes": [{"id": "a", "type": "dragon"}], "edges": []},
            "node a: 'dragon' is not one of the 22 element types",
        ),
        (
            {"nodes": [{"id": "a", "type": "Character"}], "edges": []},
            "node a: 'Character' is not one of the 22 element types",
        ),
        ({"nodes": [{"id": "a"}], "edges": []}, "node a: None is not one of the 22 element types"),
        ({"nodes": [{"id": "a", "type": "event", "name": 3}], "edges": []}, "node a: name is a string or None"),
        (
            {"nodes": [{"id": "a", "type": "event"}, {"id": "a", "type": "law"}], "edges": []},
            "the id a is a node twice",
        ),
        ({"nodes": [], "edges": [{"source": "a"}]}, "edge 0 is not {source, target}"),
        ({"nodes": [], "edges": [None]}, "edge 0 is not {source, target}"),
        ({"nodes": [], "edges": [{"source": "a", "target": "b", "field": 1}]}, "edge 0: field is a string"),
        ({"nodes": [], "edges": [{"source": "a", "target": "b", "index": "0"}]}, "edge 0: index is a number"),
        ({"nodes": [], "edges": [{"source": "a", "target": "b", "index": True}]}, "edge 0: index is a number"),
        ({"nodes": [], "edges": [{"source": "a", "target": "b", "index": math.nan}]}, "edge 0: index is a number"),
        ({"nodes": [], "edges": [{"source": "a", "target": "b", "field": None}]}, "edge 0: field is a string"),
        ({"nodes": [], "edges": [{"source": "a", "target": "b", "index": None}]}, "edge 0: index is a number"),
    ],
)
def test_a_graph_it_cannot_read_is_refused_by_both(graph: Any, message: str) -> None:
    with pytest.raises(TypeError) as e:
        layout_by_kind(graph)
    assert str(e.value) == f"layout_by_kind: {message}"
    with pytest.raises(TypeError) as e:
        layout_around(graph, "a")
    assert str(e.value) == f"layout_around: {message}"


def test_a_focus_that_is_not_a_node_is_refused() -> None:
    graph = {"nodes": [{"id": _id(1), "type": "character"}], "edges": [{"source": _id(1), "target": _id(2)}]}
    for focus in (_id(2), "", None):
        with pytest.raises(ValueError, match="is not a node of the graph"):
            layout_around(graph, focus)  # type: ignore[arg-type]


@pytest.mark.parametrize("steps", [0, 3, -1])
def test_steps_beyond_one_or_two_are_refused(steps: int) -> None:
    graph = {"nodes": [{"id": _id(1), "type": "character"}], "edges": []}
    with pytest.raises(ValueError, match=rf"^layout_around: steps is 1 or 2, not {steps}$"):
        layout_around(graph, _id(1), steps=steps)


@pytest.mark.parametrize("steps", [True, 1.0, "1", None])
def test_steps_that_are_not_whole_numbers_are_refused(steps: Any) -> None:
    graph = {"nodes": [{"id": _id(1), "type": "character"}], "edges": []}
    with pytest.raises(TypeError, match=r"^layout_around: steps is 1 or 2, not "):
        layout_around(graph, _id(1), steps=steps)


def test_around_steps_default_to_one() -> None:
    case = next(c for c in FX["around"] if c["name"] == "one-step-of-the-same")
    assert case["steps"] == 1
    assert layout_around(copy.deepcopy(case["graph"]), case["focus"]) == layout_around(
        copy.deepcopy(case["graph"]), case["focus"], steps=1
    )


def test_around_reads_no_name_as_the_empty_name() -> None:
    centre = {"id": _id(1), "type": "character", "name": "C"}
    leaves: list[dict[str, Any]] = [
        {"id": _id(2), "type": "character", "name": "a"},
        {"id": _id(3), "type": "character", "name": None},
        {"id": _id(4), "type": "character"},
        {"id": _id(5), "type": "character", "name": ""},
    ]
    edges = [{"source": _id(1), "target": x["id"]} for x in leaves]
    got = layout_around({"nodes": [centre, *leaves], "edges": edges}, _id(1))
    # The three unnamed tie on "" and go by node order; "a" after them: the ring runs clockwise from the top.
    first = [p for p in got["points"] if p["depth"] == 1]
    angles_by_id = {p["id"]: (p["x"], p["y"]) for p in first}
    order = [_id(3), _id(4), _id(5), _id(2)]
    ring = layout_around(
        {
            "nodes": [centre, *[{"id": i, "type": "character", "name": f"{k}"} for k, i in enumerate(order)]],
            "edges": [{"source": _id(1), "target": i} for i in order],
        },
        _id(1),
    )
    assert angles_by_id == {p["id"]: (p["x"], p["y"]) for p in ring["points"] if p["depth"] == 1}


def test_around_names_go_by_code_point_not_by_locale() -> None:
    case = next(c for c in FX["around"] if c["name"] == "names-by-code-point-not-locale")
    got = layout_around(copy.deepcopy(case["graph"]), case["focus"])
    names = {x["id"]: x["name"] for x in case["graph"]["nodes"]}
    ring = [p for p in got["points"] if p["depth"] == 1]
    # Clockwise from the top: the first point is the one nearest straight up (smallest angle past -pi/2).
    by_angle = sorted(ring, key=lambda p: (math.atan2(p["y"], p["x"]) + math.pi / 2) % (2 * math.pi))
    assert [names[p["id"]] for p in by_angle] == sorted(names[p["id"]] for p in ring)
    assert sorted(names[p["id"]] for p in ring)[-1] == chr(0x1D400) + "lpha"

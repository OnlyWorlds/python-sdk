"""by-links-3d, a 3D layout method read from a world's graph and its Maps and Pins. The method's shared fixture
(``tests/fixtures/layout/by-links-3d.fixture.json``, sha256 held here and in the npm SDK's test) gives each case's
input and the answer the reference implementation gives; the fixture's head (``call``, ``compare``) says how a case is
run and compared:
  exact    every element placed centre, with or map: each of x, y, z the same double (the eight bytes, so a zero's
           sign counts); and every ids, how, group, part, held and centres entry
  within   every element placed arm, link or shelf that is not held: each of x, y, z within 1e-9 of a rest, since
           those are placed with the runtime's cosine and sine
  held     every element answered as held: the very double the case's input.held gives for it
  refused  the call raises before anything runs, with the case's code
Then the baked directions table against the table the fixture names, the handed order, the inputs left unchanged,
and the exports."""

from __future__ import annotations

import copy
import hashlib
import json
import struct
from pathlib import Path
from typing import Any

import pytest

import onlyworlds
from onlyworlds import BY_LINKS_3D_REST, LayoutByLinks3d, layout_by_links_3d
from onlyworlds._directions import DIRECTIONS
from onlyworlds.layout_links_3d import HeldRangeError, HeldTypeError

REPO = Path(__file__).resolve().parent.parent
FIXTURE = REPO / "tests" / "fixtures" / "layout" / "by-links-3d.fixture.json"
TABLE = REPO / "codegen" / "layout" / "directions.json"
FIXTURE_SHA = "16284adffac8903777e754cc01d547de95a61447b6d945ca2f641ddf93c4d4eb"
BYTES = FIXTURE.read_bytes()


def _int(text: str) -> int | float:
    # a JSON -0 is the double -0.0 (int("-0") would lose the sign); the fixture writes none, but the compare reads one
    return -0.0 if text == "-0" else int(text)


FX: dict[str, Any] = json.loads(BYTES.decode("utf-8"), parse_int=_int)
EXACT = {"centre", "with", "map"}
ERROR_CLASS: dict[str, type[Exception]] = {
    "held-not-object": HeldTypeError,
    "held-not-point": HeldTypeError,
    "held-box": HeldRangeError,
    "held-unit": HeldRangeError,
}


def bits(v: float) -> bytes:
    return struct.pack("<d", float(v))


def options_of(case_input: dict[str, Any]) -> dict[str, Any]:
    """input.held and input.heldUnit, handed only where the input has the key (a JSON null is handed as None)."""
    out: dict[str, Any] = {}
    if "held" in case_input:
        out["held"] = case_input["held"]
    if "heldUnit" in case_input:
        out["held_unit"] = case_input["heldUnit"]
    return out


def run(case_input: dict[str, Any]) -> LayoutByLinks3d:
    graph = {"nodes": case_input["nodes"], "edges": case_input["edges"]}
    return layout_by_links_3d(graph, case_input["rows"], **options_of(case_input))


def named(name: str) -> dict[str, Any]:
    for c in FX["cases"]:
        if c["name"] == name:
            return dict(c)
    raise AssertionError(f"the fixture has no case {name}")


def test_the_fixture_is_the_one_both_packages_hold() -> None:
    assert hashlib.sha256(BYTES).hexdigest() == FIXTURE_SHA
    assert FX["method"] == "by-links-3d"
    assert FX["rest"] == BY_LINKS_3D_REST
    assert list(FX["compare"]) == ["exact", "within", "held", "refused"]


def test_the_baked_directions_are_the_table_the_fixture_names() -> None:
    raw = TABLE.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == FX["table_sha256"]
    table = json.loads(raw.decode("utf-8"), parse_int=_int)["directions"]
    assert list(DIRECTIONS) == list(table)
    for k, row in table.items():
        assert len(DIRECTIONS[k]) == len(row) == int(k)
        for got, want in zip(DIRECTIONS[k], row, strict=True):
            # by the eight bytes, so a -0.0 written as 0.0 fails here
            assert [bits(v) for v in got] == [bits(v) for v in want], k


@pytest.mark.parametrize("case", FX["cases"], ids=[c["name"] for c in FX["cases"]])
def test_by_links_3d_case(case: dict[str, Any]) -> None:
    assert case["steps"] == 300, "every case runs at the method's own 300 steps"
    want = case["want"]
    if "refused" in want:
        with pytest.raises(ERROR_CLASS[want["refused"]]) as err:
            run(copy.deepcopy(case["input"]))
        assert getattr(err.value, "code", None) == want["refused"]
        return
    got = run(copy.deepcopy(case["input"]))
    assert got["method"] == "by-links-3d"
    assert got["ids"] == want["ids"]
    for key in ("how", "group", "part", "held", "centres"):
        assert got[key] == want[key], key
    assert len(got["points"]) == len(want["points"])
    tolerance = 1e-9 * FX["rest"]
    off = []
    for i, id_ in enumerate(want["ids"]):
        for a in range(3):
            v, w = got["points"][3 * i + a], float(want["points"][3 * i + a])
            if want["held"][i] is True:
                h = float(case["input"]["held"][id_][a])
                same = bits(v) == bits(h) and bits(w) == bits(h)
            elif want["how"][i] in EXACT:
                same = bits(v) == bits(w)
            else:
                same = abs(v - w) <= tolerance
            if not same:
                off.append(
                    f"{id_}.{'xyz'[a]} ({want['how'][i]}{', held' if want['held'][i] else ''}): {v!r}, want {w!r}"
                )
    assert off == [], f"{len(off)} numbers differ"


def test_the_answer_follows_the_handed_order() -> None:
    for name in ("Moppetopia", "held: a saved answer, rounded, with heldUnit"):
        case_input = copy.deepcopy(named(name)["input"])
        base = run(copy.deepcopy(case_input))
        # a fixed shuffle: every third node first, then the rest reversed; the links and the rows reversed
        nodes = case_input["nodes"]
        case_input["nodes"] = [x for i, x in enumerate(nodes) if i % 3 == 0] + [
            x for i, x in enumerate(nodes) if i % 3 != 0
        ][::-1]
        case_input["edges"] = case_input["edges"][::-1]
        if case_input["rows"]:
            case_input["rows"] = case_input["rows"][::-1]
        got = run(case_input)
        assert got["ids"] == [x["id"] for x in case_input["nodes"]]
        at = {id_: j for j, id_ in enumerate(base["ids"])}
        for i, id_ in enumerate(got["ids"]):
            j = at[id_]
            for a in range(3):
                assert bits(got["points"][3 * i + a]) == bits(base["points"][3 * j + a]), f"{name}: {id_}.{'xyz'[a]}"
            assert got["how"][i] == base["how"][j]
            assert got["group"][i] == base["group"][j]
            assert got["part"][i] == base["part"][j]
            assert got["held"][i] == base["held"][j]
        assert got["centres"] == base["centres"]


def test_the_call_changes_none_of_its_inputs() -> None:
    for name in (
        "a small plate taken on the second pass",
        "held: a leaf beside a held leaf under a pinned parent",
        "held: a saved answer, rounded, with heldUnit",
    ):
        case_input = named(name)["input"]
        graph = {"nodes": copy.deepcopy(case_input["nodes"]), "edges": copy.deepcopy(case_input["edges"])}
        elements = copy.deepcopy(case_input["rows"])
        options = copy.deepcopy(options_of(case_input))
        before = copy.deepcopy({"graph": graph, "elements": elements, "options": options})
        layout_by_links_3d(graph, elements, **options)
        assert {"graph": graph, "elements": elements, "options": options} == before, name


def test_the_refusals_and_the_graph() -> None:
    with pytest.raises(TypeError, match="the graph is"):
        layout_by_links_3d({"nodes": []})
    with pytest.raises(HeldTypeError) as err:
        layout_by_links_3d({"nodes": [], "edges": []}, None, held=[[0, 0, 0]])  # type: ignore[arg-type]
    assert err.value.code == "held-not-object"
    assert isinstance(err.value, TypeError)
    with pytest.raises(HeldRangeError) as err2:
        layout_by_links_3d({"nodes": [], "edges": []}, held_unit=-1)
    assert err2.value.code == "held-unit"
    assert isinstance(err2.value, ValueError)
    with pytest.raises(ValueError, match="two nodes share the id"):
        layout_by_links_3d({"nodes": [{"id": "a", "type": "character"}] * 2, "edges": []})


def test_the_names_are_exported() -> None:
    for name in ("layout_by_links_3d", "LayoutByLinks3d", "BY_LINKS_3D_REST"):
        assert name in onlyworlds.__all__
        assert getattr(onlyworlds, name) is not None
    assert BY_LINKS_3D_REST == 60.0
    empty = layout_by_links_3d({"nodes": [], "edges": []})
    assert dict(empty) == {
        "method": "by-links-3d",
        "ids": [],
        "points": [],
        "how": [],
        "group": [],
        "part": [],
        "centres": [],
        "held": [],
    }

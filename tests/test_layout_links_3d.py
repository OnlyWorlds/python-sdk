"""by-links-3d, a 3D layout method read from a world's graph and its Maps and Pins. The method's fixture, as the schema
distribution publishes it (``codegen/schema-dist/profiles/layout-by-links-3d.fixture.json``, vendored with the pin; its
sha256 held here and in the npm SDK's test) gives each case's input and the answer the reference implementation gives;
the fixture's head (``call``, ``compare``) says how a case is run and compared:
  pieces   the graph read into pieces; a ring piece is every other piece of two nodes or more with no node pinned
           (want.how "map") and no node held (in input.held and not pinned)
  exact    every ids, unplaced, how, group, part, held and centres entry; every element not of a ring piece placed
           centre, with or map, or held: each of x, y, z the same double (a zero compared by its value)
  within   every element placed arm or link that is not held, and every coordinate of every element of a ring piece:
           each within 1e-9 of a rest, since those are placed with the runtime's cosine, sine and arcsine
  held     every element answered as held: the very double the case's input.held gives for it
  refused  the call raises with the case's code
The replay walks every case and reports the cases that disagree, by name, before it counts them. The fixture's
``unplaced`` cases are ``unplaced_by_links_3d`` of a graph and a Map's placed ids: the same ids in the same order. Then
the baked directions table against the table the fixture names, the handed order, the inputs left unchanged, and the
exports."""

from __future__ import annotations

import copy
import hashlib
import json
import struct
from pathlib import Path
from typing import Any

import pytest

import onlyworlds
from onlyworlds import (
    BY_LINKS_3D_REST,
    BY_LINKS_3D_VERSION,
    LayoutByLinks3d,
    layout_by_links_3d,
    unplaced_by_links_3d,
)
from onlyworlds._directions import DIRECTIONS
from onlyworlds._layout3d.pieces import FIT, RING_GAP
from onlyworlds.layout_links_3d import HeldRangeError, HeldTypeError

REPO = Path(__file__).resolve().parent.parent
PROFILES = REPO / "codegen" / "schema-dist" / "profiles"
FIXTURE = PROFILES / "layout-by-links-3d.fixture.json"
DIST_TABLE = PROFILES / "layout-by-links-3d.directions.json"
TABLE = REPO / "codegen" / "layout" / "directions.json"
FIXTURE_SHA = "acd6da7252493485cafc24356a84c53656d078872a28c695c0f7554009b6fb2a"
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


def ring_ids(case: dict[str, Any]) -> set[str]:
    """The ids of the case's ring pieces, as the fixture's compare.pieces reads them from the input and the want."""
    nodes, edges, want = case["input"]["nodes"], case["input"]["edges"], case["want"]
    ids = sorted(x["id"] for x in nodes)
    at = {id_: i for i, id_ in enumerate(ids)}
    parent = list(range(len(ids)))

    def find(a: int) -> int:
        while parent[a] != a:
            a = parent[a]
        return a

    for e in edges:
        a, b = at.get(e["source"]), at.get(e["target"])
        if a is None or b is None or a == b:
            continue
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)
    pieces: dict[int, list[str]] = {}
    for v in range(len(ids)):
        pieces.setdefault(find(v), []).append(ids[v])
    # the main piece: the most nodes, a tie to the smaller least id (dicts keep the order of the least id here)
    main = max(pieces.values(), key=len) if pieces else []
    how = dict(zip(want["ids"], want["how"], strict=True))
    held = case["input"].get("held") or {}
    out: set[str] = set()
    for members in pieces.values():
        if members is main or len(members) < 2:
            continue
        if any(how.get(i) == "map" for i in members):
            continue
        if any(i in held and how.get(i) != "map" for i in members):
            continue
        out.update(members)
    return out


def disagreement(case: dict[str, Any]) -> list[str]:
    """What the package answers differently from the case's want, as the fixture's compare says; [] when it agrees."""
    want = case["want"]
    if "refused" in want:
        try:
            run(copy.deepcopy(case["input"]))
        except Exception as err:
            code = getattr(err, "code", None)
            if not isinstance(err, ERROR_CLASS[want["refused"]]) or code != want["refused"]:
                return [f"raised {type(err).__name__} {code!r}, want {want['refused']}"]
            return []
        return [f"answered, want refused {want['refused']}"]
    got = run(copy.deepcopy(case["input"]))
    off: list[str] = []
    if got["method"] != "by-links-3d":
        off.append(f"method {got['method']!r}")
    for key in ("ids", "unplaced", "how", "group", "part", "held", "centres"):
        if got[key] != want[key]:
            off.append(f"{key}: {got[key]!r}, want {want[key]!r}")
    if off or len(got["points"]) != len(want["points"]):
        return off or [f"{len(got['points'])} numbers, want {len(want['points'])}"]
    ring = ring_ids(case)
    tolerance = 1e-9 * FX["rest"]
    for i, id_ in enumerate(want["ids"]):
        for a in range(3):
            v, w = got["points"][3 * i + a], float(want["points"][3 * i + a])
            if want["held"][i] is True:
                h = float(case["input"]["held"][id_][a])
                same = bits(v) == bits(h) and bits(w) == bits(h)
            elif id_ in ring or want["how"][i] not in EXACT:
                same = abs(v - w) <= tolerance
            else:
                same = v == w  # the same double; a zero compared by its value
            if not same:
                how = want["how"][i] + (", held" if want["held"][i] else "") + (", ring" if id_ in ring else "")
                off.append(f"{id_}.{'xyz'[a]} ({how}): {v!r}, want {w!r}")
    return off


def test_the_fixture_is_the_one_both_packages_hold() -> None:
    assert hashlib.sha256(BYTES).hexdigest() == FIXTURE_SHA
    assert FX["method"] == "by-links-3d"
    assert FX["rest"] == BY_LINKS_3D_REST
    assert FX["ring_gap"] == RING_GAP
    assert FX["fit"] == FIT
    assert list(FX["compare"]) == ["pieces", "exact", "within", "held", "refused", "fit", "unplaced"]


def test_the_baked_directions_are_the_table_the_fixture_names() -> None:
    raw = TABLE.read_bytes()
    assert raw == DIST_TABLE.read_bytes(), "codegen/layout/directions.json is the distribution's table, byte for byte"
    assert hashlib.sha256(raw).hexdigest() == FX["table_sha256"]
    table = json.loads(raw.decode("utf-8"), parse_int=_int)["directions"]
    assert list(DIRECTIONS) == list(table)
    for k, row in table.items():
        assert len(DIRECTIONS[k]) == len(row) == int(k)
        for got, want in zip(DIRECTIONS[k], row, strict=True):
            # by the eight bytes, so a -0.0 written as 0.0 fails here
            assert [bits(v) for v in got] == [bits(v) for v in want], k


def test_every_case_of_the_fixture() -> None:
    red: dict[str, list[str]] = {}
    ran = 0
    for case in FX["cases"]:
        assert case["steps"] == 300, "every case runs at the method's own 300 steps"
        off = disagreement(case)
        if off:
            red[case["name"]] = off[:6] + ([f"... {len(off) - 6} more"] if len(off) > 6 else [])
        ran += 1
    assert list(red) == [], json.dumps(red, indent=1)
    assert ran == len(FX["cases"]) == 116


def test_the_answer_follows_the_handed_order() -> None:
    for name in (
        "Moppetopia",
        "held: an earlier answer rounded to whole numbers, with heldUnit",
        "pieces: a main and three equal pieces",
    ):
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
        assert got["ids"] == [x["id"] for x in case_input["nodes"] if x["id"] in base["ids"]]
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
        assert got["unplaced"] == base["unplaced"]


def test_the_call_changes_none_of_its_inputs() -> None:
    for name in (
        "a small plate taken on the second pass",
        "held: a leaf beside a held leaf under a pinned parent",
        "held: an earlier answer rounded to whole numbers, with heldUnit",
        "pieces: a chain pinned at both ends",
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


@pytest.mark.parametrize("case", FX["unplaced"], ids=[c["name"] for c in FX["unplaced"]])
def test_unplaced_case_exactly(case: dict[str, Any]) -> None:
    assert unplaced_by_links_3d(copy.deepcopy(case["graph"]), copy.deepcopy(case["placed"])) == case["want"]


def test_unplaced_reads_a_list_and_a_set_alike_and_passes_over_what_is_no_id() -> None:
    case = next(c for c in FX["unplaced"] if c["name"] == "by-links-3d-a-placed-id-that-is-no-node")
    assert case["want"] == ["s2"]
    graph, placed = case["graph"], case["placed"]
    for given in (list(placed), tuple(placed), set(placed)):
        assert unplaced_by_links_3d(copy.deepcopy(graph), given) == case["want"]
    # a Pin that stands for no element gives no id: None, "" and a number place nothing
    assert unplaced_by_links_3d(copy.deepcopy(graph), [None, "", 7, *placed, *placed]) == case["want"]
    # nothing placed: every node, by id in code point order, whatever order was handed
    ids = [x["id"] for x in graph["nodes"]]
    assert unplaced_by_links_3d(copy.deepcopy(graph), []) == sorted(ids)
    assert ids != sorted(ids)
    one = {"nodes": [{"id": "a", "type": "character"}], "edges": []}
    not_placed: tuple[Any, ...] = ("a", None, {"a": True})
    for bad in not_placed:
        with pytest.raises(TypeError, match=r"^unplaced_by_links_3d: placed is a list or a set of element ids$"):
            unplaced_by_links_3d(copy.deepcopy(one), bad)
    not_graphs: tuple[Any, ...] = ({"nodes": []}, {"edges": []}, {"nodes": {}, "edges": []}, None, [])
    for not_a_graph in not_graphs:
        with pytest.raises(TypeError, match=r"^unplaced_by_links_3d: the graph is \{nodes, edges\}"):
            unplaced_by_links_3d(not_a_graph, [])
    with pytest.raises(ValueError, match=r"^unplaced_by_links_3d: two nodes share the id a$"):
        unplaced_by_links_3d({"nodes": [{"id": "a", "type": "character"}] * 2, "edges": []}, [])
    assert unplaced_by_links_3d({"nodes": [], "edges": []}, []) == []


def test_the_answers_version() -> None:
    # The npm SDK's BY_LINKS_3D_VERSION (src/layout-by-links-3d.ts), raised with this package's in the same change:
    # 2 since the pieces (schema-dist serial 137). Raised whenever a case's answer moves.
    assert BY_LINKS_3D_VERSION == 2


def test_the_names_are_exported() -> None:
    for name in (
        "layout_by_links_3d",
        "unplaced_by_links_3d",
        "LayoutByLinks3d",
        "BY_LINKS_3D_REST",
        "BY_LINKS_3D_VERSION",
    ):
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
        "unplaced": [],
    }

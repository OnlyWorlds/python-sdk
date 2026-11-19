"""The map-space profile's frame reading (schema-dist ``profiles/map-space.md``, rules 13 and 14): every case under
``frame_cases`` in ``codegen/schema-dist/profiles/map-space.fixture.json``, vendored with the distribution, each its own
test, through ``carry_of``. The Map read is the last Map row served with the case's id (or each row ``map_index``
lists); ``maps`` is every row of the case. A number in ``parent_frame`` and ``points`` compares as a 64-bit float,
exactly, with no tolerance; every other part as written, key order included. A missing fixture fails, never skips."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from onlyworlds import carry_of, map_space

REPO = Path(__file__).resolve().parent.parent
FIXTURE = REPO / "codegen" / "schema-dist" / "profiles" / "map-space.fixture.json"
FRAME_CASES_IN_FIXTURE = 66


def load_fixture() -> dict[str, Any]:
    assert FIXTURE.is_file(), f"no map-space fixture at {FIXTURE}"
    doc: dict[str, Any] = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert doc["profile"] == "map-space"
    return doc


CASES: list[dict[str, Any]] = load_fixture().get("frame_cases", [])


def rows_read(case: dict[str, Any]) -> list[Any]:
    if "map_index" in case:
        assert "map" not in case, f"{case['name']}: both map and map_index"
        return [case["elements"][i] for i in case["map_index"]]
    rows = [e for e in case["elements"] if e.get("type") == "map" and e.get("id") == case["map"]]
    assert rows, f"{case['name']}: no Map row with the case's id"
    return [rows[-1]]


def same(got: Any, want: Any, path: str) -> None:
    """Exactly equal: a number as a 64-bit float (a bool is no number), the rest as written, key order held."""
    if isinstance(want, (int, float)) and not isinstance(want, bool):
        assert isinstance(got, (int, float)) and not isinstance(got, bool), f"{path}: a number, got {got!r}"
        assert float(got) == float(want), f"{path}: {got!r} is not {want!r}"
        return
    if isinstance(want, list):
        assert isinstance(got, list) and len(got) == len(want), f"{path}: {got!r} is not {want!r}"
        for i, (g, w) in enumerate(zip(got, want, strict=True)):
            same(g, w, f"{path}[{i}]")
        return
    if isinstance(want, dict):
        assert isinstance(got, dict), f"{path}: an object"
        assert list(got) == list(want), f"{path}: keys {list(got)} are not {list(want)}"
        for k in want:
            same(got[k], want[k], f"{path}.{k}")
        return
    assert got == want and type(got) is type(want), f"{path}: {got!r} is not {want!r}"


def test_the_fixture_holds_every_frame_case() -> None:
    assert len(CASES) == FRAME_CASES_IN_FIXTURE
    assert len({c["name"] for c in CASES}) == FRAME_CASES_IN_FIXTURE


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["name"])
def test_carry_of(case: dict[str, Any]) -> None:
    for row in rows_read(case):
        same(carry_of(row, case["point"], case["elements"]), case["want"], "answer")


def test_every_carried_number_is_a_float() -> None:
    """Every point past the first is carried in 64-bit floats, whatever the fixture's numbers were written as."""
    for case in CASES:
        for row in rows_read(case):
            for p in carry_of(row, case["point"], case["elements"])["points"][1:]:
                assert type(p["x"]) is float and type(p["y"]) is float, case["name"]


def test_map_space_carries_no_frame_key() -> None:
    for case in CASES:
        for m in map_space(case["elements"])["maps"]:
            assert "parent_frame" not in m and "x_parent_frame" not in m, case["name"]


@pytest.mark.parametrize("bad", [[1], [1, 2, 3], ["1", 2], [1, float("nan")], [1, float("inf")], [True, 2], None, "12"])
def test_a_point_that_is_not_two_finite_numbers_is_refused(bad: Any) -> None:
    m = {"type": "map", "id": "a", "width": 10, "height": 10}
    with pytest.raises(TypeError):
        carry_of(m, bad, [m])

"""The map-space profile (schema-dist ``profiles/map-space.md``): every conformance case in
``codegen/schema-dist/profiles/map-space.fixture.json``, vendored with the distribution (the pinned MANIFEST.json holds
its sha256, checked by ``codegen/generate_schema.py --check``), each its own test, through ``map_space``. Key order is
part of the answer, so each case is compared as serialised text as well as by value. A missing fixture fails, never
skips."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from onlyworlds import map_space

REPO = Path(__file__).resolve().parent.parent
FIXTURE = REPO / "codegen" / "schema-dist" / "profiles" / "map-space.fixture.json"
CASES_IN_FIXTURE = 34


def load_fixture() -> dict[str, Any]:
    assert FIXTURE.is_file(), f"no map-space fixture at {FIXTURE}"
    doc: dict[str, Any] = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert doc["profile"] == "map-space"
    assert doc["profile_page"] == "profiles/map-space.md"
    return doc


DOC = load_fixture()
CASES: list[dict[str, Any]] = DOC["cases"]


def text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def test_the_fixture_holds_every_case() -> None:
    assert len(CASES) == CASES_IN_FIXTURE
    assert len({c["name"] for c in CASES}) == CASES_IN_FIXTURE


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["name"])
def test_map_space(case: dict[str, Any]) -> None:
    elements = copy.deepcopy(case["elements"])
    got = map_space(elements)
    assert got == case["want"], case.get("claim")
    assert text(got) == text(case["want"]), "the same answer in another key order"
    assert elements == case["elements"], "map_space moved its input"


def test_a_whole_float_reads_as_its_integer_and_a_boolean_is_no_number() -> None:
    elements: list[dict[str, Any]] = [
        {"type": "map", "id": "m", "width": 10, "height": 10},
        {"type": "zone", "id": "z"},
        {"type": "marker", "id": "a", "zone": "z", "map": "m", "x": 2.0, "y": 3, "z": True, "order": 1.0},
        {"type": "marker", "id": "b", "zone": "z", "map": "m", "x": True, "y": 3},
        {"type": "marker", "id": "c", "zone": "z", "map": "m", "x": 1.5, "y": 3},
        {"type": "marker", "id": "d", "zone": "z", "map": "m", "x": "4", "y": 3},
    ]
    got = map_space(elements)
    assert got["zones"] == [{"zone": "z", "map": "m", "shape": "polygon", "points": [[2, 3, 0]]}]
    assert got["out"] == {"no_point": 3}
    assert all(type(n) is int for n in got["zones"][0]["points"][0])

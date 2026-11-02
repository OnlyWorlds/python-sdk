"""The map-space profile: ``map_space`` on every case of ``tests/fixtures/map-space.fixture.json``, every expected
answer written by hand or, for the whole plan of record, held by a second reader. Key order is part of the answer, so
each case is compared as serialised text as well as by value. A missing fixture fails, never skips."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from onlyworlds import map_space

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "map-space.fixture.json"
FIXTURE_SHA256 = "0aff4e2317e317583750c977cd24463dc8ed56d67252e3cfcccb103ab8b6a2ec"
CASES_IN_FIXTURE = 24


def load_fixture() -> dict[str, Any]:
    assert FIXTURE.is_file(), f"no map-space fixture at {FIXTURE}"
    data = FIXTURE.read_bytes()
    assert hashlib.sha256(data).hexdigest() == FIXTURE_SHA256
    doc: dict[str, Any] = json.loads(data.decode("utf-8"))
    assert doc["profile"] == "map-space"
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

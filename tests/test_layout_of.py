"""The map-space profile's layout reading (schema-dist ``profiles/map-space.md``, rules 8 to 10): every case under
``layout_cases`` in ``codegen/schema-dist/profiles/map-space.fixture.json``, vendored with the distribution (the
pinned MANIFEST.json holds its sha256, checked by ``codegen/generate_schema.py --check``), each its own test, through
``layout_of``. A case names the Map read by id; ``maps`` are the case's Map rows and ``pins`` its Pin rows. Key order
is part of the answer, so each case is compared as serialised text as well as by value. A missing fixture fails,
never skips."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from onlyworlds import layout_of, map_space

REPO = Path(__file__).resolve().parent.parent
FIXTURE = REPO / "codegen" / "schema-dist" / "profiles" / "map-space.fixture.json"
LAYOUT_CASES_IN_FIXTURE = 17


def load_fixture() -> dict[str, Any]:
    assert FIXTURE.is_file(), f"no map-space fixture at {FIXTURE}"
    doc: dict[str, Any] = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert doc["profile"] == "map-space"
    assert doc["profile_page"] == "profiles/map-space.md"
    return doc


DOC = load_fixture()
CASES: list[dict[str, Any]] = DOC["layout_cases"]


def text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def test_the_fixture_holds_every_layout_case() -> None:
    assert len(CASES) == LAYOUT_CASES_IN_FIXTURE
    assert len({c["name"] for c in CASES}) == LAYOUT_CASES_IN_FIXTURE


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["name"])
def test_layout_of(case: dict[str, Any]) -> None:
    elements = copy.deepcopy(case["elements"])
    maps = [e for e in elements if e["type"] == "map"]
    pins = [e for e in elements if e["type"] == "pin"]
    (this,) = [m for m in maps if m["id"] == case["map"]]
    got = layout_of(this, maps, pins)
    assert got == case["want"], case.get("claim")
    assert text(got) == text(case["want"]), "the same answer in another key order"
    assert elements == case["elements"], "layout_of moved its input"


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["name"])
def test_map_space_carries_no_layout_key(case: dict[str, Any]) -> None:
    got = map_space(case["elements"])
    assert list(got) == ["maps", "zones", "pins", "out"]
    assert not any(k.startswith("x_") or k in ("layout", "hand") for row in got["maps"] + got["pins"] for k in row)


def test_rows_are_read_as_the_map_space_reading_reads_them() -> None:
    # Reading H: a row without a string id is no Pin. Reading I: the last row served for an id wins.
    board = {"type": "map", "id": "m", "x_layout": {"method": "hand"}}
    pins: list[Any] = [
        {"type": "pin", "id": "b", "map": "m"},
        {"type": "pin", "id": "", "map": "m"},
        {"type": "pin", "id": 7, "map": "m"},
        {"type": "pin", "map": "m"},
        "not a row",
        {"type": "pin", "id": "a", "map": "m"},
        {"type": "pin", "id": "a", "map": "elsewhere"},
    ]
    assert layout_of(board, [board], pins) == {"layout": "hand", "ground": None, "hand": ["b"]}


def test_a_method_that_is_a_boolean_is_no_layout() -> None:
    for method in (True, False, 1, 1.0, None, ["hand"], {"method": "hand"}):
        this = {"type": "map", "id": "m", "x_layout": {"method": method}}
        pin = {"type": "pin", "id": "p", "map": "m", "x_hand": True}
        assert layout_of(this, [this], [pin]) == {"layout": None, "ground": None, "hand": []}, method


def test_hand_is_in_code_point_order_above_u_ffff() -> None:
    # U+FFFF sorts before U+10000 by code point, after it by UTF-16 unit.
    board = {"type": "map", "id": "m", "x_layout": {"method": "hand"}}
    pins = [{"type": "pin", "id": chr(0x10000), "map": "m"}, {"type": "pin", "id": chr(0xFFFF), "map": "m"}]
    assert layout_of(board, [board], pins)["hand"] == [chr(0xFFFF), chr(0x10000)]


def test_settings_are_never_returned() -> None:
    ground = {"type": "map", "id": "g", "width": 30, "height": 20}
    this = {
        "type": "map",
        "id": "m",
        "x_layout": {"method": "trail-by-place", "settings": {"ground": {"map": "g", "width": 3, "height": 2}}},
    }
    assert layout_of(this, [this, ground], []) == {"layout": "trail-by-place", "ground": "g", "hand": []}


def test_a_ground_map_that_is_no_id_is_no_ground() -> None:
    ground = {"type": "map", "id": "g"}
    for named in ("", 5, True, None, ["g"], {"id": "g"}):
        this = {
            "type": "map",
            "id": "m",
            "x_layout": {"method": "trail-by-place", "settings": {"ground": {"map": named}}},
        }
        assert layout_of(this, [this, ground], [])["ground"] is None, named

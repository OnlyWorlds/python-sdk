"""Which calendar speaks (the calendar profile, serial 147): ``speaking_calendar(world, elements)`` on every case of the
vendored ``profiles/calendar.fixture.json`` that carries ``speaks``, the World's keys beside the world's elements; the
same cases as the npm SDK's ``speakingCalendar`` test."""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

import pytest

from onlyworlds.calendar import WORLD_CALENDAR_KEY, speaking_calendar

FIXTURE = Path(__file__).resolve().parents[1] / "codegen" / "schema-dist" / "profiles" / "calendar.fixture.json"
CASES = [c for c in json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"] if "speaks" in c]


def test_every_case_that_says_which_calendar_speaks_answers_as_written() -> None:
    wrong = []
    for c in CASES:
        try:
            found = speaking_calendar(c["world"], c["elements"])
            got: Any = found.id if found is not None else None
        except Exception as err:  # a case that raises is wrong, never passed over
            got = f"raised {err!r}"
        if got != c["speaks"]:
            wrong.append(f"{c['name']}: gave {got}, the fixture says {c['speaks']}")
    assert wrong == []
    # After the cases, so a red pin never hides a case: serial 147 carries 12.
    assert len(CASES) == 12, f"the fixture holds {len(CASES)} cases that say which calendar speaks, serial 147 has 12"


CAL: dict[str, Any] = {
    "version": 1,
    "grain": "day",
    "bundles": {"months": {"names": ["Frost", "Thaw"], "lengths": [10, 10]}},
}
ELEMENTS: list[dict[str, Any]] = [
    {"id": "a", "name": "A", "atlas_calendar": CAL},
    {"id": "b", "name": "B", "atlas_calendar": json.dumps(CAL)},
]


def _id(world: Mapping[str, Any], elements: Any = ELEMENTS) -> str | None:
    found = speaking_calendar(world, elements)
    return found.id if found is not None else None


def test_the_key_is_x_calendar() -> None:
    assert WORLD_CALENDAR_KEY == "x_calendar"
    assert _id({"x_calendar": "b"}) == "b"  # a calendar stored as a JSON string speaks
    assert _id({}, ELEMENTS[:1]) == "a"  # none named and one calendar: it speaks
    assert _id({}) is None  # none named and two: none
    assert _id({"x_calendar": 7}, ELEMENTS[:1]) is None  # a value that is no id speaks none
    assert _id({"x_calendar": True}, ELEMENTS[:1]) is None


def test_elements_may_be_any_iterable() -> None:
    def gen() -> Iterator[dict[str, Any]]:
        yield from ELEMENTS

    assert _id({"x_calendar": "a"}, gen()) == "a"
    assert _id({}, gen()) is None


@pytest.mark.parametrize("world", [None, "x_calendar", 3, ["a"]])
def test_a_world_that_is_not_a_mapping_is_the_callers_bug(world: Any) -> None:
    with pytest.raises(TypeError):
        speaking_calendar(world, ELEMENTS)

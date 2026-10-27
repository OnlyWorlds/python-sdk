"""The lens profile's date table and ``date_of``: the exported table read back against the table the vendored
profile states (``codegen/schema-dist/profiles/lens.md``, rule 8), the fixture's ``date_table`` and the
schema's own fields, and ``date_of`` on every dated type, the timeless ones and the values that are not a date.
The npm SDK's ``test/date.test.mjs`` holds ``dateOf`` to the same cases."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

import pytest

from onlyworlds import DATE_FIELD, FIELD_KINDS, date_of

PROFILES = Path(__file__).resolve().parent.parent / "codegen" / "schema-dist" / "profiles"


def _profile_table() -> tuple[dict[str, str], list[str]]:
    text = (PROFILES / "lens.md").read_text(encoding="utf-8")
    start = text.index("The **date table**")
    sentence = text[start : text.index("are timeless", start)]
    dated: dict[str, str] = {}
    for field, types in re.findall(r"`([a-z_]+)` \(([A-Za-z, ]+)\)", sentence):
        for t in types.split(","):
            dated[t.strip().lower()] = field
    found = re.search(r"no date field \(([A-Za-z, ]+)\)", sentence)
    assert found is not None
    return dated, [t.strip().lower() for t in found.group(1).split(",")]


def test_date_field_is_the_profiles_table() -> None:
    dated, timeless = _profile_table()
    assert len(dated) == 12 and len(timeless) == 10
    assert dict(DATE_FIELD) == dated
    fixture = json.loads((PROFILES / "lens.fixture.json").read_text(encoding="utf-8"))
    assert dict(DATE_FIELD) == fixture["date_table"]
    assert sorted([*dated, *timeless]) == sorted(FIELD_KINDS)
    for kind, field in DATE_FIELD.items():
        assert FIELD_KINDS[kind][field] == "integer", f"{kind}.{field}"
    with pytest.raises(TypeError):
        DATE_FIELD["object"] = "start_date"  # type: ignore[index]


def test_date_of_reads_the_whole_number_zero_included() -> None:
    for kind, field in DATE_FIELD.items():
        assert date_of({"type": kind, field: 1204}) == 1204, kind
        assert date_of({"type": kind, field: 0}) == 0, kind
        assert date_of({"type": kind, field: -40}) == -40, kind
    assert date_of({"type": " Event ", "start_date": 7}) == 7
    assert date_of({"type": "EVENT", "start_date": 7}) == 7
    assert date_of({"type": "event", "start_date": 7.0}) == 7


@pytest.mark.parametrize("value", [None, "12", 1.5, True, math.nan, [3], {"year": 3}])
def test_date_of_is_none_for_what_is_not_a_date(value: Any) -> None:
    assert date_of({"type": "event", "start_date": value}) is None


def test_date_of_is_none_for_the_timeless_and_the_untyped() -> None:
    _, timeless = _profile_table()
    for kind in timeless:
        assert date_of({"type": kind, "start_date": 5, "birth_date": 5, "date": 5}) is None, kind
    assert date_of({"type": "event", "birth_date": 5}) is None
    assert date_of({"type": "event"}) is None
    assert date_of({"start_date": 5}) is None
    assert date_of({"type": 3, "start_date": 5}) is None
    assert date_of({"type": "event", "known_of": True, "name": "A stub"}) is None
    for value in (None, "event", 3, [{"type": "event", "start_date": 1}]):
        assert date_of(value) is None

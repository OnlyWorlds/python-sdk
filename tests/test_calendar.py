"""The calendar profile (schema-dist ``profiles/calendar.md``): ``onlyworlds.calendar`` on every conformance
case of the vendored ``profiles/calendar.fixture.json``, the npm SDK's own kernel, lens and version-2 tests
the fixture does not cover (``test/calendar-kernel.test.mjs``, ``calendar-lens.test.mjs``,
``calendar-v2.test.mjs``), and one test for each place where Python's default reading differs from
JavaScript's and the module reads as the SDK does."""

from __future__ import annotations

import copy
import json
import math
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

import pytest

from onlyworlds.calendar import (
    CALENDAR_FIELD,
    CALENDAR_SUPERTYPE,
    absolute_year,
    approx_year_length,
    breakdown_step,
    era_for_step,
    floor_div,
    floor_mod,
    format_duration,
    format_mid_label,
    format_step,
    format_year_label,
    intercalary_in_year,
    is_leap_year,
    is_parse_error,
    month_start_steps,
    parse_date,
    read_calendar_config,
    read_calendar_value,
    resolve_calendar_lens,
    validate_calendar_config,
    weekday_for_step,
    world_calendars,
    year_length,
    year_start_step,
)

FIXTURE = Path(__file__).resolve().parents[1] / "codegen" / "schema-dist" / "profiles" / "calendar.fixture.json"


def load_fixture() -> dict[str, Any]:
    doc: dict[str, Any] = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return doc


def case(name: str) -> dict[str, Any]:
    value: dict[str, Any] = next(c for c in load_fixture()["cases"] if c["name"] == name)["value"]
    return value


def as_json(value: Any) -> str:
    """One canonical JSON text: Python's ``==`` holds ``True == 1`` and ``1 == 1.0``, which JSON does not."""
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def step_of(r: Any) -> int:
    assert not is_parse_error(r), r
    step: int = r["step"]
    return step


# ---- The fixture ----


def test_the_vendored_fixture_reads_every_case_as_written() -> None:
    doc = load_fixture()
    assert doc["profile"] == "atlas_calendar"
    cases = doc["cases"]
    # Counted, so a fixture that stops loading (or loses cases) fails here rather than passing on nothing.
    assert len(cases) == 64
    assert sum(c["valid"] for c in cases) == 30 and sum(not c["valid"] for c in cases) == 34
    assert sum(len(c.get("steps", [])) for c in cases) == 198
    assert len(next(c for c in cases if c["name"] == "v2-except-chain-gregorian")["steps"]) == 29
    failed = []
    replayed = 0
    for c in cases:
        cfg = read_calendar_value(c["value"])
        if (cfg is not None) != c["valid"]:
            failed.append(f"{c['name']}: read as {'valid' if cfg is not None else 'not a calendar'}")
            continue
        for s in c.get("steps", []):
            assert cfg is not None
            b = breakdown_step(cfg, s["step"])
            got = {
                "absYear": b.abs_year,
                "year": b.year,
                "era": b.era["name"] if b.era is not None else None,
                "month": b.month,
                "monthName": b.month_name,
                "day": b.day,
                "intercalary": b.intercalary,
                "weekday": b.weekday,
            }
            words = format_step(cfg, s["step"])
            if words != s["words"] or as_json(got) != as_json(s["breakdown"]):
                failed.append(f"{c['name']} step {s['step']}: {words!r} {got} for {s['words']!r} {s['breakdown']}")
            replayed += 1
    assert failed == []
    assert replayed == 198


def test_the_reader_returns_the_value_itself_unknown_keys_kept() -> None:
    value = {**case("months-plain-free-week"), "x_tool": {"kept": True}}
    assert read_calendar_config(value) is value and read_calendar_value(value) is value
    assert read_calendar_value(json.dumps(value)) == value


# ---- The kernel's tests (calendar-kernel.test.mjs) ----

KIRROWMOSS: dict[str, Any] = {
    "version": 1,
    "grain": "day",
    "eras": [
        {"name": "Kingsreckoning", "abbrev": "KR", "start": -131400, "end": -3600, "restart": True, "closed": True},
        {"name": "Occupation Count", "abbrev": "OC", "start": -3600, "restart": True, "closed": True},
        {"name": "Freehold Tally", "abbrev": "FT", "start": 0, "restart": True},
    ],
    "bundles": {
        "months": {
            "names": [
                "Sowmarch",
                "Thistlewane",
                "Greening",
                "Suncrest",
                "Longhay",
                "Ashfall",
                "Rootdeep",
                "Frostwake",
                "Bellmoot",
                "Hearthtide",
                "Graytide",
                "Coldmark",
            ],
            "lengths": [30, 28, 32, 30, 31, 29, 30, 28, 32, 30, 29, 31],
        },
        "week": {"length": 6, "names": ["Ondel", "Tresk", "Mireth", "Aldun", "Volk", "Hearth"], "mode": "free"},
    },
    "format": "{day} {month}, Year {year} {era}",
}
VESSACH: dict[str, Any] = {
    "version": 1,
    "grain": "year",
    "eras": [
        {"name": "First Age", "abbrev": "FA", "start": -20000, "end": -10000, "restart": True, "year_base": 0},
        {"name": "Third Age", "abbrev": "TA", "start": 0, "restart": True, "year_base": 0},
    ],
    "format": "{year} {era}",
}
DUNE: dict[str, Any] = {
    "version": 1,
    "grain": "year",
    "eras": [
        {"name": "Before Guild", "abbrev": "B.G.", "start": 0, "direction": "down", "restart": True},
        {"name": "After Guild", "abbrev": "A.G.", "start": 0, "restart": True, "year_base": 0},
    ],
    "format": "{year} {era}",
}
HARPTOS: dict[str, Any] = {
    "version": 1,
    "grain": "day",
    "eras": [{"name": "Dalereckoning", "abbrev": "DR", "start": 0, "restart": True, "year_base": 0}],
    "bundles": {
        "months": {
            "names": [
                "Hammer",
                "Alturiak",
                "Ches",
                "Tarsakh",
                "Mirtul",
                "Kythorn",
                "Flamerule",
                "Eleasis",
                "Eleint",
                "Marpenoth",
                "Uktar",
                "Nightal",
            ],
            "lengths": [30] * 12,
        },
        "week": {
            "length": 10,
            "names": ["1st", "2nd", "3rd", "4th", "5th", "6th", "7th", "8th", "9th", "10th"],
            "mode": "nested",
        },
    },
    "intercalary": [
        {"name": "Midwinter", "after_month": 1},
        {"name": "Greengrass", "after_month": 3},
        {"name": "Midsummer", "after_month": 7},
        {"name": "Shieldmeet", "after_month": 7, "every_years": 4},
        {"name": "Highharvestide", "after_month": 9},
        {"name": "Feast of the Moon", "after_month": 11},
    ],
    "format": "{day} {month}, {year} {era}",
    "format_intercalary": "{intercalary}, {year} {era}",
}
SHIRE: dict[str, Any] = {
    "version": 1,
    "grain": "day",
    "eras": [{"name": "Shire Reckoning", "abbrev": "S.R.", "start": 0, "restart": True}],
    "bundles": {
        "months": {
            "names": [
                "Afteryule",
                "Solmath",
                "Rethe",
                "Astron",
                "Thrimidge",
                "Forelithe",
                "Afterlithe",
                "Wedmath",
                "Halimath",
                "Winterfilth",
                "Blotmath",
                "Foreyule",
            ],
            "lengths": [30] * 12,
        },
        "week": {
            "length": 7,
            "names": ["Sterday", "Sunday", "Monday", "Trewsday", "Hevensday", "Mersday", "Highday"],
            "mode": "free",
        },
    },
    "intercalary": [
        {"name": "2 Yule", "after_month": 0},
        {"name": "1 Lithe", "after_month": 6},
        {"name": "Mid-year's Day", "after_month": 6, "in_week": False},
        {"name": "Overlithe", "after_month": 6, "every_years": 4, "in_week": False},
        {"name": "2 Lithe", "after_month": 6},
        {"name": "1 Yule", "after_month": 12},
    ],
    "format": "{day} {month}, S.R. {year}",
    "format_intercalary": "{intercalary}, S.R. {year}",
}
MINIMAL: dict[str, Any] = {
    "version": 1,
    "grain": "year",
    "eras": [{"name": "Third Age", "abbrev": "TA", "start": 0, "restart": True, "year_base": 0}],
    "format": "{year} {era}",
}
ALL = [KIRROWMOSS, VESSACH, DUNE, HARPTOS, SHIRE, MINIMAL]


def era_abbrev(cfg: Mapping[str, Any], step: int) -> Any:
    era = era_for_step(cfg, step)
    return era["abbrev"] if era is not None else None


def test_floor_division_floors_toward_negative_infinity() -> None:
    assert (floor_div(-400, 360), floor_div(400, 360), floor_div(-360, 360)) == (-2, 1, -1)
    assert (floor_mod(-1, 4), floor_mod(-4, 4), floor_mod(-8, 4)) == (3, 0, 0)


def test_the_absolute_year_is_zero_based() -> None:
    assert [absolute_year(KIRROWMOSS, s) for s in (0, 359, 360, -1, -360, -361)] == [0, 0, 1, -1, -1, -2]
    assert (absolute_year(DUNE, 10191), absolute_year(DUNE, -108)) == (10191, -108)


def test_leap_years_astride_year_0() -> None:
    assert [is_leap_year(y, 4) for y in (0, 4, -4, -1, 3)] == [True, True, True, False, False]
    assert [year_length(HARPTOS, y) for y in (0, 1, 4, -4)] == [366, 365, 366, 366]
    assert [year_start_step(HARPTOS, y) for y in (0, 1, 2, -1, -4)] == [0, 366, 731, -365, -365 * 3 - 366]
    for y in (-5, -4, -1, 0, 1, 3, 4, 100):
        assert absolute_year(HARPTOS, year_start_step(HARPTOS, y)) == y
        assert absolute_year(HARPTOS, year_start_step(HARPTOS, y + 1) - 1) == y


def test_eras_by_domain_gaps_and_down_eras() -> None:
    assert [era_abbrev(KIRROWMOSS, s) for s in (0, -1, -3600, -3601)] == ["FT", "OC", "OC", "KR"]
    assert [era_abbrev(VESSACH, s) for s in (-20000, -10001, -10000, -5000, 0)] == ["FA", "FA", None, None, "TA"]
    assert (format_step(VESSACH, -5000), format_step(VESSACH, -30000)) == ("-5000", "-30000")
    assert (era_abbrev(DUNE, 0), era_abbrev(DUNE, -1)) == ("A.G.", "B.G.")
    assert [format_step(DUNE, s) for s in (-1, -108, 0, 10191)] == ["1 B.G.", "108 B.G.", "0 A.G.", "10191 A.G."]
    assert format_step(KIRROWMOSS, 0) == "1 Sowmarch, Year 1 FT"
    assert [format_step(VESSACH, s) for s in (0, 1204, -19912)] == ["0 TA", "1204 TA", "88 FA"]
    common = {
        "version": 1,
        "grain": "year",
        "eras": [{"name": "Common Era", "abbrev": "CE", "start": -500, "restart": False}],
    }
    assert (format_step(common, 454), format_step(common, -100)) == ("454 CE", "-100 CE")


def test_kirrowmoss_irregular_months_and_free_week() -> None:
    assert format_step(KIRROWMOSS, 7603) == "14 Thistlewane, Year 22 FT"
    assert step_of(parse_date(KIRROWMOSS, "14 Thistlewane, Year 22 FT")) == 7603
    b, c = breakdown_step(KIRROWMOSS, 30), breakdown_step(KIRROWMOSS, 58)
    assert (b.month_name, b.day, c.month_name, c.day) == ("Thistlewane", 1, "Greening", 1)
    assert [weekday_for_step(KIRROWMOSS, s) for s in (0, 5, 6, 30, -1)] == [
        "Ondel",
        "Hearth",
        "Ondel",
        "Ondel",
        "Hearth",
    ]


def test_harptos_days_outside_the_months_leap_and_tendays() -> None:
    assert format_step(HARPTOS, 30) == "Midwinter, 0 DR"
    b = breakdown_step(HARPTOS, 30)
    assert (b.intercalary, b.month, b.day) == ("Midwinter", None, None)
    y1372, y1373 = year_start_step(HARPTOS, 1372), year_start_step(HARPTOS, 1373)
    assert format_step(HARPTOS, y1372 + 212) == "Midsummer, 1372 DR"
    assert format_step(HARPTOS, y1372 + 213) == "Shieldmeet, 1372 DR"
    assert format_step(HARPTOS, y1373 + 213) == "1 Eleasis, 1373 DR"
    assert format_step(HARPTOS, step_of(parse_date(HARPTOS, "Shieldmeet 1372"))) == "Shieldmeet, 1372 DR"
    assert is_parse_error(parse_date(HARPTOS, "Shieldmeet 1373"))
    assert [weekday_for_step(HARPTOS, s) for s in (0, 9, 10, 30)] == ["1st", "10th", "1st", None]


def test_the_shire_weekday_lock() -> None:
    def weekday(year: int, month: str, day: int) -> str | None:
        return weekday_for_step(SHIRE, step_of(parse_date(SHIRE, f"{day} {month} {year}")))

    first = weekday(1, "Afteryule", 1)
    assert all(weekday(y, "Afteryule", 1) == first for y in (2, 3, 4, 5, 9, 100, 1401))
    mid = weekday(1, "Halimath", 22)
    assert all(weekday(y, "Halimath", 22) == mid for y in (2, 4, 5, 1401))
    assert weekday_for_step(SHIRE, step_of(parse_date(SHIRE, "Mid-year's Day 1401"))) is None
    assert weekday_for_step(SHIRE, step_of(parse_date(SHIRE, "2 Yule 1401"))) is not None


def test_format_tokens() -> None:
    assert format_step({**MINIMAL, "format": "{day} {month}, {year} {era} {frob}"}, 454) == "454 TA {frob}"
    assert format_step({**MINIMAL, "format": "{day} {month}, {year} {era}"}, 454) == "454 TA"
    assert format_step({**MINIMAL, "format": "{year} {era} (step {step})"}, 454) == "454 TA (step 454)"
    assert format_step({"version": 1, "grain": "year", "eras": MINIMAL["eras"]}, 454) == "454 TA"


def test_the_parser() -> None:
    assert step_of(parse_date(KIRROWMOSS, "454")) == 454 and step_of(parse_date(KIRROWMOSS, "-480")) == -480
    assert step_of(parse_date(KIRROWMOSS, "14 thistlewane, year 22 ft")) == 7603
    assert step_of(parse_date(KIRROWMOSS, "Year 22 FT")) == 21 * 360
    assert is_parse_error(parse_date(KIRROWMOSS, "Thistlewane 22"))  # a day with no year and no now: never guessed
    assert format_step(KIRROWMOSS, step_of(parse_date(KIRROWMOSS, "Thistlewane 400"))) == "1 Thistlewane, Year 400 FT"
    assert step_of(parse_date(KIRROWMOSS, "Thistlewane 14", now=7900)) == 7603
    assert step_of(parse_date(KIRROWMOSS, "Year 12")) == 11 * 360
    assert step_of(parse_date(KIRROWMOSS, "Year 2", now=-3000)) == -3600 + 360
    assert step_of(parse_date(DUNE, "108 B.G.")) == -108
    assert is_parse_error(parse_date(KIRROWMOSS, "the fifth of never")) and is_parse_error(parse_date(KIRROWMOSS, ""))
    with pytest.raises(TypeError):
        parse_date(KIRROWMOSS, "12", Now=5)  # type: ignore[call-arg]  # an unknown option, as the SDK refuses one


def test_format_parse_format_is_stable() -> None:
    for cfg in (KIRROWMOSS, HARPTOS, SHIRE, DUNE, VESSACH):
        for n in (-3601, -108, -1, 0, 30, 213, 7603, 500596):
            words = format_step(cfg, n)
            assert format_step(cfg, step_of(parse_date(cfg, words, now=0))) == words, (cfg["eras"][0]["name"], n)


def test_validation() -> None:
    bad = {**KIRROWMOSS, "bundles": {**KIRROWMOSS["bundles"], "year": {"steps": 360}}}
    assert any("year.steps" in e for e in validate_calendar_config(bad))
    overlap = {
        "version": 1,
        "grain": "year",
        "eras": [{"name": "A", "start": 0, "end": 100}, {"name": "B", "start": 50}],
    }
    assert any("overlap" in e for e in validate_calendar_config(overlap))
    floating = {"version": 1, "grain": "year", "intercalary": [{"name": "Floating Day", "after_month": 0}]}
    assert "Festival days need months" in validate_calendar_config(floating)
    for cfg in ALL:
        assert validate_calendar_config(cfg) == []


def test_surface_helpers() -> None:
    assert format_year_label(KIRROWMOSS, 7603) == "22 FT"
    assert (format_year_label(DUNE, -108), format_year_label(VESSACH, -5000)) == ("108 B.G.", "-5000")
    assert (approx_year_length(KIRROWMOSS), approx_year_length(HARPTOS), approx_year_length(MINIMAL)) == (
        360,
        365,
        None,
    )
    assert format_duration(KIRROWMOSS, 360 * 19) == "19 years"
    assert format_duration(KIRROWMOSS, 540) == "1.5 years"
    assert (format_duration(KIRROWMOSS, 14), format_duration(KIRROWMOSS, 1)) == ("14 days", "1 day")
    assert format_duration(MINIMAL, 19) == "19 years"
    assert format_duration({"version": 1, "grain": "day", "step_name": "sol"}, 14) == "14 sols"


def test_mid_labels_and_month_starts() -> None:
    """Not in the SDK's tests; the comparison against its built package covers them too."""
    assert format_mid_label(KIRROWMOSS, 7603) == "14 Thistlewane 22"
    assert format_mid_label(HARPTOS, 30) == "Midwinter 0"
    assert format_mid_label(MINIMAL, 454) == "454 TA"
    rows = month_start_steps(HARPTOS, 0)
    assert rows[:3] == [
        {"month": 1, "name": "Hammer", "step": 0},
        {"month": 2, "name": "Alturiak", "step": 31},
        {"month": 3, "name": "Ches", "step": 61},
    ]
    assert month_start_steps(MINIMAL, 0) == []


def test_the_defensive_read() -> None:
    for value in (
        None,
        "a string",
        {"version": 3, "grain": "day"},
        {"version": 1},
        {"version": 1, "grain": "day", "bundles": {"months": {"names": ["a"], "lengths": [1, 2]}}},
        {"version": 1, "grain": "day", "eras": [{"name": "X"}]},
    ):
        assert read_calendar_config(value) is None, value
    for falsy in (False, 0, ""):
        assert read_calendar_config({"version": 1, "grain": "day", "eras": falsy}) is None
        assert read_calendar_config({"version": 1, "grain": "day", "intercalary": falsy}) is None

    def era(**e: Any) -> dict[str, Any]:
        return {"version": 1, "grain": "year", "eras": [{"name": "A", "start": 0, **e}]}

    assert read_calendar_config(era()) is not None and read_calendar_config(era(year_base=0)) is not None
    for e in ({"start": 0.5}, {"end": 10.5}, {"year_base": "1"}, {"year_base": 2}):
        assert read_calendar_config(era(**e)) is None, e

    def named(months: list[Any], week: Any = None) -> dict[str, Any]:
        bundles: dict[str, Any] = {"months": {"names": months, "lengths": [1, 1]}}
        return {"version": 1, "grain": "day", "bundles": {**bundles, **({"week": week} if week else {})}}

    assert read_calendar_config(named(["a", "b"])) is not None
    assert read_calendar_config(named(["a", 2])) is None
    assert read_calendar_config(named(["a", "b"], {"length": 2, "names": ["x", None]})) is None
    for cfg in ALL:
        assert read_calendar_config(json.loads(json.dumps(cfg))) is not None


def test_a_down_era_has_no_year_zero_even_with_a_mid_year_pivot() -> None:
    months = {"names": ["Frost", "Thaw"], "lengths": [10, 10]}

    def cal(pivot: int) -> dict[str, Any]:
        eras = [
            {"name": "Before", "abbrev": "BG", "start": pivot, "direction": "down"},
            {"name": "After", "abbrev": "AG", "start": pivot},
        ]
        return {"version": 1, "grain": "day", "bundles": {"months": months}, "eras": eras}

    assert (format_step(cal(0), -1), format_step(cal(0), -21)) == ("10 Thaw, 1 BG", "10 Thaw, 2 BG")
    assert [format_step(cal(5), s) for s in (4, 0, -1, 5)] == [
        "5 Frost, 1 BG",
        "1 Frost, 1 BG",
        "10 Thaw, 2 BG",
        "6 Frost, 1 AG",
    ]
    for pivot in (0, 5):
        for step in range(-55, 66):
            assert step_of(parse_date(cal(pivot), format_step(cal(pivot), step))) == step


def test_a_date_the_typed_era_does_not_hold_is_refused() -> None:
    eras = [
        {"name": "Before Gate", "abbrev": "BG", "start": 5, "direction": "down"},
        {"name": "After Gate", "abbrev": "AG", "start": 5},
    ]
    cfg = {
        "version": 1,
        "grain": "day",
        "bundles": {"months": {"names": ["Frost", "Thaw"], "lengths": [10, 10]}},
        "eras": eras,
    }
    assert parse_date(cfg, "10 Thaw, 1 BG") == {"error": "not a date in Before Gate"}
    assert is_parse_error(parse_date(cfg, "3 Frost, 0 BG"))
    assert step_of(parse_date(cfg, "3 Frost, 1 BG")) == 2 and step_of(parse_date(cfg, "10 Thaw, 1 AG")) == 19


def test_equal_starts_up_over_down_then_the_later_in_the_list() -> None:
    def ups(a: str, b: str) -> dict[str, Any]:
        return {
            "version": 1,
            "grain": "year",
            "eras": [{"name": a, "start": 0, "end": 10}, {"name": b, "start": 0, "end": 10}],
        }

    def name(cfg: Mapping[str, Any], step: int) -> Any:
        era = era_for_step(cfg, step)
        return era["name"] if era is not None else None

    assert (name(ups("A", "B"), 3), name(ups("B", "A"), 3)) == ("B", "A")
    down = {"start": 10, "end": 0, "direction": "down"}
    assert name({"version": 1, "grain": "year", "eras": [{"name": "D1", **down}, {"name": "D2", **down}]}, 3) == "D2"
    nulled = [
        {"name": "Down", "start": 0, "end": -10, "direction": "down"},
        {"name": "Up", "start": 0, "end": 10, "direction": None},
    ]
    assert name({"version": 1, "grain": "year", "eras": nulled}, 0) == "Up"


def test_malformed_step_sizes_are_refused() -> None:
    base = {"version": 1, "grain": "day"}
    one = {"months": {"names": ["a"], "lengths": [30]}}
    for cfg in (
        {**base, "bundles": {"months": {"names": ["Frost", "Thaw"], "lengths": [-30, 10]}}},
        {**base, "bundles": {"months": {"names": ["Frost"], "lengths": [0]}}},
        {**base, "bundles": {"months": {"names": ["Frost"], "lengths": [2.5]}}},
        {**base, "bundles": {"months": {"names": ["Frost"], "lengths": ["30"]}}},
        {**base, "bundles": {"year": {"steps": -5}}},
        {**base, "bundles": {"year": {"steps": 0}}},
        {**base, "bundles": {"year": {"steps": math.inf}}},
        {**base, "bundles": {"year": {}}},
        {**base, "bundles": {"week": {"length": 0, "names": []}}},
        {**base, "bundles": {"week": {"length": 3, "names": "abc"}}},
        {**base, "bundles": one, "intercalary": [{"name": "Leap", "after_month": 1, "every_years": 0}]},
        {**base, "bundles": one, "intercalary": [{"name": "Leap", "after_month": 1, "every_years": -4}]},
    ):
        assert read_calendar_config(cfg) is None, cfg


class Tripwire(Mapping[str, Any]):
    """A config whose ``bundles`` read raises after ``limit`` reads: a hang turns into a failure."""

    def __init__(self, bundles: dict[str, Any], limit: int = 1_000_000) -> None:
        self._data: dict[str, Any] = {"version": 1, "grain": "day", "bundles": bundles}
        self._limit = limit
        self.reads = 0

    def __getitem__(self, key: str) -> Any:
        if key == "bundles":
            self.reads += 1
            if self.reads > self._limit:
                raise RuntimeError("runaway loop: absolute_year never exits")
        return self._data[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)


def test_the_kernel_terminates_on_a_config_that_slips_the_reader() -> None:
    neg_month = {"months": {"names": ["Frost", "Thaw"], "lengths": [-30, 10]}}
    assert math.isfinite(absolute_year(Tripwire(neg_month), 100))
    assert isinstance(format_step(Tripwire(copy.deepcopy(neg_month)), 100), str)
    assert math.isfinite(absolute_year(Tripwire({"year": {"steps": -5}}), 100))
    assert isinstance(format_step(Tripwire({"year": {"steps": -5}}), 100), str)


def test_the_correction_bound_never_bites_a_valid_calendar_far_from_zero() -> None:
    for step in (0, 1, -1, 10**9, -(10**9), 10**12, -(10**12)):
        y = absolute_year(HARPTOS, step)
        assert year_start_step(HARPTOS, y) <= step < year_start_step(HARPTOS, y + 1)
    dense = {
        "version": 1,
        "grain": "day",
        "bundles": {"months": {"names": ["a"], "lengths": [1]}},
        "intercalary": [
            {"name": "F", "after_month": 1, "every_years": 1},
            {"name": "G", "after_month": 0, "every_years": 3},
        ],
    }
    for step in (0, 7, -7, 5_000_000, -5_000_000):
        y = absolute_year(dense, step)
        assert year_start_step(dense, y) <= step < year_start_step(dense, y + 1)


# ---- Version 2 (calendar-v2.test.mjs, beside the fixture) ----


def test_version_2_leap_keys_change_the_leap_years_and_version_1_ignores_them() -> None:
    greg = case("v2-except-chain-gregorian")
    leap = next(i for i in greg["intercalary"] if i.get("every_years"))
    # 1900 (index 1899) is not a leap year, 2000 (index 1999) is, 1999 is not: offset 1, except [100, 400].
    assert [intercalary_in_year(greg, leap, y) for y in (1899, 1999, 1998, 2003)] == [False, True, False, True]
    assert (year_length(greg, 1899), year_length(greg, 1999)) == (365, 366)
    v1 = {**greg, "version": 1}
    assert read_calendar_config(v1) is not None
    assert (intercalary_in_year(v1, leap, 1899), intercalary_in_year(v1, leap, 1900)) == (False, True)
    assert year_length(v1, 1900) == 366
    assert "version 2" in " ".join(validate_calendar_config(v1))


@pytest.mark.parametrize("name", ["v2-except-chain-gregorian", "v2-offset-harptos", "v2-except-offset-small"])
def test_the_closed_form_year_starts_equal_the_sum_of_year_lengths(name: str) -> None:
    cfg = case(name)
    start = 0
    for y in range(1300):
        assert year_start_step(cfg, y) == start, y
        start += year_length(cfg, y)
    start = 0
    for y in range(-1, -1300, -1):
        start -= year_length(cfg, y)
        assert year_start_step(cfg, y) == start, y
    # The search seeds on the mean year, except chain included: a seed that ignored it lands outside.
    for step in (-(10**12), -500000, -146097, -1, 0, 1, 146097, 730484, 1000000, 10**12):
        y = absolute_year(cfg, step)
        assert year_start_step(cfg, y) <= step < year_start_step(cfg, y + 1), step


def test_a_version_2_date_parses_back_to_its_step() -> None:
    greg = case("v2-except-chain-gregorian")
    for step in (0, 59, 365, 730484, 730484 + 59, -1, -366):
        assert step_of(parse_date(greg, format_step(greg, step))) == step


def test_version_2_refuses_a_leap_rule_it_cannot_read() -> None:
    base = {"version": 2, "grain": "day", "bundles": {"months": {"names": ["A", "B"], "lengths": [10, 10]}}}

    def with_leap(**extra: Any) -> dict[str, Any]:
        return {**base, "intercalary": [{"name": "L", "after_month": 1, "every_years": 4, **extra}]}

    for extra in ([100, 250], [400, 100], [4], [6], 100, [100.5]):
        assert read_calendar_config(with_leap(**{"except": extra})) is None, extra
        assert validate_calendar_config(with_leap(**{"except": extra})) != [], extra
    for offset in (0.5, "1"):
        assert read_calendar_config(with_leap(offset=offset)) is None and validate_calendar_config(
            with_leap(offset=offset)
        )
    assert read_calendar_config({**base, "intercalary": [{"name": "L", "after_month": 1, "offset": 1}]}) is None
    assert read_calendar_config(with_leap(**{"except": [100, 400], "offset": -3})) is not None
    assert read_calendar_config(with_leap(**{"except": None, "offset": None})) is not None
    assert read_calendar_config({**base, "version": 3}) is None


def test_an_up_era_runs_past_a_down_era_listed_after_it() -> None:
    after = {"name": "After", "abbrev": "AF", "start": 0}
    before = {"name": "Before", "abbrev": "BF", "start": 0, "direction": "down"}
    cfg: dict[str, Any] = {"version": 1, "grain": "year", "eras": [after, before]}
    assert (era_for_step(cfg, 5) or {}).get("name") == "After"
    assert (format_step(cfg, 5), format_step(cfg, -1)) == ("6 AF", "1 BF")
    assert format_step({**cfg, "eras": [before, after]}, 5) == "6 AF"
    later = {**cfg, "eras": [after, before, {"name": "Third", "abbrev": "TH", "start": 10}]}
    assert ((era_for_step(later, 9) or {}).get("name"), (era_for_step(later, 10) or {}).get("name")) == (
        "After",
        "Third",
    )


# ---- A world's calendars (calendar-lens.test.mjs) ----

CONFIG: dict[str, Any] = {
    "version": 1,
    "grain": "year",
    "eras": [{"name": "Third Age", "abbrev": "TA", "start": 0}],
    "format": "{year} {era}",
}


def test_world_calendars_detects_by_the_field_never_by_supertype() -> None:
    elements: list[dict[str, Any]] = [
        {
            "id": "c1",
            "type": "construct",
            "name": "Imperial Reckoning",
            "supertype": "calendar",
            CALENDAR_FIELD: CONFIG,
        },
        {"id": "c2", "type": "construct", "name": "The Old Calendar", "supertype": "Calendar"},
        {"id": "c3", "type": "phenomenon", "name": "Tide Count", CALENDAR_FIELD: CONFIG},
    ]
    assert [c.id for c in world_calendars(elements)] == ["c1", "c3"]
    assert (CALENDAR_FIELD, CALENDAR_SUPERTYPE) == ("atlas_calendar", "calendar")


def test_world_calendars_reads_a_json_string_and_skips_the_malformed() -> None:
    elements: list[dict[str, Any]] = [
        {"id": "s1", "name": "Stringy", CALENDAR_FIELD: json.dumps(CONFIG)},
        {"id": "s2", "name": "Broken", CALENDAR_FIELD: "{not json"},
        {"id": "s3", "name": "Wrong shape", CALENDAR_FIELD: {"version": 9}},
    ]
    assert [c.id for c in world_calendars(elements)] == ["s1"]
    found = world_calendars(e for e in [{"id": "u1", "name": "", CALENDAR_FIELD: CONFIG}])  # any iterable
    assert found[0].name == "(unnamed calendar)"


def test_read_calendar_value_reads_objects_and_json_strings_alike() -> None:
    cfg = read_calendar_value(CONFIG)
    assert cfg is not None and cfg["grain"] == "year"
    assert read_calendar_value(json.dumps(CONFIG)) == CONFIG
    for junk in ("{not json", None, 42):
        assert read_calendar_value(junk) is None


def test_resolve_calendar_lens() -> None:
    elements = [{"id": "c1", "type": "construct", "name": "Imperial", CALENDAR_FIELD: CONFIG}]
    chosen_one = resolve_calendar_lens(elements, "c1")
    assert chosen_one is not None and chosen_one.name == "Imperial"
    for chosen in ("gone", None):
        assert resolve_calendar_lens(elements, chosen) is None
    assert resolve_calendar_lens([], "c1") is None
    only = resolve_calendar_lens(elements, fallback_to_only=True)  # never chosen: the only one
    assert only is not None and only.name == "Imperial"
    assert resolve_calendar_lens(elements, None, fallback_to_only=True) is None  # "no calendar" stays
    two = [*elements, {"id": "c2", "name": "Guild", CALENDAR_FIELD: CONFIG}]
    assert resolve_calendar_lens(two, fallback_to_only=True) is None  # never a guess
    assert resolve_calendar_lens(elements) is None  # opt-in
    with pytest.raises(TypeError):
        resolve_calendar_lens(elements, fallbackToOnly=True)  # type: ignore[call-arg]


# ---- Where Python's default reading differs from JavaScript's: read as the SDK reads ----


def test_trim_is_javascripts_white_space() -> None:
    """``str.strip()`` keeps U+FEFF and takes U+001C and U+0085; ``trim()`` is the other way round."""
    bom, fs, nel = chr(0xFEFF), chr(0x1C), chr(0x85)
    assert step_of(parse_date(KIRROWMOSS, f"{bom}12{bom}")) == 12
    assert parse_date(KIRROWMOSS, f"{fs}12") == {"error": f'unrecognized: "{fs}12"'}
    assert parse_date(KIRROWMOSS, f"{nel}12") == {"error": f'unrecognized: "{nel}12"'}
    assert format_duration({"version": 1, "grain": "day", "step_name": f"{bom}sol{bom}"}, 14) == "14 sols"
    assert format_duration({"version": 1, "grain": "day", "step_name": f"{fs}sol"}, 14) == f"14 {fs}sols"


def test_white_space_in_the_collapse_is_javascripts() -> None:
    """``\\s`` around an empty token: U+FEFF closes up, U+001C stays (Python's ``re`` reads them the other way)."""
    cfg = {"version": 1, "grain": "day", "bundles": {"months": {"names": ["M"], "lengths": [3]}}}
    template = "{weekday}" + chr(0xFEFF) + "{day}" + chr(0x1C) + "{weekday}{month}"
    assert format_step({**cfg, "format": template}, 0) == "1" + chr(0x1C) + " M"


def test_digits_are_ascii() -> None:
    """``\\d`` is 0 to 9; Python's ``re`` and ``int()`` also take other scripts' digits."""
    arabic_indic = chr(0x661) + chr(0x662)
    assert parse_date(KIRROWMOSS, arabic_indic) == {"error": f'unrecognized: "{arabic_indic}"'}


def test_a_bare_number_is_read_as_parseint_reads_it() -> None:
    """``int()`` takes ``1_000``, ``+12`` and padding and refuses more than 4300 digits; ``parseInt`` on
    ``-?[0-9]+`` takes any length, and the step is a double."""
    assert parse_date(KIRROWMOSS, "1_000") == {"error": 'unrecognized: "1_000"'}
    assert parse_date(KIRROWMOSS, "+12") == {"error": 'unrecognized: "+12"'}
    assert step_of(parse_date(KIRROWMOSS, "0" * 400 + "5")) == 5
    assert step_of(parse_date(KIRROWMOSS, "9" * 30)) == int(float("9" * 30))  # 1e30, not 999...9
    assert step_of(parse_date(KIRROWMOSS, "9" * 309)) == math.inf
    assert step_of(parse_date(KIRROWMOSS, "1" + "0" * 4400)) == math.inf


def test_numbers_are_doubles() -> None:
    """A step past 2**53 is the nearest double, past the double range infinity, and prints as JavaScript prints it."""
    year = {"version": 1, "grain": "year"}
    assert breakdown_step(year, 2**53 + 1).step == 2**53
    assert format_step(year, 2**53 + 1) == "9007199254740992"
    assert format_step(year, 10**22) == "1e+22" and format_step(year, 10**21) == "1e+21"
    assert format_step(year, 10**20) == "100000000000000000000"
    b = breakdown_step(year, 10**400)
    assert (b.step, b.abs_year, format_step(year, 10**400)) == (math.inf, math.inf, "Infinity")
    assert format_duration(year, 0.005) == "0.01 years"  # Math.round: halves up, 0.5 -> 1, where round() goes to even


def test_floor_division_by_zero_is_not_an_error() -> None:
    """``Math.floor(a / 0)`` is an infinity and ``a % 0`` NaN, where Python's ``//`` and ``%`` raise."""
    assert floor_div(7, 0) == math.inf and floor_div(-7, 0) == -math.inf
    assert math.isnan(floor_mod(7, 0)) and math.isnan(floor_div(0, 0))
    assert floor_div(2**60 + 1, 1) == 2**60  # the argument is a double first


def test_a_sum_adds_left_to_right() -> None:
    """``reduce((a, b) => a + b, 0)``; Python's ``sum()`` of floats compensates and can answer otherwise."""
    lengths = [2**53 - 1, 2**53 - 1, 2**53 - 1, 2**52 + 1]
    cfg = {"version": 1, "grain": "day", "bundles": {"months": {"names": ["a", "b", "c", "d"], "lengths": lengths}}}
    assert read_calendar_value(cfg) is not None
    assert approx_year_length(cfg) == 31525197391593468 != int(sum(map(float, lengths)))


def test_string_length_counts_utf16_code_units() -> None:
    """Longer names are eaten first by ``.length``: an astral character counts two, where ``len()`` counts one."""
    smile = chr(0x1F600)
    cfg = {
        "version": 1,
        "grain": "day",
        "bundles": {"months": {"names": ["M"], "lengths": [5]}},
        "intercalary": [{"name": "ab", "after_month": 1}, {"name": smile + "a", "after_month": 1}],
    }
    assert parse_date(cfg, f"{smile}a ab 5") == {"error": 'unrecognized: "ab"'}


def test_javascript_truthiness() -> None:
    """An empty object is there (``{}`` is falsy in Python); 0, "" and false read as absent; a bool is no number."""
    good = {"version": 1, "grain": "day"}
    assert read_calendar_value({**good, "bundles": {"months": {}}}) is None
    for absent in (0, "", False):
        assert read_calendar_value({**good, "bundles": {"months": absent}}) is not None
    assert read_calendar_value({**good, "version": True}) is None
    assert read_calendar_value({**good, "version": 2.0}) is not None  # 2.0 is the number 2
    cfg = {**good, "bundles": {"months": {"names": ["A"], "lengths": [True]}}}
    assert read_calendar_value(cfg) is None
    # An era abbrev that is an empty list prints as "" without closing up; one that is a number prints it.
    assert format_step({"version": 1, "grain": "year", "eras": [{"name": "Age", "abbrev": [], "start": 0}]}, 3) == "4"
    numbered = {"version": 1, "grain": "year", "eras": [{"name": "Age", "abbrev": 5, "start": 0}]}
    assert format_step(numbered, 3) == "4 5"
    assert step_of(parse_date(numbered, "Age 3")) == 2
    with pytest.raises(TypeError):  # the number reached as a word: ``(5).toLowerCase`` throws there
        parse_date(numbered, "3 x")


def test_json_is_read_as_json_parse_reads_it() -> None:
    """No NaN or Infinity (``json.loads`` takes both); an integer of any length (``int()`` refuses 4300 digits);
    any depth (``json.loads`` stops at Python's C recursion limit, V8 does not)."""
    text = json.dumps({"version": 1, "grain": "day"})
    assert read_calendar_value(text) is not None
    assert read_calendar_value(text[:-1] + ', "x": NaN}') is None
    assert read_calendar_value(text[:-1] + ', "x": -Infinity}') is None
    big = read_calendar_value(text[:-1] + ', "x": ' + "1" * 5000 + "}")
    assert big is not None and dict(big).get("x") == math.inf
    deep = read_calendar_value(text[:-1] + ', "x": ' + '{"a": [' * 3000 + "1" + "]}" * 3000 + "}")
    assert deep is not None
    assert read_calendar_value(text[:-1] + ', "x": ' + "[" * 3000 + "1," + "]" * 3000 + "}") is None
    assert read_calendar_value(chr(0xFEFF) + text) is None and read_calendar_value(" \n" + text + "\r\n") is not None
    assert read_calendar_value(text.replace('"day"', "'day'")) is None

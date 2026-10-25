"""LegendKeeper calendars into the calendar profile's ``atlas_calendar`` (onlyworlds.legendkeeper).

``fixtures/legendkeeper/api-calendars.json`` is the API's answer to ``GET /projects/{id}/calendars``
on a Pro project, read live on 2026-10-25: the six preset calendars every LegendKeeper project
carries (Gregorian, Harptos, Eberron, Exandria, Greyhawk, Scrolls). The configs made from five of
them agree with LegendKeeper's own breakdown of 466 chosen minutes (Gregorian 93, Harptos 100,
Eberron 85, Exandria 79, Greyhawk 109) read back from events made on each, replayed through the
TypeScript SDK's ``breakdownStep`` (4.76.0, which reads the profile's version 2); Scrolls is
refused, with its reasons. The projects below are made up around them.
"""

from __future__ import annotations

import copy
import gzip
import json
import subprocess
import sys
import uuid
from itertools import pairwise
from pathlib import Path
from typing import Any

import pytest

from onlyworlds import read_folder
from onlyworlds.legendkeeper import (
    LEGENDKEEPER_NAMESPACE,
    ImportReport,
    RecordedSource,
    _calendar_config,
    import_legendkeeper,
)

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "codegen" / "schema-dist"
LINT = DIST / "walk" / "lint_folder.py"
FIX = Path(__file__).resolve().parent / "fixtures" / "legendkeeper"
PID = "calendar0"
P = f"/projects/{PID}"
REALM = "realm001"
DAY = 24 * 60


def page() -> dict[str, Any]:
    answer: dict[str, Any] = json.loads((FIX / "api-calendars.json").read_text(encoding="utf-8"))["answer"]
    return answer


def preset(name: str) -> dict[str, Any]:
    return copy.deepcopy(next(c for c in page()["data"] if c["name"] == name))


def eid(*parts: str) -> str:
    return str(uuid.uuid5(LEGENDKEEPER_NAMESPACE, ":".join(("legendkeeper", PID, *parts))))


# --- the profile's "Not a calendar" rules (profiles/calendar.md), as a reader applies them ----------


def whole(v: Any, least: int | None = None) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and (least is None or v >= least)


def at(value: Any, key: str) -> Any:
    """``value[key]`` when value is an object, else None (a JavaScript reader's ``value?.key``)."""
    return value.get(key) if isinstance(value, dict) else None


def not_a_calendar(value: Any) -> list[str]:
    """Every rule of the profile's "Not a calendar" list the value breaks (version 2, schema-dist
    serial 68); [] when a reader takes it. Replayed against the vendored fixture's 64 cases."""
    if isinstance(value, str):  # the same object as a JSON string, strict JSON only
        try:
            value = json.loads(value)
        except ValueError:
            return ["a string that is not JSON"]
    if not isinstance(value, dict):
        return ["not an object"]
    out = []
    if value.get("version") not in (1, 2):
        out.append("version is not 1 or 2")
    if not isinstance(value.get("grain"), str):
        out.append("grain is not a string")
    bundles = value.get("bundles")
    months = at(bundles, "months")
    if months not in (None, False, 0, ""):  # a falsy value reads as absent, as in the SDK's reader
        names, lengths = at(months, "names"), at(months, "lengths")
        if not isinstance(names, list) or not isinstance(lengths, list) or len(names) != len(lengths) or not names:
            out.append("months' names and lengths are not lists of one non-zero length")
        elif not all(isinstance(n, str) for n in names):
            out.append("a month name is not a string")
        elif not all(whole(n, 1) for n in lengths):
            out.append("a month length is not a whole number from 1")
    year = at(bundles, "year")
    if year is not None and not whole(at(year, "steps"), 1):
        out.append("bundles.year.steps is not a whole number from 1")
    week = at(bundles, "week")
    if week is not None:
        if not whole(at(week, "length"), 1):
            out.append("bundles.week.length is not a whole number from 1")
        wnames = at(week, "names")
        if not isinstance(wnames, list) or not all(isinstance(n, str) for n in wnames):
            out.append("bundles.week.names is not a list of strings")
    if "eras" in value and value["eras"] is not None:
        eras = value["eras"]
        if not isinstance(eras, list):
            out.append("eras is not a list")
        else:
            for e in eras:
                if not isinstance(e, dict) or not isinstance(e.get("name"), str) or not whole(e.get("start")):
                    out.append("an era lacks a string name or a whole start")
                elif any(e.get(k) is not None and not whole(e[k]) for k in ("end", "year_base")):
                    out.append("an era's end or year_base is not a whole number")
    if "intercalary" in value and value["intercalary"] is not None:
        inter = value["intercalary"]
        if not isinstance(inter, list):
            out.append("intercalary is not a list")
        else:
            for i in inter:
                if not isinstance(i, dict) or not isinstance(i.get("name"), str) or not whole(i.get("after_month")):
                    out.append("an intercalary entry lacks a string name or a whole after_month")
                elif i.get("every_years") is not None and not whole(i["every_years"], 1):
                    out.append("an every_years is not a whole number from 1")
                elif i.get("every_years") is None and (i.get("offset") is not None or i.get("except") is not None):
                    out.append("an offset or except on an entry with no every_years")
                elif i.get("offset") is not None and not whole(i["offset"]):
                    out.append("an offset is not a whole number")
                elif i.get("except") is not None:
                    chain = [i.get("every_years"), *i["except"]] if isinstance(i["except"], list) else []
                    if not chain[1:] or not all(whole(n, 1) for n in chain):
                        out.append("an except is not a list of whole numbers")
                    elif any(b <= a or b % a for a, b in pairwise(chain)):
                        out.append("an except is not ascending, each a multiple of the one before")
    return out


def version_fits(value: dict[str, Any]) -> bool:
    """The writer's side of the version row: 2 exactly when an intercalary entry carries ``except``
    or ``offset``, so a reader of version 1 alone refuses it whole rather than misreading it."""
    raw = value.get("intercalary")
    entries: list[Any] = raw if isinstance(raw, list) else []
    needs_2 = any(isinstance(i, dict) and ("except" in i or "offset" in i) for i in entries)
    return value.get("version") == (2 if needs_2 else 1)


def test_the_helper_reads_the_vendored_fixture_as_the_profile_does() -> None:
    """The calendar fixture beside the profile (serial 68: 64 cases, 30 calendars and 34 refusals):
    the helper refuses exactly the values the fixture marks not valid."""
    fixture = json.loads((DIST / "profiles" / "calendar.fixture.json").read_text(encoding="utf-8"))
    cases = fixture["cases"]
    assert len(cases) == 64 and sum(not c["valid"] for c in cases) == 34
    wrong = [c["name"] for c in cases if bool(not_a_calendar(c["value"])) == c["valid"]]
    assert wrong == []


def test_the_helper_refuses_what_the_profile_refuses() -> None:
    good: dict[str, Any] = {"version": 1, "grain": "day", "bundles": {"months": {"names": ["A"], "lengths": [3]}}}
    assert not_a_calendar(good) == []
    four = {"name": "Leap", "after_month": 1, "every_years": 4}
    assert not_a_calendar({**good, "version": 2, "intercalary": [{**four, "except": [100, 400], "offset": 1}]}) == []
    assert version_fits(good) and not version_fits({**good, "version": 2})  # nothing that needs it
    assert not version_fits({**good, "intercalary": [{**four, "offset": 1}]})  # version 1 with a version 2 key
    bad = [
        {**good, "version": 3},
        {**good, "version": 2, "intercalary": [{**four, "except": [4]}]},
        {**good, "version": 2, "intercalary": [{**four, "except": [100, 250]}]},
        {**good, "version": 2, "intercalary": [{**four, "offset": 0.5}]},
        {**good, "grain": None},
        {**good, "bundles": {"months": {"names": ["A"], "lengths": [0]}}},
        {**good, "bundles": {"months": {"names": [], "lengths": []}}},
        {**good, "eras": False},
        {**good, "eras": [{"name": "E", "start": 0.5}]},
        {**good, "intercalary": [{"name": "Leap", "after_month": 1, "every_years": 0}]},
        {**good, "bundles": {**good["bundles"], "week": {"length": 7, "names": [1]}}},
    ]
    for value in bad:
        assert not_a_calendar(value), value


# --- the six presets ---------------------------------------------------------------------------

EBERRON = {
    "version": 1,
    "grain": "day",
    "step_name": "day",
    "bundles": {
        "months": {
            "names": [
                "Zarantyr",
                "Olarune",
                "Therendor",
                "Eyre",
                "Dravago",
                "Nymm",
                "Lharvion",
                "Barrakas",
                "Rhaan",
                "Sypheros",
                "Aryth",
                "Vult",
            ],
            "lengths": [28] * 12,
        },
        "week": {"length": 7, "names": ["Sul", "Mol", "Zol", "Wir", "Zor", "Far", "Sar"], "mode": "free"},
    },
    "eras": [{"name": "Year of the Kingdom", "abbrev": "YK", "start": 0, "year_base": 1}],
    "format": "{month} {day}, {year} {era}",
}
EXANDRIA = {
    "version": 1,
    "grain": "day",
    "step_name": "day",
    "bundles": {
        "months": {
            "names": [
                "Horisal",
                "Misuthar",
                "Dualahei",
                "Thunsheer",
                "Unndilar",
                "Brussendar",
                "Sydenstar",
                "Fessuran",
                "Quen'pillar",
                "Cuersaar",
                "Duscar",
            ],
            "lengths": [29, 30, 30, 31, 28, 31, 32, 29, 27, 29, 32],
        },
        "week": {
            "length": 7,
            "names": ["Miresen", "Grissen", "Whelsen", "Conthsen", "Folsen", "Yulisen", "Da'sen"],
            "mode": "free",
        },
    },
    "eras": [{"name": "Post-Divergence", "abbrev": "PD", "start": 0, "year_base": 0}],  # a year 0
    "format": "{month} {day}, {year} {era}",
}
GREYHAWK = {
    "version": 1,
    "grain": "day",
    "step_name": "day",
    "bundles": {
        "months": {
            "names": [
                "Fireseek",
                "Readying",
                "Coldeven",
                "Growfest",
                "Planting",
                "Flocktime",
                "Wealsun",
                "Richfest",
                "Reaping",
                "Goodmonth",
                "Harvester",
                "Brewfest",
                "Patchwall",
                "Ready'reat",
                "Sunsebb",
                "Needfest",
            ],
            "lengths": [28, 28, 28, 7, 28, 28, 28, 7, 28, 28, 28, 7, 28, 28, 28, 7],  # the festivals are months
        },
        "week": {
            "length": 7,
            "names": ["Starday", "Sunday", "Moonday", "Godsday", "Waterday", "Earthday", "Freeday"],
            "mode": "free",
        },
    },
    "eras": [{"name": "Common Year", "abbrev": "CY", "start": 0, "year_base": 1}],
    "format": "{month} {day}, {year} {era}",
}
GREGORIAN = {
    "version": 2,  # its leap entry carries except and offset
    "grain": "day",
    "step_name": "day",
    "bundles": {
        "months": {
            "names": [
                "January",
                "February",
                "March",
                "April",
                "May",
                "June",
                "July",
                "August",
                "September",
                "October",
                "November",
                "December",
            ],
            "lengths": [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31],
        },
        "week": {  # minute 0 is a Monday (epochWeekday 1)
            "length": 7,
            "names": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
            "mode": "free",
        },
    },
    "intercalary": [{"name": "Leap Day", "after_month": 2, "every_years": 4, "except": [100, 400], "offset": 1}],
    "eras": [
        {"name": "Before Common Era", "abbrev": "BCE", "start": 0, "end": -525600, "direction": "down", "year_base": 1},
        {"name": "Common Era", "abbrev": "CE", "start": 0, "year_base": 1},
    ],
    "format": "{month} {day}, {year} {era}",
}
HARPTOS = {
    "version": 2,  # its leap entry carries an offset (no year 0)
    "grain": "day",
    "step_name": "day",
    "bundles": {
        "months": {
            "names": [
                "Hammer",
                "Alturiak",
                "Ches",
                "Tarsak",
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
            "names": ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"],
            "mode": "nested",
        },
    },
    "intercalary": [
        {"name": "Midwinter", "after_month": 1},
        {"name": "Greengrass", "after_month": 4},
        {"name": "Midsummer", "after_month": 7},
        {"name": "Shieldsmeet", "after_month": 7, "every_years": 4, "offset": 1},  # Midsummer's second day
        {"name": "Highharvestide", "after_month": 9},
        {"name": "The Feast of the Moon", "after_month": 11},
    ],
    "eras": [{"name": "Dale Reckoning", "abbrev": "DR", "start": 0, "year_base": 1}],
    "format": "{month} {day}, {year}",
}


def test_each_preset_is_exact_or_refused_with_its_reasons() -> None:
    made = {c["name"]: _calendar_config(c) for c in page()["data"]}
    assert sorted(made) == ["Eberron", "Exandria", "Gregorian", "Greyhawk", "Harptos", "Scrolls"]
    assert made["Eberron"] == (EBERRON, [])
    assert made["Exandria"] == (EXANDRIA, [])
    assert made["Greyhawk"] == (GREYHAWK, [])
    assert made["Gregorian"] == (GREGORIAN, [])
    assert made["Harptos"] == (HARPTOS, [])
    assert made["Scrolls"] == (
        None,
        [
            "era 'Second Era' restarts its years at minute 1536298560 (unwitnessed)",
            "era 'Third Era' restarts its years at minute 2006496000 (unwitnessed)",
            "era 'Fourth Era' restarts its years at minute 2234232000 (unwitnessed)",
        ],
    )


@pytest.mark.parametrize(
    "config",
    [EBERRON, EXANDRIA, GREYHAWK, GREGORIAN, HARPTOS],
    ids=["Eberron", "Exandria", "Greyhawk", "Gregorian", "Harptos"],
)
def test_the_exact_configs_are_calendars_by_the_profile(config: dict[str, Any]) -> None:
    assert not_a_calendar(config) == [] and version_fits(config)


def test_the_week_turns_so_its_first_name_is_the_weekday_at_minute_0() -> None:
    cal = preset("Eberron")
    cal["epochWeekday"] = 3  # minute 0 is a Wir
    cfg, why = _calendar_config(cal)
    assert why == [] and cfg is not None
    assert cfg["bundles"]["week"] == {
        "length": 7,
        "names": ["Wir", "Zor", "Far", "Sar", "Sul", "Mol", "Zol"],
        "mode": "free",
    }
    cal["weekResetsEachMonth"] = True  # restarts each month: the names as given
    nested, _ = _calendar_config(cal)
    assert nested is not None and nested["bundles"]["week"]["names"][0] == "Sul"
    assert nested["bundles"]["week"]["mode"] == "nested"


def test_a_negative_era_is_a_down_era_listed_first() -> None:
    """Before serial 68 an open era ran to the next era's start, down eras too: listed after the up
    era at 0, the down era ended that era where it began. Listed first, every reader reads it."""
    cal = preset("Eberron")
    cal["negativeEra"] = {"id": "bk", "name": "Before the Kingdom", "abbr": "BK", "startsAt": -100 * 336 * DAY}
    cfg, why = _calendar_config(cal)
    assert why == [] and cfg is not None
    assert cfg["eras"] == [
        {"name": "Before the Kingdom", "abbrev": "BK", "start": 0, "end": -33600, "direction": "down", "year_base": 1},
        {"name": "Year of the Kingdom", "abbrev": "YK", "start": 0, "year_base": 1},
    ]
    assert not_a_calendar(cfg) == []


def leap(interval: str, offset: int = 0) -> dict[str, Any]:
    return {"name": "Leap", "month": 1, "interval": interval, "offset": offset, "day": 0, "intercalary": False}


def test_a_leap_rule_reads_the_year_as_shown() -> None:
    """LegendKeeper reads the rule on the year as shown (index + 1 with no year 0): offset 1 then,
    and version 2; with a year 0 the rule is the year index's, version 1 with no offset."""
    cal = preset("Eberron")  # hasZeroYear false
    cal["leapDays"] = [leap("4")]
    cfg, why = _calendar_config(cal)
    assert why == [] and cfg is not None and cfg["version"] == 2
    assert cfg["intercalary"] == [{"name": "Leap", "after_month": 2, "every_years": 4, "offset": 1}]  # after Olarune
    cal["hasZeroYear"] = True
    cfg, why = _calendar_config(cal)
    assert why == [] and cfg is not None and cfg["version"] == 1
    assert cfg["intercalary"] == [{"name": "Leap", "after_month": 2, "every_years": 4}]
    assert cfg["eras"][0]["year_base"] == 0
    cal["hasZeroYear"], cal["leapDays"] = False, [leap("1")]
    cfg, why = _calendar_config(cal)  # every year: nothing to count, so no offset and version 1
    assert why == [] and cfg is not None and cfg["version"] == 1
    assert cfg["intercalary"] == [{"name": "Leap", "after_month": 2, "every_years": 1}]


def test_a_leap_chain_alternates_on_off_on() -> None:
    cal = preset("Eberron")
    cal["hasZeroYear"] = True
    cal["leapDays"] = [leap("!100,400,4")]  # any order: read smallest first
    cfg, why = _calendar_config(cal)
    assert why == [] and cfg is not None and cfg["version"] == 2
    assert cfg["intercalary"] == [{"name": "Leap", "after_month": 2, "every_years": 4, "except": [100, 400]}]
    refused = {
        "4,100": "does not alternate on, off, on from its smallest term",
        "!4,100": "does not alternate on, off, on from its smallest term",
        "4,!10": "has a term that is not a larger multiple of the one before",
        "4,!8,!16": "does not alternate on, off, on from its smallest term",
        "4,!100,250": "has a term that is not a larger multiple of the one before",
        "4+1": "carries an offset of its own (unwitnessed)",
        "400,!100+2,4": "carries an offset of its own (unwitnessed)",
        "four": "is not a list of whole numbers of years",
        "0": "is not a list of whole numbers of years",
    }
    for rule, said in refused.items():
        cal["leapDays"] = [leap(rule)]
        assert _calendar_config(cal) == (None, [f"leap day 'Leap': its rule {rule!r} {said}"]), rule
    cal["leapDays"] = [leap("4", offset=2)]  # the leap day's own offset: unprobed
    assert _calendar_config(cal) == (None, ["leap day 'Leap': its rule '4' carries an offset of its own (unwitnessed)"])


def test_a_leap_day_on_a_one_day_month_follows_that_day() -> None:
    """Harptos's Shieldmeet lengthens Midsummer, a one-day month: the leap day comes after it. With
    a year 0 the single-term rule stays version 1, with no offset."""
    cal = preset("Harptos")
    cal["hasZeroYear"] = True
    cfg, why = _calendar_config(cal)
    assert why == [] and cfg is not None and cfg["version"] == 1
    assert cfg["intercalary"] == [
        {"name": "Midwinter", "after_month": 1},
        {"name": "Greengrass", "after_month": 4},
        {"name": "Midsummer", "after_month": 7},
        {"name": "Shieldsmeet", "after_month": 7, "every_years": 4},
        {"name": "Highharvestide", "after_month": 9},
        {"name": "The Feast of the Moon", "after_month": 11},
    ]
    assert cfg["bundles"]["week"]["mode"] == "nested" and len(cfg["bundles"]["months"]["names"]) == 12


def test_a_leap_day_on_a_regular_month_comes_before_the_festival_after_it() -> None:
    """The other side of the same rule: a lengthened regular month's leap day is its last day, so
    a one-day month that follows comes after it, at the same after_month."""
    cal = preset("Eberron")
    cal["hasZeroYear"] = True
    cal["months"].insert(2, {"id": "fest", "name": "Fest", "isIntercalary": True, "length": 1, "interval": 1})
    cal["leapDays"] = [{"name": "Leap", "month": 1, "interval": "4", "offset": 0, "day": 0, "intercalary": False}]
    cfg, why = _calendar_config(cal)
    assert why == [] and cfg is not None
    assert cfg["intercalary"] == [
        {"name": "Leap", "after_month": 2, "every_years": 4},
        {"name": "Fest", "after_month": 2},
    ]


def test_the_rest_of_the_rules() -> None:
    cal = preset("Eberron")
    cal["months"][3]["interval"] = 2
    assert _calendar_config(cal)[1] == ["month 'Eyre' comes every 2 years"]
    cal = preset("Eberron")
    cal["positiveEras"][0]["resetMode"] = "calendar"
    assert _calendar_config(cal)[1] == ["era 'Year of the Kingdom' restarts months and days"]
    cal = preset("Eberron")
    cal["positiveEras"][0]["startsAt"] = 60
    assert _calendar_config(cal)[1] == [
        "the first era 'Year of the Kingdom' starts at minute 60, not 0",
        "era 'Year of the Kingdom' starts inside a day",
    ]
    cal = preset("Exandria")  # a year 0: a later era counting on from the epoch is exact
    cal["positiveEras"].append({"name": "Later", "abbr": "L", "startsAt": 10 * DAY, "resetMode": "none"})
    cfg, why = _calendar_config(cal)
    assert (
        why == []
        and cfg is not None
        and cfg["eras"][1] == {"name": "Later", "abbrev": "L", "start": 10, "restart": False}
    )
    cal["hasZeroYear"] = False
    assert "era 'Later' counts its years on from the epoch, which has no year 0" in _calendar_config(cal)[1]
    cal = preset("Eberron")
    cal["positiveEras"][0].update(hideAbbr=True)
    cal["positiveEras"][0].pop("abbr")
    assert (_calendar_config(cal)[0] or {})["eras"][0]["abbrev"] == ""
    cal["positiveEras"][0]["hideAbbr"] = False
    assert (_calendar_config(cal)[0] or {})["eras"][0]["abbrev"] == "AD"
    assert _calendar_config({"name": "broken", "months": [{"name": "A"}]})[1][0].startswith("not read as a calendar")


@pytest.mark.parametrize(
    ("template", "want"),
    [
        ("MMMM D^, YYYY E", "{month} {day}, {year} {era}"),
        ("D^ MMMM, E YYYY", "{day} {month}, {era} {year}"),
        ("DDDD, [the] DD [of] MMMM, YYYY EE", "{weekday}, the {day} of {month}, {year} {era}"),
        ("MMM D, YYYY", None),  # a short month name: no twin, the profile's default
        ("DDD YYYY", None),
        ("MMMM D, YYYY HH:mm", None),
        ("[unclosed MMMM", None),
    ],
)
def test_the_day_format(template: str, want: str | None) -> None:
    cal = preset("Eberron")
    cal["format"]["day"] = template
    cfg = _calendar_config(cal)[0]
    assert cfg is not None and cfg.get("format") == want


# --- a project: timelines on the calendars ------------------------------------------------------


def ev(eid_: str, start: int, end: int | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {"id": eid_, "type": "event", "name": f"Event {eid_}", "start": start}
    if end is not None:
        out["end"] = end
    return out


def project(timelines: list[tuple[str, str, list[dict[str, Any]]]], calendars: Any = None) -> dict[str, Any]:
    """One resource holding a timeline document per (document id, calendar id, events)."""
    docs = [{"id": did, "name": f"History {did}", "type": "time", "calendarId": cid} for did, cid, _ in timelines]
    row: dict[str, Any] = {"id": REALM, "name": "The Realm", "parentId": None, "tags": [], "aliases": []}
    row["isHidden"] = False
    out: dict[str, Any] = {
        P: {"id": PID, "name": "The Realm"},
        f"{P}/resources": {"data": [{**row, "documents": docs}], "hasMore": False, "nextCursor": None},
        f"{P}/resources/{REALM}": {**row, "documents": [{**d, "isHidden": False} for d in docs], "properties": []},
        f"{P}/calendars": page() if calendars is None else calendars,
    }
    for did, _, events in timelines:
        out[f"{P}/resources/{REALM}/docs/{did}/lanes"] = {"data": [], "hasMore": False}
        out[f"{P}/resources/{REALM}/docs/{did}/events"] = {"data": events, "hasMore": False}
    return out


def run(tmp: Path, ans: dict[str, Any], name: str = "world") -> tuple[Path, ImportReport]:
    out = tmp / name
    return out, import_legendkeeper(RecordedSource(ans), PID, out)


def by_lk_id(out: Path) -> dict[str, dict[str, Any]]:
    return {
        e.body["x_legendkeeper_id"]: e.body for e in read_folder(out).elements.values() if "x_legendkeeper_id" in e.body
    }


def world(out: Path) -> dict[str, Any]:
    w: dict[str, Any] = json.loads((out / "world.json").read_text(encoding="utf-8"))
    return w


EVENTS = [ev("zero", 0), ev("minus", -1), ev("span", DAY - 1, 3 * DAY + 5), ev("back", -DAY - 1), ev("one", DAY)]


def test_an_exact_calendar_dates_its_events_in_days(tmp_path: Path) -> None:
    out, report = run(tmp_path, project([("tl1", "eberron", EVENTS)]))
    els = by_lk_id(out)
    dates = {k: (els[k].get("start_date"), els[k].get("end_date")) for k in ("zero", "minus", "span", "back", "one")}
    assert dates == {"zero": (0, None), "minus": (-1, None), "span": (0, 3), "back": (-2, None), "one": (1, None)}
    assert els["span"]["x_legendkeeper_start"] == {"minutes": DAY - 1}  # the minutes stay beside
    assert els["span"]["x_legendkeeper_end"] == {"minutes": 3 * DAY + 5}
    assert els["minus"]["x_legendkeeper_calendar"] == "eberron"
    cal = els["eberron"]
    assert (cal["type"], cal["supertype"], cal["name"]) == ("construct", "calendar", "Eberron")
    assert cal["id"] == eid("calendar", "eberron")
    assert cal["atlas_calendar"] == EBERRON
    assert cal["x_legendkeeper_calendar"] == preset("Eberron")  # whole, so a push back is exact
    assert cal["description"] == preset("Eberron")["description"]
    assert world(out)["time_basic_unit"] == "day"
    assert report.counts["construct"] == 1  # the five calendars no timeline names make nothing
    notes = "\n".join(report.notes)
    assert "calendar 'Eberron' (eberron): a Construct (supertype calendar) carrying atlas_calendar" in notes
    assert "5 events dated, start_date and end_date the minutes divided by 1440 (a day), rounded down" in notes
    assert "5 calendars no timeline names, not made: 'Gregorian', 'Harptos', 'Exandria', 'Greyhawk', 'Scrolls'" in notes
    assert "start_date and end_date in days from the calendar 'Eberron' (5 dated)" in notes


def test_a_calendar_that_is_not_exact_is_kept_raw_and_dates_nothing(tmp_path: Path) -> None:
    out, report = run(tmp_path, project([("tl1", "elder-scrolls", EVENTS)]))
    els = by_lk_id(out)
    for k in ("zero", "minus", "span"):
        assert "start_date" not in els[k] and "end_date" not in els[k], k
        assert "minutes" in els[k]["x_legendkeeper_start"]
    cal = els["elder-scrolls"]
    assert cal["type"] == "construct" and "atlas_calendar" not in cal
    assert cal["x_legendkeeper_calendar"] == preset("Scrolls")
    assert "time_basic_unit" not in world(out)  # no Event got a date
    notes = "\n".join(report.notes)
    assert (
        "calendar 'Scrolls' (elder-scrolls): a Construct (supertype calendar), kept raw as x_legendkeeper_calendar"
        in notes
    )
    assert "not exact: era 'Second Era' restarts its years at minute 1536298560 (unwitnessed)" in notes
    assert "start_date and end_date unset: the calendar 'Scrolls' is kept raw" in notes
    assert "the world's time_basic_unit is day" not in notes


def test_two_timelines_on_two_calendars(tmp_path: Path) -> None:
    timelines = [("tl1", "gregorian", [ev("a", 2 * DAY)]), ("tl2", "elder-scrolls", [ev("b", 0)])]
    out, report = run(tmp_path, project(timelines))
    els = by_lk_id(out)
    assert els["a"]["start_date"] == 2 and "start_date" not in els["b"]
    assert els["gregorian"]["atlas_calendar"] == GREGORIAN and "atlas_calendar" not in els["elder-scrolls"]
    assert world(out)["time_basic_unit"] == "day"  # one dated Event names the unit
    assert report.counts["construct"] == 2


def test_a_calendar_only_hidden_timelines_name_is_hidden(tmp_path: Path) -> None:
    ans = project([("tl1", "eberron", [ev("a", 0)]), ("tl2", "eberron", [ev("b", 0)])])
    docs = ans[f"{P}/resources/{REALM}"]["documents"]
    for d in docs:
        d["isHidden"] = True
    out, _ = run(tmp_path, ans, name="hidden")
    assert by_lk_id(out)["eberron"]["hidden"] is True
    docs[1]["isHidden"] = False  # one visible timeline names it: shown
    out, _ = run(tmp_path, ans, name="shown")
    assert "hidden" not in by_lk_id(out)["eberron"]


def test_a_calendar_no_timeline_names_makes_nothing(tmp_path: Path) -> None:
    out, report = run(tmp_path, project([]))
    assert "construct" not in report.counts and "time_basic_unit" not in world(out)
    assert any(n.startswith("6 calendars no timeline names, not made: 'Gregorian'") for n in report.notes)


def test_a_calendar_id_not_among_the_calendars_is_a_note(tmp_path: Path) -> None:
    out, report = run(tmp_path, project([("tl1", "fhynh6n4", EVENTS)]))
    els = by_lk_id(out)
    assert "start_date" not in els["zero"] and els["zero"]["x_legendkeeper_calendar"] == "fhynh6n4"
    assert "construct" not in report.counts and "time_basic_unit" not in world(out)
    assert (
        "timeline 'History tl1' on 'The Realm' names the calendar 'fhynh6n4', which is not among the project's"
        " calendars: its events keep their minutes, with no dates"
    ) in report.notes


def test_calendars_that_do_not_answer_are_unread(tmp_path: Path) -> None:
    ans = project([("tl1", "eberron", EVENTS)])
    del ans[f"{P}/calendars"]
    out, report = run(tmp_path, ans)
    assert any(u.startswith(f"the project's calendars: GET {P}/calendars: 404") for u in report.unread)
    assert "start_date" not in by_lk_id(out)["zero"] and "construct" not in report.counts


def test_the_calendars_are_read_once_with_no_page_size(tmp_path: Path) -> None:
    src = RecordedSource(project([("tl1", "eberron", EVENTS), ("tl2", "eberron", [ev("c", 5)])]))
    report = import_legendkeeper(src, PID, plan_only=True)
    assert src.calls.count(f"{P}/calendars") == 1
    assert report.counts["construct"] == 1  # one Construct for the calendar both name


def test_the_export_file_reads_its_calendars_as_the_api_serves_them(tmp_path: Path) -> None:
    """The export's ``calendars`` list, assumed in the API's shape (no real export holding one has been read)."""
    content = {"lanes": [], "events": EVENTS}
    doc = {"id": "tl1", "name": "History", "type": "time", "calendarId": "exandria", "content": content}
    export = {
        "version": 1,
        "exportId": "x",
        "exportedAt": "2026-10-25T00:00:00Z",
        "resources": [{"id": REALM, "name": "The Realm", "pos": "a", "tags": [], "documents": [doc]}],
        "calendars": [preset("Exandria"), preset("Harptos")],
        "resourceCount": 1,
    }
    path = tmp_path / "realm.lk"
    path.write_bytes(gzip.compress(json.dumps(export).encode("utf-8")))
    out = tmp_path / "file"
    report = import_legendkeeper(path, out_dir=out)
    els = by_lk_id(out)
    assert els["minus"]["start_date"] == -1 and els["span"]["end_date"] == 3
    assert els["exandria"]["atlas_calendar"] == EXANDRIA
    assert world(out)["time_basic_unit"] == "day"
    assert any(n.startswith("2 calendars in the export, read as the API serves calendars") for n in report.notes)
    assert any(n.startswith("1 calendar no timeline names, not made: 'Harptos'") for n in report.notes)


def test_a_dated_folder_passes_the_lint(tmp_path: Path) -> None:
    pytest.importorskip("yaml", reason="the dist's lint decodes the schema YAML")
    out, report = run(tmp_path, project([("tl1", "eberron", EVENTS), ("tl2", "harptos", [ev("h", 0)])]))
    r = subprocess.run([sys.executable, str(LINT), str(out)], capture_output=True, text=True)
    lines = r.stdout.strip().splitlines()
    assert str(report.total) in lines[-1], r.stdout + r.stderr
    assert [line for line in lines[:-1] if not line.startswith("walk note:")] == [], r.stdout + r.stderr
    assert r.returncode == 0, r.stdout + r.stderr

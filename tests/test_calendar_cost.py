"""A stored calendar does not set what one label costs. The shared cases (``tests/fixtures/calendar-cost.cases.json``,
the same bytes as the npm SDK's ``test/fixtures/calendar-cost.cases.json``; both suites hold its sha256): a long run
of white space in a template or a name, a long run of marks at a label's edge, and a month of millions of days, each
answered with its words inside the bound. Before 0.148.2 every case ran past it."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

import pytest

from onlyworlds import calendar as cal

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "calendar-cost.cases.json"
FIXTURE_SHA256 = "1e326d378cbdc6db91deba2219ed07cf67ad72211653bd25219f963fc81ebc0f"
DATA: dict[str, Any] = json.loads(FIXTURE.read_bytes())
PYTHON_FACTOR = 5


def _expand(v: Any) -> Any:
    if isinstance(v, list):
        return [_expand(x) for x in v]
    if isinstance(v, dict):
        if "$repeat" in v:
            return "".join(piece * times for piece, times in v["$repeat"])
        return {k: _expand(x) for k, x in v.items()}
    return v


def test_the_cases_are_the_sdks_bytes() -> None:
    assert hashlib.sha256(FIXTURE.read_bytes()).hexdigest() == FIXTURE_SHA256


# Since serial 149 a template or a name longer than 256 code points is not a calendar, and five of the cases hold
# one. The reader refuses them; the kernel is still timed on them as given, since a config built in code never
# passes the reader, and the cost bound is what holds a label's cost there.
def _past_the_bound(cfg: dict[str, Any]) -> str | None:
    def long(s: object) -> bool:
        return isinstance(s, str) and len(s) > 256

    if long(cfg.get("format")):
        return "its format is longer than 256 characters"
    names = ((cfg.get("bundles") or {}).get("months") or {}).get("names") or []
    if any(long(n) for n in names):
        return "a month name is longer than 256 characters"
    return None


def test_five_of_the_cases_are_past_a_size_bound_three_inside_them() -> None:
    assert sum(_past_the_bound(_expand(c["cfg"])) is not None for c in DATA["cases"]) == 5
    assert len(DATA["cases"]) == 8


@pytest.mark.parametrize("case", DATA["cases"], ids=[c["name"] for c in DATA["cases"]])
def test_each_case_answers_its_words_inside_the_bound(case: dict[str, Any]) -> None:
    value = _expand(case["cfg"])
    read = cal.read_calendar_config(value)
    bound = _past_the_bound(value)
    if bound is not None:
        assert read is None, f"the reader refuses it: {bound}"
        cfg = value
    else:
        assert read is not None, "the case's calendar is one the reader accepts"
        cfg = read
    start = time.perf_counter()
    if case["call"] == "format":
        got: Any = cal.format_step(cfg, case["step"])
    elif case["call"] == "weekday":
        got = cal.weekday_for_step(cfg, case["step"])
    else:
        label = cal.format_step(cfg, case["step"])
        got = [label, cal.parse_date(cfg, label)]
    ms = (time.perf_counter() - start) * 1000
    assert got == _expand(case["want"])
    assert ms < DATA["underMs"] * PYTHON_FACTOR, f"{round(ms)} ms"


def test_a_length_that_is_not_a_whole_int_keeps_the_list_and_its_answer() -> None:
    # The runs are built only where every month length is an int; a float length is read as before.
    as_int = {"version": 1, "grain": "day", "bundles": {"months": {"names": ["A", "B"], "lengths": [3, 2]}}}
    as_float = {"version": 1, "grain": "day", "bundles": {"months": {"names": ["A", "B"], "lengths": [3.0, 2.0]}}}
    assert cal._year_runs(as_float, 0) is None
    assert cal._year_runs(as_int, 0) is not None
    for step in range(-6, 7):
        assert cal.format_step(as_float, step) == cal.format_step(as_int, step)

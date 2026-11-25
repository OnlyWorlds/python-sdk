"""``format_steps``: a page of steps in one calendar, the same words as ``format_step`` for every step, with the
calendar's own work done once. Held against the loop on every valid calendar of the vendored profile fixture,
over the fixture's own steps, a dense run inside a few years, steps spread over many years, and the far edges."""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

import pytest

from onlyworlds import calendar as cal

FIXTURE = Path(__file__).resolve().parents[1] / "codegen" / "schema-dist" / "profiles" / "calendar.fixture.json"
CASES: list[dict[str, Any]] = [c for c in json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"] if c["valid"]]
EDGES = [0, 1, -1, 2**31 - 1, -(2**31), 2**53 - 1, -(2**53 - 1)]


def steps_for(c: dict[str, Any], cfg: Any) -> list[int]:
    rng = random.Random(c["name"])
    length = cal.approx_year_length(cfg) or 365
    out = [s["step"] for s in c.get("steps", [])] + EDGES
    for start in (0, -3 * length, 40 * length):  # a dense run: every step of a stretch inside a few years
        out += list(range(start, start + 2 * length + 3))
    out += [rng.randint(-(2**40), 2**40) for _ in range(200)]  # one step in each of many years
    out += out[:50]  # a step asked twice in one call
    return out


def test_every_fixture_calendar_says_the_same_words_as_format_step() -> None:
    assert len(CASES) == 48  # counted, so a fixture that stops loading fails here rather than passing on nothing
    compared = 0
    for c in CASES:
        cfg = cal.read_calendar_value(c["value"])
        assert cfg is not None, c["name"]
        steps = steps_for(c, cfg)
        loop = [cal.format_step(cfg, s) for s in steps]
        assert cal.format_steps(cfg, steps) == loop, c["name"]
        compared += len(steps)
    assert compared > 35 * 400


def test_steps_may_be_any_iterable_and_no_steps_give_an_empty_list() -> None:
    cfg = cal.read_calendar_value(CASES[0]["value"])
    assert cfg is not None
    assert cal.format_steps(cfg, (s for s in [0, 1, 2])) == [cal.format_step(cfg, s) for s in [0, 1, 2]]
    assert cal.format_steps(cfg, []) == []


def test_the_memo_lives_only_for_the_call() -> None:
    cfg = cal.read_calendar_value(CASES[0]["value"])
    assert cfg is not None
    assert cal._MEMO.get() is None
    cal.format_steps(cfg, [0, 5, 10])
    assert cal._MEMO.get() is None
    with pytest.raises(TypeError):
        cal.format_steps(cfg, [0, "not a step"])  # type: ignore[list-item]
    assert cal._MEMO.get() is None


def test_a_step_format_step_refuses_is_refused_the_same_way() -> None:
    cfg = cal.read_calendar_value(CASES[0]["value"])
    assert cfg is not None
    with pytest.raises(TypeError) as one:
        cal.format_step(cfg, "not a step")  # type: ignore[arg-type]
    with pytest.raises(TypeError) as many:
        cal.format_steps(cfg, [0, "not a step"])  # type: ignore[list-item]
    assert (type(many.value), str(many.value)) == (type(one.value), str(one.value))


def test_two_calendars_in_one_process_keep_their_own_answers() -> None:
    a, b = (cal.read_calendar_value(c["value"]) for c in CASES[:2])
    assert a is not None and b is not None
    steps = list(range(-400, 400, 7))
    assert cal.format_steps(a, steps) == [cal.format_step(a, s) for s in steps]
    assert cal.format_steps(b, steps) == [cal.format_step(b, s) for s in steps]

"""The record profile (schema-dist ``profiles/record.md``, serial 103): every conformance case in
``codegen/schema-dist/profiles/record.fixture.json``, vendored with the distribution, each its own test, through
``record_mark_of`` and ``records_of``. The npm SDK's ``recordMarkOf`` and ``recordsOf`` run the same cases.
``OW_RECORD_FIXTURE`` points it at another copy of the fixture (a staged branch before the serial)."""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any

import pytest

from onlyworlds import RECORD_FIELD, record_mark_of, records_of

REPO = Path(__file__).resolve().parent.parent
FIXTURE = Path(
    os.environ.get("OW_RECORD_FIXTURE") or REPO / "codegen" / "schema-dist" / "profiles" / "record.fixture.json"
)


def load_fixture() -> dict[str, Any]:
    assert FIXTURE.is_file(), f"no record fixture at {FIXTURE}"
    doc: dict[str, Any] = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert doc["profile"] == "record"
    return doc


DOC = load_fixture()
CASES: list[dict[str, Any]] = DOC["cases"]


def test_the_fixture_holds_serial_103s_40_cases() -> None:
    assert DOC["mark"]["field"] == RECORD_FIELD == "x_record"
    assert DOC["mark"]["members"] == ["tool", "played_at", "version", "seed", "outcome", "seats"]
    assert len(CASES) == 40, f"the fixture holds {len(CASES)} cases, serial 103 has 40"


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_fixture_case(case: dict[str, Any]) -> None:
    elements = copy.deepcopy(DOC["worlds"][case["world"]]["elements"])
    if case["kind"] == "mark":
        el = next((e for e in elements if e["id"] == case["element"]), None)
        assert el is not None, f"no element {case['element']}"
        assert record_mark_of(el) == case["want"]
    elif case["kind"] == "records":
        assert records_of(case["character"], elements) == case["want"]
    else:
        pytest.fail(f"a case of unknown kind {case['kind']}")


def test_records_of_is_pure() -> None:
    elements = copy.deepcopy(next(iter(DOC["worlds"].values()))["elements"])
    before = json.dumps(elements, sort_keys=True)
    who = next(c["character"] for c in CASES if c["kind"] == "records" and c["want"])
    got = records_of(who, elements)
    got[0]["event"]["name"] = "planted"
    got[0]["stories"].append({"id": "x", "name": "x", "as": "both"})
    mark = record_mark_of(next(e for e in elements if record_mark_of(e)))
    assert mark is not None
    mark["seats"]["planted"] = "planted"
    assert json.dumps(elements, sort_keys=True) == before
    assert records_of(who, elements)[0]["event"]["name"] != "planted"


def test_a_narrative_naming_an_event_twice_is_one_story_and_no_two_records_share_one() -> None:
    c = "019a8000-0000-7000-8000-000000000101"

    def ev(i: str, at: str) -> dict[str, Any]:
        return {"id": i, "type": "event", "name": i, "characters": [c], "x_record": {"tool": "tangle", "played_at": at}}

    world: list[Any] = [
        ev("e1", "2026-11-02T00:00:00Z"),
        ev("e2", "2026-11-01T00:00:00Z"),
        {"id": "n1", "type": "narrative", "name": "One", "protagonist": c, "events": ["e1", "e1", "e2"]},
        {"id": "n2", "type": "narrative", "name": "Two", "narrator": c, "events": [7, None, {}, ["e1"], "e1"]},
    ]
    got = records_of(c, world)
    assert [(r["event"]["id"], [f"{s['id']}:{s['as']}" for s in r["stories"]]) for r in got] == [
        ("e1", ["n1:protagonist", "n2:narrator"]),
        ("e2", ["n1:protagonist"]),
    ]
    got[0]["stories"][0]["name"] = "planted"
    assert got[1]["stories"][0]["name"] == "One"


def test_an_event_or_narrative_whose_id_is_not_a_string_is_never_read() -> None:
    c = "019a8000-0000-7000-8000-000000000101"
    mark = {"tool": "tangle", "played_at": "2026-11-01T00:00:00Z"}
    world: list[Any] = [
        {"id": "e1", "type": "event", "name": "One", "characters": [c], "x_record": mark},
        {"id": 7, "type": "event", "name": "Seven", "characters": [c], "x_record": mark},
        {"type": "event", "name": "None", "characters": [c], "x_record": mark},
        {"id": ["e1"], "type": "narrative", "name": "Listed", "protagonist": c, "events": ["e1"]},
        {"type": "narrative", "name": "Unnamed", "narrator": c, "events": ["e1"]},
        {"id": "n1", "type": "narrative", "name": "Kept", "narrator": c, "events": ["e1", 7]},
    ]
    got = records_of(c, world)
    assert [(r["event"]["id"], [s["id"] for s in r["stories"]]) for r in got] == [("e1", ["n1"])]


@pytest.mark.parametrize(
    "played_at",
    [
        "\uff12\uff10\uff12\uff16-11-01T00:00:00Z",
        "\u0662\u0660\u0662\u0666-11-01T00:00:00Z",
        "2026-11-01T00:00:0\u0669Z",
    ],
)
def test_a_played_at_with_digits_outside_ascii_is_no_mark(played_at: str) -> None:
    assert record_mark_of({"id": "e", "type": "event", "x_record": {"tool": "tangle", "played_at": played_at}}) is None


def test_records_of_refuses_what_is_not_an_id_or_a_list() -> None:
    with pytest.raises(TypeError):
        records_of(None, [])  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        records_of("a", None)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        records_of("a", "abc")
    assert records_of("a", []) == []


def _ev(id_: str, at: str) -> dict[str, Any]:
    return {"id": id_, "type": "event", "name": id_, "characters": ["c"], "x_record": {"tool": "subs", "played_at": at}}


def test_played_at_orders_as_its_instant() -> None:
    got = records_of(
        "c", [_ev("a", "2026-11-01T00:30Z"), _ev("b", "2026-11-01T00:30:00.500Z"), _ev("c", "2026-11-01T00:29:59Z")]
    )
    assert [r["event"]["id"] for r in got] == ["b", "a", "c"]


def test_played_at_orders_to_the_millisecond_as_javascript_does() -> None:
    # .1239 and .1231 are the same millisecond: a tie, so the Event's id decides, as in the npm SDK.
    got = records_of("c", [_ev("b", "2026-11-01T00:30:00.1239Z"), _ev("a", "2026-11-01T00:30:00.1231Z")])
    assert [r["event"]["id"] for r in got] == ["a", "b"]


@pytest.mark.parametrize(
    "at",
    [
        "2026-13-01T00:00Z",
        "2026-02-30T00:00Z",
        "2026-02-29T00:00Z",
        "2026-11-01T24:00Z",
        "2026-11-01T00:60Z",
        "2026-11-01T00:00:60Z",
        "0000-01-01T00:00Z",
        "2026-00-01T00:00Z",
        "2026-11-00T00:00Z",
    ],
)
def test_a_played_at_that_is_no_real_instant_is_no_mark(at: str) -> None:
    ev = {"id": "e", "type": "event", "characters": ["c"], "x_record": {"tool": "subs", "played_at": at}}
    assert record_mark_of(ev) is None
    assert records_of("c", [ev]) == []


@pytest.mark.parametrize("at", ["2028-02-29T00:00Z", "2000-02-29T23:59:59.999Z", "0001-01-01T00:00Z"])
def test_a_real_instant_is_a_mark(at: str) -> None:
    ev = {"id": "e", "type": "event", "characters": ["c"], "x_record": {"tool": "subs", "played_at": at}}
    assert record_mark_of(ev) is not None

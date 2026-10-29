"""The door history: ``doors_of`` on every case of ``tests/fixtures/doors.fixture.json``, the same bytes as the npm
SDK's ``test/fixtures/doors.fixture.json`` (both suites hold its sha256), every expected list written by hand, and
``door_where`` on each entry against the case's where list. Then the refusals, and ``TOOLS``, the baked list, as the
default. A missing fixture fails, never skips."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from onlyworlds import TOOLS, door_where, doors_of

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "doors.fixture.json"
FIXTURE_SHA256 = "3b21bb1e86470c1eb158d486691acc95440a5f1c707cc22fef7dc98e306d7de1"
CASES = 27


def test_every_case_of_the_shared_fixture() -> None:
    data = FIXTURE.read_bytes()
    assert hashlib.sha256(data).hexdigest() == FIXTURE_SHA256
    doc = json.loads(data.decode("utf-8"))
    wrong = []
    for c in doc["cases"]:
        got: Any
        try:
            got = doors_of(c["element"], c["tools"] if "tools" in c else doc["tools"])
        except Exception as err:
            got = {"threw": repr(err)}
        if got != c["expected"]:
            wrong.append(f"{c['name']}: gave {got}, want {c['expected']}")
    for line in wrong:
        print(line)
    assert wrong == []
    assert len(doc["cases"]) == CASES


def test_door_where_gives_every_cases_where_list() -> None:
    doc = json.loads(FIXTURE.read_bytes().decode("utf-8"))
    wrong = []
    for c in doc["cases"]:
        got: Any
        try:
            got = [door_where(e) for e in c["expected"]]
        except Exception as err:
            got = {"threw": repr(err)}
        if got != c["where"]:
            wrong.append(f"{c['name']}: gave {got}, want {c['where']}")
    for line in wrong:
        print(line)
    assert wrong == []
    # Every phrase the rules give is held by at least one entry.
    phrases = {p for c in doc["cases"] for p in c["where"]}
    for p in ["in Atlas", "in Lantern", "in Zephyr", "on onlyworlds.com", "with an AI", "by OnlyWorlds", "in code"]:
        assert p in phrases, p


@pytest.mark.parametrize(
    "door",
    [
        None,
        [],
        "site",
        7,
        {},
        {"door": 7},
        {"door": None},
        {"door": "atlas", "tool": "Atlas"},
        {"door": "atlas", "tool": {"id": "atlas"}},
    ],
)
def test_door_where_refuses_what_is_not_an_entry(door: Any) -> None:
    with pytest.raises(TypeError, match=r"^door_where: "):
        door_where(door)


def test_door_where_reads_only_door_and_tool() -> None:
    entry: Any = {"door": "mcp"}
    assert door_where(entry) == "with an AI"
    entry = {"door": "atlas", "tool": None}
    assert door_where(entry) == "in code"


@pytest.mark.parametrize("element", [None, [], ["x"], "element", 7, True])
def test_an_element_that_is_not_a_mapping_is_a_type_error(element: Any) -> None:
    with pytest.raises(TypeError, match="element"):
        doors_of(element)


@pytest.mark.parametrize("tools", [None, {}, "atlas", b"atlas", 7])
def test_tools_that_are_not_a_sequence_is_a_type_error(tools: Any) -> None:
    with pytest.raises(TypeError, match="tools"):
        doors_of({}, tools)


def test_a_tools_row_that_is_not_one_matches_nothing() -> None:
    rows: Any = [None, "atlas", {"client": "atlas", "id": "a", "name": "A"}]
    assert doors_of({"doors": {"atlas": "2026-10-29T12:00:00Z"}}, rows)[0]["tool"] == {"id": "a", "name": "A"}


def test_the_default_tools_are_tools_the_baked_list() -> None:
    at = "2026-10-29T14:31:07.123456+00:00"
    listed = [t for t in TOOLS if isinstance(t["client"], str)]
    assert listed
    for row in listed:
        assert row["client"] is not None
        element = {"doors": {row["client"]: at, "site": "2026-10-28T09:00:00Z"}, "updated_at": at}
        assert doors_of(element) == doors_of(element, TOOLS)
        assert doors_of(element)[0] == {
            "door": row["client"],
            "at": at,
            "tool": {"id": row["id"], "name": row["name"]},
            "last": True,
            "from": "doors",
        }
        assert [door_where(e) for e in doors_of(element)] == [f"in {row['name']}", "on onlyworlds.com"]

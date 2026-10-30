"""The strand profile (schema-dist ``profiles/strand.md``, serial 98): every conformance case in
``codegen/schema-dist/profiles/strand.fixture.json``, vendored with the distribution, each its own test, through
``strand_of``. The npm SDK's ``strandOf`` runs the same cases."""

from __future__ import annotations

import copy
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from onlyworlds import STRAND_FIELD, strand_of

REPO = Path(__file__).resolve().parent.parent
FIXTURE = REPO / "codegen" / "schema-dist" / "profiles" / "strand.fixture.json"


def load_fixture() -> dict[str, Any]:
    assert FIXTURE.is_file(), f"no strand fixture at {FIXTURE}"
    doc: dict[str, Any] = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert doc["profile"] == "strand"
    return doc


DOC = load_fixture()
CASES: list[dict[str, Any]] = DOC["cases"]
EMPTY = {"narrative": None, "event": None, "location": None, "character": None, "now": None, "same": None}


def world_of(c: Mapping[str, Any]) -> dict[str, Any]:
    world = c["world"]
    return copy.deepcopy(DOC["worlds"][world] if isinstance(world, str) else world)


def test_the_fixture_holds_serial_99s_cases() -> None:
    assert DOC["profile_page"] == "profiles/strand.md"
    assert DOC["mark"]["field"] == STRAND_FIELD == "x_strand"
    assert DOC["mark"]["members"] == ["narrative", "event", "location"]
    assert len(CASES) == 21, f"the fixture holds {len(CASES)} cases, serial 99 has 21"
    assert {c["kind"] for c in CASES} == {"strand"}


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["name"])
def test_strand_of(case: dict[str, Any]) -> None:
    world = world_of(case)
    before = json.dumps(world, sort_keys=True)
    assert strand_of(world, world["readers"][case["reader"]]) == case["want"], case.get("claim")
    assert json.dumps(world, sort_keys=True) == before, "strand_of moved the world"


def test_a_strand_is_the_readers_own_copy() -> None:
    world = world_of({"world": "harbour"})
    got = strand_of(world, {"rung": "owner"})
    assert got["narrative"] is not None
    got["narrative"]["name"] = "planted"
    again = strand_of(world, {"rung": "owner"})["narrative"]
    assert again is not None and again["name"] != "planted"


def test_strand_of_refuses_what_is_not_a_world_and_a_reader_the_lens_profile_does_not_know() -> None:
    with pytest.raises(TypeError):
        strand_of(None, {"rung": "owner"})  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        strand_of({"x_strand": {}}, {"rung": "owner"})
    with pytest.raises(TypeError):
        strand_of(world_of({"world": "harbour"}), {"rung": "stranger"})


def test_a_public_reader_reads_no_strand_of_a_world_that_is_not_open_and_the_open_ones() -> None:
    world = world_of({"world": "harbour"})
    assert strand_of(world, {"rung": "public"}) == EMPTY
    owner = next(c for c in CASES if c["name"] == "owner-reads-the-full-strand-two-places")["want"]
    assert strand_of({**world, "open": True}, {"rung": "public"}) == owner


def test_a_mark_with_no_story_or_an_event_or_place_neither_an_id_nor_unset_is_no_mark() -> None:
    world = world_of({"world": "harbour"})
    m = world["x_strand"]
    no_story = {k: v for k, v in m.items() if k != "narrative"}
    as_list = [m["narrative"], m["event"], m["location"]]
    bads: list[Any] = [no_story, {**m, "narrative": ""}, {**m, "narrative": 7}, {**m, "narrative": None}]
    bads += [
        {**m, "location": ""},
        {**m, "event": 7},
        {**m, "event": {}},
        {**m, "location": False},
        as_list,
        m["narrative"],
        None,
    ]
    for bad in bads:
        assert strand_of({**world, "x_strand": bad}, {"rung": "owner"})["narrative"] is None, bad

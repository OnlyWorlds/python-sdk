"""The charter profile (schema-dist ``profiles/charter.md``, serial 83): every conformance case in
``codegen/schema-dist/profiles/charter.fixture.json``, vendored with the distribution, each its own test, through
``charter_of`` and ``domains_of`` (the packet) and ``is_charter_element`` (the pair and the mark), and the
fixture's tables read back against the package's. The npm SDK's ``charterOf``, ``domainsOf`` and
``isCharterElement`` run the same cases."""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from onlyworlds import (
    CHECKS_FIELD,
    READING_AID_MARK,
    READING_AID_PAIRS,
    SKILL_MAX,
    FolderElement,
    charter_of,
    domains_of,
    is_charter_element,
    reading_aid_of,
)
from onlyworlds._schema import LINK_TARGETS

REPO = Path(__file__).resolve().parent.parent
FIXTURE = REPO / "codegen" / "schema-dist" / "profiles" / "charter.fixture.json"


def load_fixture() -> dict[str, Any]:
    assert FIXTURE.is_file(), f"no charter fixture at {FIXTURE}"
    doc: dict[str, Any] = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert doc["profile"] == "charter"
    return doc


DOC = load_fixture()
CASES: list[dict[str, Any]] = DOC["cases"]


def world_of(c: Mapping[str, Any]) -> dict[str, Any]:
    world = c["world"]
    return dict(DOC["worlds"][world]) if isinstance(world, str) else dict(world)


def reader_of(world: Mapping[str, Any], name: str) -> dict[str, Any]:
    """A reader as the fixture writes it, its ``as`` (a reader's name) turned into that reader."""
    r: dict[str, Any] = dict(world["readers"][name])
    if r.get("as"):
        r["as"] = world["readers"][r["as"]]
    return r


def test_the_fixture_holds_serial_86s_cases() -> None:
    assert len(CASES) == 23, f"the fixture holds {len(CASES)} cases, serial 86 has 23"
    assert Counter(c["kind"] for c in CASES) == {"charter": 18, "element": 5}
    assert sorted(DOC["worlds"]) == ["bare", "copy", "harbour", "lore", "open", "skills", "ties"]


def test_the_fixtures_tables_are_the_packages() -> None:
    assert DOC["profile_page"] == "profiles/charter.md"
    assert [(p["type"], p["supertype"].lower()) for p in DOC["pairs"]] == list(READING_AID_PAIRS)
    assert [p["aid"] for p in DOC["pairs"]] == ["charter", "guide", "domain"]
    assert DOC["mark"]["field"] == READING_AID_MARK == "x_charter_of"
    assert DOC["rules_field"] == CHECKS_FIELD
    assert DOC["skill_max"] == SKILL_MAX == 5
    assert [(h["field"], h["type"]) for h in DOC["hub_fields"]] == list(LINK_TARGETS["construct"].items())


@pytest.mark.parametrize("case", [c for c in CASES if c["kind"] == "element"], ids=lambda c: c["name"])
def test_is_charter_element(case: dict[str, Any]) -> None:
    assert is_charter_element(case["element"]) is case["is_charter_element"], case.get("note")


@pytest.mark.parametrize("case", [c for c in CASES if c["kind"] == "charter"], ids=lambda c: c["name"])
def test_charter_of(case: dict[str, Any]) -> None:
    world = world_of(case)
    before = json.dumps(world, sort_keys=True)
    reader = reader_of(world, case["reader"])
    got = charter_of(world, reader)
    assert got == case["want"], case.get("note")
    assert domains_of(world, reader) == case["want"]["domains"]
    assert json.dumps(world, sort_keys=True) == before, "charter_of moved the world"


def test_a_packet_is_the_readers_own_copy() -> None:
    world = world_of({"world": "harbour"})
    got = charter_of(world, {"rung": "owner"})
    assert got["charter"] is not None
    got["charter"]["rules"].append("planted")
    got["domains"][0]["hubs"].append({"type": "object", "id": "planted"})
    assert charter_of(world, {"rung": "owner"}) == charter_of(world_of({"world": "harbour"}), {"rung": "owner"})


def test_the_owner_as_another_reader_reads_that_readers_packet() -> None:
    world = world_of({"world": "harbour"})
    for name in ("contributor", "guest", "public"):
        seen = reader_of(world, name)
        assert charter_of(world, {"rung": "owner", "as": seen}) == charter_of(world, seen), name


def test_a_proposed_object_is_no_hub_for_any_reader() -> None:
    """charter.md (serial 94): a proposed element is in no reader's view, the owner's included, so a Domain's link to
    one is no hub, though the owner's and a contributor's served lists keep the id. The npm SDK holds the same case."""
    world = {
        "id": "w",
        "elements": [
            {
                "id": "d",
                "type": "construct",
                "name": "The Hall",
                "supertype": "Domain",
                "x_charter_of": "w",
                "objects": ["p", "o"],
            },
            {"id": "o", "type": "object", "name": "Ledger"},
            {"id": "p", "type": "object", "name": "Draft", "x_review_proposed": "is this real?"},
        ],
    }
    for reader in ({"rung": "owner"}, {"rung": "contributor"}):
        assert domains_of(world, reader)[0]["hubs"] == [{"type": "object", "id": "o"}], reader


def test_charter_of_refuses_what_is_not_a_reading() -> None:
    with pytest.raises(TypeError):
        charter_of({}, {"rung": "owner"})
    with pytest.raises(TypeError):
        charter_of({"elements": []}, {"rung": "admin"})
    assert charter_of({"elements": []}, {"rung": "owner"}) == {"charter": None, "guide": None, "domains": []}


@pytest.mark.parametrize("case", [c for c in CASES if c["kind"] == "charter"], ids=lambda c: c["name"])
def test_charter_of_does_not_read_the_elements_order(case: dict[str, Any]) -> None:
    """The selection's ties are the higher id and created_at, never which element came first in the snapshot."""
    world = world_of(case)
    reader = reader_of(world, case["reader"])
    reversed_world = {**world, "elements": list(reversed(world["elements"]))}
    assert charter_of(reversed_world, reader) == case["want"]


def test_reading_aid_of_reads_the_pair_alone() -> None:
    """Each of the fixture's pairs to its aid, trimmed and folded, the whole word; the mark is never read."""
    assert len(DOC["pairs"]) == 3
    for p in DOC["pairs"]:
        assert reading_aid_of({"type": p["type"], "supertype": p["supertype"]}) == p["aid"], p
    assert reading_aid_of({"type": "law", "supertype": " charter "}) == "charter"
    assert reading_aid_of({"type": "LAW", "supertype": "CHARTER" + chr(0x3000)}) == "charter"
    assert reading_aid_of({"type": "law", "supertype": "Guide"}) is None
    assert reading_aid_of({"type": "law", "supertype": "Charters"}) is None
    assert reading_aid_of({"type": "object", "supertype": "Domain"}) is None
    # Unmarked, so lore to is_charter_element, and still the pair of a charter.
    unmarked = {"type": "law", "supertype": "Charter"}
    assert is_charter_element(unmarked) is False
    assert reading_aid_of(unmarked) == "charter"
    assert reading_aid_of({**unmarked, "x_charter_of": None}) == "charter"
    body = {"id": "g1", "supertype": "Guide"}
    path = Path("elements") / "construct" / "g1.json"
    el = FolderElement(id="g1", type="construct", type_inferred=True, body=body, path=path, layout="elements")
    assert reading_aid_of(el) == "guide"
    bad: list[Any] = [None, "law/charter", 7, ["law", "Charter"], {"type": "law"}, {"type": "law", "supertype": None}]
    for b in [*bad, {"supertype": "Charter"}]:
        assert reading_aid_of(b) is None, b

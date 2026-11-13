"""The address profile's same-id rule (serial 122): inside a world an id has one spelling and two ids are the same
when written the same; an id is read in either case and taken in lowercase at two doors only, an address and an id
found in a text; what a door's id is matched against is read as written. The three readers here folded the held id
too, and no longer do."""

from __future__ import annotations

from typing import Any

import pytest

from onlyworlds import TOOLS, charter_of, openers_for
from onlyworlds._markdown import prose_target

WORLD = "0199c3a1-7b2e-7c3d-8e4f-5a6b7c8d9e0f"
ID = "0199c3a1-7b2e-7c3d-8e4f-5a6b7c8d9e1a"
UPPER = ID.upper()


def _charter_world(object_id: str, description: str) -> dict[str, Any]:
    return {
        "id": WORLD,
        "name": "W",
        "hidden": [],
        "readers": {"owner": {"rung": "owner", "character": None}},
        "elements": [
            {
                "id": "0199c3a1-7b2e-7c3d-8e4f-5a6b7c8d9e2b",
                "type": "law",
                "name": "Rules",
                "supertype": "Charter",
                "x_charter_of": WORLD,
                "created_at": "2026-11-12T10:00:00Z",
                "description": description,
            },
            {"id": object_id, "type": "object", "name": "The Ledger"},
        ],
    }


@pytest.mark.parametrize("named", [ID, UPPER])
def test_a_charter_skill_names_an_object_held_in_lowercase_in_either_case(named: str) -> None:
    world = _charter_world(ID, f"Read ow://object/{named} first.")
    charter = charter_of(world, world["readers"]["owner"])["charter"]
    assert charter is not None
    assert charter["skill"] == [ID]


@pytest.mark.parametrize("named", [ID, UPPER])
def test_a_charter_skill_names_no_object_held_in_upper_case(named: str) -> None:
    world = _charter_world(UPPER, f"Read ow://object/{named} first.")
    charter = charter_of(world, world["readers"]["owner"])["charter"]
    assert charter is not None
    assert charter["skill"] == []


def _at(aid: str) -> dict[str, Any]:
    return {"form": "text", "world": WORLD, "type": "location", "id": aid}


def _el(eid: str) -> dict[str, Any]:
    return {"id": eid, "type": "location", "name": "The element"}


SURFACE = {"audience": "member", "signed_in": True}


def test_an_address_in_upper_case_names_the_element_held_in_lowercase() -> None:
    assert openers_for(TOOLS, "element", _at(UPPER), SURFACE, element=_el(ID)) == openers_for(
        TOOLS, "element", _at(ID), SURFACE, element=_el(ID)
    )


@pytest.mark.parametrize("aid", [ID, UPPER])
def test_an_element_held_in_upper_case_is_not_the_element_an_address_names(aid: str) -> None:
    # No address can name it, so its menu has no rows (serial 123's release); it is no refusal.
    assert openers_for(TOOLS, "element", _at(aid), SURFACE, element=_el(UPPER)) == []


@pytest.mark.parametrize("world", [WORLD, WORLD.upper()])
def test_a_prose_link_in_either_case_names_an_element_of_a_world_held_in_lowercase(world: str) -> None:
    assert prose_target(f"ow://{world}/location/{ID}", WORLD) == ID


def test_a_prose_link_names_nothing_in_a_world_held_in_upper_case() -> None:
    assert prose_target(f"ow://{WORLD}/location/{ID}", WORLD.upper()) is None


@pytest.mark.parametrize("named", [ID, UPPER])
def test_an_in_world_prose_link_in_either_case_names_the_lowercase_id(named: str) -> None:
    assert prose_target(f"ow://location/{named}", WORLD) == ID


def test_an_in_world_prose_link_not_in_the_form_is_read_as_written() -> None:
    assert prose_target("ow://location/A1", WORLD) == "A1"

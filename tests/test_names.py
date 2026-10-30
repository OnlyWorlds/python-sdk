"""The names profile (schema-dist ``profiles/names.md``): ``type_word`` on every conformance case in
``codegen/schema-dist/profiles/names.fixture.json``, vendored with the distribution from
``v0.33.0-dist.48``. The vendored copy is the only source: a missing fixture fails, never skips. The npm
SDK's ``typeWord`` runs the same cases."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from onlyworlds import type_word

REPO = Path(__file__).resolve().parents[1]
VENDORED = REPO / "codegen" / "schema-dist" / "profiles" / "names.fixture.json"


def load_fixture() -> dict[str, Any]:
    assert VENDORED.is_file(), f"no names fixture at {VENDORED}"
    doc: dict[str, Any] = json.loads(VENDORED.read_text(encoding="utf-8"))
    assert doc["profile"] == "x_names"
    return doc


def test_every_case_of_the_names_fixture() -> None:
    cases = load_fixture()["cases"]
    assert len(cases) >= 23
    for c in cases:
        got = type_word({"x_names": c["map"]}, c["type"], supertype=c.get("supertype"), many=c["many"])
        assert got == c["word"], c["name"]


def test_types_or_supertypes_present_as_null_is_refused_whole() -> None:
    """names.md: ``types`` (or ``supertypes``) "present and not an object" refuses the whole map, and a null is
    present: the standard's name, as the npm SDK reads it."""
    supertypes = {"character": {"Agent": {"one": "AI agent"}}}
    world: dict[str, Any] = {"x_names": {"version": 1, "types": None, "supertypes": supertypes}}
    assert type_word(world, "character", supertype="Agent") is None
    world = {"x_names": {"version": 1, "types": {"character": {"one": "Employee"}}, "supertypes": None}}
    assert type_word(world, "character") is None


def test_no_world_or_no_map_is_the_standard_name() -> None:
    assert type_word(None, "character") is None
    assert type_word({}, "character") is None
    assert type_word({"x_names": "Employee"}, "character") is None
    assert type_word({"x_names": {"version": True, "types": {"character": {"one": "Employee"}}}}, "character") is None

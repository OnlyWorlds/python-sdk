"""The names profile (schema-dist ``profiles/names.md``): ``type_word`` on every conformance case in
``codegen/schema-dist/profiles/names.fixture.json``, vendored with the distribution. Until the serial
carries it, the draft beside Skeld's profile (Orrery ``product/schema/names.fixture.json``) is read; on
the serial the vendored copy wins and the draft path goes. The npm SDK's ``typeWord`` runs the same cases."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from onlyworlds import type_word

REPO = Path(__file__).resolve().parents[1]
VENDORED = REPO / "codegen" / "schema-dist" / "profiles" / "names.fixture.json"
DRAFT = Path("C:/Users/Titus/Carrier/Orrery/product/schema/names.fixture.json")


def load_fixture() -> dict[str, Any]:
    path = VENDORED if VENDORED.is_file() else DRAFT
    if not path.is_file():
        pytest.skip(f"no names fixture at {VENDORED} or {DRAFT}")
    doc: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    assert doc["profile"] == "x_names"
    return doc


def test_every_case_of_the_names_fixture() -> None:
    cases = load_fixture()["cases"]
    assert len(cases) >= 22
    for c in cases:
        got = type_word({"x_names": c["map"]}, c["type"], supertype=c.get("supertype"), many=c["many"])
        assert got == c["word"], c["name"]


def test_no_world_or_no_map_is_the_standard_name() -> None:
    assert type_word(None, "character") is None
    assert type_word({}, "character") is None
    assert type_word({"x_names": "Employee"}, "character") is None
    assert type_word({"x_names": {"version": True, "types": {"character": {"one": "Employee"}}}}, "character") is None

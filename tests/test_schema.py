"""The type list and field kinds come from the pinned schema distribution, and the committed module is current."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import onlyworlds
from onlyworlds import ELEMENT_TYPES, FIELD_KINDS
from onlyworlds._schema import ELEMENT_GROUPS, ELEMENT_ICONS

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "codegen" / "schema-dist"


def test_generated_module_is_current() -> None:
    r = subprocess.run(
        [sys.executable, str(ROOT / "codegen" / "generate_schema.py"), "--check"], capture_output=True, text=True
    )
    assert r.returncode == 0, r.stderr


def test_manifest_matches_pin_and_every_file_matches_manifest() -> None:
    pin = json.loads((ROOT / "codegen" / "schema-pin.json").read_text(encoding="utf-8"))
    manifest = DIST / "MANIFEST.json"
    assert hashlib.sha256(manifest.read_bytes()).hexdigest() == pin["manifest_sha256"]
    files = json.loads(manifest.read_text(encoding="utf-8"))["files"]
    on_disk = {p.relative_to(DIST).as_posix() for p in DIST.rglob("*") if p.is_file() and "__pycache__" not in p.parts}
    assert on_disk == set(files) | {"MANIFEST.json"}
    for rel, digest in files.items():
        assert hashlib.sha256((DIST / rel).read_bytes()).hexdigest() == digest, rel
    assert pin["tag"] == onlyworlds.SCHEMA_DIST_TAG
    assert pin["manifest_sha256"] == onlyworlds.SCHEMA_MANIFEST_SHA256


def test_twenty_two_types_agree_with_the_dist_files() -> None:
    stems = {p.stem for p in (DIST / "schema").glob("*.yaml")} - {"base_properties", "world"}
    assert len(ELEMENT_TYPES) == 22
    assert set(ELEMENT_TYPES) == stems


def test_field_kinds() -> None:
    assert set(FIELD_KINDS) == set(ELEMENT_TYPES)
    assert sum(len(v) for v in FIELD_KINDS.values()) == 467  # 356 walked + 22 x 5 base + the generic pair's extra half
    assert FIELD_KINDS["zone"]["shape"] == "text"
    assert FIELD_KINDS["pin"]["map"] == "single_link"
    assert FIELD_KINDS["pin"]["element_id"] == "single_link"
    assert FIELD_KINDS["character"]["name"] == "text"
    assert "world" not in FIELD_KINDS["character"] and "id" not in FIELD_KINDS["character"]
    # ruling collective-equipment-target: the v2 target, not the decommissioned v1 one
    assert FIELD_KINDS["collective"]["equipment"] == "multi_link"


def test_colour_groups_are_the_presentation_defaults_colour_words() -> None:
    """Serial 86: each type's colour group is the colour word presentation.json gives it, one of the four in
    ``colors.order``; Construct moved to pink and Ability to amber."""
    presentation = json.loads((DIST / "presentation.json").read_text(encoding="utf-8"))
    assert presentation["colors"]["order"] == ["blue", "green", "pink", "amber"]
    assert {t: presentation["types"][t]["family"] for t in ELEMENT_TYPES} == ELEMENT_GROUPS
    assert {t: presentation["types"][t]["icon"] for t in ELEMENT_TYPES} == ELEMENT_ICONS
    assert ELEMENT_GROUPS["construct"] == "pink"
    assert ELEMENT_GROUPS["ability"] == "amber"
    assert set(ELEMENT_GROUPS.values()) == {"blue", "green", "pink", "amber"}

"""The type list and field kinds come from the pinned schema distribution, and the committed module is current."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import onlyworlds
from onlyworlds import ELEMENT_TYPES, FIELD_KINDS

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
    assert len(files) == 31
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
    assert sum(len(v) for v in FIELD_KINDS.values()) == 466  # 355 walked + 22 x 5 base + the generic pair's extra half
    assert FIELD_KINDS["pin"]["map"] == "single_link"
    assert FIELD_KINDS["pin"]["element_id"] == "single_link"
    assert FIELD_KINDS["character"]["name"] == "text"
    assert "world" not in FIELD_KINDS["character"] and "id" not in FIELD_KINDS["character"]
    # ruling collective-equipment-target: the v2 target, not the decommissioned v1 one
    assert FIELD_KINDS["collective"]["equipment"] == "multi_link"

def test_probe_fails_on_purpose() -> None:
    assert False, "CI probe: this branch is deleted after the run"

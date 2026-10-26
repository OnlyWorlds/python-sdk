"""``draught_text`` on every case of ``tests/fixtures/draught-text/``, vendored byte for byte from the npm
SDK (its ``test/fixtures/draught-text/``, written there by ``generate-draught-text.mjs`` from the SDK's
``draughtText``). Each file's sha256 is checked against the manifest before any case is replayed, each
draught's text against its ``expected.txt`` byte for byte, and each full packet against its compact twin.
A missing fixture fails, never skips."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from onlyworlds import draught_text

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "draught-text"


def _manifest() -> dict[str, str]:
    assert FIXTURE.is_dir(), f"no draught-text fixture at {FIXTURE}"
    files: dict[str, str] = json.loads((FIXTURE / "MANIFEST.json").read_text(encoding="utf-8"))["files"]
    return files


def _cases() -> list[str]:
    return sorted(p.name for p in FIXTURE.iterdir() if p.is_dir())


def _draught(name: str) -> Any:
    return json.loads((FIXTURE / name / "draught.json").read_bytes().decode("utf-8"))


def _expected(name: str) -> bytes:
    return (FIXTURE / name / "expected.txt").read_bytes()


def test_every_file_is_in_the_manifest_and_matches_its_sha256() -> None:
    files = _manifest()
    on_disk = sorted(f"{p.parent.name}/{p.name}" for case in _cases() for p in (FIXTURE / case).iterdir())
    assert sorted(files) == on_disk
    for path, sha in files.items():
        assert hashlib.sha256((FIXTURE / path).read_bytes()).hexdigest() == sha, path


def test_every_case_gives_its_expected_text_byte_for_byte() -> None:
    test_every_file_is_in_the_manifest_and_matches_its_sha256()
    cases = _cases()
    assert len(cases) >= 34
    for real in ("as-of-248", "as-of-300", "as-of-453"):
        assert real in cases and f"{real}-compact" in cases, real
    for name in cases:
        assert draught_text(_draught(name)).encode("utf-8") == _expected(name), name


def test_a_full_packet_and_its_compact_twin_give_the_same_text() -> None:
    cases = _cases()
    twins = [n for n in cases if n.endswith("-compact")]
    assert len(twins) * 2 == len(cases), "every case has its twin"
    for twin in twins:
        full = twin[: -len("-compact")]
        assert full in cases, twin
        assert _expected(full) == _expected(twin), full
        assert draught_text(_draught(full)) == draught_text(_draught(twin)), full


@pytest.mark.parametrize("bad", [None, [], "draught", 1, True, {}, {"world": None}, {"world": []}, {"world": "W"}])
def test_a_draught_that_is_not_a_mapping_or_has_no_world_mapping_is_a_type_error(bad: Any) -> None:
    with pytest.raises(TypeError):
        draught_text(bad)

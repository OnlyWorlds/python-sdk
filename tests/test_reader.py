"""Reader conformance: the shared fixture from the Atlas repo, answered from its expected.json, zero bytes touched.

The fixture stays in the Atlas repo; this test reads it in place and
skips (loudly) where it is absent. Override the path with OW_CONFORMANCE_FIXTURE.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import pytest

from onlyworlds import read_folder

FIXTURE = Path(os.environ["OW_CONFORMANCE_FIXTURE"]) if os.environ.get("OW_CONFORMANCE_FIXTURE") else None
needs_fixture = pytest.mark.skipif(
    FIXTURE is None or not FIXTURE.is_dir(),
    reason="set OW_CONFORMANCE_FIXTURE to a copy of the Atlas repo's tests/fixtures/folder-conformance",
)


def fingerprint(root: Path) -> dict[str, str]:
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    } | {str(p.relative_to(root)) + "/": "dir" for p in root.rglob("*") if p.is_dir()}


@needs_fixture
@pytest.mark.parametrize("legacy", [False, True], ids=["elements-only", "legacy-tolerant"])
def test_conformance_fixture(legacy: bool) -> None:
    expected: dict[str, Any] = json.loads((FIXTURE / "expected.json").read_text(encoding="utf-8"))
    assert expected["fixture_version"] == "1.2.1"  # 1.2.0 to 1.2.1 changed no element
    world_dir = FIXTURE / "world"
    before = fingerprint(FIXTURE)

    folder = read_folder(world_dir, legacy=legacy)

    after = fingerprint(FIXTURE)
    assert after == before, "the read mutated the fixture"

    assert folder.world is not None
    assert folder.world["id"] == expected["world"]["id"]
    assert folder.world["name"] == expected["world"]["name"]

    want = {e["id"]: e for e in expected["elements"]}
    assert set(folder.elements) == set(want)
    assert len(folder.elements) == len(expected["elements"]) == 9
    for eid, w in want.items():
        got = folder.elements[eid]
        assert got.body["name"] == w["name"]
        assert got.type == w["type"], eid  # body beats directory (declared-elsewhere is a location)
        for forbidden in w.get("must_not_have", []):
            assert forbidden not in got.body
        for link, target in w.get("links", {}).items():
            assert got.body[link] == target
    only = folder.elements["11111111-2222-4333-8444-555555555501"]
    assert only.type_inferred and "type" not in only.body  # inferred, flagged, never written onto the body
    assert folder.elements["11111111-2222-4333-8444-555555555502"].path.parent.name == "character"
    assert folder.elements["11111111-2222-4333-8444-555555555509"].body["name"] == ""
    nulls = folder.elements["11111111-2222-4333-8444-55555555550a"].body
    assert all(nulls[k] is None for k in ("description", "birth_date", "species", "traits"))
    assert "x_probe_note" in folder.elements["11111111-2222-4333-8444-555555555507"].body

    legacy_ids = {e["id"] for e in expected["legacy_elements"]}
    assert set(folder.legacy) == (legacy_ids if legacy else set())
    assert not (legacy_ids & set(folder.elements))  # never leaks into the elements/ count
    assert len(folder.all_elements()) == 9 + (1 if legacy else 0)

    skipped = {p.path.relative_to(world_dir).as_posix() for p in folder.skipped}
    assert skipped == {s["path"] for s in expected["skipped_files"]}
    for s in expected["skipped_files"]:
        assert (world_dir / s["path"]).is_file()
    assert folder.duplicates == []


def _w(path: Path, text: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8") if isinstance(text, str) else text)


def test_reader_edges(tmp_path: Path) -> None:
    _w(tmp_path / "world.json", '{"id": "w", "name": "W", "time_range_current": 5, "api": {"world_id": "srv"}}')
    _w(tmp_path / "elements" / "character" / "a.json", '{"id": "1", "name": "first"}')
    _w(tmp_path / "elements" / "character" / "b.json", '{"id": "1", "name": "dupe"}')
    _w(tmp_path / "elements" / "character" / "bom.json", b'\xef\xbb\xbf{"id": "2", "name": "bom"}')
    _w(tmp_path / "elements" / "character" / "nan.json", '{"id": "3", "x": NaN}')
    _w(tmp_path / "elements" / "character" / "list.json", "[1, 2]")
    _w(tmp_path / "elements" / "character" / "notes.txt", "not json")
    _w(tmp_path / "elements" / "Species" / "s.json", '{"id": "4", "name": "cased dir"}')
    _w(tmp_path / "elements" / "banana" / "b.json", '{"id": "5"}')
    _w(tmp_path / "spatial" / "pin" / "p.json", '{"id": "6", "map_id": "m"}')
    _w(tmp_path / "spatial" / "pin" / "q.json", '{"id": "1", "type": "pin"}')
    _w(tmp_path / "spatial" / "character" / "c.json", '{"id": "7"}')
    before = fingerprint(tmp_path)

    f = read_folder(tmp_path)

    assert fingerprint(tmp_path) == before
    assert set(f.elements) == {"1", "2", "4"}
    assert f.elements["1"].body["name"] == "first"
    assert [(d.id, d.ignored.name) for d in f.duplicates] == [("1", "b.json")]
    assert f.elements["4"].type == "species"
    assert {s.path.name for s in f.skipped} == {"nan.json", "list.json"}
    assert {p.name for p in f.ignored_dirs} == {"banana", "character"}
    assert set(f.legacy) == {"6", "1"}
    assert f.all_elements()["1"].layout == "elements"  # elements/ wins the union
    assert f.server_world_id == "srv"
    assert f.time_current == 5


def test_missing_everything_is_empty_not_an_error(tmp_path: Path) -> None:
    f = read_folder(tmp_path)
    assert f.world is None and f.elements == {} and f.skipped == []

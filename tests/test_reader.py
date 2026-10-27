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
    assert FIXTURE is not None  # needs_fixture skips the test otherwise
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


def test_a_dotfile_in_a_type_dir_is_skipped_and_a_null_time_current_reads_the_range(tmp_path: Path) -> None:
    """Skeld's two clarifications (2026-10-17): a dot-prefixed file in a type directory is a tool's
    litter, not an element, even when it holds a valid body with the same id as a real file; and
    prefer ``time_current`` means a non-null one."""
    eid = "11111111-2222-4333-8444-5555555555c1"
    d = tmp_path / "elements" / "character"
    d.mkdir(parents=True)
    (d / ".tmp-a.json").write_text(json.dumps({"id": eid, "name": "litter"}), encoding="utf-8")
    (d / f"real--{eid[-8:]}.json").write_text(json.dumps({"id": eid, "name": "real"}), encoding="utf-8")
    world = {"id": "w", "name": "W", "time_current": None, "time_range_current": 7}
    (tmp_path / "world.json").write_text(json.dumps(world), encoding="utf-8")
    f = read_folder(tmp_path)
    assert f.elements[eid].body["name"] == "real"
    assert f.duplicates == []
    assert [s.path.name for s in f.skipped] == [".tmp-a.json"]
    assert f.time_current == 7


def test_missing_everything_is_empty_not_an_error(tmp_path: Path) -> None:
    f = read_folder(tmp_path)
    assert f.world is None and f.elements == {} and f.skipped == []


def test_an_id_in_both_layouts_serves_elements_and_is_named(tmp_path: Path) -> None:
    """§4, v0.3.8 (one id, one file): a reader that finds an id in both layouts serves the
    ``elements/`` copy and SHOULD log it; ``in_both_layouts`` names it, whichever copy is newer."""
    pid, other = "11111111-2222-4333-8444-5555555555b1", "11111111-2222-4333-8444-5555555555b2"
    copies = (
        ("elements", "from elements", "2026-01-01T00:00:00Z"),
        ("spatial", "from spatial", "2026-12-31T00:00:00Z"),
    )
    for layout, name, stamp in copies:
        d = tmp_path / layout / "pin"
        d.mkdir(parents=True)
        body = {"id": pid, "name": name, "local_updated_at": stamp}
        (d / f"p--{pid[-8:]}.json").write_text(json.dumps(body), encoding="utf-8")
    only = {"id": other, "name": "only legacy"}
    (tmp_path / "spatial" / "pin" / f"q--{other[-8:]}.json").write_text(json.dumps(only), encoding="utf-8")
    f = read_folder(tmp_path)
    # elements/ wins, even against a newer spatial/ stamp
    assert f.all_elements()[pid].body["name"] == "from elements"
    assert f.all_elements()[other].body["name"] == "only legacy"
    assert f.in_both_layouts == [pid]
    assert read_folder(tmp_path, legacy=False).in_both_layouts == []


def test_a_repeated_id_keeps_the_first_file_by_code_point_on_every_platform(tmp_path: Path) -> None:
    """Names compare by code point, never as Paths: a Windows path sorts case-blind, where 'a.json'
    comes before 'B.json', so the kept file would differ between platforms."""
    d = tmp_path / "elements" / "character"
    _w(d / "a.json", '{"id": "1", "name": "lower"}')
    _w(d / "B.json", '{"id": "1", "name": "upper"}')
    f = read_folder(tmp_path)
    assert f.elements["1"].body["name"] == "upper"  # "B" (U+0042) before "a" (U+0061)
    assert [d.ignored.name for d in f.duplicates] == ["a.json"]

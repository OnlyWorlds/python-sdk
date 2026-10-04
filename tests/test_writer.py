from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from onlyworlds import FORMAT_VERSION, read_folder, write_folder
from onlyworlds.folder import world_for_disk

WORLD: dict[str, Any] = {
    "id": "49501a68-179b-4a3c-8eaf-7f46f73d5fd2",
    "name": "Sikelia",
    "description": "",
    "time_range_min": None,
    "time_range_current": -492,
    "public_read": False,
    "created_at": "2026-07-31T16:19:14.760004+00:00",
}


def el(eid: str, name: str, **extra: Any) -> dict[str, Any]:
    return {"id": eid, "type": "character", "name": name, **extra}


def test_layout_bytes_and_world(tmp_path: Path) -> None:
    out = tmp_path / "w"
    elements = {
        "character": [el("00000000-0000-7000-8000-000000000001", "Gelon", x_note={"b": 1, "a": [1.0, "Σ"]})],
        "map": [{"id": "00000000-0000-7000-8000-000000000002", "type": "map", "name": "Sicily"}],
        "zone": [],
    }
    rep = write_folder(out, WORLD, elements)
    assert rep.counts == {"character": 1, "map": 1}
    assert sorted(p.name for p in (out / "elements").iterdir()) == ["character", "map"]  # empty zone omitted
    f = out / "elements" / "character" / "gelon--00000001.json"
    raw = f.read_bytes()
    assert b"\r" not in raw and raw.endswith(b"\n")
    assert raw.decode("utf-8") == (
        "{\n"
        '  "id": "00000000-0000-7000-8000-000000000001",\n'
        '  "type": "character",\n'
        '  "name": "Gelon",\n'
        '  "x_note": {\n'
        '    "b": 1,\n'
        '    "a": [\n'
        "      1,\n"
        '      "Σ"\n'
        "    ]\n"
        "  }\n"
        "}\n"
    )
    world = json.loads((out / "world.json").read_text(encoding="utf-8"))
    # renamed IN PLACE (key order as received), nothing dropped, nothing invented but format_version
    assert list(world) == [
        "id",
        "name",
        "description",
        "time_range_min",
        "time_current",
        "public_read",
        "created_at",
        "format_version",
    ]
    assert world["time_current"] == -492
    assert world["format_version"] == FORMAT_VERSION
    assert not list(tmp_path.glob(".w.tmp-*"))


def test_world_for_disk_rules() -> None:
    both = world_for_disk({"id": "w", "name": "", "time_range_current": 1, "time_current": 2})
    assert both["time_current"] == 2 and both["time_range_current"] == 1  # neither dropped
    kept = world_for_disk({"id": "w", "name": "n", "format_version": "0.3.4"})
    assert kept["format_version"] == "0.3.4"  # carried, never rewritten
    linked = world_for_disk({"id": "w", "name": "n", "snapshot_counts": {"character": 9}})
    assert "snapshot_counts" not in linked  # v0.3.6: a non-snapshot MUST NOT carry it
    snap = world_for_disk({"id": "w", "name": "n", "snapshot_of": "s", "snapshot_counts": {"x": 9}}, {"character": 2})
    assert snap["snapshot_counts"] == {"character": 2}  # recounted from the files written, never carried
    with pytest.raises(ValueError):
        world_for_disk({"name": "no id"})
    with pytest.raises(ValueError):
        world_for_disk({"id": "w"})


def test_collision_writes_both(tmp_path: Path) -> None:
    a = "aaaaaaaa-0000-7000-8000-000011112222"
    b = "bbbbbbbb-0000-7000-8000-000011112222"
    rep = write_folder(tmp_path / "w", WORLD, {"character": [el(b, "Twin"), el(a, "Twin")]})
    names = sorted(p.name for p in (tmp_path / "w" / "elements" / "character").iterdir())
    assert names == ["twin--11112222.json", f"twin--{b}.json"]  # a (lower id) keeps the short form
    assert rep.collisions == [b]
    assert len(read_folder(tmp_path / "w").elements) == 2


def test_repeated_id_last_wins_and_cross_type_id_refused(tmp_path: Path) -> None:
    eid = "00000000-0000-7000-8000-000000000009"
    write_folder(tmp_path / "w", WORLD, {"character": [el(eid, "Old"), el(eid, "New")]})
    files = list((tmp_path / "w" / "elements" / "character").iterdir())
    assert [p.name for p in files] == ["new--00000009.json"]
    with pytest.raises(ValueError):
        write_folder(tmp_path / "x", WORLD, {"character": [el(eid, "A")], "species": [{"id": eid, "name": "B"}]})


def test_refuses_to_write_over_a_folder(tmp_path: Path) -> None:
    (tmp_path / "w").mkdir()
    (tmp_path / "w" / "keep.txt").write_text("x")
    with pytest.raises(FileExistsError):
        write_folder(tmp_path / "w", WORLD, {})
    (tmp_path / "e").mkdir()
    write_folder(tmp_path / "e", WORLD, {})  # an empty dir is fine
    assert (tmp_path / "e" / "world.json").is_file()


def test_refuses_bad_input(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        write_folder(tmp_path / "a", WORLD, {"characters": [el("x", "y")]})
    with pytest.raises(ValueError):
        write_folder(tmp_path / "b", WORLD, {"character": [{"name": "no id"}]})
    assert not list(tmp_path.iterdir())  # nothing left behind


def test_read_write_round_trip_is_byte_identical(tmp_path: Path) -> None:
    body = el("00000000-0000-7000-8000-00000000000a", "Round Trip", x_deep={"z": [None, {"y": ""}], "a": 0.25})
    write_folder(tmp_path / "one", WORLD, {"character": [body]})
    folder = read_folder(tmp_path / "one")
    assert folder.world is not None
    by_type: dict[str, list[dict[str, Any]]] = {}
    for e in folder.elements.values():
        by_type.setdefault(e.type, []).append(e.body)
    write_folder(tmp_path / "two", folder.world, by_type)
    for p in (tmp_path / "one").rglob("*.json"):
        assert (tmp_path / "two" / p.relative_to(tmp_path / "one")).read_bytes() == p.read_bytes()

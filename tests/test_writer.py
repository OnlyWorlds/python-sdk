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
    src = {"server": "https://www.onlyworlds.com", "world": "w0", "at": "2026-10-19T10:00:00.000Z"}
    slice_ = {"kind": "character", "role": "guest", "character": {"id": "c", "name": "Mira"}}
    branch = world_for_disk({"id": "w", "name": "n", "source": src, "exported_as": slice_})
    assert branch["source"] == src and branch["exported_as"] == slice_  # v0.3.9: a branch keeps its parent's
    linked = world_for_disk({"id": "w", "name": "n", "snapshot_counts": {"character": 9}})
    assert "snapshot_counts" not in linked  # v0.3.6: a non-snapshot MUST NOT carry it
    snap = world_for_disk({"id": "w", "name": "n", "snapshot_of": "s", "snapshot_counts": {"x": 9}}, {"character": 2})
    assert snap["snapshot_counts"] == {"character": 2}  # recounted from the files written, never carried
    first = {
        "source": {"server": "https://www.onlyworlds.com", "world": "w0", "at": "2026-10-01T09:00:00Z"},
        "producer": {"tool": "atlas", "version": "1.82.0", "input": "bare"},
    }
    origin = world_for_disk({"id": "w", "name": "n", "origin": first, "source": src})
    assert origin["origin"] == first and origin["source"] == src  # v0.3.16: carried as given, beside this folder's own
    none = world_for_disk({"id": "w", "name": "n", "source": src, "producer": first["producer"]})
    assert "origin" not in none  # v0.3.16: never derived from source or producer
    with pytest.raises(ValueError):
        world_for_disk({"name": "no id"})
    with pytest.raises(ValueError):
        world_for_disk({"id": "w"})


# --- v0.3.14 the producer line (§4.2): a folder made from a folder keeps its maker's ---------


def _rewrite(tmp_path: Path, world: dict[str, Any]) -> tuple[bytes, bytes]:
    """Write a folder, read it, write the read one again (a branch, a copy): both world.json bytes."""
    els = {"character": [el("00000000-0000-7000-8000-000000000001", "Gelon")]}
    write_folder(tmp_path / "a", world, els)
    a = read_folder(tmp_path / "a")
    assert a.world is not None and not a.skipped
    write_folder(tmp_path / "b", a.world, {"character": [e.body for e in a.elements.values()]})
    return (tmp_path / "a" / "world.json").read_bytes(), (tmp_path / "b" / "world.json").read_bytes()


def test_a_folder_from_a_folder_keeps_its_producer_and_unknown_keys_verbatim(tmp_path: Path) -> None:
    producer = {"tool": "azgaar-converter", "version": "0.4.0", "input": "azgaar-map"}
    world = {**WORLD, "producer": producer, "future_key": {"z": 1, "a": [2, "Σ"]}, "x_tool": True}
    a, b = _rewrite(tmp_path, world)
    assert a == b  # byte-exact: nothing dropped, reordered or re-stamped
    got = json.loads(b.decode("utf-8"))
    assert got["producer"] == producer and got["future_key"] == {"z": 1, "a": [2, "Σ"]} and got["x_tool"] is True


def test_a_folder_with_no_producer_gets_none(tmp_path: Path) -> None:
    a, b = _rewrite(tmp_path, dict(WORLD))
    assert a == b
    assert "producer" not in json.loads(b.decode("utf-8"))  # absent is the honest value; never invented


def test_an_input_word_the_package_does_not_know_reads_fine(tmp_path: Path) -> None:
    from onlyworlds.doctor import doctor_folder

    producer = {"tool": "papyrus", "version": "9", "input": "papyrus-scroll"}
    a, b = _rewrite(tmp_path, {**WORLD, "producer": producer})
    assert a == b
    folder = read_folder(tmp_path / "b")
    assert folder.world is not None and folder.world["producer"] == producer and not folder.skipped
    report = doctor_folder(folder)
    assert not [f for f in report.findings if f["element"] is None]  # nothing said about the world file


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


def test_world_json_carries_the_three_unit_settings_under_the_same_spelling():
    """Canonical 00.31.00: length_unit, mass_unit and distance_unit are wire and disk keys alike.

    Folder spec v0.3.7.
    """
    from onlyworlds.folder import world_for_disk

    units = {"length_unit": "cm", "mass_unit": "kg", "distance_unit": "km"}
    world = {"id": "w1", "name": "W", "time_range_current": 5, **units}
    out = world_for_disk(world)
    assert (out["length_unit"], out["mass_unit"], out["distance_unit"]) == ("cm", "kg", "km")
    keys = [k for k in out if k != "format_version"]
    assert keys == ["id", "name", "time_current", "length_unit", "mass_unit", "distance_unit"]

"""A fixed name held only in another case is refused with that cause (folder spec 4.8), never read as a
world with no elements; the three names are read as written; under spatial/ only the four are read."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pytest

from onlyworlds.folder import FolderNameCaseError, misnamed_fixed_name, read_folder
from onlyworlds.worldfile import WorldFileError, read_world_file

WID = "0192a000-aaaa-7bbb-8ccc-000000000001"
CID = "0192a000-aaaa-7bbb-8ccc-0000000000c1"
LONG_S = chr(0x17F) + "patial"


def _world(root: Path, world_name: str = "world.json") -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / world_name).write_text(json.dumps({"id": WID, "name": "W"}, indent=2) + "\n", encoding="utf-8")


def _element(root: Path, rel: str, eid: str = CID) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"id": eid, "name": "Ada"}, indent=2) + "\n", encoding="utf-8")


def _zip(files: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, text in files.items():
            z.writestr(name, text)
    return buf.getvalue()


W = json.dumps({"id": WID, "name": "W"})
E = json.dumps({"id": CID, "name": "Ada"})


@pytest.mark.parametrize(
    ("rel", "found", "wanted"),
    [
        ("Elements/character/ada.json", "Elements/", "elements/"),
        ("Spatial/pin/p.json", "Spatial/", "spatial/"),
        (f"{LONG_S}/pin/p.json", f"{LONG_S}/", "spatial/"),
    ],
)
def test_a_folder_holding_a_fixed_folder_only_in_another_case_raises(
    tmp_path: Path, rel: str, found: str, wanted: str
) -> None:
    _world(tmp_path)
    _element(tmp_path, rel)
    with pytest.raises(FolderNameCaseError) as exc:
        read_folder(tmp_path)
    assert (exc.value.found, exc.value.wanted) == (found, wanted)
    assert f"holds {found} where the folder format names {wanted}" in str(exc.value)


def test_a_folder_holding_world_json_only_in_another_case_raises(tmp_path: Path) -> None:
    _world(tmp_path, "World.JSON")
    with pytest.raises(FolderNameCaseError, match=r"holds World\.JSON where the folder format names world\.json"):
        read_folder(tmp_path)


def test_the_names_as_written_read_and_an_absent_folder_is_none(tmp_path: Path) -> None:
    _world(tmp_path)
    _element(tmp_path, "elements/character/ada.json")
    f = read_folder(tmp_path)
    assert f.world is not None and len(f.elements) == 1
    bare = tmp_path / "bare"
    _world(bare)
    assert len(read_folder(bare).elements) == 0


def test_under_spatial_only_the_four_are_read_as_written(tmp_path: Path) -> None:
    # Two folders: on a disk that ignores case, spatial/Pin/ and spatial/pin/ would be one directory.
    odd = tmp_path / "odd"
    _world(odd)
    _element(odd, "spatial/character/a.json", "0192a000-aaaa-7bbb-8ccc-0000000000a1")
    _element(odd, "spatial/Pin/p.json", "0192a000-aaaa-7bbb-8ccc-0000000000a2")
    f = read_folder(odd)
    assert f.legacy == {} and f.elements == {}
    good = tmp_path / "good"
    _world(good)
    _element(good, "spatial/pin/q.json", "0192a000-aaaa-7bbb-8ccc-0000000000a3")
    assert sorted(read_folder(good).legacy) == ["0192a000-aaaa-7bbb-8ccc-0000000000a3"]


@pytest.mark.parametrize(
    "files",
    [
        {"w/world.json": W, "w/Elements/character/ada.json": E},
        {"world.json": W, "ELEMENTS/character/ada.json": E},
        {"w/world.json": W, f"w/{LONG_S}/pin/p.json": E},
        {"World.JSON": W},
        {"w/World.json": W},
    ],
)
def test_a_world_file_holding_a_fixed_name_only_in_another_case_is_name_case(files: dict[str, str]) -> None:
    with pytest.raises(WorldFileError) as exc:
        read_world_file(_zip(files))
    assert exc.value.reason == "name_case"


def test_a_world_file_with_the_names_as_written_reads(tmp_path: Path) -> None:
    assert len(read_world_file(_zip({"w/world.json": W, "w/elements/character/ada.json": E})).entries) == 2
    assert len(read_world_file(_zip({"w/world.json": W, "w/notes/Elements.txt": "x"})).entries) == 2
    with pytest.raises(WorldFileError) as exc:
        read_world_file(_zip({".atlas/World.json": "{}"}))
    assert exc.value.reason == "not_a_world"


def test_misnamed_fixed_name_reads_paths() -> None:
    assert misnamed_fixed_name(["world.json", "Elements/x"]) == ("Elements/", "elements/")
    assert misnamed_fixed_name(["world.json", "elements/x", "Elements/y"]) is None
    assert misnamed_fixed_name(["world.json"]) is None
    assert misnamed_fixed_name(["elements"]) is None  # a file named elements is no folder

"""The Notion door (onlyworlds.notion) on a fixture built here from the export's believed shape.

No real Notion export has been read yet: the tree below is what the module's docstring believes
(the 32-hex suffix, ``_all.csv``, a database's rows in a folder named like its CSV, sub-pages in a
folder named like their page, relation cells as ``Title (path)``). A real export, banked beside
this file, is the fixture to come.
"""

from __future__ import annotations

import hashlib
import io
import json
import subprocess
import sys
import uuid
import zipfile
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any

import pytest

from onlyworlds import read_folder, write_folder
from onlyworlds.folder import FORMAT_VERSION
from onlyworlds.notion import (
    NOTION_NAMESPACE,
    PRODUCER_INPUT,
    ImportReport,
    category_of,
    import_notion,
    main,
    parse_name,
)

ROOT = Path(__file__).resolve().parents[1]
LINT = ROOT / "codegen" / "schema-dist" / "walk" / "lint_folder.py"
TOP = "Export-test"


def nid(name: str) -> str:
    """A stable 32-hex Notion id for a fixture page."""
    return hashlib.md5(name.encode()).hexdigest()


def eid(notion_id: str) -> str:
    return str(uuid.uuid5(NOTION_NAMESPACE, notion_id))


R, S, DC, A, B, DL, H, DQ, Q, G = (
    nid(n) for n in ("root", "sub", "db-chars", "aria", "borin", "db-locs", "harbor", "db-quests", "quest", "ghost")
)
WN = f"World Notes {R}"
WN_URL = f"World%20Notes%20{R}"
BOM = chr(0xFEFF)  # Notion's CSVs open with a byte order mark (believed)
PNG = b"\x89PNG\r\n\x1a\nnot really a picture"


def export_files() -> dict[str, bytes]:
    """The believed export, path -> bytes (under the zip's one top folder)."""
    t: dict[str, str] = {
        f"{WN}.md": (
            "# World Notes\n\n"
            f"The world of the test. See [Old Map]({WN_URL}/Old%20Map%20{S}.md) "
            f"and [Aria]({WN_URL}/Characters%20{DC}/Aria%20{A}.md).\n\n"
            f"![The map]({WN_URL}/map.png)\n\n"
            "<aside>A callout</aside>\n\n"
            f"A broken link: [Ghost](Ghost%20{G}.md).\n"
        ),
        f"{WN}/Old Map {S}.md": "# Old Map\n\nAn old map page.\n",
        f"{WN}/Characters {DC}.csv": BOM + "Name,Description,Plain Only\nAria,A sailor,x\nBorin,A smith,y\n",
        f"{WN}/Characters {DC}_all.csv": (
            BOM + "Name,Description,birthplace,Favourite Colour,Height\n"
            f"Aria,A sailor,Harbor (../Locations%20{DL}/Harbor%20{H}.md),blue,170\n"
            "Borin,A smith,Atlantis,red,tall\n"
        ),
        f"{WN}/Characters {DC}/Aria {A}.md": (
            "# Aria\n\nDescription: A sailor\n"
            f"birthplace: Harbor (../Locations%20{DL}/Harbor%20{H}.md)\n"
            "Favourite Colour: blue\nHeight: 170\n\nAria grew up by the sea.\n"
        ),
        f"{WN}/Characters {DC}/Borin {B}.md": (
            "# Borin\n\nDescription: A smith\nbirthplace: Atlantis\nFavourite Colour: red\nHeight: tall\n\n"
            "Borin works the forge.\n"
        ),
        f"{WN}/Locations {DL}.csv": BOM + "Name,Description\nHarbor,\n",
        f"{WN}/Locations {DL}/Harbor {H}.md": "# Harbor\n\nA busy port.\n",
        f"{WN}/Quests {DQ}.csv": BOM + "Name,Status,Reward\nFind the Key,Open,100 gold\n",
        f"{WN}/Quests {DQ}/Find the Key {Q}.md": "# Find the Key\n\nStatus: Open\nReward: 100 gold\n\nFind it.\n",
    }
    files = {path: text.encode("utf-8") for path, text in t.items()}
    files[f"{WN}/map.png"] = PNG
    return files


def make_zip(tmp: Path) -> Path:
    path = tmp / "Export-test.zip"
    with zipfile.ZipFile(path, "w") as zf:
        for rel, data in sorted(export_files().items()):
            zf.writestr(f"{TOP}/{rel}", data)
    return path


def make_dir(tmp: Path) -> Path:
    base = tmp / "unzipped"
    for rel, data in export_files().items():
        p = base / TOP / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    return base


def tree(root: Path, *, skip: str | None = None) -> dict[str, bytes]:
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file() and not (skip and p.relative_to(root).as_posix().startswith(skip))
    }


def bodies(out: Path) -> dict[str, dict[str, Any]]:
    """id -> body for every element the folder holds."""
    folder = read_folder(out)
    return {e.id: e.body for e in folder.elements.values()}


@pytest.fixture
def imported(tmp_path: Path) -> tuple[Path, ImportReport]:
    out = tmp_path / "world"
    return out, import_notion(make_zip(tmp_path), out)


def test_parse_name() -> None:
    assert parse_name(f"Aria Vell {A}") == ("Aria Vell", A)
    assert parse_name(f"Aria {A.upper()}") == ("Aria", A)
    assert parse_name("No id here") == ("No id here", None)
    assert parse_name(A) == ("", A)
    assert category_of("Characters") == "character"
    assert category_of(" phenomena ") == "phenomenon"
    assert category_of("SPECIES") == "species"
    assert category_of("My Characters") is None


def test_namespace_is_pinned() -> None:
    """Changing the namespace would re-id every element of every re-imported workspace."""
    assert str(NOTION_NAMESPACE) == str(uuid.uuid5(uuid.NAMESPACE_URL, "https://onlyworlds.com/ns/notion-export"))


def test_types_links_and_extensions(imported: tuple[Path, ImportReport]) -> None:
    out, report = imported
    assert report.counts == {"character": 2, "location": 1, "narrative": 3}
    els = bodies(out)
    aria, borin, harbor = els[eid(A)], els[eid(B)], els[eid(H)]
    assert aria["type"] == "character" and aria["name"] == "Aria"
    assert aria["description"] == "A sailor"
    assert aria["x_notion_body"] == "Aria grew up by the sea."  # the property lines are left out
    assert aria["birthplace"] == harbor["id"]
    assert aria["height"] == 170
    assert aria["x_notion_favourite_colour"] == "blue"  # the odd column, verbatim
    assert "x_notion_birthplace" not in aria
    assert borin["x_notion_birthplace"] == "Atlantis" and "birthplace" not in borin
    assert borin["x_notion_height"] == "tall" and "height" not in borin
    assert not any("plain" in k for el in els.values() for k in el)  # the _all CSV was read, never the plain one
    assert harbor["description"] == "A busy port."
    assert aria["x_notion_id"] == A
    assert aria["x_notion_parent"] == eid(R)


def test_untyped_rows_are_narratives(imported: tuple[Path, ImportReport]) -> None:
    out, report = imported
    quest = bodies(out)[eid(Q)]
    assert quest["type"] == "narrative"
    assert (quest["supertype"], quest["subtype"]) == ("notion", "Quests")
    assert quest["x_notion_status"] == "Open" and quest["x_notion_reward"] == "100 gold"
    assert quest["description"] == "Find it."
    assert report.untyped_databases == ["Quests"]


def test_pages_tree_links_and_media(imported: tuple[Path, ImportReport]) -> None:
    out, report = imported
    els = bodies(out)
    root, sub = els[eid(R)], els[eid(S)]
    assert root["name"] == "World Notes" and root["type"] == "narrative"
    assert "x_notion_parent" not in root
    assert sub["x_notion_parent"] == root["id"]
    assert root["characters"] == [eid(A)]  # a page link to a Character finds Narrative's field
    desc = root["description"]
    assert not desc.startswith("# World Notes")
    assert f"[Old Map]({WN_URL}/Old%20Map%20{S}.md)" in desc  # page links stay as they were
    assert "<aside>A callout</aside>" in desc
    assert f"![The map](media/notion/{WN_URL}/map.png)" in desc
    assert (out / "media" / "notion" / WN / "map.png").read_bytes() == PNG
    assert report.media == [f"media/notion/{WN}/map.png"]


def test_world_json(imported: tuple[Path, ImportReport]) -> None:
    out, _ = imported
    world = json.loads((out / "world.json").read_text(encoding="utf-8"))
    assert world["id"] == str(uuid.uuid5(NOTION_NAMESPACE, f"world:{TOP}"))
    assert world["name"] == "World Notes"
    assert world["producer"]["input"] == PRODUCER_INPUT == "notion-export"
    assert world["producer"]["tool"] == "onlyworlds"
    assert world["format_version"] == FORMAT_VERSION


def test_folder_lint_is_green(imported: tuple[Path, ImportReport]) -> None:
    """Gate 1: the dist's own folder lint on the output, its count line the output's count."""
    pytest.importorskip("yaml", reason="the dist's lint decodes the schema YAML")
    out, report = imported
    r = subprocess.run([sys.executable, str(LINT), str(out)], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert str(report.total) in r.stdout.strip().splitlines()[-1]


def test_round_trip_is_byte_equal(imported: tuple[Path, ImportReport], tmp_path: Path) -> None:
    """Gate 2: read_folder opens it, and write_folder of what it read gives the same bytes."""
    out, _ = imported
    folder = read_folder(out)
    assert not folder.skipped and folder.world is not None
    by_type: dict[str, list[dict[str, Any]]] = {}
    for el in folder.elements.values():
        by_type.setdefault(el.type, []).append(el.body)
    again = tmp_path / "again"
    write_folder(again, folder.world, by_type)
    assert tree(again) == tree(out, skip="media/")


def test_deterministic(tmp_path: Path) -> None:
    """Gate 4: the same zip twice gives byte-equal folders; the unzipped directory gives the same one."""
    src = make_zip(tmp_path)
    import_notion(src, tmp_path / "one")
    import_notion(src, tmp_path / "two")
    import_notion(make_dir(tmp_path), tmp_path / "three")
    assert tree(tmp_path / "one") == tree(tmp_path / "two") == tree(tmp_path / "three")


def test_parts_as_inner_zips(tmp_path: Path) -> None:
    """A large export holds its parts as inner zips (believed): one level is read, as one export."""
    files = sorted(export_files().items())
    outer = tmp_path / "Export-test.zip"
    with zipfile.ZipFile(outer, "w") as zf:
        for part, half in enumerate((files[::2], files[1::2]), start=1):
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w") as inner:
                for rel, data in half:
                    inner.writestr(f"{TOP}/{rel}", data)
            zf.writestr(f"Export-test-Part-{part}.zip", buf.getvalue())
    import_notion(outer, tmp_path / "parts")
    whole = tmp_path / "whole"
    whole.mkdir()
    import_notion(make_zip(whole), tmp_path / "one")
    assert tree(tmp_path / "parts") == tree(tmp_path / "one")


def test_report_names_the_odd_column_and_the_unresolved(imported: tuple[Path, ImportReport]) -> None:
    """Gate 5: a column that cannot be placed and a link that cannot be resolved each appear by name."""
    _, report = imported
    odd = [u for u in report.unplaced if (u.database, u.column) == ("Characters", "Favourite Colour")]
    assert len(odd) == 1 and odd[0].kept_as == "x_notion_favourite_colour"
    assert any(u.column == "Height" and "whole number" in u.why for u in report.unplaced)
    atlantis = [u for u in report.unresolved if u.target == "Atlantis"]
    assert len(atlantis) == 1 and atlantis[0].where == "column birthplace" and atlantis[0].source == "Borin"
    assert any(u.where == "body" and "Ghost" in u.target for u in report.unresolved)
    text = report.render()
    assert "'Favourite Colour'" in text and "'Atlantis'" in text and "Wrote" in text


def test_plan_writes_nothing(tmp_path: Path) -> None:
    out = tmp_path / "planned"
    report = import_notion(make_zip(tmp_path), out, plan_only=True)
    assert not out.exists() and report.out is None
    assert report.counts == {"character": 2, "location": 1, "narrative": 3}
    assert "Plan only: nothing written." in report.render()


def test_type_column(tmp_path: Path) -> None:
    """A database whose title names no type is typed row by row by its Type column."""
    base = tmp_path / "bestiary"
    base.mkdir()
    db = nid("bestiary")
    (base / f"Bestiary {db}.csv").write_text(
        "Name,Type,Description\nWolf,Creature,Grey\nMoonfire,phenomena,Bright\nThing,Gizmo,Odd\n", encoding="utf-8"
    )
    report = import_notion(base, tmp_path / "out")
    assert report.counts == {"creature": 1, "narrative": 1, "phenomenon": 1}
    els = {b["name"]: b for b in bodies(tmp_path / "out").values()}
    assert els["Wolf"]["type"] == "creature" and els["Wolf"]["description"] == "Grey"
    assert "x_notion_type" not in els["Wolf"]  # the cell that typed it is its type
    assert els["Thing"]["supertype"] == "notion" and els["Thing"]["x_notion_type"] == "Gizmo"
    assert len(report.ids_from_path) == 3  # rows with no page take their path's id, listed


def test_cli(tmp_path: Path) -> None:
    """Gate 6, from Python: --plan prints and writes nothing, then the write; an occupied OUT-DIR is exit 2."""
    src = make_zip(tmp_path)
    out = tmp_path / "cli"
    buf = io.StringIO()
    with redirect_stdout(buf):
        assert main([str(src), str(out), "--plan"]) == 0
    assert "Plan only" in buf.getvalue() and not out.exists()
    with redirect_stdout(io.StringIO()):
        assert main([str(src), str(out)]) == 0
    assert (out / "world.json").is_file()
    assert main([str(src), str(out)]) == 2

"""The Notion door (onlyworlds.notion) on a fixture built here from the export's believed shape,
and on two real exports.

The built tree is what the module's docstring believes (the 32-hex suffix, ``_all.csv``, a
database's rows in a folder named like its CSV, sub-pages in a folder named like their page,
relation cells as ``Title (path)``). The real ones, in ``fixtures/notion/``, are a free account's
page export with sub-pages, Markdown & CSV (Boss, 2026-10-24; invented content, no personal data):
``notion-page-export-with-subpages.zip`` with "Create folders for subpages" off, flat, every page
and CSV in one directory; ``notion-page-export-folders-locations.zip`` with it on, the same
workspace with Places renamed Locations and Home renamed Location, its folders named by title alone.
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
    assert (quest["supertype"], quest["subtype"]) == ("Article", "Quests")
    assert quest["x_notion_status"] == "Open" and quest["x_notion_reward"] == "100 gold"
    assert quest["description"] == "Find it."
    assert report.untyped_databases == ["Quests"]


def test_ids_do_not_move_with_the_supertype(imported: tuple[Path, ImportReport]) -> None:
    """No tool name in a supertype (Skeld's ruling): the fixture's ids are those 0.41.0
    gave (the sha256 of the sorted ids, one a line), on the fixture built here."""
    out, _ = imported
    ids = sorted(bodies(out))
    assert len(ids) == 6
    assert hashlib.sha256("\n".join(ids).encode()).hexdigest() == (
        "a8deaf0550063d1051c74d97f2bed47b925ae47c7d949188e28029bea147672e"
    )


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


def assert_lint_green(out: Path, report: ImportReport) -> None:
    """The dist's own folder lint on the output, its count line the output's count."""
    pytest.importorskip("yaml", reason="the dist's lint decodes the schema YAML")
    r = subprocess.run([sys.executable, str(LINT), str(out)], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert str(report.total) in r.stdout.strip().splitlines()[-1]


def assert_round_trip(out: Path, again: Path) -> None:
    """read_folder opens it, and write_folder of what it read gives the same bytes."""
    folder = read_folder(out)
    assert not folder.skipped and folder.world is not None
    by_type: dict[str, list[dict[str, Any]]] = {}
    for el in folder.elements.values():
        by_type.setdefault(el.type, []).append(el.body)
    write_folder(again, folder.world, by_type)
    assert tree(again) == tree(out, skip="media/")


def test_folder_lint_is_green(imported: tuple[Path, ImportReport]) -> None:
    """Gate 1: the dist's own folder lint on the output."""
    assert_lint_green(*imported)


def test_round_trip_is_byte_equal(imported: tuple[Path, ImportReport], tmp_path: Path) -> None:
    """Gate 2: the folder round-trips byte for byte."""
    assert_round_trip(imported[0], tmp_path / "again")


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
    assert els["Thing"]["supertype"] == "Article" and els["Thing"]["x_notion_type"] == "Gizmo"
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


# ---------------------------------------------------------------------------
# The real exports: flat (no database has a folder), and with folders named by title
# ---------------------------------------------------------------------------

REAL = ROOT / "tests" / "fixtures" / "notion" / "notion-page-export-with-subpages.zip"
#: the same workspace, Places renamed Locations and Home renamed Location, "Create folders for subpages" on
FOLDERED = ROOT / "tests" / "fixtures" / "notion" / "notion-page-export-folders-locations.zip"
CHARACTERS = ("Mara Voss", "Tobin Ashgrove", "Zéphyrine Dubois", "Old Ketch", "Brannoch O'Dell")
PLACES = ("Aurelia Harbour", "Stonewick", "O'Brannock's Rest", "Lac Élan", "The Hollow Mile")
PAGES = ("Welcome to Notion", "World overview", "Calendar and seasons")
HOMES = {
    "Mara Voss": "Aurelia Harbour",
    "Tobin Ashgrove": "Stonewick",
    "Zéphyrine Dubois": "Lac Élan",
    "Brannoch O'Dell": "O'Brannock's Rest",
}


def real_files(src: Path = REAL) -> dict[str, bytes]:
    with zipfile.ZipFile(src) as zf:
        return {i.filename: zf.read(i) for i in zf.infolist()}


def real_ids(src: Path = REAL) -> dict[str, str]:
    """Every page's title -> its Notion id, read from the zip's names."""
    out: dict[str, str] = {}
    for name in real_files(src):
        if name.endswith(".md"):
            title, notion_id = parse_name(name.rsplit("/", 1)[-1][:-3])
            assert notion_id is not None and title not in out
            out[title] = notion_id
    return out


def remade(tmp: Path, name: str, edit: dict[str, bytes | None], src: Path = REAL) -> Path:
    """A real export with entries replaced, added, or (None) removed."""
    files = {**real_files(src), **edit}
    path = tmp / name
    with zipfile.ZipFile(path, "w") as zf:
        for rel, data in sorted(files.items()):
            if data is not None:
                zf.writestr(rel, data)
    return path


def test_real_export_is_flat() -> None:
    """The fixture is what the door's flat rule is for: no database has a folder, every page sits beside the CSVs."""
    names = list(real_files())
    assert len(names) == 17 and not any("/" in n for n in names)
    assert sum(n.endswith(".csv") for n in names) == 4 and sum(n.endswith(".md") for n in names) == 13


def test_flat_rows_pair_with_their_pages(tmp_path: Path) -> None:
    """Each row once, with its page's id and text; no Narrative repeats a row; the plain pages stay pages."""
    out = tmp_path / "real"
    report = import_notion(REAL, out)
    ids = real_ids()
    assert report.counts == {"character": 5, "narrative": 8}
    assert report.pages == len(PAGES)
    assert report.ids_from_path == []
    els = list(bodies(out).values())
    assert sorted(e["name"] for e in els) == sorted(CHARACTERS + PLACES + PAGES)  # each name once
    for e in els:
        assert e["id"] == eid(ids[e["name"]]) and e["x_notion_id"] == ids[e["name"]]
    by_name = {e["name"]: e for e in els}
    assert all(by_name[n]["type"] == "character" for n in CHARACTERS)
    for n in PLACES:
        place = by_name[n]
        assert (place["type"], place["supertype"], place["subtype"]) == ("narrative", "Article", "Places")
        assert "description" not in place  # its page holds only its property line
    for n in PAGES:
        assert by_name[n]["type"] == "narrative" and "supertype" not in by_name[n]
    brannoch = by_name["Brannoch O'Dell"]
    assert brannoch["description"].startswith("## Early life")  # the heading and property lines left out
    assert "Born:" not in brannoch["description"] and brannoch["x_notion_born"] == "September 21, 1405"
    # Home is no Character field: kept verbatim, by design
    assert brannoch["x_notion_home"].startswith("O'Brannock's Rest (O'Brannock's%20Rest%20")
    assert "x_notion_home" not in by_name["Old Ketch"]
    assert sum("no folder of its own: 5 of its 5 rows paired" in n for n in report.notes) == 2


@pytest.mark.parametrize("src", [REAL, FOLDERED], ids=["flat", "foldered"])
def test_real_export_lints_round_trips_and_repeats(src: Path, tmp_path: Path) -> None:
    one = tmp_path / "one"
    report = import_notion(src, one)
    assert_lint_green(one, report)
    assert_round_trip(one, tmp_path / "again")
    import_notion(src, tmp_path / "two")
    assert tree(one) == tree(tmp_path / "two")


def test_foldered_export_layout() -> None:
    """The second fixture's folders are named by title alone: a database's beside its CSV, a page's beside the page."""
    names = list(real_files(FOLDERED))
    assert len(names) == 17
    assert "Welcome to Notion/Characters 403709f00ea1817189e3c97a2b7784e2.csv" in names
    assert sum(n.startswith("Welcome to Notion/Characters/") for n in names) == 5
    assert sum(n.startswith("Welcome to Notion/Locations/") for n in names) == 5
    assert any(n.startswith("Welcome to Notion/World overview/Calendar and seasons ") for n in names)
    assert not any(parse_name(n.rsplit("/", 1)[0])[1] for n in names if "/" in n)  # no folder carries an id


def test_title_folders_hold_rows_and_sub_pages(tmp_path: Path) -> None:
    """Rows in ``<Title>/`` pair with their pages; the Location cells resolve by id to the Location
    elements; sub-pages in ``<Title>/`` beside their page sit under it."""
    out = tmp_path / "foldered"
    report = import_notion(FOLDERED, out)
    ids = real_ids(FOLDERED)
    assert report.counts == {"character": 5, "location": 5, "narrative": 3}
    assert report.pages == len(PAGES) and report.ids_from_path == []
    els = list(bodies(out).values())
    assert sorted(e["name"] for e in els) == sorted(CHARACTERS + PLACES + PAGES)  # each name once
    for e in els:
        assert e["id"] == eid(ids[e["name"]]) and e["x_notion_id"] == ids[e["name"]]
    by_name = {e["name"]: e for e in els}
    assert all(by_name[n]["type"] == "character" for n in CHARACTERS)
    assert all(by_name[n]["type"] == "location" for n in PLACES)
    assert {n: by_name[n].get("location") for n in CHARACTERS} == {
        **{n: eid(ids[home]) for n, home in HOMES.items()},
        "Old Ketch": None,
    }
    assert not any("x_notion_location" in e for e in els)
    assert not any(u.where == "column Location" for u in report.unresolved)
    assert by_name["Brannoch O'Dell"]["description"].startswith("## Early life")
    welcome, overview = by_name["Welcome to Notion"], by_name["World overview"]
    assert "x_notion_parent" not in welcome
    assert overview["x_notion_parent"] == welcome["id"]
    assert by_name["Calendar and seasons"]["x_notion_parent"] == overview["id"]
    assert all(by_name[n]["x_notion_parent"] == welcome["id"] for n in CHARACTERS + PLACES)
    assert json.loads((out / "world.json").read_text(encoding="utf-8"))["name"] == "Welcome to Notion"


def test_title_folder_shared_with_a_page(tmp_path: Path) -> None:
    """A ``<Title>/`` folder that a page beside it with the database's title also names holds that
    page's sub-pages too: only the pages that fit a row by title and cells are rows; the others stay
    pages under that page."""
    page, sub = f"Characters {nid('cast page')}", f"Cast notes {nid('cast notes')}"
    edit: dict[str, bytes | None] = {
        f"Welcome to Notion/{page}.md": b"# Characters\n\nA page about the cast.\n",
        f"Welcome to Notion/Characters/{sub}.md": b"# Cast notes\n\nWho is who.\n",
    }
    out = tmp_path / "out"
    report = import_notion(remade(tmp_path, "shared.zip", edit, FOLDERED), out)
    ids = real_ids(FOLDERED)
    assert report.counts == {"character": 5, "location": 5, "narrative": 5} and report.ids_from_path == []
    by_name = {e["name"]: e for e in bodies(out).values()}
    assert all(by_name[n]["id"] == eid(ids[n]) for n in CHARACTERS)
    assert by_name["Mara Voss"]["location"] == eid(ids["Aurelia Harbour"])
    assert by_name["Cast notes"]["x_notion_parent"] == by_name["Characters"]["id"] == eid(nid("cast page"))
    assert (
        "database 'Characters' shares its folder Welcome to Notion/Characters/ with page"
        f" Welcome to Notion/{page}.md: 5 of its 5 rows paired" in report.render()
    )


def test_flat_relation_resolves_by_the_id_in_its_cell(tmp_path: Path) -> None:
    """A relation cell names its target as ``Title (Title%20<id>.csv)``, a file not in the zip; the id
    is the target row's page, so the link resolves once the rows carry their pages' ids. Here the
    real export retitled: Places as Locations, Home as birthplace (a Character field)."""
    edit: dict[str, bytes | None] = {}
    for rel, data in real_files().items():
        if rel.startswith("Places "):
            edit[rel] = None
            edit["Locations " + rel[len("Places ") :]] = data
        elif rel.startswith("Characters "):
            edit[rel] = data.replace(b",Home,", b",birthplace,")
        elif b"\nHome: " in data:
            edit[rel] = data.replace(b"\nHome: ", b"\nbirthplace: ")
    out = tmp_path / "out"
    report = import_notion(remade(tmp_path, "relinked.zip", edit), out)
    ids = real_ids()
    assert report.counts == {"character": 5, "location": 5, "narrative": 3} and report.ids_from_path == []
    by_name = {e["name"]: e for e in bodies(out).values()}
    assert by_name["Mara Voss"]["birthplace"] == eid(ids["Aurelia Harbour"])
    assert by_name["Zéphyrine Dubois"]["birthplace"] == eid(ids["Lac Élan"])
    assert by_name["Brannoch O'Dell"]["birthplace"] == eid(ids["O'Brannock's Rest"])
    assert "birthplace" not in by_name["Old Ketch"]
    assert not any("x_notion_birthplace" in e for e in by_name.values())
    assert all(u.where != "column birthplace" for u in report.unresolved)


def test_flat_row_without_a_unique_page_keeps_the_path_id(tmp_path: Path) -> None:
    """A row whose cells no page beside the CSV repeats, a row two pages fit, and two rows one page
    fits, stay CSV rows with no page (path ids, listed with why); those pages stay pages."""
    ids = real_ids()
    files = real_files()
    names = {parse_name(rel[:-3])[0]: rel for rel in files if rel.endswith(".md")}
    twin = "Stonewick " + "0" * 32 + ".md"
    edit: dict[str, bytes | None] = {
        names["Aurelia Harbour"]: b"# Aurelia Harbour\n\nKind: Village\n",  # a cell the row does not hold
        twin: b"# Stonewick\n\nKind: Town\n",  # a second page that fits the row
    }
    for rel, data in files.items():
        if rel.startswith("Places "):
            edit[rel] = data + b"\r\nThe Hollow Mile,Road"  # a second row the page fits (no final newline, as Notion)
    out = tmp_path / "out"
    report = import_notion(remade(tmp_path, "unsure.zip", edit), out)
    whys = {p.path: p.why for p in report.ids_from_path}
    places = next(d.path for d in report.databases if d.title == "Places")
    assert set(whys) == {f"{places}#row {n}" for n in (2, 3, 6, 7)}
    assert "no page beside its CSV carries the row's title and cells" in whys[f"{places}#row 2"]
    assert "2 pages beside its CSV fit the row" in whys[f"{places}#row 3"]
    assert whys[f"{places}#row 6"] == whys[f"{places}#row 7"]
    assert f"{names['The Hollow Mile']} fits it and another row" in whys[f"{places}#row 6"]
    els = list(bodies(out).values())
    rows = [e for e in els if e.get("subtype") == "Places"]
    assert len(rows) == 6
    pages = sorted(e["name"] for e in els if "subtype" not in e and e["type"] == "narrative")
    assert pages == sorted([*PAGES, "Aurelia Harbour", "Stonewick", "Stonewick", "The Hollow Mile"])
    assert eid(ids["Aurelia Harbour"]) not in {e["id"] for e in rows}
    assert "'Places' has no folder of its own: 2 of its 6 rows paired" in report.render()

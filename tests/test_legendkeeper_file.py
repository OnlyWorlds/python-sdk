"""The LegendKeeper door's file source (onlyworlds.legendkeeper.FileSource) on a real export.

``fixtures/legendkeeper/the-quay-world.lk`` is the file LegendKeeper gave on 2026-10-23 (export
version 1) for a project made on a 14-day Pro trial, nothing paid (read
for secrets, none found). What was typed: six pages, Ada Okafor, Mara
Voss, The quay, The ferry crossing, The Ferry Guild and The ledger of the first crossing, with no
tags, properties or links; the project home renamed "The quay world", and three
"Untitled" pages (two empty strays, one made from the Character template). The rest is the
tutorial and templates LegendKeeper seeds a new project with: 3 hidden tabs, 13 Secret blocks,
maps, a board and a timeline. Nothing in the project is a hidden page. Banked as a scrubbed
copy: the account's ``createdBy`` id a placeholder of the same
length, every other byte as exported; the door's folder from it is the unscrubbed file's.

The JSON type of the same export (a minute later; found equal but for ``exportId``,
``exportedAt`` and ``hash``, pretty-printed) is not banked, at 576 KB: ``json_twin`` makes it from
the ``.lk`` the same way. The real twin was checked to give a byte-identical folder when this
door was built.

``fixtures/legendkeeper/the-quay-world-3.json`` is her third export of the same project, the JSON
type, a few hours on: Ada Okafor now mentions Mara Voss and
carries a tag, and "The quay map" is a map of her own with two pins: "The quay", on her page The
quay, and one near the map's right edge with no name and no uri (the name she typed was not kept).
Five map documents in three cases: her map (an image address and bounds), the tutorial's Realm of
Tutoria (a bare asset id, bounds, 16 pins with no name of their own) and three templates' maps
with no ``map`` object at all. Banked as a scrubbed copy: the account's
``createdBy`` id and the map image's asset id each a placeholder of the same length; LegendKeeper's
tutorial asset ids and its authors' ids as exported, and every other byte.
"""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import re
import subprocess
import sys
import uuid
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any

import pytest

from onlyworlds import read_folder
from onlyworlds.folder import FORMAT_VERSION
from onlyworlds.legendkeeper import (
    LEGENDKEEPER_NAMESPACE,
    PRODUCER_INPUT_FILE,
    FileSource,
    ImportReport,
    SourceError,
    import_legendkeeper,
    main,
)

ROOT = Path(__file__).resolve().parents[1]
LINT = ROOT / "codegen" / "schema-dist" / "walk" / "lint_folder.py"
EXPORT = Path(__file__).resolve().parent / "fixtures" / "legendkeeper" / "the-quay-world.lk"
SHA256 = "5ee673bd78e4cf542f069be57698af50b6dead90ad11b29852a889a85278ec6f"
HOME = "ajkxoqw3"  # The quay world: the first top-level resource, which keys the ids
ADA, CHARACTER, WIKI = "p805c6i9", "nj687ndp", "oqwc8iom"
TYPED_BY_HAND = {
    "Ada Okafor": "Ada keeps the quay ledger and knows every crossing by its number. She trusts Mara Voss's routes.",
    "Mara Voss": "Mara plans the ferry routes from the quay to the far shore, and argues with Ada about the ledger.",
    "The quay": "The stone quay where the ferry docks. The ledger is kept in the small office at its landward end.",
    "The ferry crossing": "A forty-minute crossing between the quay and the far shore, run on a rope in good weather.",
    "The Ferry Guild": "The guild that owns the ferry and the rope. Ada and Mara both answer to it.",
    "The ledger of the first crossing": "The first entry reads: one crossing, eleven passengers, no losses.",
}
HIDDEN_PAGES = {"Character: Backstory", "Untitled: Backstory", "Location: History"}
SECRET_OWNERS = {
    "Scene", "Technology", "Artifact", "Quest", "Creature", "Country", "Myth",
    "Ethnicity", "Character", "Organization", "Event", "Untitled", "Location",
}  # fmt: skip
# The tutorial board 'Main' adds a Map, 51 Pins (12 cards, 39 notes and texts), 39 Narratives, 2 Relations
# (its arrows between two cards or frames, not to themselves), 14 Zones and 56 Markers (its frames):
# test_legendkeeper_boards.py counts them.
COUNTS = {
    "character": 2,
    "creature": 1,
    "event": 29,
    "location": 1,
    "map": 4 + 1,
    "marker": 56,
    "narrative": 52 + 39 + 4,  # + the timeline's Narrative and its three lanes' (0.56.0)
    "pin": 16 + 51,
    "relation": 3 + 2,
    "zone": 14,
}

# The first export's folder as 0.41.0 wrote it, before Maps and the Article supertype: the sha256 of
# every element file (path, NUL, bytes, NUL, in path order; world.json aside, it names the version)
# and of the element ids, one a line, sorted.
OLD_FOLDER = "2a16370b97b1c9e1c7fe175a388c7b8362a2a331f92f3cc7fea09acc330610da"
OLD_IDS = "bb8b8c0ebeafb4b82050351b5b9683bd3ea98c312cb139b8e07f00f4c1ee435c"


def eid(lk_id: str, pid: str = HOME) -> str:
    return str(uuid.uuid5(LEGENDKEEPER_NAMESPACE, f"legendkeeper:{pid}:{lk_id}"))


def export() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(gzip.decompress(EXPORT.read_bytes()))
    return data


def write_lk(tmp: Path, data: dict[str, Any], name: str = "variant.lk") -> Path:
    path = tmp / name
    path.write_bytes(gzip.compress(json.dumps(data, separators=(",", ":")).encode("utf-8")))
    return path


def json_twin(tmp: Path) -> Path:
    """The JSON type of the export: plain, pretty-printed, its own exportId, exportedAt and hash."""
    data = export()
    data.update(exportId="qgpje3jc", exportedAt="2026-10-23T07:59:39.853Z", hash="0" * 64)
    path = tmp / "the-quay-world.json"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def run(tmp: Path, src: Any = EXPORT, name: str = "world", **kw: Any) -> tuple[Path, ImportReport]:
    out = tmp / name
    return out, import_legendkeeper(src, out_dir=out, **kw)


def bodies(out: Path) -> dict[str, dict[str, Any]]:
    return {e.id: e.body for e in read_folder(out).elements.values()}


def by_name(out: Path) -> dict[str, list[dict[str, Any]]]:
    named: dict[str, list[dict[str, Any]]] = {}
    for b in bodies(out).values():
        if b["type"] != "pin":  # a pin is named as the element it places: of_type(out, "pin") reads them
            named.setdefault(b["name"], []).append(b)
    return named


def one(out: Path, name: str) -> dict[str, Any]:
    (body,) = by_name(out)[name]
    return body


def tree(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def visible(out: Path) -> str:
    return json.dumps([b for b in bodies(out).values() if b.get("hidden") is not True])


# ---------------------------------------------------------------------------


def test_the_fixture_is_the_file_seethe_exported() -> None:
    assert hashlib.sha256(EXPORT.read_bytes()).hexdigest() == SHA256
    data = export()
    assert data["version"] == 1 and len(data["resources"]) == data["resourceCount"] == 41
    assert PRODUCER_INPUT_FILE == "legendkeeper-export"


def test_the_real_project_becomes_the_element_set(tmp_path: Path) -> None:
    out, report = run(tmp_path)
    assert report.counts == COUNTS
    assert report.total == sum(COUNTS.values()) == len(bodies(out))
    typed = {t.name: (t.type, t.by) for t in report.typed if t.name in ("Character", "Location", "Event")}
    assert typed == {
        "Character": ("character", "tag 'character'"),
        "Location": ("location", "tag 'location'"),
        "Event": ("event", "tag 'event'"),
    }
    world = json.loads((out / "world.json").read_text(encoding="utf-8"))
    assert world["id"] == str(uuid.uuid5(LEGENDKEEPER_NAMESPACE, f"legendkeeper:{HOME}"))
    assert world["name"] == "The quay world" and world["format_version"] == FORMAT_VERSION
    assert world["producer"]["tool"] == "onlyworlds" and world["producer"]["input"] == "legendkeeper-export"


def test_the_six_hand_typed_pages_with_their_text(tmp_path: Path) -> None:
    out, _ = run(tmp_path)
    for name, text in TYPED_BY_HAND.items():
        body = one(out, name)
        assert body["type"] == "narrative" and body["supertype"] == "Article", name  # no tags: untyped
        assert body["description"] == text, name
        assert "hidden" not in body, name
    assert one(out, "Ada Okafor")["id"] == eid(ADA)
    # the three Untitled: two strays (one blank, one empty page) and the one made from a template
    untitled = by_name(out)["Untitled"]
    assert sorted(b["type"] for b in untitled) == ["character", "narrative", "narrative"]
    assert sum(1 for b in untitled if "description" in b) == 1


def test_the_hidden_tabs_are_hidden_narratives(tmp_path: Path) -> None:
    out, report = run(tmp_path)
    for name in HIDDEN_PAGES:
        page = one(out, name)
        assert page["hidden"] is True and page["type"] == "narrative", name
        assert page["story"].startswith("Here's a space for elaborating on this"), name
    backstory = one(out, "Character: Backstory")
    assert backstory["characters"] == [eid(CHARACTER)] and backstory["x_legendkeeper_parent"] == eid(CHARACTER)
    assert backstory["x_legendkeeper_document"] == "ro4mhiqb"
    assert backstory["id"] == str(
        uuid.uuid5(LEGENDKEEPER_NAMESPACE, f"legendkeeper:{HOME}:document:{CHARACTER}:ro4mhiqb")
    )
    assert "elaborating on this character's backstory" not in visible(out)
    assert one(out, "Location: History")["locations"] == [eid("v1cjkvea")]
    assert report.hidden.documents == 3


def test_secret_blocks_are_hidden_narratives_never_in_a_visible_description(tmp_path: Path) -> None:
    out, report = run(tmp_path)
    secrets = {b["name"]: b for b in bodies(out).values() if b["name"].endswith(": Secret")}
    assert {n.removesuffix(": Secret") for n in secrets} == SECRET_OWNERS
    for body in secrets.values():
        assert body["hidden"] is True and "information that only admins can see" in body["story"]
    assert "only admins can see" not in visible(out)
    assert "Secret" not in json.dumps([b.get("description", "") for b in bodies(out).values() if not b.get("hidden")])
    character = secrets["Character: Secret"]
    assert character["characters"] == [eid(CHARACTER)]
    assert character["id"] == str(
        uuid.uuid5(LEGENDKEEPER_NAMESPACE, f"legendkeeper:{HOME}:secret:{CHARACTER}:trbktjzu:1")
    )
    assert report.hidden.secret_blocks == 13 and report.hidden.secrets_inside == 0
    text = report.render()
    assert "3 hidden pages on a visible resource, each its own Narrative" in text
    assert "13 secret blocks in a visible page, each its own Narrative" in text


def test_the_lk_and_the_json_give_byte_identical_folders(tmp_path: Path) -> None:
    one_, r1 = run(tmp_path, EXPORT, name="lk")
    two, r2 = run(tmp_path, json_twin(tmp_path), name="json")
    assert tree(one_) == tree(two)
    assert r1.counts == r2.counts
    assert "export l6bjxemb" in r1.render() and "export qgpje3jc" in r2.render()  # the report names each


def test_two_runs_are_byte_identical(tmp_path: Path) -> None:
    one_, _ = run(tmp_path, name="one")
    two, _ = run(tmp_path, name="two")
    assert tree(one_) == tree(two)


def test_plan_writes_nothing(tmp_path: Path) -> None:
    out = tmp_path / "planned"
    report = import_legendkeeper(EXPORT, out_dir=out, plan_only=True)
    assert not out.exists() and report.out is None and report.counts == COUNTS
    assert "Plan only: nothing written." in report.render()


def test_folder_lint_passes_with_the_hidden_mark(tmp_path: Path) -> None:
    """The dist's lint: no problem at all, the 16 hidden marks included (``hidden`` a folder key
    since schema-dist serial 53), and its count line the output's count."""
    pytest.importorskip("yaml", reason="the dist's lint decodes the schema YAML")
    out, report = run(tmp_path)
    r = subprocess.run([sys.executable, str(LINT), str(out)], capture_output=True, text=True)
    lines = r.stdout.strip().splitlines()
    assert str(report.total) in lines[-1], r.stdout + r.stderr
    problems = [line for line in lines[:-1] if not line.startswith("walk note:")]
    hidden = sum(1 for b in bodies(out).values() if b.get("hidden") is True)
    assert hidden == 16
    assert problems == [], r.stdout + r.stderr
    assert r.returncode == 0, r.stdout + r.stderr


def test_templates_are_marked_and_tutorial_pages_imported(tmp_path: Path) -> None:
    out, report = run(tmp_path)
    templates = sorted(b["name"] for b in bodies(out).values() if b.get("x_legendkeeper_template") is True)
    assert templates == sorted(SECRET_OWNERS - {"Untitled"})
    assert "x_legendkeeper_template" not in one(out, "Ada Okafor")
    wiki = one(out, "Wiki City")  # a tutorial page, imported like the rest
    assert wiki["x_legendkeeper_tags"] == ["city", "guide"]
    assert "- [x] **Create a new project**" in wiki["description"]
    assert any("templates folder" in n and "'Character'" in n for n in report.notes)
    assert not any("its parent templates" in n for n in report.notes)


def test_the_editor_document_reads_as_the_api_blocks(tmp_path: Path) -> None:
    out, report = run(tmp_path)
    home = one(out, "The quay world")["description"]
    assert home.startswith("## Welcome to LegendKeeper\n\n> [!info]\n> This page is your **Project Home**")
    assert "[Join our Discord Community](https://lk.quest/discord)" in home
    assert "https://www.youtube.com/embed/YJRIoy4Ugwc" in home  # a block-youtube extension: an embed
    assert one(out, "The quay world")["x_legendkeeper_mentions"][0] == eid(WIKI)
    assert "![](https://assets.legendkeeper.com/d0676b37" in one(out, "Shortcut Shoals")["description"]
    assert "  - List view for the big chronological picture," in one(out, "Temple of Time")["description"]
    character = next(b for b in by_name(out)["Character"] if b["type"] == "character")
    assert "> *Something the character has said.*" in character["description"]
    peninsula = one(out, "Property Peninsula")
    assert peninsula["image_url"].startswith("https://assets.legendkeeper.com/")
    assert peninsula["x_legendkeeper_defenses"][0] == {"name": "Wall Integrity", "current": 85, "max": 100}
    assert peninsula["x_legendkeeper_aliases"] == ["New User Guide", "Tutoria"]
    notes = "\n".join(report.notes)
    for needle in ("19 inline icons", "18 sidebar properties showing", "20 empty collection", "block-subpage-index"):
        assert needle in notes, needle
    assert [(n.kind, n.resource) for n in report.not_imported].count(("board", "Board Bastion")) == 0  # a Map now


def test_the_timeline_becomes_events_with_raw_minutes(tmp_path: Path) -> None:
    out, _ = run(tmp_path)
    events = [b for b in bodies(out).values() if b["type"] == "event" and "x_legendkeeper_start" in b]
    assert len(events) == 28
    raid = one(out, "Party raids the Spiral Stair")
    assert raid["x_legendkeeper_start"] == {"minutes": 631177920}  # the export gives no formatted date
    assert raid["x_legendkeeper_end"] == {"minutes": 631179360}
    assert raid["x_legendkeeper_lane"] == "Players" and raid["x_legendkeeper_calendar"] == "fhynh6n4"
    assert raid["x_legendkeeper_parent"] == eid("qoi1yh5t")


def test_a_hidden_resource_in_the_file(tmp_path: Path) -> None:
    """No resource of the real project is hidden: the same file with Ada's mark set, and a page under her."""
    data = export()
    for r in data["resources"]:
        if r["id"] == ADA:
            r["isHidden"] = True
        if r["name"] == "The ledger of the first crossing":
            r["parentId"] = ADA
    out, report = run(tmp_path, write_lk(tmp_path, data))
    assert one(out, "Ada Okafor")["hidden"] is True and one(out, "Ada Okafor")["description"].startswith("Ada keeps")
    assert one(out, "The ledger of the first crossing")["hidden"] is True
    assert (report.hidden.resources, report.hidden.under_hidden) == (1, 1)
    assert "Ada keeps" not in visible(out) and report.counts == COUNTS


def test_project_id_keys_the_ids_as_the_api_road_does(tmp_path: Path) -> None:
    out, _ = run(tmp_path, FileSource(EXPORT, "proj1234"))
    assert one(out, "Ada Okafor")["id"] == eid(ADA, "proj1234")
    world = json.loads((out / "world.json").read_text(encoding="utf-8"))
    assert world["id"] == str(uuid.uuid5(LEGENDKEEPER_NAMESPACE, "legendkeeper:proj1234"))
    out2, _ = run(tmp_path, EXPORT, name="path", project_id="proj1234")
    assert tree(out) == tree(out2)
    with pytest.raises(ValueError):
        import_legendkeeper(FileSource(EXPORT), "other", tmp_path / "x")


def test_what_is_not_an_export_is_refused(tmp_path: Path) -> None:
    bad = tmp_path / "bad.lk"
    bad.write_bytes(gzip.compress(b"not json"))
    with pytest.raises(ValueError, match="not a LegendKeeper export"):
        FileSource(bad)
    bad.write_text('{"resources": "no"}', encoding="utf-8")
    with pytest.raises(ValueError, match="no resources list"):
        FileSource(bad)
    with pytest.raises(FileNotFoundError):
        FileSource(tmp_path / "missing.lk")
    with pytest.raises(SourceError):
        FileSource(EXPORT).get("/projects/x/resources/nope")


def test_cli_reads_the_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LEGENDKEEPER_API_KEY", raising=False)  # the file needs no key
    out = tmp_path / "cli"
    buf = io.StringIO()
    with redirect_stdout(buf):
        assert main(["--file", str(EXPORT), str(out), "--plan"]) == 0
    assert "Plan only" in buf.getvalue() and not out.exists()
    with redirect_stdout(io.StringIO()):
        assert main(["--file", str(EXPORT), "--map", "quest=Narrative", str(out)]) == 0
    assert tree(out)
    err = io.StringIO()
    with redirect_stderr(err), redirect_stdout(io.StringIO()):
        assert main(["--file", str(EXPORT), str(out)]) == 2  # not empty
        assert main(["--file", str(tmp_path / "missing.lk"), "--plan"]) == 2
        assert main(["--file", str(EXPORT), "--key-file", str(EXPORT), "--plan"]) == 2
    assert "missing.lk" in err.getvalue()


# --- the untyped supertype and the first export's folder ------------------------


def element_digests(out: Path) -> tuple[str, str]:
    """(the folder, the ids) as OLD_FOLDER and OLD_IDS were taken: Maps and Pins aside, what a board
    made (each carries x_legendkeeper_board_map) and a timeline's Narratives (supertype Timeline, since
    0.56.0), Article read back as 0.41.0's supertype, so only the rule's own change is undone."""
    h = hashlib.sha256()
    for p in sorted(out.rglob("*")):
        rel = p.relative_to(out).as_posix()
        skip = ("elements/map/", "elements/pin/", "records/")  # the board's records are new, beside the elements
        if p.is_file() and p.name != "world.json" and not rel.startswith(skip):
            raw = p.read_bytes().replace(b'"supertype": "Article"', b'"supertype": "legendkeeper"')
            if b'"x_legendkeeper_board_map":' not in raw and b'"supertype": "Timeline"' not in raw:
                h.update(rel.encode() + b"\0" + raw + b"\0")
    ids = sorted(
        b["id"]
        for b in bodies(out).values()
        if b["type"] not in ("map", "pin") and "x_legendkeeper_board_map" not in b and b.get("supertype") != "Timeline"
    )
    return h.hexdigest(), hashlib.sha256("\n".join(ids).encode()).hexdigest()


def test_the_first_export_gives_its_old_folder_but_for_the_supertype(tmp_path: Path) -> None:
    """No tool name in a supertype (as ruled): untyped is Article now,
    and nothing else of the first export's folder moved, its ids least of all; its maps are added."""
    out, report = run(tmp_path)
    assert element_digests(out) == (OLD_FOLDER, OLD_IDS)
    untyped = [
        b
        for b in bodies(out).values()
        if b["type"] == "narrative"
        and "supertype" in b
        and "x_legendkeeper_board_map" not in b  # a board's notes: Note
        and b["supertype"] != "Timeline"  # a timeline's Narratives
    ]
    assert untyped and {b["supertype"] for b in untyped} == {"Article"}
    assert not any(
        "legendkeeper" in str(b.get("supertype", "")) + str(b.get("subtype", "")) for b in bodies(out).values()
    )
    assert "(supertype Article)" in report.render()


# --- the third export: maps and pins -------------------------------------------

EXPORT3 = EXPORT.parent / "the-quay-world-3.json"
SHA256_3 = "8d80c57e2aac45301a9d6cc1d76019dcf27bfd9ca249af9438463eeb1349ec29"
COUNTS_3 = {
    "character": 2,
    "creature": 1,
    "event": 29,
    "location": 1,
    "map": 5 + 1,
    "marker": 56,
    "narrative": 54 + 39 + 4,
    "pin": 18 + 51,
    "relation": 3 + 2,
    "zone": 14,
}  # the board's elements added, as in COUNTS
QUAY_MAP, QUAY, TUTORIA, LOCATION = "ha7uu4sb", "sz2hbafh", "cdtsrn5b", "v1cjkvea"
CORNER = "uhljd0gj"  # the second pin on the quay map: no name, no uri
ASSET = re.compile(
    r"https://(?:dev-)?assets\.legendkeeper\.com/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"
)
#: The same-length placeholder for the map image's asset id
MAP_ASSET = "00000000-0000-4000-8000-000000000001"
#: the map image's real asset id and the account's id, by hash (sha256), so neither is in the package
MAP_ASSET_SHA256 = "d04851f3065f8a3cc2d7624db15d65a8ca528f0d1978dd5f2af89c3cb21e27fe"
ACCOUNT_SHA256 = "fceeab8b4d7652711e65241ff1c880b3bbb28fb71e63ca5815b278d7acc74156"
CREATED_BY = re.compile(r'"createdBy": ?"([^"]*)"')
MAPLESS = {"Creature: Habitat Map", "Country: Map", "Location: Map"}


def map_id(rid: str, did: str) -> str:
    return str(uuid.uuid5(LEGENDKEEPER_NAMESPACE, f"legendkeeper:{HOME}:map:{rid}:{did}"))


def export3() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(EXPORT3.read_text(encoding="utf-8"))
    return data


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def write_json(tmp: Path, data: dict[str, Any], name: str = "variant.json") -> Path:
    path = tmp / name
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def map_doc(data: dict[str, Any], rid: str) -> dict[str, Any]:
    (doc,) = (d for r in data["resources"] if r["id"] == rid for d in r["documents"] if d["type"] == "map")
    found: dict[str, Any] = doc
    return found


def of_type(out: Path, etype: str) -> dict[str, dict[str, Any]]:
    return {b["name"]: b for b in bodies(out).values() if b["type"] == etype}


def lint_ok(out: Path, total: int) -> None:
    """The dist's lint: no problem at all (as test_folder_lint_passes_with_the_hidden_mark)."""
    r = subprocess.run([sys.executable, str(LINT), str(out)], capture_output=True, text=True)
    lines = r.stdout.strip().splitlines()
    assert str(total) in lines[-1], r.stdout + r.stderr
    problems = [line for line in lines[:-1] if not line.startswith("walk note:")]
    assert problems == [], r.stdout + r.stderr
    assert r.returncode == 0, r.stdout + r.stderr


def asset_uuids(text: str) -> set[str]:
    return set(ASSET.findall(text))


def test_the_third_export_is_banked_with_no_account_asset_or_id() -> None:
    raw = EXPORT3.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == SHA256_3 and len(raw) == 581_870  # the size she exported
    text = raw.decode("utf-8")
    found = asset_uuids(text)
    assert MAP_ASSET in found and MAP_ASSET_SHA256 not in {sha(u) for u in found}
    assert ACCOUNT_SHA256 not in {sha(a) for a in CREATED_BY.findall(text)}
    # every other uuid on LegendKeeper's asset hosts is LegendKeeper's own tutorial content: in the first export too
    first = gzip.decompress(EXPORT.read_bytes()).decode("utf-8")
    assert found - {MAP_ASSET} <= asset_uuids(first) and MAP_ASSET not in first
    assert ACCOUNT_SHA256 not in {sha(a) for a in CREATED_BY.findall(first)}
    # the patterns catch what they are for (a made-up uuid and account id, never a real one)
    planted = '"url": "https://assets.legendkeeper.com/12345678-abcd-4bcd-8bcd-123456789abc.png", "createdBy": "cx"'
    assert asset_uuids(planted) == {"12345678-abcd-4bcd-8bcd-123456789abc"} and CREATED_BY.findall(planted) == ["cx"]
    assert not asset_uuids(planted) <= asset_uuids(first)
    assert len(export3()["resources"]) == export3()["resourceCount"] == 43


def test_the_third_export_becomes_the_element_set(tmp_path: Path) -> None:
    out, report = run(tmp_path, EXPORT3)
    assert report.counts == COUNTS_3 and report.total == len(bodies(out)) == 113 + 163 + 4  # 163 from the board
    assert [(m.name, m.width, m.height, m.pins, m.image, m.mapless, m.max_zoom) for m in report.maps] == [
        ("The Realm of Tutoria: Main", 10000, 7000, 16, "id", False, 6),
        ("Creature: Habitat Map", None, None, 0, "none", True, None),
        ("The quay map: Main", 800, 600, 2, "url", False, 2),
        ("Country: Map", None, None, 0, "none", True, None),
        ("Location: Map", None, None, 0, "none", True, None),
    ]
    assert report.pins_unlinked == ["'Untitled pin (uhljd0gj)' on 'The quay map: Main': no uri; a Pin with no element"]
    assert report.hidden.maps == report.hidden.pins == 0
    assert not any(n.kind == "map" for n in report.not_imported)
    ada = one(out, "Ada Okafor")
    assert ada["x_legendkeeper_mentions"] == [eid("mna7xe5q")] and ada["x_legendkeeper_tags"] == ["keeper"]
    text = report.render()
    assert "'The Realm of Tutoria: Main': 10000 x 7000, 16 pins," in text
    assert "positions scaled by 2^6 = 64" in text and "positions scaled by 2^2 = 4" in text
    assert any(n.startswith("18 pins placed: LegendKeeper's pos is [y, x] in zoom-0 units") for n in report.notes)


def test_the_quay_map_and_its_two_pins(tmp_path: Path) -> None:
    out, report = run(tmp_path, EXPORT3)
    quay_map = of_type(out, "map")["The quay map: Main"]
    assert quay_map["id"] == map_id(QUAY_MAP, "bkxigc0g")
    assert (quay_map["width"], quay_map["height"]) == (800, 600)
    assert quay_map["image_url"] == f"https://assets.legendkeeper.com/{MAP_ASSET}.png"  # the address as given
    assert "location" not in quay_map  # its resource is a Narrative: kept by element id
    assert quay_map["x_legendkeeper_resource"] == eid(QUAY_MAP)
    assert quay_map["x_legendkeeper_document"] == "bkxigc0g"
    assert quay_map["x_legendkeeper_bounds"] == {"min_x": 0, "max_x": 800, "min_y": -600, "max_y": 0}
    assert quay_map["x_legendkeeper_max_zoom"] == 2 and "x_legendkeeper_map" not in quay_map  # locatorId = mapId
    pin = of_type(out, "pin")["The quay"]
    assert pin["map"] == quay_map["id"]
    assert (pin["element_type"], pin["element_id"]) == ("narrative", eid(QUAY))
    # [y, x] = [-27.5, 32] in zoom-0 units, max_zoom 2: image pixel (128, 110) from the top left, y from the bottom
    assert (pin["x"], pin["y"]) == (128, 490)
    assert pin["x_legendkeeper_pos"] == [-27.5, 32]
    assert pin["x_legendkeeper_pin"] == {
        "iconGlyph": "book-open-cover", "iconColor": "#3b82f6", "iconShape": "pin-medium",
        "labelSize": "medium", "labelVisibility": "hover",
    }  # fmt: skip
    assert pin["x_legendkeeper_id"] == "ekns6z68" and pin["x_legendkeeper_uri"] == f"lk://resources/{QUAY}"
    assert pin["id"] == str(uuid.uuid5(LEGENDKEEPER_NAMESPACE, f"legendkeeper:{HOME}:pin:{QUAY_MAP}:bkxigc0g:ekns6z68"))
    assert "hidden" not in pin and "description" not in pin
    corner = of_type(out, "pin")[f"Untitled pin ({CORNER})"]  # no name, no uri: LegendKeeper's fallback
    assert corner["map"] == quay_map["id"] and "element_id" not in corner and "element_type" not in corner
    assert corner["x_legendkeeper_pos"] == [-131.11831103678927, 199.31438127090297]
    assert (corner["x"], corner["y"]) == (797, 76)  # 797.26 and 75.53: near the right edge, low on the map
    assert "x_legendkeeper_uri" not in corner and corner["x_legendkeeper_id"] == CORNER
    assert f"'Untitled pin ({CORNER})' (pin {CORNER} on 'The quay map: Main')" in report.pins_named
    text = report.render()
    assert "'The quay map: Main': 800 x 600, 2 pins, image_url LegendKeeper's address, positions scaled by 2^2 = 4" in (
        text
    )
    assert "loads only as long as that account's asset does" in text


def test_the_bare_id_map_and_its_unnamed_pins(tmp_path: Path) -> None:
    out, report = run(tmp_path, EXPORT3)
    realm = of_type(out, "map")["The Realm of Tutoria: Main"]
    assert "image_url" not in realm  # a bare asset id is never written as a URL
    assert realm["x_legendkeeper_map_id"] == "ckt3hmegk00023h677l0o5ff9"
    assert (realm["width"], realm["height"], realm["x_legendkeeper_resource"]) == (10000, 7000, eid(TUTORIA))
    pins = [b for b in bodies(out).values() if b["type"] == "pin" and b["map"] == realm["id"]]
    assert len(pins) == 16 and len(report.pins_named) == 17  # and the quay map's corner pin
    elements = bodies(out)
    for pin in pins:
        target = elements[pin["element_id"]]
        assert pin["name"] == target["name"]  # no name of its own: named as LegendKeeper shows it
        assert pin["x_legendkeeper_uri"] == f"lk://resources/{target['x_legendkeeper_id']}"
        assert pin["x_legendkeeper_pin"] == {"isSynced": True}
        assert 0 <= pin["x"] <= realm["width"] and 0 <= pin["y"] <= realm["height"]
        assert any(f"{pin['name']!r} (pin {pin['x_legendkeeper_id']} on" in p for p in report.pins_named)
    wiki = next(p for p in pins if p["name"] == "Wiki City")
    assert wiki["x_legendkeeper_pos"] == [-24.289565058479525, 55.5190058479532]
    assert (wiki["x"], wiki["y"]) == (3553, 5445)  # max_zoom 6: 55.519 * 64 = 3553.22, -24.290 * 64 + 7000 = 5445.47
    assert "its image a LegendKeeper asset id, not an address" in report.render()


def test_map_documents_with_no_map_object(tmp_path: Path) -> None:
    out, report = run(tmp_path, EXPORT3)
    maps = of_type(out, "map")
    for name in MAPLESS:
        m = maps[name]
        assert not {"width", "height", "image_url", "x_legendkeeper_bounds", "x_legendkeeper_map_id"} & set(m), name
    assert maps["Location: Map"]["location"] == eid(LOCATION)  # the template became a Location: linked
    assert "x_legendkeeper_resource" not in maps["Location: Map"]
    assert maps["Creature: Habitat Map"]["x_legendkeeper_resource"] == eid("fqqy13pb")  # a Creature: kept
    assert {m.name for m in report.maps if m.mapless} == MAPLESS
    text = report.render()
    for name in MAPLESS:
        assert f"{name!r}: no map object (no bounds, no image)" in text, name


def test_the_third_export_lints_and_is_deterministic(tmp_path: Path) -> None:
    one_, report = run(tmp_path, EXPORT3, name="one")
    two, _ = run(tmp_path, EXPORT3, name="two")
    assert tree(one_) == tree(two)
    pytest.importorskip("yaml", reason="the dist's lint decodes the schema YAML")
    lint_ok(one_, report.total)


def test_bounds_that_do_not_start_at_zero(tmp_path: Path) -> None:
    """Every real map's bounds start at x 0, y 0: the quay map moved by 100 each way (planted) keeps
    its size and its pin's place, and a map with half its bounds gives no size and no pin place."""
    data = export3()
    doc = map_doc(data, QUAY_MAP)
    doc["map"].update(min_x=100, max_x=900, min_y=-500, max_y=100)
    doc["content"]["pins"][0]["pos"] = [-2.5, 57]  # 4 times that, less the moved corner: 128, 490 again
    out, _ = run(tmp_path, write_json(tmp_path, data), name="moved")
    moved = of_type(out, "map")["The quay map: Main"]
    assert (moved["width"], moved["height"]) == (800, 600)
    assert (of_type(out, "pin")["The quay"]["x"], of_type(out, "pin")["The quay"]["y"]) == (128, 490)
    del doc["map"]["max_y"], doc["map"]["min_y"]
    out, report = run(tmp_path, write_json(tmp_path, data, "half.json"), name="half")
    half = of_type(out, "map")["The quay map: Main"]
    assert "width" not in half and half["x_legendkeeper_bounds"] == {"min_x": 100, "max_x": 900}
    pin = of_type(out, "pin")["The quay"]
    assert "x" not in pin and pin["x_legendkeeper_pos"] == [-2.5, 57]
    assert any(n.startswith("2 pins with no x, y: no pos, or a map with no bounds") for n in report.notes)
    assert "'The quay map: Main': no bounds, 2 pins, image_url LegendKeeper's address\n" in report.render()


def test_a_map_with_no_max_zoom_places_no_pin(tmp_path: Path) -> None:
    """The scale is 2^max_zoom: a map with bounds and pins but no max_zoom (planted) gives its pins no
    x, y, never a guess; each keeps its pos, and the report names the map."""
    data = export3()
    del map_doc(data, QUAY_MAP)["map"]["max_zoom"]
    out, report = run(tmp_path, write_json(tmp_path, data))
    quay_map = of_type(out, "map")["The quay map: Main"]
    assert (quay_map["width"], quay_map["height"]) == (800, 600) and "x_legendkeeper_max_zoom" not in quay_map
    on_it = [b for b in bodies(out).values() if b["type"] == "pin" and b["map"] == quay_map["id"]]
    assert len(on_it) == 2 and not any("x" in b or "y" in b for b in on_it)
    assert sorted(b["x_legendkeeper_pos"][1] for b in on_it) == [32, 199.31438127090297]
    text = report.render()
    assert "'The quay map: Main': 800 x 600, 2 pins, image_url LegendKeeper's address, no max_zoom: its pins" in text
    assert "positions scaled by 2^6 = 64" in text  # the tutorial map still places its own
    assert any(n.startswith("2 pins with no x, y on a map with no max_zoom") for n in report.notes)
    assert any(n.startswith("16 pins placed") for n in report.notes)


def test_a_hidden_pin_and_a_hidden_map(tmp_path: Path) -> None:
    """No real file has a hidden pin or map yet: planted on copies of the third export."""
    data = export3()
    map_doc(data, QUAY_MAP)["content"]["pins"][0]["isHidden"] = True
    out, report = run(tmp_path, write_json(tmp_path, data), name="pin")
    assert of_type(out, "pin")["The quay"]["hidden"] is True
    assert "hidden" not in of_type(out, "map")["The quay map: Main"]
    assert (report.hidden.maps, report.hidden.pins) == (0, 1)
    assert "1 hidden Pin (the pin or its Map hidden)" in report.render()
    data = export3()
    map_doc(data, TUTORIA)["isHidden"] = True
    out, report = run(tmp_path, write_json(tmp_path, data, "map.json"), name="map")
    assert of_type(out, "map")["The Realm of Tutoria: Main"]["hidden"] is True
    realm = of_type(out, "map")["The Realm of Tutoria: Main"]["id"]
    on_it = [b for b in bodies(out).values() if b["type"] == "pin" and b["map"] == realm]
    assert len(on_it) == 16 and all(b["hidden"] is True for b in on_it)
    assert "hidden" not in of_type(out, "pin")["The quay"]
    assert "hidden" not in of_type(out, "pin")[f"Untitled pin ({CORNER})"]
    assert (report.hidden.maps, report.hidden.pins) == (1, 16)
    pytest.importorskip("yaml", reason="the dist's lint decodes the schema YAML")
    lint_ok(out, report.total)


def test_a_pin_with_no_element(tmp_path: Path) -> None:
    """A pin whose uri names no resource of the export (planted), beside the real corner pin with no
    uri and no name: Pins with no element, named in the report, never a dangling id."""
    data = export3()
    pins = map_doc(data, QUAY_MAP)["content"]["pins"]
    pins[0]["uri"] = "lk://resources/gone0000"
    out, report = run(tmp_path, write_json(tmp_path, data))
    gone = of_type(out, "pin")["The quay"]
    assert "element_id" not in gone and "element_type" not in gone
    assert gone["x_legendkeeper_uri"] == "lk://resources/gone0000"
    untitled = of_type(out, "pin")[f"Untitled pin ({CORNER})"]
    assert "element_id" not in untitled and untitled["map"] == gone["map"]
    assert len(report.pins_unlinked) == 2 and "gone0000" in report.pins_unlinked[0]
    text = report.render()
    assert "Pins with no element (2):" in text and "no uri; a Pin with no element" in text
    assert "gone0000" not in json.dumps([b for b in bodies(out).values() if b["type"] == "pin"]).replace(
        '"x_legendkeeper_uri": "lk://resources/gone0000"', ""
    )


def test_a_visible_pin_on_a_hidden_page_is_named(tmp_path: Path) -> None:
    data = export3()
    for r in data["resources"]:
        if r["id"] == QUAY:
            r["isHidden"] = True
    out, report = run(tmp_path, write_json(tmp_path, data))
    pin = of_type(out, "pin")["The quay"]
    assert "hidden" not in pin and pin["element_id"] == eid(QUAY)
    assert "'The quay': a visible pin on 'The quay map: Main' places the hidden 'The quay'" in report.notes

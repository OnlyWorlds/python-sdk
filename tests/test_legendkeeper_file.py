"""The LegendKeeper door's file source (onlyworlds.legendkeeper.FileSource) on a real export.

``fixtures/legendkeeper/the-quay-world.lk`` is the file LegendKeeper gave on 2026-10-23 (export
version 1) for a project Seethe made on a crew account's 14-day Pro trial, nothing paid (her
receipt: ``Carrier/Studio/desk/current/2026-10-23-exports/receipts/legendkeeper.md``; Boss read it
for secrets and found none, OW Market h40 #11227). What she typed: six pages, Ada Okafor, Mara
Voss, The quay, The ferry crossing, The Ferry Guild and The ledger of the first crossing, with no
tags, properties or links; she renamed the project home "The quay world", and left three
"Untitled" pages (two empty strays, one made from the Character template). The rest is the
tutorial and templates LegendKeeper seeds a new project with: 3 hidden tabs, 13 Secret blocks,
maps, a board and a timeline. Nothing in the project is a hidden page.

The JSON type of the same export (a minute later; Boss found it equal but for ``exportId``,
``exportedAt`` and ``hash``, pretty-printed) is not banked, at 576 KB: ``json_twin`` makes it from
the ``.lk`` the same way. The real twin was checked to give a byte-identical folder when this
door was built.
"""

from __future__ import annotations

import gzip
import hashlib
import io
import json
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
SHA256 = "d484efc1839de13d658f11a942e481aa7be5c99476e5d030f3128306133ea62b"
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
COUNTS = {"character": 2, "creature": 1, "event": 29, "location": 1, "narrative": 52, "relation": 3}


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
        assert body["type"] == "narrative" and body["supertype"] == "legendkeeper", name  # no tags: untyped
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


def test_folder_lint_passes_but_for_the_hidden_mark(tmp_path: Path) -> None:
    """The dist's lint: no problem but the ``hidden`` key, one line per hidden element (the lint
    before schema-dist serial 53 does not know the mark), and its count line the output's count."""
    pytest.importorskip("yaml", reason="the dist's lint decodes the schema YAML")
    out, report = run(tmp_path)
    r = subprocess.run([sys.executable, str(LINT), str(out)], capture_output=True, text=True)
    lines = r.stdout.strip().splitlines()
    assert str(report.total) in lines[-1], r.stdout + r.stderr
    problems = [line for line in lines[:-1] if not line.startswith("walk note:")]
    hidden = sum(1 for b in bodies(out).values() if b.get("hidden") is True)
    assert hidden == 16
    assert all("`hidden` is not a field of" in p for p in problems), r.stdout + r.stderr
    assert len(problems) in (0, hidden), r.stdout  # 0 once the lint knows the mark
    assert r.returncode == (1 if problems else 0)


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
    assert [(n.kind, n.resource) for n in report.not_imported].count(("board", "Board Bastion")) == 1


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

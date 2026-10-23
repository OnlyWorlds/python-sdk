"""The Kanka door (onlyworlds.kanka) on a real Kanka JSON export.

``fixtures/kanka/quay-export-world_20261023_074706.zip`` is the file Kanka 3.15 gave on 2026-10-23
for a campaign Seethe made on a crew free account and typed in Kanka's own editor (her receipt:
``Carrier/Studio/desk/current/2026-10-23-exports/receipts/kanka.md``; Boss read it for keys,
tokens, mail and sessions and found none), its account identifiers scrubbed by Boss's script
(OW Market h40 #11420, #11430): the username, the user id and the campaign id each a placeholder
of the same length, so the campaign id that keys the ids is 910001; every other byte as exported.
What she typed: two Characters (Ada Okafor, Ferry clerk; Mara Voss, Route planner), two Locations
(The quay; The ferry crossing, under The quay), one Organisation (The Ferry Guild), one Note (The
ledger of the first crossing), a two-way "friend" relationship Ada to Mara, and a post on Ada; the
relationship and the post were made twice by a script rerun. Kanka seeded four starter entries in
the new campaign, and they are in the file. Variants (a private entity, a hidden post) are the
same file with one key changed.
"""

from __future__ import annotations

import hashlib
import io
import json
import subprocess
import sys
import uuid
import zipfile
from collections.abc import Callable
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any

import pytest

from onlyworlds import read_folder, write_folder
from onlyworlds.folder import FORMAT_VERSION
from onlyworlds.kanka import (
    KANKA_NAMESPACE,
    PRODUCER_INPUT,
    ImportReport,
    html_to_markdown,
    import_kanka,
    main,
)

ROOT = Path(__file__).resolve().parents[1]
LINT = ROOT / "codegen" / "schema-dist" / "walk" / "lint_folder.py"
EXPORT = Path(__file__).resolve().parent / "fixtures" / "kanka" / "quay-export-world_20261023_074706.zip"
SHA256 = "b900ea8161fd2a32b971a53f71f208734d33d39a6a8f75f7cf9eac8adf10e5e4"
CAMPAIGN = 910001  # the scrubbed campaign id (a real user's ids are keyed on their own)

# entity ids (the number in each filename)
ADA, MARA, QUAY, CROSSING, GUILD, LEDGER = 10074602, 10074603, 10074604, 10074605, 10074606, 10074607
YOU, ALLIED, KINGDOM, CAPITAL = 10074596, 10074597, 10074594, 10074595
TYPED = {
    "Ada Okafor": "character",
    "Mara Voss": "character",
    "The quay": "location",
    "The ferry crossing": "location",
    "The Ferry Guild": "institution",
    "The ledger of the first crossing": "narrative",
}
STARTER = ["[Allied Character Name]", "[Your Character Name]", "[Your Capital City]", "[Your Kingdom Name]"]
ADA_FILE, MARA_FILE = "characters/ada-okafor_10074602.json", "characters/mara-voss_10074603.json"


def eid(entity_id: int) -> str:
    return str(uuid.uuid5(KANKA_NAMESPACE, f"kanka:{CAMPAIGN}:{entity_id}"))


def files() -> dict[str, bytes]:
    with zipfile.ZipFile(EXPORT) as zf:
        return {i.filename: zf.read(i) for i in zf.infolist()}


def variant(tmp: Path, change: Callable[[dict[str, Any]], None], path: str, name: str = "variant.zip") -> Path:
    """The real export with one file's JSON changed."""
    data = files()
    doc = json.loads(data[path])
    change(doc)
    data[path] = json.dumps(doc).encode()
    out = tmp / name
    with zipfile.ZipFile(out, "w") as zf:
        for rel, raw in data.items():
            zf.writestr(rel, raw)
    return out


def run(tmp: Path, src: Path = EXPORT, name: str = "world", **kw: Any) -> tuple[Path, ImportReport]:
    out = tmp / name
    return out, import_kanka(src, out, **kw)


def bodies(out: Path) -> dict[str, dict[str, Any]]:
    return {e.id: e.body for e in read_folder(out).elements.values()}


def by_name(out: Path) -> dict[str, dict[str, Any]]:
    return {b["name"]: b for b in bodies(out).values() if b["type"] != "relation"}


def relations(out: Path) -> list[dict[str, Any]]:
    return sorted((b for b in bodies(out).values() if b["type"] == "relation"), key=lambda b: b["name"])


def tree(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


# ---------------------------------------------------------------------------


def test_the_fixture_is_the_real_file() -> None:
    assert hashlib.sha256(EXPORT.read_bytes()).hexdigest() == SHA256


def test_namespace_is_pinned() -> None:
    """Changing it would give every element of every re-imported campaign a new id."""
    assert str(KANKA_NAMESPACE) == str(uuid.uuid5(uuid.NAMESPACE_URL, "https://onlyworlds.com/ns/kanka"))
    assert PRODUCER_INPUT == "kanka-export"


def test_what_seethe_typed_is_what_comes_out(tmp_path: Path) -> None:
    """Six typed entities and Kanka's four starters, each its module's type; one Relation a pair;
    the two starters' hidden personality traits in two hidden Narratives."""
    out, report = run(tmp_path)
    assert report.counts == {"character": 4, "institution": 1, "location": 4, "narrative": 3, "relation": 2}
    els = by_name(out)
    for name, etype in TYPED.items():
        assert els[name]["type"] == etype, name
    shown = [n for n, b in els.items() if not b.get("hidden")]
    assert sorted(n for n in shown if n not in TYPED) == sorted(STARTER)
    assert sorted(n for n, b in els.items() if b.get("hidden")) == [
        "[Allied Character Name]: hidden details",
        "[Your Character Name]: hidden details",
    ]
    assert {(m.folder, m.type, m.entities, m.status) for m in report.modules} == {
        ("characters", "character", 4, "proven"),
        ("locations", "location", 4, "proven"),
        ("notes", "narrative", 1, "proven"),
        ("organisations", "institution", 1, "proven"),
    }
    ada = els["Ada Okafor"]
    assert ada["id"] == eid(ADA)
    assert ada["supertype"] == "Ferry clerk"
    assert ada["x_kanka_title"] == "Keeper of the quay ledger"  # Character has no title field
    assert (ada["x_kanka_id"], ada["x_kanka_entity_id"], ada["x_kanka_module"]) == (2607496, ADA, "characters")
    assert els["The Ferry Guild"]["supertype"] == "Guild"
    ledger = els["The ledger of the first crossing"]
    assert ledger["story"] == "The first entry reads: one crossing, eleven passengers, no losses."
    assert "description" not in ledger


def test_the_parent_resolves_through_the_entity_id(tmp_path: Path) -> None:
    """The ferry crossing's parent_id is The quay's entity id (10074604), not its row id (2270244)."""
    out, _ = run(tmp_path)
    els = by_name(out)
    crossing = els["The ferry crossing"]
    assert crossing["parent_location"] == eid(QUAY) == els["The quay"]["id"]
    assert crossing["x_kanka_parent"] == eid(QUAY)
    assert "parent_location" not in els["The quay"]


def test_a_two_way_relationship_is_one_relation(tmp_path: Path) -> None:
    out, report = run(tmp_path)
    friends = [r for r in relations(out) if r["name"] == "friend"]
    assert len(friends) == 1
    (rel,) = friends
    assert rel["actor"] == eid(ADA) and rel["characters"] == [eid(MARA)]
    assert rel["x_kanka_source"] == eid(ADA) and rel["x_kanka_target"] == eid(MARA)
    assert rel["x_kanka_two_way"] is True and rel["x_kanka_id"] == 1158037
    assert "x_kanka_mirror" not in rel  # the two sides say the same
    assert rel["id"] == str(uuid.uuid5(KANKA_NAMESPACE, f"kanka:{CAMPAIGN}:relation:1158037"))
    assert report.relations == {"friend": 1, "[Friend/Mentor/Rival]": 1}
    starter = next(r for r in relations(out) if r["name"] == "[Friend/Mentor/Rival]")
    assert "x_kanka_two_way" not in starter and starter["x_kanka_attitude"] == 0


def test_exact_duplicates_fold_and_are_reported(tmp_path: Path) -> None:
    out, report = run(tmp_path)
    ada = by_name(out)["Ada Okafor"]
    assert ada["description"].count("## The night of the long crossing") == 1
    assert ada["description"].count("lamplight") == 1
    folded = {(f.element, f.what, f.name, f.copies) for f in report.folded}
    assert folded == {
        ("Ada Okafor", "post", "The night of the long crossing", 2),
        ("Ada Okafor", "relationship", "friend", 2),
        ("[Allied Character Name]", "trait", "Trait 2", 2),  # Kanka's own starter carries it twice
        ("[Your Character Name]", "trait", "Trait 2", 2),
    }
    text = report.render()
    assert "2 identical posts 'The night of the long crossing', kept once" in text
    assert "2 identical relationships 'friend', kept once" in text


def test_a_near_duplicate_is_kept(tmp_path: Path) -> None:
    def change(doc: dict[str, Any]) -> None:
        doc["entity"]["posts"][1]["entry"] = "<p>The rope held.</p>"
        doc["entity"]["relationships"][1]["relation"] = "old friend"

    out, report = run(tmp_path, variant(tmp_path, change, ADA_FILE))
    ada = by_name(out)["Ada Okafor"]
    assert ada["description"].count("## The night of the long crossing") == 2
    assert {r["name"] for r in relations(out)} == {"friend", "old friend", "[Friend/Mentor/Rival]"}
    old = next(r for r in relations(out) if r["name"] == "old friend")
    assert old["x_kanka_mirror"] == {"relation": "friend"}  # Mara's side still says friend
    assert not any(f.element == "Ada Okafor" for f in report.folded)


def test_starter_entries_are_imported_and_named(tmp_path: Path) -> None:
    """Nothing in the data marks them, so they travel; the report names them as possible starters."""
    out, report = run(tmp_path)
    assert sorted(report.possibly_starter) == sorted(STARTER)
    assert all(name in by_name(out) for name in STARTER)
    assert "Possibly Kanka's starter content" in report.render()
    allied = by_name(out)["[Allied Character Name]"]
    assert allied["location"] == eid(CAPITAL)  # entityLocations names the Location's row id, 2270241
    assert "helps or travels with [Your Character Name]." in allied["description"]  # [entity:10074596]
    assert allied["x_kanka_mentions"] == [eid(YOU)]
    assert "1. [Skill 1: Combat/Magic/Healing/Crafting]" in allied["description"]  # the post's list
    assert (
        allied["physicality"]
        == "Build: [Lean/Average/Muscular]\nNotable features: [Scares, tattoos, distinctive clothing]"
    )
    kingdom = by_name(out)["[Your Kingdom Name]"]
    assert kingdom["x_kanka_capital"] == "[Your Capital City]" and kingdom["x_kanka_mentions"] == [eid(CAPITAL)]
    assert kingdom["x_kanka_population"] == "~50'000"


def test_personality_not_visible_to_players_is_hidden_not_dropped(tmp_path: Path) -> None:
    """The starters' is_personality_visible is false: their personality traits go to a hidden Narrative."""
    out, report = run(tmp_path)
    els = by_name(out)
    you = els["[Your Character Name]"]
    assert "mentality" not in you and "hidden" not in you
    details = els["[Your Character Name]: hidden details"]
    assert details["hidden"] is True and details["type"] == "narrative"
    assert (
        details["story"]
        == "## Personality\n\nTrait 1: [Brave/Cautious/Ambitious]\nTrait 2: [Loyal/Independant/Cunning]"
    )
    assert details["characters"] == [eid(YOU)] and details["x_kanka_parent"] == eid(YOU)
    assert details["id"] == str(uuid.uuid5(KANKA_NAMESPACE, f"kanka:{CAMPAIGN}:hidden:{YOU}"))
    assert (report.hidden.personality, report.hidden.details) == (4, 2)  # Trait 2 folded on each first
    assert "2 hidden-details Narratives holding 4 personality traits" in report.render()
    assert "mentality" not in els["Ada Okafor"]  # Ada has no traits; her personality is visible


def test_a_private_entity_is_hidden_not_dropped(tmp_path: Path) -> None:
    def change(doc: dict[str, Any]) -> None:
        doc["entity"]["is_private"] = True

    out, report = run(tmp_path, variant(tmp_path, change, MARA_FILE))
    mara = by_name(out)["Mara Voss"]
    assert mara["hidden"] is True and mara["id"] == eid(MARA)
    assert mara["description"].startswith("Mara plans the ferry routes")  # whole, not cut
    assert "hidden" not in by_name(out)["Ada Okafor"]
    friend = next(r for r in relations(out) if r["name"] == "friend")
    assert friend["hidden"] is True  # it touches a hidden entity
    assert (report.hidden.entities, report.hidden.relationships) == (1, 1)
    assert report.counts["relation"] == 2 and report.unresolved == []
    assert "1 private entity (is_private)" in report.render()


def test_a_private_post_is_its_own_hidden_narrative(tmp_path: Path) -> None:
    def change(doc: dict[str, Any]) -> None:
        for post in doc["entity"]["posts"]:
            post["visibility_id"] = 2
        for rel in doc["entity"]["relationships"]:
            rel["visibility_id"] = 2

    out, report = run(tmp_path, variant(tmp_path, change, ADA_FILE))
    els = by_name(out)
    ada = els["Ada Okafor"]
    assert "hidden" not in ada and "lamplight" not in ada["description"]  # the visible text only
    assert ada["description"].startswith("Ada keeps the quay ledger")
    post = els["The night of the long crossing"]
    assert post["hidden"] is True and post["type"] == "narrative"
    assert post["story"] == "The rope held, the ledger got wet, and Ada wrote it all down by lamplight anyway."
    assert post["characters"] == [eid(ADA)] and post["x_kanka_parent"] == eid(ADA)
    assert (post["x_kanka_id"], post["x_kanka_visibility_id"]) == (1575114, 2)
    assert post["id"] == str(uuid.uuid5(KANKA_NAMESPACE, f"kanka:{CAMPAIGN}:post:1575114"))
    friend = next(r for r in relations(out) if r["name"] == "friend")
    assert friend["hidden"] is True and friend["x_kanka_mirror"] == {"visibility_id": 1}  # Mara's side
    assert (report.hidden.posts, report.hidden.relationships) == (1, 1)  # each folded first
    assert "1 post not visible to all, its own Narrative (visibility_id)" in report.render()


def test_folder_lint_passes_but_for_the_hidden_mark(tmp_path: Path) -> None:
    """The dist's lint on the output: no problem but the ``hidden`` key, one line per hidden element
    (the lint does not know the mark yet), and its count line the output's count."""
    pytest.importorskip("yaml", reason="the dist's lint decodes the schema YAML")

    def private(doc: dict[str, Any]) -> None:
        doc["entity"]["is_private"] = True

    for name, src in (("real", EXPORT), ("private", variant(tmp_path, private, MARA_FILE))):
        out, report = run(tmp_path, src, name=name)
        r = subprocess.run([sys.executable, str(LINT), str(out)], capture_output=True, text=True)
        lines = r.stdout.strip().splitlines()
        assert str(report.total) in lines[-1]
        problems = [line for line in lines[:-1] if not line.startswith("walk note:")]
        hidden = sum(1 for b in bodies(out).values() if b.get("hidden") is True)
        assert hidden and all("`hidden` is not a field of" in p for p in problems), r.stdout + r.stderr
        assert len(problems) in (0, hidden), r.stdout  # 0 once the lint knows the mark
        assert r.returncode == (1 if problems else 0)
    # with nothing hidden, the lint is green outright
    data = files()
    for rel in ("characters/your-character-name_10074596.json", "characters/allied-character-name_10074597.json"):
        doc = json.loads(data[rel])
        doc["is_personality_visible"] = True
        data[rel] = json.dumps(doc).encode()
    shown = tmp_path / "shown.zip"
    with zipfile.ZipFile(shown, "w") as zf:
        for rel, raw in data.items():
            zf.writestr(rel, raw)
    out, report = run(tmp_path, shown, name="shown")
    assert not any(b.get("hidden") for b in bodies(out).values())
    r = subprocess.run([sys.executable, str(LINT), str(out)], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert f"checked {report.total} element files" in r.stdout


def test_deterministic(tmp_path: Path) -> None:
    """The same zip twice gives byte-equal folders; the unzipped directory gives the same one."""
    run(tmp_path, name="one")
    run(tmp_path, name="two")
    unzipped = tmp_path / "unzipped"
    for rel, raw in files().items():
        (unzipped / rel).parent.mkdir(parents=True, exist_ok=True)
        (unzipped / rel).write_bytes(raw)
    run(tmp_path, unzipped, name="three")
    assert tree(tmp_path / "one") == tree(tmp_path / "two") == tree(tmp_path / "three")


def test_ids_do_not_move_with_the_supertype(tmp_path: Path) -> None:
    """No tool name in a supertype (Skeld, OW Market h40 #11385): the real export's ids are those
    0.41.0 gave (the sha256 of the sorted ids, one a line; 0.41.0 run on the scrubbed file, whose
    campaign id moved the ids from those it gave on the unscrubbed one)."""
    out, _ = run(tmp_path)
    ids = sorted(bodies(out))
    assert len(ids) == 14
    assert hashlib.sha256("\n".join(ids).encode()).hexdigest() == (
        "18a80950ae202537f882f17ed9d793e17d0dcb837f834bdd13b9b63714828530"
    )


def test_a_module_with_no_type_is_an_article_narrative(tmp_path: Path) -> None:
    """No module of the real export lacks a type: a planted timelines/ file, the note's own shape."""
    data = files()
    doc = json.loads(data["notes/the-ledger-of-the-first-crossing_10074607.json"])
    doc["id"], doc["name"] = 346499, "The crossing timeline"
    doc["entity"].update(id=10074699, entity_id=346499, name="The crossing timeline")
    data["timelines/the-crossing-timeline_10074699.json"] = json.dumps(doc).encode()
    src = tmp_path / "planted.zip"
    with zipfile.ZipFile(src, "w") as zf:
        for rel, raw in data.items():
            zf.writestr(rel, raw)
    out, report = run(tmp_path, src)
    timeline = by_name(out)["The crossing timeline"]
    assert timeline["type"] == "narrative"
    assert (timeline["supertype"], timeline["subtype"]) == ("Article", "timelines")  # what it is, never kanka
    assert timeline["x_kanka_type"] == "Ledger"  # the module's own type word, kept
    assert "supertype Article, subtype 'timelines'" in report.render()


def test_round_trip_is_byte_equal(tmp_path: Path) -> None:
    out, _ = run(tmp_path)
    folder = read_folder(out)
    assert not folder.skipped and folder.world is not None
    by_type: dict[str, list[dict[str, Any]]] = {}
    for el in folder.elements.values():
        by_type.setdefault(el.type, []).append(el.body)
    again = tmp_path / "again"
    write_folder(again, folder.world, by_type)
    assert tree(again) == tree(out)


def test_plan_writes_nothing(tmp_path: Path) -> None:
    out = tmp_path / "planned"
    report = import_kanka(EXPORT, out, plan_only=True)
    assert not out.exists() and report.out is None
    assert report.total == 14
    assert "Plan only: nothing written." in report.render()


def test_world_json(tmp_path: Path) -> None:
    out, _ = run(tmp_path)
    world = json.loads((out / "world.json").read_text(encoding="utf-8"))
    assert world["id"] == str(uuid.uuid5(KANKA_NAMESPACE, f"kanka:{CAMPAIGN}"))
    assert world["name"] == "crew-export-user's world"  # the scrubbed username's
    assert world["producer"]["tool"] == "onlyworlds" and world["producer"]["input"] == "kanka-export"
    assert world["format_version"] == FORMAT_VERSION
    assert "description" not in world  # the campaign has no entry


def test_the_report_names_every_key_not_placed(tmp_path: Path) -> None:
    _, report = run(tmp_path)
    unplaced = {(u.element, u.key): u.kept_as for u in report.unplaced}
    assert unplaced[("Ada Okafor", "title")] == "x_kanka_title"
    assert unplaced[("Ada Okafor", "status_id")] == "x_kanka_status_id"
    assert unplaced[("[Your Kingdom Name]", "Capital")] == "x_kanka_capital"
    assert report.unresolved == []
    assert any(n.startswith("Kanka 3.15, export version 3.15") for n in report.notes)


def test_an_attribute_named_like_a_field_fills_it(tmp_path: Path) -> None:
    def change(doc: dict[str, Any]) -> None:
        doc["entity"]["entityAttributes"] = [
            {"id": 1, "name": "Architecture", "value": "Stone and slate", "is_private": False, "is_hidden": False},
            {"id": 2, "name": "Elevation", "value": "high", "is_private": False, "is_hidden": False},
            {"id": 3, "name": "Founding date", "value": "-40", "is_private": False, "is_hidden": False},
            {"id": 4, "name": "Rival", "value": "[entity:10074594]", "is_private": False, "is_hidden": False},
            {"id": 5, "name": "Secret", "value": "a tunnel", "is_private": True, "is_hidden": False},
        ]

    out, report = run(tmp_path, variant(tmp_path, change, "locations/the-quay_10074604.json"))
    quay = by_name(out)["The quay"]
    assert quay["architecture"] == "Stone and slate" and quay["founding_date"] == -40
    assert quay["rival"] == eid(KINGDOM) and "x_kanka_mentions" not in quay
    assert quay["x_kanka_elevation"] == "high" and "elevation" not in quay
    assert "x_kanka_secret" not in quay and "a tunnel" not in json.dumps(quay)
    details = by_name(out)["The quay: hidden details"]
    assert details["hidden"] is True and details["locations"] == [eid(QUAY)]
    assert details["story"] == "## Attributes\n\nSecret: a tunnel"
    assert (report.hidden.attributes, report.hidden.details) == (1, 3)


def test_html_to_markdown() -> None:
    html = (
        "<h2>Head</h2><p>One <strong>bold</strong> and <em>soft</em> &amp; <a href='https://x.y'>a link</a>"
        "<br>next line</p><ul><li>a</li><li>b<ul><li>c</li></ul></li></ul><ol start='3'><li>three</li></ol>"
        "<blockquote><p>said</p></blockquote><hr><p><s>gone</s> <code>x = 1</code></p>"
        "<table><tr><th>k</th><th>v</th></tr><tr><td>a|b</td><td>2</td></tr></table>"
    )
    assert html_to_markdown(html) == (
        "## Head\n\nOne **bold** and *soft* & [a link](https://x.y)\nnext line\n\n- a\n- b\n  - c\n\n3. three"
        "\n\n> said\n\n---\n\n~~gone~~ `x = 1`\n\n| k | v |\n| --- | --- |\n| a\\|b | 2 |"
    )
    assert html_to_markdown(None) == "" and html_to_markdown("plain text") == "plain text"


def test_not_a_kanka_export(tmp_path: Path) -> None:
    bad = tmp_path / "bad.zip"
    with zipfile.ZipFile(bad, "w") as zf:
        zf.writestr("notes.md", "# hello")
    with pytest.raises(ValueError, match=r"campaign\.json"):
        import_kanka(bad, tmp_path / "x")


# --- the command line --------------------------------------------------------


def test_cli(tmp_path: Path) -> None:
    out = tmp_path / "cli"
    buf = io.StringIO()
    with redirect_stdout(buf):
        assert main([str(EXPORT), str(out), "--plan"]) == 0
    assert "Plan only" in buf.getvalue() and not out.exists()
    with redirect_stdout(io.StringIO()):
        assert main([str(EXPORT), str(out)]) == 0
    assert by_name(out)["[Your Character Name]: hidden details"]["hidden"] is True
    err = io.StringIO()
    with redirect_stderr(err):
        assert main([str(EXPORT), str(out)]) == 2  # not empty
        assert main([str(tmp_path / "missing.zip"), "--plan"]) == 2
        assert main([str(EXPORT)]) == 2  # no OUT-DIR, no --plan

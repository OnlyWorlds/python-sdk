"""The LegendKeeper door (onlyworlds.legendkeeper) on Boss's recorded wire answers.

The three files in ``fixtures/legendkeeper/`` are real answers of the LegendKeeper API v3, read
live on 2026-10-22 on the Captain's project (made-up content, no key, no email; Boss's findings,
``Orrery/market/2026-10-22-legendkeeper-wire/findings.md``). They are specimens, not a whole
walk, so ``answers()`` composes the walk the door makes from them and says what it fills in:

- the project answer (``getProject``) was not recorded: ``{"id": PID, "name": "Sikelia"}``, the
  name of the project's root page; ``PID`` is made up (the fixtures carry no project id);
- ``getResource`` was recorded for Aldric only, before his two sidebar properties were made: the
  recorded ``listProperties`` answer is put in as his ``properties``;
- the other four resources' ``getResource`` answers are their recorded list rows with
  ``properties: []`` and each document's recorded answer where there is one (the timeline, the
  map), else the listed document with ``isHidden: false``;
- blocks were recorded for Aldric's page only; the other documents are ``blank`` (never read,
  by the spec's definition empty), ``time`` (lanes and events recorded) or ``map``;
- the map document's own answer was recorded (``mapImage`` null: no image yet); its features
  were not read that day, so they are filled in as none (``{"data": []}``), what a map with no
  pins answers (read live on 2026-10-25, ``api-maps.json``).

No network: the API client is tested on the conftest's fake transport.
"""

from __future__ import annotations

import copy
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
from conftest import FakeTransport, jresp

from onlyworlds import read_folder, write_folder
from onlyworlds.folder import FORMAT_VERSION
from onlyworlds.http import Response
from onlyworlds.legendkeeper import (
    API_BASE,
    LEGENDKEEPER_NAMESPACE,
    PRODUCER_INPUT,
    ApiSource,
    ImportReport,
    RecordedSource,
    SourceError,
    import_legendkeeper,
    main,
)

ROOT = Path(__file__).resolve().parents[1]
LINT = ROOT / "codegen" / "schema-dist" / "walk" / "lint_folder.py"
FIX = Path(__file__).resolve().parent / "fixtures" / "legendkeeper"
PID = "sikelia0"
P = f"/projects/{PID}"
KEY = "lk_test_SECRET_never_written"

ALDRIC, SIKELIA, BOSS, ORDER, CASTLE = "i7xzob1r", "imjcfwi6", "lfyv1ubb", "tgzavfel", "zicarhdp"
SIEGE, FOUNDING = "myaqa6t9c2omcsch90ff4de3", "r6q4dpwpyfn5lrazhrglg811"
MAP = {"place": "location", "faction": "institution"}


def load(name: str) -> Any:
    return json.loads((FIX / f"{name}.json").read_text(encoding="utf-8"))


def eid(lk_id: str) -> str:
    return str(uuid.uuid5(LEGENDKEEPER_NAMESPACE, f"legendkeeper:{PID}:{lk_id}"))


def event_id(lk_id: str) -> str:
    return str(uuid.uuid5(LEGENDKEEPER_NAMESPACE, f"legendkeeper:{PID}:event:{lk_id}"))


def answers() -> dict[str, Any]:
    """The walk the door makes, composed from the three recorded files (the module docstring says how)."""
    a, m, t = load("aldric-and-properties"), load("map-search-tags-tree"), load("timeline")
    out: dict[str, Any] = {P: {"id": PID, "name": "Sikelia"}, f"{P}/resources": m["resources"]}
    recorded = {d["id"]: d for d in (a["timeline_doc"], m["map_doc"], a["aldric_doc"])}
    for item in m["resources"]["data"]:
        if item["id"] == ALDRIC:
            full = {**a["aldric_resource"], "properties": a["props"]["data"]}
        else:
            docs = [recorded.get(d["id"], {**d, "isHidden": False}) for d in item["documents"]]
            full = {**item, "documents": docs, "properties": [], "permissions": {}}
        out[f"{P}/resources/{item['id']}"] = full
    out[f"{P}/resources/{ALDRIC}/docs/z3kj5ubq/blocks"] = a["aldric_blocks"]
    out[f"{P}/resources/{ORDER}/docs/ke9g0py4/lanes"] = t["lanes"]
    out[f"{P}/resources/{ORDER}/docs/ke9g0py4/events"] = t["events"]
    out[f"{P}/resources/{CASTLE}/docs/yrr58xqo"] = m["map_doc"]
    out[f"{P}/resources/{CASTLE}/docs/yrr58xqo/features"] = {"data": []}
    return out


def run(tmp: Path, ans: dict[str, Any] | None = None, name: str = "world", **kw: Any) -> tuple[Path, ImportReport]:
    out = tmp / name
    return out, import_legendkeeper(RecordedSource(ans or answers()), PID, out, **kw)


def bodies(out: Path) -> dict[str, dict[str, Any]]:
    return {e.id: e.body for e in read_folder(out).elements.values()}


def by_name(out: Path) -> dict[str, dict[str, Any]]:
    return {b["name"]: b for b in bodies(out).values() if b["type"] != "relation"}


def relations(out: Path) -> list[dict[str, Any]]:
    return sorted((b for b in bodies(out).values() if b["type"] == "relation"), key=lambda b: b["name"])


def tree(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def aldric_rows(ans: dict[str, Any]) -> list[dict[str, Any]]:
    """The keyValue rows of Aldric's infobox, to edit in a variant."""
    infobox = next(b for b in ans[f"{P}/resources/{ALDRIC}/docs/z3kj5ubq/blocks"]["blocks"] if b["kind"] == "infobox")
    rows: list[dict[str, Any]] = next(r for r in infobox["rows"] if r["kind"] == "keyValue")["rows"]
    return rows


def kv(key: str, text: str) -> dict[str, Any]:
    return {"key": key, "content": [{"text": text}], "text": text, "id": f"row-{key}", "rank": "z"}


def hide(ans: dict[str, Any], rid: str) -> dict[str, Any]:
    ans = copy.deepcopy(ans)
    for item in ans[f"{P}/resources"]["data"]:
        if item["id"] == rid:
            item["isHidden"] = True
    ans[f"{P}/resources/{rid}"]["isHidden"] = True
    return ans


# ---------------------------------------------------------------------------


def test_namespace_is_pinned() -> None:
    """Changing it would give every element of every re-imported project a new id."""
    assert str(LEGENDKEEPER_NAMESPACE) == str(uuid.uuid5(uuid.NAMESPACE_URL, "https://onlyworlds.com/ns/legendkeeper"))
    assert PRODUCER_INPUT == "legendkeeper-api"
    assert API_BASE == "https://www.legendkeeper.com/api/v3"


def test_the_tree_converts_to_the_element_set(tmp_path: Path) -> None:
    out, report = run(tmp_path)
    assert report.counts == {"character": 1, "event": 2, "map": 1, "narrative": 5, "relation": 3}
    els = by_name(out)
    aldric = els["Aldric Veyra"]
    assert aldric["id"] == eid(ALDRIC) and aldric["type"] == "character"
    assert aldric["x_legendkeeper_id"] == ALDRIC
    assert aldric["x_legendkeeper_tags"] == ["character", "noble"]
    assert aldric["x_legendkeeper_aliases"] == ["Lord Veyra", "the Ash Lord"]
    assert aldric["x_legendkeeper_parent"] == eid(BOSS)
    assert "supertype" not in aldric
    for name in ("Sikelia", "Boss wire test (delete me)", "Order of the Ash", "Castle Veyra"):
        assert els[name]["type"] == "narrative" and els[name]["supertype"] == "Article", name
    assert "x_legendkeeper_parent" not in els["Sikelia"]
    assert els["Order of the Ash"]["x_legendkeeper_tags"] == ["faction"]
    typed = {t.name: (t.type, t.by) for t in report.typed}
    assert typed["Aldric Veyra"] == ("character", "tag 'character'")
    assert typed["Castle Veyra"] == ("narrative", "untyped")


def test_map_adds_tag_types(tmp_path: Path) -> None:
    out, report = run(tmp_path, type_map=MAP)
    assert report.counts == {
        "character": 1,
        "event": 2,
        "institution": 1,
        "location": 1,
        "map": 1,
        "narrative": 3,
        "relation": 3,
    }
    els = by_name(out)
    assert els["Castle Veyra"]["type"] == "location" and "supertype" not in els["Castle Veyra"]
    assert "parent_location" not in els["Castle Veyra"]  # its parent is a Narrative
    assert {t.name: t.by for t in report.typed}["Order of the Ash"] == "--map faction=institution"


def test_a_location_under_a_location_gets_its_parent_field(tmp_path: Path) -> None:
    ans = answers()
    for item in ans[f"{P}/resources"]["data"]:
        if item["id"] == BOSS:
            item["tags"] = ["Location"]  # a type name, any case
    out, _ = run(tmp_path, ans, type_map=MAP)
    els = by_name(out)
    assert els["Boss wire test (delete me)"]["type"] == "location"
    assert els["Castle Veyra"]["parent_location"] == eid(BOSS)
    assert els["Castle Veyra"]["x_legendkeeper_parent"] == eid(BOSS)


def test_two_type_tags_are_never_a_guess(tmp_path: Path) -> None:
    ans = answers()
    for item in ans[f"{P}/resources"]["data"]:
        if item["id"] == ALDRIC:
            item["tags"] = ["character", "location"]
    out, report = run(tmp_path, ans)
    assert by_name(out)["Aldric Veyra"]["type"] == "narrative"
    by = {t.name: t.by for t in report.typed}["Aldric Veyra"]
    assert by.startswith("ambiguous") and "character" in by and "location" in by


def test_properties_become_extensions_and_are_reported(tmp_path: Path) -> None:
    out, report = run(tmp_path)
    aldric = by_name(out)["Aldric Veyra"]
    assert aldric["x_legendkeeper_born"] == "Year 412"  # Character has birth_date, not born: never a synonym
    assert aldric["x_legendkeeper_rank"] == "Lord"
    assert aldric["x_legendkeeper_alignment"] == "Lawful"  # the sidebar property
    unplaced = {(u.element, u.key): u for u in report.unplaced}
    assert unplaced[("Aldric Veyra", "Born")].kept_as == "x_legendkeeper_born"
    assert "character has no field 'born'" in unplaced[("Aldric Veyra", "Born")].why
    assert ("Aldric Veyra", "Alignment") in unplaced and ("Aldric Veyra", "Rank") in unplaced


def test_a_key_that_names_a_field_becomes_the_field(tmp_path: Path) -> None:
    ans = answers()
    aldric_rows(ans).extend([kv("Height", "180"), kv("Reputation", "Feared at court"), kv("Weight", "heavy")])
    out, report = run(tmp_path, ans)
    aldric = by_name(out)["Aldric Veyra"]
    assert aldric["height"] == 180 and aldric["reputation"] == "Feared at court"
    assert "weight" not in aldric and aldric["x_legendkeeper_weight"] == "heavy"
    assert any(u.key == "Weight" and "whole number" in u.why for u in report.unplaced)
    assert not any(u.key in ("Height", "Reputation") for u in report.unplaced)


def test_titled_links_with_no_field_become_relations(tmp_path: Path) -> None:
    out, report = run(tmp_path)
    rels = relations(out)
    assert [r["name"] for r in rels] == ["Allies", "Home", "Member of"]
    home = rels[1]
    assert home["actor"] == eid(ALDRIC) and home["narratives"] == [eid(CASTLE)]
    assert home["x_legendkeeper_source"] == eid(ALDRIC) and home["x_legendkeeper_target"] == eid(CASTLE)
    assert report.relations == {"Allies": 1, "Home": 1, "Member of": 1}
    # with the tags mapped, the target lands on the Relation's field for its type
    out2, _ = run(tmp_path, type_map=MAP, name="mapped")
    assert relations(out2)[1]["locations"] == [eid(CASTLE)]
    assert relations(out2)[2]["institutions"] == [eid(ORDER)]


def test_a_titled_link_that_names_a_field_becomes_the_field(tmp_path: Path) -> None:
    ans = answers()
    blocks = ans[f"{P}/resources/{ALDRIC}/docs/z3kj5ubq/blocks"]["blocks"]
    infobox = next(b for b in blocks if b["kind"] == "infobox")
    for row in infobox["rows"]:
        if row.get("title") == "Home":
            row["title"] = "Location"
        if row.get("title") == "Member of":
            row["title"] = "Institutions"
    out, report = run(tmp_path, ans, type_map=MAP)
    aldric = by_name(out)["Aldric Veyra"]
    assert aldric["location"] == eid(CASTLE)
    assert aldric["institutions"] == [eid(ORDER)]
    assert report.relations == {"Allies": 1}
    # untyped targets do not fit the field: Relations instead, and the report says why
    out2, report2 = run(tmp_path, ans, name="untyped")
    assert "location" not in by_name(out2)["Aldric Veyra"]
    assert report2.relations == {"Allies": 1, "Institutions": 1, "Location": 1}


def test_blocks_to_markdown_and_mentions(tmp_path: Path) -> None:
    out, _ = run(tmp_path)
    aldric = by_name(out)["Aldric Veyra"]
    assert aldric["description"] == (
        "Lord of Castle Veyra, sworn to the Order. He is **feared** and *loved* ([source](https://example.org/aldric)).\n"
        "\n"
        "| Year | Event |\n"
        "| --- | --- |\n"
        "| 430 | The siege |"
    )
    assert aldric["x_legendkeeper_mentions"] == [eid(CASTLE), eid(ORDER)]


def test_the_timeline_becomes_events_with_raw_minutes(tmp_path: Path) -> None:
    out, report = run(tmp_path)
    els = by_name(out)
    siege, founding = els["The Siege"], els["Founding"]
    assert siege["id"] == event_id(SIEGE) and siege["type"] == "event"
    assert siege["x_legendkeeper_start"] == {"minutes": 1000000, "formatted": "November 26th, 2 CE"}
    assert siege["x_legendkeeper_end"] == {"minutes": 1005000, "formatted": "November 29th, 2 CE"}
    assert founding["x_legendkeeper_start"] == {"minutes": 500000, "formatted": "December 14th, 1 CE"}
    assert "x_legendkeeper_end" not in founding
    for ev in (siege, founding):
        assert "start_date" not in ev and "end_date" not in ev  # the unit is the world's decision
        assert ev["x_legendkeeper_lane"] == "Wars"
        assert ev["x_legendkeeper_calendar"] == "gregorian"
        assert ev["x_legendkeeper_timeline"] == "History"
        assert ev["x_legendkeeper_parent"] == eid(ORDER)
    assert any("History" in n and "2 events" in n for n in report.notes)


def secret_id(rid: str, did: str, n: int) -> str:
    return str(uuid.uuid5(LEGENDKEEPER_NAMESPACE, f"legendkeeper:{PID}:secret:{rid}:{did}:{n}"))


def visible(out: Path) -> str:
    """Every element a reader who may not see hidden ones is served, as one JSON text."""
    return json.dumps([b for b in bodies(out).values() if b.get("hidden") is not True])


def test_a_secret_block_becomes_its_own_hidden_narrative(tmp_path: Path) -> None:
    """Skeld's rule (OW Market h40 #11228): what the source hides, we hide, never drop and never publish."""
    out, report = run(tmp_path)
    els = by_name(out)
    secret = els["Aldric Veyra: Secret"]
    assert secret["id"] == secret_id(ALDRIC, "z3kj5ubq", 1)
    assert secret["hidden"] is True and secret["type"] == "narrative"
    assert secret["story"] == "He poisoned his brother."
    assert secret["characters"] == [eid(ALDRIC)] and secret["x_legendkeeper_parent"] == eid(ALDRIC)
    assert secret["x_legendkeeper_document"] == "z3kj5ubq"
    assert "poisoned" not in visible(out)  # the page keeps only its visible text
    assert "Lord of Castle Veyra" in els["Aldric Veyra"]["description"]
    assert report.hidden.secret_blocks == 1
    assert "1 secret block in a visible page, its own Narrative" in report.render()


def test_a_hidden_resource_is_an_element_carrying_the_mark(tmp_path: Path) -> None:
    src = RecordedSource(hide(answers(), ORDER))
    out = tmp_path / "hidden"
    report = import_legendkeeper(src, PID, out)
    assert any(ORDER in path for path in src.calls)  # read like any other: nothing is dropped
    assert report.hidden.resources == 1
    assert report.counts == {"character": 1, "event": 2, "map": 1, "narrative": 5, "relation": 3}
    els = by_name(out)
    order = els["Order of the Ash"]
    assert order["hidden"] is True and list(order)[:4] == ["type", "id", "name", "hidden"]
    assert "Order of the Ash" not in visible(out)
    for ev in ("The Siege", "Founding"):  # its timeline's events are its own
        assert els[ev]["hidden"] is True
    rels = {r["name"]: r for r in relations(out)}
    assert rels["Member of"]["hidden"] is True and rels["Allies"]["hidden"] is True  # a hidden end
    assert "hidden" not in rels["Home"]
    assert (report.hidden.events, report.hidden.relations) == (2, 2)
    assert report.unresolved == []
    assert els["Aldric Veyra"]["x_legendkeeper_mentions"] == [eid(CASTLE), eid(ORDER)]
    assert "'Aldric Veyra': visible text mentions the hidden 'Order of the Ash' by name" in report.notes


def test_a_hidden_parent_hides_its_subtree(tmp_path: Path) -> None:
    out, report = run(tmp_path, hide(answers(), BOSS))
    assert report.counts == {"character": 1, "event": 2, "map": 1, "narrative": 4, "relation": 3}  # no secret Narrative
    assert (report.hidden.resources, report.hidden.under_hidden) == (1, 3)
    shown = [b["name"] for b in bodies(out).values() if not b.get("hidden")]
    assert shown == ["Sikelia"]
    # inside text already hidden, a secret stays in place, marked
    assert "> [!secret]\n> He poisoned his brother." in by_name(out)["Aldric Veyra"]["description"]
    assert (report.hidden.secret_blocks, report.hidden.secrets_inside) == (0, 1)


def test_a_hidden_page_becomes_its_own_hidden_narrative(tmp_path: Path) -> None:
    ans = answers()
    for doc in ans[f"{P}/resources/{ALDRIC}"]["documents"]:
        doc["isHidden"] = True
    out, report = run(tmp_path, ans)
    els = by_name(out)
    page = els["Aldric Veyra: Main"]
    assert page["hidden"] is True and page["characters"] == [eid(ALDRIC)]
    assert page["id"] == str(uuid.uuid5(LEGENDKEEPER_NAMESPACE, f"legendkeeper:{PID}:document:{ALDRIC}:z3kj5ubq"))
    assert page["story"].startswith("Lord of Castle Veyra")
    assert "> [!secret]\n> He poisoned his brother." in page["story"]  # inside a hidden page: in place
    assert page["x_legendkeeper_mentions"] == [eid(CASTLE), eid(ORDER)]
    assert "description" not in els["Aldric Veyra"] and "x_legendkeeper_mentions" not in els["Aldric Veyra"]
    assert "Lord of Castle" not in visible(out)
    assert (report.hidden.documents, report.hidden.secrets_inside) == (1, 1)


def test_hidden_properties_and_events_are_hidden(tmp_path: Path) -> None:
    ans = answers()
    for prop in ans[f"{P}/resources/{ALDRIC}"]["properties"]:
        prop["isHidden"] = True  # Alignment, and the Allies link
    ans[f"{P}/resources/{ORDER}/docs/ke9g0py4/events"]["data"][0]["isHidden"] = True
    out, report = run(tmp_path, ans)
    els = by_name(out)
    held = els["Aldric Veyra: hidden properties"]
    assert held["hidden"] is True and held["characters"] == [eid(ALDRIC)]
    assert held["x_legendkeeper_alignment"] == "Lawful"
    assert "x_legendkeeper_alignment" not in els["Aldric Veyra"]
    allies = {r["name"]: r for r in relations(out)}["Allies"]
    assert allies["hidden"] is True and allies["x_legendkeeper_source"] == held["id"]
    assert els["Founding"]["hidden"] is True and "hidden" not in els["The Siege"]
    h = report.hidden
    assert (h.properties, h.property_narratives, h.events, h.relations) == (2, 1, 1, 1)
    assert "1 hidden-properties Narrative holding 2 hidden properties" in report.render()


def test_ids_are_stable_across_two_runs(tmp_path: Path) -> None:
    one, _ = run(tmp_path, name="one")
    two, _ = run(tmp_path, name="two")
    assert tree(one) == tree(two)


def test_plan_writes_nothing(tmp_path: Path) -> None:
    out = tmp_path / "planned"
    report = import_legendkeeper(RecordedSource(answers()), PID, out, plan_only=True)
    assert not out.exists() and report.out is None
    assert report.counts == {"character": 1, "event": 2, "map": 1, "narrative": 5, "relation": 3}
    text = report.render()
    assert "Plan only: nothing written." in text
    assert "'faction'" in text and "'place'" in text  # the tags --map could type


def test_the_report_names_everything_not_placed(tmp_path: Path) -> None:
    _, report = run(tmp_path)
    assert report.not_imported == []
    text = report.render()
    for needle in ("'Born'", "'Rank'", "'Alignment'", "'Home'", "'Member of'", "'Allies'", "Region map", "blank"):
        assert needle in text, needle
    assert "Wrote" in text
    assert report.unread == []
    # a map with no image yet: a Map with no size, no pins, and the report says so
    assert [(m.name, m.mapless, m.pins) for m in report.maps] == [("Castle Veyra: Region map", True, 0)]
    assert report.counts.get("map") == 1


def test_ids_do_not_move_with_the_supertype(tmp_path: Path) -> None:
    """Untyped is supertype Article now (no tool name in a supertype, Skeld, OW Market h40 #11385);
    the ids are those 0.41.0 gave: the sha256 of the sorted ids, one a line. The Region map's Map,
    made since 0.53.0, is the one id added."""
    out, _ = run(tmp_path)
    ids = sorted(i for i, b in bodies(out).items() if b["type"] != "map")
    assert [b["name"] for b in bodies(out).values() if b["type"] == "map"] == ["Castle Veyra: Region map"]
    assert hashlib.sha256("\n".join(ids).encode()).hexdigest() == (
        "d5ffef3b277079ef64e225c9c91ada4d877292aae9ce06c6ff7392863a4a31e1"
    )


def test_world_json(tmp_path: Path) -> None:
    out, _ = run(tmp_path)
    world = json.loads((out / "world.json").read_text(encoding="utf-8"))
    assert world["id"] == str(uuid.uuid5(LEGENDKEEPER_NAMESPACE, f"legendkeeper:{PID}"))
    assert world["name"] == "Sikelia"
    assert world["producer"]["tool"] == "onlyworlds" and world["producer"]["input"] == "legendkeeper-api"
    assert world["format_version"] == FORMAT_VERSION


def lint(out: Path, total: int) -> None:
    """The dist's lint on a folder: no problem at all, the ``hidden`` mark included (a folder key
    since schema-dist serial 53), and its count line the total."""
    r = subprocess.run([sys.executable, str(LINT), str(out)], capture_output=True, text=True)
    lines = r.stdout.strip().splitlines()
    assert str(total) in lines[-1], r.stdout + r.stderr
    problems = [line for line in lines[:-1] if not line.startswith("walk note:")]
    assert problems == [], r.stdout + r.stderr
    assert r.returncode == 0, r.stdout + r.stderr


def test_folder_lint_passes_with_the_hidden_mark(tmp_path: Path) -> None:
    pytest.importorskip("yaml", reason="the dist's lint decodes the schema YAML")
    cases: list[tuple[str, dict[str, Any], dict[str, Any]]] = [
        ("plain", answers(), {}),
        ("mapped", answers(), {"type_map": MAP}),
        ("hidden", hide(answers(), BOSS), {}),
    ]
    for name, ans, kw in cases:
        out, report = run(tmp_path, ans, name=name, **kw)
        if name == "hidden":
            assert any(b.get("hidden") is True for b in bodies(out).values())
        lint(out, report.total)
    # with nothing hidden, the lint is green outright
    ans = answers()
    blocks = ans[f"{P}/resources/{ALDRIC}/docs/z3kj5ubq/blocks"]["blocks"]
    blocks[:] = [b for b in blocks if b["kind"] != "secret"]
    out, report = run(tmp_path, ans, name="shown")
    r = subprocess.run([sys.executable, str(LINT), str(out)], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_round_trip_is_byte_equal(tmp_path: Path) -> None:
    out, _ = run(tmp_path, type_map=MAP)
    folder = read_folder(out)
    assert not folder.skipped and folder.world is not None
    by_type: dict[str, list[dict[str, Any]]] = {}
    for el in folder.elements.values():
        by_type.setdefault(el.type, []).append(el.body)
    again = tmp_path / "again"
    write_folder(again, folder.world, by_type)
    assert tree(again) == tree(out)


def test_an_answer_that_cannot_be_read_is_reported(tmp_path: Path) -> None:
    ans = answers()
    del ans[f"{P}/resources/{ALDRIC}/docs/z3kj5ubq/blocks"]
    out, report = run(tmp_path, ans)
    assert any("Aldric Veyra" in u and "Main" in u for u in report.unread)
    assert "description" not in by_name(out)["Aldric Veyra"]
    assert report.counts["character"] == 1


def para(text: str) -> dict[str, Any]:
    return {"kind": "paragraph", "content": [{"text": text}]}


def test_other_block_kinds(tmp_path: Path) -> None:
    """The kinds the fixtures do not hold, shaped as the OpenAPI document declares them (not observed)."""
    ans = answers()
    blocks = ans[f"{P}/resources/{ALDRIC}/docs/z3kj5ubq/blocks"]["blocks"]
    blocks[:] = [
        {"kind": "heading", "level": 2, "content": [{"text": "Deeds"}]},
        {
            "kind": "bulletList",
            "children": [
                {
                    "kind": "listItem",
                    "children": [
                        para("one"),
                        {"kind": "orderedList", "children": [{"kind": "listItem", "children": [para("deep")]}]},
                    ],
                },
                {"kind": "listItem", "children": [para("two")]},
            ],
        },
        {"kind": "taskList", "children": [{"kind": "taskItem", "checked": True, "content": [{"text": "done"}]}]},
        {"kind": "quote", "children": [para("A saying.")]},
        {"kind": "callout", "tone": "warning", "children": [para("Beware.")]},
        {"kind": "code", "language": "py", "text": "print(1)"},
        {"kind": "rule"},
        {"kind": "image", "url": "https://img.example/a.png", "alt": "A crest"},
        {"kind": "embed", "provider": "youtube", "url": "https://youtube.example/v"},
        {"kind": "expand", "title": "More", "children": [para("Hidden detail.")]},
        {
            "kind": "layout",
            "children": [
                {"kind": "layoutColumn", "children": [para("Left")]},
                {"kind": "layoutColumn", "children": [para("Right")]},
            ],
        },
        {"kind": "paragraph", "content": [{"text": "x", "underline": True}, {"break": True}, {"text": "y"}]},
        {"kind": "unsupported", "id": "u1"},
    ]
    out, report = run(tmp_path, ans)
    assert by_name(out)["Aldric Veyra"]["description"] == (
        "## Deeds\n\n"
        "- one\n  1. deep\n- two\n\n"
        "- [x] done\n\n"
        "> A saying.\n\n"
        "> [!warning]\n> Beware.\n\n"
        "```py\nprint(1)\n```\n\n"
        "---\n\n"
        "![A crest](https://img.example/a.png)\n\n"
        "https://youtube.example/v\n\n"
        "**More**\n\nHidden detail.\n\n"
        "Left\n\nRight\n\n"
        "x\ny"
    )
    text = report.render()
    assert "unsupported" in text and "underline" in text


# --- the wire client ---------------------------------------------------------


def serve(ans: dict[str, Any], page_resources: bool = False) -> FakeTransport:
    """A fake LegendKeeper over HTTP from the composed answers; optionally the tree in two pages."""
    data = copy.deepcopy(ans)
    if page_resources:
        rows = data[f"{P}/resources"]["data"]
        data[f"{P}/resources"] = {"data": rows[:2], "hasMore": True, "nextCursor": "c2"}
        data[f"{P}/resources?cursor=c2"] = {"data": rows[2:], "hasMore": False, "nextCursor": None}

    def handler(method: str, url: str, headers: Any, body: bytes | None) -> Response:
        assert method == "GET" and body is None
        path = url.removeprefix(API_BASE)
        base, _, query = path.partition("?")
        cursor = [q for q in query.split("&") if q.startswith("cursor=")]
        keyed = base + ("?" + cursor[0] if cursor else "")
        if keyed not in data:
            return jresp(404, {"message": "Not found", "code": "NOT_FOUND", "requestId": "r"})
        return jresp(200, data[keyed], {"x-ratelimit-remaining": "250", "x-ratelimit-reset": "0"})

    return FakeTransport(handler=handler)


def test_the_api_source_walks_the_same_folder(tmp_path: Path) -> None:
    fake = serve(answers(), page_resources=True)
    sleeps: list[float] = []
    src = ApiSource(KEY, transport=fake, sleep=sleeps.append)
    out = tmp_path / "api"
    import_legendkeeper(src, PID, out)
    recorded, _ = run(tmp_path, name="recorded")
    assert tree(out) == tree(recorded)
    assert all(c.method == "GET" for c in fake.calls)
    assert all(c.headers["Authorization"] == f"Bearer {KEY}" for c in fake.calls)
    assert any("cursor=c2" in c.url for c in fake.calls)  # the tree was paged
    assert sleeps == []
    assert KEY not in repr(src)
    for path, data in tree(out).items():
        assert KEY.encode() not in data, path


OW_ALDRIC = "0195f3a2-7c1e-7d4b-9a10-3c5e8f2b6a01"


def pushed(ans: dict[str, Any], rid: str, rows: list[dict[str, Any]], tags: tuple[str, ...] = ()) -> None:
    """What the OnlyWorlds push writes on a resource: a Fields key-value property and its tags."""
    ans[f"{P}/resources/{rid}"]["properties"].append(
        {"id": f"fields-{rid}", "rank": "a", "kind": "keyValue", "title": "Fields", "rows": rows, "display": "list"}
    )
    for where in (ans[f"{P}/resources/{rid}"], next(r for r in ans[f"{P}/resources"]["data"] if r["id"] == rid)):
        where["tags"] = [*where.get("tags", []), *tags]


def test_a_pushed_element_comes_back_with_its_own_id_and_conventions(tmp_path: Path) -> None:
    """The push convention read back (OnlyWorlds into LegendKeeper and out): the id from the
    onlyworlds-id row, supertype and subtype from their tags, extension keys under their own names
    (JSON text read back as JSON), the push's unmapped note in the report and not on the element."""
    ans = answers()
    rows = [
        kv("onlyworlds-id", OW_ALDRIC.upper()),
        kv("onlyworlds-unmapped", "rivals: 1 link(s) outside the slice"),
        kv("atlas_aliases", '["Al", "the Heir"]'),
        kv("x_house_motto", "Ever onward"),
    ]
    pushed(ans, ALDRIC, rows, ("ow-supertype:Hero", "ow-subtype:Knight"))
    pushed(ans, BOSS, [], ("ow-supertype:Ledger",))  # an untyped page: its own supertype over Article
    out, report = run(tmp_path, ans)
    els = by_name(out)
    aldric = els["Aldric Veyra"]
    assert aldric["id"] == OW_ALDRIC
    assert (aldric["supertype"], aldric["subtype"]) == ("Hero", "Knight")
    assert aldric["atlas_aliases"] == ["Al", "the Heir"] and aldric["x_house_motto"] == "Ever onward"
    assert not [k for k in aldric if "onlyworlds" in k]
    assert report.ow_unmapped == ["'Aldric Veyra': rivals: 1 link(s) outside the slice"]
    assert by_name(out)["Boss wire test (delete me)"]["supertype"] == "Ledger"
    assert not [tag for tag in report.untyped_tags if tag.startswith("ow-")]
    assert any(n.startswith("1 element take their id from their 'onlyworlds-id' row") for n in report.notes)
    # every link to Aldric uses that id
    home = relations(out)[0]
    assert home["actor"] == OW_ALDRIC and home["x_legendkeeper_source"] == OW_ALDRIC
    # a second trip gives back the same element
    out2, _ = run(tmp_path, ans, name="again")
    assert by_name(out2)["Aldric Veyra"]["id"] == OW_ALDRIC


def test_an_onlyworlds_id_that_is_not_a_uuid_or_is_claimed_twice_is_not_the_id(tmp_path: Path) -> None:
    ans = answers()
    pushed(ans, ALDRIC, [kv("onlyworlds-id", OW_ALDRIC)])
    pushed(ans, CASTLE, [kv("onlyworlds-id", OW_ALDRIC)])  # the same id on a second resource
    pushed(ans, BOSS, [kv("onlyworlds-id", "not-a-uuid")])
    out, report = run(tmp_path, ans)
    els = by_name(out)
    assert els["Aldric Veyra"]["id"] == OW_ALDRIC
    assert els["Castle Veyra"]["id"] == eid(CASTLE)
    assert els["Castle Veyra"]["x_legendkeeper_onlyworlds-id"] == OW_ALDRIC  # kept, never dropped
    boss = els["Boss wire test (delete me)"]
    assert boss["id"] == eid(BOSS) and boss["x_legendkeeper_onlyworlds-id"] == "not-a-uuid"
    assert any("is another resource's ('Aldric Veyra')" in n for n in report.notes)


def test_the_api_source_paces_and_retries() -> None:
    sleeps: list[float] = []
    fake = FakeTransport(
        script=[
            jresp(200, {"id": PID}, {"x-ratelimit-remaining": "0", "x-ratelimit-reset": "1012"}),
            jresp(429, {"message": "Slow down", "code": "RATE_LIMITED", "requestId": "r"}, {"Retry-After": "3"}),
            jresp(200, {"id": PID}),
            jresp(402, {"message": "Upgrade", "code": "PAID_PLAN_REQUIRED", "requestId": "r"}),
        ]
    )
    src = ApiSource(KEY, transport=fake, sleep=sleeps.append, clock=lambda: 1000.0)
    assert src.get(P) == {"id": PID}
    assert sleeps == [12.0]  # remaining 0: wait to the reset
    assert src.get(P) == {"id": PID}
    assert sleeps == [12.0, 3.0]  # the 429's Retry-After, then the retry
    with pytest.raises(SourceError) as err:
        src.get(P)
    assert err.value.status == 402 and err.value.code == "PAID_PLAN_REQUIRED"
    assert KEY not in str(err.value)


# --- the command line --------------------------------------------------------


def test_cli(tmp_path: Path) -> None:
    src = RecordedSource(answers())
    out = tmp_path / "cli"
    buf = io.StringIO()
    with redirect_stdout(buf):
        assert main(["--project", PID, str(out), "--plan"], source=src) == 0
    assert "Plan only" in buf.getvalue() and not out.exists()
    with redirect_stdout(io.StringIO()):
        assert main(["--project", PID, "--map", "place=Location", str(out)], source=src) == 0
    assert by_name(out)["Castle Veyra"]["type"] == "location"
    err = io.StringIO()
    with redirect_stderr(err):
        assert main(["--project", PID, str(out)], source=src) == 2  # not empty
        assert main(["--project", PID, "--map", "place=Town", "--plan"], source=src) == 2  # not a type
        assert main(["--project", PID, "--map", "place", "--plan"], source=src) == 2
        assert main(["--plan"], source=src) == 2  # neither --project nor --file
        for gone in ("--include-hidden", "--include-secrets"):  # 0.38.0: what LegendKeeper hides comes in hidden
            with pytest.raises(SystemExit) as stop:
                main(["--project", PID, "--plan", gone], source=src)
            assert stop.value.code == 2


def test_cli_reads_the_key_and_never_prints_it(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LEGENDKEEPER_API_KEY", raising=False)
    err = io.StringIO()
    with redirect_stderr(err):
        assert main(["--project", PID, "--plan"]) == 2
    assert "LEGENDKEEPER_API_KEY" in err.getvalue()
    key_file = tmp_path / "lk.key"
    key_file.write_text(KEY + "\n", encoding="utf-8")
    fake = serve(answers())
    buf, err = io.StringIO(), io.StringIO()
    with redirect_stdout(buf), redirect_stderr(err):
        assert main(["--project", PID, "--key-file", str(key_file), str(tmp_path / "k")], transport=fake) == 0
    assert fake.calls and fake.calls[0].headers["Authorization"] == f"Bearer {KEY}"
    assert KEY not in buf.getvalue() + err.getvalue()
    monkeypatch.setenv("LEGENDKEEPER_API_KEY", KEY)
    refused = FakeTransport(script=[jresp(401, {"message": "Bad key", "code": "UNAUTHENTICATED", "requestId": "r"})])
    err = io.StringIO()
    with redirect_stdout(io.StringIO()), redirect_stderr(err):
        assert main(["--project", PID, "--plan"], transport=refused) == 2
    assert "UNAUTHENTICATED" in err.getvalue() and KEY not in err.getvalue()

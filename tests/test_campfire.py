"""The Campfire door (onlyworlds.campfire) on a real Campfire export.

``fixtures/campfire/campfire-export.html`` is the file Campfire's web app gave on 2026-10-23
(File, Export Elements, html, Select all Elements) for a project Seethe made on a free account
(Boss read it: no script, form, image or tracker, no mail, key, token or handle, one Google Fonts import).
Its bytes are kept. Two elements: Ada Okafor (a Character: a description, Full Name, Place of
Residence "The quay", a Bio naming Mara Voss) and The Ferry Quay (a Location: a description).
The file names no module, has no ids, no links and no hidden marks; what it does not show runs
on planted copies.
"""

from __future__ import annotations

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

from onlyworlds import campfire, read_folder, write_folder
from onlyworlds.campfire import (
    CAMPFIRE_NAMESPACE,
    MODULE_TYPES,
    PRODUCER_INPUT,
    SEEN_MODULES,
    TEMPLATE_MODULES,
    UNTYPED_SUPERTYPE,
    ImportReport,
    import_campfire,
    main,
)
from onlyworlds.folder import FORMAT_VERSION

ROOT = Path(__file__).resolve().parents[1]
LINT = ROOT / "codegen" / "schema-dist" / "walk" / "lint_folder.py"
EXPORT = Path(__file__).resolve().parent / "fixtures" / "campfire" / "campfire-export.html"
SHA256 = "ec82065044a3c2df25205418b2fca80f983283d6821a6ac20b4375cf0df22333"
RESIDENCE = '<span style="font-size: 12pt; ">The quay</span>'
BIO_PANEL = re.compile(
    r'\s*<section class="panel-section panel-text">\s*<h4 class="panel-header">Bio</h4>.*?</section>', re.S
)
END = "</div></section></div></div></section></div>\n    </main>"
APOS, DASH = chr(0x2019), chr(0x2014)  # the file's apostrophe and its empty mark

#: What must never be in the fixture.
FORBIDDEN = {
    "a script": re.compile(r"<script\b", re.IGNORECASE),
    "a form": re.compile(r"<form\b", re.IGNORECASE),
    "a mail address": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
}


def eid(etype: str, name: str) -> str:
    return str(uuid.uuid5(CAMPFIRE_NAMESPACE, f"campfire:{etype}:{name}"))


ADA, QUAY = eid("character", "Ada Okafor"), eid("location", "The Ferry Quay")


def run(tmp: Path, src: Path = EXPORT, name: str = "world", **kw: Any) -> tuple[Path, ImportReport]:
    out = tmp / name
    return out, import_campfire(src, out, **kw)


def planted(tmp: Path, *swaps: tuple[str, str], name: str = "planted.html") -> Path:
    """The real export with each ``old`` replaced once by ``new`` (each must be there once)."""
    text = EXPORT.read_text(encoding="utf-8")
    for old, new in swaps:
        assert text.count(old) == 1, old
        text = text.replace(old, new)
    path = tmp / name
    path.write_text(text, encoding="utf-8", newline="")
    return path


def element(name: str, *panels: tuple[str, list[tuple[str, str]]], description: str = "") -> str:
    """A planted export-item in Campfire's markup: custom panels of Label / value pairs."""
    rows = "".join(
        f'<section class="panel-section panel-custom"><h4 class="panel-header">{head}</h4>'
        '<div class="panel-content"><dl class="custom-panel attributes-list">'
        + "".join(
            f'<div class="attribute-row"><dt class="attribute-label">{k}</dt><dd class="attribute-value">'
            f"<p><span>{v}</span></p></dd></div>"
            for k, v in pairs
        )
        + "</dl></div></section>"
        for head, pairs in panels
    )
    return (
        f'<section class="export-item pb_before"><header class="item-header"><h2 class="item-title">{name}</h2>'
        f'<div class="item-description"><p><span>{description}</span></p></div></header>'
        '<div class="pages-collection"><div class="page-wrapper"><section class="page-section">'
        '<header class="page-header"><h3 class="page-title">Overview</h3></header>'
        f'<div class="page-panels">{rows}</div></section></div></div></section>'
    )


def with_elements(tmp: Path, *items: str, name: str = "more.html") -> Path:
    return planted(
        tmp, (END, END.replace("</section></div>\n", "</section>" + "".join(items) + "</div>\n", 1)), name=name
    )


def bodies(out: Path) -> dict[str, dict[str, Any]]:
    return {e.id: e.body for e in read_folder(out).elements.values()}


def by_name(out: Path) -> dict[str, dict[str, Any]]:
    return {b["name"]: b for b in bodies(out).values()}


def tree(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def lint(out: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(LINT), str(out)], capture_output=True, text=True)


# --- the fixture -------------------------------------------------------------


def test_the_fixture_is_the_real_file() -> None:
    assert hashlib.sha256(EXPORT.read_bytes()).hexdigest() == SHA256
    assert len(EXPORT.read_bytes()) == 30206


def test_the_fixture_carries_no_script_no_form_no_mail() -> None:
    text = EXPORT.read_text(encoding="utf-8")
    found = {what: pat.findall(text) for what, pat in FORBIDDEN.items() if pat.search(text)}
    assert not found, found
    assert text.count("fonts.googleapis.com") == 1  # the one outside fetch: a font import


def test_the_forbidden_patterns_catch_what_they_name() -> None:
    samples = ["<SCRIPT src=x>", '<form action="/x">', "write to someone@example.org"]
    assert {what for what, pat in FORBIDDEN.items() for s in samples if pat.search(s)} == set(FORBIDDEN)


def test_namespace_producer_and_tables_are_pinned() -> None:
    """Changing the namespace would give every element of every re-imported project a new id."""
    assert str(CAMPFIRE_NAMESPACE) == str(uuid.uuid5(uuid.NAMESPACE_URL, "https://onlyworlds.com/ns/campfire"))
    assert PRODUCER_INPUT == "campfire-export"  # the folder spec's §4.2 word (v0.3.18)
    assert UNTYPED_SUPERTYPE == "Article"
    assert set(MODULE_TYPES) >= SEEN_MODULES and {MODULE_TYPES[m] for m in SEEN_MODULES} == {"character", "location"}
    assert set(TEMPLATE_MODULES) == SEEN_MODULES  # a template's words only where a real file showed them
    assert not TEMPLATE_MODULES["characters"] & TEMPLATE_MODULES["locations"]


def test_the_module_table_is_as_ruled() -> None:
    """Skeld's ruling: the whole table; every other module an Article Narrative."""
    assert MODULE_TYPES == {
        "characters": "character",
        "locations": "location",
        "species": "species",
        "cultures": "species",
        "items": "object",
        "languages": "language",
        "religions": "construct",
        "philosophies": "construct",
        "systems": "construct",
        "magic": "construct",
        "maps": "map",
    }
    assert {"characters", "locations"} == SEEN_MODULES
    for unknown in ("timelines", "arcs", "manuscript", "encyclopedia", "research", "relationships"):
        assert unknown not in MODULE_TYPES


# --- the real file -----------------------------------------------------------


def test_the_real_export(tmp_path: Path) -> None:
    out, report = run(tmp_path)
    assert report.counts == {"character": 1, "location": 1}
    els = bodies(out)
    assert set(els) == {ADA, QUAY}
    assert els[ADA] == {
        "type": "character",
        "id": ADA,
        "name": "Ada Okafor",
        "description": f"The ferry{APOS}s ledger-keeper on the quay.",
        "x_campfire_basic_information_full_name": "Ada Okafor",
        "x_campfire_basic_information_place_of_residence": "The quay",
        "x_campfire_bio": (
            f"Keeps the ferry{APOS}s ledger and knows every name that crossed. Mara Voss owes her a fare."
        ),
    }
    assert els[QUAY] == {
        "type": "location",
        "id": QUAY,
        "name": "The Ferry Quay",
        "description": "The stone landing where the ferry ties up and the ledger is kept.",
        "x_campfire_location_details_location_age": 0,
        "x_campfire_basic_information_area": 0,
        "x_campfire_basic_information_population": 0,
        "x_campfire_basic_information_average_temperature": 0,
    }
    assert {(p.module, p.type, p.status) for p in report.plans} == {
        ("Characters", "character", "seen"),
        ("Locations", "location", "seen"),
    }
    world = json.loads((out / "world.json").read_text(encoding="utf-8"))
    assert world == {
        "id": str(uuid.uuid5(CAMPFIRE_NAMESPACE, "campfire:world:Campfire Export")),
        "name": "Campfire Export",
        "format_version": FORMAT_VERSION,
        "producer": {"tool": "onlyworlds", "version": world["producer"]["version"], "input": "campfire-export"},
    }


def test_the_em_dash_is_empty_and_not_written(tmp_path: Path) -> None:
    out, report = run(tmp_path)
    ada = bodies(out)[ADA]
    assert not any(k.endswith(("origin_country", "gender", "formal_education", "occupation")) for k in ada)
    assert DASH not in json.dumps(bodies(out), ensure_ascii=False)
    assert ("Ada Okafor", "Basic Information", "Gender") in report.empty
    full = '<span style="font-size: 12pt; ">Ada Okafor</span>'
    out2, _ = run(tmp_path, planted(tmp_path, (full, f'<span class="no-value">{DASH}</span>')), name="dash")
    assert "x_campfire_basic_information_full_name" not in bodies(out2)[ADA]


def test_place_of_residence_naming_no_location_stays_the_field(tmp_path: Path) -> None:
    """The real file: 'The quay' is not 'The Ferry Quay', so no link."""
    out, report = run(tmp_path)
    ada = bodies(out)[ADA]
    assert "location" not in ada and ada["x_campfire_basic_information_place_of_residence"] == "The quay"
    assert report.resolved == [] and report.unresolved == [("Ada Okafor", "The quay")]


def test_place_of_residence_naming_a_location_becomes_the_link(tmp_path: Path) -> None:
    src = planted(tmp_path, (RESIDENCE, RESIDENCE.replace("The quay", "The Ferry Quay")))
    out, report = run(tmp_path, src)
    ada = bodies(out)[ADA]
    assert ada["location"] == QUAY and bodies(out)[ada["location"]]["name"] == "The Ferry Quay"
    assert "x_campfire_basic_information_place_of_residence" not in ada
    assert report.resolved == [("Ada Okafor", "The Ferry Quay")] and report.unresolved == []
    assert "Place of Residence made the location link (1)" in report.render()


def test_place_of_residence_must_equal_exactly(tmp_path: Path) -> None:
    src = planted(tmp_path, (RESIDENCE, RESIDENCE.replace("The quay", "the ferry quay")))
    out, _ = run(tmp_path, src)
    assert "location" not in bodies(out)[ADA]


def test_a_name_in_prose_stays_prose(tmp_path: Path) -> None:
    out, report = run(tmp_path)
    assert "Mara Voss" in bodies(out)[ADA]["x_campfire_bio"]
    assert "Mara Voss" not in {b["name"] for b in bodies(out).values()}
    assert not any("mention" in k or k == "location" for b in bodies(out).values() for k in b)
    assert "Mara Voss" not in "".join(v for _, v in report.resolved + report.unresolved)


def test_nothing_is_hidden_and_the_report_says_the_files_limits(tmp_path: Path) -> None:
    out, report = run(tmp_path)
    assert not any("hidden" in b for b in bodies(out).values())
    text = report.render()
    for needle in (
        "It has no ids: each element's id is derived from its type and its name",
        "a renamed element comes in as a new one",
        "The file holds no links between elements",
        "Nothing in the file marks an element hidden",
        "The file names no module",
        "Two projects exported under Campfire's default title 'Campfire Export' would share ids",
        "--project NAME keys them apart",
    ):
        assert needle in text, needle


def test_the_report_names_each_elements_module_evidence(tmp_path: Path) -> None:
    """Per element: which panel words matched which module (Skeld's ruling)."""
    _, report = run(tmp_path)
    ev = {e.element: e for e in report.evidence}
    assert [e.element for e in report.evidence] == ["Ada Okafor", "The Ferry Quay"]
    assert (ev["Ada Okafor"].module, ev["Ada Okafor"].type) == ("characters", "character")
    assert ev["Ada Okafor"].matched == tuple(
        ("characters", "Basic Information", k)
        for k in ("Full Name", "Origin Country", "Place of Residence", "Formal Education", "Occupation")
    )
    assert {m for m, _, _ in ev["The Ferry Quay"].matched} == {"locations"}
    assert ("locations", "Location Details", "Location Type") in ev["The Ferry Quay"].matched
    text = report.render()
    assert (
        "'Ada Okafor': Characters, from 'Basic Information' / 'Full Name', 'Basic Information' / 'Origin Country',"
        in text
    )
    assert "'The Ferry Quay': Locations, from 'Location Details' / 'Location Type'," in text


def test_the_report_names_everything_not_placed(tmp_path: Path) -> None:
    _, report = run(tmp_path)
    assert [(e, p, k) for e, p, k, _ in report.kept] == [
        ("Ada Okafor", "Basic Information", "Full Name"),
        ("Ada Okafor", "Basic Information", "Place of Residence"),
        ("Ada Okafor", "Bio", ""),
        ("The Ferry Quay", "Location Details", "Location Age"),
        ("The Ferry Quay", "Basic Information", "Area"),
        ("The Ferry Quay", "Basic Information", "Population"),
        ("The Ferry Quay", "Basic Information", "Average Temperature"),
    ]
    assert len(report.empty) == 17 and len(report.zeros) == 4
    text = report.render()
    for needle in (
        "'Ada Okafor' / 'Bio': x_campfire_bio",
        "'Ada Okafor': 'The quay'",
        "Numbers printed 0 (4), kept as 0",
        "'The Ferry Quay' / 'History'",
        "'Ada Okafor' / 'Basic Information' / 'Occupation'",
        "The file names no project",
        "Wrote ",
    ):
        assert needle in text, needle
    assert not any("outside" in n for n in report.notes)  # nothing read past, in an element or on the page


def test_folder_lint_is_clean(tmp_path: Path) -> None:
    pytest.importorskip("yaml", reason="the dist's lint decodes the schema YAML")
    out, report = run(tmp_path)
    r = lint(out)
    assert r.returncode == 0, r.stdout + r.stderr
    assert f"checked {report.total} element files" in r.stdout


def test_folder_lint_is_clean_with_the_link(tmp_path: Path) -> None:
    pytest.importorskip("yaml", reason="the dist's lint decodes the schema YAML")
    out, _ = run(tmp_path, planted(tmp_path, (RESIDENCE, RESIDENCE.replace("The quay", "The Ferry Quay"))))
    r = lint(out)
    assert r.returncode == 0, r.stdout + r.stderr


def test_deterministic(tmp_path: Path) -> None:
    one, _ = run(tmp_path, name="one")
    two, _ = run(tmp_path, name="two")
    assert tree(one) == tree(two)


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
    report = import_campfire(EXPORT, out, plan_only=True)
    assert not out.exists() and report.out is None and report.total == 2
    assert "Plan only: nothing written." in report.render()


# --- what the real file does not show (planted) --------------------------------


def test_an_element_of_no_known_module_is_an_article(tmp_path: Path) -> None:
    rules = element("Tidecalling", ("Rules", [("Source", "The river"), ("Cost", DASH)]), description="Water magic.")
    out, report = run(tmp_path, with_elements(tmp_path, rules))
    tide = by_name(out)["Tidecalling"]
    assert tide["type"] == "narrative" and tide["supertype"] == "Article" and "subtype" not in tide
    assert tide["description"] == "Water magic." and tide["x_campfire_rules_source"] == "The river"
    assert ("Tidecalling", "its panels name no module this door knows") in report.untyped
    assert ("", "narrative", "unknown") in {(p.module, p.type, p.status) for p in report.plans}
    text = report.render()
    assert "'Tidecalling': its panels name no module this door knows" in text
    assert "'Tidecalling': no panel words of a module this door knows; a Narrative, supertype Article" in text
    assert next(e for e in report.evidence if e.element == "Tidecalling").matched == ()


def test_a_magic_module_is_a_construct(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Skeld's ruling: a magic system is how the world works, so a Construct (believed)."""
    monkeypatch.setitem(campfire.TEMPLATE_MODULES, "magic", frozenset({("rules", "source")}))
    rules = element("Tidecalling", ("Rules", [("Source", "The river")]))
    out, report = run(tmp_path, with_elements(tmp_path, rules))
    tide = by_name(out)["Tidecalling"]
    assert tide["type"] == "construct" and "supertype" not in tide and tide["x_campfire_rules_source"] == "The river"
    assert ("Magic", "construct", "believed") in {(p.module, p.type, p.status) for p in report.plans}
    assert "'Tidecalling': Magic, from 'Rules' / 'Source'; a construct" in report.render()


def test_a_module_not_in_the_table_is_an_article_with_its_name(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A module the panels name but ``MODULE_TYPES`` does not type: its name the subtype."""
    monkeypatch.setitem(campfire.TEMPLATE_MODULES, "timelines", frozenset({("events", "era")}))
    era = element("The Long Tide", ("Events", [("Era", "The second flood")]))
    out, report = run(tmp_path, with_elements(tmp_path, era))
    tide = by_name(out)["The Long Tide"]
    assert (tide["type"], tide["supertype"], tide["subtype"]) == ("narrative", "Article", "Timelines")
    assert ("The Long Tide", "the module 'timelines' has no OnlyWorlds type") in report.untyped
    assert ("Timelines", "narrative", "untyped") in {(p.module, p.type, p.status) for p in report.plans}
    assert (
        "'The Long Tide': Timelines, from 'Events' / 'Era'; a Narrative, supertype Article, subtype Timelines"
        in report.render()
    )


def test_two_modules_named_is_untyped(tmp_path: Path) -> None:
    both = element("Mixed", ("Basic Information", [("Full Name", "X"), ("Biome", "Marsh")]))
    out, report = run(tmp_path, with_elements(tmp_path, both))
    mixed = by_name(out)["Mixed"]
    assert mixed["type"] == "narrative" and mixed["supertype"] == "Article"
    assert "'Mixed': its panels name two modules (characters, locations): untyped" in report.notes
    assert (
        "'Mixed': two modules (Characters from 'Basic Information' / 'Full Name';"
        " Locations from 'Basic Information' / 'Biome'); a Narrative, supertype Article"
    ) in report.render()


def test_a_missing_panel(tmp_path: Path) -> None:
    """Campfire leaves an empty panel out: Ada with no Bio is still a Character, with no Bio key."""
    text = EXPORT.read_text(encoding="utf-8")
    new, n = BIO_PANEL.subn("", text)
    assert n == 1
    src = tmp_path / "no-bio.html"
    src.write_text(new, encoding="utf-8", newline="")
    out, report = run(tmp_path, src)
    ada = bodies(out)[ADA]
    assert ada["type"] == "character" and "x_campfire_bio" not in ada
    assert ("Ada Okafor", "Bio", "") not in [(e, p, k) for e, p, k, _ in report.kept]


def test_a_second_element_of_one_name_is_keyed_apart(tmp_path: Path) -> None:
    other = element("Ada Okafor", ("Basic Information", [("Full Name", "Ada Okafor the younger")]))
    out, report = run(tmp_path, with_elements(tmp_path, other))
    assert report.counts == {"character": 2, "location": 1}
    second = str(uuid.uuid5(CAMPFIRE_NAMESPACE, "campfire:character:Ada Okafor:2"))
    assert set(bodies(out)) == {ADA, QUAY, second}
    assert report.renamed == [("Ada Okafor", "campfire:character:Ada Okafor:2")]


def test_an_exact_copy_folds(tmp_path: Path) -> None:
    text = EXPORT.read_text(encoding="utf-8")
    start = text.index('<section class="export-item pb_before">')
    end = text.index("</div>\n    </main>")
    src = tmp_path / "twice.html"
    src.write_text(text[:end] + text[start:end] + text[end:], encoding="utf-8", newline="")
    _, report = run(tmp_path, src)
    assert report.counts == {"character": 1, "location": 1}
    assert [(f.element, f.copies) for f in report.folded] == [("The Ferry Quay", 2)]


def test_text_no_part_reads_is_kept_and_named(tmp_path: Path) -> None:
    desc = "on the quay.</span></p>\n</div></header>"
    out, report = run(tmp_path, planted(tmp_path, (desc, desc + '<div class="stray">Sails at dawn.</div>')))
    assert bodies(out)[ADA]["x_campfire_unread"] == "Sails at dawn."
    assert "'Ada Okafor': text outside the parts this door reads, kept as x_campfire_unread" in report.notes


def test_a_panel_kind_not_yet_seen_is_read_as_text(tmp_path: Path) -> None:
    listed = (
        '<section class="panel-section panel-list"><h4 class="panel-header">Allies</h4><div class="panel-content">'
        '<div class="list-panel"><div class="list-item"><h5>Mara Voss</h5></div></div></div></section>'
    )
    out, report = run(
        tmp_path,
        planted(
            tmp_path,
            (
                "\n  </div></section></div></div></section><section",
                f"{listed}</div></section></div></div></section><section",
            ),
        ),
    )
    assert bodies(out)[ADA]["x_campfire_allies"] == "##### Mara Voss"
    assert "'Ada Okafor' / 'Allies': a panel-list panel, not yet seen in a real export; read as text" in report.notes


# --- the project name (--project; Skeld's ruling) ---------------


def world_of(out: Path) -> dict[str, Any]:
    return dict(json.loads((out / "world.json").read_text(encoding="utf-8")))


def test_without_a_project_the_ids_are_todays(tmp_path: Path) -> None:
    """Pinned as literals: without --project the ids are exactly 0.41.0's first build's."""
    out, report = run(tmp_path)
    assert ADA == "01dad068-f8cf-5052-90ab-8dddda8d62cb" and QUAY == "3c8a8002-1c36-5a61-b5e6-bb2d12c800da"
    assert set(bodies(out)) == {ADA, QUAY}
    assert world_of(out)["id"] == "8e90fd5a-771b-5309-b0f5-a45775066e21"
    assert world_of(out)["name"] == "Campfire Export" and report.project is None


def test_a_project_keys_every_id_and_names_the_world(tmp_path: Path) -> None:
    out, report = run(tmp_path, project="Harbour")
    keyed = {
        str(uuid.uuid5(CAMPFIRE_NAMESPACE, f"campfire:Harbour:{t}:{n}"))
        for t, n in (
            ("character", "Ada Okafor"),
            ("location", "The Ferry Quay"),
        )
    }
    assert set(bodies(out)) == keyed and not keyed & {ADA, QUAY}
    world = world_of(out)
    assert world["name"] == "Harbour"
    assert world["id"] == str(uuid.uuid5(CAMPFIRE_NAMESPACE, "campfire:Harbour:world"))
    assert world["format_version"] == FORMAT_VERSION
    ada = by_name(out)["Ada Okafor"]
    assert ada["id"] == str(uuid.uuid5(CAMPFIRE_NAMESPACE, "campfire:Harbour:character:Ada Okafor"))
    text = report.render()
    assert "The world is named for the project given ('Harbour')" in text and "--project NAME keys" not in text
    again, _ = run(tmp_path, name="again", project="Harbour")
    assert tree(again) == tree(out)  # stable across runs


def test_two_project_names_give_two_sets_of_ids(tmp_path: Path) -> None:
    one, _ = run(tmp_path, name="one", project="Harbour")
    two, _ = run(tmp_path, name="two", project="Inland")
    assert not set(bodies(one)) & set(bodies(two))
    assert world_of(one)["id"] != world_of(two)["id"]


def test_a_project_keys_a_second_element_of_one_name(tmp_path: Path) -> None:
    other = element("Ada Okafor", ("Basic Information", [("Full Name", "Ada Okafor the younger")]))
    _, report = run(tmp_path, with_elements(tmp_path, other), project="Harbour")
    assert report.renamed == [("Ada Okafor", "campfire:Harbour:character:Ada Okafor:2")]


def test_a_blank_project_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="--project"):
        import_campfire(EXPORT, tmp_path / "x", project="  ")
    assert not (tmp_path / "x").exists()


def test_not_a_campfire_export(tmp_path: Path) -> None:
    bad = tmp_path / "bad.html"
    bad.write_text("<html><body><p>hello</p></body></html>", encoding="utf-8")
    with pytest.raises(ValueError, match="not a Campfire export"):
        import_campfire(bad, tmp_path / "x")
    with pytest.raises(FileNotFoundError):
        import_campfire(tmp_path / "missing.html", tmp_path / "y")


# --- the command line --------------------------------------------------------


def test_cli(tmp_path: Path) -> None:
    out = tmp_path / "cli"
    buf = io.StringIO()
    with redirect_stdout(buf):
        assert main(["--file", str(EXPORT), str(out), "--plan"]) == 0
    assert "Plan only" in buf.getvalue() and not out.exists()
    with redirect_stdout(io.StringIO()):
        assert main(["--file", str(EXPORT), str(out)]) == 0
    assert by_name(out)["Ada Okafor"]["type"] == "character"
    err = io.StringIO()
    with redirect_stderr(err):
        assert main(["--file", str(EXPORT), str(out)]) == 2  # not empty
        assert main(["--file", str(tmp_path / "missing.html"), "--plan"]) == 2
        assert main([str(out)]) == 2  # no --file
        assert main(["--file", str(EXPORT)]) == 2  # no OUT-DIR, no --plan
        assert main(["--file", str(EXPORT), str(tmp_path / "blank"), "--project", " "]) == 2
    assert "missing.html" in err.getvalue() and "--project" in err.getvalue()
    assert not (tmp_path / "blank").exists()


def test_cli_project(tmp_path: Path) -> None:
    out = tmp_path / "cli"
    buf = io.StringIO()
    with redirect_stdout(buf):
        assert main(["--file", str(EXPORT), str(out), "--project", "Harbour", "--plan"]) == 0
    assert "Plan only" in buf.getvalue() and "('Harbour')" in buf.getvalue() and not out.exists()
    with redirect_stdout(io.StringIO()):
        assert main(["--file", str(EXPORT), str(out), "--project", "Harbour"]) == 0
    assert world_of(out)["name"] == "Harbour"
    assert by_name(out)["Ada Okafor"]["id"] == str(
        uuid.uuid5(CAMPFIRE_NAMESPACE, "campfire:Harbour:character:Ada Okafor")
    )

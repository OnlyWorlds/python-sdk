"""The World Anvil door (onlyworlds.worldanvil) on two real World Anvil exports.

``fixtures/worldanvil/the-quay-world-export-1.scrubbed.html`` and ``-2.scrubbed.html`` are the
page World Anvil's "Export World" gave on 2026-10-23 for a world made on a free account,
each scrubbed by script of the page's scripts, forms, share links and the account's handle
(``[author]``). Only the scrubbed copies may be fixtures.
The first: three articles, Ada Quay (a Character, body text, fields Gender Woman and Eyes Grey),
Riverfolk (a Species), The ferry crossing (a Geographic Location), and an empty Species draft
the Codex lists with no title and the export prints no article for. The second: the same world
later, Ada Quay and Riverfolk linking each other, Riverfolk in a category "Quay folk", and two
mentions World Anvil did not resolve (``@Ada``, ``@Ada Quay``). Neither has an article that is
not public, nor a Secret: those paths run on planted copies.
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

from onlyworlds import read_folder, write_folder
from onlyworlds.folder import FORMAT_VERSION
from onlyworlds.worldanvil import (
    DATE_KEYS,
    PRODUCER_INPUT,
    PROVEN_TEMPLATES,
    TEMPLATE_TYPES,
    UNTYPED_SUPERTYPE,
    WORLDANVIL_NAMESPACE,
    ImportReport,
    import_worldanvil,
    main,
)

ROOT = Path(__file__).resolve().parents[1]
LINT = ROOT / "codegen" / "schema-dist" / "walk" / "lint_folder.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "worldanvil"
ONE = FIXTURES / "the-quay-world-export-1.scrubbed.html"
TWO = FIXTURES / "the-quay-world-export-2.scrubbed.html"
SHA256 = {
    ONE: "ffde7951d3818a9dd612f5e345c4577f8e5c1e119d680c9c09c537cba5163ca1",
    TWO: "72cbc88d49c214466b2ab84a62688161c493781d5dd77b6984c1989dd9163a6d",
}
WORLD = "1a081cde-5f42-4aa9-9506-948fcb0c54b5"
ADA, RIVERFOLK, FERRY = (
    "d7e88519-cc6b-4476-bab5-e0b62f813a79",
    "9d377749-9177-4f9f-98a8-1fb56309e1a6",
    "2d0c7829-9295-4b4a-a105-8cbb263c186d",
)
DRAFT = "516196cd-dc42-4482-b670-858883651a33"  # the Codex's untitled Species draft, no article
TYPES = {"Ada Quay": "character", "Riverfolk": "species", "The ferry crossing": "location"}
RIVERFOLK_LINK = f'data-article-privacy="public" data-article-id="{RIVERFOLK}"'

#: The export account's handle, by hash (sha256 of the lowercased name), so the name stays out of
#: the package: no word-ish token of a fixture may hash to it.
HANDLE_SHA256 = "115bc6ac1c0836fbd92dda1b8a74d16a2d36f56ad66b75c55f43aaa9068a094c"


def tokens_hashing_to(text: str, digest: str) -> list[str]:
    """The word-ish tokens of ``text``, lowercased, whose sha256 is ``digest``."""
    words = {w.lower() for w in re.findall(r"[A-Za-z0-9_]+", text)}
    return sorted(w for w in words if hashlib.sha256(w.encode("utf-8")).hexdigest() == digest)


#: What must never be in a fixture: the comment form's CSRF token, analytics ids (the handle: above).
FORBIDDEN = {
    "the comment form's CSRF token": re.compile(r"appbundle_comment(\[_token\])?"),
    "a Google Analytics 4 id": re.compile(r"G-[A-Za-z0-9]+"),
    "a Universal Analytics id": re.compile(r"UA-\d+"),
    "a gtag call": re.compile(r"gtag\("),
    "Google Tag Manager": re.compile(r"googletagmanager"),
    "a Bing UET beacon": re.compile(r"bat\.bing\.(net|com)"),
}


def eid(article: str) -> str:
    return str(uuid.uuid5(WORLDANVIL_NAMESPACE, f"worldanvil:{WORLD}:{article}"))


def run(tmp: Path, src: Path = TWO, name: str = "world", **kw: Any) -> tuple[Path, ImportReport]:
    out = tmp / name
    return out, import_worldanvil(src, out, **kw)


def planted(tmp: Path, src: Path, *swaps: tuple[str, str], name: str = "planted.html") -> Path:
    """The real export with each ``old`` replaced once by ``new`` (each must be there once)."""
    text = src.read_text(encoding="utf-8")
    for old, new in swaps:
        assert text.count(old) == 1, old
        text = text.replace(old, new)
    path = tmp / name
    path.write_text(text, encoding="utf-8", newline="")
    return path


def bodies(out: Path) -> dict[str, dict[str, Any]]:
    return {e.id: e.body for e in read_folder(out).elements.values()}


def by_name(out: Path) -> dict[str, dict[str, Any]]:
    return {b["name"]: b for b in bodies(out).values()}


def tree(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def visible(out: Path) -> str:
    return json.dumps([b for b in bodies(out).values() if b.get("hidden") is not True])


def lint(out: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(LINT), str(out)], capture_output=True, text=True)


# --- the fixtures ------------------------------------------------------------


def test_the_fixtures_are_the_scrubbed_files() -> None:
    for path, sha in SHA256.items():
        assert hashlib.sha256(path.read_bytes()).hexdigest() == sha, path.name


@pytest.mark.parametrize("path", [ONE, TWO], ids=["export-1", "export-2"])
def test_no_fixture_carries_a_token_a_handle_or_an_analytics_id(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    found = {what: pat.findall(text) for what, pat in FORBIDDEN.items() if pat.search(text)}
    assert not found, f"{path.name}: {found}"
    assert not tokens_hashing_to(text, HANDLE_SHA256), f"{path.name}: the account's handle"


@pytest.mark.parametrize("planted", ["plantedhandle", "PlantedHandle"])
def test_the_handle_check_flags_a_planted_token(planted: str) -> None:
    """The check, run over the digest of a stand-in name: it finds the token, any case, in prose."""
    digest = hashlib.sha256(b"plantedhandle").hexdigest()
    assert tokens_hashing_to(f'<a href="/~{planted}">by {planted}</a>', digest) == ["plantedhandle"]
    assert tokens_hashing_to("by someone-else plantedhandles", digest) == []


def test_the_forbidden_patterns_catch_what_they_name() -> None:
    samples = [
        'name="appbundle_comment[_token]"',
        "gtag('config', 'G-ABC123XYZ')",
        "UA-12345-1",
        "https://www.googletagmanager.com/gtm.js",
        "https://bat.bing.net/action/0?ti=343205616&amp;Ver=2",
    ]
    hit = {what for what, pat in FORBIDDEN.items() for s in samples if pat.search(s)}
    assert hit == set(FORBIDDEN)


def test_namespace_and_producer_word_are_pinned() -> None:
    """Changing the namespace would give every element of every re-imported world a new id."""
    assert str(WORLDANVIL_NAMESPACE) == str(uuid.uuid5(uuid.NAMESPACE_URL, "https://onlyworlds.com/ns/worldanvil"))
    assert PRODUCER_INPUT == "worldanvil-export"  # folder spec §4.2's list
    assert set(TEMPLATE_TYPES) >= PROVEN_TEMPLATES
    # Organization read on a real page 2026-10-26
    assert {TEMPLATE_TYPES[k] for k in PROVEN_TEMPLATES} == {"character", "species", "location", "institution"}
    assert UNTYPED_SUPERTYPE == "Article"  # what it is, never where it came from


def test_the_template_table_is_the_owners_ruling() -> None:
    """Ruled: every row of 0.39.0 holds, four added, anything else unknown."""
    assert TEMPLATE_TYPES == {
        "character": "character",
        "person": "character",
        "species": "species",
        "geographic location": "location",
        "location": "location",
        "settlement": "location",
        "building / landmark": "location",
        "landmark": "location",
        "organization": "institution",
        "item": "object",
        "language": "language",
        "law": "law",
        "spell": "ability",
        "military conflict": "event",
        "conflict": "event",
        "rank / title": "title",
        "rank": "title",
        "ethnicity": "species",
        "myth / legend": "narrative",
        "vehicle": "object",
        "profession": "title",
    }


# --- the real files ----------------------------------------------------------


def test_the_first_export(tmp_path: Path) -> None:
    out, report = run(tmp_path, ONE)
    assert report.counts == {"character": 1, "location": 1, "species": 1}
    els = by_name(out)
    assert {n: b["type"] for n, b in els.items()} == TYPES
    ada = els["Ada Quay"]
    assert ada["id"] == eid(ADA) and ada["x_worldanvil_id"] == ADA
    assert ada["description"] == "Ada keeps the ferry at the quay and knows every crossing of the river."
    assert (ada["x_worldanvil_gender"], ada["x_worldanvil_eyes"]) == ("Woman", "Grey")  # no such fields
    assert ada["x_worldanvil_template"] == "Character" and ada["x_worldanvil_work_in_progress"] is True
    assert els["The ferry crossing"]["x_worldanvil_template"] == "Geographic Location"
    assert not any("hidden" in b or "x_worldanvil_mentions" in b for b in els.values())
    assert not any("x_worldanvil_category" in b for b in els.values())
    assert {(t.template, t.type, t.status) for t in report.templates} == {
        ("Character", "character", "proven"),
        ("Geographic Location", "location", "proven"),
        ("Species", "species", "proven"),
    }
    assert report.codex_only == [(DRAFT, "")]  # listed, never printed: not made
    for b in els.values():  # the three dates, kept under the export's words, as ISO 8601
        assert {k: b[k] for k in DATE_KEYS.values()} == dict.fromkeys(DATE_KEYS.values(), "2026-10-23")
    assert report.dates == 9 and report.dates_unparsed == []
    world = json.loads((out / "world.json").read_text(encoding="utf-8"))
    assert world == {
        "id": str(uuid.uuid5(WORLDANVIL_NAMESPACE, f"worldanvil:{WORLD}")),
        "name": "The quay world",
        "format_version": FORMAT_VERSION,
        "producer": {"tool": "onlyworlds", "version": world["producer"]["version"], "input": "worldanvil-export"},
    }


def test_the_two_exports_give_the_same_ids(tmp_path: Path) -> None:
    one, _ = run(tmp_path, ONE, name="one")
    two, _ = run(tmp_path, TWO, name="two")
    assert set(bodies(one)) == set(bodies(two)) == {eid(ADA), eid(RIVERFOLK), eid(FERRY)}
    assert (one / "world.json").read_bytes() == (two / "world.json").read_bytes()


def test_links_round_trip_by_id(tmp_path: Path) -> None:
    """Ada links Riverfolk and Riverfolk links Ada: each a mention by element id, the text kept."""
    out, report = run(tmp_path)
    els = bodies(out)
    ada, riverfolk = els[eid(ADA)], els[eid(RIVERFOLK)]
    assert ada["x_worldanvil_mentions"] == [eid(RIVERFOLK)] and els[ada["x_worldanvil_mentions"][0]] is riverfolk
    assert riverfolk["x_worldanvil_mentions"] == [eid(ADA)] and els[riverfolk["x_worldanvil_mentions"][0]] is ada
    assert ada["description"].endswith("Her people are the Riverfolk .")  # the text as World Anvil prints it
    assert riverfolk["description"].endswith("Their keeper: Ada Quay .")
    assert "/edit" not in json.dumps(els) and "athena" not in json.dumps(els)  # the editor anchor is chrome
    assert (ada["x_worldanvil_template_type"], riverfolk["x_worldanvil_template_type"]) == ("person", "species")
    assert report.unresolved == [] and not any("x_worldanvil_unresolved" in b for b in els.values())


def test_the_category_is_kept(tmp_path: Path) -> None:
    out, report = run(tmp_path)
    els = by_name(out)
    assert els["Riverfolk"]["x_worldanvil_category"] == "Quay folk"
    assert "x_worldanvil_category" not in els["Ada Quay"] and "x_worldanvil_category" not in els["The ferry crossing"]
    assert report.counts == {"character": 1, "location": 1, "species": 1}  # no element for the category
    assert not any("category" in n for n in report.notes)  # the Codex and the Metadata tab agree


def test_the_category_is_read_from_each_place(tmp_path: Path) -> None:
    """The Metadata tab's Category alone keeps it; the Codex's heading alone keeps it too."""
    no_codex = planted(tmp_path, TWO, ("<h5>Quay folk</h5>", ""), name="no-codex.html")
    out, _ = run(tmp_path, no_codex, name="metadata-only")
    assert by_name(out)["Riverfolk"]["x_worldanvil_category"] == "Quay folk"
    text = TWO.read_text(encoding="utf-8")
    new, n = re.subn(
        r'<div class="row">\s*<div[^>]*>Category</div>\s*<div[^>]*><a[^>]*>Quay folk</a>\s*</div>\s*</div>', "", text
    )
    assert n == 1
    no_meta = tmp_path / "no-meta.html"
    no_meta.write_text(new, encoding="utf-8", newline="")
    out, _ = run(tmp_path, no_meta, name="codex-only")
    assert by_name(out)["Riverfolk"]["x_worldanvil_category"] == "Quay folk"
    renamed = planted(tmp_path, TWO, ("<h5>Quay folk</h5>", "<h5>River folk</h5>"), name="renamed.html")
    _, report = run(tmp_path, renamed, name="renamed")
    assert (
        "article 'Riverfolk': its Metadata tab names the category 'Quay folk', the Codex 'River folk'" in report.notes
    )


def test_unresolved_mentions_stay_as_text(tmp_path: Path) -> None:
    out, report = run(tmp_path)
    els = by_name(out)
    assert els["The ferry crossing"]["description"].endswith("It is kept by @Ada.")
    assert "Its best known keeper is @Ada Quay\n\n" in els["Riverfolk"]["description"]
    assert "x_worldanvil_mentions" not in els["The ferry crossing"]
    assert report.at_mentions == [("The ferry crossing", "@Ada"), ("Riverfolk", "@Ada Quay")]


def test_the_report_names_every_unplaced_item(tmp_path: Path) -> None:
    _, report = run(tmp_path)
    assert {(u.element, u.key): u.kept_as for u in report.unplaced} == {
        ("Ada Quay", "Gender"): "x_worldanvil_gender",
        ("Ada Quay", "Eyes"): "x_worldanvil_eyes",
    }
    text = report.render()
    for needle in (
        "'Ada Quay' / 'Gender': character has no field 'gender'; kept as x_worldanvil_gender",
        "'Ada Quay' / 'Eyes'",
        "'The ferry crossing': '@Ada'",
        "'Riverfolk': '@Ada Quay'",
        f"{DRAFT}: no title",
        "'Ada Quay: Children'",  # the empty template field
        "3 cover images inherited",
        "2 editor anchor(s)",
        "Dates kept on the elements (x_worldanvil_created, x_worldanvil_updated,"
        " x_worldanvil_published): 9 as ISO 8601",
        "Author, named here and never on an element: '[author]' (3 articles)",
        "Views, Favorites, Comments",
        "Wrote ",
    ):
        assert needle in text, needle
    assert "not parsed exactly" not in text
    assert not any(u.key == "unread" for u in report.unplaced)  # nothing in an article read past
    assert not any("outside the articles" in n for n in report.notes)  # nor on the page


@pytest.mark.parametrize("src", [ONE, TWO], ids=["export-1", "export-2"])
def test_folder_lint_is_clean(tmp_path: Path, src: Path) -> None:
    pytest.importorskip("yaml", reason="the dist's lint decodes the schema YAML")
    out, report = run(tmp_path, src)
    r = lint(out)
    assert r.returncode == 0, r.stdout + r.stderr
    assert f"checked {report.total} element files" in r.stdout


@pytest.mark.parametrize("src", [ONE, TWO], ids=["export-1", "export-2"])
def test_deterministic(tmp_path: Path, src: Path) -> None:
    one, _ = run(tmp_path, src, name="one")
    two, _ = run(tmp_path, src, name="two")
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
    report = import_worldanvil(TWO, out, plan_only=True)
    assert not out.exists() and report.out is None and report.total == 3
    assert "Plan only: nothing written." in report.render()


# --- hidden, never dropped (planted: neither real file has it) ---------------


def hidden_lint_ok(out: Path) -> None:
    """The dist's lint: no problem at all, the ``hidden`` mark included (a folder key since
    schema-dist serial 53)."""
    pytest.importorskip("yaml", reason="the dist's lint decodes the schema YAML")
    r = lint(out)
    lines = r.stdout.strip().splitlines()
    problems = [line for line in lines[:-1] if not line.startswith("walk note:")]
    hidden = sum(1 for b in bodies(out).values() if b.get("hidden") is True)
    assert hidden, r.stdout
    assert problems == [], r.stdout + r.stderr
    assert r.returncode == 0, r.stdout + r.stderr


def test_a_private_article_is_hidden_never_dropped(tmp_path: Path) -> None:
    src = planted(tmp_path, TWO, (RIVERFOLK_LINK, RIVERFOLK_LINK.replace("public", "private")))
    out, report = run(tmp_path, src)
    els = by_name(out)
    riverfolk = els["Riverfolk"]
    assert riverfolk["hidden"] is True and list(riverfolk)[:4] == ["type", "id", "name", "hidden"]
    assert riverfolk["description"].startswith("The Riverfolk are the people")  # whole, not cut
    assert riverfolk["x_worldanvil_article_privacy"] == ["private"]
    assert "hidden" not in els["Ada Quay"] and "hidden" not in els["The ferry crossing"]
    assert [(h.name, h.why) for h in report.hidden] == [
        ("Riverfolk", "data-article-privacy 'private' on a link from 'Ada Quay'")
    ]
    assert report.counts == {"character": 1, "location": 1, "species": 1}
    text = report.render()
    assert "Hidden as the source hides it (elements carrying hidden: true): 'Riverfolk' (" in text
    assert "'Ada Quay': visible text mentions the hidden 'Riverfolk' by name" in text
    hidden_lint_ok(out)


def test_visibility_other_than_public_hides(tmp_path: Path) -> None:
    text = ONE.read_text(encoding="utf-8")
    ferry = text.index(f'id="article-{FERRY}"')
    at = text.index("Public", text.index("Visibility</div>", ferry))
    src = tmp_path / "private.html"
    src.write_text(text[:at] + "Private" + text[at + len("Public") :], encoding="utf-8", newline="")
    out, report = run(tmp_path, src)
    ferry_el = by_name(out)["The ferry crossing"]
    assert ferry_el["hidden"] is True and ferry_el["x_worldanvil_visibility"] == "Private"
    assert [(h.name, h.why) for h in report.hidden] == [
        ("The ferry crossing", "Visibility 'Private' on its Metadata tab")
    ]


def test_a_missing_privacy_where_another_place_gives_one_hides(tmp_path: Path) -> None:
    src = planted(tmp_path, TWO, (RIVERFOLK_LINK, f'data-article-id="{RIVERFOLK}"'))
    out, report = run(tmp_path, src)
    riverfolk = by_name(out)["Riverfolk"]
    assert riverfolk["hidden"] is True and riverfolk["x_worldanvil_article_privacy"] == [None]
    assert [h.why for h in report.hidden] == [
        "no data-article-privacy on a link from 'Ada Quay', where another place gives one"
    ]


def test_a_secret_block_is_its_own_hidden_narrative(tmp_path: Path) -> None:
    body = "<p>The ferry crossing is the quay where Ada keeps her flat boat, a day below the falls.</p>"
    secret = '<div class="secret-container"><p>The rope was cut on purpose.</p></div>'
    out, report = run(tmp_path, planted(tmp_path, ONE, (body, body + secret)))
    els = by_name(out)
    narr = els["The ferry crossing: Secret"]
    assert narr["hidden"] is True and narr["type"] == "narrative" and narr["story"] == "The rope was cut on purpose."
    assert narr["locations"] == [eid(FERRY)] and narr["x_worldanvil_parent"] == eid(FERRY)
    assert narr["id"] == str(uuid.uuid5(WORLDANVIL_NAMESPACE, f"worldanvil:{WORLD}:secret:{FERRY}:1"))
    assert "hidden" not in els["The ferry crossing"] and "rope was cut" not in visible(out)
    assert report.secret_blocks == 1 and "1 Secret block in a visible article" in report.render()
    hidden_lint_ok(out)


# --- what the real files do not show (planted) --------------------------------


def test_a_link_to_an_article_not_in_the_export_stays_text(tmp_path: Path) -> None:
    gone = "00000000-0000-4000-8000-000000000000"
    src = planted(tmp_path, TWO, (RIVERFOLK_LINK, RIVERFOLK_LINK.replace(RIVERFOLK, gone)))
    out, report = run(tmp_path, src)
    ada = by_name(out)["Ada Quay"]
    assert ada["description"].endswith("Her people are the Riverfolk .") and "x_worldanvil_mentions" not in ada
    (kept,) = ada["x_worldanvil_unresolved"]
    assert kept["article"] == gone and kept["text"] == "Riverfolk" and kept["template_type"] == "species"
    assert [(u.element, u.where, u.target) for u in report.unresolved] == [("Ada Quay", "link 'Riverfolk'", gone)]


def test_a_template_field_named_like_a_field_fills_it(tmp_path: Path) -> None:
    link = (
        f'<a data-article-privacy="public" data-article-id="{RIVERFOLK}" data-template-type="species"'
        ' class="article-explorer-link" href="/w/x/a/riverfolk-species">Riverfolk</a>'
    )
    sections = "".join(
        f'<div class="visibility-toggler"><div class="section-title"><strong class="section-heading">{h}</strong>'
        f'</div><div class="section-payload">{v}</div></div>'
        for h, v in (("Species", link), ("Height", "170"), ("Weight", "heavy"))
    )
    eyes = '<div class="section-payload">\n            Grey\n        </div>\n    </div>'
    out, report = run(tmp_path, planted(tmp_path, TWO, (eyes, eyes + sections)))
    ada = by_name(out)["Ada Quay"]
    assert ada["species"] == [eid(RIVERFOLK)] and ada["height"] == 170
    assert ada["x_worldanvil_weight"] == "heavy"
    assert ada["x_worldanvil_mentions"] == [eid(RIVERFOLK)]  # from the body's link, not the field's
    why = {u.key: u.why for u in report.unplaced}
    assert why["Weight"] == "the value is not a whole number (weight is an integer)"


def retemplated(tmp: Path, template: str) -> Path:
    """The first export with Riverfolk's Article template renamed."""
    text = ONE.read_text(encoding="utf-8")
    new, n = re.subn(r"(Article template</div>\s*<div[^>]*>\s*)Species", rf"\g<1>{template}", text)
    assert n == 1
    src = tmp / f"{re.sub(r'\W+', '-', template)}.html"
    src.write_text(new, encoding="utf-8", newline="")
    return src


def test_an_unknown_template_is_an_article_narrative_and_named(tmp_path: Path) -> None:
    """Ruled: supertype Article, the template as World Anvil spells it the subtype."""
    out, report = run(tmp_path, retemplated(tmp_path, "Technology"))
    riverfolk = by_name(out)["Riverfolk"]
    assert riverfolk["type"] == "narrative"
    assert (riverfolk["supertype"], riverfolk["subtype"]) == ("Article", "Technology")
    assert riverfolk["x_worldanvil_template"] == "Technology"
    assert ("Technology", "narrative", "untyped") in {(t.template, t.type, t.status) for t in report.templates}
    assert "template 'Technology' (1): narrative; no OnlyWorlds type: Narratives, supertype Article" in report.render()
    assert "worldanvil" not in {b.get("supertype") for b in bodies(out).values()}


@pytest.mark.parametrize(
    ("template", "etype"),
    [("Ethnicity", "species"), ("Myth / Legend", "narrative"), ("Vehicle", "object"), ("Profession", "title")],
)
def test_the_four_added_templates_type(tmp_path: Path, template: str, etype: str) -> None:
    out, report = run(tmp_path, retemplated(tmp_path, template))
    riverfolk = by_name(out)["Riverfolk"]
    assert riverfolk["type"] == etype and riverfolk["x_worldanvil_template"] == template
    assert "supertype" not in riverfolk  # typed, not an Article
    assert (template, etype, "believed") in {(t.template, t.type, t.status) for t in report.templates}


def test_a_date_not_parsed_exactly_is_kept_as_printed_and_named(tmp_path: Path) -> None:
    text = ONE.read_text(encoding="utf-8")
    ferry = text.index(f'id="article-{FERRY}"')
    at = text.index("23 Oct, 2026", text.index("Creation Date</div>", ferry))
    src = tmp_path / "date.html"
    src.write_text(text[:at] + "Spring, 2026" + text[at + len("23 Oct, 2026") :], encoding="utf-8", newline="")
    out, report = run(tmp_path, src)
    ferry_el = by_name(out)["The ferry crossing"]
    assert ferry_el["x_worldanvil_created"] == "Spring, 2026"  # never guessed
    assert ferry_el["x_worldanvil_published"] == "2026-10-23"
    assert report.dates_unparsed == [("The ferry crossing", "Creation Date", "Spring, 2026")]
    assert report.dates == 8
    assert "'The ferry crossing' / 'Creation Date': 'Spring, 2026'" in report.render()


@pytest.mark.parametrize(
    ("printed", "iso"),
    [("23 Oct, 2026", "2026-10-23"), ("3 March, 2025", "2025-03-03"), ("31 Feb, 2026", None), ("Oct 23, 2026", None)],
)
def test_the_date_parse_is_exact(printed: str, iso: str | None) -> None:
    from onlyworlds.worldanvil import _iso_date

    assert _iso_date(printed) == iso


def test_the_author_stays_out_of_the_elements(tmp_path: Path) -> None:
    """Ruled: one username for the whole export, named in the report only."""
    out, report = run(tmp_path)
    assert report.authors == {"[author]": 3}
    assert "[author]" not in json.dumps(bodies(out))
    assert not any("author" in k for b in bodies(out).values() for k in b)


def test_text_no_part_reads_is_kept_and_named(tmp_path: Path) -> None:
    eyes = '<div class="section-payload">\n            Grey\n        </div>\n    </div>'
    stray = '<div class="sidebar-note"><p>Sails at dawn.</p></div>'
    out, report = run(tmp_path, planted(tmp_path, TWO, (eyes, eyes + stray)))
    assert by_name(out)["Ada Quay"]["x_worldanvil_unread"] == "Sails at dawn."
    assert ("Ada Quay", "unread") in {(u.element, u.key) for u in report.unplaced}


EYES = '<div class="section-payload">\n            Grey\n        </div>\n    </div>'
PORTRAIT = (
    '<img class="character-article-portrait  img-fluid img-responsive m-b-20" src="https://cdn.example/{}.png" alt="">'
)


def sections(*pairs: tuple[str, str]) -> str:
    return "".join(
        f'<div class="visibility-toggler"><div class="section-title"><strong class="section-heading">{h}</strong>'
        f'</div><div class="section-payload">{v}</div></div>'
        for h, v in pairs
    )


def test_an_uploaded_portrait_is_the_picture(tmp_path: Path) -> None:
    """The Character template prints an uploaded portrait in the right column."""
    two = PORTRAIT.format("face") + PORTRAIT.format("other")
    out, report = run(tmp_path, planted(tmp_path, TWO, (EYES, EYES + two)))
    ada = by_name(out)["Ada Quay"]
    assert ada["image_url"] == "https://cdn.example/face.png"
    assert ada["x_worldanvil_portrait"] == "https://cdn.example/other.png"
    assert "x_worldanvil_unread_images" not in ada
    assert ("Ada Quay", "portrait") in {(u.element, u.key) for u in report.unplaced}


def test_a_picture_no_part_reads_is_kept_and_named(tmp_path: Path) -> None:
    stray = '<div class="gallery"><img src="https://cdn.example/map.png"><img src="https://cdn.example/map.png"></div>'
    out, report = run(tmp_path, planted(tmp_path, TWO, (EYES, EYES + stray)))
    ada = by_name(out)["Ada Quay"]
    assert ada["x_worldanvil_unread_images"] == ["https://cdn.example/map.png"]
    assert "image_url" not in ada
    assert ("Ada Quay", "unread images") in {(u.element, u.key) for u in report.unplaced}


def test_a_link_field_given_as_a_name_links_the_one_element_named(tmp_path: Path) -> None:
    """A place typed as text, not linked, is the one Location of that name (case aside)."""
    ferry = (
        f'<a data-article-privacy="public" data-article-id="{FERRY}" data-template-type="location"'
        ' class="article-explorer-link" href="/w/x/a/the-ferry-crossing">The ferry crossing</a>'
    )
    fields = sections(("Birthplace", "the Ferry Crossing"), ("Current Location", ferry))
    out, report = run(tmp_path, planted(tmp_path, TWO, (EYES, EYES + fields)))
    ada = by_name(out)["Ada Quay"]
    assert ada["birthplace"] == eid(FERRY) and ada["location"] == eid(FERRY)
    assert report.by_name == [("Ada Quay", "Birthplace", "The ferry crossing")]
    assert "'Ada Quay' / 'Birthplace': 'The ferry crossing'" in report.render()


def test_a_name_that_matches_no_element_of_the_type_stays_kept(tmp_path: Path) -> None:
    fields = sections(("Birthplace", "Riverfolk"), ("Current Location", "Somewhere else"))
    out, report = run(tmp_path, planted(tmp_path, TWO, (EYES, EYES + fields)))
    ada = by_name(out)["Ada Quay"]
    assert "birthplace" not in ada and "location" not in ada
    assert (ada["x_worldanvil_birthplace"], ada["x_worldanvil_current_location"]) == ("Riverfolk", "Somewhere else")
    why = {u.key: u.why for u in report.unplaced}
    assert why["Birthplace"] == "birthplace links a location; the value is text that names none in the folder"
    assert report.by_name == []


def test_an_article_printed_twice_folds(tmp_path: Path) -> None:
    text = ONE.read_text(encoding="utf-8")
    start = text.index(f'<div id="article-{FERRY}"')
    end = text.index('<div id="article-', start + 10)
    src = tmp_path / "twice.html"
    src.write_text(text[:end] + text[start:end] + text[end:], encoding="utf-8", newline="")
    _, report = run(tmp_path, src)
    assert report.counts == {"character": 1, "location": 1, "species": 1}
    assert [(f.element, f.what, f.copies) for f in report.folded] == [("The ferry crossing", "article", 2)]


def test_not_a_world_anvil_export(tmp_path: Path) -> None:
    bad = tmp_path / "bad.html"
    bad.write_text("<html><body><p>hello</p></body></html>", encoding="utf-8")
    with pytest.raises(ValueError, match="not a World Anvil export"):
        import_worldanvil(bad, tmp_path / "x")
    with pytest.raises(FileNotFoundError):
        import_worldanvil(tmp_path / "missing.html", tmp_path / "y")


# --- the command line --------------------------------------------------------


def test_cli(tmp_path: Path) -> None:
    out = tmp_path / "cli"
    buf = io.StringIO()
    with redirect_stdout(buf):
        assert main(["--file", str(TWO), str(out), "--plan"]) == 0
    assert "Plan only" in buf.getvalue() and not out.exists()
    with redirect_stdout(io.StringIO()):
        assert main(["--file", str(TWO), str(out)]) == 0
    assert by_name(out)["Riverfolk"]["x_worldanvil_category"] == "Quay folk"
    err = io.StringIO()
    with redirect_stderr(err):
        assert main(["--file", str(TWO), str(out)]) == 2  # not empty
        assert main(["--file", str(tmp_path / "missing.html"), "--plan"]) == 2
        assert main([str(out)]) == 2  # no --file
        assert main(["--file", str(TWO)]) == 2  # no OUT-DIR, no --plan
    assert "missing.html" in err.getvalue()

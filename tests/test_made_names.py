"""The names the import doors make, told by kind and count.

A made name is an element name that is not one string of the export taken as written. Each door declares the
kinds it makes in ``MADE_NAMES`` (``onlyworlds._made.MadeName``) and its report counts each kind, one line a
kind. These tests hold three things: every declaration is well formed; on every real export the doors' tests
read, every element name is either the export's own text or fits exactly one declared kind of its type, and the
report counts what the names show; and every declared kind is produced by some test's input, its count checked
(the ``made_in`` fixture in ``conftest.py``).

"The export's own text" is the rule of the converter gate that reads these doors from outside: a name is the
export's when, normalised (NFC, runs of whitespace as one space, trimmed, case folded), it is a substring of
everything a name could have come from (the export's raw text, its JSON strings, its HTML with the tags taken
out, its member names); a name that is not, but begins with such text (three characters or more, a trailing
``:,;-`` and dashes cut), is made; one that does neither is invented. The functions below port that rule
(``source_text`` and ``check_names`` in that gate) so these tests and the gate count the same names.
"""

from __future__ import annotations

import contextlib
import copy
import gzip
import html
import io
import json
import re
import unicodedata
import zipfile
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from conftest import MadeCheck

from onlyworlds import ELEMENT_TYPES, campfire, kanka, legendkeeper, notion, read_folder, worldanvil
from onlyworlds._made import ANY_TYPE, MadeName

FIX = Path(__file__).resolve().parent / "fixtures"
LK3 = FIX / "legendkeeper" / "the-quay-world-3.json"
LK = FIX / "legendkeeper" / "the-quay-world.lk"

DOORS: dict[str, ModuleType] = {
    "legendkeeper": legendkeeper,
    "kanka": kanka,
    "worldanvil": worldanvil,
    "notion": notion,
    "campfire": campfire,
}


def convert(door: str, export: Path, out: Path) -> Any:
    if door == "legendkeeper":
        return legendkeeper.import_legendkeeper(export, out_dir=out)
    if door == "kanka":
        return kanka.import_kanka(export, out)
    if door == "worldanvil":
        return worldanvil.import_worldanvil(export, out)
    if door == "notion":
        return notion.import_notion(export, out)
    return campfire.import_campfire(export, out)


# --- the declarations ------------------------------------------------------------------------------------


@pytest.mark.parametrize("door", DOORS)
def test_each_door_declares_the_names_it_makes(door: str) -> None:
    mod = DOORS[door]
    assert "MADE_NAMES" in mod.__all__ and "MadeName" in mod.__all__ and mod.MadeName is MadeName
    made = mod.MADE_NAMES
    assert isinstance(made, tuple) and all(isinstance(m, MadeName) for m in made)
    kinds = [m.kind for m in made]
    assert len(set(kinds)) == len(kinds), "a kind is declared once"
    for m in made:
        assert re.fullmatch(r"[a-z]+(?:-[a-z]+)*", m.kind), m.kind
        assert m.type == ANY_TYPE or m.type in ELEMENT_TYPES, m.type
        assert m.source in ("joined", "ours") and m.pattern.strip() == m.pattern != ""
        re.compile(m.regex)
        assert not m.regex.startswith("^") and not m.regex.endswith("$"), "fits() matches the whole name"
        if m.source == "joined":
            assert ".+" in m.regex, "a joined name carries the export's words"


def test_notion_makes_no_name() -> None:
    assert notion.MADE_NAMES == ()


def test_fits_reads_the_type_and_the_whole_name() -> None:
    corner = next(m for m in legendkeeper.MADE_NAMES if m.kind == "frame-corner")
    assert corner.fits("marker", "Welcome: corner 1")
    assert not corner.fits("zone", "Welcome: corner 1") and not corner.fits("marker", "Welcome: corner 12")
    untitled = next(m for m in kanka.MADE_NAMES if m.kind == "untitled-entity")
    assert untitled.type == ANY_TYPE and untitled.fits("location", "Untitled (12)")
    assert not untitled.fits("location", "Untitled (12) again")


# --- the gate's rule, ported -------------------------------------------------------------------------------


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", s)).strip().casefold()


def _members(path: Path) -> list[tuple[str, bytes]]:
    b = path.read_bytes()
    if b[:2] == b"PK":
        z = zipfile.ZipFile(io.BytesIO(b))
        return [(n, z.read(n)) for n in z.namelist() if not n.endswith("/")]
    if b[:2] == b"\x1f\x8b":
        return [("body", gzip.decompress(b))]
    return [("body", b)]


def source_text(path: Path) -> str:
    """Everything a name could have come from, normalised (the gate's ``source_text``)."""
    out: list[str] = []

    def walk(o: Any) -> None:
        if isinstance(o, dict):
            for k, v in o.items():
                out.append(str(k))
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
        elif isinstance(o, str):
            out.append(o)
            out.append(html.unescape(re.sub(r"<[^>]+>", " ", o)))

    for name, b in _members(path):
        out.append(name)
        if b[:4] in (b"\x89PNG", b"\xff\xd8\xff\xe0") or b"\x00" in b[:200]:
            continue
        t = b.decode("utf-8", "replace")
        out.append(t)
        out.append(html.unescape(re.sub(r"<[^>]+>", " ", t)))
        with contextlib.suppress(ValueError):
            walk(json.loads(t))
    return _norm("\n".join(out))


#: What a name's first words lose before they are looked up: punctuation, dashes (en, em) and spaces.
_CUT = ":,;-" + chr(0x2013) + chr(0x2014) + " "


def name_reads(name: str, src: str) -> str:
    """``export`` (the export's own text), ``made`` (begins with it) or ``invented`` (the gate's ``check_names``)."""
    n = _norm(name)
    if not n:
        return "invented"
    if n in src:
        return "export"
    words = n.split(" ")
    starts = (" ".join(words[:k]).rstrip(_CUT) for k in range(len(words) - 1, 0, -1))
    return "made" if any(len(c) >= 3 and c in src for c in starts) else "invented"


# --- every name on every real export --------------------------------------------------------------------

#: Every real export the doors' tests read, and the names each makes by kind (the outside gate's counts on
#: the same exports: LegendKeeper 80 of 280, 78 on the .lk; Kanka 2; World Anvil, Notion, Campfire none).
REAL: list[tuple[str, Path, dict[str, int]]] = [
    ("legendkeeper", LK3, {"page-document": 17, "map-document": 6, "untitled-pin": 1, "frame-corner": 56}),
    ("legendkeeper", LK, {"page-document": 17, "map-document": 5, "frame-corner": 56}),
    *(
        ("kanka", FIX / "kanka" / f"quay-export-world_{stamp}.zip", {"hidden-details": 2})
        for stamp in ("20261023_074706", "20261024_180340", "20261025_011029")
    ),
    *(("worldanvil", p, {}) for p in sorted((FIX / "worldanvil").glob("*.html"))),
    *(("notion", p, {}) for p in sorted((FIX / "notion").glob("*.zip"))),
    ("campfire", FIX / "campfire" / "campfire-export.html", {}),
]


def test_the_list_holds_every_real_export_in_the_fixtures() -> None:
    held = {p for _, p, _ in REAL}
    real = {p for d in DOORS for p in (FIX / d).iterdir() if p.suffix in (".json", ".lk", ".zip", ".html")}
    # LegendKeeper's other files are answers of its API, recorded, not exports; a fixture made by hand from a
    # real export (its name ends in -made, as kanka-4-made.zip) is not an export either
    real = {p for p in real if (p.parent.name != "legendkeeper" or p in (LK3, LK)) and not p.stem.endswith("-made")}
    assert held == real


@pytest.mark.parametrize(("door", "export", "kinds"), REAL, ids=[f"{d}-{p.name}" for d, p, _ in REAL])
def test_every_name_on_a_real_export_is_its_text_or_a_declared_made_name(
    door: str, export: Path, kinds: dict[str, int], tmp_path: Path, made_in: MadeCheck
) -> None:
    out = tmp_path / "w"
    report = convert(door, export, out)
    declared: tuple[MadeName, ...] = DOORS[door].MADE_NAMES
    src = source_text(export)
    bodies = [e.body for e in read_folder(out).elements.values()]
    reads = {b["id"]: name_reads(str(b["name"]), src) for b in bodies}
    assert [b["name"] for b in bodies if reads[b["id"]] == "invented"] == []
    made = [b for b in bodies if reads[b["id"]] == "made"]
    for b in made:
        fits = [m.kind for m in declared if m.fits(b["type"], b["name"])]
        assert len(fits) == 1, (b["type"], b["name"], fits)
    by_gate: dict[str, int] = {}
    for b in made:
        (kind,) = (m.kind for m in declared if m.fits(b["type"], b["name"]))
        by_gate[kind] = by_gate.get(kind, 0) + 1
    assert by_gate == kinds == report.made_names  # the gate's made names, by kind, are what the report counts
    assert sum(report.made_names.values()) == len(made)
    seen = made_in(declared, report.made_names, out)
    assert {k: n for k, n in seen.items() if n} == kinds
    text = report.render()
    for m in declared:
        if m.kind in kinds:
            what = "any type" if m.type == ANY_TYPE else m.type
            assert f"  - {m.kind}, {what} {m.pattern!r}: {kinds[m.kind]} (" in text
    head = "Names made by the import, not taken whole from the export"
    assert (head in text) == bool(kinds)


# --- what the real files do not show: LegendKeeper's file road, planted ---------------------------------


def _resource(data: dict[str, Any], rid: str) -> dict[str, Any]:
    (r,) = (r for r in data["resources"] if r["id"] == rid)
    found: dict[str, Any] = r
    return found


def _doc(data: dict[str, Any], rid: str, did: str) -> dict[str, Any]:
    (d,) = (d for d in _resource(data, rid)["documents"] if d["id"] == did)
    found: dict[str, Any] = d
    return found


def _shapes(board: dict[str, Any], kind: str) -> list[dict[str, Any]]:
    return [r["val"] for r in board["content"]["shapesV2"] if r["val"].get("type") == kind]


def test_legendkeeper_names_what_has_no_name(tmp_path: Path, made_in: MadeCheck) -> None:
    """In the third export: a page, a lane, an event, a calendar and a frame with their names taken out,
    and a page card whose page is not in the project."""
    data: dict[str, Any] = json.loads(LK3.read_text(encoding="utf-8"))
    _resource(data, "emh9oo8o")["name"] = ""  # Artifact
    timeline = _doc(data, "qoi1yh5t", "syogd8g0")["content"]  # Temple of Time: History
    timeline["lanes"][0]["name"] = ""
    timeline["events"][0]["name"] = ""  # and no formattedStart
    calendars = json.loads((FIX / "legendkeeper" / "api-calendars.json").read_text(encoding="utf-8"))
    preset = copy.deepcopy(calendars["answer"]["data"][0])
    preset.update(id="fhynh6n4", name="")  # the calendar the timeline names, which the export lacks
    data["calendars"] = [preset]
    board = _doc(data, "lz0baol5", "cgljslnc")  # Board Bastion: Main
    _shapes(board, "frame")[0]["props"]["name"] = ""
    _shapes(board, "element")[0]["props"]["resourceId"] = "notinit1"
    path = tmp_path / "planted.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    report = legendkeeper.import_legendkeeper(path, out_dir=tmp_path / "w")
    seen = made_in(legendkeeper.MADE_NAMES, report.made_names, tmp_path / "w")
    assert seen["untitled-resource"] == 1
    assert seen["untitled-lane"] == 1
    assert seen["untitled-event"] == 1
    assert seen["untitled-calendar"] == 1
    assert seen["untitled-frame"] == 1
    assert seen["untitled-card"] == 1
    names = {e.body["name"] for e in read_folder(tmp_path / "w").elements.values()}
    assert {"Untitled (emh9oo8o)", "Lane (k5oq5moq)", "Untitled event", "Calendar (fhynh6n4)", "Frame"} <= names
    assert "  - untitled-lane, narrative 'Lane (<lane id>)': 1 (ours: the export gives it no name)" in (
        report.render().splitlines()
    )


# --- every declared kind is witnessed -------------------------------------------------------------------


def test_every_declared_kind_is_counted_by_a_test() -> None:
    """Each kind a door declares is named in a test that checks its count with ``made_in`` (this file's
    real exports and planted names, and each door's own test file)."""
    here = Path(__file__).resolve().parent
    texts = [p.read_text(encoding="utf-8") for p in sorted(here.glob("test_*.py"))]
    checked = [t for t in texts if "made_in(" in t]
    missing = [
        f"{door} {m.kind}"
        for door, mod in DOORS.items()
        for m in mod.MADE_NAMES
        if not any(f'"{m.kind}"' in t for t in checked)
    ]
    assert missing == []

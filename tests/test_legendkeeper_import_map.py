"""The import map (schema-dist ``profiles/import-map.md``, serial 67) in the LegendKeeper door.

The vendored table (``_walk/import-map.json``, copied byte-exact by the codegen) types a resource
by LegendKeeper's common tags (``city``, ``organization``) only on the user's yes. The profile's
fixture (27 cases) runs whole through the door's own typing function. The door-level tests read
``the-quay-world-3.json``, the tutorial export: 43 resources, of which the table types two (Wiki
City by ``city``, Drag and Drop Den by ``point of interest``); its other table words sit on
templates, which the table never types.
"""

from __future__ import annotations

import builtins
import copy
import io
import json
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any

import pytest

from onlyworlds import legendkeeper as lk
from onlyworlds import read_folder
from onlyworlds.legendkeeper import (
    ImportReport,
    RecordedSource,
    _load_import_map,
    _read_import_map,
    _type_resource,
    import_legendkeeper,
    main,
)

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "codegen" / "schema-dist" / "profiles"
EXPORT = Path(__file__).resolve().parent / "fixtures" / "legendkeeper" / "the-quay-world-3.json"
WIKI_CITY, DEN, ARTIFACT, PENINSULA = "oqwc8iom", "x5q2yh4k", "emh9oo8o", "ohv2wd82"


def table_file() -> dict[str, Any]:
    value: dict[str, Any] = json.loads((DIST / "import-map.json").read_text(encoding="utf-8"))
    return value


def fixture() -> dict[str, Any]:
    value: dict[str, Any] = json.loads((DIST / "import-map.fixture.json").read_text(encoding="utf-8"))
    return value


# --- the profile's fixture, whole ------------------------------------------------------------------


def test_the_fixture_runs_whole_through_the_doors_typing() -> None:
    cases = fixture()["cases"]
    assert len(cases) == 27
    got = []
    for c in cases:
        table = _read_import_map(c["file"] if "file" in c else table_file(), c["source"])
        t = _type_resource(c["tags"], c.get("map") or {}, table, template=bool(c.get("template")))
        got.append((c["name"], t.type, t.why, list(t.offered)))
    assert got == [(c["name"], c["type"], c["why"], c["offered"]) for c in cases]


def test_the_vendored_table_is_the_dists() -> None:
    assert (Path(lk.__file__).parent / "_walk" / "import-map.json").read_bytes() == (
        DIST / "import-map.json"
    ).read_bytes()
    table = _load_import_map()
    assert table is not None and table.source == "LegendKeeper" and table.ruled == "2026-10-25"
    assert table.types["city"] == "location" and "guide" in table.no_type and len(table.types) == 11


# --- the reader's refusals and what it ignores -------------------------------------------------------


def with_entry(**entry: Any) -> dict[str, Any]:
    value = table_file()
    value["sources"]["legendkeeper"].update(entry)
    return value


def test_what_a_reader_refuses() -> None:
    good = table_file()
    assert _read_import_map(good) is not None
    refused: list[Any] = [
        [],
        "{}",
        {**good, "version": True},
        {**good, "version": 2},
        {**good, "version": "1"},
        {**good, "sources": []},
        {**good, "sources": {"legendkeeper": ["city"]}},
        with_entry(matches="title"),
        with_entry(matches=None),
    ]
    for bad in refused:
        assert _read_import_map(bad) is None, bad
    assert _read_import_map(good, "kanka") is None  # another source's entry is not this door's


def test_what_a_reader_ignores() -> None:
    value = with_entry(
        types={"city": "location", "harbour": "port", "fort": "Location", "mine": 3},
        no_type=["guide", 7, None],
        extra={"anything": True},
    )
    value["unknown"] = [1, 2]
    value["sources"]["kanka"] = "not an object"
    table = _read_import_map(value)
    assert table is not None
    assert dict(table.types) == {"city": "location"}  # not a slug as the schema spells it: no row
    assert table.no_type == frozenset({"guide"})
    table = _read_import_map(with_entry(types=["city"], no_type="guide"))
    assert table is not None and dict(table.types) == {} and table.no_type == frozenset()


# --- the door: offered, applied only on a yes ---------------------------------------------------


def plan(**kw: Any) -> ImportReport:
    return import_legendkeeper(EXPORT, plan_only=True, **kw)


def typed(report: ImportReport) -> dict[str, tuple[str, str]]:
    return {t.resource: (t.type, t.by) for t in report.typed}


def test_offered_and_not_applied_without_a_yes() -> None:
    report = plan()
    offer = report.import_map
    assert offer is not None and not offer.applied
    assert offer.rows == [("city", "location", 1), ("point of interest", "location", 1)] and offer.would_type == 2
    assert typed(report)[WIKI_CITY] == ("narrative", "untyped") and report.counts["location"] == 1
    text = report.render()
    assert (
        "Import map (LegendKeeper's common tags to the 22 types, ruled 2026-10-25): it would type 2 resources:"
        " city → location (1), point of interest → location (1)."
    ) in text
    assert "Not applied (it never types anything without a yes): --import-map applies it for a run." in text
    assert "'guide' 3" in text  # declined: as if the file were not there, its no_type words listed too


def test_applied_on_a_yes(tmp_path: Path) -> None:
    report = import_legendkeeper(EXPORT, out_dir=tmp_path / "w", import_map=True)
    assert report.import_map is not None and report.import_map.applied
    got = typed(report)
    assert got[WIKI_CITY] == ("location", "import map: city=location")
    assert got[DEN] == ("location", "import map: point of interest=location")
    assert report.counts["location"] == 3
    text = report.render()
    assert "location 3: import map: city=location 1, import map: point of interest=location 1, tag 'location' 1" in text
    assert "Applied on your yes" in text
    assert "'guide'" not in text.split("Tags on the untyped resources")[1].split("\n")[0]  # no_type words not offered
    # the writer rule: the resource's own tags stay, never a type name the table invented
    wiki = next(
        e.body for e in read_folder(tmp_path / "w").elements.values() if e.body.get("x_legendkeeper_id") == WIKI_CITY
    )
    assert wiki["type"] == "location" and wiki["x_legendkeeper_tags"] == ["city", "guide"]


def test_a_template_is_out_of_the_tables_reach() -> None:
    report = plan(import_map=True)
    assert typed(report)[ARTIFACT] == ("narrative", "untyped")  # tagged artifact and item, in templates
    assert "'artifact' 1" in report.render()  # still offered: a map the user types reaches a template
    report = plan(import_map=True, type_map={"artifact": "object"})
    assert typed(report)[ARTIFACT] == ("object", "--map artifact=object")


def test_the_users_map_wins_over_the_table() -> None:
    report = plan(import_map=True, type_map={"City": "zone"})
    assert typed(report)[WIKI_CITY] == ("zone", "--map city=zone")
    assert typed(report)[DEN] == ("location", "import map: point of interest=location")


def test_no_type_words_alone_leave_the_resource_untyped() -> None:
    assert typed(plan(import_map=True))[PENINSULA] == ("narrative", "untyped")  # guide, tips, tutorial


def project(tags: dict[str, list[str]]) -> RecordedSource:
    """A made-up project: one resource per name, with its tags and no documents."""
    rows = [
        {"id": f"r{i}", "name": n, "parentId": None, "tags": t, "documents": []}
        for i, (n, t) in enumerate(tags.items())
    ]
    answers: dict[str, Any] = {
        "/projects/p0": {"id": "p0", "name": "P"},
        "/projects/p0/resources": {"data": rows, "hasMore": False, "nextCursor": None},
        "/projects/p0/calendars": {"data": [], "hasMore": False, "nextCursor": None},
    }
    for r in rows:
        answers[f"/projects/p0/resources/{r['id']}"] = {**copy.deepcopy(r), "properties": []}
    return RecordedSource(answers)


def test_two_types_are_ambiguous_and_the_report_names_both() -> None:
    src = project({"Port Veyra": ["city", "organization"], "The Saga": ["myth", "event"], "Harbour": ["city"]})
    report = import_legendkeeper(src, "p0", plan_only=True, import_map=True)
    got = typed(report)
    assert got["r0"] == ("narrative", "ambiguous: its tags name institution and location")
    assert got["r1"] == ("narrative", "ambiguous: its tags name event and narrative")
    assert got["r2"] == ("location", "import map: city=location")
    text = report.render()
    assert "'Port Veyra' kept untyped: ambiguous: its tags name institution and location" in text
    # the offer says the table would unsettle The Saga, an Event by its tag without it
    offer = report.import_map
    assert offer is not None and offer.unsettled == ["The Saga"] and offer.would_type == 1
    assert "It would leave 1 typed without it ambiguous: 'The Saga'." in offer.said()
    assert (
        typed(import_legendkeeper(project({"The Saga": ["myth", "event"]}), "p0", plan_only=True))["r0"][0] == "event"
    )


def test_nothing_to_offer_is_no_offer() -> None:
    report = import_legendkeeper(project({"Ada": ["character"], "Note": ["harbour"]}), "p0", plan_only=True)
    assert report.import_map is None and "Import map" not in report.render()


# --- the command line ----------------------------------------------------------------------------


def cli(argv: list[str]) -> tuple[int, str]:
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = main(argv)
    return rc, out.getvalue() + err.getvalue()


def no_input(prompt: str = "") -> str:
    raise AssertionError(f"asked when it must not ask: {prompt!r}")


def test_cli_without_a_terminal_offers_and_does_not_apply(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lk, "_interactive", lambda: False)
    monkeypatch.setattr(builtins, "input", no_input)
    rc, text = cli(["--file", str(EXPORT), str(tmp_path / "w")])
    assert rc == 0 and "Not applied" in text and "import map: city=location" not in text


def test_cli_flag_applies(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lk, "_interactive", lambda: True)
    monkeypatch.setattr(builtins, "input", no_input)  # the flag is the yes: no question
    rc, text = cli(["--file", str(EXPORT), str(tmp_path / "w"), "--import-map"])
    assert rc == 0 and "import map: city=location 1" in text and "Applied on your yes" in text


@pytest.mark.parametrize(
    ("answer", "applied"), [("y", True), (" YES ", True), ("", False), ("n", False), ("sure", False)]
)
def test_cli_at_a_terminal_asks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, answer: str, applied: bool) -> None:
    asked: list[str] = []

    def reply(prompt: str = "") -> str:
        asked.append(prompt)
        return answer

    monkeypatch.setattr(lk, "_interactive", lambda: True)
    monkeypatch.setattr(builtins, "input", reply)
    rc, text = cli(["--file", str(EXPORT), str(tmp_path / "w")])
    assert rc == 0 and asked == ["Apply the import map to this import? [y/N] "]
    assert text.startswith("Import map (LegendKeeper's common tags")  # the offer, printed before the question
    assert ("import map: city=location 1" in text) is applied


def test_cli_plan_at_a_terminal_prints_the_offer_and_never_asks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lk, "_interactive", lambda: True)
    monkeypatch.setattr(builtins, "input", no_input)
    rc, text = cli(["--file", str(EXPORT), "--plan"])
    assert rc == 0 and "it would type 2 resources" in text and "Not applied" in text


def test_cli_answer_at_end_of_input_is_no(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def eof(prompt: str = "") -> str:
        raise EOFError

    monkeypatch.setattr(lk, "_interactive", lambda: True)
    monkeypatch.setattr(builtins, "input", eof)
    rc, text = cli(["--file", str(EXPORT), str(tmp_path / "w")])
    assert rc == 0 and "Not applied" in text

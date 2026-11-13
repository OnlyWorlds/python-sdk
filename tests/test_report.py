"""The report profile's rule 9 (schema-dist ``profiles/report.md``, serial 120): every thread case in
``codegen/schema-dist/profiles/report.fixture.json``, vendored with the distribution, replayed through
``report_threads_of``; then the edges the fixture leaves out."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from onlyworlds import ROOM_PAIRS, ReportThreads, report_threads_of
from onlyworlds._schema import ROOM_MARK

REPO = Path(__file__).resolve().parent.parent
FIXTURE = REPO / "codegen" / "schema-dist" / "profiles" / "report.fixture.json"
THREAD_CASES = 29
WORLD = "019a7120-0000-7000-8000-000000000000"


def load_fixture() -> dict[str, Any]:
    assert FIXTURE.is_file(), f"no report fixture at {FIXTURE}"
    doc: dict[str, Any] = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert doc["profile"] == "report"
    return doc


def as_set(rows: list[Any]) -> list[str]:
    # The profile rules the order inside a group and none between groups: groups and lints compare as sets.
    return sorted(json.dumps(row, sort_keys=True) for row in rows)


def replay(case: dict[str, Any]) -> list[str]:
    """What the package answers that the case does not, as one line each (empty: the case passes)."""
    name = case.get("name", "<a case with no name>")
    narratives, want = case.get("narratives"), case.get("want")
    if not isinstance(narratives, list) or not isinstance(want, dict):
        return [f"{name}: the test cannot read it (no narratives list or no want); keys {sorted(case)}"]
    got = report_threads_of(narratives)
    wrong: list[str] = []
    if list(got["parents"].items()) != list(want["parents"].items()):
        wrong.append(f"{name}: parents gave {got['parents']!r}, the fixture says {want['parents']!r}")
    if as_set(list(got["groups"])) != as_set(want["groups"]):
        wrong.append(f"{name}: groups gave {got['groups']!r}, the fixture says {want['groups']!r}")
    if as_set(list(got["lints"])) != as_set(want["lints"]):
        wrong.append(f"{name}: lints gave {got['lints']!r}, the fixture says {want['lints']!r}")
    return wrong


def test_the_fixture_names_the_pairs_and_mark_the_package_reads() -> None:
    doc = load_fixture()
    assert (doc["pair"]["type"], doc["pair"]["supertype"]) in ROOM_PAIRS
    assert (doc["board_pair"]["type"], doc["board_pair"]["supertype"]) in ROOM_PAIRS
    assert doc["mark"]["field"] == ROOM_MARK


def test_every_thread_case_replays() -> None:
    cases = load_fixture()["thread_cases"]
    assert len(cases) == THREAD_CASES, f"{len(cases)} thread cases; this test was written for {THREAD_CASES}"
    names = [c.get("name") for c in cases]
    assert len(set(names)) == len(names), "two thread cases share a name"
    wrong = [line for case in cases for line in replay(case)]
    assert not wrong, "\n".join(wrong)


def thread_cases() -> list[Any]:
    # Collected by name; with no fixture, test_every_thread_case_replays says so.
    return list(load_fixture()["thread_cases"]) if FIXTURE.is_file() else []


@pytest.mark.parametrize("case", thread_cases(), ids=lambda c: str(c.get("name")))
def test_thread_case(case: dict[str, Any]) -> None:
    wrong = replay(case)
    assert not wrong, "\n".join(wrong)


def report(rid: Any, parent: Any = None, created_at: str | None = None, **more: Any) -> dict[str, Any]:
    body: dict[str, Any] = {"type": "narrative", "supertype": "Report", ROOM_MARK: WORLD, "parent_narrative": parent}
    if rid is not None:
        body["id"] = rid
    if created_at is not None:
        body["created_at"] = created_at
    return body | more


def board(bid: str) -> dict[str, Any]:
    return {"id": bid, "type": "narrative", "supertype": "Board", ROOM_MARK: WORLD}


def test_a_non_mapping_in_the_list_is_passed_over() -> None:
    got = report_threads_of(
        [None, 7, "r1", ["r1"], report("r1"), report("r2", "r1")]  # type: ignore[list-item]
    )
    want: ReportThreads = {
        "parents": {"r1": "none", "r2": "report"},
        "groups": [{"parent": "r1", "kind": "report", "reports": ["r2"]}],
        "lints": [],
    }
    assert got == want


def test_an_element_with_no_id_or_an_empty_one_is_passed_over() -> None:
    """No id, or one that is not a non-empty string: the element is no report and no parent."""
    got = report_threads_of([report(None, "r1"), report(5, "r1"), report("", "r1"), report("r1")])
    want: ReportThreads = {"parents": {"r1": "none"}, "groups": [], "lints": []}
    assert got == want
    # An empty id is no parent either: a report naming "" names none.
    assert report_threads_of([report(""), report("r2", "")])["parents"] == {"r2": "none"}


def test_the_first_of_two_with_one_id_counts() -> None:
    got = report_threads_of([report("r1"), {"id": "r1", "type": "narrative"}, report("r2", "r1")])
    assert got["parents"] == {"r1": "none", "r2": "report"}
    assert got["groups"] == [{"parent": "r1", "kind": "report", "reports": ["r2"]}]


def test_a_known_of_stub_is_read_as_served() -> None:
    """A stub served without the pair and the mark is neither a report nor a board entry: as a parent it reads
    other, and the report under it is a thread of one."""
    stub = {"id": "r1", "type": "narrative", "name": "A report", "known_of": True}
    got = report_threads_of([stub, report("r2", "r1")])
    want: ReportThreads = {"parents": {"r2": "other"}, "groups": [], "lints": []}
    assert got == want
    board_stub = {"id": "b1", "type": "narrative", "supertype": "Board", "known_of": True}
    assert report_threads_of([board_stub, report("r3", "b1")])["parents"] == {"r3": "other"}
    # Served with the pair and the mark, a stub is a report: none in parents (no parent served), report as a parent.
    marked = report_threads_of([report("r1", known_of=True), report("r2", "r1")])
    assert marked["parents"] == {"r1": "none", "r2": "report"}
    assert marked["groups"] == [{"parent": "r1", "kind": "report", "reports": ["r2"]}]


@pytest.mark.parametrize("parent", [42, {"id": "r1"}, ["r1"], True])
def test_a_parent_that_is_not_a_string_reads_as_none(parent: Any) -> None:
    got = report_threads_of([report("r1"), report("r2", parent)])
    want: ReportThreads = {"parents": {"r1": "none", "r2": "none"}, "groups": [], "lints": []}
    assert got == want


@pytest.mark.parametrize("parent", ["", "   ", "\t\n", chr(0x00A0) + chr(0x3000)])
def test_a_parent_blank_once_trimmed_reads_as_none(parent: str) -> None:
    got = report_threads_of([report("r1"), report("r2", parent)])
    assert got["parents"] == {"r1": "none", "r2": "none"}


def test_a_parent_with_content_is_read_as_written_never_trimmed() -> None:
    got = report_threads_of([report("r1"), report("r2", " r1 "), report("r3", "r1\n")])
    assert got["parents"] == {"r1": "none", "r2": "missing", "r3": "missing"}
    assert got["groups"] == []


def test_only_reports_are_grouped() -> None:
    """A message, a board entry or lore naming a report is in no part of the answer."""
    message = {"id": "m1", "type": "narrative", "supertype": "Message", ROOM_MARK: WORLD, "parent_narrative": "r1"}
    entry = board("b1") | {"parent_narrative": "r1"}
    lore = {"id": "l1", "type": "narrative", "supertype": "Chapter", "parent_narrative": "r1"}
    got = report_threads_of([report("r1"), message, entry, lore])
    want: ReportThreads = {"parents": {"r1": "none"}, "groups": [], "lints": []}
    assert got == want


def test_a_report_without_the_mark_or_with_another_pair_is_no_report() -> None:
    lore = report("r1")
    del lore[ROOM_MARK]
    blank = report("r2", **{ROOM_MARK: "  "})
    plural = report("r3", supertype="Reports")
    # Trimmed by White_Space (a no-break space, an em space) and folded: still the pair.
    folded = report("r4", type=" NARRATIVE ", supertype=chr(0x00A0) + "report" + chr(0x2003))
    got = report_threads_of([lore, blank, plural, folded])
    assert got["parents"] == {"r4": "none"}


def test_no_chain_through_a_parent_that_names_itself() -> None:
    """A report that names itself reads as naming no parent: it reads ``self`` with its lint and still heads the
    group of the reports that name it, and those carry no chain lint."""
    got = report_threads_of([report("b", "b"), report("c", "b")])
    want: ReportThreads = {
        "parents": {"b": "self", "c": "report"},
        "groups": [{"parent": "b", "kind": "report", "reports": ["c"]}],
        "lints": [{"kind": "self", "report": "b"}],
    }
    assert got == want


def test_a_chain_is_a_parent_report_whose_own_parent_is_another_report() -> None:
    chain = report_threads_of([report("a"), report("b", "a"), report("c", "b")])
    assert chain["lints"] == [{"kind": "chain", "report": "c"}]
    assert chain["groups"] == [
        {"parent": "a", "kind": "report", "reports": ["b"]},
        {"parent": "b", "kind": "report", "reports": ["c"]},
    ]


@pytest.mark.parametrize(
    ("above", "reads"),
    [
        ([], "missing"),
        ([{"id": "a", "type": "narrative", "supertype": "Chapter"}], "other"),
        ([{"id": "a", "type": "narrative", "supertype": "Report"}], "other"),
        ([board("a")], "board"),
    ],
    ids=["unheld", "lore", "a-report-without-the-mark", "board"],
)
def test_no_chain_when_the_parent_reports_own_parent_is_no_report(above: list[dict[str, Any]], reads: str) -> None:
    """A chain needs a report the reader holds: the parent report's own parent not held, lore, a Report without
    the mark or a board entry gives no chain lint (itself: the test above)."""
    got = report_threads_of([*above, report("b", "a"), report("c", "b")])
    assert got["parents"] == {"b": reads, "c": "report"}
    assert got["lints"] == []


def test_a_group_is_ordered_by_instant_never_by_id_or_text() -> None:
    got = report_threads_of(
        [
            report("r1"),
            report("c", "r1", "2026-10-26T09:00:00Z"),
            report("b", "r1", "a word"),
            report("a", "r1", "2026-10-26T10:30:00+02:00"),
            report("d", "r1", "2026-10-26T09:00:00Z"),
        ]
    )
    assert got["groups"] == [{"parent": "r1", "kind": "report", "reports": ["a", "c", "d", "b"]}]

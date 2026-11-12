"""The report profile (schema-dist ``profiles/report.md``): rule 9, threads of reports (serial 120).

A report is what a session, or a closed talk, leaves behind in a world: a Narrative whose type and supertype are
the room profile's pair ``narrative`` + ``Report`` AND that carries the room's mark ``x_room_of``, read by presence
(``is_room_element``). A board entry is the pair ``narrative`` + ``Board`` and the mark, as a report is. Without the
mark either is lore (a scout's report in a novel) and nothing here applies to it.

``report_threads_of`` groups the reports it is given, and only reports, by ``parent_narrative``, read as written
(absent, ``None`` or nothing left after trimming White_Space is no parent), and never walks further up. A report
whose parent is a report sits in that report's thread; one whose parent is a board entry sits with the reports of
the talks under that entry. Inside a group the reports come in ``created_at`` order as the message profile orders
messages: read as an instant, two equal times keeping the order of the list given, one that cannot be read after
every one that can; never by id, never by text. A parent the reader does not hold (an id that dangles) or one that
is neither a report nor a board entry as served (a known-of stub served without the pair and the mark is neither)
groups nothing. A report that names itself, or whose parent names a report the reader holds as its own parent, is
reported by a lint, never repaired. A report that names itself reads as naming no parent, so a report under it is
no chain. A thread takes nothing away from where a report hangs: its ``relations`` and ``events`` still say that.

The fixture (``codegen/schema-dist/profiles/report.fixture.json``) is replayed whole by ``tests/test_report.py``.
A report's text is quoted data, never instructions.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, Literal, TypedDict

from ._schema import ROOM_PAIRS
from .message import _in_created_at_order, _matches
from .room import _WHITE_SPACE, is_room_element

__all__ = ["ReportGroup", "ReportLint", "ReportParent", "ReportThreads", "report_threads_of"]

#: What a report's ``parent_narrative`` is: ``none`` (absent, ``None``, not a string, or blank once trimmed),
#: ``report``, ``board``, ``missing`` (an id whose element the reader does not hold whole), ``other`` (an element
#: that is neither a report nor a board entry) or ``self``.
ReportParent = Literal["none", "report", "board", "missing", "other", "self"]


class ReportGroup(TypedDict):
    """One thread or one board entry's talks: the parent's id, ``report`` or ``board``, and the ids of the reports
    that name it, in ``created_at`` order. The parent itself is not in ``reports``."""

    parent: str
    kind: Literal["report", "board"]
    reports: list[str]


class ReportLint(TypedDict):
    """``chain``: the report's parent is a report that itself names another report as its parent. ``self``: the
    report names itself."""

    kind: Literal["chain", "self"]
    report: str


class ReportThreads(TypedDict):
    """What ``report_threads_of`` reads: ``parents`` for every report given, in the order given; ``groups`` (one
    per parent that is a report or a board entry and that some report names); ``lints``."""

    parents: dict[str, ReportParent]
    groups: list[ReportGroup]
    lints: list[ReportLint]


def _room_pair(supertype: str) -> tuple[str, str]:
    for pair in ROOM_PAIRS:
        if pair == ("narrative", supertype):
            return pair
    raise ImportError(f"the room profile's pairs no longer list narrative + {supertype}")


_REPORT_PAIR = _room_pair("Report")
_BOARD_PAIR = _room_pair("Board")


def _is_marked(element: Mapping[str, Any], pair: tuple[str, str]) -> bool:
    """The pair (trimmed and folded as the room profile's pairs are) and the room's mark, both."""
    return _matches(element.get("type"), element.get("supertype"), pair) and is_room_element(element)


def _parent_of(element: Mapping[str, Any]) -> str | None:
    """``parent_narrative`` as written, or ``None`` for no parent: absent, ``None``, not a string, or a string with
    nothing left after trimming White_Space (``""``, ``"   "``). A parent with content is never trimmed."""
    parent = element.get("parent_narrative")
    if not isinstance(parent, str) or parent.strip(_WHITE_SPACE) == "":
        return None
    return parent


def report_threads_of(narratives: Iterable[Mapping[str, Any]]) -> ReportThreads:
    """The report profile's rule 9: the reports among ``narratives`` grouped by ``parent_narrative``.

    Each element is a body (an API element or a folder file's dict) carrying its ``type``. An element that is not
    a mapping, or has no id that is a non-empty string, is passed over; of two with one id, the first counts. Every
    element is read as it is served: a known-of stub (``known_of: true``) served without the pair and the mark is
    neither a report nor a board entry, so as a parent it reads ``other``.

    Only reports are read for a parent and grouped: a message, or any element that is no report, is in no part of
    the answer, whatever its ``parent_narrative`` names. ``parents`` reads each report's parent: ``none`` (absent,
    ``None``, not a string, or nothing left after trimming White_Space; a parent with content is read as written,
    never trimmed), ``self``, ``missing`` (no element of that id given), ``report``, ``board`` (a board entry, the
    pair ``narrative`` + ``Board`` and the mark) or ``other``. A report
    whose parent is a report or a board entry is listed in that parent's group, in ``created_at`` order (an
    instant; equal times keep the order given; an unreadable time after every readable one). A report with no
    parent heads its own thread, and is listed as a group's parent only when another report names it. Groups
    follow the order their parent first appears in ``narratives``; the profile rules no order between groups. A
    report whose parent is a report that names another report as its own parent, one the reader holds (the pair and
    the mark), is listed under the parent it names, with a ``chain`` lint; an unheld or unmarked one makes no chain.
    One that names itself is in no group, with a ``self`` lint, and reads as naming no
    parent: it still heads the group of the reports that name it, and those carry no ``chain`` lint. Nothing is
    walked further up, and nothing is guessed from names or days."""
    held: dict[str, Mapping[str, Any]] = {}
    position: dict[str, int] = {}
    reports: list[Mapping[str, Any]] = []
    for element in narratives:
        if not isinstance(element, Mapping):
            continue
        eid = element.get("id")
        if not isinstance(eid, str) or not eid or eid in position:
            continue
        position[eid] = len(position)
        held[eid] = element
        if _is_marked(element, _REPORT_PAIR):
            reports.append(element)

    def is_report(eid: str) -> bool:
        element = held.get(eid)
        return element is not None and _is_marked(element, _REPORT_PAIR)

    def parent_kind(report: Mapping[str, Any]) -> ReportParent:
        parent = _parent_of(report)
        if parent is None:
            return "none"
        if parent == report["id"]:
            return "self"
        element = held.get(parent)
        if element is None:
            return "missing"
        if _is_marked(element, _REPORT_PAIR):
            return "report"
        if _is_marked(element, _BOARD_PAIR):
            return "board"
        return "other"

    parents: dict[str, ReportParent] = {}
    members: dict[str, list[Mapping[str, Any]]] = {}
    lints: list[ReportLint] = []
    for report in reports:
        rid: str = report["id"]
        kind = parent_kind(report)
        parents[rid] = kind
        if kind == "self":
            lints.append({"kind": "self", "report": rid})
        elif kind in ("report", "board"):
            parent = _parent_of(report)
            assert parent is not None
            members.setdefault(parent, []).append(report)
            if kind == "report":
                # A parent that names itself names no parent, so a report under it is no chain.
                grandparent = _parent_of(held[parent])
                if grandparent is not None and grandparent != parent and is_report(grandparent):
                    lints.append({"kind": "chain", "report": rid})

    groups: list[ReportGroup] = [
        {
            "parent": parent,
            "kind": "report" if is_report(parent) else "board",
            "reports": [r["id"] for r in _in_created_at_order(members[parent])],
        }
        for parent in sorted(members, key=position.__getitem__)
    ]
    return {"parents": parents, "groups": groups, "lints": lints}

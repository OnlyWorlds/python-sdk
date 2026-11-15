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

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Literal, TypedDict

from ._schema import ROOM_PAIRS
from .address import AddressReading, find_ow_links
from .message import _in_created_at_order, _matches
from .room import _WHITE_SPACE, is_room_element

__all__ = [
    "ReportGroup",
    "ReportLine",
    "ReportLint",
    "ReportParent",
    "ReportThreads",
    "read_report_line",
    "read_report_lines",
    "report_threads_of",
]

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


# ---- A line of ``consequences`` (the report profile's lines rulings: what a line is, its address, its shown words)

#: The closing marks, character by character (the lines rulings: a ``?`` is no closing mark, since it starts a
#: query after an address).
_CLOSING = frozenset([".", ",", ";", ":", "!", ")", "]", "}", "'", '"', "\u2019", "\u201d", "\u00bb"])
#: The pairs an address may stand in, each opener with its closer.
_PAIRS = {"(": ")", "[": "]", '"': '"', "'": "'", "\u201c": "\u201d", "\u2018": "\u2019", "\u00ab": "\u00bb"}


@dataclass(frozen=True)
class ReportLine:
    """What ``read_report_line`` reads in one line of a report's ``consequences``: ``line`` as read; ``words``, what
    a reader shows (the line without its address where nothing the writer wrote is lost, else the whole line);
    ``address``, the element the line names written ``ow://<type>/<id>`` (the id lowercase), or None; ``reading``,
    what ``parse_ow_link`` reads in the address as written, or None; ``start`` and ``end``, where that address stands
    in the line (Python string indexes, as ``find_ow_links`` counts them), or None."""

    line: str
    words: str
    address: str | None
    reading: AddressReading | None
    start: int | None
    end: int | None


def _world_option(fn: str, world: object) -> str | None:
    if world is not None and not isinstance(world, str):
        raise TypeError(f"{fn}: world must be a string (this world's id) or None")
    return world


def _read_line(line: str, world: str | None) -> ReportLine:
    # The line's address: the last one that names an element of this world, from its text alone.
    here = [
        f
        for f in find_ow_links(line)
        if f.reading.type is not None
        and f.reading.id is not None
        and (
            f.reading.world is None or (not f.reading.world_is_slug and world is not None and f.reading.world == world)
        )
    ]
    if not here:
        return ReportLine(line, line, None, None, None, None)
    last = here[-1]
    start, end, reading = last.start, last.end, last.reading
    found = ReportLine(line, line, f"ow://{reading.type}/{reading.id}", reading, start, end)
    # It leaves the words only when nothing the writer wrote is lost: canonical, no moment, no lens, standing apart.
    if not reading.canonical or reading.moment is not None or reading.lens is not None:
        return found
    lo, hi = start, end
    before = line[start - 1] if start > 0 else ""
    if before in _PAIRS:
        # A matched pair goes with it; an opener not closed right after keeps the whole line.
        if line[end : end + 1] != _PAIRS[before]:
            return found
        lo, hi = start - 1, end + 1
    apart_before = lo == 0 or line[lo - 1] in _WHITE_SPACE or line[lo - 1] == ":"
    apart_after = hi == len(line) or line[hi] in _WHITE_SPACE or line[hi] in _CLOSING
    if not (apart_before and apart_after):
        return found
    # The White_Space on both sides goes, and one colon right before it with the White_Space before that colon.
    left = line[:lo].rstrip(_WHITE_SPACE)
    if left.endswith(":"):
        left = left[:-1].rstrip(_WHITE_SPACE)
    right = line[hi:].lstrip(_WHITE_SPACE)
    # Nothing stands before the address: the whole line stays, so a line never shows empty.
    if left == "":
        return found
    if right == "":
        words = left
    elif right[0] in _CLOSING:
        words = left + right
    else:
        words = f"{left} {right}"
    return ReportLine(line, words, found.address, reading, start, end)


def read_report_line(line: str, *, world: str | None = None) -> ReportLine:
    """One line of a report's ``consequences``, read as the report profile reads it: the element it names and the
    words a reader shows. The line's address is the last address in it (found as the address profile finds one in
    prose, by ``find_ow_links``) that names an element of this world: an ``ow://`` or site address, its ids' hex in
    either case (the prefix, the host and the type word only in lowercase), whose world is ``world`` or is left out,
    and whose type and id have an element's shape. ``world`` is this world's id, lowercase as the world holds it: an
    address's world is read lowercase and compared with it exactly. An address of another world, a slug, a world
    alone or a lens with no element is prose, and a line with only those has no address, which is no fault. The
    address leaves the shown words only when nothing the
    writer wrote is lost: it is canonical, carries no moment and no lens, and stands apart (before it the line's
    start, White_Space or one colon; after it the line's end, White_Space or a closing mark: ``. , ; : ! ) ] }``,
    a straight quote, a closing curly quote or a closing guillemet), alone or in a matched pair (brackets, straight
    quotes, curly quotes or guillemets). Then it goes with the White_Space on both sides and one colon before it,
    and the two halves join with one space, or none when the second is empty or begins with a closing mark. In
    every other shape, and when nothing stands before the address, the whole line stays, still naming its element.
    Whether that element exists is the caller's to read. The line is read as given: ``read_report_lines`` splits
    and trims a whole text. A line that is not a string, or a ``world`` that is not a string or None, is a
    TypeError."""
    if not isinstance(line, str):
        raise TypeError("read_report_line: line must be a string")
    return _read_line(line, _world_option("read_report_line", world))


def read_report_lines(text: str, *, world: str | None = None) -> list[ReportLine]:
    """Every line of a report's ``consequences``, each read by ``read_report_line``. The text is split at every
    carriage return and every line feed (so CRLF is one break), each piece trimmed of Unicode White_Space at both
    ends, and a piece empty after trimming is no line; U+2028 and U+0085 stay inside a line, and a byte order mark
    is no White_Space. A text that is not a string is a TypeError."""
    if not isinstance(text, str):
        raise TypeError("read_report_lines: text must be a string")
    w = _world_option("read_report_lines", world)
    pieces = (p.strip(_WHITE_SPACE) for p in re.split(r"[\r\n]", text))
    return [_read_line(p, w) for p in pieces if p != ""]

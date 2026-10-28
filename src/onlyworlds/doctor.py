"""The doctor: a read-only check over a world, from a folder or through the API.

It reports what a keeper should look at, each finding with the element and the reason,
and it never writes: no file, no API write, no fix. Two doors, one walk:

::

    python -m onlyworlds.doctor PATH/TO/WORLD-FOLDER [--json | --packet] [--days N] [--changes N]
    python -m onlyworlds.doctor --api [--json | --packet] [--days N] [--changes N]

The API door reads its key from ``OW_API_KEY`` (else the toolkit's ``ONLYWORLDS_API_KEY``) and
its PIN from ``OW_API_PIN`` (else ``ONLYWORLDS_API_PIN``), lists every type in pages of 1,000 and
walks the change feed from the start.

The flags (the first list):

1. a link to an element that is not there;
2. a Title whose holders changed with no dated Relation;
3. an Event ending before it starts;
4. an element with no links in or out;
5. two elements of one type whose names collide after folding (NFKC, case-folded,
   whitespace and punctuation collapsed); a name shared across types is not one (a Location
   and its Pin or Zone share a name by the format's own convention);
6. a stub never filled, two readings: (6a) a known-of stub (``known_of: true``) older
   than N days, and (6b) an element with no text in any of its type's text fields, on the
   types with at least two prose fields beside ``description`` (not map, marker, pin and
   relation: their text is their links or their place);
7. a message unread by its addressee after N days;
8. a charter (a Law with supertype Charter) untouched after N changes;

and two from the file side, on the folder door only: (9) a ``format_version`` older than
this package's ``FORMAT_VERSION``; (10) an ``api_key`` in ``world.json``'s ``api`` block
when ``world.json`` is tracked by git.

And on both doors, (11) the world's own house rules: the checks profile (schema-dist
``profiles/checks.md``, dist.47; the list case and reader rules 6 to 8 from dist.54),
``x_checks_rules`` on the world's Charter, read by
``onlyworlds.checks.apply_checks``. The Charter is the charter profile's (schema-dist
``profiles/charter.md``, serial 83): the newest marked Charter, a Law with supertype Charter that
carries the mark ``x_charter_of``, which only a keeper may set; through the API it is
``front_door.charter`` from ``GET /me``, keel's own answer, and otherwise ``charter_of``'s selection
over what the door read. Every other marked Charter is a finding, its rules not applied (a tool
offers to retire it); a Law with supertype Charter and no mark is lore, not a Charter and not a
finding, and any house rules it carries are never applied (serial 85). Each element a rule finds
short is a finding (the rule's sentence as the reason; the charter, the rule's index and its field
as evidence); a rule the reader cannot apply is a finding on the charter, naming the rule and why;
a key that is not a list is one finding on the charter; a charter without the key checks nothing and
says so. ``compared`` carries every rule's ``scoped`` and ``short`` counts and the view read (``folder``, or the
key's role). A known-of stub is not judged (its absent fields are unknown; the profile's rule
6), and the rules are
on a Law only: a charter of another type that carries them is a finding, its rules not read.

On the API door only, (12) proposals waiting: the open and the lapsed rows of the
world's queue (``GET /world/proposals``, paged through), one finding on the world when any wait.
The queue holds two kinds of row: a proposal (``kind: "proposal"``, or no ``kind``
from a server before 2026-10-23) and a new element marked for review (``kind: "new_element"``, an
element carrying ``x_review_proposed``), counted apart and never one as the other. The finding
gives the proposals' open and lapsed counts, the marked new elements' when there are any, and the
oldest open proposal's age in days. ``compared`` carries the four counts and the view read (a
keeper reads every row, any other member its own). A key with no member reads no queue (403 or
404): the flag does not run, and says why. A row's ``evidence`` is outside text and is never read
into a finding.

On both doors, (13) the spine (schema-dist ``profiles/spine.md``, serial 61), on a world where some
element carries an ``x_spine_`` key (any other world skips it and says so). Each element is read by
``onlyworlds.spine.read_spine_element``: a listed type whose supertype is off the spine's list (or
empty) is a finding, and so is every value the reader drops (the key and the value) and a probe not in
the probe form; a type the list does not name, and the three free types, are not. Then the audit's
definite parts, which need the whole world. On a source world (one without the projection mark below):
each row (an Object, Construct, Location or Law of a kind on the list, the world's ``Charter`` too: the
page exempts none) is kept by exactly one Seat (a Title with supertype ``Seat``), through the Title's
field for the row's own type (``objects`` for an Object, ``constructs``, ``locations``, ``laws``); no
seat, or two, is a finding, and a Title that is not a Seat neither owns nor counts. Every
``x_spine_depends_on`` id must be in the world, a check that does not run through a guest key. A
``legacy`` or ``provenance`` row has an Event with supertype ``Retirement`` that names the row in
``x_spine_retires`` (the row's id as a string) and links it through its typed link field where the type
has one (``objects``, ``constructs``, ``locations``; an Event has no ``laws`` field, so a Law's
retirement is attributed by the key alone), not only in its text: a row no Retirement Event names is a
finding, and so is one whose naming Event does not link it. That check runs only through a key that
sees every element and is served hidden ones. A row still at ``gone`` is a finding: its retirement is
unfinished. Two rows of one row type whose names are one once trimmed and folded for case (as the room
profile defines both; a Seat or any other element is outside the rule) are a finding on the first by
id, naming the others (flag 5 folds wider, on every element). Whether a probe passes and
``x_spine_probed`` (the probe gate's) are never checked, and ``compared`` names them in
``not_checked``. A known-of stub is not read, though a Seat or a Retirement Event that is one still
keeps, names or links what it lists.

A projection (a public world built from a spine, each row naming its keeping Seat in ``x_spine_owner``)
is marked on its World: ``x_spine_projection``, ``{source, at}``, which also makes flag 13 run.
``source`` is the projected-from world's id as a string, never a link: a UUID, and a string equal to
any element's id in this world is a finding; ``at`` is the ISO 8601 time of the last rebuild, and a
string that ``datetime.fromisoformat`` does not parse is a finding (both on the World, which is still
read as a projection). On a projection only its three run: each row must carry ``x_spine_owner`` (the
keeping Seat's name in the source; it need match nothing in the projection) and no element may be
hidden (through a key that is not served hidden elements, ``not_checked`` says so). The source's
checks (one Seat per row, ``x_spine_depends_on``, the Retirement Event, ``gone``, name uniqueness) do
not run there, and ``not_checked`` names each. On an unmarked world ``x_spine_owner`` on any element
is a finding: it belongs on a projection only. A mark that is not an object with a string ``source``
and a string ``at`` is a finding on the World (``element`` null; on the folder door the evidence
names ``world.json``), and the world is then read as unmarked. ``compared`` carries the mark as
``projection`` (null when unmarked).

On both doors, (14) the reading aids' entries (the charter profile's Health line): a link on a marked
Guide or Domain (a Construct with supertype Guide or Domain carrying ``x_charter_of``) to an id that is not
in the world (deleted), or to a hidden element (the door names it; the Guide or Domain is served to every
reader without it). A Guide or Domain that is itself hidden is read by keepers only, so its hidden entries
are not findings; a known-of stub serves no links. Through a guest key the flag does not run (a link to an
element it cannot see is neither hidden nor deleted to it); through a key that is not served hidden
elements, ``compared`` names ``hidden`` in ``not_checked``. A deleted entry is flag 1's finding too, named
here on the aid.

A flag the walk cannot evaluate is reported in ``not_run`` with its reason, never as clean,
and every flag that ran says how much it could compare (``compared: {n, of}``): a clean
count over nothing compared is not a pass. A known-of stub's absent fields are unknown,
not empty (folder spec §4.4), so a stub is never counted as linkless or textless.

A finding on a parlor- or message-shaped element (supertype Message, Board, Work item, Spec,
Heart, Vote or Sitting) carries ``"kind": "message"``: it is about a room, not a fact about
the world. The prose groups those last and leaves them out of the "things to look at" count;
they still make the exit code 1.

What the feed can show was measured, not assumed: keel serves each element's upsert from
its row at its latest ``change_seq`` (keel ``core/changes.py``, spec §8: "every live element
is present at its latest change_seq"), so a walk carries current bodies only and flag 2
reports ``not_run`` unless the walk holds two versions of one element. No read mark exists
in the folder format, the API or this package, so flag 7 never runs.

``--packet`` prints the findings as work packets (``packets``): the ``packet`` extension
profile (schema-dist ``profiles/packet.md``, dist.36), a Relation with supertype ``Work item``
holding ``x_packet_elements`` (one entry per element, ``{type, id, reason}``, in flag order),
``x_packet_source`` (``{server, world}``; ``server`` null for a folder) and
``x_packet_producer`` (this tool and version), the same elements on the Relation's typed link
fields, no ``id`` (the tool that lands it mints one). A JSON array: empty on a clean run,
several packets past the extension cap (``PACKET_CAP``, each named ``(i of n)``). Findings on
messages and room things, and findings with no element (no charter), stay in the report and
out of the packet. The doctor still writes nothing: a packet is output, landing it is the
reader's act.

From the command line: exit 0 clean, 1 findings, 2 nothing could be read.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import io
import json
import os
import re
import subprocess
import sys
import unicodedata
from collections import defaultdict
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from itertools import pairwise
from pathlib import Path
from typing import Any, Protocol

from ._schema import ELEMENT_TYPES, FIELD_KINDS, GENERIC_PAIRS, LINK_TARGETS, SPINE_KINDS
from ._version import __version__
from .charter import charter_of
from .checks import CHECKS_FIELD, apply_checks
from .errors import ApiError
from .folder import FORMAT_VERSION, HIDDEN, WORLD_FILE, Folder, is_hidden, is_known_of, read_folder
from .http import API_BASE, Client
from .room import _fold, _reading_aid_key
from .spine import SPINE_OFF_LIST, SPINE_PREFIX, SpineRead, read_spine_element

__all__ = [
    "AIDS_FLAG",
    "CHECKS_FLAG",
    "FLAGS",
    "MESSAGE_SUPERTYPES",
    "PACKET_CAP",
    "PACKET_TOOL",
    "PROPOSALS_FLAG",
    "SPINE_FLAG",
    "ListReader",
    "Reader",
    "Report",
    "doctor_api",
    "doctor_folder",
    "fold_name",
    "main",
    "packets",
    "render_prose",
]

#: The house-rules flag (the checks profile): read from every Charter on both doors.
CHECKS_FLAG = "11"
#: The proposals flag: the world's queue, on the API door only.
PROPOSALS_FLAG = "12"
#: The spine flag (the spine profile and its audit): on both doors, on a world that carries an x_spine_ key.
SPINE_FLAG = "13"
#: The reading aids' flag (the charter profile's Health line): a Guide's or Domain's entry naming a hidden or
#: deleted element, on both doors.
AIDS_FLAG = "14"

#: Flag id -> what it looks for. The ids are strings because flag 6 has two readings.
FLAGS: dict[str, str] = {
    "1": "A link to an element that is not there",
    "2": "A Title whose holders changed with no dated Relation",
    "3": "An Event ending before it starts",
    "4": "An element with no links in or out",
    "5": "Two elements whose names collide after folding",
    "6a": "A known-of stub never filled",
    "6b": "An element with no text in any of its type's text fields",
    "7": "A message unread by its addressee",
    "8": "A charter untouched after N changes",
    "9": "A format_version older than this package's",
    "10": "An api_key in a tracked world.json",
    CHECKS_FLAG: "House rules (the checks profile)",
    PROPOSALS_FLAG: "Proposals waiting",
    SPINE_FLAG: "The spine (its profile and its audit)",
    AIDS_FLAG: "A Guide or Domain entry that names a hidden or deleted element",
}

#: A finding on an element of these supertypes (compared case-folded) is ``kind: "message"``
#: (ruled 2026-10-21): a world's own parlor, messages and room things, not facts about the world.
MESSAGE_SUPERTYPES: frozenset[str] = frozenset({"message", "board", "work item", "spec", "heart", "vote", "sitting"})

#: What each flag's ``compared`` counts, for the prose report.
_UNITS: dict[str, str] = {
    "1": "link values",
    "2": "Titles with two versions in the feed",
    "3": "Events with both dates",
    "4": "elements",
    "5": "named elements (names shared across types are not counted)",
    "6a": "known-of stubs with an updated_at",
    "6b": "whole elements",
    "8": "charters found in the feed",
    "9": "world.json format_version",
    "10": "world.json",
    CHECKS_FLAG: "house rules applied",
    PROPOSALS_FLAG: "open and lapsed queue rows read",
    SPINE_FLAG: "elements read under the spine profile",
    AIDS_FLAG: "links on marked Guides and Domains",
}

#: Fields that hold no prose even when the schema types them text.
_NOT_PROSE = frozenset({"name", "supertype", "subtype", "image_url"}) | {
    type_key for pairs in GENERIC_PAIRS.values() for type_key, _ in pairs
}
#: Flag 6b leaves out the types with fewer than two prose fields beside ``description``
#: (measured from the schema: map, marker, pin, relation). A Relation's text is its links.
_SPARSE_TYPES: tuple[str, ...] = tuple(
    t
    for t in ELEMENT_TYPES
    if len([f for f, k in FIELD_KINDS[t].items() if k == "text" and f not in _NOT_PROSE and f != "description"]) < 2
)
#: Atlas-written pins and markers spell two links ``map_id`` / ``zone_id`` (spec §5; ``push``).
_LEGACY_LINK_SPELLINGS: dict[str, dict[str, str]] = {
    "pin": {"map_id": "map", "zone_id": "zone"},
    "marker": {"map_id": "map", "zone_id": "zone"},
}
#: A Relation of these supertypes, naming a Title in ``titles``, dates a holding.
_HOLDING_SUPERTYPES = frozenset({"tenure", "membership"})
_PAGE = 1000
_GIT_TIMEOUT = 30.0
#: The bytes of a packet's three ``x_packet_*`` keys (ASCII JSON) one work item may carry: keel
#: caps extensions at 64 KB per element; the margin is for how keel measures.
PACKET_CAP = 60_000
#: The tool name a packet's producer line carries (decision 8 of the doctor's sheet).
PACKET_TOOL = "onlyworlds doctor"
#: Element type -> the Relation's multi-link field that holds it (the typed view of a packet).
_RELATION_FIELD: dict[str, str] = {
    target: f for f, target in LINK_TARGETS["relation"].items() if FIELD_KINDS["relation"][f] == "multi_link"
}


class ListReader(Protocol):
    """The reads a whole-world walk makes (the pack's API door needs only these); ``Client`` is one."""

    def me(self) -> dict[str, Any]: ...

    def get_world(self) -> dict[str, Any]: ...

    def list_page(
        self, element_type: str, *, limit: int | None = None, cursor: str | None = None
    ) -> dict[str, Any]: ...


class Reader(ListReader, Protocol):
    """The reads the API door makes; ``Client`` is one. Nothing here writes. A reader without
    ``world_proposals`` (one written before keel served the proposals queue) still works: flag 12 does not run."""

    def changes(self, *, since: str | None = None, limit: int | None = None) -> dict[str, Any]: ...

    def world_proposals(
        self,
        *,
        state: str | None = None,
        since: str | None = None,
        element: str | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> dict[str, Any]: ...


@dataclass
class Report:
    """One run. ``as_dict`` is the JSON report, keys in this order."""

    world: dict[str, Any]
    ran: list[str] = field(default_factory=list)
    not_run: list[dict[str, str]] = field(default_factory=list)
    findings: list[dict[str, Any]] = field(default_factory=list)
    #: flag -> ``{n, of}``; 6b adds ``skipped_types``
    compared: dict[str, dict[str, Any]] = field(default_factory=dict)
    #: always 0: the doctor never writes
    written: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "world": self.world,
            "ran": self.ran,
            "not_run": self.not_run,
            "findings": self.findings,
            "compared": self.compared,
            "written": self.written,
        }

    @property
    def exit_code(self) -> int:
        """1 for any finding, a message-shaped one too; 0 for none."""
        return 1 if self.findings else 0

    @property
    def to_look_at(self) -> list[dict[str, Any]]:
        """The findings that are facts about the world: all but ``kind: "message"``."""
        return [f for f in self.findings if f.get("kind") != "message"]

    @property
    def messages(self) -> list[dict[str, Any]]:
        """The findings on messages and room things (``kind: "message"``)."""
        return [f for f in self.findings if f.get("kind") == "message"]


@dataclass(frozen=True)
class _El:
    type: str
    id: str
    body: Mapping[str, Any]

    @property
    def name(self) -> str:
        name = self.body.get("name")
        return name if isinstance(name, str) else ""

    @property
    def known_of(self) -> bool:
        return is_known_of(self.body)

    def ref(self) -> dict[str, str]:
        return {"type": self.type, "id": self.id, "name": self.name}


class _Run:
    """Collects one report in flag order, whatever order the checks run in."""

    def __init__(self, world: dict[str, Any]):
        self.report = Report(world=world)
        self._ran: set[str] = set()
        self._not_run: dict[str, str] = {}
        self._findings: dict[str, list[dict[str, Any]]] = defaultdict(list)

    def ran(self, flag: str, n: int | None = None, of: int | None = None, **extra: Any) -> None:
        self._ran.add(flag)
        if n is not None and of is not None:
            self.report.compared[flag] = {"n": n, "of": of, **extra}

    def skip(self, flag: str, why: str) -> None:
        self._not_run[flag] = why

    def find(self, flag: str, element: _El | None, reason: str, evidence: Mapping[str, Any]) -> None:
        finding: dict[str, Any] = {
            "flag": flag,
            "element": element.ref() if element else None,
            "reason": reason,
            "evidence": dict(evidence),
        }
        if element is not None and _folded(element.body.get("supertype")) in MESSAGE_SUPERTYPES:
            finding["kind"] = "message"  # additive: a finding on anything else has no `kind`
        self._findings[flag].append(finding)

    def done(self) -> Report:
        r = self.report
        r.ran = [f for f in FLAGS if f in self._ran]
        r.not_run = [{"flag": f, "why": self._not_run[f]} for f in FLAGS if f in self._not_run]
        r.findings = [x for f in FLAGS for x in self._findings.get(f, [])]
        r.compared = {f: r.compared[f] for f in FLAGS if f in r.compared}
        return r


# ---------------------------------------------------------------------------
# Reading a body
# ---------------------------------------------------------------------------


def _has_value(value: Any) -> bool:
    return not (value is None or value == "" or value == [])


def _links(el: _El) -> Iterator[tuple[str, Any]]:
    """Every link value on ``el`` as (field, value), one per id in a multi link. A value that is
    not a string id is yielded too: it counts as a link it could not compare."""
    kinds = FIELD_KINDS.get(el.type, {})
    renames = _LEGACY_LINK_SPELLINGS.get(el.type, {})
    for key, value in el.body.items():
        name = renames.get(key, key)
        if name != key and name in el.body:
            continue  # the wire's spelling wins over Atlas's
        kind = kinds.get(name)
        if kind == "single_link" and _has_value(value):
            yield name, value
        elif kind == "multi_link" and _has_value(value):
            if isinstance(value, list):
                for item in value:
                    if _has_value(item):
                        yield name, item
            else:
                yield name, value


def _text_fields(element_type: str) -> list[str]:
    """The type's prose fields from the schema: every ``text`` field but name, supertype, subtype,
    image_url and a generic link's type key. Never ``description`` alone: a Law's text is in
    ``declaration`` and ``purpose``, a Narrative's in ``story``, a Title's in ``authority``."""
    return [f for f, kind in FIELD_KINDS.get(element_type, {}).items() if kind == "text" and f not in _NOT_PROSE]


def _int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _time(value: Any) -> _dt.datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        t = _dt.datetime.fromisoformat(value)
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=_dt.UTC)


def _type_order(element_type: str) -> int:
    return ELEMENT_TYPES.index(element_type) if element_type in ELEMENT_TYPES else len(ELEMENT_TYPES)


def _folded(value: Any) -> str:
    return value.strip().casefold() if isinstance(value, str) else ""


def fold_name(name: str) -> str:
    """A name as flag 5 compares it: NFKC, case-folded, every run of whitespace and punctuation
    one space, trimmed. ``"Ada, Inspector"`` and ``"ada  inspector"`` fold alike."""
    out: list[str] = []
    gap = False
    for ch in unicodedata.normalize("NFKC", name).casefold():
        if ch.isspace() or unicodedata.category(ch).startswith("P"):
            gap = True
            continue
        if gap and out:
            out.append(" ")
        gap = False
        out.append(ch)
    return "".join(out)


# ---------------------------------------------------------------------------
# The walk: flags that read the elements alone
# ---------------------------------------------------------------------------


def _walk(run: _Run, els: list[_El], *, days: int, now: _dt.datetime, whole_view: bool = True) -> None:
    """The flags read from the elements alone (1, 3, 4, 5, 6a, 6b). ``whole_view`` False: the
    reader cannot see every element (a guest), so flag 1 does not run."""
    ids = {el.id for el in els}

    # 1. A link to an element that is not there.
    if whole_view:
        values = compared = 0
        for el in els:
            for fname, value in _links(el):
                values += 1
                if not isinstance(value, str):
                    continue
                compared += 1
                if value not in ids:
                    run.find(
                        "1",
                        el,
                        f"its {fname} names an id that is not in the world",
                        {"field": fname, "missing_id": value},
                    )
        run.ran("1", compared, values)
    else:
        run.skip("1", "a guest key cannot see every element: a link to one it cannot see is not a deletion")

    # 3. An Event ending before it starts.
    events = [el for el in els if el.type == "event"]
    dated = 0
    for el in events:
        start, end = _int(el.body.get("start_date")), _int(el.body.get("end_date"))
        if start is None or end is None:
            continue
        dated += 1
        if end < start:
            run.find("3", el, "it ends before it starts", {"start_date": start, "end_date": end})
    run.ran("3", dated, len(events))

    # 4. An element with no links in or out.
    linked_to: set[str] = set()
    links_out: set[str] = set()
    for el in els:
        for _, value in _links(el):
            links_out.add(el.id)
            if isinstance(value, str):
                linked_to.add(value)
    # On a spine world (flag 13's test) a dependency is a link: the profile draws its edges with
    # x_spine_depends_on, so a row that only depends, or is only depended on, is not unlinked.
    spine = any(isinstance(k, str) and k.startswith(SPINE_PREFIX) for el in els for k in el.body)
    if spine:
        for el in els:
            deps = read_spine_element(el.type, el.body).depends_on or ()
            if deps:
                links_out.add(el.id)
                linked_to.update(deps)
    known = 0
    for el in els:
        if el.id in linked_to or el.id in links_out:
            known += 1
            continue
        if el.known_of:
            continue  # a stub's absent links are unknown, not absent
        known += 1
        why = "no link field is set on it and no element links to it"
        if spine:
            why = "no link field or x_spine_depends_on is set on it, and no element links to it or depends on it"
        run.find("4", el, why, {})
    run.ran("4", known, len(els))

    # 5. Two elements of one type whose names collide after folding. Across types is no
    # collision: a Location and its Pin or Zone share a name by the format's own convention.
    groups: dict[tuple[str, str], list[_El]] = defaultdict(list)
    for el in els:
        key = fold_name(el.name)
        if key:
            groups[(el.type, key)].append(el)
    named = sum(len(g) for g in groups.values())
    for (_, key), group in sorted(groups.items(), key=lambda kv: (_type_order(kv[0][0]), kv[0][1])):
        if len(group) < 2:
            continue
        same = sorted(group, key=lambda e: e.id)
        run.find(
            "5",
            same[0],
            f"{len(same)} elements of one type share this name once folded",
            {"folded": key, "with": [e.ref() for e in same[1:]]},
        )
    run.ran("5", named, len(els))

    # 6a. A known-of stub older than `days`.
    stubs = [el for el in els if el.known_of]
    timed = 0
    horizon = now - _dt.timedelta(days=days)
    for el in stubs:
        updated = _time(el.body.get("updated_at"))
        if updated is None:
            continue
        timed += 1
        if updated < horizon:
            run.find(
                "6a",
                el,
                f"a known-of stub not updated in {days} days",
                {"updated_at": el.body.get("updated_at"), "days": days},
            )
    run.ran("6a", timed, len(stubs))

    # 6b. No text in any of the type's text fields, on the types with prose beside description.
    whole = 0
    for el in els:
        if el.known_of:
            continue  # its absent fields are unknown, not empty: 6a's reading
        if el.type in _SPARSE_TYPES:
            continue
        whole += 1
        fields = _text_fields(el.type)
        if fields and not any(isinstance(el.body.get(f), str) and el.body[f].strip() for f in fields):
            run.find("6b", el, f"no text in any of its {len(fields)} text fields", {"fields": fields})
    of = sum(1 for el in els if el.type not in _SPARSE_TYPES)
    run.ran("6b", whole, of, skipped_types=list(_SPARSE_TYPES))


def _json_kind(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "a boolean"
    if isinstance(value, int | float):
        return "a number"
    if isinstance(value, str):
        return "a string"
    return "an object" if isinstance(value, Mapping) else type(value).__name__


#: ``named`` when the door could not ask keel which Law is the Charter (a folder, or a /me with no
#: ``front_door``): the doctor applies keel's rule to what it holds instead.
_NOT_ASKED = object()


def _aid_word(el: _El) -> str | None:
    """The reading aid's pair word (``law/charter``, ``construct/guide``, ``construct/domain``) when ``el`` is one:
    the pair, trimmed and folded, AND the mark ``x_charter_of`` by presence (``is_charter_element``)."""
    return _reading_aid_key({**el.body, "type": el.type})


def _the_charter(els: list[_El], laws: list[_El], named: Any) -> tuple[_El | None, str, str | None]:
    """The world's Charter among ``laws`` (each a Law with supertype Charter), by the charter profile (serial 83):
    the newest marked Charter. Returns the Charter or None, where the answer came from, and a reason when it could
    not be told.

    Through the API keel answers it: ``front_door.charter`` from ``GET /me`` (``named``, an id or None).
    Otherwise ``charter_of``'s selection over every element the door read, as their keeper reads them: the
    newest marked Charter by ``created_at``, then the higher id. Who made the Law no longer decides: the mark
    does, and only a keeper may set it."""
    if named is not _NOT_ASKED:
        if named is None:
            return None, "front_door", None
        hit = next((el for el in laws if el.id == named), None)
        if hit is None:
            return None, "front_door", f"GET /me names {named} as the Charter, and no Law this key listed has that id"
        return hit, "front_door", None
    packet = charter_of({"elements": [{**el.body, "type": el.type, "id": el.id} for el in els]}, {"rung": "owner"})
    chosen = packet["charter"]["id"] if packet["charter"] is not None else None
    return next((el for el in laws if el.id == chosen), None), "mark", None


def _house_rules(run: _Run, els: list[_El], *, view: str, named: Any = _NOT_ASKED) -> None:
    """Flag 11: the Charter's ``x_checks_rules`` (the checks profile) applied to the elements the
    door could read; the Charter is the newest marked one (``_the_charter``), every other marked Charter is a
    finding, its rules not applied; a Law with supertype Charter without the mark is lore, not a Charter and not a
    finding, and its rules are never applied. Never writes, reorders or repairs a list."""
    flag = CHECKS_FLAG
    charters = [el for el in els if _folded(el.body.get("supertype")) == "charter"]
    for el in charters:
        if el.type != "law" and CHECKS_FIELD in el.body:
            run.find(
                flag,
                el,
                f"{CHECKS_FIELD} rides on a Law with supertype Charter; on this {el.type.capitalize()} its house "
                "rules are not read",
                {"filed_as": el.type},
            )
    laws = [el for el in charters if el.type == "law"]
    the, source, unknown = _the_charter(els, laws, named)
    if unknown is not None:
        run.find(flag, None, f"no house rule is checked: {unknown}", {"source": source})
    marked = [el for el in laws if _aid_word(el) == "law/charter"]
    for el in marked:
        if el is the:
            continue
        rules = el.body.get(CHECKS_FIELD)
        held = f"; its {len(rules)} house rule(s) are not applied" if isinstance(rules, list) and rules else ""
        evidence = {
            "charter": the.id if the is not None else None,
            "source": source,
            "carries_rules": CHECKS_FIELD in el.body,
            "marked": True,
        }
        why = "a marked Charter that is not the world's Charter (the newest marked one); a tool offers to retire it"
        run.find(flag, el, f"{why}{held}", evidence)
    # The pair without the mark is lore (a kingdom's charter): not a Charter and not a finding, and any house
    # rules it carries are never applied.
    judged = [el for el in els if not el.known_of]  # a stub's absent fields are unknown, not short
    bodies = [{**el.body, "type": el.type, "id": el.id} for el in judged]
    by_ref = {(el.type, el.id): el for el in judged}
    rows: list[dict[str, Any]] = []
    applied = carrying = 0
    for charter in [the] if the is not None else []:
        if CHECKS_FIELD not in charter.body:
            continue
        carrying += 1
        rules = charter.body[CHECKS_FIELD]
        if not isinstance(rules, list):
            got = _json_kind(rules)
            run.find(
                flag,
                charter,
                f"{CHECKS_FIELD} is not a list ({got}), so no house rule on it is checked",
                {"charter": charter.id, "got": got.removeprefix("a ").removeprefix("an ")},
            )
            continue
        for row in apply_checks(rules, bodies):
            rows.append({"charter": charter.id, **row.as_dict(), "short": len(row.short)})
            if row.not_checked is not None:
                named = f', "{row.rule}",' if row.rule is not None else ""
                run.find(
                    flag,
                    charter,
                    f"house rule {row.index}{named} is not checked: {row.not_checked}",
                    {"charter": charter.id, "rule": row.index, "sentence": row.rule, "why": row.not_checked},
                )
                continue
            applied += 1
            for ref in row.short:
                run.find(
                    flag,
                    by_ref[(ref["type"], ref["id"])],
                    row.rule or "",
                    {"charter": charter.id, "rule": row.index, "field": row.field},
                )
    run.ran(
        flag,
        applied,
        len(rows),
        view=view,
        charters=len(laws),
        marked=len(marked),
        charter=the.id if the is not None else None,
        charter_from=source,
        carrying=carrying,
        stubs_not_judged=len(els) - len(judged),
        rules=rows,
    )


def _aid_entries(run: _Run, els: list[_El], *, whole_view: bool = True, sees_hidden: bool = True) -> None:
    """Flag 14, the charter profile's Health line: a marked Guide's or Domain's link naming an id that is not in the
    world, or a hidden element. ``whole_view`` False (a guest) does not run; ``sees_hidden`` False reads the
    deleted half only and names ``hidden`` in ``not_checked``. A hidden Guide or Domain is read by keepers only,
    so its hidden entries are not findings; a known-of stub serves no links."""
    flag = AIDS_FLAG
    if not whole_view:
        run.skip(flag, "a guest key cannot see every element: a link to one it cannot see is not hidden or gone to it")
        return
    by_id = {el.id: el for el in els}
    aids = [el for el in els if not el.known_of and _aid_word(el) in ("construct/guide", "construct/domain")]
    values = compared = 0
    for el in aids:
        word = "Guide" if _aid_word(el) == "construct/guide" else "Domain"
        for fname, value in _links(el):
            values += 1
            if not isinstance(value, str):
                continue
            compared += 1
            target = by_id.get(value)
            if target is None:
                run.find(
                    flag,
                    el,
                    f"this {word}'s {fname} names an id that is not in the world (deleted)",
                    {"field": fname, "missing_id": value},
                )
            elif sees_hidden and not is_hidden(el.body) and is_hidden(target.body):
                run.find(
                    flag,
                    el,
                    f"this {word}'s {fname} names a hidden element: every other reader is served the {word} without it",
                    {"field": fname, "hidden": target.ref()},
                )
    extra: dict[str, Any] = {"aids": len(aids)}
    if not sees_hidden:
        extra["not_checked"] = ["hidden"]
    run.ran(flag, compared, values, **extra)


#: A row kind's type -> the Title's field that lists it (the spine profile: "Ownership is the standard's").
_SEAT_FIELDS: dict[str, str] = {"object": "objects", "construct": "constructs", "location": "locations", "law": "laws"}
#: A row kind's type -> the Retirement Event's typed link field for it (serial 58). An Event has no ``laws``
#: field: a Law's retirement is attributed by ``x_spine_retires`` alone (serial 60).
_EVENT_FIELDS: dict[str, str] = {"object": "objects", "construct": "constructs", "location": "locations"}
#: The statuses whose row has a Retirement Event (the page's "Status, in time").
_RETIRING = ("legacy", "provenance")
#: The status a row passes through: still present at it, its retirement is unfinished (serial 60).
_GONE = "gone"
#: What flag 13 never checks, and why (the gate's own).
_SPINE_NOT_CHECKED: tuple[tuple[str, str], ...] = (
    ("probe passes", "whether a probe passes is the probe gate's to run; the doctor runs nothing"),
    ("x_spine_probed", "written by the probe gate only; the doctor does not read it"),
)
#: The World's mark of a projection (the spine profile, serial 58): ``{source, at}``.
_PROJECTION_KEY = f"{SPINE_PREFIX}projection"
#: The key a projection's row carries: the keeping Seat's name (spine.md serial 58; an anonymous key before).
_OWNER_KEY = f"{SPINE_PREFIX}owner"
#: The key a Retirement Event names the row it retires in: the row's id as a string (spine.md serial 60).
_RETIRES_KEY = f"{SPINE_PREFIX}retires"
#: A UUID as text: ``source`` is the projected-from world's id (serial 60).
_UUID = re.compile("[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
#: The roles whose keys are served hidden elements: any other key's view leaves them out.
_SEES_HIDDEN = frozenset({"owner", "co_builder"})
_ON_A_SOURCE = "a source world's check: on a projection only its three run"
#: What flag 13 does not check on a projection (serial 60: the source's checks run on a source world only).
_PROJECTION_SKIPS: tuple[dict[str, str], ...] = (
    {
        "check": "one seat per row",
        "why": "a source world's check: on a projection a row's owner is x_spine_owner, and a Seat there "
        "describes the organisation and owns nothing",
    },
    {"check": "x_spine_depends_on", "why": _ON_A_SOURCE},
    {"check": "retirement", "why": _ON_A_SOURCE},
    {"check": "gone", "why": _ON_A_SOURCE},
    {"check": "name unique", "why": _ON_A_SOURCE},
)
_HIDDEN_UNSEEN = {
    "check": "hidden",
    "why": "this key is not served hidden elements (the owner's and a co-builder's are): none seen is not none held",
}
_RETIREMENT_UNSEEN = {
    "check": "retirement",
    "why": "this key cannot see every element (a guest's) or is not served hidden ones: a Retirement Event it "
    "cannot see is not a missing one",
}


def _projection_mark(value: Any) -> dict[str, str] | None:
    """The mark as ``{source, at}`` when it is an object with a string ``source`` and a string ``at``."""
    if isinstance(value, Mapping):
        source, at = value.get("source"), value.get("at")
        if isinstance(source, str) and isinstance(at, str):
            return {"source": source, "at": at}
    return None


def _parses_as_iso(text: str) -> bool:
    try:
        _dt.datetime.fromisoformat(text)
    except ValueError:
        return False
    return True


def _listed(body: Mapping[str, Any], fname: str) -> set[str]:
    value = body.get(fname)
    return {v for v in value if isinstance(v, str)} if isinstance(value, list) else set()


def _spine(
    run: _Run,
    els: list[_El],
    world: Mapping[str, Any],
    *,
    whole_view: bool = True,
    sees_hidden: bool = True,
    world_file: str | None = None,
) -> None:
    """Flag 13: each element read under the spine profile (``read_spine_element``), and the audit's
    definite parts (spine.md serial 60). Runs on a world that carries an ``x_spine_`` key on an element,
    or the projection mark (``x_spine_projection``) on its World. A known-of stub is not read: its absent
    supertype is unknown, not off the list.

    On a source world (unmarked): a row kept by exactly one Seat, through the Title's field for the row's
    own type (a Title that is not a Seat neither owns nor counts); every ``x_spine_depends_on`` id
    resolving (only with the whole view); a ``legacy`` or ``provenance`` row named by a ``Retirement``
    Event in ``x_spine_retires`` and linked by that Event through its typed link field where the type has
    one (a Law by the key alone: an Event has no ``laws``; only with the whole view, hidden elements
    served); a row still at ``gone`` (its retirement unfinished); a row's name unique within its row type
    once folded (trimmed, without regard to case); and ``x_spine_owner`` on no element.

    On a projection (the World marked ``{source, at}``) only its three run: each row carries
    ``x_spine_owner`` (the keeping Seat's name in the source, matched against nothing here), and no
    element is hidden (``sees_hidden`` False: the key is not served hidden elements, so that is named in
    ``not_checked``); the source's checks are named in ``not_checked``. Its ``source`` must be a UUID
    that is no element's id in this world, and its ``at`` must parse as an ISO 8601 time: each is a
    finding on the World otherwise. A mark that is not an object with a string ``source`` and a string
    ``at`` is a finding on the World, and the world is then read as unmarked (``x_spine_owner`` a
    finding, no row asked for one, the source's checks run)."""
    flag = SPINE_FLAG
    raw_mark = world.get(_PROJECTION_KEY)
    if raw_mark is None and not any(isinstance(k, str) and k.startswith(SPINE_PREFIX) for el in els for k in el.body):
        run.skip(flag, f"no {SPINE_PREFIX} key in the world")
        return
    mark = _projection_mark(raw_mark)
    where = {"file": world_file} if world_file else {}
    if raw_mark is not None and mark is None:
        run.find(
            flag,
            None,
            f"the world's {_PROJECTION_KEY} is malformed: the mark is an object with a string source and a "
            "string at, so the world is read as unmarked",
            {**where, "key": _PROJECTION_KEY, "value": raw_mark},
        )
    ids = {el.id for el in els}
    if mark is not None:
        source, at = mark["source"], mark["at"]
        if not _UUID.fullmatch(source):
            run.find(
                flag,
                None,
                f"the world's {_PROJECTION_KEY} source is not a UUID: it is the id of the world projected from",
                {**where, "key": _PROJECTION_KEY, "source": source},
            )
        if source in ids:
            same = next(el for el in els if el.id == source)
            run.find(
                flag,
                None,
                f"the world's {_PROJECTION_KEY} source is the id of an element in this world, not of the world "
                "projected from",
                {**where, "key": _PROJECTION_KEY, "source": source, "element": same.ref()},
            )
        if not _parses_as_iso(at):
            run.find(
                flag,
                None,
                f"the world's {_PROJECTION_KEY} at does not parse as an ISO 8601 time",
                {**where, "key": _PROJECTION_KEY, "at": at},
            )
    judged = [el for el in els if not el.known_of]
    reads = [(el, read_spine_element(el.type, el.body)) for el in judged]

    for el, read in reads:
        if read.kind == SPINE_OFF_LIST and el.type in SPINE_KINDS:
            listed = ", ".join(SPINE_KINDS[el.type])
            supertype = el.body.get("supertype")
            run.find(
                flag,
                el,
                f"its supertype is off the spine's list for {el.type} ({listed})",
                {"supertype": supertype},
            )
        for entry in read.dropped:
            run.find(
                flag,
                el,
                f"the spine reader left out a value of {entry['key']}",
                {"key": entry["key"], "value": entry["value"]},
            )
        if read.probe == "unsupported":
            run.find(
                flag,
                el,
                "its x_spine_probe is not in the probe form, so it is never run",
                {"probe": el.body.get("x_spine_probe")},
            )

    rows = [(el, read) for el, read in reads if el.type in _SEAT_FIELDS and read.kind != SPINE_OFF_LIST]
    seats = [el for el in els if el.type == "title" and read_spine_element("title", el.body).kind == "Seat"]
    skipped: list[dict[str, str]] = []
    depends: int | None = None
    retiring: int | None = None
    if mark is not None:
        # A projection: only its three run. Every row carries its keeping Seat's name (the source's, which
        # need match nothing here), and nothing is hidden.
        for el, read in rows:
            owner = el.body.get(_OWNER_KEY)
            if not (isinstance(owner, str) and owner.strip()):
                run.find(
                    flag,
                    el,
                    f"it is a row of a projection and carries no {_OWNER_KEY}",
                    {"spine_kind": read.kind, "key": _OWNER_KEY, "value": owner},
                )
        for el in els:
            if is_hidden(el.body):
                run.find(
                    flag,
                    el,
                    "it is hidden, and a projection carries nothing hidden",
                    {"key": HIDDEN, "value": el.body.get(HIDDEN)},
                )
        skipped += [dict(x) for x in _PROJECTION_SKIPS]
        if not sees_hidden:
            skipped.append(dict(_HIDDEN_UNSEEN))
    else:
        # x_spine_owner belongs on a projection only. Any element: a stub's present key is present.
        for el in els:
            if el.body.get(_OWNER_KEY) is not None:
                run.find(
                    flag,
                    el,
                    f"it carries {_OWNER_KEY}, which belongs on a projection only, and the world carries no "
                    f"{_PROJECTION_KEY} mark",
                    {"key": _OWNER_KEY, "value": el.body.get(_OWNER_KEY)},
                )
        depends, retiring = _spine_source(run, els, ids, reads, rows, seats, whole_view, sees_hidden, skipped)

    run.ran(
        flag,
        len(reads),
        len(els),
        rows=len(rows),
        seats=len(seats),
        depends_on=depends,
        retiring=retiring,
        stubs_not_judged=len(els) - len(judged),
        projection=mark,
        not_checked=skipped + [{"check": check, "why": why} for check, why in _SPINE_NOT_CHECKED],
    )


def _spine_source(
    run: _Run,
    els: list[_El],
    ids: set[str],
    reads: list[tuple[_El, SpineRead]],
    rows: list[tuple[_El, SpineRead]],
    seats: list[_El],
    whole_view: bool,
    sees_hidden: bool,
    skipped: list[dict[str, str]],
) -> tuple[int | None, int | None]:
    """Flag 13's checks that run on a source world only (spine.md serial 60). Appends what this key
    cannot check to ``skipped``; returns the ``x_spine_depends_on`` ids compared and the retiring rows
    looked for (None when not checked)."""
    flag = SPINE_FLAG
    # One owner per row: exactly one Title with supertype Seat lists it, in its field for the row's own
    # type; a Title that is not a Seat neither owns nor counts. A Seat that is a known-of stub still keeps
    # what it lists.
    keepers: dict[tuple[str, str], list[_El]] = defaultdict(list)
    for seat in seats:
        for fname in _SEAT_FIELDS.values():
            value = seat.body.get(fname)
            ids_listed = value if isinstance(value, list) else []
            for rid in dict.fromkeys(v for v in ids_listed if isinstance(v, str)):
                keepers[(fname, rid)].append(seat)
    for el, read in rows:
        fname = _SEAT_FIELDS[el.type]
        kept = keepers.get((fname, el.id), [])
        if not kept:
            run.find(
                flag,
                el,
                f"no seat keeps it: no Title with supertype Seat lists it in its {fname}",
                {"spine_kind": read.kind, "field": fname, "seats": []},
            )
        elif len(kept) > 1:
            names = ", ".join(s.name or s.id for s in kept)
            run.find(
                flag,
                el,
                f"{len(kept)} seats keep it ({names}): a row has one owner",
                {"spine_kind": read.kind, "field": fname, "seats": [s.ref() for s in kept]},
            )

    # Every x_spine_depends_on id resolves to an element in the world.
    depends: int | None = None
    if whole_view:
        depends = 0
        for el, read in reads:
            for dep in read.depends_on or ():
                depends += 1
                if dep not in ids:
                    run.find(
                        flag,
                        el,
                        "its x_spine_depends_on names an id that is not in the world",
                        {"key": "x_spine_depends_on", "missing_id": dep},
                    )
    else:
        skipped.append(
            {
                "check": "x_spine_depends_on",
                "why": "a guest key cannot see every element: an id it cannot see is not a missing one",
            }
        )

    # A legacy or provenance row has a Retirement Event that names it in x_spine_retires (serial 60) and
    # links it through the Event's typed field for the row's own type (serial 58) where the type has one:
    # an Event has no laws field, so a Law's is the key alone. A Retirement Event that is a known-of stub
    # still names and links what it lists.
    retiring: int | None = None
    if whole_view and sees_hidden:
        retiring = 0
        events = [el for el in els if el.type == "event" and read_spine_element("event", el.body).kind == "Retirement"]
        naming: dict[str, list[_El]] = defaultdict(list)
        for event in events:
            retires = event.body.get(_RETIRES_KEY)
            if isinstance(retires, str):
                naming[retires].append(event)
        for el, read in rows:
            if read.status not in _RETIRING:
                continue
            retiring += 1
            efield = _EVENT_FIELDS.get(el.type)
            named = naming.get(el.id, [])
            if not named:
                linking = [e for e in events if efield is not None and el.id in _listed(e.body, efield)]
                run.find(
                    flag,
                    el,
                    f"it is {read.status} and no Event with supertype Retirement names it in {_RETIRES_KEY}",
                    {
                        "spine_kind": read.kind,
                        "status": read.status,
                        "key": _RETIRES_KEY,
                        "linked_by": [e.ref() for e in linking],
                    },
                )
            elif efield is not None and not any(el.id in _listed(e.body, efield) for e in named):
                run.find(
                    flag,
                    el,
                    f"it is {read.status} and the Retirement Event that names it in {_RETIRES_KEY} does not link "
                    f"it in its {efield}",
                    {
                        "spine_kind": read.kind,
                        "status": read.status,
                        "field": efield,
                        "events": [e.ref() for e in named],
                    },
                )
    else:
        skipped.append(dict(_RETIREMENT_UNSEEN))

    # A row still at gone: its Retirement Event written, it is removed; present, the retirement is unfinished.
    for el, read in rows:
        if read.status == _GONE:
            run.find(
                flag,
                el,
                "it is gone and still in the world: its retirement is unfinished",
                {"spine_kind": read.kind, "status": _GONE},
            )

    # A row's name is unique within its row type once folded (trimmed, without regard to case, as the room
    # profile defines it): two that share one take names that say which. The four row types only.
    by_name: dict[tuple[str, str], list[_El]] = defaultdict(list)
    for el, _ in rows:
        folded = _fold(el.name)
        if folded:
            by_name[(el.type, folded)].append(el)
    for (_, folded), group in sorted(by_name.items(), key=lambda kv: (_type_order(kv[0][0]), kv[0][1])):
        if len(group) < 2:
            continue
        same = sorted(group, key=lambda e: e.id)
        run.find(
            flag,
            same[0],
            f"{len(same)} rows of one type share this name once trimmed and folded for case: a row's name says "
            "which it is",
            {"folded": folded, "with": [e.ref() for e in same[1:]]},
        )
    return depends, retiring


# ---------------------------------------------------------------------------
# The folder door
# ---------------------------------------------------------------------------


def _version_tuple(value: Any) -> tuple[int, ...] | None:
    if not isinstance(value, str):
        return None
    try:
        return tuple(int(part) for part in value.split("."))
    except ValueError:
        return None


def _git(root: Path, *args: str) -> bool:
    """True when a read-only git command succeeds in ``root``. Raises FileNotFoundError without git."""
    done = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        timeout=_GIT_TIMEOUT,
        check=False,
        stdin=subprocess.DEVNULL,
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},  # not even an index refresh
    )
    return done.returncode == 0


def _file_side(run: _Run, folder: Folder) -> None:
    world = folder.world
    if world is None:
        run.skip("9", "world.json could not be read")
        run.skip("10", "world.json could not be read")
        return

    # 9. A format_version older than this package's.
    declared = world.get("format_version")
    mine, theirs = _version_tuple(FORMAT_VERSION), _version_tuple(declared)
    if mine is not None and theirs is not None:
        run.ran("9", 1, 1)
        if theirs < mine:
            run.find(
                "9",
                None,
                f"world.json declares format_version {declared}, older than {FORMAT_VERSION}",
                {"file": WORLD_FILE, "format_version": declared, "package": FORMAT_VERSION},
            )
    else:
        run.ran("9", 0, 1)

    # 10. An api_key in a tracked world.json. The key itself is never printed.
    api = world.get("api")
    has_key = isinstance(api, Mapping) and _has_value(api.get("api_key"))
    try:
        in_repo = (folder.root / ".git").exists() or _git(folder.root, "rev-parse", "--is-inside-work-tree")
        tracked = in_repo and _git(folder.root, "ls-files", "--error-unmatch", WORLD_FILE)
    except (OSError, subprocess.SubprocessError) as exc:
        if not (folder.root / ".git").exists():
            run.ran("10", 1, 1)  # no repository and no git: nothing tracks world.json
            return
        run.skip("10", f"the folder is a git repository, but git could not be run ({type(exc).__name__})")
        return
    run.ran("10", 1, 1)
    if has_key and tracked:
        run.find(
            "10",
            None,
            "world.json holds an api_key and git tracks world.json, so the key is in the repository",
            {"file": WORLD_FILE, "key": "api.api_key", "tracked": True},
        )


def doctor_folder(folder: Folder, *, days: int = 14, changes: int = 50, now: _dt.datetime | None = None) -> Report:
    """Check a read folder (``read_folder``). Reads only; ``changes`` is unused here (no feed in a
    folder) and kept so both doors take the same arguments."""
    world = folder.world or {}
    run = _Run({"id": world.get("id"), "name": world.get("name"), "door": "folder"})
    els = [_El(fe.type, eid, fe.body) for eid, fe in folder.all_elements().items()]
    _walk(run, els, days=days, now=now or _dt.datetime.now(_dt.UTC))
    _house_rules(run, els, view="folder")
    _spine(run, els, world, world_file=WORLD_FILE)
    _aid_entries(run, els)
    run.skip("2", "needs the feed's history of Title.holders")
    run.skip("7", "read marks are not in the folder")
    run.skip("8", "no feed in a folder")
    run.skip(PROPOSALS_FLAG, "proposals are kept on the server, not in a folder")
    _file_side(run, folder)
    return run.done()


# ---------------------------------------------------------------------------
# The API door
# ---------------------------------------------------------------------------


def _list_all(client: ListReader, element_type: str) -> Iterator[dict[str, Any]]:
    cursor: str | None = None
    while True:
        page = client.list_page(element_type, limit=_PAGE, cursor=cursor)
        yield from (b for b in page.get("data", []) if isinstance(b, dict))
        if not page.get("has_more"):
            return
        nxt = page.get("next_cursor")
        if not isinstance(nxt, str) or not nxt or nxt == cursor:
            raise ValueError(f"{element_type}: has_more without a new next_cursor")
        cursor = nxt


def _feed(client: Reader) -> tuple[list[dict[str, Any]], Any]:
    """The whole feed from the start, in its order, and its ``head``."""
    rows: list[dict[str, Any]] = []
    cursor: str | None = None
    while True:
        page = client.changes(since=cursor, limit=_PAGE)
        rows.extend(r for r in page.get("changes", []) if isinstance(r, dict))
        head = page.get("head")
        if not page.get("has_more"):
            return rows, head
        nxt = page.get("cursor")
        if not isinstance(nxt, str) or nxt == cursor:
            raise ValueError("/changes said has_more but gave no new cursor")
        cursor = nxt


def _holders(body: Any) -> frozenset[str]:
    value = body.get("holders") if isinstance(body, Mapping) else None
    return frozenset(v for v in value if isinstance(v, str)) if isinstance(value, list) else frozenset()


def _title_history(run: _Run, els: list[_El], rows: list[dict[str, Any]]) -> None:
    """Flag 2, from the feed: a Title whose holders differ between two of its upserts."""
    upserts = [r for r in rows if r.get("op") == "upsert" and isinstance(r.get("id"), str)]
    distinct = {r["id"] for r in upserts}
    if len(distinct) == len(upserts):
        run.skip(
            "2",
            "the feed carries current bodies only; a holders change cannot be seen "
            f"(measured: {len(upserts)} upserts for {len(distinct)} ids)",
        )
        return
    titles = {el.id: el for el in els if el.type == "title"}
    versions: dict[str, list[frozenset[str]]] = defaultdict(list)
    for r in upserts:
        if r["id"] in titles:
            versions[r["id"]].append(_holders(r.get("element")))
    dated: set[str] = set()
    for el in els:
        if el.type != "relation" or _folded(el.body.get("supertype")) not in _HOLDING_SUPERTYPES:
            continue
        if _int(el.body.get("start_date")) is None and _int(el.body.get("end_date")) is None:
            continue
        named = el.body.get("titles")
        if isinstance(named, list):
            dated.update(v for v in named if isinstance(v, str))
    seen = 0
    for tid, held in versions.items():
        if len(held) < 2:
            continue
        seen += 1
        moves = [(a, b) for a, b in pairwise(held) if a != b]
        if moves and tid not in dated:
            before, after = moves[-1]
            run.find(
                "2",
                titles[tid],
                "its holders changed and no dated Tenure or Membership Relation names it",
                {"holders_before": sorted(before), "holders_after": sorted(after), "versions": len(held)},
            )
    run.ran("2", seen, len(titles))


def _charters(run: _Run, els: list[_El], rows: list[dict[str, Any]], head: Any, *, changes: int) -> None:
    """Flag 8: a charter with more than ``changes`` feed rows after its own."""
    charters = [el for el in els if _folded(el.body.get("supertype")) == "charter"]
    if not charters:
        run.ran("8", 0, 0)
        run.find("8", None, "no charter: no element with supertype Charter (the guidance names a Law)", {})
        return
    for el in charters:
        if el.type != "law":
            # BrainBoost files its charter as a Construct: still a charter to this flag,
            # but keel's world page and the parlor read a Law with supertype Charter, so say so.
            run.find(
                "8",
                el,
                f"the charter is filed as a {el.type.capitalize()}: keel's world page and the parlor read a Law "
                "with supertype Charter",
                {"filed_as": el.type},
            )
    position = {r["id"]: i for i, r in enumerate(rows) if r.get("op") == "upsert" and isinstance(r.get("id"), str)}
    found = 0
    for el in charters:
        at = position.get(el.id)
        if at is None:
            continue
        found += 1
        after = len(rows) - at - 1
        if after > changes:
            run.find(
                "8",
                el,
                f"{after} changes in the feed since this charter last changed (more than {changes})",
                {"changes_after": after, "limit": changes, "change_seq": el.body.get("change_seq"), "head": head},
            )
    run.ran("8", found, len(charters))


#: The ``kind`` of a queue row that is a new element marked for review, not a proposal.
_NEW_ELEMENT = "new_element"


def _queue(client: Reader, state: str) -> list[dict[str, Any]]:
    """Every row of the world's proposal queue in one state, paged through."""
    rows: list[dict[str, Any]] = []
    cursor: str | None = None
    while True:
        page = client.world_proposals(state=state, limit=_PAGE, cursor=cursor)
        rows.extend(r for r in page.get("data", []) if isinstance(r, dict))
        if not page.get("has_more"):
            return rows
        nxt = page.get("next_cursor")
        if not isinstance(nxt, str) or not nxt or nxt == cursor:
            raise ValueError("/world/proposals said has_more without a new next_cursor")
        cursor = nxt


def _proposals(run: _Run, client: Reader, *, view: str, now: _dt.datetime) -> None:
    """Flag 12: the open and the lapsed proposals, and the new elements marked for review, waiting
    for a keeper: one finding on the world."""
    flag = PROPOSALS_FLAG
    if getattr(client, "world_proposals", None) is None:
        run.skip(flag, "this reader has no proposal queue read")
        return
    try:
        waiting = {state: _queue(client, state) for state in ("open", "lapsed")}
    except ApiError as exc:
        if exc.status in (403, 404):
            run.skip(
                flag,
                f"the proposal queue answered {exc.status}: a key with no member (the owner's read key, a "
                "demo key) reads no queue, and an older server has none",
            )
        else:
            run.skip(flag, f"the proposal queue could not be read ({exc})")
        return
    except (ConnectionError, ValueError) as exc:
        run.skip(flag, f"the proposal queue could not be read ({exc})")
        return
    # A marked new element is a row of its own kind, never a proposal.
    proposals = {s: [r for r in rows if r.get("kind") != _NEW_ELEMENT] for s, rows in waiting.items()}
    marked = {s: [r for r in rows if r.get("kind") == _NEW_ELEMENT] for s, rows in waiting.items()}
    opened, lapsed = len(proposals["open"]), len(proposals["lapsed"])
    new_open, new_lapsed = len(marked["open"]), len(marked["lapsed"])
    total = opened + lapsed + new_open + new_lapsed
    run.ran(flag, total, total, open=opened, lapsed=lapsed, new_open=new_open, new_lapsed=new_lapsed, view=view)
    if not total:
        return
    dated = [(t, r) for r in proposals["open"] if (t := _time(r.get("created_at"))) is not None]
    oldest = min(dated, key=lambda tr: tr[0]) if dated else None
    said = [f"{opened} proposals open and {lapsed} lapsed"] if opened or lapsed else []
    if new_open or new_lapsed:
        said.append(f"{new_open} new elements open for review and {new_lapsed} lapsed")
    reason = ", and ".join(said) + ", waiting for a keeper"
    evidence: dict[str, Any] = {
        "open": opened,
        "lapsed": lapsed,
        "new_open": new_open,
        "new_lapsed": new_lapsed,
        "oldest_open_days": None,
        "oldest_open": None,
    }
    if oldest is not None:
        days = (now - oldest[0]).days
        reason += f"; the oldest open proposal is {days} days old"
        row = oldest[1]
        evidence["oldest_open_days"] = days
        evidence["oldest_open"] = {k: row.get(k) for k in ("id", "element_type", "element_id")}
    run.find(flag, None, reason, evidence)


def doctor_api(client: Reader, *, days: int = 14, changes: int = 50, now: _dt.datetime | None = None) -> Report:
    """Check the key's world through the API: ``me``, ``get_world``, every type's list, the feed
    and the proposal queue. Reads only. A failure to read the world or a list raises (``ApiError``,
    ``ConnectionError``, ``ValueError``); a feed that cannot be read makes flags 2 and 8 ``not_run``,
    a queue that cannot be read flag 12."""
    world = client.get_world()
    try:
        me = client.me()
    except (ApiError, ValueError):
        me = {}
    role = me.get("role")
    view = role if isinstance(role, str) and role else "unknown"
    door = me.get("front_door")
    named = door.get("charter") if isinstance(door, dict) and "charter" in door else _NOT_ASKED
    at = now or _dt.datetime.now(_dt.UTC)
    run = _Run({"id": world.get("id"), "name": world.get("name"), "door": "api"})
    els: list[_El] = []
    for t in ELEMENT_TYPES:
        els.extend(_El(t, b["id"], b) for b in _list_all(client, t) if isinstance(b.get("id"), str))
    _walk(run, els, days=days, now=at, whole_view=role != "guest")
    _house_rules(run, els, view=view, named=named)
    _spine(run, els, world, whole_view=role != "guest", sees_hidden=role in _SEES_HIDDEN)
    _aid_entries(run, els, whole_view=role != "guest", sees_hidden=role in _SEES_HIDDEN)
    try:
        rows, head = _feed(client)
    except (ApiError, ConnectionError, ValueError) as exc:
        why = f"the feed could not be read ({exc})"
        run.skip("2", why)
        run.skip("8", why)
    else:
        _title_history(run, els, rows)
        _charters(run, els, rows, head, changes=changes)
    _proposals(run, client, view=view, now=at)
    run.skip("7", "read marks are not readable through the API")
    run.skip("9", "a file-side check: the API door reads no world.json")
    run.skip("10", "a file-side check: the API door reads no world.json")
    return run.done()


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------


def _say(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def _lines(report: Report) -> Iterable[str]:
    w = report.world
    yield f"The doctor on {w.get('name') or '(no name)'} ({w.get('id') or 'no id'}), {w.get('door')} door"
    yield ""
    messages = report.messages
    yield (
        f"{len(report.to_look_at)} things to look at, {len(report.ran)} flags ran, "
        f"{len(report.not_run)} could not run, {report.written} things written"
        + (f" ({len(messages)} on messages and room things, listed last)" if messages else "")
    )
    yield from _by_flag(report.to_look_at)
    yield ""
    yield "What was checked"
    for flag in report.ran:
        c = report.compared.get(flag)
        counted = f": {c['n']} of {c['of']} {_UNITS.get(flag, '')}".rstrip() if c else ""
        if c and c.get("skipped_types"):
            skipped = ", ".join(c["skipped_types"])
            counted += f" (not compared: {skipped}, types with under two text fields beside description)"
        if c and flag == CHECKS_FLAG:
            counted += f" ({_rules_note(c)})"
        if c and flag == PROPOSALS_FLAG:
            counted += f" (proposals open: {c['open']}, lapsed: {c['lapsed']}"
            if c.get("new_open") or c.get("new_lapsed"):
                counted += f"; new elements open: {c['new_open']}, lapsed: {c['new_lapsed']}"
            counted += f"; view: {c['view']})"
        if c and flag == SPINE_FLAG:
            counted += f" ({_spine_note(c)})"
        yield f"  {flag}. {FLAGS[flag]}{counted}"
        if c and flag == CHECKS_FLAG:
            yield from _rule_lines(c)
        if c and flag == SPINE_FLAG:
            for item in c.get("not_checked", []):
                yield f"      not checked, {item['check']}: {item['why']}"
    if report.not_run:
        yield ""
        yield "What could not be checked, and why"
        for item in report.not_run:
            yield f"  {item['flag']}. {FLAGS[item['flag']]}: {item['why']}"
    if messages:
        yield ""
        yield "Messages and room things (not facts about the world)"
        yield f"  {len(messages)} findings on elements whose supertype marks a message or a room thing;"
        yield "  they are not counted above, but they still make the exit code 1."
        yield from _by_flag(messages)


def _rules_note(c: Mapping[str, Any]) -> str:
    """The house-rules line's parenthesis: the view read, and why nothing was checked when nothing was."""
    note = f"view: {c.get('view')}"
    if not c.get("charters"):
        note += "; no Law with supertype Charter"
    elif not c.get("carrying"):
        note += f"; no charter carries {CHECKS_FIELD}"
    if c.get("stubs_not_judged"):
        note += f"; {c['stubs_not_judged']} known-of stubs not judged"
    return note


def _spine_note(c: Mapping[str, Any]) -> str:
    """The spine line's parenthesis: rows and seats, the dependencies compared, the stubs not read."""
    mark = c.get("projection")
    if mark:
        note = f"{c['rows']} rows of a projection of {mark['source']}, rebuilt {mark['at']}"
    else:
        note = f"{c['rows']} rows against {c['seats']} seats"
    if c.get("depends_on") is not None:
        note += f"; {c['depends_on']} x_spine_depends_on ids compared"
    if c.get("retiring"):
        note += f"; {c['retiring']} legacy or provenance rows looked for in Retirement Events"
    if c.get("stubs_not_judged"):
        note += f"; {c['stubs_not_judged']} known-of stubs not read"
    return note


def _rule_lines(c: Mapping[str, Any]) -> Iterable[str]:
    """One line per house rule: scoped and short, or not checked and why."""
    several = c.get("carrying", 0) > 1
    for row in c.get("rules", []):
        named = f', "{row["rule"]}"' if row["rule"] is not None else ""
        where = f" (charter {row['charter']})" if several else ""
        if row["not_checked"] is not None:
            yield f"      rule {row['index']}{named}{where}: not checked ({row['not_checked']})"
        else:
            yield f"      rule {row['index']}{named}{where}: {row['scoped']} scoped, {row['short']} short"


def _by_flag(findings: list[dict[str, Any]]) -> Iterable[str]:
    for flag in FLAGS:
        found = [x for x in findings if x["flag"] == flag]
        if not found:
            continue
        yield ""
        yield f"{flag}. {FLAGS[flag]} ({len(found)})"
        for x in found:
            el = x["element"]
            who = f"{el['type']} {el['name'] or '(no name)'} ({el['id']})" if el else "the world"
            yield f"  - {who}: {x['reason']}"
            if x["evidence"]:
                yield "    " + "; ".join(f"{k}: {_say(v)}" for k, v in x["evidence"].items())


def render_prose(report: Report) -> str:
    """The report a person reads: counts first, the findings by flag, what was checked, what could not be."""
    return "\n".join(_lines(report)) + "\n"


# ---------------------------------------------------------------------------
# The packet: the findings as work items (the ``packet`` extension profile, dist.36)
# ---------------------------------------------------------------------------


def _sentence(text: str) -> str:
    text = text.strip()
    return text if not text or text[-1] in ".!?" else text + "."


def _packet_bytes(entries: list[dict[str, str]], source: dict[str, Any], producer: dict[str, str]) -> int:
    ext = {"x_packet_elements": entries, "x_packet_source": source, "x_packet_producer": producer}
    return len(json.dumps(ext, ensure_ascii=True, separators=(",", ":")))


def packets(
    report: Report, *, server: str | None = None, now: _dt.datetime | None = None, cap: int = PACKET_CAP
) -> list[dict[str, Any]]:
    """The report's findings as work packets: a list of Relations (``type: relation``, supertype
    ``Work item``, subtype ``open``, no ``id``) in the ``packet`` profile's shape. One entry per
    element in ``x_packet_elements`` (``{type, id, reason}``, first in flag order; an element with
    several findings has their reasons joined), the same ids on the Relation's typed link fields
    where it has one for the type, ``x_packet_source`` ``{server, world}`` (``server`` is the API
    base the world was read from, ``None`` for a folder) and ``x_packet_producer``. Only the
    findings that are facts about the world with an element go in (not ``kind: "message"``, not
    a finding on the world itself). Empty on a clean run; split past ``cap`` bytes of the three
    ``x_packet_*`` keys, each part complete and named ``(i of n)``."""
    reasons: dict[tuple[str, str], list[str]] = {}
    for f in report.to_look_at:
        el = f.get("element")
        if not el or not isinstance(el.get("id"), str) or not isinstance(el.get("type"), str):
            continue
        reasons.setdefault((el["type"], el["id"]), []).append(_sentence(f["reason"]))
    if not reasons:
        return []
    entries = [{"type": t, "id": i, "reason": " ".join(rs)} for (t, i), rs in reasons.items()]
    source: dict[str, Any] = {"server": server, "world": report.world.get("id")}
    producer = {"tool": PACKET_TOOL, "version": __version__}
    parts: list[list[dict[str, str]]] = [[]]
    for e in entries:
        if parts[-1] and _packet_bytes([*parts[-1], e], source, producer) > cap:
            parts.append([])
        parts[-1].append(e)
    day = (now or _dt.datetime.now(_dt.UTC)).date().isoformat()
    world_name = report.world.get("name") or "this world"
    out: list[dict[str, Any]] = []
    for i, part in enumerate(parts, 1):
        suffix = f" ({i} of {len(parts)})" if len(parts) > 1 else ""
        body: dict[str, Any] = {
            "type": "relation",
            "supertype": "Work item",
            "subtype": "open",
            "name": f"Doctor's findings, {day}{suffix}",
            "description": (
                f"{len(part)} of {len(entries)} elements to look at in {world_name}, from the doctor's run on {day}"
                f" ({len(report.ran)} flags ran, {len(report.not_run)} could not)."
            ),
        }
        for e in part:
            field_name = _RELATION_FIELD.get(e["type"])
            if field_name:
                body.setdefault(field_name, []).append(e["id"])
        body["x_packet_elements"] = part
        body["x_packet_source"] = dict(source)
        body["x_packet_producer"] = dict(producer)
        out.append(body)
    return out


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="python -m onlyworlds.doctor", description=(__doc__ or "").splitlines()[0])
    ap.add_argument("folder", nargs="?", type=Path, help="a world folder (holds world.json and elements/)")
    ap.add_argument(
        "--api",
        action="store_true",
        help="check the world of the key in OW_API_KEY or ONLYWORLDS_API_KEY (PIN: OW_API_PIN or ONLYWORLDS_API_PIN)",
    )
    ap.add_argument("--base-url", default=API_BASE, help=f"the API to read (default {API_BASE})")
    ap.add_argument("--json", action="store_true", help="print the JSON report instead of the prose one")
    ap.add_argument(
        "--packet",
        action="store_true",
        help="print the findings as work packets (the packet extension profile), a JSON array",
    )
    ap.add_argument("--days", type=int, default=14, help="flag 6a: a stub older than this many days (default 14)")
    ap.add_argument("--changes", type=int, default=50, help="flag 8: more changes than this (default 50)")
    args = ap.parse_args(argv)
    if (args.folder is None) == (not args.api):
        print("give a world folder or --api, one of the two", file=sys.stderr)
        return 2
    if args.json and args.packet:
        print("--json or --packet, one of the two", file=sys.stderr)
        return 2

    if args.api:
        key = os.environ.get("OW_API_KEY") or os.environ.get("ONLYWORLDS_API_KEY")
        if not key:
            print(
                "--api reads the key from OW_API_KEY or ONLYWORLDS_API_KEY (the PIN from OW_API_PIN or "
                "ONLYWORLDS_API_PIN); neither key variable is set",
                file=sys.stderr,
            )
            return 2
        pin = os.environ.get("OW_API_PIN") or os.environ.get("ONLYWORLDS_API_PIN") or None
        client = Client(key, pin, base_url=args.base_url)
        try:
            report = doctor_api(client, days=args.days, changes=args.changes)
        except (ApiError, ConnectionError, ValueError) as exc:
            print(f"nothing could be read: {exc}", file=sys.stderr)
            return 2
    else:
        if not args.folder.is_dir():
            print(f"{args.folder}: not a directory", file=sys.stderr)
            return 2
        folder = read_folder(args.folder)
        if folder.world is None and not folder.all_elements():
            print(f"{args.folder}: nothing could be read (no world.json, no elements)", file=sys.stderr)
            return 2
        report = doctor_folder(folder, days=args.days, changes=args.changes)

    if args.json:
        print(json.dumps(report.as_dict(), ensure_ascii=True, indent=2))
    elif args.packet:
        server = args.base_url.rstrip("/") if args.api else None
        print(json.dumps(packets(report, server=server), ensure_ascii=True, indent=2))
    else:
        sys.stdout.write(render_prose(report))
    return report.exit_code


if __name__ == "__main__":
    sys.exit(main())

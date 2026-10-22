"""Read a LegendKeeper project into a world folder through LegendKeeper's own API: read-only, no AI.

    LEGENDKEEPER_API_KEY=lk_... python -m onlyworlds.legendkeeper --project ID OUT-DIR [--plan]
        [--key-file PATH] [--map TAG=TYPE ...] [--include-hidden] [--include-secrets]

or ``import_legendkeeper(ApiSource(key), project_id, out_dir, ...)``. The key is the person's own
(Project Settings, Developers, API Keys; LegendKeeper requires the project owner to be on a paid
plan), read from ``LEGENDKEEPER_API_KEY`` or the file ``--key-file`` names. It is sent as
``Authorization: Bearer`` and nowhere else: never stored, never printed, never written into the
folder or the report. ``--plan`` reads the project and prints what would become what, and writes
nothing. OUT-DIR must not exist yet (or be empty): a folder is written whole, once.

Reading and converting are apart. A ``Source`` answers ``get(path, params)`` with the decoded JSON
of one GET below ``https://www.legendkeeper.com/api/v3``: ``ApiSource`` asks the live API (GET only,
paced on ``x-ratelimit-remaining`` and ``x-ratelimit-reset``, a 429's ``Retry-After`` honoured),
``RecordedSource`` answers from recorded replies (the tests). ``read_project`` walks a source into
a ``Snapshot``; the converter reads only the snapshot.

**Observed** (Boss, 2026-10-22, live on a real project; the recorded answers are this package's
test fixtures): the tree as one flat list of resources (``id``, ``name``, ``parentId``, ``tags``,
``aliases``, ``isHidden``, ``documents``), a resource's documents typed ``blank``, ``page``, ``map``
or ``time``; a page's blocks (``heading``, ``paragraph``, ``infobox``, ``secret``, ``table``) and
runs (marks, ``link``, ``mention``); ``keyValue`` and titled ``resourceLink`` rows in an infobox and
on the sidebar; a timeline's lanes and events, ``start``/``end`` in minutes since the calendar's
epoch with ``formattedStart``/``formattedEnd``; the rate-limit headers. **Believed** from
LegendKeeper's OpenAPI document (3.0.0, read 2026-10-17), not yet seen on the wire: the paths; the
other block and property kinds' shapes; cursor paging of resources and events; that a ``blank``
document is empty (the first write converts it); that a key below project admin sees only
resources reachable through non-hidden ancestors, so a hidden resource hides its subtree; that a
timeline's events include those of the timelines it chains (``sourceUri`` names their owner). A
real worldbuilder's project is the walk still to come.

What becomes what:

- **A resource becomes an element.** Its type is a tag equal to one of the 22 type names (any
  case), or a tag ``--map TAG=TYPE`` names; never a guess. A resource whose tags name no type, or
  name two, becomes a Narrative with supertype ``legendkeeper`` (the report lists the tags
  ``--map`` could use, and the two-type ones). ``name`` is its name; its page documents' blocks,
  as Markdown, its ``description`` (each page under ``## <document name>`` when it has more than
  one; a first heading equal to the name is left out). ``x_legendkeeper_id`` is the resource's
  id, ``x_legendkeeper_tags`` and ``x_legendkeeper_aliases`` its tags and aliases,
  ``x_legendkeeper_parent`` the element id of the resource it sits under; a Location under a
  Location also gets ``parent_location`` (an Institution under an Institution,
  ``parent_institution``). The resource's own picture is ``image_url``.
- **Blocks to Markdown**: headings, paragraphs and runs (bold, italic, strike, code, links; other
  marks read as plain text and are counted), bullet, ordered and task lists, tables, quotes,
  callouts (``> [!tone]``), code, rules, expand blocks (their title in bold), layout columns one
  after another, an image as ``![alt](url)``, an embed as its URL, a map block as a line naming
  the map. A mention becomes its display text (what LegendKeeper's own plain text shows), and its
  target, when it is an element of the folder, joins ``x_legendkeeper_mentions`` (element ids, in
  order, once each). An ``unsupported`` block (content LegendKeeper's public model cannot express)
  has nothing to read and is counted.
- **Properties** (the sidebar, an infobox's rows, and ``keyValue``, ``resourceLink`` and
  ``resourceCollection`` blocks in a page, which are data, not prose): a ``keyValue`` row whose key,
  lowercased with spaces as underscores, is a field of the element's type becomes that field when
  the value fits its kind (text; a whole number for an integer; mentions of elements of the
  linked type for a link); else it is kept as ``x_legendkeeper_<key>`` and listed in the report. A
  Narrative made from an untyped resource keeps every key as an extension. A titled
  ``resourceLink`` list (or a ``resourceCollection`` of picked items) whose title names a link
  field of the element's type, and whose targets are of that field's type, becomes that field;
  otherwise each target becomes a **Relation** element named by the title, its source on
  ``actor`` (a Character) or on Relation's field for the source's type, its target on Relation's
  field for the target's type, and ``x_legendkeeper_source``/``x_legendkeeper_target`` holding the
  two element ids so the direction is kept. A ``textField`` property whose title names a text
  field fills it; images go to ``image_url`` while it is unset; meters, embeds, maps, filtered
  collections and kinds not known here are kept as ``x_legendkeeper_<title>`` and listed.
- **A timeline** (a ``time`` document) gives one Event per event or note: its name, the raw
  minutes and the formatted string as ``x_legendkeeper_start``/``x_legendkeeper_end``
  (``{"minutes": ..., "formatted": ...}``), ``x_legendkeeper_calendar`` the calendar's id,
  ``x_legendkeeper_lane`` its lane's name, ``x_legendkeeper_timeline`` the document's name,
  ``x_legendkeeper_parent`` the resource it belongs to. ``start_date`` and ``end_date`` are left
  unset: the unit is the world's own time system, and converting minutes into it is a later step
  that needs the world's time settings named. Placeholders are layout and are counted.
- **Hidden** resources (and what sits under them), documents, properties and events, and
  ``secret`` blocks, are omitted by default and counted: the safe side for a player-facing world.
  ``--include-hidden`` and ``--include-secrets`` take them in (a secret as ``> [!secret]``).
  Hidden content is never fetched unless asked for.
- **Not imported**, named in the report with their resource: ``map`` documents (features are not
  read yet) and ``board`` documents. ``blank`` documents are empty and counted. Not kept, named in
  the report: icons, sibling order, timestamps, lock state, permissions, banners, event colours
  and icons, and the server's computed event dates (they follow from the minutes and calendar).

**Ids are UUIDv5** in ``LEGENDKEEPER_NAMESPACE``: of ``legendkeeper:<project id>:<resource id>`` for
a resource, ``legendkeeper:<project id>:event:<event id>`` for an event, and
``legendkeeper:<project id>:link:<resource id>:<list id>:<item id>`` for a Relation (a kind word,
since LegendKeeper lets a client choose 8- or 24-character ids for resources and events alike). A
second import of the same project finds the same elements. ``world.json``: ``id`` UUIDv5 of
``legendkeeper:<project id>``, ``name`` the project's name, ``producer`` ``{"tool": "onlyworlds",
"version": ..., "input": "legendkeeper-api"}`` (``PRODUCER_INPUT``; the word awaits the folder
spec's list of inputs, and a reader never refuses an unknown word), ``format_version`` this
package's.

The report (``ImportReport``, printed at the end of a run and by ``--plan``) names what became what
with counts and how each type was decided, every key not placed (element, key, why, the extension
it was kept as), every titled link kept as Relations (by title, with counts), every link or mention
whose target is not in the folder, what was omitted and why, the documents not imported, every
answer that could not be read, and anything else read past. Nothing from the source is dropped
without a line in it.

From the command line: exit 0 written (or planned), 2 on bad arguments (no key, a ``--map`` that
names no type, an OUT-DIR that is not empty) or a project that cannot be read (the key refused, the
plan gate, no such project); the error names the call and LegendKeeper's error code, never the key.
"""

from __future__ import annotations

import argparse
import copy
import io
import os
import re
import sys
import time
import urllib.parse
import uuid
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from ._schema import ELEMENT_TYPES, FIELD_KINDS, LINK_TARGETS
from ._version import __version__
from .errors import parse_retry_after
from .folder import FORMAT_VERSION, write_folder
from .http import Response, Transport, UrllibTransport

__all__ = [
    "API_BASE",
    "EXT_PREFIX",
    "KEY_ENV",
    "LEGENDKEEPER_NAMESPACE",
    "PRODUCER_INPUT",
    "ApiSource",
    "ImportReport",
    "NotImported",
    "Omitted",
    "RecordedSource",
    "Snapshot",
    "Source",
    "SourceError",
    "Typed",
    "Unplaced",
    "Unresolved",
    "import_legendkeeper",
    "main",
    "read_project",
]

#: The ``producer.input`` word for this door; new to the folder spec's list.
PRODUCER_INPUT = "legendkeeper-api"

#: The namespace every id this door mints is UUIDv5 in. Fixed for good: changing it would give
#: every element of every re-imported project a new id.
LEGENDKEEPER_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "https://onlyworlds.com/ns/legendkeeper")

#: LegendKeeper's API v3; every path below is relative to it.
API_BASE = "https://www.legendkeeper.com/api/v3"

#: Where the command line reads the key from when no ``--key-file`` is given.
KEY_ENV = "LEGENDKEEPER_API_KEY"

#: Every extension key this door writes starts with this.
EXT_PREFIX = "x_legendkeeper_"

#: The supertype a Narrative made from an untyped resource carries.
UNTYPED_SUPERTYPE = "legendkeeper"

#: Resources and events per page (the API's maximum).
PAGE_SIZE = 100

#: The longest the client waits on one rate-limit pause, in seconds.
MAX_WAIT = 600.0

_USER_AGENT = f"onlyworlds-python/{__version__} (legendkeeper door; read-only)"

_OWN = (
    "id",
    "parent",
    "tags",
    "aliases",
    "mentions",
    "body",
    "start",
    "end",
    "calendar",
    "lane",
    "timeline",
    "event_type",
    "uri",
    "source",
    "target",
)
#: The door's own extension keys; a property's key never takes one of them.
_RESERVED = frozenset(f"{EXT_PREFIX}{k}" for k in _OWN)

#: What a resource or event carries that the folder does not keep (one report line).
_NOT_KEPT = (
    "icons (iconGlyph, iconColor, iconShape, iconSize), sibling order (rank), timestamps, lock state, "
    "permissions, banners, event colours and icons, and the server's computed event dates "
    "(startDate, endDate: they follow from the minutes and the calendar)"
)

#: type -> {lowercased field name: field name}, so a key ``str`` finds ``STR``.
_FIELD_BY_LOWER: dict[str, dict[str, str]] = {t: {f.lower(): f for f in kinds} for t, kinds in FIELD_KINDS.items()}

#: target type -> Relation's multi-link field for it (schema order, the first one wins).
_RELATION_FIELD_FOR: dict[str, str] = {}
for _f, _kind in FIELD_KINDS["relation"].items():
    if _kind == "multi_link":
        _RELATION_FIELD_FOR.setdefault(LINK_TARGETS["relation"][_f], _f)

#: An element type whose own parent field takes a parent of the same type.
_PARENT_FIELD: dict[str, str] = {"location": "parent_location", "institution": "parent_institution"}

_INT = re.compile(r"\s*-?\d+\s*")
_LK_URI = re.compile(r"^lk://resources/(?P<rid>[^/\s]+)(?:/docs/(?P<did>[^/\s]+))?")
_SEPARATORS = re.compile(r"[\s,;]*")
_PLAIN_MARKS = ("underline", "sub", "sup", "color", "highlight")


def _norm(name: str) -> str:
    """A key or title lowercased, whitespace runs as underscores: the name a field is compared to."""
    return re.sub(r"\s+", "_", name.strip().lower())


def _uuid(key: str) -> str:
    return str(uuid.uuid5(LEGENDKEEPER_NAMESPACE, key))


def _seg(value: str) -> str:
    return urllib.parse.quote(str(value), safe="")


# ---------------------------------------------------------------------------
# Sources: where the answers come from
# ---------------------------------------------------------------------------


class SourceError(Exception):
    """A GET that gave no usable answer: its path, the HTTP status, LegendKeeper's error code."""

    def __init__(self, path: str, status: int | None, code: str | None, message: str) -> None:
        head = f"GET {path}: " + (f"{status}" if status is not None else "no answer")
        super().__init__(head + (f" {code}" if code else "") + (f": {message}" if message else ""))
        self.path = path
        self.status = status
        self.code = code
        self.message = message


class Source(Protocol):
    """One GET below the API base, answered with its decoded JSON; ``SourceError`` when there is none."""

    def get(self, path: str, params: Mapping[str, str] | None = None) -> Any: ...


class RecordedSource:
    """Answers from recorded replies, keyed by path (``/projects/<id>/resources``), with
    ``?cursor=<cursor>`` appended for a later page. The page size is not part of the key.

    ``calls`` lists every key asked for, in order. A key with no recorded answer is a
    ``SourceError`` (status 404, code ``NOT_RECORDED``).
    """

    def __init__(self, answers: Mapping[str, Any]) -> None:
        self.answers = dict(answers)
        self.calls: list[str] = []

    def get(self, path: str, params: Mapping[str, str] | None = None) -> Any:
        cursor = (params or {}).get("cursor")
        key = path + (f"?cursor={cursor}" if cursor else "")
        self.calls.append(key)
        if key not in self.answers:
            raise SourceError(path, 404, "NOT_RECORDED", "no recorded answer")
        return copy.deepcopy(self.answers[key])


class ApiSource:
    """The live API: GET only, ``Authorization: Bearer <key>``, stdlib ``urllib`` (no dependency).

    After an answer whose ``x-ratelimit-remaining`` is 0 it waits until ``x-ratelimit-reset`` (a
    Unix time). A 429 (and a 502, 503 or 504) is retried after its ``Retry-After``, else after the
    reset, else after a doubling pause; ``attempts`` counts every try. Each pause is capped at
    ``MAX_WAIT``. The key is held privately: not in ``repr``, not in any error.
    """

    def __init__(
        self,
        key: str,
        *,
        base: str = API_BASE,
        transport: Transport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.time,
        timeout: float = 60.0,
        attempts: int = 5,
    ) -> None:
        if not isinstance(key, str) or not key.strip():
            raise ValueError("the LegendKeeper key is empty")
        self.__key = key.strip()
        self.base = base.rstrip("/")
        self.transport: Transport = transport if transport is not None else UrllibTransport()
        self.sleep = sleep
        self.clock = clock
        self.timeout = timeout
        self.attempts = max(1, attempts)

    def __repr__(self) -> str:
        return f"ApiSource(base={self.base!r})"

    def get(self, path: str, params: Mapping[str, str] | None = None) -> Any:
        query = urllib.parse.urlencode(sorted((params or {}).items()))
        url = self.base + path + (f"?{query}" if query else "")
        headers = {"Authorization": f"Bearer {self.__key}", "Accept": "application/json", "User-Agent": _USER_AGENT}
        for attempt in range(self.attempts):
            last = attempt == self.attempts - 1
            try:
                r = self.transport("GET", url, headers, None, self.timeout)
            except Exception as exc:  # no answer at all: timeouts, resets, DNS
                if last:
                    raise SourceError(path, None, None, self._scrub(f"{type(exc).__name__}: {exc}")) from None
                self.sleep(self._backoff(attempt))
                continue
            if r.status == 429 or r.status in (502, 503, 504):
                if last:
                    raise self._error(path, r)
                wait = parse_retry_after(r.header("Retry-After"))
                if wait is None:
                    wait = self._until_reset(r)
                self.sleep(min(MAX_WAIT, wait if wait is not None else self._backoff(attempt)))
                continue
            if not 200 <= r.status < 300:
                raise self._error(path, r)
            if r.header("x-ratelimit-remaining") == "0":
                wait = self._until_reset(r)
                if wait:
                    self.sleep(min(MAX_WAIT, wait))
            try:
                return r.json()
            except ValueError:
                raise SourceError(path, r.status, None, "the answer is not JSON") from None
        raise AssertionError("unreachable")  # pragma: no cover

    def _scrub(self, text: str) -> str:
        return text.replace(self.__key, "***")

    @staticmethod
    def _backoff(attempt: int) -> float:
        return float(min(30, 2**attempt))

    def _until_reset(self, r: Response) -> float | None:
        raw = r.header("x-ratelimit-reset")
        try:
            reset = float(raw) if raw is not None else None
        except ValueError:
            return None
        if reset is None:
            return None
        if reset > 1e11:  # milliseconds, not seconds
            reset /= 1000.0
        return max(0.0, reset - self.clock())

    def _error(self, path: str, r: Response) -> SourceError:
        code: str | None = None
        message = ""
        try:
            body = r.json()
        except ValueError:
            body = None
        if isinstance(body, dict):
            code = body.get("code") if isinstance(body.get("code"), str) else None
            message = str(body.get("message") or "")[:200]
        return SourceError(path, r.status, code, self._scrub(message))


# ---------------------------------------------------------------------------
# Reading: a source walked into a snapshot
# ---------------------------------------------------------------------------


@dataclass
class Snapshot:
    """What ``read_project`` read: the converter reads nothing else."""

    project_id: str
    project: dict[str, Any]
    #: the tree, every row as listed (hidden ones too)
    resources: list[dict[str, Any]]
    #: resource id -> its ``getResource`` answer (documents with ``isHidden``, properties, picture)
    full: dict[str, dict[str, Any]] = field(default_factory=dict)
    #: page document id -> its blocks answer
    blocks: dict[str, dict[str, Any]] = field(default_factory=dict)
    #: time document id -> its lanes / its events
    lanes: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    events: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    #: every answer that could not be read, one line each
    unread: list[str] = field(default_factory=list)


def _paged(source: Source, path: str, *, sized: bool) -> list[dict[str, Any]]:
    """Every row of a cursor-paged list (``{data, hasMore, nextCursor}``)."""
    out: list[dict[str, Any]] = []
    cursor: str | None = None
    seen: set[str] = set()
    while True:
        params: dict[str, str] = {"limit": str(PAGE_SIZE)} if sized else {}
        if cursor:
            params["cursor"] = cursor
        page = source.get(path, params or None)
        if not isinstance(page, dict):
            raise SourceError(path, None, None, "the answer is not a list page")
        out += [row for row in page.get("data") or [] if isinstance(row, dict)]
        nxt = page.get("nextCursor")
        if not page.get("hasMore") or not isinstance(nxt, str) or not nxt:
            return out
        if nxt in seen:
            raise SourceError(path, None, None, f"the cursor {nxt!r} came back twice")
        seen.add(nxt)
        cursor = nxt


def _split_hidden(resources: Iterable[dict[str, Any]], include_hidden: bool) -> dict[str, str]:
    """resource id -> ``kept``, ``hidden`` (its own mark) or ``under`` (a hidden ancestor)."""
    rows = {r["id"]: r for r in resources}
    if include_hidden:
        return dict.fromkeys(rows, "kept")
    state: dict[str, str] = {}
    for rid, row in rows.items():
        if row.get("isHidden"):
            state[rid] = "hidden"
            continue
        verdict, seen, cur = "kept", {rid}, row.get("parentId")
        while isinstance(cur, str) and cur in rows and cur not in seen:
            if rows[cur].get("isHidden"):
                verdict = "under"
                break
            seen.add(cur)
            cur = rows[cur].get("parentId")
        state[rid] = verdict
    return state


def read_project(source: Source, project_id: str, *, include_hidden: bool = False) -> Snapshot:
    """Walk a project: the project, its whole tree, then each kept resource, its page blocks and
    its timelines. Hidden content is not fetched unless ``include_hidden``.

    The project and the tree must answer (a ``SourceError`` otherwise); a resource, a page or a
    timeline that does not is listed in ``unread`` and the walk goes on.
    """
    root = f"/projects/{_seg(project_id)}"
    project = source.get(root)
    if not isinstance(project, dict):
        raise SourceError(root, None, None, "the answer is not a project")
    resources = [r for r in _paged(source, f"{root}/resources", sized=True) if isinstance(r.get("id"), str)]
    snap = Snapshot(project_id, project, resources)
    state = _split_hidden(resources, include_hidden)
    for row in resources:
        rid = row["id"]
        if state[rid] != "kept":
            continue
        rpath = f"{root}/resources/{_seg(rid)}"
        try:
            full = source.get(rpath)
        except SourceError as exc:
            snap.unread.append(f"resource {row.get('name')!r} ({rid}): {exc}; kept from the tree without its content")
            continue
        if not isinstance(full, dict):
            snap.unread.append(f"resource {row.get('name')!r} ({rid}): not a resource; kept from the tree")
            continue
        snap.full[rid] = full
        for doc in full.get("documents") or []:
            if not isinstance(doc, dict) or not isinstance(doc.get("id"), str):
                continue
            if doc.get("isHidden") and not include_hidden:
                continue
            did, dtype = doc["id"], doc.get("type")
            dpath = f"{rpath}/docs/{_seg(did)}"
            where = f"resource {row.get('name')!r}, document {doc.get('name')!r} ({did})"
            try:
                if dtype == "page":
                    blocks = source.get(f"{dpath}/blocks")
                    if isinstance(blocks, dict):
                        snap.blocks[did] = blocks
                    else:
                        snap.unread.append(f"{where}: the blocks answer is not a document")
                elif dtype == "time":
                    snap.lanes[did] = _paged(source, f"{dpath}/lanes", sized=False)
                    snap.events[did] = _paged(source, f"{dpath}/events", sized=True)
            except SourceError as exc:
                snap.unread.append(f"{where}: {exc}")
    return snap


# ---------------------------------------------------------------------------
# The report
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Typed:
    """How one resource's type was decided."""

    name: str
    resource: str
    type: str
    #: ``tag '<tag>'``, ``--map <tag>=<type>``, ``untyped`` or ``ambiguous: ...``
    by: str


@dataclass(frozen=True)
class Unplaced:
    """A key (or a property) not placed on a field, kept as ``kept_as``."""

    element: str
    key: str
    why: str
    kept_as: str


@dataclass(frozen=True)
class Unresolved:
    """A link or mention whose target is not an element of the folder."""

    element: str
    #: ``link '<title>'``, ``mention '<text>'``, ``key '<key>'`` or ``event uri``
    where: str
    #: the LegendKeeper resource id
    target: str
    why: str


@dataclass(frozen=True)
class NotImported:
    """A document this door does not import."""

    kind: str
    resource: str
    document: str


@dataclass
class Omitted:
    """What was left out on the safe side, each opt-in by a flag."""

    hidden_resources: int = 0
    under_hidden: int = 0
    hidden_documents: int = 0
    hidden_properties: int = 0
    hidden_events: int = 0
    secret_blocks: int = 0


@dataclass
class ImportReport:
    project: str
    world: dict[str, Any]
    counts: dict[str, int] = field(default_factory=dict)
    typed: list[Typed] = field(default_factory=list)
    unplaced: list[Unplaced] = field(default_factory=list)
    #: titled link -> Relation elements made for it
    relations: dict[str, int] = field(default_factory=dict)
    unresolved: list[Unresolved] = field(default_factory=list)
    omitted: Omitted = field(default_factory=Omitted)
    not_imported: list[NotImported] = field(default_factory=list)
    unread: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    #: tags on the resources kept untyped -> how many carry each: what ``--map`` could type
    untyped_tags: dict[str, int] = field(default_factory=dict)
    #: where the folder was written; None for a plan
    out: Path | None = None

    @property
    def total(self) -> int:
        return sum(self.counts.values())

    def render(self) -> str:
        """The report in prose, one finding a line."""
        lines: list[str] = []
        name = self.world.get("name", self.project)
        by_type = ", ".join(f"{t} {n}" for t, n in sorted(self.counts.items()))
        lines.append(f"LegendKeeper project {name!r} ({self.project}): {self.total} elements ({by_type or 'none'}).")
        if self.typed:
            lines.append("How each resource's type was decided:")
            groups: dict[str, dict[str, int]] = {}
            for t in self.typed:
                how = "ambiguous" if t.by.startswith("ambiguous") else t.by
                groups.setdefault(t.type, {})
                groups[t.type][how] = groups[t.type].get(how, 0) + 1
            for etype, hows in sorted(groups.items()):
                parts = ", ".join(f"{h} {n}" for h, n in sorted(hows.items()))
                extra = f" (supertype {UNTYPED_SUPERTYPE})" if etype == "narrative" and "untyped" in hows else ""
                lines.append(f"  - {etype} {sum(hows.values())}: {parts}{extra}")
            for t in self.typed:
                if t.by.startswith("ambiguous"):
                    lines.append(f"  - {t.name!r} kept untyped: {t.by}")
        if self.untyped_tags:
            listed = ", ".join(f"{t!r} {n}" for t, n in sorted(self.untyped_tags.items()))
            lines.append(f"Tags on the untyped resources (--map TAG=TYPE types them): {listed}.")
        if self.unplaced:
            lines.append(f"Keys not placed on a field ({len(self.unplaced)}), kept as extensions:")
            lines += [f"  - {u.element!r} / {u.key!r}: {u.why}; kept as {u.kept_as}" for u in self.unplaced]
        if self.relations:
            listed = ", ".join(f"{t!r} {n}" for t, n in sorted(self.relations.items()))
            lines.append(
                f"Titled links with no field, kept as Relation elements ({sum(self.relations.values())}): {listed}."
            )
        if self.unresolved:
            lines.append(f"Links and mentions whose target is not in the folder ({len(self.unresolved)}):")
            lines += [f"  - {u.element!r}, {u.where}: {u.target}: {u.why}" for u in self.unresolved]
        o = self.omitted
        omitted = [
            (o.hidden_resources, "hidden resource", "--include-hidden"),
            (o.under_hidden, "resource under a hidden one", "--include-hidden"),
            (o.hidden_documents, "hidden document", "--include-hidden"),
            (o.hidden_properties, "hidden property", "--include-hidden"),
            (o.hidden_events, "hidden timeline event", "--include-hidden"),
            (o.secret_blocks, "secret block", "--include-secrets"),
        ]
        said = [f"{n} {what}{'' if n == 1 else 's'} ({flag})" for n, what, flag in omitted if n]
        if said:
            lines.append("Omitted, on the safe side: " + "; ".join(said) + ".")
        if self.not_imported:
            lines.append(f"Documents not imported ({len(self.not_imported)}):")
            lines += [f"  - {n.kind} {n.document!r} on {n.resource!r}" for n in self.not_imported]
        if self.unread:
            lines.append(f"Could not read ({len(self.unread)}):")
            lines += [f"  - {u}" for u in self.unread]
        if self.notes:
            lines.append(f"Notes ({len(self.notes)}):")
            lines += [f"  - {n}" for n in self.notes]
        lines.append(f"Wrote {self.out}." if self.out is not None else "Plan only: nothing written.")
        return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Converting: a snapshot into element bodies
# ---------------------------------------------------------------------------


@dataclass
class _Item:
    """One resource's element being built."""

    etype: str
    eid: str
    name: str
    lk_id: str
    typed: bool
    row: dict[str, Any]
    fields: dict[str, Any] = field(default_factory=dict)
    ext: dict[str, Any] = field(default_factory=dict)
    taken: set[str] = field(default_factory=set)
    mentions: list[str] = field(default_factory=list)


def _plain(runs: Any) -> str:
    """Runs as plain text, with no side effects (for comparing a heading to a name)."""
    out: list[str] = []
    for run in runs or []:
        if isinstance(run, dict):
            m = run.get("mention")
            out.append((m.get("text") or m.get("name") or "") if isinstance(m, dict) else str(run.get("text") or ""))
    return "".join(out).strip()


def _quote(text: str, marker: str = "> ") -> str:
    return "\n".join(marker + line if line else marker.rstrip() for line in text.split("\n"))


class _Converter:
    def __init__(
        self, snap: Snapshot, type_map: Mapping[str, str], *, include_hidden: bool, include_secrets: bool
    ) -> None:
        self.snap = snap
        self.type_map = dict(type_map)
        self.include_hidden = include_hidden
        self.include_secrets = include_secrets
        self.report = ImportReport(project=snap.project_id, world={}, unread=list(snap.unread))
        self.rows = {r["id"]: r for r in snap.resources}
        self.state = _split_hidden(snap.resources, include_hidden)
        self.items: dict[str, _Item] = {}
        self.relations: list[dict[str, Any]] = []
        self.events: list[dict[str, Any]] = []
        self.event_ids: set[str] = set()
        self.marks: dict[str, int] = {}
        self.unsupported = 0
        self.unknown: dict[str, int] = {}
        self.map_blocks = 0
        self.blank = 0
        self.placeholders = 0
        self._unplaced_seen: set[Unplaced] = set()

    def _id(self, *parts: str) -> str:
        return _uuid(":".join(("legendkeeper", self.snap.project_id, *parts)))

    # -- pass 1: every element, with its type and id --------------------------

    def collect(self) -> None:
        untyped_tags: dict[str, int] = {}
        for row in self.snap.resources:
            rid = row["id"]
            st = self.state[rid]
            if st == "hidden":
                self.report.omitted.hidden_resources += 1
                continue
            if st == "under":
                self.report.omitted.under_hidden += 1
                continue
            tags = [t for t in row.get("tags") or [] if isinstance(t, str)]
            etype, by = self._type_of(tags)
            name = str(row.get("name") or "").strip() or f"Untitled ({rid})"
            item = _Item(
                etype, self._id(rid), name, rid, typed=by != "untyped" and not by.startswith("ambiguous"), row=row
            )
            if not item.typed:
                item.fields["supertype"] = UNTYPED_SUPERTYPE
                for t in tags:
                    untyped_tags[t] = untyped_tags.get(t, 0) + 1
            self.items[rid] = item
            self.report.typed.append(Typed(name, rid, etype, by))
        self.report.untyped_tags = untyped_tags

    def _type_of(self, tags: list[str]) -> tuple[str, str]:
        found: dict[str, str] = {}
        for tag in tags:
            low = tag.strip().lower()
            if low in self.type_map:
                found.setdefault(self.type_map[low], f"--map {low}={self.type_map[low]}")
            elif low in ELEMENT_TYPES:
                found.setdefault(low, f"tag {tag!r}")
        if len(found) == 1:
            ((etype, by),) = found.items()
            return etype, by
        if not found:
            return "narrative", "untyped"
        return "narrative", "ambiguous: its tags name " + " and ".join(sorted(found))

    # -- pass 2: fields, links, text, timelines -----------------------------

    def fill(self) -> None:
        for item in self.items.values():
            self._fill(item)

    def _fill(self, item: _Item) -> None:
        row = item.row
        full = self.snap.full.get(item.lk_id)
        item.taken |= _RESERVED
        item.ext[f"{EXT_PREFIX}id"] = item.lk_id
        parent_id = row.get("parentId")
        if isinstance(parent_id, str) and parent_id:
            parent = self.items.get(parent_id)
            if parent is not None:
                item.ext[f"{EXT_PREFIX}parent"] = parent.eid
                pfield = _PARENT_FIELD.get(item.etype)
                if pfield and parent.etype == item.etype:
                    item.fields[pfield] = parent.eid
            else:
                self.report.notes.append(f"{item.name!r}: its parent {parent_id} is not in the project's tree")
        for key in ("tags", "aliases"):
            values = [v for v in row.get(key) or [] if isinstance(v, str)]
            if values:
                item.ext[f"{EXT_PREFIX}{key}"] = values
        if full is None:
            return
        image = full.get("imageUrl")
        if isinstance(image, str) and image:
            item.fields["image_url"] = image

        docs = [d for d in full.get("documents") or [] if isinstance(d, dict)]
        pages = [d for d in docs if d.get("type") == "page" and (self.include_hidden or not d.get("isHidden"))]
        parts: list[str] = []
        for doc in docs:
            dtype, dname = doc.get("type"), str(doc.get("name") or "")
            if doc.get("isHidden") and not self.include_hidden:
                self.report.omitted.hidden_documents += 1
                continue
            if dtype == "page":
                answer = self.snap.blocks.get(doc.get("id", ""))
                if answer is None:
                    continue  # listed in unread
                blocks = [b for b in answer.get("blocks") or [] if isinstance(b, dict)]
                if blocks and blocks[0].get("kind") == "heading" and _plain(blocks[0].get("content")) == item.name:
                    blocks = blocks[1:]
                md = "\n\n".join(self._blocks(item, blocks))
                if md:
                    parts.append(f"## {dname}\n\n{md}" if len(pages) > 1 else md)
            elif dtype == "blank":
                self.blank += 1
            elif dtype == "time":
                self._timeline(item, doc)
            else:
                self.report.not_imported.append(NotImported(str(dtype or "unknown"), item.name, dname))
        for prop in full.get("properties") or []:
            if isinstance(prop, dict):
                self._property(item, prop)
        text = "\n\n".join(parts)
        if text:
            if "description" in item.fields:
                item.ext[f"{EXT_PREFIX}body"] = text
            else:
                item.fields["description"] = text

    # -- blocks ----------------------------------------------------------------

    def _blocks(self, item: _Item, blocks: Iterable[Any]) -> list[str]:
        out: list[str] = []
        for b in blocks:
            if isinstance(b, dict):
                chunk = self._block(item, b)
                if chunk:
                    out.append(chunk)
        return out

    def _children(self, item: _Item, b: dict[str, Any], sep: str = "\n\n") -> str:
        return sep.join(self._blocks(item, b.get("children") or []))

    def _block(self, item: _Item, b: dict[str, Any]) -> str | None:
        kind = b.get("kind")
        if kind == "paragraph":
            return self._runs(item, b.get("content")) or None
        if kind == "heading":
            text = self._runs(item, b.get("content"))
            level = b.get("level")
            n = min(6, max(1, level)) if isinstance(level, int) and not isinstance(level, bool) else 1
            return f"{'#' * n} {text}" if text else None
        if kind == "quote":
            inner = self._children(item, b)
            return _quote(inner) if inner else None
        if kind == "callout":
            inner = self._children(item, b)
            head = f"> [!{b.get('tone') or 'note'}]"
            return head + ("\n" + _quote(inner) if inner else "")
        if kind == "secret":
            if not self.include_secrets:
                self.report.omitted.secret_blocks += 1
                return None
            inner = self._children(item, b)
            return "> [!secret]" + ("\n" + _quote(inner) if inner else "")
        if kind == "code":
            return f"```{b.get('language') or ''}\n{b.get('text') or ''}\n```"
        if kind == "rule":
            return "---"
        if kind in ("bulletList", "orderedList", "taskList"):
            return self._list(item, b)
        if kind in ("listItem", "taskItem"):
            return self._list(item, {"kind": "taskList" if kind == "taskItem" else "bulletList", "children": [b]})
        if kind == "table":
            return self._table(item, b)
        if kind in ("tableRow", "tableCell", "layout", "layoutColumn"):
            return self._children(item, b) or None
        if kind == "expand":
            inner = self._children(item, b)
            title = str(b.get("title") or "").strip()
            head = f"**{title}**" if title else ""
            return "\n\n".join(p for p in (head, inner) if p) or None
        if kind == "textField":
            inner = self._children(item, b)
            title = str(b.get("title") or "").strip()
            head = f"**{title}**" if title and not b.get("isTitleHidden") else ""
            return "\n\n".join(p for p in (head, inner) if p) or None
        if kind == "image":
            url = b.get("url")
            alt = str(b.get("alt") or b.get("title") or "")
            return f"![{alt}]({url})" if isinstance(url, str) and url else None
        if kind == "embed":
            url = b.get("url")
            return url if isinstance(url, str) and url else None
        if kind == "meter":
            title = str(b.get("title") or "").strip()
            rows = [
                f"- {m.get('name') or 'value'}: {m.get('current')} / {m.get('max')}"
                for m in b.get("items") or []
                if isinstance(m, dict)
            ]
            return "\n\n".join(p for p in (f"**{title}**" if title else "", "\n".join(rows)) if p) or None
        if kind == "map":
            self.map_blocks += 1
            target = self.rows.get(str(b.get("resourceId") or ""))
            return f"Map: {target.get('name')}" if target is not None else "Map"
        if kind == "infobox":
            for row in b.get("rows") or []:
                if isinstance(row, dict):
                    self._property(item, row)
            return None
        if kind in ("keyValue", "resourceLink", "resourceCollection"):
            self._property(item, b)
            return None
        if kind == "unsupported":
            self.unsupported += 1
            return None
        self.unknown[str(kind)] = self.unknown.get(str(kind), 0) + 1
        text = self._runs(item, b.get("content")) if b.get("content") else ""
        return text or self._children(item, b) or None

    def _list(self, item: _Item, b: dict[str, Any]) -> str | None:
        lines: list[str] = []
        start = b.get("start")
        n: int = start if isinstance(start, int) and not isinstance(start, bool) else 1
        for child in b.get("children") or []:
            if not isinstance(child, dict):
                continue
            if child.get("kind") == "taskItem":
                marker = f"- [{'x' if child.get('checked') else ' '}] "
                body = self._runs(item, child.get("content"))
            else:
                if b.get("kind") == "orderedList":
                    marker = f"{n}. "
                    n += 1
                else:
                    marker = "- "
                body = self._children(item, child, sep="\n")
            first, *rest = body.split("\n")
            lines.append(marker + first)
            lines += [(" " * len(marker) + line) if line else "" for line in rest]
        return "\n".join(lines) or None

    def _table(self, item: _Item, b: dict[str, Any]) -> str | None:
        grid: list[list[str]] = []
        for row in b.get("children") or []:
            if isinstance(row, dict) and row.get("kind") == "tableRow":
                cells = []
                for cell in row.get("children") or []:
                    if isinstance(cell, dict):
                        text = "<br>".join(self._blocks(item, cell.get("children") or []))
                        cells.append(text.replace("|", "\\|").replace("\n", "<br>"))
                grid.append(cells)
        width = max((len(r) for r in grid), default=0)
        if not width:
            return None
        grid = [r + [""] * (width - len(r)) for r in grid]
        lines = ["| " + " | ".join(grid[0]) + " |", "| " + " | ".join(["---"] * width) + " |"]
        lines += ["| " + " | ".join(r) + " |" for r in grid[1:]]
        return "\n".join(lines)

    def _runs(self, item: _Item, runs: Any) -> str:
        out: list[str] = []
        for run in runs or []:
            if not isinstance(run, dict):
                continue
            if run.get("break"):
                out.append("\n")
                continue
            mention = run.get("mention")
            if isinstance(mention, dict):
                text = str(mention.get("text") or mention.get("name") or "")
                self._mention(item, mention, text)
                out.append(text)
                continue
            text = str(run.get("text") or "")
            if text:
                out.append(self._marked(text, run))
        return "".join(out).strip()

    def _marked(self, text: str, run: dict[str, Any]) -> str:
        for mark in _PLAIN_MARKS:
            if run.get(mark):
                self.marks[mark] = self.marks.get(mark, 0) + 1
        core = text.strip()
        if not core:
            return text
        lead, trail = text[: len(text) - len(text.lstrip())], text[len(text.rstrip()) :]
        if run.get("code"):
            core = f"`{core}`"
        else:
            if run.get("strike"):
                core = f"~~{core}~~"
            if run.get("italic"):
                core = f"*{core}*"
            if run.get("bold"):
                core = f"**{core}**"
        link = run.get("link")
        if isinstance(link, str) and link:
            core = f"[{core}]({link})"
        return lead + core + trail

    def _why_missing(self, rid: str) -> str:
        st = self.state.get(rid)
        if st == "hidden":
            return "the resource is hidden (omitted; --include-hidden takes it in)"
        if st == "under":
            return "the resource sits under a hidden one (omitted; --include-hidden takes it in)"
        return "no such resource in the project's tree"

    def _mention(self, item: _Item, mention: dict[str, Any], text: str) -> None:
        rid = str(mention.get("resourceId") or "")
        target = self.items.get(rid)
        if target is None:
            self.report.unresolved.append(Unresolved(item.name, f"mention {text!r}", rid, self._why_missing(rid)))
        elif target is not item and target.eid not in item.mentions:
            item.mentions.append(target.eid)

    # -- properties ----------------------------------------------------------

    def _unplaced(self, item: _Item, key: str, why: str, kept_as: str) -> None:
        u = Unplaced(item.name, key, why, kept_as)
        if u not in self._unplaced_seen:
            self._unplaced_seen.add(u)
            self.report.unplaced.append(u)

    def _keep(self, item: _Item, key: str, value: Any, why: str) -> None:
        """Keep a value as ``x_legendkeeper_<key>`` (``_2`` and on when taken) and report it."""
        base = f"{EXT_PREFIX}{_norm(key) or 'value'}"
        ext, n = base, 2
        while ext in item.taken:
            ext, n = f"{base}_{n}", n + 1
        item.taken.add(ext)
        item.ext[ext] = value
        self._unplaced(item, key, why, ext)

    def _property(self, item: _Item, prop: dict[str, Any]) -> None:
        if prop.get("isHidden") and not self.include_hidden:
            self.report.omitted.hidden_properties += 1
            return
        kind = prop.get("kind")
        title = str(prop.get("title") or "").strip()
        if kind == "keyValue":
            for row in prop.get("rows") or []:
                if isinstance(row, dict):
                    self._key_value(item, row)
        elif kind == "resourceLink" or (kind == "resourceCollection" and prop.get("items")):
            self._link(item, prop, title or ("Links" if kind == "resourceLink" else "Collection"))
        elif kind == "resourceCollection":
            self._keep(item, title or "collection", prop.get("filter"), "a collection chosen by a filter: not expanded")
        elif kind == "textField":
            self._text_field(item, title or "Text", "\n\n".join(self._blocks(item, prop.get("children") or [])))
        elif kind == "image":
            url = prop.get("url")
            if isinstance(url, str) and url and "image_url" not in item.fields:
                item.fields["image_url"] = url
            elif isinstance(url, str) and url:
                self._keep(item, title or "image", url, "image_url already holds the resource's picture")
        elif kind == "meter":
            values = [
                {"name": m.get("name"), "current": m.get("current"), "max": m.get("max")}
                for m in prop.get("items") or []
                if isinstance(m, dict)
            ]
            self._keep(item, title or "meter", values, "a meter has no field")
        elif kind == "embed":
            self._keep(item, title or "embed", prop.get("url"), "an embed has no field")
        elif kind == "map":
            target = self.items.get(str(prop.get("resourceId") or ""))
            where = {"resource": target.eid if target else prop.get("resourceId"), "document": prop.get("documentId")}
            self._keep(item, title or "map", where, "maps are not imported")
        elif kind == "unsupported":
            self.unsupported += 1
        else:
            self._keep(
                item, title or str(kind or "property"), prop, f"a property kind this door does not read ({kind})"
            )

    def _key_value(self, item: _Item, row: dict[str, Any]) -> None:
        key = str(row.get("key") or "").strip()
        runs = row.get("content")
        text = self._runs(item, runs) if runs else str(row.get("text") or "").strip()
        if not text:
            return  # a key with no value carries nothing
        if not item.typed:
            self._keep(item, key, text, "the resource's type is not known")
            return
        norm = _norm(key)
        fname = _FIELD_BY_LOWER[item.etype].get(norm)
        if fname is None:
            why = f"{item.etype} has no field {norm!r}"
        elif fname == "name":
            why = "the resource's name is the name"
        elif fname in item.fields:
            why = f"{fname} is already set"
        else:
            kind = FIELD_KINDS[item.etype][fname]
            if kind == "text":
                item.fields[fname] = text
                return
            if kind == "integer":
                if _INT.fullmatch(text):
                    item.fields[fname] = int(text)
                    return
                why = f"the value is not a whole number ({fname} is an integer)"
            else:
                target_type = LINK_TARGETS[item.etype][fname]
                ids = self._mentioned(runs)
                hits = [self.items.get(i) for i in ids or []]
                if not ids:
                    why = f"{fname} links a {target_type}; the value is not a list of mentions"
                elif any(h is None for h in hits):
                    why = "a resource it mentions is not in the folder"
                elif any(h is not None and h.etype != target_type for h in hits):
                    why = f"{fname} links a {target_type}; a resource it mentions is not one"
                elif kind == "single_link" and len(hits) > 1:
                    why = f"it mentions {len(hits)} resources; {fname} links one"
                else:
                    eids = list(dict.fromkeys(h.eid for h in hits if h is not None))
                    item.fields[fname] = eids[0] if kind == "single_link" else eids
                    return
        self._keep(item, key, text, why)

    @staticmethod
    def _mentioned(runs: Any) -> list[str] | None:
        """The resource ids a value's runs mention, when they are nothing but mentions and separators."""
        ids: list[str] = []
        for run in runs or []:
            if not isinstance(run, dict):
                return None
            m = run.get("mention")
            if isinstance(m, dict) and m.get("resourceId"):
                ids.append(str(m["resourceId"]))
            elif run.get("break") or _SEPARATORS.fullmatch(str(run.get("text") or "")):
                continue
            else:
                return None
        return ids or None

    def _text_field(self, item: _Item, title: str, text: str) -> None:
        if not text:
            return
        if not item.typed:
            self._keep(item, title, text, "the resource's type is not known")
            return
        fname = _FIELD_BY_LOWER[item.etype].get(_norm(title))
        if fname is not None and fname != "name" and FIELD_KINDS[item.etype][fname] == "text":
            if fname not in item.fields:
                item.fields[fname] = text
                return
            self._keep(item, title, text, f"{fname} is already set")
            return
        self._keep(item, title, text, f"{item.etype} has no text field {_norm(title)!r}")

    def _link(self, item: _Item, prop: dict[str, Any], title: str) -> None:
        hits: list[tuple[dict[str, Any], _Item]] = []
        for x in prop.get("items") or []:
            if not isinstance(x, dict) or not x.get("resourceId"):
                continue
            rid = str(x["resourceId"])
            target = self.items.get(rid)
            if target is None:
                self.report.unresolved.append(Unresolved(item.name, f"link {title!r}", rid, self._why_missing(rid)))
            else:
                hits.append((x, target))
        if not hits:
            return
        fname = _FIELD_BY_LOWER[item.etype].get(_norm(title)) if item.typed else None
        kind = FIELD_KINDS[item.etype].get(fname) if fname else None
        if fname is not None and kind in ("single_link", "multi_link"):
            target_type = LINK_TARGETS[item.etype][fname]
            eids = list(dict.fromkeys(t.eid for _, t in hits))
            if fname in item.fields:
                why = f"{fname} is already set"
            elif any(t.etype != target_type for _, t in hits):
                types = ", ".join(sorted({t.etype for _, t in hits}))
                why = f"{fname} links a {target_type} and the targets are {types}"
            elif kind == "single_link" and len(eids) > 1:
                why = f"{fname} links one and the list holds {len(eids)}"
            else:
                item.fields[fname] = eids[0] if kind == "single_link" else eids
                return
            self.report.notes.append(
                f"{item.name!r}: link {title!r} names the field {fname}, but {why}; kept as Relations"
            )
        list_id = str(prop.get("id") or title)
        for x, target in hits:
            self._relation(item, title, list_id, x, target)

    def _relation(self, item: _Item, title: str, list_id: str, x: dict[str, Any], target: _Item) -> None:
        fields: dict[str, Any] = {}
        if item.etype == "character":
            fields["actor"] = item.eid
        for end in (item, target) if item.etype != "character" else (target,):
            fname = _RELATION_FIELD_FOR.get(end.etype)
            if fname is None:
                self.report.notes.append(
                    f"Relation {title!r} from {item.name!r}: Relation has no field for a {end.etype}; "
                    f"{end.name!r} is in x_legendkeeper_source/target only"
                )
                continue
            links = fields.setdefault(fname, [])
            if end.eid not in links:
                links.append(end.eid)
        body: dict[str, Any] = {
            "type": "relation",
            "id": self._id("link", item.lk_id, list_id, str(x.get("id") or target.lk_id)),
            "name": title,
        }
        for fname in FIELD_KINDS["relation"]:
            if fname in fields:
                body[fname] = fields[fname]
        body[f"{EXT_PREFIX}source"] = item.eid
        body[f"{EXT_PREFIX}target"] = target.eid
        self.relations.append(body)
        self.report.relations[title] = self.report.relations.get(title, 0) + 1

    # -- timelines -----------------------------------------------------------

    def _timeline(self, item: _Item, doc: dict[str, Any]) -> None:
        did = str(doc.get("id"))
        events = self.snap.events.get(did)
        if events is None:
            return  # listed in unread
        lanes = {str(lane.get("id")): lane for lane in self.snap.lanes.get(did, [])}
        calendar = doc.get("calendarId")
        made = 0
        for ev in events:
            ev_id = ev.get("id")
            if not isinstance(ev_id, str) or ev_id in self.event_ids:
                continue  # an event of a chained timeline, already made
            owner = item
            uri = _LK_URI.match(str(ev.get("sourceUri") or ""))
            if uri is not None and uri["rid"] != item.lk_id:
                chained = self.items.get(uri["rid"])
                if chained is not None:
                    owner = chained
                elif self.state.get(uri["rid"]) in ("hidden", "under"):
                    self.report.omitted.hidden_events += 1  # an event of a hidden resource's timeline
                    continue
                else:
                    self.report.notes.append(
                        f"event {ev.get('name')!r} on {item.name!r} comes from {uri['rid']}, not in the tree;"
                        f" kept under {item.name!r}"
                    )
            etype = ev.get("type")
            if etype in ("placeholder", "invisible-placeholder"):
                self.placeholders += 1
                continue
            if ev.get("isHidden") and not self.include_hidden:
                self.report.omitted.hidden_events += 1
                continue
            self.event_ids.add(ev_id)
            lane = lanes.get(str(ev.get("laneId")))
            name = str(ev.get("name") or "").strip()
            if not name:
                name = str(ev.get("formattedStart") or "Untitled event")
                self.report.notes.append(f"an event with no name on {item.name!r} is named {name!r}")
            fields: dict[str, Any] = {}
            image = ev.get("imageUrl")
            if isinstance(image, str) and image:
                fields["image_url"] = image
            ext: dict[str, Any] = {f"{EXT_PREFIX}id": ev_id}
            for key, minutes, text in (
                ("start", ev.get("start"), ev.get("formattedStart")),
                ("end", ev.get("end"), ev.get("formattedEnd")),
            ):
                if minutes is not None:
                    ext[f"{EXT_PREFIX}{key}"] = {"minutes": minutes, **({"formatted": text} if text else {})}
            if calendar:
                ext[f"{EXT_PREFIX}calendar"] = calendar
            if lane is not None:
                ext[f"{EXT_PREFIX}lane"] = lane.get("name")
            elif ev.get("laneId"):
                ext[f"{EXT_PREFIX}lane"] = ev.get("laneId")
                self.report.notes.append(f"event {name!r}: its lane {ev.get('laneId')} is not in the lanes list")
            ext[f"{EXT_PREFIX}timeline"] = (lane or {}).get("documentName") or doc.get("name")
            ext[f"{EXT_PREFIX}parent"] = owner.eid
            if etype and etype != "event":
                ext[f"{EXT_PREFIX}event_type"] = etype
            link = _LK_URI.match(str(ev.get("uri") or ""))
            if ev.get("uri"):
                ext[f"{EXT_PREFIX}uri"] = ev.get("uri")
            if link is not None:
                target = self.items.get(link["rid"])
                fname = next(
                    (f for f, t in LINK_TARGETS["event"].items() if target is not None and t == target.etype),
                    None,
                )
                if target is None:
                    self.report.unresolved.append(
                        Unresolved(name, "event uri", link["rid"], self._why_missing(link["rid"]))
                    )
                elif fname is not None and FIELD_KINDS["event"][fname] == "multi_link":
                    fields.setdefault(fname, []).append(target.eid)
            body: dict[str, Any] = {"type": "event", "id": self._id("event", ev_id), "name": name}
            for fname in FIELD_KINDS["event"]:
                if fname in fields:
                    body[fname] = fields[fname]
            body.update(ext)
            self.events.append(body)
            made += 1
        self.report.notes.append(
            f"timeline {doc.get('name')!r} on {item.name!r}: {made} event{'' if made == 1 else 's'}"
            " (start and end kept as minutes and the formatted date; start_date and end_date unset)"
        )

    # -- the bodies ----------------------------------------------------------

    def bodies(self) -> dict[str, list[dict[str, Any]]]:
        out: dict[str, list[dict[str, Any]]] = {}
        for item in self.items.values():
            body: dict[str, Any] = {"type": item.etype, "id": item.eid, "name": item.name}
            for fname in FIELD_KINDS[item.etype]:
                if fname in item.fields and fname != "name":
                    body[fname] = item.fields[fname]
            body.update(item.ext)
            if item.mentions:
                body[f"{EXT_PREFIX}mentions"] = item.mentions
            out.setdefault(item.etype, []).append(body)
        for body in self.relations + self.events:
            out.setdefault(body["type"], []).append(body)
        self.report.counts = {t: len(b) for t, b in sorted(out.items())}
        self._notes()
        return out

    def _notes(self) -> None:
        n = self.report.notes
        if self.blank:
            n.append(f"{self.blank} blank document{'' if self.blank == 1 else 's'}: empty by LegendKeeper's definition")
        if self.placeholders:
            n.append(f"{self.placeholders} timeline placeholder{'' if self.placeholders == 1 else 's'}: layout only")
        if self.map_blocks:
            n.append(f"{self.map_blocks} map block{'' if self.map_blocks == 1 else 's'}: a line naming the map")
        if self.unsupported:
            n.append(
                f"{self.unsupported} unsupported block{'' if self.unsupported == 1 else 's'} or propert"
                f"{'y' if self.unsupported == 1 else 'ies'} (LegendKeeper's public model cannot express it): nothing"
                " to read"
            )
        for kind, count in sorted(self.unknown.items()):
            n.append(f"{count} block{'' if count == 1 else 's'} of kind {kind!r}, not known here: read by its text")
        if self.marks:
            listed = ", ".join(f"{m} {c}" for m, c in sorted(self.marks.items()))
            n.append(f"runs with marks Markdown has no syntax for, read as plain text: {listed}")
        if self.items:
            n.append(f"not kept: {_NOT_KEPT}")

    def world(self) -> dict[str, Any]:
        pid = self.snap.project_id
        name = str(self.snap.project.get("name") or "").strip() or f"LegendKeeper project {pid}"
        return {
            "id": _uuid(f"legendkeeper:{pid}"),
            "name": name,
            "format_version": FORMAT_VERSION,
            "producer": {"tool": "onlyworlds", "version": __version__, "input": PRODUCER_INPUT},
        }


def _type_map(pairs: Mapping[str, str] | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for tag, etype in (pairs or {}).items():
        t, e = str(tag).strip().lower(), str(etype).strip().lower()
        if not t:
            raise ValueError("a --map needs a tag before the '='")
        if e not in ELEMENT_TYPES:
            raise ValueError(f"--map {tag}={etype}: {etype!r} is not one of the 22 types ({', '.join(ELEMENT_TYPES)})")
        out[t] = e
    return out


def import_legendkeeper(
    source: Source,
    project_id: str,
    out_dir: str | os.PathLike[str] | None,
    *,
    plan_only: bool = False,
    type_map: Mapping[str, str] | None = None,
    include_hidden: bool = False,
    include_secrets: bool = False,
) -> ImportReport:
    """Read the LegendKeeper project ``project_id`` from ``source`` into a world folder at
    ``out_dir``, which must not exist or be empty.

    ``type_map`` maps a tag to one of the 22 types (``{"faction": "institution"}``), besides the
    tags that are type names. With ``plan_only`` nothing is written (``out_dir`` may be None) and
    the report says what would be. Raises ``FileExistsError`` for an ``out_dir`` that is not
    empty, ``ValueError`` for a ``type_map`` that names no type, ``SourceError`` when the project
    or its tree cannot be read.
    """
    if not isinstance(project_id, str) or not project_id.strip():
        raise ValueError("give the LegendKeeper project id")
    mapping = _type_map(type_map)
    out = Path(out_dir) if out_dir is not None else None
    if not plan_only:
        if out is None:
            raise ValueError("give an out_dir, or plan_only=True")
        if out.exists() and (not out.is_dir() or any(out.iterdir())):
            raise FileExistsError(f"{out} exists and is not an empty directory; a folder is written whole, once")
    snap = read_project(source, project_id.strip(), include_hidden=include_hidden)
    conv = _Converter(snap, mapping, include_hidden=include_hidden, include_secrets=include_secrets)
    conv.collect()
    conv.fill()
    elements = conv.bodies()
    report = conv.report
    report.world = conv.world()
    if plan_only:
        return report
    assert out is not None
    write_folder(out, report.world, elements)
    report.out = out
    return report


def _read_key(key_file: Path | None) -> str:
    if key_file is not None:
        try:
            key = key_file.read_text(encoding="utf-8-sig").strip()
        except OSError as exc:
            raise ValueError(f"{key_file}: cannot read the key file ({type(exc).__name__})") from None
        if not key:
            raise ValueError(f"{key_file}: the key file is empty")
        return key
    key = os.environ.get(KEY_ENV, "").strip()
    if not key:
        raise ValueError(f"no key: set {KEY_ENV}, or pass --key-file PATH (a file holding the key)")
    return key


def main(argv: list[str] | None = None, *, source: Source | None = None, transport: Transport | None = None) -> int:
    """The command line. ``source`` (a recorded one) or ``transport`` (a fake HTTP) are for tests."""
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="python -m onlyworlds.legendkeeper", description=(__doc__ or "").splitlines()[0])
    ap.add_argument("out", type=Path, nargs="?", help="the world folder to create; must not exist or be empty")
    ap.add_argument("--project", required=True, help="the LegendKeeper project id (the key is bound to it)")
    ap.add_argument("--plan", action="store_true", help="read the project, print what would become what, write nothing")
    ap.add_argument("--key-file", type=Path, help=f"a file holding the API key (else ${KEY_ENV})")
    ap.add_argument("--map", action="append", default=[], metavar="TAG=TYPE", help="type the resources with this tag")
    ap.add_argument("--include-hidden", action="store_true", help="take in hidden resources, documents and events")
    ap.add_argument("--include-secrets", action="store_true", help="take in secret blocks")
    args = ap.parse_args(argv)
    if args.out is None and not args.plan:
        print("give OUT-DIR, or --plan", file=sys.stderr)
        return 2
    pairs: dict[str, str] = {}
    for item in args.map:
        tag, eq, etype = item.partition("=")
        if not eq or not tag.strip() or not etype.strip():
            print(f"--map {item!r}: write TAG=TYPE (faction=institution)", file=sys.stderr)
            return 2
        pairs[tag] = etype
    try:
        src = source if source is not None else ApiSource(_read_key(args.key_file), transport=transport)
        report = import_legendkeeper(
            src,
            args.project,
            args.out,
            plan_only=args.plan,
            type_map=pairs,
            include_hidden=args.include_hidden,
            include_secrets=args.include_secrets,
        )
    except (FileExistsError, ValueError, SourceError) as exc:
        print(f"{exc}", file=sys.stderr)
        return 2
    sys.stdout.write(report.render())
    return 0


if __name__ == "__main__":
    sys.exit(main())

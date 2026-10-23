"""Read a LegendKeeper project into a world folder, through LegendKeeper's own API or from its own
export file: read-only, no AI.

    LEGENDKEEPER_API_KEY=lk_... python -m onlyworlds.legendkeeper --project ID OUT-DIR [--plan]
        [--key-file PATH] [--map TAG=TYPE ...]
    python -m onlyworlds.legendkeeper --file EXPORT.lk OUT-DIR [--plan] [--project ID] [--map TAG=TYPE ...]

or ``import_legendkeeper(ApiSource(key), project_id, out_dir, ...)`` and
``import_legendkeeper("EXPORT.lk", out_dir=...)``. The key is the person's own (Project Settings,
Developers, API Keys; LegendKeeper requires the project owner to be on a paid plan), read from
``LEGENDKEEPER_API_KEY`` or the file ``--key-file`` names. It is sent as ``Authorization: Bearer``
and nowhere else: never stored, never printed, never written into the folder or the report. The
export file needs no key. ``--plan`` reads the project and prints what would become what, and
writes nothing. OUT-DIR must not exist yet (or be empty): a folder is written whole, once.

Reading and converting are apart. A ``Source`` answers ``get(path, params)`` with the decoded JSON
of one GET below ``https://www.legendkeeper.com/api/v3``: ``ApiSource`` asks the live API (GET only,
paced on ``x-ratelimit-remaining`` and ``x-ratelimit-reset``, a 429's ``Retry-After`` honoured),
``RecordedSource`` answers from recorded replies (the tests), and ``FileSource`` answers from
LegendKeeper's own export file, each answer in the API's shape. ``read_project`` walks a source
into a ``Snapshot``; the converter reads only the snapshot, so both roads give the same elements.

**The export file** (Project Settings, Export; ``.lk`` is the JSON gzipped, the JSON type the same
data plain; read either, by its first bytes, never by its name) holds the whole project in one
object, ``{version, exportId, exportedAt, resources, calendars, resourceCount, hash}``. **Proven on
two real exports** of one project (version 1, 2026-10-23, Seethe's project on a crew trial account:
``tests/fixtures/legendkeeper/the-quay-world.lk``, and ``the-quay-world-3.json`` a few hours on,
with a map of her own and two pins on it; the account's ids and its map image's asset id replaced
by placeholders). ``FileSource`` adapts where its shape is not the API's:

- no project: the export names neither the project's id nor its name. Ids are keyed on the id of
  the first top-level resource in LegendKeeper's own sibling order (``pos``; the project home in
  a new project), the world named by that resource, unless ``project_id`` (``--project``) names
  the project, when ids are those the API road gives. Reordering the top level, or deleting that
  resource, moves the key: give ``--project`` for ids that hold.
- the tree is one list, not pages; a top-level resource has no ``parentId`` key (the API's is
  null); each document carries its ``content`` inline (the API serves it per document).
- **a page's content is the editor's own document** (``{type: doc, content: [...]}``, Atlassian
  ADF style nodes: ``type``, ``attrs``, text nodes with ``marks``), not the API's blocks (``kind``,
  ``children``, runs with flags). It is translated node for node: paragraph, heading, the three
  lists and their items (a task's ``state`` DONE as checked), blockquote as a quote, panel as a
  callout (``panelType`` its tone), codeBlock, rule, mediaSingle and media as images, layoutSection
  and layoutColumn, expand, tables; a ``bodiedExtension`` ``block-secret`` is the API's ``secret``
  block, an ``extension`` ``block-youtube`` an embed; marks strong, em, strike, code, underline,
  link (``href``), textColor, subsup; hardBreak a break; a mention's ``attrs.id`` its
  ``resourceId``. An inline icon (``inline-icon``) is counted, not kept; another node or extension
  goes on under its own name, which the report counts as a kind not known here.
- sidebar properties are ``{id, title, type, data, pos}``: ``IMAGE``, ``TEXT_FIELD`` (its
  ``fragment`` an editor document), ``RESOURCE_COLLECTION``, ``METER`` and ``SPOTIFY_SINGLE`` (an
  embed) become the API's kinds; ``TAGS`` and ``ALIAS`` only show the resource's tags and aliases
  (which are kept) and are counted; any other goes on under its own type, kept whole.
- a timeline's ``content`` holds its lanes and events; an event carries no formatted dates and
  no ``sourceUri`` (the server computes those), so ``x_legendkeeper_start`` holds the minutes only.
- a map document carries a ``map`` object (``mapId``, ``locatorId``, ``min_x``, ``max_x``,
  ``min_y``, ``max_y``, ``max_zoom``; none on a map with no image) and ``content.pins``; the pins
  ride on the document as ``pins``, beside the ``map`` object. The API's map shape is not known
  (Boss's walk could neither make nor read a pin), so a map read through the API stays not
  imported, named: only the file makes Maps.
- not kept, named in the report: ``exportId``, ``exportedAt`` and ``hash`` (the report names the
  export; two exports of one project give one folder), ``createdBy`` (an account id),
  ``schemaVersion``, ``showPropertyBar``, ``isFullWidth``, document locators, ``transforms`` and
  ``sources``, and ``calendars`` (the export of 2026-10-23 holds none, though its timeline names a
  calendar).

LegendKeeper's starter pages (the tutorial a new project is seeded with: Wiki City, Temple of
Time, ...) travel like the rest: nothing in the file marks them, so they are imported. On the one
real export their ``createdBy`` is another account than the person's, which is a tell, not a rule.
The templates (Character, Location, ...) are marked: they sit in LegendKeeper's templates folder,
``parentId`` ``templates`` (no resource has that id), and each is imported carrying
``x_legendkeeper_template: true``, the report naming them.

The Markdown zip LegendKeeper also exports is not a source: it loses the tags, the properties,
the hidden marks and the ids.

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
  name two, becomes a Narrative with supertype ``Article`` (what it is, never where it came from:
  the producer line and the ``x_legendkeeper_`` keys say that; the report lists the tags
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
- **A map document** (read from the export file) **becomes a Map** (Skeld's ruling, OW Market h40
  #11385), named ``<resource>: <document>`` as a hidden page's Narrative is: ``width`` is
  ``max_x - min_x`` and ``height`` ``max_y - min_y`` from the document's ``map`` bounds (whole
  numbers), the bounds kept as ``x_legendkeeper_bounds`` and ``max_zoom`` as
  ``x_legendkeeper_max_zoom``. ``image_url`` is the map's ``mapId`` only when it is an http(s)
  address, as given and never copied (Skeld #11386): the image lives on LegendKeeper's host and
  loads only as long as that account's asset does, which the report says; a bare asset id
  (LegendKeeper's tutorial map's) is kept as ``x_legendkeeper_map_id``, never written as a URL. A
  ``locatorId`` equal to the ``mapId`` is not kept; any other key of the ``map`` object is kept in
  ``x_legendkeeper_map``. The Map links its resource as ``location`` when the resource became a
  Location, else keeps the resource's element id as ``x_legendkeeper_resource``;
  ``x_legendkeeper_document`` is the document's id. A map document with no ``map`` object is a Map
  with no width, height or image, named so in the report, never zeros.
- **Each pin becomes a Pin** on its Map: its ``name``, or, for a pin with none, the name of the
  element it places (LegendKeeper shows the linked page's name on it), else ``Untitled pin (<id>)``,
  each named in the report; ``element_type`` and ``element_id`` the element its ``uri``
  (``lk://resources/<id>``) names. A pin with no uri, or whose uri names no resource of the
  export, is a Pin with no element, named in the report, never a dangling id. **Its place**:
  the bounds are image pixels, but LegendKeeper stores ``pos`` as ``[y, x]`` in zoom-0 units, an
  image pixel divided by ``2^max_zoom``, y counting down from 0 at the map's top to ``min_y``.
  OnlyWorlds counts image pixels from the bottom left, so ``x`` is ``x * 2^max_zoom - min_x`` and
  ``y`` is ``y * 2^max_zoom - min_y``, a half rounded up, the exact pair kept as
  ``x_legendkeeper_pos``; the report names each map's scale (``positions scaled by 2^2 = 4``).
  Measured on two pins of Seethe's quay map (an 800 by 600 image, bounds x 0..800, y -600..0,
  ``max_zoom`` 2; OW Market h40 #11426, #11429, Skeld #11428): the first, read at image pixel
  (127, 110) from the top left, is stored ``[-27.5, 32]`` (times 4, pixel 128, 110): x 128, y 490;
  the second, read at about (796, 524), is stored ``[-131.118, 199.314]``: x 797, y 76. Both fit
  the scaled reading and neither the unscaled one. A pin on a map with no bounds has no x, y, and
  so does a pin on a map with no ``max_zoom`` (the scale is not known, never guessed; named in the
  report). Its icon and label (``iconGlyph``, ``iconColor``, ``iconShape``, ``labelSize``,
  ``labelVisibility``, ``isSynced`` and any other key but its id, name, pos, uri, hidden mark, rank
  and timestamps) are kept together as ``x_legendkeeper_pin``, its id as ``x_legendkeeper_id``,
  its uri as ``x_legendkeeper_uri``.
- **Not imported**, named in the report with their resource: ``board`` documents, and ``map``
  documents read through the API (the report says why). ``blank`` documents are empty and counted.
  Not kept, named in the report: a resource's and an event's icons, sibling order, timestamps, lock
  state, permissions, banners, event colours, and the server's computed event dates (they follow
  from the minutes and calendar).

**What the source hides, the folder hides: never dropped, never public** (Skeld's rule, OW Market
h40 #11228). Each hidden thing is an element carrying ``hidden: true`` at the top of its body
(OnlyWorlds' hidden mark), counted in the report, from either road:

- a resource whose ``isHidden`` is true, and every resource under it (LegendKeeper hides a
  hidden page's subtree from a reader below admin): its element, whole; its hidden pages and
  secret blocks stay in its own text (a page under its heading, a secret as ``> [!secret]``);
- a hidden ``page`` document on a visible resource: its own Narrative, named
  ``<resource>: <document>``, the page's text its ``story``, linked to the resource's element
  (Narrative's field for the element's type, ``parent_narrative`` for a Narrative) and
  ``x_legendkeeper_parent``; ``x_legendkeeper_document`` the document's id;
- a ``secret`` block in a visible page: its own Narrative, ``<resource>: Secret`` (the block's
  title when it has one; numbered when a resource has more than one), the block's text its
  ``story``, linked the same way; the page keeps only its visible text;
- a hidden property on a visible resource: into one Narrative per resource,
  ``<resource>: hidden properties``, linked the same way, its keys kept as extensions;
- a timeline event whose ``isHidden`` is true, or on a hidden document or resource: its Event;
- a Relation either end of which is hidden;
- a map document whose ``isHidden`` is true, or on a hidden resource: its Map and every Pin on it;
- a pin whose ``isHidden`` is true: its Pin (no real file has one yet: the tests plant it).

A visible text that mentions a hidden element by name, or a visible pin that places one, is named
in the report. A hidden board or blank document is named or counted as a visible one is.

**Ids are UUIDv5** in ``LEGENDKEEPER_NAMESPACE``: of ``legendkeeper:<project id>:<resource id>`` for
a resource, ``legendkeeper:<project id>:event:<event id>`` for an event,
``legendkeeper:<project id>:link:<resource id>:<list id>:<item id>`` for a Relation (a kind word,
since LegendKeeper lets a client choose 8- or 24-character ids for resources and events alike),
``legendkeeper:<project id>:document:<resource id>:<document id>`` for a hidden document's
Narrative, ``legendkeeper:<project id>:secret:<resource id>:<document id>:<n>`` for the n-th secret
block of a page (the export gives a block no id, so both roads count them) and
``legendkeeper:<project id>:properties:<resource id>`` for a resource's hidden properties,
``legendkeeper:<project id>:map:<resource id>:<document id>`` for a Map and
``legendkeeper:<project id>:pin:<resource id>:<document id>:<pin id>`` for a Pin. A second
import of the same project finds the same elements. ``world.json``: ``id`` UUIDv5 of
``legendkeeper:<project id>``, ``name`` the project's name, ``producer`` ``{"tool": "onlyworlds",
"version": ..., "input": ...}`` with ``legendkeeper-api`` (``PRODUCER_INPUT``) from the API and
``legendkeeper-export`` (``PRODUCER_INPUT_FILE``) from the file (both on the folder spec's list,
§4.2, v0.3.17), ``format_version`` this package's.

The report (``ImportReport``, printed at the end of a run and by ``--plan``) names what became what
with counts and how each type was decided, every key not placed (element, key, why, the extension
it was kept as), every titled link kept as Relations (by title, with counts), every link or mention
whose target is not in the folder, what is hidden and how, every Map (its size, pins and image) and
every pin named or left with no element, the documents not imported, every answer
that could not be read, and anything else read past. Nothing from the source is dropped without a
line in it.

From the command line: exit 0 written (or planned), 2 on bad arguments (no key, a ``--map`` that
names no type, an OUT-DIR that is not empty, a file that is not a LegendKeeper export) or a project
that cannot be read (the key refused, the plan gate, no such project); the error names the call and
LegendKeeper's error code, never the key.
"""

from __future__ import annotations

import argparse
import copy
import gzip
import io
import json
import math
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
    "PRODUCER_INPUT_FILE",
    "ApiSource",
    "FileSource",
    "Hidden",
    "ImportReport",
    "MapMade",
    "NotImported",
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

#: The ``producer.input`` word for a folder read through the API (folder spec §4.2, v0.3.17).
PRODUCER_INPUT = "legendkeeper-api"

#: The ``producer.input`` word for a folder read from LegendKeeper's export file (§4.2, v0.3.17).
PRODUCER_INPUT_FILE = "legendkeeper-export"

#: The ``parentId`` of a resource in LegendKeeper's templates folder (seen in the export; no
#: resource of the tree carries this id).
TEMPLATES_PARENT = "templates"

#: The most an export may hold once unzipped, in bytes: a file past it is refused, not read.
MAX_EXPORT_BYTES = 256 * 1024 * 1024

#: The namespace every id this door mints is UUIDv5 in. Fixed for good: changing it would give
#: every element of every re-imported project a new id.
LEGENDKEEPER_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "https://onlyworlds.com/ns/legendkeeper")

#: LegendKeeper's API v3; every path below is relative to it.
API_BASE = "https://www.legendkeeper.com/api/v3"

#: Where the command line reads the key from when no ``--key-file`` is given.
KEY_ENV = "LEGENDKEEPER_API_KEY"

#: Every extension key this door writes starts with this.
EXT_PREFIX = "x_legendkeeper_"

#: The supertype a Narrative made from an untyped resource carries: what it is, never where it came
#: from (the producer line and the x_legendkeeper_ keys say that; Skeld, OW Market h40 #11385).
UNTYPED_SUPERTYPE = "Article"

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
    "document",
    "template",
    "resource",
    "map_id",
    "bounds",
    "max_zoom",
    "map",
    "pos",
    "pin",
)
#: The door's own extension keys; a property's key never takes one of them.
_RESERVED = frozenset(f"{EXT_PREFIX}{k}" for k in _OWN)

#: What a resource or event carries that the folder does not keep (one report line).
_NOT_KEPT = (
    "a resource's and an event's icons (iconGlyph, iconColor, iconShape, iconSize; a pin's are kept), sibling "
    "order (rank), timestamps, lock state, "
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

#: target type -> Narrative's multi-link field for it: how a hidden Narrative links its resource.
_NARRATIVE_FIELD_FOR: dict[str, str] = {}
for _f, _kind in FIELD_KINDS["narrative"].items():
    if _kind == "multi_link":
        _NARRATIVE_FIELD_FOR.setdefault(LINK_TARGETS["narrative"][_f], _f)

#: An element type whose own parent field takes a parent of the same type.
_PARENT_FIELD: dict[str, str] = {"location": "parent_location", "institution": "parent_institution"}

_INT = re.compile(r"\s*-?\d+\s*")
_LK_URI = re.compile(r"^lk://resources/(?P<rid>[^/\s]+)(?:/docs/(?P<did>[^/\s]+))?")
_SEPARATORS = re.compile(r"[\s,;]*")
_HTTP = re.compile(r"^https?://", re.IGNORECASE)

#: A map's bounds, as the export's ``map`` object names them.
_BOUNDS = ("min_x", "max_x", "min_y", "max_y")

#: What a pin carries that is said elsewhere (its own fields, or the report's not-kept line):
#: everything else on it (icon, label, isSynced, ...) is kept together as ``x_legendkeeper_pin``.
_PIN_SAID = frozenset({"id", "name", "pos", "uri", "isHidden", "rank", "createdAt", "updatedAt"})
_PLAIN_MARKS = ("underline", "sub", "sup", "color", "highlight")


def _norm(name: str) -> str:
    """A key or title lowercased, whitespace runs as underscores: the name a field is compared to."""
    return re.sub(r"\s+", "_", name.strip().lower())


def _uuid(key: str) -> str:
    return str(uuid.uuid5(LEGENDKEEPER_NAMESPACE, key))


def _number(value: Any) -> float | None:
    """``value`` when it is a number (not a bool), else None."""
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _whole(value: float) -> int:
    """A coordinate or a size as a whole number, a half rounded up (572.5 is 573)."""
    return math.floor(value + 0.5)


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


#: Editor marks -> the API run's flag (a link and a colour carry their value).
_PM_MARKS = {"strong": "bold", "em": "italic", "strike": "strike", "code": "code", "underline": "underline"}

#: Editor block nodes whose children are blocks, -> the API block kind.
_PM_CONTAINERS = {
    "listItem": "listItem",
    "blockquote": "quote",
    "layoutSection": "layout",
    "layoutColumn": "layoutColumn",
    "tableRow": "tableRow",
}

#: Sidebar property types that only show the resource's own tags or aliases (kept from the row).
_SHOWS_ROW = ("TAGS", "ALIAS")


def _obj(value: Any) -> dict[str, Any]:
    """``value`` when it is an object, else an empty one."""
    return value if isinstance(value, dict) else {}


def _export_bytes(path: Path) -> bytes:
    """The export's JSON bytes: ``.lk`` is gzip (told by its first two bytes), the JSON type plain."""
    try:
        with path.open("rb") as fh:
            head = fh.read(2)
            fh.seek(0)
            if head == b"\x1f\x8b":
                with gzip.GzipFile(fileobj=fh) as gz:
                    data = gz.read(MAX_EXPORT_BYTES + 1)
            else:
                data = fh.read(MAX_EXPORT_BYTES + 1)
    except (OSError, EOFError, gzip.BadGzipFile) as exc:
        raise ValueError(f"{path}: cannot read the export ({type(exc).__name__}: {exc})") from None
    if len(data) > MAX_EXPORT_BYTES:
        raise ValueError(f"{path}: the export holds more than {MAX_EXPORT_BYTES} bytes; refused")
    return data


class FileSource:
    """LegendKeeper's own export file (``.lk``, gzipped, or the JSON type), answering the API's
    paths in the API's shapes, so ``read_project`` walks it as it walks the API. What it adapts,
    and why, is in the module docstring; ``notes`` names what it read past.

    ``project_id`` is the id the folder's ids are keyed on: the project's own when given (the API
    road's ids), else the id of the export's first top-level resource in ``pos`` order. ``name``
    is that resource's name. Raises ``FileNotFoundError`` for a missing file and ``ValueError``
    for one that is not a LegendKeeper export.
    """

    producer_input = PRODUCER_INPUT_FILE

    def __init__(self, path: str | os.PathLike[str], project_id: str | None = None) -> None:
        self.path = Path(path)
        if not self.path.is_file():
            raise FileNotFoundError(f"{self.path}: no such export file")
        raw = _export_bytes(self.path)
        try:
            data = json.loads(raw.decode("utf-8-sig"))
        except ValueError:  # UnicodeDecodeError and JSONDecodeError both
            raise ValueError(f"{self.path}: not a LegendKeeper export (not UTF-8 JSON)") from None
        if not isinstance(data, dict) or not isinstance(data.get("resources"), list):
            raise ValueError(f"{self.path}: not a LegendKeeper export (no resources list)")
        self.export: dict[str, Any] = data
        self.notes: list[str] = []
        self._icons = 0
        self._shows_row = 0
        self._marks: dict[str, int] = {}
        rows = [r for r in data["resources"] if isinstance(r, dict) and isinstance(r.get("id"), str)]
        self._rows = {r["id"]: r for r in rows}
        tops = sorted(
            (r for r in rows if not isinstance(r.get("parentId"), str) or r["parentId"] not in self._rows),
            key=lambda r: (str(r.get("pos") or ""), r["id"]),
        )
        if project_id is not None and not str(project_id).strip():
            raise ValueError("give the LegendKeeper project id, or leave it out")
        first = tops[0] if tops else None
        self.project_id = str(project_id).strip() if project_id else (first["id"] if first else "export")
        self.name = str(first.get("name") or "").strip() if first else ""
        self._answers = self._build(rows)
        self._note(first, project_id)

    def __repr__(self) -> str:
        return f"FileSource({str(self.path)!r})"

    def get(self, path: str, params: Mapping[str, str] | None = None) -> Any:
        parts = path.strip("/").split("/")
        if len(parts) < 2 or parts[0] != "projects":
            raise SourceError(path, 404, "NOT_IN_EXPORT", "not a path the export answers")
        key = "/".join(urllib.parse.unquote(p) for p in parts[2:])
        if key not in self._answers:
            raise SourceError(path, 404, "NOT_IN_EXPORT", "the export holds no such thing")
        return copy.deepcopy(self._answers[key])

    # -- the answers, built once --------------------------------------------

    def _build(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        out: dict[str, Any] = {"": {"id": self.project_id, "name": self.name}}
        listed: list[dict[str, Any]] = []
        for r in rows:
            docs = [d for d in r.get("documents") or [] if isinstance(d, dict) and isinstance(d.get("id"), str)]
            heads = [{k: v for k, v in d.items() if k != "content"} for d in docs]
            for head, d in zip(heads, docs, strict=True):
                if d.get("type") == "map":  # its pins ride on the document, beside its map object
                    pins = _obj(d.get("content")).get("pins")
                    head["pins"] = [p for p in pins if isinstance(p, dict)] if isinstance(pins, list) else []
            row = {k: v for k, v in r.items() if k not in ("documents", "properties")}
            row["parentId"] = r.get("parentId") if isinstance(r.get("parentId"), str) else None
            listed.append(
                {**row, "documents": [{"id": d["id"], "name": d.get("name"), "type": d.get("type")} for d in docs]}
            )
            props = [p for p in (self._property(p) for p in r.get("properties") or [] if isinstance(p, dict)) if p]
            rpath = f"resources/{r['id']}"
            out[rpath] = {**row, "documents": heads, "properties": props}
            for d in docs:
                content = _obj(d.get("content"))
                if d.get("type") == "page":
                    out[f"{rpath}/docs/{d['id']}/blocks"] = {
                        "id": d["id"],
                        "blocks": self._blocks(content.get("content")),
                    }
                elif d.get("type") == "time":
                    lanes = [x for x in content.get("lanes") or [] if isinstance(x, dict)]
                    events = [x for x in content.get("events") or [] if isinstance(x, dict)]
                    out[f"{rpath}/docs/{d['id']}/lanes"] = {"data": lanes, "hasMore": False}
                    out[f"{rpath}/docs/{d['id']}/events"] = {"data": events, "hasMore": False}
        out["resources"] = {"data": listed, "hasMore": False, "nextCursor": None}
        return out

    def _note(self, first: dict[str, Any] | None, project_id: str | None) -> None:
        e = self.export
        self.notes.append(
            f"read from LegendKeeper's export file (version {e.get('version')}, export {e.get('exportId')}, made"
            f" {e.get('exportedAt')}); exportId, exportedAt and hash are not kept, so two exports give one folder"
        )
        if project_id:
            self.notes.append(f"ids keyed on the project id given, {self.project_id}: the API road's ids")
        elif first is not None:
            self.notes.append(
                f"the export names no project: ids keyed on the first top-level resource, {first.get('name')!r}"
                f" ({self.project_id}), the world named by it; --project ID keys them on the project's own id"
            )
        count = e.get("resourceCount")
        if isinstance(count, int) and count != len(self._rows):
            self.notes.append(f"the export says it holds {count} resources and lists {len(self._rows)}")
        calendars = e.get("calendars")
        if isinstance(calendars, list) and calendars:
            self.notes.append(f"{len(calendars)} calendar{'' if len(calendars) == 1 else 's'} in the export: not read")
        if self._icons:
            self.notes.append(f"{self._icons} inline icon{'' if self._icons == 1 else 's'}: not kept")
        if self._shows_row:
            n = self._shows_row
            self.notes.append(
                f"{n} sidebar propert{'y' if n == 1 else 'ies'} showing the resource's tags or aliases (TAGS, ALIAS):"
                " the tags and aliases are kept from the resource"
            )
        if self._marks:
            listed = ", ".join(f"{m} {c}" for m, c in sorted(self._marks.items()))
            self.notes.append(f"text marks and inline nodes not known here, read as plain text: {listed}")
        self.notes.append(
            "not kept from the export: createdBy (an account id), schemaVersion, showPropertyBar, isFullWidth,"
            " document locators, transforms and sources"
        )

    # -- the editor's document into the API's blocks --------------------------

    def _blocks(self, nodes: Any) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for n in nodes if isinstance(nodes, list) else []:
            if isinstance(n, dict):
                out += self._block(n)
        return out

    def _block(self, n: dict[str, Any]) -> list[dict[str, Any]]:
        t = str(n.get("type") or "")
        attrs = _obj(n.get("attrs"))
        kids = n.get("content")
        if t == "paragraph":
            return [{"kind": "paragraph", "content": self._runs(kids)}]
        if t == "heading":
            return [{"kind": "heading", "level": attrs.get("level"), "content": self._runs(kids)}]
        if t in ("bulletList", "orderedList", "taskList"):
            b: dict[str, Any] = {"kind": t, "children": self._blocks(kids)}
            if t == "orderedList" and isinstance(attrs.get("order"), int):
                b["start"] = attrs["order"]
            return [b]
        if t == "taskItem":
            return [{"kind": "taskItem", "checked": attrs.get("state") == "DONE", "content": self._runs(kids)}]
        if t in _PM_CONTAINERS:
            return [{"kind": _PM_CONTAINERS[t], "children": self._blocks(kids)}]
        if t == "panel":
            return [{"kind": "callout", "tone": attrs.get("panelType") or "note", "children": self._blocks(kids)}]
        if t == "codeBlock":
            text = "".join(str(k.get("text") or "") for k in kids or [] if isinstance(k, dict))
            return [{"kind": "code", "language": attrs.get("language"), "text": text}]
        if t == "rule":
            return [{"kind": "rule"}]
        if t in ("mediaSingle", "mediaGroup"):
            return self._blocks(kids)
        if t == "media":
            return [{"kind": "image", "url": attrs.get("url"), "alt": attrs.get("alt")}]
        if t in ("expand", "nestedExpand"):
            return [{"kind": "expand", "title": attrs.get("title"), "children": self._blocks(kids)}]
        if t == "table":
            return [{"kind": "table", "children": self._blocks(kids)}]
        if t in ("tableCell", "tableHeader"):
            return [{"kind": "tableCell", "header": t == "tableHeader", "children": self._blocks(kids)}]
        if t in ("blockCard", "embedCard"):
            return [{"kind": "embed", "url": attrs.get("url")}]
        if t in ("bodiedExtension", "extension"):
            key = str(attrs.get("extensionKey") or t)
            params = _obj(attrs.get("parameters"))
            if key == "block-secret":
                return [{"kind": "secret", "title": params.get("extensionTitle"), "children": self._blocks(kids)}]
            if key == "block-youtube":
                return [{"kind": "embed", "provider": "youtube", "url": params.get("embedUrl")}]
            return [{"kind": key, "children": self._blocks(kids)}]
        # a node not known here goes on under its own name: the converter counts it and reads its text
        inline = any(isinstance(k, dict) and k.get("type") in ("text", "mention", "hardBreak") for k in kids or [])
        return [
            {"kind": t or "unknown", **({"content": self._runs(kids)} if inline else {"children": self._blocks(kids)})}
        ]

    def _runs(self, nodes: Any) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for n in nodes if isinstance(nodes, list) else []:
            if not isinstance(n, dict):
                continue
            t = n.get("type")
            attrs = _obj(n.get("attrs"))
            if t == "text":
                out.append(self._text(n))
            elif t == "hardBreak":
                out.append({"break": True})
            elif t == "mention":
                out.append(
                    {
                        "mention": {
                            "resourceId": attrs.get("id"),
                            "documentId": attrs.get("documentId") or None,
                            "text": attrs.get("text"),
                        }
                    }
                )
            elif t == "inlineExtension" and attrs.get("extensionKey") == "inline-icon":
                self._icons += 1
            elif t == "emoji":
                out.append({"text": attrs.get("text") or attrs.get("shortName") or ""})
            elif t == "inlineCard" and isinstance(attrs.get("url"), str):
                out.append({"text": attrs["url"], "link": attrs["url"]})
            else:
                text = attrs.get("text")
                out.append({"text": text if isinstance(text, str) else ""})
                self._marks[f"node {t}"] = self._marks.get(f"node {t}", 0) + 1
        return out

    def _text(self, n: dict[str, Any]) -> dict[str, Any]:
        run: dict[str, Any] = {"text": str(n.get("text") or "")}
        for m in n.get("marks") or []:
            if not isinstance(m, dict):
                continue
            mt = m.get("type")
            attrs = _obj(m.get("attrs"))
            if mt in _PM_MARKS:
                run[_PM_MARKS[str(mt)]] = True
            elif mt == "link":
                run["link"] = attrs.get("href")
            elif mt == "textColor":
                run["color"] = attrs.get("color") or True
            elif mt == "subsup" and attrs.get("type") in ("sub", "sup"):
                run[str(attrs["type"])] = True
            else:
                self._marks[str(mt)] = self._marks.get(str(mt), 0) + 1
        return run

    def _property(self, p: dict[str, Any]) -> dict[str, Any] | None:
        ptype = str(p.get("type") or "")
        data = _obj(p.get("data"))
        head = {"id": p.get("id"), "title": p.get("title")}
        if ptype == "IMAGE":
            return {**head, "kind": "image", "url": data.get("url")}
        if ptype == "TEXT_FIELD":
            fragment = _obj(data.get("fragment"))
            return {**head, "kind": "textField", "children": self._blocks(fragment.get("content"))}
        if ptype == "RESOURCE_COLLECTION":
            items = [
                {"id": x.get("id"), "resourceId": x.get("resourceId") or x.get("id")}
                for x in data.get("items") or []
                if isinstance(x, dict)
            ]
            return {**head, "kind": "resourceCollection", "items": items, "filter": data.get("filter")}
        if ptype == "METER":
            return {**head, "kind": "meter", "items": data.get("items") or []}
        if ptype == "SPOTIFY_SINGLE":
            return {**head, "kind": "embed", "provider": "spotify", "url": data.get("url")}
        if ptype in _SHOWS_ROW:
            self._shows_row += 1
            return None
        return {**head, "kind": ptype or "property", **data}


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
    #: what the source read past (the export file's adaptations), one line each
    notes: list[str] = field(default_factory=list)
    #: the folder's ``producer.input``: the source's word
    producer_input: str = PRODUCER_INPUT


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


def _split_hidden(resources: Iterable[dict[str, Any]]) -> dict[str, str]:
    """resource id -> ``shown``, ``hidden`` (its own mark) or ``under`` (a hidden ancestor)."""
    rows = {r["id"]: r for r in resources}
    state: dict[str, str] = {}
    for rid, row in rows.items():
        if row.get("isHidden"):
            state[rid] = "hidden"
            continue
        verdict, seen, cur = "shown", {rid}, row.get("parentId")
        while isinstance(cur, str) and cur in rows and cur not in seen:
            if rows[cur].get("isHidden"):
                verdict = "under"
                break
            seen.add(cur)
            cur = rows[cur].get("parentId")
        state[rid] = verdict
    return state


def read_project(source: Source, project_id: str) -> Snapshot:
    """Walk a project: the project, its whole tree, then each resource, its page blocks and its
    timelines, hidden ones too (the converter marks them hidden; nothing is left out).

    The project and the tree must answer (a ``SourceError`` otherwise); a resource, a page or a
    timeline that does not is listed in ``unread`` and the walk goes on.
    """
    root = f"/projects/{_seg(project_id)}"
    project = source.get(root)
    if not isinstance(project, dict):
        raise SourceError(root, None, None, "the answer is not a project")
    resources = [r for r in _paged(source, f"{root}/resources", sized=True) if isinstance(r.get("id"), str)]
    snap = Snapshot(project_id, project, resources)
    snap.producer_input = str(getattr(source, "producer_input", PRODUCER_INPUT))
    for row in resources:
        rid = row["id"]
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
    snap.notes = list(getattr(source, "notes", None) or [])
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
    #: the document is hidden in LegendKeeper
    hidden: bool = False


@dataclass
class Hidden:
    """What the source hides, imported with ``hidden: true``: never dropped, never public."""

    #: resources marked hidden: elements carrying the mark
    resources: int = 0
    #: resources under a hidden one: elements carrying the mark
    under_hidden: int = 0
    #: hidden pages on a visible resource: each its own hidden Narrative
    documents: int = 0
    #: secret blocks in visible pages: each its own hidden Narrative
    secret_blocks: int = 0
    #: secret blocks inside text already hidden (a hidden resource or page): kept in place
    secrets_inside: int = 0
    #: hidden properties on a visible resource, held in its hidden-properties Narrative
    properties: int = 0
    #: hidden-properties Narratives made (one per visible resource with any)
    property_narratives: int = 0
    #: events hidden, on a hidden timeline or of a hidden resource: hidden Events
    events: int = 0
    #: Relations with a hidden end: hidden Relations
    relations: int = 0
    #: map documents hidden, or of a hidden resource: hidden Maps
    maps: int = 0
    #: pins hidden, or on a hidden Map: hidden Pins
    pins: int = 0


@dataclass(frozen=True)
class MapMade:
    """A map document made a Map (read from the export file; the API road does not read maps)."""

    #: the Map's name, ``<resource>: <document>``
    name: str
    resource: str
    #: max_x - min_x and max_y - min_y; None when the document gives no bounds
    width: int | None
    height: int | None
    pins: int
    #: ``url`` (image_url, LegendKeeper's address as given), ``id`` (a LegendKeeper asset id, not an
    #: address: kept as x_legendkeeper_map_id) or ``none``
    image: str
    #: the document carries no ``map`` object (no bounds, no image)
    mapless: bool = False
    hidden: bool = False
    #: the map's max_zoom: its pins' positions are scaled by 2^max_zoom; None when it gives none
    max_zoom: float | None = None


def _scale_said(zoom: float) -> str:
    """``positions scaled by 2^2 = 4`` (whole numbers printed whole)."""
    z = int(zoom) if zoom.is_integer() else zoom
    n = 2.0**zoom
    return f"positions scaled by 2^{z} = {int(n) if n.is_integer() else f'{n:g}'}"


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
    hidden: Hidden = field(default_factory=Hidden)
    not_imported: list[NotImported] = field(default_factory=list)
    #: every map document made a Map
    maps: list[MapMade] = field(default_factory=list)
    #: pins with no name of their own, each ``<name given> (pin <id> on <map>)``
    pins_named: list[str] = field(default_factory=list)
    #: pins with no element (no uri, or a uri naming no resource of the export), one line each
    pins_unlinked: list[str] = field(default_factory=list)
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
        h = self.hidden
        kinds = [
            (h.resources, "hidden resource (isHidden)", "hidden resources (isHidden)"),
            (h.under_hidden, "resource under a hidden one", "resources under a hidden one"),
            (
                h.documents,
                "hidden page on a visible resource, its own Narrative",
                "hidden pages on a visible resource, each its own Narrative",
            ),
            (
                h.secret_blocks,
                "secret block in a visible page, its own Narrative",
                "secret blocks in a visible page, each its own Narrative",
            ),
            (
                h.secrets_inside,
                "secret block inside hidden text, kept in place",
                "secret blocks inside hidden text, kept in place",
            ),
            (h.events, "hidden timeline event", "hidden timeline events"),
            (h.relations, "Relation with a hidden end", "Relations with a hidden end"),
            (h.maps, "hidden Map (its document or resource hidden)", "hidden Maps (their document or resource hidden)"),
            (h.pins, "hidden Pin (the pin or its Map hidden)", "hidden Pins (the pin or its Map hidden)"),
        ]
        said = [f"{n} {one if n == 1 else many}" for n, one, many in kinds if n]
        if h.properties:
            said.append(
                f"{h.property_narratives} hidden-properties Narrative{'' if h.property_narratives == 1 else 's'}"
                f" holding {h.properties} hidden propert{'y' if h.properties == 1 else 'ies'}"
            )
        if said:
            lines.append("Hidden as the source hides it (elements carrying hidden: true): " + "; ".join(said) + ".")
        if self.maps:
            lines.append(f"Map documents, each a Map and its pins Pins ({len(self.maps)}):")
            for m in self.maps:
                pins = f"{m.pins} pin{'' if m.pins == 1 else 's'}"
                if m.mapless:
                    what = f"no map object (no bounds, no image): a Map with no width, height or image_url, {pins}"
                else:
                    size = f"{m.width} x {m.height}" if m.width is not None and m.height is not None else "no bounds"
                    image = {
                        "url": "image_url LegendKeeper's address",
                        "id": "its image a LegendKeeper asset id, not an address: kept as x_legendkeeper_map_id,"
                        " no image_url",
                        "none": "no image",
                    }[m.image]
                    what = f"{size}, {pins}, {image}"
                    if m.pins and m.width is not None and m.height is not None:
                        what += (
                            f", {_scale_said(m.max_zoom)}"
                            if m.max_zoom is not None
                            else ", no max_zoom: its pins have no x, y (the scale is not known, never guessed;"
                            " pos kept as x_legendkeeper_pos)"
                        )
                lines.append(f"  - {m.name!r}{' (hidden)' if m.hidden else ''}: {what}")
            if any(m.image == "url" for m in self.maps):
                lines.append(
                    "  A Map's image_url is LegendKeeper's own address, as given, never copied: the image lives on"
                    " LegendKeeper's host and loads only as long as that account's asset does."
                )
        if self.pins_named:
            lines.append(f"Pins with no name of their own, named as LegendKeeper shows them ({len(self.pins_named)}):")
            lines += [f"  - {p}" for p in self.pins_named]
        if self.pins_unlinked:
            lines.append(f"Pins with no element ({len(self.pins_unlinked)}):")
            lines += [f"  - {p}" for p in self.pins_unlinked]
        if self.not_imported:
            lines.append(f"Documents not imported ({len(self.not_imported)}):")
            lines += [
                f"  - {n.kind} {n.document!r} on {n.resource!r}{' (hidden)' if n.hidden else ''}"
                for n in self.not_imported
            ]
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
    """One resource's element being built, or a hidden Narrative beside one (``owner`` set)."""

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
    #: the element carries ``hidden: true``
    hidden: bool = False
    #: for a hidden Narrative made from a resource's hidden page, secret or properties: that resource
    owner: _Item | None = None


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
    def __init__(self, snap: Snapshot, type_map: Mapping[str, str]) -> None:
        self.snap = snap
        self.type_map = dict(type_map)
        self.report = ImportReport(project=snap.project_id, world={}, unread=list(snap.unread), notes=list(snap.notes))
        self.rows = {r["id"]: r for r in snap.resources}
        self.state = _split_hidden(snap.resources)
        self.items: dict[str, _Item] = {}
        #: hidden Narratives made beside resources (hidden pages, secrets, hidden properties)
        self.extra: list[_Item] = []
        self._secrets: dict[str, list[_Item]] = {}
        self._secret_n: dict[str, int] = {}
        self._hidden_props: dict[str, _Item] = {}
        #: the document whose blocks are being read (keys a secret block's id)
        self._doc = ""
        self.relations: list[dict[str, Any]] = []
        self.events: list[dict[str, Any]] = []
        self.event_ids: set[str] = set()
        self.maps: list[dict[str, Any]] = []
        self.pins: list[dict[str, Any]] = []
        #: map documents read through the API (no bounds or pins in its answers): not imported
        self.api_maps = 0
        self.placed_pins = 0
        self.unplaced_pins = 0
        #: pins with a pos on a map with bounds but no max_zoom: the scale is not known, so no x, y
        self.unscaled_pins = 0
        self.marks: dict[str, int] = {}
        self.unsupported = 0
        self.unknown: dict[str, int] = {}
        self.map_blocks = 0
        self.blank = 0
        self.empty_props = 0
        #: names of the resources in LegendKeeper's templates folder
        self.templates: list[str] = []
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
                self.report.hidden.resources += 1
            elif st == "under":
                self.report.hidden.under_hidden += 1
            tags = [t for t in row.get("tags") or [] if isinstance(t, str)]
            etype, by = self._type_of(tags)
            name = str(row.get("name") or "").strip() or f"Untitled ({rid})"
            item = _Item(
                etype,
                self._id(rid),
                name,
                rid,
                typed=by != "untyped" and not by.startswith("ambiguous"),
                row=row,
                hidden=st != "shown",
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
            elif parent_id == TEMPLATES_PARENT:
                item.ext[f"{EXT_PREFIX}template"] = True
                self.templates.append(item.name)
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
        # a hidden page on a visible resource is its own Narrative, so it does not count here
        pages = [d for d in docs if d.get("type") == "page" and (item.hidden or not d.get("isHidden"))]
        parts: list[str] = []
        for doc in docs:
            dtype, dname = doc.get("type"), str(doc.get("name") or "")
            if dtype == "page":
                answer = self.snap.blocks.get(doc.get("id", ""))
                if answer is None:
                    continue  # listed in unread
                self._doc = str(doc.get("id"))
                blocks = [b for b in answer.get("blocks") or [] if isinstance(b, dict)]
                if blocks and blocks[0].get("kind") == "heading" and _plain(blocks[0].get("content")) == item.name:
                    blocks = blocks[1:]
                if doc.get("isHidden") and not item.hidden:
                    self._hidden_page(item, doc, dname, blocks)
                    continue
                md = "\n\n".join(self._blocks(item, blocks))
                if md:
                    parts.append(f"## {dname}\n\n{md}" if len(pages) > 1 else md)
            elif dtype == "blank":
                self.blank += 1
            elif dtype == "time":
                self._timeline(item, doc)
            elif dtype == "map" and isinstance(doc.get("pins"), list):
                self._map(item, doc)
            else:
                if dtype == "map":
                    self.api_maps += 1
                self.report.not_imported.append(
                    NotImported(str(dtype or "unknown"), item.name, dname, hidden=bool(doc.get("isHidden")))
                )
        self._doc = "properties"
        for prop in full.get("properties") or []:
            if isinstance(prop, dict):
                self._property(item, prop)
        text = "\n\n".join(parts)
        if text:
            if "description" in item.fields:
                item.ext[f"{EXT_PREFIX}body"] = text
            else:
                item.fields["description"] = text

    # -- what the source hides on a visible resource ---------------------------

    def _narrative(self, owner: _Item, key: str, name: str) -> _Item:
        """A hidden Narrative beside ``owner``, linked back to it when its body is made."""
        narr = _Item(
            "narrative", self._id(key), name, owner.lk_id, typed=False, row=owner.row, hidden=True, owner=owner
        )
        narr.taken |= _RESERVED
        self.extra.append(narr)
        return narr

    def _hidden_page(self, item: _Item, doc: dict[str, Any], dname: str, blocks: list[dict[str, Any]]) -> None:
        narr = self._narrative(item, f"document:{item.lk_id}:{doc.get('id')}", f"{item.name}: {dname or 'Page'}")
        narr.ext[f"{EXT_PREFIX}document"] = doc.get("id")
        story = "\n\n".join(self._blocks(narr, blocks))
        if story:
            narr.fields["story"] = story
        self.report.hidden.documents += 1

    def _secret(self, item: _Item, b: dict[str, Any]) -> None:
        """A secret block in a visible page: its own hidden Narrative; the page keeps the rest."""
        where = f"{item.lk_id}:{self._doc}"
        n = self._secret_n[where] = self._secret_n.get(where, 0) + 1
        title = str(b.get("title") or "").strip() or "Secret"
        narr = self._narrative(item, f"secret:{where}:{n}", f"{item.name}: {title}")
        if self._doc != "properties":
            narr.ext[f"{EXT_PREFIX}document"] = self._doc
        story = self._children(narr, b)
        if story:
            narr.fields["story"] = story
        self._secrets.setdefault(item.lk_id, []).append(narr)
        self.report.hidden.secret_blocks += 1

    def _props_narrative(self, item: _Item) -> _Item:
        narr = self._hidden_props.get(item.lk_id)
        if narr is None:
            narr = self._narrative(item, f"properties:{item.lk_id}", f"{item.name}: hidden properties")
            self._hidden_props[item.lk_id] = narr
            self.report.hidden.property_narratives += 1
        return narr

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
            if not item.hidden:
                self._secret(item, b)
                return None
            self.report.hidden.secrets_inside += 1  # the text around it is hidden already
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

    _MISSING = "no such resource in the project's tree"

    def _mention(self, item: _Item, mention: dict[str, Any], text: str) -> None:
        rid = str(mention.get("resourceId") or "")
        target = self.items.get(rid)
        if target is None:
            self.report.unresolved.append(Unresolved(item.name, f"mention {text!r}", rid, self._MISSING))
            return
        if target is not item and target.eid not in item.mentions:
            item.mentions.append(target.eid)
        note = f"{item.name!r}: visible text mentions the hidden {target.name!r} by name"
        if target.hidden and not item.hidden and note not in self.report.notes:
            self.report.notes.append(note)

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
        if prop.get("isHidden") and not item.hidden:
            item = self._props_narrative(item)  # the hidden-properties Narrative takes it, whole
            self.report.hidden.properties += 1
        kind = prop.get("kind")
        title = str(prop.get("title") or "").strip()
        if kind == "keyValue":
            for row in prop.get("rows") or []:
                if isinstance(row, dict):
                    self._key_value(item, row)
        elif kind == "resourceLink" or (kind == "resourceCollection" and prop.get("items")):
            self._link(item, prop, title or ("Links" if kind == "resourceLink" else "Collection"))
        elif kind == "resourceCollection" and prop.get("filter") is not None:
            self._keep(item, title or "collection", prop.get("filter"), "a collection chosen by a filter: not expanded")
        elif kind in ("resourceCollection", "meter", "embed") and not (prop.get("items") or prop.get("url")):
            self.empty_props += 1  # an empty collection, meter or embed (a template's sidebar) carries nothing
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
                self.report.unresolved.append(Unresolved(item.name, f"link {title!r}", rid, self._MISSING))
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
        if item.hidden or target.hidden:
            body["hidden"] = True
            self.report.hidden.relations += 1
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
                else:
                    self.report.notes.append(
                        f"event {ev.get('name')!r} on {item.name!r} comes from {uri['rid']}, not in the tree;"
                        f" kept under {item.name!r}"
                    )
            etype = ev.get("type")
            if etype in ("placeholder", "invisible-placeholder"):
                self.placeholders += 1
                continue
            # hidden itself, of a hidden resource, or on this hidden timeline (a chained one's own mark is its own)
            hidden = bool(ev.get("isHidden")) or owner.hidden or (owner is item and bool(doc.get("isHidden")))
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
                    self.report.unresolved.append(Unresolved(name, "event uri", link["rid"], self._MISSING))
                elif fname is not None and FIELD_KINDS["event"][fname] == "multi_link":
                    fields.setdefault(fname, []).append(target.eid)
            body: dict[str, Any] = {"type": "event", "id": self._id("event", ev_id), "name": name}
            if hidden:
                body["hidden"] = True
                self.report.hidden.events += 1
            for fname in FIELD_KINDS["event"]:
                if fname in fields:
                    body[fname] = fields[fname]
            body.update(ext)
            self.events.append(body)
            made += 1
        self.report.notes.append(
            f"timeline {doc.get('name')!r} on {item.name!r}: {made} event{'' if made == 1 else 's'} (start and end"
            " kept as minutes, with the formatted date when the source gives one; start_date and end_date unset)"
        )

    # -- maps ----------------------------------------------------------------

    def _map(self, item: _Item, doc: dict[str, Any]) -> None:
        """A map document (from the export file) as a Map, each of its pins a Pin on it."""
        did = str(doc.get("id"))
        dname = str(doc.get("name") or "").strip()
        name = f"{item.name}: {dname or 'Map'}"
        hidden = item.hidden or bool(doc.get("isHidden"))
        fields: dict[str, Any] = {}
        ext: dict[str, Any] = {f"{EXT_PREFIX}document": did}
        if item.etype == "location":
            fields["location"] = item.eid
        else:
            ext[f"{EXT_PREFIX}resource"] = item.eid
        m = doc.get("map")
        bounds: dict[str, float] = {}
        zoom: float | None = None
        image = "none"
        if isinstance(m, dict):
            zoom = _number(m.get("max_zoom"))
            mid = m.get("mapId")
            if isinstance(mid, str) and _HTTP.match(mid):
                fields["image_url"] = mid  # as given: LegendKeeper's host, never copied
                image = "url"
            elif isinstance(mid, str) and mid:
                ext[f"{EXT_PREFIX}map_id"] = mid  # an asset id, not an address
                image = "id"
            bounds = {k: v for k in _BOUNDS if (v := _number(m.get(k))) is not None}
            if len(bounds) == len(_BOUNDS):
                fields["width"] = _whole(bounds["max_x"] - bounds["min_x"])
                fields["height"] = _whole(bounds["max_y"] - bounds["min_y"])
            if bounds:
                ext[f"{EXT_PREFIX}bounds"] = {k: m[k] for k in _BOUNDS if k in bounds}
            if "max_zoom" in m:
                ext[f"{EXT_PREFIX}max_zoom"] = m["max_zoom"]
            rest = {
                k: v
                for k, v in m.items()
                if k not in ("mapId", "max_zoom", *bounds) and not (k == "locatorId" and v == mid)
            }
            if rest:
                ext[f"{EXT_PREFIX}map"] = rest
        map_id = self._id("map", item.lk_id, did)
        body: dict[str, Any] = {"type": "map", "id": map_id, "name": name}
        if hidden:
            body["hidden"] = True
            self.report.hidden.maps += 1
        for fname in FIELD_KINDS["map"]:
            if fname in fields:
                body[fname] = fields[fname]
        body.update(ext)
        self.maps.append(body)
        pins = [p for p in doc.get("pins") or [] if isinstance(p, dict)]
        for n, pin in enumerate(pins, 1):
            self._pin(pin, n, item, did, name, map_id, hidden, bounds, zoom)
        self.report.maps.append(
            MapMade(
                name,
                item.name,
                fields.get("width"),
                fields.get("height"),
                len(pins),
                image,
                mapless=not isinstance(m, dict),
                hidden=hidden,
                max_zoom=zoom,
            )
        )

    def _pin(
        self,
        pin: dict[str, Any],
        n: int,
        item: _Item,
        did: str,
        map_name: str,
        map_id: str,
        map_hidden: bool,
        bounds: dict[str, float],
        zoom: float | None,
    ) -> None:
        pid = str(pin.get("id") or f"#{n}")
        uri = pin.get("uri")
        link = _LK_URI.match(uri) if isinstance(uri, str) else None
        target = self.items.get(link["rid"]) if link is not None else None
        name = str(pin.get("name") or "").strip()
        if not name:  # LegendKeeper shows the linked page's name on a pin that has none
            name = target.name if target is not None else f"Untitled pin ({pid})"
            self.report.pins_named.append(f"{name!r} (pin {pid} on {map_name!r})")
        fields: dict[str, Any] = {"map": map_id}
        if target is not None:
            fields["element_type"] = target.etype
            fields["element_id"] = target.eid
        elif link is not None:
            self.report.pins_unlinked.append(
                f"{name!r} on {map_name!r}: its uri names {link['rid']}, {self._MISSING}; a Pin with no element"
            )
        else:
            self.report.pins_unlinked.append(f"{name!r} on {map_name!r}: no uri; a Pin with no element")
        pos = pin.get("pos")
        yx = [_number(v) for v in pos] if isinstance(pos, list) and len(pos) == 2 else []
        if len(yx) == 2 and yx[0] is not None and yx[1] is not None and len(bounds) == len(_BOUNDS):
            if zoom is None:  # the scale is not known: never guessed
                self.unscaled_pins += 1
            else:
                # LegendKeeper's pos is [y, x] in zoom-0 units (an image pixel / 2^max_zoom), y from 0 at the top
                # down to min_y; the bounds are image pixels, and OnlyWorlds counts from the bottom left
                scale = 2.0**zoom
                fields["x"] = _whole(yx[1] * scale - bounds["min_x"])
                fields["y"] = _whole(yx[0] * scale - bounds["min_y"])
                self.placed_pins += 1
        else:
            self.unplaced_pins += 1
        hidden = map_hidden or pin.get("isHidden") is True
        body: dict[str, Any] = {"type": "pin", "id": self._id("pin", item.lk_id, did, pid), "name": name}
        if hidden:
            body["hidden"] = True
            self.report.hidden.pins += 1
        for fname in FIELD_KINDS["pin"]:
            if fname in fields:
                body[fname] = fields[fname]
        body[f"{EXT_PREFIX}id"] = pid
        if pos is not None:
            body[f"{EXT_PREFIX}pos"] = pos
        if uri:
            body[f"{EXT_PREFIX}uri"] = uri
        rest = {k: v for k, v in pin.items() if k not in _PIN_SAID}
        if rest:
            body[f"{EXT_PREFIX}pin"] = rest
        note = f"{name!r}: a visible pin on {map_name!r} places the hidden {target.name!r}" if target else ""
        if target is not None and target.hidden and not hidden and note not in self.report.notes:
            self.report.notes.append(note)
        self.pins.append(body)

    # -- the bodies ----------------------------------------------------------

    def bodies(self) -> dict[str, list[dict[str, Any]]]:
        out: dict[str, list[dict[str, Any]]] = {}
        for narrs in self._secrets.values():
            if len(narrs) > 1:  # several secrets on one resource: numbered in the order they were read
                for n, narr in enumerate(narrs, 1):
                    narr.name = f"{narr.name} {n}"
        for item in [*self.items.values(), *self.extra]:
            body: dict[str, Any] = {"type": item.etype, "id": item.eid, "name": item.name}
            if item.hidden:
                body["hidden"] = True
            if item.owner is not None:
                self._link_back(item, item.owner)
                item.ext[f"{EXT_PREFIX}parent"] = item.owner.eid
            for fname in FIELD_KINDS[item.etype]:
                if fname in item.fields and fname != "name":
                    body[fname] = item.fields[fname]
            body.update(item.ext)
            if item.mentions:
                body[f"{EXT_PREFIX}mentions"] = item.mentions
            out.setdefault(item.etype, []).append(body)
        for body in self.relations + self.events + self.maps + self.pins:
            out.setdefault(body["type"], []).append(body)
        self.report.counts = {t: len(b) for t, b in sorted(out.items())}
        self._notes()
        return out

    @staticmethod
    def _link_back(narr: _Item, owner: _Item) -> None:
        """A hidden Narrative's link to its resource: Narrative's field for the resource's type."""
        if owner.etype == "narrative":
            narr.fields["parent_narrative"] = owner.eid
        elif owner.etype in _NARRATIVE_FIELD_FOR:
            narr.fields[_NARRATIVE_FIELD_FOR[owner.etype]] = [owner.eid]

    def _notes(self) -> None:
        n = self.report.notes
        if self.templates:
            listed = ", ".join(repr(t) for t in self.templates)
            n.append(
                f"{len(self.templates)} resource{'' if len(self.templates) == 1 else 's'} in LegendKeeper's templates"
                f" folder (parentId {TEMPLATES_PARENT!r}), imported with x_legendkeeper_template true: {listed}"
            )
        if self.blank:
            n.append(f"{self.blank} blank document{'' if self.blank == 1 else 's'}: empty by LegendKeeper's definition")
        if self.empty_props:
            e = self.empty_props
            n.append(
                f"{e} empty collection, meter or embed propert{'y' if e == 1 else 'ies'} (no items, no URL): nothing"
                " to keep"
            )
        if self.placeholders:
            n.append(f"{self.placeholders} timeline placeholder{'' if self.placeholders == 1 else 's'}: layout only")
        if self.map_blocks:
            n.append(f"{self.map_blocks} map block{'' if self.map_blocks == 1 else 's'}: a line naming the map")
        if self.placed_pins:
            n.append(
                f"{self.placed_pins} pin{'' if self.placed_pins == 1 else 's'} placed: LegendKeeper's pos is [y, x]"
                " in zoom-0 units (an image pixel divided by 2^max_zoom), y from 0 at the map's top down to min_y,"
                " and the bounds are image pixels; x is x * 2^max_zoom - min_x and y is y * 2^max_zoom - min_y"
                " (OnlyWorlds counts from the bottom left), rounded to whole numbers, the exact pair kept as"
                " x_legendkeeper_pos (measured on two pins of one map, Seethe's, OW Market h40 #11426, #11429)"
            )
        if self.unplaced_pins:
            n.append(
                f"{self.unplaced_pins} pin{'' if self.unplaced_pins == 1 else 's'} with no x, y: no pos, or a map with"
                " no bounds (pos kept as x_legendkeeper_pos when given)"
            )
        if self.unscaled_pins:
            n.append(
                f"{self.unscaled_pins} pin{'' if self.unscaled_pins == 1 else 's'} with no x, y on a map with no"
                " max_zoom: LegendKeeper's pos is scaled by 2^max_zoom, so with none the place is not guessed (pos"
                " kept as x_legendkeeper_pos)"
            )
        if self.api_maps:
            n.append(
                f"{self.api_maps} map document{'' if self.api_maps == 1 else 's'} read through the API, not imported:"
                " the API's map shape (bounds, pins) is not known here, never read on the wire; LegendKeeper's export"
                " file (--file) reads them"
            )
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
            "producer": {"tool": "onlyworlds", "version": __version__, "input": self.snap.producer_input},
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
    source: Source | str | os.PathLike[str],
    project_id: str | None = None,
    out_dir: str | os.PathLike[str] | None = None,
    *,
    plan_only: bool = False,
    type_map: Mapping[str, str] | None = None,
) -> ImportReport:
    """Read a LegendKeeper project from ``source`` into a world folder at ``out_dir``, which must
    not exist or be empty.

    ``source`` is a ``Source`` (``ApiSource(key)``, with the project's id as ``project_id``), or
    the path of LegendKeeper's export file (``.lk`` or the JSON type), read through ``FileSource``;
    for a file, ``project_id`` is optional and keys the ids on the project's own id (the module
    docstring says what keys them without it). What LegendKeeper hides is imported carrying
    ``hidden: true`` and counted in the report. ``type_map`` maps a tag to one of the 22 types
    (``{"faction": "institution"}``), besides the tags that are type names. With ``plan_only``
    nothing is written (``out_dir`` may be None) and the report says what would be. Raises
    ``FileExistsError`` for an ``out_dir`` that is not empty, ``FileNotFoundError`` for a missing
    export file, ``ValueError`` for a ``type_map`` that names no type or a file that is not an
    export, ``SourceError`` when the project or its tree cannot be read.
    """
    mapping = _type_map(type_map)
    out = Path(out_dir) if out_dir is not None else None
    if not plan_only:
        if out is None:
            raise ValueError("give an out_dir, or plan_only=True")
        if out.exists() and (not out.is_dir() or any(out.iterdir())):
            raise FileExistsError(f"{out} exists and is not an empty directory; a folder is written whole, once")
    if isinstance(source, (str, os.PathLike)):
        source = FileSource(source, project_id)
    if isinstance(source, FileSource):
        if project_id is not None and project_id.strip() != source.project_id:
            raise ValueError("give the project id to FileSource(path, project_id), which keys the ids on it")
        project_id = source.project_id
    if not isinstance(project_id, str) or not project_id.strip():
        raise ValueError("give the LegendKeeper project id")
    snap = read_project(source, project_id.strip())
    conv = _Converter(snap, mapping)
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
    ap.add_argument(
        "--project", help="the LegendKeeper project id (the API key is bound to it; with --file, it keys the ids)"
    )
    ap.add_argument("--file", type=Path, help="LegendKeeper's export file (.lk, or the JSON type): no key, no API")
    ap.add_argument("--plan", action="store_true", help="read the project, print what would become what, write nothing")
    ap.add_argument("--key-file", type=Path, help=f"a file holding the API key (else ${KEY_ENV})")
    ap.add_argument("--map", action="append", default=[], metavar="TAG=TYPE", help="type the resources with this tag")
    args = ap.parse_args(argv)
    if args.out is None and not args.plan:
        print("give OUT-DIR, or --plan", file=sys.stderr)
        return 2
    if args.file is None and not args.project:
        print("give --project ID (the API), or --file EXPORT (LegendKeeper's export file)", file=sys.stderr)
        return 2
    if args.file is not None and args.key_file is not None:
        print("--key-file is for the API; an export file needs no key", file=sys.stderr)
        return 2
    pairs: dict[str, str] = {}
    for item in args.map:
        tag, eq, etype = item.partition("=")
        if not eq or not tag.strip() or not etype.strip():
            print(f"--map {item!r}: write TAG=TYPE (faction=institution)", file=sys.stderr)
            return 2
        pairs[tag] = etype
    try:
        src: Source | Path
        if args.file is not None:
            src = args.file
        else:
            src = source if source is not None else ApiSource(_read_key(args.key_file), transport=transport)
        report = import_legendkeeper(src, args.project, args.out, plan_only=args.plan, type_map=pairs)
    except (FileExistsError, FileNotFoundError, ValueError, SourceError) as exc:
        print(f"{exc}", file=sys.stderr)
        return 2
    sys.stdout.write(report.render())
    return 0


if __name__ == "__main__":
    sys.exit(main())

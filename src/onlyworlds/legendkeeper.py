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
two real exports** of one project (version 1, 2026-10-23, a maintainer's project on a trial account:
``tests/fixtures/legendkeeper/the-quay-world.lk``, and ``the-quay-world-3.json`` a few hours on,
with a map added and two pins on it; the account's ids and its map image's asset id replaced
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
  ride on the document as ``pins``, beside the ``map`` object. The API serves the same map as the
  document's ``mapImage`` (bounds in zoom-0 units) and its pins under ``/features``; ``read_project``
  puts them on the document in this shape (``_api_map``), so both roads make the same Maps and Pins
  (the tutorial map's 16 pins land on the same pixels from either, 2026-10-25).
- a board document's ``content`` is ``{shapes, bindings, shapesV2}``, ``shapesV2`` a list of
  ``{key, val}`` whose ``val`` is a tldraw record (``typeName`` shape, binding, asset, page or
  document); the records ride on the document as ``board``, ``{shapes, bindings, assets, pages}``
  split by ``typeName`` (``content.shapes`` and ``content.bindings`` when there is no ``shapesV2``).
  The API serves the same records under ``/docs/<id>/board``; ``read_project`` puts them on the
  document in this shape, so both roads make the same board (the tutorial's board, 154 shapes and
  52 bindings, the same records from either but for the resource ids, which are each project's).
- not kept, named in the report: ``exportId``, ``exportedAt`` and ``hash`` (the report names the
  export; two exports of one project give one folder), ``createdBy`` (an account id),
  ``schemaVersion``, ``showPropertyBar``, ``isFullWidth``, document locators, ``transforms`` and
  ``sources``.
- the export's ``calendars`` list answers as the API's calendars route does. Its calendar shape is
  assumed equal to the API's and is unproven on a real file: the export of 2026-10-23 holds none,
  though its timeline names a calendar (which the report then names as not among the calendars).

**A world pushed from OnlyWorlds comes back as itself.** A push into LegendKeeper writes the element's
id in a key-value row ``onlyworlds-id``, its supertype and subtype as tags ``ow-supertype:<value>`` and
``ow-subtype:<value>``, extension keys (``x_*``, ``atlas_*``, ``shadow_*``) as rows under their own names
(a list or an object as JSON text), and what had no slot in ``onlyworlds-unmapped``. Read back, a uuid in
``onlyworlds-id`` is the element's id (one claimed twice, or not a uuid, is kept and the id derived), the
tags fill the two fields, the extension keys return under their names, and the unmapped rows go to the
report. Measured on a push of ten Moppetopia elements: ids, names, descriptions, scalar fields and the
links inside the slice all equal (2026-10-25).

LegendKeeper's starter pages (the tutorial a new project is seeded with: Wiki City, Temple of
Time, ...) travel like the rest: nothing in the file marks them, so they are imported. On the one
real export their ``createdBy`` is another account than the person's, which is a tell, not a rule.
The templates (Character, Location, ...) are marked: they sit in LegendKeeper's templates folder,
``parentId`` ``templates`` (no resource has that id), and each is imported carrying
``x_legendkeeper_template: true``, the report naming them.

The Markdown zip LegendKeeper also exports is not a source: it loses the tags, the properties,
the hidden marks and the ids.

**Observed** (2026-10-22, live on a real project; the recorded answers are this package's
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
  ``x_legendkeeper_parent`` the resource it belongs to. When the timeline's calendar is exact (the
  next point), ``start_date`` and ``end_date`` are days: the minutes divided by the minutes in the
  calendar's day, rounded down (minute -1 is day -1); otherwise they are left unset and the minutes
  stand alone. Placeholders are layout and are counted. The timeline
  itself is a Narrative, ``<resource>: <document>``, with supertype ``Timeline``, its ``events`` the
  Events read on it, linked to its resource as a hidden page's Narrative is; each lane is a child
  Narrative (supertype ``Timeline``, subtype ``lane``, ``parent_narrative`` the timeline) holding that
  lane's Events. Hidden with its resource or document, a lane also on its own mark.
- **A calendar a timeline names** (its ``calendarId``, among the project's calendars: ``GET
  /projects/<id>/calendars``, read once; every project carries six presets, read live 2026-10-25)
  **becomes a Construct** with supertype ``calendar``, named by the calendar, its ``description``
  the calendar's, ``x_legendkeeper_id`` its id and ``x_legendkeeper_calendar`` the whole calendar as
  read, so a push back is exact. It carries ``atlas_calendar`` (the calendar profile,
  schema-dist ``profiles/calendar.md``: grain ``day``, one step a day) only when the profile can say
  the calendar exactly; ``_calendar_config`` holds the rules and what witnessed them. Of the
  presets, five are exact: Eberron, Exandria and Greyhawk in the profile's version 1, Gregorian
  and Harptos in its version 2 (schema-dist serial 68: a leap rule with exceptions, read on the
  year as shown). Scrolls is not: its later eras restart their years, which no probe has
  witnessed. The report names each calendar made, exact or kept raw
  with its reasons, and counts the calendars no timeline names, which are not made. A calendar id
  not among the calendars is a report line, and its events keep their minutes only. The Construct
  is hidden while only hidden timelines name it.
- **A map document** (from either road) **becomes a Map** (ruled
  2026-10-23), named ``<resource>: <document>`` as a hidden page's Narrative is: ``width`` is
  ``max_x - min_x`` and ``height`` ``max_y - min_y`` from the document's ``map`` bounds (whole
  numbers), the bounds kept as ``x_legendkeeper_bounds`` and ``max_zoom`` as
  ``x_legendkeeper_max_zoom``. ``image_url`` is the map's ``mapId`` only when it is an http(s)
  address, as given and never copied (ruled 2026-10-23): the image lives on LegendKeeper's host and
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
  Measured on two pins of one quay map (an 800 by 600 image, bounds x 0..800, y -600..0,
  ``max_zoom`` 2; 2026-10-23): the first, read at image pixel
  (127, 110) from the top left, is stored ``[-27.5, 32]`` (times 4, pixel 128, 110): x 128, y 490;
  the second, read at about (796, 524), is stored ``[-131.118, 199.314]``: x 797, y 76. Both fit
  the scaled reading and neither the unscaled one. A pin on a map with no bounds has no x, y, and
  so does a pin on a map with no ``max_zoom`` (the scale is not known, never guessed; named in the
  report). Its icon and label (``iconGlyph``, ``iconColor``, ``iconShape``, ``labelSize``,
  ``labelVisibility``, ``isSynced`` and any other key but its id, name, pos, uri, hidden mark, rank
  and timestamps) are kept together as ``x_legendkeeper_pin``, its id as ``x_legendkeeper_id``,
  its uri as ``x_legendkeeper_uri``.
- **A board document becomes a Map with supertype Board** (ruled 2026-10-25), named
  ``<resource>: <document>``, with no image; ``location`` and ``x_legendkeeper_document`` as a
  map's. **The board's records are kept whole** (``{shapes, bindings, assets, pages}``, each list
  in the order read), so a push back can restore the canvas and nothing the elements below do not
  carry (styles, rotation, the shapes that make nothing) is lost: not on the Map (the tutorial
  board's are 110 KB, past what an element may carry online) but in the folder's records (folder
  spec §4.5), one file per board, ``records/legendkeeper/boards/<document id>.json``, the Map's
  ``x_legendkeeper_board_record`` that path, and an entry in ``records/RECORDS.json`` (producer
  ``legendkeeper``, ``deltas`` false), ``"private": true`` when any board is hidden or shows a
  hidden page, which marks the whole ``records/legendkeeper/`` (an export or a share leaves it out
  unless asked). A plan writes none. A board is a tldraw
  canvas: each shape's ``x``, ``y`` and ``rotation`` (radians) are in its parent's space (a frame
  or a group; ``page:...`` is the canvas), so a shape's page-space origin is its parent's origin
  plus the parent's page rotation applied to ``(x, y)``, and its page rotation the parent's plus
  its own. The Map spans every point placed below and the corners
  of every shape with a size: ``width`` and ``height`` that box's size, whole numbers, the box kept
  as ``x_legendkeeper_board_extent`` (page space, y down). tldraw's y counts down, OnlyWorlds' up
  from the bottom left: ``x`` is ``X - min_x`` and ``y`` ``max_y - Y``, a half rounded up, the
  page-space pair kept as ``x_legendkeeper_board_pos``. Everything made from a board carries
  ``x_legendkeeper_board_map`` (the board's Map) and ``x_legendkeeper_id`` (the shape's id):
  - a page card (an ``element`` shape) is a Pin at the card's centre on the element of its
    ``resourceId``. A card whose ``documentId`` names a board document of that resource is a Pin
    on that board's Map, which takes ``parent_map`` this board's Map (unless it has one, or that
    would close a loop; named in the report); a ``documentId`` naming a map document places that
    Map, with no ``parent_map``. A card whose
    resource is not in the project is a Pin with no element, named. A card on a hidden page (its
    resource, its document or the board it shows hidden) is a hidden Pin.
  - a frame is a Zone (its ``name``, else ``Frame``; subtype ``Frame``, ``shape`` ``polygon``) and
    four Markers at its corners, ``order`` 0 to 3 from its top left, clockwise.
  - an arrow whose two ends are both bound (tldraw's arrow bindings) to a page card whose resource
    is an element, or to a frame (its Zone), is a Relation, supertype ``Board link``, named by the
    arrow's label (else ``Board link``): the two elements linked as a titled link's Relation links
    them (a Zone on ``zones``), ``x_legendkeeper_source``/``x_legendkeeper_target`` start and end,
    ``x_legendkeeper_board_map`` so a reader draws it on that board only. An arrow whose two ends
    are one element (a frame to itself, two cards of one page) is counted, not made, and so is
    every other arrow; each stays in the board's records.
  - a sticky note or a text is a Narrative, supertype ``Note``, subtype ``note`` or ``text``,
    named by its first line (80 characters at most), its whole text its ``description``, and a
    Pin placing it: a note's at its centre, a text's at its origin (a text shape has a width but
    no height). An empty one is counted, not made.
  - geo shapes, drawings, images, bookmarks and groups are counted per type, a geo's text and a
    bookmark's URL named in the count.
- **Not imported**, named in the report with their resource: a map or board document whose
  content could not be read (the reason is under unread). ``blank`` documents are empty and counted.
  Not kept, named in the report: a resource's and an event's icons, sibling order, timestamps, lock
  state, permissions, banners, event colours, and the server's computed event dates (they follow
  from the minutes and calendar).

**What the source hides, the folder hides: never dropped, never public** (ruled
2026-10-23). Each hidden thing is an element carrying ``hidden: true`` at the top of its body
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
- a pin whose ``isHidden`` is true: its Pin (no real file has one yet: the tests plant it);
- a board document whose ``isHidden`` is true, or on a hidden resource: its Map and everything
  made from it; on a visible board, a card on a hidden page, and an arrow either end of which is.

A visible text that mentions a hidden element by name, or a visible pin that places one, is named
in the report. A hidden blank document is counted as a visible one is.

**Ids are UUIDv5** in ``LEGENDKEEPER_NAMESPACE``: of ``legendkeeper:<project id>:<resource id>`` for
a resource, ``legendkeeper:<project id>:event:<event id>`` for an event,
``legendkeeper:<project id>:link:<resource id>:<list id>:<item id>`` for a Relation (a kind word,
since LegendKeeper lets a client choose 8- or 24-character ids for resources and events alike),
``legendkeeper:<project id>:document:<resource id>:<document id>`` for a hidden document's
Narrative, ``legendkeeper:<project id>:secret:<resource id>:<document id>:<n>`` for the n-th secret
block of a page (the export gives a block no id, so both roads count them) and
``legendkeeper:<project id>:properties:<resource id>`` for a resource's hidden properties,
``legendkeeper:<project id>:map:<resource id>:<document id>`` for a Map and
``legendkeeper:<project id>:pin:<resource id>:<document id>:<pin id>`` for a Pin;
``legendkeeper:<project id>:board:<resource id>:<document id>`` for a board's Map, with ``:<shape
id>`` for what a shape makes (a card's Pin, a frame's Zone, an arrow's Relation, a note's
Narrative), its Pin ``:<shape id>:pin`` and a frame's Markers ``:<shape id>:<order>``;
``legendkeeper:<project id>:calendar:<calendar id>`` for a calendar's Construct. A second
import of the same project finds the same elements. ``world.json``: ``id`` UUIDv5 of
``legendkeeper:<project id>``, ``name`` the project's name, ``time_basic_unit`` ``day`` when at
least one Event got a date (the folder is a new world, so it has no unit of its own yet; without
a dated Event no unit is set), ``producer`` ``{"tool": "onlyworlds",
"version": ..., "input": ...}`` with ``legendkeeper-api`` (``PRODUCER_INPUT``) from the API and
``legendkeeper-export`` (``PRODUCER_INPUT_FILE``) from the file (both on the folder spec's list,
§4.2, v0.3.17), ``format_version`` this package's.

The report (``ImportReport``, printed at the end of a run and by ``--plan``) names what became what
with counts and how each type was decided, every key not placed (element, key, why, the extension
it was kept as), every titled link kept as Relations (by title, with counts), every link or mention
whose target is not in the folder, what is hidden and how, every Map (its size, pins and image) and
every pin named or left with no element, every board (its size, what it made and what it
counted), the documents not imported, every answer
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
from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from itertools import pairwise
from pathlib import Path
from typing import Any, Protocol

from ._jsonfmt import encode
from ._schema import ELEMENT_TYPES, FIELD_KINDS, LINK_TARGETS
from ._version import __version__
from .errors import parse_retry_after
from .folder import FORMAT_VERSION, write_folder
from .http import Response, Transport, UrllibTransport
from .worldfile import RECORDS_MANIFEST

__all__ = [
    "API_BASE",
    "EXT_PREFIX",
    "KEY_ENV",
    "LEGENDKEEPER_NAMESPACE",
    "PRODUCER_INPUT",
    "PRODUCER_INPUT_FILE",
    "ApiSource",
    "BoardMade",
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
#: from (the producer line and the x_legendkeeper_ keys say that; ruled 2026-10-23).
UNTYPED_SUPERTYPE = "Article"
#: a timeline's Narrative and its lanes' supertype
TIMELINE = "Timeline"

#: The push convention (OnlyWorlds into LegendKeeper, the trial of 2026-10-25): a key-value row keyed
#: ``onlyworlds-id`` holds the element's own id, ``onlyworlds-unmapped`` what had no slot, and tags
#: ``ow-supertype:<value>`` and ``ow-subtype:<value>`` the two fields. Read back, the id is the element's id.
OW_ID_KEY = "onlyworlds-id"
OW_UNMAPPED_KEY = "onlyworlds-unmapped"
OW_TAG_PREFIXES = {"ow-supertype:": "supertype", "ow-subtype:": "subtype"}
_UUID_TEXT = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
#: a key that is an extension key in the standard's own namespaces comes back under its own name
_EXT_KEY = re.compile(r"(?:x|atlas|shadow)_[a-z0-9_]+")

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
    "board_record",
    "board_map",
    "board_pos",
    "board_extent",
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

#: The tldraw records a board carries, by ``typeName``: what rides on a board document as ``board``.
_BOARD_RECORDS = (("shapes", "shape"), ("bindings", "binding"), ("assets", "asset"), ("pages", "page"))

#: An arrow's two terminals, start then end: the Relation's source and target.
TERMINALS = ("start", "end")

#: The records producer this door writes (folder spec §4.5): its directory under ``records/``, and
#: its entry in ``records/RECORDS.json``.
RECORDS_PRODUCER = "legendkeeper"
RECORDS_ENTRY = {
    "producer": RECORDS_PRODUCER,
    "format": "tldraw board records as LegendKeeper serves them",
    "version": "1",
    "deltas": False,
}
_SAFE_NAME = re.compile(r"[A-Za-z0-9_-]+")

#: The supertype of a Relation made from a board's arrow, and its name when the arrow has no label.
BOARD_LINK = "Board link"

#: tldraw's sticky note is 200 by 200 (its ``growY`` added to the height), times its ``scale``: its
#: props carry no ``w`` or ``h``.
_NOTE_SIDE = 200.0
_PLAIN_MARKS = ("underline", "sub", "sup", "color", "highlight")


def _norm(name: str) -> str:
    """A key or title lowercased, whitespace runs as underscores: the name a field is compared to."""
    return re.sub(r"\s+", "_", name.strip().lower())


def _json_or_text(text: str) -> Any:
    """An extension value as a push writes it: a JSON array or object when the text is one (a list
    or an object cannot ride a key-value row otherwise), else the text itself."""
    if text[:1] in "[{":
        try:
            return json.loads(text)
        except ValueError:
            pass
    return text


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


def _board_records(content: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """A board document's tldraw records as ``{shapes, bindings, assets, pages}``: the export's
    ``shapesV2`` (``{key, val}`` pairs) split by each ``val``'s ``typeName``, else its older
    ``shapes`` and ``bindings`` lists."""
    v2 = content.get("shapesV2")
    if isinstance(v2, list):
        recs = [_obj(_obj(pair).get("val")) for pair in v2]
        return {key: [r for r in recs if r.get("typeName") == kind] for key, kind in _BOARD_RECORDS}
    out: dict[str, list[dict[str, Any]]] = {key: [] for key, _ in _BOARD_RECORDS}
    for key in ("shapes", "bindings"):
        out[key] = [r for r in content.get(key) or [] if isinstance(r, dict)]
    return out


#: A shape's frame in page space: its origin's x and y, and its rotation in radians.
_Frame = tuple[float, float, float]


def _page_frames(shapes: Mapping[str, dict[str, Any]]) -> dict[str, _Frame]:
    """shape id -> its frame in the board's page space. tldraw keeps a shape's ``x``, ``y`` and
    ``rotation`` in its parent's space (a frame or a group; a ``page:...`` parent is the page), so
    a child's origin is its parent's origin plus the parent's page rotation applied to ``(x, y)``,
    and its rotation the parent's plus its own. A parent that is not a shape of the board, or a
    loop, counts as the page."""
    out: dict[str, _Frame] = {}

    def frame(sid: str, seen: frozenset[str]) -> _Frame:
        if sid in out:
            return out[sid]
        s = shapes[sid]
        x, y, rot = (_number(s.get(k)) or 0.0 for k in ("x", "y", "rotation"))
        parent = s.get("parentId")
        seen = seen | {sid}
        if isinstance(parent, str) and parent in shapes and parent not in seen:
            px, py, prot = frame(parent, seen)
            x, y = px + math.cos(prot) * x - math.sin(prot) * y, py + math.sin(prot) * x + math.cos(prot) * y
            rot += prot
        out[sid] = (x, y, rot)
        return out[sid]

    for sid in shapes:
        frame(sid, frozenset())
    return out


def _at(f: _Frame, u: float, v: float) -> tuple[float, float]:
    """The page-space point of a shape's local point ``(u, v)``: its origin plus its rotation applied."""
    x, y, rot = f
    return x + math.cos(rot) * u - math.sin(rot) * v, y + math.sin(rot) * u + math.cos(rot) * v


def _shape_size(s: dict[str, Any]) -> tuple[float, float] | None:
    """A shape's width and height in its own space: ``props.w`` and ``props.h``, a sticky note's
    from tldraw's fixed note size; None for a shape with no size (a text, a drawing, an arrow, a group)."""
    props = _obj(s.get("props"))
    if s.get("type") == "note":
        scale = _number(props.get("scale")) or 1.0
        return _NOTE_SIDE * scale, (_NOTE_SIDE + (_number(props.get("growY")) or 0.0)) * scale
    w, h = _number(props.get("w")), _number(props.get("h"))
    return (w, h) if w is not None and h is not None else None


def _shape_text(props: dict[str, Any]) -> str:
    """A note's, text's, geo's or arrow's text: ``props.text``, or the plain text of a newer tldraw's
    ``richText`` document (its paragraphs a line each)."""
    text = props.get("text")
    if isinstance(text, str):
        return text
    rich = props.get("richText")

    def plain(n: Any) -> str:
        if not isinstance(n, dict):
            return ""
        if n.get("type") == "text":
            return str(n.get("text") or "")
        if n.get("type") == "hardBreak":
            return "\n"
        return "".join(plain(c) for c in n.get("content") or [])

    return "\n".join(plain(c) for c in _obj(rich).get("content") or [])


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
                elif d.get("type") == "board":  # its tldraw records ride on the document, split by kind
                    head["board"] = _board_records(_obj(d.get("content")))
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
        # assumed in the API's shape: no real export holding a calendar has been read
        calendars = self.export.get("calendars")
        rows_c = [c for c in calendars if isinstance(c, dict)] if isinstance(calendars, list) else []
        out["calendars"] = {"data": rows_c, "hasMore": False, "nextCursor": None}
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
            self.notes.append(
                f"{len(calendars)} calendar{'' if len(calendars) == 1 else 's'} in the export, read as the API serves"
                " calendars (the export's calendar shape is assumed the API's: unproven on a real file)"
            )
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
# Calendars: a LegendKeeper calendar as the calendar profile's atlas_calendar
# ---------------------------------------------------------------------------

#: The calendar profile's key (schema-dist ``profiles/calendar.md``) and the supertype of the
#: Construct that carries it, by the profile's convention.
CALENDAR_FIELD = "atlas_calendar"
CALENDAR_SUPERTYPE = "calendar"

#: LegendKeeper's day-format tokens (each a run of one letter) and the profile's template tokens.
_LK_FORMAT_TOKENS = {
    "MMMM": "{month}",
    "D": "{day}",
    "DD": "{day}",
    "DDDD": "{weekday}",
    "YYYY": "{year}",
    "E": "{era}",
    "EE": "{era}",
}


def _lk_template(template: str) -> str | None:
    """LegendKeeper's ``day`` template in the profile's tokens: ``^`` (the ordinal suffix) dropped,
    ``[literal]`` kept. None when it holds a token the profile has no twin for (``MMM``, ``DDD``, ``H``)."""
    out: list[str] = []
    i = 0
    while i < len(template):
        ch = template[i]
        if ch == "[":
            j = template.find("]", i)
            if j < 0:
                return None
            out.append(template[i + 1 : j])
            i = j + 1
        elif ch == "^":
            i += 1
        elif ch.isalpha():
            j = i
            while j < len(template) and template[j] == ch:
                j += 1
            token = _LK_FORMAT_TOKENS.get(template[i:j])
            if token is None:
                return None
            out.append(token)
            i = j
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def _minutes_in_day(cal: Mapping[str, Any]) -> int:
    return int(cal.get("hoursInDay") or 24) * int(cal.get("minutesInHour") or 60)


def _day_of(minutes: Any, day: int) -> int | None:
    """The day a LegendKeeper minute falls in: a real floor of ``minutes / day``, so minute -1 is day -1."""
    if isinstance(minutes, bool):
        return None
    if isinstance(minutes, int):
        return minutes // day
    if isinstance(minutes, float) and math.isfinite(minutes):
        return math.floor(minutes / day)
    return None


def _leap_rule(interval: Any, offset: int, zero: bool) -> tuple[dict[str, Any] | None, str]:
    """A leap day's ``interval`` (``4``, ``400,!100,4``) as the profile's ``every_years``, ``except``
    and ``offset``; None and why when the profile cannot say it."""
    terms = [t.strip() for t in str(interval or "").split(",") if t.strip()]
    if any("+" in t for t in terms) or offset:
        return None, "carries an offset of its own (unwitnessed)"
    chain: list[tuple[int, bool]] = []
    for t in terms:
        digits = t[1:] if t.startswith("!") else t
        if not digits.isdigit() or int(digits) < 1:
            return None, "is not a list of whole numbers of years"
        chain.append((int(digits), not t.startswith("!")))
    chain.sort()
    ns = [n for n, _ in chain]
    if not chain or any(on != (i % 2 == 0) for i, (_, on) in enumerate(chain)):
        return None, "does not alternate on, off, on from its smallest term"
    if any(b <= a or b % a for a, b in pairwise(ns)):
        return None, "has a term that is not a larger multiple of the one before"
    rule: dict[str, Any] = {"every_years": ns[0]}
    if ns[1:]:
        rule["except"] = ns[1:]
    if not zero and ns != [1]:  # LegendKeeper reads the rule on the year as shown, index + 1 with no year 0
        rule["offset"] = 1
    return rule, ""


def _calendar_config(cal: Mapping[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    """A LegendKeeper calendar as an ``atlas_calendar`` value (grain ``day``, one step a day; the
    profile's version 2 when a leap rule needs ``except`` or ``offset``, else version 1), or None
    and the reasons it cannot be exact (none when exact).

    Witnessed on LegendKeeper's six preset calendars (2026-10-25): its own breakdown of 559 chosen
    minutes, read back from events made on each, against the TypeScript SDK's ``breakdownStep``
    (4.76.0) on the config made here; Gregorian, Harptos, Eberron, Exandria and Greyhawk agree on
    every one. The rules, each kept for a reason the witness gave:

    - a month is a month; one marked ``isIntercalary`` and one day long is an ``intercalary`` day
      after the months before it; a longer one (Greyhawk's festivals) a month; a month that does
      not come every year (``interval`` other than 1) is not exact.
    - a leap day is an ``intercalary`` day after the month it lengthens (after that month's own day,
      when that month is itself one day long). Its rule's terms, smallest first, must alternate on,
      off, on (``4``, ``!100``, ``400``), each a larger multiple of the one before: the first is
      ``every_years``, the rest ``except``. LegendKeeper reads the rule on the year as shown (the
      year index plus one with no year 0; 286 of 286 probed days of Gregorian, Harptos and Scrolls
      agree, before the epoch too), so with no year 0 the entry carries ``offset`` 1. A term with its own
      ``+`` offset, or a leap day's own nonzero ``offset``, is not exact (unwitnessed).
    - a week that restarts each month is ``nested``; else ``free``, the names turned so the first
      is the weekday at minute 0 (``epochWeekday``).
    - the first era starts at 0; every era starts on a day; an era that restarts months and days
      (``resetMode`` ``calendar``) is not exact, nor a later era that restarts its years
      (unwitnessed), nor a later era counting on from the epoch with no year 0. The first era's
      ``year_base`` is 0 with a year 0, else 1. A negative era is a ``down`` era, pivot 0, ``end``
      its start in days, ``year_base`` 1, listed first: an era without an end runs to the next
      era's start, so a down era listed after the up era at 0 would end that era where it begins.
    - the ``day`` format's tokens become the profile's; one with no twin leaves the profile's
      default. Moons and the clock have no place in the profile: they stay in the raw calendar.
    """
    try:
        cfg, why = _read_calendar(cal)
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        return None, [f"not read as a calendar ({type(exc).__name__}: {exc})"]
    return (None if why else cfg), why


def _read_calendar(cal: Mapping[str, Any]) -> tuple[dict[str, Any], list[str]]:
    why: list[str] = []
    day = _minutes_in_day(cal)
    if day < 1:
        why.append(f"a day of {day} minutes")
        day = 1
    zero = bool(cal.get("hasZeroYear"))
    months: list[Mapping[str, Any]] = list(cal.get("months") or [])
    # month index -> the leap days that lengthen it
    leaps: dict[int, list[dict[str, Any]]] = {}
    for ld in cal.get("leapDays") or []:
        label = str(ld.get("name") or "Leap day")
        rule, said = _leap_rule(ld.get("interval"), int(ld.get("offset") or 0), zero)
        if rule is None:
            why.append(f"leap day {label!r}: its rule {ld.get('interval')!r} {said}")
            continue
        mi = int(ld.get("month") or 0)
        if not 0 <= mi < len(months):
            why.append(f"leap day {label!r} lengthens month {mi}, which the calendar does not have")
            continue
        if int(ld.get("day") or 0) != 0 or ld.get("intercalary"):
            why.append(f"leap day {label!r}: a day inside the month or its own intercalary mark (unwitnessed)")
        leaps.setdefault(mi, []).append({"name": label, **rule})
    names: list[str] = []
    lengths: list[int] = []
    inter: list[dict[str, Any]] = []
    for i, m in enumerate(months):
        name = str(m.get("name") or f"Month {i + 1}")
        length = int(m["length"])
        if int(m.get("interval") or 1) != 1:
            why.append(f"month {name!r} comes every {m.get('interval')} years")
        elif m.get("isIntercalary") and length == 1:
            inter.append({"name": name, "after_month": len(names)})
        else:
            if length < 1:
                why.append(f"month {name!r} is {length} days long")
            names.append(name)
            lengths.append(length)
        # LegendKeeper lengthens the month itself: its leap day follows the month's own days
        inter += [{"name": lp["name"], "after_month": len(names), **lp} for lp in leaps.get(i, [])]
    if not names:
        why.append("no month that comes every year")
    cfg: dict[str, Any] = {
        # version 2 says except and offset; a reader of version 1 alone refuses it whole, never misreads it
        "version": 2 if any("except" in e or "offset" in e for e in inter) else 1,
        "grain": "day",
        "step_name": "day",
        "bundles": {"months": {"names": names, "lengths": lengths}},
    }
    wd = [str(_obj(w).get("name") or "") for w in cal.get("weekdays") or []]
    if wd:
        if cal.get("weekResetsEachMonth"):
            cfg["bundles"]["week"] = {"length": len(wd), "names": wd, "mode": "nested"}
        else:
            k = int(cal.get("epochWeekday") or 0) % len(wd)
            cfg["bundles"]["week"] = {"length": len(wd), "names": wd[k:] + wd[:k], "mode": "free"}
    if inter:
        cfg["intercalary"] = inter
    eras: list[dict[str, Any]] = []
    for i, e in enumerate(cal.get("positiveEras") or []):
        ename = str(e["name"])
        start = int(e["startsAt"])
        if i == 0 and start != 0:
            why.append(f"the first era {ename!r} starts at minute {start}, not 0")
        if start % day:
            why.append(f"era {ename!r} starts inside a day")
        mode = e.get("resetMode") or "none"
        if mode == "calendar":
            why.append(f"era {ename!r} restarts months and days")
        elif mode not in ("none", "year"):
            why.append(f"era {ename!r}: reset mode {mode!r} not known here")
        elif i > 0 and mode == "year":
            why.append(f"era {ename!r} restarts its years at minute {start} (unwitnessed)")
        elif i > 0 and not zero:
            why.append(f"era {ename!r} counts its years on from the epoch, which has no year 0")
        era: dict[str, Any] = {"name": ename, "abbrev": "" if e.get("hideAbbr") else str(e.get("abbr") or "AD")}
        era["start"] = start // day
        if i == 0 or mode == "year":
            era["year_base"] = 0 if zero else 1
        else:
            era["restart"] = False
        eras.append(era)
    ne = cal.get("negativeEra")
    if ne:
        ename = str(ne["name"])
        start = int(ne["startsAt"])
        if start >= 0:
            why.append(f"the negative era {ename!r} starts at minute {start}, not before 0")
        if start % day:
            why.append(f"era {ename!r} starts inside a day")
        # first in the list: an era without an end runs to the next era's start, so this down era
        # listed after the up era at 0 would end that era where it begins
        down = {"name": ename, "abbrev": "" if ne.get("hideAbbr") else str(ne.get("abbr") or "AD"), "start": 0}
        eras.insert(0, {**down, "end": start // day, "direction": "down", "year_base": 1})
    if eras:
        cfg["eras"] = eras
    fmt = _obj(cal.get("format")).get("day")
    if isinstance(fmt, str) and fmt:
        template = _lk_template(fmt)
        if template:
            cfg["format"] = template
    return cfg, why


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
    #: the project's calendars (``GET /projects/<id>/calendars``; the export file's ``calendars``)
    calendars: list[dict[str, Any]] = field(default_factory=list)
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


def _api_map(doc: dict[str, Any], image: Any, features: list[dict[str, Any]]) -> list[str]:
    """Put the API's map document on ``doc`` in the export file's shape, so one converter reads both.

    The API's ``mapImage`` is ``{assetId, url, width, height, bounds, tiles: {urlTemplate,
    maxNativeZoom}}`` with ``bounds`` ``[[y0, x0], [y1, x1]]`` in zoom-0 units; the file's ``map`` is
    ``{mapId, min_x, max_x, min_y, max_y, max_zoom}`` in image pixels, so each bound is scaled by
    ``2^maxNativeZoom``. A pin is a feature of type ``pin``, its ``pos`` the file's (measured on
    LegendKeeper's tutorial map, the same 16 pin ids and positions on both roads, 2026-10-25).
    Returns the notes for what is not read: features of another type."""
    pins = [f for f in features if f.get("type") == "pin"]
    other = Counter(str(f.get("type")) for f in features if f.get("type") != "pin")
    doc["pins"] = [{k: v for k, v in f.items() if k != "type"} for f in pins]
    m: dict[str, Any] = {}
    if isinstance(image, dict):
        tiles = _obj(image.get("tiles"))
        zoom = tiles.get("maxNativeZoom")
        for key in ("url", "assetId"):
            if isinstance(image.get(key), str) and image[key]:
                m["mapId"] = image[key]
                break
        b = image.get("bounds")
        pairs = [c for c in b if isinstance(c, list) and len(c) == 2] if isinstance(b, list) else []
        corners = [[_number(v) for v in c] for c in pairs]
        z = _number(zoom)
        if z is not None and len(corners) == 2 and all(v is not None for c in corners for v in c):
            s = 2.0**z

            def px(v: float | None) -> int | float:
                n = float(v or 0) * s
                return int(n) if n.is_integer() else n

            m.update(min_y=px(corners[0][0]), min_x=px(corners[0][1]), max_y=px(corners[1][0]), max_x=px(corners[1][1]))
            m["max_zoom"] = zoom
        said = ("url", "assetId", "bounds", "tiles", "width", "height")
        rest = {k: v for k, v in image.items() if k not in said and v is not None}
        if tiles.get("urlTemplate"):
            rest["tiles"] = tiles.get("urlTemplate")
        m.update(rest)
    doc["map"] = m or None
    return [
        f"{n} map feature{'' if n == 1 else 's'} of type {kind!r} on {doc.get('name')!r}: not read (only pins are)"
        for kind, n in sorted(other.items())
    ]


def read_project(source: Source, project_id: str) -> Snapshot:
    """Walk a project: the project, its whole tree, its calendars, then each resource, its page
    blocks, its timelines, maps and boards, hidden ones too (the converter marks them hidden;
    nothing is left out).

    The project and the tree must answer (a ``SourceError`` otherwise); the calendars, a
    resource, a page or a timeline that does not is listed in ``unread`` and the walk goes on.
    The calendars are one list, read once (the route takes no page size, by LegendKeeper's
    OpenAPI document).
    """
    root = f"/projects/{_seg(project_id)}"
    project = source.get(root)
    if not isinstance(project, dict):
        raise SourceError(root, None, None, "the answer is not a project")
    resources = [r for r in _paged(source, f"{root}/resources", sized=True) if isinstance(r.get("id"), str)]
    snap = Snapshot(project_id, project, resources)
    snap.producer_input = str(getattr(source, "producer_input", PRODUCER_INPUT))
    try:
        snap.calendars = _paged(source, f"{root}/calendars", sized=False)
    except SourceError as exc:
        snap.unread.append(f"the project's calendars: {exc}; its events keep their minutes, with no dates")
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
                elif dtype == "map" and "pins" not in doc:  # the export file's maps carry their pins already
                    head = source.get(dpath)
                    features = _paged(source, f"{dpath}/features", sized=False)
                    snap.notes += _api_map(doc, _obj(head).get("mapImage"), features)
                elif dtype == "board" and "board" not in doc:  # the export file's boards carry their records already
                    answer = source.get(f"{dpath}/board")
                    if isinstance(answer, dict):  # {shapes, bindings, assets, pages, schema, version}
                        doc["board"] = {
                            key: [r for r in answer.get(key) or [] if isinstance(r, dict)] for key, _ in _BOARD_RECORDS
                        }
                    else:
                        snap.unread.append(f"{where}: the board answer is not a board")
            except SourceError as exc:
                snap.unread.append(f"{where}: {exc}")
    snap.notes = list(getattr(source, "notes", None) or []) + snap.notes
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
    #: board documents hidden, or of a hidden resource: hidden Maps, everything made from them hidden
    boards: int = 0
    #: cards on a visible board that show a hidden page: hidden Pins
    board_pins: int = 0
    #: timelines hidden, or of a hidden resource: hidden Timeline Narratives (their lanes with them)
    timelines: int = 0


@dataclass(frozen=True)
class MapMade:
    """A map document made a Map (from the export file or the API)."""

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


@dataclass
class BoardMade:
    """A board document made a Map with supertype Board, and what its shapes made."""

    #: the Map's name, ``<resource>: <document>``
    name: str
    resource: str
    #: the size of the box over what the board places; None for a board with nothing on it
    width: int | None
    height: int | None
    #: made: ``card pins``, ``note pins``, ``child maps``, ``zones``, ``markers``, ``relations``, ``narratives``
    made: dict[str, int] = field(default_factory=dict)
    #: shapes that made nothing, by type (``note`` and ``text`` when empty)
    counted: dict[str, int] = field(default_factory=dict)
    #: arrows whose two ends are not both bound to page cards (whose resources are elements) or frames
    loose_arrows: int = 0
    #: arrows whose two ends are one element (a frame to itself, two cards of one page)
    self_arrows: int = 0
    #: the folder path of the file holding the board's records whole
    record: str = ""
    #: the geo shapes' texts and the bookmarks' URLs, in shape id order
    geo_texts: list[str] = field(default_factory=list)
    urls: list[str] = field(default_factory=list)
    #: tldraw pages on the board (all placed on the one Map)
    pages: int = 1
    hidden: bool = False


def _some(words: list[str], n: int = 4, width: int = 40) -> str:
    """Up to ``n`` of ``words`` quoted (each cut to ``width`` characters), and how many more."""
    cut = [" ".join(w.split()) for w in words[:n]]
    said = ", ".join(repr(w if len(w) <= width else w[: width - 3] + "...") for w in cut)
    return said + (f", {len(words) - n} more" if len(words) > n else "")


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
    #: every board document made a Map
    boards: list[BoardMade] = field(default_factory=list)
    #: the boards' records are marked private in records/RECORDS.json (a board hidden, or showing a hidden page)
    records_private: bool = False
    unread: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    #: tags on the resources kept untyped -> how many carry each: what ``--map`` could type
    untyped_tags: dict[str, int] = field(default_factory=dict)
    #: what an OnlyWorlds push said it could not place (its ``onlyworlds-unmapped`` rows), one line each
    ow_unmapped: list[str] = field(default_factory=list)
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
        if self.ow_unmapped:
            lines.append(f"What the OnlyWorlds push could not place, as it says ({len(self.ow_unmapped)}):")
            lines += [f"  - {u}" for u in self.ow_unmapped]
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
            (
                h.timelines,
                "hidden timeline, its Narrative and its lanes'",
                "hidden timelines, each its Narrative and its lanes'",
            ),
            (h.relations, "Relation with a hidden end", "Relations with a hidden end"),
            (h.maps, "hidden Map (its document or resource hidden)", "hidden Maps (their document or resource hidden)"),
            (h.pins, "hidden Pin (the pin or its Map hidden)", "hidden Pins (the pin or its Map hidden)"),
            (
                h.boards,
                "hidden board (its document or resource hidden), its Map and everything on it",
                "hidden boards (their document or resource hidden), each its Map and everything on it",
            ),
            (
                h.board_pins,
                "card on a visible board showing a hidden page, a hidden Pin",
                "cards on a visible board showing a hidden page, each a hidden Pin",
            ),
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
        if self.boards:
            lines.append(
                f"Board documents, each a Map (supertype Board) and what its shapes made ({len(self.boards)}):"
            )
            for b in self.boards:
                got = b.made
                size = f"{b.width} x {b.height}" if b.width is not None and b.height is not None else "nothing placed"
                pages = f", its {b.pages} pages on the one Map" if b.pages > 1 else ""
                lines.append(
                    f"  - {b.name!r}{' (hidden)' if b.hidden else ''}: {size}{pages}; Pins {got['card pins']} for page"
                    f" cards (child Maps {got['child maps']}) and {got['note pins']} for notes and texts, Zones"
                    f" {got['zones']} for frames with Markers {got['markers']}, Relations {got['relations']} for arrows"
                    f" between two cards or frames, Narratives {got['narratives']} for notes and texts"
                )
                said = [f"arrows not between two cards or frames {b.loose_arrows}"] if b.loose_arrows else []
                if b.self_arrows:
                    said.append(f"arrows from a thing to itself {b.self_arrows}")
                for kind, n in sorted(b.counted.items()):
                    if kind == "geo" and b.geo_texts:
                        said.append(f"geo {n} ({len(b.geo_texts)} with text: {_some(b.geo_texts)})")
                    elif kind == "bookmark" and b.urls:
                        said.append(f"bookmark {n} ({_some(b.urls, 2, 60)})")
                    else:
                        said.append(f"{kind} {n}")
                if said:
                    lines.append("    not made, counted: " + "; ".join(said))
        if self.boards:
            where = f"records/{RECORDS_PRODUCER}/boards/"
            done = "written" if self.out is not None else "to be written (a plan writes none)"
            lines.append(
                f"Board records, each board's tldraw records whole, {done} under {where}, one file a board"
                f" ({len(self.boards)}), each named on its Map as x_legendkeeper_board_record, the producer"
                f" {RECORDS_PRODUCER!r} entered in {RECORDS_MANIFEST}."
            )
            if self.records_private:
                lines.append(
                    f'  Marked "private": true in {RECORDS_MANIFEST}: a board is hidden or shows a hidden page, and'
                    f" the mark covers the whole records/{RECORDS_PRODUCER}/ (an export or a share leaves it out"
                    " unless asked)."
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


@dataclass
class _Card:
    """A page card that shows a map or board document: its Pin is made once every document is."""

    #: the Pin's slot in the pins list (filled in place, so the order holds)
    slot: dict[str, Any]
    pin_id: str
    #: the card's resource, and the document of it the card shows
    target: _Item
    doc: dict[str, Any]
    #: the Pin's map and place, and its extension keys
    fields: dict[str, Any]
    ext: dict[str, Any]
    board: BoardMade
    board_map: dict[str, Any]
    board_hidden: bool


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
        #: a timeline's Narrative and its lanes' (convention 3)
        self.timelines: list[dict[str, Any]] = []
        self.pins: list[dict[str, Any]] = []
        #: what boards make beside their Maps and Pins
        self.zones: list[dict[str, Any]] = []
        self.markers: list[dict[str, Any]] = []
        self.notes_made: list[dict[str, Any]] = []
        #: (resource id, document id) -> the Map made from that map or board document
        self._made: dict[tuple[str, str], dict[str, Any]] = {}
        #: cards that show a map or board document, placed once every document is made
        self._cards: list[_Card] = []
        #: records/ path -> a board's records, written whole beside the folder's elements
        self.board_records: dict[str, dict[str, Any]] = {}
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
        #: elements whose id is the ``onlyworlds-id`` they carry
        self.own_ids = 0
        #: the project's calendars by id; the Constructs made for those a timeline names
        self.calendars = {c["id"]: c for c in snap.calendars if isinstance(c.get("id"), str) and c["id"]}
        self.constructs: list[dict[str, Any]] = []
        #: calendar id -> (its name, minutes in its day when exact else None, why not exact)
        self._cal: dict[str, tuple[str, int | None, list[str]]] = {}
        self._cal_bodies: dict[str, dict[str, Any]] = {}
        #: calendar id -> the Events dated from it
        self._cal_dated: Counter[str] = Counter()

    def _id(self, *parts: str) -> str:
        return _uuid(":".join(("legendkeeper", self.snap.project_id, *parts)))

    # -- pass 1: every element, with its type and id --------------------------

    def _own_id(self, rid: str) -> str | None:
        """The element id a resource carries in an ``onlyworlds-id`` key-value row, when it is a uuid."""
        for prop in _obj(self.snap.full.get(rid)).get("properties") or []:
            if not isinstance(prop, dict) or prop.get("kind") != "keyValue":
                continue
            for row in prop.get("rows") or []:
                if isinstance(row, dict) and str(row.get("key") or "").strip() == OW_ID_KEY:
                    text = _plain(row.get("content")) or str(row.get("text") or "").strip()
                    return text.lower() if _UUID_TEXT.fullmatch(text.lower()) else None
        return None

    def collect(self) -> None:
        untyped_tags: dict[str, int] = {}
        claimed: dict[str, str] = {}
        for row in self.snap.resources:
            rid = row["id"]
            st = self.state[rid]
            if st == "hidden":
                self.report.hidden.resources += 1
            elif st == "under":
                self.report.hidden.under_hidden += 1
            tags = [t for t in row.get("tags") or [] if isinstance(t, str)]
            ow_tags = {
                fname: t[len(pre) :].strip()
                for t in tags
                for pre, fname in OW_TAG_PREFIXES.items()
                if t.lower().startswith(pre) and t[len(pre) :].strip()
            }
            tags = [t for t in tags if not any(t.lower().startswith(pre) for pre in OW_TAG_PREFIXES)]
            etype, by = self._type_of(tags)
            name = str(row.get("name") or "").strip() or f"Untitled ({rid})"
            own = self._own_id(rid)
            if own is not None and own in claimed:
                self.report.notes.append(
                    f"{name!r}: its {OW_ID_KEY} {own} is another resource's ({claimed[own]!r}): its id is derived"
                )
                own = None
            if own is not None:
                claimed[own] = name
            item = _Item(
                etype,
                own or self._id(rid),
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
            item.fields.update(ow_tags)
            if own is not None:
                self.own_ids += 1
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
        for card in self._cards:
            self._card_on_map(card)

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
            elif dtype == "board" and isinstance(doc.get("board"), dict):
                self._board(item, doc)
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
        if key == OW_ID_KEY:
            if item.eid != text.lower():  # not the element's id: kept, never dropped
                self._keep(item, key, text, f"not used as the id ({item.name!r} has its own)")
            return
        if key == OW_UNMAPPED_KEY:
            self.report.ow_unmapped.append(f"{item.name!r}: {text}")
            return
        if _EXT_KEY.fullmatch(key) and not key.startswith(EXT_PREFIX) and key not in item.ext:
            item.ext[key] = _json_or_text(text)
            return
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

    def _relation_ends(self, item: _Item, target: _Item, title: str) -> dict[str, Any]:
        """A Relation's links to its two ends: a Character source on ``actor``, else each end on
        Relation's field for its type; an end of a type Relation has no field for is noted."""
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
        return fields

    def _relation(self, item: _Item, title: str, list_id: str, x: dict[str, Any], target: _Item) -> None:
        fields = self._relation_ends(item, target, title)
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
        day = self._calendar(item, doc, calendar) if isinstance(calendar, str) and calendar else None
        made = dated = 0
        mine: list[str] = []  # the events read on this timeline, in order
        per_lane: dict[str, list[str]] = {}
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
                when = _day_of(minutes, day) if day is not None else None
                if when is not None:
                    fields[f"{key}_date"] = when
            if "start_date" in fields or "end_date" in fields:
                dated += 1
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
            mine.append(body["id"])
            if lane is not None:
                per_lane.setdefault(str(lane.get("id")), []).append(body["id"])
        self._timeline_narratives(item, doc, lanes, mine, per_lane)
        if isinstance(calendar, str) and dated:
            self._cal_dated[calendar] += dated
            dates = f"start_date and end_date in days from the calendar {self._cal[calendar][0]!r} ({dated} dated)"
        elif isinstance(calendar, str) and calendar in self._cal:
            dates = f"start_date and end_date unset: the calendar {self._cal[calendar][0]!r} is kept raw"
        else:
            dates = "start_date and end_date unset: no calendar read"
        self.report.notes.append(
            f"timeline {doc.get('name')!r} on {item.name!r}: a Narrative (supertype {TIMELINE}) holding {made}"
            f" event{'' if made == 1 else 's'} and a child Narrative for each of its {len(lanes)}"
            f" lane{'' if len(lanes) == 1 else 's'} (start and end kept as minutes, with the formatted date when the"
            f" source gives one; {dates})"
        )

    def _calendar(self, item: _Item, doc: dict[str, Any], cid: str) -> int | None:
        """The calendar a timeline names, made a Construct the first time (supertype ``calendar``,
        the raw calendar whole as ``x_legendkeeper_calendar``, ``atlas_calendar`` only when exact).
        Returns the minutes in its day when exact, so its Events get dates; else None. Hidden while
        only hidden timelines name it (a custom calendar's names can tell what the timeline hides)."""
        shown = not (item.hidden or bool(doc.get("isHidden")))
        if cid in self._cal:
            if shown:
                self._cal_bodies[cid].pop("hidden", None)
            return self._cal[cid][1]
        cal = self.calendars.get(cid)
        if cal is None:
            self.report.notes.append(
                f"timeline {doc.get('name')!r} on {item.name!r} names the calendar {cid!r}, which is not among the"
                " project's calendars: its events keep their minutes, with no dates"
            )
            return None
        config, why = _calendar_config(cal)
        name = str(cal.get("name") or "").strip() or f"Calendar ({cid})"
        fields: dict[str, Any] = {"supertype": CALENDAR_SUPERTYPE}
        if isinstance(cal.get("description"), str) and cal["description"].strip():
            fields["description"] = cal["description"].strip()
        ext: dict[str, Any] = {CALENDAR_FIELD: config} if config is not None else {}
        ext[f"{EXT_PREFIX}id"] = cid
        ext[f"{EXT_PREFIX}calendar"] = copy.deepcopy(cal)
        body = self._body("construct", self._id("calendar", cid), name, not shown, fields, ext)
        self.constructs.append(body)
        self._cal_bodies[cid] = body
        day = _minutes_in_day(cal) if config is not None else None
        self._cal[cid] = (name, day, why)
        return day

    def _timeline_narratives(
        self,
        item: _Item,
        doc: dict[str, Any],
        lanes: Mapping[str, dict[str, Any]],
        events: list[str],
        per_lane: Mapping[str, list[str]],
    ) -> None:
        """A timeline as a Narrative with supertype Timeline whose ``events`` are its Events, linked to
        its resource as a hidden page's Narrative is; each lane a child Narrative (subtype lane) holding
        that lane's Events. Hidden with the resource or the timeline; a lane hides on its own mark."""
        did = str(doc.get("id"))
        dname = str(doc.get("name") or "").strip() or "Timeline"
        hidden = item.hidden or bool(doc.get("isHidden"))
        tl_id = self._id("timeline", item.lk_id, did)
        fields: dict[str, Any] = {"supertype": TIMELINE, "events": events} if events else {"supertype": TIMELINE}
        if item.etype == "narrative":
            fields["parent_narrative"] = item.eid
        elif item.etype in _NARRATIVE_FIELD_FOR:
            fields[_NARRATIVE_FIELD_FOR[item.etype]] = [item.eid]
        ext: dict[str, Any] = {f"{EXT_PREFIX}document": did, f"{EXT_PREFIX}parent": item.eid}
        if doc.get("calendarId"):
            ext[f"{EXT_PREFIX}calendar"] = doc.get("calendarId")
        self.timelines.append(self._body("narrative", tl_id, f"{item.name}: {dname}", hidden, fields, ext))
        if hidden:
            self.report.hidden.timelines += 1
        for lid, lane in lanes.items():
            lane_hidden = hidden or bool(lane.get("isHidden"))
            lf: dict[str, Any] = {"supertype": TIMELINE, "subtype": "lane", "parent_narrative": tl_id}
            if per_lane.get(lid):
                lf["events"] = per_lane[lid]
            lname = str(lane.get("name") or "").strip() or f"Lane ({lid})"
            lext = {f"{EXT_PREFIX}id": lid, f"{EXT_PREFIX}parent": item.eid}
            self.timelines.append(
                self._body("narrative", self._id("lane", item.lk_id, did, lid), lname, lane_hidden, lf, lext)
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
        self._made[(item.lk_id, did)] = body
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

    # -- boards ----------------------------------------------------------------

    @staticmethod
    def _body(
        etype: str, eid: str, name: str, hidden: bool, fields: dict[str, Any], ext: dict[str, Any]
    ) -> dict[str, Any]:
        """An element body: type, id, name, the hidden mark, its type's fields in schema order, then ``ext``."""
        body: dict[str, Any] = {"type": etype, "id": eid, "name": name}
        if hidden:
            body["hidden"] = True
        body.update({f: fields[f] for f in FIELD_KINDS[etype] if f in fields and f != "name"})
        body.update(ext)
        return body

    def _card_item(self, shape: Any) -> _Item | None:
        """The element a page card (an ``element`` shape) shows, when its resource is in the project."""
        if not isinstance(shape, dict) or shape.get("type") != "element":
            return None
        rid = _obj(shape.get("props")).get("resourceId")
        return self.items.get(rid) if isinstance(rid, str) else None

    def _board(self, item: _Item, doc: dict[str, Any]) -> None:
        """A board document (its tldraw records, from either road) as a Map with supertype Board,
        the records kept whole on it: each page card a Pin, each frame a Zone and four Markers, each
        arrow between two cards or frames a Relation, each note and text a Narrative and a Pin; the
        rest counted (the module docstring)."""
        did = str(doc.get("id"))
        dname = str(doc.get("name") or "").strip()
        name = f"{item.name}: {dname or 'Board'}"
        hidden = item.hidden or bool(doc.get("isHidden"))
        recs = _obj(doc.get("board"))
        shapes = {s["id"]: s for s in recs.get("shapes") or [] if isinstance(s, dict) and isinstance(s.get("id"), str)}
        frames = _page_frames(shapes)
        map_id = self._id("board", item.lk_id, did)
        made = BoardMade(name, item.name, None, None, hidden=hidden, pages=max(1, len(recs.get("pages") or [])))
        made.made = dict.fromkeys(
            ("card pins", "note pins", "child maps", "zones", "markers", "relations", "narratives"), 0
        )
        ends: dict[str, dict[str, str]] = {}  # arrow id -> {"start": shape id, "end": shape id}
        for b in recs.get("bindings") or []:
            term = _obj(b.get("props")).get("terminal") if isinstance(b, dict) else None
            if term in ("start", "end") and b.get("type") == "arrow" and isinstance(b.get("toId"), str):
                ends.setdefault(str(b.get("fromId")), {})[term] = b["toId"]
        # what each shape places, in page space; the Map spans those points and every sized shape's corners
        texts = {
            sid: _shape_text(_obj(s.get("props"))) for sid, s in shapes.items() if s.get("type") in ("note", "text")
        }
        corners: dict[str, list[tuple[float, float]]] = {}
        placed: dict[str, tuple[float, float]] = {}
        for sid, s in shapes.items():
            size = _shape_size(s)
            if size is not None:
                w, h = size
                corners[sid] = [_at(frames[sid], u, v) for u, v in ((0.0, 0.0), (w, 0.0), (w, h), (0.0, h))]
            if s.get("type") == "element" or (s.get("type") == "note" and texts[sid].strip()):
                # a card's or a note's place is its centre
                placed[sid] = _at(frames[sid], size[0] / 2, size[1] / 2) if size else _at(frames[sid], 0.0, 0.0)
            elif s.get("type") == "text" and texts[sid].strip():
                placed[sid] = _at(frames[sid], 0.0, 0.0)  # a text has a width but no height: its origin
        points = [p for c in corners.values() for p in c] + list(placed.values())
        box = (
            (min(p[0] for p in points), min(p[1] for p in points), max(p[0] for p in points), max(p[1] for p in points))
            if points
            else None
        )

        def where(pt: tuple[float, float]) -> dict[str, int]:
            # tldraw's y counts down the page; OnlyWorlds counts up from the bottom left of the Map
            return {"x": _whole(pt[0] - box[0]), "y": _whole(box[3] - pt[1])} if box is not None else {}

        fields: dict[str, Any] = {"supertype": "Board"}
        # the board's records exactly as read, so a push back can restore the canvas: a file of the
        # folder's records/, named by the document's id (by the Map's when that is not a plain name)
        stem = did if _SAFE_NAME.fullmatch(did) else map_id
        made.record = f"records/{RECORDS_PRODUCER}/boards/{stem}.json"
        self.board_records[made.record] = recs
        if hidden:
            self.report.records_private = True
        ext: dict[str, Any] = {f"{EXT_PREFIX}document": did, f"{EXT_PREFIX}board_record": made.record}
        if box is not None:
            made.width, made.height = _whole(box[2] - box[0]), _whole(box[3] - box[1])
            fields.update(width=made.width, height=made.height)
            ext[f"{EXT_PREFIX}board_extent"] = dict(zip(("min_x", "min_y", "max_x", "max_y"), box, strict=True))
        if item.etype == "location":
            fields["location"] = item.eid
        else:
            ext[f"{EXT_PREFIX}resource"] = item.eid
        board_map = self._body("map", map_id, name, hidden, fields, ext)
        if hidden:
            self.report.hidden.boards += 1
        self.maps.append(board_map)
        self._made[(item.lk_id, did)] = board_map
        n = made.made
        # a frame's Zone is an element an arrow can link: each frame's, before any arrow is read
        zones = {
            sid: _Item(
                "zone",
                self._id("board", item.lk_id, did, sid),
                str(_obj(s.get("props")).get("name") or "").strip() or "Frame",
                item.lk_id,
                typed=True,
                row={},
                hidden=hidden,
            )
            for sid, s in shapes.items()
            if s.get("type") == "frame"
        }
        for sid in sorted(shapes):  # shape id order: both roads list the same records, not always in one order
            s = shapes[sid]
            kind = str(s.get("type") or "unknown")
            props = _obj(s.get("props"))
            mine = {f"{EXT_PREFIX}id": sid, f"{EXT_PREFIX}board_map": map_id}
            pos = {f"{EXT_PREFIX}board_pos": list(placed[sid])} if sid in placed else {}
            if kind == "element":
                n["card pins"] += 1
                pin_id = self._id("board", item.lk_id, did, sid)
                at = {"map": map_id, **where(placed[sid])}
                card_ext = {**mine, **pos}
                target = self._card_item(s)
                docid = props.get("documentId")
                shown: dict[str, Any] | None = None  # the document of its resource the card shows, when it names one
                if target is not None and isinstance(docid, str) and docid:
                    docs = _obj(self.snap.full.get(target.lk_id)).get("documents") or []
                    shown = next((d for d in docs if isinstance(d, dict) and d.get("id") == docid), None)
                if target is not None and shown is not None and shown.get("type") in ("map", "board"):
                    slot: dict[str, Any] = {}  # made once every map and board is
                    self.pins.append(slot)
                    self._cards.append(_Card(slot, pin_id, target, shown, at, card_ext, made, board_map, hidden))
                elif target is None:
                    rid = props.get("resourceId")
                    why = f"its resource {rid}, {self._MISSING}" if isinstance(rid, str) and rid else "no resource"
                    self.report.pins_unlinked.append(f"card {sid} on {name!r}: {why}; a Pin with no element")
                    self.pins.append(self._body("pin", pin_id, f"Untitled card ({sid})", hidden, at, card_ext))
                else:
                    # a card shows its page: a hidden page (its resource or the document shown) is a hidden Pin
                    on_hidden = target.hidden or bool(shown is not None and shown.get("isHidden"))
                    if on_hidden and not hidden:
                        self.report.hidden.board_pins += 1
                        self.report.records_private = True  # its records name a hidden page
                    at.update(element_type=target.etype, element_id=target.eid)
                    self.pins.append(self._body("pin", pin_id, target.name, hidden or on_hidden, at, card_ext))
            elif kind == "frame":
                zname, zone_id = zones[sid].name, zones[sid].eid
                zone = {"subtype": "Frame", "shape": "polygon"}
                self.zones.append(self._body("zone", zone_id, zname, hidden, zone, mine))
                n["zones"] += 1
                for order, pt in enumerate(corners.get(sid, [])):  # top left, top right, bottom right, bottom left
                    at = {"map": map_id, "zone": zone_id, **where(pt), "order": order}
                    mid = self._id("board", item.lk_id, did, sid, str(order))
                    marker_ext = {**mine, f"{EXT_PREFIX}board_pos": list(pt)}
                    self.markers.append(
                        self._body("marker", mid, f"{zname}: corner {order + 1}", hidden, at, marker_ext)
                    )
                    n["markers"] += 1
            elif kind in ("note", "text"):
                text = texts[sid]
                if not text.strip():
                    made.counted[f"{kind} (empty)"] = made.counted.get(f"{kind} (empty)", 0) + 1
                    continue
                title = next(line.strip() for line in text.splitlines() if line.strip())[:80].rstrip()
                narr_id = self._id("board", item.lk_id, did, sid)
                narr = {"description": text, "supertype": "Note", "subtype": kind}
                self.notes_made.append(
                    self._body("narrative", narr_id, title, hidden, narr, {**mine, f"{EXT_PREFIX}parent": item.eid})
                )
                at = {"map": map_id, "element_type": "narrative", "element_id": narr_id, **where(placed[sid])}
                pin_id = self._id("board", item.lk_id, did, sid, "pin")
                self.pins.append(self._body("pin", pin_id, title, hidden, at, {**mine, **pos}))
                n["narratives"] += 1
                n["note pins"] += 1
            elif kind == "arrow":
                bound = ends.get(sid, {})
                src, dst = (
                    zones.get(bound.get(t, "")) or self._card_item(shapes.get(bound.get(t, ""))) for t in TERMINALS
                )
                if src is None or dst is None:  # a free end, or an end on neither a page card nor a frame
                    made.loose_arrows += 1
                    continue
                if src.eid == dst.eid:  # a frame to itself, or two cards of one page: no Relation
                    made.self_arrows += 1
                    continue
                title = " ".join(_shape_text(props).split()) or BOARD_LINK
                links = {**self._relation_ends(src, dst, title), "supertype": BOARD_LINK}
                rel_hidden = hidden or src.hidden or dst.hidden
                if rel_hidden and not hidden:
                    self.report.hidden.relations += 1
                rel_ext = {**mine, f"{EXT_PREFIX}source": src.eid, f"{EXT_PREFIX}target": dst.eid}
                rel_id = self._id("board", item.lk_id, did, sid)
                self.relations.append(self._body("relation", rel_id, title, rel_hidden, links, rel_ext))
                n["relations"] += 1
            else:
                made.counted[kind] = made.counted.get(kind, 0) + 1
                if kind == "geo" and _shape_text(props).strip():
                    made.geo_texts.append(_shape_text(props).strip())
                elif kind == "bookmark" and isinstance(props.get("url"), str) and props["url"]:
                    made.urls.append(props["url"])
        self.report.boards.append(made)

    def _card_on_map(self, card: _Card) -> None:
        """A card that shows a map or board document: a Pin placing that document's Map, and for a
        board, that Map's ``parent_map`` this board's Map (its first, and never a loop)."""
        child = self._made.get((card.target.lk_id, str(card.doc.get("id"))))
        fields = dict(card.fields)
        what = f"{card.doc.get('type')} {card.doc.get('name')!r} of {card.target.name!r}"
        if child is None:  # its content was not read (named under unread): the card places its page
            fields.update(element_type=card.target.etype, element_id=card.target.eid)
            name, on_hidden = card.target.name, card.target.hidden or bool(card.doc.get("isHidden"))
            self.report.notes.append(
                f"a card on {card.board.name!r} shows the {what}, which was not made: its Pin places {name!r}"
            )
        else:
            fields.update(element_type="map", element_id=child["id"])
            name, on_hidden = child["name"], child.get("hidden") is True
            if card.doc.get("type") == "board":
                self._parent_map(child, card)
        if on_hidden and not card.board_hidden:
            self.report.hidden.board_pins += 1
            self.report.records_private = True
        card.slot.update(self._body("pin", card.pin_id, name, card.board_hidden or on_hidden, fields, card.ext))

    def _parent_map(self, child: dict[str, Any], card: _Card) -> None:
        parent = card.board_map
        if child is parent:
            self.report.notes.append(f"a card on {card.board.name!r} shows that board itself: no parent_map")
            return
        if "parent_map" in child:
            if child["parent_map"] != parent["id"]:
                self.report.notes.append(
                    f"{child['name']!r} is shown on more than one board: its parent_map is the first, kept"
                )
            return
        by_id = {m["id"]: m for m in self.maps}
        cur: dict[str, Any] | None = parent
        seen: set[str] = set()
        while cur is not None and cur["id"] not in seen:
            if cur is child:
                self.report.notes.append(
                    f"{child['name']!r} is shown on {card.board.name!r}, which sits under it: no parent_map (a loop)"
                )
                return
            seen.add(cur["id"])
            cur = by_id.get(str(cur.get("parent_map")))
        child["parent_map"] = parent["id"]
        ordered = self._body("map", child["id"], child["name"], child.get("hidden") is True, child, {})
        ordered.update({k: v for k, v in child.items() if k not in ordered})
        child.clear()
        child.update(ordered)
        card.board.made["child maps"] += 1

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
        for body in (
            self.relations
            + self.events
            + self.maps
            + self.pins
            + self.zones
            + self.markers
            + self.notes_made
            + self.timelines
            + self.constructs
        ):
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
        if self.own_ids:
            n.append(
                f"{self.own_ids} element{'' if self.own_ids == 1 else 's'} take their id from their {OW_ID_KEY!r} row"
                " (an OnlyWorlds push wrote it), so a round trip gives back the same elements"
            )
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
                " x_legendkeeper_pos (measured on two pins of one map, 2026-10-23)"
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
        if self.report.boards:
            n.append(
                "board places: tldraw's page space (y down), each shape through its parent chain (a frame's or a"
                " group's offset and rotation); a card's and a note's Pin at its centre, a text's at its origin (a"
                " text has no height), a frame's four Markers at its corners; each board's Map spans those points and"
                " the corners of every shape with a size, x = X - min_x and y = max_y - Y (OnlyWorlds counts from the"
                " bottom left), whole numbers, the page-space pair kept as x_legendkeeper_board_pos and the box as"
                " x_legendkeeper_board_extent"
            )
            n.append(
                f"a board's records (shapes, bindings, assets, pages) are kept whole in records/{RECORDS_PRODUCER}/,"
                " so what the elements do not carry (styles, rotation, order, lock state, an arrow's bend and"
                " anchors, a card's view, the images, the arrows that made no Relation) is kept there"
            )
        if self.api_maps:
            n.append(
                f"{self.api_maps} map document{'' if self.api_maps == 1 else 's'} whose map and pins could not be read"
                " through the API (the reason is under unread), not imported; LegendKeeper's export file (--file)"
                " reads them"
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
        for cid, (name, day, why) in self._cal.items():
            if day is not None:
                k = self._cal_dated[cid]
                n.append(
                    f"calendar {name!r} ({cid}): a Construct (supertype {CALENDAR_SUPERTYPE}) carrying"
                    f" {CALENDAR_FIELD}, grain day; {k} event{'' if k == 1 else 's'} dated, start_date and end_date"
                    f" the minutes divided by {day} (a day), rounded down, the minutes kept beside; the calendar kept"
                    " whole as"
                    f" {EXT_PREFIX}calendar"
                )
            else:
                n.append(
                    f"calendar {name!r} ({cid}): a Construct (supertype {CALENDAR_SUPERTYPE}), kept raw as"
                    f" {EXT_PREFIX}calendar, with no {CALENDAR_FIELD} and no dates, not exact: " + "; ".join(why)
                )
        left = [str(c.get("name") or cid) for cid, c in self.calendars.items() if cid not in self._cal]
        if left:
            n.append(
                f"{len(left)} calendar{'' if len(left) == 1 else 's'} no timeline names, not made: "
                + ", ".join(repr(x) for x in left)
            )
        if sum(self._cal_dated.values()):
            n.append(
                "the world's time_basic_unit is day: every date in the folder counts days from the calendar's epoch"
            )
        if self.items:
            n.append(f"not kept: {_NOT_KEPT}")

    def world(self) -> dict[str, Any]:
        pid = self.snap.project_id
        name = str(self.snap.project.get("name") or "").strip() or f"LegendKeeper project {pid}"
        world: dict[str, Any] = {"id": _uuid(f"legendkeeper:{pid}"), "name": name}
        if sum(self._cal_dated.values()):  # a new world has no unit yet: the dates name it
            world["time_basic_unit"] = "day"
        world["format_version"] = FORMAT_VERSION
        world["producer"] = {"tool": "onlyworlds", "version": __version__, "input": self.snap.producer_input}
        return world


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
    _write_records(out, conv.board_records, private=report.records_private)
    report.out = out
    return report


def _write_records(out: Path, boards: Mapping[str, dict[str, Any]], *, private: bool) -> None:
    """The boards' records into the finished folder (folder spec §4.5): one file a board under
    ``records/legendkeeper/``, in the folder's own JSON (UTF-8, LF, two-space indent), and the
    producer's entry in ``records/RECORDS.json``. ``write_folder`` writes elements only."""
    if not boards:
        return
    for rel, recs in boards.items():
        path = out / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(encode(recs))
    entry: dict[str, Any] = dict(RECORDS_ENTRY)
    if private:
        entry["private"] = True
    (out / RECORDS_MANIFEST).write_bytes(encode([entry]))


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

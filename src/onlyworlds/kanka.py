"""Read a Kanka JSON export into a world folder: no AI, no account, the same folder every time.

    python -m onlyworlds.kanka EXPORT.zip OUT-DIR [--plan]

or ``import_kanka(source, out_dir, plan_only=False)``. ``source`` is the
zip Kanka's "Export the campaign" gives for the JSON type (Campaign, Settings, Data, Export; the
Markdown type is for premium campaigns), or a directory it was unzipped into. ``--plan`` prints
what would become what and writes nothing. OUT-DIR must not exist yet (or be empty): a folder is
written whole, once, through ``write_folder``.

**Proven on one real export** (Kanka 3.15, ``export_version`` 3.15, made 2026-10-23 on a free
account, ``tests/fixtures/kanka/``): ``info.json``, ``campaign.json``, ``settings/modules.json``
and ``settings/custom-modules.json`` at the root; one folder per module holding one JSON per
entity named ``<slug>_<entity id>.json``, in ``characters/``, ``locations/``, ``notes/`` and
``organisations/``. Each file is the module's own row (a character's ``id``, ``name``, ``title``,
``age``, ``sex``, ``pronouns``, ``is_private``, its ``character_traits`` and the camelCase twins of
its lists) with an ``entity`` object holding what every module shares: ``id`` (the entity id, the
number in the filename), ``entity_id`` (the module row's id), ``parent_id``, ``name``, ``type``,
``entry`` (HTML), ``is_private``, ``tooltip``, ``image_path``, ``status_id``, timestamps,
``created_by``, and when present ``relationships``, ``posts``, ``mentions``, ``entityLocations``
and ``entityAttributes``. Two numbering systems meet in one file: ``entity.parent_id``,
``relationships[].owner_id``/``target_id`` and an ``[entity:N]`` mention name entity ids, while a
module row's foreign keys (``entityLocations[].location_id``) name module row ids.

**Believed**, not yet seen in a file: the folders ``families/``, ``races/``, ``items/``,
``creatures/``, ``events/``, ``abilities/``, ``quests/``, ``journals/``, ``maps/`` and every other
module; the shapes of ``character_families``, ``character_races`` and
``organisation_memberships`` items (``family_id``, ``race_id``, ``organisation_id``), of an
organisation's ``members`` (``character_id``), of ``is_dead``, of ``[entity:N|text]``, of a
campaign's ``entry``; that ``character_traits`` section 1 is appearance and 2 personality (Kanka's
own API names them so, read live by Skeld on 2026-07-18; the export carries the number only).

What becomes what (the type map follows Skeld's ruled table for his staged converter):

- **An entity becomes an element** of its module's type: ``characters`` Character, ``locations``
  Location, ``organisations`` Institution (Institution is the schema's organisation with a
  doctrine, status and allies; Collective is a group of members), ``notes`` Narrative (the four
  proven); ``families`` Family, ``races`` Species, ``items`` Object, ``creatures`` Creature,
  ``events`` Event, ``abilities`` Ability, ``quests`` and ``journals`` Narrative, ``maps`` Map
  (believed). Any other folder whose files carry an ``entity`` object (``tags``, ``calendars``,
  ``timelines``, a custom module) becomes a Narrative with supertype ``kanka`` and the folder's
  name as subtype, its entity ``type`` kept as ``x_kanka_type``. The entity's ``type`` is the
  element's ``supertype``; its ``name`` the name.
- **Text**: ``entry`` from HTML to Markdown (paragraphs, line breaks, headings, bold, italic,
  strike, code, links, lists, quotes, rules, images, tables; other tags read through to their
  text) is the ``description``, or the ``story`` for a Narrative from ``notes``, ``quests`` or
  ``journals``. A mention ``[entity:N]`` becomes the entity's name and joins ``x_kanka_mentions``
  (element ids, in order, once each); one whose entity is not in the folder stays as written and
  is reported. **Posts** (Kanka's extra articles on an entity) follow the entry in the same
  field, each under ``## <post name>``, in Kanka's ``position`` order; a post's ``location_id``,
  ``layout_id`` and pins are kept in ``x_kanka_posts_meta``.
- **The parent**: ``entity.parent_id`` resolves to the parent's element (``x_kanka_parent``), and
  to the type's own parent field when the parent is the same type (``parent_location``,
  ``parent_institution``, ``parent_narrative``, ``parent_object``, ``parent_species``,
  ``parent_map``).
- **Places, kin, kind, membership**: ``entityLocations`` (and a row's ``location_id``) resolve
  through the Locations' row ids to ``location`` (a single link: the first, every one kept in
  ``x_kanka_locations`` when there are more) or ``locations``; ``character_races`` and
  ``race_id`` to Character ``species``; ``character_families`` to ``family``;
  ``organisation_memberships`` and an organisation's ``members`` to the Character's
  ``institutions`` (the link direction the schema has).
- **A character's traits**: appearance (section 1) to ``physicality`` and personality (section 2)
  to ``mentality``, one ``Name: entry`` line each; another section is kept as ``x_kanka_traits``.
  ``is_dead`` puts ``[Deceased] `` before ``physicality`` (the schema skill's convention for a
  dead Character until a status field lands). ``status_id`` (1 on the two characters made in
  the editor, null on the starters) is kept as ``x_kanka_status_id``: what its numbers mean is
  not in the file.
- **Attributes** (``entityAttributes``): one whose name, lowercased with spaces as underscores, is
  a field of the type fills it when the value fits (text; a whole number for an integer; only
  mentions, of the linked type, for a link); every other is kept as ``x_kanka_<name>`` with its
  mentions as names, and reported.
- **Relationships** become Relation elements named by the relation's text: the owner on
  ``actor`` (a Character) or on Relation's field for its type, the target on Relation's field
  for its type, ``x_kanka_source``/``x_kanka_target`` the two element ids so the direction is
  kept. A two-way relationship is two rows that name each other as ``mirror_id``: it becomes one
  Relation (``x_kanka_two_way``), owned by the row with the lower id, and a side that differs
  from the other is kept as ``x_kanka_mirror``. ``attitude`` and ``colour`` are kept as
  extensions.
- **Every key not placed** (on the row or the entity) is kept as ``x_kanka_<key>`` and listed in
  the report. Not kept, named in the report: timestamps and who made or changed a row, Kanka's
  own numbering kept elsewhere (``campaign_id``, ``type_id``), image focus points and uploads'
  uuids, marketplace ids, pin and display flags, the server's ``mentions`` index (the text holds
  the mentions), and the camelCase twins of a character's lists.

**Exact duplicates fold into one**: two relationships, posts, traits or attributes on one entity
whose every field is equal but their ids, positions and timestamps are one, and the report names
each fold. Anything that differs is kept.

**What the source hides, the folder hides: never dropped, never public** (Skeld's rule). Each
hidden thing is an element carrying ``hidden: true`` at the top of its body (OnlyWorlds' hidden
mark), counted in the report:

- an entity whose ``is_private`` is true (on the entity or its row): its element, whole;
- a post whose ``visibility_id`` is not 1 (all), on a visible entity: its own Narrative, the
  post's name its name and its text the ``story``, linked to the entity's element (Narrative's
  field for the entity's type, ``parent_narrative`` for a Narrative) and ``x_kanka_parent``; the
  entity keeps only the visible text;
- a relationship whose ``visibility_id`` is not 1 on either side, or that touches a hidden
  entity: its Relation;
- on a visible entity, what cannot be an element of its own (a trait or list item whose
  ``is_private`` is true, an attribute whose ``is_private`` or ``is_hidden`` is true, every
  attribute when ``is_attributes_private`` is true, and the personality traits of a character
  whose ``is_personality_visible`` is false): one Narrative per entity, ``<name>: hidden
  details``, its ``story`` a section per kind (``## Personality``, ``## Attributes``, ...) and a
  private list item kept as ``x_kanka_<list>``, linked to the entity the same way.

A visible text that mentions a hidden entity by name is named in the report.

**Starter entries travel.** A new Kanka campaign seeds template entries (``[Your Character
Name]``, ``[Your Kingdom Name]``, ...), and they are in the export. Nothing in the data marks
them: ``is_template`` is false, ``marketplace_uuid`` null and ``created_by`` the person's own id
on all of them, as on what the person typed. Their only tells are their bracketed names and a
``created_at`` within seconds of the campaign's, neither a rule. So every entry is imported, and
the report names the ones made within ``STARTER_WINDOW`` seconds of the campaign as possibly
Kanka's starter content: a note, never a leave-out.

**Ids are UUIDv5** in ``KANKA_NAMESPACE`` of ``kanka:<campaign id>:<entity id>`` for an entity and
``kanka:<campaign id>:relation:<relationship id>`` for a Relation (the lower id of a two-way
pair), ``kanka:<campaign id>:post:<post id>`` for a hidden post's Narrative and
``kanka:<campaign id>:hidden:<entity id>`` for an entity's hidden details, so the same export
twice gives byte-equal folders and a later export of the same campaign finds the same elements.
``world.json``: ``id`` UUIDv5 of ``kanka:<campaign id>``, ``name`` the campaign's name,
``description`` its ``entry`` when it has one, ``producer`` ``{"tool": "onlyworlds", "version":
..., "input": "kanka-export"}`` (``PRODUCER_INPUT``; on the folder spec's list, §4.2, from
v0.3.17), ``format_version`` this package's.

The folder lint of the schema distribution does not know the ``hidden`` key yet (keel serves it
on a hidden element to a reader who still sees it): it reports one line for each hidden element.

From the command line: exit 0 written (or planned), 2 on bad arguments (a missing source, an
OUT-DIR that is not empty, a file that is not a zip, an export with no ``campaign.json``).
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
import uuid
from collections.abc import Callable, Iterable, Mapping
from contextlib import ExitStack
from dataclasses import dataclass, field
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from ._schema import FIELD_KINDS, LINK_TARGETS
from ._version import __version__
from .folder import FORMAT_VERSION, write_folder
from .notion import _open_tree

__all__ = [
    "EXT_PREFIX",
    "KANKA_NAMESPACE",
    "MODULE_TYPES",
    "PRODUCER_INPUT",
    "PROVEN_MODULES",
    "STARTER_WINDOW",
    "Folded",
    "Hidden",
    "ImportReport",
    "ModulePlan",
    "Unplaced",
    "Unresolved",
    "html_to_markdown",
    "import_kanka",
    "main",
]

#: The ``producer.input`` word for this door; new to the folder spec's list.
PRODUCER_INPUT = "kanka-export"

#: The namespace every id this door mints is UUIDv5 in. Fixed for good: changing it would give
#: every element of every re-imported campaign a new id.
KANKA_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "https://onlyworlds.com/ns/kanka")

#: Every extension key this door writes starts with this.
EXT_PREFIX = "x_kanka_"

#: The supertype of a Narrative made from a module with no OnlyWorlds type.
UNTYPED_SUPERTYPE = "kanka"

#: Export folder -> element type (Skeld's table; the four in ``PROVEN_MODULES`` read on a real file).
MODULE_TYPES: dict[str, str] = {
    "characters": "character",
    "locations": "location",
    "organisations": "institution",
    "notes": "narrative",
    "families": "family",
    "races": "species",
    "items": "object",
    "creatures": "creature",
    "events": "event",
    "abilities": "ability",
    "quests": "narrative",
    "journals": "narrative",
    "maps": "map",
}
PROVEN_MODULES = frozenset({"characters", "locations", "organisations", "notes"})

#: Modules whose text is a Narrative's ``story`` rather than its ``description``.
_STORY_MODULES = frozenset({"notes", "quests", "journals"})

#: Seconds after the campaign's ``created_at`` within which an entity is named possible starter content.
STARTER_WINDOW = 5.0

#: An element type -> its own parent field, which takes a parent of the same type.
_PARENT_FIELD: dict[str, str] = {
    "location": "parent_location",
    "institution": "parent_institution",
    "narrative": "parent_narrative",
    "object": "parent_object",
    "species": "parent_species",
    "map": "parent_map",
}

#: Root files the door reads; anything else at the root is named in the report.
_ROOT_FILES = frozenset({"info.json", "campaign.json"})

#: Keys read by the door itself (never kept as ``x_kanka_<key>`` by the generic rule).
_ROW_HANDLED = frozenset(
    {
        "id",
        "name",
        "entry",
        "type",
        "is_private",
        "entity",
        "location_id",
        "race_id",
        "is_dead",
        "character_traits",
        "character_families",
        "character_races",
        "organisation_memberships",
        "members",
        "is_personality_visible",
    }
)
_ENTITY_HANDLED = frozenset(
    {
        "id",
        "entity_id",
        "parent_id",
        "name",
        "type",
        "entry",
        "is_private",
        "is_attributes_private",
        "posts",
        "relationships",
        "entityLocations",
        "entityAttributes",
    }
)

#: What a row or entity carries that the folder does not keep (one report line).
_NOT_KEPT_KEYS = frozenset(
    {
        "campaign_id",
        "type_id",
        "created_at",
        "updated_at",
        "deleted_at",
        "created_by",
        "updated_by",
        "deleted_by",
        "focus_x",
        "focus_y",
        "image_uuid",
        "header_uuid",
        "marketplace_uuid",
        "is_personality_pinned",
        "is_appearance_pinned",
        "is_pinned",
        "mentions",
        "characterTraits",
        "characterFamilies",
        "characterRaces",
        "organisationMemberships",
    }
)
#: Flags kept only when true.
_KEPT_WHEN_TRUE = frozenset({"is_template"})
_NOT_KEPT = (
    "timestamps and who made or changed a row (created_at, updated_at, created_by, updated_by), "
    "campaign_id and type_id, image focus points and upload uuids, marketplace ids, pin and display flags, "
    "the server's mentions index (the text holds the mentions), and the camelCase twins of a character's lists "
    "(characterTraits and the rest: the same rows without their ids)"
)

#: Fields that make two copies the same thing; every other key (ids, order, times) may differ.
_NOT_CONTENT = frozenset(
    {
        "id",
        "mirror_id",
        "position",
        "default_order",
        "created_at",
        "updated_at",
        "created_by",
        "updated_by",
        "deleted_at",
        "deleted_by",
        "marketplace_uuid",
        "entity_id",
        "character_id",
        "words",
    }
)

_MENTION = re.compile(r"\[entity:(?P<id>\d+)(?:\|(?P<text>[^\]]*))?\]")
_FILE_ID = re.compile(r"_(?P<id>\d+)\.json$")
_INT = re.compile(r"\s*-?\d+\s*")

#: type -> {lowercased field name: field name}, so an attribute ``str`` finds ``STR``.
_FIELD_BY_LOWER: dict[str, dict[str, str]] = {t: {f.lower(): f for f in kinds} for t, kinds in FIELD_KINDS.items()}

#: target type -> Relation's multi-link field for it (schema order, the first one wins).
_RELATION_FIELD_FOR: dict[str, str] = {}
for _f, _kind in FIELD_KINDS["relation"].items():
    if _kind == "multi_link":
        _RELATION_FIELD_FOR.setdefault(LINK_TARGETS["relation"][_f], _f)

#: target type -> Narrative's multi-link field for it: how a hidden Narrative links its entity.
_NARRATIVE_FIELD_FOR: dict[str, str] = {}
for _f, _kind in FIELD_KINDS["narrative"].items():
    if _kind == "multi_link":
        _NARRATIVE_FIELD_FOR.setdefault(LINK_TARGETS["narrative"][_f], _f)


def _uuid(key: str) -> str:
    return str(uuid.uuid5(KANKA_NAMESPACE, key))


def _norm(name: str) -> str:
    """A key lowercased, camelCase and whitespace runs as underscores: the name a field is compared to."""
    snake = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", name.strip())
    return re.sub(r"[\s-]+", "_", snake.lower())


def _empty(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {}


def _on(value: Any) -> bool:
    """Kanka writes a flag as a boolean, 0/1 or ``"0"``/``"1"``."""
    return value not in (None, False, 0, "", "0", "false")


def _public(visibility: Any) -> bool:
    """``visibility_id`` 1 is "all"; none given reads as all."""
    return visibility is None or visibility == 1 or visibility == "1"


def _content(row: Mapping[str, Any]) -> str:
    """A row's content as one comparable string: every key but ids, order and times."""
    return json.dumps({k: v for k, v in row.items() if k not in _NOT_CONTENT}, sort_keys=True, ensure_ascii=False)


def _when(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _int_id(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value)
    return None


# ---------------------------------------------------------------------------
# HTML to Markdown
# ---------------------------------------------------------------------------

_VOID = frozenset({"br", "hr", "img", "input", "meta", "link", "wbr", "col", "area", "source", "embed"})
_BLOCK = frozenset(
    {
        "p",
        "div",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "ul",
        "ol",
        "li",
        "blockquote",
        "pre",
        "hr",
        "table",
        "thead",
        "tbody",
        "tfoot",
        "tr",
        "td",
        "th",
        "figure",
        "figcaption",
        "section",
        "article",
        "header",
        "footer",
        "aside",
        "details",
        "summary",
        "dl",
        "dt",
        "dd",
    }
)


@dataclass
class _Node:
    tag: str
    attrs: dict[str, str]
    children: list[_Node | str] = field(default_factory=list)


class _Tree(HTMLParser):
    """A forgiving parse into nodes: an end tag closes up to its own open tag, a stray one is ignored."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = _Node("root", {})
        self.stack = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = _Node(tag, {k: v or "" for k, v in attrs})
        self.stack[-1].children.append(node)
        if tag not in _VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.stack[-1].children.append(_Node(tag, {k: v or "" for k, v in attrs}))

    def handle_endtag(self, tag: str) -> None:
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, data: str) -> None:
        self.stack[-1].children.append(data)


def _is_block(child: _Node | str) -> bool:
    return isinstance(child, _Node) and child.tag in _BLOCK


def _wrap(text: str, mark: str) -> str:
    core = text.strip()
    if not core:
        return text
    lead, trail = text[: len(text) - len(text.lstrip())], text[len(text.rstrip()) :]
    return f"{lead}{mark}{core}{mark}{trail}"


def _inline(children: Iterable[_Node | str], pre: bool = False) -> str:
    out: list[str] = []
    for c in children:
        if isinstance(c, str):
            out.append(c if pre else re.sub(r"\s+", " ", c))
            continue
        tag = c.tag
        if tag == "br":
            out.append("\n")
        elif tag in ("strong", "b"):
            out.append(_wrap(_inline(c.children, pre), "**"))
        elif tag in ("em", "i"):
            out.append(_wrap(_inline(c.children, pre), "*"))
        elif tag in ("s", "strike", "del"):
            out.append(_wrap(_inline(c.children, pre), "~~"))
        elif tag == "code":
            out.append(_wrap(_inline(c.children, True), "`"))
        elif tag == "a":
            text = _inline(c.children, pre)
            href = c.attrs.get("href", "")
            out.append(f"[{text.strip()}]({href})" if href and text.strip() else text)
        elif tag == "img":
            src = c.attrs.get("src", "")
            out.append(f"![{c.attrs.get('alt', '')}]({src})" if src else "")
        elif tag in _BLOCK:
            out.append(" " + " ".join(_blocks(c)) + " ")
        else:
            out.append(_inline(c.children, pre))
    return "".join(out)


def _clean(text: str) -> str:
    """Inline text with each line trimmed of the spaces HTML layout leaves."""
    return "\n".join(line.strip() for line in text.strip().split("\n"))


def _blocks(node: _Node) -> list[str]:
    """A container's children as Markdown blocks: runs of inline content are paragraphs."""
    out: list[str] = []
    run: list[_Node | str] = []

    def flush() -> None:
        text = _clean(_inline(run))
        if text:
            out.append(text)
        run.clear()

    for c in node.children:
        if not _is_block(c):
            run.append(c)
            continue
        flush()
        assert isinstance(c, _Node)
        block = _block(c)
        if block:
            out.append(block)
    flush()
    return out


def _indent(body: str, marker: str) -> str:
    first, *rest = body.split("\n")
    return "\n".join([marker + first, *[(" " * len(marker) + line) if line else "" for line in rest]])


def _block(node: _Node) -> str:
    tag = node.tag
    if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
        text = _clean(_inline(node.children)).replace("\n", " ")
        return f"{'#' * int(tag[1])} {text}" if text else ""
    if tag == "hr":
        return "---"
    if tag == "pre":
        return "```\n" + _inline(node.children, True).strip("\n") + "\n```"
    if tag == "blockquote":
        inner = "\n\n".join(_blocks(node))
        return "\n".join("> " + line if line else ">" for line in inner.split("\n")) if inner else ""
    if tag in ("ul", "ol"):
        start = _int_id(node.attrs.get("start")) or 1
        lines = []
        for i, li in enumerate(c for c in node.children if isinstance(c, _Node) and c.tag == "li"):
            marker = f"{start + i}. " if tag == "ol" else "- "
            lines.append(_indent("\n".join(_blocks(li)), marker))
        return "\n".join(lines)
    if tag == "table":
        rows: list[list[str]] = []

        def walk(n: _Node) -> None:
            for c in n.children:
                if isinstance(c, _Node) and c.tag == "tr":
                    cells = [c2 for c2 in c.children if isinstance(c2, _Node) and c2.tag in ("td", "th")]
                    rows.append(
                        ["<br>".join(_blocks(cell)).replace("|", "\\|").replace("\n", "<br>") for cell in cells]
                    )
                elif isinstance(c, _Node):
                    walk(c)

        walk(node)
        width = max((len(r) for r in rows), default=0)
        if not width:
            return ""
        rows = [r + [""] * (width - len(r)) for r in rows]
        lines = ["| " + " | ".join(rows[0]) + " |", "| " + " | ".join(["---"] * width) + " |"]
        return "\n".join(lines + ["| " + " | ".join(r) + " |" for r in rows[1:]])
    return "\n\n".join(_blocks(node))


def html_to_markdown(html: str | None) -> str:
    """Kanka's entry HTML as Markdown; mentions (``[entity:N]``) are left as written."""
    if not html:
        return ""
    tree = _Tree()
    tree.feed(html)
    tree.close()
    return "\n\n".join(_blocks(tree.root)).strip()


# ---------------------------------------------------------------------------
# The report
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ModulePlan:
    """One export folder and what its entities became."""

    folder: str
    type: str
    entities: int
    #: ``proven`` (read on a real export), ``believed`` or ``untyped``
    status: str


@dataclass(frozen=True)
class Unplaced:
    """A key (or an attribute) not placed on a field, kept as ``kept_as``."""

    element: str
    key: str
    why: str
    kept_as: str


@dataclass(frozen=True)
class Unresolved:
    """A link or mention whose target is not an element of the folder."""

    element: str
    #: ``parent``, ``mention``, ``relationship '<text>'``, ``entityLocations``, ...
    where: str
    #: the Kanka id as written (an entity id, or a module row id for a row's foreign key)
    target: str
    why: str


@dataclass(frozen=True)
class Folded:
    """Exact copies on one entity folded into one."""

    element: str
    #: ``relationship``, ``post``, ``trait`` or ``attribute``
    what: str
    name: str
    copies: int


@dataclass
class Hidden:
    """What the source hides, imported with ``hidden: true``: never dropped, never public."""

    #: entities marked private: elements carrying the mark
    entities: int = 0
    #: posts not visible to all on a visible entity: each its own hidden Narrative
    posts: int = 0
    #: relationships hidden on either side, or touching a hidden entity: hidden Relations
    relationships: int = 0
    #: on a visible entity, held in its hidden-details Narrative
    traits: int = 0
    personality: int = 0
    attributes: int = 0
    links: int = 0
    #: hidden-details Narratives made (one per visible entity with any of the four above)
    details: int = 0


@dataclass
class ImportReport:
    source: Path
    world: dict[str, Any]
    counts: dict[str, int] = field(default_factory=dict)
    modules: list[ModulePlan] = field(default_factory=list)
    unplaced: list[Unplaced] = field(default_factory=list)
    #: relation text -> Relation elements made for it
    relations: dict[str, int] = field(default_factory=dict)
    folded: list[Folded] = field(default_factory=list)
    unresolved: list[Unresolved] = field(default_factory=list)
    hidden: Hidden = field(default_factory=Hidden)
    #: names of the entities made within STARTER_WINDOW seconds of the campaign (imported all the same)
    possibly_starter: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    #: where the folder was written; None for a plan
    out: Path | None = None

    @property
    def total(self) -> int:
        return sum(self.counts.values())

    def render(self) -> str:
        """The report in prose, one finding a line."""
        lines: list[str] = []
        name = self.world.get("name", "")
        by_type = ", ".join(f"{t} {n}" for t, n in sorted(self.counts.items()))
        lines.append(f"Kanka export {self.source} ({name!r}): {self.total} elements ({by_type or 'none'}).")
        if self.modules:
            lines.append("What became what:")
            for m in self.modules:
                how = {
                    "proven": "read on a real export",
                    "believed": "believed, not yet seen in a real export",
                    "untyped": f"no OnlyWorlds type: Narratives, supertype {UNTYPED_SUPERTYPE}, subtype {m.folder!r}",
                }[m.status]
                lines.append(f"  - {m.folder}/ ({m.entities}): {m.type}; {how}")
        if self.relations:
            listed = ", ".join(f"{t!r} {n}" for t, n in sorted(self.relations.items()))
            lines.append(f"Relationships kept as Relation elements ({sum(self.relations.values())}): {listed}.")
        if self.folded:
            lines.append(f"Exact duplicates folded into one ({len(self.folded)}):")
            lines += [f"  - {f.element!r}: {f.copies} identical {f.what}s {f.name!r}, kept once" for f in self.folded]
        if self.possibly_starter:
            listed = ", ".join(repr(n) for n in self.possibly_starter)
            lines.append(
                f"Possibly Kanka's starter content (made within {STARTER_WINDOW:g} seconds of the campaign;"
                f" nothing in the data marks it, so it is imported): {listed}."
            )
        h = self.hidden
        elements = [
            (h.entities, "private entity (is_private)", "private entities (is_private)"),
            (
                h.posts,
                "post not visible to all, its own Narrative (visibility_id)",
                "posts not visible to all, each its own Narrative (visibility_id)",
            ),
            (
                h.relationships,
                "relationship hidden on a side or touching a hidden entity (visibility_id)",
                "relationships hidden on a side or touching a hidden entity (visibility_id)",
            ),
        ]
        held = [
            (h.traits, "private trait (is_private)", "private traits (is_private)"),
            (
                h.personality,
                "personality trait not visible to players (is_personality_visible)",
                "personality traits not visible to players (is_personality_visible)",
            ),
            (
                h.attributes,
                "private or hidden attribute (is_private, is_hidden, is_attributes_private)",
                "private or hidden attributes (is_private, is_hidden, is_attributes_private)",
            ),
            (h.links, "private link (is_private)", "private links (is_private)"),
        ]
        said = [f"{n} {one if n == 1 else many}" for n, one, many in elements if n]
        inside = [f"{n} {one if n == 1 else many}" for n, one, many in held if n]
        if inside:
            said.append(
                f"{h.details} hidden-details Narrative{'' if h.details == 1 else 's'} holding " + ", ".join(inside)
            )
        if said:
            lines.append("Hidden as the source hides it (elements carrying hidden: true): " + "; ".join(said) + ".")
        if self.unplaced:
            lines.append(f"Keys not placed on a field ({len(self.unplaced)}), kept as extensions:")
            lines += [f"  - {u.element!r} / {u.key!r}: {u.why}; kept as {u.kept_as}" for u in self.unplaced]
        if self.unresolved:
            lines.append(f"Links and mentions whose target is not in the folder ({len(self.unresolved)}):")
            lines += [f"  - {u.element!r}, {u.where}: {u.target}: {u.why}" for u in self.unresolved]
        if self.notes:
            lines.append(f"Notes ({len(self.notes)}):")
            lines += [f"  - {n}" for n in self.notes]
        lines.append(f"Wrote {self.out}." if self.out is not None else "Plan only: nothing written.")
        return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# The import
# ---------------------------------------------------------------------------


@dataclass
class _Item:
    """One entity's element being built."""

    folder: str
    path: str
    row: dict[str, Any]
    ent: dict[str, Any]
    entity_id: int
    etype: str
    eid: str
    name: str
    typed: bool
    fields: dict[str, Any] = field(default_factory=dict)
    ext: dict[str, Any] = field(default_factory=dict)
    taken: set[str] = field(default_factory=set)
    mentions: list[str] = field(default_factory=list)
    #: the entity is private: its element carries ``hidden: true``, whole
    hidden: bool = False
    #: on a visible entity, what the source hides: heading -> lines, and extension keys
    secret: dict[str, list[str]] = field(default_factory=dict)
    secret_ext: dict[str, Any] = field(default_factory=dict)
    secret_mentions: list[str] = field(default_factory=list)


class _Importer:
    def __init__(self, files: Mapping[str, Callable[[], bytes]], source: Path, notes: list[str]) -> None:
        self.files = files
        self.report = ImportReport(source=source, world={}, notes=list(notes))
        self.campaign: dict[str, Any] = {}
        self.items: list[_Item] = []
        self.by_entity: dict[int, _Item] = {}
        #: (folder, module row id) -> item: what a row's foreign key names
        self.by_row: dict[tuple[str, int], _Item] = {}
        self.relations: list[dict[str, Any]] = []
        #: hidden Narratives: one per private post, one per entity's hidden details
        self.narratives: list[dict[str, Any]] = []
        self._unplaced_seen: set[Unplaced] = set()

    def _json(self, rel: str) -> Any:
        try:
            return json.loads(self.files[rel]().decode("utf-8-sig"))
        except (ValueError, UnicodeDecodeError) as exc:
            self.report.notes.append(f"{rel}: not readable JSON ({type(exc).__name__}); skipped")
            return None

    def _id(self, *parts: str) -> str:
        return _uuid(":".join(("kanka", str(self.campaign.get("id")), *parts)))

    # -- pass 1: every entity, with its type and id ---------------------------

    def collect(self) -> None:
        campaign = self._json("campaign.json") if "campaign.json" in self.files else None
        if not isinstance(campaign, dict) or _empty(campaign.get("id")):
            raise ValueError(f"{self.report.source}: no campaign.json with an id (is it Kanka's JSON export?)")
        self.campaign = campaign
        info = self._json("info.json") if "info.json" in self.files else None
        if isinstance(info, dict):
            version = info.get("export_version")
            self.report.notes.append(
                f"Kanka {info.get('kanka_version')}, export version {version}"
                + ("" if str(version) == "3.15" else " (this door was proven on 3.15)")
            )
        born = _when(campaign.get("created_at"))
        plans: dict[str, int] = {}
        for rel in sorted(self.files):
            parts = rel.split("/")
            if len(parts) == 1:
                if rel not in _ROOT_FILES:
                    self.report.notes.append(f"{rel}: a file at the export's root this door does not read")
                continue
            folder = parts[0]
            if folder == "settings":
                self._setting(rel)
                continue
            if len(parts) != 2 or not rel.lower().endswith(".json"):
                self.report.notes.append(f"{rel}: not an entity file (one JSON per entity in a module folder); skipped")
                continue
            row = self._json(rel)
            if row is None:
                continue
            ent = row.get("entity") if isinstance(row, dict) else None
            entity_id = _int_id(ent.get("id")) if isinstance(ent, dict) else None
            if not isinstance(row, dict) or not isinstance(ent, dict) or entity_id is None:
                self.report.notes.append(f"{rel}: no entity object with an id; skipped")
                continue
            m = _FILE_ID.search(rel)
            if m is not None and int(m["id"]) != entity_id:
                self.report.notes.append(f"{rel}: the filename's number is not the entity's id {entity_id}")
            if entity_id in self.by_entity:
                self.report.notes.append(f"{rel}: a second file for entity {entity_id}; the first is kept")
                continue
            name = str(ent.get("name") or row.get("name") or "").strip() or f"Untitled ({entity_id})"
            etype = MODULE_TYPES.get(folder, "narrative")
            item = _Item(
                folder, rel, row, ent, entity_id, etype, self._id(str(entity_id)), name, folder in MODULE_TYPES
            )
            if _on(ent.get("is_private")) or _on(row.get("is_private")):
                item.hidden = True
                self.report.hidden.entities += 1
            self.items.append(item)
            self.by_entity[entity_id] = item
            row_id = _int_id(row.get("id"))
            if row_id is not None:
                self.by_row[(folder, row_id)] = item
            plans[folder] = plans.get(folder, 0) + 1
            made = _when(ent.get("created_at"))
            if born is not None and made is not None and 0 <= (made - born).total_seconds() <= STARTER_WINDOW:
                self.report.possibly_starter.append(name)
        for folder, n in sorted(plans.items()):
            status = "proven" if folder in PROVEN_MODULES else "believed" if folder in MODULE_TYPES else "untyped"
            self.report.modules.append(ModulePlan(folder, MODULE_TYPES.get(folder, "narrative"), n, status))

    def _setting(self, rel: str) -> None:
        data = self._json(rel)
        if rel == "settings/custom-modules.json" and data:
            self.report.notes.append(
                f"{rel}: custom modules are defined; their entities, if exported, are read by folder"
            )
        elif rel not in ("settings/modules.json", "settings/custom-modules.json"):
            self.report.notes.append(f"{rel}: a settings file this door does not read")

    # -- pass 2: fields, links, text -----------------------------------------

    def fill(self) -> None:
        for item in self.items:
            self._fill(item)
        self._memberships()
        for item in self.items:
            self._details(item)
        self._relationships()

    def _unplaced(self, item: _Item, key: str, why: str, kept_as: str) -> None:
        u = Unplaced(item.name, key, why, kept_as)
        if u not in self._unplaced_seen:
            self._unplaced_seen.add(u)
            self.report.unplaced.append(u)

    def _keep(self, item: _Item, key: str, value: Any, why: str) -> None:
        """Keep a value as ``x_kanka_<key>`` (``_2`` and on when taken) and report it."""
        base = f"{EXT_PREFIX}{_norm(key) or 'value'}"
        ext, n = base, 2
        while ext in item.taken:
            ext, n = f"{base}_{n}", n + 1
        item.taken.add(ext)
        item.ext[ext] = value
        self._unplaced(item, key, why, ext)

    def _own(self, item: _Item, key: str, value: Any) -> None:
        """One of the door's own extension keys (not reported: the docstring names them)."""
        ext = f"{EXT_PREFIX}{key}"
        item.taken.add(ext)
        item.ext[ext] = value

    @staticmethod
    def _why_missing(entity_id: int | None) -> str:
        return "no such entity in the export"

    def _fold(self, item: _Item, what: str, rows: list[dict[str, Any]], name_key: str = "name") -> list[dict[str, Any]]:
        """Exact copies kept once, the first in order; each fold reported."""
        seen: dict[str, int] = {}
        kept: list[dict[str, Any]] = []
        copies: list[int] = []
        for row in rows:
            key = _content(row)
            if key in seen:
                copies[seen[key]] += 1
                continue
            seen[key] = len(kept)
            kept.append(row)
            copies.append(1)
        for row, n in zip(kept, copies, strict=True):
            if n > 1:
                self.report.folded.append(Folded(item.name, what, str(row.get(name_key) or ""), n))
        return kept

    def _text(self, item: _Item, html: Any, mentions: list[str] | None = None, *, shown: bool = True) -> str:
        """Entry HTML as Markdown, mentions as names (collected into ``mentions``, else the item's),
        unresolved ones as written (reported). ``shown``: the text is on a visible element."""
        md = html_to_markdown(html if isinstance(html, str) else None)
        into = item.mentions if mentions is None else mentions

        def swap(m: re.Match[str]) -> str:
            target = self.by_entity.get(int(m["id"]))
            if target is None:
                self.report.unresolved.append(
                    Unresolved(item.name, "mention", m["id"], self._why_missing(int(m["id"])))
                )
                return m[0]
            if target is not item and target.eid not in into:
                into.append(target.eid)
            if shown and not item.hidden and target.hidden:
                self.report.notes.append(f"{item.name!r}: visible text mentions the hidden {target.name!r} by name")
            return m["text"] if m["text"] else target.name

        return _MENTION.sub(swap, md)

    def _hide(self, item: _Item, heading: str, line: str) -> None:
        """A line of what the source hides on a visible entity, for its hidden-details Narrative."""
        item.secret.setdefault(heading, []).append(line)

    def _fill(self, item: _Item) -> None:
        row, ent = item.row, item.ent
        item.taken |= {f"{EXT_PREFIX}{k}" for k in ("id", "entity_id", "module", "parent", "mentions")}
        self._own(item, "id", row.get("id"))
        self._own(item, "entity_id", item.entity_id)
        self._own(item, "module", item.folder)
        kind = ent.get("type") if not _empty(ent.get("type")) else row.get("type")
        if item.typed:
            if not _empty(kind):
                item.fields["supertype"] = str(kind)
        else:
            item.fields["supertype"] = UNTYPED_SUPERTYPE
            item.fields["subtype"] = item.folder
            if not _empty(kind):
                self._keep(item, "type", kind, "a module with no OnlyWorlds type keeps its own type")
        self._parent(item)

        # text: the entry, then the posts
        parts: list[str] = []
        entry = ent.get("entry") if not _empty(ent.get("entry")) else row.get("entry")
        text = self._text(item, entry)
        if text:
            parts.append(text)
        if not _empty(row.get("entry")) and not _empty(ent.get("entry")) and row.get("entry") != ent.get("entry"):
            self._keep(item, "entry", row.get("entry"), "the row's entry differs from the entity's (kept as written)")
        parts += self._posts(item)
        body = "\n\n".join(parts)
        if body:
            item.fields["story" if item.etype == "narrative" and item.folder in _STORY_MODULES else "description"] = (
                body
            )

        if item.etype == "character":
            self._character(item)
        self._places(item)
        self._attributes(item)
        if item.folder != "organisations" and not _empty(row.get("members")):  # organisations: _memberships
            self._keep(item, "members", row.get("members"), "members on a module that is not organisations")
        self._generic(item)

    def _parent(self, item: _Item) -> None:
        # Boss's shape point: a child's entity.parent_id is the parent's entity.id (the number in the
        # parent's filename), never its entity.entity_id, which is the parent's module row id.
        raw = item.ent.get("parent_id")
        pid = _int_id(raw)
        if pid is None:
            if not _empty(raw):
                self._keep(item, "parent_id", raw, "not an entity id")
            return
        parent = self.by_entity.get(pid)
        if parent is None:
            self.report.unresolved.append(Unresolved(item.name, "parent", str(pid), self._why_missing(pid)))
            self._keep(item, "parent_id", pid, "its parent is not in the folder")
            return
        self._own(item, "parent", parent.eid)
        pfield = _PARENT_FIELD.get(item.etype)
        if pfield and parent.etype == item.etype:
            item.fields[pfield] = parent.eid

    def _posts(self, item: _Item) -> list[str]:
        posts = [p for p in item.ent.get("posts") or [] if isinstance(p, dict)]
        posts.sort(
            key=lambda p: (p.get("position") is None, _int_id(p.get("position")) or 0, _int_id(p.get("id")) or 0)
        )
        posts = self._fold(item, "post", posts)
        out: list[str] = []
        meta: list[dict[str, Any]] = []
        for p in posts:
            name = str(p.get("name") or "").strip() or "Post"
            if not item.hidden and not _public(p.get("visibility_id")):
                self._post_narrative(item, p, name)
                continue
            text = self._text(item, p.get("entry"))
            out.append(f"## {name}\n\n{text}" if text else f"## {name}")
            extra = {k: p[k] for k in ("location_id", "layout_id", "is_pinned", "is_template") if _on(p.get(k))}
            settings = p.get("settings")
            if isinstance(settings, dict) and any(k != "collapsed" for k in settings):
                extra["settings"] = settings  # "collapsed" is how the page shows the post, not content
            if not _public(p.get("visibility_id")):
                extra["visibility_id"] = p.get("visibility_id")
            if extra:
                meta.append({"name": name, **extra})
        if meta:
            self._keep(item, "posts_meta", meta, "a post's layout, place, pins or visibility have no field")
        return out

    @staticmethod
    def _link_back(fields: dict[str, Any], item: _Item) -> None:
        """A Narrative's link to the entity it came from: Narrative's field for the entity's type."""
        if item.etype == "narrative":
            fields["parent_narrative"] = item.eid
        elif item.etype in _NARRATIVE_FIELD_FOR:
            fields[_NARRATIVE_FIELD_FOR[item.etype]] = [item.eid]

    def _hidden_narrative(
        self, key: str, name: str, story: str, item: _Item, ext: dict[str, Any], mentions: list[str]
    ) -> None:
        fields: dict[str, Any] = {"story": story} if story else {}
        self._link_back(fields, item)
        body: dict[str, Any] = {"type": "narrative", "id": self._id(key), "name": name, "hidden": True}
        for fname in FIELD_KINDS["narrative"]:
            if fname in fields:
                body[fname] = fields[fname]
        body[f"{EXT_PREFIX}parent"] = item.eid
        body.update(ext)
        if mentions:
            body[f"{EXT_PREFIX}mentions"] = mentions
        self.narratives.append(body)

    def _post_narrative(self, item: _Item, p: dict[str, Any], name: str) -> None:
        """A post the source hides on a visible entity: its own Narrative, hidden, linked to the entity."""
        mentions: list[str] = []
        text = self._text(item, p.get("entry"), mentions, shown=False)
        ext: dict[str, Any] = {f"{EXT_PREFIX}id": p.get("id"), f"{EXT_PREFIX}module": "posts"}
        ext[f"{EXT_PREFIX}visibility_id"] = p.get("visibility_id")
        for k in ("location_id", "layout_id", "is_pinned", "is_template"):
            if _on(p.get(k)):
                ext[f"{EXT_PREFIX}{k}"] = p[k]
        self._hidden_narrative(f"post:{p.get('id')}", name, text, item, ext, mentions)
        self.report.hidden.posts += 1

    def _details(self, item: _Item) -> None:
        """The hidden-details Narrative of a visible entity, when the source hides any of its details."""
        if not item.secret and not item.secret_ext:
            return
        story = "\n\n".join(f"## {h}\n\n" + "\n".join(lines) for h, lines in item.secret.items())
        ext = {f"{EXT_PREFIX}entity_id": item.entity_id, **item.secret_ext}
        self._hidden_narrative(
            f"hidden:{item.entity_id}", f"{item.name}: hidden details", story, item, ext, item.secret_mentions
        )
        self.report.hidden.details += 1

    def _character(self, item: _Item) -> None:
        row = item.row
        traits = [t for t in row.get("character_traits") or [] if isinstance(t, dict)]
        traits = self._fold(item, "trait", traits)
        personality_hidden = row.get("is_personality_visible") is not None and not _on(
            row.get("is_personality_visible")
        )
        sections: dict[int, list[str]] = {}
        other: list[dict[str, Any]] = []
        for t in traits:
            section = _int_id(t.get("section_id"))
            private = _on(t.get("is_private"))
            if not item.hidden and (private or (section == 2 and personality_hidden)):
                entry = self._text(item, t.get("entry"), item.secret_mentions, shown=False)
                heading = {1: "Appearance", 2: "Personality"}.get(section or 0, "Traits")
                self._hide(item, heading, f"{str(t.get('name') or '').strip()}: {entry}".strip())
                if private:
                    self.report.hidden.traits += 1
                else:
                    self.report.hidden.personality += 1
                continue
            line = f"{str(t.get('name') or '').strip()}: {self._text(item, t.get('entry'))}".strip()
            if section in (1, 2):
                sections.setdefault(section, []).append(line)
            else:
                other.append({"name": t.get("name"), "entry": t.get("entry"), "section_id": t.get("section_id")})
        physicality = "\n".join(sections.get(1, []))
        if _on(row.get("is_dead")):
            physicality = f"[Deceased] {physicality}".rstrip()
        if physicality:
            item.fields["physicality"] = physicality
        if sections.get(2):
            item.fields["mentality"] = "\n".join(sections[2])
        if other:
            self._keep(item, "traits", other, "a trait section other than appearance (1) and personality (2)")
        races = self._list(item, "character_races", "race_id")
        if _int_id(row.get("race_id")) is not None:
            races.append(row["race_id"])
        self._link_rows(item, "species", "races", races, "character_races")
        families = self._list(item, "character_families", "family_id")
        self._link_rows(item, "family", "families", families, "character_families")
        orgs = self._list(item, "organisation_memberships", "organisation_id")
        self._link_rows(item, "institutions", "organisations", orgs, "organisation_memberships")

    def _list(self, item: _Item, key: str, id_key: str) -> list[Any]:
        """The ids a row's list names (``[{"race_id": 3}, ...]`` or ``[3, ...]``); the list kept when it says more."""
        row = item.row
        ids: list[Any] = []
        more = False
        for x in row.get(key) or []:
            if isinstance(x, dict):
                if _on(x.get("is_private")) and not item.hidden:
                    item.secret_ext.setdefault(f"{EXT_PREFIX}{_norm(key)}", []).append(x)
                    self.report.hidden.links += 1
                    continue
                ids.append(x.get(id_key))
                if any(not _empty(v) and k not in (id_key, "id", "is_private", *_NOT_CONTENT) for k, v in x.items()):
                    more = True
            else:
                ids.append(x)
        if more:
            shown = [
                x for x in row.get(key) or [] if item.hidden or not (isinstance(x, dict) and _on(x.get("is_private")))
            ]
            self._keep(item, key, shown, "an item carries more than the id it links")
        return ids

    def _link_rows(self, item: _Item, fname: str, folder: str, raw_ids: list[Any], where: str) -> None:
        """Module row ids of ``folder`` onto the multi-link ``fname``."""
        eids: list[str] = []
        for raw in raw_ids:
            rid = _int_id(raw)
            target = self.by_row.get((folder, rid)) if rid is not None else None
            if target is None:
                self.report.unresolved.append(Unresolved(item.name, where, str(raw), f"no {folder} row with that id"))
            elif target.eid not in eids:
                eids.append(target.eid)
        if eids:
            links = item.fields.setdefault(fname, [])
            links += [e for e in eids if e not in links]

    def _places(self, item: _Item) -> None:
        raw = [x.get("location_id") if isinstance(x, dict) else x for x in item.ent.get("entityLocations") or []]
        if _int_id(item.row.get("location_id")) is not None:
            raw.append(item.row["location_id"])
        eids: list[str] = []
        for r in raw:
            rid = _int_id(r)
            target = self.by_row.get(("locations", rid)) if rid is not None else None
            if target is None:
                self.report.unresolved.append(Unresolved(item.name, "entityLocations", str(r), "no locations row"))
            elif target.eid not in eids:
                eids.append(target.eid)
        if not eids:
            return
        kinds = FIELD_KINDS[item.etype]
        if kinds.get("location") == "single_link" and LINK_TARGETS[item.etype].get("location") == "location":
            item.fields["location"] = eids[0]
            if len(eids) > 1:
                self._keep(item, "locations", eids, "location links one; every place kept")
        elif kinds.get("locations") == "multi_link" and LINK_TARGETS[item.etype].get("locations") == "location":
            item.fields["locations"] = eids
        else:
            self._keep(item, "locations", eids, f"{item.etype} has no location field")

    def _attributes(self, item: _Item) -> None:
        attrs = [a for a in item.ent.get("entityAttributes") or [] if isinstance(a, dict)]
        all_private = _on(item.ent.get("is_attributes_private"))
        for a in self._fold(item, "attribute", attrs):
            if not item.hidden and (all_private or _on(a.get("is_private")) or _on(a.get("is_hidden"))):
                raw = a.get("value")
                if _empty(raw) or not str(a.get("name") or "").strip():
                    continue  # a name with no value (a section heading) carries nothing
                value = self._text(item, str(raw), item.secret_mentions, shown=False) if isinstance(raw, str) else raw
                self._hide(item, "Attributes", f"{str(a.get('name')).strip()}: {value}")
                self.report.hidden.attributes += 1
                continue
            self._attribute(item, a)

    def _attribute(self, item: _Item, a: dict[str, Any]) -> None:
        key = str(a.get("name") or "").strip()
        raw = a.get("value")
        if _empty(raw) or not key:
            return  # a name with no value (a section heading) carries nothing
        before = list(item.mentions)
        text = self._text(item, str(raw)) if isinstance(raw, str) else raw
        fname = _FIELD_BY_LOWER[item.etype].get(_norm(key))
        if fname is None:
            why = f"{item.etype} has no field {_norm(key)!r}"
        elif fname in ("name", "supertype", "subtype") or fname in item.fields:
            why = f"{fname} is already set"
        else:
            kind = FIELD_KINDS[item.etype][fname]
            if kind == "text":
                item.fields[fname] = str(text)
                return
            if kind == "integer":
                if isinstance(raw, int) or (isinstance(raw, str) and _INT.fullmatch(raw)):
                    item.fields[fname] = int(raw)
                    return
                why = f"the value is not a whole number ({fname} is an integer)"
            else:
                target_type = LINK_TARGETS[item.etype][fname]
                ids = [int(m["id"]) for m in _MENTION.finditer(str(raw))]
                rest = _MENTION.sub("", str(raw)).strip(" ,;\n")
                hits = [self.by_entity.get(i) for i in ids]
                if not ids or rest:
                    why = f"{fname} links a {target_type}; the value is not a list of mentions"
                elif any(h is None or h.etype != target_type for h in hits):
                    why = f"{fname} links a {target_type}; a mention is not one in the folder"
                elif kind == "single_link" and len(set(ids)) > 1:
                    why = f"{fname} links one; the value names {len(set(ids))}"
                else:
                    eids = list(dict.fromkeys(h.eid for h in hits if h is not None))
                    item.fields[fname] = eids[0] if kind == "single_link" else eids
                    item.mentions[:] = before
                    return
        self._keep(item, key, text, why)

    def _generic(self, item: _Item) -> None:
        """Every key of the row and the entity not read above, kept as ``x_kanka_<key>``."""
        for where, data, handled in (("row", item.row, _ROW_HANDLED), ("entity", item.ent, _ENTITY_HANDLED)):
            for key, value in data.items():
                if key in handled or key in _NOT_KEPT_KEYS or _empty(value):
                    continue
                if key in _KEPT_WHEN_TRUE and not _on(value):
                    continue
                self._keep(item, key, value, f"no field for the {where}'s {key}")

    # -- links that need every element ---------------------------------------

    def _memberships(self) -> None:
        for org in self.items:
            if org.folder != "organisations":
                continue
            for m in org.row.get("members") or []:
                cid = _int_id(m.get("character_id")) if isinstance(m, dict) else _int_id(m)
                if isinstance(m, dict) and _on(m.get("is_private")) and not org.hidden:
                    org.secret_ext.setdefault(f"{EXT_PREFIX}members", []).append(m)
                    self.report.hidden.links += 1
                    continue
                member = self.by_row.get(("characters", cid)) if cid is not None else None
                if member is None:
                    self.report.unresolved.append(Unresolved(org.name, "members", str(cid), "no characters row"))
                    continue
                links = member.fields.setdefault("institutions", [])
                if org.eid not in links:
                    links.append(org.eid)
            members = [
                m
                for m in org.row.get("members") or []
                if org.hidden or not (isinstance(m, dict) and _on(m.get("is_private")))
            ]
            if any(
                isinstance(m, dict)
                and any(
                    not _empty(v)
                    for k, v in m.items()
                    if k not in ("id", "character_id", "organisation_id", "is_private", *_NOT_CONTENT)
                )
                for m in members
            ):
                self._keep(org, "members", members, "a member carries more than the character it links (a role)")

    def _relationships(self) -> None:
        rows: dict[int, tuple[_Item, dict[str, Any]]] = {}
        for item in self.items:
            for rel in item.ent.get("relationships") or []:
                rid = _int_id(rel.get("id")) if isinstance(rel, dict) else None
                if rid is None or not isinstance(rel, dict):
                    continue
                rows[rid] = (item, rel)
        units: list[tuple[int, _Item, dict[str, Any], dict[str, Any] | None]] = []
        used: set[int] = set()
        for rid in sorted(rows):
            if rid in used:
                continue
            item, rel = rows[rid]
            mid = _int_id(rel.get("mirror_id"))
            pair = rows.get(mid) if mid is not None else None
            if mid is not None and pair is not None and _int_id(pair[1].get("mirror_id")) == rid and mid not in used:
                used |= {rid, mid}
                units.append((rid, item, rel, pair[1]))
            else:
                used.add(rid)
                if mid is not None and mid not in rows:
                    self.report.notes.append(
                        f"relationship {rel.get('relation')!r} on {item.name!r}: its mirror {mid} is not in the export;"
                        " kept one-way"
                    )
                units.append((rid, item, rel, None))
        # fold exact copies: the same owner, target, text and every other field, on both sides
        seen: dict[str, int] = {}
        kept: list[tuple[int, _Item, dict[str, Any], dict[str, Any] | None]] = []
        copies: list[int] = []
        for unit in units:
            _, item, rel, mirror = unit
            key = _content(rel) + "|" + (_content(mirror) if mirror is not None else "")
            if key in seen:
                copies[seen[key]] += 1
                continue
            seen[key] = len(kept)
            kept.append(unit)
            copies.append(1)
        for (_, item, rel, _m), n in zip(kept, copies, strict=True):
            if n > 1:
                self.report.folded.append(Folded(item.name, "relationship", str(rel.get("relation") or ""), n))
        for rid, item, rel, mirror in kept:
            self._relation(rid, item, rel, mirror)

    def _relation(self, rid: int, owner: _Item, rel: dict[str, Any], mirror: dict[str, Any] | None) -> None:
        text = str(rel.get("relation") or "").strip()
        tid = _int_id(rel.get("target_id"))
        target = self.by_entity.get(tid) if tid is not None else None
        if target is None:
            self.report.unresolved.append(
                Unresolved(owner.name, f"relationship {text!r}", str(rel.get("target_id")), self._why_missing(tid))
            )
            return
        name = text or "Relationship"
        if not text:
            self.report.notes.append(
                f"a relationship from {owner.name!r} to {target.name!r} has no text; named {name!r}"
            )
        fields: dict[str, Any] = {}
        if owner.etype == "character":
            fields["actor"] = owner.eid
        for end in (owner, target) if owner.etype != "character" else (target,):
            fname = _RELATION_FIELD_FOR.get(end.etype)
            if fname is None:
                self.report.notes.append(
                    f"Relation {name!r} from {owner.name!r}: Relation has no field for a {end.etype};"
                    f" {end.name!r} is in x_kanka_source/target only"
                )
                continue
            links = fields.setdefault(fname, [])
            if end.eid not in links:
                links.append(end.eid)
        body: dict[str, Any] = {"type": "relation", "id": self._id("relation", str(rid)), "name": name}
        sides = (rel, mirror) if mirror is not None else (rel,)
        if owner.hidden or target.hidden or any(not _public(s.get("visibility_id")) for s in sides):
            body["hidden"] = True
            self.report.hidden.relationships += 1
        for fname in FIELD_KINDS["relation"]:
            if fname in fields:
                body[fname] = fields[fname]
        body[f"{EXT_PREFIX}id"] = rid
        body[f"{EXT_PREFIX}source"] = owner.eid
        body[f"{EXT_PREFIX}target"] = target.eid
        if mirror is not None:
            body[f"{EXT_PREFIX}two_way"] = True
            mine = {k: v for k, v in rel.items() if k not in _NOT_CONTENT and k not in ("owner_id", "target_id")}
            theirs = {k: v for k, v in mirror.items() if k not in _NOT_CONTENT and k not in ("owner_id", "target_id")}
            differs = {k: theirs[k] for k in sorted(theirs) if mine.get(k) != theirs[k]}
            if differs:
                body[f"{EXT_PREFIX}mirror"] = differs
        if rel.get("attitude") is not None:
            body[f"{EXT_PREFIX}attitude"] = rel["attitude"]
        if not _empty(rel.get("colour")):
            body[f"{EXT_PREFIX}colour"] = rel["colour"]
        if not _public(rel.get("visibility_id")):
            body[f"{EXT_PREFIX}visibility_id"] = rel["visibility_id"]
        self.relations.append(body)
        self.report.relations[name] = self.report.relations.get(name, 0) + 1

    # -- the bodies ----------------------------------------------------------

    def bodies(self) -> dict[str, list[dict[str, Any]]]:
        out: dict[str, list[dict[str, Any]]] = {}
        for item in self.items:
            body: dict[str, Any] = {"type": item.etype, "id": item.eid, "name": item.name}
            if item.hidden:
                body["hidden"] = True
            for fname in FIELD_KINDS[item.etype]:
                if fname in item.fields and fname != "name":
                    body[fname] = item.fields[fname]
            body.update(item.ext)
            if item.mentions:
                body[f"{EXT_PREFIX}mentions"] = item.mentions
            out.setdefault(item.etype, []).append(body)
        for body in self.narratives + self.relations:
            out.setdefault(body["type"], []).append(body)
        self.report.counts = {t: len(b) for t, b in sorted(out.items())}
        if self.items:
            self.report.notes.append(f"not kept: {_NOT_KEPT}")
        return out

    def world(self) -> dict[str, Any]:
        cid = self.campaign.get("id")
        name = str(self.campaign.get("name") or "").strip() or f"Kanka campaign {cid}"
        world: dict[str, Any] = {"id": _uuid(f"kanka:{cid}"), "name": name}
        if not _empty(self.campaign.get("entry")):
            world["description"] = html_to_markdown(str(self.campaign["entry"]))
        world["format_version"] = FORMAT_VERSION
        world["producer"] = {"tool": "onlyworlds", "version": __version__, "input": PRODUCER_INPUT}
        return world


def import_kanka(
    source: str | os.PathLike[str],
    out_dir: str | os.PathLike[str] | None,
    *,
    plan_only: bool = False,
) -> ImportReport:
    """Read the Kanka JSON export at ``source`` (the zip, or the directory it was unzipped into)
    into a world folder at ``out_dir``, which must not exist or be empty.

    With ``plan_only`` nothing is written (``out_dir`` may be None) and the report says what would
    be. What Kanka hides is imported carrying ``hidden: true`` and counted in the report.
    Raises ``FileExistsError`` for an ``out_dir`` that is not empty, ``FileNotFoundError`` for a
    missing source, ``ValueError`` for a file that is not a zip or an export with no
    ``campaign.json``.
    """
    src = Path(source)
    out = Path(out_dir) if out_dir is not None else None
    if not plan_only:
        if out is None:
            raise ValueError("give an out_dir, or plan_only=True")
        if out.exists() and (not out.is_dir() or any(out.iterdir())):
            raise FileExistsError(f"{out} exists and is not an empty directory; a folder is written whole, once")
    with ExitStack() as stack:
        tree = _open_tree(src, stack)
        imp = _Importer(tree.files, src, tree.notes)
        imp.collect()
        imp.fill()
        elements = imp.bodies()
        report = imp.report
        report.world = imp.world()
    if plan_only:
        return report
    assert out is not None
    write_folder(out, report.world, elements)
    report.out = out
    return report


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="python -m onlyworlds.kanka", description=(__doc__ or "").splitlines()[0])
    ap.add_argument("source", type=Path, help="Kanka's JSON export: the zip, or the directory it unzips to")
    ap.add_argument("out", type=Path, nargs="?", help="the world folder to create; must not exist or be empty")
    ap.add_argument("--plan", action="store_true", help="print what would become what and write nothing")
    args = ap.parse_args(argv)
    if args.out is None and not args.plan:
        print("give OUT-DIR, or --plan", file=sys.stderr)
        return 2
    try:
        report = import_kanka(args.source, args.out, plan_only=args.plan)
    except (FileExistsError, FileNotFoundError, ValueError) as exc:
        print(f"{exc}", file=sys.stderr)
        return 2
    sys.stdout.write(report.render())
    return 0


if __name__ == "__main__":
    sys.exit(main())

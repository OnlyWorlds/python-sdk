"""Read a World Anvil world export into a world folder: no AI, no account, the same folder every time.

    python -m onlyworlds.worldanvil --file EXPORT.html OUT-DIR [--plan]

or ``import_worldanvil(source, out_dir, plan_only=False)``. ``source`` is the page World Anvil's
"Export World" gives (world settings, Export World, Export this World): it is not a data file but
one print-style HTML page, ``/world/<slug>/export``, saved from the browser. ``--plan`` prints what
would become what and writes nothing. OUT-DIR must not exist yet (or be empty): a folder is
written whole, once, through ``write_folder``.

**Proven on two real exports** of one small world (2026-10-23, a maintainer's world on a free account,
both copies scrubbed of the page's scripts, forms and the account's handle by a script;
``tests/fixtures/worldanvil/``): the world's title (``h1.world-title``), a World Codex
(``#world-toc``) of ``#article-<uuid>`` anchors grouped under a category's ``<h5>`` (the rest under
``<h4>Uncategorized Articles</h4>``), then one ``div.article-print-container`` per article, its
``id`` ``article-<uuid>``: an ``h1`` with the template's icon, the body in
``.article-content-left``, the template's filled fields in ``.article-content-right`` as
``.section-title`` / ``.section-payload`` pairs, and a Metadata tab (rows of ``.metadata-label``
and ``.metadata-value``: Article template, World, Author, the dates, Visibility, Category, the
counters) with a Work In Progress badge; then an empty Timelines section. A link to another
article is ``a.article-explorer-link`` carrying ``data-article-id``, ``data-template-type`` and
``data-article-privacy``, followed by an editor anchor (``a.world-editor-link``); a mention World
Anvil did not resolve is plain text with an at sign (``@Ada``). The world's own uuid is in each
article's "copy world block" button (``[worldblock:<uuid>]``).

**Believed**, not yet seen in a file: every template but Character, Species, Geographic
Location and Organization (``TEMPLATE_TYPES`` marks which; a template field holding links and
an uploaded portrait were read on a real World Anvil page, 2026-10-26); a filled cover image;
more than one category, or one inside another; an article that is not public; a Secret or a
subscriber block (paid features); timelines.

What becomes what:

- **An article becomes an element** of its template's type (``TEMPLATE_TYPES``, keyed on the
  template as the Metadata tab names it, ``Character``, or as a link's ``data-template-type``
  names it, ``person``; the schema owner's table, ruled 2026-10-23). A template not in
  the table, or an article with none, becomes a Narrative with supertype ``Article`` (what it is,
  never where it came from) and the template's name as World Anvil spells it as subtype; the
  report names each such template and its count. The ``h1`` is the name (the Codex's name when
  the ``h1`` is empty); the template's name is kept as ``x_worldanvil_template``, a link's slug
  for it as ``x_worldanvil_template_type``, and the article's uuid as ``x_worldanvil_id``.
- **Text**: the body, HTML to Markdown (the Kanka door's converter), is the ``description``. A
  link to another article becomes its text, and its target joins ``x_worldanvil_mentions``
  (element ids, in order, once each), as a Kanka mention does; the editor anchor after it is
  page chrome and is left out. A link to an article not in the export stays as its text, its
  target kept in ``x_worldanvil_unresolved`` (``{article, text, template_type, privacy, href}``)
  and named in the report. A mention World Anvil did not resolve (``@Name``) stays as written and
  is named in the report.
- **Template fields**: one whose heading, lowercased with spaces as underscores, is a field of
  the type fills it when the value fits (text; a whole number for an integer; only links to
  articles of the linked type, for a link); every other is kept as ``x_worldanvil_<heading>``
  and named in the report. A Narrative made from an unknown template keeps every field as an
  extension (the LegendKeeper door's rule for an untyped resource). An empty field (World Anvil
  prints it and hides it) carries nothing and is counted.
- **The category** (the Metadata tab's Category, and the Codex's heading) is kept as
  ``x_worldanvil_category``; a category inside another keeps its path as
  ``x_worldanvil_category_path``. No element is made for it: the export holds only its name.
- **The Metadata tab**: Visibility is read for the hidden mark below and kept as
  ``x_worldanvil_visibility`` when it is not Public; the Work In Progress badge as
  ``x_worldanvil_work_in_progress: true``; World is checked against the world's name. A row this
  door does not know is kept as ``x_worldanvil_<label>`` and named in the report. The three dates
  are kept under the owner's three names (``DATE_KEYS``: ``x_worldanvil_created``,
  ``_updated``, ``_published``) as ISO 8601 (``23 Oct, 2026`` is ``2026-10-23``);
  a date not parsed exactly is kept as printed and named in the report, never guessed. The Author
  is one platform username for the whole export, not a fact about an element: named in the
  report, never on an element (ruled 2026-10-23). The counters (Views, Favorites,
  Comments) are not kept, and the report says so.
- **A picture**: an uploaded portrait (an ``img`` whose class ends ``-article-portrait``, as the
  Character template prints it) becomes ``image_url``, and a cover image of the article's own when
  there is no portrait; the other is kept as ``x_worldanvil_cover`` or ``x_worldanvil_portrait``.
  World Anvil's inherited default cover (``img-inherited``) is counted and not kept.
- **Nothing read past in silence**: text anywhere in an article outside the parts above and the
  page's chrome is kept as ``x_worldanvil_unread``, a picture as ``x_worldanvil_unread_images``
  (its addresses), each named in the report; text on the page
  outside the articles (a filled Timelines section) is named in the report.

**What the source hides, the folder hides: never dropped, never public** (ruled
2026-10-23; folder format §4.8). An article is written whole carrying ``hidden: true`` at the top
of its body, and the report names it with why, when any place that gives its privacy says other
than public (a link's ``data-article-privacy``, the Metadata tab's Visibility), or when one place
gives none while another gives one (a link with no ``data-article-privacy`` to an article
another link marks). A block in an article whose class names a secret or a subscriber group
becomes its own hidden Narrative, ``<article>: Secret`` (numbered when an article has more than
one), linked to the article's element (Narrative's field for its type) and
``x_worldanvil_parent``; inside a hidden article it stays in place. A visible text that mentions a
hidden article is named in the report. **Unwalked on a real file**: neither export holds an
article that is not public, nor a Secret (a paid feature); the paths are tested on planted copies,
and the Secret's markup is a guess.

**Exact duplicates fold into one**: an article printed twice whole, or a template field given
twice with one value, is kept once and the report names the fold. A second copy that differs is
named in the report; the first is kept.

**Ids are UUIDv5** in ``WORLDANVIL_NAMESPACE`` of ``worldanvil:<world uuid>:<article uuid>`` for an
article and ``worldanvil:<world uuid>:secret:<article uuid>:<n>`` for its n-th Secret block, so
the same export twice gives byte-equal folders and a later export of the same world finds the
same elements. ``world.json``: ``id`` UUIDv5 of ``worldanvil:<world uuid>``, ``name`` the world's
title, ``description`` its subheading when it has one, ``producer`` ``{"tool": "onlyworlds",
"version": ..., "input": "worldanvil-export"}`` (``PRODUCER_INPUT``, on the folder spec's list,
§4.2), ``format_version`` this package's. An export with no world block is keyed on the world's
address (``/w/<slug>``), and the report says so.

From the command line: exit 0 written (or planned), 2 on bad arguments (no ``--file``, a missing
file, an OUT-DIR that is not empty, a file that is not a World Anvil export).
"""

from __future__ import annotations

import argparse
import datetime
import io
import itertools
import os
import re
import sys
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ._schema import FIELD_KINDS, LINK_TARGETS
from ._version import __version__
from .folder import FORMAT_VERSION, write_folder
from .kanka import _blocks, _clean, _inline, _Node, _norm, _Tree

__all__ = [
    "DATE_KEYS",
    "EXT_PREFIX",
    "PRODUCER_INPUT",
    "PROVEN_TEMPLATES",
    "TEMPLATE_TYPES",
    "WORLDANVIL_NAMESPACE",
    "Folded",
    "HiddenArticle",
    "ImportReport",
    "TemplatePlan",
    "Unplaced",
    "Unresolved",
    "import_worldanvil",
    "main",
]

#: The ``producer.input`` word for this door (folder spec §4.2's list).
PRODUCER_INPUT = "worldanvil-export"

#: The namespace every id this door mints is UUIDv5 in. Fixed for good: changing it would give
#: every element of every re-imported world a new id.
WORLDANVIL_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "https://onlyworlds.com/ns/worldanvil")

#: Every extension key this door writes starts with this.
EXT_PREFIX = "x_worldanvil_"

#: The supertype of a Narrative made from an article whose template has no OnlyWorlds type: what
#: the thing is, never where it came from (the producer line says that; ruled 2026-10-23).
UNTYPED_SUPERTYPE = "Article"

#: The most an export may hold, in bytes: a file past it is refused, not read.
MAX_EXPORT_BYTES = 256 * 1024 * 1024

#: World Anvil's article template -> element type: the one table, as the schema owner ruled it
#: against the definitions page (2026-10-23: every row below holds, the last four
#: added on that reading; anything else stays unknown). Keyed lowercased on the template as the
#: Metadata tab names it (``Geographic Location``) or as a link's ``data-template-type`` names it
#: (``person``). The keys in ``PROVEN_TEMPLATES`` were read on a real export; the rest are believed.
TEMPLATE_TYPES: dict[str, str] = {
    "character": "character",
    "person": "character",
    "species": "species",
    "geographic location": "location",
    "location": "location",
    "settlement": "location",
    "building / landmark": "location",
    "landmark": "location",
    "organization": "institution",
    "item": "object",
    "language": "language",
    "law": "law",
    "spell": "ability",
    "military conflict": "event",
    "conflict": "event",
    "rank / title": "title",
    "rank": "title",
    "ethnicity": "species",
    "myth / legend": "narrative",
    "vehicle": "object",
    "profession": "title",
}
PROVEN_TEMPLATES = frozenset({"character", "person", "species", "geographic location", "organization"})

#: The door's own extension keys; a template field never takes one of them.
_OWN = (
    "id",
    "template",
    "template_type",
    "category",
    "category_path",
    "mentions",
    "unresolved",
    "visibility",
    "article_privacy",
    "work_in_progress",
    "parent",
    "unread",
    "unread_images",
)

#: The Metadata tab's dates, kept on the element under the owner's three names (ruled
#: 2026-10-23: ``created``, ``updated``, ``published``, "or the template's own words"), as ISO 8601.
DATE_KEYS: dict[str, str] = {
    "creation date": f"{EXT_PREFIX}created",
    "last update date": f"{EXT_PREFIX}updated",
    "publication date": f"{EXT_PREFIX}published",
}
_RESERVED = frozenset(f"{EXT_PREFIX}{k}" for k in _OWN) | frozenset(DATE_KEYS.values())

#: A date as the Metadata tab prints it: ``23 Oct, 2026``. Any other shape is kept as printed.
_PRINTED_DATE = re.compile(r"(?P<day>\d{1,2}) (?P<month>[A-Za-z]+),? (?P<year>\d{4})")
_MONTHS = {
    m: i
    for i, names in enumerate(
        (
            ("jan", "january"),
            ("feb", "february"),
            ("mar", "march"),
            ("apr", "april"),
            ("may",),
            ("jun", "june"),
            ("jul", "july"),
            ("aug", "august"),
            ("sep", "september"),
            ("oct", "october"),
            ("nov", "november"),
            ("dec", "december"),
        ),
        1,
    )
    for m in names
}

#: Metadata rows not kept (one report line; the author's name is in the report); the rest are read or kept.
_META_NOT_KEPT = frozenset({"author", "views", "favorites", "comments"})
_NOT_KEPT = (
    "the page's chrome and layout (the title icons, World Anvil's inherited cover image, share, report and"
    " block-link buttons, the comment form, navigation, the Codex's layout ids), who wrote an article (Author,"
    " the world's 'Created by' line: named above, never on an element), the counters"
    " (Views, Favorites, Comments), a link's page address, tooltip and editor anchor once its target is kept by"
    " id, and the template fields' visibility-toggle ids (a hash each; what they toggle is not in the file)"
)

#: Classes of page chrome: never read, never kept.
_CHROME = frozenset(
    {
        "article-footer",
        "article-social-media",
        "backtoworld",
        "article-horizontal-navigation",
        "extendedbody-tabs",
        "comment-form",
        "goToToC",
    }
)
_SKIP_TAGS = frozenset({"style", "script", "head", "noscript", "template"})

_ARTICLE_ID = re.compile(r"^article-(?P<id>[0-9a-fA-F-]{8,})$")
_CODEX_HREF = re.compile(r"^\s*#article-(?P<id>[0-9a-fA-F-]{8,})\s*$")
_WORLD_BLOCK = re.compile(r"\[worldblock:(?P<id>[0-9a-fA-F-]{8,})\]")
_WORLD_PATH = re.compile(r"^\s*/w/(?P<slug>[^/\s]+)")
_TOKEN = re.compile(r"\x00(?P<n>\d+)\x00")
_AT_MENTION = re.compile(r"(?<![\w@])@[^\s.,;:!?()\[\]]+(?: [A-Z][^\s.,;:!?()\[\]]*)*")
_INT = re.compile(r"\s*-?\d+\s*")
_SECRET_CLASS = re.compile(r"secret|subscriber", re.IGNORECASE)

#: type -> {lowercased field name: field name}, so a heading ``str`` finds ``STR``.
_FIELD_BY_LOWER: dict[str, dict[str, str]] = {t: {f.lower(): f for f in kinds} for t, kinds in FIELD_KINDS.items()}

#: type -> {a template field's heading, normalised: the field it names}, where World Anvil's word
#: differs from the schema's (``Current Location`` is Character's ``location``, its present place).
_LABEL_FIELDS: dict[str, dict[str, str]] = {"character": {"current_location": "location"}}

#: An uploaded portrait's class (``character-article-portrait``).
_PORTRAIT = re.compile(r"(^|\s)[\w-]*-article-portrait(\s|$)")

#: target type -> Narrative's multi-link field for it: how a Secret's Narrative links its article.
_NARRATIVE_FIELD_FOR: dict[str, str] = {}
for _f, _kind in FIELD_KINDS["narrative"].items():
    if _kind == "multi_link":
        _NARRATIVE_FIELD_FOR.setdefault(LINK_TARGETS["narrative"][_f], _f)


def _uuid(key: str) -> str:
    return str(uuid.uuid5(WORLDANVIL_NAMESPACE, key))


def _classes(node: _Node) -> set[str]:
    return set(node.attrs.get("class", "").split())


def _walk(node: _Node) -> Iterator[_Node]:
    """Every node below ``node`` (not itself), in document order."""
    for c in node.children:
        if isinstance(c, _Node):
            yield c
            yield from _walk(c)


def _find(node: _Node, pred: Callable[[_Node], bool]) -> _Node | None:
    return next((n for n in _walk(node) if pred(n)), None)


def _has(cls: str) -> Callable[[_Node], bool]:
    return lambda n: cls in _classes(n)


def _plain(node: _Node | str, skip: frozenset[int] = frozenset()) -> str:
    """A node's text, whitespace runs as one space, styles and scripts left out."""
    out: list[str] = []

    def go(n: _Node | str) -> None:
        if isinstance(n, str):
            out.append(n)
        elif n.tag not in _SKIP_TAGS and id(n) not in skip:
            for c in n.children:
                go(c)

    go(node)
    return re.sub(r"\s+", " ", "".join(out)).strip()


def _markdown(node: _Node) -> str:
    """A container's children as Markdown (the Kanka door's converter), styles and scripts left out."""
    _strip(node)
    return "\n\n".join(_blocks(node)).strip()


def _strip(node: _Node) -> None:
    node.children = [c for c in node.children if not (isinstance(c, _Node) and c.tag in _SKIP_TAGS)]
    for c in node.children:
        if isinstance(c, _Node):
            _strip(c)


def _public(value: str) -> bool:
    return value.strip().casefold() == "public"


def _iso_date(printed: str) -> str | None:
    """``23 Oct, 2026`` as ``2026-10-23``; None for anything not exactly a day, a month and a year."""
    m = _PRINTED_DATE.fullmatch(printed.strip())
    month = _MONTHS.get(m["month"].casefold()) if m is not None else None
    if m is None or month is None:
        return None
    try:
        return datetime.date(int(m["year"]), month, int(m["day"])).isoformat()
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# The report
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TemplatePlan:
    """One article template and what its articles became."""

    #: the template as the Metadata tab names it ('' when an article names none)
    template: str
    type: str
    articles: int
    #: ``proven`` (read on a real export), ``believed`` or ``untyped``
    status: str


@dataclass(frozen=True)
class Unplaced:
    """A template field or metadata row not placed on a field, kept as ``kept_as``."""

    element: str
    key: str
    why: str
    kept_as: str


@dataclass(frozen=True)
class Unresolved:
    """A link whose target is not an element of the folder."""

    element: str
    #: ``link '<text>'``
    where: str
    #: the World Anvil article id the link names
    target: str
    why: str


@dataclass(frozen=True)
class Folded:
    """Exact copies folded into one."""

    element: str
    #: ``article`` or ``template field``
    what: str
    name: str
    copies: int


@dataclass(frozen=True)
class HiddenArticle:
    """An article written with ``hidden: true``, and why."""

    name: str
    article: str
    why: str


@dataclass
class ImportReport:
    source: Path
    world: dict[str, Any]
    counts: dict[str, int] = field(default_factory=dict)
    templates: list[TemplatePlan] = field(default_factory=list)
    unplaced: list[Unplaced] = field(default_factory=list)
    unresolved: list[Unresolved] = field(default_factory=list)
    #: (element name, the text as written): mentions World Anvil did not resolve, kept as written
    at_mentions: list[tuple[str, str]] = field(default_factory=list)
    #: (article id, the Codex's name for it): listed in the World Codex, no article in the export
    codex_only: list[tuple[str, str]] = field(default_factory=list)
    folded: list[Folded] = field(default_factory=list)
    #: (element, the template field, the element it names): a link field World Anvil gave as a
    #: name typed as text, placed on the one element of the field's type with that name
    by_name: list[tuple[str, str, str]] = field(default_factory=list)
    hidden: list[HiddenArticle] = field(default_factory=list)
    #: Secret blocks in visible articles, each its own hidden Narrative
    secret_blocks: int = 0
    #: Secret blocks inside a hidden article, kept in place
    secrets_inside: int = 0
    #: the Metadata tab's Author -> articles naming it: in this report, never on an element
    authors: dict[str, int] = field(default_factory=dict)
    #: dates kept on the elements as ISO 8601
    dates: int = 0
    #: (element, label, the text as printed): a date not parsed exactly, kept as printed
    dates_unparsed: list[tuple[str, str, str]] = field(default_factory=list)
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
        lines.append(f"World Anvil export {self.source} ({name!r}): {self.total} elements ({by_type or 'none'}).")
        if self.templates:
            lines.append("What became what:")
            for t in self.templates:
                how = {
                    "proven": "read on a real export",
                    "believed": "believed, not yet seen in a real export",
                    "untyped": f"no OnlyWorlds type: Narratives, supertype {UNTYPED_SUPERTYPE}",
                }[t.status]
                label = repr(t.template) if t.template else "no template named"
                lines.append(f"  - template {label} ({t.articles}): {t.type}; {how}")
        if self.folded:
            lines.append(f"Exact duplicates folded into one ({len(self.folded)}):")
            lines += [f"  - {f.element!r}: {f.copies} identical {f.what}s {f.name!r}, kept once" for f in self.folded]
        said = [f"{h.name!r} ({h.why})" for h in self.hidden]
        if self.secret_blocks:
            n = self.secret_blocks
            said.append(f"{n} Secret block{'' if n == 1 else 's'} in a visible article, each its own Narrative")
        if self.secrets_inside:
            n = self.secrets_inside
            said.append(f"{n} Secret block{'' if n == 1 else 's'} inside a hidden article, kept in place")
        if said:
            lines.append("Hidden as the source hides it (elements carrying hidden: true): " + "; ".join(said) + ".")
        if self.unplaced:
            lines.append(f"Fields not placed on an OnlyWorlds field ({len(self.unplaced)}), kept as extensions:")
            lines += [f"  - {u.element!r} / {u.key!r}: {u.why}; kept as {u.kept_as}" for u in self.unplaced]
        if self.by_name:
            lines.append(f"Links given as a name, placed on the one element with that name ({len(self.by_name)}):")
            lines += [f"  - {e!r} / {k!r}: {t!r}" for e, k, t in self.by_name]
        if self.unresolved:
            lines.append(f"Links whose target is not in the folder ({len(self.unresolved)}), kept as text:")
            lines += [f"  - {u.element!r}, {u.where}: {u.target}: {u.why}" for u in self.unresolved]
        if self.at_mentions:
            lines.append(
                f"Mentions World Anvil did not resolve, kept as written ({len(self.at_mentions)}):"
                " the text has an at sign and no link"
            )
            lines += [f"  - {e!r}: {t!r}" for e, t in self.at_mentions]
        if self.codex_only:
            lines.append(f"In the World Codex with no article in the export ({len(self.codex_only)}): not made")
            lines += [f"  - {a}: {repr(n) if n else 'no title'}" for a, n in self.codex_only]
        if self.dates or self.dates_unparsed:
            keys = ", ".join(DATE_KEYS.values())
            lines.append(f"Dates kept on the elements ({keys}): {self.dates} as ISO 8601")
            if self.dates_unparsed:
                lines.append(f"Dates not parsed exactly, kept as printed ({len(self.dates_unparsed)}):")
                lines += [f"  - {e!r} / {k!r}: {t!r}" for e, k, t in self.dates_unparsed]
        if self.authors:
            who = ", ".join(f"{a!r} ({n} article{'' if n == 1 else 's'})" for a, n in self.authors.items())
            lines.append(f"Author, named here and never on an element: {who}")
        if self.notes:
            lines.append(f"Notes ({len(self.notes)}):")
            lines += [f"  - {n}" for n in self.notes]
        lines.append(f"Wrote {self.out}." if self.out is not None else "Plan only: nothing written.")
        return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# The import
# ---------------------------------------------------------------------------


@dataclass
class _Link:
    """An ``a.article-explorer-link``, replaced in the tree by its token ``\\x00<n>\\x00``."""

    article: str
    text: str
    template_type: str | None
    #: ``data-article-privacy``; None when the link carries none
    privacy: str | None
    href: str
    #: the article the link is in
    owner: str


@dataclass
class _Item:
    """One article's element being built."""

    aid: str
    node: _Node
    name: str
    #: the template as the Metadata tab names it ('' for none)
    template: str
    eid: str
    meta: list[tuple[str, _Node, _Node]] = field(default_factory=list)
    etype: str = "narrative"
    #: the ``TEMPLATE_TYPES`` key that typed it ('' when untyped)
    by: str = ""
    #: the template slugs links to it name, in order
    slugs: list[str] = field(default_factory=list)
    #: the privacy values links to it give (None for a link with none), when any is not public
    privacy: list[str | None] = field(default_factory=list)
    fields: dict[str, Any] = field(default_factory=dict)
    ext: dict[str, Any] = field(default_factory=dict)
    taken: set[str] = field(default_factory=set)
    mentions: list[str] = field(default_factory=list)
    unresolved: list[dict[str, Any]] = field(default_factory=list)
    hidden: bool = False
    #: nodes read (by ``id``): the guard reads the rest
    consumed: set[int] = field(default_factory=set)

    @property
    def typed(self) -> bool:
        return bool(self.by)


class _Importer:
    def __init__(self, html: str, source: Path) -> None:
        tree = _Tree()
        tree.feed(html)
        tree.close()
        self.root = tree.root
        self.report = ImportReport(source=source, world={})
        self.world_key = ""
        self.items: list[_Item] = []
        self.by_id: dict[str, _Item] = {}
        self.links: list[_Link] = []
        self.codex: dict[str, tuple[str, list[str]]] = {}
        self.narratives: list[dict[str, Any]] = []
        self.page_consumed: set[int] = set()
        self._unplaced_seen: set[Unplaced] = set()
        self.editor_links = 0
        self.inherited_covers = 0
        self.empty_fields: list[str] = []

    def _id(self, *parts: str) -> str:
        return _uuid(":".join(("worldanvil", self.world_key, *parts)))

    # -- pass 1: the world, the Codex, every article with its type and id ------

    def collect(self) -> None:
        containers = [n for n in _walk(self.root) if "article-print-container" in _classes(n)]
        toc = _find(self.root, lambda n: n.attrs.get("id") == "world-toc")
        if not containers and toc is None:
            raise ValueError(
                f"{self.report.source}: not a World Anvil export (no World Codex, no article-print-container)"
            )
        self._world_key()
        if toc is not None:
            self.page_consumed.add(id(toc))
            self._codex(toc)
        raw: dict[str, str] = {}
        copies: dict[str, int] = {}
        for node in containers:
            m = _ARTICLE_ID.match(node.attrs.get("id", ""))
            if m is None:
                self.report.notes.append("an article-print-container with no article id: its text is page text")
                continue
            self.page_consumed.add(id(node))
            aid = m["id"].lower()
            if aid in self.by_id:
                if _plain(node) == raw[aid]:
                    copies[aid] = copies.get(aid, 1) + 1
                else:
                    self.report.notes.append(
                        f"article {aid} is printed twice and the copies differ; the first is kept, the second not read"
                    )
                continue
            raw[aid] = _plain(node)
            item = self._article(aid, node)
            self.items.append(item)
            self.by_id[aid] = item
        for aid, n in copies.items():
            name = self.by_id[aid].name
            self.report.folded.append(Folded(name, "article", name, n))
        for aid, (name, _) in self.codex.items():
            if aid not in self.by_id:
                self.report.codex_only.append((aid, name))
        self._type()
        plans: dict[tuple[str, str, str], int] = {}
        for item in self.items:
            status = "proven" if item.by in PROVEN_TEMPLATES else "believed" if item.by else "untyped"
            key = (item.template, item.etype, status)
            plans[key] = plans.get(key, 0) + 1
        for (template, etype, status), n in sorted(plans.items()):
            self.report.templates.append(TemplatePlan(template, etype, n, status))
        self._privacy()

    def _world_key(self) -> None:
        for n in _walk(self.root):
            m = _WORLD_BLOCK.search(n.attrs.get("data-clipboard-text", ""))
            if m is not None:
                self.world_key = m["id"].lower()
                return
        for n in _walk(self.root):
            if n.tag == "a" and (m := _WORLD_PATH.match(n.attrs.get("href", ""))) is not None:
                self.world_key = m["slug"]
                self.report.notes.append(
                    f"no world block in the export: ids keyed on the world's address /w/{m['slug']}"
                )
                return
        raise ValueError(f"{self.report.source}: no world id in the export (no world block, no /w/ address)")

    def _codex(self, toc: _Node) -> None:
        def go(node: _Node, path: list[str]) -> None:
            heads = [c for c in node.children if isinstance(c, _Node) and c.tag == "h5"]
            if heads:
                path = [*path, _plain(heads[0])]
            for c in node.children:
                if not isinstance(c, _Node):
                    continue
                m = _CODEX_HREF.match(c.attrs.get("href", "")) if c.tag == "a" else None
                if m is not None:
                    aid = m["id"].lower()
                    if aid not in self.codex:
                        self.codex[aid] = (_plain(c), path)
                else:
                    go(c, path)

        go(toc, [])

    def _article(self, aid: str, node: _Node) -> _Item:
        consumed: set[int] = set()
        meta: list[tuple[str, _Node, _Node]] = []
        pane = _find(node, lambda n: n.attrs.get("id") == "metadata")
        if pane is not None:
            for row in _walk(pane):
                kids = [c for c in row.children if isinstance(c, _Node)]
                for label, value in itertools.pairwise(kids):
                    if "metadata-label" in _classes(label) and "metadata-value" in _classes(value):
                        meta.append((_plain(label), label, value))
        template = next((_plain(v) for k, _, v in meta if k.casefold() == "article template"), "")
        title = _find(node, _has("article-title"))
        h1 = _find(title, lambda n: n.tag == "h1") if title is not None else None
        name = ""
        if h1 is not None:
            consumed.add(id(h1))
            icons = frozenset(id(i) for i in _walk(h1) if "article-title-icon" in _classes(i))
            name = _plain(h1, icons)
        codex_name = self.codex.get(aid, ("", []))[0]
        if not name:
            name = codex_name or f"Untitled ({aid[:8]})"
            self.report.notes.append(f"article {aid} has no title; named {name!r}")
        elif codex_name and codex_name != name:
            self.report.notes.append(f"article {name!r}: the World Codex names it {codex_name!r}")
        item = _Item(aid, node, name, template, self._id(aid), meta, consumed=consumed)
        self._links(item, node)
        return item

    def _links(self, item: _Item, node: _Node) -> None:
        """Explorer links become tokens (recorded in ``self.links``); editor anchors are left out."""
        kept: list[_Node | str] = []
        for c in node.children:
            if isinstance(c, _Node) and c.tag == "a":
                classes = _classes(c)
                if "world-editor-link" in classes:
                    self.editor_links += 1
                    continue
                target = c.attrs.get("data-article-id", "").strip().lower()
                if "article-explorer-link" in classes and target:
                    text = _clean(_inline(c.children)).replace("\n", " ")
                    privacy = c.attrs.get("data-article-privacy")
                    tslug = c.attrs.get("data-template-type", "").strip() or None
                    self.links.append(_Link(target, text, tslug, privacy, c.attrs.get("href", ""), item.aid))
                    kept.append(f"\x00{len(self.links) - 1}\x00")
                    continue
            if isinstance(c, _Node):
                self._links(item, c)
            kept.append(c)
        node.children = kept

    def _type(self) -> None:
        """Each article's type: its template's name in the table, else a slug a link to it names."""
        for item in self.items:
            item.slugs = list(
                dict.fromkeys(lk.template_type for lk in self.links if lk.article == item.aid and lk.template_type)
            )
            low = item.template.casefold()
            if low in TEMPLATE_TYPES:
                item.by = low
            else:
                item.by = next((s.casefold() for s in item.slugs if s.casefold() in TEMPLATE_TYPES), "")
                if item.by:
                    self.report.notes.append(
                        f"article {item.name!r}: its template {item.template!r} is not in the table; typed"
                        f" {TEMPLATE_TYPES[item.by]} by a link's data-template-type {item.by!r}"
                    )
            item.etype = TEMPLATE_TYPES.get(item.by, "narrative")
            for s in item.slugs:
                t = TEMPLATE_TYPES.get(s.casefold())
                if t is not None and t != item.etype:
                    self.report.notes.append(
                        f"article {item.name!r}: a link names its template {s!r} ({t}); its template"
                        f" {item.template!r} made it a {item.etype}"
                    )

    def _privacy(self) -> None:
        """The hidden mark: a place that gives the article's privacy says other than public, or one
        place gives none while another gives one."""
        for item in self.items:
            links = [lk for lk in self.links if lk.article == item.aid]
            vis = next((v for k, _, v in item.meta if k.casefold() == "visibility"), None)
            places: list[tuple[str, str, str | None]] = [
                ("Visibility", "its Metadata tab", _plain(vis) if vis is not None else None)
            ]
            for lk in links:
                owner = self.by_id.get(lk.owner)
                src = repr(owner.name) if owner is not None else lk.owner
                places.append(("data-article-privacy", f"a link from {src}", lk.privacy))
            why = [f"{key} {v!r} on {where}" for key, where, v in places if v is not None and not _public(v)]
            if any(v is not None for _, _, v in places):
                why += [f"no {key} on {where}, where another place gives one" for key, where, v in places if v is None]
            if any(lk.privacy is None or not _public(lk.privacy) for lk in links):
                item.privacy = list(dict.fromkeys(lk.privacy for lk in links))
            if why:
                item.hidden = True
                self.report.hidden.append(HiddenArticle(item.name, item.aid, "; ".join(why)))

    # -- pass 2: text, fields, metadata ---------------------------------------

    def fill(self) -> None:
        for item in self.items:
            self._fill(item)
        self._page_guard()

    def _unplaced(self, item: _Item, key: str, why: str, kept_as: str) -> None:
        u = Unplaced(item.name, key, why, kept_as)
        if u not in self._unplaced_seen:
            self._unplaced_seen.add(u)
            self.report.unplaced.append(u)

    def _keep(self, item: _Item, key: str, value: Any, why: str) -> None:
        """Keep a value as ``x_worldanvil_<key>`` (``_2`` and on when taken) and report it."""
        base = f"{EXT_PREFIX}{_norm(key) or 'value'}"
        ext, n = base, 2
        while ext in item.taken:
            ext, n = f"{base}_{n}", n + 1
        item.taken.add(ext)
        item.ext[ext] = value
        self._unplaced(item, key, why, ext)

    def _resolve(self, item: _Item, md: str, into: list[str], *, shown: bool = True) -> str:
        """Tokens back to their links' text; targets into ``into``, the rest kept as unresolved."""

        def swap(m: re.Match[str]) -> str:
            lk = self.links[int(m["n"])]
            target = self.by_id.get(lk.article)
            if target is None:
                text = lk.text or lk.article
                self.report.unresolved.append(
                    Unresolved(item.name, f"link {text!r}", lk.article, "no such article in the export")
                )
                kept = {"article": lk.article, "text": lk.text, "template_type": lk.template_type}
                kept |= {"privacy": lk.privacy, "href": lk.href}
                if kept not in item.unresolved:
                    item.unresolved.append(kept)
                return text
            if target is not item and target.eid not in into:
                into.append(target.eid)
            if shown and not item.hidden and target.hidden:
                note = f"{item.name!r}: visible text mentions the hidden {target.name!r} by name"
                if note not in self.report.notes:
                    self.report.notes.append(note)
            return lk.text or target.name

        return _TOKEN.sub(swap, md)

    def _text(self, item: _Item, md: str) -> str:
        """Tokens resolved into the item's mentions; an ``@Name`` World Anvil left as text, named."""
        text = self._resolve(item, md, item.mentions)
        for m in _AT_MENTION.finditer(text):
            self.report.at_mentions.append((item.name, m[0]))
        return text

    def _fill(self, item: _Item) -> None:
        node = item.node
        item.taken |= _RESERVED
        item.ext[f"{EXT_PREFIX}id"] = item.aid
        if item.template:
            item.ext[f"{EXT_PREFIX}template"] = item.template
        if item.slugs:
            item.ext[f"{EXT_PREFIX}template_type"] = item.slugs[0] if len(item.slugs) == 1 else item.slugs
        if item.privacy:
            item.ext[f"{EXT_PREFIX}article_privacy"] = item.privacy
        if not item.typed:
            item.fields["supertype"] = UNTYPED_SUPERTYPE
            if item.template:
                item.fields["subtype"] = item.template
        self._portrait(item)
        self._cover(item)
        left = _find(node, _has("article-content-left"))
        right = _find(node, _has("article-content-right"))
        for part in (left, right):
            if part is not None:
                self._secrets(item, part)
        if left is not None:
            item.consumed.add(id(left))
            body = self._text(item, _markdown(left))
            if body:
                item.fields["description"] = body
        if right is not None:
            self._sections(item, right)
        self._metadata(item)
        self._guard(item)
        if item.unresolved:
            item.ext[f"{EXT_PREFIX}unresolved"] = item.unresolved

    def _portrait(self, item: _Item) -> None:
        """An uploaded portrait: the element's picture, before any cover."""
        for img in (n for n in _walk(item.node) if n.tag == "img" and _PORTRAIT.search(n.attrs.get("class", ""))):
            item.consumed.add(id(img))
            src = img.attrs.get("src", "")
            if src and "image_url" not in item.fields:
                item.fields["image_url"] = src
            elif src:
                self._keep(item, "portrait", src, "image_url already holds a portrait")

    def _cover(self, item: _Item) -> None:
        cover = _find(item.node, lambda n: n.attrs.get("id") == "cover")
        if cover is None:
            return
        item.consumed.add(id(cover))
        for img in (n for n in _walk(cover) if n.tag == "img"):
            src = img.attrs.get("src", "")
            if "img-inherited" in _classes(img):
                self.inherited_covers += 1
            elif src and "image_url" not in item.fields:
                item.fields["image_url"] = src
            elif src:
                self._keep(item, "cover", src, "image_url already holds the portrait or a cover")

    def _secrets(self, item: _Item, part: _Node) -> None:
        """A Secret (or subscriber) block: its own hidden Narrative, or kept in place in a hidden article."""
        found: list[_Node] = []

        def go(node: _Node) -> None:
            kept: list[_Node | str] = []
            for c in node.children:
                if isinstance(c, _Node) and _SECRET_CLASS.search(c.attrs.get("class", "")):
                    if item.hidden:
                        self.report.secrets_inside += 1
                    else:
                        found.append(c)
                        continue
                if isinstance(c, _Node):
                    go(c)
                kept.append(c)
            node.children = kept

        go(part)
        for n, block in enumerate(found, 1):
            mentions: list[str] = []
            story = self._resolve(item, _markdown(block), mentions, shown=False)
            name = f"{item.name}: Secret" + (f" {n}" if len(found) > 1 else "")
            body: dict[str, Any] = {"type": "narrative", "id": self._id("secret", item.aid, str(n)), "name": name}
            body["hidden"] = True
            if story:
                body["story"] = story
            if item.etype == "narrative":
                body["parent_narrative"] = item.eid
            elif item.etype in _NARRATIVE_FIELD_FOR:
                body[_NARRATIVE_FIELD_FOR[item.etype]] = [item.eid]
            body[f"{EXT_PREFIX}parent"] = item.eid
            if mentions:
                body[f"{EXT_PREFIX}mentions"] = mentions
            self.narratives.append(body)
            self.report.secret_blocks += 1

    def _sections(self, item: _Item, right: _Node) -> None:
        values: dict[str, list[str]] = {}
        order: list[tuple[str, str]] = []

        def go(node: _Node) -> None:
            kids = [c for c in node.children if isinstance(c, _Node)]
            for i, c in enumerate(kids):
                if "section-title" in _classes(c):
                    item.consumed.add(id(c))
                    head = _find(c, _has("section-heading"))
                    heading = _plain(head if head is not None else c)
                    nxt = kids[i + 1] if i + 1 < len(kids) else None
                    md = ""
                    if nxt is not None and _classes(nxt) & {"section-payload", "section-content"}:
                        item.consumed.add(id(nxt))
                        md = _markdown(nxt)
                    if not md.strip():
                        self.empty_fields.append(f"{item.name}: {heading}")
                        continue
                    if md in values.get(heading, []):
                        self.report.folded.append(Folded(item.name, "template field", heading, 2))
                        continue
                    values.setdefault(heading, []).append(md)
                    order.append((heading, md))
                elif c.tag not in _SKIP_TAGS:
                    go(c)

        go(right)
        for heading, md in order:
            self._field(item, heading, md)

    def _field(self, item: _Item, key: str, md: str) -> None:
        """A template field onto the field its heading names, when the value fits; else kept."""
        why = self._place(item, key, md) if item.typed else "the article's template has no type"
        if why:
            self._keep(item, key, self._text(item, md), why)

    def _place(self, item: _Item, key: str, md: str) -> str:
        """Place the value and return '', or return why it was not placed."""
        label = _norm(key)
        fname = _LABEL_FIELDS.get(item.etype, {}).get(label) or _FIELD_BY_LOWER[item.etype].get(label)
        if fname is None:
            return f"{item.etype} has no field {_norm(key)!r}"
        if fname in ("name", "supertype", "subtype", "description") or fname in item.fields:
            return f"{fname} is already set"
        kind = FIELD_KINDS[item.etype][fname]
        if kind == "text":
            item.fields[fname] = self._text(item, md)
            return ""
        if kind == "integer":
            if _INT.fullmatch(md):
                item.fields[fname] = int(md)
                return ""
            return f"the value is not a whole number ({fname} is an integer)"
        target_type = LINK_TARGETS[item.etype][fname]
        ids = [int(m["n"]) for m in _TOKEN.finditer(md)]
        rest = _TOKEN.sub("", md).strip(" ,;\n")
        hits = [self.by_id.get(self.links[i].article) for i in ids]
        if not ids and rest:
            # A name typed as text, not linked: the one element of that type with that name.
            named = [
                o
                for o in self.items
                if o is not item and o.etype == target_type and o.name.casefold() == rest.casefold()
            ]
            if len(named) != 1:
                return f"{fname} links a {target_type}; the value is text that names " + (
                    f"{len(named)} of them in the folder" if named else "none in the folder"
                )
            item.fields[fname] = named[0].eid if kind == "single_link" else [named[0].eid]
            self.report.by_name.append((item.name, key, named[0].name))
            return ""
        if not ids or rest:
            return f"{fname} links a {target_type}; the value is not a list of links"
        if any(h is None or h.etype != target_type for h in hits):
            return f"{fname} links a {target_type}; a link is not to one in the folder"
        eids = list(dict.fromkeys(h.eid for h in hits if h is not None))
        if kind == "single_link" and len(eids) > 1:
            return f"{fname} links one; the value names {len(eids)}"
        item.fields[fname] = eids[0] if kind == "single_link" else eids
        return ""

    def _metadata(self, item: _Item) -> None:
        pane = _find(item.node, lambda n: n.attrs.get("id") == "metadata")
        if pane is None:
            return
        for badge in (n for n in _walk(pane) if "badge-wip" in _classes(n)):
            item.consumed.add(id(badge))
            item.ext[f"{EXT_PREFIX}work_in_progress"] = True
        for label, lnode, vnode in item.meta:
            item.consumed |= {id(lnode), id(vnode)}
            low = label.casefold()
            value = _plain(vnode)
            if low == "author" and value:
                self.report.authors[value] = self.report.authors.get(value, 0) + 1
            if low in ("article template",) or low in _META_NOT_KEPT:
                continue
            if low in DATE_KEYS:
                if value:
                    iso = _iso_date(value)
                    item.ext[DATE_KEYS[low]] = value if iso is None else iso
                    if iso is None:
                        self.report.dates_unparsed.append((item.name, label, value))
                    else:
                        self.report.dates += 1
            elif low == "world":
                if value != self.report.world.get("name", value):
                    self.report.notes.append(f"article {item.name!r} names its world {value!r}")
            elif low == "visibility":
                if value and not _public(value):
                    item.ext[f"{EXT_PREFIX}visibility"] = value
            elif low == "category":
                if value:
                    item.ext[f"{EXT_PREFIX}category"] = value
            elif value:
                self._keep(item, label, value, "a Metadata row this door does not read")
        codex_path = self.codex.get(item.aid, ("", []))[1]
        if codex_path:
            mine = item.ext.get(f"{EXT_PREFIX}category")
            if mine is None:
                item.ext[f"{EXT_PREFIX}category"] = codex_path[-1]
            elif mine != codex_path[-1]:
                self.report.notes.append(
                    f"article {item.name!r}: its Metadata tab names the category {mine!r}, the Codex {codex_path[-1]!r}"
                )
            if len(codex_path) > 1:
                item.ext[f"{EXT_PREFIX}category_path"] = codex_path

    @staticmethod
    def _is_chrome(node: _Node) -> bool:
        if node.tag in _SKIP_TAGS or _classes(node) & _CHROME:
            return True
        # the comments section with no comment in it: its heading only
        return "extendedbody-comments" in _classes(node) and _plain(node) in ("", "Comments")

    def _leftover(self, node: _Node, consumed: set[int]) -> list[str]:
        out: list[str] = []
        for c in node.children:
            if isinstance(c, str):
                if c.strip():
                    out.append(c)
            elif id(c) not in consumed and not self._is_chrome(c):
                out += self._leftover(c, consumed)
        return out

    def _images(self, node: _Node, consumed: set[int]) -> list[str]:
        """The addresses of pictures no part above read, outside the chrome, in page order."""
        out: list[str] = []
        for c in node.children:
            if not isinstance(c, _Node) or id(c) in consumed or self._is_chrome(c):
                continue
            if c.tag == "img" and "img-inherited" not in _classes(c) and c.attrs.get("src"):
                out.append(c.attrs["src"])
            out += self._images(c, consumed)
        return out

    def _guard(self, item: _Item) -> None:
        """Text and pictures in the article that no part above read: kept, and named."""
        rest = re.sub(r"\s+", " ", " ".join(self._leftover(item.node, item.consumed))).strip()
        if rest:
            ext = f"{EXT_PREFIX}unread"
            item.ext[ext] = self._text(item, rest)
            self._unplaced(item, "unread", "text outside the parts this door reads", ext)
        images = list(dict.fromkeys(self._images(item.node, item.consumed)))
        if images:
            ext = f"{EXT_PREFIX}unread_images"
            item.ext[ext] = images
            self._unplaced(item, "unread images", "pictures outside the parts this door reads", ext)

    def _page_guard(self) -> None:
        heading = _find(self.root, _has("heading"))
        if heading is not None:
            self.page_consumed.add(id(heading))
        for n in _walk(self.root):
            if n.tag == "h1" and "big-title" in _classes(n) and _plain(n) in ("Articles", "Timelines"):
                self.page_consumed.add(id(n))
        rest = re.sub(r"\s+", " ", " ".join(self._leftover(self.root, self.page_consumed))).strip()
        if rest:
            self.report.notes.append(f"text on the page outside the articles, not imported: {rest!r}")

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
        for body in self.narratives:
            out.setdefault(body["type"], []).append(body)
        self.report.counts = {t: len(b) for t, b in sorted(out.items())}
        self._notes()
        return out

    def _notes(self) -> None:
        n = self.report.notes
        if self.empty_fields:
            listed = ", ".join(repr(f) for f in self.empty_fields)
            n.append(f"{len(self.empty_fields)} empty template field(s) (World Anvil prints them hidden): {listed}")
        if self.inherited_covers:
            c = self.inherited_covers
            n.append(f"{c} cover image{'' if c == 1 else 's'} inherited from World Anvil's default: not kept")
        if self.editor_links:
            n.append(f"{self.editor_links} editor anchor(s) after a link (World Anvil's /edit route): page chrome")
        if self.items:
            n.append(f"not kept: {_NOT_KEPT}")

    def world(self) -> dict[str, Any]:
        title = _find(self.root, _has("world-title"))
        name = _plain(title) if title is not None else ""
        if not name:
            name = f"World Anvil world {self.world_key}"
            self.report.notes.append(f"the export names no world title; named {name!r}")
        world: dict[str, Any] = {"id": _uuid(f"worldanvil:{self.world_key}"), "name": name}
        sub = _find(self.root, _has("subheading"))
        if sub is not None and _plain(sub):
            world["description"] = _plain(sub)
        date = _find(self.root, _has("world-currentDate"))
        if date is not None and _plain(date):
            self.report.notes.append(f"the world's current date {_plain(date)!r} has no world.json key: not kept")
        world["format_version"] = FORMAT_VERSION
        world["producer"] = {"tool": "onlyworlds", "version": __version__, "input": PRODUCER_INPUT}
        return world


def _read(path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError(f"{path}: no such export file")
    try:
        with path.open("rb") as fh:
            data = fh.read(MAX_EXPORT_BYTES + 1)
    except OSError as exc:
        raise ValueError(f"{path}: cannot read the export ({type(exc).__name__}: {exc})") from None
    if len(data) > MAX_EXPORT_BYTES:
        raise ValueError(f"{path}: the export holds more than {MAX_EXPORT_BYTES} bytes; refused")
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValueError(f"{path}: not a World Anvil export (not UTF-8 HTML)") from None


def import_worldanvil(
    source: str | os.PathLike[str],
    out_dir: str | os.PathLike[str] | None,
    *,
    plan_only: bool = False,
) -> ImportReport:
    """Read the World Anvil export page at ``source`` (the HTML of ``/world/<slug>/export``) into
    a world folder at ``out_dir``, which must not exist or be empty.

    With ``plan_only`` nothing is written (``out_dir`` may be None) and the report says what would
    be. What World Anvil hides is imported carrying ``hidden: true`` and named in the report.
    Raises ``FileExistsError`` for an ``out_dir`` that is not empty, ``FileNotFoundError`` for a
    missing file, ``ValueError`` for a file that is not a World Anvil export.
    """
    src = Path(source)
    out = Path(out_dir) if out_dir is not None else None
    if not plan_only:
        if out is None:
            raise ValueError("give an out_dir, or plan_only=True")
        if out.exists() and (not out.is_dir() or any(out.iterdir())):
            raise FileExistsError(f"{out} exists and is not an empty directory; a folder is written whole, once")
    imp = _Importer(_read(src), src)
    imp.collect()
    imp.report.world = imp.world()
    imp.fill()
    elements = imp.bodies()
    report = imp.report
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
    ap = argparse.ArgumentParser(prog="python -m onlyworlds.worldanvil", description=(__doc__ or "").splitlines()[0])
    ap.add_argument("out", type=Path, nargs="?", help="the world folder to create; must not exist or be empty")
    ap.add_argument("--file", type=Path, help="World Anvil's export page (/world/<slug>/export, saved as HTML)")
    ap.add_argument("--plan", action="store_true", help="print what would become what and write nothing")
    args = ap.parse_args(argv)
    if args.file is None:
        print("give --file EXPORT.html (World Anvil's export page, saved from the browser)", file=sys.stderr)
        return 2
    if args.out is None and not args.plan:
        print("give OUT-DIR, or --plan", file=sys.stderr)
        return 2
    try:
        report = import_worldanvil(args.file, args.out, plan_only=args.plan)
    except (FileExistsError, FileNotFoundError, ValueError) as exc:
        print(f"{exc}", file=sys.stderr)
        return 2
    sys.stdout.write(report.render())
    return 0


if __name__ == "__main__":
    sys.exit(main())

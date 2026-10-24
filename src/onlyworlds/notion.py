"""Read a Notion export into a world folder: no AI, no account, the same folder every time.

    python -m onlyworlds.notion EXPORT.zip OUT-DIR [--plan]

or ``import_notion(source, out_dir, plan_only=False)``. ``source`` is Notion's "Markdown & CSV"
export, the zip as downloaded or a directory it was unzipped into. ``--plan`` prints what would
become what and writes nothing. OUT-DIR must not exist yet (or be empty): a folder is written
whole, once, through ``write_folder``.

**Two real exports have been read** (a free account's page export with sub-pages, once flat
and once with folders: ``tests/fixtures/notion/``); what they showed is marked *seen*, the rest is
believed from Notion's help page and from practice. Every name this module reads is parsed in one
place (``parse_name``, ``_cell_items``, ``_ID_IN_URL``, the ``_all`` suffix in
``_Importer._databases``) so a real export can correct them in one place. The shape:

- every exported page is ``<Title> <32 hex>.md``; the 32 hex digits are the page's Notion id
  (identity), the title before them is presentation (seen);
- a full-page database is ``<Title> <32 hex>.csv``, beside ``<Title> <32 hex>_all.csv`` holding
  every property (seen, both times, the two alike): ``_all`` is read when both exist, never both;
- the CSV's first column is the title property (``Name``), UTF-8 with a byte order mark (seen);
- a database's rows are pages; a row page repeats the row's properties as ``Key: value`` lines
  under its ``# Title`` heading, an empty property with no line (seen), and those lines are left
  out of its text;
- a page's text opens with ``# <Title>``, which is left out (it is the name; seen).

Where the rows' pages and the sub-pages are, three layouts:

- **Folders named by title** (seen: a page export with "Create folders for subpages" on). A
  database's rows sit in ``<Title>/`` beside its CSV (``Characters 4037....csv`` and
  ``Characters/Mara Voss 4037....md``), and a page's sub-pages in ``<Title>/`` beside the page
  (``World overview 4037....md`` and ``World overview/Calendar and seasons 4037....md``).
- **Folders named by title and id** (believed, not yet seen): ``<Title> <32 hex>/`` in the same
  places. Read first when both exist.
- **Flat** (seen: the same export with that switch off): the CSVs and every page, the rows' pages
  among them, in one directory. The tree is not in the files, so no ``x_notion_parent`` is
  written.

In a database's folder a CSV row is matched to its page by title (exactly, else with the
characters a filename cannot hold removed and case folded), the folder's name matched to the
database's title the same way. A database with no folder (flat), or whose ``<Title>/`` folder is
also named by a page beside it with the same title (it then holds that page's sub-pages too) or by
a second database, pairs each row with a page in that directory whose ``# Title`` heading matches
the row's title and whose property lines each equal the row's cell for that column (a relation's
target compared by its id, since the CSV's path ends ``.csv`` where the page's ends ``.md``), with
at least one such line when the row has a cell besides its title. Paired only when the row fits
one page and the page fits no other row; a row left unpaired is a CSV row with no page (below),
and the report says why; a page left unpaired stays a page.

The rest:

- a relation cell lists page titles separated by commas, each followed by its exported path in
  parentheses (seen: ``Harbor (Harbor%20<id>.csv)`` flat, ``Harbor (Locations/Harbor%20<id>.csv)``
  with folders: a path to no file, the id the row page's; believed: a ``.md`` path, a notion.so
  URL, a Markdown link); the target's id is read from that path; an empty relation is an empty cell;
- links between pages in a page's text are relative Markdown links to the exported files,
  percent-encoded (seen); callouts come as HTML (``<aside>``) and are kept as text;
- attachments are files beside the page, in the page's folder;
- a large export may hold its parts as inner zips (``...-Part-1.zip``); one level is read.

What becomes what:

- **A database row becomes an element** when the database's title is a category (the 22 types,
  singular or plural, any case: ``Characters``, ``location``), or else, row by row, when a column
  named ``Type`` (any case) holds one. A column becomes a field when its name, lowercased with
  spaces as underscores, equals a field of that type (compared without case, so ``str`` finds
  ``STR``); the title column is ``name``. A value that does not fit the field's kind (text in an
  integer field, two targets for a single link) is kept as an extension instead. A relation
  column becomes a link field of the same name when the field links: each target is resolved by
  its Notion id, failing that by its exact title among the elements of typed databases of the
  field's target type. When any target is unresolved the cell is also kept verbatim under the
  extension. Every column that is not placed is kept verbatim as ``x_notion_<column, lowercased,
  spaces as underscores>`` (``_2`` and on when two columns, or a column and the door's own keys,
  would share a key): nothing is dropped. A row's page text is its ``description``, or
  ``x_notion_body`` when a column filled ``description``.
- **A row of an untyped database becomes a Narrative**, supertype ``Article`` (what it is, never
  where it came from: the producer line says that), subtype the database's title, every column
  under ``x_notion_``, its page text the description.
- **A page becomes a Narrative**: the title its name, its Markdown its description,
  ``x_notion_id`` the Notion id, ``x_notion_parent`` the element id of the page (or row) it sits
  under. A relative link in its text to another exported page also becomes a link on Narrative's
  multi-link field for that page's type (``characters``, ``locations``, ...) when there is one;
  the text keeps the link as it was either way. Untyped rows are Narratives and are read the same.
- **An attachment** a page or row links to is copied into the folder at
  ``media/notion/<its path in the export>`` and the link in the text rewritten to that path. The
  folder format leaves ``media/`` unspecified, so every type is copied; an attachment no text
  links to is listed, not copied.
- **Ids are UUIDv5** in ``NOTION_NAMESPACE`` of the 32 hex digits, so the same export twice, or a
  later export of the same workspace, gives the same ids. A page with no id in its name, a CSV
  row with no page, and a second file claiming an id already seen, take UUIDv5 of their path in
  the export and are listed. ``world.json``: ``id`` UUIDv5 of the export's root folder name (the
  zip's one top folder, else the zip's or directory's own name), ``name`` the one top page's
  title (else that name, its id removed), ``producer`` ``{"tool": "onlyworlds", "version": ...,
  "input": "notion-export"}`` (``PRODUCER_INPUT``), ``format_version`` this package's.

Nothing is guessed: no type from prose, no field from a synonym. The report (``ImportReport``,
printed at the end of a run and by ``--plan``) names what became what with counts, the untyped
databases, every column not placed (database, column, why, the key it was kept as), every link
not resolved (the element, the column or ``body``, the target as written, why), every id taken
from a path, the attachments copied and anything skipped. Not read: Notion's HTML export, HTML
links (only Markdown ones), links whose target holds a space or a parenthesis unencoded.

From the command line: exit 0 written (or planned), 2 on bad arguments (a missing source, an
OUT-DIR that is not empty, a file that is not a zip, an export with no page or database in it).
"""

from __future__ import annotations

import argparse
import csv
import functools
import io
import os
import posixpath
import re
import sys
import unicodedata
import urllib.parse
import uuid
import zipfile
from collections.abc import Callable, Iterable
from contextlib import ExitStack
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ._schema import ELEMENT_TYPES, FIELD_KINDS, LINK_TARGETS
from ._version import __version__
from .folder import FORMAT_VERSION, write_folder

__all__ = [
    "CATEGORY_WORDS",
    "EXT_PREFIX",
    "NOTION_NAMESPACE",
    "PRODUCER_INPUT",
    "DatabasePlan",
    "IdFromPath",
    "ImportReport",
    "Unplaced",
    "Unresolved",
    "category_of",
    "import_notion",
    "main",
    "parse_name",
]

#: The ``producer.input`` word for this door (Skeld's ruling, decision 3 of the dossier's sheet).
PRODUCER_INPUT = "notion-export"

#: The namespace every id this door mints is UUIDv5 in. Fixed for good: changing it would give
#: every element of every re-imported workspace a new id. ``_ids.py`` mints v7 ids only and has
#: no namespace, so this one is the door's own (UUIDv5 of a URL in the URL namespace).
NOTION_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "https://onlyworlds.com/ns/notion-export")

#: Every extension key this door writes starts with this.
EXT_PREFIX = "x_notion_"
_EXT_ID = f"{EXT_PREFIX}id"
_EXT_PARENT = f"{EXT_PREFIX}parent"
_EXT_BODY = f"{EXT_PREFIX}body"
_RESERVED = frozenset({_EXT_ID, _EXT_PARENT, _EXT_BODY})

#: The supertype an untyped database's rows carry: what they are, never where they came from (the
#: producer line and the x_notion_ keys say that; Skeld, OW Market h40 #11385).
UNTYPED_SUPERTYPE = "Article"

#: Where attachments land inside the folder (decision 2).
MEDIA_DIR = "media/notion"

_PLURALS: dict[str, str] = {
    "ability": "abilities",
    "collective": "collectives",
    "character": "characters",
    "construct": "constructs",
    "creature": "creatures",
    "event": "events",
    "family": "families",
    "institution": "institutions",
    "language": "languages",
    "law": "laws",
    "location": "locations",
    "map": "maps",
    "marker": "markers",
    "narrative": "narratives",
    "object": "objects",
    "phenomenon": "phenomena",
    "pin": "pins",
    "relation": "relations",
    "species": "species",
    "title": "titles",
    "trait": "traits",
    "zone": "zones",
}

#: Lowercased word -> type: each of the 22 types under its singular and its plural.
CATEGORY_WORDS: dict[str, str] = {
    **{t: t for t in ELEMENT_TYPES},
    **{_PLURALS[t]: t for t in ELEMENT_TYPES},
}

#: type -> {lowercased field name: field name}, so a column ``str`` finds ``STR``.
_FIELD_BY_LOWER: dict[str, dict[str, str]] = {t: {f.lower(): f for f in kinds} for t, kinds in FIELD_KINDS.items()}

#: target type -> Narrative's multi-link field for it (schema order, the first one wins).
_NARRATIVE_FIELD_FOR: dict[str, str] = {}
for _f, _kind in FIELD_KINDS["narrative"].items():
    if _kind == "multi_link":
        _NARRATIVE_FIELD_FOR.setdefault(LINK_TARGETS["narrative"][_f], _f)


def category_of(word: str) -> str | None:
    """The type a word names (``Characters``, ``location``, ``Phenomena``), or None."""
    return CATEGORY_WORDS.get(word.strip().lower())


# ---------------------------------------------------------------------------
# Names: every believed piece of Notion's naming, in one place.
# ---------------------------------------------------------------------------

_NAME_ID = re.compile(r"(?:(?P<title>.*?)\s+)?(?P<id>[0-9a-fA-F]{32})", re.S)
_ID_IN_URL = re.compile(
    r"(?<![0-9a-fA-F])(?:(?P<hex>[0-9a-fA-F]{32})|(?P<dashed>[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}"
    r"-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}))(?![0-9a-fA-F])"
)
_ALL_SUFFIX = "_all"
_FILENAME_UNSAFE = re.compile(r'[\\/:*?"<>|]')


def parse_name(stem: str) -> tuple[str, str | None]:
    """``"Aria Vell 0123...cdef"`` -> ``("Aria Vell", "0123...cdef")``; a stem with no 32-hex id -> ``(stem, None)``.

    Believed: Notion appends the page id, 32 lowercase hex digits, after one space.
    """
    m = _NAME_ID.fullmatch(stem)
    if m is None:
        return stem.strip(), None
    return (m["title"] or "").strip(), m["id"].lower()


def _id_in_url(url: str) -> str | None:
    """The last Notion id in a link target (an exported path or a notion.so URL), or None."""
    found = list(_ID_IN_URL.finditer(urllib.parse.unquote(url)))
    if not found:
        return None
    m = found[-1]
    return (m["hex"] or m["dashed"].replace("-", "")).lower()


_CELL_ITEM = re.compile(
    r"""\s*(?:
        \[(?P<md_text>[^\]]*)\]\((?P<md_url>[^)\s]*)\)
      | (?P<p_text>[^,]*?)\s*\((?P<p_url>[^()\s]*?(?:\.md|[0-9a-fA-F]{32})[^()\s]*)\)
      | (?P<plain>[^,]*)
    )\s*(?:,|$)""",
    re.X,
)


def _cell_items(cell: str) -> list[tuple[str, str | None]]:
    """A relation cell -> ``[(title, url or None), ...]``.

    Believed: items separated by commas, each ``Title (url)``, ``[Title](url)`` or a bare title.
    A bare title holding a comma reads as two.
    """
    out: list[tuple[str, str | None]] = []
    pos = 0
    while pos < len(cell):
        m = _CELL_ITEM.match(cell, pos)
        if m is None or m.end() == pos:
            break
        pos = m.end()
        if m["md_url"] is not None:
            out.append((m["md_text"].strip(), m["md_url"]))
        elif m["p_url"] is not None:
            out.append((m["p_text"].strip(), m["p_url"]))
        elif m["plain"] and m["plain"].strip():
            out.append((m["plain"].strip(), None))
    return out


def _fold_title(title: str) -> str:
    return _FILENAME_UNSAFE.sub("", unicodedata.normalize("NFC", title)).casefold().strip()


def _column_key(header: str) -> str:
    """A column's name lowercased, whitespace runs as underscores: the name a field is compared to."""
    return re.sub(r"\s+", "_", header.strip().lower())


# ---------------------------------------------------------------------------
# The report
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Unplaced:
    """A column (or some of its values) not placed on a field, kept as ``kept_as``."""

    database: str
    column: str
    why: str
    kept_as: str


@dataclass(frozen=True)
class Unresolved:
    """A link whose target is not an element of the folder; kept as text."""

    source: str
    source_id: str
    #: ``column <name>`` or ``body``
    where: str
    target: str
    why: str


@dataclass(frozen=True)
class IdFromPath:
    """An element whose id is UUIDv5 of its path in the export, not of a Notion id."""

    path: str
    why: str


@dataclass(frozen=True)
class DatabasePlan:
    title: str
    path: str
    rows: int
    #: type -> rows of it; ``narrative`` holds the untyped rows too
    becomes: dict[str, int]
    #: ``title`` (its title names the category), ``column`` (a Type column) or ``untyped``
    typed_by: str


@dataclass
class ImportReport:
    source: Path
    world: dict[str, Any]
    counts: dict[str, int] = field(default_factory=dict)
    databases: list[DatabasePlan] = field(default_factory=list)
    pages: int = 0
    unplaced: list[Unplaced] = field(default_factory=list)
    unresolved: list[Unresolved] = field(default_factory=list)
    ids_from_path: list[IdFromPath] = field(default_factory=list)
    #: folder-relative paths of the attachments copied
    media: list[str] = field(default_factory=list)
    #: anything read past or left out, one line each
    notes: list[str] = field(default_factory=list)
    #: where the folder was written; None for a plan
    out: Path | None = None

    @property
    def total(self) -> int:
        return sum(self.counts.values())

    @property
    def untyped_databases(self) -> list[str]:
        return [d.title for d in self.databases if d.typed_by == "untyped"]

    def render(self) -> str:
        """The report in prose, one finding a line."""
        lines: list[str] = []
        by_type = ", ".join(f"{t} {n}" for t, n in sorted(self.counts.items()))
        lines.append(f"Notion export {self.source}: {self.total} elements ({by_type or 'none'}).")
        if self.databases or self.pages:
            lines.append("What became what:")
            for d in self.databases:
                parts = ", ".join(f"{t} {n}" for t, n in sorted(d.becomes.items()))
                how = {
                    "title": "its title names the type",
                    "column": "typed row by row by its Type column",
                    "untyped": f"untyped: Narratives, supertype {UNTYPED_SUPERTYPE}, subtype {d.title!r}",
                }[d.typed_by]
                rows = f"{d.rows} row" + ("" if d.rows == 1 else "s")
                lines.append(f"  - database {d.title!r} ({rows}): {parts or 'nothing'}; {how}")
            if self.pages:
                lines.append(f"  - {self.pages} page{'' if self.pages == 1 else 's'}: narrative")
        if self.untyped_databases:
            lines.append(
                "Kept untyped (retype them later): " + ", ".join(repr(t) for t in self.untyped_databases) + "."
            )
        if self.unplaced:
            lines.append(f"Columns not placed on a field ({len(self.unplaced)}), kept as extensions:")
            lines += [f"  - {u.database!r} / {u.column!r}: {u.why}; kept as {u.kept_as}" for u in self.unplaced]
        if self.unresolved:
            lines.append(f"Links not resolved ({len(self.unresolved)}), kept as text:")
            lines += [f"  - {u.source!r} ({u.source_id}), {u.where}: {u.target!r}: {u.why}" for u in self.unresolved]
        if self.ids_from_path:
            lines.append(f"Ids taken from the path, not a Notion id ({len(self.ids_from_path)}):")
            lines += [f"  - {p.path}: {p.why}" for p in self.ids_from_path]
        if self.media:
            lines.append(f"Attachments copied to {MEDIA_DIR}/: {len(self.media)}.")
        if self.notes:
            lines.append(f"Notes ({len(self.notes)}):")
            lines += [f"  - {n}" for n in self.notes]
        lines.append(f"Wrote {self.out}." if self.out is not None else "Plan only: nothing written.")
        return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# The export as a tree of files
# ---------------------------------------------------------------------------

Opener = Callable[[], bytes]


@dataclass
class _Tree:
    root_name: str
    #: export-relative POSIX path (NFC, the one top folder removed) -> its bytes, read on demand
    files: dict[str, Opener]
    notes: list[str]


def _safe_rel(name: str) -> str | None:
    """A zip or directory entry's name as a relative POSIX path, or None when it climbs out or is absolute."""
    rel = unicodedata.normalize("NFC", name.replace("\\", "/"))
    if rel.startswith("/") or re.match(r"^[A-Za-z]:", rel):
        return None
    parts = [p for p in rel.split("/") if p not in ("", ".")]
    if not parts or any(p == ".." for p in parts):
        return None
    return "/".join(parts)


def _litter(rel: str) -> bool:
    return any(p.startswith(".") or p == "__MACOSX" for p in rel.split("/"))


def _add_zip(zf: zipfile.ZipFile, files: dict[str, Opener], notes: list[str], *, nested: bool) -> None:
    for info in sorted(zf.infolist(), key=lambda i: i.filename):
        if info.is_dir():
            continue
        rel = _safe_rel(info.filename)
        if rel is None:
            notes.append(f"skipped {info.filename!r}: an unsafe path")
            continue
        if _litter(rel):
            notes.append(f"skipped {rel}: not part of the export (a dot-file or __MACOSX)")
            continue
        if rel.lower().endswith(".zip") and not nested:
            inner = zipfile.ZipFile(io.BytesIO(zf.read(info)))
            _add_zip(inner, files, notes, nested=True)
            continue
        if rel in files:
            notes.append(f"skipped a second {rel} (the first one read is kept)")
            continue
        files[rel] = functools.partial(zf.read, info)


def _open_tree(source: Path, stack: ExitStack) -> _Tree:
    files: dict[str, Opener] = {}
    notes: list[str] = []
    if source.is_dir():
        own_name = source.name
        for path in sorted(p for p in source.rglob("*") if p.is_file()):
            rel = _safe_rel(path.relative_to(source).as_posix())
            if rel is None:
                continue
            if _litter(rel):
                notes.append(f"skipped {rel}: not part of the export (a dot-file or __MACOSX)")
                continue
            files[rel] = path.read_bytes
    elif source.is_file():
        own_name = source.stem
        try:
            zf = stack.enter_context(zipfile.ZipFile(source))
        except zipfile.BadZipFile as exc:
            raise ValueError(f"{source}: not a zip file ({exc})") from exc
        _add_zip(zf, files, notes, nested=False)
    else:
        raise FileNotFoundError(f"{source}: no such file or directory")
    tops = {rel.split("/", 1)[0] for rel in files}
    if len(tops) == 1 and all("/" in rel for rel in files):
        top = tops.pop()
        return _Tree(top, {rel.split("/", 1)[1]: op for rel, op in files.items()}, notes)
    return _Tree(own_name, files, notes)


# ---------------------------------------------------------------------------
# The import
# ---------------------------------------------------------------------------


def _uuid(key: str) -> str:
    return str(uuid.uuid5(NOTION_NAMESPACE, key))


@dataclass
class _Database:
    title: str
    notion_id: str | None
    csv: str
    rows_dir: str
    #: the type its title names, or None
    typed_type: str | None
    headers: list[str] = field(default_factory=list)
    #: the CSV's rows below the header, blank rows left out
    rows: list[list[str]] = field(default_factory=list)
    #: one ``x_notion_`` key per column
    ext_keys: list[str] = field(default_factory=list)
    #: the Type column's index, when the title names no type and the database has one
    type_col: int | None = None


@dataclass(frozen=True)
class _Candidates:
    """A database whose rows are paired with pages by title and cells, and where those pages are."""

    db: _Database
    #: the directory whose pages may be its rows
    dir: str
    #: where that is, as the report says it (``beside its CSV``, ``in <folder>/``)
    place: str
    #: what the report says first when no page fits a row
    lead: str
    #: why its folder is not read by the folder rule ("shares its folder ... with ..."), or "" (flat)
    shared: str


def _by_title[T](named: Iterable[tuple[str, T]], title: str) -> list[T]:
    """The values whose name is ``title``: exactly, else folded (the door's title rule)."""
    pairs = list(named)
    exact = [v for n, v in pairs if n == title]
    return exact or [v for n, v in pairs if _fold_title(n) == _fold_title(title)]


@dataclass
class _Item:
    """One element being built."""

    etype: str
    eid: str
    name: str
    notion_id: str | None
    #: the page's .md path in the export, None for a CSV row with no page
    md: str | None
    #: True for an element from a typed database: what a relation may find by title
    typed: bool = False
    parent: str | None = None
    #: the database a row is from, None for a page
    db: _Database | None = None
    #: a row's cells, the title first
    cells: list[str] = field(default_factory=list)
    #: True when the row's Type cell named its type (the cell is then not kept)
    type_consumed: bool = False
    fields: dict[str, Any] = field(default_factory=dict)
    ext: dict[str, Any] = field(default_factory=dict)
    text: str = ""


_LINK = re.compile(r"(?P<bang>!?)\[(?P<text>[^\]]*)\]\((?P<target>[^)\s]+)(?P<rest>\s+\"[^\"]*\")?\)")
_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
_PROP_LINE = re.compile(r"^(?P<key>[^:\n]+):(?: (?P<value>.*))?$")
_INT = re.compile(r"\s*-?\d+\s*")


def _decode(data: bytes) -> str:
    return data.decode("utf-8-sig", errors="replace").replace("\r\n", "\n")


def _heading_at(lines: list[str]) -> int:
    """The index of a page's first non-blank line (its ``# Title`` heading, when it has one)."""
    i = 0
    while i < len(lines) and not lines[i].strip():
        i += 1
    return i


def _prop_span(lines: list[str], i: int, keys: set[str]) -> tuple[int, int]:
    """``(j, k)``: ``lines[j:k]`` are the ``Key: value`` lines from ``i`` on (blank lines first are passed)
    whose key is one of ``keys``; ``j == k`` when there are none."""
    j = i
    while j < len(lines) and not lines[j].strip():
        j += 1
    k = j
    while k < len(lines):
        m = _PROP_LINE.match(lines[k])
        if m is None or m["key"].strip() not in keys:
            break
        k += 1
    return j, k


def _page_text(raw: str, titles: Iterable[str], props: Iterable[str] = ()) -> str:
    """A page's Markdown less its ``# Title`` heading and, for a row's page, the property lines under it.

    The heading is left out only when it is one of ``titles`` (the file's title, the row's); a page
    whose first line is anything else keeps every line.
    """
    lines = raw.split("\n")
    names = {t.strip() for t in titles}
    i = _heading_at(lines)
    if i < len(lines) and lines[i].startswith("# ") and lines[i][2:].strip() in names:
        i += 1
        keys = set(props)
        if keys:
            j, k = _prop_span(lines, i, keys)
            if k > j:
                i = k
    else:
        i = 0
    return "\n".join(lines[i:]).strip("\n").rstrip()


def _heading_and_props(raw: str, keys: set[str]) -> tuple[str | None, list[tuple[str, str]]]:
    """A page's ``# Title`` heading (None when its first line is not one) and the property lines
    under it that ``_page_text`` would leave out for a row of a database with these column names."""
    lines = raw.split("\n")
    i = _heading_at(lines)
    if i >= len(lines) or not lines[i].startswith("# "):
        return None, []
    j, k = _prop_span(lines, i + 1, keys)
    props: list[tuple[str, str]] = []
    for line in lines[j:k]:
        m = _PROP_LINE.match(line)
        assert m is not None
        props.append((m["key"].strip(), m["value"] or ""))
    return lines[i][2:].strip(), props


def _cell_key(value: str) -> list[tuple[str, str | None]]:
    """A cell read as relation items, each target by its Notion id when it holds one: a row's page
    writes ``Harbor (Harbor%20<id>.md)`` where the CSV writes ``Harbor (Harbor%20<id>.csv)``."""
    return [(t, (_id_in_url(u) or u) if u is not None else None) for t, u in _cell_items(value)]


def _same_cell(page_value: str, cell: str) -> bool:
    """A row page's property value is the row's cell: equal as text, or as relation items whose
    titles and target ids agree (the extensions may differ)."""
    a, b = page_value.strip(), cell.strip()
    if a == b:
        return True
    ka = _cell_key(a)
    return any(u is not None for _, u in ka) and ka == _cell_key(b)


def _props_fit(props: list[tuple[str, str]], cells: list[str], cols: dict[str, list[int]]) -> bool:
    """Each of a page's property lines equals the row's cell for its column, and a row with a cell
    besides its title has at least one line (so a plain page that only shares a row's title is not it)."""
    if not props and any(c.strip() for c in cells[1:]):
        return False
    return all(any(_same_cell(v, cells[i] if i < len(cells) else "") for i in cols[k]) for k, v in props)


class _Importer:
    def __init__(self, tree: _Tree, source: Path) -> None:
        self.tree = tree
        self.report = ImportReport(source=source, world={}, notes=list(tree.notes))
        self.items: list[_Item] = []
        self.by_md: dict[str, _Item] = {}
        self.by_notion: dict[str, _Item] = {}
        self.by_title: dict[tuple[str, str], list[_Item]] = {}
        #: directory -> the pages (rows' pages too) in it, for the parent rule
        self._pages_in: dict[str, list[_Item]] = {}
        #: export-relative path of an attachment -> its folder-relative path
        self.media: dict[str, str] = {}
        self._unplaced_seen: set[Unplaced] = set()

    # -- the files ----------------------------------------------------------

    def _databases(self) -> list[_Database]:
        """Every CSV, the ``_all`` one preferred when both exist (never both read)."""
        groups: dict[tuple[str, str], dict[bool, str]] = {}
        for rel in self.tree.files:
            if not rel.lower().endswith(".csv"):
                continue
            d, stem = posixpath.split(rel[:-4])
            is_all = stem.endswith(_ALL_SUFFIX) and parse_name(stem[: -len(_ALL_SUFFIX)])[1] is not None
            base = stem[: -len(_ALL_SUFFIX)] if is_all else stem
            groups.setdefault((d, base), {})[is_all] = rel
        out: list[_Database] = []
        for (d, base), pair in sorted(groups.items()):
            if True in pair and False in pair:
                self.report.notes.append(f"read {pair[True]}, not {pair[False]} (the _all CSV holds every property)")
            title, nid = parse_name(base)
            out.append(
                _Database(title, nid, pair.get(True) or pair[False], posixpath.join(d, base), category_of(title))
            )
        return out

    def _claim_id(self, path: str, nid: str | None, why_none: str) -> tuple[str, str | None]:
        """The element id for ``path``: UUIDv5 of the Notion id, or of the path (reported)."""
        if nid is not None and nid not in self.by_notion:
            return _uuid(nid), nid
        why = why_none if nid is None else f"its Notion id is also {self.by_notion[nid].md or 'another row'}'s"
        self.report.ids_from_path.append(IdFromPath(path, why))
        return _uuid(f"path:{path}"), None

    def _add(self, item: _Item) -> _Item:
        self.items.append(item)
        if item.md is not None:
            self.by_md[item.md] = item
        if item.notion_id is not None:
            self.by_notion[item.notion_id] = item
        if item.typed:
            self.by_title.setdefault((item.etype, item.name), []).append(item)
        return item

    def _read_csv(self, rel: str) -> list[list[str]]:
        text = self.tree.files[rel]().decode("utf-8-sig", errors="replace")
        return [row for row in csv.reader(io.StringIO(text, newline=""))]

    # -- pass 1: every element, with its type and id ------------------------

    def collect(self) -> None:
        databases = self._databases()
        mds = [rel for rel in sorted(self.tree.files) if rel.lower().endswith(".md")]
        by_dir: dict[str, list[str]] = {}
        for rel in mds:
            by_dir.setdefault(posixpath.dirname(rel), []).append(rel)

        for db in databases:
            rows = self._read_csv(db.csv)
            db.headers = rows[0] if rows else []
            db.rows = [r for r in rows[1:] if any(c.strip() for c in r)]
        folders, strict = self._row_folders(databases, by_dir)
        taken = set(folders.values())
        flat = self._pair_flat(strict, {d: rels for d, rels in by_dir.items() if d not in taken})
        paired = {md for pairs in flat.values() for md, _why in pairs if md is not None}
        pages = [rel for rel in mds if posixpath.dirname(rel) not in taken and rel not in paired]

        for db in databases:
            folder = folders.get(db.csv)
            self._collect_database(db, by_dir[folder] if folder is not None else [], flat.get(db.csv))
        for rel in pages:
            title, nid = parse_name(posixpath.basename(rel)[:-3])
            eid, kept = self._claim_id(rel, nid, "no Notion id in the file's name")
            self._add(_Item("narrative", eid, title, kept, rel))
            self.report.pages += 1
        if not self.items:
            raise ValueError(f"{self.report.source}: no page or database found (is it a Markdown & CSV export?)")

        # parents: a page's is the page whose folder holds it; a row's, its database's own page
        # (an .md named like the CSV) or else the page whose folder holds the CSV
        for rel, item in self.by_md.items():
            self._pages_in.setdefault(posixpath.dirname(rel), []).append(item)
        for item in self.items:
            if item.db is not None:
                item.parent = self._page_for_dir(item.db.rows_dir) or self._page_for_dir(posixpath.dirname(item.db.csv))
            elif item.md is not None:
                item.parent = self._page_for_dir(posixpath.dirname(item.md))

    def _page_for_dir(self, d: str) -> str | None:
        """The page whose sub-pages folder ``d`` is: ``<d>.md`` (a ``<Title> <id>/`` folder), else the one
        page beside the folder whose title is the folder's name (a ``<Title>/`` folder)."""
        if not d:
            return None
        page = self.by_md.get(f"{d}.md")
        if page is None:
            up, name = posixpath.split(d)
            near = [(parse_name(posixpath.basename(i.md or "")[:-3])[0], i) for i in self._pages_in.get(up, [])]
            hits = _by_title(near, name)
            page = hits[0] if len(hits) == 1 else None
        return page.eid if page is not None else None

    def _row_folders(
        self, databases: list[_Database], by_dir: dict[str, list[str]]
    ) -> tuple[dict[str, str], list[_Candidates]]:
        """Where each database's rows' pages are.

        Returns the databases read by the folder rule (CSV -> its folder: ``<Title> <id>/`` beside the
        CSV, else ``<Title>/``, the title matched exactly, else folded) and those whose rows are
        paired by title and cells instead: a database with no folder (flat), and a database whose
        ``<Title>/`` folder another database, or a page beside it with the same title, also names.
        Such a folder holds the page's sub-pages as well as the rows, so only the pages that fit a
        row by title and cells are rows; the rest stay pages under that page.
        """
        folders: dict[str, str] = {}
        by_title_dir: dict[str, list[_Database]] = {}
        strict: list[_Candidates] = []
        for db in databases:
            if db.rows_dir in by_dir:
                folders[db.csv] = db.rows_dir
                continue
            d = posixpath.dirname(db.csv)
            subs = [(posixpath.basename(x), x) for x in sorted(by_dir) if x and x != d and posixpath.dirname(x) == d]
            hits = _by_title(subs, db.title)
            if len(hits) == 1:
                by_title_dir.setdefault(hits[0], []).append(db)
            else:
                strict.append(_Candidates(db, d, "beside its CSV", "the database has no folder, and ", ""))
        for sub, dbs in sorted(by_title_dir.items()):
            up, name = posixpath.split(sub)
            own = {db.notion_id for db in dbs}
            named = [
                rel
                for rel in _by_title([(parse_name(posixpath.basename(r)[:-3])[0], r) for r in by_dir.get(up, [])], name)
                if parse_name(posixpath.basename(rel)[:-3])[1] not in own
            ]
            if len(dbs) == 1 and not named:
                folders[dbs[0].csv] = sub
                continue
            for db in dbs:
                others = [*(f"database {o.title!r}" for o in dbs if o is not db), *(f"page {p}" for p in named)]
                shared = f"shares its folder {sub}/ with {', '.join(others)}"
                strict.append(_Candidates(db, sub, f"in {sub}/", "", shared))
        return folders, strict

    def _pair_flat(
        self, groups: list[_Candidates], by_dir: dict[str, list[str]]
    ) -> dict[str, list[tuple[str | None, str]]]:
        """Each database whose rows are paired by title and cells -> per row, its page and, when it
        has none, why.

        A row's page is a page in the group's directory (the CSV's, in a flat export) whose ``# Title``
        heading is the row's title (exactly, else folded, as the folder rule matches) and whose
        property lines each equal the row's cell for that column (at least one line when the row has
        a cell besides its title). Paired only when the row has one such page and the page fits no
        other row.
        """
        raw: dict[str, str] = {}
        hits: dict[tuple[str, int], list[str]] = {}
        claims: dict[str, int] = {}
        for group in groups:
            db = group.db
            cols: dict[str, list[int]] = {}
            for i, h in enumerate(db.headers):
                cols.setdefault(h.strip(), []).append(i)
            read: list[tuple[str, str | None, list[tuple[str, str]]]] = []
            for md in by_dir.get(group.dir, []):
                if md not in raw:
                    raw[md] = _decode(self.tree.files[md]())
                read.append((md, *_heading_and_props(raw[md], set(cols))))
            for n, cells in enumerate(db.rows):
                title = cells[0].strip() if cells else ""
                found = [
                    (md, head)
                    for md, head, props in read
                    if title
                    and head is not None
                    and _fold_title(head) == _fold_title(title)
                    and _props_fit(props, cells, cols)
                ]
                exact = [md for md, head in found if head == title]
                pick = exact if exact else [md for md, _head in found]
                hits[(db.csv, n)] = pick
                for md in pick:
                    claims[md] = claims.get(md, 0) + 1
        out: dict[str, list[tuple[str | None, str]]] = {}
        for group in groups:
            db, place = group.db, group.place
            pairs: list[tuple[str | None, str]] = []
            for n in range(len(db.rows)):
                pick = hits[(db.csv, n)]
                if len(pick) == 1 and claims[pick[0]] == 1:
                    pairs.append((pick[0], ""))
                elif not pick:
                    why = f"{group.lead}no page {place} carries the row's title and cells"
                    pairs.append((None, f"a CSV row with no page of its own ({why})"))
                elif len(pick) > 1:
                    pairs.append((None, f"a CSV row with no page of its own ({len(pick)} pages {place} fit the row)"))
                else:
                    pairs.append((None, f"a CSV row with no page of its own ({pick[0]} fits it and another row)"))
            out[db.csv] = pairs
            if db.rows:
                got = sum(md is not None for md, _why in pairs)
                head = group.shared or "has no folder of its own"
                rest = " (the other pages there stay pages)" if group.shared else ""
                self.report.notes.append(
                    f"database {db.title!r} {head}: {got} of its {len(db.rows)} rows paired"
                    f" with a page {place} by title and cells{rest}"
                )
        return out

    def _collect_database(
        self, db: _Database, mds: list[str], flat: list[tuple[str | None, str]] | None = None
    ) -> None:
        body_rows = db.rows
        if db.typed_type is None:
            db.type_col = next((i for i, h in enumerate(db.headers) if i > 0 and h.strip().lower() == "type"), None)
        db.ext_keys = self._ext_keys(db.headers)
        type_col = db.type_col

        # match rows to their pages: in a flat export, as _pair_flat paired them; else in the
        # database's folder, exactly by title, then folded; each page used once
        pending = [(parse_name(posixpath.basename(m)[:-3]), m) for m in mds]
        matched: list[str | None] = []
        whys = ["a CSV row with no page of its own"] * len(body_rows)
        if flat is not None:
            matched = [md for md, _why in flat]
            whys = [why for _md, why in flat]
        else:
            for cells in body_rows:
                title = cells[0].strip() if cells else ""
                pick = next((i for i, ((t, _), _m) in enumerate(pending) if t == title), None)
                if pick is None:
                    pick = next(
                        (i for i, ((t, _), _m) in enumerate(pending) if _fold_title(t) == _fold_title(title)), None
                    )
                matched.append(pending.pop(pick)[1] if pick is not None else None)

        becomes: dict[str, int] = {}
        typed_by = "title" if db.typed_type else ("column" if type_col is not None else "untyped")
        for n, (cells, md, why) in enumerate(zip(body_rows, matched, whys, strict=True), start=2):
            etype = db.typed_type
            consumed = False
            if etype is None and type_col is not None and type_col < len(cells):
                etype = category_of(cells[type_col])
                consumed = etype is not None
            if md is not None:
                eid, nid = self._claim_id(md, parse_name(posixpath.basename(md)[:-3])[1], "no Notion id in the name")
            else:
                eid, nid = self._claim_id(f"{db.csv}#row {n}", None, why)
            title = cells[0] if cells else ""
            if not title.strip() and md is not None:
                title = parse_name(posixpath.basename(md)[:-3])[0]
            item = _Item(etype or "narrative", eid, title.strip(), nid, md, typed=etype is not None, db=db)
            item.cells, item.type_consumed = cells, consumed
            self._add(item)
            becomes[item.etype] = becomes.get(item.etype, 0) + 1
        for (title, nid), md in pending:
            self.report.notes.append(f"{md}: a page in database {db.title!r} with no row in its CSV; read as a row")
            eid, kept = self._claim_id(md, nid, "no Notion id in the name")
            etype = db.typed_type or "narrative"
            item = _Item(etype, eid, title, kept, md, typed=db.typed_type is not None, db=db, cells=[title])
            self._add(item)
            becomes[etype] = becomes.get(etype, 0) + 1
        self.report.databases.append(
            DatabasePlan(db.title, db.csv, len(body_rows) + len(pending), dict(sorted(becomes.items())), typed_by)
        )

    def _ext_keys(self, headers: list[str]) -> list[str]:
        """One ``x_notion_`` key per column, unique within the database and apart from the door's own keys."""
        taken = set(_RESERVED)
        out: list[str] = []
        for i, header in enumerate(headers):
            base = f"{EXT_PREFIX}{_column_key(header) or f'column_{i + 1}'}"
            key, n = base, 2
            while key in taken:
                key, n = f"{base}_{n}", n + 1
            taken.add(key)
            out.append(key)
        return out

    # -- pass 2: fields, links, text ----------------------------------------

    def fill(self) -> None:
        for item in self.items:
            if item.db is not None:
                self._fill_row(item, item.db)
            if item.md is not None:
                raw = _decode(self.tree.files[item.md]())
                titles = (parse_name(posixpath.basename(item.md)[:-3])[0], item.name)
                props = item.db.headers if item.db is not None else []
                item.text = self._body_links(item, _page_text(raw, titles, props))

    def _unplaced(self, database: str, column: str, why: str, kept_as: str) -> None:
        u = Unplaced(database, column, why, kept_as)
        if u not in self._unplaced_seen:
            self._unplaced_seen.add(u)
            self.report.unplaced.append(u)

    def _fill_row(self, item: _Item, db: _Database) -> None:
        db_title, cells = db.title, item.cells
        lookup = _FIELD_BY_LOWER[item.etype]
        for i, header in enumerate(db.headers):
            if i == 0 or (item.type_consumed and i == db.type_col):
                continue  # the title column is the name; a Type cell that typed the row is its type
            value = cells[i] if i < len(cells) else ""
            if not value.strip():
                continue
            ext = db.ext_keys[i]
            if not item.typed:
                item.ext[ext] = value
                untyped = "the database is untyped" if db.type_col is None else "the row's Type names no type"
                self._unplaced(db_title, header, untyped, ext)
                continue
            name = lookup.get(_column_key(header))
            if name is None or name == "name":
                why = (
                    "the title column is the name"
                    if name == "name"
                    else f"{item.etype} has no field {_column_key(header)!r}"
                )
                item.ext[ext] = value
                self._unplaced(db_title, header, why, ext)
                continue
            kind = FIELD_KINDS[item.etype][name]
            if kind == "text":
                item.fields[name] = value
            elif kind == "integer":
                if _INT.fullmatch(value):
                    item.fields[name] = int(value)
                else:
                    item.ext[ext] = value
                    self._unplaced(db_title, header, f"a value is not a whole number ({name} is an integer)", ext)
            else:
                self._fill_link(item, db_title, header, value, name, kind, ext)

    def _fill_link(self, item: _Item, db_title: str, header: str, value: str, name: str, kind: str, ext: str) -> None:
        target_type = LINK_TARGETS[item.etype][name]
        targets = _cell_items(value)
        if kind == "single_link" and len(targets) > 1:
            item.ext[ext] = value
            self._unplaced(db_title, header, f"a cell names {len(targets)} targets ({name} links one)", ext)
            return
        found: list[str] = []
        missed = False
        for text, url in targets:
            hit, why = self._resolve(text, url, target_type)
            if hit is None:
                missed = True
                self.report.unresolved.append(
                    Unresolved(item.name, item.eid, f"column {header}", text or (url or ""), why)
                )
            elif hit.eid not in found:
                found.append(hit.eid)
        if found:
            item.fields[name] = found[0] if kind == "single_link" else found
        if missed:
            item.ext[ext] = value

    def _resolve(self, text: str, url: str | None, target_type: str) -> tuple[_Item | None, str]:
        nid = _id_in_url(url) if url else None
        if nid is not None and nid in self.by_notion:
            hit = self.by_notion[nid]
            if hit.etype == target_type:
                return hit, ""
            return None, f"the page is a {hit.etype}; the field links a {target_type}"
        same = self.by_title.get((target_type, text), [])
        if len(same) == 1:
            return same[0], ""
        if len(same) > 1:
            return None, f"{len(same)} {target_type} elements carry that name"
        return None, f"no {target_type} in the export by that id or name"

    def _unresolved_body(self, item: _Item, target: str, why: str) -> None:
        self.report.unresolved.append(Unresolved(item.name, item.eid, "body", target, why))

    def _body_links(self, item: _Item, text: str) -> str:
        assert item.md is not None
        here = posixpath.dirname(item.md)
        narrative = item.etype == "narrative"

        def swap(m: re.Match[str]) -> str:
            target = m["target"]
            if _SCHEME.match(target) or target.startswith(("#", "/")):
                return m[0]
            path = urllib.parse.unquote(target.split("#", 1)[0].split("?", 1)[0])
            rel = _safe_rel(posixpath.normpath(posixpath.join(here, path)))
            if (rel or path).lower().endswith(".md"):
                hit = self.by_md.get(rel or "") or self.by_notion.get(_id_in_url(target) or "")
                if hit is None:
                    self._unresolved_body(item, target, "no page in the export")
                elif narrative and hit is not item:
                    fname = _NARRATIVE_FIELD_FOR.get(hit.etype)
                    if fname is not None:
                        links = item.fields.setdefault(fname, [])
                        if hit.eid not in links:
                            links.append(hit.eid)
                return m[0]
            if rel is not None and rel.lower().endswith(".csv"):
                self._unresolved_body(item, target, "a database, not a page")
                return m[0]
            if rel is None or rel not in self.tree.files:
                self._unresolved_body(item, target, "no file in the export")
                return m[0]
            if _FILENAME_UNSAFE.search(posixpath.basename(rel)) or any(p.endswith((" ", ".")) for p in rel.split("/")):
                self.report.notes.append(f"{rel}: not copied (its name cannot be written on every system)")
                return m[0]
            dest = self.media.setdefault(rel, f"{MEDIA_DIR}/{rel}")
            new = urllib.parse.quote(dest, safe="/")
            return f"{m['bang']}[{m['text']}]({new}{m['rest'] or ''})"

        return _LINK.sub(swap, text)

    # -- the bodies ----------------------------------------------------------

    def bodies(self) -> dict[str, list[dict[str, Any]]]:
        out: dict[str, list[dict[str, Any]]] = {}
        for item in self.items:
            body: dict[str, Any] = {"type": item.etype, "id": item.eid, "name": item.name}
            fields = dict(item.fields)
            ext = dict(item.ext)
            if item.text:
                if "description" in fields:
                    ext[_EXT_BODY] = item.text
                else:
                    fields["description"] = item.text
            if item.db is not None and not item.typed:
                fields["supertype"] = UNTYPED_SUPERTYPE
                fields["subtype"] = item.db.title
            for fname in FIELD_KINDS[item.etype]:
                if fname in fields and fname != "name":
                    body[fname] = fields[fname]
            body.update(ext)
            if item.notion_id is not None:
                body[_EXT_ID] = item.notion_id
            if item.parent is not None and item.parent != item.eid:
                body[_EXT_PARENT] = item.parent
            out.setdefault(item.etype, []).append(body)
            self.report.counts[item.etype] = self.report.counts.get(item.etype, 0) + 1
        self.report.counts = dict(sorted(self.report.counts.items()))
        return out

    def world(self) -> dict[str, Any]:
        tops = [i for i in self.items if i.md is not None and "/" not in i.md and i.db is None]
        name = tops[0].name if len(tops) == 1 else (parse_name(self.tree.root_name)[0] or "Notion export")
        return {
            "id": _uuid(f"world:{self.tree.root_name}"),
            "name": name,
            "format_version": FORMAT_VERSION,
            "producer": {"tool": "onlyworlds", "version": __version__, "input": PRODUCER_INPUT},
        }


def import_notion(
    source: str | os.PathLike[str], out_dir: str | os.PathLike[str] | None, *, plan_only: bool = False
) -> ImportReport:
    """Read the Notion export at ``source`` (a zip, or the directory it was unzipped into) into a
    world folder at ``out_dir``, which must not exist or be empty.

    With ``plan_only`` nothing is written (``out_dir`` may be None) and the report says what would
    be. Raises ``FileExistsError`` for an ``out_dir`` that is not empty, ``FileNotFoundError`` for a
    missing source, ``ValueError`` for a file that is not a zip or an export with nothing to read.
    The folder (``world.json`` and ``elements/``) is written whole through ``write_folder``; the
    attachments are copied into its ``media/notion/`` after.
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
        imp = _Importer(tree, src)
        imp.collect()
        imp.fill()
        elements = imp.bodies()
        world = imp.world()
        report = imp.report
        report.world = world
        report.media = sorted(imp.media.values())
        referenced = set(imp.media)
        for rel in sorted(tree.files):
            if not rel.lower().endswith((".md", ".csv")) and rel not in referenced:
                report.notes.append(f"{rel}: an attachment no page links to; not copied")
        if plan_only:
            return report
        assert out is not None
        write_folder(out, world, elements)
        for rel, dest in sorted(imp.media.items()):
            target = out.joinpath(*dest.split("/"))
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(tree.files[rel]())
        report.out = out
    return report


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="python -m onlyworlds.notion", description=(__doc__ or "").splitlines()[0])
    ap.add_argument("source", type=Path, help="Notion's Markdown & CSV export: the zip, or the directory it unzips to")
    ap.add_argument("out", type=Path, nargs="?", help="the world folder to create; must not exist or be empty")
    ap.add_argument("--plan", action="store_true", help="print what would become what and write nothing")
    args = ap.parse_args(argv)
    if args.out is None and not args.plan:
        print("give OUT-DIR, or --plan", file=sys.stderr)
        return 2
    try:
        report = import_notion(args.source, args.out, plan_only=args.plan)
    except (FileExistsError, FileNotFoundError, ValueError) as exc:
        print(f"{exc}", file=sys.stderr)
        return 2
    sys.stdout.write(report.render())
    return 0


if __name__ == "__main__":
    sys.exit(main())

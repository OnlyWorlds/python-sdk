"""Read a Campfire export into a world folder: no AI, no account, the same folder every time.

    python -m onlyworlds.campfire --file EXPORT.html OUT-DIR [--project NAME] [--plan]

or ``import_campfire(source, out_dir, plan_only=False, project=None)``. ``source`` is the HTML
file Campfire's web app gives (File, Export Elements, the html format; ``Select all Elements``).
``--plan`` prints what would become what and writes nothing. ``--project NAME`` names the world
and keys every id on the project (below). OUT-DIR must not exist yet (or be empty): a folder is
written whole, once, through ``write_folder``.

**A documents door.** Campfire's web app has no data export: Export Elements gives four documents
(docx, pdf, html, rtf), the same text four ways, and this door reads the html. A document has no
ids, no links and no hidden marks, so the folder carries none of them either, and the report says
so on every run (ruled 2026-10-23).

**Proven on one real export** (2026-10-23, a maintainer's project on a free account;
``tests/fixtures/campfire/campfire-export.html``): the document's title (``h1.document-title``,
``Campfire Export``), then one ``section.export-item`` per element: its name in ``h2.item-title``,
its description in ``div.item-description``, then its pages (``section.page-section``, a
``h3.page-title``), each holding panels (``section.panel-section``, a ``h4.panel-header``): a
custom panel (``panel-custom``) is ``dt.attribute-label`` / ``dd.attribute-value`` pairs, a text
panel (``panel-text``) free text. An empty value is an em dash (``span.no-value``) or an empty
paragraph; a number Campfire prints in ``span.number-value``. Campfire leaves a panel with no
content out of the file.

**Believed**, not yet seen in a file: every module but Characters and Locations; a list, stats,
links, image or research panel with content (read as text, below); a second page; an element
made from a template whose panels were renamed.

What becomes what:

- **Each element heading is an element.** The ``h2`` is the name; the description block (one
  paragraph in the real file) is the ``description``, as Markdown.
- **The type**: the file names no module: no Characters or Locations heading, no section word, in
  the html or the docx. What it carries of Campfire's own is each template's panel words, so the
  module is read from them (``TEMPLATE_MODULES``: a panel's header and a label in it, as Campfire's
  template writes them, ``Basic Information`` / ``Place of Residence`` for Characters, ``Location
  Details`` / ``Location Type`` for Locations) and the type from the module (``MODULE_TYPES``, the
  one table, mapped against the OnlyWorlds definitions as the World Anvil door's is; reading the
  module from the panels was ruled 2026-10-23). A module not in ``MODULE_TYPES``
  becomes a Narrative with supertype ``Article`` and the module's name as subtype; an element
  whose panels match no module this door knows, or two, becomes a Narrative with supertype
  ``Article`` and no subtype. The report names, per element, the panel words its module was read
  from (which panel and label matched which module), or that none matched.
- **Panels**: each filled panel's Label / value pairs are kept as ``x_campfire_<panel>_<label>``
  in lower snake case (``x_campfire_basic_information_full_name``), the value as Markdown, a
  number as a number; a panel with no pairs (a text panel) as ``x_campfire_<panel>``. An em dash
  is read as empty and not written, and so is an empty paragraph. No panel value fills an
  OnlyWorlds field, as ruled: the one exception is below.
- **One resolution**: a Character's ``Place of Residence`` whose value equals (exactly, after
  trimming) the name of a Location in the same export becomes the Character's ``location`` link;
  any other stays the ``x_campfire_...`` field. A name inside prose (a Bio naming someone) stays
  prose: no link, no mention, no element made for it.
- **Nothing read past in silence**: text in an element outside the parts above is kept as
  ``x_campfire_unread`` and named in the report; text on the page outside the elements is named.

**No hidden mark**: nothing in the file marks an element hidden, so there is no hidden rule to key
on, and no element carries ``hidden``. **No links**: the file holds no link between elements; the
one link this door makes is the resolution above.

**Ids are UUIDv5** in ``CAMPFIRE_NAMESPACE`` (the file has no ids, so they are derived): the same
export twice gives byte-equal folders, and a second export of the same project gives the same ids
only while the names hold; a renamed element comes in as a new one. The file names no project,
so the project is given or the title stands in:

- **With** ``--project NAME`` (``project=``): each element is keyed ``campfire:<project>:<type>:<name>``,
  the world ``campfire:<project>:world``, and ``world.json``'s ``name`` is the project name.
- **Without**: each element is keyed ``campfire:<type>:<name>``, the world
  ``campfire:world:<title>``, and the world is named for the document's title. Two projects
  exported under Campfire's default title ``Campfire Export`` then share a world id, and any
  elements they name alike share ids; the report says so, and that ``--project`` keys them apart.

A second element of one type and name gets ``:<n>`` on its key and is named in the report; an
exact copy folds into one. ``producer`` is ``{"tool": "onlyworlds", "version": ..., "input":
"campfire-export"}`` (``PRODUCER_INPUT``, on the folder spec's §4.2 list since v0.3.18; the
folder's ``format_version`` is the package's ``FORMAT_VERSION``, 0.3.20 since 0.82.0).

From the command line: exit 0 written (or planned), 2 on bad arguments (no ``--file``, a missing
file, an OUT-DIR that is not empty, a blank ``--project``, a file that is not a Campfire export).
"""

from __future__ import annotations

import argparse
import io
import os
import re
import sys
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ._version import __version__
from .folder import FORMAT_VERSION, write_folder
from .kanka import _blocks, _Node, _Tree

__all__ = [
    "CAMPFIRE_NAMESPACE",
    "EXT_PREFIX",
    "MODULE_TYPES",
    "PRODUCER_INPUT",
    "SEEN_MODULES",
    "TEMPLATE_MODULES",
    "UNTYPED_SUPERTYPE",
    "ElementPlan",
    "Folded",
    "ImportReport",
    "ModuleEvidence",
    "import_campfire",
    "main",
]

#: The ``producer.input`` word for this door, on the folder spec's §4.2 list (v0.3.18).
PRODUCER_INPUT = "campfire-export"

#: The namespace every id this door mints is UUIDv5 in. Fixed for good: changing it would give
#: every element of every re-imported project a new id.
CAMPFIRE_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "https://onlyworlds.com/ns/campfire")

#: Every extension key this door writes starts with this.
EXT_PREFIX = "x_campfire_"

#: The supertype of a Narrative whose module has no OnlyWorlds type: what it is, never where it
#: came from (the World Anvil ruling, 2026-10-23, and the same for Campfire).
UNTYPED_SUPERTYPE = "Article"

#: The most an export may hold, in bytes: a file past it is refused, not read.
MAX_EXPORT_BYTES = 256 * 1024 * 1024

#: Campfire's module -> element type: the one table, keyed lowercased on the module's name as
#: Campfire spells it, each row read against the OnlyWorlds definitions. ``SEEN_MODULES`` were
#: in the real export (their elements, not the word: the file prints no module name); the rest
#: are believed from Campfire's module list (the table as ruled, 2026-10-23).
#: Left out, so an Article Narrative: Timelines, Arcs, Manuscript, Encyclopedia and Research (an
#: author's tools or a mix of kinds, not one thing in the world), and Relationships until a real
#: file shows one with two ends (then Relation).
MODULE_TYPES: dict[str, str] = {
    "characters": "character",  # "an individual with agency and the capacity to make choices"
    "locations": "location",  # "a distinct place within the world where activities occur"
    "species": "species",  # "a distinct biological or cultural form of life"
    "cultures": "species",  # the cultural half of Species, as World Anvil's Ethnicity was ruled
    "items": "object",  # "tangible, non-living things that can be made, owned, traded or destroyed"
    "languages": "language",  # "systems of shared meaning"
    "religions": "construct",  # "structured ideas or systems ... believed or structured"
    "philosophies": "construct",  # the same
    "systems": "construct",  # "structured ideas or systems that the world acknowledges"
    "magic": "construct",  # "a magic system is how the world works, not a thing anyone does"
    "maps": "map",  # "a spatial template"; a document carries no coordinates, only the name and text
}
SEEN_MODULES = frozenset({"characters", "locations"})

#: A template's own panel words -> the module that wrote it: ``(panel header, label)`` pairs,
#: lowercased, as Campfire's default template prints them (each read on the real export). An
#: element is of a module when any pair of its panels is one of that module's.
TEMPLATE_MODULES: dict[str, frozenset[tuple[str, str]]] = {
    "characters": frozenset(
        ("basic information", label)
        for label in ("full name", "origin country", "place of residence", "formal education", "occupation")
    ),
    "locations": frozenset(
        [
            *(
                ("location details", label)
                for label in (
                    "location type",
                    "location age",
                    "created/built by",
                    "date created/built",
                    "purpose of construction",
                )
            ),
            *(
                ("basic information", label)
                for label in (
                    "area",
                    "ethnic groups",
                    "population",
                    "average temperature",
                    "biome",
                    "natural resources",
                )
            ),
        ]
    ),
}

#: The label whose value may become a Character's ``location`` link (the one resolution).
RESIDENCE = "place of residence"

#: The door's own extension keys; a panel never takes one of them.
_RESERVED = frozenset({f"{EXT_PREFIX}unread"})

_SKIP_TAGS = frozenset({"style", "script", "head", "noscript", "template"})
_EM_DASH = chr(0x2014)
_INT = re.compile(r"-?\d+")
_FLOAT = re.compile(r"-?\d+\.\d+")


def _uuid(key: str) -> str:
    return str(uuid.uuid5(CAMPFIRE_NAMESPACE, key))


def _snake(name: str) -> str:
    """Lower snake case: ``Created/Built by`` is ``created_built_by``."""
    return re.sub(r"[^0-9a-z]+", "_", name.casefold()).strip("_")


def _classes(node: _Node) -> set[str]:
    return set(node.attrs.get("class", "").split())


def _walk(node: _Node) -> Iterator[_Node]:
    for c in node.children:
        if isinstance(c, _Node):
            yield c
            yield from _walk(c)


def _find(node: _Node, pred: Callable[[_Node], bool]) -> _Node | None:
    return next((n for n in _walk(node) if pred(n)), None)


def _has(cls: str) -> Callable[[_Node], bool]:
    return lambda n: cls in _classes(n)


def _plain(node: _Node | str) -> str:
    out: list[str] = []

    def go(n: _Node | str) -> None:
        if isinstance(n, str):
            out.append(n)
        elif n.tag not in _SKIP_TAGS:
            for c in n.children:
                go(c)

    go(node)
    return re.sub(r"\s+", " ", "".join(out)).strip()


def _markdown(node: _Node) -> str:
    """A container's children as Markdown (the Kanka door's converter); an em dash alone is empty."""
    text = "\n\n".join(_blocks(node)).strip()
    return "" if text == _EM_DASH else text


# ---------------------------------------------------------------------------
# The report
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ElementPlan:
    """One module (as its template's panels name it) and what its elements became."""

    #: the module's name, as Campfire spells it ('' when no module is known)
    module: str
    type: str
    elements: int
    #: ``seen`` (in a real export), ``believed``, ``untyped`` (a module not in the table) or
    #: ``unknown`` (no module known)
    status: str


@dataclass(frozen=True)
class ModuleEvidence:
    """One element: the panel words its module was read from, and what it became."""

    element: str
    #: the module read ('' when its panels match none, or two)
    module: str
    type: str
    #: (module, panel, label): each of the element's panel words that is one of a module's
    #: ``TEMPLATE_MODULES`` pairs, in the file's order (empty when none matched)
    matched: tuple[tuple[str, str, str], ...]

    def render(self) -> str:
        def words(module: str) -> str:
            return ", ".join(f"{p!r} / {k!r}" for m, p, k in self.matched if m == module)

        modules = sorted({m for m, _, _ in self.matched})
        if self.module:
            how = f"{self.module.capitalize()}, from {words(self.module)}"
        elif modules:
            how = "two modules (" + "; ".join(f"{m.capitalize()} from {words(m)}" for m in modules) + ")"
        else:
            how = "no panel words of a module this door knows"
        if self.module in MODULE_TYPES:
            what = f"a {self.type}"
        else:
            what = f"a Narrative, supertype {UNTYPED_SUPERTYPE}" + (
                f", subtype {self.module.capitalize()}" if self.module else ""
            )
        return f"{self.element!r}: {how}; {what}"


@dataclass(frozen=True)
class Folded:
    """Exact copies folded into one."""

    element: str
    copies: int


@dataclass
class ImportReport:
    source: Path
    world: dict[str, Any]
    #: the project name given (``--project``), which keys every id; None when the title keys them
    project: str | None = None
    counts: dict[str, int] = field(default_factory=dict)
    plans: list[ElementPlan] = field(default_factory=list)
    #: per element, in the file's order: the panel words its module was read from
    evidence: list[ModuleEvidence] = field(default_factory=list)
    #: (element, why): no module known, or a module with no OnlyWorlds type
    untyped: list[tuple[str, str]] = field(default_factory=list)
    #: (element, panel, label or '', kept as): every panel value kept
    kept: list[tuple[str, str, str, str]] = field(default_factory=list)
    #: (element, the value, the Location's name): Place of Residence made a ``location`` link
    resolved: list[tuple[str, str]] = field(default_factory=list)
    #: (element, the value): a Place of Residence that names no Location in the export
    unresolved: list[tuple[str, str]] = field(default_factory=list)
    #: (element, panel, label): an empty value (an em dash, an empty paragraph), not written
    empty: list[tuple[str, str, str]] = field(default_factory=list)
    #: (element, panel, label): a 0 Campfire prints, which may be a number never set
    zeros: list[tuple[str, str, str]] = field(default_factory=list)
    #: (element, the key it got): a second element of one type and name
    renamed: list[tuple[str, str]] = field(default_factory=list)
    folded: list[Folded] = field(default_factory=list)
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
        lines.append(f"Campfire export {self.source} ({name!r}): {self.total} elements ({by_type or 'none'}).")
        keyed = (
            f"the project name ({self.project!r}), its type and its name" if self.project else "its type and its name"
        )
        lines.append(
            "A documents door: the file is a document, not data. It has no ids: each element's id is"
            f" derived from {keyed}, so a second export gives the same ids only while the"
            " names hold, and a renamed element comes in as a new one."
        )
        if self.project:
            lines.append(
                f"The world is named for the project given ({self.project!r}), and its id and every"
                " element's are keyed on it (--project)."
            )
        else:
            lines.append(
                f"The file names no project: the world is named for the document's title ({name!r}) and"
                " keyed on it, and each element on its type and name alone. Two projects exported under"
                " Campfire's default title 'Campfire Export' would share ids: the world's, and those of"
                " any elements they name alike. --project NAME keys them apart."
            )
        lines.append(
            "The file holds no links between elements: none are made, but for a Place of Residence"
            " that names a Location in the export."
        )
        lines.append("Nothing in the file marks an element hidden: no element is written hidden.")
        lines.append(
            "The file names no module: each element's module is read from its template's panel words"
            " (TEMPLATE_MODULES)."
        )
        if self.plans:
            lines.append("What became what:")
            for p in self.plans:
                how = {
                    "seen": "read on a real export",
                    "believed": "believed, not yet seen in a real export",
                    "untyped": f"no OnlyWorlds type: Narratives, supertype {UNTYPED_SUPERTYPE}, the module as subtype",
                    "unknown": f"no module known: Narratives, supertype {UNTYPED_SUPERTYPE}",
                }[p.status]
                label = repr(p.module) if p.module else "no module"
                lines.append(f"  - {label} ({p.elements}): {p.type}; {how}")
        if self.evidence:
            lines.append(f"Each element's module, as its panel words name it ({len(self.evidence)}):")
            lines += [f"  - {ev.render()}" for ev in self.evidence]
        if self.untyped:
            lines.append(f"Not typed ({len(self.untyped)}), each a Narrative with supertype {UNTYPED_SUPERTYPE}:")
            lines += [f"  - {e!r}: {why}" for e, why in self.untyped]
        if self.resolved:
            lines.append(f"Place of Residence made the location link ({len(self.resolved)}):")
            lines += [f"  - {e!r}: {v!r}, the Location of that name" for e, v in self.resolved]
        if self.unresolved:
            lines.append(f"Place of Residence naming no Location in the export ({len(self.unresolved)}), kept as text:")
            lines += [f"  - {e!r}: {v!r}" for e, v in self.unresolved]
        if self.kept:
            lines.append(f"Panel values kept as extensions ({len(self.kept)}; no panel fills an OnlyWorlds field):")
            lines += [f"  - {e!r} / {p!r}" + (f" / {k!r}" if k else "") + f": {x}" for e, p, k, x in self.kept]
        if self.zeros:
            lines.append(
                f"Numbers printed 0 ({len(self.zeros)}), kept as 0: Campfire prints 0 for a number never set,"
                " so the file cannot tell the two apart"
            )
            lines += [f"  - {e!r} / {p!r} / {k!r}" for e, p, k in self.zeros]
        if self.empty:
            lines.append(f"Empty (an em dash or an empty paragraph), not written ({len(self.empty)}):")
            lines += [f"  - {e!r} / {p!r}" + (f" / {k!r}" if k else "") for e, p, k in self.empty]
        if self.folded:
            lines.append(f"Exact duplicates folded into one ({len(self.folded)}):")
            lines += [f"  - {f.element!r}: {f.copies} identical copies, kept once" for f in self.folded]
        if self.renamed:
            lines.append(f"A second element of one type and name ({len(self.renamed)}), keyed apart:")
            lines += [f"  - {e!r}: id from {k!r}" for e, k in self.renamed]
        if self.notes:
            lines.append(f"Notes ({len(self.notes)}):")
            lines += [f"  - {n}" for n in self.notes]
        lines.append(f"Wrote {self.out}." if self.out is not None else "Plan only: nothing written.")
        return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# The import
# ---------------------------------------------------------------------------


@dataclass
class _Value:
    panel: str
    #: '' for a panel with no pairs
    label: str
    value: Any


@dataclass
class _Item:
    node: _Node
    name: str
    description: str
    values: list[_Value]
    #: (panel, label) of every value, filled or empty, in the file's order: Campfire's template
    #: words, read for the module
    words: list[tuple[str, str]] = field(default_factory=list)
    module: str = ""
    etype: str = "narrative"
    eid: str = ""
    consumed: set[int] = field(default_factory=set)


class _Importer:
    def __init__(self, html: str, source: Path, project: str | None = None) -> None:
        tree = _Tree()
        tree.feed(html)
        tree.close()
        self.root = tree.root
        self.project = project
        self.report = ImportReport(source=source, world={}, project=project)
        self.items: list[_Item] = []
        self.page_consumed: set[int] = set()
        self.pages = 0

    # -- pass 1: each element, its panels, its module and type ----------------

    def collect(self) -> None:
        sections = [n for n in _walk(self.root) if n.tag == "section" and "export-item" in _classes(n)]
        if not sections:
            raise ValueError(f"{self.report.source}: not a Campfire export (no export-item section)")
        raw: dict[str, int] = {}
        seen: dict[str, _Item] = {}
        for node in sections:
            self.page_consumed.add(id(node))
            text = _plain(node)
            if text in raw:
                raw[text] += 1
                continue
            raw[text] = 1
            item = self._element(node)
            seen[text] = item
            self.items.append(item)
        for text, n in raw.items():
            if n > 1:
                self.report.folded.append(Folded(seen[text].name, n))
        self._type()
        self._ids()

    def _element(self, node: _Node) -> _Item:
        consumed: set[int] = set()
        title = _find(node, _has("item-title"))
        name = _plain(title) if title is not None else ""
        if title is not None:
            consumed.add(id(title))
        if not name:
            name = f"Untitled ({len(self.items) + 1})"
            self.report.notes.append(f"an element with no heading; named {name!r}")
        desc = _find(node, _has("item-description"))
        description = ""
        if desc is not None:
            consumed.add(id(desc))
            description = _markdown(desc)
        item = _Item(node, name, description, [], consumed=consumed)
        for page in (n for n in _walk(node) if "page-section" in _classes(n)):
            self.pages += 1
            ptitle = _find(page, _has("page-title"))
            if ptitle is not None:
                item.consumed.add(id(ptitle))
                if _plain(ptitle) != "Overview":
                    self.report.notes.append(
                        f"{name!r}: a page {_plain(ptitle)!r} (its panels are read; its name is not kept)"
                    )
        for panel in (n for n in _walk(node) if "panel-section" in _classes(n)):
            self._panel(item, panel)
        return item

    def _panel(self, item: _Item, panel: _Node) -> None:
        head = _find(panel, _has("panel-header"))
        heading = _plain(head) if head is not None else ""
        if head is not None:
            item.consumed.add(id(head))
        content = _find(panel, _has("panel-content")) or panel
        item.consumed.add(id(content))
        rows = [n for n in _walk(content) if "attribute-row" in _classes(n)]
        kind = next((c for c in sorted(_classes(panel)) if c.startswith("panel-") and c != "panel-section"), "")
        if kind not in ("panel-custom", "panel-text", ""):
            self.report.notes.append(
                f"{item.name!r} / {heading!r}: a {kind} panel, not yet seen in a real export; read as text"
            )
        if not rows:
            text = _markdown(content)
            if text:
                item.words.append((heading, ""))
                item.values.append(_Value(heading, "", text))
            else:
                self._empty(item, heading, "")
            return
        for row in rows:
            dt = _find(row, _has("attribute-label"))
            dd = _find(row, _has("attribute-value"))
            label = _plain(dt) if dt is not None else ""
            if dd is None:
                self._empty(item, heading, label)
                continue
            number = _find(dd, _has("number-value"))
            if number is not None and _plain(number) == _plain(dd):
                printed = _plain(number)
                value: Any = (
                    int(printed)
                    if _INT.fullmatch(printed)
                    else float(printed)
                    if _FLOAT.fullmatch(printed)
                    else printed
                )
                if value == 0:
                    self.report.zeros.append((item.name, heading, label))
            else:
                value = _markdown(dd)
            if value == "":
                self._empty(item, heading, label)
                continue
            item.words.append((heading, label))
            item.values.append(_Value(heading, label, value))

    def _empty(self, item: _Item, panel: str, label: str) -> None:
        item.words.append((panel, label))
        self.report.empty.append((item.name, panel, label))

    def _type(self) -> None:
        plans: dict[tuple[str, str, str], int] = {}
        for item in self.items:
            matched = tuple(
                (m, p, k)
                for p, k in dict.fromkeys(item.words)
                for m, sig in sorted(TEMPLATE_MODULES.items())
                if (p.casefold(), k.casefold()) in sig
            )
            hits = sorted({m for m, _, _ in matched})
            if len(hits) == 1:
                item.module = hits[0]
            elif hits:
                self.report.notes.append(f"{item.name!r}: its panels name two modules ({', '.join(hits)}): untyped")
            if item.module in MODULE_TYPES:
                item.etype = MODULE_TYPES[item.module]
                status = "seen" if item.module in SEEN_MODULES else "believed"
            elif item.module:
                status = "untyped"
                self.report.untyped.append((item.name, f"the module {item.module!r} has no OnlyWorlds type"))
            else:
                status = "unknown"
                self.report.untyped.append((item.name, "its panels name no module this door knows"))
            self.report.evidence.append(ModuleEvidence(item.name, item.module, item.etype, matched))
            key = (item.module.capitalize(), item.etype, status)
            plans[key] = plans.get(key, 0) + 1
        for (module, etype, status), n in sorted(plans.items()):
            self.report.plans.append(ElementPlan(module, etype, n, status))

    def _ids(self) -> None:
        scope = f"campfire:{self.project}:" if self.project is not None else "campfire:"
        taken: dict[tuple[str, str], int] = {}
        for item in self.items:
            n = taken.get((item.etype, item.name), 0) + 1
            taken[(item.etype, item.name)] = n
            key = f"{scope}{item.etype}:{item.name}" + (f":{n}" if n > 1 else "")
            if n > 1:
                self.report.renamed.append((item.name, key))
            item.eid = _uuid(key)

    # -- pass 2: the bodies -----------------------------------------------------

    def bodies(self) -> dict[str, list[dict[str, Any]]]:
        places: dict[str, list[_Item]] = {}
        for item in self.items:
            if item.etype == "location":
                places.setdefault(item.name, []).append(item)
        out: dict[str, list[dict[str, Any]]] = {}
        for item in self.items:
            body: dict[str, Any] = {"type": item.etype, "id": item.eid, "name": item.name}
            if item.description:
                body["description"] = item.description
            if item.etype == "narrative" and item.module not in MODULE_TYPES:
                body["supertype"] = UNTYPED_SUPERTYPE
                if item.module:
                    body["subtype"] = item.module.capitalize()
            taken = set(_RESERVED)
            for v in item.values:
                if item.etype == "character" and v.label.casefold() == RESIDENCE and "location" not in body:
                    text = v.value.strip() if isinstance(v.value, str) else v.value
                    hits = places.get(text, []) if isinstance(text, str) else []
                    if len(hits) == 1:
                        body["location"] = hits[0].eid
                        self.report.resolved.append((item.name, text))
                        continue
                    self.report.unresolved.append((item.name, str(v.value)))
                    if len(hits) > 1:
                        self.report.notes.append(f"{item.name!r}: {len(hits)} Locations are named {text!r}; not linked")
                base = f"{EXT_PREFIX}{'_'.join(s for s in (_snake(v.panel), _snake(v.label)) if s) or 'value'}"
                key, n = base, 2
                while key in taken:
                    key, n = f"{base}_{n}", n + 1
                taken.add(key)
                body[key] = v.value
                self.report.kept.append((item.name, v.panel, v.label, key))
            self._guard(item, body)
            out.setdefault(item.etype, []).append(body)
        self.report.counts = {t: len(b) for t, b in sorted(out.items())}
        self._page_guard()
        if self.pages:
            self.report.notes.append(f"{self.pages} page(s) of panels; a page's name is layout, not kept")
        return out

    def _leftover(self, node: _Node, consumed: set[int]) -> list[str]:
        out: list[str] = []
        for c in node.children:
            if isinstance(c, str):
                if c.strip():
                    out.append(c)
            elif id(c) not in consumed and c.tag not in _SKIP_TAGS:
                out += self._leftover(c, consumed)
        return out

    def _guard(self, item: _Item, body: dict[str, Any]) -> None:
        rest = re.sub(r"\s+", " ", " ".join(self._leftover(item.node, item.consumed))).strip()
        if rest:
            body[f"{EXT_PREFIX}unread"] = rest
            self.report.notes.append(
                f"{item.name!r}: text outside the parts this door reads, kept as x_campfire_unread"
            )

    def _page_guard(self) -> None:
        title = _find(self.root, _has("document-title"))
        if title is not None:
            self.page_consumed.add(id(title))
        rest = re.sub(r"\s+", " ", " ".join(self._leftover(self.root, self.page_consumed))).strip()
        if rest:
            self.report.notes.append(f"text on the page outside the elements, not imported: {rest!r}")

    def world(self) -> dict[str, Any]:
        title = _find(self.root, _has("document-title"))
        name = _plain(title) if title is not None else ""
        if self.project is not None:
            key, name = f"campfire:{self.project}:world", self.project
        else:
            if not name:
                name = "Campfire Export"
                self.report.notes.append(f"the export names no title; named {name!r}")
            key = f"campfire:world:{name}"
        return {
            "id": _uuid(key),
            "name": name,
            "format_version": FORMAT_VERSION,
            "producer": {"tool": "onlyworlds", "version": __version__, "input": PRODUCER_INPUT},
        }


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
        raise ValueError(f"{path}: not a Campfire export (not UTF-8 HTML)") from None


def import_campfire(
    source: str | os.PathLike[str],
    out_dir: str | os.PathLike[str] | None,
    *,
    plan_only: bool = False,
    project: str | None = None,
) -> ImportReport:
    """Read the Campfire export at ``source`` (Export Elements, the html) into a world folder at
    ``out_dir``, which must not exist or be empty.

    With ``plan_only`` nothing is written (``out_dir`` may be None) and the report says what would
    be. ``project`` names the world and keys every id on it (``campfire:<project>:<type>:<name>``,
    ``campfire:<project>:world``); without it the ids are keyed as the module docstring says.
    Raises ``FileExistsError`` for an ``out_dir`` that is not empty, ``FileNotFoundError`` for a
    missing file, ``ValueError`` for a blank ``project`` or a file that is not a Campfire export.
    """
    if project is not None:
        project = project.strip()
        if not project:
            raise ValueError("--project: give the project's name (it names the world and keys every id)")
    src = Path(source)
    out = Path(out_dir) if out_dir is not None else None
    if not plan_only:
        if out is None:
            raise ValueError("give an out_dir, or plan_only=True")
        if out.exists() and (not out.is_dir() or any(out.iterdir())):
            raise FileExistsError(f"{out} exists and is not an empty directory; a folder is written whole, once")
    imp = _Importer(_read(src), src, project)
    imp.collect()
    imp.report.world = imp.world()
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
    ap = argparse.ArgumentParser(prog="python -m onlyworlds.campfire", description=(__doc__ or "").splitlines()[0])
    ap.add_argument("out", type=Path, nargs="?", help="the world folder to create; must not exist or be empty")
    ap.add_argument("--file", type=Path, help="Campfire's export (File, Export Elements, html)")
    ap.add_argument(
        "--project",
        metavar="NAME",
        help="the project's name: names the world and keys every id on it, so two projects exported"
        " under one title (Campfire's default, 'Campfire Export') stay apart",
    )
    ap.add_argument("--plan", action="store_true", help="print what would become what and write nothing")
    args = ap.parse_args(argv)
    if args.file is None:
        print("give --file EXPORT.html (Campfire's File, Export Elements, as html)", file=sys.stderr)
        return 2
    if args.out is None and not args.plan:
        print("give OUT-DIR, or --plan", file=sys.stderr)
        return 2
    try:
        report = import_campfire(args.file, args.out, plan_only=args.plan, project=args.project)
    except (FileExistsError, FileNotFoundError, ValueError) as exc:
        print(f"{exc}", file=sys.stderr)
        return 2
    sys.stdout.write(report.render())
    return 0


if __name__ == "__main__":
    sys.exit(main())

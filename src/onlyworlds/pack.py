"""The Markdown pack: a world as a few merged Markdown files, sized for an AI notebook's sources.

    python -m onlyworlds.pack PATH/TO/WORLD-FOLDER OUT-DIR [--words N] [--bytes N] [--files N]
    python -m onlyworlds.pack --api OUT-DIR [--base-url URL] [--words N] [--bytes N] [--files N]

with ``--rooms`` and ``--extensions`` on either, or ``pack_folder``, ``pack_api`` and ``pack_world``
from Python. A person uploads the files into a notebook and asks about their world. The caps fit
NotebookLM (50 sources per notebook, 500,000 words per source: Google's FAQ) and Claude Projects
(30 MB per file), with a margin: by default 400,000 words, 25,000,000 bytes and 50 files.

The overlap, said once. OKF (``onlyworlds.okf``) writes one concept per element, with frontmatter
and relative links, for knowledge tools like Obsidian; the pack writes merged prose that names
elements instead of linking paths, for notebooks that cap their sources. The toolkit's context skill
says how a session should load a world and names no file shape; the pack is one such shape.

The files, in OUT-DIR (which must not exist), named so they sort:

    00-world.md          the world's own fields, then an index: one line per element, by type
    01-character.md      one file per element type present, in schema order; the number is
    02-location.md       the file's place in the list, not the type's

Each element is ``## <Name>``, then ``*<Type> · id <id> · <supertype> / <subtype>*`` (the parts
that are set), then its description and its type's fields in schema order, then its picture's
URL: text as ``**<Field>:**`` with the text on the lines below (a line markdown would read as a
heading is escaped, as okf escapes it), an integer and a link on one line. A link is written as
the target's name and type, ``Ann (character)``, resolved against the whole world read; an id the
world does not hold is written ``<id> (unresolved)`` and listed in ``PackReport.unresolved``. An
in-prose reference, ``[Label](ow://<type>/<id>)``, becomes the label, with the target's name
after it in brackets when the two differ. A known-of stub (folder format §4.4) says so under its
id line: its missing fields are unknown, not empty. Nothing is invented and an unset field is
left out.

Left out unless asked: room elements (the room profile, ``room.is_room_element``; ``--rooms``
keeps them) and extension keys (``x_``, ``atlas_``, ``shadow_``; ``--extensions`` keeps them),
each counted in the report. Server keys (``push.NOT_SENT``) are never written; a key that is not
a field of its type is a note.

Sizing. A type's file past ``--words`` (whitespace-split) or ``--bytes`` (UTF-8) is split at
element boundaries into ``NN-<type>-1.md``, ``NN-<type>-2.md``, ... each headed ``(part k of n)``;
the world file past a cap splits the same way at index lines (``00-world-1.md``, ...).
When there are then more files than ``--files``, adjacent unsplit type files are merged, the
smallest pair first, while the merged file stays under both caps (``03-object-construct.md``;
past four types, ``03-object-to-zone.md``). When that cannot reach ``--files`` every file is still
written and ``PackReport.files_over`` is set: no element is ever left out to meet a cap. One
element past a cap is written alone in its own file, whole, and named in ``PackReport.oversize``.

The output is deterministic: the same world gives the same bytes (UTF-8, LF, no timestamp of the
run). Within a type, elements go by name, then id. From the command line: exit 0 written, 1 when
the files are more than ``--files``, 2 on bad arguments or nothing read.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ._markdown import escape_text, heading, one_line
from ._schema import (
    BASE_FIELDS,
    ELEMENT_TYPES,
    EXTENSION_PREFIXES,
    FIELD_KINDS,
    GENERIC_LINKS,
    LINK_TARGETS,
    SECTIONS,
    WORLD_FIELDS,
)
from .doctor import _LEGACY_LINK_SPELLINGS, Reader, _list_all
from .errors import ApiError
from .export import exported_as as _exported_as
from .folder import KNOWN_OF, WORLD_FILE, Folder, is_known_of, read_folder
from .http import API_BASE, Client
from .push import NOT_SENT
from .room import is_room_element

__all__ = [
    "DEFAULT_BYTES",
    "DEFAULT_FILES",
    "DEFAULT_WORDS",
    "PackError",
    "PackReport",
    "build_pack",
    "main",
    "pack_api",
    "pack_folder",
    "pack_world",
]

#: The default caps: under NotebookLM's 500,000 words per source and 50 sources per notebook, and
#: Claude Projects' 30 MB per file, with a margin.
DEFAULT_WORDS = 400_000
DEFAULT_BYTES = 25_000_000
DEFAULT_FILES = 50

WORLD_NAME = "00-world.md"
KNOWN_OF_LINE = "*Known of: only the fields shown are known; a field missing here is unknown, not empty.*"
INTRO_LINE = (
    "*An OnlyWorlds world in Markdown. This file holds the world's own fields and an index of its elements; "
    "the other files hold the elements, by type. A link between elements is written as the name and type "
    "of the element it points to.*"
)


def made_by_line(exported_as: Mapping[str, Any] | None) -> str | None:
    """The one line saying which kind of key made the pack (a label, never a fix: a pack holds only
    what its key was served; Boss's four-way walk, h58 #10628). From the folder's ``exported_as``
    (spec 4.2) or ``/me`` on the API; None, and no line, when the slice is not known. Never the key."""
    if not isinstance(exported_as, Mapping):
        return None
    kind, role = exported_as.get("kind"), exported_as.get("role")
    if kind == "owner":
        return "*Made with the owner's key: the whole world.*"
    if kind == "member" and isinstance(role, str) and role:
        return f"*Made with a member's key ({role.replace('_', '-')}): that member's view of the world.*"
    if kind == "character":
        ch = exported_as.get("character")
        name = ch.get("name") if isinstance(ch, Mapping) else None
        who = f"the Character {name}" if isinstance(name, str) and name else "a Character"
        return f"*Made as {who}: that Character's view, not the whole world.*"
    if kind == "public":
        return "*Made from the public view: only what the world shows everyone.*"
    return None


#: A merged file past this many types is named by its first and last type.
_NAME_TYPES = 4
#: An index line's first sentence is cut at this many characters.
_INDEX_CHARS = 240

PLURALS: dict[str, str] = {
    "ability": "Abilities", "character": "Characters", "collective": "Collectives", "construct": "Constructs",
    "creature": "Creatures", "event": "Events", "family": "Families", "institution": "Institutions",
    "language": "Languages", "law": "Laws", "location": "Locations", "map": "Maps", "marker": "Markers",
    "narrative": "Narratives", "object": "Objects", "phenomenon": "Phenomena", "pin": "Pins",
    "relation": "Relations", "species": "Species", "title": "Titles", "trait": "Traits", "zone": "Zones",
}  # fmt: skip

Note = Callable[[str], None]


class PackError(ValueError):
    """The source cannot be packed: no world could be read."""


@dataclass
class PackReport:
    """What a pack did. ``notes`` are what it left out or chose, one line each, in order."""

    #: the file names, in order (``00-world.md`` first)
    files: list[str] = field(default_factory=list)
    elements: int = 0
    types: int = 0
    #: totals over every file: whitespace-split words, UTF-8 bytes
    words: int = 0
    bytes: int = 0
    rooms_left_out: int = 0
    #: extension keys with a value, on elements and the world, not written (no ``--extensions``)
    extensions_left_out: int = 0
    #: elements written as known-of stubs (§4.4)
    known_of: int = 0
    #: ``<type> <name> (<id>): `<field>` -> <id>`` for each link to an id the world does not hold
    unresolved: list[str] = field(default_factory=list)
    #: files past ``words`` or ``bytes`` (one element alone, or the world's index)
    oversize: list[str] = field(default_factory=list)
    #: True when the files are more than ``files`` even after merging
    files_over: bool = False
    notes: list[str] = field(default_factory=list)
    out: Path | None = None


# --- values and names


def _set(value: Any) -> bool:
    return not (value is None or value == "" or value == [] or value == {})


def _name(body: Mapping[str, Any]) -> str:
    return one_line(body.get("name") or "") or "(unnamed)"


def _scalar(value: Any) -> str:
    """A non-text value on one line: a string or a number as itself, a list of them joined, the rest as JSON."""
    if isinstance(value, str):
        return one_line(value)
    if isinstance(value, int | float) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, list) and all(isinstance(v, str | int | float) and not isinstance(v, bool) for v in value):
        return ", ".join(one_line(v) for v in value)
    return json.dumps(value, ensure_ascii=False)


def _kind(body: Mapping[str, Any]) -> str:
    return " / ".join(one_line(body[k]) for k in ("supertype", "subtype") if _set(body.get(k)))


# An in-prose element reference (folder format, in-prose references; atlas `src/core/ow-links.ts`).
_OW_REF = re.compile(r"\[([^\]\n]*)\]\(ow://([A-Za-z_]+)/([\w-]+)\)")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s")


class _World:
    """The names every link resolves to (the whole world read, room elements too), and the report."""

    def __init__(self, everything: Iterable[tuple[str, Mapping[str, Any]]], report: PackReport, note: Note):
        self.names: dict[str, tuple[str, str]] = {}
        for slug, body in everything:
            self.names[body["id"]] = (_name(body), slug)
        self.report, self.note = report, note
        self.unknown: Counter[tuple[str, str]] = Counter()

    def link(self, here: str, name: str, eid: Any, target: str | None) -> str | None:
        if not isinstance(eid, str) or not eid:
            self.note(f"{here}: `{name}` holds {eid!r}, not an id; left out")
            return None
        if eid not in self.names:
            self.report.unresolved.append(f"{here}: `{name}` -> {eid}")
            return f"{eid} (unresolved)"
        title, actual = self.names[eid]
        if target and actual != target:
            self.note(f"{here}: `{name}` -> a {actual}, where the schema expects a {target}; written as it is")
        return f"{title} ({actual})"

    def prose(self, text: str, here: str | None = None, name: str = "") -> str:
        """In-prose references as words. ``here`` None (the index) reports nothing."""

        def swap(m: re.Match[str]) -> str:
            label, eid = one_line(m.group(1)), m.group(3)
            if eid not in self.names:
                if here is None:
                    return label or eid
                self.report.unresolved.append(f"{here}: `{name}` (prose) -> {eid}")
                return m.group(0)
            title = self.names[eid][0]
            if not label or label.casefold() == title.casefold():
                return title if not label else m.group(1)
            return f"{m.group(1)} ({title})"

        return _OW_REF.sub(swap, text)

    def first_sentence(self, text: Any) -> str:
        line = one_line(self.prose(str(text)))
        line = _SENTENCE_END.split(line, maxsplit=1)[0]
        if len(line) > _INDEX_CHARS:
            line = line[:_INDEX_CHARS].rsplit(" ", 1)[0] + " …"
        return line


# --- one element


def element_block(slug: str, body: Mapping[str, Any], w: _World, *, extensions: bool) -> str:
    """One element as its ``## <Name>`` section, ending in one LF."""
    eid = body["id"]
    title = _name(body)
    here = f"{slug} {title} ({eid})"
    meta = [slug.capitalize(), f"id {eid}"]
    if _kind(body):
        meta.append(_kind(body))
    head = [f"## {title}", "*" + " · ".join(meta) + "*"]
    if is_known_of(body):
        head.append(KNOWN_OF_LINE)
        w.report.known_of += 1

    kinds = FIELD_KINDS[slug]
    targets = LINK_TARGETS.get(slug, {})
    generic = GENERIC_LINKS.get(slug, {})
    legacy = _LEGACY_LINK_SPELLINGS.get(slug, {})
    known = {*BASE_FIELDS, *kinds, *NOT_SENT, KNOWN_OF, *legacy}
    fields: list[str] = []

    def text(name: str, value: Any) -> None:
        if str(value).strip():
            fields.append(f"**{heading(name)}:**\n{escape_text(w.prose(str(value), here, name))}")

    def links(name: str, ids: list[Any], target: str | None) -> None:
        shown = [s for s in (w.link(here, name, v, target) for v in ids) if s]
        if shown:
            fields.append(f"**{heading(name)}:** " + ", ".join(shown))

    if _set(body.get("description")):
        text("description", body["description"])
    for _section, names in SECTIONS[slug]:
        for name in names:
            if name in generic:
                type_key, id_key = generic[name]
                known.update((type_key, id_key))
                if _set(body.get(id_key)):
                    target = body.get(type_key)
                    links(name, [body[id_key]], target if target in ELEMENT_TYPES else None)
                continue
            value = body.get(name)
            if not _set(value):
                value = next((body.get(k) for k, v in legacy.items() if v == name and _set(body.get(k))), None)
            if not _set(value):
                continue
            kind = kinds.get(name)
            if kind == "text":
                text(name, value)
            elif kind == "integer":
                fields.append(f"**{heading(name)}:** {_scalar(value)}")
            elif kind == "single_link":
                links(name, [value], targets.get(name))
            elif kind == "multi_link":
                if isinstance(value, list):
                    links(name, value, targets.get(name))
                else:
                    w.note(f"{here}: `{name}` is not a list; left out")
            else:
                w.note(f"{here}: `{name}` has kind `{kind}`, which the pack does not know; left out")
    if _set(body.get("image_url")):
        fields.append(f"**{heading('image_url')}:** {_scalar(body['image_url'])}")

    for key, value in body.items():
        if key.startswith(EXTENSION_PREFIXES):
            if not _set(value):
                continue
            if extensions:
                fields.append(_extension(key, value))
            else:
                w.report.extensions_left_out += 1
        elif key not in known:
            w.unknown[(slug, key)] += 1

    return "\n".join(head) + "\n" + "".join(f"\n{f}\n" for f in fields)


def _extension(key: str, value: Any) -> str:
    if isinstance(value, str) and "\n" in value.strip():
        return f"**{key}:**\n{escape_text(value)}"
    return f"**{key}:** {_scalar(value)}"


# --- the world file


def _time_current(world: Mapping[str, Any]) -> Any:
    """Folder format §5: both spellings, a non-null ``time_current`` first (as ``Folder.time_current``)."""
    if world.get("time_current") is not None:
        return world["time_current"]
    if "time_range_current" in world:
        return world["time_range_current"]
    return world.get("time_current")


def _world_fields(world: Mapping[str, Any], w: _World, *, extensions: bool) -> str:
    """The world's schema fields (unset ones left out), each a paragraph, then its extension keys if asked."""
    fields: list[str] = []
    for name in WORLD_FIELDS:
        if name == "name":
            continue
        value = _time_current(world) if name == "time_current" else world.get(name)
        if not _set(value):
            continue
        if name == "description":
            if str(value).strip():
                fields.append(f"**{heading(name)}:**\n{escape_text(w.prose(str(value), 'world', name))}")
        else:
            fields.append(f"**{heading(name)}:** {_scalar(value)}")
    for key, value in world.items():
        if key.startswith(EXTENSION_PREFIXES) and _set(value):
            if extensions:
                fields.append(_extension(key, value))
            else:
                w.report.extensions_left_out += 1
    return "".join(f"{f}\n\n" for f in fields)


def _index_line(body: Mapping[str, Any], w: _World) -> str:
    line = f"- **{_name(body)}**"
    if _kind(body):
        line += f" ({_kind(body)})"
    first = w.first_sentence(body["description"]) if _set(body.get("description")) else ""
    return f"{line}: {first}" if first else line


#: A world part's first member when it holds the world's fields (for the oversize note).
_WORLD_FIELDS_MEMBER = "the world's own fields"


def world_parts(
    world: Mapping[str, Any],
    title: str,
    index: Mapping[str, list[Mapping[str, Any]]],
    w: _World,
    *,
    extensions: bool,
    words: int,
    bytes_: int,
    exported_as: Mapping[str, Any] | None = None,
) -> list[_Part]:
    """00-world.md: the world's fields, then the index, one line per element by type. Past a cap,
    parts at index-line boundaries: the fields in the first, each later part headed
    ``## Index (continued)``, a type's heading repeated ``(continued)`` where it runs on."""
    fields = _world_fields(world, w, extensions=extensions)
    made = made_by_line(exported_as)
    intro = f"{INTRO_LINE}\n\n{made}" if made else INTRO_LINE
    items = [(slug, _name(b), _index_line(b, w) + "\n") for slug in ELEMENT_TYPES for b in index.get(slug, [])]

    def head(k: int, n: int) -> str:
        top = f"# {title}" + (f" (part {k} of {n})" if n > 1 else "")
        return f"{top}\n\n{intro}\n\n{fields}## Index\n" if k == 1 else f"{top}\n\n## Index (continued)\n"

    def type_head(slug: str, continued: bool) -> str:
        return f"\n### {PLURALS.get(slug, slug.capitalize())}{' (continued)' if continued else ''}\n\n"

    def render(groups: list[list[int]]) -> list[_Part]:
        parts, started = [], set()
        for k, group in enumerate(groups, 1):
            text, members, last = [head(k, len(groups))], [_WORLD_FIELDS_MEMBER] if k == 1 else [], None
            for i in group:
                slug, name, line = items[i]
                if slug != last:
                    text.append(type_head(slug, slug in started))
                    started.add(slug)
                    last = slug
                text.append(line)
                members.append(name)
            joined = "".join(text)
            parts.append(_Part(joined, *_count(joined), members))
        return parts

    whole = render([list(range(len(items)))])
    if not items or (whole[0].words <= words and whole[0].bytes <= bytes_):
        return whole
    digits = "9" * len(str(len(items) + 1))
    probe = f"{title} (part {digits} of {digits})"
    first_head = _count(f"# {probe}\n\n{intro}\n\n{fields}## Index\n")
    later_head = _count(f"# {probe}\n\n## Index (continued)\n")
    groups: list[list[int]] = []
    cur: list[int] = []
    (cur_w, cur_b), holds_fields, last = first_head, True, None
    for i, (slug, _member, line) in enumerate(items):
        lw, lb = _count(line)
        th_w, th_b = _count(type_head(slug, True))  # the longer heading: the sizing never falls short
        add_w, add_b = (lw + th_w, lb + th_b) if slug != last else (lw, lb)
        if (cur or holds_fields) and (cur_w + add_w > words or cur_b + add_b > bytes_):
            groups.append(cur)
            cur, (cur_w, cur_b), holds_fields = [], later_head, False
            add_w, add_b = lw + th_w, lb + th_b
        cur.append(i)
        cur_w, cur_b, last = cur_w + add_w, cur_b + add_b, slug
    groups.append(cur)
    return render(groups)


# --- sizing


@dataclass
class _Part:
    text: str
    words: int
    bytes: int
    #: the names of the elements in it (one: an element alone)
    members: list[str]


@dataclass
class _Unit:
    slugs: list[str]
    parts: list[_Part]


def _count(text: str) -> tuple[int, int]:
    return len(text.split()), len(text.encode("utf-8"))


def _split(title: str, blocks: list[tuple[str, str]], words: int, bytes_: int) -> list[_Part]:
    """A type's file, or its parts at element boundaries when it is past a cap. ``blocks`` are
    (element name, block text). An element past a cap alone is a part alone."""

    def doc(head: str, group: list[tuple[str, str]]) -> _Part:
        text = f"# {head}\n\n" + "\n".join(b for _, b in group)
        return _Part(text, *_count(text), [n for n, _ in group])

    whole = doc(title, blocks)
    if (whole.words <= words and whole.bytes <= bytes_) or len(blocks) == 1:
        return [whole]
    digits = "9" * len(str(len(blocks)))
    head_w, head_b = _count(f"# {title} (part {digits} of {digits})\n\n")
    sizes = [_count(b) for _, b in blocks]
    groups: list[list[int]] = []
    cur: list[int] = []
    cur_w, cur_b = head_w, head_b
    for i, (bw, bb) in enumerate(sizes):
        join = 1 if cur else 0  # the blank line between two blocks
        if cur and (cur_w + bw > words or cur_b + join + bb > bytes_):
            groups.append(cur)
            cur, cur_w, cur_b, join = [], head_w, head_b, 0
        cur.append(i)
        cur_w, cur_b = cur_w + bw, cur_b + join + bb
    groups.append(cur)
    n = len(groups)
    return [doc(f"{title} (part {k} of {n})", [blocks[i] for i in g]) for k, g in enumerate(groups, 1)]


def _merge(units: list[_Unit], files: int, words: int, bytes_: int) -> bool:
    """Merge adjacent unsplit units, the smallest pair first, while the result fits both caps,
    until there are at most ``files`` files (one for the world counted). False when it cannot."""
    total = 1 + sum(len(u.parts) for u in units)
    while total > files:
        best: tuple[int, int] | None = None
        for i in range(len(units) - 1):
            a, b = units[i], units[i + 1]
            if len(a.parts) != 1 or len(b.parts) != 1:
                continue
            pa, pb = a.parts[0], b.parts[0]
            mw, mb = pa.words + pb.words, pa.bytes + 1 + pb.bytes
            if mw <= words and mb <= bytes_ and (best is None or mb < best[0]):
                best = (mb, i)
        if best is None:
            return False
        i = best[1]
        a, b = units[i], units.pop(i + 1)
        pa, pb = a.parts[0], b.parts[0]
        merged = pa.text + "\n" + pb.text
        a.parts = [_Part(merged, pa.words + pb.words, pa.bytes + 1 + pb.bytes, pa.members + pb.members)]
        a.slugs += b.slugs
        total -= 1
    return True


def _unit_name(slugs: list[str]) -> str:
    return "-".join(slugs) if len(slugs) <= _NAME_TYPES else f"{slugs[0]}-to-{slugs[-1]}"


# --- the pack


def build_pack(
    world: Mapping[str, Any],
    elements: Iterable[tuple[str, Mapping[str, Any]]],
    *,
    words: int = DEFAULT_WORDS,
    bytes_: int = DEFAULT_BYTES,
    files: int = DEFAULT_FILES,
    rooms: bool = False,
    extensions: bool = False,
    note: Note | None = None,
    exported_as: Mapping[str, Any] | None = None,
) -> tuple[dict[str, str], PackReport]:
    """Every file as {name: text}, in order, and the report. Writes nothing.

    ``elements`` are (type slug, body). ``note`` is called with each note as it is made (they are
    also in ``report.notes``). ``exported_as`` (spec 4.2's line, or None) puts one line in the world
    file saying which kind of key made the pack. Raises ValueError when a cap is below 1.
    """
    for flag, cap in (("words", words), ("bytes", bytes_), ("files", files)):
        if not isinstance(cap, int) or cap < 1:
            raise ValueError(f"{flag} must be a whole number of at least 1, got {cap!r}")
    report = PackReport()

    def noted(msg: str) -> None:
        report.notes.append(msg)
        if note is not None:
            note(msg)

    valid: list[tuple[str, Mapping[str, Any]]] = []
    for slug, body in elements:
        eid = body.get("id")
        if slug not in ELEMENT_TYPES:
            noted(f"{slug} {eid}: `{slug}` is not one of the 22 types; left out")
        elif not isinstance(eid, str) or not eid:
            noted(f"a {slug} named {_name(body)!r} has no id; left out")
        else:
            valid.append((slug, body))
    w = _World(valid, report, noted)

    kept: dict[str, list[Mapping[str, Any]]] = {}
    for slug, body in valid:
        if not rooms and is_room_element({**body, "type": slug}):
            report.rooms_left_out += 1
        else:
            kept.setdefault(slug, []).append(body)
    for bodies in kept.values():
        bodies.sort(key=lambda b: (_name(b).casefold(), _name(b), str(b["id"])))

    world_title = one_line(world.get("name") or "") or "Untitled world"
    units: list[_Unit] = []
    for slug in ELEMENT_TYPES:
        if slug not in kept:
            continue
        blocks = [(_name(b), element_block(slug, b, w, extensions=extensions)) for b in kept[slug]]
        title = f"{PLURALS.get(slug, slug.capitalize())} of {world_title}"
        units.append(_Unit([slug], _split(title, blocks, words, bytes_)))
    for (slug, key), n in sorted(w.unknown.items()):
        noted(f"{slug}: `{key}` is not a field of {slug}; left out ({n} element{'s' if n != 1 else ''})")
    report.elements = sum(len(b) for b in kept.values())
    report.types = len(kept)

    head = world_parts(
        world, world_title, kept, w, extensions=extensions, words=words, bytes_=bytes_, exported_as=exported_as
    )
    report.files_over = not _merge(units, files - len(head) + 1, words, bytes_)

    named: list[tuple[str, _Part, bool]] = []  # (file name, part, a world part)
    if len(head) == 1:
        named.append((WORLD_NAME, head[0], True))
    else:
        named += [(WORLD_NAME.replace(".md", f"-{k}.md"), p, True) for k, p in enumerate(head, 1)]
    for i, unit in enumerate(units, 1):
        base = f"{i:02d}-{_unit_name(unit.slugs)}"
        if len(unit.parts) == 1:
            named.append((f"{base}.md", unit.parts[0], False))
        else:
            named += [(f"{base}-{k}.md", p, False) for k, p in enumerate(unit.parts, 1)]

    out: dict[str, str] = {}
    for name, part, of_world in named:
        out[name] = part.text
        report.words += part.words
        report.bytes += part.bytes
        if part.words > words or part.bytes > bytes_:
            report.oversize.append(name)
            alone = part.members[0]
            if not of_world:
                what = f"one element, {alone}, alone"
            else:
                what = alone if alone == _WORLD_FIELDS_MEMBER else f"the index line of {alone}, alone"
            noted(f"{name}: {part.words:,} words, {part.bytes:,} bytes, past a cap: {what}; written whole")
    report.files = list(out)
    return out, report


def pack_world(
    world: Mapping[str, Any],
    elements: Iterable[tuple[str, Mapping[str, Any]]],
    out: str | os.PathLike[str],
    *,
    words: int = DEFAULT_WORDS,
    bytes_: int = DEFAULT_BYTES,
    files: int = DEFAULT_FILES,
    rooms: bool = False,
    extensions: bool = False,
    note: Note | None = None,
    exported_as: Mapping[str, Any] | None = None,
) -> PackReport:
    """Pack a world (its ``GET /world`` body or ``world.json``, and its elements as (type slug,
    body)) into ``out``, which must not exist (``FileExistsError``). Nothing is written unless the
    whole pack was built. When ``report.files_over`` is set, every file is still written."""
    path = Path(out)
    if path.exists():
        raise FileExistsError(f"{path}: already exists; give a new directory")
    texts, report = build_pack(
        world,
        elements,
        words=words,
        bytes_=bytes_,
        files=files,
        rooms=rooms,
        extensions=extensions,
        note=note,
        exported_as=exported_as,
    )
    path.mkdir(parents=True, exist_ok=False)
    for name, text in texts.items():
        (path / name).write_bytes(text.encode("utf-8"))
    report.out = path
    return report


def _folder_elements(folder: Folder, note: Note) -> list[tuple[str, Mapping[str, Any]]]:
    """(type, body) for every element ``read_folder`` served; what it skipped or set aside, noted."""

    def rel(path: Path) -> str:
        return path.relative_to(folder.root).as_posix()

    for s in folder.skipped:
        if not (s.path.parent == folder.root and s.path.name == WORLD_FILE):
            note(f"{rel(s.path)}: {s.reason}; skipped")
    for d in folder.ignored_dirs:
        note(f"{rel(d)}/: not a type directory; skipped")
    for dup in folder.duplicates:
        note(f"{rel(dup.ignored)}: id {dup.id} also in {rel(dup.kept)}; packed {rel(dup.kept)}")
    for eid in folder.in_both_layouts:
        note(f"{rel(folder.legacy[eid].path)}: id {eid} also at {rel(folder.elements[eid].path)}; packed elements/")
    found = sorted(folder.all_elements().values(), key=lambda e: (e.layout != "elements", e.path))
    return [(e.type, e.body) for e in found]


def pack_folder(
    folder: Folder | str | os.PathLike[str],
    out: str | os.PathLike[str],
    *,
    words: int = DEFAULT_WORDS,
    bytes_: int = DEFAULT_BYTES,
    files: int = DEFAULT_FILES,
    rooms: bool = False,
    extensions: bool = False,
    note: Note | None = None,
) -> PackReport:
    """Pack the world folder at ``folder`` (read by ``read_folder``) into ``out``. Raises
    ``PackError`` when ``world.json`` cannot be read, ``FileExistsError`` when ``out`` exists."""
    if not isinstance(folder, Folder):
        folder = read_folder(folder)
    if folder.world is None:
        why = [s.reason for s in folder.skipped if s.path.parent == folder.root and s.path.name == WORLD_FILE]
        raise PackError(f"{folder.root}: {why[0] if why else 'no ' + WORLD_FILE}")
    early: list[str] = []

    def noted(msg: str) -> None:
        early.append(msg)
        if note is not None:
            note(msg)

    elements = _folder_elements(folder, noted)
    report = pack_world(
        folder.world, elements, out, words=words, bytes_=bytes_, files=files, rooms=rooms, extensions=extensions,
        note=note, exported_as=folder.world.get("exported_as"),
    )  # fmt: skip
    report.notes[:0] = early
    return report


def pack_api(
    client: Reader,
    out: str | os.PathLike[str],
    *,
    words: int = DEFAULT_WORDS,
    bytes_: int = DEFAULT_BYTES,
    files: int = DEFAULT_FILES,
    rooms: bool = False,
    extensions: bool = False,
    note: Note | None = None,
) -> PackReport:
    """Pack the key's world, read through the API (``get_world`` and every type's list; reads
    only), into ``out``. A failure to read raises (``ApiError``, ``ConnectionError``, ``ValueError``)
    before anything is written."""
    path = Path(out)
    if path.exists():
        raise FileExistsError(f"{path}: already exists; give a new directory")
    world = client.get_world()
    elements = [(t, b) for t in ELEMENT_TYPES for b in _list_all(client, t)]
    # Which kind of key made the pack (the label line): /me, mapped as export.exported_as maps it,
    # a Character's name from the Characters read; no /me, no line.
    try:
        me: Mapping[str, Any] | None = client.me()
    except (ApiError, ConnectionError, ValueError, AttributeError):
        me = None
    names = {
        str(b.get("id")): str(b.get("name")) for t, b in elements if t == "character" and isinstance(b.get("name"), str)
    }
    slice_ = _exported_as(me, names.get)
    return pack_world(
        world,
        elements,
        path,
        words=words,
        bytes_=bytes_,
        files=files,
        rooms=rooms,
        extensions=extensions,
        note=note,
        exported_as=slice_,
    )


# --- the command line


def _plural(n: int, word: str) -> str:
    return f"{n:,} {word}{'' if n == 1 else 's'}"


def _kb(n: int) -> str:
    return f"{max(1, (n + 500) // 1000) if n else 0:,} KB"


def _sentence(report: PackReport, out: object) -> str:
    """The one line the command prints."""
    extra = []
    if report.rooms_left_out:
        extra.append(f"{_plural(report.rooms_left_out, 'room element')} left out")
    if report.extensions_left_out:
        extra.append(f"{_plural(report.extensions_left_out, 'extension field')} left out")
    if report.known_of:
        extra.append(f"{report.known_of:,} known of")
    if report.unresolved:
        extra.append(_plural(len(report.unresolved), "unresolved link"))
    if report.oversize:
        extra.append(f"{_plural(len(report.oversize), 'file')} past a cap")
    return (
        f"packed {_plural(report.elements, 'element')} in {_plural(report.types, 'type')} to {out}: "
        f"{_plural(len(report.files), 'file')}, {_plural(report.words, 'word')}, {_kb(report.bytes)}"
        + "".join(f"; {e}" for e in extra)
    )


def _positive(text: str) -> int:
    try:
        n = int(text.replace("_", "").replace(",", ""))
    except ValueError:
        raise argparse.ArgumentTypeError(f"{text!r} is not a whole number") from None
    if n < 1:
        raise argparse.ArgumentTypeError(f"{text} is below 1")
    return n


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="python -m onlyworlds.pack", description=(__doc__ or "").splitlines()[0])
    ap.add_argument("paths", nargs="*", metavar="PATH", help="FOLDER OUT, or OUT with --api; OUT must not exist")
    ap.add_argument(
        "--api",
        action="store_true",
        help="pack the world of the key in OW_API_KEY or ONLYWORLDS_API_KEY (PIN: OW_API_PIN or ONLYWORLDS_API_PIN)",
    )
    ap.add_argument("--base-url", default=API_BASE, help=f"the API to read (default {API_BASE})")
    ap.add_argument("--words", type=_positive, default=DEFAULT_WORDS, help=f"words per file (default {DEFAULT_WORDS})")
    ap.add_argument("--bytes", type=_positive, default=DEFAULT_BYTES, help=f"bytes per file (default {DEFAULT_BYTES})")
    ap.add_argument("--files", type=_positive, default=DEFAULT_FILES, help=f"files at most (default {DEFAULT_FILES})")
    ap.add_argument("--rooms", action="store_true", help="keep room elements (the room profile); left out by default")
    ap.add_argument("--extensions", action="store_true", help="keep x_, atlas_ and shadow_ keys; left out by default")
    try:
        args = ap.parse_args(argv)
    except SystemExit as exc:  # argparse's own errors (exit 2) and --help (exit 0), as a return
        return exc.code if isinstance(exc.code, int) else 2
    if len(args.paths) != (1 if args.api else 2):
        print("give a world folder and an out directory, or --api and an out directory", file=sys.stderr)
        return 2
    out = Path(args.paths[-1])
    if out.exists():
        print(f"{out}: already exists; give a new directory", file=sys.stderr)
        return 2
    opts: dict[str, Any] = {
        "words": args.words,
        "bytes_": args.bytes,
        "files": args.files,
        "rooms": args.rooms,
        "extensions": args.extensions,
    }

    def note(msg: str) -> None:
        print(f"note: {msg}", file=sys.stderr)

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
            report = pack_api(client, out, note=note, **opts)
        except (ApiError, ConnectionError, ValueError) as exc:
            print(f"nothing could be read: {exc}", file=sys.stderr)
            return 2
    else:
        folder = Path(args.paths[0])
        if not (folder / WORLD_FILE).is_file():
            print(f"{folder}: not a world folder (no {WORLD_FILE})", file=sys.stderr)
            return 2
        try:
            report = pack_folder(folder, out, note=note, **opts)
        except PackError as exc:
            print(f"nothing could be read: {exc}", file=sys.stderr)
            return 2

    for line in report.unresolved:
        note(f"unresolved link: {line}")
    print(_sentence(report, out))
    if report.files_over:
        print(
            f"the world needs {len(report.files)} files at these caps, more than --files {args.files}: every "
            "element was written; raise --files, or raise --words or --bytes so more types can share a file",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""The OnlyWorlds world folder: filenames, the writer, the reader.

Spec: OnlyWorlds Folder Format v0.3.18.
Section numbers below are that document's.

::

    <world>/
    ├── world.json               id + name required; every other key carried, never invented (§4.1)
    ├── elements/<type>/*.json   all 22 types, one element per file, empty type dirs omitted (§4)
    └── spatial/{map,pin,zone,marker}/   legacy layout: READ, never written (§4)

Filenames are presentation only (§3.1). Identity is the ``id`` inside the file.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import unicodedata
import uuid
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from ._jsonfmt import encode
from ._schema import ELEMENT_TYPES

__all__ = [
    "ELEMENTS_DIR",
    "FORMAT_VERSION",
    "HIDDEN",
    "ID_TAIL_LEN",
    "KNOWN_OF",
    "KNOWN_OF_KEEPS",
    "LEGACY_SPATIAL_DIR",
    "LEGACY_SPATIAL_TYPES",
    "SLUG_ID_SEP",
    "SLUG_MAX_LEN",
    "WIRE_TO_DISK_WORLD_KEYS",
    "WORLD_FILE",
    "WORLD_FOLDER_KEYS",
    "DuplicateId",
    "Folder",
    "FolderElement",
    "SkippedFile",
    "WriteReport",
    "element_filename",
    "element_filename_full_id",
    "id_tail",
    "is_hidden",
    "is_known_of",
    "known_of_for_disk",
    "read_folder",
    "resolve_filenames",
    "slugify",
    "world_for_disk",
    "write_folder",
]

#: The spec version this module writes and reads against (§4.2 ``format_version``).
FORMAT_VERSION = "0.3.18"

#: §4.4 (v0.3.10; keel PR 113): the stub marker. keel hands a guest an element it reaches only
#: through its own Character's sheet as a stub, ``known_of: true``: these keys, its type's public
#: fields with their values (keel PR 117: ``PUBLIC_FIELDS``), every other field unset.
KNOWN_OF = "known_of"
#: The hidden mark's key (folder format §4.8, ``is_hidden``).
HIDDEN = "hidden"
#: The keys every stub keeps (§4.4, keel's ``KNOWN_OF_BASE``): written even when empty.
KNOWN_OF_KEEPS: frozenset[str] = frozenset(
    {"id", "type", "name", "description", "supertype", "subtype", "image_url", "created_at", "updated_at", "change_seq"}
)


def is_known_of(body: Mapping[str, Any]) -> bool:
    """True for a stub (``known_of: true``, §4.4): an element known of, never a whole one.

    Its absent fields are unknown, not empty: never read them as values or as a deletion,
    never merge them over a whole copy, never push it. Absent, ``false`` or anything else: whole.
    """
    return body.get(KNOWN_OF) is True


def is_hidden(body: Mapping[str, Any]) -> bool:
    """True when the element carries the hidden mark (``hidden: true`` at the top level, folder format
    §4.8; keel serves it so to the owner's and co-builders' keys). Hidden from whoever the world is
    handed to, never from its holder: a reader that hands a world on (the pack, the OKF bundle, a
    shared ``.owworld``) leaves it out unless asked; a copy keeps it byte for byte. Any value but
    absent, null and ``false`` counts as marked, so a doubt leaves the element out rather than
    handing it on."""
    value = body.get(HIDDEN)
    return value is not None and value is not False


def _is_set(value: Any) -> bool:
    """A value is anything but ``""``, ``None`` and ``[]``: ``0`` and ``False`` are values."""
    return not (value is None or (isinstance(value, str) and value == "") or (isinstance(value, list) and not value))


def known_of_for_disk(body: Mapping[str, Any]) -> dict[str, Any]:
    """A stub as §4.4 writes it, its keys in received order, then ``known_of: true``: every
    ``KNOWN_OF_KEEPS`` key, and every other key the server sent with a value.

    The unset fields keel serves (``""``, ``null``, ``[]``) are left out, never written:
    on disk they would read as a whole element with nothing filled in. Anything else it
    sent is kept, whatever the field (a Character's public ``physicality``, ``height``,
    ``species``: keel PR 117), since a writer never drops data it has (§3). This reads the
    body, never ``PUBLIC_FIELDS``, so a type that gains public fields needs no change here.
    """
    out = {k: v for k, v in body.items() if k != KNOWN_OF and (k in KNOWN_OF_KEEPS or _is_set(v))}
    out[KNOWN_OF] = True
    return out


ELEMENTS_DIR = "elements"
WORLD_FILE = "world.json"
LEGACY_SPATIAL_DIR = "spatial"
LEGACY_SPATIAL_TYPES: tuple[str, ...] = ("map", "pin", "zone", "marker")

#: §5 (v0.3.5): ``world.json`` keys follow the CANONICAL SCHEMA, not the wire. One rename today.
WIRE_TO_DISK_WORLD_KEYS: Mapping[str, str] = {"time_range_current": "time_current"}

#: §4.2: the ``world.json`` keys this spec defines beside the World's schema fields (besides
#: ``api`` and the ``snapshot_*`` keys). They say what the folder is, never what the world is,
#: so the wire neither serves nor takes them: ``Client.patch_world`` leaves them out.
WORLD_FOLDER_KEYS: tuple[str, ...] = ("format_version", "writable", "source", "exported_as", "producer")

# ---------------------------------------------------------------------------
# Filenames (§3.2) — behaviour ported from Atlas `src/store/fs-utils.ts`, the
# reference implementation, via ow-folder-store `src/filename.ts`. Where the
# spec and the reference disagree on an arbitrary constant, the reference wins.
# ---------------------------------------------------------------------------

SLUG_ID_SEP = "--"
ID_TAIL_LEN = 8
SLUG_MAX_LEN = 40

# Escaped, never raw: raw combining characters do not survive every transport.
_COMBINING_MARKS = re.compile("[̀-ͯ]")
_NON_ALNUM_RUN = re.compile(r"[^a-z0-9]+")


def slugify(name: str | None) -> str:
    """Lowercase ASCII kebab of a name, capped at 40, trailing ``-`` re-trimmed after the cap.

    NFKD first and the combining marks removed BEFORE the alphanumeric pass, so
    ``José`` is ``jose`` and not ``jos``. Empty result means "unsluggable"; the
    caller falls back to the full id (§3.2), never to a placeholder word.
    """
    if not name:
        return ""
    ascii_ish = _COMBINING_MARKS.sub("", unicodedata.normalize("NFKD", name)).lower()
    trimmed = _NON_ALNUM_RUN.sub("-", ascii_ish).strip("-")
    if len(trimmed) <= SLUG_MAX_LEN:
        return trimmed
    return trimmed[:SLUG_MAX_LEN].rstrip("-")


def id_tail(element_id: str) -> str:
    """The last 8 characters of an id, guarded so the ``--`` separator stays unambiguous."""
    if len(element_id) <= ID_TAIL_LEN:
        return element_id
    raw = element_id[-ID_TAIL_LEN:]
    if SLUG_ID_SEP in raw or raw.startswith("-"):
        compact = element_id.replace("-", "")
        return compact if len(compact) <= ID_TAIL_LEN else compact[-ID_TAIL_LEN:]
    return raw


def element_filename(element_id: str, name: str | None) -> str:
    """``<slug>--<tail8>.json``; an unsluggable name gives ``<full-id>.json`` (§3.2)."""
    slug = slugify(name)
    return f"{slug}{SLUG_ID_SEP}{id_tail(element_id)}.json" if slug else f"{element_id}.json"


def element_filename_full_id(element_id: str, name: str | None) -> str:
    """The collision fallback: the full id in place of the tail (Atlas ``elementFilenameFullId``)."""
    slug = slugify(name)
    return f"{slug}{SLUG_ID_SEP}{element_id}.json" if slug else f"{element_id}.json"


def _name_of(body: Mapping[str, Any]) -> str | None:
    name = body.get("name")
    return name if isinstance(name, str) else None


def resolve_filenames(elements: Iterable[tuple[str, str | None]]) -> dict[str, str]:
    """★ The writer collision rule (§3.2, MUST): id -> filename for ONE type directory.

    Two elements whose short names would land on one path (compared case-folded,
    because NTFS and APFS resolve them to one file) are resolved id-ascending:
    the lowest id keeps the short form, every other claimant takes the full id.
    Deterministic across writers and re-runs, whatever order the elements came in.
    """
    names: dict[str, str | None] = {}
    buckets: dict[str, list[str]] = {}
    for element_id, name in elements:
        if element_id in names:
            raise ValueError(f"duplicate id {element_id!r} in one type directory")
        names[element_id] = name
        buckets.setdefault(element_filename(element_id, name).lower(), []).append(element_id)
    out: dict[str, str] = {}
    for ids in buckets.values():
        for i, element_id in enumerate(sorted(ids)):
            maker = element_filename if i == 0 else element_filename_full_id
            out[element_id] = maker(element_id, names[element_id])
    return out


# ---------------------------------------------------------------------------
# Writer
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WriteReport:
    root: Path
    counts: dict[str, int]
    #: ids that took the full-id fallback under the collision rule
    collisions: list[str]

    @property
    def total(self) -> int:
        return sum(self.counts.values())


def world_for_disk(world: Mapping[str, Any], counts: Mapping[str, int] | None = None) -> dict[str, Any]:
    """The ``world.json`` a writer emits for ``world`` (a wire ``GET /world`` body or a read folder's).

    - Every key is carried, in received order (§4.1: MUST NOT drop, MUST NOT invent).
    - ``time_range_current`` becomes ``time_current`` IN PLACE (§5, v0.3.5). If both
      spellings are present, both are kept: dropping one would be a drop.
    - ``snapshot_counts`` (§4.2, v0.3.6) belongs to snapshots only and is never
      carried forward: recounted from ``counts`` when ``snapshot_of`` is present,
      removed otherwise.
    - ``format_version`` is written at a folder's birth; a value already carried
      is kept, never rewritten.
    - ``source`` and ``exported_as`` (§4.2, v0.3.9) and ``producer`` (v0.3.14) are
      carried like any key, so a folder rewritten from a read one keeps its parent's
      verbatim, and one that has none gets none; ``export_world`` is what writes them
      fresh.
    - ``origin`` (§4.2, v0.3.16) is the world's first import as the server keeps it: carried
      as given, from ``GET /world`` or a read ``world.json``, never derived from ``source`` or
      ``producer``; a world that has none gets none.
    """
    wid = world.get("id")
    if not isinstance(wid, str) or not wid:
        raise ValueError("world.json requires a non-empty string `id` (§4.1)")
    if not isinstance(world.get("name"), str):
        raise ValueError("world.json requires a string `name` (it MAY be empty) (§4.1)")
    out: dict[str, Any] = {}
    for key, value in world.items():
        disk_key = WIRE_TO_DISK_WORLD_KEYS.get(key, key)
        out[key if disk_key in world else disk_key] = value
    if "snapshot_counts" in out:
        if "snapshot_of" in out and counts is not None:
            out["snapshot_counts"] = {t: n for t, n in counts.items() if n}
        else:
            del out["snapshot_counts"]
    out.setdefault("format_version", FORMAT_VERSION)
    return out


def write_folder(
    root: str | os.PathLike[str],
    world: Mapping[str, Any],
    elements: Mapping[str, Iterable[Mapping[str, Any]]],
) -> WriteReport:
    """Write one world folder at ``root``. ``elements`` maps type -> element bodies.

    Bodies are written whole and untouched: no field stripped, added or reordered
    (§3.3 binds foreign values byte-for-byte, §4.2 keeps server-managed fields).
    The one exception is a stub (``known_of: true``, §4.4): it is written as it is,
    its kept keys, the fields it holds a value for and ``known_of``, never its unset
    fields (``known_of_for_disk``).
    Within a type, a repeated id keeps its LAST body (id-keyed overwrite, the
    spec's answer to a keyset walk that met a mid-walk write), so a stub that later
    arrives whole is written whole, without ``known_of`` (§4.4 rule 4). The same id
    under two types is an error.

    ``root`` must not exist, or be an empty directory: this writes a folder's
    birth, never over another folder (stale files from renamed or deleted
    elements would survive a merge-write). The tree is built in a sibling temp
    directory and renamed into place, so a crash never leaves a folder that
    looks complete.
    """
    root = Path(root)
    if root.exists() and (not root.is_dir() or any(root.iterdir())):
        raise FileExistsError(f"{root} exists and is not an empty directory; a folder is written whole, once")

    by_type: dict[str, dict[str, Mapping[str, Any]]] = {}
    owner: dict[str, str] = {}
    for etype, bodies in elements.items():
        if etype not in ELEMENT_TYPES:
            raise ValueError(f"unknown element type {etype!r}; the 22 are {ELEMENT_TYPES}")
        slot = by_type.setdefault(etype, {})
        for body in bodies:
            eid = body.get("id")
            if not isinstance(eid, str) or not eid:
                raise ValueError(f"{etype} element without a non-empty string id: {dict(body)!r:.200}")
            if owner.setdefault(eid, etype) != etype:
                raise ValueError(f"id {eid} appears under both {owner[eid]} and {etype}")
            slot.pop(eid, None)  # last wins, and takes the last position
            slot[eid] = body

    counts: dict[str, int] = {}
    collisions: list[str] = []
    tmp = root.parent / f".{root.name}.tmp-{uuid.uuid4().hex[:8]}"
    tmp.mkdir(parents=True)
    try:
        for etype in ELEMENT_TYPES:
            bodies_by_id = by_type.get(etype)
            if not bodies_by_id:
                continue  # §4: empty type directories are omitted
            tdir = tmp / ELEMENTS_DIR / etype
            tdir.mkdir(parents=True)
            names = resolve_filenames((eid, _name_of(b)) for eid, b in bodies_by_id.items())
            for eid, body in bodies_by_id.items():
                filename = names[eid]
                if filename != element_filename(eid, _name_of(body)):
                    collisions.append(eid)
                (tdir / filename).write_bytes(encode(known_of_for_disk(body) if is_known_of(body) else body))
            counts[etype] = len(bodies_by_id)
        (tmp / WORLD_FILE).write_bytes(encode(world_for_disk(world, counts)))
        if root.exists():
            root.rmdir()  # empty, checked above
        root.parent.mkdir(parents=True, exist_ok=True)
        tmp.rename(root)
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    return WriteReport(root=root, counts=counts, collisions=collisions)


# ---------------------------------------------------------------------------
# Reader — never writes, moves or deletes anything.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FolderElement:
    id: str
    #: the declared ``type`` from the body when it has one (lowercased), else the directory's
    type: str
    #: True when ``type`` came from the directory (fixture README: infer it, but FLAG the inference)
    type_inferred: bool
    #: the parsed body exactly as on disk; the reader adds nothing to it (no ``type`` is injected)
    body: dict[str, Any]
    path: Path
    layout: Literal["elements", "spatial"]

    @property
    def known_of(self) -> bool:
        """True for a stub (``known_of: true``, §4.4): known of, never whole. Its absent fields are
        unknown, not empty, and it is never pushed."""
        return is_known_of(self.body)


@dataclass(frozen=True)
class SkippedFile:
    path: Path
    reason: str


@dataclass(frozen=True)
class DuplicateId:
    id: str
    kept: Path
    ignored: Path


@dataclass
class Folder:
    root: Path
    world: dict[str, Any] | None
    #: from ``elements/``, keyed by in-file id
    elements: dict[str, FolderElement] = field(default_factory=dict)
    #: from the legacy ``spatial/`` layout, kept separate (fixture README's recommended reading)
    legacy: dict[str, FolderElement] = field(default_factory=dict)
    skipped: list[SkippedFile] = field(default_factory=list)
    duplicates: list[DuplicateId] = field(default_factory=list)
    #: directories under ``elements/``/``spatial/`` that are not type directories
    ignored_dirs: list[Path] = field(default_factory=list)

    def all_elements(self) -> dict[str, FolderElement]:
        """The union Atlas reads: ``elements/`` plus ``spatial/``; ``elements/`` wins on a shared id (§4, v0.3.8)."""
        return {**self.legacy, **self.elements}

    @property
    def in_both_layouts(self) -> list[str]:
        """Ids found under both ``elements/`` and ``spatial/``, sorted. A writer never leaves one so
        (§4, v0.3.8, one id one file), so each is a folder some writer got wrong: a reader serves the
        ``elements/`` copy (``all_elements``) and SHOULD log these."""
        return sorted(self.elements.keys() & self.legacy.keys())

    @property
    def known_of(self) -> list[str]:
        """Ids of the stubs among ``all_elements`` (§4.4, ``known_of: true``), sorted: elements this
        folder knows of but does not hold whole."""
        return sorted(eid for eid, el in self.all_elements().items() if el.known_of)

    @property
    def server_world_id(self) -> str | None:
        """§4.1 (v0.3.6): prefer ``api.world_id`` when present, fall back to ``id``."""
        if self.world is None:
            return None
        api = self.world.get("api")
        if isinstance(api, Mapping) and isinstance(api.get("world_id"), str) and api["world_id"]:
            return str(api["world_id"])
        wid = self.world.get("id")
        return wid if isinstance(wid, str) else None

    @property
    def time_current(self) -> Any:
        """§5: accept both spellings forever, prefer a non-null ``time_current`` (a null one beside
        ``time_range_current`` reads the range: clarified 2026-10-17)."""
        if self.world is None:
            return None
        if self.world.get("time_current") is not None:
            return self.world["time_current"]
        if "time_range_current" in self.world:
            return self.world["time_range_current"]
        return self.world.get("time_current")


def _reject_constant(token: str) -> Any:
    raise ValueError(f"{token} is not JSON")


def _load_json(path: Path) -> Any:
    text = path.read_bytes().decode("utf-8-sig")
    return json.loads(text, parse_constant=_reject_constant)


def read_folder(root: str | os.PathLike[str], *, legacy: bool = True) -> Folder:
    """Read a world folder. Opens files for reading only; the folder is never mutated.

    - Every ``*.json`` in a type directory is ingested and keyed on its in-file ``id``;
      the filename is never parsed (§3.1). A dot-prefixed file there is a tool's litter,
      not an element: skipped and listed (clarified 2026-10-17).
    - A file that is not JSON, not an object, or has no non-empty string ``id`` is
      skipped, recorded in ``skipped``, and left where it is (§4.1).
    - A declared ``type`` beats the directory the file sits in; an absent one is
      inferred from the directory and flagged (``type_inferred``).
    - ``spatial/{map,pin,zone,marker}/`` (Atlas through v1.0) is read into ``legacy``
      unless ``legacy=False``. A missing type directory is "none of that type".
    - A repeated id keeps the first file in sorted path order; the rest land in ``duplicates``.
    - A ``known_of: true`` file is a stub (§4.4): read as it is, flagged ``FolderElement.known_of``
      and listed in ``Folder.known_of``; nothing is filled in for the fields it lacks.
    """
    root = Path(root)
    world_path = root / WORLD_FILE
    world: dict[str, Any] | None = None
    folder = Folder(root=root, world=None)
    if world_path.is_file():
        try:
            parsed = _load_json(world_path)
        except (ValueError, UnicodeDecodeError) as exc:
            folder.skipped.append(SkippedFile(world_path, f"world.json unreadable: {exc}"))
        else:
            if isinstance(parsed, dict):
                world = parsed
            else:
                folder.skipped.append(SkippedFile(world_path, "world.json is not a JSON object"))
    folder.world = world

    layouts: list[tuple[Literal["elements", "spatial"], tuple[str, ...], dict[str, FolderElement]]] = [
        ("elements", ELEMENT_TYPES, folder.elements),
    ]
    if legacy:
        layouts.append(("spatial", LEGACY_SPATIAL_TYPES, folder.legacy))

    for layout, allowed, sink in layouts:
        base = root / (ELEMENTS_DIR if layout == "elements" else LEGACY_SPATIAL_DIR)
        if not base.is_dir():
            continue
        for tdir in sorted(p for p in base.iterdir() if p.is_dir()):
            dir_type = tdir.name.lower()
            if dir_type not in allowed:
                folder.ignored_dirs.append(tdir)
                continue
            for path in sorted(p for p in tdir.iterdir() if p.is_file() and p.name.lower().endswith(".json")):
                if path.name.startswith("."):
                    folder.skipped.append(SkippedFile(path, "a dot-prefixed file: a tool's litter, not an element"))
                    continue
                try:
                    body = _load_json(path)
                except (ValueError, UnicodeDecodeError) as exc:
                    folder.skipped.append(SkippedFile(path, f"unparseable JSON: {exc}"))
                    continue
                if not isinstance(body, dict):
                    folder.skipped.append(SkippedFile(path, "not a JSON object"))
                    continue
                eid = body.get("id")
                if not isinstance(eid, str) or not eid:
                    folder.skipped.append(SkippedFile(path, "no id: not an element"))
                    continue
                declared = body.get("type")
                has_declared = isinstance(declared, str) and bool(declared)
                element = FolderElement(
                    id=eid,
                    type=str(declared).lower() if has_declared else dir_type,
                    type_inferred=not has_declared,
                    body=body,
                    path=path,
                    layout=layout,
                )
                if eid in sink:
                    folder.duplicates.append(DuplicateId(eid, sink[eid].path, path))
                    continue
                sink[eid] = element
    return folder

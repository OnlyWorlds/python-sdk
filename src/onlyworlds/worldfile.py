"""The world file, ``.owworld``: one world folder in one zip (Folder Format spec §4.7).

The archive is transport, not format (§4): it holds a folder as ``folder.py`` reads and
writes it, byte for byte. Section numbers and the check numbers OW-1 to OW-22 below are
the spec's. The semantics are the TypeScript SDK's ``world-file.ts`` (the reference reader
and writer, 80 of 80 on the fixture set), ported, not translated.

THE READER (``read_world_file``) parses the central directory itself, zip64 included,
and runs every check on names, kinds, methods and sizes before it inflates anything. It
does not use ``zipfile`` to read: on Windows ``zipfile`` turns a ``\\`` in a name into
``/`` and decodes a name without the UTF-8 flag as cp437, which would hide two of the
refusals below. Each refusal raises ``WorldFileError`` with one ``reason``, checked in
the reference checker's order:

- ``not_openable``: not a zip, a spanned one, a broken entry, an entry holding fewer
  bytes than it declares, a CRC that fails.
- ``unsafe_path`` (OW-16, OW-19): a name that is not a plain relative path (``\\``, an
  empty, ``.`` or ``..`` segment, absolute, a drive), or a path that is both a file and
  a folder.
- ``link`` (OW-20): a Unix mode that is not a regular file or a directory.
- ``method`` (OW-21): encrypted, or a method other than stored or deflate.
- ``name`` (OW-22): a Windows device name, a trailing dot or space, one of ``<>:"|?*``
  or a control character, a non-ASCII name without the UTF-8 flag, a flagged name that
  is not UTF-8.
- ``duplicate`` (OW-17), ``collision`` (OW-18: NFC, then simple case folding from the
  C and S rows of CaseFolding 15.1, ``_casefold.py``; never ``str.casefold()``).
- ``too_many``, ``too_big`` (OW-14, OW-15): past the budget by count or declared size,
  or an entry that holds more bytes than it declares.
- ``marker`` (OW-6): a root ``mimetype`` entry with other bytes than the media type.
  A marker is never required.
- ``not_a_world``, ``more_than_one`` (OW-2, OW-3, OW-5): no world, two worlds, a second
  ``world.json`` inside the world (one under ``records/`` is a producer's data), a
  ``world.json`` that will not parse or has no string id.

Files beside the world's folder and archive junk (``__MACOSX``, ``.DS_Store``,
``Thumbs.db``) are ignored (OW-4), still checked and counted. An ``api`` block in
``world.json`` is stripped and never returned (OW-10); without one, ``world.json`` keeps
its exact bytes (OW-11).

THE WRITER (``write_world_file``, ``world_file_bytes``) emits one world (OW-7, OW-12,
OW-13): the ``mimetype`` marker first and stored, then ``world.json`` (without ``api``)
and the folder's parts, ``elements/``, ``spatial/``, ``media/``, ``records/``, every entry
stamped 1980-01-01 00:00, in the UTF-8 byte order of its name, ``.json`` deflated and
everything else stored (the TypeScript writer's choice, so the two directories agree
method for method). Every other file in the folder is left out. A tool's dot-folder
travels only when handed in (``private_dir``), and makes the file a private copy, not a
portable ``.owworld`` (§4.1). A producer's records marked ``"private": true`` in
``records/RECORDS.json`` are left out whole unless asked (``include_private_records``;
OW-8, §4.5 rule 11), the manifest carried byte-exact either way. An element file carrying
``hidden: true`` is copied byte for byte unless the file is a share (``include_hidden=False``:
left out whole, and counted; folder format §4.8, Skeld's ruling, OW Atlas h20 #11469). The two
defaults differ on purpose: private records stay out unless asked, hidden elements stay in unless
the write is a share.
"""

from __future__ import annotations

import io
import json
import os
import re
import shutil
import struct
import unicodedata
import uuid
import zipfile
import zlib
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import IO, Any, Literal, NoReturn

from ._casefold import FOLD_RUNS
from ._jsonfmt import encode
from .folder import ELEMENTS_DIR, LEGACY_SPATIAL_DIR, WORLD_FILE, is_hidden, slugify

__all__ = [
    "MARKER_NAME",
    "REASONS",
    "WORLD_FILE_MAX_BYTES",
    "WORLD_FILE_MAX_ENTRIES",
    "WORLD_FILE_MEDIA_TYPE",
    "WORLD_FILE_PARTS",
    "WorldFile",
    "WorldFileError",
    "WorldFileReason",
    "read_world_file",
    "simple_case_fold",
    "world_file_bytes",
    "write_world_file",
]

#: The marker's name and its exact bytes (OW-6): ASCII, no newline.
MARKER_NAME = "mimetype"
WORLD_FILE_MEDIA_TYPE = "application/vnd.onlyworlds.world+zip"

#: The budget, uncompressed: the floor every reader accepts (OW-15, Boss's numbers).
WORLD_FILE_MAX_BYTES = 2 * 1024**3
WORLD_FILE_MAX_ENTRIES = 500_000

#: The folder's parts, the only folders a portable copy holds beside ``world.json`` (OW-7).
WORLD_FILE_PARTS: tuple[str, ...] = (ELEMENTS_DIR, LEGACY_SPATIAL_DIR, "media", "records")

WorldFileReason = Literal[
    "unsafe_path",
    "too_big",
    "too_many",
    "not_a_world",
    "more_than_one",
    "not_openable",
    "duplicate",
    "collision",
    "link",
    "method",
    "name",
    "marker",
]

#: The spec's one list of causes (§4.7), as the TypeScript reader names them.
REASONS: tuple[WorldFileReason, ...] = (
    "unsafe_path",
    "too_big",
    "too_many",
    "not_a_world",
    "more_than_one",
    "not_openable",
    "duplicate",
    "collision",
    "link",
    "method",
    "name",
    "marker",
)

_MESSAGES: Mapping[WorldFileReason, str] = {
    "unsafe_path": "The world file holds a path that cannot be written safely.",
    "too_big": "The world file is bigger than the budget allows, or a file in it is bigger than it says.",
    "too_many": "The world file holds more files than the budget allows.",
    "not_a_world": "The file is not a world: it has no readable world.json with an id.",
    "more_than_one": "The file holds more than one world.",
    "not_openable": "The file is not a zip that can be read.",
    "duplicate": "The world file holds two entries with the same name.",
    "collision": "The world file holds two names that differ only in case or in how an accent is written.",
    "link": "The world file holds a link or a special file.",
    "method": "The world file holds an encrypted entry, or one compressed other than stored or deflate.",
    "name": "The world file holds a name that some disk cannot hold.",
    "marker": "The world file's mimetype entry is not the OnlyWorlds media type.",
}


class WorldFileError(ValueError):
    """A world file was refused, or could not be written; nothing was returned or written.

    ``reason`` is one of ``REASONS``, for a tool to word its own message.
    """

    def __init__(self, reason: WorldFileReason, message: str | None = None):
        super().__init__(message or _MESSAGES[reason])
        self.reason: WorldFileReason = reason


def _refuse(reason: WorldFileReason, message: str | None = None) -> NoReturn:
    raise WorldFileError(reason, message)


# ---------------------------------------------------------------------------
# Names
# ---------------------------------------------------------------------------

_DRIVE = re.compile(r"^[A-Za-z]:")


def _path_fault(name: str) -> str | None:
    """OW-16, strict: why a name is not a plain relative path, or None."""
    if "\\" in name:
        return "holds a backslash"
    if name.startswith("/"):
        return "is absolute"
    if _DRIVE.match(name):
        return "names a drive"
    if any(seg in ("", ".", "..") for seg in name.split("/")):
        return "has an empty, . or .. segment"
    return None


_RESERVED = frozenset(
    {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
)
#: ``<>:"|?*`` and the control characters (Unicode Cc: U+0000 to U+001F, U+007F to U+009F).
_BAD_CHAR = re.compile('[<>:"|?*\x00-\x1f\x7f-\x9f]')


def _name_fault(name: str) -> str | None:
    """OW-22: why a name would not land on every disk, or None."""
    for seg in name.split("/"):
        if _BAD_CHAR.search(seg):
            return f"segment {seg!r} holds a reserved or control character"
        if seg.endswith((".", " ")):
            return f"segment {seg!r} ends in a dot or a space"
        if seg.split(".")[0].upper() in _RESERVED:
            return f"segment {seg!r} is a Windows device name"
    return None


def _is_junk(path: str) -> bool:
    """Archive junk a re-zipped folder picks up on the way: never part of a world."""
    return any(seg in ("__MACOSX", ".DS_Store", "Thumbs.db") for seg in path.split("/"))


@cache
def _fold_table() -> dict[int, int]:
    table: dict[int, int] = {}
    for start, count, stride, delta in FOLD_RUNS:
        for k in range(count):
            table[start + k * stride] = start + k * stride + delta
    return table


def simple_case_fold(text: str) -> str:
    """Unicode 15.1 simple case folding (CaseFolding.txt, C and S rows), code point by code point.

    What OW-18 applies after NFC. A code point the table does not map folds to itself; a fold
    a later Unicode adds stays out until the fixture set's pin moves.
    """
    return text.translate(_fold_table())


def _fold_name(name: str) -> str:
    """OW-18's one fold for every reader: NFC, then simple case folding. ``/`` folds to itself."""
    return simple_case_fold(unicodedata.normalize("NFC", name))


def _check_collisions(names: Iterable[str]) -> None:
    """OW-18 over every name and every folder a name implies: two that fold to one refuse."""
    by_fold: dict[str, str] = {}
    seg_fold: dict[str, str] = {}
    done: set[str] = set()
    for raw in names:
        segs = (raw[:-1] if raw.endswith("/") else raw).split("/")
        prefix = ""
        folded = ""
        for i, seg in enumerate(segs):
            f = seg_fold.get(seg)
            if f is None:
                f = seg_fold[seg] = _fold_name(seg)
            prefix = f"{prefix}/{seg}" if i else seg
            folded = f"{folded}/{f}" if i else f
            if prefix in done:
                continue
            done.add(prefix)
            other = by_fold.get(folded)
            if other is not None:
                _refuse("collision", f"The names {other!r} and {prefix!r} are one name after NFC and case folding.")
            by_fold[folded] = prefix


def _check_file_and_folder(files: set[str]) -> None:
    """OW-19: a path that is a file and also a folder of another file cannot land on a disk."""
    seen: set[str] = set()
    for name in sorted(files):
        segs = name.split("/")
        prefix = ""
        for i in range(len(segs) - 1):
            prefix = f"{prefix}/{segs[i]}" if i else segs[i]
            if prefix in seen:
                continue
            seen.add(prefix)
            if prefix in files:
                _refuse("unsafe_path", f"{prefix!r} is a file and a folder.")


# ---------------------------------------------------------------------------
# The central directory
# ---------------------------------------------------------------------------

_SIG_LOCAL = 0x04034B50
_SIG_CENTRAL = 0x02014B50
_SIG_END = b"PK\x05\x06"
_SIG_END64 = 0x06064B50
_SIG_LOCATOR64 = 0x07064B50
_MAX32 = 0xFFFFFFFF
_FLAG_ENCRYPTED = 0x0001
_FLAG_STRONG_ENCRYPTION = 0x0040
_FLAG_UTF8 = 0x0800
_S_IFMT = 0o170000
_S_IFREG = 0o100000
_S_IFDIR = 0o040000


@dataclass(frozen=True)
class _Cd:
    name: str
    flags: int
    method: int
    crc: int
    csize: int
    usize: int
    offset: int
    external: int
    #: the name's bytes hold a byte past ASCII
    non_ascii: bool
    #: the UTF-8 flag is set and the name is not UTF-8
    bad_utf8: bool


class _Bytes:
    """Little-endian reads that refuse past the end, never wrap or guess."""

    def __init__(self, data: bytes):
        self.data = data

    def u16(self, off: int) -> int:
        if off < 0 or off + 2 > len(self.data):
            _refuse("not_openable", "The zip is cut short.")
        return int(struct.unpack_from("<H", self.data, off)[0])

    def u32(self, off: int) -> int:
        if off < 0 or off + 4 > len(self.data):
            _refuse("not_openable", "The zip is cut short.")
        return int(struct.unpack_from("<I", self.data, off)[0])

    def u64(self, off: int) -> int:
        if off < 0 or off + 8 > len(self.data):
            _refuse("not_openable", "The zip is cut short.")
        return int(struct.unpack_from("<Q", self.data, off)[0])


def _zip64_fields(body: bytes) -> Iterable[int]:
    """The 8-byte values of a zip64 extra field, in order; one asked past its end is ``not_openable``."""
    for r in range(0, len(body) - 7, 8):
        yield int(struct.unpack_from("<Q", body, r)[0])
    _refuse("not_openable", "A zip64 extra field is short.")


def _central_directory(data: bytes) -> list[_Cd]:
    """Every entry of the central directory, zip64 included, or ``not_openable``. Inflates nothing."""
    b = _Bytes(data)
    n = len(data)
    end = data.rfind(_SIG_END, max(0, n - 22 - 0xFFFF), n - 18) if n >= 22 else -1
    if end < 0:
        _refuse("not_openable", "The file is not a zip: it has no end of central directory.")
    this_disk, cd_disk = b.u16(end + 4), b.u16(end + 6)
    if not ((this_disk == 0 and cd_disk == 0) or (this_disk == 0xFFFF and cd_disk == 0xFFFF)):
        _refuse("not_openable", f"The zip spans disks (its end record says disk {this_disk}, the directory {cd_disk}).")
    cd_size, cd_offset = b.u32(end + 12), b.u32(end + 16)
    loc = end - 20
    if loc >= 0 and b.u32(loc) == _SIG_LOCATOR64:
        if b.u32(loc + 4) != 0 or b.u32(loc + 16) > 1:
            _refuse("not_openable", "The zip spans disks (zip64).")
        rec = b.u64(loc + 8)
        if rec + 56 > n or b.u32(rec) != _SIG_END64:
            _refuse("not_openable", "The zip64 end record is missing.")
        if b.u32(rec + 16) != 0 or b.u32(rec + 20) != 0:
            _refuse("not_openable", "The zip spans disks (zip64).")
        cd_size, cd_offset = b.u64(rec + 40), b.u64(rec + 48)
    cd_end = cd_offset + cd_size
    if cd_end > n:
        _refuse("not_openable", "The central directory lies past the end of the file.")
    out: list[_Cd] = []
    p = cd_offset
    while p < cd_end:
        if p + 46 > cd_end or b.u32(p) != _SIG_CENTRAL:
            _refuse("not_openable", "The central directory is broken.")
        flags = b.u16(p + 8)
        nlen, elen, clen = b.u16(p + 28), b.u16(p + 30), b.u16(p + 32)
        name_bytes = data[p + 46 : p + 46 + nlen]
        extra = data[p + 46 + nlen : p + 46 + nlen + elen]
        csize, usize, offset = b.u32(p + 20), b.u32(p + 24), b.u32(p + 42)
        if _MAX32 in (usize, csize, offset):
            q = 0
            while q + 4 <= len(extra):
                tag, size = struct.unpack_from("<HH", extra, q)
                if tag != 0x0001:
                    q += 4 + size
                    continue
                fields = iter(_zip64_fields(extra[q + 4 : q + 4 + size]))
                if usize == _MAX32:
                    usize = next(fields)
                if csize == _MAX32:
                    csize = next(fields)
                if offset == _MAX32:
                    offset = next(fields)
                break
        non_ascii = any(x > 0x7F for x in name_bytes)
        bad_utf8 = False
        if flags & _FLAG_UTF8:
            try:
                name = name_bytes.decode("utf-8")
            except UnicodeDecodeError:
                name, bad_utf8 = name_bytes.decode("latin-1"), True
        else:
            name = name_bytes.decode("latin-1")
        out.append(
            _Cd(
                name=name,
                flags=flags,
                method=b.u16(p + 10),
                crc=b.u32(p + 16),
                csize=csize,
                usize=usize,
                offset=offset,
                external=b.u32(p + 38),
                non_ascii=non_ascii,
                bad_utf8=bad_utf8,
            )
        )
        p += 46 + nlen + elen + clen
    if p != cd_end:
        _refuse("not_openable", "The central directory is broken.")
    return out


def _inflate(b: _Bytes, e: _Cd) -> bytes:
    """An entry's bytes, never inflated more than one byte past the size it declares (OW-14)."""
    data = b.data
    off = e.offset
    if off + 30 > len(data) or b.u32(off) != _SIG_LOCAL:
        _refuse("not_openable", f"{e.name}: no local header at its offset.")
    start = off + 30 + b.u16(off + 26) + b.u16(off + 28)
    payload = data[start : start + e.csize]
    if e.method == 0:
        out = payload
    else:
        inflater = zlib.decompressobj(-zlib.MAX_WBITS)
        try:
            out = inflater.decompress(payload, e.usize + 1)
        except zlib.error:
            _refuse("not_openable", f"{e.name}: its deflate stream is broken.")
        if len(out) <= e.usize and not inflater.eof:
            _refuse("not_openable", f"{e.name}: its deflate stream is cut short.")
    if len(out) > e.usize:
        _refuse("too_big", f"{e.name} holds more than the {e.usize} bytes it declares.")
    if len(out) != e.usize:
        _refuse("not_openable", f"{e.name} holds {len(out)} bytes and declares {e.usize}.")
    if zlib.crc32(out) != e.crc:
        _refuse("not_openable", f"{e.name} fails its CRC.")
    return out


# ---------------------------------------------------------------------------
# world.json
# ---------------------------------------------------------------------------

#: ECMAScript's WhiteSpace and LineTerminator, what ``String.prototype.trim`` strips: OW-3's
#: "a non-empty string once trimmed" is the TypeScript reader's trim, not ``str.strip()``.
_JS_SPACE = "".join(
    map(chr, (0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x20, 0xA0, 0x1680, *range(0x2000, 0x200B), 0x2028, 0x2029, 0x202F))
) + "".join(map(chr, (0x205F, 0x3000, 0xFEFF)))
_BOM = chr(0xFEFF)


def _reject_constant(token: str) -> Any:
    raise ValueError(f"{token} is not JSON")


def _parse_world(data: bytes) -> dict[str, Any]:
    text = data.decode("utf-8", errors="replace").removeprefix(_BOM)
    try:
        meta = json.loads(text, parse_constant=_reject_constant)
    except ValueError:
        _refuse("not_a_world")
    if not isinstance(meta, dict):
        _refuse("not_a_world")
    wid = meta.get("id")
    if not isinstance(wid, str) or not wid.strip(_JS_SPACE):
        _refuse("not_a_world")
    return meta


def _without_link(data: bytes, meta: dict[str, Any]) -> tuple[bytes, dict[str, Any]]:
    """``world.json`` without its ``api`` block (OW-10): the link and its key never travel.

    Untouched bytes when there is none (OW-11); otherwise the rest, written by the folder
    writer's serializer (``JSON.stringify(rest, null, 2)``), every other key in its order.
    """
    if "api" not in meta:
        return data, meta
    rest = {k: v for k, v in meta.items() if k != "api"}
    return encode(rest), rest


# ---------------------------------------------------------------------------
# The reader
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WorldFile:
    """A world file, read: what ``read_world_file`` returns, and nothing was written yet."""

    world_id: str
    #: ``world.json``'s ``name`` as the file has it; ``""`` when it has none
    name: str
    #: ``world.json``, parsed, without ``api``
    world: dict[str, Any]
    #: the world's files, relative to its folder, ``world.json`` included (without ``api``),
    #: in code point order of the path (the UTF-8 byte order, OW-13)
    entries: dict[str, bytes] = field(repr=False)
    #: the one top-level folder the world sat in, or None for a world at the archive's root
    top: str | None = None

    def to_folder(self, dest: str | os.PathLike[str]) -> Path:
        """Write the world as a folder at ``dest``, every entry byte for byte (OW-8, OW-9).

        ``dest`` must not exist, or be an empty directory, as for ``write_folder``: a folder
        is written whole, once, never over another. The tree is built in a sibling temp
        directory and renamed into place, so a crash never leaves a folder that looks
        complete. ``read_folder(dest)`` opens what this writes.
        """
        root = Path(dest)
        if root.exists() and (not root.is_dir() or any(root.iterdir())):
            raise FileExistsError(f"{root} exists and is not an empty directory; a folder is written whole, once")
        # The reader checked every path; a WorldFile built by hand is checked here, before any write.
        for rel in self.entries:
            if _path_fault(rel) or _name_fault(rel):
                _refuse("unsafe_path", f"The path {rel!r} cannot be written safely.")
        _check_collisions(self.entries)
        _check_file_and_folder(set(self.entries))
        tmp = root.parent / f".{root.name}.tmp-{uuid.uuid4().hex[:8]}"
        tmp.mkdir(parents=True)
        try:
            for rel, data in self.entries.items():
                target = tmp.joinpath(*rel.split("/"))
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
            if root.exists():
                root.rmdir()  # empty, checked above
            tmp.rename(root)
        except BaseException:
            shutil.rmtree(tmp, ignore_errors=True)
            raise
        return root


def read_world_file(
    source: bytes | bytearray | memoryview | str | os.PathLike[str],
    *,
    max_bytes: int = WORLD_FILE_MAX_BYTES,
    max_entries: int = WORLD_FILE_MAX_ENTRIES,
    skip: Callable[[str], bool] | None = None,
) -> WorldFile:
    """Read a world file (a path, or its bytes). Raises ``WorldFileError`` saying why, having
    returned nothing; the caller writes only what this returns (``WorldFile.to_folder``).

    ``skip`` leaves a file out of ``entries`` (a path relative to the world's folder); it is
    still checked and counted. The budget defaults to the spec's floor.
    """
    data = bytes(source) if isinstance(source, (bytes, bytearray, memoryview)) else Path(source).read_bytes()
    entries = _central_directory(data)

    # Every entry from the central directory alone, before anything is inflated.
    seen: dict[str, None] = {}
    files: list[_Cd] = []
    declared = 0
    for e in entries:
        name = e.name
        is_dir = name.endswith("/")
        bare = name[:-1] if is_dir else name
        fault = _path_fault(bare)
        if fault:
            _refuse("unsafe_path", f"The entry {name!r} {fault}.")
        kind = (e.external >> 16) & _S_IFMT
        if kind not in (0, _S_IFREG, _S_IFDIR):
            _refuse("link", f"The entry {name!r} is a link or a special file.")
        if e.flags & (_FLAG_ENCRYPTED | _FLAG_STRONG_ENCRYPTION):
            _refuse("method", f"The entry {name!r} is encrypted.")
        if e.method not in (0, 8):
            _refuse("method", f"The entry {name!r} uses method {e.method} (only stored and deflate).")
        if e.bad_utf8:
            _refuse("name", f"The entry {name!r} is flagged UTF-8 and is not.")
        if e.non_ascii and not e.flags & _FLAG_UTF8:
            _refuse("name", f"The entry {name!r} is not ASCII and lacks the UTF-8 flag.")
        bad = _name_fault(bare)
        if bad:
            _refuse("name", f"The entry {name!r}: {bad}.")
        if name in seen:
            _refuse("duplicate", f"The entry {name!r} appears twice.")
        seen[name] = None
        if is_dir:
            continue
        files.append(e)
        if len(files) > max_entries:
            _refuse("too_many", f"The world file holds more than {max_entries} files.")
        declared += e.usize
        if declared > max_bytes:
            _refuse("too_big", f"The world file declares more than {max_bytes} bytes.")
    _check_collisions(seen)
    names = {e.name for e in files}
    _check_file_and_folder(names)

    b = _Bytes(data)
    # OW-6: a marker is never required; one with other bytes refuses. Its shape is the writer's.
    marker = next((e for e in files if e.name == MARKER_NAME), None)
    if marker is not None and _inflate(b, marker) != WORLD_FILE_MEDIA_TYPE.encode("ascii"):
        _refuse("marker", "The mimetype entry holds other bytes than the OnlyWorlds media type.")

    # Exactly one world (OW-2); what sits beside its folder is ignored (OW-4), a dot-folder is never a world.
    candidates = [e.name for e in files if e.name != MARKER_NAME and not _is_junk(e.name)]
    if WORLD_FILE in candidates:
        prefix = ""
    else:
        roots = sorted(
            {
                n[: -len(WORLD_FILE)]
                for n in candidates
                if n.count("/") == 1 and n.endswith(f"/{WORLD_FILE}") and not n.startswith(".")
            }
        )
        if not roots:
            _refuse("not_a_world", "There is no world.json at the root or in one top-level folder.")
        if len(roots) > 1:
            _refuse("more_than_one", f"The file holds worlds in {', '.join(roots)}.")
        prefix = roots[0]
    # OW-5: no world.json inside the world but its own, except a producer's under records/.
    inside = {n for n in candidates if n.startswith(prefix)}
    for n in sorted(inside):
        rel = n[len(prefix) :]
        if rel != WORLD_FILE and rel.endswith(f"/{WORLD_FILE}") and not rel.startswith("records/"):
            _refuse("more_than_one", f"A second world.json sits inside the world: {n}.")

    # Every entry inflated within what it declares (OW-14), kept only when it is the world's.
    content: dict[str, bytes] = {}
    for e in files:
        body = _inflate(b, e)
        if e.name in inside:
            content[e.name] = body
    world_name = f"{prefix}{WORLD_FILE}"
    world_bytes, world = _without_link(content[world_name], _parse_world(content[world_name]))
    out: dict[str, bytes] = {}
    for n in sorted(content):
        path = n[len(prefix) :]
        if skip is not None and skip(path):
            continue
        out[path] = world_bytes if n == world_name else content[n]
    name_value = world.get("name")
    return WorldFile(
        world_id=str(world["id"]),
        name=name_value if isinstance(name_value, str) else "",
        world=world,
        entries=out,
        top=prefix[:-1] or None,
    )


# ---------------------------------------------------------------------------
# The writer
# ---------------------------------------------------------------------------

#: 1980-01-01 00:00, the zip format's first second: one input, one set of bytes (OW-12).
_STAMP = (1980, 1, 1, 0, 0, 0)
_DEFLATE_LEVEL = 6
_S_IFREG_644 = 0o100644


def _carried(rel: str, private_dir: str | None) -> bool:
    """Whether a path belongs in the archive: ``world.json``, a part (no dot-names or ``.meta``
    in a content folder; ``records/`` whole), or the one tool dot-folder the caller handed in."""
    if rel == WORLD_FILE:
        return True
    segs = rel.split("/")
    if len(segs) < 2:
        return False
    if segs[0].startswith("."):
        return segs[0] == private_dir
    if segs[0] not in WORLD_FILE_PARTS:
        return False
    if segs[0] == "records":
        return True
    return not any(s.startswith(".") for s in segs) and not rel.endswith(".meta")


def _collect(root: Path, private_dir: str | None) -> dict[str, Path]:
    """The folder's files the archive carries, relative path -> file. A link or junction where a
    carried file or folder would be refuses (``link``): the archive holds the folder, not what
    a link points at."""
    out: dict[str, Path] = {}

    def walk(directory: Path, rel_dir: str) -> None:
        with os.scandir(directory) as it:
            for entry in it:
                rel = f"{rel_dir}/{entry.name}" if rel_dir else entry.name
                top = rel.split("/")[0]
                if top not in (WORLD_FILE, private_dir, *WORLD_FILE_PARTS):
                    continue
                if entry.is_symlink() or entry.is_junction():
                    if entry.is_dir() or _carried(rel, private_dir):
                        _refuse("link", f"{rel!r} in the folder is a link; the archive holds files only.")
                    continue
                if entry.is_dir():
                    walk(Path(entry.path), rel)
                elif entry.is_file() and _carried(rel, private_dir):
                    out[rel] = Path(entry.path)

    walk(root, "")
    return out


#: The records manifest (§4.5 rule 3): a JSON array of one entry per producer.
RECORDS_MANIFEST = "records/RECORDS.json"


def _private_producers(raw: bytes, where: Path) -> set[str]:
    """The producers ``RECORDS.json`` marks ``"private": true`` (§4.5 rule 11; only the JSON
    boolean ``true`` marks one). A manifest the writer cannot read raises ``ValueError``: it
    leaves nothing out by guess (OW-8), so the caller fixes the file or asks for every record."""

    def unreadable(why: str) -> NoReturn:
        raise ValueError(
            f"{where} {why}, so the writer cannot tell which records are private and leaves nothing "
            "out by guess (OW-8). Fix the manifest, or pass include_private_records=True to carry "
            "every producer's records."
        )

    try:
        doc = json.loads(raw.decode("utf-8").removeprefix(_BOM), parse_constant=_reject_constant)
    except ValueError:  # not UTF-8, or not JSON
        unreadable("is not JSON")
    if not isinstance(doc, list) or not all(isinstance(e, dict) for e in doc):
        unreadable("is not a JSON array of objects")
    private: set[str] = set()
    for e in doc:
        if e.get("private") is True:
            producer = e.get("producer")
            if not isinstance(producer, str) or "/" in producer or _path_fault(producer):
                unreadable(f"marks private an entry whose producer {producer!r} is not one directory name")
            private.add(producer)
    return private


def _default_top(world: Mapping[str, Any]) -> str:
    """Atlas and Lantern's name for the top folder: ``<slug>-<id8>``, ``world`` for an unsluggable
    name. Presentation only (§3.1), and taken from ``world.json``, so the bytes never depend on
    where the folder sits on disk."""
    name = world.get("name")
    return f"{slugify(name if isinstance(name, str) else None) or 'world'}-{str(world['id'])[:8]}"


def _hidden_element_file(rel: str, src: Path) -> bool:
    """An element file (``elements/`` or legacy ``spatial/``, ``.json``) whose JSON object carries the
    hidden mark at the top level (``folder.is_hidden``). A file that is not a JSON object is not an
    element and is carried as it is, as ever."""
    segs = rel.split("/")
    if len(segs) < 2 or segs[0] not in (ELEMENTS_DIR, LEGACY_SPATIAL_DIR) or not rel.lower().endswith(".json"):
        return False
    try:
        body = json.loads(src.read_bytes().decode("utf-8-sig"))
    except (UnicodeDecodeError, ValueError):
        return False
    return isinstance(body, dict) and is_hidden(body)


def _plan(
    folder: str | os.PathLike[str],
    top_dir: str | None,
    private_dir: str | None,
    include_private_records: bool,
    include_hidden: bool = True,
    hidden_left_out: list[str] | None = None,
) -> tuple[str, list[tuple[str, Path | bytes]]]:
    root = Path(folder)
    if not root.is_dir():
        raise NotADirectoryError(f"{root} is not a folder")
    if private_dir is not None and (not private_dir.startswith(".") or _path_fault(private_dir) or "/" in private_dir):
        raise ValueError(f"private_dir must be one dot-folder name such as '.atlas', got {private_dir!r}")
    files = _collect(root, private_dir)
    if WORLD_FILE not in files:
        _refuse("not_a_world", f"{root} has no world.json.")
    if not include_private_records and RECORDS_MANIFEST in files:
        # OW-8's private clause: each private producer's directory left out whole; the manifest stays as it is.
        # Matched by OW-18's fold, not exactly: on a disk that ignores case, a manifest's `Fold`
        # names the directory `fold`, and an exact match would let its private records travel.
        private = {
            _fold_name(p) for p in _private_producers(files[RECORDS_MANIFEST].read_bytes(), files[RECORDS_MANIFEST])
        }

        def in_private(rel: str) -> bool:
            segs = rel.split("/")
            return len(segs) > 2 and segs[0] == "records" and _fold_name(segs[1]) in private

        files = {rel: src for rel, src in files.items() if not in_private(rel)}
    if not include_hidden:
        # A share (§4.8, h20 #11469): each hidden element's file left out whole; nothing else rewritten.
        hidden = sorted(rel for rel, src in files.items() if _hidden_element_file(rel, src))
        files = {rel: src for rel, src in files.items() if rel not in set(hidden)}
        if hidden_left_out is not None:
            hidden_left_out.extend(hidden)
    raw = files[WORLD_FILE].read_bytes()
    world_bytes, world = _without_link(raw, _parse_world(raw))
    top = _default_top(world) if top_dir is None else top_dir
    if _path_fault(top) or "/" in top:
        _refuse("unsafe_path", f"The top folder {top!r} is not one plain folder name.")
    keys: list[str] = []
    for rel in files:
        fault = _path_fault(rel)
        if fault:
            _refuse("unsafe_path", f"The path {rel!r} {fault}.")
        key = f"{top}/{rel}"
        bad = _name_fault(key)
        if bad:
            _refuse("name", f"The path {key!r}: {bad}.")
        try:
            key.encode("utf-8")
        except UnicodeEncodeError:
            _refuse("name", f"The path {key!r} is not valid Unicode.")
        keys.append(key)
    _check_collisions([MARKER_NAME, *keys])
    _check_file_and_folder({MARKER_NAME, *keys})
    plan: list[tuple[str, Path | bytes]] = []
    for rel in sorted(files):  # str order is code point order, which is the UTF-8 byte order (OW-13)
        plan.append((rel, world_bytes if rel == WORLD_FILE else files[rel]))
    return top, plan


def _entry(name: str, method: int) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=_STAMP)
    info.compress_type = method
    # A regular file, rw-r--r--, said the Unix way (OW-20 reads the mode). Set, never left to zipfile,
    # whose defaults follow the host (create_system 0 on Windows, 3 elsewhere) and turn a zero mode
    # into 0o600: one input, one set of bytes, on every machine.
    info.create_system = 3
    info.external_attr = _S_IFREG_644 << 16
    return info


def _write(out: IO[bytes], top: str, plan: list[tuple[str, Path | bytes]]) -> None:
    with zipfile.ZipFile(out, "w", allowZip64=True) as zf:
        zf.writestr(_entry(MARKER_NAME, zipfile.ZIP_STORED), WORLD_FILE_MEDIA_TYPE.encode("ascii"))
        for rel, src in plan:
            data = src if isinstance(src, bytes) else src.read_bytes()
            if rel.lower().endswith(".json"):
                zf.writestr(_entry(f"{top}/{rel}", zipfile.ZIP_DEFLATED), data, compresslevel=_DEFLATE_LEVEL)
            else:
                zf.writestr(_entry(f"{top}/{rel}", zipfile.ZIP_STORED), data)


def world_file_bytes(
    folder: str | os.PathLike[str],
    *,
    top_dir: str | None = None,
    private_dir: str | None = None,
    include_private_records: bool = False,
    include_hidden: bool = True,
    hidden_left_out: list[str] | None = None,
) -> bytes:
    """The world file for the folder at ``folder``, as bytes. See ``write_world_file``: the
    same keywords, the same refusals, private records left out unless
    ``include_private_records=True``, hidden elements kept unless ``include_hidden=False``."""
    top, plan = _plan(folder, top_dir, private_dir, include_private_records, include_hidden, hidden_left_out)
    buf = io.BytesIO()
    _write(buf, top, plan)
    return buf.getvalue()


def write_world_file(
    folder: str | os.PathLike[str],
    path: str | os.PathLike[str],
    *,
    top_dir: str | None = None,
    private_dir: str | None = None,
    include_private_records: bool = False,
    include_hidden: bool = True,
    hidden_left_out: list[str] | None = None,
) -> Path:
    """Write the folder at ``folder`` as one world file at ``path``; returns ``path``.

    - One world, under one top-level folder ``top_dir`` (default ``<slug>-<id8>`` from
      ``world.json``, as Atlas and Lantern name it).
    - The ``mimetype`` marker first and stored, no extra field (OW-6); then ``world.json``
      and the folder's parts (``WORLD_FILE_PARTS``) in the UTF-8 byte order of their names
      (OW-13), every entry stamped 1980-01-01 00:00 (OW-12); ``.json`` deflated, the rest
      stored. The same folder gives the same bytes on one Python and zlib build.
    - Only ``world.json``, ``elements/``, ``spatial/``, ``media/`` and ``records/`` travel
      (OW-7); inside the parts no dot-file and no ``.meta``, except ``records/``, which
      travels whole and byte-exact (OW-8). ``private_dir`` (one name, such as ``".atlas"``)
      carries that tool's dot-folder too, and makes the file a private copy, not a portable
      ``.owworld``.
    - Private records are left out (OW-8, §4.5 rule 11): every file under
      ``records/<producer>/`` for each producer whose entry in ``records/RECORDS.json`` has
      ``"private": true`` (the JSON boolean only; ``"true"`` or ``1`` marks nothing), the
      directory whole. ``RECORDS.json`` itself travels byte-exact, its private entries kept,
      so a reader learns a producer was left out. No manifest, nothing is private.
      ``include_private_records=True`` (the caller asks) carries every producer's records
      whole, and the manifest is not read.
    - Hidden elements are kept (folder format §4.8; Skeld, OW Atlas h20 #11469): a world file is
      a copy, and an element file carrying ``hidden: true`` at the top level travels byte for
      byte. ``include_hidden=False``, for a file made to hand to someone else (a share), leaves
      every such file in ``elements/`` or ``spatial/`` out whole (any value of the mark but null
      and ``false`` counts, so a doubt leaves it out); ``hidden_left_out``, a list the caller
      passes, receives each left-out file's path inside the folder (``elements/character/x.json``),
      sorted, and its length is the count. Nothing else is rewritten: a visible element that links
      to a hidden one keeps the id, which dangles in the file (a reader meets it as a link to an
      element the world does not hold).
    - ``world.json`` is carried byte for byte, ``producer``, ``source`` and
      ``format_version`` included: a writer that copies never rewrites a folder's
      provenance. The one change is an ``api`` block, which is never written (OW-10).
    - zip64 when the archive needs it (``allowZip64``): a classic zip up to 65,535 entries.

    Refuses (``WorldFileError``) a folder without a readable ``world.json`` with an id
    (``not_a_world``), a path no disk can hold (``name``), two names that fold to one
    (``collision``), a path that is a file and a folder or an unsafe ``top_dir``
    (``unsafe_path``), and a link where a carried file would be (``link``). A
    ``RECORDS.json`` it cannot read (not UTF-8 JSON, not an array of objects, or a private
    entry whose ``producer`` is not one directory name) raises a plain ``ValueError`` naming
    the file, unless ``include_private_records=True``: the writer never guesses which
    records are private. The archive is written beside ``path`` and renamed into place, so
    a crash never leaves half a file.
    """
    top, plan = _plan(folder, top_dir, private_dir, include_private_records, include_hidden, hidden_left_out)
    target = Path(path)
    tmp = target.parent / f".{target.name}.tmp-{uuid.uuid4().hex[:8]}"
    try:
        with open(tmp, "wb") as fh:
            _write(fh, top, plan)
        os.replace(tmp, target)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    return target

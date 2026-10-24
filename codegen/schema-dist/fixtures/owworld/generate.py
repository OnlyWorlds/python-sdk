#!/usr/bin/env python3
"""The .owworld conformance fixture set (OW Council item #522): every zip, and verdicts.json, from one script.

    python generate.py                 # writes fixtures/ beside this file (every zip and verdicts.json)
    python generate.py --out DIR       # writes them to DIR instead
    python generate.py --large DIR     # also writes the big cases (500,001 and 500,000 entries, 2 GiB inflated) to DIR;
                                       # never part of the set, never committed
    python generate.py --out DIR --without records/lab/world.json
                                       # a diagnostic copy without one base file, to read a reader past one gap

Standard library only. The tests (OW-1..OW-22) are Quillon's lane report
`Armature/Notes/2026-10-21-owworld-as-tests.md`; each fixture names the test it serves and carries one cause, so a
reader cannot pass a refusal by luck.

DETERMINISM. Every zip is written by `build_zip` below, by hand: entries in the order given (sorted by the UTF-8 bytes
of their names unless a fixture tests order), every entry stamped 1980-01-01 00:00, no extra fields, no comments. No
byte depends on the clock, the file system or the zlib build: deflated entries use `deflate_literal` (a fixed-Huffman
deflate stream of literals, written here), and the one zip bomb uses `deflate_zero_bomb` (a dynamic-Huffman stream,
also written here). The only library compressor used is liblzma, for the one LZMA entry (fail-OW-21-lzma), whose
bytes depend on the liblzma build. Rerunning gives identical bytes; README.md records the sha256 check of two runs.

WHY BY HAND. Several refusals need zips `zipfile` will not write: a name twice, a symlink's mode, an encrypted entry,
a size that lies, a deflate64 or LZMA method on a plain entry, a non-ASCII name without the UTF-8 flag, a zip64 end
record on a small archive. One writer that lays out every header itself makes each of those a field, not a patch.
"""

import argparse
import hashlib
import io
import json
import os
import struct
import sys
import zipfile
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))

MIMETYPE = b"application/vnd.onlyworlds.world+zip"
WORLD_ID = "0695db52-0000-7000-8000-00000000abbe"
TOP = "abbey/"

DOS_DATE_1980 = (1 << 5) | 1  # 1980-01-01: year 0, month 1, day 1
DOS_TIME_0 = 0


def dos_stamp(y, mo, d, h, mi, s):
    return ((y - 1980) << 9) | (mo << 5) | d, (h << 11) | (mi << 5) | (s // 2)


# ---------------------------------------------------------------------------------------------------------------------
# Deflate, written here so no byte depends on the zlib build
# ---------------------------------------------------------------------------------------------------------------------

class Bits:
    """An LSB-first bit writer, as deflate packs its stream (RFC 1951 3.1.1)."""

    def __init__(self):
        self.out = bytearray()
        self.acc = 0
        self.n = 0

    def put(self, value, count):
        """A field: `count` bits of `value`, least significant first."""
        self.acc |= (value & ((1 << count) - 1)) << self.n
        self.n += count
        while self.n >= 8:
            self.out.append(self.acc & 0xFF)
            self.acc >>= 8
            self.n -= 8

    def code(self, code, length):
        """A Huffman code: its most significant bit first (RFC 1951 3.1.1)."""
        rev = 0
        for i in range(length):
            rev = (rev << 1) | ((code >> i) & 1)
        self.put(rev, length)

    def zeros(self, count):
        """`count` zero bits, whole bytes in bulk."""
        while count and self.n:
            self.put(0, 1)
            count -= 1
        self.out.extend(b"\0" * (count // 8))
        self.put(0, count % 8)

    def flush(self):
        if self.n:
            self.out.append(self.acc & 0xFF)
            self.acc = 0
            self.n = 0
        return bytes(self.out)


def deflate_literal(data):
    """One final fixed-Huffman block holding every byte as a literal (RFC 1951 3.2.6). Valid deflate, no matches."""
    b = Bits()
    b.put(1, 1)  # BFINAL
    b.put(1, 2)  # BTYPE 01: fixed Huffman
    for byte in data:
        if byte < 144:
            b.code(0x30 + byte, 8)
        else:
            b.code(0x190 + byte - 144, 9)
    b.code(0, 7)  # 256, end of block
    return b.flush()


def deflate_stored(data):
    """Stored deflate blocks (RFC 1951 3.2.4): the same bytes are a valid deflate64 stream, which keeps stored blocks."""
    out = bytearray()
    chunks = [data[i:i + 65535] for i in range(0, len(data), 65535)] or [b""]
    for i, chunk in enumerate(chunks):
        out.append(1 if i == len(chunks) - 1 else 0)
        out += struct.pack("<HH", len(chunk), len(chunk) ^ 0xFFFF)
        out += chunk
    return bytes(out)


def deflate_zero_bomb(matches):
    """
    A deflate stream inflating to 1 + 258 * `matches` zero bytes in about matches / 4 bytes: one dynamic-Huffman block
    holding a literal 0, then `matches` copies of (length 258, distance 1), two bits each.

    Codes: literal/length 0 -> '10', 256 (end) -> '11', 285 (length 258) -> '0'; distance 0 (distance 1) -> '0', a
    single one-bit distance code, which RFC 1951 3.2.7 allows. The code lengths are sent with the code-length alphabet
    18 -> '0', 1 -> '10', 2 -> '11'.
    """
    b = Bits()
    b.put(1, 1)   # BFINAL
    b.put(2, 2)   # BTYPE 10: dynamic Huffman
    b.put(29, 5)  # HLIT: 286 literal/length codes
    b.put(0, 5)   # HDIST: 1 distance code
    b.put(14, 4)  # HCLEN: 18 code-length codes
    order = [16, 17, 18, 0, 8, 7, 9, 6, 10, 5, 11, 4, 12, 3, 13, 2, 14, 1]
    cl_len = {18: 1, 1: 2, 2: 2}
    for sym in order:
        b.put(cl_len.get(sym, 0), 3)
    cl_code = {18: (0, 1), 1: (2, 2), 2: (3, 2)}

    def emit(sym, extra=None):
        b.code(*cl_code[sym])
        if extra is not None:
            b.put(extra, 7)

    emit(2)            # literal 0: length 2
    emit(18, 138 - 11)  # literals 1..138: unused
    emit(18, 117 - 11)  # literals 139..255: unused
    emit(2)            # 256 (end): length 2
    emit(18, 28 - 11)  # 257..284: unused
    emit(1)            # 285 (length 258): length 1
    emit(1)            # distance code 0: length 1
    b.code(2, 2)       # literal 0
    b.zeros(2 * matches)  # 285 '0' then distance 0 '0', `matches` times
    b.code(3, 2)       # end of block
    return b.flush()


def crc_of_zeros(count):
    crc, block = 0, b"\0" * (1 << 24)
    while count:
        n = min(count, len(block))
        crc = zlib.crc32(block[:n], crc)
        count -= n
    return crc


def lzma_payload(data):
    """LZMA as zip method 14 holds it (APPNOTE 5.8.8): liblzma through `zipfile`, the entry's data lifted out."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        info = zipfile.ZipInfo("x", date_time=(1980, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_LZMA
        z.writestr(info, data)
    raw = buf.getvalue()
    csize, = struct.unpack("<I", raw[18:22])
    n, e = struct.unpack("<HH", raw[26:30])
    return raw[30 + n + e:30 + n + e + csize]


# ---------------------------------------------------------------------------------------------------------------------
# Traditional PKWARE encryption (APPNOTE 6.1), so the encrypted entry is a real one
# ---------------------------------------------------------------------------------------------------------------------

_CRC_TABLE = []
for _i in range(256):
    _c = _i
    for _ in range(8):
        _c = (_c >> 1) ^ 0xEDB88320 if _c & 1 else _c >> 1
    _CRC_TABLE.append(_c)


def zipcrypto(payload, crc, password=b"owworld"):
    """`payload` encrypted with ZipCrypto; the 12-byte header is fixed (no clock, no randomness), its last byte the
    CRC's high byte as APPNOTE 6.1.6 asks when no data descriptor follows."""
    keys = [0x12345678, 0x23456789, 0x34567890]

    def update(byte):
        keys[0] = _CRC_TABLE[(keys[0] ^ byte) & 0xFF] ^ (keys[0] >> 8)
        keys[1] = (keys[1] + (keys[0] & 0xFF)) & 0xFFFFFFFF
        keys[1] = (keys[1] * 134775813 + 1) & 0xFFFFFFFF
        keys[2] = _CRC_TABLE[(keys[2] ^ (keys[1] >> 24)) & 0xFF] ^ (keys[2] >> 8)

    for ch in password:
        update(ch)
    header = hashlib.sha256(b"owworld-zipcrypto-header").digest()[:11] + bytes([crc >> 24])
    out = bytearray()
    for byte in header + payload:
        t = (keys[2] | 2) & 0xFFFF
        out.append(byte ^ (((t * (t ^ 1)) >> 8) & 0xFF))
        update(byte)
    return bytes(out)


# ---------------------------------------------------------------------------------------------------------------------
# The zip writer
# ---------------------------------------------------------------------------------------------------------------------

class Entry:
    """One zip entry, every header field explicit. `name` is a str (encoded UTF-8) or raw bytes."""

    def __init__(self, name, data=b"", method=None, *, utf8_flag=None, stamp=None, system=0, mode=None,
                 payload=None, crc=None, size=None, declared_size=None, encrypt=False, flags=0):
        self.name = name.encode("utf-8") if isinstance(name, str) else name
        self.data = data
        self.method = method if method is not None else (8 if self.name.lower().endswith(b".json") else 0)
        is_ascii = all(c < 0x80 for c in self.name)
        self.flags = flags
        if utf8_flag if utf8_flag is not None else not is_ascii:
            self.flags |= 0x0800  # bit 11: the name is UTF-8
        self.date, self.time = stamp or (DOS_DATE_1980, DOS_TIME_0)
        self.system = system
        self.ext_attr = (mode << 16) if mode is not None else 0
        if mode is not None and (mode & 0o170000) == 0o040000:
            self.ext_attr |= 0x10  # the MS-DOS directory bit beside the Unix mode
        self.crc = crc if crc is not None else zlib.crc32(data)
        self.size = size if size is not None else len(data)
        if payload is None:
            payload = {0: lambda d: d, 8: deflate_literal, 9: deflate_stored, 14: lzma_payload}[self.method](data)
        if self.method == 14:
            self.flags |= 0x0002  # the LZMA end-of-stream marker is present, as zipfile writes it
        if encrypt:
            payload = zipcrypto(payload, self.crc)
            self.flags |= 0x0001
        self.payload = payload
        self.declared = declared_size if declared_size is not None else self.size
        self.version = {14: 63, 9: 21}.get(self.method, 20)


def utf8_key(entry):
    return entry.name


def build_zip(entries, zip64_end=False, sort=True, disk=0):
    """The archive's bytes. `sort` orders entries by the UTF-8 bytes of their names (code point order). `disk` > 0
    writes a classic end record saying this file is that disk of a spanned set, the directory starting on disk 0."""
    if sort:
        entries = sorted(entries, key=utf8_key)
    out = bytearray()
    central = bytearray()
    for e in entries:
        offset = len(out)
        out += struct.pack("<IHHHHHIIIHH", 0x04034B50, e.version, e.flags, e.method, e.time, e.date,
                           e.crc, len(e.payload), e.declared, len(e.name), 0)
        out += e.name
        out += e.payload
        central += struct.pack("<IHHHHHHIIIHHHHHII", 0x02014B50, (e.system << 8) | 20, e.version, e.flags,
                               e.method, e.time, e.date, e.crc, len(e.payload), e.declared, len(e.name), 0, 0, 0,
                               0, e.ext_attr, offset)
        central += e.name
    cd_offset = len(out)
    out += central
    count = len(entries)
    if zip64_end or count > 0xFFFF:
        z64_offset = len(out)
        out += struct.pack("<IQHHIIQQQQ", 0x06064B50, 44, 45, 45, 0, 0, count, count, len(central), cd_offset)
        out += struct.pack("<IIQI", 0x07064B50, 0, z64_offset, 1)
        out += struct.pack("<IHHHHIIH", 0x06054B50, 0, 0, 0xFFFF, 0xFFFF, 0xFFFFFFFF, 0xFFFFFFFF, 0)
    else:
        out += struct.pack("<IHHHHIIH", 0x06054B50, disk, 0, count, count, len(central), cd_offset, 0)
    return bytes(out)


# ---------------------------------------------------------------------------------------------------------------------
# The base world
# ---------------------------------------------------------------------------------------------------------------------

def jbytes(obj):
    """JSON as the folder format writes it: two-space indent, UTF-8, LF, a final newline (spec section 5)."""
    return (json.dumps(obj, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def png_1x1():
    """A 1x1 RGBA PNG, its zlib stream a stored block, so no byte depends on the zlib build."""
    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))
    raw = b"\x00\x8f\x6b\x3a\xff"  # filter 0, one pixel
    stream = b"\x78\x01" + b"\x01" + struct.pack("<HH", len(raw), len(raw) ^ 0xFFFF) + raw + struct.pack(
        ">I", zlib.adler32(raw))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", stream) + chunk(b"IEND", b""))


PNG = png_1x1()


def element(n, name, **more):
    return jbytes(dict({"id": "0695db83-0000-7000-8000-%012x" % (0xab00 + n), "name": name}, **more))


WORLD = {
    "id": WORLD_ID,
    "name": "Watabou's Abbey",
    "description": "A small abbey world: the .owworld conformance fixtures' base.",
    "format_version": "0.3.12",
    "source": {"server": "https://www.onlyworlds.com", "world": WORLD_ID, "at": "2026-10-21T00:00:00Z"},
    "exported_as": {"kind": "owner", "role": "owner", "character": None},
}


DIAGNOSTIC_DROP = set()  # --without: base files left out of a diagnostic copy (never the set itself)


def base_files():
    """The base world, relative to its folder: what every fixture starts from. Order is irrelevant (sorted later)."""
    files = {
        "world.json": jbytes(WORLD),
        "elements/character/ana--0000ab01.json": element(1, "Ana", supertype="Novice"),
        "elements/character/brother-tomas--0000ab02.json": element(2, "Brother Tomas", supertype="Abbot"),
        "elements/location/abbey--0000ab03.json": element(3, "The Abbey", supertype="Monastery"),
        "media/a.png": PNG,
        "records/RECORDS.json": jbytes([{"producer": "lab", "format": "binary ledger rows", "version": "1",
                                         "deltas": False}]),
        # A producer's data, byte-exact: braces, CRLF, a UTF-8 BOM, NUL, 0xFF. Any re-encoding shows.
        "records/lab/ledger.bin": bytes.fromhex("7B7D0D0AEFBBBF00FF"),
        # A producer's own world.json (section 4.5 rule 6a: it travels; it is never a second world). It even has an id.
        "records/lab/world.json": jbytes({"id": "lab-settings", "seed": 7}),
        # A producer's own dot-file and its own x.meta beside its x (not Unity's: no fileFormatVersion/guid head).
        "records/lab/.cursor": b"42\n",
        "records/lab/ledger.bin.meta": b"lab: 9 bytes, one row, written by the lab\n",
    }
    return {rel: data for rel, data in files.items() if rel not in DIAGNOSTIC_DROP}


PRIVATE_PRODUCER = "fold"


def private_files():
    """The base world plus a second producer marked private (section 4.5 rule 11): the private case's source. Its
    manifest names both producers; its directory holds a history spine keyed to an element id (rule 12) and a
    dot-file. The base world itself never changes, so no other fixture's bytes move."""
    files = base_files()
    files["records/RECORDS.json"] = jbytes([
        {"producer": "lab", "format": "binary ledger rows", "version": "1", "deltas": False},
        {"producer": PRIVATE_PRODUCER, "format": "a history spine, JSON Lines keyed to element ids", "version": "1",
         "deltas": False, "private": True},
    ])
    files["records/fold/spine.jsonl"] = (b'{"element": "0695db83-0000-7000-8000-00000000ab02", '
                                         b'"note": "the abbot keeps the keys"}\n')
    files["records/fold/.head"] = b"1\n"
    return files


def world_entries(files, top=TOP, **kw):
    return [Entry(top + rel, data, **kw) for rel, data in files.items()]


def base(top=TOP, extra=None, drop=(), replace=None, **kw):
    files = base_files()
    for rel in drop:
        del files[rel]
    files.update(replace or {})
    entries = world_entries(files, top, **kw)
    for item in extra or []:
        entries.append(item if isinstance(item, Entry) else Entry(top + item[0], item[1]))
    return entries


UNITY_META = b"fileFormatVersion: 2\nguid: 3f2a9c1e5b7d4e8fa0b1c2d3e4f50617\nTextScriptImporter:\n  userData: \n"

JSON_EXPORT = jbytes({  # the shape of keel's one-file JSON export (schema-dist example/world-export.json), small
    "world": {"id": WORLD_ID, "name": "Watabou's Abbey"},
    "Character": [{"id": "0695db83-0000-7000-8000-00000000ab01", "name": "Ana"}],
    "Location": [{"id": "0695db83-0000-7000-8000-00000000ab03", "name": "The Abbey"}],
})


# ---------------------------------------------------------------------------------------------------------------------
# The fixtures
# ---------------------------------------------------------------------------------------------------------------------

def fixtures():
    """(file, bytes, verdict) for every fixture, in the set's order."""
    F = []

    def add(file, content, *, test, rule, reader="accept", writer=None, role="reader", reason=None, open_=None,
            lean=None, covers=None, roundtrip=False, strips=None, should=None, budget=None, source=None, side=None):
        if writer is None:
            writer = "accept" if reader == "accept" else "refuse"
        v = {"file": file, "test": test, "role": role, "reader": reader, "writer": writer, "rule": rule}
        if source:
            v["source"] = source
        if side:
            v["side"] = side
        if reason:
            v["reason"] = reason
        if strips:
            v["strips"] = strips
        if budget:
            v["budget"] = budget
        if should:
            v["should"] = should
        if covers:
            v["covers"] = covers
        if open_:
            v["open"] = open_
        if lean:
            v["lean"] = lean
        if roundtrip:
            v["roundtrip"] = True
        F.append((file, content, v))

    # -- The good file, and identity -------------------------------------------------------------------------------
    good = build_zip(base())
    add("pass-good.owworld", good, test="OW-1", covers=["OW-1", "OW-2", "OW-3", "OW-5", "OW-8", "OW-11", "OW-12",
                                                          "OW-13", "OW-14", "OW-16", "OW-17", "OW-18", "OW-19",
                                                          "OW-20", "OW-21", "OW-22"],
        rule="The good world: one top folder, a string id, records/ whole (its own world.json, dot-file and x.meta "
             "included), sorted, 1980 stamps, methods 0 and 8.")
    add("pass-OW-1-renamed.zip", good, test="OW-1",
        rule="The content decides, not the name: pass-good's exact bytes under .zip read the same.")
    add("fail-OW-1-json-export.owworld", JSON_EXPORT, test="OW-1", reader="refuse", reason="not_openable",
        rule="A JSON export renamed .owworld is not a zip: refused.")

    # -- OW-2: exactly one world -------------------------------------------------------------------------------------
    add("pass-OW-2-root.zip", build_zip(base(top="")), test="OW-2",
        rule="world.json at the archive's root is the same world (spec section 4: readers also accept it).")
    two = base(top="a/") + base(top="b/")
    add("fail-OW-2-two-worlds.owworld", build_zip(two), test="OW-2", reader="refuse", reason="more_than_one",
        rule="Two top folders each holding world.json: two worlds, refused.")
    add("fail-OW-2-root-and-folder.owworld", build_zip(base(top="") + [Entry("b/world.json", jbytes(WORLD))]),
        test="OW-2", reader="refuse", reason="more_than_one",
        rule="world.json at the root and in a top folder: two worlds, refused.")
    add("fail-OW-2-too-deep.owworld", build_zip(base(top="x/y/")), test="OW-2", reader="refuse",
        reason="not_a_world", rule="world.json only two folders down (x/y/world.json): no world, refused.")
    add("fail-OW-2-no-world.owworld", build_zip(base(drop=["world.json"])), test="OW-2", reader="refuse",
        reason="not_a_world", rule="No world.json anywhere a world may sit: refused.")

    # -- OW-3: world.json is an object with a non-empty string id ---------------------------------------------------
    def world_with(obj_or_bytes):
        data = obj_or_bytes if isinstance(obj_or_bytes, bytes) else jbytes(obj_or_bytes)
        return build_zip(base(replace={"world.json": data}))

    no_id = {k: v for k, v in WORLD.items() if k != "id"}
    for slug, value, why in [
        ("no-id", no_id, "has no id"),
        ("numeric-id", dict(WORLD, id=7), "has a numeric id (7)"),
        ("blank-id", dict(WORLD, id="  "), "has a blank id"),
        ("array", [WORLD_ID], "is a JSON array, not an object"),
        ("unparseable", b'{"id": "' + WORLD_ID.encode() + b'", "name": \n', "does not parse"),
    ]:
        add("fail-OW-3-%s.owworld" % slug, world_with(value), test="OW-3", reader="refuse", reason="not_a_world",
            rule="world.json %s: not a world, refused." % why)

    # -- OW-4: files beside the world's folder (ruled: a reader ignores them, a writer never emits one) -------------
    add("pass-OW-4-readme.owworld", build_zip(base() + [Entry("README.txt", b"An abbey.\n")]), test="OW-4",
        writer="refuse",
        rule="A README.txt beside the world's folder: a reader ignores it; a writer never emits it.")
    add("pass-OW-4-tool-folder.owworld",
        build_zip(base() + [Entry(".atlas/world.json", b'{"charts": []}\n')]), test="OW-4", writer="refuse",
        rule="A tool's dot-folder beside the world, holding its own world.json (Unity's UT fixture shape, which "
             "section 4.7 names: accept): a dot-folder is never a world; a reader ignores it, a writer never emits it.")
    add("pass-OW-4-archive-junk.owworld",
        build_zip(base() + [Entry("__MACOSX/abbey/._world.json", b"\x00\x05\x16\x07\x00\x02\x00\x00Mac OS X"),
                            Entry(".DS_Store", b"\x00\x00\x00\x01Bud1")]), test="OW-4", writer="refuse",
        rule="Archive junk a re-zip picks up (__MACOSX/, .DS_Store): never part of a world; ignored by a reader.")

    # -- OW-5: no second world inside the world; records/ never is one ----------------------------------------------
    add("fail-OW-5-nested.owworld", build_zip(base(extra=[("inner/world.json", jbytes(dict(WORLD, id="inner")))])),
        test="OW-5", reader="refuse", reason="more_than_one",
        rule="A world.json inside the world (abbey/inner/world.json), not under records/: refused. (pass-good "
             "holds records/lab/world.json, which must pass.)")

    # -- OW-6: the marker entry (ruled: a writer SHOULD place it; a reader never requires it, refuses other bytes) --
    def marker(data=MIMETYPE, method=0):
        return Entry("mimetype", data, method=method)

    add("pass-OW-6-marker.owworld", build_zip([marker()] + sorted(base(), key=utf8_key), sort=False), test="OW-6",
        rule="mimetype first, stored, no extra field, exactly application/vnd.onlyworlds.world+zip: accepted (and "
             "pass-good, with none, is accepted too: a reader MUST NOT require it).")
    add("fail-OW-6-marker-wrong.owworld", build_zip([marker(b"application/zip")] + sorted(base(), key=utf8_key),
                                                    sort=False),
        test="OW-6", reader="refuse", reason="marker",
        rule="A mimetype entry holding application/zip: a marker present with other bytes, refused.")
    add("fail-OW-6-marker-newline.owworld", build_zip([marker(MIMETYPE + b"\n")] + sorted(base(), key=utf8_key),
                                                      sort=False),
        test="OW-6", reader="refuse", reason="marker",
        rule="The right string with a trailing newline: the bytes are exactly the media type, ASCII, no newline; "
             "other bytes, refused.")
    add("fail-OW-6-marker-bom.owworld", build_zip([marker(b"\xef\xbb\xbf" + MIMETYPE)] + sorted(base(), key=utf8_key),
                                                  sort=False),
        test="OW-6", reader="refuse", reason="marker",
        rule="The UTF-8 byte order mark before the media type: a reader that decodes the entry as text first "
             "drops the mark and passes it (the TypeScript reader did, SDK 4.53.2 fixed it, Kael h58 #9992); the "
             "bytes are compared as bytes, so these are other bytes, refused.")
    # The shape (first, stored, no extra field) is the writer's SHOULD; the reader's MUST is about the bytes only.
    # Ruled (h58 #9817, U2): the bytes decide the reader; a marker with the right bytes in the wrong shape is read.
    add("pass-OW-6-marker-deflated.owworld", build_zip([marker(method=8)] + sorted(base(), key=utf8_key),
                                                       sort=False),
        test="OW-6", writer="refuse",
        rule="The right bytes, deflated: a reader reads it (its bytes are the media type); a writer stores the "
             "marker, so it reads from the file's opening bytes.")
    add("pass-OW-6-marker-not-first.owworld", build_zip(base() + [marker()]), test="OW-6", writer="refuse",
        rule="The right bytes, stored, but sorted after abbey/...: a reader reads it; a writer puts the marker "
             "first.")

    # -- OW-7: a writer emits only the folder's parts (writer; ruled) -----------------------------------------------
    for slug, rel, data, what in [
        ("readme", "README.md", b"# The Abbey\n", "a README.md in the world's folder"),
        ("git", ".git/HEAD", b"ref: refs/heads/main\n", "a .git/ folder"),
        ("unity-meta", "elements/character/ana--0000ab01.json.meta", UNITY_META, "Unity's .meta beside an element"),
        ("tool-folder", ".atlas/charts.json", jbytes({"charts": ["c1"]}),
         "a tool's .atlas/ folder (a private copy when the caller asks, never a portable .owworld)"),
    ]:
        add("fail-OW-7-%s.owworld" % slug, build_zip(base(extra=[(rel, data)])), test="OW-7", role="writer",
            writer="refuse",
            rule="Writer: %s is not one of the folder's parts (world.json, elements/, spatial/, media/, records/); "
                 "a reader still opens the file." % what)

    # -- OW-8: records/ travels whole and byte-exact (writer) --------------------------------------------------------
    add("fail-OW-8-records-missing.owworld", build_zip(base(drop=["records/lab/ledger.bin"])), test="OW-8",
        role="writer", writer="refuse",
        rule="Writer: records/lab/ledger.bin left out; records/ travels whole (section 4.5 rule 6a).")
    add("fail-OW-8-records-reencoded.owworld",
        build_zip(base(replace={"records/lab/ledger.bin": bytes.fromhex("7B7D0A00FF")})), test="OW-8",
        role="writer", writer="refuse",
        rule="Writer: ledger.bin re-encoded (CRLF to LF, BOM stripped); records/ travels byte-exact.")
    add("fail-OW-8-producer-meta-dropped.owworld", build_zip(base(drop=["records/lab/ledger.bin.meta"])),
        test="OW-8", role="writer", writer="refuse",
        rule="Writer: the producer's own ledger.bin.meta dropped as if it were Unity's litter.")

    # -- OW-8: private records (section 4.5 rule 11): left out unless asked, whole either way (writer, two-sided) ---
    # One source (private_files: the base plus the private producer fold), two sides a writer may emit, and the two
    # ways to get it wrong. The manifest travels byte-exact on both sides: the entry stays, only the directory goes.
    priv = private_files()
    fold = "records/%s/" % PRIVATE_PRODUCER

    def private_world(drop=(), replace=None):
        files = {rel: data for rel, data in priv.items() if rel not in drop}
        files.update(replace or {})
        return build_zip(world_entries(files))

    add("pass-OW-8-private-left-out.owworld",
        private_world(drop=[rel for rel in priv if rel.startswith(fold)]), test="OW-8", role="writer",
        source="private", side="default",
        rule="Writer, the default side: records/fold/ is marked private in RECORDS.json, so an export, share or "
             "snapshot leaves the whole directory out; RECORDS.json travels byte-exact, its fold entry kept.")
    add("pass-OW-8-private-asked.owworld", private_world(), test="OW-8", role="writer", source="private",
        side="asked",
        rule="Writer, the asked side: the caller asked for private records, so records/fold/ travels whole and "
             "byte-exact, its dot-file included, like any producer's.")
    add("fail-OW-8-private-partial.owworld", private_world(drop=[fold + "spine.jsonl"]), test="OW-8",
        role="writer", writer="refuse", source="private",
        rule="Writer: records/fold/ half carried (.head in, spine.jsonl out); a private directory goes whole or not "
             "at all.")
    add("fail-OW-8-private-manifest-rewritten.owworld",
        private_world(drop=[rel for rel in priv if rel.startswith(fold)],
                      replace={"records/RECORDS.json": base_files()["records/RECORDS.json"]}),
        test="OW-8", role="writer", writer="refuse", source="private",
        rule="Writer: records/fold/ left out and its entry cut from RECORDS.json; the manifest travels byte-exact, "
             "so a reader learns a private producer was left out rather than never there.")

    # -- OW-9: what a reader does not understand comes through a rewrite (round trip) --------------------------------
    add("pass-OW-9-unknown.owworld",
        build_zip(base(extra=[("elements/vessel/ark--0000ab0a.json", element(10, "The Ark")),
                              ("media/notes.xyz", b"\x00owworld notes\x00\xff")])),
        test="OW-9", role="roundtrip", roundtrip=True,
        rule="Read then write: entries a reader does not understand inside the folder's parts (an element type that "
             "is not one of the 22, a media file of no known kind) come back byte-equal, records/ included.")
    add("pass-OW-9-roundtrip.owworld", build_zip(base(extra=[(".atlas/charts.json", jbytes({"charts": ["c1"]}))])),
        test="OW-9", role="roundtrip", roundtrip=True, writer="refuse", covers=["OW-7", "OW-9"],
        rule="A private copy (a tool's .atlas/ carried): not a portable .owworld (OW-7), so a writer making one "
             "never emits it; a reader that rewrites it passes .atlas/charts.json and records/ through byte-equal "
             "(OW-9).")

    # -- OW-10: the api block (ruled: a reader strips it and never refuses the file for it) -------------------------
    linked = dict(WORLD, api={"world_id": WORLD_ID, "api_key": "ow_k_secret"})
    add("pass-OW-10-api.owworld", world_with(linked), test="OW-10", writer="refuse", strips="api",
        rule="world.json carries an api block with a key: a reader strips it, never returns it, and reads the "
             "world; a writer never emits it.")

    # -- OW-11: world.json otherwise unchanged (writer) --------------------------------------------------------------
    dropped = {k: v for k, v in WORLD.items() if k not in ("source", "exported_as")}
    add("fail-OW-11-provenance-dropped.owworld", world_with(dropped), test="OW-11", role="writer", writer="refuse",
        rule="Writer: world.json lost source and exported_as (section 4.1: a copy drops nothing but api).")
    add("fail-OW-11-key-added.owworld", world_with(dict(WORLD, snapshot_at="2026-10-21T00:00:00Z")), test="OW-11",
        role="writer", writer="refuse",
        rule="Writer: world.json gained snapshot_at, which the source lacked (a portable copy invents nothing).")

    # -- OW-12: one writer, one input, identical bytes (writer: the shape) -------------------------------------------
    add("fail-OW-12-stamps.owworld", build_zip(base(stamp=dos_stamp(2026, 10, 21, 12, 0, 0))), test="OW-12",
        role="writer", writer="refuse", rule="Writer: entries stamped with a clock (2026-10-21 12:00), not 1980-01-01.")
    add("fail-OW-12-unsorted.owworld", build_zip(sorted(base(), key=utf8_key, reverse=True), sort=False),
        test="OW-12", role="writer", writer="refuse",
        rule="Writer: entries in reverse order; a writer sorts them.")

    # -- OW-13: the order is defined in bytes -----------------------------------------------------------------------
    astral = base(extra=[("media/\uff21.png", PNG), ("media/\U0001F600.png", PNG)])
    add("pass-OW-13-astral.owworld", build_zip(astral), test="OW-13", role="writer",
        rule="Writer: sorted by the UTF-8 bytes of the name: media/\uff21.png (U+FF21) before media/\U0001F600.png "
             "(U+1F600).")
    add("fail-OW-13-utf16-order.owworld",
        build_zip(sorted(astral, key=lambda e: e.name.decode("utf-8").encode("utf-16-be")), sort=False),
        test="OW-13", role="writer", writer="refuse",
        rule="Writer: sorted by UTF-16 code units (C# ordinal, JS <), which puts U+1F600 before U+FF21.")

    # -- OW-14: a reader holds a budget ------------------------------------------------------------------------------
    matches = 9_363_640  # 1 + 258 * matches = 2,415,819,121 bytes, about 2.25 GiB
    bomb_size = 1 + 258 * matches
    bomb = Entry(TOP + "media/zeros.bin", b"", method=8, payload=deflate_zero_bomb(matches),
                 crc=crc_of_zeros(bomb_size), size=bomb_size)
    add("fail-OW-14-declared.owworld", build_zip(base() + [bomb]), test="OW-14", reader="refuse", reason="too_big",
        budget="floor",
        rule="An entry that truly inflates to 2.25 GiB of zeros (sizes honest, about 2.3 MB on disk): past the "
             "2 GiB floor, so a reader holding the floor's budget refuses it from its declared size, before "
             "inflating.")
    lie_body = element(9, "Liar", description="x" * 4000)
    add("fail-OW-14-lying.owworld",
        build_zip(base(extra=[Entry(TOP + "elements/character/liar--0000ab09.json", lie_body,
                                    declared_size=64)])),
        test="OW-14", reader="refuse", reason="too_big",
        rule="An element declares 64 bytes and inflates to %d (its CRC is the true one): a size that lies is "
             "refused when it is inflated." % len(lie_body))
    add("fail-OW-14-stored-lying.owworld",
        build_zip(base() + [Entry(TOP + "media/liar.png", PNG, method=0, declared_size=64)]),
        test="OW-14", reader="refuse", reason="too_big",
        rule="A stored entry declares 64 bytes and holds %d (Kael, h58 #9829): the same lie as a deflated one, the "
             "same cause." % len(PNG))
    add("fail-OW-14-stored-short.owworld",
        build_zip(base() + [Entry(TOP + "media/short.png", PNG, method=0, declared_size=len(PNG) + 64)]),
        test="OW-14", reader="refuse", reason="not_openable",
        rule="A stored entry declares %d bytes and holds %d: fewer than it declares is a broken entry, not_openable "
             "(only more is too_big; Skeld h58 #9944)." % (len(PNG) + 64, len(PNG)))
    crc_body = element(0xc1, "Crc")
    add("fail-OW-14-crc.owworld",
        build_zip(base() + [Entry(TOP + "elements/character/crc--0000abc1.json", crc_body,
                                          crc=zlib.crc32(crc_body) ^ 1)]),
        test="OW-14", reader="refuse", reason="not_openable",
        rule="An element whose bytes fail the CRC its headers declare (one bit off; Skeld h58 #9903, spec 4.7's size "
             "bullet): refused, never read as written.")

    # -- OW-15: the floor (ruled: 500,000 entries and 2 GiB, so zip64 on read) --------------------------------------
    add("pass-OW-15-zip64.owworld", build_zip(base(), zip64_end=True), test="OW-15",
        should="A writer SHOULD write a classic zip under 65,535 entries: this structure on ten files is one every "
               "reader reads, not one a writer makes.",
        rule="The good world with a zip64 end of central directory (record and locator, the classic record's "
             "counts 0xFFFF): the structure a world past 65,535 entries needs, read on ten files.")

    # -- OW-16: entry names are plain relative paths (ruled strict, TypeScript's rule) -------------------------------
    cora = element(4, "Cora")
    for slug, name in [
        ("dotdot", "../x.json"),
        ("climb-inside", "abbey/../x.json"),
        ("absolute", "/etc/x.json"),
        ("drive", "C:/x.json"),
        ("unc", "\\\\server\\x.json"),
    ]:
        add("fail-OW-16-%s.owworld" % slug, build_zip(base() + [Entry(name, cora)]), test="OW-16",
            reader="refuse", reason="unsafe_path", rule="The entry %s climbs out or is absolute: refused." % name)
    for slug, name in [
        ("backslash", "abbey\\elements\\character\\cora--0000ab04.json"),
        ("double-slash", "abbey//elements/character/cora--0000ab04.json"),
        ("dot-segment", "abbey/./elements/character/cora--0000ab04.json"),
        ("dotdot-inside", "abbey/elements/../elements/character/cora--0000ab04.json"),
    ]:
        add("fail-OW-16-%s.owworld" % slug, build_zip(base() + [Entry(name, cora)]), test="OW-16",
            reader="refuse", reason="unsafe_path",
            rule="The entry %s is not a plain relative path: refused, whatever it would resolve to." % name)

    # -- OW-17: no two entries share a name --------------------------------------------------------------------------
    add("fail-OW-17-duplicate.owworld",
        build_zip(base() + [Entry(TOP + "elements/character/ana--0000ab01.json", element(1, "Ana the Second"))]),
        test="OW-17", reader="refuse", reason="duplicate",
        rule="abbey/elements/character/ana--0000ab01.json twice, different bodies: refused.")
    add("fail-OW-17-duplicate-outside.owworld",
        build_zip(base() + [Entry("README.txt", b"one\n"), Entry("README.txt", b"two\n")]), test="OW-17",
        reader="refuse", reason="duplicate",
        rule="README.txt twice beside the world: a duplicate anywhere in the archive is refused.")

    # -- OW-18: no two names collide after NFC and case folding -----------------------------------------------------
    add("fail-OW-18-case.owworld",
        build_zip(base(extra=[("elements/character/Cora.json", cora),
                              ("elements/character/cora.json", element(5, "cora"))])),
        test="OW-18", reader="refuse", reason="collision",
        rule="Cora.json and cora.json: one file on Windows and macOS, refused.")
    add("fail-OW-18-nfc-nfd.owworld",
        build_zip(base(extra=[("media/caf\u00e9.png", PNG), ("media/cafe\u0301.png", PNG)])), test="OW-18",
        reader="refuse", reason="collision",
        rule="media/caf\u00e9.png in NFC (U+00E9) and NFD (e + U+0301), both flagged UTF-8: one name, refused.")
    add("fail-OW-18-folder-case.owworld", build_zip(base(extra=[("Elements/character/cora--0000ab04.json", cora)])),
        test="OW-18", reader="refuse", reason="collision",
        rule="abbey/Elements/ beside abbey/elements/: one folder on a case-insensitive disk, refused.")
    add("fail-OW-18-nfc-then-fold.owworld",
        build_zip(base(extra=[("media/Café.png", PNG), ("media/café.png", PNG)])), test="OW-18",
        reader="refuse", reason="collision",
        rule="media/Café.png (NFD, capital C) and media/café.png (NFC): neither NFC alone nor case "
             "folding alone joins them; NFC then folding does. Refused.")
    add("fail-OW-18-final-sigma.owworld",
        build_zip(base(extra=[("media/σ.png", PNG), ("media/ς.png", PNG)])), test="OW-18",
        reader="refuse", reason="collision",
        rule="media/σ.png (U+03C3) and media/ς.png (U+03C2, final sigma): simple case folding maps "
             "U+03C2 to U+03C3 (lowercasing does not); one name, refused.")
    add("fail-OW-18-st-ligature.owworld",
        build_zip(base(extra=[("media/ﬅ.png", PNG), ("media/ﬆ.png", PNG)])), test="OW-18",
        reader="refuse", reason="collision",
        rule="media/ﬅ.png (U+FB05, long s t) and media/ﬆ.png (U+FB06, s t): NFC keeps them apart; the S row "
             "of CaseFolding.txt 15.1.0 maps U+FB05 to U+FB06, the pair a runtime's lowercase misses (Kael, h58 "
             "#9829). One name, refused.")
    add("fail-OW-18-iota-oxia.owworld",
        build_zip(base(extra=[("media/ΐ.png", PNG), ("media/ΐ.png", PNG)])), test="OW-18",
        reader="refuse", reason="collision",
        rule="media/ΐ.png (U+1FD3) and media/ΐ.png (U+0390): NFC already makes them one (U+1FD3 is a canonical "
             "singleton), before the S row that says the same; one name, refused.")
    add("pass-OW-18-sharp-s.owworld",
        build_zip(base(extra=[("media/straße.png", PNG), ("media/strasse.png", PNG)])), test="OW-18",
        rule="media/straße.png and media/strasse.png: simple case folding leaves U+00DF alone (full folding "
             "makes it 'ss'); two names, accepted.")
    # The NFC pairs (OW Council #656, Skeld h58 #11887): one per step of NFC a reader without one, or with a wrong one,
    # gets wrong. NFC here is Unicode 15.1.0's, built from UnicodeData-15.1.0.txt and CompositionExclusions-15.1.0.txt
    # (run_py.py's `nfc`, proven on NormalizationTest-15.1.0.txt); each pair's two names are spelled in escapes.
    add("fail-OW-18-nfc-singleton.owworld",
        build_zip(base(extra=[("media/豈.png", PNG), ("media/豈.png", PNG)])), test="OW-18",
        reader="refuse", reason="collision",
        rule="media/豈.png (U+F900, a CJK compatibility ideograph) and media/豈.png (U+8C48): U+F900's "
             "decomposition is the one code point U+8C48 (a singleton), and no case folding applies, so only NFC "
             "joins them. One name, refused.")
    add("fail-OW-18-nfc-singleton-angstrom.owworld",
        build_zip(base(extra=[("media/Å.png", PNG), ("media/Å.png", PNG)])), test="OW-18",
        reader="refuse", reason="collision",
        rule="media/Å.png (U+212B ANGSTROM SIGN) and media/Å.png (A + U+030A): NFC takes U+212B to U+00C5 "
             "(a singleton, never recomposed) and composes A + U+030A to U+00C5. Against U+00C5 itself the pair "
             "needs no NFC (CaseFolding's C rows take U+212B and U+00C5 both to U+00E5), so the other side is the "
             "decomposed one: folding alone leaves a + U+030A. One name, refused.")
    add("fail-OW-18-nfc-exclusion.owworld",
        build_zip(base(extra=[("media/क़.png", PNG), ("media/क़.png", PNG)])), test="OW-18",
        reader="refuse", reason="collision",
        rule="media/क़.png (U+0958 DEVANAGARI LETTER QA) and media/क़.png (U+0915 U+093C): U+0958 "
             "decomposes to U+0915 U+093C and is a composition exclusion, so NFC of both is U+0915 U+093C, never "
             "U+0958. One name, refused. (A reader that wrongly recomposes U+0958 joins them too: no case folding "
             "applies to an excluded character, so no pair of names can show that fault; NormalizationTest does.)")
    add("fail-OW-18-nfc-reorder.owworld",
        build_zip(base(extra=[("media/lệ.png", PNG), ("media/lệ.png", PNG)])),
        test="OW-18", reader="refuse", reason="collision",
        rule="media/lệ.png and media/lệ.png (e + dot below U+0323, class 220, and circumflex "
             "U+0302, class 230, in either order): canonical ordering puts U+0323 first, and both compose to U+1EC7. "
             "A reader that composes without ordering gets U+1EC7 and U+00EA U+0323, two names. One name, refused.")
    add("pass-OW-18-nfc-same-class.owworld",
        build_zip(base(extra=[("media/lá̀.png", PNG), ("media/là́.png", PNG)])),
        test="OW-18",
        rule="media/lá̀.png and media/là́.png (acute U+0301 and grave U+0300, both class "
             "230, in either order): marks of one class keep their order, so NFC gives U+00E1 U+0300 and U+00E0 "
             "U+0301. A reader that sorts marks by code point, or unstably, joins them. Two names, accepted.")
    add("fail-OW-18-nfc-hangul.owworld",
        build_zip(base(extra=[("media/한.png", PNG), ("media/한.png", PNG)])), test="OW-18",
        reader="refuse", reason="collision",
        rule="media/한.png (U+D55C, the syllable han) and media/한.png (its jamo U+1112 "
             "U+1161 U+11AB): Hangul composes by arithmetic (L+V, then LV+T), not by UnicodeData's field 5, which "
             "lists no syllable. One name, refused.")
    add("fail-OW-18-nfc-non-starter.owworld",
        build_zip(base(extra=[("media/ΐ.png", PNG), ("media/ΐ.png", PNG)])),
        test="OW-18", reader="refuse", reason="collision",
        rule="media/ΐ.png (iota + U+0344, a mark whose decomposition U+0308 U+0301 starts with a "
             "non-starter: excluded from composition) and media/ΐ.png: NFC decomposes U+0344 and "
             "composes both to U+0390. One name, refused.")
    add("pass-OW-18-nfc-compat.owworld",
        build_zip(base(extra=[("media/ﬁ.png", PNG), ("media/fi.png", PNG)])), test="OW-18",
        rule="media/ﬁ.png (U+FB01, the fi ligature) and media/fi.png: U+FB01's mapping is <compat>, so NFC "
             "keeps it (NFKC would not), and CaseFolding has only an F row for it (simple folding keeps it; a "
             "runtime's full casefold would not). Two names, accepted.")

    # -- OW-19: no path is both a file and a folder ------------------------------------------------------------------
    add("fail-OW-19-file-and-folder.owworld", build_zip(base(extra=[("media", b"not a folder\n")])), test="OW-19",
        reader="refuse", reason="unsafe_path",
        rule="abbey/media is a file and abbey/media/a.png sits under it: refused.")

    # -- OW-20: no links or special entries --------------------------------------------------------------------------
    add("fail-OW-20-symlink.owworld",
        build_zip(base() + [Entry(TOP + "media/link.png", b"../../etc/passwd", system=3, mode=0o120777)]),
        test="OW-20", reader="refuse", reason="link",
        rule="An entry whose Unix mode is a symlink (0o120777), target ../../etc/passwd: refused.")
    add("pass-OW-20-modes.owworld",
        build_zip(base(system=3, mode=0o100644) + [Entry(TOP + "media/", b"", system=3, mode=0o040755)]),
        test="OW-20", rule="Regular files (0o100644, Unix-made) and a directory entry (0o040755): accepted.")

    # -- OW-21: stored or deflate only, nothing encrypted -----------------------------------------------------------
    for slug, kw, what in [
        ("lzma", {"method": 14}, "LZMA (method 14)"),
        ("deflate64", {"method": 9}, "deflate64 (method 9; its data stored blocks, valid deflate64)"),
        ("zipcrypto", {"method": 0, "encrypt": True}, "ZipCrypto (general-purpose bit 0; password 'owworld')"),
    ]:
        add("fail-OW-21-%s.owworld" % slug,
            build_zip(base() + [Entry(TOP + "elements/character/cora--0000ab04.json", cora, **kw)]), test="OW-21",
            reader="refuse", reason="method",
            rule="An element entry in %s: only stored and deflate, never encrypted; refused, not skipped." % what)
    add("fail-OW-21-spanned.owworld", build_zip(base(), disk=1), test="OW-21", reader="refuse",
        reason="not_openable",
        rule="The good world's bytes, its end record saying this is disk 1 of a spanned set whose directory starts "
             "on disk 0: nothing spanned, refused.")

    # -- OW-22: names that land safely on any disk -------------------------------------------------------------------
    for slug, rel, what in [
        ("con", "elements/character/CON.json", "a Windows reserved name (CON)"),
        ("nul-ext", "media/nul.txt", "a Windows reserved name with an extension (nul.txt)"),
        ("lpt1", "media/lpt1.png", "a numbered Windows reserved name (lpt1.png)"),
        ("trailing-dot", "media/a.png.", "a trailing dot"),
        ("trailing-space", "media/b.png ", "a trailing space"),
        ("reserved-char", "media/a?.png", "a reserved character (?)"),
        ("control-char", "media/a\x01.png", "a control character (U+0001)"),
    ]:
        data = cora if rel.endswith(".json") else PNG
        add("fail-OW-22-%s.owworld" % slug, build_zip(base(extra=[(rel, data)])), test="OW-22", reader="refuse",
            reason="name", rule="The entry %s has %s: refused." % (ascii(TOP + rel), what))
    add("fail-OW-22-no-utf8-flag.owworld",
        build_zip(base() + [Entry(TOP + "media/caf\u00e9.png", PNG, utf8_flag=False)]), test="OW-22",
        reader="refuse", reason="name",
        rule="A non-ASCII name (UTF-8 bytes) without the UTF-8 flag (bit 11): its decoding is a guess, refused.")
    add("fail-OW-22-bad-utf8.owworld",
        build_zip(base() + [Entry((TOP + "media/caf").encode("utf-8") + b"\xe9.png", PNG, utf8_flag=True)]),
        test="OW-22", reader="refuse", reason="name",
        rule="A name with the UTF-8 flag whose bytes are not UTF-8 (a Latin-1 e acute, 0xE9; Kael, h58 #9829): its "
             "spelling is a guess, refused.")
    add("pass-OW-22-con-prefix.owworld",
        build_zip(base(extra=[("elements/character/con--0000e1.json", element(0xe1, "Con"))])), test="OW-22",
        rule="con--0000e1.json: its base name is con--0000e1, not a reserved name; accepted.")

    return F


FLOOR_ENTRIES = 500_000  # spec 4.7 (OW-15): the floor every reader accepts
FLOOR_BYTES = 2 << 30    # 2 GiB

NOT_GENERATED = [
    {"file": "fail-OW-14-count.owworld", "test": "OW-14", "status": "not_generated", "role": "reader",
     "reader": "refuse", "writer": "refuse", "reason": "too_many", "budget": "floor",
     "rule": "One entry past the floor (500,001 files), read with the floor's budget: refused.",
     "why": "500,001 entries (zip64) come to about 112 MB. Made on demand by `generate.py --large DIR`, never part "
            "of the set."},
    {"file": "pass-OW-15-floor.owworld", "test": "OW-15", "status": "not_generated", "role": "reader",
     "reader": "accept", "writer": "accept",
     "rule": "A world of exactly 500,000 entries (zip64), the floor: every reader accepts it.",
     "why": "About 112 MB. Made on demand by `generate.py --large DIR`. pass-OW-15-zip64 carries the zip64 "
            "structure in the set."},
    {"file": "pass-OW-15-floor-bytes.owworld", "test": "OW-15", "status": "not_generated", "role": "reader",
     "reader": "accept", "writer": "accept",
     "rule": "A world whose files inflate to just under 2 GiB in all (one entry of zeros, sizes honest): every "
             "reader accepts it.",
     "why": "About 2 MB on disk, but reading it inflates 2 GiB: never run by default. Made on demand by "
            "`generate.py --large DIR`."},
]

# Spec 4.7 (line 229): the TypeScript reader's six (world-file.ts, as that reader names them) plus six.
READER_REASONS = ["unsafe_path", "too_big", "too_many", "not_a_world", "more_than_one", "not_openable",
                  "duplicate", "collision", "link", "method", "name", "marker"]


def verdicts_doc(entries):
    src = base_files()
    return {
        "set": "owworld-conformance",
        "generated_by": "generate.py",
        "spec": "folder format spec section 4.7, the archive (drafted 2026-10-22 02:24, OW Council #522), on 0.3.12; "
                "tests OW-1..OW-22 (Armature/Notes/2026-10-21-owworld-as-tests.md)",
        "notes": [
            "reader: what a reader does with the file (accept, or refuse with `reason`). Every reader runner checks "
            "this field.",
            "writer: whether the file is one a conforming writer may emit as a portable .owworld, checked against "
            "`source` (every source file present byte-exact) and the writer's MUST rules (only the folder's parts, "
            "a marker only in its shape, no api, 1980 stamps, UTF-8 byte order, methods 0 and 8). A SHOULD never "
            "makes it refuse; `should` names one a fixture breaks. Only a reference checker checks it; the role "
            "says which side the test is about.",
            "role: reader | writer | roundtrip. A writer fixture is still opened by every reader: its `reader` "
            "verdict says so.",
            "strips: a key a reader removes from world.json and never returns (OW-10: `api`), the file still read.",
            "open: what section 4.7 still leaves open on this fixture (the question, with the spec's line); the "
            "verdict follows `lean` and moves when the spec says otherwise. Every other verdict is the spec's.",
            "reason: one of `reasons` (section 4.7: the TypeScript reader's six plus duplicate, collision, link, "
            "method, name, marker). A reader that refuses for another cause fails the case.",
            "budget: reader verdicts hold for a reader whose budget is the floor (`floor`: 500,000 entries, 2 GiB). "
            "A reader whose budget is larger reads the fixtures marked `budget: floor` with the floor's budget; one "
            "whose budget is smaller fails the floor cases (pass-OW-15-floor, pass-OW-15-floor-bytes).",
            "source: a fixture's writer verdict is checked against `source` unless it names one of `sources` (the "
            "private case's world, OW-8). A source's `private` lists producers marked private in its RECORDS.json "
            "(section 4.5 rule 11): each one's directory is present whole and byte-exact, or absent whole; the "
            "manifest itself travels byte-exact either way.",
            "side: on the private case, which side of the export the file is: `default` (private records left out) "
            "or `asked` (the caller asked for them). Both are files a conforming writer emits; which one depends on "
            "the call, not the bytes.",
        ],
        "reasons": READER_REASONS,
        "floor": {"entries": FLOOR_ENTRIES, "bytes": FLOOR_BYTES},
        "marker": MIMETYPE.decode("ascii"),
        "source": {"world_id": WORLD_ID, "top": TOP.rstrip("/"),
                   "files": {rel: hashlib.sha256(data).hexdigest() for rel, data in sorted(src.items())}},
        "sources": {"private": {"world_id": WORLD_ID, "top": TOP.rstrip("/"), "private": [PRIVATE_PRODUCER],
                                "files": {rel: hashlib.sha256(data).hexdigest()
                                          for rel, data in sorted(private_files().items())}}},
        "fixtures": entries,
    }


def write_set(out):
    os.makedirs(out, exist_ok=True)
    entries = []
    for file, content, v in fixtures():
        with open(os.path.join(out, file), "wb") as fh:
            fh.write(content)
        v["sha256"] = hashlib.sha256(content).hexdigest()
        v["bytes"] = len(content)
        entries.append(v)
    entries.extend(NOT_GENERATED)
    with open(os.path.join(out, "verdicts.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(verdicts_doc(entries), indent=2, ensure_ascii=False) + "\n")
    return entries


def write_large(out):
    """The big cases, written on demand only: the floor's count and one past it (element files enough for 500,000
    and 500,001 entries), and the floor's bytes (one entry of zeros, the world just under 2 GiB inflated)."""
    os.makedirs(out, exist_ok=True)
    for file, total in (("fail-OW-14-count.owworld", FLOOR_ENTRIES + 1), ("pass-OW-15-floor.owworld", FLOOR_ENTRIES)):
        entries = base()
        for i in range(total - len(entries)):
            entries.append(Entry(TOP + "elements/character/c-%06d.json" % i,
                                 jbytes({"id": "0695db83-0000-7000-8001-%012x" % i, "name": "C%d" % i}),
                                 method=0))
        with open(os.path.join(out, file), "wb") as fh:
            fh.write(build_zip(entries))
        print("wrote", os.path.join(out, file), len(entries), "entries")
    room = FLOOR_BYTES - sum(len(d) for d in base_files().values())
    matches = (room - 1) // 258
    size = 1 + 258 * matches
    zeros = Entry(TOP + "media/zeros.bin", b"", method=8, payload=deflate_zero_bomb(matches),
                  crc=crc_of_zeros(size), size=size)
    file = "pass-OW-15-floor-bytes.owworld"
    with open(os.path.join(out, file), "wb") as fh:
        fh.write(build_zip(base() + [zeros]))
    print("wrote", os.path.join(out, file), "inflating to", size + FLOOR_BYTES - room, "bytes")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default=os.path.join(HERE, "fixtures"))
    ap.add_argument("--large", metavar="DIR",
                    help="also write the big cases (500,001 and 500,000 entries; 2 GiB inflated) to DIR")
    ap.add_argument("--without", metavar="REL", action="append", default=[],
                    help="DIAGNOSTIC ONLY, with --out elsewhere: leave this base file out of every fixture, to see a "
                         "reader's other verdicts past one gap (e.g. records/lab/world.json for OW-5)")
    a = ap.parse_args()
    if a.without and os.path.abspath(a.out) == os.path.join(HERE, "fixtures"):
        ap.error("--without writes a diagnostic copy; give it an --out outside the set")
    DIAGNOSTIC_DROP.update(a.without)
    entries = write_set(a.out)
    made = [e for e in entries if e.get("status") != "not_generated"]
    print("%d fixtures written to %s (%d not generated), verdicts.json beside them"
          % (len(made), a.out, len(entries) - len(made)))
    if a.large:
        write_large(a.large)


if __name__ == "__main__":
    sys.exit(main())

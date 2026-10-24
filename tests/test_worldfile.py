"""The world file, ``.owworld`` (folder format spec §4.7): the fixture set, the fold, the writer.

The fixture set is the schema distribution's (``codegen/schema-dist/fixtures/owworld/``,
vendored; ``OW_OWWORLD_FIXTURES`` points at another copy): every zip on disk has a verdict,
every verdict's zip is on disk, and the package's reader gives each one its verdict and cause.
"""

from __future__ import annotations

import hashlib
import importlib
import io
import json
import os
import re
import shutil
import sys
import unicodedata
import zipfile
from pathlib import Path
from typing import Any

import pytest

from onlyworlds import (
    WORLD_FILE_MEDIA_TYPE,
    WorldFile,
    WorldFileError,
    read_folder,
    read_world_file,
    world_file_bytes,
    write_world_file,
)
from onlyworlds._jsonfmt import encode
from onlyworlds.folder import slugify
from onlyworlds.worldfile import REASONS, WORLD_FILE_MAX_BYTES, WORLD_FILE_MAX_ENTRIES, nfc, simple_case_fold

REPO = Path(__file__).resolve().parent.parent
SET_ROOT = Path(os.environ.get("OW_OWWORLD_FIXTURES") or REPO / "codegen" / "schema-dist" / "fixtures" / "owworld")
FIXTURES = SET_ROOT if (SET_ROOT / "verdicts.json").is_file() else SET_ROOT / "fixtures"
CASE_FOLDING = REPO / "codegen" / "schema-dist" / "fixtures" / "owworld" / "CaseFolding-15.1.0.txt"
# Unicode's conformance file as published (unicode.org/Public/15.1.0/ucd/NormalizationTest.txt), byte for byte.
NORMALIZATION_TEST = REPO / "tests" / "fixtures" / "NormalizationTest-15.1.0.txt"
HYPERION = REPO / "codegen" / "schema-dist" / "example" / "hyperion"
WID = "0192a000-aaaa-7bbb-8ccc-000000000001"


def refuses(reason: str, source: Any, **kw: Any) -> WorldFileError:
    with pytest.raises(WorldFileError) as info:
        read_world_file(source, **kw)
    assert info.value.reason == reason, f"expected {reason}, got {info.value.reason}: {info.value}"
    return info.value


def zip_of(entries: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return buf.getvalue()


def world_json(**extra: Any) -> bytes:
    return encode({"id": WID, "name": "W", **extra})


def make_folder(root: Path, files: dict[str, bytes]) -> Path:
    for rel, data in files.items():
        target = root.joinpath(*rel.split("/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return root


def tree(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


# --- the fixture set -----------------------------------------------------------------------


def test_the_owworld_fixture_set_every_verdict_and_every_cause(tmp_path: Path) -> None:
    assert (FIXTURES / "verdicts.json").is_file(), f"no verdicts.json at {SET_ROOT} or under its fixtures/"
    doc = json.loads((FIXTURES / "verdicts.json").read_text(encoding="utf-8"))
    assert tuple(doc["reasons"]) == REASONS, "the set's causes are the package's, in the spec's order"
    assert doc["floor"] == {"entries": WORLD_FILE_MAX_ENTRIES, "bytes": WORLD_FILE_MAX_BYTES}
    assert doc["marker"] == WORLD_FILE_MEDIA_TYPE
    on_disk = sorted(p.name for p in FIXTURES.iterdir() if p.suffix in (".owworld", ".zip"))
    listed = sorted(v["file"] for v in doc["fixtures"] if v.get("status") != "not_generated")
    assert on_disk == listed, "the zips on disk and the verdicts listed"
    diffs: list[str] = []
    run = 0
    for v in doc["fixtures"]:
        if v.get("status") == "not_generated":
            continue
        run += 1
        got, reason = "accept", ""
        try:
            r = read_world_file(FIXTURES / v["file"])
            if v.get("strips"):
                key = v["strips"]
                if key in r.world or key in json.loads(r.entries["world.json"]):
                    got = "refuse"
            if v.get("roundtrip"):
                folder = r.to_folder(tmp_path / v["file"])
                # A private copy's dot-folder travels only when handed in (OW-7): hand in the one it has.
                dots = sorted({p.split("/")[0] for p in r.entries if p.startswith(".")})
                assert len(dots) <= 1, dots
                again = read_world_file(
                    world_file_bytes(folder, top_dir="abbey", private_dir=dots[0] if dots else None)
                )
                if again.entries != r.entries or list(again.entries) != list(r.entries):
                    got = "refuse"
        except WorldFileError as exc:
            got, reason = "refuse", exc.reason
        if got != v["reader"]:
            diffs.append(f"{v['file']}: expected {v['reader']}, got {got} {reason}")
        elif got == "refuse" and reason != v["reason"]:
            diffs.append(f"{v['file']}: {v['reason']} -> {reason}")
    print(f"the .owworld set: {run} fixtures run, {len(diffs)} disagreeing, from {FIXTURES}")
    for d in diffs:
        print(f"  disagrees: {d}")
    assert run == len(on_disk) == 93, f"the set holds {run} fixtures"  # dist.57: eight OW-18 NFC cases
    assert diffs == []


# Three zips the next schema-dist serial brings (Quillon's set, verdicts.json of 2026-10-24; Skeld's ruling h58
# #11968), copied here until it does: when the serial is vendored, delete tests/fixtures/owworld-next/ and this test,
# and the set above carries them.
NEXT = REPO / "tests" / "fixtures" / "owworld-next"
NEXT_CASES = {
    "fail-OW-14-deflate-early-end.owworld": (
        "b176e92b6bfe0c8bcb7fe143adcf2b7e967e2a21d14549b4ac0ffac17afe013c",
        "not_openable",
    ),
    "fail-OW-14-deflate-no-end.owworld": (
        "7dec0fffdc42643b24b527a80b54116f504e4a5933d09c675d3bfd31cbeb5ef4",
        "not_openable",
    ),
    "pass-OW-18-nfc-unassigned.owworld": ("b02a7871c3a9932a0646944c2e76850b3df63dca1fc3881fc89df4ae0b3544d4", None),
}


@pytest.mark.parametrize("file", sorted(NEXT_CASES))
def test_the_next_serials_three_cases_the_deflate_stream_to_its_declared_end_and_the_nfc_pair(file: str) -> None:
    assert sorted(p.name for p in NEXT.iterdir()) == sorted(NEXT_CASES)
    data = (NEXT / file).read_bytes()
    digest, reason = NEXT_CASES[file]
    assert hashlib.sha256(data).hexdigest() == digest, f"{file} is Quillon's"
    if reason:
        refuses(reason, data)
    else:
        assert read_world_file(data).entries


def test_the_private_case_both_sides_of_the_writer(tmp_path: Path) -> None:
    """OW-8's private clause (§4.5 rule 11), the set's two-sided case: the source world rebuilt from
    the asked side (it carries every source file, each checked against ``sources.private``), written
    with the default and when asked, each equal entry for entry to its side's fixture and to neither
    of the two a conforming writer never emits. Entries, not zip bytes (one zlib build's)."""
    doc = json.loads((FIXTURES / "verdicts.json").read_text(encoding="utf-8"))
    source = doc["sources"]["private"]
    cases = {v["file"]: v for v in doc["fixtures"] if v.get("source") == "private"}
    assert sorted(cases) == [
        "fail-OW-8-private-manifest-rewritten.owworld",
        "fail-OW-8-private-partial.owworld",
        "pass-OW-8-private-asked.owworld",
        "pass-OW-8-private-left-out.owworld",
    ]
    assert all(v["role"] == "writer" for v in cases.values())
    side = {v.get("side"): read_world_file(FIXTURES / f).entries for f, v in cases.items() if v["writer"] == "accept"}
    never = [read_world_file(FIXTURES / f).entries for f, v in cases.items() if v["writer"] == "refuse"]
    assert set(side) == {"default", "asked"} and len(never) == 2

    asked = read_world_file(FIXTURES / "pass-OW-8-private-asked.owworld")
    assert {p: hashlib.sha256(b).hexdigest() for p, b in asked.entries.items()} == source["files"]
    src = asked.to_folder(tmp_path / "abbey")
    assert source["private"] == ["fold"] and any(p.startswith("records/fold/") for p in asked.entries)

    default = read_world_file(world_file_bytes(src, top_dir=source["top"])).entries
    carried = read_world_file(write_world_file(src, tmp_path / "a.owworld", include_private_records=True)).entries
    assert default == side["default"] and list(default) == list(side["default"])
    assert carried == side["asked"] and list(carried) == list(side["asked"])
    assert not any(p.startswith("records/fold/") for p in default), "the private directory left out whole"
    assert default["records/RECORDS.json"] == asked.entries["records/RECORDS.json"], "the manifest byte-exact"
    for bad in never:
        assert default != bad and carried != bad


def test_a_records_manifest_the_writer_cannot_read_refuses_unless_asked(tmp_path: Path) -> None:
    base = {"world.json": world_json(), "records/fold/spine.jsonl": b"{}\n", "records/lab/ledger.bin": b"L"}
    for name, manifest in (
        ("object", encode({"producer": "fold", "private": True})),
        ("array-of-strings", encode(["fold"])),
        ("not-json", b"[{"),
        ("nan", b'[{"producer": "fold", "x": NaN}]'),
        ("not-utf8", b'[{"producer": "f\xffold"}]'),
        ("bad-producer", encode([{"producer": "../lab", "private": True}])),
        ("no-producer", encode([{"private": True}])),
    ):
        folder = make_folder(tmp_path / name, {**base, "records/RECORDS.json": manifest})
        with pytest.raises(ValueError) as info:
            world_file_bytes(folder)
        assert not isinstance(info.value, WorldFileError), "a plain ValueError, not a thirteenth reader cause"
        assert "RECORDS.json" in str(info.value) and "include_private_records" in str(info.value), str(info.value)
        with pytest.raises(ValueError):
            write_world_file(folder, tmp_path / f"{name}.owworld")
        assert not (tmp_path / f"{name}.owworld").exists()
        entries = read_world_file(world_file_bytes(folder, include_private_records=True)).entries
        assert entries["records/RECORDS.json"] == manifest
        assert "records/fold/spine.jsonl" in entries and "records/lab/ledger.bin" in entries


def test_only_the_json_boolean_true_marks_records_private(tmp_path: Path) -> None:
    entries: list[dict[str, Any]] = [
        {"producer": "fold", "private": True},
        {"producer": "text", "private": "true"},
        {"producer": "one", "private": 1},
        {"producer": "no", "private": False},
        {"producer": "lab"},
    ]
    files = {f"records/{e['producer']}/a.bin": b"x" for e in entries}
    folder = make_folder(tmp_path / "f", {"world.json": world_json(), "records/RECORDS.json": encode(entries), **files})
    got = read_world_file(world_file_bytes(folder)).entries
    assert sorted(p for p in got if p.startswith("records/")) == [
        "records/RECORDS.json",
        "records/lab/a.bin",
        "records/no/a.bin",
        "records/one/a.bin",
        "records/text/a.bin",
    ]
    assert got["records/RECORDS.json"] == encode(entries)


def test_a_private_producer_matches_its_directory_by_the_fold(tmp_path: Path) -> None:
    # On a disk that ignores case, `Fold` names `fold`: an exact match would let it travel.
    # A decomposed é in the manifest names the composed directory the same way (NFC first).
    decomposed, composed = "cafe" + chr(0x301), "caf" + chr(0xE9)
    entries = [{"producer": "Fold", "private": True}, {"producer": decomposed, "private": True}, {"producer": "lab"}]
    files = {"records/fold/a.bin": b"x", f"records/{composed}/n.txt": b"y", "records/lab/a.bin": b"z"}
    folder = make_folder(tmp_path / "f", {"world.json": world_json(), "records/RECORDS.json": encode(entries), **files})
    got = read_world_file(world_file_bytes(folder)).entries
    assert sorted(p for p in got if p.startswith("records/")) == ["records/RECORDS.json", "records/lab/a.bin"]


# --- the fold (OW-18) ------------------------------------------------------------------------


def test_the_fold_is_casefolding_15_1_c_and_s_rows_for_every_code_point() -> None:
    table: dict[int, int] = {}
    for line in CASE_FOLDING.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^([0-9A-F]+); ([CS]); ([0-9A-F]+);", line)
        if m:
            table[int(m.group(1), 16)] = int(m.group(3), 16)
    assert len(table) == 1457, "the C and S rows of 15.1"
    wrong = []
    for c in range(0x110000):
        if 0xD800 <= c <= 0xDFFF:
            continue
        got = ord(simple_case_fold(chr(c)))
        if got != table.get(c, c):
            wrong.append(f"U+{c:04X} -> U+{got:04X}")
    assert wrong[:20] == [], f"{len(wrong)} code points fold otherwise than the table says"
    # Simple, not full: sharp s stays apart from ss (str.casefold would join them), dotless i from i.
    assert simple_case_fold(chr(0xDF)) == chr(0xDF)
    assert simple_case_fold(chr(0x131)) == chr(0x131)
    assert simple_case_fold("Map" + chr(0x3A3)) == "map" + chr(0x3C3)


def test_the_generated_fold_table_is_current() -> None:
    sys.path.insert(0, str(REPO / "codegen"))
    try:
        generate_casefold = importlib.import_module("generate_casefold")  # codegen/ is no package: found by path
    finally:
        sys.path.pop(0)
    expected = generate_casefold.render(generate_casefold.rows(CASE_FOLDING.read_text(encoding="utf-8")))
    assert (REPO / "src" / "onlyworlds" / "_casefold.py").read_text(encoding="utf-8") == expected


# --- the NFC before the fold (OW-18, serial 57) ------------------------------------------------


def test_the_nfc_is_unicode_15_1_on_every_line_of_normalization_test() -> None:
    data = NORMALIZATION_TEST.read_bytes()
    assert hashlib.sha256(data).hexdigest() == "871238e37e3be0696ec2bd0891119a041b052da1a84485eda05a5438724b223e"
    part, lines, wrong = "", 0, []
    listed: set[int] = set()
    for line in data.decode("utf-8").splitlines():
        if line.startswith("@Part"):
            part = line.split()[0]
            continue
        if not line or line.startswith("#"):
            continue
        c = ["".join(chr(int(h, 16)) for h in col.split()) for col in line.split(";")[:5]]
        lines += 1
        if part == "@Part1":
            listed.add(ord(c[0]))
        # The file's NFC invariants: c2 == NFC(c1) == NFC(c2) == NFC(c3), c4 == NFC(c4) == NFC(c5).
        for source, want in ((0, 1), (1, 1), (2, 1), (3, 3), (4, 3)):
            got = nfc(c[source])
            if got != c[want]:
                wrong.append(f"line {lines}: NFC(c{source + 1}) is {got.encode('unicode_escape')!r}")
    assert lines == 19074, "the test lines of NormalizationTest 15.1"
    assert wrong[:20] == [], f"{len(wrong)} disagreements with NormalizationTest-15.1.0.txt"
    # And the file's rule for the rest: every code point Part 1 does not list is its own NFC.
    moved = [f"U+{c:04X}" for c in range(0x110000) if c not in listed and nfc(chr(c)) != chr(c)]
    assert moved[:20] == [], f"{len(moved)} code points outside Part 1 change under NFC"


# The 20 code points Unicode 16.0 assigns with a canonical decomposition and 15.1 leaves unassigned
# (Quillon's measurement, Armature/Notes/lane-nfc-data.md): Todhri, Tulu-Tigalari, Gurung Khema, Kirat Rai.
UNASSIGNED_IN_15_1 = {
    0x105C9: (0x105D2, 0x0307),
    0x105E4: (0x105DA, 0x0307),
    0x11383: (0x11382, 0x113C9),
    0x11385: (0x11384, 0x113BB),
    0x1138E: (0x1138B, 0x113C2),
    0x11391: (0x11390, 0x113C9),
    0x113C5: (0x113C2, 0x113C2),
    0x113C7: (0x113C2, 0x113B8),
    0x113C8: (0x113C2, 0x113C9),
    0x16121: (0x1611E, 0x1611E),
    0x16122: (0x1611E, 0x16129),
    0x16123: (0x1611E, 0x1611F),
    0x16124: (0x16129, 0x1611F),
    0x16125: (0x1611E, 0x16120),
    0x16126: (0x16121, 0x1611F),
    0x16127: (0x16122, 0x1611F),
    0x16128: (0x16121, 0x16120),
    0x16D68: (0x16D67, 0x16D67),
    0x16D69: (0x16D63, 0x16D67),
    0x16D6A: (0x16D69, 0x16D67),
}


def test_the_nfc_is_the_pinned_one_not_the_interpreters() -> None:
    # On Unicode 16.0 (Python 3.14) unicodedata joins each pair; at 15.1 they are two names.
    joined_here = int(unicodedata.unidata_version.split(".")[0]) >= 16
    for composite, parts in UNASSIGNED_IN_15_1.items():
        one, two = chr(composite), "".join(map(chr, parts))
        assert nfc(one) == one and nfc(two) == two, f"U+{composite:04X}"
        if joined_here:
            assert unicodedata.normalize("NFC", two) == one, (
                f"U+{composite:04X} under Unicode {unicodedata.unidata_version}"
            )
        read_world_file(zip_of({"w/world.json": world_json(), f"w/media/{one}.png": b"1", f"w/media/{two}.png": b"2"}))
    # What 15.1 assigns still joins, Hangul by arithmetic included.
    for one, two in ((chr(0x1EC7), "ệ"), (chr(0xD55C), "한")):
        refuses("collision", zip_of({"w/world.json": world_json(), f"w/media/{one}": b"1", f"w/media/{two}": b"2"}))


def test_the_generated_nfc_tables_are_current() -> None:
    sys.path.insert(0, str(REPO / "codegen"))
    try:
        generate_nfc = importlib.import_module("generate_nfc")  # codegen/ is no package: found by path
    finally:
        sys.path.pop(0)
    expected, _ = generate_nfc.build()
    assert (REPO / "src" / "onlyworlds" / "_nfc.py").read_text(encoding="utf-8") == expected


# --- the reader --------------------------------------------------------------------------------


def test_reads_a_world_in_one_folder_entries_in_code_point_order() -> None:
    astral, fullwidth = chr(0x1F600), chr(0xFF21)
    zf = zip_of(
        {
            "w/world.json": world_json(),
            f"w/media/{astral}.png": b"A",
            f"w/media/{fullwidth}.png": b"B",
            "w/elements/character/a.json": b"{}",
        }
    )
    r = read_world_file(zf)
    assert (r.world_id, r.name, r.top) == (WID, "W", "w")
    # UTF-16 order would put the astral name first; the spec's order is the code point's (OW-13).
    assert list(r.entries) == [
        "elements/character/a.json",
        f"media/{fullwidth}.png",
        f"media/{astral}.png",
        "world.json",
    ]


def test_a_world_at_the_root_and_a_name_it_does_not_have() -> None:
    r = read_world_file(zip_of({"world.json": encode({"id": WID}), "elements/character/a.json": b"{}"}))
    assert (r.top, r.name) == (None, "")


def test_the_api_block_is_stripped_and_never_returned_otherwise_the_bytes_are_kept() -> None:
    linked = encode({"id": WID, "name": "L", "api": {"world_id": "srv", "api_key": "ow_w_secret"}, "x": 1})
    r = read_world_file(zip_of({"l/world.json": linked}))
    assert r.world == {"id": WID, "name": "L", "x": 1}
    assert b"ow_w_secret" not in r.entries["world.json"]
    assert r.entries["world.json"] == encode({"id": WID, "name": "L", "x": 1})
    odd = ('{"name":"Kept as is","id":"' + WID + '"}').encode()
    assert read_world_file(zip_of({"w/world.json": odd})).entries["world.json"] == odd


def test_the_budget_by_count_and_by_declared_size_and_skip_still_counts() -> None:
    zf = zip_of({"w/world.json": world_json(), "w/.atlas/a": b"1", "w/.atlas/b": b"2"})
    refuses("too_many", zf, max_entries=2, skip=lambda p: p.startswith(".atlas/"))
    refuses("too_big", zf, max_bytes=len(world_json()))
    r = read_world_file(zf, skip=lambda p: p.startswith(".atlas/"))
    assert list(r.entries) == ["world.json"]


def test_not_a_zip_and_a_cut_short_zip() -> None:
    refuses("not_openable", b"just some text")
    refuses("not_openable", b"")
    whole = zip_of({"w/world.json": world_json()})
    refuses("not_openable", whole[:-30])


def test_to_folder_writes_every_entry_byte_for_byte_and_never_over_a_folder(tmp_path: Path) -> None:
    r = read_world_file(zip_of({"w/world.json": world_json(), "w/records/lab/.cursor": b"7", "w/media/a.png": b"P"}))
    out = r.to_folder(tmp_path / "out")
    assert tree(out) == r.entries
    with pytest.raises(FileExistsError):
        r.to_folder(out)
    assert [p.name for p in tmp_path.iterdir()] == ["out"], "no temp directory left behind"
    forged = WorldFile(world_id=WID, name="W", world={}, entries={"../evil.json": b"x", "world.json": b"{}"})
    with pytest.raises(WorldFileError) as info:
        forged.to_folder(tmp_path / "forged")
    assert info.value.reason == "unsafe_path"
    assert not (tmp_path / "evil.json").exists() and not (tmp_path / "forged").exists()


# --- the writer --------------------------------------------------------------------------------


def central(data: bytes) -> list[zipfile.ZipInfo]:
    return zipfile.ZipFile(io.BytesIO(data)).infolist()


def test_marker_first_and_stored_1980_stamps_utf8_byte_order_json_deflated(tmp_path: Path) -> None:
    astral, fullwidth = chr(0x1F600), chr(0xFF21)
    folder = make_folder(
        tmp_path / "anything",
        {
            "world.json": world_json(),
            f"media/{astral}.png": b"A",
            "elements/character/b.json": b"{}",
            f"media/{fullwidth}.png": b"B",
            "elements/character/a.json": b"{}",
        },
    )
    data = world_file_bytes(folder, top_dir="w")
    cd = central(data)
    assert [e.filename for e in cd] == [
        "mimetype",
        "w/elements/character/a.json",
        "w/elements/character/b.json",
        f"w/media/{fullwidth}.png",
        f"w/media/{astral}.png",
        "w/world.json",
    ]
    marker = cd[0]
    assert (marker.header_offset, marker.compress_type, marker.extra) == (0, zipfile.ZIP_STORED, b"")
    assert data[30 : 30 + 8] == b"mimetype"
    assert data[38 : 38 + len(WORLD_FILE_MEDIA_TYPE)] == WORLD_FILE_MEDIA_TYPE.encode()
    assert all(e.date_time == (1980, 1, 1, 0, 0, 0) for e in cd)
    assert [e.compress_type for e in cd] == [0, 8, 8, 0, 0, 8]
    assert all(e.flag_bits & 0x0800 for e in cd if not e.filename.isascii()), "non-ASCII names carry the UTF-8 flag"
    assert all(e.external_attr == 0o100644 << 16 and e.create_system == 3 for e in cd), "a regular file, on any host"


def test_the_same_folder_twice_gives_the_same_bytes_wherever_it_sits(tmp_path: Path) -> None:
    a = shutil.copytree(HYPERION, tmp_path / "a" / "hyperion")
    b = shutil.copytree(HYPERION, tmp_path / "somewhere-else")
    first = world_file_bytes(a)
    assert world_file_bytes(a) == first
    assert world_file_bytes(b) == first, "the top folder comes from world.json, never from the folder's path"
    written = write_world_file(a, tmp_path / "h.owworld")
    assert written.read_bytes() == first
    assert sorted(p.name for p in tmp_path.iterdir()) == ["a", "h.owworld", "somewhere-else"], "no temp file left"


def test_round_trip_folder_to_archive_to_folder_every_file_byte_equal(tmp_path: Path) -> None:
    src = shutil.copytree(HYPERION, tmp_path / "src")
    r = read_world_file(write_world_file(src, tmp_path / "h.owworld"))
    back = r.to_folder(tmp_path / "back")
    assert tree(back) == tree(src)
    a, b = read_folder(src), read_folder(back)
    assert a.world == b.world
    assert {k: v.body for k, v in a.elements.items()} == {k: v.body for k, v in b.elements.items()}
    assert r.top == f"{slugify(r.name) or 'world'}-{r.world_id[:8]}", "Atlas and Lantern's <slug>-<id8>"


def test_only_world_json_and_the_parts_travel_and_a_handed_dot_folder(tmp_path: Path) -> None:
    folder = make_folder(
        tmp_path / "f",
        {
            "world.json": world_json(),
            "elements/character/a.json": b"{}",
            "spatial/map/m.json": b"{}",
            "media/a.png": b"P",
            "records/lab/world.json": encode({"id": "lab"}),
            "records/lab/.hidden": b"kept",
            "records/lab/x.meta": b"kept",
            ".atlas/charts.json": b"[]",
            ".git/HEAD": b"no",
            "README.md": b"# no",
            "notes/todo.txt": b"no",
            "media/.DS_Store": b"no",
            "media/a.png.meta": b"no",
            "elements/.cache/x.json": b"no",
        },
    )
    portable = read_world_file(world_file_bytes(folder))
    assert list(portable.entries) == [
        "elements/character/a.json",
        "media/a.png",
        "records/lab/.hidden",
        "records/lab/world.json",
        "records/lab/x.meta",
        "spatial/map/m.json",
        "world.json",
    ]
    private = read_world_file(world_file_bytes(folder, private_dir=".atlas"))
    assert next(iter(private.entries)) == ".atlas/charts.json"
    assert ".git/HEAD" not in private.entries
    with pytest.raises(ValueError):
        world_file_bytes(folder, private_dir="atlas")


def test_world_json_travels_verbatim_provenance_included_and_api_never(tmp_path: Path) -> None:
    raw = encode(
        {
            "id": WID,
            "name": "W",
            "format_version": "0.3.9",
            "producer": {"tool": "atlas", "version": "1.0.0", "input": "bare"},
            "source": {"server": "https://www.onlyworlds.com", "world": WID, "at": "2026-10-01T00:00:00Z"},
        }
    )
    r = read_world_file(world_file_bytes(make_folder(tmp_path / "v", {"world.json": raw})))
    assert r.entries["world.json"] == raw
    linked = encode({"id": WID, "name": "L", "producer": {"tool": "x"}, "api": {"world_id": WID, "api_key": "k"}})
    data = world_file_bytes(make_folder(tmp_path / "l", {"world.json": linked}))
    assert b'"api_key"' not in zipfile.ZipFile(io.BytesIO(data)).read("l-0192a000/world.json")
    assert read_world_file(data).world == {"id": WID, "name": "L", "producer": {"tool": "x"}}


def test_the_writer_refuses(tmp_path: Path) -> None:
    def wr(folder: Path, reason: str, **kw: Any) -> None:
        with pytest.raises(WorldFileError) as info:
            world_file_bytes(folder, **kw)
        assert info.value.reason == reason, str(info.value)

    ok = make_folder(tmp_path / "ok", {"world.json": world_json()})
    wr(make_folder(tmp_path / "none", {"elements/character/a.json": b"{}"}), "not_a_world")
    wr(make_folder(tmp_path / "broken", {"world.json": b'{ "id": "x", "api": {"api_key": "s"} broken'}), "not_a_world")
    wr(make_folder(tmp_path / "noid", {"world.json": encode({"name": "no id"})}), "not_a_world")
    wr(ok, "unsafe_path", top_dir="../w")
    wr(ok, "unsafe_path", top_dir="a/b")
    wr(ok, "unsafe_path", top_dir="mimetype")  # the marker's name: a file and a folder
    wr(ok, "collision", top_dir="MimeType")
    wr(ok, "name", top_dir="w.")
    wr(ok, "name", top_dir="aux")


@pytest.mark.skipif(sys.platform == "win32", reason="NTFS cannot hold the two names (or the name) to begin with")
def test_the_writer_refuses_what_a_case_sensitive_disk_can_hold(tmp_path: Path) -> None:
    for files, reason in (
        ({"media/A.png": b"1", "media/a.png": b"2"}, "collision"),
        (
            {"media/caf" + unicodedata.normalize("NFD", chr(0xE9)) + ".png": b"1", "media/caf\xe9.png": b"2"},
            "collision",
        ),
        ({"media/aux.png": b"1"}, "name"),
        ({"media/a\\b.png": b"1"}, "unsafe_path"),
    ):
        folder = make_folder(tmp_path / reason / str(len(files)), {"world.json": world_json(), **files})
        with pytest.raises(WorldFileError) as info:
            world_file_bytes(folder)
        assert info.value.reason == reason


@pytest.mark.skipif(not hasattr(os, "symlink") or sys.platform == "win32", reason="symlinks need privileges on Windows")
def test_the_writer_refuses_a_link_where_a_carried_file_would_be(tmp_path: Path) -> None:
    folder = make_folder(tmp_path / "f", {"world.json": world_json()})
    (tmp_path / "secret").write_bytes(b"s")
    (folder / "media").mkdir()
    os.symlink(tmp_path / "secret", folder / "media" / "s.png")
    with pytest.raises(WorldFileError) as info:
        world_file_bytes(folder)
    assert info.value.reason == "link"


# --- hidden elements: kept in a copy, left out of a share (folder format §4.8; Skeld, OW Atlas h20 #11469)


def test_a_hidden_element_travels_byte_for_byte_unless_the_file_is_a_share(tmp_path: Path) -> None:
    secret = b'{\n  "id": "c-2",\n  "name": "Cy",\n  "hidden": true\n}\n'
    files = {
        "world.json": world_json(),
        "elements/character/ann--c-1.json": encode({"id": "c-1", "name": "Ann", "friends": ["c-2"]}),
        "elements/character/cy--c-2.json": secret,
        "elements/character/dee--c-3.json": encode({"id": "c-3", "name": "Dee", "hidden": False}),
        "spatial/pin/p--p-1.json": encode({"id": "p-1", "name": "P", "hidden": True}),
        "elements/character/notes.json": b"[1, 2]",  # not an element object: carried as ever
        "media/hidden.json": encode({"hidden": True}),  # not an element file
    }
    src = make_folder(tmp_path / "w", files)
    kept = read_world_file(world_file_bytes(src)).entries
    assert kept["elements/character/cy--c-2.json"] == secret and len(kept) == len(files)
    left: list[str] = []
    share = world_file_bytes(src, include_hidden=False, hidden_left_out=left)
    assert left == ["elements/character/cy--c-2.json", "spatial/pin/p--p-1.json"]
    entries = read_world_file(share).entries
    assert set(kept) - set(entries) == set(left)
    assert all(entries[p] == kept[p] for p in entries), "nothing else rewritten"
    assert b'"c-2"' in entries["elements/character/ann--c-1.json"]  # the link id dangles, as ruled
    assert world_file_bytes(src, include_hidden=False) == share and world_file_bytes(src) == world_file_bytes(src)
    again: list[str] = []
    written = write_world_file(src, tmp_path / "share.owworld", include_hidden=False, hidden_left_out=again)
    assert written.read_bytes() == share and again == left

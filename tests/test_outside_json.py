"""Text this package did not write (a folder's file, an archive, another tool's export) is parsed through
``_outside_json.loads``: JSON it cannot hold as written (nested past its depth, an integer past Python's
digit limit, a number that is not finite) must come back as a ``ValueError`` a reader catches, never a
traceback and never a value the file does not hold. The world file's writer leaves a file it could not read
as an element out of a share, listed apart from the hidden, and carries it byte for byte in a copy. And every
``json.loads`` in the package is either that one or named here."""

from __future__ import annotations

import ast
import json
import zipfile
from pathlib import Path

import pytest

from onlyworlds import _outside_json, read_folder, write_folder
from onlyworlds.folder import FORMAT_VERSION
from onlyworlds.kanka import import_kanka
from onlyworlds.worldfile import read_world_file, world_file_bytes

SRC = Path(__file__).resolve().parent.parent / "src" / "onlyworlds"
DEEP = "[" * 100_000 + "]" * 100_000
LONG = "7" * 4301


def test_what_json_reads_it_reads_the_same() -> None:
    for text in (
        '{"a": [1, 2.5, -3, 1.7976931348623157e308, "x", null, true]}',
        "12345678901234567890",
        "-" + "7" * 4300,
        "[[[[1]]]]",
    ):
        assert _outside_json.loads(text) == json.loads(text)
    assert _outside_json.loads("1", parse_int=float) == 1.0


@pytest.mark.parametrize(
    ("text", "why"),
    [
        (DEEP, "nested more than 200 deep"),
        ('{"a": ' + DEEP + "}", "nested more than 200 deep"),
        (LONG, "a number of more than 4300 digits"),
        ("-" + LONG, "a number of more than 4300 digits"),
        ('{"a": [' + LONG + "]}", "a number of more than 4300 digits"),
        ("1e400", "a number too large to read"),
        ('{"a": [1, {"b": -1e999}]}', "a number too large to read"),
        ('{"a": NaN}', "NaN is not JSON"),
        ("[Infinity]", "Infinity is not JSON"),
        ("-Infinity", "-Infinity is not JSON"),
    ],
)
def test_too_deep_and_too_long_are_value_errors_in_plain_words(text: str, why: str) -> None:
    with pytest.raises(ValueError, match=why) as err:
        _outside_json.loads(text)
    assert not isinstance(err.value, json.JSONDecodeError)
    assert "set_int_max_str_digits" not in str(err.value)


def test_the_depth_refused_is_one_number_on_every_platform() -> None:
    def nest(depth: int, open_: str, close: str) -> str:
        return open_ * depth + close * depth

    assert _outside_json.MAX_DEPTH == 200
    for open_, close in (("[", "]"), ('{"a": ', "}")):
        inner = "1" if open_ != "[" else ""
        text = open_ * 200 + inner + close * 200
        assert _outside_json.loads(text) == json.loads(text)
        with pytest.raises(ValueError, match="nested more than 200 deep"):
            _outside_json.loads(open_ * 201 + inner + close * 201)
    assert _outside_json.loads('{"a": ' + nest(199, "[", "]") + "}") is not None
    with pytest.raises(ValueError, match="nested more than 200 deep"):
        _outside_json.loads('{"a": ' + nest(200, "[", "]") + "}")


def test_text_that_is_not_json_is_still_a_decode_error() -> None:
    with pytest.raises(json.JSONDecodeError):
        _outside_json.loads('{"id": ')


@pytest.mark.parametrize(
    ("value", "why"),
    [
        (DEEP, "nested more than 200 deep"),
        (LONG, "a number of more than 4300 digits"),
        ("1e400", "a number too large to read"),
    ],
)
def test_the_folder_reader_skips_such_a_file_with_the_reason(tmp_path: Path, value: str, why: str) -> None:
    eid = "l0000000-0000-7000-8000-000000000001"
    world = {"id": "w0000000-0000-7000-8000-000000000000", "name": "W", "format_version": FORMAT_VERSION}
    write_folder(tmp_path / "w", world, {"location": [{"id": eid, "name": "Harbor"}]})
    (path,) = (tmp_path / "w" / "elements").rglob("*.json")
    path.write_text('{"id": "' + eid + '", "name": "Harbor", "x": ' + value + "}", encoding="utf-8")
    folder = read_folder(tmp_path / "w")
    assert folder.all_elements() == {}
    assert [(s.path, s.reason) for s in folder.skipped] == [(path, f"unparseable JSON: {why}")]


#: Every other ``json.loads`` in the package, by file, with what it reads. A new one fails this test until it
#: goes through ``_outside_json`` or gets a line here.
NAMED = {
    "_outside_json.py": 1,  # the reader itself
    "calendar.py": 3,  # a calendar's own text, with its own integer rule and a parser past json's depth
    "errors.py": 2,  # a response body from the server
    "http.py": 1,  # a response body from the server
    "kanka.py": 1,  # the package's own tables
    "legendkeeper.py": 1,  # the import map a person keeps beside their export
    "lint.py": 1,  # the package's own schema
    "push.py": 1,  # a line of the log this package writes
}


def test_every_json_loads_is_the_outside_reader_or_named() -> None:
    def calls(path: Path, module: str) -> int:
        """Calls of ``<module>.loads`` or ``<module>.load`` in the file's code: its syntax tree, never its text."""
        return sum(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in ("loads", "load")
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == module
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        )

    files = sorted(SRC.glob("*.py"))
    assert len(files) > 40  # the search saw the package
    assert {p.name: calls(p, "json") for p in files if calls(p, "json")} == NAMED
    used = {p.name: calls(p, "_outside_json") for p in files if calls(p, "_outside_json")}
    # worldfile.py: an archive's world.json and a folder's records manifest; folder.py's reader reads its element files.
    assert used == {"folder.py": 1, "kanka.py": 1, "legendkeeper.py": 2, "lint.py": 1, "worldfile.py": 2}


# --- a writer that must read a file to leave something out ------------------------------------------------

#: What stands where a key's value goes in a hidden element's file that the reader does not hold.
REFUSED = {
    "nested 201 deep": "[" * 200 + "]" * 200,
    "nested 100,000 deep": DEEP,
    "an integer of 4,301 digits": LONG,
    "a number past the largest double": "1e400",
    "NaN": "NaN",
}


def _folder_with_hidden(root: Path, planted: str) -> tuple[Path, bytes]:
    """A folder of two elements; the second is hidden, names who changed it, and holds ``planted``."""
    world = {"id": "w0000000-0000-7000-8000-000000000000", "name": "W", "format_version": FORMAT_VERSION}
    write_folder(root, world, {"character": [{"id": "c-1", "name": "Bo"}]})
    secret = root / "elements" / "character" / "cy--c-2.json"
    data = ('{"id": "c-2", "name": "Cy", "hidden": true, "changed_by": "m-1", "x": ' + planted + "}").encode()
    secret.write_bytes(data)
    return secret, data


@pytest.mark.parametrize("planted", REFUSED.values(), ids=REFUSED.keys())
def test_a_share_leaves_out_a_file_it_could_not_read_and_a_copy_carries_it(tmp_path: Path, planted: str) -> None:
    """0.142.0 carried such a hidden element into a share with its author fields: the reader refused the file,
    and the writer took the refusal for "not an element". 0.143.0 refused the write. As ruled since: a share
    carries a file in a type folder only when it was read as an element and no mark was found."""
    secret, data = _folder_with_hidden(tmp_path / "w", planted)
    rel = "elements/character/cy--c-2.json"
    hidden: list[str] = []
    unread: list[str] = []
    share = read_world_file(
        world_file_bytes(tmp_path / "w", include_hidden=False, hidden_left_out=hidden, unread_left_out=unread)
    ).entries
    assert rel not in share
    assert (hidden, unread) == ([], [rel]), "listed apart from the hidden"
    # A copy carries it byte for byte, with author fields left out of the others (the default) or not.
    for authors in (False, True):
        whole = read_world_file(world_file_bytes(tmp_path / "w", include_author_fields=authors)).entries
        assert whole[rel] == data
    assert secret.read_bytes() == data


def test_a_share_at_the_depth_line_and_on_text_that_is_no_json(tmp_path: Path) -> None:
    secret, _ = _folder_with_hidden(tmp_path / "w", "[" * 199 + "]" * 199)
    rel = "elements/character/cy--c-2.json"
    hidden: list[str] = []
    unread: list[str] = []
    share = read_world_file(
        world_file_bytes(tmp_path / "w", include_hidden=False, hidden_left_out=hidden, unread_left_out=unread)
    ).entries
    assert (hidden, unread) == ([rel], []) and rel not in share, "read at the line: hidden, left out as hidden"
    # A hidden element's file cut short: no JSON, so its mark cannot be told. Left out of a share, carried by a copy.
    cut = b'{"id": "c-2", "hidden": true, '
    secret.write_bytes(cut)
    for broken in (cut, b"[1, 2]", b'{"\xe9":1}'):
        secret.write_bytes(broken)
        hidden, unread = [], []
        share = read_world_file(
            world_file_bytes(tmp_path / "w", include_hidden=False, hidden_left_out=hidden, unread_left_out=unread)
        ).entries
        assert (hidden, unread) == ([], [rel]) and rel not in share
        assert read_world_file(world_file_bytes(tmp_path / "w")).entries[rel] == broken
    # Without the lists the same bytes are written.
    assert world_file_bytes(tmp_path / "w", include_hidden=False) == world_file_bytes(
        tmp_path / "w", include_hidden=False, unread_left_out=[]
    )


# --- the Kanka door ----------------------------------------------------------------------------------------

KANKA = Path(__file__).resolve().parent / "fixtures" / "kanka" / "quay-export-world_20261025_011029.zip"
ENTITY = "characters/your-character-name_10074596.json"


def _export_with(tmp_path: Path, name: str, change: str | None) -> Path:
    """The export with ``change`` put in the entity's object as a new key's value; None cuts its last brace."""
    out = tmp_path / f"{name}.zip"
    with zipfile.ZipFile(KANKA) as src, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == ENTITY:
                text = data.decode("utf-8").rstrip()
                assert text.endswith("}")
                data = (text[:-1] if change is None else text[:-1] + ',"x_planted":' + change + "}").encode()
            dst.writestr(info.filename, data)
    return out


def _door(path: Path) -> tuple[dict[str, int], list[str]]:
    """What the door would write, by type, and its notes."""
    report = import_kanka(path, None, plan_only=True)
    return dict(report.counts), list(report.notes)


#: [the planted value, the error class the note names, or None when the file is read]
KANKA_CASES: dict[str, tuple[str, str | None]] = {
    "nested 200 deep, the line": ("[" * 199 + "]" * 199, None),
    "nested 201 deep, one past it": ("[" * 200 + "]" * 200, "ValueError"),
    "nested 100,000 deep": (DEEP, "ValueError"),
    "an integer of 4,301 digits": (LONG, "ValueError"),
    "a number past the largest double": ("1e400", "ValueError"),
    "NaN": ("NaN", "ValueError"),
    "-Infinity": ("-Infinity", "ValueError"),
    "2^53 - 1": ("9007199254740991", None),
    # The one difference from the npm SDK's door, which skips these two: Python holds the integer exactly.
    "2^53 + 1": ("9007199254740993", None),
    "an integer of 4,300 digits": ("9" * 4300, None),
}


def test_the_kanka_door_skips_a_file_it_cannot_hold_with_a_note_as_one_that_is_no_json(tmp_path: Path) -> None:
    whole = _door(KANKA)
    broken = _door(_export_with(tmp_path, "broken", None))
    assert [n for n in broken[1] if n.startswith(ENTITY)] == [f"{ENTITY}: not readable JSON (JSONDecodeError); skipped"]
    assert broken[0] != whole[0]
    for n, (name, (planted, error)) in enumerate(KANKA_CASES.items()):
        got = _door(_export_with(tmp_path, f"case-{n}", planted))
        if error is None:
            assert got == whole, name
        else:
            assert got[0] == broken[0], name
            assert got[1] == [note.replace("(JSONDecodeError)", f"({error})") for note in broken[1]], name


def test_the_kanka_door_text_after_the_one_json_value_is_no_json(tmp_path: Path) -> None:
    """Ruled 2026-11-23: a file's text is one JSON value and nothing after it but whitespace."""

    def with_tail(name: str, tail: str) -> Path:
        out = tmp_path / f"{name}.zip"
        with zipfile.ZipFile(KANKA) as src, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as dst:
            for info in src.infolist():
                data = src.read(info.filename)
                if info.filename == ENTITY:
                    data = data.decode("utf-8").rstrip().encode() + tail.encode()
                dst.writestr(info.filename, data)
        return out

    whole = _door(KANKA)
    broken = _door(_export_with(tmp_path, "broken", None))
    for n, tail in enumerate([' {"hidden": true}', " x", "{}"]):
        assert _door(with_tail(f"tail-{n}", tail)) == broken, tail
    assert _door(with_tail("space", " \n\t\r\n")) == whole


def test_the_kanka_door_writes_no_file_holding_a_number_the_export_does_not(tmp_path: Path) -> None:
    out = tmp_path / "world"
    import_kanka(_export_with(tmp_path, "inf", "1e400"), out)
    written = sorted(out.rglob("*.json"))
    assert len(written) > 10
    assert not any("Infinity" in p.read_text(encoding="utf-8") for p in written)

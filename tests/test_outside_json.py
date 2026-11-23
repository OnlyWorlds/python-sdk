"""Text this package did not write (a folder's file, an archive, another tool's export) is parsed through
``_outside_json.loads``: two inputs that are JSON by the grammar must come back as a ``ValueError`` a reader
catches, never a traceback. And every ``json.loads`` in the package is either that one or named here."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from onlyworlds import _outside_json, read_folder, write_folder
from onlyworlds.folder import FORMAT_VERSION

SRC = Path(__file__).resolve().parent.parent / "src" / "onlyworlds"
DEEP = "[" * 100_000 + "]" * 100_000
LONG = "7" * 4301


def test_what_json_reads_it_reads_the_same() -> None:
    for text in ('{"a": [1, 2.5, -3, 1e400, "x", null, true]}', "12345678901234567890", "-" + "7" * 4300, "[[[[1]]]]"):
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
    ("value", "why"), [(DEEP, "nested more than 200 deep"), (LONG, "a number of more than 4300 digits")]
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
    assert used == {"folder.py": 1, "kanka.py": 1, "legendkeeper.py": 2, "lint.py": 1, "worldfile.py": 4}

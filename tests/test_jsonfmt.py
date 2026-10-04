from __future__ import annotations

import json
import math

import pytest

from onlyworlds._jsonfmt import encode, js_number, serialize


@pytest.mark.parametrize(
    ("value", "js"),
    [
        (1.0, "1"),
        (-0.0, "0"),
        (0.5, "0.5"),
        (123.456, "123.456"),
        (1e16, "10000000000000000"),
        (1e21, "1e+21"),
        (1.5e21, "1.5e+21"),
        (1e-5, "0.00001"),
        (1e-6, "0.000001"),
        (1e-7, "1e-7"),
        (1.5e-7, "1.5e-7"),
        (-2.5e-10, "-2.5e-10"),
        (0.1 + 0.2, "0.30000000000000004"),
        (123456789012345680000.0, "123456789012345680000"),
        (5e-324, "5e-324"),
        (1.7976931348623157e308, "1.7976931348623157e+308"),
    ],
)
def test_js_number(value: float, js: str) -> None:
    assert js_number(value) == js


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
def test_non_finite_is_loud(bad: float) -> None:
    with pytest.raises(ValueError):
        serialize({"x": bad})


def test_agrees_with_json_dumps_where_json_dumps_is_already_right() -> None:
    body = {
        "id": "a",
        "name": "Ἀθῆναι — José 🐉",
        "n": 3,
        "neg": -7,
        "nil": None,
        "t": True,
        "f": False,
        "empty_list": [],
        "empty_obj": {},
        "nested": {"b": [1, {"z": "q"}, []], "a": 'ctrl\x01\x1f\t\n"\\'},
        "x_big": 2**70,
        "\u2028": "\u2028\u2029\x7f",
    }
    assert serialize(body) == json.dumps(body, indent=2, ensure_ascii=False) + "\n"


def test_key_order_as_received_including_integer_like_keys() -> None:
    # JSON.stringify would enumerate "1","2" first; §5 says as received, and this keeps it.
    assert serialize({"b": 1, "2": 2, "1": 3}) == '{\n  "b": 1,\n  "2": 2,\n  "1": 3\n}\n'


def test_lone_surrogate_escaped_like_es2019() -> None:
    value = json.loads('"a\\ud800b"')
    assert serialize(value) == '"a\\ud800b"\n'
    encode(value)  # must not raise


def test_bytes_are_utf8_lf_no_bom() -> None:
    b = encode({"name": "Σικελία"})
    assert not b.startswith(b"\xef\xbb\xbf")
    assert b"\r" not in b
    assert b.endswith(b"}\n")
    assert "Σικελία".encode() in b

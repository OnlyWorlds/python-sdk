"""The address profile (schema-dist ``profiles/address.md``, serial 77): ``element_address`` and
``parse_ow_link`` on every conformance case in ``codegen/schema-dist/profiles/address.fixture.json``, vendored
with the distribution. The vendored copy is the only source: a missing fixture fails, never skips. A case of a
kind this file does not know fails. The npm SDK's ``elementAddress`` and ``parseOwLink`` run the same cases."""

from __future__ import annotations

import dataclasses
import json
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any, get_args

import pytest

from onlyworlds import ELEMENT_TYPES, AddressError, AddressReason, element_address, parse_ow_link

REPO = Path(__file__).resolve().parents[1]
VENDORED = REPO / "codegen" / "schema-dist" / "profiles" / "address.fixture.json"
WORLD = "0199c3a1-7b2e-7c3d-8e4f-5a6b7c8d9e0f"


def load_fixture() -> dict[str, Any]:
    assert VENDORED.is_file(), f"no address fixture at {VENDORED}"
    doc: dict[str, Any] = json.loads(VENDORED.read_text(encoding="utf-8"))
    assert doc["profile"] == "address"
    return doc


def answer(case: dict[str, Any]) -> dict[str, Any]:
    """What the package answers for one case: ``{"expect": ...}`` or ``{"refuse": reason}``, the fixture's keys."""
    run: Callable[[], dict[str, Any]]
    if case["kind"] == "parse":

        def run() -> dict[str, Any]:
            return {"expect": dataclasses.asdict(parse_ow_link(case["text"]))}
    elif case["kind"] == "format":

        def run() -> dict[str, Any]:
            return {"expect": element_address(case["address"])}
    else:
        raise AssertionError(f"a case of unknown kind {case['kind']}")
    try:
        return run()
    except AddressError as err:
        return {"refuse": err.reason}


def test_every_case_of_the_address_fixture() -> None:
    cases = load_fixture()["cases"]
    wrong = []
    for c in cases:
        want = {"refuse": c["refuse"]} if "refuse" in c else {"expect": c["expect"]}
        got = answer(c)
        if got != want:
            wrong.append(f"{c['kind']}/{c['name']}: gave {got}, the fixture says {want}")
    kinds = Counter(c["kind"] for c in cases)
    refusals = sum("refuse" in c for c in cases)
    line = (
        f"address: {len(cases)} cases ({', '.join(f'{k} {n}' for k, n in sorted(kinds.items()))}), "
        f"{refusals} refusals, {len(wrong)} wrong"
    )
    print(line, *wrong, sep="\n")
    assert wrong == [], line
    assert len(cases) == 137, f"the fixture holds {len(cases)} cases, serial 97 has 137"
    assert kinds == {"parse": 101, "format": 36}


def test_the_refusals_are_the_fixtures_and_every_one_is_exercised() -> None:
    doc = load_fixture()
    assert list(get_args(AddressReason)) == doc["refusals"]
    used = {c["refuse"] for c in doc["cases"] if "refuse" in c}
    assert used <= set(doc["refusals"])
    assert set(doc["refusals"]) <= used
    assert sorted(doc["types"]) == sorted(ELEMENT_TYPES)


def test_a_reading_written_back_is_canonical_and_reads_back_the_same() -> None:
    n = 0
    for c in load_fixture()["cases"]:
        if c["kind"] != "parse" or "expect" not in c or c["expect"]["world_is_slug"]:
            continue
        written = element_address(parse_ow_link(c["text"]))
        again = parse_ow_link(written)
        assert again.canonical, (c["name"], written)
        assert {**dataclasses.asdict(again), "canonical": c["expect"]["canonical"]} == c["expect"], c["name"]
        if c["expect"]["canonical"]:
            assert written == c["text"], c["name"]
        n += 1
    assert n >= 40


def test_a_slug_reads_and_a_writer_refuses_it() -> None:
    reading = parse_ow_link("https://www.onlyworlds.com/w/hyperion")
    assert reading.world_is_slug
    with pytest.raises(AddressError) as err:
        element_address(reading)
    assert err.value.reason == "bad_world"


@pytest.mark.parametrize("value", [None, 42, {}, b"ow://x", ["ow://character/019a1f3c-2b4e-7d10-8c3a-6f2e9b0d4a71"]])
def test_a_value_that_is_not_a_string_is_not_an_address(value: Any) -> None:
    with pytest.raises(AddressError) as err:
        parse_ow_link(value)
    assert err.value.reason == "not_an_address"


def test_an_address_that_is_not_a_mapping_or_carries_an_unknown_key_is_a_type_error() -> None:
    value: Any
    for value in (None, "ow://x", [], 3):
        with pytest.raises(TypeError):
            element_address(value)
    with pytest.raises(TypeError, match="element_address: unknown key 'wrold'"):
        element_address({"form": "text", "wrold": WORLD})
    assert (
        element_address({"form": "text", "world": WORLD, "type": None, "lens": None, "moment": None}) == f"ow://{WORLD}"
    )


def test_a_moment_is_a_whole_number_never_a_boolean() -> None:
    base = {"form": "text", "world": WORLD}
    assert element_address({**base, "moment": 2.0}) == f"ow://{WORLD}@2"
    assert element_address({**base, "moment": -0.0}) == f"ow://{WORLD}@0"
    for bad in (True, False, float("inf"), float("nan"), 2**31, -(2**31) - 1, "3"):
        with pytest.raises(AddressError) as err:
            element_address({**base, "moment": bad})
        assert err.value.reason == "bad_moment", bad


def test_the_error_carries_the_reason_and_a_message() -> None:
    with pytest.raises(AddressError) as err:
        parse_ow_link("ow://dragon/019a1f3c-2b4e-7d10-8c3a-6f2e9b0d4a71")
    assert isinstance(err.value, ValueError)
    assert err.value.reason == "unknown_type"
    assert "22" in str(err.value)

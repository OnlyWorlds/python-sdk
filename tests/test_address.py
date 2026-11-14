"""The address profile (schema-dist ``profiles/address.md``, serial 77): ``element_address`` and
``parse_ow_link`` on every conformance case in ``codegen/schema-dist/profiles/address.fixture.json``, vendored
with the distribution. The vendored copy is the only source: a missing fixture fails, never skips. A case of a
kind this file does not know fails. The npm SDK's ``elementAddress`` and ``parseOwLink`` run the same cases."""

from __future__ import annotations

import dataclasses
import hashlib
import json
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any, get_args

import pytest

from onlyworlds import (
    ELEMENT_TYPES,
    AddressAt,
    AddressError,
    AddressReason,
    element_address,
    parse_ow_link,
    read_ow_link_at,
)

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
    elif case["kind"] == "prose":  # serial 123: an address found in prose, read by read_ow_link_at

        def run() -> dict[str, Any]:
            index = case.get("index", 0)
            found = read_ow_link_at(case["text"], index)
            if found is None:
                return {"expect": {"address": None, "reading": None}}
            address = case["text"][index : found.end]
            return {"expect": {"address": address, "reading": dataclasses.asdict(found.reading)}}
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
    assert len(cases) == 201, f"the fixture holds {len(cases)} cases, serial 126 has 201"
    assert kinds == {"parse": 104, "format": 36, "prose": 61}


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


# Serial 123: an address found in prose. The cases are one file both packages keep byte for byte (the npm SDK's
# copy beside its tests; this test holds its sha256); {W}, {E} and {L} stand for its ids.
PROSE_FILE = REPO / "tests" / "fixtures" / "address-in-prose.json"
PROSE_SHA256 = "864f5e47f9faedb9dc1f378c04da74d41be8a17dd194c759e7940468ff458bfc"


def _prose() -> dict[str, Any]:
    raw = PROSE_FILE.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == PROSE_SHA256
    doc: dict[str, Any] = json.loads(raw.decode("utf-8"))
    return doc


def _fill(s: str, ids: dict[str, str]) -> str:
    for key, value in ids.items():
        s = s.replace("{" + key + "}", value)
    return s


def test_every_address_in_prose_case() -> None:
    doc = _prose()
    ids: dict[str, str] = doc["ids"]
    wrong: list[str] = []
    for c in doc["cases"]:
        text, index = _fill(c["text"], ids), c["index"]
        want = None if c["address"] is None else _fill(c["address"], ids)
        found = read_ow_link_at(text, index)
        if index == 0 and read_ow_link_at(text) != found:
            wrong.append(f"{c['name']}: the default index is not 0")
        if want is None:
            if found is not None:
                wrong.append(f"{c['name']}: found {text[index : found.end]!r}, the case says no address")
            continue
        if found is None:
            wrong.append(f"{c['name']}: found nothing, the case says {want!r}")
            continue
        if text[index : found.end] != want:
            wrong.append(f"{c['name']}: found {text[index : found.end]!r}, the case says {want!r}")
        elif found.reading != parse_ow_link(want):
            wrong.append(f"{c['name']}: the reading is not the whole-string parser's")
    print(f"address in prose: {len(doc['cases'])} cases, {len(wrong)} wrong", *wrong, sep="\n")
    assert wrong == []
    assert len(doc["cases"]) == 39


W = "0193a1c2-7d3e-7f00-8a11-3c5e7b9d2f40"
E = "01a1d4ef-0000-7000-8000-000000000084"
L = "0193a1c2-7d3e-7f00-8a11-3c5e7b9d2f41"
SITE = "https://www.onlyworlds.com/w/"


@pytest.mark.parametrize(
    ("text", "address"),
    [
        # A moment's value is its whole run of digits after an optional minus, read by the step grammar or not taken.
        (f"ow://object/{E}@012", f"ow://object/{E}"),
        (f"ow://object/{E}@-0.", f"ow://object/{E}"),
        (f"ow://object/{E}@2147483647.", f"ow://object/{E}@2147483647"),
        (f"ow://object/{E}@-2147483648.", f"ow://object/{E}@-2147483648"),
        (f"ow://object/{E}@2147483648.", f"ow://object/{E}"),
        (f"ow://object/{E}@4@5", f"ow://object/{E}@4"),
        # A lens is the id after ?lens=, in either case of hex; the key is lens exactly; the lens comes after a moment.
        (f"ow://object/{E}?lens={L.upper()}.", f"ow://object/{E}?lens={L.upper()}"),
        (f"ow://object/{E}?LENS={L}", f"ow://object/{E}"),
        (f"ow://object/{E}?lens={L}@4", f"ow://object/{E}?lens={L}"),
        (f"ow://object/{E}?lens=", f"ow://object/{E}"),
        (f"ow://object/{E}?lens={L}0", f"ow://object/{E}?lens={L}"),
        # The path is the longest that parses: an id has its length, so what follows it is prose.
        (f"ow://object/{E}0", f"ow://object/{E}"),
        (f"ow://{W}/thing/{E}", f"ow://{W}"),
        (f"{SITE}{W}/event/{E}?lens={L}#x", f"{SITE}{W}/event/{E}?lens={L}"),
        # No path at all, a slug in the text form, white space at the index, another prefix: no address.
        ("ow://", None),
        ("ow://moppetopia.", None),
        (f" ow://object/{E}", None),
        (f"http://www.onlyworlds.com/w/{W}", None),
        (f"{SITE}ab", None),
    ],
)
def test_an_address_in_prose_at_its_edges(text: str, address: str | None) -> None:
    found = read_ow_link_at(text)
    if address is None:
        assert found is None
        return
    assert found is not None
    assert text[: found.end] == address
    assert found.reading == parse_ow_link(address)


@pytest.mark.parametrize(
    ("text", "address"),
    [
        # The run after /w/ is read whole, once, with no order between the forms (serial 123, amendments 6 and 8):
        # it ends at the first character outside the slug's alphabet or the id's; exactly an id's form, in either
        # case, is the id; any other legal slug run is the slug; else no address.
        (f"{SITE}{W}-x.", f"{SITE}{W}-x"),
        (f"{SITE}{W}abc.", f"{SITE}{W}abc"),
        (f"{SITE}{W.upper()}.", f"{SITE}{W.upper()}"),
        (f"{SITE}{W.upper()}-x.", None),
        (f"{SITE}{W}.", f"{SITE}{W}"),
        (f"{SITE}hyperion.", f"{SITE}hyperion"),
        (f"{SITE}hyperion-world/event/{E}.", f"{SITE}hyperion-world/event/{E}"),
        (f"{SITE}hyperion/charcter/{E}.", f"{SITE}hyperion"),
        # A slug run that is a type word, ends in a hyphen or runs past forty characters is no address, nor one that
        # starts outside the alphabet.
        (f"{SITE}event.", None),
        (f"{SITE}Moppetopia.", None),
        (f"{SITE}my-world-.", None),
        (f"{SITE}moppetopia-", None),
        (f"{SITE}{'a' * 41}.", None),
        (f"{SITE}{'a' * 40}.", f"{SITE}{'a' * 40}"),
        # A run followed by a letter or an underscore is cut inside a word: no address.
        (f"{SITE}mopPetopia.", None),
        (f"{SITE}hyper_ion.", None),
        # A combining mark counts with the letters: a decomposed cafe-acute is cut inside a word.
        (f"{SITE}cafe" + chr(0x301) + ".", None),
        (f"{SITE}{W}G", None),
        (f"{SITE}{W}_", None),
        (f"{SITE}hyperion/", f"{SITE}hyperion"),
    ],
)
def test_the_run_after_w_is_read_whole_once(text: str, address: str | None) -> None:
    found = read_ow_link_at(f"See {text}", 4)
    if address is None:
        assert found is None
        return
    assert found is not None
    assert text[: found.end - 4] == address
    assert found.reading == parse_ow_link(address)


def test_read_ow_link_at_answers_the_reading_and_its_end() -> None:
    text = f"Built the gate: ow://object/{E.upper()}."
    found = read_ow_link_at(text, 16)
    assert found == AddressAt(parse_ow_link(f"ow://object/{E.upper()}"), 16 + 12 + 36)
    assert found is not None and found.reading.id == E and found.reading.canonical is False
    assert text[found.end :] == "."
    # An index at the text's end or past it holds no address; a negative one is out of range, a ValueError.
    assert read_ow_link_at(text, len(text)) is None
    assert read_ow_link_at(text, len(text) + 1) is None
    with pytest.raises(ValueError):
        read_ow_link_at(text, -1)
    with pytest.raises(TypeError):
        read_ow_link_at(None, 0)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        read_ow_link_at(text, True)
    with pytest.raises(TypeError):
        read_ow_link_at(text, 1.0)  # type: ignore[arg-type]

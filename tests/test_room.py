"""The room profile (schema-dist ``profiles/room.md``, serial 45): ``ROOM_PAIRS`` against the fixture's
pairs, and ``is_room_element`` (the pair AND the mark ``x_room_of``) on every conformance case in
``codegen/schema-dist/profiles/room.fixture.json``, vendored with the distribution, and ``talks_of`` on every
``talk_cases`` case (serial 135). The npm SDK's ``isRoomElement`` and ``talksOf`` run the same cases."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from onlyworlds import ROOM_PAIRS, FolderElement, is_room_element, talks_of

REPO = Path(__file__).resolve().parent.parent
FIXTURE = REPO / "codegen" / "schema-dist" / "profiles" / "room.fixture.json"
WORLD = "0199c3a1-7b2e-7c3d-8e4f-5a6b7c8d9e0f"


def load_fixture() -> dict[str, Any]:
    assert FIXTURE.is_file(), f"no room fixture at {FIXTURE}"
    doc: dict[str, Any] = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert doc["profile"] == "room"
    return doc


def test_room_pairs_are_the_fixtures_in_order_and_the_mark_is_x_room_of() -> None:
    doc = load_fixture()
    assert [{"type": t, "supertype": s} for t, s in ROOM_PAIRS] == doc["pairs"]
    assert len(ROOM_PAIRS) == 10
    assert doc["mark"]["field"] == "x_room_of"


def test_is_room_element_answers_every_fixture_case() -> None:
    cases = load_fixture()["cases"]
    wrong = [
        f"{c['name']}: {c['element']} gave {got}, the fixture says {c['in_room']}"
        for c in cases
        if (got := is_room_element(c["element"])) is not c["in_room"]
    ]
    assert wrong == []
    assert len(cases) == 48, f"the fixture holds {len(cases)} cases, serial 131 has 48"


def test_without_a_string_type_or_supertype_or_a_mark_it_is_not_in_the_room() -> None:
    assert is_room_element({}) is False
    assert is_room_element({"type": "narrative", "x_room_of": WORLD}) is False
    assert is_room_element({"supertype": "Message", "x_room_of": WORLD}) is False
    assert is_room_element({"type": "narrative", "supertype": "   ", "x_room_of": WORLD}) is False
    assert is_room_element({"type": "narrative", "supertype": "Message", "x_room_of": None}) is False
    assert is_room_element({"type": "narrative", "supertype": "Message"}) is False


def test_the_mark_is_read_by_presence_never_by_its_value() -> None:
    """room.md (serial 83): a mark counts when its value is not null, a string only when something is left after
    the White_Space trim; any other value counts as present."""
    message = {"type": "narrative", "supertype": "Message"}
    present: tuple[Any, ...] = (7, 0, False, ["x"], {"world": WORLD}, "x", chr(0x1F), chr(0xFEFF), f"  {WORLD}  ")
    for mark in present:
        assert is_room_element({**message, "x_room_of": mark}) is True, repr(mark)
    # Since serial 126: an empty list or an empty object is absent too (a compact reader leaves both out).
    absent: tuple[Any, ...] = (None, "", " ", chr(0xA0) + chr(0x3000), "\t\n", [], {})
    for mark in absent:
        assert is_room_element({**message, "x_room_of": mark}) is False, repr(mark)


def test_the_fold_is_unicode_simple_case_folding_as_the_npm_sdk() -> None:
    long_s = chr(0x17F)  # LATIN SMALL LETTER LONG S simple-folds to "s"; str.lower() leaves it
    assert is_room_element({"type": "NARRATIVE", "supertype": f"Me{long_s}{long_s}age", "x_room_of": WORLD}) is True
    assert is_room_element({"type": "Relation", "supertype": "\tWORK ITEM\n", "x_room_of": WORLD}) is True


# Unicode's White_Space property, the 25 code points (PropList.txt), typed here apart from the module's
# constant so the sweep below checks one against the other.
WHITE_SPACE = {
    *range(0x09, 0x0E),
    0x20,
    0x85,
    0xA0,
    0x1680,
    *range(0x2000, 0x200B),
    0x2028,
    0x2029,
    0x202F,
    0x205F,
    0x3000,
}


def test_trimmed_is_unicode_white_space_at_both_ends_and_nothing_else() -> None:
    """room.md (dist.47), "Trimmed and without regard to case, defined once"; as ruled:
    White_Space is stripped at both ends, a byte order mark stays, nothing inside is touched."""
    assert is_room_element({"type": "narrative", "supertype": " Message\u3000", "x_room_of": WORLD}) is True
    assert is_room_element({"type": "\xa0narrative\u2029", "supertype": "Message", "x_room_of": WORLD}) is True
    assert is_room_element({"type": "narrative", "supertype": "\ufeffMessage", "x_room_of": WORLD}) is False
    # U+001C is stripped by str.strip() (str.isspace) but is not White_Space.
    assert is_room_element({"type": "narrative", "supertype": "\x1cMessage", "x_room_of": WORLD}) is False
    assert is_room_element({"type": "narrative", "supertype": "\u200bMessage", "x_room_of": WORLD}) is False
    assert is_room_element({"type": "relation", "supertype": "Work\u3000item", "x_room_of": WORLD}) is False


def test_the_trim_strips_exactly_white_space_over_the_whole_bmp() -> None:
    assert len(WHITE_SPACE) == 25
    stripped = {
        cp
        for cp in range(0x10000)
        if is_room_element({"type": "narrative", "supertype": f"{chr(cp)}Message{chr(cp)}", "x_room_of": WORLD})
    }
    assert stripped == WHITE_SPACE


def test_a_folder_element_is_matched_by_its_type_even_when_the_body_has_none() -> None:
    body = {"id": "0192a000-aaaa-7bbb-8ccc-000000000001", "name": "a line", "supertype": "Message"}
    marked = {**body, "x_room_of": WORLD}

    def element(b: dict[str, Any]) -> FolderElement:
        path = Path("elements/narrative/a-line.json")
        return FolderElement(id=b["id"], type="narrative", type_inferred=True, body=b, path=path, layout="elements")

    assert is_room_element(element(marked)) is True
    assert is_room_element(marked) is False  # the body alone has no type
    assert is_room_element(element(body)) is False  # a letter without the mark is lore


# ---- The talk on an Object or a Construct (room.md, serial 135): talks_of over the fixture's talk_cases

TALK_CASES: list[dict[str, Any]] = load_fixture()["talk_cases"]


def talk_set(rows: list[Any]) -> set[tuple[str, str]]:
    return {(row["type"], row["id"]) for row in rows}


def test_the_fixture_holds_serial_135s_talk_cases() -> None:
    assert len(TALK_CASES) == 13, f"the fixture holds {len(TALK_CASES)} talk cases, serial 135 has 13"
    assert len({c["name"] for c in TALK_CASES}) == 13


@pytest.mark.parametrize("case", TALK_CASES, ids=lambda c: c["name"])
def test_talk_case(case: dict[str, Any]) -> None:
    """Compared as a set, as the page says; each talk once."""
    before = json.dumps(case["element"], sort_keys=True)
    got = talks_of(case["element"])
    assert talk_set(got) == talk_set(case["talks"]), case.get("note")
    assert len(got) == len(talk_set(got)), f"a talk twice: {got}"
    assert json.dumps(case["element"], sort_keys=True) == before, "talks_of moved the element"


LINE = {"id": "019a8b00-0000-7000-8000-0000000001ff", "type": "narrative", "supertype": "Message", "x_room_of": WORLD}
OBJ = "019a8b00-0000-7000-8000-000000000201"
CON = "019a8b00-0000-7000-8000-000000000211"


def test_talks_come_once_in_first_place_objects_before_constructs() -> None:
    # The package's own case: the order talks_of promises (the page compares as a set) and a duplicate id.
    line = {**LINE, "constructs": [CON, OBJ], "objects": [OBJ, "b", OBJ, "a"]}
    assert talks_of(line) == [
        {"type": "object", "id": OBJ},
        {"type": "object", "id": "b"},
        {"type": "object", "id": "a"},
        {"type": "construct", "id": CON},
        {"type": "construct", "id": OBJ},
    ]


def test_an_entry_with_a_space_left_on_it_is_read_as_written() -> None:
    # The package's own case: a space before, a no-break space after, and the id in upper case, each its own talk.
    line = {**LINE, "objects": [f" {OBJ}", f"{OBJ}{chr(0xA0)}", OBJ.upper(), OBJ]}
    assert [t["id"] for t in talks_of(line)] == [f" {OBJ}", f"{OBJ}{chr(0xA0)}", OBJ.upper(), OBJ]


def test_white_space_alone_names_nothing_and_other_marks_are_ids() -> None:
    # The package's own case: the trim is White_Space exactly, so U+001F and a byte order mark are left and name an
    # id as written, while a no-break space and an ideographic space alone name nothing.
    blank = ["", " ", chr(0xA0), chr(0x3000) + "\t", chr(0x2028)]
    line = {**LINE, "objects": [*blank, chr(0x1F), chr(0xFEFF)], "constructs": blank}
    assert talks_of(line) == [{"type": "object", "id": chr(0x1F)}, {"type": "object", "id": chr(0xFEFF)}]


@pytest.mark.parametrize("value", [OBJ, {"id": OBJ}, 7, None, (OBJ,), True])
def test_a_field_that_is_no_list_names_nothing(value: Any) -> None:
    # The package's own case: a string, a mapping, a number, null, a tuple and a boolean are no list.
    assert talks_of({**LINE, "objects": value, "constructs": value}) == []


def test_a_line_is_read_as_is_room_element_reads_one() -> None:
    # The package's own case: the pair trimmed and folded, the mark by presence; a folder element by its type.
    assert talks_of({**LINE, "type": " NARRATIVE", "supertype": "message\t", "objects": [OBJ]}) == [
        {"type": "object", "id": OBJ}
    ]
    absent: tuple[Any, ...] = (None, "", " ", [], {})
    for mark in absent:
        assert talks_of({**LINE, "x_room_of": mark, "objects": [OBJ]}) == [], repr(mark)
    assert talks_of({**LINE, "x_room_of": 7, "objects": [OBJ]}) == [{"type": "object", "id": OBJ}]
    assert talks_of({**LINE, "supertype": "Messages", "objects": [OBJ]}) == []
    assert talks_of({**LINE, "supertype": "Work item", "type": "relation", "objects": [OBJ]}) == []
    body = {"id": "l1", "supertype": "Message", "x_room_of": WORLD, "constructs": [CON]}
    path = Path("elements/narrative/l1.json")
    el = FolderElement(id="l1", type="narrative", type_inferred=True, body=body, path=path, layout="elements")
    assert talks_of(el) == [{"type": "construct", "id": CON}]
    no_element: tuple[Any, ...] = (None, [], "a line", 7)
    for nothing in no_element:
        assert talks_of(nothing) == []

"""The room profile (schema-dist ``profiles/room.md``, serial 45): ``ROOM_PAIRS`` against the fixture's
pairs, and ``is_room_element`` (the pair AND the mark ``x_room_of``) on every conformance case in
``codegen/schema-dist/profiles/room.fixture.json``, vendored with the distribution. The npm SDK's
``isRoomElement`` runs the same cases."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from onlyworlds import ROOM_PAIRS, FolderElement, is_room_element

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
    assert len(ROOM_PAIRS) == 9
    assert doc["mark"]["field"] == "x_room_of"


def test_is_room_element_answers_every_fixture_case() -> None:
    cases = load_fixture()["cases"]
    wrong = [
        f"{c['name']}: {c['element']} gave {got}, the fixture says {c['in_room']}"
        for c in cases
        if (got := is_room_element(c["element"])) is not c["in_room"]
    ]
    assert wrong == []
    assert len(cases) == 28, f"the fixture holds {len(cases)} cases, serial 71 has 28"


def test_without_a_string_type_supertype_or_mark_it_is_not_in_the_room() -> None:
    assert is_room_element({}) is False
    assert is_room_element({"type": "narrative", "x_room_of": WORLD}) is False
    assert is_room_element({"supertype": "Message", "x_room_of": WORLD}) is False
    assert is_room_element({"type": "narrative", "supertype": "   ", "x_room_of": WORLD}) is False
    assert is_room_element({"type": "narrative", "supertype": "Message", "x_room_of": 7}) is False


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
    """room.md (dist.47), "Trimmed and without regard to case, defined once"; Skeld's ruling:
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

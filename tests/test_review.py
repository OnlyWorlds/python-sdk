"""The review profile (schema-dist ``profiles/review.md``): ``proposed_mark_of`` (the mark as a reader that shows
a world shows it, rules 1, 2 and 4) and ``hands_on_as_proposed`` (what a reader that hands a world on leaves out,
rules 1 and 4). The profile has no fixture yet; these cases are the npm SDK's too (``test/review.test.mjs``),
case for case."""

from __future__ import annotations

from types import MappingProxyType
from typing import Any

import pytest

from onlyworlds import PROPOSED_MARK, hands_on_as_proposed, proposed_mark_of
from onlyworlds.pack import is_proposed

TODAY = "2026-10-26"
_NO_KEY = object()

FS = chr(0x1C)
BOM = chr(0xFEFF)
ARABIC_DAY = "".join(chr(c) for c in (0x662, 0x660, 0x662, 0x666)) + "-10-01"

# (what, the mark (_NO_KEY: no key), proposed_mark_of's answer, hands_on_as_proposed's answer)
CASES: list[tuple[str, Any, Any, bool]] = [
    ("no key", _NO_KEY, None, False),
    ("null: settled", None, None, False),
    ("a string: not a mark, a doubt", "yes", None, True),
    ("an empty string: an empty mark, settled", "", None, False),
    ("ASCII spaces only: an empty mark, settled", "   ", None, False),
    ("an empty array: an empty mark, settled", [], None, False),
    ("an array holding an empty array: present, not a mark, a doubt", [[]], None, True),
    ("false: a value, a doubt", False, None, True),
    ("zero: a value, a doubt", 0, None, True),
    ("an empty object: an empty mark, settled", {}, None, False),
    (
        "an object with no key the profile names: present, a mark",
        {"x": None},
        {"by": None, "expires": None, "lapsed": False},
        True,
    ),
    (
        "an object holding only a key the profile does not name: a mark (rule 5)",
        {"note": "x"},
        {"by": None, "expires": None, "lapsed": False},
        True,
    ),
    (
        "an object whose by is null: a mark, no proposer named (rule 5)",
        {"by": None},
        {"by": None, "expires": None, "lapsed": False},
        True,
    ),
    ("one: a value, a doubt", 1, None, True),
    ("true: a value, a doubt", True, None, True),
    ("a list holding a string: present, not a mark, a doubt", ["a"], None, True),
    (
        "a whole mark, open",
        {"by": "m1", "evidence": "seen", "expires": "2026-11-01"},
        {"by": "m1", "expires": "2026-11-01", "lapsed": False},
        True,
    ),
    (
        "a by read as stored, never trimmed; expires trimmed",
        {"by": "  m1 ", "expires": " 2026-11-01 "},
        {"by": "  m1 ", "expires": "2026-11-01", "lapsed": False},
        True,
    ),
    (
        "a by of owner with White_Space around it is not the word owner",
        {"by": " owner\n"},
        {"by": " owner\n", "expires": None, "lapsed": False},
        True,
    ),
    ("lapses on its own day", {"by": "m1", "expires": TODAY}, {"by": "m1", "expires": TODAY, "lapsed": True}, True),
    (
        "lapsed before today",
        {"by": "m1", "expires": "2026-10-01"},
        {"by": "m1", "expires": "2026-10-01", "lapsed": True},
        True,
    ),
    (
        "an expires not shaped as a day",
        {"by": "m1", "expires": "2026-1-1"},
        {"by": "m1", "expires": None, "lapsed": False},
        True,
    ),
    ("a blank or non-string by", {"by": "   ", "expires": 7}, {"by": None, "expires": None, "lapsed": False}, True),
    (
        "a by that is not a string names nobody",
        {"by": 7, "expires": "2026-11-01"},
        {"by": None, "expires": "2026-11-01", "lapsed": False},
        True,
    ),
    # The two languages' own defaults disagree here (see the npm test): both test presence by White_Space, trim
    # expires by it, read ASCII digits and keep a by as stored.
    ("U+3000 only: White_Space, an empty mark, settled", chr(0x3000), None, False),
    ("U+001C only: not White_Space, present, a doubt", FS, None, True),
    ("a byte order mark only: not White_Space, present, a doubt", BOM, None, True),
    (
        "a by wrapped in U+001C keeps it",
        {"by": f"{FS}m1{FS}"},
        {"by": f"{FS}m1{FS}", "expires": None, "lapsed": False},
        True,
    ),
    (
        "a by wrapped in a byte order mark keeps it",
        {"by": f"{BOM}m1"},
        {"by": f"{BOM}m1", "expires": None, "lapsed": False},
        True,
    ),
    (
        "an expires in Arabic-Indic digits is no day",
        {"by": "m1", "expires": ARABIC_DAY},
        {"by": "m1", "expires": None, "lapsed": False},
        True,
    ),
    (
        "an expires wrapped in a no-break space is trimmed",
        {"expires": chr(0xA0) + "2026-10-01"},
        {"by": None, "expires": "2026-10-01", "lapsed": True},
        True,
    ),
]


def _el(mark: Any) -> dict[str, Any]:
    return {"id": "a", "name": "A"} if mark is _NO_KEY else {"id": "a", "name": "A", PROPOSED_MARK: mark}


def test_the_mark_key_is_the_profiles() -> None:
    assert PROPOSED_MARK == "x_review_proposed"


@pytest.mark.parametrize(("what", "mark", "shown", "handed_on"), CASES, ids=[c[0] for c in CASES])
def test_review_case(what: str, mark: Any, shown: Any, handed_on: bool) -> None:
    assert proposed_mark_of(_el(mark), TODAY) == shown
    assert hands_on_as_proposed(_el(mark)) is handed_on
    assert is_proposed(_el(mark)) is handed_on  # the pack's reader is the same rule


def test_not_an_element_reads_as_settled() -> None:
    for v in (None, "x", 3, ["a"]):
        assert proposed_mark_of(v, TODAY) is None
        assert hands_on_as_proposed(v) is False


def test_today_must_be_a_day() -> None:
    with pytest.raises(TypeError):
        proposed_mark_of(_el({}), "26-10-2026")
    with pytest.raises(TypeError):
        proposed_mark_of(_el({}), 20261026)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        proposed_mark_of(_el({}), ARABIC_DAY)
    with pytest.raises(TypeError):  # Python's $ matches before a final newline; the day is the whole string
        proposed_mark_of(_el({}), "2026-10-31\n")
    assert proposed_mark_of(_el({"by": "m1"})) is not None  # today in UTC by default


def test_a_mapping_that_is_not_a_dict_reads_as_a_dict_does() -> None:
    # npm reads any object; a read-only view of an element (a MappingProxyType, a frozen record) is still one.
    mark = {"by": "m1", "expires": "2026-12-01"}
    for element in (
        MappingProxyType({"id": "a", PROPOSED_MARK: mark}),
        {"id": "a", PROPOSED_MARK: MappingProxyType(mark)},
        MappingProxyType({"id": "a", PROPOSED_MARK: MappingProxyType(mark)}),
    ):
        assert proposed_mark_of(element, "2026-11-02") == {"by": "m1", "expires": "2026-12-01", "lapsed": False}
        assert hands_on_as_proposed(element)
    # An empty mark is settled whatever mapping holds it.
    empty = MappingProxyType({"id": "a", PROPOSED_MARK: MappingProxyType({})})
    assert proposed_mark_of(empty, "2026-11-02") is None
    assert not hands_on_as_proposed(empty)

"""The review profile (schema-dist ``profiles/review.md``): ``proposed_mark_of`` (the mark as a reader that shows
a world shows it, rules 1, 2 and 4) and ``hands_on_as_proposed`` (what a reader that hands a world on leaves out,
rules 1 and 4). The profile has no fixture yet; these cases are the npm SDK's too (``test/review.test.mjs``),
case for case."""

from __future__ import annotations

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
    ("an array: not a mark, a doubt", [], None, True),
    ("false: a value, a doubt", False, None, True),
    ("zero: a value, a doubt", 0, None, True),
    ("an empty object", {}, {"by": None, "expires": None, "lapsed": False}, True),
    (
        "a whole mark, open",
        {"by": "m1", "evidence": "seen", "expires": "2026-11-01"},
        {"by": "m1", "expires": "2026-11-01", "lapsed": False},
        True,
    ),
    (
        "trimmed by and expires",
        {"by": "  m1 ", "expires": " 2026-11-01 "},
        {"by": "m1", "expires": "2026-11-01", "lapsed": False},
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
    # The two languages' own defaults disagree here (see the npm test): both trim by White_Space and read ASCII digits.
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
    assert proposed_mark_of(_el({})) is not None  # today in UTC by default

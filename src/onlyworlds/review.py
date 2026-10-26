"""The review profile's proposed mark (schema-dist ``profiles/review.md``): an element written as proposed.

An element whose ``x_review_proposed`` is an object was written as proposed (an AI seat's new element on a
world whose keeper reviews them) and is not canon until a keeper settles it: accept writes the mark null,
decline deletes the element.

Two readings, as the profile's rule 1 and rule 4 give them. A reader that shows a world to its people shows
the mark when it is an object (``proposed_mark_of``); any other value is not a mark and is reported by a
lint, never repaired. A reader that hands a world on leaves out every element whose ``x_review_proposed``
is anything but absent or null (``hands_on_as_proposed``), so a doubt never reaches an AI as canon. The npm
SDK's ``proposedMarkOf`` and ``handsOnAsProposed`` are the same readers, and ``tests/test_review.py`` holds
the same cases as its ``test/review.test.mjs``.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any, TypedDict

from .room import _WHITE_SPACE

PROPOSED_MARK = "x_review_proposed"

_DAY = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")


class ProposedMark(TypedDict):
    """A proposed element's mark as a reader shows it."""

    #: The membership or seat that proposed it, trimmed of Unicode White_Space as the room profile trims,
    #: when the mark names one.
    by: str | None
    #: The day it lapses (YYYY-MM-DD), trimmed, when the mark gives one in that shape.
    expires: str | None
    #: ``expires`` has come (on or before ``today``): shown as lapsed, never deleted on its own (rule 2).
    lapsed: bool


def _today() -> str:
    """Today as the profile writes a day, in UTC: keel reads a proposal as lapsed from midnight UTC of its day."""
    return datetime.now(UTC).strftime("%Y-%m-%d")


def proposed_mark_of(element: Any, today: str | None = None) -> ProposedMark | None:
    """The proposed mark of an element as a reader that shows a world shows it, or None for a settled
    element: ``x_review_proposed`` absent, None, or a value that is not an object (a list included).
    ``today`` is a day as the profile writes one (YYYY-MM-DD), by default today in UTC; anything else is
    a TypeError."""
    if today is not None and not (isinstance(today, str) and _DAY.match(today)):
        raise TypeError(f"proposed_mark_of: today is a day as YYYY-MM-DD; got {today!r}.")
    if not isinstance(element, dict):
        return None
    v = element.get(PROPOSED_MARK)
    if not isinstance(v, dict):
        return None
    raw_by = v.get("by")
    by = raw_by.strip(_WHITE_SPACE) if isinstance(raw_by, str) and raw_by.strip(_WHITE_SPACE) else None
    raw_exp = v.get("expires")
    expires = (
        raw_exp.strip(_WHITE_SPACE) if isinstance(raw_exp, str) and _DAY.match(raw_exp.strip(_WHITE_SPACE)) else None
    )
    lapsed = expires is not None and expires <= (today or _today())
    return {"by": by, "expires": expires, "lapsed": lapsed}


def hands_on_as_proposed(element: Any) -> bool:
    """Whether a reader that hands a world on (a pack, a context packet, an AI's context) leaves this
    element out as proposed: ``x_review_proposed`` with any value but absent or None, a value that is not a
    proper mark included (a doubt, counted with the proposed)."""
    return isinstance(element, dict) and element.get(PROPOSED_MARK) is not None

"""The review profile's proposed mark (schema-dist ``profiles/review.md``): an element written as proposed.

An element whose ``x_review_proposed`` is an object was written as proposed (an AI seat's new element on a
world whose keeper reviews them) and is not canon until a keeper settles it: accept writes the mark null,
decline deletes the element.

The mark is read by presence, as the room and charter profiles read theirs (rule 1, serial 87): absent,
None, a string with nothing left after trimming White_Space, an empty list and an empty object are all no
mark, and the element is settled. Any other value is present. Two readings of a present value, as rules 1,
4 and 5 give them. A reader that shows a world to its people shows the mark when it is an object, and an
object with at least one key is a mark whatever its keys and their values (rule 5: ``{"note": "x"}`` and
``{"by": None}`` are proposed, with no proposer named and no lapse day) (``proposed_mark_of``); any other
value is not a mark and is reported by a lint, never repaired. A reader
that hands a world on leaves out every element whose mark is present (``hands_on_as_proposed``), so a doubt
never reaches an AI as canon. The npm
SDK's ``proposedMarkOf`` and ``handsOnAsProposed`` are the same readers, and ``tests/test_review.py`` holds
the same cases as its ``test/review.test.mjs``.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, TypedDict

from .room import _WHITE_SPACE, _has_mark

PROPOSED_MARK = "x_review_proposed"

_DAY = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")


class ProposedMark(TypedDict):
    """A proposed element's mark as a reader shows it."""

    #: Who made the mark, in the writer's own word: a claim, with no format to rely on, and never proof of who wrote the
    #: mark or the element. Read as stored, never trimmed: a ``by`` that is not a string, or is White_Space alone, names
    #: nobody (None); White_Space around a word or an id makes it neither. Show it as the mark's word (for example "the
    #: mark names Ada"), in a form that keeps the name visibly the mark's, never as a fact ("proposed by Ada"). Put a
    #: name in its place in two cases only: your platform resolves it to a member on its roster or to the world's owner,
    #: comparing ids as ids, with the name it serves this reader (the id where it serves none) and the owner, an AI's
    #: seat or a player's seat said beside it; otherwise, it is the id of a Character of the same world this reader is
    #: served, said as that Character with its type, never as the member who plays it. Every other ``by`` is shown only
    #: as the raw value, apart, never where a name stands.
    by: str | None
    #: The day it lapses (YYYY-MM-DD), trimmed, when the mark gives one in that shape.
    expires: str | None
    #: ``expires`` has come (on or before ``today``): shown as lapsed, never deleted on its own (rule 2).
    lapsed: bool


def _today() -> str:
    """Today as the profile writes a day, in UTC: keel reads a proposal as lapsed from midnight UTC of its day."""
    return datetime.now(UTC).strftime("%Y-%m-%d")


def _present(value: Any) -> bool:
    """The review profile's presence rule for its mark (rule 1): the room and charter profiles' (``room._has_mark``:
    any value but None, a string only when something is left after trimming White_Space), and an empty list or an
    empty object is absent too."""
    return _has_mark(value) and not (isinstance(value, (list, Mapping)) and not value)


def proposed_mark_of(element: Any, today: str | None = None) -> ProposedMark | None:
    """The proposed mark of an element as a reader that shows a world shows it, or None for a settled
    element: ``x_review_proposed`` absent, None, empty (a blank string, ``[]``, ``{}``), or a value that is
    not an object (a list included). An object with at least one key is a mark whatever its keys (rule 5): a
    ``by`` that is not a string with something in it names no proposer, and an ``expires`` not shaped as a day
    never lapses.
    ``today`` is a day as the profile writes one (YYYY-MM-DD), by default today in UTC; anything else is
    a TypeError."""
    if today is not None and not (isinstance(today, str) and _DAY.fullmatch(today)):
        raise TypeError(f"proposed_mark_of: today is a day as YYYY-MM-DD; got {today!r}.")
    if not isinstance(element, Mapping):
        return None
    v = element.get(PROPOSED_MARK)
    if not isinstance(v, Mapping) or not _present(v):
        return None
    raw_by = v.get("by")
    by = raw_by if isinstance(raw_by, str) and raw_by.strip(_WHITE_SPACE) else None
    raw_exp = v.get("expires")
    expires = (
        raw_exp.strip(_WHITE_SPACE)
        if isinstance(raw_exp, str) and _DAY.fullmatch(raw_exp.strip(_WHITE_SPACE))
        else None
    )
    lapsed = expires is not None and expires <= (today or _today())
    return {"by": by, "expires": expires, "lapsed": lapsed}


def hands_on_as_proposed(element: Any) -> bool:
    """Whether a reader that hands a world on (a pack, a context packet, an AI's context) leaves this
    element out as proposed: ``x_review_proposed`` present (not absent, None, a blank string, ``[]`` or
    ``{}``), a value that is not a proper mark included (a doubt, counted with the proposed)."""
    return isinstance(element, Mapping) and _present(element.get(PROPOSED_MARK))

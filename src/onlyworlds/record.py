"""The record profile (schema-dist ``profiles/record.md``, serial 102): a game's run kept in the world its Characters
live in.

The run is an Event carrying the mark ``x_record`` (``tool`` and ``played_at`` required; ``version``, ``seed``,
``outcome`` and ``seats`` optional), the game's own tally beside it under its own prefix. Who took part is the Event's
``characters`` alone; a Narrative that lists the Event in ``events`` and names a Character as ``protagonist`` or
``narrator`` is that Character's story of it. A run or a story the review profile reads as proposed
(``proposed_mark_of``: an empty mark is settled; serial 103) is not read until a keeper settles it.
``records_of(character_id, elements)`` reads the elements as the reader is served them. Pure: nothing is stored or
written. The fixture
(``codegen/schema-dist/profiles/record.fixture.json``) is replayed whole by ``tests/test_record.py``; the npm SDK's
``recordsOf`` gives the same answers on the same input.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any, Literal, TypedDict

from .message import _instant
from .review import proposed_mark_of

#: The Event's field that carries the record's mark.
RECORD_FIELD = "x_record"

_TOOL = re.compile(r"[a-z0-9-]{1,32}")
_OUTCOME = re.compile(r"[a-z]{1,24}")


class RecordMark(TypedDict):
    """A record's mark as read: the required two as written, each optional member None when unset."""

    tool: str
    played_at: str
    version: str | None
    seed: str | None
    outcome: str | None
    seats: dict[str, str]


#: One Character's story of a record: about them (``protagonist``), told by them (``narrator``), or ``both``.
#: Declared by key, since ``as`` is a Python keyword.
RecordStory = TypedDict("RecordStory", {"id": str, "name": str, "as": Literal["protagonist", "narrator", "both"]})


class RecordEvent(TypedDict):
    id: str
    name: str


class Record(TypedDict):
    """One record of a Character, as ``records_of`` reads it."""

    event: RecordEvent
    tool: str
    played_at: str
    version: str | None
    seed: str | None
    outcome: str | None
    seat: str | None
    stories: list[RecordStory]


def _unset_or(value: Any, ok: bool) -> bool:
    return value is None or ok


def _proposed(element: Mapping[str, Any]) -> bool:
    """Proposed exactly when the review profile's reader says so (serial 103): an empty mark ({}, "", []) is settled."""
    return proposed_mark_of(element) is not None


def _hashable(value: Any) -> bool:
    try:
        hash(value)
    except TypeError:
        return False
    return True


def record_mark_of(element: Any) -> RecordMark | None:
    """The record's mark on an element, or None.

    The mark when the element is an Event whose ``x_record`` has the profile's shape. A broken writer never shows as a
    record: a missing or malformed ``tool`` or ``played_at``, or an optional member that is anything but its kind,
    None or absent, is no mark.
    """
    if not isinstance(element, Mapping) or element.get("type") != "event":
        return None
    m = element.get(RECORD_FIELD)
    if not isinstance(m, Mapping):
        return None
    tool, played_at = m.get("tool"), m.get("played_at")
    if not isinstance(tool, str) or not _TOOL.fullmatch(tool):
        return None
    if not isinstance(played_at, str) or _instant_ms(played_at) is None:
        return None
    version, seed, outcome, seats = m.get("version"), m.get("seed"), m.get("outcome"), m.get("seats")
    if not _unset_or(version, isinstance(version, str)):
        return None
    if not _unset_or(seed, isinstance(seed, str)):
        return None
    if not _unset_or(outcome, isinstance(outcome, str) and bool(_OUTCOME.fullmatch(outcome))):
        return None
    if not _unset_or(
        seats, isinstance(seats, Mapping) and all(isinstance(k, str) and isinstance(v, str) for k, v in seats.items())
    ):
        return None
    return {
        "tool": tool,
        "played_at": played_at,
        "version": version,
        "seed": seed,
        "outcome": outcome,
        "seats": dict(seats) if seats else {},
    }


def _instant_ms(played_at: str) -> int | None:
    """The instant in whole milliseconds, or None when the value cannot be read as a time.

    Read by the message page's grammar (serial 123), the one the message readers use (``message._instant``):
    ``YYYY-MM-DDTHH:MM:SS``, an optional fraction, then ``Z``, ``+HH:MM`` / ``-HH:MM`` or nothing (read as UTC);
    ``T`` and ``Z`` in either case; ASCII digits; a real calendar instant; seconds required. The order is to the
    millisecond, a fraction truncated past three digits, as the record page reads it."""
    unreadable, seconds, micros = _instant(played_at)
    if unreadable:
        return None
    return seconds * 1000 + micros // 1000


def records_of(character_id: str, elements: Sequence[Any]) -> list[Record]:
    """A Character's records in a world, newest first.

    Every Event with the record mark whose ``characters`` names them, ordered by ``played_at`` as an instant (ties by
    the Event's id in code point order), each with the stories that are theirs. An id no record names, or one in no
    element, reads an empty list. ``elements`` is the world as this reader is served it.
    """
    if not isinstance(character_id, str):
        raise TypeError("records_of: character_id must be a string")
    if isinstance(elements, (str, bytes)) or not isinstance(elements, Sequence):
        raise TypeError("records_of: elements must be a list")
    # This Character's stories, by each Event they name (once per Narrative, however often it names it): one pass over
    # the world, then a lookup per record, where each record rescanned the whole world through 0.100.0. An id that is
    # not hashable names no story, as the npm reader's includes() matches no object. An Event or a Narrative whose id
    # is not a string is never read (serial 103): no entry without an id, and no error sorting one.
    stories_of: dict[Any, list[RecordStory]] = {}
    for n in elements:
        if not isinstance(n, Mapping) or n.get("type") != "narrative" or not isinstance(n.get("id"), str):
            continue
        if _proposed(n):  # the review profile's reading: an empty mark is settled
            continue
        events = n.get("events")
        if not isinstance(events, list):
            continue
        p = n.get("protagonist") == character_id
        r = n.get("narrator") == character_id
        if not p and not r:
            continue
        name = n.get("name")
        role: Literal["both", "protagonist", "narrator"] = "both" if p and r else "protagonist" if p else "narrator"
        story: RecordStory = {"id": n["id"], "name": name if isinstance(name, str) else "", "as": role}
        for e in {e for e in events if _hashable(e)}:
            stories_of.setdefault(e, []).append(story)
    out: list[Record] = []
    for ev in elements:
        mark = record_mark_of(ev)
        if mark is None or not isinstance(ev.get("id"), str) or _proposed(ev):
            continue
        characters = ev.get("characters")
        if not isinstance(characters, list) or character_id not in characters:
            continue
        found = stories_of.get(ev["id"], [])
        stories: list[RecordStory] = [s.copy() for s in found]
        stories.sort(key=lambda s: s["id"])
        ev_name = ev.get("name")
        seat = mark["seats"].get(character_id)
        out.append(
            {
                "event": {"id": ev["id"], "name": ev_name if isinstance(ev_name, str) else ""},
                "tool": mark["tool"],
                "played_at": mark["played_at"],
                "version": mark["version"],
                "seed": mark["seed"],
                "outcome": mark["outcome"],
                "seat": seat if isinstance(seat, str) else None,
                "stories": stories,
            }
        )
    out.sort(key=lambda r: r["event"]["id"])
    out.sort(key=lambda r: _instant_ms(r["played_at"]) or 0, reverse=True)
    return out

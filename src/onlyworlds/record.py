"""The record profile (schema-dist ``profiles/record.md``, serial 102): a game's run kept in the world its Characters
live in.

The run is an Event carrying the mark ``x_record`` (``tool`` and ``played_at`` required; ``version``, ``seed``,
``outcome`` and ``seats`` optional), the game's own tally beside it under its own prefix. Who took part is the Event's
``characters`` alone; a Narrative that lists the Event in ``events`` and names a Character as ``protagonist`` or
``narrator`` is that Character's story of it. A run or a story still proposed (the review profile's
``x_review_proposed``, any value but null) is not read until a keeper settles it. ``records_of(character_id,
elements)`` reads the elements as the reader is served them. Pure: nothing is stored or written. The fixture
(``codegen/schema-dist/profiles/record.fixture.json``) is replayed whole by ``tests/test_record.py``; the npm SDK's
``recordsOf`` gives the same answers on the same input.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any, Literal, TypedDict

#: The Event's field that carries the record's mark.
RECORD_FIELD = "x_record"

_TOOL = re.compile(r"[a-z0-9-]{1,32}")
_PLAYED_AT = re.compile(r"(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2})(?:\.(\d+))?)?Z")
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
    return element.get("x_review_proposed") is not None


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
    """The instant in whole milliseconds, or None when the value is not a real calendar instant in the profile's form
    (month 1 to 12, the day within its month, hour 0 to 23, minute and second 0 to 59). A fraction is truncated past
    three digits, as JavaScript's Date.parse reads it, so the two packages order the same records the same way."""
    m = _PLAYED_AT.fullmatch(played_at)
    if m is None:
        return None
    y, mo, d, h, mi = (int(m.group(i)) for i in range(1, 6))
    try:
        at = datetime(y, mo, d, h, mi, int(m.group(6) or 0), tzinfo=UTC)
    except ValueError:
        return None
    return int(at.timestamp()) * 1000 + int((m.group(7) or "")[:3].ljust(3, "0"))


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
    out: list[Record] = []
    for ev in elements:
        mark = record_mark_of(ev)
        if mark is None or _proposed(ev):
            continue
        characters = ev.get("characters")
        if not isinstance(characters, list) or character_id not in characters:
            continue
        stories: list[RecordStory] = []
        for n in elements:
            if not isinstance(n, Mapping) or n.get("type") != "narrative" or _proposed(n):
                continue
            events = n.get("events")
            if not isinstance(events, list) or ev["id"] not in events:
                continue
            p = n.get("protagonist") == character_id
            r = n.get("narrator") == character_id
            if not p and not r:
                continue
            name = n.get("name")
            role: Literal["both", "protagonist", "narrator"] = "both" if p and r else "protagonist" if p else "narrator"
            stories.append({"id": n["id"], "name": name if isinstance(name, str) else "", "as": role})
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

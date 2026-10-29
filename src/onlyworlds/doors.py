"""The door history of an element: which tools wrote it, newest first, each with the time of its last write there.

The API serves every element a ``doors`` field (to a world's members only): one key per tool that wrote it, the name
the tool sent in ``X-OW-Client`` or else the door word of that write (``site``, ``api``, ``mcp``, ...), each value the
``updated_at`` that write left. Pure: a UI's "Last shaped in Atlas" line reads the first entry, a trail reads them all,
``door_where`` gives an entry's "in Atlas", and the npm SDK's ``doorsOf`` and ``doorWhere`` answer the shared fixture,
``tests/fixtures/doors.fixture.json``, the same way.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from functools import cmp_to_key
from typing import Any, Literal, NamedTuple, NoReturn, TypedDict

from ._tools import TOOLS
from .openers import Tool

__all__ = ["Door", "DoorTool", "door_where", "doors_of"]


class DoorTool(TypedDict):
    """The tools list's row whose ``client`` is the door, as its ``id`` and ``name``."""

    id: str
    name: str


Door = TypedDict(
    "Door",
    {"door": str, "at": str, "tool": DoorTool | None, "last": bool, "from": Literal["doors", "last-write"]},
)
Door.__doc__ = """One tool that wrote an element, as ``doors_of`` reads it. ``door`` is the key: the tool's client name
(``X-OW-Client``), or the door word of a write that named no client (``site``, ``api``, ``mcp``, ``seat``,
``declared``, ``v1``, ``sync``, ``server``). ``at`` is the time of this door's last write, exactly as served (ISO 8601
with an offset). ``tool`` is the tools list's row whose ``client`` is ``door``, None for a door word or a client the
list does not hold. ``last`` is True on the one entry whose ``at`` is the element's ``updated_at``: the door of its
last write. ``from`` is ``doors`` when the entry comes from the ``doors`` field, ``last-write`` when it is read from
``changed_client`` or ``changed_via`` and ``updated_at``, for an element without ``doors``."""


class _Instant(NamedTuple):
    """Whole seconds since 1970-01-01T00:00:00Z, and the fraction's digits with trailing zeros cut."""

    seconds: int
    fraction: str


_TIME = re.compile(
    r"([0-9]{4})-([0-9]{2})-([0-9]{2})T([0-9]{2}):([0-9]{2}):([0-9]{2})(?:\.([0-9]+))?(Z|([+-])([0-9]{2}):([0-9]{2}))"
)
_MONTH_DAYS = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)


def _fail(what: str) -> NoReturn:
    raise TypeError(f"doors_of: {what}")


def _days_from_civil(year: int, month: int, day: int) -> int:
    """Days from 1970-01-01 to a date of the proleptic Gregorian calendar."""
    y = year - 1 if month <= 2 else year
    era = y // 400
    yoe = y - era * 400
    doy = (153 * (month - 3 if month > 2 else month + 9) + 2) // 5 + day - 1
    doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
    return era * 146097 + doe - 719468


def _instant_of(value: object) -> _Instant | None:
    """The instant a time names, or None when it is not one: ``YYYY-MM-DDTHH:MM:SS``, an optional fraction, then ``Z``
    or ``+HH:MM``/``-HH:MM``."""
    if not isinstance(value, str):
        return None
    m = _TIME.fullmatch(value)
    if m is None:
        return None
    year, month, day, hour, minute, second = (int(g) for g in m.groups()[:6])
    if not 1 <= month <= 12:
        return None
    leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
    if not 1 <= day <= (29 if month == 2 and leap else _MONTH_DAYS[month - 1]):
        return None
    if hour > 23 or minute > 59 or second > 59:
        return None
    offset = 0
    if m.group(8) != "Z":
        oh, om = int(m.group(10)), int(m.group(11))
        if oh > 23 or om > 59:
            return None
        offset = (-1 if m.group(9) == "-" else 1) * (oh * 3600 + om * 60)
    seconds = _days_from_civil(year, month, day) * 86400 + hour * 3600 + minute * 60 + second - offset
    return _Instant(seconds, (m.group(7) or "").rstrip("0"))


def _compare_instants(a: _Instant, b: _Instant) -> int:
    """Negative when ``a`` is earlier, positive when later, 0 for the same instant, at the fraction's full precision."""
    if a.seconds != b.seconds:
        return -1 if a.seconds < b.seconds else 1
    width = max(len(a.fraction), len(b.fraction))
    fa, fb = a.fraction.ljust(width, "0"), b.fraction.ljust(width, "0")
    return 0 if fa == fb else -1 if fa < fb else 1


def _non_empty(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def doors_of(element: Mapping[str, Any], tools: Sequence[Tool] = TOOLS) -> list[Door]:
    """Which tools wrote ``element``, newest first: one entry per key of its ``doors`` field, each a ``Door``.

    Returns data only, no words or formatted dates; a UI's "Last shaped in Atlas" line reads the first entry, a trail
    reads them all.

    - From ``doors``: every key that is a non-empty string, with a value that is a time, is an entry (``from``
      ``doors``, ``at`` the value as served). An entry that is not one is skipped, never raised on.
    - Order: newest first, times compared as instants at their full precision (an offset and the microseconds count;
      never as strings). Entries at the same instant go by key, by Unicode code point.
    - Without ``doors``, or with no valid entry in it: one entry from the last write, its door ``changed_client`` if
      that is a non-empty string, else ``changed_via``; ``at`` is ``updated_at``, ``from`` is ``last-write``. With
      neither door, or no valid ``updated_at``, the result is empty: a public reader, served none of these fields,
      gets ``[]``.
    - ``tool``: the first row of ``tools`` whose ``client`` is the door, as ``{id, name}``; else None.
    - ``last``: True on the first entry whose ``at`` is the same instant as ``updated_at``, False on the rest. When no
      entry is ``last``, the last write came through no door the field records: the server moves ``updated_at`` on a
      restore or a scrub, which no door writes. Without a valid ``updated_at``, no entry is ``last``.

    A time is ``YYYY-MM-DDTHH:MM:SS``, an optional ``.`` and fraction digits, then ``Z`` or ``+HH:MM``/``-HH:MM``,
    with a real calendar date and clock; anything else is not one (never ``datetime.fromisoformat``, whose accepted
    set differs across Python versions). Who wrote it is the caller's: compare ``changed_by`` with the reader's
    membership for "by you" on the ``last`` entry.

    Raises ``TypeError`` when ``element`` is not a mapping (None, a list, a string) or ``tools`` is not a sequence;
    nothing else raises. ``tools`` defaults to ``TOOLS``, the tools list baked into this release. The npm SDK's
    ``doorsOf`` gives the same entries.
    """
    if not isinstance(element, Mapping):
        _fail("the element is a mapping, as the API serves it")
    if isinstance(tools, str | bytes) or not isinstance(tools, Sequence):
        _fail("tools is the tools list's rows, a sequence")

    def tool_of(door: str) -> DoorTool | None:
        for r in tools:
            if isinstance(r, Mapping) and r.get("client") == door:
                return {"id": r.get("id"), "name": r.get("name")}
        return None

    found: list[tuple[str, str, _Instant]] = []
    doors = element.get("doors")
    if isinstance(doors, Mapping):
        for door, at in doors.items():
            instant = _instant_of(at)
            if isinstance(door, str) and door and instant is not None:
                found.append((door, at, instant))
    updated = _instant_of(element.get("updated_at"))
    if not found:
        last_door = _non_empty(element.get("changed_client")) or _non_empty(element.get("changed_via"))
        if last_door is None or updated is None:
            return []
        at_last: str = element["updated_at"]
        return [{"door": last_door, "at": at_last, "tool": tool_of(last_door), "last": True, "from": "last-write"}]

    def order(a: tuple[str, str, _Instant], b: tuple[str, str, _Instant]) -> int:
        by_time = _compare_instants(b[2], a[2])
        return by_time or ((a[0] > b[0]) - (a[0] < b[0]))

    found.sort(key=cmp_to_key(order))
    entries: list[Door] = []
    last_seen = False
    for door, at, instant in found:
        last = not last_seen and updated is not None and _compare_instants(instant, updated) == 0
        last_seen = last_seen or last
        entries.append({"door": door, "at": at, "tool": tool_of(door), "last": last, "from": "doors"})
    return entries


# The doors that mean agent-made: an agent seat, the MCP server, or a client that declared itself (the npm SDK's
# AGENT_DOORS and isAgentDoor).
_AGENT_DOORS = frozenset({"seat", "mcp", "declared"})


def door_where(door: Door) -> str:
    """Where an entry of ``doors_of`` wrote the element, as the words a UI shows after "Last shaped": the where-phrase
    only.

    - A listed tool (``tool`` not None): ``in <tool name>``, such as ``in Atlas``. This comes first, so a door word the
      case's tools list holds as a client reads as that tool.
    - ``site``: ``on onlyworlds.com``.
    - An agent's door (``seat``, ``mcp``, ``declared``): ``with an AI``.
    - ``server``: ``by OnlyWorlds``.
    - Anything else (``sync``, ``api``, ``v1``, a client the tools list does not hold, such as ``sdk``): ``in code``.

    Nothing about the reader or the time: "by you" and when are the caller's. Raises ``TypeError`` when ``door`` is
    not a mapping, its ``door`` is not a string, or its ``tool`` is neither None nor a mapping with a string ``name``.
    The npm SDK's ``doorWhere`` gives the same words on the shared fixture.
    """
    if not isinstance(door, Mapping):
        raise TypeError("door_where: the door is an entry of doors_of, a mapping")
    word = door.get("door")
    if not isinstance(word, str):
        raise TypeError("door_where: the entry's door is a string")
    tool = door.get("tool")
    if tool is not None:
        name = tool.get("name") if isinstance(tool, Mapping) else None
        if not isinstance(name, str):
            raise TypeError("door_where: the entry's tool is None or {id, name}")
        return f"in {name}"
    if word == "site":
        return "on onlyworlds.com"
    if word in _AGENT_DOORS:
        return "with an AI"
    if word == "server":
        return "by OnlyWorlds"
    return "in code"

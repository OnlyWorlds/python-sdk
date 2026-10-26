"""A draught as plain text: one Character's context packet (``GET /character/{id}/context``, as
``Client.draught`` returns it, full or compact) as the text a person or an AI pastes.

``draught_text(draught)`` gives the same text as the npm SDK's ``draughtText``, byte for byte; the shared
fixture is ``tests/fixtures/draught-text/``, vendored from the SDK with its sha256 manifest. It reads only
what the packet carries and calls nothing. A link to an element the packet does not hold is counted,
never looked up. Nothing is trimmed or cut, so the two languages cannot disagree on where a string ends:
strings print exactly as served, with their line breaks read as LF.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from ._schema import FIELD_KINDS

__all__ = ["draught_text"]

# The sections after her own, in the packet's order, with their headings.
_SECTIONS: tuple[tuple[str, str], ...] = (
    ("role", "Role"),
    ("work", "Work"),
    ("style", "Style"),
    ("events", "Events"),
    ("knowledge", "Knowledge"),
    ("names", "Names"),
    ("sheet", "Sheet"),
    ("recent", "Recent"),
    ("messages", "Messages"),
    ("room", "Room"),
    ("proposed", "Proposed"),
    ("roster", "Members"),
)

# The sections whose rows carry an element.
_ELEMENT_SECTIONS: tuple[str, ...] = (
    "role",
    "work",
    "style",
    "events",
    "knowledge",
    "names",
    "sheet",
    "messages",
    "room",
    "proposed",
)

# Her own fields that never print as a field line.
_UNPRINTED: frozenset[str] = frozenset(
    (
        "id",
        "type",
        "name",
        "description",
        "supertype",
        "subtype",
        "hidden",
        "known_of",
        "x_review_proposed",
        "image_url",
        "created_at",
        "updated_at",
        "change_seq",
        "created_by",
        "changed_by",
        "changed_via",
        "changed_client",
        "world",
    )
)
_UNPRINTED_PREFIXES: tuple[str, ...] = ("x_", "atlas_", "shadow_")
_LINK_KINDS: frozenset[str] = frozenset(("single_link", "multi_link"))


def _int(v: Any) -> int | None:
    """A number as an integer: an int (never a bool), or a finite float with an integral value (``249.0`` reads
    as 249, as JavaScript reads it); anything else None."""
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, float) and math.isfinite(v) and v.is_integer():
        return int(v)
    return None


def _is_set(v: Any) -> bool:
    """Set: not None or absent, not "", not [] and not {}."""
    if v is None or (isinstance(v, str) and v == ""):
        return False
    if isinstance(v, (list, Mapping)):
        return len(v) > 0
    return True


def _text(v: Any) -> str | None:
    """A value as it prints: a string that is not "" with CRLF, then a lone CR, read as LF; an integer in
    plain decimal (an integral float as its integer); anything else None."""
    if isinstance(v, str):
        return None if v == "" else _lines(v)
    n = _int(v)
    return None if n is None else str(n)


def _lines(s: str) -> str:
    """CRLF, then a lone CR, read as LF."""
    return s.replace("\r\n", "\n").replace("\r", "\n")


def _type_word(t: Any) -> str:
    """A type's word: its id with the first letter upper-cased."""
    s = t if isinstance(t, str) else ""
    return s[:1].upper() + s[1:]


def _fields_of(t: Any) -> Mapping[str, str]:
    """The schema's fields for a type, or none for a type it does not know."""
    return FIELD_KINDS.get(t, {}) if isinstance(t, str) else {}


def _kind_of(el: Mapping[str, Any]) -> str | None:
    """``supertype / subtype`` when both are set, otherwise whichever is set, otherwise None."""
    sup, sub = _text(el.get("supertype")), _text(el.get("subtype"))
    if sup is not None and sub is not None:
        return f"{sup} / {sub}"
    return sup if sup is not None else sub


def _marks(el: Mapping[str, Any]) -> str:
    """`` · hidden`` when ``hidden`` is true, `` · proposed`` when ``x_review_proposed`` is present and not None (as the
    server counts it)."""
    return (" · hidden" if el.get("hidden") is True else "") + (
        " · proposed" if el.get("x_review_proposed") is not None else ""
    )


def _description_lines(el: Mapping[str, Any]) -> list[str]:
    """The description's lines, each indented by two spaces; none when it is not set."""
    d = _text(el.get("description"))
    return [] if d is None else ["  " + line for line in d.split("\n")]


def _rows_of(key: str, v: Any) -> list[Any]:
    """The rows of a section, as the packet holds them: ``style`` is one row, ``names`` a mapping of type to rows."""
    if key == "style":
        return [v]
    if key == "names":
        if not isinstance(v, Mapping):
            return []
        return [row for rows in v.values() if isinstance(rows, list) for row in rows]
    return list(v) if isinstance(v, list) else []


def draught_text(draught: Mapping[str, Any]) -> str:
    """The draught as plain text: a ``#`` title, ``##`` sections and ``- `` rows, LF line endings and one
    newline at the end. The same read gives the same text served full or ``compact``.

    The frame says what the packet does: the horizon (``as_of``), the world's now, and whose view it was
    read through (``mode``). Her own element prints whole; every other row prints its name, type and kind,
    how it reached her (``via``), its grade or date, the marks ``hidden`` and ``proposed``, and its
    description. The sections that hold nothing are named on one line; what the date horizon left out
    is named (never counted: the packet carries no count), and what the budget left out (``cut``) is
    always said.

    A draught that is not a mapping, or has no ``world`` mapping, is a TypeError. Takes no options.
    """
    d: Any = draught
    if not isinstance(d, Mapping):
        raise TypeError("draught_text: the draught is a mapping, as Client.draught returns it.")
    world = d.get("world")
    if not isinstance(world, Mapping):
        raise TypeError("draught_text: the draught has no world mapping.")

    # Names: her element first, then each row's element, in the sections' order; the first holder of an id names it.
    names: dict[str, str] = {}

    def hold(el: Any) -> None:
        if not isinstance(el, Mapping):
            return
        el_id = el.get("id")
        if isinstance(el_id, str) and el_id not in names:
            name = _text(el.get("name"))
            names[el_id] = "(unnamed)" if name is None else name

    # An absent ``character`` is not a hidden one: absent, ``self`` was not asked and there is no block of her own.
    asked = "character" in d
    character = d.get("character")
    her: Mapping[str, Any] | None = None
    if isinstance(character, Mapping) and isinstance(character.get("element"), Mapping):
        her = character["element"]
    hold(her)
    for key in _ELEMENT_SECTIONS:
        for row in _rows_of(key, d.get(key)):
            if isinstance(row, Mapping):
                hold(row.get("element"))

    calendar = d.get("calendar")
    unit = _text(calendar.get("time_basic_unit")) if isinstance(calendar, Mapping) else None

    def moment(n: int) -> str:
        return str(n) if unit is None else f"{unit} {n}"

    if her is None:
        her_name = "the Character"
    else:
        named = _text(her.get("name"))
        her_name = "(unnamed)" if named is None else named
    world_name = _text(world.get("name"))
    out: list[str] = []

    def put(line: str, cont: str = "  ") -> None:
        """One line of the text. A line break a value brought in starts a continuation line indented by ``cont``;
        an empty one is the indent alone."""
        first, *rest = _lines(line).split("\n")
        out.append(first)
        out.extend(cont + part for part in rest)

    put(f"# {her_name}, in {'(unnamed)' if world_name is None else world_name}")

    as_of, now, mode = _int(d.get("as_of")), _int(d.get("now")), d.get("mode")
    frame = f"What the record holds around {her_name}"
    if as_of is not None:
        frame += f", dated up to {moment(as_of)}"
    if now is not None:
        frame += f" (the world's now: {moment(now)})"
    frame += "."
    if mode == "voice":
        frame += " Read as the Character's own view."
    elif mode == "act":
        frame += " Read as the caller's view."
    put(frame)

    # Her block, when ``self`` was asked.
    if asked:
        out.append("")
        put(f"## {her_name}")
    if asked and her is None:
        out.append("Hidden from this reader.")
    elif her is not None:
        her_type = her.get("type")
        kind = _kind_of(her)
        put(_type_word(her_type) + ("" if kind is None else f" · {kind}") + _marks(her))
        for line in _description_lines(her):
            put(line)
        fields = _fields_of(her_type)
        for key, v in her.items():
            if key in _UNPRINTED or key.startswith(_UNPRINTED_PREFIXES) or not _is_set(v):
                continue
            value: str | None
            if fields.get(key) in _LINK_KINDS:
                resolved: list[str] = []
                missing = 0
                for link in v if isinstance(v, list) else [v]:
                    if not isinstance(link, str) or link == "":
                        continue
                    if link in names:
                        resolved.append(names[link])
                    else:
                        missing += 1
                not_held = f"{missing} not in this draught"
                if missing == 0:
                    value = ", ".join(resolved) if resolved else None
                else:
                    value = f"{', '.join(resolved)}, and {not_held}" if resolved else not_held
            elif isinstance(v, list):
                parts = [p for p in map(_text, v) if p is not None]
                value = ", ".join(parts) if parts else None
            else:
                value = _text(v)
            if value is not None:
                put(f"  {key.replace('_', ' ')}: {value}", "    ")

    # The roster's names by membership id, for ``recent``'s writers.
    roster = d.get("roster")

    def member_name(member: Any) -> str | None:
        if not isinstance(roster, list):
            return None
        for r in roster:
            if isinstance(r, Mapping) and isinstance(member, str) and r.get("id") == member:
                return _text(r.get("name"))
        return None

    def element_row(row: Mapping[str, Any]) -> list[str]:
        raw = row.get("element")
        el: Mapping[str, Any] = raw if isinstance(raw, Mapping) else {}
        el_type = el.get("type")
        kind = _kind_of(el)
        name = _text(el.get("name"))
        line = f"- {'(unnamed)' if name is None else name} ({_type_word(el_type)}"
        line += ("" if kind is None else f" · {kind}") + ")"
        via_raw = row.get("via")
        via = [f for f in map(_text, via_raw if isinstance(via_raw, list) else []) if f is not None]
        if via:
            line += " · via " + ", ".join(f.replace("_", " ") for f in via)
        start = _int(el.get("start_date"))
        if row.get("grade") == "known_of":
            line += " · known of"
        elif start is not None:
            line += f" · {moment(start)}"
        elif "start_date" in _fields_of(el_type):
            line += " · undated"
        line += _marks(el)
        return [line, *_description_lines(el)]

    def recent_row(row: Mapping[str, Any]) -> str:
        op = row.get("op")
        if op == "upsert":
            verb = "changed"
        elif op == "delete":
            verb = "deleted"
        else:
            verb = _text(op) or ""
        row_id = row.get("id")
        target = names.get(row_id) if isinstance(row_id, str) else None
        if target is None:
            target = _text(row_id) or ""
        who = row.get("who")
        if not _is_set(who):
            writer = "an unrecorded writer"
        elif who == "owner":
            writer = "the owner"
        else:
            writer = member_name(who) or "a member"
        when, door = _text(row.get("when")), _text(row.get("door"))
        line = f"- {'' if when is None else when + ' · '}{verb} {_type_word(row.get('type'))} {target} · by {writer}"
        return line + ("" if door is None else f" · through {door}")

    def member_row(row: Mapping[str, Any]) -> str:
        line = f"- {_text(row.get('role')) or ''}"
        name = _text(row.get("name"))
        if name is not None:
            line += f" · {name}"
        plays = row.get("character")
        if _is_set(plays):
            held = names.get(plays) if isinstance(plays, str) else None
            line += " · plays a Character not in this draught" if held is None else f" · plays {held}"
        if row.get("status") == "removed":
            line += " · removed from the world"
        return line

    # ``recent_more`` true makes Recent a section even with no rows.
    recent_more = d.get("recent_more") is True

    def section_set(key: str) -> bool:
        return _is_set(d.get(key)) or (key == "recent" and recent_more)

    for key, heading in _SECTIONS:
        v = d.get(key)
        if not section_set(key):
            continue
        out.append("")
        put(f"## {heading}")
        for row in _rows_of(key, v):
            if not isinstance(row, Mapping):
                continue
            if key == "recent":
                put(recent_row(row))
            elif key == "roster":
                put(member_row(row))
            else:
                for line in element_row(row):
                    put(line)
        if key == "recent" and recent_more:
            out.append("More changes than these; read on from recent_cursor.")

    # Nothing in: the components read whose sections hold nothing, as keel spells them.
    policy = d.get("policy")
    components = policy.get("components") if isinstance(policy, Mapping) else None
    if isinstance(components, list):
        empty = [c for c in components if isinstance(c, str) and c != "self" and not section_set(c)]
        if empty:
            out.append("")
            put(f"Nothing in: {', '.join(empty)}.")

    # Left out: what the horizon fenced, by mode (keel's ``_past_horizon``; uncounted), then what the budget dropped.
    cut = d.get("cut")
    counts = [(k, _int(n)) for k, n in cut.items()] if isinstance(cut, Mapping) else []
    left = [f"{n} {k}" for k, n in counts if n is not None]
    out.append("")
    if as_of is not None and mode == "voice":
        put(f"Not listed: rows dated after {moment(as_of)}.")
    elif as_of is not None and mode == "act":
        put(f"Not listed: Events, Knowledge and proposed Events or Narratives dated after {moment(as_of)}.")
    put(f"Left out by the budget: {', '.join(left) if left else 'nothing'}.")

    return "\n".join(out) + "\n"

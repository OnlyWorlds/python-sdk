"""The room profile (schema-dist ``profiles/room.md``, serial 45; the mark by presence, serial 83): which elements a
parlor puts in a world.

A parlor's lines, board entries, work items, specs, hearts, votes, sittings and member cards live in
the world as ordinary elements, told apart by type and supertype and marked with ``x_room_of`` (the id
of the world or sitting the room belongs to). ``ROOM_PAIRS`` (generated from the pinned dist) lists the
pairs; ``is_room_element`` reads the pair and the mark together. A lore view (a list, a count, search,
a graph, a link picker, a story's context, a survey) leaves room elements out unless the person asks;
the room's own views show them whole. A writer writes them like any element, the mark kept byte for
byte: the rule is the reader's. A convention on the 22 types, never a change to the standard. The npm
SDK's ``isRoomElement`` is the same matcher, with the same fold. ``talks_of`` (serial 135) reads the talks on an
Object or a Construct that a line in the room is in.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal, TypedDict, cast

from ._schema import READING_AID_MARK, READING_AID_PAIRS, ROOM_MARK, ROOM_PAIRS
from .folder import FolderElement
from .worldfile import simple_case_fold

__all__ = ["ROOM_PAIRS", "Talk", "is_charter_element", "is_room_element", "reading_aid_of", "talks_of"]

#: The three reading aids, as the charter profile names them (``profiles/charter.fixture.json``'s ``aid``).
ReadingAid = Literal["charter", "guide", "domain"]


class Talk(TypedDict):
    """A talk on an element (the room profile, serial 135): ``object`` for an id a line or a report names in its
    ``objects``, ``construct`` for one in its ``constructs``; the id as written."""

    type: Literal["object", "construct"]
    id: str


_WHITE_SPACE: str = "".join(
    map(
        chr,
        (
            *range(0x0009, 0x000E),
            0x0020,
            0x0085,
            0x00A0,
            0x1680,
            *range(0x2000, 0x200B),
            0x2028,
            0x2029,
            0x202F,
            0x205F,
            0x3000,
        ),
    )
)
"""The 25 code points of Unicode's White_Space property (PropList.txt): U+0009 to U+000D, U+0020, U+0085,
U+00A0, U+1680, U+2000 to U+200A, U+2028, U+2029, U+202F, U+205F, U+3000.

The profiles' "trimmed" (schema-dist ``profiles/room.md``, dist.47, "Trimmed and without regard to case,
defined once") is leading and trailing whitespace removed, nothing inside touched, and whitespace is
White_Space exactly (ruled 2026-10-22): a byte order mark (U+FEFF) and a zero width
space (U+200B) stay. Bare ``str.strip()`` is not used: it strips by ``str.isspace()``, which also takes
U+001C to U+001F. The npm SDK's ``isRoomElement`` trims by the same 25."""


def _fold(text: str) -> str:
    return simple_case_fold(text.strip(_WHITE_SPACE))


def _has_mark(value: Any) -> bool:
    """The room and charter profiles' presence rule for a mark (``x_room_of``, ``x_charter_of``): any value but
    ``None``; a string only when something is left after trimming White_Space; an empty list or an empty object is
    absent too (serial 126). Never compared to anything."""
    if value is None or (isinstance(value, (list, Mapping)) and not value):
        return False
    return not (isinstance(value, str) and value.strip(_WHITE_SPACE) == "")


def is_room_element(element: Mapping[str, Any] | FolderElement) -> bool:
    """True when the element's type and supertype, each trimmed (Unicode White_Space at both ends, so a
    leading byte order mark is no match) and compared without regard to case (Unicode simple case
    folding, the ``.owworld`` reader's table), match one of ``ROOM_PAIRS``, AND it
    carries the mark ``x_room_of``, read by presence (serial 83): any value but ``None``, a string only when
    something is left after trimming it, an empty list or mapping never (serial 126), and the value is never
    compared (a number counts, ``"  "`` does not).

    Both, always: a pair without the mark is lore (a novel's letters are Narratives with supertype
    Message), and a mark without a pair is not a room element (a malformed mark: report it, never hide
    it). The pair match is the whole word: a Narrative with supertype ``Messages`` is lore. The charter
    (``law`` / ``Charter``) is never a room element: with its own mark it is a reading aid
    (``is_charter_element``), without it lore. A missing, ``None`` or empty supertype is never a room element.
    Takes a body (an API element or a folder file's dict) or a ``FolderElement``, whose type may come from
    its directory when the body has none.
    """
    body: Mapping[str, Any]
    kind: Any
    if isinstance(element, FolderElement):
        body, kind = element.body, element.type
    elif isinstance(element, Mapping):
        body, kind = element, element.get("type")
    else:
        return False  # no object, no element: False, never an error
    supertype, mark = body.get("supertype"), body.get(ROOM_MARK)
    if not isinstance(kind, str) or not isinstance(supertype, str):
        return False
    if not _has_mark(mark):
        return False
    key = (_fold(kind), _fold(supertype))
    return any((_fold(t), _fold(s)) == key for t, s in ROOM_PAIRS)


def _body_and_kind(element: Any) -> tuple[Mapping[str, Any], Any] | None:
    if isinstance(element, FolderElement):
        return element.body, element.type
    if isinstance(element, Mapping):
        return element, element.get("type")
    return None


def _is_pair(element: Any, pair: tuple[str, str]) -> bool:
    """The element's type and supertype, each trimmed and folded as ``is_room_element`` reads them, are ``pair``."""
    found = _body_and_kind(element)
    if found is None:
        return False
    body, kind = found
    supertype = body.get("supertype")
    if not isinstance(kind, str) or not isinstance(supertype, str):
        return False
    return (_fold(kind), _fold(supertype)) == (_fold(pair[0]), _fold(pair[1]))


_TALK_FIELDS: tuple[tuple[str, Literal["object", "construct"]], ...] = (
    ("objects", "object"),
    ("constructs", "construct"),
)
"""The only two fields that make a talk on an element, in the order their talks are answered."""


def _named_talks(body: Mapping[str, Any]) -> list[Talk]:
    """The talks a line or a report names (the room profile, serial 135): each id in ``objects`` an Object's, each
    in ``constructs`` a Construct's. An entry that is not a string, or is empty once trimmed of White_Space, names
    nothing, and a field that is not a list names nothing; every other entry is the id as written, untrimmed and
    with its case. Each ``{type, id}`` once, in its first place, the objects before the constructs."""
    out: list[Talk] = []
    seen: set[tuple[str, str]] = set()
    for field, kind in _TALK_FIELDS:
        value = body.get(field)
        if not isinstance(value, list):
            continue
        for entry in value:
            if not isinstance(entry, str) or entry.strip(_WHITE_SPACE) == "":
                continue
            if (kind, entry) not in seen:
                seen.add((kind, entry))
                out.append({"type": kind, "id": entry})
    return out


_LINE_PAIR: tuple[str, str] = next(p for p in ROOM_PAIRS if (_fold(p[0]), _fold(p[1])) == ("narrative", "message"))
"""A line in the room: the room profile's pair ``narrative`` + ``Message``, with the mark."""


def talks_of(element: Mapping[str, Any] | FolderElement) -> list[Talk]:
    """The talks on an element that ``element`` is in as a line (schema-dist ``profiles/room.md``, serial 135).

    Only a line in the room is in a talk: the pair ``narrative`` + ``Message`` and the mark ``x_room_of``, read as
    ``is_room_element`` reads them. Each id in its ``objects`` is ``{"type": "object", "id": id}``, each in its
    ``constructs`` ``{"type": "construct", "id": id}``. An entry that is not a string, or is empty once trimmed of
    White_Space, names nothing, and a field that is not a list names nothing; every other entry is the id as written,
    a space left on it and its case included (the address profile's "The same id"), so ``ABC`` and ``abc`` are two
    talks. Each ``{type, id}`` comes once, in its first place, the objects before the constructs. A line's
    ``characters`` are its recipients and make no talk, and no other field does. Any other element (a Message
    without the mark, a board entry, a report, lore, anything that is no element) answers ``[]``. Takes a body or a
    ``FolderElement``. The npm SDK's ``talksOf`` is the same reader."""
    if not is_room_element(element) or not _is_pair(element, _LINE_PAIR):
        return []
    found = _body_and_kind(element)
    assert found is not None
    return _named_talks(found[0])


_READING_AID_KEYS: frozenset[str] = frozenset(f"{_fold(t)}/{_fold(s)}" for t, s in READING_AID_PAIRS)
"""The reading aids' pairs as ``types`` words, folded: ``law/charter``, ``construct/guide``, ``construct/domain``."""


def _reading_aid_key(element: Any) -> str | None:
    """The reading aid's pair word (folded) when the element is one, else ``None`` (the lens and graph readers read
    it). The mark counts when it is present and not ``None``, and a string only when something is left after
    trimming, as the API reads it."""
    body: Any
    kind: Any
    if isinstance(element, FolderElement):
        body, kind = element.body, element.type
    elif isinstance(element, Mapping):
        body, kind = element, element.get("type")
    else:
        return None
    supertype = body.get("supertype")
    if not isinstance(kind, str) or not isinstance(supertype, str):
        return None
    key = f"{_fold(kind)}/{_fold(supertype)}"
    if key not in _READING_AID_KEYS:
        return None
    if not _has_mark(body.get(READING_AID_MARK)):
        return None
    return key


def is_charter_element(element: Mapping[str, Any] | FolderElement) -> bool:
    """True when the element is a reading aid (schema-dist ``profiles/room.md``, ``profiles/lens.md`` rule 4): the
    world's charter (``law``, supertype ``Charter``), its guide (``construct``, supertype ``Guide``) or one of its
    domains (``construct``, supertype ``Domain``), the type and supertype each trimmed and compared without regard
    to case, the whole word, AND the mark ``x_charter_of``, the id of the world the aid belongs to. The mark counts
    when it is present and not ``None``; a string mark counts only when something is left after trimming, and an
    empty list or mapping never. Both,
    always: the pair without the mark is lore, and stays in every view (a kingdom's Charter in a novel's world is a
    Law like any other).

    What it is for: a tool's front door shows the aids first; a lore view (a list, a graph, a story's context)
    leaves them out by default. A reading aid is not a room element: ``is_room_element`` answers ``False`` for one,
    and a public reader sees it. In a lens, one reached by a hop is kept only when ``types`` names its pair
    (``law/charter``, ``construct/guide``, ``construct/domain``); one the lens names as an anchor is kept and
    followed like any anchor. The npm SDK's ``isCharterElement`` is the same matcher, with the same fold."""
    return _reading_aid_key(element) is not None


_AID_BY_KEY: dict[str, ReadingAid] = {
    f"{_fold(t)}/{_fold(s)}": cast(ReadingAid, _fold(s)) for t, s in READING_AID_PAIRS
}
"""The reading aids' pair words to their aid: each aid is its pair's supertype, folded, as the charter fixture's
``pairs`` write it (``law/charter`` to ``charter``)."""


def reading_aid_of(element: Mapping[str, Any] | FolderElement) -> ReadingAid | None:
    """Which reading aid the element's pair makes it (schema-dist ``profiles/charter.md``): ``"charter"`` for a
    ``law`` with supertype ``Charter``, ``"guide"`` for a ``construct`` with supertype ``Guide``, ``"domain"`` for a
    ``construct`` with supertype ``Domain``, the type and supertype each trimmed and compared without regard to
    case, the whole word, as ``is_charter_element`` matches them; ``None`` for any other pair, for an element
    without a string type and supertype, and for anything that is neither a mapping nor a ``FolderElement``.

    It reads the pair only and ignores the mark ``x_charter_of``: an unmarked Charter answers ``"charter"``, which
    is what a tool offering to mark an element needs. Whether the element IS a reading aid (the pair and the mark)
    is ``is_charter_element``. The npm SDK's ``readingAidOf`` is the same reader, with the same fold."""
    body: Any
    kind: Any
    if isinstance(element, FolderElement):
        body, kind = element.body, element.type
    elif isinstance(element, Mapping):
        body, kind = element, element.get("type")
    else:
        return None
    supertype = body.get("supertype")
    if not isinstance(kind, str) or not isinstance(supertype, str):
        return None
    return _AID_BY_KEY.get(f"{_fold(kind)}/{_fold(supertype)}")

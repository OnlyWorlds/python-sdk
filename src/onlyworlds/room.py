"""The room profile (schema-dist ``profiles/room.md``, serial 45): which elements a parlor puts in a world.

A parlor's lines, board entries, work items, specs, hearts, votes, sittings and member cards live in
the world as ordinary elements, told apart by type and supertype and marked with ``x_room_of`` (the id
of the world or sitting the room belongs to). ``ROOM_PAIRS`` (generated from the pinned dist) lists the
pairs; ``is_room_element`` reads the pair and the mark together. A lore view (a list, a count, search,
a graph, a link picker, a story's context, a survey) leaves room elements out unless the person asks;
the room's own views show them whole. A writer writes them like any element, the mark kept byte for
byte: the rule is the reader's. A convention on the 22 types, never a change to the standard. The npm
SDK's ``isRoomElement`` is the same matcher, with the same fold.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ._schema import READING_AID_MARK, READING_AID_PAIRS, ROOM_MARK, ROOM_PAIRS
from .folder import FolderElement
from .worldfile import simple_case_fold

__all__ = ["ROOM_PAIRS", "is_charter_element", "is_room_element"]


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


def is_room_element(element: Mapping[str, Any] | FolderElement) -> bool:
    """True when the element's type and supertype, each trimmed (Unicode White_Space at both ends, so a
    leading byte order mark is no match) and compared without regard to case (Unicode simple case
    folding, the ``.owworld`` reader's table), match one of ``ROOM_PAIRS``, AND it
    carries the mark ``x_room_of`` as a non-empty string.

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
    else:
        body, kind = element, element.get("type")
    supertype, mark = body.get("supertype"), body.get(ROOM_MARK)
    if not isinstance(kind, str) or not isinstance(supertype, str):
        return False
    if not isinstance(mark, str) or mark == "":
        return False
    key = (_fold(kind), _fold(supertype))
    return any((_fold(t), _fold(s)) == key for t, s in ROOM_PAIRS)


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
    mark = body.get(READING_AID_MARK)
    if mark is None or (isinstance(mark, str) and mark.strip(_WHITE_SPACE) == ""):
        return None
    return key


def is_charter_element(element: Mapping[str, Any] | FolderElement) -> bool:
    """True when the element is a reading aid (schema-dist ``profiles/room.md``, ``profiles/lens.md`` rule 4): the
    world's charter (``law``, supertype ``Charter``), its guide (``construct``, supertype ``Guide``) or one of its
    domains (``construct``, supertype ``Domain``), the type and supertype each trimmed and compared without regard
    to case, the whole word, AND the mark ``x_charter_of``, the id of the world the aid belongs to. The mark counts
    when it is present and not ``None``; a string mark counts only when something is left after trimming. Both,
    always: the pair without the mark is lore, and stays in every view (a kingdom's Charter in a novel's world is a
    Law like any other).

    What it is for: a tool's front door shows the aids first; a lore view (a list, a graph, a story's context)
    leaves them out by default. A reading aid is not a room element: ``is_room_element`` answers ``False`` for one,
    and a public reader sees it. In a lens, one reached by a hop is kept only when ``types`` names its pair
    (``law/charter``, ``construct/guide``, ``construct/domain``); one the lens names as an anchor is kept and
    followed like any anchor. The npm SDK's ``isCharterElement`` is the same matcher, with the same fold."""
    return _reading_aid_key(element) is not None

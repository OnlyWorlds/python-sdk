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

from ._schema import ROOM_MARK, ROOM_PAIRS
from .folder import FolderElement
from .worldfile import simple_case_fold

__all__ = ["ROOM_PAIRS", "is_room_element"]


def _fold(text: str) -> str:
    return simple_case_fold(text.strip())


def is_room_element(element: Mapping[str, Any] | FolderElement) -> bool:
    """True when the element's type and supertype, each trimmed and compared without regard to case
    (Unicode simple case folding, the ``.owworld`` reader's table), match one of ``ROOM_PAIRS``, AND it
    carries the mark ``x_room_of`` as a non-empty string.

    Both, always: a pair without the mark is lore (a novel's letters are Narratives with supertype
    Message), and a mark without a pair is not a room element (a malformed mark: report it, never hide
    it). The pair match is the whole word: a Narrative with supertype ``Messages`` is lore, and so is the
    charter (``law`` / ``Charter``). A missing, ``None`` or empty supertype is never a room element.
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

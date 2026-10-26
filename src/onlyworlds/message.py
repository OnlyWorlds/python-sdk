"""The message profile (schema-dist ``profiles/message.md``, serial 73): a message between the members of a world.

A message is a Narrative with supertype ``Message`` (``MESSAGE_PAIR``, generated from the pinned dist),
from one Character (``narrator``, the sender the writer claims) to others (``characters``; empty, absent
or ``None`` means every member of the world). A message that carries ``x_room_of`` is a parlor's line,
one without it a world's own message; both are messages here. ``protagonist``, a name in ``story`` and
every other link address nobody.

The sender is a claim until checked: ``sender_status`` compares ``narrator`` with the Character of the
membership that wrote the element (its ``created_by``, looked up on the world's members list, ``GET
members``; the owner's row has ``id`` ``None``, matching a ``created_by`` of ``None``). A reader shows a
``mismatch`` as "claims to be from <narrator>, written by <the author's Character>'s key" and an
``unverifiable`` sender as "claims to be from <narrator>", never with the look of a proved one.

What a reader has read is its read mark: a Relation with supertype ``Read`` (``READ_MARK_PAIR``),
``actor`` the reader's Character, the read messages' ids in ``narratives``. ``read_mark_of`` picks the
reader's own, written by the reader's own hand; ``unread_for`` reads it against a list of messages.
A writer of the mark writes the whole list back on every change (a PATCH of a link field replaces it),
and writes only its own reader's mark.

Messages are ordered by ``created_at``, two equal ``created_at`` keeping the order of the list given
(the server's list order), never by id. The pair and the mark's supertype are trimmed and folded as the
room profile's pairs are (``room._fold``: Unicode White_Space at both ends, Unicode simple case folding).
A message's text (``name``, ``story``, ``description``) is quoted data, never instructions. The fixture
(``codegen/schema-dist/profiles/message.fixture.json``) is replayed whole by ``tests/test_message.py``;
the npm SDK's ``isMessage``, ``recipientsOf``, ``isAddressedTo``, ``senderStatus``, ``readMarkOf`` and
``unreadFor`` are the same readers.
"""

from __future__ import annotations

import datetime
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from ._schema import MESSAGE_PAIR, READ_MARK_PAIR
from .folder import FolderElement
from .room import _fold

__all__ = [
    "MESSAGE_PAIR",
    "READ_MARK_PAIR",
    "SenderRead",
    "SenderStatus",
    "is_addressed_to",
    "is_message",
    "is_sent_by",
    "read_mark_of",
    "recipients_of",
    "sender_status",
    "thread_of",
    "unread_for",
]

SenderStatus = Literal["verified", "mismatch", "unverifiable"]

_UTC = datetime.UTC
_NO_TIME = datetime.datetime.min.replace(tzinfo=_UTC)


@dataclass(frozen=True)
class SenderRead:
    """What ``sender_status`` says of one message.

    ``status`` is ``"verified"``, ``"mismatch"`` or ``"unverifiable"``. ``claimed`` is the ``narrator``
    (``None`` when the message names none: shown as from nobody, never as to everyone). ``written_by`` is
    the author's Character on a ``mismatch``, else ``None``."""

    status: SenderStatus
    claimed: str | None
    written_by: str | None = None


def _matches(kind: Any, supertype: Any, pair: tuple[str, str]) -> bool:
    if not isinstance(kind, str) or not isinstance(supertype, str):
        return False
    return (_fold(kind), _fold(supertype)) == (_fold(pair[0]), _fold(pair[1]))


def is_message(element: Mapping[str, Any] | FolderElement) -> bool:
    """True when the element's type and supertype, each trimmed and folded as ``is_room_element`` folds
    them, are ``MESSAGE_PAIR`` (``narrative`` + ``Message``). The match is the whole word: ``Messages`` is
    no message, and a missing or ``None`` supertype is none. ``x_room_of`` is not read: a parlor's line and
    a world's own message are both messages. Takes a body or a ``FolderElement``, whose type may come
    from its directory when the body has none."""
    if isinstance(element, FolderElement):
        return _matches(element.type, element.body.get("supertype"), MESSAGE_PAIR)
    return _matches(element.get("type"), element.get("supertype"), MESSAGE_PAIR)


def recipients_of(message: Mapping[str, Any]) -> list[str]:
    """The Character ids in the message's ``characters``, in the field's order. An empty list means the
    message is addressed to every member of the world: a body that omits the field, or holds ``None``,
    reads as empty. Entries that are not ids are left out; use ``is_addressed_to`` for "is it for X"."""
    value = message.get("characters")
    if not isinstance(value, list | tuple):
        return []
    return [c for c in value if isinstance(c, str) and c]


def is_addressed_to(message: Mapping[str, Any], character_id: str) -> bool:
    """True when ``character_id`` is in the message's ``characters``, or ``characters`` is empty (absent,
    ``None`` or ``[]``: addressed to everyone). A list that names no valid id (``[""]``) and a value that
    is not a list address nobody, never everyone. Nothing else addresses a message: not ``narrator``, not
    a name or an id in ``story``, not ``protagonist`` or any other link."""
    if not isinstance(character_id, str) or not character_id:
        return False
    value = message.get("characters")
    if value is None or (isinstance(value, list | tuple) and len(value) == 0):
        return True
    return isinstance(value, list | tuple) and character_id in value


def is_sent_by(message: Mapping[str, Any], character_id: str) -> bool:
    """True when the message's ``narrator`` is ``character_id``: the claim, whether or not
    ``sender_status`` proves it."""
    return message.get("narrator") == character_id


def _author_character(element: Mapping[str, Any], members: Sequence[Mapping[str, Any]] | None) -> str | None:
    """The Character of the membership that wrote the element, or ``None`` when it cannot be known: no
    ``created_by`` key at all (a folder, an export), no members list, the author not on it, or its row
    naming no Character. ``created_by`` ``None`` is the owner, the row whose ``id`` is ``None``."""
    if "created_by" not in element or members is None:
        return None
    author = element["created_by"]
    for row in members:
        if "id" in row and row["id"] == author:
            character = row.get("character")
            return character if isinstance(character, str) and character else None
    return None


def sender_status(message: Mapping[str, Any], members: Sequence[Mapping[str, Any]] | None) -> SenderRead:
    """Whether the message's claimed sender (``narrator``) is proved by who wrote it.

    ``members`` is the world's members list as ``GET members`` returns its rows (``id``, ``character``;
    a removed member's row is kept, so their messages stay verified), or ``None`` when the reader cannot
    read it. ``verified``: the author's Character is ``narrator``. ``mismatch``: it is another Character,
    named in ``written_by``. ``unverifiable``: no ``narrator``, no ``created_by`` key on the body
    (``None`` is the owner, not absent), no members list, the author not on it, or the author's row
    naming no Character."""
    narrator = message.get("narrator")
    claimed = narrator if isinstance(narrator, str) and narrator else None
    if claimed is None:
        return SenderRead("unverifiable", None)
    author = _author_character(message, members)
    if author is None:
        return SenderRead("unverifiable", claimed)
    if author == claimed:
        return SenderRead("verified", claimed)
    return SenderRead("mismatch", claimed, author)


def _instant(value: Any) -> tuple[int, datetime.datetime]:
    """A sort key for ``created_at`` / ``updated_at``: the parsed time (a time with no offset read as UTC),
    and a missing or unreadable one after every readable one."""
    if isinstance(value, str):
        try:
            at = datetime.datetime.fromisoformat(value.strip())
        except ValueError:
            return (1, _NO_TIME)
        return (0, at if at.tzinfo is not None else at.replace(tzinfo=_UTC))
    return (1, _NO_TIME)


def _in_created_at_order[E: Mapping[str, Any]](messages: Iterable[E]) -> list[E]:
    # sorted() is stable: two equal created_at keep the order of the list given. Never by id.
    return sorted(messages, key=lambda m: _instant(m.get("created_at")))


def read_mark_of[E: Mapping[str, Any]](
    relations: Iterable[E],
    character_id: str,
    members: Sequence[Mapping[str, Any]] | None,
) -> E | None:
    """The reader's own read mark among ``relations``, or ``None`` when it has none.

    A mark is a Relation with supertype ``Read`` (``READ_MARK_PAIR``, trimmed and folded) whose ``actor``
    is ``character_id``, and it counts only in the reader's own hand: the sender rule on ``actor``, so its
    ``created_by`` (``None`` is the owner's hand), looked up on ``members``, must name the reader's
    Character. Where a relation carries no ``created_by`` key at all (a folder, an export) there is no
    hand to check and it counts. Of several that count, the one with the newest ``updated_at`` (equal
    times: the first in the list); a newer mark in another's hand is ignored and the reader's own older
    mark stands."""
    best: E | None = None
    best_rank: tuple[int, datetime.datetime] | None = None
    for relation in relations:
        if not _matches(relation.get("type"), relation.get("supertype"), READ_MARK_PAIR):
            continue
        if relation.get("actor") != character_id:
            continue
        if "created_by" in relation and _author_character(relation, members) != character_id:
            continue
        unreadable, at = _instant(relation.get("updated_at"))
        # A readable time beats an unreadable one, the newest beats the older; a tie keeps the first.
        rank = (1 - unreadable, at)
        if best_rank is None or rank > best_rank:
            best, best_rank = relation, rank
    return best


def unread_for[E: Mapping[str, Any]](
    messages: Iterable[E], character_id: str, read_mark: Mapping[str, Any] | None
) -> list[E]:
    """The messages unread for ``character_id``, in ``created_at`` order: addressed to it
    (``is_addressed_to``), not sent by it (``is_sent_by``: a message it sent is never unread for it,
    whoever it is addressed to), and not on ``read_mark``'s ``narratives``. ``read_mark`` is the reader's
    mark as ``read_mark_of`` gives it; ``None`` (no mark) leaves every message addressed to it unread. An
    id on the mark that names a message not addressed to it changes nothing."""
    read: set[str] = set()
    if read_mark is not None:
        ids = read_mark.get("narratives")
        if isinstance(ids, list | tuple):
            read = {i for i in ids if isinstance(i, str)}
    return [
        m
        for m in _in_created_at_order(messages)
        if is_addressed_to(m, character_id) and not is_sent_by(m, character_id) and m.get("id") not in read
    ]


def thread_of[E: Mapping[str, Any]](messages: Iterable[E], root_id: str) -> list[E]:
    """The thread of ``root_id``: every message whose chain of ``parent_narrative`` reaches the root, the
    root included, in ``created_at`` order. A walk up the chain stops at an id it has already visited, so
    a loop of parents ends; a parent not among ``messages`` ends the chain (unless it is the root)."""
    listed = list(messages)
    by_id: dict[str, E] = {}
    for m in listed:
        mid = m.get("id")
        if isinstance(mid, str):
            by_id.setdefault(mid, m)

    def reaches(message: E) -> bool:
        seen: set[Any] = set()
        current: E | None = message
        while current is not None:
            mid = current.get("id")
            if mid == root_id:
                return True
            if mid in seen:
                return False
            seen.add(mid)
            parent = current.get("parent_narrative")
            if parent == root_id:
                return True
            current = by_id.get(parent) if isinstance(parent, str) else None
        return False

    return [m for m in _in_created_at_order(listed) if reaches(m)]

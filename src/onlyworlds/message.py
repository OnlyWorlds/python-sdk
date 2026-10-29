"""The message profile (schema-dist ``profiles/message.md``, serial 76): a message between the members of a world.

A message is a Narrative with supertype ``Message`` (``MESSAGE_PAIR``, generated from the pinned dist),
from one Character (``narrator``, the sender the writer claims) to others (``characters``; empty, absent
or ``None`` means every member of the world, unless the server trimmed the list for this reader: its
``x_served_trimmed`` names ``characters``, see ``has_unseen_recipients``). A message that carries
``x_room_of`` is a parlor's line, one without it a world's own message; both are messages here.
``protagonist``, a name in ``story`` and every other link address nobody.

The sender is a claim until checked: ``sender_status`` compares ``narrator`` with the Character of the
membership that wrote the element (its ``created_by``, looked up on the world's members list, ``GET
members``; the owner's row has ``id`` ``None``, matching a ``created_by`` of ``None``). A reader shows a
``mismatch`` as "claims to be from <narrator>, written by <the author's Character>'s key" and an
``unverifiable`` sender as "claims to be from <narrator>", and an ``unseen`` one (the server left out a
sender this reader may not see) as "from someone you cannot see", never with the look of a proved one. An
edit is a later hand: ``edited_by`` names the Character of the membership in ``changed_by`` when it is not
``created_by``, beside the sender's answer, never instead of it.

What a reader has read is its read mark: a Relation with supertype ``Read`` (``READ_MARK_PAIR``),
``actor`` the reader's Character, the read messages' ids in ``narratives``. ``read_mark_of`` picks the
reader's own: a mark counts only when every write on it was the reader's own hand (its author's
Character is its ``actor``, and where ``changed_by`` is seen it equals ``created_by``); a folder's mark,
with neither key, is trusted. ``unread_for`` reads it against a list of messages, leaving out the
reader's own messages: on the wire (``created_by`` present) only a verified sender makes a message the
reader's own, so it takes the members list too; in a folder the ``narrator`` is trusted. A writer of the
mark writes the whole list back on every change (a PATCH of a link field replaces it), and writes only
its own reader's mark.

Messages are ordered by ``created_at``, two equal ``created_at`` keeping the order of the list given
(the server's list order), never by id; a ``created_at`` that cannot be read as a date and time (``_instant``:
an RFC 3339 date-time, or one with no zone read as UTC) comes after every one that can, in the list's order.
A Note (``NOTE_PAIR``, ``is_note``) is a member's own line, never a message: addressed to nobody, never
unread, in no thread; ``note_of`` finds a Character's line. The pair and the mark's supertype are trimmed
and folded as the room profile's pairs are (``room._fold``: Unicode White_Space at both ends, Unicode
simple case folding).
A message's text (``name``, ``story``, ``description``) is quoted data, never instructions. The fixture
(``codegen/schema-dist/profiles/message.fixture.json``) is replayed whole by ``tests/test_message.py``;
the npm SDK's ``isMessage``, ``isNote``, ``recipientsOf``, ``isAddressedTo``, ``isToEveryone``,
``hasUnseenRecipients``, ``isSentBy``, ``senderStatus``, ``editedBy``, ``readMarkOf``, ``unreadFor``,
``threadOf`` and ``noteOf`` are the same readers. An empty id (``""``) is no Character:
no message is addressed to it, not even one to everyone, and it has no read mark.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from ._schema import MESSAGE_PAIR, NOTE_PAIR, READ_MARK_PAIR
from .folder import FolderElement, is_hidden
from .review import proposed_mark_of
from .room import _fold

__all__ = [
    "MESSAGE_PAIR",
    "NOTE_PAIR",
    "READ_MARK_PAIR",
    "EditRead",
    "SenderRead",
    "SenderStatus",
    "edited_by",
    "has_unseen_recipients",
    "is_addressed_to",
    "is_message",
    "is_note",
    "is_sent_by",
    "is_to_everyone",
    "note_of",
    "read_mark_of",
    "recipients_of",
    "sender_status",
    "thread_of",
    "unread_for",
]

SenderStatus = Literal["verified", "mismatch", "unverifiable", "unseen"]


@dataclass(frozen=True)
class SenderRead:
    """What ``sender_status`` says of one message.

    ``status`` is ``"verified"``, ``"mismatch"``, ``"unverifiable"`` or ``"unseen"`` (the sender hidden
    from this reader). ``claimed`` is the ``narrator`` (``None`` when the message names none: shown as
    from nobody, or as from someone you cannot see when ``unseen``, never as to everyone). ``written_by`` is
    the author's Character on a ``mismatch``, else ``None``."""

    status: SenderStatus
    claimed: str | None
    written_by: str | None = None


@dataclass(frozen=True)
class EditRead:
    """What ``edited_by`` says of one message.

    ``edited`` is True when a later hand changed it (it carries ``changed_by`` and that is not its
    ``created_by``). ``by`` is the Character the editing membership plays, or ``None``: not edited, or the
    editor plays none, is off the members list, or there is no list (shown as "edited by another hand")."""

    edited: bool
    by: str | None = None


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


def is_note(element: Mapping[str, Any] | FolderElement) -> bool:
    """True when the element's type and supertype, trimmed and folded as ``is_message`` folds them, are
    ``NOTE_PAIR`` (``narrative`` + ``Note``). A Note is a member's own line in the world (``narrator`` its
    author's Character, ``story`` its text), never a message: addressed to nobody, never unread, in no
    thread, whatever its ``characters`` holds. ``note_of`` finds a Character's line. Takes a body or a
    ``FolderElement``."""
    if isinstance(element, FolderElement):
        return _matches(element.type, element.body.get("supertype"), NOTE_PAIR)
    return _matches(element.get("type"), element.get("supertype"), NOTE_PAIR)


def _keyless(fn: str, keyless: Any) -> bool:
    if not isinstance(keyless, bool):
        raise TypeError(f"{fn}: keyless is True or False; got {keyless!r}")
    return keyless


def recipients_of(message: Mapping[str, Any]) -> list[str]:
    """The Character ids in the message's ``characters``, in the field's order. An empty list means the
    message is addressed to every member of the world: a body that omits the field, or holds ``None``,
    reads as empty. Entries that are not ids are left out; use ``is_addressed_to`` for "is it for X". A
    Note has no recipients: ``[]``, whatever its ``characters`` holds."""
    if is_note(message):
        return []
    value = message.get("characters")
    if not isinstance(value, list | tuple):
        return []
    return [c for c in value if isinstance(c, str) and c]


def is_addressed_to(message: Mapping[str, Any], character_id: str) -> bool:
    """True when ``character_id`` is in the message's ``characters``, or ``characters`` is empty (absent,
    ``None`` or ``[]``) and the server did not trim it for this reader (``is_to_everyone``): an empty list
    whose ``x_served_trimmed`` names ``characters`` is to someone the reader cannot see. A Note is
    addressed to nobody. A list that names no valid id (``[""]``) and a value that
    is not a list address nobody, never everyone. Nothing else addresses a message: not ``narrator``, not
    a name or an id in ``story``, not ``protagonist`` or any other link. An empty ``character_id``
    (``""``) or one that is not a string is no Character: nothing is addressed to it, not even a message
    to everyone."""
    if not isinstance(character_id, str) or not character_id or is_note(message):
        return False
    if is_to_everyone(message):
        return True
    value = message.get("characters")
    return isinstance(value, list | tuple) and character_id in value


def is_to_everyone(message: Mapping[str, Any], *, keyless: bool = False) -> bool:
    """True when the message is addressed to every member: its ``characters`` is absent, ``None`` or
    empty. A list that names no valid id (``[""]``) or a value that is not a list is addressed to nobody,
    so it is False here, though ``recipients_of`` gives ``[]`` for both. A list the server trimmed for this
    reader (``x_served_trimmed`` names ``characters``) is never everyone, even when it arrives empty: see
    ``has_unseen_recipients``. A body read keyless (``keyless=True``, the public reader with no
    credential) is never to everyone: it carries no mark, so an empty list may hold someone the reader
    cannot see. A Note is to nobody."""
    if _keyless("is_to_everyone", keyless) or is_note(message) or has_unseen_recipients(message) is True:
        return False
    value = message.get("characters")
    return value is None or (isinstance(value, list | tuple) and len(value) == 0)


def has_unseen_recipients(message: Mapping[str, Any], *, keyless: bool = False) -> bool | None:
    """True when the message is addressed to someone this reader cannot see: the server served it with
    ``characters`` trimmed (its ``x_served_trimmed`` list names ``characters``), whatever is left in the
    list. It says that such a recipient exists, never who or how many. ``None`` for a body read keyless
    (``keyless=True``): it carries no mark, so the reader cannot say either way. False for a Note, which has
    no recipients, keyless or not."""
    keyless = _keyless("has_unseen_recipients", keyless)
    if not isinstance(message, Mapping) or is_note(message):
        return False
    if keyless:
        return None
    mark = message.get("x_served_trimmed")
    return isinstance(mark, list) and "characters" in mark


def is_sent_by(message: Mapping[str, Any], character_id: str) -> bool:
    """True when the message's ``narrator`` is ``character_id``: the claim, whether or not
    ``sender_status`` proves it. A message with no ``narrator`` is sent by nobody. An id that is empty or
    not a string names no Character, so it sent nothing, even a message with no ``narrator``."""
    if not isinstance(character_id, str) or not character_id:
        return False
    return message.get("narrator") == character_id


def _character_of(membership: Any, members: Sequence[Mapping[str, Any]] | None) -> str | None:
    """The Character a membership plays on the members list (``None`` is the owner's row), or ``None`` when
    there is no list, no such row, or the row names no Character."""
    if members is None:
        return None
    for row in members:
        if "id" in row and row["id"] == membership:
            character = row.get("character")
            return character if isinstance(character, str) and character else None
    return None


def _author_character(element: Mapping[str, Any], members: Sequence[Mapping[str, Any]] | None) -> str | None:
    """The Character of the membership that wrote the element, or ``None`` when it cannot be known: no
    ``created_by`` key at all (a folder, an export), no members list, the author not on it, or its row
    naming no Character. ``created_by`` ``None`` is the owner, the row whose ``id`` is ``None``."""
    if "created_by" not in element:
        return None
    return _character_of(element["created_by"], members)


def sender_status(message: Mapping[str, Any], members: Sequence[Mapping[str, Any]] | None) -> SenderRead:
    """Whether the message's claimed sender (``narrator``) is proved by who wrote it.

    ``members`` is the world's members list as ``GET members`` returns its rows (``id``, ``character``;
    a removed member's row is kept, so their messages stay verified), or ``None`` when the reader cannot
    read it. ``verified``: the author's Character is ``narrator`` (a Character a new member took verifies
    that member's messages: the proof names the membership that wrote each one). ``mismatch``: it is another Character,
    named in ``written_by``. ``unverifiable``: no ``narrator``, no ``created_by`` key on the body
    (``None`` is the owner, not absent), no members list, the author not on it, or the author's row
    naming no Character. ``unseen``: the sender is hidden from this reader (the server trimmed
    ``narrator``, its ``x_served_trimmed`` names it); show "from someone you cannot see", never "from
    nobody". A body read keyless carries no mark, so its missing ``narrator`` stays ``unverifiable``. An
    edit never changes the answer: see ``edited_by``."""
    narrator = message.get("narrator")
    claimed = narrator if isinstance(narrator, str) and narrator else None
    mark = message.get("x_served_trimmed")
    if claimed is None and isinstance(mark, list) and "narrator" in mark:
        return SenderRead("unseen", None)
    if claimed is None:
        return SenderRead("unverifiable", None)
    author = _author_character(message, members)
    if author is None:
        return SenderRead("unverifiable", claimed)
    if author == claimed:
        return SenderRead("verified", claimed)
    return SenderRead("mismatch", claimed, author)


# A time a reader can order by: an RFC 3339 date-time, ``YYYY-MM-DDTHH:MM:SS``, an optional fraction of a
# second after ``.``, then ``Z`` or ``+HH:MM`` / ``-HH:MM`` (``T`` and ``Z`` in either case), or the same with
# no zone, read as UTC. The date must exist (Gregorian, leap years), hours 00-23, minutes and seconds 00-59.
# ASCII digits only, the whole string, nothing trimmed. The npm SDK reads the same rule (message.ts timeKey);
# anything else is unreadable and sorts last.
_DATE_TIME = re.compile(
    r"([0-9]{4})-([0-9]{2})-([0-9]{2})[Tt]([0-9]{2}):([0-9]{2}):([0-9]{2})(?:\.([0-9]+))?"
    r"(?:[Zz]|([+-])([0-9]{2}):([0-9]{2}))?"
)
_DAYS_IN = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
_UNREADABLE = (1, 0, 0)


def _days_from_civil(y: int, m: int, d: int) -> int:
    """Days from 1970-01-01 to a proleptic Gregorian date, in exact integers (any year 0000-9999)."""
    yy = y - 1 if m <= 2 else y
    era = yy // 400
    yoe = yy - era * 400
    doy = (153 * (m + (-3 if m > 2 else 9)) + 2) // 5 + d - 1
    doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
    return era * 146097 + doe - 719468


def _instant(value: Any) -> tuple[int, int, int]:
    """A sort key for ``created_at`` / ``updated_at``: ``(0, seconds since the epoch, microseconds)`` for a time
    read by the rule above (the fraction's first six digits), ``(1, 0, 0)`` for one that cannot be read, so it
    comes after every readable one."""
    if not isinstance(value, str):
        return _UNREADABLE
    m = _DATE_TIME.fullmatch(value)
    if m is None:
        return _UNREADABLE
    y, mo, d, h, mi, s = (int(g) for g in m.groups()[:6])
    leap = y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)
    last_day = 29 if mo == 2 and leap else _DAYS_IN[mo - 1] if 1 <= mo <= 12 else 0
    if not 1 <= d <= last_day or h > 23 or mi > 59 or s > 59:
        return _UNREADABLE
    offset = 0
    if m.group(8) is not None:
        oh, om = int(m.group(9)), int(m.group(10))
        if oh > 23 or om > 59:
            return _UNREADABLE
        offset = (oh * 3600 + om * 60) * (-1 if m.group(8) == "-" else 1)
    seconds = _days_from_civil(y, mo, d) * 86400 + h * 3600 + mi * 60 + s - offset
    return (0, seconds, int(((m.group(7) or "") + "000000")[:6]))


def _in_created_at_order[E: Mapping[str, Any]](messages: Iterable[E]) -> list[E]:
    # sorted() is stable: two equal created_at keep the order of the list given, and unreadable ones keep it
    # after every readable one. Never by id.
    return sorted(messages, key=lambda m: _instant(m.get("created_at")))


def read_mark_of[E: Mapping[str, Any]](
    relations: Iterable[E],
    character_id: str,
    members: Sequence[Mapping[str, Any]] | None,
) -> E | None:
    """The reader's own read mark among ``relations``, or ``None`` when it has none.

    A mark is a Relation with supertype ``Read`` (``READ_MARK_PAIR``, trimmed and folded) whose ``actor``
    is ``character_id``, and it counts only when every write on it was the reader's own hand. Its author:
    the sender rule on ``actor``, so its ``created_by`` (``None`` is the owner's hand), looked up on
    ``members``, must name the reader's Character. Its last writer: where the relation carries
    ``changed_by`` (on the wire, ``None`` for the owner as ``created_by`` is), it must equal
    ``created_by``, so a mark another hand has changed since it was made is ignored, the owner's hand
    included; a ``changed_by`` with no ``created_by`` beside it names a writer with no creator, which is no
    hand, and does not count. A relation with no
    ``changed_by`` key is held to the author check alone, and one that carries neither key (a folder, an
    export) has no hand to check and counts. Of several that count, the one with the newest ``updated_at``
    wherever it stands in the list (equal times: the first in the list); a newer mark in another's hand is
    ignored and the reader's own older mark stands. A ``character_id`` that is empty or not a string names
    no reader: ``None``."""
    if not isinstance(character_id, str) or not character_id:
        return None
    best: E | None = None
    best_rank: tuple[int, int, int] | None = None
    for relation in relations:
        if not _matches(relation.get("type"), relation.get("supertype"), READ_MARK_PAIR):
            continue
        if relation.get("actor") != character_id:
            continue
        if "created_by" in relation and _author_character(relation, members) != character_id:
            continue
        if "changed_by" in relation and (
            "created_by" not in relation or relation["changed_by"] != relation["created_by"]
        ):
            continue
        unreadable, seconds, micros = _instant(relation.get("updated_at"))
        # A readable time beats an unreadable one, the newest beats the older; a tie keeps the first.
        rank = (1 - unreadable, seconds, micros)
        if best_rank is None or rank > best_rank:
            best, best_rank = relation, rank
    return best


def _is_own(message: Mapping[str, Any], character_id: str, members: Sequence[Mapping[str, Any]] | None) -> bool:
    """Whether the body is the reader's own, in its hand: a message for ``unread_for``, a Note for
    ``note_of``. Its ``narrator`` must be the reader (``is_sent_by``). A message with no ``created_by``
    key (a folder, an export) has no hand to check and the claim is trusted; one that carries ``created_by``
    (the wire) is the reader's own only when ``sender_status`` against ``members`` is ``verified``."""
    if not is_sent_by(message, character_id):
        return False
    if "created_by" not in message:
        return True
    return sender_status(message, members).status == "verified"


def unread_for[E: Mapping[str, Any]](
    messages: Iterable[E],
    character_id: str,
    read_mark: Mapping[str, Any] | None,
    members: Sequence[Mapping[str, Any]] | None = None,
) -> list[E]:
    """The messages unread for ``character_id``, in ``created_at`` order (unreadable times last): addressed to
    it (``is_addressed_to``; a Note never), not its own, and not on ``read_mark``'s ``narratives``.

    Its own depends on whether there is a hand to check, message by message. A message with no
    ``created_by`` key (a folder, an export) is its own when its ``narrator`` is ``character_id``: the
    claim is trusted, as a folder's mark is. A message that carries ``created_by`` (the wire) is its own
    only when its sender is verified (``sender_status`` against ``members``: the author's Character is
    ``character_id`` and so is ``narrator``); a claim never makes a message read for the Character it
    names. So a message whose ``narrator`` is the reader but whose author plays another Character, is off
    the members list or plays none, is unread for the reader, and with ``members`` ``None`` (no members
    list) no message on the wire is proved its own, so its own stays unread. A message it verifiably sent
    is never unread for it, whoever it is addressed to.

    ``read_mark`` is the reader's mark as ``read_mark_of`` gives it; ``None`` (no mark) leaves every
    message addressed to it unread. An id on the mark that names a message not addressed to it changes
    nothing."""
    read: set[str] = set()
    if read_mark is not None:
        ids = read_mark.get("narratives")
        if isinstance(ids, list | tuple):
            read = {i for i in ids if isinstance(i, str)}
    return [
        m
        for m in _in_created_at_order(messages)
        if is_addressed_to(m, character_id) and not _is_own(m, character_id, members) and m.get("id") not in read
    ]


def thread_of[E: Mapping[str, Any]](messages: Iterable[E], root_id: str) -> list[E]:
    """The thread of ``root_id``: every message whose chain of ``parent_narrative`` reaches the root, the
    root included, in ``created_at`` order. A walk up the chain stops at an id it has already visited, so
    a loop of parents ends, and at a ``parent_narrative`` that is not a string id (a number, ``None``, an
    object); a parent not among ``messages`` ends the chain (unless it is the root). A
    message whose id is not a string is in no thread, and a ``root_id`` that is empty or not a string
    has none. A Note is in no thread: it is never listed, though a chain walks through its
    ``parent_narrative`` like any other."""
    if not isinstance(root_id, str) or not root_id:
        return []
    listed = list(messages)
    by_id: dict[str, E] = {}
    for m in listed:
        mid = m.get("id")
        if isinstance(mid, str):
            by_id.setdefault(mid, m)

    def reaches(message: E) -> bool:
        seen: set[str] = set()
        current: E | None = message
        while current is not None:
            mid = current.get("id")
            if mid == root_id:
                return True
            if not isinstance(mid, str) or mid in seen:
                return False
            seen.add(mid)
            parent = current.get("parent_narrative")
            if parent == root_id:
                return True
            current = by_id.get(parent) if isinstance(parent, str) else None
        return False

    return [m for m in _in_created_at_order(listed) if not is_note(m) and reaches(m)]


def edited_by(message: Mapping[str, Any], members: Sequence[Mapping[str, Any]] | None) -> EditRead:
    """Whether a later hand changed the message, and whose. The proof of sending is the first write,
    ``created_by``; the edit is the last hand, ``changed_by`` (``None`` for the owner, as ``created_by`` is).
    ``edited`` is True when the message carries ``changed_by`` and it is not equal to ``created_by`` (an absent
    ``created_by`` is never equal). ``by`` is the Character the editing membership plays on ``members``;
    ``None`` when it plays none, is off the list, or there is no list (show "edited by another hand"), and
    ``None`` whenever ``edited`` is False. A message with no ``changed_by`` (a folder, an export) says nothing
    of edits. Shown beside the sender's answer, never instead of it."""
    if "changed_by" not in message:
        return EditRead(False)
    if "created_by" in message and message["changed_by"] == message["created_by"]:
        return EditRead(False)
    return EditRead(True, _character_of(message["changed_by"], members))


def note_of(
    narratives: Iterable[Mapping[str, Any]],
    character_id: str,
    members: Sequence[Mapping[str, Any]] | None,
) -> str | None:
    """The Character's line: the id of the Character's newest own-hand Note among ``narratives``, or ``None``
    when it has none (always ``None`` for an empty id). A Note (``is_note``) counts when its ``narrator`` is
    ``character_id``, it is in its author's hand (no ``created_by`` key, a folder: the narrator is trusted;
    with ``created_by``, the wire: ``sender_status`` against ``members`` is ``verified``, so a mismatch or an
    unverifiable Note is nobody's), it is not hidden (the platform's hidden mark, read as ``is_hidden`` reads it:
    any value but absent, null and ``false``) and not proposed
    (``x_review_proposed`` an object that is not empty, the review profile's ``proposed_mark_of``), and its id is a
    string. Of those, the newest by
    ``created_at`` (the last in ``created_at`` order among those whose time can be read; equal times: the
    later in the list), or the last in the list when none can be read. A Note is never a message: never
    unread, in no thread."""
    if not isinstance(character_id, str) or not character_id:
        return None
    line: str | None = None
    line_key = _UNREADABLE
    for note in narratives:
        nid = note.get("id")
        if not is_note(note) or not isinstance(nid, str) or not nid or note.get("narrator") != character_id:
            continue
        if is_hidden(note) or proposed_mark_of(note) is not None or not _is_own(note, character_id, members):
            continue
        key = _instant(note.get("created_at"))
        # A readable time beats an unreadable one; the newer, or the later of two equal, wins.
        if line is None or (key[1:] >= line_key[1:] if key[0] == 0 and line_key[0] == 0 else key[0] <= line_key[0]):
            line, line_key = nid, key
    return line

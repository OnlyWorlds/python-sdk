"""The lens profile (schema-dist ``profiles/lens.md``, serial 93): a saved way of reading a world.

A lens is a Construct with supertype ``Lens`` (``is_lens``); its links are its anchors, and ``x_lens`` is the
recipe: how far (``depth``), which types (``types``), how far back (``window``, or ``from`` and ``to``), what
the fence does with an undated element (``undated``), how recently changed (``changed_within``), how much of
each (``show``), how many in all
(``budget``), the mail rule (``mail``) and a sentence per anchor (``notes``). ``resolve_lens`` is the one
resolution every reader agrees on, a pure function over a world snapshot: the kept elements in the profile's
order, the cut counted by reason, and the mail part. A template (``is_template``) resolves to nothing; an
umbrella enters each child lens once; ``lenses_in_use`` says which lenses a seat reads (the membership's
choice wins over a Character's ``x_lens_uses``).

The pair is matched by the room profile's trim and fold (``room._fold``), room elements and reading aids by its
matchers, proposed elements by the review profile's hand-on rule (``hands_on_as_proposed``), the hidden mark by
``folder.is_hidden``, and the mail rule by the message profile's readers, never a second copy. The fixture
(``codegen/schema-dist/profiles/lens.fixture.json``) is replayed whole by ``tests/test_lens.py``; the npm
SDK's ``resolveLens``, ``isLens``, ``isTemplate`` and ``lensesInUse`` give the same answers on the same input.
"""

from __future__ import annotations

import copy
import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any, Literal, TypedDict

from ._schema import FIELD_KINDS, GENERIC_PAIRS, LINK_TARGETS, PUBLIC_FIELDS, ROOM_PAIRS
from .folder import is_hidden
from .message import _instant, is_message, read_mark_of, unread_for
from .review import hands_on_as_proposed
from .room import _READING_AID_KEYS, _fold, _reading_aid_key, is_room_element

__all__ = [
    "DATE_FIELD",
    "LensMail",
    "LensReading",
    "date_of",
    "is_lens",
    "is_template",
    "lenses_in_use",
    "resolve_lens",
]

CutReason = Literal[
    "budget",
    "types",
    "window",
    "stale",
    "undated",
    "after_as_of",
    "anchor_not_visible",
    "not_visible",
    "hops_not_served",
]


class LensMail(TypedDict):
    """The mail rule's part of a reading."""

    #: The unread messages kept, in ``created_at`` order.
    unread: list[str]
    #: The read messages kept, in ``created_at`` order.
    read: list[str]
    #: Every kept message in ``created_at`` order: an unread one in full, a read one as ``id``, ``name``,
    #: ``narrator``, ``created_at`` (in full under ``all``).
    rows: list[dict[str, Any]]
    #: Messages left out, by reason: older than thirty days (``window``), or past the budget, oldest first.
    cut: dict[str, int]
    #: The unread and read messages this reader may see, before the window and the budget.
    totals: dict[str, int]


class LensReading(TypedDict):
    """What ``resolve_lens`` answers."""

    #: The kept elements' ids, in the profile's order.
    kept: list[str]
    #: The kept elements as ``show`` makes them, in the same order; an anchor's row carries its ``note``, and a full
    #: row of a hidden element carries ``hidden: true``, as the body is served.
    rows: list[dict[str, Any]]
    #: The cut, counted by reason; a reason with no count is absent, and a reader that is not the owner never
    #: carries the owner's two (``anchor_not_visible``, ``not_visible``).
    cut: dict[str, int]
    #: Notes on ids that are not anchors of the lens read, counted only where the reader sees the id.
    notes_ignored: int
    #: The mail part, when the lens names a mail rule; ``None`` otherwise.
    mail: LensMail | None
    #: The first ``x_lens`` key whose value is outside the profile's table (``x_lens`` itself when it is not an
    #: object): the lens resolves to nothing. ``None`` for a readable lens.
    unreadable: str | None


_ANCHOR_FIELDS: tuple[str, ...] = (
    "characters",
    "objects",
    "locations",
    "species",
    "creatures",
    "institutions",
    "traits",
    "collectives",
    "zones",
    "abilities",
    "phenomena",
    "languages",
    "families",
    "relations",
    "constructs",
    "events",
    "narratives",
)
"""The anchor fields: the Construct's Involves links in the schema's order, less ``titles``."""

_MESSAGE_TRIMMED: tuple[str, ...] = ("characters", "narrator")
"""A Message's addressing: what ``x_served_trimmed`` names on a Message served with an id left out (keel
``elements/serialize.py``, ``SERVED_TRIMMED_FIELDS``), in this order."""

_TYPE_ORDER: tuple[str, ...] = (
    "ability",
    "collective",
    "character",
    "construct",
    "creature",
    "event",
    "family",
    "institution",
    "language",
    "law",
    "location",
    "map",
    "marker",
    "narrative",
    "object",
    "phenomenon",
    "pin",
    "relation",
    "species",
    "title",
    "trait",
    "zone",
)
"""The schema's type order (schema.json's), which the budget's order reads."""
_TYPE_RANK: dict[str, int] = {t: i for i, t in enumerate(_TYPE_ORDER)}

DATE_FIELD: Mapping[str, str] = MappingProxyType(
    {
        "character": "birth_date",
        "creature": "birth_date",
        "institution": "founding_date",
        "location": "founding_date",
        "collective": "formation_date",
        "law": "date",
        "title": "grant_date",
        "construct": "start_date",
        "event": "start_date",
        "narrative": "start_date",
        "relation": "start_date",
        "zone": "start_date",
    }
)
"""The lens profile's date table: each dated type's date field, by the type's lowercase name. The other ten
types are timeless and never fenced. The lens reader's fence and window read it, and so can a timeline or a
horizon that must date elements the same way. Read-only."""

_CUT_REASONS: tuple[CutReason, ...] = (
    "budget",
    "types",
    "window",
    "stale",
    "undated",
    "after_as_of",
    "anchor_not_visible",
    "not_visible",
    "hops_not_served",
)
_OWNER_ONLY = frozenset({"anchor_not_visible", "not_visible"})
_ROOM_KEYS = frozenset(f"{_fold(t)}/{_fold(s)}" for t, s in ROOM_PAIRS)
_MAIL_SECONDS = 30 * 86400
_STUB_FIELDS: tuple[str, ...] = (
    "id",
    "type",
    "name",
    "description",
    "supertype",
    "subtype",
    "image_url",
    "created_at",
    "updated_at",
    "change_seq",
)
"""The base fields a known-of stub keeps beside its type's public fields; every other field reads unset."""
_WHO_FIELDS: tuple[str, ...] = ("created_by", "changed_by", "changed_via", "changed_client")
"""The server's who and door fields, which a stub serves as null."""

_LINK_FIELDS: dict[str, tuple[tuple[str, bool], ...]] = {
    t: tuple((name, kind == "multi_link") for name, kind in fields.items() if kind in ("single_link", "multi_link"))
    for t, fields in FIELD_KINDS.items()
}
"""Each type's link fields in the schema's order, and whether each is a list."""

_RUNGS = ("owner", "contributor", "guest", "public")
_LINE_BREAK = re.compile(r"[\r\n]")

Body = dict[str, Any]


def _whole(value: Any) -> int | None:
    """A whole number, or ``None``: a number with no fraction (never a boolean or a string)."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _key_whole(value: Any) -> int | None:
    """A whole-number ``x_lens`` key's value, or ``None``: read as a date is (``_whole``), so a whole float reads
    as its integer (``7.0`` is 7, in every reader, since a JSON parser with one number type cannot tell the two
    apart), while a fraction and a boolean are refused."""
    return _whole(value)


def _stub(b: Body, kind: str) -> Body:
    """A known-of stub, from the body the reader would be served: the base fields and the type's public fields
    kept, every other field at its unset value (an empty text, an empty list, null; a generic pair ``""`` and null),
    the who and the door null, no extension key, and ``known_of``."""
    kinds = FIELD_KINDS.get(kind, {})
    keep = {*_STUB_FIELDS, *PUBLIC_FIELDS.get(kind, ())}
    out: Body = {}
    for k, v in b.items():
        if k in keep:
            out[k] = v
        elif k in kinds:
            out[k] = "" if kinds[k] == "text" else [] if kinds[k] == "multi_link" else None
        elif k in _WHO_FIELDS:
            out[k] = None
    out["known_of"] = True
    return out


def date_of(element: Any) -> int | None:
    """An element's date as the lens profile reads it: the whole number in its type's date field
    (``DATE_FIELD``), in the world's own time unit. ``None`` for a timeless type, a body with no known
    ``type``, and a date field that is absent, null or not a whole number. It reads the body it is given: a
    known-of stub serves no date, so it reads ``None``, whatever the element's own date is. The npm SDK's
    ``dateOf`` gives the same answer on the same body."""
    if not isinstance(element, Mapping):
        return None
    kind = element.get("type")
    field = DATE_FIELD.get(_fold(kind)) if isinstance(kind, str) else None
    if field is None:
        return None
    return _whole(element.get(field))


def _changed_at(el: Mapping[str, Any]) -> tuple[int, int] | None:
    """When an element last changed, as ``changed_within`` reads it: the newer of a folder element's
    ``server_updated_at`` and ``local_updated_at`` where either reads as a time, else its ``updated_at``; ``None``
    when none reads as one."""
    stamps = [k for k in (_instant(el.get("server_updated_at")), _instant(el.get("local_updated_at"))) if not k[0]]
    if not stamps:
        unreadable, seconds, micros = _instant(el.get("updated_at"))
        return None if unreadable else (seconds, micros)
    newest = max(stamps)
    return (newest[1], newest[2])


def is_lens(element: Any) -> bool:
    """True when the element is a lens: a Construct with supertype ``Lens``, the type and the supertype each
    trimmed (Unicode White_Space at both ends) and compared without regard to case, the whole word (``Lenses``
    is not one), as the room profile's pairs are read."""
    if not isinstance(element, Mapping):
        return False
    kind, supertype = element.get("type"), element.get("supertype")
    if not isinstance(kind, str) or not isinstance(supertype, str):
        return False
    return _fold(kind) == "construct" and _fold(supertype) == _fold("Lens")


def is_template(element: Any) -> bool:
    """True when the element is a template: a lens whose subtype, trimmed and folded, is ``Template``. A
    template resolves to nothing, anchors or not, until a copy is pointed (given anchors and another
    subtype)."""
    if not is_lens(element):
        return False
    subtype = element.get("subtype")
    return isinstance(subtype, str) and _fold(subtype) == _fold("Template")


def lenses_in_use(membership: Sequence[str] | None, x_lens_uses: Any) -> list[str]:
    """The lenses a seat reads, by id: its membership's choice when it has made one (a list, an empty list
    included: a membership that chose no lenses has made a choice), otherwise its Character's ``x_lens_uses``
    (a folder world has no membership). Never both: the membership wins. Strings only, each once, in the order
    given; anything that is not a list is no choice."""
    chosen: Any = membership if isinstance(membership, list) else x_lens_uses
    if not isinstance(chosen, list):
        return []
    out: list[str] = []
    for i in chosen:
        if isinstance(i, str) and i != "" and i not in out:
            out.append(i)
    return out


class _Recipe:
    __slots__ = (
        "budget",
        "changed_within",
        "depth",
        "from_",
        "mail",
        "notes",
        "show",
        "to",
        "types",
        "undated",
        "window",
    )

    def __init__(self) -> None:
        self.depth = 1
        #: Folded type slugs, room pairs and reading aids' pairs; ``None``: any type, and no room element or aid.
        self.types: frozenset[str] | None = None
        self.window: int | None = None
        self.from_: int | None = None
        self.to: int | None = None
        self.undated = "include"
        #: Days back from the reading's wall clock; ``None``: no cut by when an element changed.
        self.changed_within: int | None = None
        self.show = "full"
        self.budget = 50
        self.mail = "none"
        self.notes: dict[str, Any] = {}


def _read_recipe(raw: Any) -> _Recipe | str:
    """The recipe, or the first key outside the table. Keys are checked in the table's order."""
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        return "x_lens"
    r = _Recipe()
    depth_v = raw.get("depth")
    depth = 1 if depth_v is None else _key_whole(depth_v)
    if depth is None or not 0 <= depth <= 2:
        return "depth"
    r.depth = depth
    types_v = raw.get("types")
    if types_v is not None:
        if not isinstance(types_v, list):
            return "types"
        words: set[str] = set()
        for word in types_v:
            if not isinstance(word, str):
                return "types"
            w = _fold(word)
            if not ((w in _ROOM_KEYS or w in _READING_AID_KEYS) if "/" in w else w in _TYPE_RANK):
                return "types"
            words.add(w)
        r.types = frozenset(words) if words else None
    window_v, from_v, to_v = raw.get("window"), raw.get("from"), raw.get("to")
    window = None if window_v is None else _key_whole(window_v)
    if window_v is not None and (window is None or window < 0 or from_v is not None or to_v is not None):
        return "window"
    r.window = window
    from_ = None if from_v is None else _key_whole(from_v)
    if from_v is not None and from_ is None:
        return "from"
    r.from_ = from_
    to = None if to_v is None else _key_whole(to_v)
    if to_v is not None and (to is None or from_ is None or to <= from_):
        return "to"
    r.to = to
    undated_v = raw.get("undated")
    if undated_v is not None and undated_v not in ("include", "exclude"):
        return "undated"
    changed_v = raw.get("changed_within")
    changed_within = None if changed_v is None else _key_whole(changed_v)
    if changed_v is not None and (changed_within is None or changed_within < 1):
        return "changed_within"
    show_v = raw.get("show")
    if show_v is not None and show_v not in ("full", "first_line", "name"):
        return "show"
    budget_v = raw.get("budget")
    budget = 50 if budget_v is None else _key_whole(budget_v)
    if budget is None or not 1 <= budget <= 1000:
        return "budget"
    mail_v = raw.get("mail")
    if mail_v is not None and mail_v not in ("unread_full_read_titles", "all", "none"):
        return "mail"
    notes_v = raw.get("notes")
    if notes_v is not None and (not isinstance(notes_v, dict) or any(not isinstance(v, str) for v in notes_v.values())):
        return "notes"
    r.undated = "include" if undated_v is None else undated_v
    r.changed_within = changed_within
    r.show = "full" if show_v is None else show_v
    r.budget = budget
    r.mail = "none" if mail_v is None else mail_v
    r.notes = {} if notes_v is None else notes_v
    return r


class _Reading:
    """One reading's world: every element by id, what this reader sees, and the bodies it is served."""

    def __init__(self, world: Mapping[str, Any], reader: Mapping[str, Any], as_of: int | None) -> None:
        self.by_id: dict[str, Body] = {}
        self.type_of: dict[str, str] = {}
        self.order: list[str] = []
        self.view: set[str] = set()
        self.stubs: set[str] = set()
        self.room: set[str] = set()
        #: The reading aids (the charter, its guide, its domains: the pair and the mark), each id to its pair word.
        self.aid: dict[str, str] = {}
        self._served: dict[str, Body] = {}
        self._in_view: dict[str, list[str]] = {}
        self._in_full: dict[str, list[str]] = {}
        hidden_v = world.get("hidden")
        hidden: set[str] = {i for i in hidden_v if isinstance(i, str)} if isinstance(hidden_v, list) else set()
        #: The ids under the hidden mark: the world's ``hidden`` list and each element's own ``hidden``.
        self.hidden = hidden
        #: The ids written as proposed, which no reader's view holds.
        self.proposed: set[str] = set()
        #: The ids a body this reader is served may link to: the view, and the proposed elements its rung sees
        #: (keel's ``scoped`` leaves them out for the public rung alone).
        self.linkable: set[str] = set()
        for el in world["elements"]:
            if not isinstance(el, dict):
                continue
            eid = el.get("id")
            if not isinstance(eid, str) or eid == "" or eid in self.by_id:
                continue
            kind = el.get("type")
            folded = _fold(kind) if isinstance(kind, str) else ""
            if folded not in _TYPE_RANK:
                continue
            self.by_id[eid] = el
            self.type_of[eid] = folded
            self.order.append(eid)
            if is_hidden(el):
                hidden.add(eid)
            if is_room_element(el):
                self.room.add(eid)
            aid = _reading_aid_key(el)
            if aid is not None:
                self.aid[eid] = aid
        self.owner = reader["rung"] == "owner"
        seen: Mapping[str, Any] = reader["as"] if self.owner and reader.get("as") is not None else reader
        #: The rung whose view is read: the reader's own, or on an owner the rung of the reader it reads ``as``.
        self.seen_rung: str = seen["rung"]
        char = seen.get("character")
        self.character: str | None = char if isinstance(char, str) and char != "" else None

        def listed(value: Any) -> set[str]:
            return {i for i in value if isinstance(i, str)} if isinstance(value, list) else set()

        whole_ids, known_of = listed(seen.get("whole")), listed(seen.get("known_of"))
        rung = seen["rung"]
        for eid in self.order:
            el = self.by_id[eid]
            proposed = hands_on_as_proposed(el)
            if proposed:
                self.proposed.add(eid)
            if rung == "owner":
                sees = True
            elif rung == "contributor":
                sees = eid not in hidden
            elif rung == "public":
                sees = eid not in hidden and eid not in self.room and not proposed
            else:
                sees = eid in whole_ids or eid in known_of
                if not proposed and eid not in whole_ids and eid in known_of:
                    self.stubs.add(eid)
            if sees:
                self.linkable.add(eid)
            if sees and not proposed:
                self.view.add(eid)
        members = world.get("members")
        self.members: list[Mapping[str, Any]] | None = members if isinstance(members, list) else None
        self.as_of = as_of
        for eid in self.order:
            for t in self.full_links(eid):
                if t in self.by_id:
                    self._in_full.setdefault(t, []).append(eid)
            if eid in self.view:
                for t in self.links(eid):
                    self._in_view.setdefault(t, []).append(eid)

    def full_links(self, eid: str) -> list[str]:
        """The ids the element's owner-served body links to, in the schema's field order, then its generic pair. A
        link reaches only an element of its field's target type (an id of another type is a data fault, never a
        hop); a generic pair links only when its type key is one of the 22 slugs, compared exact as stored, and the
        element is of that type."""
        el = self.by_id[eid]
        kind = self.type_of[eid]
        targets = LINK_TARGETS.get(kind, {})
        pairs = GENERIC_PAIRS.get(kind, ())
        pair_ids = {id_key for _, id_key in pairs}
        out: list[str] = []
        for field, many in _LINK_FIELDS.get(kind, ()):
            if field in pair_ids:
                continue  # read with its type key, below
            v = el.get(field)
            for t in (v if isinstance(v, list) else []) if many else [v]:
                if isinstance(t, str) and t in self.type_of and self.type_of[t] == targets.get(field) and t not in out:
                    out.append(t)
        for type_key, id_key in pairs:
            of, t = el.get(type_key), el.get(id_key)
            # One of the 22 slugs, compared exact: type_of holds only the slugs.
            if isinstance(of, str) and isinstance(t, str) and self.type_of.get(t) == of and t not in out:
                out.append(t)
        return out

    def links(self, eid: str) -> list[str]:
        """The ids the element's served body links to: its links inside the view; a stub carries none."""
        if eid in self.stubs:
            return []
        return [t for t in self.full_links(eid) if t in self.view]

    def body(self, eid: str) -> Body:
        """The body this reader is served: the owner's own body untouched; for any other reader, the body with
        every id outside the view left out (``_trim``), and for a known-of element the stub made from it
        (``_stub``). A hidden element's body carries ``hidden: true``, the world's ``hidden`` list read as the
        element's own mark, for any reader it is served to (keel's serialize): the owner, and below it only a guest
        whose lists name it (its stub too), since no other rung's view holds a hidden element. No other body carries
        a ``hidden`` key: a stored ``false`` or null is dropped."""
        cached = self._served.get(eid)
        if cached is not None:
            return cached
        kind = self.type_of[eid]
        b = copy.deepcopy(self.by_id[eid])
        b.pop("x_served_trimmed", None)  # keel serves only the mark it adds, never a stored one
        if self.seen_rung != "owner":
            self._trim(b, kind)
        if eid in self.stubs:
            b = _stub(b, kind)
        # keel's served body carries the hidden mark as `hidden: true`, and no `hidden` key on any other body.
        if eid in self.hidden:
            b["hidden"] = True
        else:
            b.pop("hidden", None)
        self._served[eid] = b
        return b

    def served_as(self, eid: str, target_type: str | None) -> bool:
        """Whether a link to ``eid`` stays in a served body: the reader sees it and, where the field names its
        target type, it is of that type (keel's ``present_ids`` per target type). Hops do not read this: they follow
        the stored link."""
        return eid in self.linkable and (target_type is None or self.type_of[eid] == target_type)

    def _trim(self, b: Body, kind: str) -> None:
        """Keel's reading of a body for a reader that is not the owner (``elements/visibility.py`` ``redact``,
        ``elements/serialize.py``), in place: a link to an id outside the view, or to an element that is not the
        field's target type, is left out (a single link reads ``None``, a list keeps its order), a Pin's generic pair
        whose target is unseen or not of its ``element_type`` (read exact, nothing folded) reads ``""`` and ``None``,
        and a lens's ``x_lens.notes`` keeps the notes on its served anchors and on other ids the reader sees. Below
        co-builder and never on the
        public rung, ``x_served_trimmed`` names what the trim changed the meaning of: a Message's ``characters`` and
        ``narrator``, a lens's anchor fields and, when an anchor's note went with it, ``notes``; names only, never an
        id or a count."""
        for type_key, id_key in GENERIC_PAIRS.get(kind, ()):
            target, of = b.get(id_key), b.get(type_key)
            if not isinstance(target, str) or target == "":
                continue
            if not (isinstance(of, str) and self.served_as(target, of)):  # the type key exact, nothing folded
                if type_key in b:
                    b[type_key] = ""
                b[id_key] = None
        lens = is_lens(b)
        before = {i for f in _ANCHOR_FIELDS for i in (b.get(f) or []) if isinstance(i, str)} if lens else set()
        changed: list[str] = []
        targets = LINK_TARGETS.get(kind, {})
        for field, many in _LINK_FIELDS.get(kind, ()):
            if field not in b:
                continue
            v = b[field]
            target_type = targets.get(field)
            if many:
                if not isinstance(v, list):
                    continue
                if any(isinstance(t, str) and not self.served_as(t, target_type) for t in v):
                    changed.append(field)
                b[field] = [t for t in v if isinstance(t, str) and self.served_as(t, target_type)]
            elif isinstance(v, str) and v != "" and not self.served_as(v, target_type):  # "" names no id: as stored
                b[field] = None
                changed.append(field)
        named: tuple[str, ...] = _ANCHOR_FIELDS if lens else _MESSAGE_TRIMMED if is_message(b) else ()
        mark = [f for f in named if f in changed]
        x = b.get("x_lens")
        if lens and isinstance(x, dict) and isinstance(x.get("notes"), dict):
            served = {i for f in _ANCHOR_FIELDS for i in (b.get(f) or []) if isinstance(i, str)}
            gone = before - served
            notes: dict[str, Any] = x["notes"]
            kept = {k: v for k, v in notes.items() if k in served or (k not in gone and k in self.linkable)}
            if len(kept) != len(notes):
                b["x_lens"] = {**x, "notes": kept}
                if any(k in gone for k in notes):
                    mark.append("notes")
        if mark and self.seen_rung != "public":
            b["x_served_trimmed"] = mark

    def reach(
        self, start: Iterable[str], excluded: Callable[[str], bool], stops: Callable[[str], bool] | None = None
    ) -> tuple[set[str], list[str]]:
        """One hop from each element of ``start``, both ways, and on through each Relation it lands on to that
        Relation's parties. Nothing hops out of a stub or a room element, nor out of an element ``stops`` names.
        Gives what it reached and the Relations that carried the hop."""
        landed: set[str] = set()
        for f in start:
            if f in self.stubs or f in self.room or (stops is not None and stops(f)):
                continue
            for t in [*self.links(f), *self._in_view.get(f, [])]:
                if not excluded(t):
                    landed.add(t)
        reached = set(landed)
        edges: list[str] = []
        for r in landed:
            if self.type_of[r] != "relation" or r in self.stubs or r in self.room:
                continue
            edges.append(r)
            for t in self.links(r):
                if not excluded(t):
                    reached.add(t)
        return reached, edges

    def unseen(self, start: Sequence[str], edges: Sequence[str], excluded: Callable[[str], bool]) -> set[str]:
        """What one hop from ``start`` would reach in the owner's world that this reader's view leaves out (the
        owner's count)."""
        out: set[str] = set()

        def consider(t: str) -> None:
            if t in self.by_id and t not in self.view and not excluded(t):
                out.add(t)

        for f in start:
            if f in self.stubs or f in self.room:
                continue
            for t in self.full_links(f):
                consider(t)
            for t in self._in_full.get(f, []):
                consider(t)
        for r in edges:
            for t in self.full_links(r):
                consider(t)
        return out

    def _date(self, eid: str) -> tuple[bool, int | None]:
        field = DATE_FIELD.get(self.type_of[eid])
        if field is None:
            return False, None
        return True, _whole(self.by_id[eid].get(field))

    def fence_cut(self, eid: str, recipe: _Recipe) -> CutReason | None:
        """The fence (keel's ``as_of``, on the element's own date) and ``undated``."""
        dated, d = self._date(eid)
        if not dated:
            return None
        if d is None:
            return "undated" if recipe.undated == "exclude" else None
        return "after_as_of" if self.as_of is not None and d > self.as_of else None

    def window_cut(self, eid: str, recipe: _Recipe) -> CutReason | None:
        """``window``, or ``from`` and ``to`` (closed-open). A ``to`` after ``as_of`` is clipped: the fence stays the
        upper edge, so an element dated ``as_of`` is kept, and every element such a ``to`` would cut is already cut
        by the fence (``after_as_of``, counted first)."""
        _, d = self._date(eid)
        if d is None:
            return None
        if recipe.window is not None and self.as_of is not None and d < self.as_of - recipe.window:
            return "window"
        if recipe.from_ is not None and d < recipe.from_:
            return "window"
        if recipe.to is not None and d >= recipe.to:
            return "window"
        return None

    def stale_cut(self, eid: str, recipe: _Recipe, wall: tuple[int, int]) -> CutReason | None:
        """``changed_within``: changed longer ago than that many days before the reading's wall clock. The time read
        is the element's ``updated_at``, or for a folder element (one carrying ``server_updated_at`` or
        ``local_updated_at``) the newer of those two; an element with no readable time is never cut."""
        if recipe.changed_within is None:
            return None
        at = _changed_at(self.by_id[eid])
        if at is None:
            return None
        return "stale" if at < (wall[0] - recipe.changed_within * 86400, wall[1]) else None

    def kept(self, eid: str, recipe: _Recipe) -> bool:
        """Whether ``types`` keeps the element: a room element or a reading aid only when its pair is named, any
        other by its type (or any type when ``types`` is empty)."""
        if eid in self.room:
            el = self.by_id[eid]
            return recipe.types is not None and f"{_fold(el['type'])}/{_fold(el['supertype'])}" in recipe.types
        aid = self.aid.get(eid)
        if aid is not None:
            return recipe.types is not None and aid in recipe.types
        return recipe.types is None or self.type_of[eid] in recipe.types

    def stops_at(self, eid: str, recipe: _Recipe) -> bool:
        """Rule 4: a reading aid a hop reached is not hopped out of unless ``types`` names its pair."""
        aid = self.aid.get(eid)
        return aid is not None and not (recipe.types is not None and aid in recipe.types)

    def sort(self, ids: Iterable[str]) -> list[str]:
        """Rule 5's order past the anchors: the schema's type order, newest ``updated_at`` first (an unreadable
        time last), then by id (by code point)."""

        def key(eid: str) -> tuple[int, int, int, int, str]:
            unreadable, seconds, micros = _instant(self.by_id[eid].get("updated_at"))
            return (_TYPE_RANK[self.type_of[eid]], unreadable, -seconds, -micros, eid)

        return sorted(ids, key=key)

    def row(self, eid: str, show: str, notes: Mapping[str, Any] | None) -> dict[str, Any]:
        b = self.body(eid)
        row: dict[str, Any]
        if show == "full":
            row = copy.deepcopy(b)
        else:
            row = {"id": b.get("id"), "type": b.get("type"), "name": b.get("name")}
            description = b.get("description")
            if show == "first_line" and isinstance(description, str):
                m = _LINE_BREAK.search(description)
                row["description"] = description if m is None else description[: m.start()]
        if notes is not None and eid in notes:
            row["note"] = notes[eid]
        return row


def _anchors_of(lens: Mapping[str, Any], r: _Reading) -> tuple[list[str], list[str], set[str], bool]:
    """The anchors and the umbrella's children of a lens, in its link order, and whether it names any.

    A child is a lens in ``constructs`` the reader sees whole; one it knows only as a stub serves no recipe
    and no links, so it is an anchor the reader cannot see (``unseen``), never entered (keel's ``_anchors``).
    An id that names no element of the world, or an element of another type than its field's, is one too.
    """
    anchors: list[str] = []
    children: list[str] = []
    unseen: set[str] = set()
    seen: set[str] = set()
    targets = LINK_TARGETS["construct"]
    for field in _ANCHOR_FIELDS:
        v = lens.get(field)
        if not isinstance(v, list):
            continue
        for i in v:
            if not isinstance(i, str) or i == "" or i in seen:
                continue
            seen.add(i)
            if field == "constructs" and i in r.view and is_lens(r.by_id[i]):
                if i not in r.stubs:
                    children.append(i)
                    continue
                unseen.add(i)
            if r.type_of.get(i) != targets[field]:
                unseen.add(i)
            anchors.append(i)
    mark = lens.get("x_served_trimmed")
    trimmed = isinstance(mark, list) and any(isinstance(f, str) and f in _ANCHOR_FIELDS for f in mark)
    return anchors, children, unseen, bool(seen) or trimmed


def _resolve_one(
    lens: Mapping[str, Any], recipe: _Recipe, r: _Reading, visited: set[str], clock: tuple[int, int, int]
) -> tuple[list[str], dict[str, CutReason], LensMail | None]:
    """One lens by its own recipe, its children entered once each through the shared visited set: its kept ids
    (after its own mail rule and its own budget), the reason each element it left out was cut, and its mail part.

    An anchor is kept and followed whatever ``types``, ``window`` and ``changed_within`` say (a reading aid too; a
    room element is kept and not followed); what a hop or a filter reaches is cut by the fence, then ``types``, then
    the window, then ``changed_within``, against ``clock``, the reading's wall clock. Nothing is hopped out of an
    element the fence cuts ``after_as_of``, an anchor among them (rule 8). Each child keeps at most its own
    ``budget`` and loses its own mail rule's messages, uncounted, before its kept joins the union in link order
    (rule 3); the union drops an element only by its id, so a sibling lens a child's hop reached stays an
    element. The rows are made once, by the caller, from the lens read."""
    wall = (clock[1], clock[2])
    cut: dict[str, CutReason] = {}

    def add_cut(eid: str, why: CutReason) -> None:
        cut.setdefault(eid, why)

    anchors, children, unseen, anchored = _anchors_of(lens, r)
    anchor_set = set(anchors)
    listed: list[str] = []
    frontier: list[str] = []
    for eid in anchors:
        # Rule 6 before the visited check: an anchor the reader cannot see is counted, the lens's own id included.
        if eid not in r.view or eid in unseen:
            add_cut(eid, "anchor_not_visible")
            continue
        if eid in visited:
            continue
        why = r.fence_cut(eid, recipe)
        if why != "after_as_of":
            frontier.append(eid)
        if why is not None:
            add_cut(eid, why)
        else:
            listed.append(eid)

    def passes(eid: str) -> bool:
        why = r.fence_cut(eid, recipe)
        if why is None and not r.kept(eid, recipe):
            why = "types"
        if why is None:
            why = r.window_cut(eid, recipe)
        if why is None:
            why = r.stale_cut(eid, recipe, wall)
        if why is not None:
            add_cut(eid, why)
        return why is None

    if not anchored:
        # A filter: every element of its types the reader can see; others are not selected and not counted.
        selected = [e for e in r.order if e in r.view and e not in visited and r.kept(e, recipe)]
        listed.extend(r.sort([e for e in selected if passes(e)]))
    elif recipe.depth >= 1:

        def excluded(eid: str) -> bool:
            return eid in anchor_set or eid in visited

        hop, edges = r.reach(frontier, excluded)
        listed.extend(r.sort([e for e in hop if passes(e)]))
        if r.owner:
            for eid in r.unseen(frontier, edges, excluded):
                add_cut(eid, "not_visible")
        if recipe.depth == 2:
            onward = [e for e in hop if r.fence_cut(e, recipe) != "after_as_of"]
            second, _ = r.reach(onward, lambda e: excluded(e) or e in hop, lambda e: r.stops_at(e, recipe))
            for eid in second:
                # Rule 4 stops a hop at a room element or a reading aid whose pair `types` does not name, so the
                # second hop never counts one.
                if (eid not in r.room and eid not in r.aid) or r.kept(eid, recipe):
                    add_cut(eid, "hops_not_served")
    for child in children:
        if child in visited:
            continue
        visited.add(child)
        body = r.by_id[child]
        read = _read_recipe(body.get("x_lens"))
        if isinstance(read, str) or is_template(body):
            continue
        sub, sub_cut, _ = _resolve_one(body, read, r, visited, clock)
        listed.extend(sub)
        for eid, why in sub_cut.items():
            add_cut(eid, why)
    mail: LensMail | None = None
    if recipe.mail != "none":
        mail = _mail_part(r, recipe.mail, recipe.budget, clock)
        in_mail = {*mail["unread"], *mail["read"]}
        listed = [e for e in listed if e not in in_mail]
    union = list(dict.fromkeys(listed))
    keep = union[: recipe.budget]
    for eid in union[recipe.budget :]:
        cut[eid] = "budget"
    for eid in keep:
        cut.pop(eid, None)
    return keep, cut, mail


def _mail_part(r: _Reading, mode: str, budget: int, clock: tuple[int, int, int]) -> LensMail:
    """The mail rule (the message profile's readers over the reader's view)."""
    if r.character is None:
        return {"unread": [], "read": [], "rows": [], "cut": {}, "totals": {"unread": 0, "read": 0}}
    in_view = [e for e in r.order if e in r.view]
    # Whole bodies only: a known-of stub serves no `characters`, so its recipients are unknown, never everyone
    # (keel's `_mail`).
    messages = [b for b in (r.body(e) for e in in_view if e not in r.stubs) if is_message(b)]
    relations = [r.body(e) for e in in_view if r.type_of[e] == "relation"]
    mark = read_mark_of(relations, r.character, r.members)
    mine = unread_for(messages, r.character, None, r.members)
    unread = {id(m) for m in unread_for(messages, r.character, mark, r.members)}
    lower = (clock[1] - _MAIL_SECONDS, clock[2])
    in_window = []
    for m in mine:
        unreadable, seconds, micros = _instant(m.get("created_at"))
        if not unreadable and (seconds, micros) >= lower:
            in_window.append(m)
    kept = in_window[max(0, len(in_window) - budget) :]
    cut: dict[str, int] = {}
    if len(in_window) > len(kept):
        cut["budget"] = len(in_window) - len(kept)
    if len(mine) > len(in_window):
        cut["window"] = len(mine) - len(in_window)
    return {
        "unread": [m["id"] for m in kept if id(m) in unread],
        "read": [m["id"] for m in kept if id(m) not in unread],
        "rows": [
            copy.deepcopy(m)
            if mode == "all" or id(m) in unread
            else {
                "id": m.get("id"),
                "name": m.get("name"),
                "narrator": m.get("narrator"),
                "created_at": m.get("created_at"),
            }
            for m in kept
        ],
        "cut": cut,
        "totals": {"unread": len(unread), "read": len(mine) - len(unread)},
    }


def _nothing(unreadable: str | None = None) -> LensReading:
    return {"kept": [], "rows": [], "cut": {}, "notes_ignored": 0, "mail": None, "unreadable": unreadable}


def _check_reader(reader: Any, where: str) -> None:
    if not isinstance(reader, Mapping) or reader.get("rung") not in _RUNGS:
        raise TypeError(
            f"{where}: a reader is a mapping whose rung is owner, contributor, guest or public; got {reader!r}."
        )
    if reader.get("as") is not None:
        _check_reader(reader["as"], f"{where}.as")


def resolve_lens(
    world: Mapping[str, Any],
    lens: Mapping[str, Any] | str,
    reader: Mapping[str, Any],
    *,
    as_of: int | None = None,
    clock: str | None = None,
) -> LensReading:
    """Resolve a lens for one reader over a world snapshot (schema-dist ``profiles/lens.md``): the kept elements
    in the profile's order, the cut counted by reason, and, when the lens names a mail rule, the mail part. Pure:
    it never writes, and nothing in the world moves.

    ``world`` holds the elements as the owner is served them (``elements``), the ids its hidden mark keeps
    (``hidden``, beside each element's own ``hidden``), its ``members`` for the mail rule and its now (``now``,
    else the World's ``time_current`` as a folder spells it, else ``time_range_current`` as the API serves it).
    ``lens`` is a lens body or the id of a lens in the world the reader can
    see. ``reader`` is a mapping: ``rung`` (``owner``, ``contributor``, ``guest`` with its ``whole`` and
    ``known_of`` ids, or ``public``), ``character`` (for the mail rule), and on an owner ``as``, the reader it
    reads as (that reader's view, the owner's two counts). ``as_of`` is the reading's date (absent: the world's
    now; none at all: no fence, and the window cuts nothing), ``clock`` the reading's wall-clock time for the mail
    rule's thirty days and ``changed_within`` (absent: the machine's time), never the world's now.

    The rules, in short: visibility first (a hidden or proposed element is not there to hop through; a known-of
    stub is kept as served, its base and public fields with every other field unset, and nothing hops out of it);
    a hop reaches both ways, and on through a Relation to its parties, and a link reaches only an element of its
    field's target type (a generic pair only by one of the 22 slugs, compared exact); an umbrella enters each child
    lens once; a hop never crosses a room element; a reading aid (the charter, its guide, a domain:
    ``is_charter_element``) a hop reaches is kept, and hopped on from, only when ``types`` names its pair, while one
    the lens names as an anchor is kept and followed; anchors first in link order, then by type in the schema's
    order, newest first, then by id; an anchor the reader cannot see (one of no element, or of another type than
    its field's, among them) is never kept, counted for the owner as ``anchor_not_visible``; a template resolves to
    nothing; the fence is ``as_of`` on each element's own date; ``changed_within`` cuts what a hop or a filter
    reaches that changed longer ago than that many days before ``clock`` (``stale``), never an anchor. A value
    outside the profile's table makes the lens unreadable: ``unreadable`` names the key and nothing is resolved.
    The npm SDK's ``resolveLens`` gives the same answer on the same input."""
    if not isinstance(world, Mapping) or not isinstance(world.get("elements"), list):
        raise TypeError("resolve_lens: world is a mapping with an elements list.")
    _check_reader(reader, "resolve_lens: reader")
    if as_of is not None and _whole(as_of) is None:
        raise TypeError(f"resolve_lens: as_of is a whole number; got {as_of!r}.")
    if clock is not None and _instant(clock)[0]:
        raise TypeError(f"resolve_lens: clock is a date-time; got {clock!r}.")
    if not isinstance(lens, str | Mapping):
        raise TypeError("resolve_lens: lens is a lens body or its id.")
    return _lens_reading(_Reading(world, reader, _reading_date(world, as_of)), lens, clock)[0]


def _reading_date(world: Mapping[str, Any], as_of: int | None) -> int | None:
    """The reading's date: ``as_of``, else the world's now (the fixture's ``now``, else the World's
    ``time_current``). With none of them there is no fence, and the window cuts nothing."""
    when = _whole(as_of) if as_of is not None else _whole(world.get("now"))
    if when is None:
        when = _whole(world.get("time_current"))
    if when is None:
        when = _whole(world.get("time_range_current"))
    return when


def _lens_reading(
    r: _Reading, lens: Mapping[str, Any] | str, clock: str | None
) -> tuple[LensReading, dict[str, CutReason]]:
    """A lens read over one reading's world: the reading ``resolve_lens`` answers, and the reason each element
    it left out was cut, by id, before the counts drop the owner's two."""
    # An id is read only when the reader is served that element whole: a stub serves no links and no
    # recipe, so a lens known only as a stub reads as one the reader cannot see (keel's find_lens). A
    # body is read as given.
    body: Mapping[str, Any] | None = (
        (r.by_id[lens] if lens in r.view and lens not in r.stubs else None) if isinstance(lens, str) else lens
    )
    if body is None or not is_lens(body):
        return _nothing(), {}
    recipe = _read_recipe(body.get("x_lens"))
    if isinstance(recipe, str):
        return _nothing(recipe), {}
    if is_template(body):
        return _nothing(), {}

    # The reading's wall clock, read once: the mail rule's thirty days and ``changed_within`` both measure from it.
    instant = _instant(clock or datetime.now(UTC).isoformat())
    visited: set[str] = set()
    if isinstance(body.get("id"), str):
        visited.add(body["id"])
    keep, cut, mail = _resolve_one(body, recipe, r, visited, instant)
    counts: dict[str, int] = {}
    for why in _CUT_REASONS:
        if why in _OWNER_ONLY and not r.owner:
            continue
        n = sum(1 for w in cut.values() if w == why)
        if n:
            counts[why] = n
    anchors, _, _, _ = _anchors_of(body, r)
    # A note on an id that is not an anchor is counted only where the reader sees that id: a note keyed to an
    # element it cannot see, or to no element, is no note of its, and counting it would tell a guest it exists.
    notes_ignored = sum(1 for k in recipe.notes if k not in anchors and k in r.view)
    # The rows are made once, from the union, by this lens's `show`; a note captions this lens's own anchors only
    # (a child's notes and `show` stay the child's, rule 3).
    own = set(anchors)
    reading: LensReading = {
        "kept": keep,
        "rows": [r.row(e, recipe.show, recipe.notes if e in own else None) for e in keep],
        "cut": counts,
        "notes_ignored": notes_ignored,
        "mail": mail,
        "unreadable": None,
    }
    return reading, cut

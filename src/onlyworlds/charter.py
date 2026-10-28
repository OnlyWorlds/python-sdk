"""The charter profile (schema-dist ``profiles/charter.md``, serial 83): a world's reading aids at its door.

A world may carry three reading aids for whoever enters it, a person or an AI: the Charter (a Law with supertype
``Charter``: the rules here), the Guide (a Construct with supertype ``Guide``: start here) and the Domains
(Constructs with supertype ``Domain``: the places in the world, each one sentence and the hub elements it links).
An element is one when its pair (``READING_AID_PAIRS``, trimmed and folded as the room profile folds) AND the mark
``x_charter_of`` both hold (``is_charter_element``, the mark read by presence); the pair without the mark is lore.

``charter_of(world, reader)`` is the packet every front door shows first, ``{charter, guide, domains}`` as that
reader sees the world, and ``domains_of`` the list alone: keel serves the same packet as ``reading_aids`` beside
``front_door`` on ``GET /me`` and the join reply. Pure: nothing is stored or written. The world and the reader are
the lens reader's (``resolve_lens``): the elements as the owner is served them, the ids the hidden mark keeps, and a
reader by its rung; the view and each served body are that reader's, never a second copy. The fixture
(``codegen/schema-dist/profiles/charter.fixture.json``) is replayed whole by ``tests/test_charter.py``; the npm
SDK's ``charterOf`` and ``domainsOf`` give the same answers on the same input.
"""

from __future__ import annotations

import copy
import re
from collections.abc import Mapping
from typing import Any, TypedDict

from ._schema import LINK_TARGETS
from .checks import CHECKS_FIELD
from .lens import _check_reader, _Reading
from .message import _instant
from .room import _WHITE_SPACE, _fold

__all__ = [
    "SKILL_MAX",
    "CharterHub",
    "CharterPacket",
    "CharterRead",
    "DomainRead",
    "GuideRead",
    "charter_of",
    "domains_of",
]

#: At most this many skill Objects on the Charter (keel's ``charter_skill``, D152).
SKILL_MAX = 5

_ID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
"""An element id written anywhere in a text: in any ``ow://`` form, in a site address or bare (keel's ``_ID``)."""
_LINE_BREAK = re.compile(r"\r\n|\r|\n")
_HUB_FIELDS: tuple[tuple[str, str], ...] = tuple(LINK_TARGETS["construct"].items())
"""A Domain's link fields in the schema's order, each with the type it links: where its hubs are read."""


class CharterRead(TypedDict):
    """The world's Charter in a packet."""

    id: str
    name: str
    #: ``x_checks_rules`` as stored (the checks profile), ``[]`` when absent or null.
    rules: Any
    #: The Objects of this world the Charter's text names that the reader sees, each once, in the order written,
    #: at most ``SKILL_MAX``, lowercase.
    skill: list[str]


class GuideRead(TypedDict):
    """The world's Guide in a packet."""

    id: str
    name: str


class CharterHub(TypedDict):
    """One hub of a Domain: an element its link fields name."""

    type: str
    id: str


class DomainRead(TypedDict):
    """One Domain in a packet."""

    id: str
    name: str
    #: The description up to its first line break (a carriage return included), trimmed; ``""`` when none.
    sentence: str
    #: The distinct elements its served link fields name, itself excluded, in the schema's field order; a stub
    #: serves no links, so ``[]``.
    hubs: list[CharterHub]


class CharterPacket(TypedDict):
    """What ``charter_of`` answers."""

    charter: CharterRead | None
    guide: GuideRead | None
    domains: list[DomainRead]


def _newest(r: _Reading, ids: list[str]) -> str | None:
    """The newest by ``created_at`` compared as instants (none, or one that does not read as a time, sorts as the
    oldest), then the higher id by code point: so editing an aid never changes which one leads."""

    def key(eid: str) -> tuple[int, int, int, str]:
        unreadable, seconds, micros = _instant(r.by_id[eid].get("created_at"))
        return (0, 0, 0, eid) if unreadable else (1, seconds, micros, eid)

    return max(ids, key=key, default=None)


def _first_line(text: Any) -> str:
    """The lens profile's ``first_line``: trimmed, up to the first line break, trimmed again."""
    if not isinstance(text, str):
        return ""
    return _LINE_BREAK.split(text.strip(_WHITE_SPACE), maxsplit=1)[0].strip(_WHITE_SPACE)


def _skill(r: _Reading, text: Any) -> list[str]:
    """Keel's ``charter_skill``: every id the text names, lowercase, each once in the order written, kept when it is
    an Object of this world the reader sees, the first ``SKILL_MAX`` of those kept."""
    objects = {eid.lower() for eid in r.view if r.type_of[eid] == "object"}
    found: list[str] = []
    for m in _ID.finditer(text if isinstance(text, str) else ""):
        value = m.group(0).lower()
        if value not in found:
            found.append(value)
    return [i for i in found if i in objects][:SKILL_MAX]


def _hubs(eid: str, body: Mapping[str, Any]) -> list[CharterHub]:
    out: list[CharterHub] = []
    seen = {("construct", eid)}
    for field, target in _HUB_FIELDS:
        value = body.get(field)
        for i in value if isinstance(value, list) else [value]:
            if isinstance(i, str) and i != "" and (target, i) not in seen:
                seen.add((target, i))
                out.append({"type": target, "id": i})
    return out


def _name(value: Any) -> str:
    return value if isinstance(value, str) else ""


def charter_of(world: Mapping[str, Any], reader: Mapping[str, Any]) -> CharterPacket:
    """The world's reading aids as ``reader`` sees them (schema-dist ``profiles/charter.md``): ``{charter, guide,
    domains}``, what every front door shows first. Pure: nothing is stored or written.

    ``world`` holds the elements as the owner is served them (``elements``), the ids its hidden mark keeps
    (``hidden``, beside each element's own ``hidden``), and ``open: true`` for a world open to anyone; ``reader`` is
    the lens reader's (``rung`` ``owner``, ``contributor``, ``guest`` with its ``whole`` and ``known_of`` ids, or
    ``public``; on an owner, ``as`` the reader it reads as). A public reader of a world not open to anyone reads
    nothing.

    ``charter`` is the newest marked Charter the reader sees (by ``created_at`` as an instant, none the oldest, then
    the higher id), ``{id, name, rules, skill}``: ``rules`` its ``x_checks_rules`` as stored (``[]`` when none),
    ``skill`` the Objects its description names (any ``ow://`` form, a site address or a bare id) that the reader
    sees, each once in the order written, lowercase, at most five, as keel's ``charter_skill``. ``guide`` is the
    newest marked Guide the reader sees, ``{id, name}``. ``domains`` is every marked Domain the reader sees, ``{id,
    name, sentence, hubs}``: first in the order of the Guide's ``constructs`` as the reader is served them (an id
    named twice keeps its first place, an entry that is no marked Domain or one the reader cannot see is skipped),
    then the rest by folded name and then id. A Domain the reader knows only as a stub has its served name and
    sentence and no hubs; a hidden one is not there. Whether an element is an aid is read from the element as the
    owner is served it, since a stub serves no mark. The npm SDK's ``charterOf`` gives the same answer."""
    if not isinstance(world, Mapping) or not isinstance(world.get("elements"), list):
        raise TypeError("charter_of: world is a mapping with an elements list.")
    _check_reader(reader, "charter_of: reader")
    r = _Reading(world, reader, None)
    if r.seen_rung == "public" and world.get("open") is not True:
        return {"charter": None, "guide": None, "domains": []}

    def marked(pair: str) -> list[str]:
        return [e for e in r.order if e in r.view and r.aid.get(e) == pair]

    packet: CharterPacket = {"charter": None, "guide": None, "domains": []}
    law = _newest(r, marked("law/charter"))
    if law is not None:
        stored = r.by_id[law]
        rules = stored.get(CHECKS_FIELD)
        packet["charter"] = {
            "id": law,
            "name": _name(stored.get("name")),
            "rules": [] if rules is None else copy.deepcopy(rules),
            "skill": _skill(r, stored.get("description")),
        }
    guide = _newest(r, marked("construct/guide"))
    order: list[str] = []
    domains = marked("construct/domain")
    if guide is not None:
        packet["guide"] = {"id": guide, "name": _name(r.by_id[guide].get("name"))}
        listed = r.body(guide).get("constructs")
        for i in listed if isinstance(listed, list) else []:
            if i in domains and i not in order:
                order.append(i)
    rest = sorted((d for d in domains if d not in order), key=lambda d: (_fold(_name(r.by_id[d].get("name"))), d))
    for d in order + rest:
        body = r.body(d)
        packet["domains"].append(
            {
                "id": d,
                "name": _name(body.get("name")),
                "sentence": _first_line(body.get("description")),
                "hubs": [] if body.get("known_of") is True else _hubs(d, body),
            }
        )
    return packet


def domains_of(world: Mapping[str, Any], reader: Mapping[str, Any]) -> list[DomainRead]:
    """The Domains alone, as ``charter_of`` lists them for ``reader``."""
    return charter_of(world, reader)["domains"]

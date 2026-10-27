"""The address profile (schema-dist ``profiles/address.md``, serial 77): one element named by one triple.

The world's id, the type word and the element's id, in three spellings: the site's address
(``https://www.onlyworlds.com/w/<world>/<type>/<id>``), the text form inside a world (``ow://<type>/<id>``)
and the text form across worlds (``ow://<world>/<type>/<id>``); a world by itself in two of them; an
optional moment (``@<step>``) and lens (``?lens=<id>``). ``element_address`` writes one, ``parse_ow_link``
reads one. The fixture, ``profiles/address.fixture.json``, is this module's own test, and the npm SDK's
``elementAddress`` and ``parseOwLink`` answer every string the same way.

The parser is written out by hand, never ``urllib.parse``: a URL parser lowercases the host, splits
userinfo and ports, and may decode, and the profile refuses or keeps each of those as written. Case is
ASCII case (A to Z) only, and nothing is percent-decoded.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal, NoReturn

from ._schema import ELEMENT_TYPES
from .room import _WHITE_SPACE

__all__ = [
    "AddressError",
    "AddressForm",
    "AddressReading",
    "AddressReason",
    "element_address",
    "parse_ow_link",
]

AddressForm = Literal["human", "text"]
"""The two forms of an address: the site's (``human``) and the ``ow://`` text forms (``text``)."""

AddressReason = Literal[
    "not_an_address",
    "uppercase",
    "segments",
    "bad_world",
    "unknown_type",
    "bad_id",
    "bad_moment",
    "bad_lens",
    "no_world",
    "bad_form",
]
"""Why an address was refused, by the profile's own names, in its order (``typing.get_args`` lists them).
``no_world`` and ``bad_form`` are the writer's only."""

_MESSAGES: dict[AddressReason, str] = {
    "not_an_address": "not an address: it starts with neither https://www.onlyworlds.com/w/ nor ow://",
    "uppercase": "an address is written in lowercase: the prefix or the type word is in another case",
    "segments": "the wrong number of path segments, or an empty one: a type needs an id and an id a type",
    "bad_world": "the world is not an id (or, in the site's address only, a slug)",
    "unknown_type": "the type word is not one of the 22",
    "bad_id": "the element id is not a UUID in the hyphenated 8-4-4-4-12 form",
    "bad_moment": "the moment is not a whole step in decimal within the 32-bit range",
    "bad_lens": "the lens is not one lowercase lens key holding an id",
    "no_world": "this address needs a world",
    "bad_form": "the form is neither human nor text",
}


class AddressError(ValueError):
    """An address was refused; nothing was read or written. ``reason`` names why, by the profile's name."""

    def __init__(self, reason: AddressReason, message: str | None = None):
        super().__init__(message or _MESSAGES[reason])
        self.reason: AddressReason = reason


@dataclass(frozen=True)
class AddressReading:
    """What ``parse_ow_link`` reads from a string. Hex is given lowercase; ``type`` and ``id`` are None for a
    world's own address. ``world`` is the world's id or, in the site's form only, its slug (``world_is_slug``,
    never canonical); None in the text form inside a world. ``canonical`` is True when the string as received
    is exactly what ``element_address`` writes for this reading."""

    form: AddressForm
    world: str | None
    world_is_slug: bool
    type: str | None
    id: str | None
    lens: str | None
    moment: int | None
    canonical: bool


def _refuse(reason: AddressReason) -> NoReturn:
    raise AddressError(reason)


_HUMAN_PREFIX = "https://www.onlyworlds.com/w/"
_TEXT_PREFIX = "ow://"
_TYPES = frozenset(ELEMENT_TYPES)
_UUID = re.compile(r"[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}")
_SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
_STEP = re.compile(r"0|-?[1-9][0-9]*")
_STEP_MIN = -2147483648
_STEP_MAX = 2147483647
_ADDRESS_KEYS = ("form", "world", "type", "id", "lens", "moment", "world_is_slug", "canonical")
_ASCII_LOWER = {c: c + 32 for c in range(ord("A"), ord("Z") + 1)}


def _ascii_lower(s: str) -> str:
    """A to Z lowered, nothing else: the profile's case is ASCII's, so no Unicode table decides it."""
    return s.translate(_ASCII_LOWER)


def _is_uuid(s: str) -> bool:
    return _UUID.fullmatch(s) is not None


def _is_slug(s: str) -> bool:
    return 3 <= len(s) <= 40 and _SLUG.fullmatch(s) is not None


def _check_type(word: str) -> str:
    """The type word as given, or ``uppercase`` for one of the 22 in another case, else ``unknown_type``."""
    if word in _TYPES:
        return word
    _refuse("uppercase" if _ascii_lower(word) in _TYPES else "unknown_type")


def _write(
    form: str, world: str | None, type_: str | None, id_: str | None, moment: int | None, lens: str | None
) -> str:
    """The string a writer writes; every part already checked, hex already lowercase."""
    parts = [world] if world is not None else []
    if type_ is not None and id_ is not None:
        parts += [type_, id_]
    out = (_HUMAN_PREFIX if form == "human" else _TEXT_PREFIX) + "/".join(parts)
    if moment is not None:
        out += f"@{moment}"
    if lens is not None:
        out += f"?lens={lens}"
    return out


def _moment(value: Any) -> int:
    """A step as a writer takes it: a whole number in range (an integral float too: JavaScript has one number)."""
    if isinstance(value, bool):
        _refuse("bad_moment")
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    if not isinstance(value, int) or not _STEP_MIN <= value <= _STEP_MAX:
        _refuse("bad_moment")
    return value


def element_address(address: Mapping[str, Any] | AddressReading) -> str:
    """An address as the profile writes it: lowercase throughout, the world's id (never its slug), the moment
    before the lens, nothing else.

    ``address`` is a form and a triple (``{"form": "text", "world": ..., "type": ..., "id": ...}``; no
    ``world`` for the text form inside a world), or a form and a world alone for the world's own address;
    ``lens`` and ``moment`` optional; absent and None are the same. An ``AddressReading`` is taken as it
    stands, so ``element_address(parse_ow_link(s))`` is the canonical spelling of ``s`` (a slug refuses).

    Raises ``AddressError`` (``reason``): ``bad_form``, ``segments`` (a type without an id or an id without a
    type), ``no_world`` (the site's form, or a world's own text form, with no world), ``bad_world`` (not an
    id: a slug too), ``uppercase`` / ``unknown_type``, ``bad_id``, ``bad_moment`` (not a whole number in the
    32-bit range), ``bad_lens``, in that order. A key it does not know is a ``TypeError``.
    """
    a: Mapping[str, Any]
    if isinstance(address, AddressReading):
        a = {k: getattr(address, k) for k in _ADDRESS_KEYS}
    elif isinstance(address, Mapping):
        a = address
    else:
        raise TypeError("element_address: the address is a mapping (form, world, type, id, lens, moment)")
    for key in a:
        if key not in _ADDRESS_KEYS:
            raise TypeError(f"element_address: unknown key {key!r}. The keys are {', '.join(_ADDRESS_KEYS)}.")
    form = a.get("form")
    if not isinstance(form, str) or form not in ("human", "text"):
        _refuse("bad_form")
    raw_world, raw_type, raw_id = a.get("world"), a.get("type"), a.get("id")
    has_type, has_id = raw_type is not None, raw_id is not None
    if has_type != has_id:
        _refuse("segments")
    if raw_world is None and (form == "human" or not has_type):
        _refuse("no_world")
    world: str | None = None
    if raw_world is not None:
        if not isinstance(raw_world, str) or not _is_uuid(raw_world):
            _refuse("bad_world")
        world = raw_world.lower()
    type_: str | None = None
    id_: str | None = None
    if has_type:
        type_ = _check_type(raw_type) if isinstance(raw_type, str) else _refuse("unknown_type")
        if not isinstance(raw_id, str) or not _is_uuid(raw_id):
            _refuse("bad_id")
        id_ = raw_id.lower()
    moment = None if a.get("moment") is None else _moment(a.get("moment"))
    lens: str | None = None
    raw_lens = a.get("lens")
    if raw_lens is not None:
        if not isinstance(raw_lens, str) or not _is_uuid(raw_lens):
            _refuse("bad_lens")
        lens = raw_lens.lower()
    return _write(form, world, type_, id_, moment, lens)


def _read_lens(query: str) -> str | None:
    """The value of the one ``lens`` key, or None without one. A key that is ``lens`` in another case, a second
    one, or a value that is not an id refuses."""
    lens: str | None = None
    seen = False
    for part in query.split("&"):
        key, eq, value = part.partition("=")
        if _ascii_lower(key) != "lens":
            continue  # another key: ignored (and the address is not canonical)
        if key != "lens" or seen:
            _refuse("bad_lens")
        seen = True
        if not eq or not _is_uuid(value):
            _refuse("bad_lens")
        lens = value.lower()
    return lens


def parse_ow_link(text: str) -> AddressReading:
    """One string read whole as an address (a link inside other text is the caller's to find first).

    The checks run in the profile's order and the first that fails names the refusal, as an ``AddressError``
    with ``reason``: trim (Unicode White_Space), the prefix (``uppercase`` for one in another case, else
    ``not_an_address``; a value that is not a string is ``not_an_address`` too), drop a fragment, split off
    the query at the first ``?``, split the path on ``/``, the last segment at its first ``@``; then
    ``segments``, ``bad_world``, ``unknown_type`` / ``uppercase``, ``bad_id``, ``bad_moment``, ``bad_lens``.

    Another query key and a fragment are ignored and make the reading not canonical; nothing is
    percent-decoded. The site's form takes a slug for the world (``world_is_slug``, never canonical); the text
    forms take the id only. Ids are read in either case of hex and given lowercase.
    """
    if not isinstance(text, str):
        _refuse("not_an_address")
    s = text.strip(_WHITE_SPACE)
    form: AddressForm
    if s.startswith(_HUMAN_PREFIX):
        form, rest = "human", s[len(_HUMAN_PREFIX) :]
    elif s.startswith(_TEXT_PREFIX):
        form, rest = "text", s[len(_TEXT_PREFIX) :]
    else:
        lowered = _ascii_lower(s)
        _refuse(
            "uppercase" if lowered.startswith(_HUMAN_PREFIX) or lowered.startswith(_TEXT_PREFIX) else "not_an_address"
        )
    rest = rest.partition("#")[0]
    path, has_query, query = rest.partition("?")
    segments = path.split("/")
    base, has_step, step = segments[-1].partition("@")
    segments[-1] = base

    n = len(segments)
    if (n not in (1, 3)) if form == "human" else not 1 <= n <= 3:
        _refuse("segments")
    if any(seg == "" for seg in segments):
        _refuse("segments")
    if n == 1 and segments[0] in _TYPES:
        _refuse("segments")

    world: str | None = None
    world_is_slug = False
    if n != 2:
        w = segments[0]
        if _is_uuid(w):
            world = w.lower()
        elif form == "human" and _is_slug(w) and w not in _TYPES:
            world, world_is_slug = w, True
        else:
            _refuse("bad_world")
    type_: str | None = None
    id_: str | None = None
    if n != 1:
        type_ = _check_type(segments[n - 2])
        if not _is_uuid(segments[n - 1]):
            _refuse("bad_id")
        id_ = segments[n - 1].lower()
    moment: int | None = None
    if has_step:
        if _STEP.fullmatch(step) is None or len(step) > 11:
            _refuse("bad_moment")
        moment = int(step)
        if not _STEP_MIN <= moment <= _STEP_MAX:
            _refuse("bad_moment")
    lens = _read_lens(query) if has_query else None
    canonical = not world_is_slug and text == _write(form, world, type_, id_, moment, lens)
    return AddressReading(form, world, world_is_slug, type_, id_, lens, moment, canonical)

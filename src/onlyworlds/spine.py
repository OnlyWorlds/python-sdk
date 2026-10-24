"""The spine profile (schema-dist ``profiles/spine.md``, serial 60): a world that maps a software ecosystem.

A spine world describes what is built, the contracts it speaks, where each thing lives, who keeps it and
what it depends on, in the 22 types and nothing more. Each kind is a type with a supertype from a closed
list (``SPINE_KINDS``, generated from the pinned dist: ``Tool``, ``Service`` and nine more on an Object,
``Repo`` and six more on a Location, ...); a Character, an Institution and a Collective take any supertype
(``SPINE_FREE_TYPES``). Thirteen ``x_spine_*`` keys (``SPINE_KEYS``) carry what no schema field holds
(two of them, ``x_spine_owner`` and ``x_spine_projection``, only on a projection; one, ``x_spine_retires``,
only on a Retirement Event). Ownership is the standard's (a Title with supertype ``Seat`` lists what it
keeps), so no key on a row names its owner (on a projection, ``x_spine_owner`` does: the keeping Seat's
name, serial 58).

``read_spine_element(type, element)`` reads one element as the profile's conforming reader does and
returns a ``SpineRead``: its kind (the list's spelling, ``"off-list"`` for a listed type whose supertype
is off its list or empty, and for every type the list does not name, ``"free"`` for the three free types),
each key as read or ``None`` when not stated, the audience's primary, the probe's verb (or
``"unsupported"``), the verified date, and every value it left out, named in ``dropped`` as
``{"key", "value"}`` with the value exactly as the element held it (compared as JSON values, never as
text: Python and JavaScript write JSON differently). A probe's verb is syntax, matched as written
(case-sensitive, single spaces), after the outer trim. A supertype and
every machine value is compared trimmed and without regard to case as the room profile defines it
(Unicode White_Space at both ends, Unicode simple case folding: ``room._fold``), never ``str.strip()``
or ``str.casefold()``. An ``x_spine_`` key the reader does not know is ignored, never an error.

What one element cannot say is the world's audit, not this reader's (the doctor's flag 13 does it): a
row kept by exactly one Seat, whether a ``x_spine_depends_on`` id resolves, a ``legacy`` or ``provenance``
row's Retirement Event naming it in ``x_spine_retires`` and linking it, a row still at ``gone``, a row's
name unique within its row type once folded, and a projection's three. Nor does it read
``x_spine_probed`` (the probe gate's), ``x_spine_owner`` (a projection's only), ``x_spine_projection`` (a
projection's World's) or ``x_spine_retires`` (a Retirement Event's, the audit's structural attribution of
a retirement: the page's conformance read of one element, and its fixture, carry no such key), and it
never runs a probe. A spine counts days from
day 0 (2012-01-01) through a Construct with supertype ``Calendar`` whose ``atlas_calendar`` the profile
ships; this package has no calendar kernel, so the fixture's calendar steps are checked by the npm SDK's
kernel (4.70.0), not here. The fixture (``codegen/schema-dist/profiles/spine.fixture.json``) is replayed
whole by ``tests/test_spine.py``.
"""

from __future__ import annotations

import copy
import datetime
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from ._schema import SPINE_KINDS
from .folder import FolderElement
from .room import _WHITE_SPACE, _fold

__all__ = [
    "SPINE_ACCESS",
    "SPINE_AUDIENCE",
    "SPINE_FREE",
    "SPINE_FREE_TYPES",
    "SPINE_KEYS",
    "SPINE_KINDS",
    "SPINE_LAYERS",
    "SPINE_OFF_LIST",
    "SPINE_PREFIX",
    "SPINE_PROBE_VERBS",
    "SPINE_STATUSES",
    "SpineRead",
    "read_spine_element",
]

#: The profile's reserved prefix: every key it defines starts with it.
SPINE_PREFIX = "x_spine_"
#: The thirteen keys the profile defines, in the page's table order (serial 60 adds ``x_spine_retires``).
#: ``read_spine_element`` reads nine; ``x_spine_probed`` is the probe gate's, ``x_spine_owner``,
#: ``x_spine_projection`` and ``x_spine_retires`` the world's audit's.
SPINE_KEYS: tuple[str, ...] = (
    "x_spine_address",
    "x_spine_truth",
    "x_spine_access",
    "x_spine_status",
    "x_spine_layer",
    "x_spine_audience",
    "x_spine_depends_on",
    "x_spine_probe",
    "x_spine_probed",
    "x_spine_owner",
    "x_spine_projection",
    "x_spine_retires",
    "x_spine_verified",
)
#: The kind of an element of a listed type whose supertype is off its list or empty, and of a type the list
#: does not name.
SPINE_OFF_LIST = "off-list"
#: The kind of a Character, an Institution or a Collective: drawn by their type, any supertype.
SPINE_FREE = "free"
#: The three types that take any supertype.
SPINE_FREE_TYPES: tuple[str, ...] = ("character", "institution", "collective")
#: ``x_spine_access``: one of these.
SPINE_ACCESS: tuple[str, ...] = ("public", "members-only", "crew-only", "private")
#: ``x_spine_status``: one of these.
SPINE_STATUSES: tuple[str, ...] = ("live", "legacy", "provenance", "gone")
#: ``x_spine_layer``: one of these.
SPINE_LAYERS: tuple[str, ...] = ("standard", "platform", "interface", "client", "docs", "community", "crew")
#: ``x_spine_audience``: an ordered list from these, the primary first.
SPINE_AUDIENCE: tuple[str, ...] = ("stranger", "builder", "player", "agent", "crew")
#: The probe form's verbs, in the page's order (closed: a new verb is a new serial).
SPINE_PROBE_VERBS: tuple[str, ...] = ("http", "gh repo", "gh release", "npm", "pypi", "dns", "room", "file", "none")

# One token of the probe form: no White_Space inside (the trim's 25 code points, not ``\S``'s).
_TOKEN = f"[^{re.escape(_WHITE_SPACE)}]+"
_PROBE_FORMS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("http", re.compile(f"http GET {_TOKEN} expect [0-9]{{3}}")),
    ("gh repo", re.compile(f"gh repo {_TOKEN}/{_TOKEN}")),
    ("gh release", re.compile(f"gh release {_TOKEN}/{_TOKEN}")),
    ("npm", re.compile(f"npm {_TOKEN}")),
    ("pypi", re.compile(f"pypi {_TOKEN}")),
    ("dns", re.compile(f"dns {_TOKEN} {_TOKEN}")),
    ("room", re.compile(f"room {_TOKEN}")),
    ("file", re.compile("file .+")),
    ("none", re.compile("none .+")),
)
_DATE = re.compile(r"([0-9]{4}-[0-9]{2}-[0-9]{2})(T.*)?", re.DOTALL)


@dataclass(frozen=True)
class SpineRead:
    """What a conforming reader says of one element (the fixture's ``read`` block, ``as_dict()``).

    ``kind`` is the list's spelling, ``SPINE_OFF_LIST`` or ``SPINE_FREE``. Every other field is ``None``
    when its key is not stated. ``address``, ``audience`` and ``depends_on`` keep the value's order;
    ``access``, ``status``, ``layer`` and each audience word are the list's spelling; ``truth`` and
    ``verified_at`` are the value as written (``verified_at`` trimmed). ``primary`` is the audience's
    first known word, ``probe`` the probe's verb or ``"unsupported"``. ``dropped`` names each value left
    out as ``{"key": <the x_spine_ key>, "value": <the value as the element held it>}``, in key order
    address, truth, access, status, layer, audience, depends_on, probe, verified (within a list, the
    list's order)."""

    kind: str
    address: tuple[str, ...] | None = None
    truth: str | None = None
    access: str | None = None
    status: str | None = None
    layer: str | None = None
    audience: tuple[str, ...] | None = None
    primary: str | None = None
    depends_on: tuple[str, ...] | None = None
    probe: str | None = None
    verified_at: str | None = None
    dropped: tuple[dict[str, Any], ...] = ()

    def as_dict(self) -> dict[str, Any]:
        """The fixture's shape: tuples as lists, ``None`` kept."""

        def listed(value: tuple[str, ...] | None) -> list[str] | None:
            return None if value is None else list(value)

        return {
            "kind": self.kind,
            "address": listed(self.address),
            "truth": self.truth,
            "access": self.access,
            "status": self.status,
            "layer": self.layer,
            "audience": listed(self.audience),
            "primary": self.primary,
            "depends_on": listed(self.depends_on),
            "probe": self.probe,
            "verified_at": self.verified_at,
            "dropped": [dict(entry) for entry in self.dropped],
        }


def _named(key: str, value: Any) -> dict[str, Any]:
    return {"key": key, "value": copy.deepcopy(value)}


def _one_of(value: Any, words: tuple[str, ...]) -> str | None:
    """The list's word the value folds to, or None (not a string, or off the list)."""
    if not isinstance(value, str):
        return None
    folded = _fold(value)
    return next((w for w in words if _fold(w) == folded), None)


def _kind(element_type: str, supertype: Any) -> str:
    folded_type = _fold(element_type)
    if folded_type in SPINE_FREE_TYPES:
        return SPINE_FREE
    if not isinstance(supertype, str):
        return SPINE_OFF_LIST
    return _one_of(supertype, SPINE_KINDS.get(folded_type, ())) or SPINE_OFF_LIST


def _probe_verb(probe: str) -> str:
    text = probe.strip(_WHITE_SPACE)
    return next((verb for verb, form in _PROBE_FORMS if form.fullmatch(text)), "unsupported")


def _verified_at(value: Any) -> str | None:
    """``at`` trimmed when it is an ISO date (a real day, optionally followed by a ``T`` time), else None."""
    if not isinstance(value, Mapping) or not isinstance(value.get("at"), str):
        return None
    at: str = value["at"].strip(_WHITE_SPACE)
    m = _DATE.fullmatch(at)
    if not m:
        return None
    try:
        datetime.date.fromisoformat(m[1])
    except ValueError:
        return None
    return at


def read_spine_element(type: str, element: Mapping[str, Any] | FolderElement) -> SpineRead:
    """Read one element of the given type (a slug, compared trimmed and without regard to case) under the
    spine profile. Takes a body (an API element or a folder file's dict) or a ``FolderElement`` (its body
    is read; ``type`` is the caller's). Never raises on the element's values and never writes: a value it
    cannot read is not stated, and named in ``dropped`` when the profile says so.

    How each key reads (spine.md's table): ``x_spine_address`` a list whose non-empty strings are kept
    (a blank entry and a non-string are dropped; no entry left, or not a list, is not stated);
    ``x_spine_truth`` a string that is not blank (a non-string dropped); ``x_spine_access``, ``x_spine_status`` and
    ``x_spine_layer`` one of their lists; ``x_spine_audience`` a list whose known words are kept and the
    rest dropped, the primary the first known; ``x_spine_depends_on`` a list whose strings are kept, an
    empty list stated as empty (whether an id resolves is the world's audit); ``x_spine_probe`` a string
    in the probe form, or ``"unsupported"`` (a non-string dropped); ``x_spine_verified`` an object whose
    ``at`` is a real calendar day. A key
    that is absent or ``None`` is not stated and drops nothing.
    """
    body: Mapping[str, Any] = element.body if isinstance(element, FolderElement) else element
    dropped: list[dict[str, Any]] = []

    address: tuple[str, ...] | None = None
    raw = body.get("x_spine_address")
    if isinstance(raw, list):
        kept = [a for a in raw if isinstance(a, str) and a.strip(_WHITE_SPACE)]
        dropped += [_named("x_spine_address", a) for a in raw if not (isinstance(a, str) and a.strip(_WHITE_SPACE))]
        address = tuple(kept) or None
    elif raw is not None:
        dropped.append(_named("x_spine_address", raw))

    raw = body.get("x_spine_truth")
    truth = raw if isinstance(raw, str) and raw.strip(_WHITE_SPACE) else None
    if raw is not None and not isinstance(raw, str):
        dropped.append(_named("x_spine_truth", raw))

    one_of: dict[str, str | None] = {}
    for key, words in (
        ("x_spine_access", SPINE_ACCESS),
        ("x_spine_status", SPINE_STATUSES),
        ("x_spine_layer", SPINE_LAYERS),
    ):
        raw = body.get(key)
        one_of[key] = _one_of(raw, words)
        if one_of[key] is None and raw is not None:
            dropped.append(_named(key, raw))

    audience: tuple[str, ...] | None = None
    raw = body.get("x_spine_audience")
    if isinstance(raw, list):
        known: list[str] = []
        for word in raw:
            spelled = _one_of(word, SPINE_AUDIENCE)
            if spelled is None:
                dropped.append(_named("x_spine_audience", word))
            else:
                known.append(spelled)
        audience = tuple(known) or None
    elif raw is not None:
        dropped.append(_named("x_spine_audience", raw))

    depends_on: tuple[str, ...] | None = None
    raw = body.get("x_spine_depends_on")
    if isinstance(raw, list):
        depends_on = tuple(d for d in raw if isinstance(d, str))
        dropped += [_named("x_spine_depends_on", d) for d in raw if not isinstance(d, str)]
    elif raw is not None:
        dropped.append(_named("x_spine_depends_on", raw))

    raw = body.get("x_spine_probe")
    probe = _probe_verb(raw) if isinstance(raw, str) else None
    if raw is not None and not isinstance(raw, str):
        dropped.append(_named("x_spine_probe", raw))

    raw = body.get("x_spine_verified")
    verified_at = _verified_at(raw)
    if verified_at is None and raw is not None:
        dropped.append(_named("x_spine_verified", raw))

    return SpineRead(
        kind=_kind(type, body.get("supertype")) if isinstance(type, str) else SPINE_OFF_LIST,
        address=address,
        truth=truth,
        access=one_of["x_spine_access"],
        status=one_of["x_spine_status"],
        layer=one_of["x_spine_layer"],
        audience=audience,
        primary=audience[0] if audience else None,
        depends_on=depends_on,
        probe=probe,
        verified_at=verified_at,
        dropped=tuple(dropped),
    )

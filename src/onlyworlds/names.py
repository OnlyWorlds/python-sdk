"""The names profile (schema-dist ``profiles/names.md``): a world's own words for the 22 types, ``x_names``
on the World. A display lookup only: the API, the folder, the schema and every id keep the standard's
names. The fixture, ``profiles/names.fixture.json``, is this module's own test, as it is the npm SDK's
``typeWord``.

``type_word(world, type, supertype=, many=)`` reads ``world["x_names"]`` (a ``GET /world`` body or a
folder's ``world.json``) and answers the word to print, or None for the standard's name. The order: the
supertype's entry, matched trimmed and without regard to case (the room profile's one definition), then
the type's entry, then None. A map that is not a names map (not an object, ``version`` not 1, ``types`` or
``supertypes`` not objects, a ``supertypes`` value not an object) is None everywhere; a bad entry or an
unknown slug is ignored. The word is printed as written, never re-cased."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ._schema import ELEMENT_TYPES
from .room import _WHITE_SPACE, _fold

__all__ = ["type_word"]

_SLUGS = frozenset(ELEMENT_TYPES)


def _word(pair: Any, many: bool) -> str | None:
    """The word a pair prints, or None when the entry is ignored (no string ``one`` left after trimming)."""
    raw = pair.get("one") if isinstance(pair, Mapping) else None
    if not isinstance(raw, str):
        return None
    one = raw.strip(_WHITE_SPACE)
    if not one:
        return None
    if not many:
        return one
    plural = pair.get("many")
    plural = plural.strip(_WHITE_SPACE) if isinstance(plural, str) else ""
    return plural or one


def type_word(
    world: Mapping[str, Any] | None,
    element_type: str,
    *,
    supertype: str | None = None,
    many: bool = False,
) -> str | None:
    """The world's own word for ``element_type``, or None for the standard's name (print your usual label)."""
    names = world.get("x_names") if isinstance(world, Mapping) else None
    if not isinstance(names, Mapping) or names.get("version") != 1 or isinstance(names.get("version"), bool):
        return None
    types, supertypes = names.get("types"), names.get("supertypes")
    if types is not None and not isinstance(types, Mapping):
        return None
    if supertypes is not None and (
        not isinstance(supertypes, Mapping) or not all(isinstance(v, Mapping) for v in supertypes.values())
    ):
        return None
    if element_type not in _SLUGS:
        return None
    wanted = _fold(supertype) if isinstance(supertype, str) else ""
    if wanted and isinstance(supertypes, Mapping):
        for key, pair in (supertypes.get(element_type) or {}).items():
            if isinstance(key, str) and _fold(key) == wanted:
                found = _word(pair, many)
                if found is not None:
                    return found
    return _word(types.get(element_type), many) if isinstance(types, Mapping) else None

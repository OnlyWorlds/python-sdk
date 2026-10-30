"""The strand profile (schema-dist ``profiles/strand.md``, serial 98): a world in miniature, one story read off four
links the standard already has.

The World's mark ``x_strand`` is an object of three ids: the story (a Narrative), one of its ``events`` and one of
that Event's ``locations``. The hero is the story's ``protagonist`` and where the hero is now is the hero's
``location``. ``strand_of(world, reader)`` answers the six slots as that reader sees the world. Pure: nothing is
stored or written. The world and the reader are the lens reader's (``resolve_lens``): the elements as the owner is
served them, the ids the hidden mark keeps, and a reader by its rung; the view and each served body are that reader's,
never a second copy. The fixture (``codegen/schema-dist/profiles/strand.fixture.json``) is replayed whole by
``tests/test_strand.py``; the npm SDK's ``strandOf`` gives the same answers on the same input.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypedDict, TypeGuard

from .lens import _check_reader, _Reading

#: The World's field that carries the strand's mark.
STRAND_FIELD = "x_strand"


class StrandSlot(TypedDict):
    """A filled slot."""

    id: str
    name: str


class Strand(TypedDict):
    """A world's strand as one reader sees it: five slots and whether then and now are one place. An empty slot is
    None."""

    #: The story: the Narrative the mark names.
    narrative: StrandSlot | None
    #: The happening: the Event the mark names, when it is in the story's ``events``.
    event: StrandSlot | None
    #: The place, then: the Location the mark names, when it is in the event's ``locations``.
    location: StrandSlot | None
    #: The hero: the story's ``protagonist``.
    character: StrandSlot | None
    #: The place, now: the hero's ``location``.
    now: StrandSlot | None
    #: True when ``now`` and ``location`` are both filled and one place, False when two, None otherwise.
    same: bool | None


def _empty() -> Strand:
    return {"narrative": None, "event": None, "location": None, "character": None, "now": None, "same": None}


class _NoMark(Exception):
    pass


def _optional_id(value: Any) -> str | None:
    """A member the mark may leave unset: its id, None when it is None or absent; anything else is no mark."""
    if value is None:
        return None
    if isinstance(value, str) and value != "":
        return value
    raise _NoMark


def _mark(value: Any) -> tuple[str, str | None, str | None] | None:
    """The mark's ids, ``(narrative, event, location)``, or None when the value is not the profile's shape: a mapping
    whose ``narrative`` is a non-empty string, and whose ``event`` and ``location`` are each a non-empty string, None or
    absent (read as unset)."""
    if not isinstance(value, Mapping):
        return None
    story = value.get("narrative")
    if not isinstance(story, str) or story == "":
        return None
    try:
        return story, _optional_id(value.get("event")), _optional_id(value.get("location"))
    except _NoMark:
        return None


def strand_of(world: Mapping[str, Any], reader: Mapping[str, Any]) -> Strand:
    """A world's strand as ``reader`` sees it (schema-dist ``profiles/strand.md``): ``{narrative, event, location,
    character, now, same}``, each filled slot ``{id, name}`` and an empty one None. Pure.

    ``narrative`` is the element the mark names when it is a Narrative in the reader's view; with none, every slot is
    empty. ``event`` is the element the mark names when it is an Event in the reader's view and in the story's
    ``events`` as the reader is served them; ``location`` the element the mark names when it is a Location in the
    reader's view and in that event's ``locations``, empty when the event is. ``character`` is the story's
    ``protagonist`` when it is a Character in the reader's view; ``now`` the hero's ``location`` when it is a Location
    in the reader's view, empty when the hero is. ``same`` is True when ``now`` and ``location`` are both filled with
    one id, False when with two, else None. A list's order is never read, and no slot is filled from another: not the
    hero from the event's ``characters``, not ``location`` from ``now``, not ``now`` from ``location``. Only the story
    is required: ``event`` and ``location`` None or absent read as unset (a strand begun, its empty slots the next thing
    to make), and a place with no event is an empty place. A mark whose ``narrative`` is not a non-empty string, or
    whose ``event`` or ``location`` is anything but a non-empty string, None or absent, is no mark, and the strand is
    empty.

    ``world`` holds the elements as the owner is served them (``elements``), the ids its hidden mark keeps
    (``hidden``, beside each element's own ``hidden``), the World's ``x_strand``, and ``open: true`` for a world open
    to anyone; ``reader`` is the lens reader's (``rung`` ``owner``, ``contributor``, ``guest`` with its ``whole`` and
    ``known_of`` ids, or ``public``; on an owner, ``as`` the reader it reads as). A public reader of a world not open
    to anyone reads nothing. A slot's links are read from the body the reader is served, so a story known only as a
    stub fills its own slot and nothing past it."""
    if not isinstance(world, Mapping) or not isinstance(world.get("elements"), list):
        raise TypeError("strand_of: world is a mapping with an elements list.")
    _check_reader(reader, "strand_of: reader")
    out = _empty()
    mark = _mark(world.get(STRAND_FIELD))
    if mark is None:
        return out
    r = _Reading(world, reader, None)
    if r.seen_rung == "public" and world.get("open") is not True:
        return out

    def seen(eid: Any, kind: str) -> TypeGuard[str]:
        return isinstance(eid, str) and eid in r.view and r.type_of.get(eid) == kind

    def slot(eid: str) -> StrandSlot:
        name = r.body(eid).get("name")
        return {"id": eid, "name": name if isinstance(name, str) else ""}

    def listed(holder: str, field: str, eid: str) -> bool:
        v = r.body(holder).get(field)
        return isinstance(v, list) and eid in v

    story, event, place = mark
    if not seen(story, "narrative"):
        return out
    out["narrative"] = slot(story)
    if seen(event, "event") and listed(story, "events", event):
        out["event"] = slot(event)
        if seen(place, "location") and listed(event, "locations", place):
            out["location"] = slot(place)
    hero = r.body(story).get("protagonist")
    if seen(hero, "character"):
        out["character"] = slot(hero)
        now = r.body(hero).get("location")
        if seen(now, "location"):
            out["now"] = slot(now)
    if out["now"] is not None and out["location"] is not None:
        out["same"] = out["now"]["id"] == out["location"]["id"]
    return out

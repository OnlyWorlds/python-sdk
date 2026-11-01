"""What a lore view leaves an element out by, in the lens profile's graph section's words: the room, the hidden
mark, a proposal, map space and the reading aids. Each is read by the reader the lens and graph readers use
(``is_room_element``, ``is_hidden``, ``hands_on_as_proposed``, ``_reading_aid_key``, the type), so a menu that asks
"can this door open it" and ``world_graph`` that asks "is it a node" give one answer. The npm SDK's ``marks.ts``
reads the same. Module-internal.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .folder import is_hidden
from .review import hands_on_as_proposed
from .room import _fold, _reading_aid_key, is_room_element

#: The marks in the graph section's order.
ELEMENT_MARKS: tuple[str, ...] = ("room", "hidden", "proposed", "map_space", "reading_aid")

#: Map, Pin and Marker: the map space a lore view leaves out by default. A Zone is content.
MAP_SPACE = frozenset({"map", "pin", "marker"})


def marks_of(el: Mapping[str, Any]) -> list[str]:
    """The marks an element carries, in the graph section's order; [] for one a lore view keeps."""
    out: list[str] = []
    if is_room_element(el):
        out.append("room")
    if is_hidden(el):
        out.append("hidden")
    if hands_on_as_proposed(el):
        out.append("proposed")
    kind = el.get("type")
    if isinstance(kind, str) and _fold(kind) in MAP_SPACE:
        out.append("map_space")
    if _reading_aid_key(el) is not None:
        out.append("reading_aid")
    return out

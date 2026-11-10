"""The map-space profile (schema-dist ``profiles/map-space.md``): how a reader turns a world's Maps, Zones, Markers
and Pins into geometry.

``map_space(elements)`` answers ``{maps, zones, pins, out}`` from the elements as a reader is served them (a folder's
rows or the API's, so visibility is already applied). Pure: nothing is stored or written. Coordinates count from the
bottom left of the Map, in the Map's pixels, and are whole numbers; a tool converts to its own units from the
``scale`` the answer reports. Looks, cameras, walls and rooms are a drawing tool's and are not read here.

A Zone's outline is its Markers on one Map in ``order``, a Marker without a whole ``order`` after the ordered ones,
ties by id in code point order. A row the reading leaves aside is counted in ``out`` by reason (``no_point``,
``no_markers``, ``dangling``, ``no_map``); a reason with nothing counted is absent. The same input gives the same
answer, key order included. The fixture (``codegen/schema-dist/profiles/map-space.fixture.json``) is replayed
whole by ``tests/test_map_space.py``.

``layout_of(map, maps, pins)`` is the page's second, small reading (rules 8 to 10): whether one Map is a layout map
(``x_layout`` with a non-empty string ``method``; ``"hand"`` is a board), the served Map its layout stands on, and
the Pins a new lay-out keeps where they are. ``map_space`` reads none of these keys. The fixture's ``layout_cases``
are replayed whole by ``tests/test_layout_of.py``.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, Literal, NotRequired, TypedDict

from .lens import _whole

MapSpaceShape = Literal["polygon", "line"]


class MapSpaceMap(TypedDict):
    """A Map's frame. ``width`` and ``height`` are the Map's own, or, when it has none, the largest x and y among its
    own outline points and Pins (None when it has no point), and ``extent`` is then ``"points"``."""

    id: str
    width: int | None
    height: int | None
    #: The z extent, None when the Map carries none.
    depth: int | None
    #: The largest z among the Map's own points (outlines and Pins), None when it has none: beside ``depth``, so a
    #: tool sees a z past it.
    z_max: int | None
    #: Metres per pixel: the Map's ``x_metres_per_pixel`` when a positive number, else None.
    scale: int | float | None
    location: str | None
    parent_map: str | None
    #: Present, as ``"points"``, only when a slot of ``width`` and ``height`` was measured.
    extent: NotRequired[Literal["points"]]


class MapSpaceOutline(TypedDict):
    """One Zone's outline on one Map: its points as ``[x, y, z]`` in order, a repeated point kept."""

    zone: str
    map: str
    shape: MapSpaceShape
    points: list[list[int]]


class MapSpacePin(TypedDict):
    """A Pin's point. The element is None, both keys, unless the Pin names both."""

    pin: str
    map: str
    element_type: str | None
    element_id: str | None
    x: int
    y: int
    z: int


class MapSpace(TypedDict):
    """The reading: ``maps``, ``zones`` and ``pins`` in id order, and what was left aside by reason."""

    maps: list[MapSpaceMap]
    zones: list[MapSpaceOutline]
    pins: list[MapSpacePin]
    out: dict[str, int]


class MapLayout(TypedDict):
    """The layout reading of one Map (rules 8 to 10)."""

    #: The ``x_layout`` method when the Map is a layout map (``"hand"`` for a board), else None. A method no page
    #: names answers itself.
    layout: str | None
    #: When ``layout`` is not None, the id ``x_layout.settings.ground.map`` names when it is a served Map other than
    #: this one, else None. Its size is not returned: the caller holds the served Map.
    ground: str | None
    #: The ids of the Pins a new lay-out keeps where they are, in code point order: every Pin of a board, the Pins
    #: whose ``x_hand`` is exactly ``True`` on any other layout map, and none on a Map that is not a layout map.
    hand: list[str]


def _id(value: Any) -> str | None:
    """An id: a non-empty string, else None."""
    return value if isinstance(value, str) and value != "" else None


def _scale(value: Any) -> int | float | None:
    """A scale: a positive number (never a boolean), else None."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value if value > 0 else None


def _point(element: Mapping[str, Any]) -> list[int] | None:
    """``[x, y, z]`` of a Marker or a Pin, None when ``x`` or ``y`` is not a whole number; a missing ``z`` is 0."""
    x, y, z = _whole(element.get("x")), _whole(element.get("y")), _whole(element.get("z"))
    if x is None or y is None:
        return None
    return [x, y, 0 if z is None else z]


def _by_type(elements: Iterable[Any]) -> dict[str, list[Mapping[str, Any]]]:
    """The rows by type. A row without a string id is no element: it is ignored, not counted."""
    found: dict[str, list[Mapping[str, Any]]] = {}
    for element in elements:
        if isinstance(element, Mapping) and isinstance(element.get("type"), str) and _id(element.get("id")):
            found.setdefault(element["type"], []).append(element)
    return found


def _served(rows: list[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    """The rows by id, the last served of each (serial 106, reading I: an element is its id)."""
    return {row["id"]: row for row in rows}


def _order(marker: Mapping[str, Any]) -> tuple[int, int, str]:
    """A Marker's place in its outline: the ordered ones by ``order``, then the rest, each tie by id."""
    order = _whole(marker.get("order"))
    return (1, 0, marker["id"]) if order is None else (0, order, marker["id"])


def map_space(elements: Iterable[Mapping[str, Any]]) -> MapSpace:
    """Read the map space of ``elements`` (types ``map``, ``zone``, ``marker``, ``pin``)."""
    by_type = _by_type(elements)
    maps = _served(by_type.get("map", []))
    zones = _served(by_type.get("zone", []))
    out = {"no_point": 0, "no_markers": 0, "dangling": 0, "no_map": 0}

    # A Marker whose Zone or Map is not served is dangling, checked before its point: one reason per row.
    placed: dict[tuple[str, str], list[tuple[tuple[int, int, str], list[int]]]] = {}
    for marker in _served(by_type.get("marker", [])).values():
        zone, map_id = _id(marker.get("zone")), _id(marker.get("map"))
        if zone is None or map_id is None or zone not in zones or map_id not in maps:
            out["dangling"] += 1
        elif (point := _point(marker)) is None:
            out["no_point"] += 1
        else:
            placed.setdefault((zone, map_id), []).append((_order(marker), point))

    outlines: list[MapSpaceOutline] = []
    for zone_id in sorted(zones):
        keys = sorted(key for key in placed if key[0] == zone_id)
        if not keys:
            out["no_markers"] += 1
            continue
        shape: MapSpaceShape = "line" if zones[zone_id].get("shape") == "line" else "polygon"
        for key in keys:
            points = [point for _, point in sorted(placed[key], key=lambda entry: entry[0])]
            outlines.append({"zone": zone_id, "map": key[1], "shape": shape, "points": points})

    pins: list[MapSpacePin] = []
    for pin_id, pin in sorted(_served(by_type.get("pin", [])).items()):
        map_id = _id(pin.get("map"))
        if map_id is None or map_id not in maps:
            out["no_map"] += 1
            continue
        point = _point(pin)
        if point is None:
            out["no_point"] += 1
            continue
        # A link needs both keys: one alone reads as neither.
        element_type, element_id = _id(pin.get("element_type")), _id(pin.get("element_id"))
        if element_type is None or element_id is None:
            element_type = element_id = None
        pins.append(
            {
                "pin": pin_id,
                "map": map_id,
                "element_type": element_type,
                "element_id": element_id,
                "x": point[0],
                "y": point[1],
                "z": point[2],
            }
        )

    frames: list[MapSpaceMap] = []
    for map_id in sorted(maps):
        source = maps[map_id]
        own = [p for o in outlines if o["map"] == map_id for p in o["points"]]
        own += [[p["x"], p["y"], p["z"]] for p in pins if p["map"] == map_id]
        measured = False
        sizes: list[int | None] = []
        for field, axis in (("width", 0), ("height", 1)):
            size = _whole(source.get(field))
            if size is None:
                size = max((p[axis] for p in own), default=None)
                measured = True
            sizes.append(size)
        frame: MapSpaceMap = {
            "id": map_id,
            "width": sizes[0],
            "height": sizes[1],
            "depth": _whole(source.get("depth")),
            "z_max": max((p[2] for p in own), default=None),
            "scale": _scale(source.get("x_metres_per_pixel")),
            "location": _id(source.get("location")),
            "parent_map": _id(source.get("parent_map")),
        }
        if measured:
            frame["extent"] = "points"
        frames.append(frame)

    return {"maps": frames, "zones": outlines, "pins": pins, "out": {k: n for k, n in out.items() if n}}


def _rows(rows: Iterable[Any]) -> dict[str, Mapping[str, Any]]:
    """Rows by id as the map-space reading takes them: a row without a string id is none (reading H), and the last
    row served for an id wins (reading I)."""
    return {row["id"]: row for row in rows if isinstance(row, Mapping) and _id(row.get("id"))}


def layout_of(
    map: Mapping[str, Any], maps: Iterable[Mapping[str, Any]], pins: Iterable[Mapping[str, Any]]
) -> MapLayout:
    """Read the layout keys of one Map: ``map`` the Map, ``maps`` the Maps the reader is served, ``pins`` every Pin
    the caller holds, of any Map (the reading keeps those whose ``map`` names this Map)."""
    this = _id(map.get("id")) if isinstance(map, Mapping) else None
    if this is None:
        # A Map row without a string id is no Map (reading H), whatever it carries: the empty answer.
        return {"layout": None, "ground": None, "hand": []}
    recipe = map.get("x_layout")
    method = recipe.get("method") if isinstance(recipe, Mapping) else None
    if not isinstance(recipe, Mapping) or not isinstance(method, str) or method == "":
        return {"layout": None, "ground": None, "hand": []}

    ground: str | None = None
    settings = recipe.get("settings")
    named = settings.get("ground") if isinstance(settings, Mapping) else None
    if isinstance(named, Mapping):
        ground = _id(named.get("map"))
        if ground is not None and (ground == this or ground not in _rows(maps)):
            ground = None

    # A board's Pins are all placed by hand; on any other method only a Pin marked exactly true (never 1 or "true").
    hand = sorted(
        pin_id
        for pin_id, pin in _rows(pins).items()
        if this is not None and pin.get("map") == this and (method == "hand" or pin.get("x_hand") is True)
    )
    return {"layout": method, "ground": ground, "hand": hand}

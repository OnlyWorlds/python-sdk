"""The by-links-3d layout, in front of step 4: the world's Maps and Pins as the map-space profile reads them.

The standard has one reading of a world's Maps and Pins, the map-space profile's (``map_space``), and one of the
layout mark (``layout_of``). A method that read Pins a second way could disagree with every other tool on which Pins a
world has. So the caller hands the method the world's elements, and space_rows() turns them into the rows plate()
reads, through those two readers and nothing of its own:

    space_rows(elements) -> rows, or None

  elements   the world's elements as served (any types; only Map and Pin elements are read), or None: no rows, so
             no plate

The rows, in this order:
  one {"type": "map", "id", "width", "height", "location"[, "name"]} for each Map ``map_space`` lists (by id) that is
      no layout map: ``layout_of(map, maps, pins)["layout"] is None``. width, height and location are map_space's;
      ``name`` only where the Map row has the key.
  one {"type": "pin", "id", "map", "element_id", "x", "y"} for each Pin ``map_space`` lists, by id, with the element
      map_space reads for it (None unless the Pin has both ``element_type`` and ``element_id``). A Pin of a layout map
      is among the rows and counts for no map: plate() holds no row for its Map.
Not read here: a Pin's z. The plate is flat.

The one thing written here that map_space also does: which raw row is a Map's or a Pin's (a row with a string
``type`` and a non-empty string ``id``; of two rows of one type with one id, the last served). layout_of needs the raw
Map row for its mark, and map_space's answer does not carry it.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from ..map_space import layout_of, map_space


def _id(v: Any) -> str | None:
    return v if isinstance(v, str) and v != "" else None


def space_rows(elements: Sequence[Any] | None) -> list[dict[str, Any]] | None:
    if elements is None:
        return None
    space = map_space(elements)
    raw_maps: dict[str, Any] = {}
    raw_pins: dict[str, Any] = {}
    for e in elements:
        if not isinstance(e, Mapping) or not isinstance(e.get("type"), str):
            continue
        id_ = _id(e.get("id"))
        if id_ is None:
            continue
        if e["type"] == "map":
            raw_maps[id_] = e
        elif e["type"] == "pin":
            raw_pins[id_] = e
    maps, pins = list(raw_maps.values()), list(raw_pins.values())
    rows: list[dict[str, Any]] = []
    for m in space["maps"]:
        raw = raw_maps[m["id"]]
        if layout_of(raw, maps, pins)["layout"] is not None:
            continue  # a layout map is no map of the world's space
        row: dict[str, Any] = {
            "type": "map",
            "id": m["id"],
            "width": m["width"],
            "height": m["height"],
            "location": m["location"],
        }
        if "name" in raw:
            row["name"] = raw["name"]
        rows.append(row)
    for p in space["pins"]:
        rows.append(
            {"type": "pin", "id": p["pin"], "map": p["map"], "element_id": p["element_id"], "x": p["x"], "y": p["y"]}
        )
    return rows

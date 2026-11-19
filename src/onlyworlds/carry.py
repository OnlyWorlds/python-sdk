"""The map-space profile's frame reading (schema-dist ``profiles/map-space.md``, rules 13 and 14): where a point on a
child Map lies on its parent, and on each Map above it. A child Map says where it lies on the Map its ``parent_map``
names with ``x_parent_frame``, a box ``[x0, y0, x1, y1]`` in the parent's pixels. The profile's ``frame_cases`` are
the test. ``map_space`` and ``layout_of`` do not read the key.

Every number is read as a 64-bit float before any arithmetic: Python's exact integers would otherwise round
differently from every other reader past 2**53."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any, Literal, TypedDict

CarryStop = Literal["top", "dangling", "cycle", "no_frame", "no_carry"]
CarryLint = Literal["no_parent", "not_four_numbers", "not_a_box"]


class CarryPoint(TypedDict):
    """A point on one Map: its id and the point in its pixels, from its bottom left."""

    map: str
    x: float
    y: float


class CarryOf(TypedDict):
    """One Map's frame reading. ``parent_frame`` is the key as written when it is a parent frame, else None;
    ``lint`` names what is wrong with this Map's own key; ``points`` is the point as given, then on each Map it is
    carried to up ``parent_map``; ``stop`` says why the walk ended (None only for a row that is no Map)."""

    parent_frame: list[Any] | None
    lint: CarryLint | None
    points: list[CarryPoint]
    stop: CarryStop | None


def _id(value: Any) -> str | None:
    """An id or a link: a string that is not empty; anything else reads as none (reading H)."""
    return value if isinstance(value, str) and value != "" else None


def _map_id(row: Any) -> str | None:
    """A Map row: ``type`` exactly ``map`` (reading K) and a non-empty string id (reading H)."""
    return _id(row.get("id")) if isinstance(row, Mapping) and row.get("type") == "map" else None


def _float(value: Any) -> float | None:
    """A number as rule 13 reads one: a JSON number held as a finite 64-bit float, else None. A bool, a string, null,
    a list, an object, and an integer too large for a 64-bit float are none."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        f = float(value)
    except OverflowError:
        return None
    return f if math.isfinite(f) else None


def _carry_size(value: Any) -> float | None:
    """A size a carry may divide by: a whole number above 0, by value (reading K: 100.0 reads as 100)."""
    f = _float(value)
    return f if f is not None and f.is_integer() and f > 0 else None


def _frame_of(row: Mapping[str, Any]) -> tuple[list[Any] | None, CarryLint | None]:
    """This Map's own parent frame (as written) and lint (rule 13)."""
    key = row.get("x_parent_frame")
    present = key is not None
    if _id(row.get("parent_map")) is None:
        return None, ("no_parent" if present else None)
    if not present:
        return None, None
    if not isinstance(key, list) or len(key) != 4:
        return None, "not_four_numbers"
    nums = [_float(v) for v in key]
    if any(n is None for n in nums):
        return None, "not_four_numbers"
    x0, y0, x1, y1 = (n for n in nums if n is not None)
    if not (x0 < x1) or not (y0 < y1):
        return None, "not_a_box"
    return key, None


def carry_of(map: Any, point: Sequence[float], maps: Sequence[Any]) -> CarryOf:
    """One Map's frame reading: ``{parent_frame, lint, points, stop}``, every key always present.

    ``map`` is the Map read, ``point`` is ``[x, y]`` on it (two finite numbers in its pixels from its bottom left),
    ``maps`` the Maps the reader is served: rows of any other type are skipped, a row whose ``type`` is not exactly
    ``map`` or that has no non-empty string id is no Map, and of two rows with one id the last served is read. A
    ``map`` that is no Map answers ``{parent_frame: None, lint: None, points: [], stop: None}``.

    The point is carried one level at a time up ``parent_map``, by each level's own frame, as
    ``x0 + ((x * (x1 - x0)) / width)`` and ``y0 + ((y * (y1 - y0)) / height)`` in 64-bit floats in that order,
    never through one product of the levels' ratios. The walk ends at a Map with no ``parent_map`` (``top``), one
    whose parent is not served (``dangling``), one whose parent the walk has already reached, itself included
    (``cycle``), one with no parent frame (``no_frame``), or one whose written ``width`` or ``height`` is not a whole
    number above 0 (``no_carry``). A point outside the child is carried as written; ``z`` is not carried. Pure."""
    if not isinstance(map, Mapping):
        raise TypeError("carry_of: map is one Map element.")
    if isinstance(point, (str, bytes)) or not isinstance(point, Sequence) or len(point) != 2:
        raise TypeError(f"carry_of: point is [x, y], two finite numbers; got {point!r}.")
    px, py = _float(point[0]), _float(point[1])
    if px is None or py is None:
        raise TypeError(f"carry_of: point is [x, y], two finite numbers; got {point!r}.")
    if isinstance(maps, (str, bytes)) or not isinstance(maps, Sequence):
        raise TypeError("carry_of: maps is a list of Map elements.")
    mid = _map_id(map)
    if mid is None:
        return {"parent_frame": None, "lint": None, "points": [], "stop": None}

    served: dict[str, Mapping[str, Any]] = {}
    for m in maps:
        sid = _map_id(m)
        if sid is not None:
            served[sid] = m

    own_frame, own_lint = _frame_of(map)
    # The point as given is the first entry; every carried one is a 64-bit float.
    points: list[CarryPoint] = [{"map": mid, "x": point[0], "y": point[1]}]
    x, y = px, py
    reached = {mid}
    at: Mapping[str, Any] = map
    frame = own_frame
    stop: CarryStop
    while True:
        parent_id = _id(at.get("parent_map"))
        if parent_id is None:
            stop = "top"
            break
        parent = served.get(parent_id)
        if parent is None:
            stop = "dangling"
            break
        if parent_id in reached:
            stop = "cycle"
            break
        if frame is None:
            stop = "no_frame"
            break
        width, height = _carry_size(at.get("width")), _carry_size(at.get("height"))
        if width is None or height is None:
            stop = "no_carry"
            break
        x0, y0, x1, y1 = (float(v) for v in frame)
        x = x0 + ((x * (x1 - x0)) / width)
        y = y0 + ((y * (y1 - y0)) / height)
        points.append({"map": parent_id, "x": x, "y": y})
        reached.add(parent_id)
        at = parent
        frame = _frame_of(parent)[0]
    return {"parent_frame": own_frame, "lint": own_lint, "points": points, "stop": stop}

"""The by-links-3d layout, step 4: the flat part, the world's first map as a plate.

    plate(rows, nodes[, scale]) -> None, or {"at": [(element id, [x, y, z]), ...],
                                             "first": [(element id, [x - W / 2, y - H / 2]), ...]}

rows are the Map and Pin rows space_rows() makes; nodes the graph's node ids. The rules, in order:
  1. the maps by id (a layout map, is_layout_map(), is passed over as if absent);
  2. the Pins in id order (code point order); for each map, each element's first place, read only from a Pin whose map
     is one of those maps, whose element is a node, and whose x and y are numbers;
  3. the first map: the one that holds the most elements, a tie to the greater id; with fewer than three, or no width
     or no height, there is no plate (None);
  4. the scale: SPREAD * REST over the root of (width * height / count), unless a scale is handed in; each element of
     the first map stands at ((x - W / 2) * scale, (y - H / 2) * scale, 0);
  5. the small plates: passes over the other maps in id order until a pass takes none. A map is taken when its
     location already stands, it has a width and a height, it holds three or more elements and one of them does not
     stand yet: each such element stands at the location plus (x - w / 2, y - h / 2) times TILE * REST over the root of
     (w * h / count), and REST * 4 above it (REST * 2 when the map holds fewer than 20).
"first" is the first map's elements at their places with the map's middle at 0, 0, in the order of "at".

A row's key that is absent is read as UNDEF, which is not None. Map and element ids are held as keys by jkey(), so
True and 1 are two keys and 1 and 1.0 one (as the npm SDK's Map holds them). A width or height that is not a number,
raises PlateError. A width or height that is not over 0 is no size: such a first map gives no plate, such a small
map is not taken, so a negative area is never reached. A division by a zero root is infinite (js_div()).
"""

from __future__ import annotations

import functools
import math
from collections.abc import Sequence
from typing import Any

REST = 60.0
SPREAD = 2.0
TILE = 0.4


class _Undef:
    def __repr__(self) -> str:
        return "undefined"


UNDEF: Any = _Undef()
NAN = float("nan")


class PlateError(Exception):
    pass


def get(e: Any, k: str) -> Any:
    """``e.k`` on a parsed JSON value: UNDEF when absent; None and UNDEF raise"""
    if e is None or e is UNDEF:
        raise PlateError(f"plate: cannot read properties of null (reading '{k}')")
    if isinstance(e, dict):
        return e.get(k, UNDEF)
    if isinstance(e, str) and k == "length":
        return len(e)
    if isinstance(e, list) and k == "length":
        return len(e)
    return UNDEF


def is_num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def jkey(v: Any, what: str | None = None) -> tuple[Any, ...]:
    """the key of a JSON value (a boolean, a number and a string never one key); what: raise on an object or array"""
    if v is UNDEF:
        return ("u",)
    if v is None:
        return ("z",)
    if isinstance(v, bool):
        return ("b", v)
    if is_num(v):
        return ("n", float(v))
    if isinstance(v, str):
        return ("s", v)
    if what is None:
        return ("o", id(v))  # an object in a set: by identity
    raise PlateError(f"plate: {what} is unhashable")


def key(v: Any, what: str) -> tuple[Any, ...]:
    return jkey(v, what)


def sized(v: Any) -> bool:
    """a size: truthy and, when a number, over 0 (a Map's width is any whole number; NaN is no size)"""
    if not truthy(v):
        return False
    if is_num(v):
        return bool(v > 0)
    return True


def truthy(v: Any) -> bool:
    """the truth of a JSON value: UNDEF, None, False, 0, "", an empty list or object are false; NaN is true"""
    if v is UNDEF or v is None or v is False:
        return False
    if is_num(v):
        return bool(v != 0)  # NaN != 0: true
    if isinstance(v, str):
        return v != ""
    if isinstance(v, list):
        return len(v) > 0
    if isinstance(v, dict):
        return len(v) > 0
    return True


def is_layout_map(row: Any) -> bool:
    """the map-space profile's layout mark: ``x_layout`` an object (not None, not a list) whose ``method`` is a string
    of length 1 or more. A JSON object is a dict here; a dict's absent ``method`` is UNDEF."""
    v = get(row, "x_layout")
    if not isinstance(v, dict):
        return False
    m = v.get("method", UNDEF)
    return isinstance(m, str) and len(m) > 0


def numeric(v: Any) -> bool:
    """isinstance(v, int | float), a bool included"""
    return isinstance(v, (int, float))


def to_num(v: Any) -> float:
    """a numeric() value as a double (an int past the doubles is infinite)"""
    try:
        return float(v)
    except OverflowError:
        return math.inf if v > 0 else -math.inf


def js_div(a: float, b: float) -> float:
    """a / b as a double divides: infinite or NaN where Python would raise"""
    if b != 0:
        return a / b
    if a != a or a == 0:
        return NAN
    neg = (a < 0) != str(b).startswith("-")  # the zero's sign, read without another float function
    return -math.inf if neg else math.inf


def by_code_point(a: Any, b: Any) -> float:
    """code point order on two strings: -1, 0 or 1; NaN for a pair it cannot order, and raises on None or UNDEF"""
    if a is None or a is UNDEF or b is None or b is UNDEF:
        raise PlateError("plate: cannot read properties of null (reading 'length')")
    if isinstance(a, str) and isinstance(b, str):
        return -1 if a < b else (1 if a > b else 0)
    # with a length on b and none on a, a's characters would be read: raise
    n = get(b, "length")
    if n is not UNDEF and n > 0 and not isinstance(a, str):
        raise PlateError("plate: a.charCodeAt is not a function")
    return NAN


def _sort_cmp(a: Any, b: Any) -> int:
    r = by_code_point(a, b)
    if r != r:
        return 0  # a NaN comparison reads as equal
    return int(r)


def root(w: Any, h: Any, count: int, what: str) -> float:
    """sqrt(w * h / count)"""
    if not numeric(w) or not numeric(h):
        raise PlateError(f"plate: {what}: a width or height that is no number")
    a = to_num(w) * to_num(h) / count
    if a < 0:
        raise PlateError(f"plate: {what}: math domain error (sqrt of {a})")
    return math.sqrt(a)


def plate(rows: Sequence[Any], nodes: Sequence[Any], scale: Any = UNDEF) -> dict[str, Any] | None:
    node_set = {jkey(v) for v in nodes}

    # 1. the maps, by id; a layout map is passed over, as if absent (its id is not read)
    maps: dict[tuple[Any, ...], Any] = {}  # jkey -> row
    for e in rows:
        if not (get(e, "type") == "map" and isinstance(get(e, "type"), str)):
            continue
        if is_layout_map(e):
            continue
        maps[key(get(e, "id"), "a map id")] = e

    # 2. the pins in id order; per map, each element's first place
    pins = []
    for e in rows:
        t = get(e, "type")
        if isinstance(t, str) and t == "pin":
            if not isinstance(get(e, "id"), str):
                raise PlateError("plate: a pin's id is not a string")
            pins.append(e)
    pins = sorted(pins, key=lambda p: p["id"])
    # jkey(map id) -> (map id, {jkey(element id): (element id, [x, y])})
    at: dict[tuple[Any, ...], tuple[Any, dict[tuple[Any, ...], tuple[Any, list[float]]]]] = {}
    for pin in pins:
        m = get(pin, "map")
        m = None if m is UNDEF else m
        el = get(pin, "element_id")
        el = None if el is UNDEF else el
        px, py = get(pin, "x"), get(pin, "y")
        # in this order: whether the element is a node is read only when the map is one of the maps
        if key(m, "a pin's map") in maps and key(el, "a pin's element_id") in node_set and numeric(px) and numeric(py):
            mk = jkey(m)
            if mk not in at:
                at[mk] = (m, {})
            row = at[mk][1]
            ek = jkey(el)
            if ek not in row:
                row[ek] = (el, [to_num(px), to_num(py)])
    if len(at) == 0:
        return None

    # 3. the first map: the most elements, a tie to the greater id
    m, mk, best = None, None, -1  # type: ignore[assignment]
    for ck, (c, row) in at.items():
        better = len(row) > best or (len(row) == best and by_code_point(c, m) > 0)
        if better:
            m, mk, best = c, ck, len(row)
    assert mk is not None
    mp = maps[mk]
    W, H = get(mp, "width"), get(mp, "height")
    count = len(at[mk][1])
    if count < 3 or not sized(W) or not sized(H):
        return None

    # 4. the scale and the first map's places
    own = js_div(SPREAD * REST, root(W, H, count, "the first map"))
    if scale is UNDEF:
        scale = own
        sv = own
    elif scale is None:
        sv = 0.0  # a scale of None multiplies as 0
    elif numeric(scale):
        sv = to_num(scale)
    else:
        raise TypeError(f"plate: a scale of this type is not read ({scale!r})")
    out: dict[tuple[Any, ...], tuple[Any, list[float]]] = {}  # jkey(element id) -> (element id, [x, y, z])
    # jkey(element id) -> (element id, [x - W / 2, y - H / 2])
    on_first: dict[tuple[Any, ...], tuple[Any, list[float]]] = {}
    for ek, (el, (x, y)) in at[mk][1].items():
        mx, my = x - to_num(W) / 2, y - to_num(H) / 2
        on_first[ek] = (el, [mx, my])
        out[ek] = (el, [mx * sv, my * sv, 0.0])

    # 5. the small plates: passes until one takes none
    todo = [ck for ck in at if ck != mk]
    todo = sorted(todo, key=functools.cmp_to_key(lambda p, q: _sort_cmp(at[p][0], at[q][0])))  # type: ignore[index]
    moved = True
    while moved:
        moved = False
        for ck in list(todo):
            c = at[ck][0]
            row = maps[ck]
            loc = get(row, "location")
            loc = None if loc is UNDEF else loc
            cw, ch = get(row, "width"), get(row, "height")
            mine = at[ck][1]
            fresh = []
            for ek, (el, xy) in mine.items():
                if ek not in out:
                    fresh.append((ek, el, xy))
            if key(loc, "a map's location") in out and sized(cw) and sized(ch) and len(mine) >= 3 and len(fresh):
                sc = js_div(TILE * REST, root(cw, ch, len(mine), f"the map {c}"))
                lx, ly, lz = out[jkey(loc)][1]
                rise = REST * (4 if len(mine) >= 20 else 2)
                for ek, el, (x, y) in fresh:
                    out[ek] = (el, [lx + (x - to_num(cw) / 2) * sc, ly + (y - to_num(ch) / 2) * sc, lz + rise])
                todo.remove(ck)
                moved = True
    return {
        "at": [(el, xyz) for (el, xyz) in out.values()],
        "first": [(el, xy) for (el, xy) in on_first.values()],
    }

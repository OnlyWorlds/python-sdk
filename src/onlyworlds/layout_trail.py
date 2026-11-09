"""A layout method, ``trail-by-place``: a world laid out along a route on a ground map.

The places sit in travel order, at their own pins on the ground map or between pinned ones, and every other element
hangs on a spiral round the place it belongs to, lifted to the height of its kind. The answer is a layout in the
standard's own fields: a Map frame (``width``, ``height``, ``depth``) and one Pin per element, whole numbers in the
Map's pixels, read back by ``map_space``.

The method places; it does not read. Which elements are in, the order of travel, which pinned places an unpinned
place falls between and which place each element hangs from are the caller's. Same input, same answer, and the same
answer as the npm SDK's ``trailByPlace``: the input and the recipe are the same JSON in both packages, and
``tests/fixtures/layout/trail-by-place.json`` (the npm SDK's bytes, sha256 held by both tests) is replayed whole.
"""

from __future__ import annotations

import copy
import math
from collections.abc import Mapping, Sequence
from typing import Any, Literal, NotRequired, TypedDict, cast

from .lens import _whole


class TrailTier(TypedDict):
    """One floor: the kinds (element type words) that stand at this height."""

    name: str
    z: int
    kinds: list[str]


class TrailSpiral(TypedDict):
    #: The first member's distance from the place's point; above 0, so nothing shares a place's own point.
    r0: float
    #: The n-th member stands at ``r0 + c * sqrt(n)``.
    c: float
    #: The turn between members, in radians: ``n * angle``.
    angle: float


class TrailSettings(TypedDict):
    """What a Map's recipe carries, so the layout runs again from the Map alone."""

    #: The ground map's frame, and ``map``, the ground Map's element id, when the caller gives one.
    ground: dict[str, Any]
    margin: int
    depth: int
    tiers: list[TrailTier]
    spiral: TrailSpiral
    parentRing: float


class TrailRecipe(TypedDict):
    method: Literal["trail-by-place"]
    settings: TrailSettings


class TrailPin(TypedDict):
    element_type: str
    element_id: str
    name: str
    x: int
    y: int
    z: int
    #: Why it stands there, in plain words: the caller's, then the method's.
    by: str


class TrailLayout(TypedDict):
    map: dict[str, int]
    #: One per place, hanger and hero, sorted by element id (code point order).
    pins: list[TrailPin]
    #: The places' points in travel order, ``[x, y, 0]``, rounded and not moved.
    route: list[list[int]]
    recipe: TrailRecipe
    nudged: int
    clamped: int


class TrailPlace(TypedDict):
    id: str
    type: str
    name: str
    pin: NotRequired[list[float]]
    between: NotRequired[list[str]]
    parent: NotRequired[str]
    by: NotRequired[str]


class TrailHanger(TypedDict):
    id: str
    type: str
    name: str
    at: list[str]
    by: NotRequired[str]


#: The default floors: places and things on the ground, the living above, what happened higher, what is told highest.
TRAIL_TIERS: tuple[TrailTier, ...] = (
    {"name": "ground: places and things", "z": 0, "kinds": ["location", "object", "zone"]},
    {"name": "people and the living", "z": 240, "kinds": ["character", "collective", "creature", "species"]},
    {"name": "what happened", "z": 480, "kinds": ["event"]},
    {
        "name": "told or abstract",
        "z": 720,
        "kinds": [
            "ability",
            "construct",
            "family",
            "institution",
            "language",
            "law",
            "narrative",
            "phenomenon",
            "relation",
            "title",
            "trait",
        ],
    },
)

_DEFAULT_SPIRAL: TrailSpiral = {"r0": 140, "c": 20, "angle": 2.399963}
_DEFAULT_PARENT_RING = 140
_INPUT_KEYS = ("ground", "margin", "depth", "tiers", "spiral", "parentRing", "places", "hangers", "hero")
_PLACE_KEYS = ("id", "type", "name", "pin", "between", "parent", "by")
_HANGER_KEYS = ("id", "type", "name", "at", "by")


def _fail(msg: str) -> TypeError:
    return TypeError(f"trail_by_place: {msg}")


def _refuse_unknown(what: str, value: Mapping[str, Any], keys: Sequence[str]) -> None:
    for k in value:
        if k not in keys:
            raise _fail(f"{what}: unknown key {k!r}. The keys are {', '.join(keys)}.")


def _number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _js(v: Any) -> str:
    """A number as JavaScript writes it, so a ``by`` line reads the same in both packages (``7.0`` is ``7``)."""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def _whole_above(v: Any, low: int) -> bool:
    w = _whole(v)
    return w is not None and w > low


def _check_element(e: Any, what: str, keys: Sequence[str]) -> None:
    if not isinstance(e, Mapping):
        raise _fail(f"{what} is not an object")
    _refuse_unknown(what, e, keys)
    if not isinstance(e.get("id"), str) or not e["id"]:
        raise _fail(f"{what} has no id")
    if not isinstance(e.get("type"), str) or not e["type"]:
        raise _fail(f"{what} ({e['id']}) has no type")
    if not isinstance(e.get("name"), str):
        raise _fail(f"{what} ({e['id']}) has no name")
    if "by" in e and not isinstance(e["by"], str):
        raise _fail(f"{what} ({e['id']}): by is not a string")


def trail_by_place(input: Mapping[str, Any]) -> TrailLayout:
    """Lay out a trail.

    Places first: a pinned place at its pin plus the margin; a place ``between`` two pinned places evenly along the
    line between them, with the others between the same two, in travel order; a place inside a ``parent`` on a ring
    round it, siblings by id. Then every hanger and the hero: grouped by the rounded mean of their places' points, each
    group on one sunflower spiral round that point (the hero first, then by floor, then by id; the n-th member at
    ``r0 + c * sqrt(n)`` and ``n * angle``), at its floor's height. Last, every point is rounded half to even, kept
    inside the frame, and, by element id order, a point already taken moves along x from its own point (one pixel
    right, one left, two right, two left, and on), so no two Pins share a point.

    Raises ``TypeError``, naming what, on an input it cannot place: an unknown key at any level, a place with none or
    two of ``pin``, ``between`` and ``parent``, a reference to a place it does not hold, a kind with no floor, an id
    given twice, a row of the frame with no free point left.
    """
    if not isinstance(input, Mapping):
        raise _fail("the input is not an object")
    _refuse_unknown("trail_by_place", input, _INPUT_KEYS)
    g = input.get("ground")
    if not isinstance(g, Mapping):
        raise _fail("no ground")
    _refuse_unknown("ground", g, ("map", "width", "height"))
    if "map" in g and (not isinstance(g["map"], str) or not g["map"]):
        raise _fail("ground.map is the ground Map's element id, a non-empty string")
    if not _whole_above(g.get("width"), 0) or not _whole_above(g.get("height"), 0):
        raise _fail("the ground's width and height are whole numbers above 0")
    gw, gh = int(g["width"]), int(g["height"])
    margin = _whole(input.get("margin", 0))
    if margin is None or margin < 0:
        raise _fail("margin is a whole number, 0 or more")
    if not _whole_above(input.get("depth"), 0):
        raise _fail("depth is a whole number above 0")
    depth = int(input["depth"])
    spiral = input.get("spiral", _DEFAULT_SPIRAL)
    if not isinstance(spiral, Mapping):
        raise _fail("spiral is {r0 above 0, c 0 or more, angle}")
    _refuse_unknown("spiral", spiral, ("r0", "c", "angle"))
    sr0, sc, sangle = spiral.get("r0"), spiral.get("c"), spiral.get("angle")
    if not (_number(sr0) and _number(sc) and _number(sangle)):
        raise _fail("spiral is {r0 above 0, c 0 or more, angle}")
    # kept as given (an int stays an int), so the recipe is the same JSON as the npm SDK's
    r0, c, angle = cast(float, sr0), cast(float, sc), cast(float, sangle)
    if r0 <= 0 or c < 0:
        raise _fail("spiral is {r0 above 0, c 0 or more, angle}")
    ring = input.get("parentRing", _DEFAULT_PARENT_RING)
    if not _number(ring) or ring <= 0:
        raise _fail("parentRing is a number above 0")
    tiers = input.get("tiers", TRAIL_TIERS)
    if not isinstance(tiers, Sequence) or isinstance(tiers, str) or len(tiers) == 0:
        raise _fail("tiers is a list of at least one tier")
    for t in tiers:
        if not isinstance(t, Mapping):
            raise _fail("a tier is {name, z (a whole number, 0 or more), kinds}")
        _refuse_unknown("tier", t, ("name", "z", "kinds"))
        z = _whole(t.get("z"))
        if not isinstance(t.get("name"), str) or z is None or z < 0 or not isinstance(t.get("kinds"), list):
            raise _fail("a tier is {name, z (a whole number, 0 or more), kinds}")

    def tier_of(kind: str, id_: str) -> int:
        for k, t in enumerate(tiers):
            if kind in t["kinds"]:
                return k
        raise _fail(f"no tier holds the kind {kind!r} ({id_})")

    places = input.get("places")
    hangers = input.get("hangers")
    hero = input.get("hero")
    if not isinstance(places, list) or len(places) == 0:
        raise _fail("places is a list of at least one place")
    if not isinstance(hangers, list):
        raise _fail("hangers is a list")

    M, W, H, D = margin, gw + 2 * margin, gh + 2 * margin, depth
    seen: set[str] = set()

    def once(id_: str) -> None:
        if id_ in seen:
            raise _fail(f"the id {id_} is given twice")
        seen.add(id_)

    by_id: dict[str, Mapping[str, Any]] = {}
    for i, p in enumerate(places):
        _check_element(p, f"place {i}", _PLACE_KEYS)
        once(p["id"])
        rules = [k for k in ("pin", "between", "parent") if k in p]
        if len(rules) != 1:
            has = ", ".join(rules) if rules else "none"
            raise _fail(f"place {p['name']} ({p['id']}) needs exactly one of pin, between, parent; it has {has}")
        if "pin" in p and not (isinstance(p["pin"], list) and len(p["pin"]) == 2 and all(_number(v) for v in p["pin"])):
            raise _fail(f"place {p['name']}: pin is [x, y]")
        if "between" in p and not (
            isinstance(p["between"], list) and len(p["between"]) == 2 and all(isinstance(v, str) for v in p["between"])
        ):
            raise _fail(f"place {p['name']}: between is [place id, place id]")
        if "parent" in p and not isinstance(p["parent"], str):
            raise _fail(f"place {p['name']}: parent is a place id")
        by_id[p["id"]] = p

    pt: dict[str, tuple[float, float]] = {}
    by: dict[str, str] = {}
    for p in places:
        if "pin" not in p:
            continue
        x, y = p["pin"]
        pt[p["id"]] = (x + M, y + M)
        by[p["id"]] = p.get("by", f"its pin on the ground ({_js(x)}, {_js(y)}), plus the {M} px margin")
    groups: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for p in places:
        if "between" not in p:
            continue
        for end in p["between"]:
            if end not in by_id:
                raise _fail(f"place {p['name']}: between names {end}, which is not one of the places")
            if end not in pt:
                raise _fail(f"place {p['name']}: between names {by_id[end]['name']}, which has no pin")
        groups.setdefault((p["between"][0], p["between"][1]), []).append(p)
    for (a, b), members in groups.items():
        for n, p in enumerate(members):
            f = (n + 1) / (len(members) + 1)
            (ax, ay), (bx, by_) = pt[a], pt[b]
            pt[p["id"]] = (ax + (bx - ax) * f, ay + (by_ - ay) * f)
            base = f"no pin: between {by_id[a]['name']} and {by_id[b]['name']}"
            by[p["id"]] = f"{base} ({p['by']})" if "by" in p else base
    sibs: dict[str, list[str]] = {}
    for p in places:
        if "parent" not in p:
            continue
        if p["parent"] not in by_id:
            raise _fail(f"place {p['name']}: parent {p['parent']} is not one of the places")
        sibs.setdefault(p["parent"], []).append(p["id"])
    for s in sibs.values():
        s.sort()
    left, passes = True, 0
    while left and passes <= len(places):
        left, passes = False, passes + 1
        for p in places:
            if "parent" not in p or p["id"] in pt:
                continue
            if p["parent"] not in pt:
                left = True
                continue
            s = sibs[p["parent"]]
            a_ = math.pi / 4 + 2 * math.pi * s.index(p["id"]) / len(s)
            cx, cy = pt[p["parent"]]
            pt[p["id"]] = (cx + ring * math.cos(a_), cy + ring * math.sin(a_))
            why = p.get("by", "its parent_location")
            by[p["id"]] = f"no pin: inside {by_id[p['parent']]['name']} ({why}), beside it"
    for p in places:
        if p["id"] not in pt:
            raise _fail(
                f"place {p['name']} ({p['id']}) sits inside a ring of parents that never reaches a placed place"
            )

    raw: list[dict[str, Any]] = [
        {
            "element_type": p["type"],
            "element_id": p["id"],
            "name": p["name"],
            "x": pt[p["id"]][0],
            "y": pt[p["id"]][1],
            "z": 0,
            "by": by[p["id"]],
        }
        for p in places
    ]
    members_in: list[tuple[Mapping[str, Any], str]] = [(h, f"hanger {i}") for i, h in enumerate(hangers)]
    if hero is not None:
        members_in.append((hero, "the hero"))
    clusters: dict[tuple[int, int], list[tuple[Mapping[str, Any], int]]] = {}
    for h, what in members_in:
        _check_element(h, what, _HANGER_KEYS)
        once(h["id"])
        at = h.get("at")
        if not isinstance(at, list) or len(at) == 0:
            raise _fail(f"{what} {h['name']}: at is a list of at least one place id")
        for q in at:
            if q not in pt:
                raise _fail(f"{what} {h['name']}: at names {q}, which is not one of the places")
        cx_ = round(sum(pt[q][0] for q in at) / len(at))
        cy_ = round(sum(pt[q][1] for q in at) / len(at))
        clusters.setdefault((cx_, cy_), []).append((h, tier_of(h["type"], h["id"])))
    hero_id = hero["id"] if hero is not None else None
    for (cx_, cy_), hs in clusters.items():
        hs.sort(key=lambda e: (e[0]["id"] != hero_id, e[1], e[0]["id"]))
        for n, (h, tier) in enumerate(hs):
            r = r0 + c * math.sqrt(n)
            a_ = n * angle
            where = f"tier {tiers[tier]['name']}; {n + 1} of {len(hs)} on the spiral round it"
            raw.append(
                {
                    "element_type": h["type"],
                    "element_id": h["id"],
                    "name": h["name"],
                    "x": cx_ + r * math.cos(a_),
                    "y": cy_ + r * math.sin(a_),
                    "z": tiers[tier]["z"],
                    "by": f"{h['by']}; {where}" if "by" in h else where,
                }
            )

    raw.sort(key=lambda p: p["element_id"])
    taken: set[tuple[int, int, int]] = set()
    nudged = clamped = 0
    for p in raw:
        for k, hi in (("x", W), ("y", H), ("z", D)):
            v = round(p[k])
            cv = min(max(v, 0), hi)
            clamped += cv != v
            p[k] = cv
        # Every x on the row is tried within 2 * width + 2 steps; a row with none free is refused, never walked forever.
        x0, step = p["x"], 0
        while (p["x"], p["y"], p["z"]) in taken:
            step += 1
            if step > 2 * W + 2:
                raise _fail(
                    f"no free point left for {p['name']} ({p['element_id']}) on its row (y {p['y']}, z {p['z']}): "
                    f"the frame is {W} wide"
                )
            p["x"] = min(max(x0 + (1 if step % 2 else -1) * ((step + 1) // 2), 0), W)
            nudged += 1
        taken.add((p["x"], p["y"], p["z"]))

    pins: list[TrailPin] = [
        {
            "element_type": p["element_type"],
            "element_id": p["element_id"],
            "name": p["name"],
            "x": p["x"],
            "y": p["y"],
            "z": p["z"],
            "by": p["by"],
        }
        for p in raw
    ]
    settings: TrailSettings = {
        "ground": {"map": g["map"], "width": gw, "height": gh} if "map" in g else {"width": gw, "height": gh},
        "margin": M,
        "depth": D,
        "tiers": [{"name": t["name"], "z": t["z"], "kinds": list(t["kinds"])} for t in tiers],
        "spiral": {"r0": r0, "c": c, "angle": angle},
        "parentRing": ring,
    }
    return {
        "map": {"width": W, "height": H, "depth": D},
        "pins": pins,
        "route": [[round(pt[p["id"]][0]), round(pt[p["id"]][1]), 0] for p in places],
        "recipe": {"method": "trail-by-place", "settings": copy.deepcopy(settings)},
        "nudged": nudged,
        "clamped": clamped,
    }

"""The by-links-3d layout as one function: the parts (structure, centres, plate, points, relax, spread, hang) joined
in order, with the two pieces no part holds: the feed of the force steps and the answer. No rule of a part is written
again here: every part is imported and called as its head says.

    layout3d(nodes, edges, rows, table, held=None, held_unit=None) -> answer

  nodes      [{"id", "type"[, "name"]}]                  the graph's nodes, in any order; each id once
  edges      [{"source", "target"[, "field"][, "index"]}] the graph's links, in any order; a link whose end is no
                                                         node is passed over
  rows       the world's Maps and Pins as space_rows() makes them, or None: no plate
  table      the directions table
  held       a mapping, element id -> [x, y, z], or None: nothing held
  held_unit  the step the held points were rounded to, or None: 0

The answer: {"method", "ids", "points" (3n floats), "how", "group", "part", "centres", "held"}, rows in the order the
nodes were handed in.

The order, in this sequence:
  0. the refusals (read_held(), then read_unit()), before anything runs;
  1. the input in one order: nodes by id (code point order); links by source, then field (absent as ""), then index
     (absent as 0), then target; the undirected pairs (each unordered pair of distinct nodes once) in node order;
  2. structure(); 3. centres();
  4. plate(), and with held points the frame (frame_of()) and, with a frame, plate() again at the frame's scale;
  5. points(), with held points its fixed parts and the snap;
  6. the feed (feed_of()); 7. the start (start_of()); 8. relax(), STEPS steps;
  9. hang();
  10. the answer, rows put back in the handed order.

Held points: a held element that is not pinned stands at its held point; the structure, the centres and the groups
are read from today's graph; a pinned element stands at its Pin, so ``held`` is False for it. Each group's point,
the first case that applies: (1) its centre is pinned (over the plate); (2) its centre is held: the held point; (3) it
has held members (in the body, held, not pinned): their mean, x, y, z each summed in id order and divided by the
count; (4) the packing's. With anything held, no centre that is not held is fixed in the steps.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

from .centres import centres
from .hang import ARM, CENTRE, HOW, LINE, LINK, MAP, WITH, hang
from .plate import plate as plate_of
from .points import Table, points
from .relax import relax
from .spread import plain_start
from .structure import structure

METHOD = "by-links-3d"
REST = 60.0
STEPS = 300
CROSS = 0.25  # a link between two groups pulls this much of a link inside one
PLATE = 0.02  # a link to a pinned element
HOLD = 0.12  # how hard an element is held to its group's point
CAP0 = 0.1  # the first step's cap, in rests
CUTOFF = 3  # the push's reach, in rests
SNAP = REST / 1e9  # a billionth of a rest
HELD_BOX = 768  # the widest box of held points, in rests, on any side
REFUSED = {"notObject": "held-not-object", "notPoint": "held-not-point", "box": "held-box", "unit": "held-unit"}


class HeldTypeError(TypeError):
    """``held`` is not a mapping (``held-not-object``), or a held value is not three finite numbers
    (``held-not-point``): the refusal's word is ``code``."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class HeldRangeError(ValueError):
    """The held points spread wider than 768 rests on an axis (``held-box``), or ``held_unit`` is not a finite number
    from 0 to an eighth of a rest (``held-unit``): the refusal's word is ``code``."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _is_number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def is_point(p: Any) -> bool:
    """a list or tuple of exactly three finite numbers (a bool is no number)"""
    if not isinstance(p, (list, tuple)):
        return False
    if len(p) != 3:
        return False
    for v in p:  # noqa: SIM110
        if not _is_number(v) or not math.isfinite(v):
            return False
    return True


def read_held(held: Any) -> list[tuple[Any, list[float]]] | None:
    """None when absent or empty, else its entries [(id, [x, y, z])], every number a float. The box is read over
    every value handed in, an id that is no node's too."""
    if held is None:
        return None
    if not isinstance(held, Mapping):
        raise HeldTypeError(REFUSED["notObject"], "layout_by_links_3d: held is not a mapping")
    entries = list(held.items())
    for id_, p in entries:
        if not is_point(p):
            raise HeldTypeError(REFUSED["notPoint"], f"layout_by_links_3d: held[{id_}] is not three finite numbers")
    if entries:
        lo = [math.inf, math.inf, math.inf]
        hi = [-math.inf, -math.inf, -math.inf]
        for _id, p in entries:
            for a in range(3):
                if p[a] < lo[a]:
                    lo[a] = p[a]
                if p[a] > hi[a]:
                    hi[a] = p[a]
        for a in range(3):
            if hi[a] - lo[a] > HELD_BOX * REST:
                raise HeldRangeError(
                    REFUSED["box"],
                    f"layout_by_links_3d: the held points' box is {(hi[a] - lo[a]) / REST} rests on "
                    f"{'xyz'[a]}, wider than {HELD_BOX}",
                )
    return [(id_, [float(p[0]), float(p[1]), float(p[2])]) for id_, p in entries] if entries else None


def read_unit(u: Any) -> float:
    if u is None:
        return 0.0  # None is read as absent, as held None is
    if not _is_number(u) or not math.isfinite(u) or u < 0 or u > LINE:
        raise HeldRangeError(
            REFUSED["unit"], f"layout_by_links_3d: held_unit {u!r} is not a finite number from 0 to {LINE}"
        )
    return float(u)


def frame_of(
    first: Sequence[tuple[Any, Sequence[float]]],
    at: Mapping[str, int],
    hflag: Sequence[int],
    hat: Sequence[float],
    unit: float,
    need: int = 3,
) -> dict[str, Any] | None:
    """Where the first map stood when the held points were answered: None, or {"a", "b", "s", "P", "agree"} (a and b
    element indexes). first: plate()'s "first".

    Candidates: the held elements on the first map, in id order. For a candidate a, the b's: the candidates whose held
    z is within unit + SNAP of a's and whose map place is not a's, farthest on the map first (a tie to the first in id
    order). For each b: s = the 2D distance of their held points over that of their map places, P = a's held point
    less s times its map place (z: a's). A candidate agrees when each axis of its held point is within 3 * unit + SNAP
    of P + s * its map place. The frame is that of the first pair that ``need`` candidates agree with (a counted)."""
    cv: list[int] = []
    cx: list[float] = []
    cy: list[float] = []
    for id_, q in first:
        v = at[id_]
        if hflag[v]:
            cv.append(v)
            cx.append(q[0])
            cy.append(q[1])
    order = sorted(range(len(cv)), key=lambda i: cv[i])  # the candidates in id order
    m = len(order)
    tol_z, near = unit + SNAP, 3 * unit + SNAP
    for ia in range(m):
        a = order[ia]
        va = cv[a]
        ax, ay, az = hat[3 * va], hat[3 * va + 1], hat[3 * va + 2]
        # the b's: candidates of a's z whose map place is not a's, farthest on the map first, a tie to the first in
        # id order (the list is built in id order and the sort is stable)
        bdist: list[tuple[int, float]] = []
        for ib in range(m):
            c = order[ib]
            if c == a:
                continue
            dz = hat[3 * cv[c] + 2] - az
            if not (dz <= tol_z and -dz <= tol_z):
                continue
            if cx[c] == cx[a] and cy[c] == cy[a]:
                continue
            mx, my = cx[c] - cx[a], cy[c] - cy[a]
            bdist.append((c, math.sqrt(mx * mx + my * my)))
        bs = sorted(range(len(bdist)), key=lambda p: (-bdist[p][1], p))
        for ib in bs:
            b, bd = bdist[ib]
            vb = cv[b]
            hx, hy = hat[3 * vb] - ax, hat[3 * vb + 1] - ay
            if hx == 0 and hy == 0:
                continue  # the two held points are one point in x and y: no frame
            s = math.sqrt(hx * hx + hy * hy) / bd
            P = [ax - s * cx[a], ay - s * cy[a], az]
            agree = 0
            for ic in range(m):
                c = order[ic]
                vc = cv[c]
                ex = hat[3 * vc] - (P[0] + s * cx[c])
                ey = hat[3 * vc + 1] - (P[1] + s * cy[c])
                ez = hat[3 * vc + 2] - P[2]
                if ex <= near and -ex <= near and ey <= near and -ey <= near and ez <= near and -ez <= near:
                    agree += 1
            if agree >= need:
                return {"a": va, "b": vb, "s": s, "P": P, "agree": agree}
    return None


def _utf8(id_: str) -> bytes:
    # a lone surrogate is written as U+FFFD, as a UTF-8 encoder that replaces does; Python's own would raise on it
    try:
        return id_.encode("utf-8")
    except UnicodeEncodeError:
        return id_.encode("utf-16-le", "surrogatepass").decode("utf-16-le", "replace").encode("utf-8")


def fnv1a(id_: str) -> int:
    """FNV-1a, 32 bits, over the id's UTF-8 bytes: each element's own seed"""
    h = 2166136261
    for b in _utf8(id_):
        h = ((h ^ b) * 16777619) % 4294967296
    return h


def _link_key(e: Mapping[str, Any]) -> tuple[Any, ...]:
    f = e.get("field")
    i = e.get("index")
    return (e["source"], "" if f is None else f, 0 if i is None else i, e["target"])


def feed_of(
    ids: Sequence[str],
    body: Sequence[int],
    pairs: Sequence[Sequence[str]],
    taken: Sequence[int],
    group: Sequence[int],
    cpt: Sequence[float],
    plate: dict[str, Any] | None,
    steps: int,
    held: dict[str, Any] | None = None,
    free: Sequence[int] | None = None,
    extra: Sequence[int] = (),
) -> dict[str, Any]:
    """The feed of the force steps, over the body's elements in id order.

    pairs: each link between two body elements once, as (lower place, higher place) in the body list, sorted; weight:
    1.0 inside one group, CROSS between two, PLATE when either end is pinned; anchor: the group's point, a pinned
    element's place, a held element's held point; pull: HOLD; fixed: a centre (unless its group is free), a pinned
    element, a held one. Then ``extra``: held elements outside the body, fixed at their held points, pull 0, in no
    pair."""
    n = len(ids)
    at = {id_: i for i, id_ in enumerate(ids)}
    blist: list[int] = []
    bi = [-1] * n
    for v in range(n):
        if body[v]:
            bi[v] = len(blist)
            blist.append(v)
    nb = len(blist)
    centre = [0] * n
    for t in taken:
        centre[t] = 1
    pinned = plate["pinned"] if plate else None

    seen: set[int] = set()
    bp: list[list[int]] = []
    for x, y in pairs:
        a, b = at.get(x), at.get(y)
        if a is None or b is None or a == b:
            continue
        i, j = bi[a], bi[b]
        if i < 0 or j < 0:
            continue
        if i > j:
            i, j = j, i
        key = i * nb + j
        if key in seen:
            continue
        seen.add(key)
        bp.append([i, j])
    bp.sort(key=lambda p: (p[0], p[1]))

    weight: list[float] = []
    for i, j in bp:
        u, w = blist[i], blist[j]
        wt = 1.0 if group[u] == group[w] else CROSS
        if pinned and (pinned[u] or pinned[w]):
            wt = PLATE
        weight.append(wt)
    anchor: list[list[float]] = []
    for v in blist:
        if pinned and pinned[v]:
            assert plate is not None
            anchor.append([plate["at"][3 * v], plate["at"][3 * v + 1], plate["at"][3 * v + 2]])
        elif held and held["flag"][v]:
            anchor.append([held["at"][3 * v], held["at"][3 * v + 1], held["at"][3 * v + 2]])
        else:
            g = group[v]
            anchor.append([cpt[3 * g], cpt[3 * g + 1], cpt[3 * g + 2]])
    pull = [HOLD for _ in blist]
    fixed = [
        bool(
            (centre[v] and not (free and free[group[v]] == 1))
            or (pinned and pinned[v])
            or (held and held["flag"][v] == 1)
        )
        for v in blist
    ]
    feed: dict[str, Any] = {
        "rest": REST,
        "steps": steps,
        "ids": [ids[v] for v in blist],
        "pairs": bp,
        "weight": weight,
        "anchor": anchor,
        "pull": pull,
        "fixed": fixed,
        "group": [group[v] for v in blist],
        "num": [fnv1a(ids[v]) for v in blist],
    }
    for v in extra:  # after the body, in id order; no link, no hold
        assert held is not None
        feed["ids"].append(ids[v])
        feed["anchor"].append([held["at"][3 * v], held["at"][3 * v + 1], held["at"][3 * v + 2]])
        feed["pull"].append(0.0)
        feed["fixed"].append(True)
        feed["group"].append(-1)
        feed["num"].append(fnv1a(ids[v]))
    return feed


def start_of(feed: dict[str, Any]) -> list[list[float]]:
    """Each element's point before the steps, in the feed's order: a fixed element at its anchor; each group's other
    elements in a ball round the group's point, by plain_start() called once per group on that group's moving
    elements with every anchor at zero, the anchor added after."""
    nb = len(feed["anchor"])
    out: list[list[float]] = [[] for _ in range(nb)]
    members: dict[int, list[int]] = {}  # group -> the places counted for its ball, in order
    for i in range(nb):
        if feed["fixed"][i]:
            a = feed["anchor"][i]
            out[i] = [a[0], a[1], a[2]]
            continue
        members.setdefault(feed["group"][i], []).append(i)
    for lst in members.values():
        zero = [[0.0, 0.0, 0.0] for _ in lst]
        off = plain_start(
            {"rest": feed["rest"], "pos": zero, "anchor": zero, "fixed": None}, [feed["num"][i] for i in lst]
        )
        for k_, i in enumerate(lst):
            a = feed["anchor"][i]
            out[i] = [a[0] + off[k_][0], a[1] + off[k_][1], a[2] + off[k_][2]]
    return out


def layout3d(
    nodes: Sequence[Mapping[str, Any]],
    edges: Sequence[Mapping[str, Any]],
    rows: Sequence[Any] | None,
    table: Table,
    held: Any = None,
    held_unit: Any = None,
) -> dict[str, Any]:
    held_in = read_held(held)  # 0. refused before anything runs
    unit = read_unit(held_unit)
    steps = STEPS
    n = len(nodes)
    handed = [x["id"] for x in nodes]
    if not n:
        return {
            "method": METHOD,
            "ids": [],
            "points": [],
            "how": [],
            "group": [],
            "part": [],
            "centres": [],
            "held": [],
        }

    # 1. the input in one order
    sorted_nodes = sorted(nodes, key=lambda x: x["id"])
    ids = [x["id"] for x in sorted_nodes]
    for i in range(1, n):
        if ids[i] == ids[i - 1]:
            raise ValueError(f"layout_by_links_3d: two nodes share the id {ids[i]}")
    at = {id_: i for i, id_ in enumerate(ids)}
    links = sorted((e for e in edges if e["source"] in at and e["target"] in at), key=_link_key)
    seen: set[int] = set()
    ip: list[tuple[int, int]] = []
    for e in links:
        a, b = at[e["source"]], at[e["target"]]
        if a == b:
            continue
        lo, hi = (a, b) if a < b else (b, a)
        key = lo * n + hi
        if key in seen:
            continue
        seen.add(key)
        ip.append((lo, hi))
    ip.sort()
    pairs = [[ids[a], ids[b]] for a, b in ip]
    edges3 = [[e["source"], e["target"], e.get("field")] for e in links]

    # 2 and 3: the body, the centres and the groups, from today's graph
    s = structure(ids, pairs)
    c = centres(ids, pairs, s["body"])
    k = len(c["taken"])

    # the held points that are nodes (a held id that is no node is passed over)
    hflag: list[int] | None = None
    hat: list[float] | None = None
    if held_in:
        for id_, q in held_in:
            v = at.get(id_)
            if v is None:
                continue
            if hflag is None or hat is None:
                hflag, hat = [0] * n, [0.0] * (3 * n)
            hflag[v] = 1
            hat[3 * v], hat[3 * v + 1], hat[3 * v + 2] = q[0], q[1], q[2]

    # 4. the flat part; with held points, the frame and the plate again at the frame's scale
    plate_at = None
    frame = None
    if rows is not None:
        plate_ans = plate_of(rows, ids)
        if plate_ans and hflag and hat is not None:
            frame = frame_of(plate_ans["first"], at, hflag, hat, unit, 3)
            if frame:
                plate_ans = plate_of(rows, ids, frame["s"])
        plate_at = {el: xyz for el, xyz in plate_ans["at"]} if plate_ans else None

    # each group's case, and the fixed parts and the snap for points()
    keep = cases = None
    fixed = snap = None
    extra: list[int] = []
    if hflag and hat is not None:
        pinned_v = [0] * n
        if plate_at:
            for id_ in plate_at:
                pinned_v[at[id_]] = 1
        keep = [1 if (hflag[v] and not pinned_v[v]) else 0 for v in range(n)]
        cases = [0] * k
        gflag, gat = [0] * k, [0.0] * (3 * k)
        sx, sy, sz, cnt = [0.0] * k, [0.0] * k, [0.0] * k, [0] * k
        for v in range(n):  # the held members, in id order
            if not s["body"][v] or not keep[v]:
                continue
            g = c["group"][v]
            sx[g] += hat[3 * v]
            sy[g] += hat[3 * v + 1]
            sz[g] += hat[3 * v + 2]
            cnt[g] += 1
        for g in range(k):
            t = c["taken"][g]
            if pinned_v[t]:
                cases[g] = 1
            elif keep[t]:
                cases[g] = 2
                gflag[g] = 1
                gat[3 * g], gat[3 * g + 1], gat[3 * g + 2] = hat[3 * t], hat[3 * t + 1], hat[3 * t + 2]
            elif cnt[g] > 0:
                cases[g] = 3
                gflag[g] = 1
                gat[3 * g], gat[3 * g + 1], gat[3 * g + 2] = sx[g] / cnt[g], sy[g] / cnt[g], sz[g] / cnt[g]
            else:
                cases[g] = 4
        fixed = {"group": gflag, "at": gat, "plate": list(frame["P"]) if frame else None, "blind": False}
        snap = {"flag": hflag, "at": hat, "near": 3 * unit + SNAP}
        for v in range(n):
            if keep[v] and not s["body"][v]:
                extra.append(v)

    # 5. each group's point (the fixed parts, the plate and the snap)
    p = points(s["ids"], s["body"], c["taken"], c["group"], pairs, edges3, plate_at, table, fixed, snap)
    held_opt = {"flag": keep, "at": hat} if keep else None
    # with anything held no centre that is not held is fixed: case 3 and case 4 free
    free = None
    if cases:
        free = [1 if cases[g] in (3, 4) else 0 for g in range(k)]

    # 6 to 8: the feed, the start, the steps
    feed = feed_of(
        s["ids"], s["body"], pairs, c["taken"], c["group"], p["cpt"], p["plate"], steps, held_opt, free, extra
    )
    start = start_of(feed)
    r = relax(dict(feed, pos=start), cutoff=CUTOFF, cap0=CAP0)
    relaxed = [0.0] * (3 * n)
    j = 0
    for v in range(n):
        if not s["body"][v]:
            continue
        relaxed[3 * v], relaxed[3 * v + 1], relaxed[3 * v + 2] = (
            r["pos"][3 * j],
            r["pos"][3 * j + 1],
            r["pos"][3 * j + 2],
        )
        j += 1

    # 9. what is placed after the steps
    kind = [x["type"] for x in sorted_nodes]
    degree = [0] * n
    for a, b in ip:
        degree[a] += 1
        degree[b] += 1
    hopts = dict(held_opt, line=LINE, claim=True) if held_opt else None
    h = hang(
        s["ids"],
        s["body"],
        s["hangCut"],
        s["hangDepth"],
        s["off"],
        c["taken"],
        c["group"],
        p["cpt"],
        p["plate"],
        kind,
        degree,
        relaxed,
        hopts,
    )

    # 10. the answer, in the handed order
    out = [0.0] * (3 * n)
    how: list[str | None] = [None] * n
    group: list[str | None] = [None] * n
    part: list[str | None] = [None] * n
    held_out = [False] * n
    for i in range(n):
        v = at[handed[i]]
        out[3 * i], out[3 * i + 1], out[3 * i + 2] = h["pos"][3 * v], h["pos"][3 * v + 1], h["pos"][3 * v + 2]
        held_out[i] = keep is not None and keep[v] == 1
        w = h["how"][v]
        how[i] = HOW[w]
        own = bool(s["body"][v]) and c["taken"][c["group"][v]] == v
        if w == CENTRE or w == WITH or (w == MAP and own):  # noqa: SIM109
            group[i] = ids[c["taken"][c["group"][v]]]
            part[i] = None
        elif w == MAP:
            group[i], part[i] = None, "map"
        elif w == ARM or w == LINK:  # noqa: SIM109
            group[i], part[i] = None, "one-link"
        else:
            group[i], part[i] = None, "no-link"
    return {
        "method": METHOD,
        "ids": handed,
        "points": out,
        "how": how,
        "group": group,
        "part": part,
        "centres": [ids[t] for t in c["taken"]],
        "held": held_out,
    }

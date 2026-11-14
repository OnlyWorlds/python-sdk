"""Two layout methods for a world nobody laid out, read from its graph as ``world_graph`` answers it.

``by-kind`` (``layout_by_kind``): each kind of element gets a point on a circle, links act as springs, neighbours
push apart, for a fixed number of seeded steps; the answer is fitted into a square. ``around`` (``layout_around``):
one element at the centre, its neighbours on rings round it, and at two steps their neighbours further out, near the
element that reached them.

Both give the same answer as the npm SDK's ``layoutByKind`` and ``layoutAround``. ``by-kind`` is exact: the same graph
gives the same points to the last bit in every language and browser. The kinds' points on the circle are read from a
table of numbers baked into the package, never computed with the runtime's own cosine and sine (which differ in the
last place between runtimes, and the method magnifies one unit in the last place into a visibly different picture);
everything else is addition, subtraction, multiplication, division, square root and floor, which every runtime rounds
alike. Both first put the graph in one order (nodes by id, edges by source, field, index and target), so the order
a caller hands it in changes no point. ``tests/fixtures/layout/by-kind.json`` (the npm SDK's bytes, sha256 held by both
tests) is replayed whole.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from typing import Any, Literal, TypedDict

from ._anchors import ANCHORS, GROUP_ORDER
from ._schema import ELEMENT_GROUPS

__all__ = ["AroundLayout", "AroundPoint", "KindLayout", "KindPoint", "layout_around", "layout_by_kind"]

_STEPS = 320
_CELL_MAX = 12
_RING_ONE = 60


class KindPoint(TypedDict):
    """One element's point, in a frame of -1 to 1 on the picture's longer axis, centred."""

    id: str
    x: float
    y: float


class KindLayout(TypedDict):
    """What ``layout_by_kind`` answers: one point per node, in the graph's node order, and the method that made them."""

    method: Literal["by-kind"]
    version: int
    points: list[KindPoint]


class AroundPoint(TypedDict):
    """One element's point round the focus: the focus at 0, 0, and how many links away from it the element is."""

    id: str
    #: 0 for the focus, 1 for its neighbours, 2 for theirs.
    depth: int
    x: float
    y: float


class AroundLayout(TypedDict):
    """What ``layout_around`` answers: the focus and every element within the steps, in the graph's node order."""

    method: Literal["around"]
    version: int
    points: list[AroundPoint]


def _cell_key(x: int, y: int) -> int:
    return (x + 1048576) * 2097152 + (y + 1048576)


def _rng(seed: int) -> Callable[[], float]:
    """The 32-bit linear congruential generator, exact in float64 in every language."""
    s = seed & 0xFFFFFFFF

    def next_() -> float:
        nonlocal s
        s = (s * 1664525 + 1013904223) & 0xFFFFFFFF
        return s / 4294967296

    return next_


def _group_rank(kind: str) -> int:
    return GROUP_ORDER.index(ELEMENT_GROUPS[kind])


def _read_graph(
    fn: str, graph: Any
) -> tuple[list[Mapping[str, Any]], list[Mapping[str, Any]], list[Mapping[str, Any]], dict[str, int]]:
    """The caller's nodes, then the method's one order of the graph: the nodes by id, the edges by source, field (none
    as ``""``), index (none as 0) and target, every word by code point (Python orders strings by code point), and each
    node's place in that order. A TypeError naming what cannot be read."""

    def fail(msg: str) -> TypeError:
        return TypeError(f"{fn}: {msg}")

    given = graph.get("nodes") if isinstance(graph, Mapping) else None
    links = graph.get("edges") if isinstance(graph, Mapping) else None
    if not isinstance(given, list) or not isinstance(links, list):
        raise fail("the graph is {nodes, edges}, as world_graph answers it")
    seen: set[str] = set()
    for i, node in enumerate(given):
        if not isinstance(node, Mapping):
            raise fail(f"node {i} is not an object")
        id_ = node.get("id")
        if not isinstance(id_, str) or not id_:
            raise fail(f"node {i} has no id")
        kind = node.get("type")
        if not isinstance(kind, str) or kind not in ELEMENT_GROUPS:
            raise fail(f"node {id_}: {kind!r} is not one of the 22 element types")
        name = node.get("name")
        if name is not None and not isinstance(name, str):
            raise fail(f"node {id_}: name is a string or None")
        if id_ in seen:
            raise fail(f"the id {id_} is a node twice")
        seen.add(id_)
    for k, e in enumerate(links):
        if not isinstance(e, Mapping) or not isinstance(e.get("source"), str) or not isinstance(e.get("target"), str):
            raise fail(f"edge {k} is not {{source, target}}")
        field = e.get("field")
        if field is not None and not isinstance(field, str):
            raise fail(f"edge {k}: field is a string")
        at = e.get("index")
        if at is not None and (not isinstance(at, (int, float)) or isinstance(at, bool) or not math.isfinite(at)):
            raise fail(f"edge {k}: index is a number")
    nodes = sorted(given, key=lambda x: str(x["id"]))
    edges = sorted(
        links,
        key=lambda e: (e["source"], e.get("field") or "", e.get("index") or 0, e["target"]),
    )
    return given, nodes, edges, {x["id"]: i for i, x in enumerate(nodes)}


def layout_by_kind(graph: Mapping[str, Any]) -> KindLayout:
    """Lay out a whole graph by kind.

    Each kind present gets an anchor on a circle, in colour group order (blue, green, pink, amber) and then by type
    word in code point order; every element starts near its kind's anchor, at a seeded jitter. Then, for 320 steps
    (160 past 2,000 elements): elements closer than a few rest lengths push each other apart (a cell holding more than
    12 pushes with a rotating sample of 12, scaled up), every link pulls its two ends towards a rest length, every
    element is drawn back towards its kind's anchor, and no element moves further in one step than a cap that shrinks
    as the steps run out. Last, the points are fitted into a frame of -1 to 1 on the longer axis, centred, proportions
    kept.

    ``graph`` is ``world_graph``'s answer, or any mapping of the same shape: ``nodes`` (each with ``id`` and ``type``)
    and ``edges`` (each with ``source`` and ``target``). Answers
    ``{"method": "by-kind", "version": 1, "points": [...]}``, one ``{"id", "x", "y"}`` per node in the graph's node
    order, so a saved layout can say what made it. An empty graph answers no points; a graph of one element answers
    0, 0.

    The graph is first put in one order: the nodes by id, the edges by source, then field (none as ``""``), then index
    (none as 0), then target, every word by code point. ``world_graph`` answers in that order already; a graph handed
    in any other order gives the same points, each under its id.

    The same graph gives the same points to the last bit in every language and browser, the npm SDK's ``layoutByKind``
    included: the anchors are a baked table of numbers, never computed, and the rest is arithmetic every runtime rounds
    alike. Self-links pull nothing; a link to an id that is not a node is passed over.

    Raises ``TypeError``, naming what, on a graph it cannot read: no nodes or edges list, a node with no id, a type
    that is not one of the 22, a name that is not a string or None, an id twice, an edge without a string source and
    target.
    """
    given, nodes, edges, index = _read_graph("layout_by_kind", graph)
    n = len(nodes)
    if n <= 1:
        return {"method": "by-kind", "version": 1, "points": [{"id": x["id"], "x": 0.0, "y": 0.0} for x in given]}

    links: list[tuple[int, int]] = []
    for e in edges:
        a, b = index.get(e["source"]), index.get(e["target"])
        if a is not None and b is not None and a != b:
            links.append((a, b))
    # Colour group order, then the type word by code point (Python orders strings by code point).
    kinds = sorted({x["type"] for x in nodes}, key=lambda t: (_group_rank(t), t))
    table = ANCHORS[len(kinds)]
    anchor = {t: table[i] for i, t in enumerate(kinds)}

    rand = _rng(7)
    px = [0.0] * n
    py = [0.0] * n
    for i, x in enumerate(nodes):
        ax, ay = anchor[x["type"]]
        px[i] = ax * 0.8 + (rand() - 0.5) * 0.5
        py[i] = ay * 0.8 + (rand() - 0.5) * 0.5
    rest = max(0.002, 0.9 / math.sqrt(n))
    tx = [anchor[x["type"]][0] * 0.85 for x in nodes]
    ty = [anchor[x["type"]][1] * 0.85 for x in nodes]
    cell = rest * 2.2
    cell2 = cell * cell
    steps = _STEPS // 2 if n > 2000 else _STEPS
    for it in range(steps):
        t = 1 - it / steps
        fx = [0.0] * n
        fy = [0.0] * n
        grid: dict[int, list[int]] = {}
        for i in range(n):
            grid.setdefault(_cell_key(math.floor(px[i] / cell), math.floor(py[i] / cell)), []).append(i)
        for i in range(n):
            pxi, pyi = px[i], py[i]
            cx, cy = math.floor(pxi / cell), math.floor(pyi / cell)
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    members = grid.get(_cell_key(cx + dx, cy + dy))
                    if members is None:
                        continue
                    if len(members) > _CELL_MAX:
                        size = len(members)
                        off = (i * 7 + it * 13) % size
                        scale = size / _CELL_MAX
                        for k in range(_CELL_MAX):
                            j = members[(off + k) % size]
                            if j == i:
                                continue
                            ux = pxi - px[j]
                            uy = pyi - py[j]
                            d2 = ux * ux + uy * uy + 1e-6
                            if d2 > cell2:
                                continue
                            d = math.sqrt(d2)
                            f = (rest * rest * 1.4 * 1 * scale) / d2
                            fx[i] += (ux / d) * f
                            fy[i] += (uy / d) * f
                        continue
                    for j in members:
                        if j <= i:
                            continue
                        ux = pxi - px[j]
                        uy = pyi - py[j]
                        d2 = ux * ux + uy * uy + 1e-6
                        if d2 > cell2:
                            continue
                        d = math.sqrt(d2)
                        f = (rest * rest * 1.4 * 1) / d2
                        fx[i] += (ux / d) * f
                        fy[i] += (uy / d) * f
                        fx[j] -= (ux / d) * f
                        fy[j] -= (uy / d) * f
        for a, b in links:
            ux = px[b] - px[a]
            uy = py[b] - py[a]
            d = math.sqrt(ux * ux + uy * uy) + 1e-6
            f = (d - rest) * 0.06
            fx[a] += (ux / d) * f
            fy[a] += (uy / d) * f
            fx[b] -= (ux / d) * f
            fy[b] -= (uy / d) * f
        cap = 0.03 * t + 0.002
        for i in range(n):
            fx[i] += (tx[i] - px[i]) * 0.06
            fy[i] += (ty[i] - py[i]) * 0.06
            m = math.sqrt(fx[i] * fx[i] + fy[i] * fy[i])
            s = cap / m if m > cap else 1.0
            px[i] += fx[i] * s
            py[i] += fy[i] * s

    x0, x1, y0, y1 = math.inf, -math.inf, math.inf, -math.inf
    for i in range(n):
        x0, x1 = min(x0, px[i]), max(x1, px[i])
        y0, y1 = min(y0, py[i]), max(y1, py[i])
    span = max(x1 - x0, y1 - y0)
    s = 2 / span if span > 1e-9 else 1.0
    mx = (x0 + x1) / 2
    my = (y0 + y1) / 2
    return {
        "method": "by-kind",
        "version": 1,
        "points": [
            {"id": x["id"], "x": (px[index[x["id"]]] - mx) * s, "y": (py[index[x["id"]]] - my) * s} for x in given
        ],
    }


def layout_around(graph: Mapping[str, Any], focus: str, *, steps: int = 1) -> AroundLayout:
    """Lay out one element and what is linked to it.

    The focus stands at 0, 0. Its neighbours (one link away, in either direction) stand on a ring round it, in colour
    group order, then by type word, then by name (code point order, the same in every language and locale; no name
    sorts as the empty name), up to 60 on the first ring and further rings beyond it. With ``steps=2``, each
    neighbour's own neighbours stand on an outer ring, fanned out near the neighbour that reached them.

    ``graph`` is ``world_graph``'s answer, or any mapping of the same shape, as for ``layout_by_kind``; ``focus`` is a
    node's id. Answers ``{"method": "around", "version": 1, "points": [...]}``: the focus and every element within the
    steps, in the graph's node order, each ``{"id", "depth", "x", "y"}`` with its depth (0, 1 or 2). Nothing iterates,
    so each point is one cosine and one sine of an angle the method computes exactly; the npm SDK's ``layoutAround``
    agrees to within about 1e-12. The graph is first put in ``layout_by_kind``'s one order, so the order a graph is
    handed in does not move a point.

    Raises ``TypeError`` on a ``steps`` that is not a whole number or a graph it cannot read (as ``layout_by_kind``),
    and ``ValueError`` on a ``steps`` that is not 1 or 2 or a focus that is not one of the graph's nodes.
    """
    if not isinstance(steps, int) or isinstance(steps, bool):
        raise TypeError(f"layout_around: steps is 1 or 2, not {steps!r}")
    if steps not in (1, 2):
        raise ValueError(f"layout_around: steps is 1 or 2, not {steps!r}")
    given, nodes, edges, index = _read_graph("layout_around", graph)
    centre = index.get(focus) if isinstance(focus, str) else None
    if centre is None:
        raise ValueError(f"layout_around: the focus {focus!r} is not a node of the graph")

    adj: list[list[int]] = [[] for _ in nodes]
    for e in edges:
        a, b = index.get(e["source"]), index.get(e["target"])
        if a is None or b is None:
            continue
        adj[a].append(b)
        if a != b:
            adj[b].append(a)
    depth: dict[int, int] = {centre: 0}
    via: dict[int, int] = {}
    frontier = [centre]
    for s in range(1, steps + 1):
        nxt: list[int] = []
        for a in frontier:
            for to in adj[a]:
                if to not in depth:
                    depth[to] = s
                    via[to] = a
                    nxt.append(to)
        frontier = nxt

    def name(j: int) -> str:
        v = nodes[j].get("name")
        return v if isinstance(v, str) else ""

    ring1 = sorted(
        (j for j, s in depth.items() if s == 1),
        key=lambda j: (_group_rank(nodes[j]["type"]), nodes[j]["type"], name(j), j),
    )
    at: dict[int, tuple[float, float]] = {centre: (0.0, 0.0)}
    ang: dict[int, float] = {}
    if ring1:
        r1 = max(0.34, min(len(ring1), _RING_ONE) * 0.017)
        gap = (2 * math.pi * r1) / min(len(ring1), _RING_ONE)
        placed, r = 0, r1
        while placed < len(ring1):
            room = max(1, math.floor((2 * math.pi * r) / gap))
            these = ring1[placed : placed + room]
            for k, j in enumerate(these):
                angle = -math.pi / 2 + (2 * math.pi * (k + 0.5)) / len(these)
                ang[j] = angle
                at[j] = (math.cos(angle) * r, math.sin(angle) * r)
            placed += len(these)
            r += gap * 1.2
        outer = r - gap * 1.2
        kids: dict[int, list[int]] = {}
        for j, s in depth.items():
            if s == 2:
                kids.setdefault(via[j], []).append(j)
        spread = min(0.5, ((2 * math.pi) / max(1, len(ring1))) * 0.9)
        for p, ks in kids.items():
            a0 = ang.get(p, 0.0)
            for k, j in enumerate(ks):
                angle = a0 + (0 if len(ks) == 1 else (k / (len(ks) - 1) - 0.5) * spread)
                at[j] = (math.cos(angle) * outer * 1.8, math.sin(angle) * outer * 1.8)
    return {
        "method": "around",
        "version": 1,
        "points": [
            {"id": x["id"], "depth": depth[j], "x": at[j][0], "y": at[j][1]}
            for x in given
            if (j := index[x["id"]]) in at
        ],
    }

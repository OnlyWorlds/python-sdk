"""The landing profile (schema-dist ``profiles/landing.md``): a world's first picture at a door, read from the
graph ``world_graph`` answers. A real world shows its most-linked Characters, each with what it links; a small
one shows its gaps. Structure only, never coordinates: a layout is the drawing tool's, keyed by id. The npm SDK's
``landingOf`` gives the same answer on the same graph."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal, TypedDict

from .lens import _whole

LandingMode = Literal["gaps", "graph"]
LandingGapKind = Literal["orphan", "near_orphan", "no_place", "nobody_here"]


class LandingMember(TypedDict):
    id: str
    #: Steps from the head: 0 for the head itself.
    hops: int
    degree: int


class LandingCluster(TypedDict):
    head: str
    #: The head first, then by hops, then by degree (highest first), then by id in code point order.
    members: list[LandingMember]


class LandingUnclustered(TypedDict):
    id: str
    degree: int


class LandingGap(TypedDict):
    kind: LandingGapKind
    id: str


class Landing(TypedDict):
    mode: LandingMode
    #: The size the mode was read at.
    size: int
    clusters: list[LandingCluster]
    #: Every node no head reaches within ``hops``, by degree (highest first), then by id.
    unclustered: list[LandingUnclustered]
    #: In the kinds' order (orphan, near_orphan, no_place, nobody_here), then by id; a node can carry several.
    gaps: list[LandingGap]


_GAP_ORDER: dict[str, int] = {"orphan": 0, "near_orphan": 1, "no_place": 2, "nobody_here": 3}


def _option(name: str, value: Any, default: int) -> int:
    if value is None:
        return default
    n = _whole(value)
    if n is None or n < 1:
        raise ValueError(f"landing_of: {name} is a whole number, 1 or more; got {value!r}.")
    return n


def landing_of(
    graph: Mapping[str, Any],
    *,
    heads: int | None = None,
    hops: int | None = None,
    size: int | None = None,
) -> Landing:
    """A world's first picture at a door, from the graph ``world_graph`` answered for the visitor, so it holds
    exactly what that reader may see. The mode is ``gaps`` when the graph has fewer nodes than ``size`` (default
    24), else ``graph``; both parts are always read. Heads: the Characters with an edge, most linked first
    (``degree_of``'s count), ties by id in code point order, at most ``heads`` (default 5), never a known-of node.
    A node within ``hops`` steps of a head (default 1; either way along an edge) joins the nearest head, a tie
    going to the higher-ranked one. Gaps: an orphan (degree 0) and a near-orphan (degree 1) by that same count, a
    Character whose ``location`` names no Location node (``no_place``), a Location no Character's ``location``
    names (``nobody_here``); a known-of node is never a gap. The same graph and options give the same answer, byte
    for byte. An option that is not a whole number of 1 or more is a ValueError naming it; None is its default."""
    if (
        not isinstance(graph, Mapping)
        or not isinstance(graph.get("nodes"), list)
        or not isinstance(graph.get("edges"), list)
    ):
        raise TypeError("landing_of: graph is what world_graph answers, a mapping with nodes and edges lists.")
    k = _option("heads", heads, 5)
    reach = _option("hops", hops, 1)
    cut = _option("size", size, 24)

    nodes: list[Mapping[str, Any]] = graph["nodes"]
    degree: dict[str, int] = {n["id"]: 0 for n in nodes}
    near: dict[str, set[str]] = {n["id"]: set() for n in nodes}
    kind_of: dict[str, Any] = {n["id"]: n.get("type") for n in nodes}
    placed: set[str] = set()
    inhabited: set[str] = set()
    for e in graph["edges"]:
        s, t = e["source"], e["target"]
        if s in degree:
            degree[s] += 1
        if t != s and t in degree:
            degree[t] += 1
        if t != s and s in near and t in near:
            near[s].add(t)
            near[t].add(s)
        if e.get("field") == "location" and kind_of.get(s) == "character" and kind_of.get(t) == "location":
            placed.add(s)
            inhabited.add(t)

    # Python compares str by code point, the profile's order, never by UTF-16 unit.
    head_ids = sorted(
        (
            n["id"]
            for n in nodes
            if n.get("type") == "character" and n.get("known_of") is not True and degree[n["id"]] > 0
        ),
        key=lambda i: (-degree[i], i),
    )[:k]

    # Each node's least (hops, rank) over every head's own walk, so no queue order ever decides a tie.
    best: dict[str, tuple[int, int]] = {}
    for rank, head in enumerate(head_ids):
        seen: dict[str, int] = {head: 0}
        frontier = [head]
        step = 0
        while step < reach and frontier:
            nxt: list[str] = []
            for i in frontier:
                for nb in near[i]:
                    if nb in seen:
                        continue
                    seen[nb] = step + 1
                    nxt.append(nb)
            frontier = nxt
            step += 1
        for i, h in seen.items():
            b = best.get(i)
            if b is None or (h, rank) < b:
                best[i] = (h, rank)

    clusters: list[LandingCluster] = [{"head": h, "members": []} for h in head_ids]
    unclustered: list[LandingUnclustered] = []
    for n in nodes:
        i = n["id"]
        b = best.get(i)
        if b is not None:
            clusters[b[1]]["members"].append({"id": i, "hops": b[0], "degree": degree[i]})
        else:
            unclustered.append({"id": i, "degree": degree[i]})
    for c in clusters:
        c["members"].sort(key=lambda m: (m["hops"], -m["degree"], m["id"]))
    unclustered.sort(key=lambda u: (-u["degree"], u["id"]))

    gaps: list[LandingGap] = []
    for n in nodes:
        if n.get("known_of") is True:
            continue
        i = n["id"]
        if degree[i] == 0:
            gaps.append({"kind": "orphan", "id": i})
        if degree[i] == 1:
            gaps.append({"kind": "near_orphan", "id": i})
        if n.get("type") == "character" and i not in placed:
            gaps.append({"kind": "no_place", "id": i})
        if n.get("type") == "location" and i not in inhabited:
            gaps.append({"kind": "nobody_here", "id": i})
    gaps.sort(key=lambda g: (_GAP_ORDER[g["kind"]], g["id"]))

    return {
        "mode": "gaps" if len(nodes) < cut else "graph",
        "size": cut,
        "clusters": clusters,
        "unclustered": unclustered,
        "gaps": gaps,
    }

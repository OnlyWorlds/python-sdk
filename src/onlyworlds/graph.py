"""The graph section of the lens profile (schema-dist ``profiles/lens.md``): a reading of a world as nodes and edges.

The elements a reader sees are the nodes, the links between them the edges. ``world_graph`` adds nothing to the
world and stores nothing. Who sees what is the lens reader's own reading (``lens._Reading``), never a second copy;
with a lens the nodes are exactly what the lens kept. The npm SDK's ``worldGraph`` gives the same answers, byte for
byte, on the same input.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any, Literal, NotRequired, TypedDict

from ._schema import ELEMENT_FAMILIES, ELEMENT_ICONS
from .lens import (
    _CUT_REASONS,
    _LINK_FIELDS,
    _OWNER_ONLY,
    _check_reader,
    _lens_reading,
    _Reading,
    _reading_date,
    _whole,
)
from .message import _instant

__all__ = ["GraphEdge", "GraphNode", "WorldGraph", "degree_of", "world_graph"]

GraphMark = Literal["room", "hidden", "proposed"]


class GraphNode(TypedDict):
    """One element of the graph."""

    id: str
    #: The element's type, as its slug (``character``).
    type: str
    #: The element's name, or ``None`` when it has none.
    name: str | None
    #: The type's family, from the distribution's presentation defaults.
    family: str
    #: The type's icon name, from the distribution's presentation defaults.
    icon: str
    #: The out-by-default kinds the element belongs to, in this order: ``room``, ``hidden``, ``proposed``; absent
    #: when none.
    marks: NotRequired[list[GraphMark]]
    #: True on a guest's known-of element, a stub that has no edges out; absent otherwise.
    known_of: NotRequired[bool]


class GraphEdge(TypedDict):
    """One link: one source, one field, one target, at its place in the field's list (0 for a single link)."""

    source: str
    field: str
    target: str
    index: int


class WorldGraph(TypedDict):
    """What ``world_graph`` answers."""

    #: The nodes, by id in code point order.
    nodes: list[GraphNode]
    #: The edges, by source id, then field name (both in code point order), then index.
    edges: list[GraphEdge]
    #: The links left out because their target is not a node, counted by the target's reason, in the reasons' one
    #: order: the lens's cut reasons, then ``room``, ``hidden``, ``proposed``, ``map_space``, ``outside_lens``. A
    #: reason with no count is absent; a reader that is not the owner never carries ``anchor_not_visible``,
    #: ``not_visible``, ``hidden`` or ``proposed``, and every reader carries ``outside_lens`` (a link, with a lens,
    #: to an element the reader sees that the lens neither kept nor cut; never in a lens's cut).
    edges_cut: dict[str, int]
    #: With a lens, the lens's own cut, unchanged. Without one, the elements out by default, counted by reason
    #: (``room``, ``hidden`` and ``proposed`` for the owner only, ``map_space``).
    cut: dict[str, int]
    #: With a lens whose ``x_lens`` the lens reader cannot read, the key it names (as ``resolve_lens``'s
    #: ``unreadable``), and the graph is empty. ``None`` otherwise, and always ``None`` without a lens.
    unreadable: str | None


_DECLARED_LINKS: tuple[str, ...] = ("x_lens_leads_to", "x_spine_depends_on")
"""The extension fields a published profile declares a link, each a list of ids: the lens profile's and the spine
profile's."""
_MAP_SPACE = frozenset({"map", "pin", "marker", "zone"})
_KINDS: tuple[str, ...] = ("room", "hidden", "proposed", "map_space")
_MARKS: tuple[GraphMark, ...] = ("room", "hidden", "proposed")
_GRAPH_REASONS: tuple[str, ...] = (*_CUT_REASONS, *_KINDS, "outside_lens")
_GRAPH_OWNER_ONLY = frozenset({*_OWNER_ONLY, "hidden", "proposed"})


def _tally(counts: Mapping[str, int], owner: bool) -> dict[str, int]:
    """Counts in the reasons' one order, a reason with no count left out, and the owner's reasons kept for the
    owner."""
    return {
        why: counts[why] for why in _GRAPH_REASONS if counts.get(why, 0) > 0 and (owner or why not in _GRAPH_OWNER_ONLY)
    }


def world_graph(
    world: Mapping[str, Any],
    reader: Mapping[str, Any],
    *,
    lens: Mapping[str, Any] | str | None = None,
    as_of: int | None = None,
    clock: str | None = None,
    rooms: bool = False,
    hidden: bool = False,
    proposed: bool = False,
    map_space: bool = False,
) -> WorldGraph:
    """Read a world as a graph for one reader (the lens profile's graph section): the elements the reader sees as
    nodes, the links between them as edges, and what was left out, counted by reason. Pure: it never writes, and
    nothing in the world moves.

    ``world`` and ``reader`` are what ``resolve_lens`` takes. Without ``lens`` the nodes are every element the
    reader sees less what is out by default: room elements, hidden ones, proposed ones and map space (Map, Pin,
    Marker, Zone), each brought back by its flag (``rooms``, ``hidden``, ``proposed``, ``map_space``) and then
    marked. With ``lens`` (a lens body, or the id of a lens the reader can see) the nodes are exactly the lens's
    ``kept``, its cut rides along unchanged, and a flag adds nothing; ``as_of`` and ``clock`` are the lens's, as
    ``resolve_lens`` takes them, and are read only with a lens. A lens whose ``x_lens`` cannot be read gives an
    empty graph with ``unreadable`` naming the key, as ``resolve_lens`` does.

    Each schema link field, and each extension field a profile declares a link (``x_lens_leads_to``,
    ``x_spine_depends_on``), gives one edge per target that is a node, with the target's place in the list as the
    reader is served it; a link held on both ends is two edges. A guest's known-of element has no edges out. A link
    to an element that is not a node is counted in ``edges_cut`` by that element's reason: the lens's cut reason,
    else, with a lens, ``outside_lens`` for one the reader sees that the lens neither kept nor cut (counted for every
    rung); one of the four kinds without a lens; and ``not_visible`` for one the reader does not see. A link to an id
    that is not in the world is left out and not counted.

    ``hidden`` or ``proposed`` from a reader that is not the owner, or any flag from a public reader, raises
    ``ValueError`` naming the flag before anything is read. An owner reading ``as`` another reader is judged by that
    reader's rung. The npm SDK's ``worldGraph`` gives the same answer on the same input."""
    if not isinstance(world, Mapping) or not isinstance(world.get("elements"), list):
        raise TypeError("world_graph: world is a mapping with an elements list.")
    _check_reader(reader, "world_graph: reader")
    flags = {"room": rooms, "hidden": hidden, "proposed": proposed, "map_space": map_space}
    names = {"room": "rooms", "hidden": "hidden", "proposed": "proposed", "map_space": "map_space"}
    for kind, value in flags.items():
        if value is not None and not isinstance(value, bool):
            raise TypeError(f"world_graph: {names[kind]} is a boolean; got {value!r}.")
    seen_rung = reader["as"]["rung"] if reader["rung"] == "owner" and reader.get("as") is not None else reader["rung"]
    for kind in ("hidden", "proposed"):
        if flags[kind] and seen_rung != "owner":
            raise ValueError(f"world_graph: {names[kind]} is the owner's alone; a {seen_rung} reader may not ask it.")
    if seen_rung == "public":
        for kind in ("room", "map_space"):
            if flags[kind]:
                raise ValueError(f"world_graph: a public reader takes no flag; it asked {names[kind]}.")
    if as_of is not None and _whole(as_of) is None:
        raise TypeError(f"world_graph: as_of is a whole number; got {as_of!r}.")
    if clock is not None and _instant(clock)[0]:
        raise TypeError(f"world_graph: clock is a date-time; got {clock!r}.")
    if lens is not None and not isinstance(lens, str | Mapping):
        raise TypeError("world_graph: lens is a lens body or its id.")

    r = _Reading(world, reader, _reading_date(world, as_of))
    seen_owner = r.seen_rung == "owner"

    def kinds(eid: str) -> list[str]:
        out: list[str] = []
        if eid in r.room:
            out.append("room")
        if eid in r.hidden:
            out.append("hidden")
        if eid in r.proposed:
            out.append("proposed")
        if r.type_of[eid] in _MAP_SPACE:
            out.append("map_space")
        return out

    def candidate(eid: str) -> bool:
        # What the reader could see as a node: its view, and for the owner what is written as proposed too.
        return eid in r.view or (seen_owner and eid in r.proposed)

    node_ids: set[str] = set()
    cut: dict[str, int]
    reason_of: Callable[[str], str | None]
    unreadable: str | None = None
    if lens is not None:
        reading, cut_by_id = _lens_reading(r, lens, clock)
        node_ids.update(reading["kept"])
        cut = dict(reading["cut"])
        unreadable = reading["unreadable"]

        def lens_reason(eid: str) -> str | None:
            why = cut_by_id.get(eid)
            if why is not None:
                return why
            return "outside_lens" if eid in r.view else "not_visible"

        reason_of = lens_reason

    else:

        def out_by(eid: str) -> str | None:
            return next((k for k in kinds(eid) if not flags[k]), None)

        counts: dict[str, int] = {}
        for eid in r.order:
            if not candidate(eid):
                continue
            why = out_by(eid)
            if why is None:
                node_ids.add(eid)
            else:
                counts[why] = counts.get(why, 0) + 1
        cut = _tally(counts, r.owner)

        def flag_reason(eid: str) -> str | None:
            return out_by(eid) if candidate(eid) else "not_visible"

        reason_of = flag_reason

    ids = sorted(node_ids)
    nodes: list[GraphNode] = []
    for eid in ids:
        kind = r.type_of[eid]
        name = r.by_id[eid].get("name")
        node: GraphNode = {
            "id": eid,
            "type": kind,
            "name": name if isinstance(name, str) else None,
            "family": ELEMENT_FAMILIES[kind],
            "icon": ELEMENT_ICONS[kind],
        }
        present = kinds(eid)
        marks: list[GraphMark] = [m for m in _MARKS if m in present]
        if marks:
            node["marks"] = marks
        if eid in r.stubs:
            node["known_of"] = True
        nodes.append(node)

    edges: list[GraphEdge] = []
    cut_edges: dict[str, int] = {}

    def visit(source: str, field: str, target: Any, index: int) -> None:
        if not isinstance(target, str) or target not in r.by_id:
            return
        if target in node_ids:
            edges.append({"source": source, "field": field, "target": target, "index": index})
            return
        why = reason_of(target)
        if why is not None:
            cut_edges[why] = cut_edges.get(why, 0) + 1

    for source in ids:
        if source in r.stubs:
            continue
        el = r.by_id[source]
        # A schema link is served whole to the owner; any other view is served it less the ids outside that view.
        for field, many in _LINK_FIELDS.get(r.type_of[source], ()):
            v = el.get(field)
            entries: list[Any] = (v if isinstance(v, list) else []) if many else [v]
            served = 0
            for i, t in enumerate(entries):
                in_served = seen_owner or (isinstance(t, str) and t in r.view)
                visit(source, field, t, i if seen_owner else served)
                if in_served:
                    served += 1
        # A declared extension link is served as stored to every reader.
        for field in _DECLARED_LINKS:
            v = el.get(field)
            if isinstance(v, list):
                for i, t in enumerate(v):
                    visit(source, field, t, i)
    edges.sort(key=lambda e: (e["source"], e["field"], e["index"]))
    return {
        "nodes": nodes,
        "edges": edges,
        "edges_cut": _tally(cut_edges, r.owner),
        "cut": cut,
        "unreadable": unreadable,
    }


def degree_of(graph: Mapping[str, Any]) -> dict[str, int]:
    """Each node's degree in a graph ``world_graph`` answered: the number of its edges, in or out, each edge
    counted once for every node it touches (a mirror pair is two edges, so each end counts 2; a link to itself
    counts once). Every node is a key, 0 included, in the graph's node order. Edges join nodes only, so the count
    is the reader's: what the reading left out (hidden, room, proposed, map space, past a lens) is never counted.
    This is "most linked" for a finder: rank by it, highest first. A graph that is not one is a TypeError. The
    npm SDK's ``degreeOf`` gives the same answer on the same graph."""
    if (
        not isinstance(graph, Mapping)
        or not isinstance(graph.get("nodes"), list)
        or not isinstance(graph.get("edges"), list)
    ):
        raise TypeError("degree_of: graph is what world_graph answers, a mapping with nodes and edges lists.")
    count: dict[str, int] = {n["id"]: 0 for n in graph["nodes"]}
    for e in graph["edges"]:
        if e["source"] in count:
            count[e["source"]] += 1
        if e["target"] != e["source"] and e["target"] in count:
            count[e["target"]] += 1
    return count

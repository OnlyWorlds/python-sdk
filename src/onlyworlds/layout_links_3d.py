"""A 3D layout method for a world nobody laid out, read from its graph and its Maps and Pins: ``by-links-3d``.

The parts live in the private ``onlyworlds._layout3d``, one module a step, and the directions table is baked into the
package (``onlyworlds._directions``, generated from ``codegen/layout/directions.json``). The method is exact where it
can be: everything but the cosine and sine that place what hangs off the body, and the arcsine, cosine and sine that
set the other pieces on their ring, is addition, subtraction, multiplication, division, square root and floor, which
every runtime rounds alike. It gives the same answer as the npm SDK's ``layoutByLinks3d``: the method's fixture, as the
schema distribution publishes it (``codegen/schema-dist/profiles/layout-by-links-3d.fixture.json``, sha256 held by both
packages' tests), is replayed whole.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any, Literal, TypedDict, cast

from ._directions import DIRECTIONS
from ._layout3d.method import HeldRangeError, HeldTypeError
from ._layout3d.pieces import layout_pieces
from ._layout3d.space import space_rows
from .layout_kind import _placed_ids

__all__ = [
    "BY_LINKS_3D_REST",
    "BY_LINKS_3D_VERSION",
    "HeldRangeError",
    "HeldTypeError",
    "LayoutByLinks3d",
    "layout_by_links_3d",
    "unplaced_by_links_3d",
]

#: The rest length of the by-links-3d layout: a link's length at rest, and the unit of its answer's points.
BY_LINKS_3D_REST = 60.0

#: The version of ``layout_by_links_3d``'s answers: raised whenever the answer to any case of the method's fixture
#: changes (a constant, a rule, a fix that moves a point), and never for a release that moves none. A tool that keeps
#: a picture to hand back as ``held`` stores it beside the points and reads another value as no picture kept, so a
#: change to the method lays the world out fresh instead of holding points the method no longer gives. The npm SDK's
#: ``BY_LINKS_3D_VERSION`` has the same value.
BY_LINKS_3D_VERSION = 2


class LayoutByLinks3d(TypedDict):
    """What ``layout_by_links_3d`` answers: one row per placed node, in the order the nodes were handed in, and the
    nodes it does not place."""

    #: The method's word, ``by-links-3d``, as the layout profile's page names it.
    method: Literal["by-links-3d"]
    #: The placed nodes' ids, in the order handed in.
    ids: list[str]
    #: x, y, z of ``ids[i]`` at ``3 * i``, in units where a link at rest is ``BY_LINKS_3D_REST`` long.
    points: list[float]
    #: How each element was placed: ``centre`` (a group's centre), ``with`` (in a centre's group), ``arm`` (hanging
    #: off the body, more than one link out or with links of its own), ``link`` (an element whose only link is to the
    #: body), ``map`` (at its Pin on the world's map). In a piece other than the main one the words mean what they
    #: mean in the main shape.
    how: list[Literal["centre", "with", "arm", "link", "map"]]
    #: The id of the centre the element stands with (a centre's own id, a pinned centre's too), or None.
    group: list[str | None]
    #: None where ``group`` is an id; else ``map`` (pinned, no centre) or ``one-link`` (``arm`` or ``link``).
    part: list[Literal["map", "one-link"] | None]
    #: The centres' ids: the main piece's in rank order, then each other piece's, the pieces in the ring's order.
    centres: list[str]
    #: True where the point answered is the element's held point; False everywhere when nothing is held. A pinned
    #: element stands at its Pin and is never held, so False does not mean new: what is new is every id that was not
    #: handed in.
    held: list[bool]
    #: The ids of the nodes not placed, by id in code point order: every node linked to no other and pinned on no
    #: map, a held one too.
    unplaced: list[str]


def layout_by_links_3d(
    graph: Mapping[str, Any],
    elements: Iterable[Any] | None = None,
    *,
    held: Mapping[str, Sequence[float]] | None = None,
    held_unit: float | None = None,
) -> LayoutByLinks3d:
    """Lay out a graph in three dimensions by its links: every node linked to another node or pinned on a map.

    The body of the graph (its largest piece that no single element's removal parts) is cut into groups round its
    centres, the elements with most links (twelve at most, more when a group that holds over half the body is split);
    the groups are packed apart in directions read from a table baked into the package, and for 300 seeded force
    steps links pull, near elements push apart and every element is held to its group's point. What hangs off the
    body by one element is fanned out from it. When the world has a Map that holds three or more elements of the
    graph by a Pin, the Map that holds the most (a tie to the greater id) is a flat plate, each of its pinned elements
    at its Pin, the groups whose centre is pinned standing over it; a Map over a place on that plate is a small plate a
    little above it. A Map whose width or height is not over 0 is no plate, and when it is the Map that holds the
    most, the world is laid out by its links alone. A Pin's z is not read: the plate is flat. A layout map (a Map
    whose ``x_layout`` names a method, the map-space profile's mark) is never the plate: a saved layout never stands
    in for the world's own space.

    Each other piece of the graph that holds a pair of linked elements is laid out the same way on its own. One that
    holds a pinned element (held at its Pin) or a held element stands where those points put it; every other is set
    on a ring round the main shape, level with the main shape's middle, larger pieces first (a tie to the piece that
    holds the smaller id), no nearer than 1.8 rests (108 units) to anything placed before the ring or to another ring
    piece; a ring that is full opens the next one further out. An element linked to no other and pinned on no map is
    not placed: the answer lists it in ``unplaced``.

    ``graph`` is ``world_graph``'s answer, or any mapping of the same shape: ``nodes`` (each with ``id`` and
    ``type``) and ``edges`` (each with ``source`` and ``target``, and ``field`` and ``index`` where it has them), the
    same graph ``layout_by_kind`` takes. ``elements`` is the world's elements as served (any types; only Map and Pin
    elements are read, by ``map_space`` and ``layout_of``), or None for none. The graph is first put in one order
    (nodes by id in code point order; links by source, field, index, then target), so the order the nodes and links
    are handed in moves no point. The same input gives the same points in every runtime, the npm SDK's
    ``layoutByLinks3d`` included: to the last bit for every element placed ``centre``, ``with`` or ``map`` that does
    not stand on the ring, and for every held element; within a billionth of a rest for the rest, which are placed
    with the runtime's own cosine and sine (and, on the ring, its arcsine).

    Answers a ``LayoutByLinks3d``: ``method`` (``"by-links-3d"``), ``ids`` (the placed nodes' ids in the order handed
    in), ``points`` (a flat list, x, y, z of ``ids[i]`` at ``3 * i``, in units where a link at rest is
    ``BY_LINKS_3D_REST``, 60, long), and per placed node ``how``, ``group``, ``part`` and ``held``, with ``centres``
    the main piece's centres in rank order, then each other piece's, the pieces in the ring's order, and ``unplaced``
    the ids of the nodes not placed, by id in code point order. An empty graph answers every list empty.

    ``held`` hands back points an earlier answer gave, so the picture keeps still as the world changes: element id to
    ``[x, y, z]``, exactly three finite numbers (a slice of an earlier answer's ``points`` will do). A held element
    that is still a node and is not pinned stands at its held point, and the answer's ``held`` says which; the rest
    is laid out round the held ones: a group with held members starts from them, and when held elements on the
    world's first map agree on where that map stood, the map is put back there. A pinned element stands at its Pin
    whatever is held for it. An id that is no node is passed over, and so is that of a node linked to no other and
    pinned on no map: a held point alone places nothing. ``held_unit`` is the step the held points were
    rounded to, in the answer's units (a saver that keeps whole numbers: 1), so the map's place is still found from
    rounded points: a finite number from 0 to an eighth of ``BY_LINKS_3D_REST``. None, or left out, for either: the
    method as it is.

    Refused, each an error with a ``code``, before any step of the layout runs: ``held`` that is not a mapping,
    ``HeldTypeError`` ``held-not-object``; a held value that is not a list or tuple of three finite numbers (every
    value read, under an id that is no node too), ``HeldTypeError`` ``held-not-point``; a ``held_unit`` that is not
    None and not a finite number from 0 to an eighth of a rest, ``HeldRangeError`` ``held-unit``. Then each layout
    run tests the held points it holds, the main piece's first and then each other piece's in the ring's order (a
    piece's Pins counted among them): spread wider than 768 rests on any axis, ``HeldRangeError`` ``held-box``.
    ``HeldTypeError`` is a ``TypeError`` and ``HeldRangeError`` a ``ValueError``; both are importable from
    ``onlyworlds.layout_links_3d``. A graph that is not ``{nodes, edges}`` raises ``TypeError``; two nodes with one id
    raise ``ValueError``.

    The method is pure Python, so a large world is slow: a world of several thousand elements takes minutes (about
    nine for 8,899 elements on the machine it was measured on).

    The method's word, ``by-links-3d``, is the layout profile's page's. ``BY_LINKS_3D_VERSION`` says when a release
    moves its points.
    """
    nodes = graph.get("nodes") if isinstance(graph, Mapping) else None
    edges = graph.get("edges") if isinstance(graph, Mapping) else None
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise TypeError("layout_by_links_3d: the graph is {nodes, edges}, as world_graph answers it")
    rows = space_rows(list(elements) if elements is not None else None)
    return cast(LayoutByLinks3d, layout_pieces(nodes, edges, rows, DIRECTIONS, held=held, held_unit=held_unit))


def unplaced_by_links_3d(graph: Mapping[str, Any], placed: Iterable[Any]) -> list[str]:
    """What a saved ``by-links-3d`` layout map does not place.

    Answers the ids of the graph's nodes that are not in ``placed``, by id in code point order. Every node of the
    graph counts, of any type, also one the method would not place (linked to no other and pinned on no map), so for
    the Map an answer makes this is that answer's own ``unplaced``. ``placed`` is the
    ids of the elements the Map's Pins stand for, a list or a set: from ``map_space``, the ``element_id`` of each pin
    whose ``map`` is this Map. A member that is not a non-empty string (a Pin that stands for no element) is passed
    over, and an id that is no node of the graph is no part of the answer. The answer's length is the count a tool
    shows; reading or drawing a layout map never changes it. The npm SDK's ``unplacedByLinks3d`` answers the same
    list.

    Raises ``TypeError`` on a graph that is not ``{nodes, edges}`` or a ``placed`` that is not a list or a set, and,
    as ``layout_by_links_3d`` does, ``ValueError`` when two nodes share an id.
    """
    nodes = graph.get("nodes") if isinstance(graph, Mapping) else None
    edges = graph.get("edges") if isinstance(graph, Mapping) else None
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise TypeError("unplaced_by_links_3d: the graph is {nodes, edges}, as world_graph answers it")
    taken = _placed_ids("unplaced_by_links_3d", placed)
    ids = sorted(x["id"] for x in nodes)
    for i in range(1, len(ids)):
        if ids[i] == ids[i - 1]:
            raise ValueError(f"unplaced_by_links_3d: two nodes share the id {ids[i]}")
    return [i for i in ids if i not in taken]

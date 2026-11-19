"""The by-links-3d layout, steps 10 to 12: the pieces, the ring and the answer. A wrapper round ``method.layout3d``:
one run on the whole graph, one run on each other piece that holds a pair; no rule of a run is written again here.

    layout_pieces(nodes, edges, rows, table, held=None, held_unit=None) -> answer

  nodes, edges, rows, table, held, held_unit   as ``layout3d`` takes them (its head)

The answer: {"method", "ids", "points" (3n floats), "how", "group", "part", "centres", "held", "unplaced"}: ids to
held over the placed nodes only, in the order handed in; ``unplaced`` the ids of the nodes that are a piece of one and
not pinned, by id (code point order); ``centres`` the main run's that are placed, then each other piece's, the pieces
in the ring's order.

In this order:
  0. the refusals on the caller's whole ``held``: its shape (``held-not-object``, ``held-not-point``), then
     ``held_unit``; the box waits for the runs;
  1. the pieces: the undirected pairs as ``layout3d`` builds them (a link whose end is no node passed over, a self-link
     none); a node in no pair is a piece of one; the main piece the largest, a tie to the smaller least id;
  2. the main run: ``layout3d`` on the whole graph with the Maps and Pins, holding the held points of the main piece's
     nodes (when it holds a pair) and of every node step 4 places; a node is pinned when this run answers it ``map``.
     It keeps every node of the main piece (when it holds a pair) and every pinned node;
  3. each other piece of two or more: ``layout3d`` on its nodes and the links between them, no Maps and Pins, holding
     each pinned node at its main-run point and each other node at its held point, where it has one. A piece that holds
     a pinned or held node is not moved; every other is a ring piece. Each run tests the box of what it holds: the main
     run first, then the pieces in the ring's order;
  4. the main shape: M the mean of the kept nodes' points (id order); Rmain the greatest distance from M over them and
     over every node of a piece that is not moved;
  5. each ring piece's c (the mean of its run's points, id order) and r (the greatest distance from c); the ring's
     order: by size, larger first, a tie to the smaller least id; rmax the greatest r;
  6. the rings: ring 0 at R = Rmain + RING_GAP + rmax, each next at R + 2 * rmax + RING_GAP; each piece's angle
     th = 2 * asin((r + RING_GAP / 2) / R); a piece joins a ring when it is the ring's first or the angles summed so far
     plus its own are at most 2 pi - FIT; each ring's left-over angle shared equally, one share after each piece; every
     ring in the plane z = M.z, the first piece of each at +x;
  7. the answer, in the handed order.

math.asin, math.cos and math.sin place the ring pieces, and are not correctly rounded in every runtime: a ring piece's
points can differ from another runtime's in the last places. Everything else here is + - * / and sqrt, every sum
taken in id order, the same double in every runtime.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

from .method import REST, layout3d, read_held, read_unit
from .plate import plate as plate_of
from .points import CLEAR, Table

RING_GAP = CLEAR * REST  # the ring's gap, the packing's own clearance: 108 units
FIT = 1e-6  # the fit's margin, in radians: a piece joins a ring while the angles sum to at most 2 pi - FIT
TWO_PI = 2 * math.pi
FIT_EDGE = TWO_PI - FIT  # one double, worked out once


def layout_pieces(
    nodes: Sequence[Mapping[str, Any]],
    edges: Sequence[Mapping[str, Any]],
    rows: Sequence[Any] | None,
    table: Table,
    held: Any = None,
    held_unit: Any = None,
) -> dict[str, Any]:
    # 0. the shape refusals on the caller's whole held, then held_unit; the box waits for the runs
    read_held(held, box=False)
    read_unit(held_unit)
    n = len(nodes)
    if not n:
        # no node: no held id is a node's, so the one run holds none of them
        out = layout3d(nodes, edges, rows, table, held=None, held_unit=held_unit)
        out["unplaced"] = []
        return out
    handed = [x["id"] for x in nodes]
    main_row = {id_: i for i, id_ in enumerate(handed)}

    # 1. the pieces
    ids = sorted(handed)
    for i in range(1, n):
        if ids[i] == ids[i - 1]:
            raise ValueError(f"layout_by_links_3d: two nodes share the id {ids[i]}")
    at = {id_: i for i, id_ in enumerate(ids)}
    parent = list(range(n))

    def find(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for e in edges:
        a, b = at.get(e["source"]), at.get(e["target"])
        if a is None or b is None or a == b:
            continue
        ra, rb = find(a), find(b)
        if ra != rb:
            if ra < rb:
                parent[rb] = ra
            else:
                parent[ra] = rb
    piece_of = [-1] * n
    members: list[list[int]] = []  # each piece's nodes in id order; the pieces in the order of their least id
    for v in range(n):
        r = find(v)
        if piece_of[r] == -1:
            piece_of[r] = len(members)
            members.append([])
        piece_of[v] = piece_of[r]
        members[piece_of[v]].append(v)
    main_p, main_size = -1, 0
    for p in range(len(members)):
        if len(members[p]) > main_size:
            main_size, main_p = len(members[p]), p

    # 2. the main run, holding the held points of its piece's nodes and of every node step 4 places
    held_all: Mapping[str, Any] = held if held is not None else {}
    on_map: set[str] = set()
    if rows:
        pa = plate_of(rows, ids)
        if pa:
            on_map = {el for el, _xyz in pa["at"]}
    main_set = {ids[v] for v in members[main_p]} if main_size >= 2 else set()
    main_held = {id_: q for id_, q in held_all.items() if id_ in main_set or id_ in on_map}
    main = layout3d(nodes, edges, rows, table, held=None if held is None else main_held, held_unit=held_unit)
    ma: list[float] = main["points"]

    # 2. what the answer keeps from the main run
    pinned, keep = [0] * n, [0] * n
    for v in range(n):
        if main["how"][main_row[ids[v]]] == "map":
            pinned[v] = 1
        if (main_size >= 2 and piece_of[v] == main_p) or pinned[v]:
            keep[v] = 1

    # the ring's order: by size, larger first; a tie to the smaller least id
    others = [p for p in range(len(members)) if p != main_p and len(members[p]) >= 2]
    others.sort(key=lambda p: (-len(members[p]), ids[members[p][0]]))

    # 3. each other piece of two or more, run alone
    runs: dict[int, dict[str, Any]] = {}
    for p in others:
        in_p = {ids[v] for v in members[p]}
        pnodes = [x for x in nodes if x["id"] in in_p]
        pedges = [e for e in edges if e["source"] in in_p and e["target"] in in_p]
        # its held points: each pinned node's main-run point, and the held point of each other node that has one
        sub: dict[str, Any] = {}
        for v in members[p]:
            if pinned[v]:
                m = main_row[ids[v]]
                sub[ids[v]] = [ma[3 * m], ma[3 * m + 1], ma[3 * m + 2]]
            elif ids[v] in held_all:
                sub[ids[v]] = held_all[ids[v]]
        ans = layout3d(pnodes, pedges, None, table, held=sub if sub else None, held_unit=held_unit)
        runs[p] = {
            "ans": ans,
            "row": {id_: i for i, id_ in enumerate(ans["ids"])},
            "ring": not sub,  # a held or a pinned node: not moved; neither: on the ring
            "T": None,
            "c": None,
            "r": 0.0,
        }

    # 4. the main shape: M over the kept nodes, in id order; Rmain over the kept nodes and every node of a piece that
    # is not moved, at its final point
    cnt, sx, sy, sz = 0, 0.0, 0.0, 0.0
    for v in range(n):
        if not keep[v]:
            continue
        m = main_row[ids[v]]
        sx += ma[3 * m]
        sy += ma[3 * m + 1]
        sz += ma[3 * m + 2]
        cnt += 1
    M = [sx / cnt, sy / cnt, sz / cnt] if cnt else [0.0, 0.0, 0.0]
    rmain = 0.0
    for v in range(n):
        if not keep[v]:
            continue
        m = main_row[ids[v]]
        dx, dy, dz = ma[3 * m] - M[0], ma[3 * m + 1] - M[1], ma[3 * m + 2] - M[2]
        d = math.sqrt(dx * dx + dy * dy + dz * dz)
        if d > rmain:
            rmain = d
    for p in others:
        u = runs[p]
        if u["ring"]:
            continue
        pp: list[float] = u["ans"]["points"]
        for v in members[p]:
            if pinned[v]:
                continue  # kept: read above, at its main-run point
            j = u["row"][ids[v]]
            dx, dy, dz = pp[3 * j] - M[0], pp[3 * j + 1] - M[1], pp[3 * j + 2] - M[2]
            d = math.sqrt(dx * dx + dy * dy + dz * dz)
            if d > rmain:
                rmain = d

    # 5. each ring piece's c and r, over its run's points in id order
    ring_list = [p for p in others if runs[p]["ring"]]
    for p in ring_list:
        u = runs[p]
        pp = u["ans"]["points"]
        qx, qy, qz = 0.0, 0.0, 0.0
        for v in members[p]:
            i = u["row"][ids[v]]
            qx += pp[3 * i]
            qy += pp[3 * i + 1]
            qz += pp[3 * i + 2]
        k = len(members[p])
        c = [qx / k, qy / k, qz / k]
        rp = 0.0
        for v in members[p]:
            i = u["row"][ids[v]]
            dx, dy, dz = pp[3 * i] - c[0], pp[3 * i + 1] - c[1], pp[3 * i + 2] - c[2]
            d = math.sqrt(dx * dx + dy * dy + dz * dz)
            if d > rp:
                rp = d
        u["c"], u["r"] = c, rp

    # 6. the rings: rmax over every ring piece; ring 0 at Rmain + RING_GAP + rmax, each next at R + 2 * rmax + RING_GAP
    rmax = 0.0
    for p in ring_list:
        if runs[p]["r"] > rmax:
            rmax = runs[p]["r"]
    rings: list[tuple[float, list[tuple[int, float]], float]] = []  # (R, [(piece, th)], sum)
    R, total = rmain + RING_GAP + rmax, 0.0
    on: list[tuple[int, float]] = []
    for p in ring_list:
        u = runs[p]
        th = 2 * math.asin((u["r"] + RING_GAP / 2) / R)
        if on and not (total + th <= FIT_EDGE):  # a ring holds at least one piece; one that does not fit opens the next
            rings.append((R, on, total))
            R = R + 2 * rmax + RING_GAP
            on, total = [], 0.0
            th = 2 * math.asin((u["r"] + RING_GAP / 2) / R)
        on.append((p, th))
        total += th
    if on:
        rings.append((R, on, total))
    for R, on, total in rings:
        share = (TWO_PI - total) / len(on)
        acc = 0.0
        for p, th in on:
            phi = acc + th / 2
            acc += th + share
            u = runs[p]
            c = u["c"]
            u["T"] = [M[0] + R * math.cos(phi) - c[0], M[1] + R * math.sin(phi) - c[1], M[2] - c[2]]

    # 7. the answer: the placed nodes in the order handed in
    out_ids: list[str] = []
    pts: list[float] = []
    how: list[Any] = []
    group: list[Any] = []
    part: list[Any] = []
    held_out: list[bool] = []
    unplaced: list[str] = []
    for id_ in handed:
        v = at[id_]
        if keep[v]:
            m = main_row[id_]
            out_ids.append(id_)
            pts += [ma[3 * m], ma[3 * m + 1], ma[3 * m + 2]]
            how.append(main["how"][m])
            group.append(main["group"][m])
            part.append(main["part"][m])
            held_out.append(main["held"][m])
            # a pinned node its piece's run makes a centre answers as a pinned centre of the main shape does: group its
            # own id, part None
            pr = runs.get(piece_of[v]) if pinned[v] and piece_of[v] != main_p else None
            if pr is not None and id_ in pr["ans"]["centres"]:
                group[-1], part[-1] = id_, None
            continue
        p = piece_of[v]
        if len(members[p]) < 2:
            unplaced.append(id_)
            continue
        u = runs[p]
        j = u["row"][id_]
        a = u["ans"]
        x, y, z = a["points"][3 * j], a["points"][3 * j + 1], a["points"][3 * j + 2]
        T = u["T"]
        if T is not None:
            x, y, z = x + T[0], y + T[1], z + T[2]
        out_ids.append(id_)
        pts += [x, y, z]
        how.append(a["how"][j])
        group.append(a["group"][j])
        part.append(a["part"][j])
        held_out.append(a["held"][j])
    unplaced.sort()  # by id, in code point order
    placed = set(out_ids)
    centres = [id_ for id_ in main["centres"] if id_ in placed]
    for p in others:
        centres += runs[p]["ans"]["centres"]
    return {
        "method": main["method"],
        "ids": out_ids,
        "points": pts,
        "how": how,
        "group": group,
        "part": part,
        "centres": centres,
        "held": held_out,
        "unplaced": unplaced,
    }

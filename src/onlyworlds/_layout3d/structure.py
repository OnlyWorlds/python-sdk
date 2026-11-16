"""The by-links-3d layout, step 2: the graph's structure.

    structure(ids, pairs) -> {"ids": sorted ids, "body": [0|1]*n, "hangCut": [int]*n (-1 none),
                              "hangDepth": [int]*n, "off": [0|1]*n}

Three walks, in this order:
  1. the pieces (the parts of the graph joined by links): the main piece is the largest, a tie to the piece with the
     least id;
  2. the main piece's blocks (the parts that no single element's removal parts): the body is the largest block; of
     two largest blocks of one size, the body is the one whose members' places, in rising order, come later at the
     first place they differ (after(), below), whichever the walk closes first;
  3. outward from the body: for each other element of the main piece, the body element it hangs through (its cut) and
     how many links away it is.
An element not in the main piece is off.

Ids are put in code point order (Python's own string order). An id handed twice keeps its later place. A pair whose
end is no id, or whose two ends are one element, is passed over.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any


def after(a: list[int], b: list[int]) -> bool:
    """a and b: two blocks of one size, each its members' places in rising order. True when a comes after b."""
    for i in range(len(a)):
        if a[i] != b[i]:
            return a[i] > b[i]
    return False


def structure(ids: Sequence[str], pairs: Sequence[Sequence[str]]) -> dict[str, Any]:
    sorted_ids = sorted(ids)
    at = {id_: i for i, id_ in enumerate(sorted_ids)}
    n = len(sorted_ids)
    # the links as two rows per link, grouped by element
    deg = [0] * (n + 1)
    ea = [0] * len(pairs)
    eb = [0] * len(pairs)
    m = 0
    for pr in pairs:
        x, y = pr[0], pr[1]
        a = at.get(x)
        b = at.get(y)
        if a is None or b is None or a == b:
            continue
        ea[m] = a
        eb[m] = b
        m += 1
        deg[a + 1] += 1
        deg[b + 1] += 1
    for i in range(n):
        deg[i + 1] += deg[i]
    fill = deg[:n]
    nb = [0] * (2 * m)
    for k in range(m):
        nb[fill[ea[k]]] = eb[k]
        fill[ea[k]] += 1
        nb[fill[eb[k]]] = ea[k]
        fill[eb[k]] += 1

    # 1. the pieces
    piece = [-1] * n
    queue = [0] * n
    main, main_size, pieces = -1, 0, 0
    for s in range(n):
        if piece[s] != -1:
            continue
        head, tail = 0, 0
        queue[tail] = s
        tail += 1
        piece[s] = pieces
        while head < tail:
            v = queue[head]
            head += 1
            for k in range(deg[v], deg[v + 1]):
                w = nb[k]
                if piece[w] == -1:
                    piece[w] = pieces
                    queue[tail] = w
                    tail += 1
        # s rises, so an equal later piece has the larger least id: the first of that size stays
        if tail > main_size:
            main_size = tail
            main = pieces
        pieces += 1

    # 2. the main piece's blocks; the largest is the body
    body = [0] * n
    if main_size == 1:
        for i in range(n):
            if piece[i] == main:
                body[i] = 1
    elif main_size > 1:
        disc = [-1] * n
        low = [0] * n
        parent = [-1] * n
        nxt = [0] * n
        stack_v = [0] * n
        edge_a = [0] * m
        edge_b = [0] * m
        stamp = [-1] * n
        best: list[int] = []
        blocks, clock, top, etop = 0, 0, 0, 0
        root = 0
        while piece[root] != main:
            root += 1
        disc[root] = clock
        low[root] = clock
        clock += 1
        nxt[root] = deg[root]
        stack_v[top] = root
        top += 1
        while top:
            v = stack_v[top - 1]
            if nxt[v] < deg[v + 1]:
                w = nb[nxt[v]]
                nxt[v] += 1
                if disc[w] == -1:
                    parent[w] = v
                    disc[w] = clock
                    low[w] = clock
                    clock += 1
                    nxt[w] = deg[w]
                    edge_a[etop] = v
                    edge_b[etop] = w
                    etop += 1
                    stack_v[top] = w
                    top += 1
                elif w != parent[v] and disc[w] < disc[v]:
                    edge_a[etop] = v
                    edge_b[etop] = w
                    etop += 1
                    if disc[w] < low[v]:
                        low[v] = disc[w]
            else:
                top -= 1
                u = parent[v]
                if u == -1:
                    continue
                if low[v] < low[u]:
                    low[u] = low[v]
                if low[v] >= disc[u]:
                    # u parts v's side from the rest: the edges down to (u, v) are one block
                    members: list[int] = []
                    while True:
                        etop -= 1
                        a = edge_a[etop]
                        b = edge_b[etop]
                        if stamp[a] != blocks:
                            stamp[a] = blocks
                            members.append(a)
                        if stamp[b] != blocks:
                            stamp[b] = blocks
                            members.append(b)
                        if a == u and b == v:
                            break
                    if len(members) >= len(best):
                        members.sort()
                        wins = len(members) > len(best)
                        if not wins:
                            wins = after(members, best)
                        if wins:
                            best = members
                    blocks += 1
        for v in best:
            body[v] = 1

    # 3. outward from the body: the joint each other element of the main piece hangs through, and how far
    hang_cut = [-1] * n
    hang_depth = [0] * n
    head, tail = 0, 0
    for i in range(n):
        if body[i]:
            queue[tail] = i
            tail += 1
    while head < tail:
        v = queue[head]
        head += 1
        for k in range(deg[v], deg[v + 1]):
            w = nb[k]
            if body[w] or hang_cut[w] != -1:
                continue
            hang_cut[w] = v if body[v] else hang_cut[v]
            hang_depth[w] = hang_depth[v] + 1
            queue[tail] = w
            tail += 1
    off = [0] * n
    for i in range(n):
        if piece[i] != main:
            off[i] = 1
    return {"ids": sorted_ids, "body": body, "hangCut": hang_cut, "hangDepth": hang_depth, "off": off}

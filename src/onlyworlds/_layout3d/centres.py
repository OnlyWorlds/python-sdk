"""The by-links-3d layout, step 3: the centres and the groups.

    centres(ids, pairs, body) -> {"ids": sorted ids, "taken": [int], "group": [int]*n, "dist": [int]*n}

Among the body's elements, the centres are picked by their links to other body elements, most first (a tie to the
lower place): an element is a centre when it has at least max(3, the root of the body's size rounded up) such links
and fewer than twelve centres are taken, unless half or more of those neighbours are one taken centre or that
centre's neighbours (then it is passed over). Each body
element joins the centre it has the most shortest paths from (a tie to the earlier centre); a group under three
members gives its centre up, the last-ranked of the small ones first. Then, at most twice, a group holding more than
half the body is split by the same picking among its own members.

Ids are put in code point order (Python's own string order). Each element's neighbours are read once each, in rising
place: a link handed twice is one neighbour. The path counts are doubles, each sum capped at 2^52, so every runtime
counts alike.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

MAX_CENTRES = 12
MIN_GROUP = 3
WAYS_CAP = float(2**52)

Rows = tuple[list[int], list[int]]


def rows(sorted_ids: Sequence[str], pairs: Sequence[Sequence[str]]) -> Rows:
    """The links as rows by element, each neighbour once and in rising index: a doubled link is one neighbour."""
    at = {id_: i for i, id_ in enumerate(sorted_ids)}
    n = len(sorted_ids)
    ea: list[int] = []
    eb: list[int] = []
    for pr in pairs:
        x, y = pr[0], pr[1]
        a = at.get(x)
        b = at.get(y)
        if a is None or b is None or a == b:
            continue
        ea.append(a)
        eb.append(b)
    m = len(ea)
    start = [0] * (n + 1)
    for k in range(m):
        start[ea[k] + 1] += 1
        start[eb[k] + 1] += 1
    for i in range(n):
        start[i + 1] += start[i]
    fill = start[:n]
    raw = [0] * (2 * m)
    for k in range(m):
        raw[fill[ea[k]]] = eb[k]
        fill[ea[k]] += 1
        raw[fill[eb[k]]] = ea[k]
        fill[eb[k]] += 1
    # each row sorted, doubles dropped
    deg = [0] * (n + 1)
    nb = [0] * (2 * m)
    out = 0
    for i in range(n):
        row = sorted(raw[start[i] : start[i + 1]])
        deg[i] = out
        for k in range(len(row)):
            if k == 0 or row[k] != row[k - 1]:
                nb[out] = row[k]
                out += 1
    deg[n] = out
    return deg, nb


def pick(n: int, g: Rows, members: list[int], in_set: Sequence[int]) -> tuple[list[int], list[int], list[int]]:
    """The centres among the set's members (rising indexes; in_set marks them) by their links to each other, and each
    member's group and distance (per element lists; -1 where not a member or not reached)."""
    deg, nb = g
    size = len(members)
    count = [0] * n
    for v in members:
        c = 0
        for k in range(deg[v], deg[v + 1]):
            if in_set[nb[k]]:
                c += 1
        count[v] = c
    ranked = sorted(members, key=lambda a: (-count[a], a))
    f = 0
    while f * f < size:
        f += 1
    floor = 3 if 3 > f else f  # noqa: SIM300

    # mark[w] bit r: w is centre r or one of its neighbours in the set
    mark = [0] * n
    hit = [0] * MAX_CENTRES
    taken: list[int] = []
    for v in ranked:
        if count[v] < floor or len(taken) == MAX_CENTRES:
            break
        for r in range(MAX_CENTRES):
            hit[r] = 0
        for k in range(deg[v], deg[v + 1]):
            w = nb[k]
            if not in_set[w]:
                continue
            for r in range(len(taken)):
                hit[r] += (mark[w] >> r) & 1
        ok = True
        for r in range(len(taken)):
            if 2 * hit[r] >= count[v]:
                ok = False
                break
        if not ok:
            continue
        r = len(taken)
        taken.append(v)
        mark[v] |= 1 << r
        for k in range(deg[v], deg[v + 1]):
            if in_set[nb[k]]:
                mark[nb[k]] |= 1 << r
    if len(taken) == 0 and len(ranked):
        taken = [ranked[0]]

    while True:
        group, dist = reach(n, g, members, in_set, taken)
        sizes = [0] * len(taken)
        for v in members:
            if len(taken) and group[v] != -1:
                sizes[group[v]] += 1
        last = -1
        for r in range(len(taken)):
            if sizes[r] < MIN_GROUP:
                last = r
        if last == -1 or len(taken) == 1:
            return taken, group, dist
        del taken[last]  # the last-ranked of the small ones goes, then the reach is read again


def reach(n: int, g: Rows, members: list[int], in_set: Sequence[int], taken: list[int]) -> tuple[list[int], list[int]]:
    """Breadth-first from every centre at once. ways[v * K + r]: shortest paths from centre r to v, saturating."""
    deg, nb = g
    K = len(taken)
    dist = [-1] * n
    group = [-1] * n
    ways = [0.0] * (n * K)
    front = [0] * n
    nxt = [0] * n
    fl = 0
    for r in range(K):
        c = taken[r]
        dist[c] = 0
        ways[c * K + r] = 1.0
        front[fl] = c
        fl += 1
    d = 0
    while fl:
        d += 1
        nl = 0
        for i in range(fl):
            v = front[i]
            for k in range(deg[v], deg[v + 1]):
                w = nb[k]
                if not in_set[w]:
                    continue
                if dist[w] == -1:
                    dist[w] = d
                    nxt[nl] = w
                    nl += 1
                if dist[w] != d:
                    continue
                for r in range(K):
                    s = ways[w * K + r] + ways[v * K + r]
                    ways[w * K + r] = WAYS_CAP if WAYS_CAP < s else s  # noqa: SIM300  (the lesser of the cap and the sum)
        front, nxt = nxt, front
        fl = nl
    for r in range(K):
        group[taken[r]] = r
    for v in members:
        if dist[v] == 0:
            continue  # a centre: its own group
        if dist[v] == -1:
            continue  # not reached: in no group of this reach
        best = 0
        for r in range(1, K):
            if ways[v * K + r] > ways[v * K + best]:
                best = r
        group[v] = best
    return group, dist


def centres(ids: Sequence[str], pairs: Sequence[Sequence[str]], body: Sequence[int]) -> dict[str, Any]:
    sorted_ids = sorted(ids)
    n = len(sorted_ids)
    g = rows(sorted_ids, pairs)
    members: list[int] = []
    for i in range(n):
        if body[i]:
            members.append(i)
    taken, group, dist = pick(n, g, members, body)

    for _round in range(2):
        sizes = [0] * len(taken)
        for v in members:
            if 0 <= group[v] < len(sizes):  # an element in no group (-1) counts for none
                sizes[group[v]] += 1
        big = 0
        for r in range(1, len(taken)):
            if sizes[r] > sizes[big]:
                big = r
        if not len(taken) or 2 * sizes[big] <= len(members):
            break
        inside: list[int] = []
        in_set = [0] * n
        for v in members:
            if group[v] == big and v != taken[big]:
                inside.append(v)
                in_set[v] = 1
        sub_taken, sub_group, sub_dist = pick(n, g, inside, in_set)
        if len(sub_taken) < 2:
            break
        base = len(taken)
        taken = taken + sub_taken
        for v in inside:
            if sub_dist[v] != -1:
                group[v] = base + sub_group[v]
                dist[v] = sub_dist[v]
    return {"ids": sorted_ids, "taken": taken, "group": group, "dist": dist}

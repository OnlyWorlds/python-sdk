"""The by-links-3d layout, step 5: each group's point.

    points(ids, body, taken, group, pairs, edges, plate, table[, fixed, snap]) -> {"k", "size", "link", "opp", "slot",
        "ends", "dirs", "lobe", "cpt", "plate"}

  ids     the element ids in code point order (as structure() and centres() answer them)
  plate   None, or a mapping id -> [x, y] or [x, y, z]: each pinned element's place on the plate
  table   the directions table: for each count of parts K (the key, as a string), K unit vectors [x, y, z]
  fixed   None, or {"group": [0 | 1] * k, "at": [x, y, z] * k, "plate": [x, y, z] or None, "blind": bool}: the groups
          (and the plate) whose point is fixed; a group flag is read by its truth, an index past the list as false
  snap    None, or {"flag": [0 | 1] * n, "at": [x, y, z] * n, "near": number}; read only when there is a plate

The groups are counted (their sizes, the links between two groups, and the opposing links: a link whose field is one of
OPPOSING), each group is given one of the table's K directions (slots()), and the groups are packed as balls of radius
REST * LOBE * the cube root of their size, started apart in their directions (pack()). With a plate, the groups whose
centre is pinned stand over their centre's place, and the plate itself is one more part of the packing, its radius
CLEAR times the farthest pinned place from the plate's middle. With fixed parts the packing is pack_fixed().

Every sum runs in the order written and every expression keeps its grouping; brackets mark it where it is not plain
left to right. Math.max-style maxima keep a NaN (js_max()), and a division by a zero count is NaN (js_div()).
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

from .spread import cube_root

REST = 60.0
LOBE = 1.1
GAP = 1.25
CLEAR = 1.8
PACK_STEPS = 600
OPPOSING = ["rivals", "adversaries", "rival", "antagonist"]
NAN = float("nan")

Table = Mapping[str, Sequence[Sequence[float]]]


def neg_zero(v: float) -> bool:
    return v == 0 and str(v).startswith("-")


def js_max(a: float, b: float) -> float:
    """the greater of a and b: NaN when either is, and 0.0 over -0.0"""
    if a != a or b != b:
        return NAN
    if a > b:
        return a
    if b > a:
        return b
    return b if neg_zero(a) else a


def js_div(a: float, b: float) -> float:
    if b != 0:
        return a / b
    if a != a or a == 0:
        return NAN
    return -math.inf if (a < 0) != str(b).startswith("-") else math.inf


def to_double(v: Any) -> float:
    """a coordinate as a double: None is 0.0, a boolean 1.0 or 0.0"""
    if v is None:
        return 0.0
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    if isinstance(v, (int, float)):
        return float(v)
    raise TypeError(f"points: a coordinate that is no number ({v!r})")


def root(v: float) -> float:
    return cube_root(v)


def length3(dx: float, dy: float, dz: float) -> float:
    """math.sqrt(dx * dx + dy * dy + dz * dz), in that order"""
    return math.sqrt(dx * dx + dy * dy + dz * dz)


def length2(x: float, y: float) -> float:
    return math.sqrt(x * x + y * y)


def _index_key(k: str) -> int | None:
    """an array index: a canonical whole number below 2^32 - 1"""
    if not k or not k.isascii() or not k.isdigit():
        return None
    if len(k) > 1 and k[0] == "0":
        return None
    v = int(k)
    return v if v < 4294967295 else None


def object_entries(d: Mapping[str, Any]) -> list[tuple[str, Any]]:
    """a JSON object's entries as the npm SDK reads them: integer-like keys first in rising number, then the rest as
    written. The plate loop reads them for a maximum and a count, so the order cannot change the answer."""
    ints: list[tuple[int, str, Any]] = []
    rest: list[tuple[str, Any]] = []
    for k, v in d.items():
        i = _index_key(k)
        if i is None:
            rest.append((k, v))
        else:
            ints.append((i, k, v))
    ints.sort()
    return [(k, v) for (_i, k, v) in ints] + rest


def count(
    n: int, K: int, part: Sequence[int], at: Mapping[str, int], pairs: Sequence[Sequence[str]], edges: Sequence[Any]
) -> tuple[list[int], list[int], list[int]]:
    """size, link and opp over a labelling of the body into K parts (part[v] = -1 outside the body)."""
    size = [0] * K
    link = [0] * (K * K)
    opp = [0] * (K * K)
    for v in range(n):
        if part[v] != -1:
            size[part[v]] += 1
    seen: set[int] = set()
    for pr in pairs:
        x, y = pr[0], pr[1]
        a = at.get(x)
        b = at.get(y)
        if a is None or b is None or a == b:
            continue
        if a > b:
            a, b = b, a
        key = a * n + b
        if key in seen:
            continue
        seen.add(key)
        p, q = part[a], part[b]
        if p == -1 or q == -1 or p == q:
            continue
        if p < q:
            link[p * K + q] += 1
        else:
            link[q * K + p] += 1
    for e in edges:
        s = e[0]
        t = e[1] if len(e) > 1 else None
        field = e[2] if len(e) > 2 else None
        if not (isinstance(field, str) and field in OPPOSING):
            continue
        a = at.get(s)
        b = at.get(t)  # type: ignore[arg-type]
        if a is None or b is None:
            continue
        p, q = part[a], part[b]
        if p == -1 or q == -1 or p == q:
            continue
        if p < q:
            opp[p * K + q] += 1
        else:
            opp[q * K + p] += 1
    return size, link, opp


def by_size(K: int, size: Sequence[int]) -> list[int]:
    """The parts by size, largest first; a tie to the lower index."""
    return sorted(range(K), key=lambda i: (-size[i], i))


def slots(
    K: int, size: Sequence[int], link: Sequence[int], opp: Sequence[int], table: Table
) -> tuple[list[int], list[int] | None, list[float]]:
    """Which part stands in which of the K directions.

    The two ends: with an opposing link, the pair of parts with the most opposing links (a tie to the larger pair);
    else, among the four largest parts, the pair with the fewest links for their sizes. The ends take the first and
    the last direction; then each other part, largest first, takes the free direction where its links (less four
    times its opposing links) to the parts already placed are shortest in sum."""
    slot = [0] * K
    dirs = [0.0] * (3 * K)
    if K == 1:
        return slot, None, dirs  # one part: the zero point (slot 0)
    D = table.get(str(K))
    if not D or len(D) != K:
        raise ValueError(f"points: the table has no row of {K} directions")
    any_opp = False
    for i in range(K):
        for j in range(i + 1, K):
            if opp[i * K + j] > 0:
                any_opp = True
    b0, b1 = -1, -1
    if any_opp:
        bo, bs = -1, -1
        for i in range(K):
            for j in range(i + 1, K):
                o, s = opp[i * K + j], size[i] + size[j]
                if o > bo or (o == bo and s > bs):
                    bo, bs, b0, b1 = o, s, i, j
    else:
        order = by_size(K, size)
        m = K if K < 4 else 4
        big = sorted(order[:m])
        for x in range(m):
            for y in range(x + 1, m):
                i, j = big[x], big[y]
                if b0 == -1:
                    b0, b1 = i, j
                    continue
                lp, lq = link[i * K + j], link[b0 * K + b1]
                left, right = lp * size[b0] * size[b1], lq * size[i] * size[j]
                if left < right:
                    b0, b1 = i, j
    place = [-1] * K
    used = [0] * K
    placed = [0] * K
    np_ = 0
    place[b0] = 0
    used[0] = 1
    placed[np_] = b0
    np_ += 1
    place[b1] = K - 1
    used[K - 1] = 1
    placed[np_] = b1
    np_ += 1
    order = by_size(K, size)
    for oi in range(K):
        g = order[oi]
        if place[g] != -1:
            continue
        best_s, best_c = -1, 0.0
        for s in range(K):
            if used[s]:
                continue
            c = 0.0
            for pi in range(np_):
                h = placed[pi]
                t = place[h]
                lo = g if g < h else h
                hi = h if g < h else g
                w = link[lo * K + hi] - 4 * opp[lo * K + hi]
                dx, dy, dz = D[s][0] - D[t][0], D[s][1] - D[t][1], D[s][2] - D[t][2]
                c += w * length3(dx, dy, dz)
            if best_s == -1 or c < best_c:
                best_s, best_c = s, c
        place[g] = best_s
        used[best_s] = 1
        placed[np_] = g
        np_ += 1
    for g in range(K):
        slot[g] = place[g]
        dirs[3 * g] = D[place[g]][0]
        dirs[3 * g + 1] = D[place[g]][1]
        dirs[3 * g + 2] = D[place[g]][2]
    return slot, [b0, b1], dirs


def pack(
    K: int,
    radius: Sequence[float],
    link: Sequence[int],
    opp: Sequence[int],
    dirs: Sequence[float],
    gap: float,
    fx: dict[str, Any] | None = None,
) -> list[float]:
    """Where each part's point stands, the parts as balls of the given radii started apart in their directions.
    fx None, or {"flag": [0 | 1] * K, "at": [float] * 3K}: the fixed parts; with none flagged, the packing as it was.

    Each part starts at its direction times the sum of every radius. For PACK_STEPS steps, each pair of parts (i < j,
    in order) moves apart when nearer than gap times their radii's sum, or together, more weakly, when further (by
    0.02 plus half their share of the links, a quarter of that with an opposing link); each moves half of its summed
    move. Last, the mean of the points is moved to 0, 0, 0."""
    nf = 0
    if fx is not None:
        for i in range(K):
            if fx["flag"][i]:
                nf += 1
    if nf > 0:
        assert fx is not None
        return pack_fixed(K, radius, link, opp, dirs, gap, fx, nf)
    P = [0.0] * (3 * K)
    if K == 1:
        return P
    total_r = 0.0
    for i in range(K):
        total_r += radius[i]
    for c in range(3 * K):
        P[c] = dirs[c] * total_r
    total = 0
    for i in range(K):
        for j in range(i + 1, K):
            total += link[i * K + j]
    if total == 0:
        total = 1
    D = [0.0] * (3 * K)
    for _step in range(PACK_STEPS):
        for c in range(3 * K):
            D[c] = 0.0
        for i in range(K):
            for j in range(i + 1, K):
                dx = P[3 * i] - P[3 * j]
                dy = P[3 * i + 1] - P[3 * j + 1]
                dz = P[3 * i + 2] - P[3 * j + 2]
                dist = js_max(length3(dx, dy, dz), 1e-6)
                need = gap * (radius[i] + radius[j])
                f = dist - need  # under 0: inside each other
                if f > 0:
                    f = f * ((0.02 + ((0.5 * link[i * K + j]) / total)) * (0.25 if opp[i * K + j] != 0 else 1.0))
                ux = ((dx / dist) * f) * 0.5
                uy = ((dy / dist) * f) * 0.5
                uz = ((dz / dist) * f) * 0.5
                D[3 * i] = D[3 * i] - ux
                D[3 * i + 1] = D[3 * i + 1] - uy
                D[3 * i + 2] = D[3 * i + 2] - uz
                D[3 * j] = D[3 * j] + ux
                D[3 * j + 1] = D[3 * j + 1] + uy
                D[3 * j + 2] = D[3 * j + 2] + uz
        for c in range(3 * K):
            P[c] = P[c] + (D[c] * 0.5)
    mx, my, mz = 0.0, 0.0, 0.0
    for i in range(K):
        mx = mx + P[3 * i]
        my = my + P[3 * i + 1]
        mz = mz + P[3 * i + 2]
    mx = js_div(mx, K)
    my = js_div(my, K)
    mz = js_div(mz, K)
    for i in range(K):
        P[3 * i] = P[3 * i] - mx
        P[3 * i + 1] = P[3 * i + 1] - my
        P[3 * i + 2] = P[3 * i + 2] - mz
    return P


def pack_fixed(
    K: int,
    radius: Sequence[float],
    link: Sequence[int],
    opp: Sequence[int],
    dirs: Sequence[float],
    gap: float,
    fx: dict[str, Any],
    nf: int,
) -> list[float]:
    """nf > 0 parts fixed. A fixed part stands at its point and its move is never applied; a free part starts at O +
    its direction * the sum of all the radii (O the mean of the fixed points, x, y and z each summed in part order,
    divided by nf); the same steps over the same pairs; no centring. Every part fixed: no steps."""
    flag, fat = fx["flag"], fx["at"]
    P = [0.0] * (3 * K)
    ox, oy, oz = 0.0, 0.0, 0.0
    for i in range(K):
        if not flag[i]:
            continue
        P[3 * i] = fat[3 * i]
        P[3 * i + 1] = fat[3 * i + 1]
        P[3 * i + 2] = fat[3 * i + 2]
        ox = ox + fat[3 * i]
        oy = oy + fat[3 * i + 1]
        oz = oz + fat[3 * i + 2]
    if nf == K:
        return P
    ox = ox / nf
    oy = oy / nf
    oz = oz / nf
    total_r = 0.0
    for i in range(K):
        total_r += radius[i]
    for i in range(K):
        if flag[i]:
            continue
        P[3 * i] = ox + (dirs[3 * i] * total_r)
        P[3 * i + 1] = oy + (dirs[3 * i + 1] * total_r)
        P[3 * i + 2] = oz + (dirs[3 * i + 2] * total_r)
    total = 0
    for i in range(K):
        for j in range(i + 1, K):
            total += link[i * K + j]
    if total == 0:
        total = 1
    D = [0.0] * (3 * K)
    for _step in range(PACK_STEPS):
        for c in range(3 * K):
            D[c] = 0.0
        for i in range(K):
            for j in range(i + 1, K):
                dx = P[3 * i] - P[3 * j]
                dy = P[3 * i + 1] - P[3 * j + 1]
                dz = P[3 * i + 2] - P[3 * j + 2]
                dist = js_max(length3(dx, dy, dz), 1e-6)
                need = gap * (radius[i] + radius[j])
                f = dist - need
                if f > 0:
                    f = f * ((0.02 + ((0.5 * link[i * K + j]) / total)) * (0.25 if opp[i * K + j] != 0 else 1.0))
                ux = ((dx / dist) * f) * 0.5
                uy = ((dy / dist) * f) * 0.5
                uz = ((dz / dist) * f) * 0.5
                D[3 * i] = D[3 * i] - ux
                D[3 * i + 1] = D[3 * i + 1] - uy
                D[3 * i + 2] = D[3 * i + 2] - uz
                D[3 * j] = D[3 * j] + ux
                D[3 * j + 1] = D[3 * j + 1] + uy
                D[3 * j + 2] = D[3 * j + 2] + uz
        for i in range(K):
            if flag[i]:
                continue
            for c in range(3 * i, 3 * i + 3):
                P[c] = P[c] + (D[c] * 0.5)
    return P


def fixed_parts(K: int, flag: list[int], at: list[float]) -> dict[str, Any] | None:
    """the fixed parts as pack() takes them, or None when no part is flagged"""
    for i in range(K):
        if flag[i]:
            return {"flag": flag, "at": at}
    return None


def _ta(arr: Sequence[Any] | None, i: int) -> Any:
    """arr[i], or None past either end"""
    if arr is None or i < 0 or i >= len(arr):
        return None
    return arr[i]


def _tf(arr: Sequence[Any] | None, i: int) -> float:
    """arr[i] as a double: NaN past the end"""
    if arr is None or i < 0 or i >= len(arr):
        return NAN
    return to_double(arr[i])


def points(
    ids: Sequence[str],
    body: Sequence[int],
    taken: Sequence[int],
    group: Sequence[int],
    pairs: Sequence[Sequence[str]],
    edges: Sequence[Any],
    plate: Mapping[str, Sequence[Any]] | None,
    table: Table,
    fixed: dict[str, Any] | None = None,
    snap: dict[str, Any] | None = None,
) -> dict[str, Any]:
    dir_table = table
    gap = GAP
    n, k = len(ids), len(taken)
    at = {id_: i for i, id_ in enumerate(ids)}

    part = [-1] * n
    for v in range(n):
        if body[v]:
            part[v] = group[v]
    size, link, opp = count(n, k, part, at, pairs, edges)
    slot1, ends1, dirs1 = slots(k, size, link, opp, dir_table)
    lobe = [0.0] * k
    for g in range(k):
        lobe[g] = REST * LOBE * root(size[g])
    out: dict[str, Any] = {
        "k": k,
        "size": size,
        "link": link,
        "opp": opp,
        "slot": slot1,
        "ends": ends1,
        "dirs": dirs1,
        "lobe": lobe,
        "cpt": None,
        "plate": None,
    }

    blind = bool(fixed is not None and fixed.get("blind"))
    entries = object_entries(plate) if plate else []
    if not len(entries):
        fx = None
        if fixed is not None:
            flag, fat = [0] * k, [0.0] * (3 * k)
            fg, fa = fixed.get("group"), fixed.get("at")
            for g in range(k):
                if _ta(fg, g):
                    flag[g] = 1
                    fat[3 * g] = _tf(fa, 3 * g)
                    fat[3 * g + 1] = _tf(fa, 3 * g + 1)
                    fat[3 * g + 2] = _tf(fa, 3 * g + 2)
            fx = fixed_parts(k, flag, fat)
        cpt = pack(k, lobe, link, opp, dirs1, gap, None if blind else fx)
        if blind and fx is not None:
            for c in range(3 * k):
                if fx["flag"][c // 3]:
                    cpt[c] = fx["at"][c]
        out["cpt"] = cpt
        return out

    # the plate branch: the groups' own packing is not needed
    pinned = [0] * n
    q = [0.0] * (3 * n)
    outside, half = 0, 0.0
    for id_, xy in entries:
        v = at.get(id_)  # type: ignore[assignment]
        if v is None:
            raise ValueError(f"points: the plate names {id_}, which is not among the ids")
        pinned[v] = 1
        x0, y0 = to_double(xy[0]), to_double(xy[1])
        q[3 * v] = x0
        q[3 * v + 1] = y0
        q[3 * v + 2] = to_double(xy[2]) if len(xy) > 2 else 0.0
        if not body[v]:
            outside += 1
        half = js_max(half, length2(x0, y0))
    over = [0] * k
    unit = [-1] * k
    pu = 0
    for g in range(k):
        if pinned[taken[g]]:
            over[g] = 1
        else:
            unit[g] = pu
            pu += 1
    K = pu + 1
    upart = [-1] * n
    for v in range(n):
        if body[v]:
            # an element in no group (-1) reads as in no group over the plate: part 0
            gv = group[v]
            inside = 0 <= gv < k
            upart[v] = pu if (pinned[v] or (inside and over[gv])) else (unit[gv] if inside else 0)
    usize, ulink, uopp = count(n, K, upart, at, pairs, edges)
    usize[pu] += outside
    slot2, ends2, dirs2 = slots(K, usize, ulink, uopp, dir_table)
    radius = [0.0] * K
    for p in range(pu):
        radius[p] = REST * LOBE * root(usize[p])
    radius[pu] = half * CLEAR
    fx = None
    if fixed is not None:
        flag, fat = [0] * K, [0.0] * (3 * K)
        fg, fa = fixed.get("group"), fixed.get("at")
        for g in range(k):
            if not over[g] and _ta(fg, g):
                p = unit[g]
                flag[p] = 1
                fat[3 * p] = _tf(fa, 3 * g)
                fat[3 * p + 1] = _tf(fa, 3 * g + 1)
                fat[3 * p + 2] = _tf(fa, 3 * g + 2)
        fp = fixed.get("plate")
        if fp is not None:
            flag[pu] = 1
            fat[3 * pu] = _tf(fp, 0)
            fat[3 * pu + 1] = _tf(fp, 1)
            fat[3 * pu + 2] = _tf(fp, 2)
        fx = fixed_parts(K, flag, fat)
    upt = pack(K, radius, ulink, uopp, dirs2, gap, None if blind else fx)
    if blind and fx is not None:
        for c in range(3 * K):
            if fx["flag"][c // 3]:
                upt[c] = fx["at"][c]
    point = [upt[3 * pu], upt[3 * pu + 1], upt[3 * pu + 2]]
    plate_at = [0.0] * (3 * n)
    for v in range(n):
        if not pinned[v]:
            continue
        for c in range(3):
            plate_at[3 * v + c] = point[c] + q[3 * v + c]
    # the snap: a held pinned element within `near` of its held point on each axis stands at the held point
    if snap is not None:
        sf, sa = snap.get("flag"), snap.get("at")
        near = to_double(snap.get("near"))
        for v in range(n):
            if not pinned[v] or not _ta(sf, v):
                continue
            close = True
            for c in range(3):
                d = plate_at[3 * v + c] - _tf(sa, 3 * v + c)
                if not (d <= near and -d <= near):
                    close = False
            if close:
                for c in range(3):
                    plate_at[3 * v + c] = _tf(sa, 3 * v + c)
    cpt = [0.0] * (3 * k)
    for g in range(k):
        if over[g]:
            c = taken[g]
            cpt[3 * g] = plate_at[3 * c] + 0.0
            cpt[3 * g + 1] = plate_at[3 * c + 1] + 0.0
            cpt[3 * g + 2] = plate_at[3 * c + 2] + (lobe[g] + (REST * 6))
        else:
            p = unit[g]
            cpt[3 * g] = upt[3 * p]
            cpt[3 * g + 1] = upt[3 * p + 1]
            cpt[3 * g + 2] = upt[3 * p + 2]
    out["cpt"] = cpt
    out["plate"] = {
        "parts": K,
        "over": over,
        "unit": unit,
        "size": usize,
        "link": ulink,
        "opp": uopp,
        "slot": slot2,
        "ends": ends2,
        "dirs": dirs2,
        "radius": radius,
        "half": half,
        "point": point,
        "pinned": pinned,
        "at": plate_at,
    }
    return out

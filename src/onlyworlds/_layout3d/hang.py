"""The by-links-3d layout, step 9: what is placed after the force steps.

    hang(ids, body, hang_cut, hang_depth, off, taken, group, cpt, plate, kind, degree, relaxed[, held])
        -> {"pos": [x0, y0, z0, x1, ...] (3n floats), "how": [int] * n (an index into HOW), "skin": [float] * k,
            "middle": [x, y, z]}

  plate   None, or points()' "plate": only "pinned" and "at" are read
  held    None, or {"flag": [0 | 1] * n, "at": [x, y, z] * n[, "line"][, "claim"]}: the held points

In this order:
  1. the body stands at its relaxed points, each element ``centre`` (its group's centre) or ``with``;
  2. the middle: the mean of the body's relaxed points;
  3. each group's skin: the 0.9 quantile (linear, as numpy's default) of its unpinned members' distances from its point;
  4. outward(): from the group's point through a place, leaning away from the middle (by 0.75 of a unit);
  5. what hangs from the body, cut by cut in place order, the members of a cut by depth then place: a member at depth
     d and rank j stands on a fan round the outward line, REST * d beyond the skin, at the golden angle times j and
     REST * 0.5 * the root of j from the line (over a pinned cut: straight above its place, the fan half as wide),
     ``link`` when its only link is to the cut, else ``arm``;
  6. the shelf: each element off the main piece and not pinned, by kind then place, at the golden angle times j and
     REST * 0.9 * the root of j + 1 from the middle of what is on the main piece, REST * 3 under its lowest point;
  8. every held element that is not pinned stands at its held point (and the fan and shelf places near a held point,
     within ``line``, are left to it, taking the next free place);
  7. last, a pinned element stands at its place, ``map``.

math.cos and math.sin are the two functions that are not correctly rounded in every runtime: an element they place
(an arm, a one-link element, a shelf element) can differ from another runtime's in the last places. Everything else
here is + - * /, sqrt and floor, the same double in every runtime.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

REST = 60.0
GOLD = math.pi * (3.0 - math.sqrt(5.0))
HOW = ["centre", "with", "arm", "link", "shelf", "map"]
CENTRE, WITH, ARM, LINK, SHELF, MAP = 0, 1, 2, 3, 4, 5
LINE = REST / 8  # a held element nearer than this to a free place takes it (held points only)


def len3(x: float, y: float, z: float) -> float:
    return math.sqrt(x * x + y * y + z * z)


def quantile90(a: Sequence[float], m: int) -> float:
    """numpy's default quantile ('linear') of the first m values of a, at q = 0.9"""
    if m == 0:
        return 0.0
    s = sorted(a[:m])
    vi = (m - 1) * 0.9
    if vi >= m - 1:
        lo = hi = m - 1
    else:
        lo = math.floor(vi)
        hi = lo + 1
    t = vi - lo
    d = s[hi] - s[lo]
    return s[hi] - d * (1 - t) if t >= 0.5 else s[lo] + d * t


def hang(
    ids: Sequence[str],
    body: Sequence[int],
    hang_cut: Sequence[int],
    hang_depth: Sequence[int],
    off: Sequence[int],
    taken: Sequence[int],
    group: Sequence[int],
    cpt: Sequence[float],
    plate: dict[str, Any] | None,
    kind: Sequence[str],
    degree: Sequence[int],
    relaxed: Sequence[float],
    held: dict[str, Any] | None = None,
) -> dict[str, Any]:
    n, k = len(ids), len(taken)
    pinned = plate["pinned"] if plate else [0] * n
    at = plate["at"] if plate else None
    pos = [0.0] * (3 * n)
    how = [255] * n
    sqrt, cos, sin = math.sqrt, math.cos, math.sin

    # the held elements that are not pinned, and the near test against every one of them
    H = held
    hat = H["at"] if H else None
    line = H["line"] if (H and H.get("line") is not None) else LINE
    claim_on = not (H and H.get("claim") is False)
    in_h = [0] * n
    hl: list[int] = []
    if H:
        for v in range(n):
            if H["flag"][v] == 1 and not pinned[v]:
                in_h[v] = 1
                hl.append(v)

    def near(x: float, y: float, z: float) -> bool:
        assert hat is not None
        for u in hl:  # noqa: SIM110
            if len3(x - hat[3 * u], y - hat[3 * u + 1], z - hat[3 * u + 2]) < line:
                return True
        return False

    # 1. the body at its relaxed points
    nb = 0
    for v in range(n):
        if not body[v]:
            continue
        pos[3 * v] = relaxed[3 * v]
        pos[3 * v + 1] = relaxed[3 * v + 1]
        pos[3 * v + 2] = relaxed[3 * v + 2]
        how[v] = CENTRE if taken[group[v]] == v else WITH
        nb += 1

    # 2. the middle
    middle = [0.0, 0.0, 0.0]
    for v in range(n):
        if not body[v]:
            continue
        middle[0] += relaxed[3 * v]
        middle[1] += relaxed[3 * v + 1]
        middle[2] += relaxed[3 * v + 2]
    middle[0] /= nb
    middle[1] /= nb
    middle[2] /= nb

    # 3. each group's skin
    skin = [0.0] * k
    vals = [0.0] * n
    for g in range(k):
        m = 0
        for v in range(n):
            if not body[v] or group[v] != g or pinned[v]:
                continue
            vals[m] = len3(
                relaxed[3 * v] - cpt[3 * g], relaxed[3 * v + 1] - cpt[3 * g + 1], relaxed[3 * v + 2] - cpt[3 * g + 2]
            )
            m += 1
        skin[g] = quantile90(vals, m)

    # 4. outward from the group's point through p, leaning away from the middle
    def outward(px: float, py: float, pz: float, g: int) -> tuple[float, float, float]:
        ux, uy, uz = px - cpt[3 * g], py - cpt[3 * g + 1], pz - cpt[3 * g + 2]
        lu = len3(ux, uy, uz)
        if lu > 1e-6:
            ux, uy, uz = ux / lu, uy / lu, uz / lu
        else:
            ux, uy, uz = 0.0, 0.0, 0.0
        ox, oy, oz = cpt[3 * g] - middle[0], cpt[3 * g + 1] - middle[1], cpt[3 * g + 2] - middle[2]
        lo = len3(ox, oy, oz)
        if lo > 1e-6:
            ox, oy, oz = ox / lo, oy / lo, oz / lo
        else:
            ox, oy, oz = 0.0, 0.0, 1.0
        ux, uy, uz = ux + 0.75 * ox, uy + 0.75 * oy, uz + 0.75 * oz
        ln = len3(ux, uy, uz)  # never under 0.25: a unit vector plus 0.75 of another
        return ux / ln, uy / ln, uz / ln

    # 5. what hangs from the body: the members of each cut, by depth then index
    rows: list[list[int]] = [[] for _ in range(n)]
    for v in range(n):
        if hang_cut[v] != -1:
            rows[hang_cut[v]].append(v)  # rising index within a cut
    for c in range(n):
        if not rows[c]:
            continue
        row = sorted(rows[c], key=lambda v: (hang_depth[v], v))
        g = group[c]
        ux, uy, uz = outward(pos[3 * c], pos[3 * c + 1], pos[3 * c + 2], g)
        # t = u x (0, 0, 1), else u x (1, 0, 0)
        tx, ty, tz = uy * 1.0 - uz * 0.0, uz * 0.0 - ux * 1.0, ux * 0.0 - uy * 0.0
        if len3(tx, ty, tz) < 1e-3:
            tx, ty, tz = uy * 0.0 - uz * 0.0, uz * 1.0 - ux * 0.0, ux * 0.0 - uy * 1.0
        lt = len3(tx, ty, tz)
        tx, ty, tz = tx / lt, ty / lt, tz / lt
        wx, wy, wz = uy * tz - uz * ty, uz * tx - ux * tz, ux * ty - uy * tx
        over_place = bool(pinned[c])

        def fan_point(j: int, d: int) -> tuple[float, float, float]:
            """place j's point for a member at depth d (read in the same pass of the loop that defines it)"""
            ang = GOLD * j
            fan = REST * 0.5 * sqrt(j)
            ca, sa = cos(ang), sin(ang)
            if over_place:  # noqa: B023  (what hangs from a place on the map stands over that place)
                assert at is not None
                return (at[3 * c] + ca * fan * 0.5, at[3 * c + 1] + sa * fan * 0.5, at[3 * c + 2] + REST * d)  # noqa: B023
            reach = skin[g] + REST * d  # noqa: B023
            return (
                cpt[3 * g] + ux * reach + (tx * ca + wx * sa) * fan,  # noqa: B023
                cpt[3 * g + 1] + uy * reach + (ty * ca + wy * sa) * fan,  # noqa: B023
                cpt[3 * g + 2] + uz * reach + (tz * ca + wz * sa) * fan,  # noqa: B023
            )

        used: set[int] = set()  # places taken by this cut's members not held, and the places claimed
        if H and claim_on:
            assert hat is not None
            for v in row:
                if not in_h[v]:
                    continue
                d = hang_depth[v]
                hx, hy, hz = hat[3 * v], hat[3 * v + 1], hat[3 * v + 2]
                # the fan's axis point at depth d, and the held point's distance from it
                if over_place:
                    assert at is not None
                    axx, axy, axz = at[3 * c], at[3 * c + 1], at[3 * c + 2] + REST * d
                else:
                    reach = skin[g] + REST * d
                    axx, axy, axz = cpt[3 * g] + ux * reach, cpt[3 * g + 1] + uy * reach, cpt[3 * g + 2] + uz * reach
                bound = len3(hx - axx, hy - axy, hz - axz) + line + REST
                j = 0
                while True:
                    fan = REST * 0.5 * sqrt(j)
                    if not ((fan * 0.5 if over_place else fan) < bound):
                        break
                    fx, fy, fz = fan_point(j, d)
                    if len3(fx - hx, fy - hy, fz - hz) < line:
                        used.add(j)
                    j += 1
        for r, v in enumerate(row):
            d = hang_depth[v]
            how[v] = LINK if (degree[v] == 1 and d == 1) else ARM
            j = r  # nothing held: the member's rank
            if H:
                if in_h[v]:
                    continue  # keeps its held point (step 8)
                j = 0
                while True:
                    if j not in used:
                        fx, fy, fz = fan_point(j, d)
                        if not near(fx, fy, fz):
                            break
                    j += 1
                used.add(j)
            fx, fy, fz = fan_point(j, d)
            pos[3 * v], pos[3 * v + 1], pos[3 * v + 2] = fx, fy, fz

    # 6. the shelf: what is off the main piece and not pinned, under the shape, by kind then index
    any_off = 0
    for v in range(n):
        if off[v]:
            any_off += 1
    if any_off:
        zmin, sx, sy, cnt = math.inf, 0.0, 0.0, 0
        for v in range(n):
            if off[v]:
                continue
            # a pinned element ends at its Pin (step 7), a held element at its held point (step 8)
            src = at if pinned[v] else (hat if in_h[v] else pos)
            assert src is not None
            fx, fy, fz = src[3 * v], src[3 * v + 1], src[3 * v + 2]
            if fz < zmin:
                zmin = fz
            sx += fx
            sy += fy
            cnt += 1
        zmin = zmin - REST * 3
        cx, cy = sx / cnt, sy / cnt
        shelf = sorted((v for v in range(n) if off[v] and not pinned[v]), key=lambda v: (kind[v], v))

        def shelf_point(j: int) -> tuple[float, float, float]:
            r = REST * 0.9 * sqrt(j + 1)
            return (cx + r * cos(GOLD * j), cy + r * sin(GOLD * j), zmin)

        used = set()  # places taken by shelf elements not held
        for q, v in enumerate(shelf):
            how[v] = SHELF
            j = q  # nothing held: its place in the order
            if H:
                if in_h[v]:
                    continue  # keeps its held point (step 8)
                j = 0
                while True:
                    if j not in used:
                        fx, fy, fz = shelf_point(j)
                        if not near(fx, fy, fz):
                            break
                    j += 1
                used.add(j)
            fx, fy, fz = shelf_point(j)
            pos[3 * v], pos[3 * v + 1], pos[3 * v + 2] = fx, fy, fz

    # 8. every held element that is not pinned stands at its held point, whatever the rules above gave it
    if H:
        assert hat is not None
        for v in hl:
            pos[3 * v], pos[3 * v + 1], pos[3 * v + 2] = hat[3 * v], hat[3 * v + 1], hat[3 * v + 2]

    # 7. last, so nothing above moves it: a pinned element stands at its place
    for v in range(n):
        if not pinned[v]:
            continue
        assert at is not None
        pos[3 * v], pos[3 * v + 1], pos[3 * v + 2] = at[3 * v], at[3 * v + 1], at[3 * v + 2]
        how[v] = MAP
    for v in range(n):
        if how[v] == 255:
            raise ValueError(f"hang: {ids[v]} was placed by no rule")
    return {"pos": pos, "how": how, "skin": skin, "middle": middle}

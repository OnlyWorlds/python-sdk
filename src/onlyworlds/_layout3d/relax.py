"""The by-links-3d layout, step 8: the force steps.

    relax(feed, cutoff=3, cap0=3) -> {"pos": [x0, y0, z0, x1, ...] (3n floats)}

The feed: "rest" (R), "steps", "pos" and "anchor" ([x, y, z] each, floats), "pull" (a number, or [x, y, z], each),
"fixed" (truthy: the element stands at its anchor), "pairs" ([i, j] places) and "weight" (one per pair).

Each step, in this order:
  1. the push: the elements are sorted into cells of CUT = cutoff * R on a side (from the box's low corner), and each
     pair of elements in one cell or in two neighbouring cells (each cell with itself and the 13 cells ahead of it, in
     a fixed order), no further apart than CUT, pushes apart by (R * R / d - R / 3) / d along their difference;
  2. the links: each pair, in order, pulls by ((d - R) * 0.5 * weight) / d along its difference;
  3. the move: each element's push, plus its links' pull times its scale (1 over the larger of 1 and a quarter of its
     links' summed weight), plus (anchor - point) * pull, moves it by at most the cap, cap0 * R * (1 - step / steps)
     + R / 20; a fixed element stands at its anchor.
The push between two fixed elements is never read and is not worked out, which moves no number.
Every sum runs in the order written and every expression keeps its grouping. A distance under 1e-6 is read as 1e-6 and
a move's length under 1e-9 as 1e-9; a NaN goes through as it is (no max() or min()).
"""

from __future__ import annotations

import math
from typing import Any


def _offsets() -> list[tuple[int, int, int]]:
    # this cell with itself and with the 13 cells ahead of it, in the loop's order
    offs = []
    for ox in range(0, 2):
        for oy in range(-1 if ox else 0, 2):
            for oz in range(-1 if (ox or oy) else 0, 2):
                offs.append((ox, oy, oz))
    return offs


def relax(feed: dict[str, Any], cutoff: float = 3, cap0: float = 3) -> dict[str, Any]:
    sqrt, floor = math.sqrt, math.floor
    R = feed["rest"]
    STEPS = feed["steps"]
    CUT = cutoff * R
    CAP0 = cap0
    n = len(feed["pos"])
    m = len(feed["pairs"])
    px = [p[0] for p in feed["pos"]]
    py = [p[1] for p in feed["pos"]]
    pz = [p[2] for p in feed["pos"]]
    ax = [p[0] for p in feed["anchor"]]
    ay = [p[1] for p in feed["anchor"]]
    az = [p[2] for p in feed["anchor"]]
    per_axis = n > 0 and isinstance(feed["pull"][0], list)
    if per_axis:
        pullX = [p[0] for p in feed["pull"]]
        pullY = [p[1] for p in feed["pull"]]
        pullZ = [p[2] for p in feed["pull"]]
    else:
        pullX = list(feed["pull"][:n])
        pullY = list(pullX)
        pullZ = list(pullX)
    fixed = [0] * n
    if feed.get("fixed"):
        fixed = [1 if feed["fixed"][i] else 0 for i in range(n)]
    ea = [int(p[0]) for p in feed["pairs"]]
    eb = [int(p[1]) for p in feed["pairs"]]
    ew = list(feed["weight"][:m])
    scale = [0.0] * n
    for k in range(m):
        scale[ea[k]] += ew[k]
        scale[eb[k]] += ew[k]
    for i in range(n):
        t = scale[i] / 4
        scale[i] = 1 / (1.0 if t < 1 else t)

    dx = [0.0] * n
    dy = [0.0] * n
    dz = [0.0] * n
    cut2 = CUT * CUT
    RR = R * R  # (R * R) and R / 3 are the same doubles each time they are worked out
    R3 = R / 3
    OFFS = _offsets()

    # Two fixed elements push each other and neither moves, so that push is never read: it is not worked out (a
    # cell pair with no free element is passed over whole, and so is a pair of two fixed elements). The pushes on a
    # free element are still summed in the same order, so no number of the answer changes. With no free element at
    # all one step does what every step would: each element at its anchor.
    free = n - sum(fixed)
    run = min(STEPS, 1) if free == 0 else STEPS
    for step in range(run):
        x0 = y0 = z0 = math.inf
        x1 = y1 = z1 = -math.inf
        for i in range(n):
            v = px[i]
            if v < x0:
                x0 = v
            if v > x1:
                x1 = v
            v = py[i]
            if v < y0:
                y0 = v
            if v > y1:
                y1 = v
            v = pz[i]
            if v < z0:
                z0 = v
            if v > z1:
                z1 = v
        nx = floor((x1 - x0) / CUT) + 1
        ny = floor((y1 - y0) / CUT) + 1
        nz = floor((z1 - z0) / CUT) + 1
        cells = nx * ny * nz
        startOf = [0] * (cells + 1)
        cellOf = [0] * n
        for i in range(n):
            c = (floor((px[i] - x0) / CUT) * ny + floor((py[i] - y0) / CUT)) * nz + floor((pz[i] - z0) / CUT)
            cellOf[i] = c
            startOf[c + 1] += 1
        for c in range(cells):
            startOf[c + 1] += startOf[c]
        fill = startOf[:cells]
        order = [0] * n
        for i in range(n):
            c = cellOf[i]
            order[fill[c]] = i
            fill[c] += 1
        freeIn = [0] * cells
        for i in range(n):
            if not fixed[i]:
                freeIn[cellOf[i]] += 1

        for i in range(n):
            dx[i] = 0.0
            dy[i] = 0.0
            dz[i] = 0.0
        for cx in range(nx):
            for cy in range(ny):
                for cz in range(nz):
                    c = (cx * ny + cy) * nz + cz
                    s0 = startOf[c]
                    s1 = startOf[c + 1]
                    if s0 == s1:
                        continue
                    for ox, oy, oz in OFFS:
                        qx = cx + ox
                        qy = cy + oy
                        qz = cz + oz
                        if qx >= nx or qy < 0 or qy >= ny or qz < 0 or qz >= nz:
                            continue
                        q = (qx * ny + qy) * nz + qz
                        same = q == c
                        t0 = startOf[q]
                        t1 = startOf[q + 1]
                        if t0 == t1:
                            continue
                        if freeIn[c] == 0 and freeIn[q] == 0:
                            continue
                        for u in range(s0, s1):
                            i = order[u]
                            xi = px[i]
                            yi = py[i]
                            zi = pz[i]
                            for w in range(u + 1 if same else t0, t1):
                                j = order[w]
                                if fixed[i] and fixed[j]:
                                    continue
                                ux = xi - px[j]
                                uy = yi - py[j]
                                uz = zi - pz[j]
                                d2 = ux * ux + uy * uy + uz * uz
                                if d2 > cut2:
                                    continue
                                d = sqrt(d2)
                                if d < 1e-6:  # at least 1e-6, a NaN kept
                                    d = 1e-6
                                f = (RR / d - R3) / d
                                dx[i] += ux * f
                                dy[i] += uy * f
                                dz[i] += uz * f
                                dx[j] -= ux * f
                                dy[j] -= uy * f
                                dz[j] -= uz * f

        lx = [0.0] * n
        ly = [0.0] * n
        lz = [0.0] * n
        for k in range(m):
            a = ea[k]
            b = eb[k]
            ux = px[a] - px[b]
            uy = py[a] - py[b]
            uz = pz[a] - pz[b]
            d = sqrt(ux * ux + uy * uy + uz * uz)
            if d < 1e-6:
                d = 1e-6
            f = ((d - R) * 0.5 * ew[k]) / d
            lx[b] += ux * f
            ly[b] += uy * f
            lz[b] += uz * f
            lx[a] -= ux * f
            ly[a] -= uy * f
            lz[a] -= uz * f

        cap = CAP0 * R * (1 - step / STEPS) + R / 20
        for i in range(n):
            if fixed[i]:
                px[i] = ax[i]
                py[i] = ay[i]
                pz[i] = az[i]
                continue
            vx = dx[i] + lx[i] * scale[i] + (ax[i] - px[i]) * pullX[i]
            vy = dy[i] + ly[i] * scale[i] + (ay[i] - py[i]) * pullY[i]
            vz = dz[i] + lz[i] * scale[i] + (az[i] - pz[i]) * pullZ[i]
            ln = sqrt(vx * vx + vy * vy + vz * vz)
            if ln < 1e-9:  # at least 1e-9, a NaN kept
                ln = 1e-9
            q = cap / ln
            s = 1.0 if q > 1 else q  # at most 1, a NaN kept
            px[i] += vx * s
            py[i] += vy * s
            pz[i] += vz * s

    pos = [0.0] * (n * 3)
    for i in range(n):
        pos[3 * i] = px[i]
        pos[3 * i + 1] = py[i]
        pos[3 * i + 2] = pz[i]
    return {"pos": pos}

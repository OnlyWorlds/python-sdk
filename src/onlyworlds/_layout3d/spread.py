"""The by-links-3d layout: the cube root and the seeded start of the force steps.

    cube_root(v)              -> float
    plain_start(feed, num)    -> [[x, y, z], ...]

cube_root is forty Newton steps from the square root (at least 1), so it is the same double in every runtime, where a
runtime's own cube root or ``v ** (1 / 3)`` is not.

plain_start puts each element that is not fixed at a seeded point in a ball round its anchor: the ball's radius is
REST * 1.1 * the cube root of the count of free elements that share its anchor, and the point is the first of up to 64
draws of a 32-bit linear congruential generator (seeded by the element's own number, its first two draws passed over)
that falls inside the unit ball, else the anchor itself. A fixed element stays where it is. The feed's coordinates are
floats; ``num[i]`` is a whole number, read modulo 2^32 (to_uint32()). Every step of the generator is exact: no
intermediate reaches 2^53.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any


def groups_of(feed: dict[str, Any]) -> dict[tuple[float, float, float], list[int]]:
    """free elements held to one point are one group: key -> [index, ...] in index order (-0.0 and 0.0 one key)"""
    groups: dict[tuple[float, float, float], list[int]] = {}
    fixed = feed.get("fixed")
    for i, p in enumerate(feed["anchor"]):
        if fixed and fixed[i]:
            continue
        k = (p[0], p[1], p[2])
        if k not in groups:
            groups[k] = []
        groups[k].append(i)
    return groups


def cube_root(v: float) -> float:
    if not (v > 0):
        return 0.0
    v = float(v)
    x = math.sqrt(v)
    if x < 1:
        x = 1.0
    for _ in range(40):
        x = (2 * x + v / (x * x)) / 3
    return x


def to_uint32(v: int | float) -> int:
    """a whole number modulo 2^32, a float truncated toward zero first (a non-finite one is 0)"""
    if isinstance(v, float):
        if not math.isfinite(v):
            return 0
        v = math.trunc(v)
    return v % 4294967296


def plain_start(feed: dict[str, Any], num: Sequence[int]) -> list[list[float]]:
    if not num:
        raise ValueError("plain_start: needs each element's own number")
    REST = feed["rest"]
    groups = groups_of(feed)
    fixed = feed.get("fixed")
    out: list[list[float]] = []
    for i, p in enumerate(feed["pos"]):
        if fixed and fixed[i]:
            out.append(p)
            continue
        anc = feed["anchor"][i]
        size = len(groups[(anc[0], anc[1], anc[2])])
        lobe = REST * 1.1 * cube_root(size)
        g = to_uint32(num[i])
        # each draw: g = (g * 1664525 + 1013904223) % 4294967296, read as g / 4294967296
        g = (g * 1664525 + 1013904223) % 4294967296
        g = (g * 1664525 + 1013904223) % 4294967296  # the first draws of near seeds lie near each other: passed over
        x = y = z = 0.0
        for _ in range(64):
            g = (g * 1664525 + 1013904223) % 4294967296
            a = 2 * (g / 4294967296) - 1
            g = (g * 1664525 + 1013904223) % 4294967296
            b = 2 * (g / 4294967296) - 1
            g = (g * 1664525 + 1013904223) % 4294967296
            c = 2 * (g / 4294967296) - 1
            if a * a + b * b + c * c <= 1:
                x, y, z = a, b, c
                break
        out.append([anc[0] + x * lobe, anc[1] + y * lobe, anc[2] + z * lobe])
    return out

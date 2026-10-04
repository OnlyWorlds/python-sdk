"""UUIDv7 minting (RFC 9562), because Python's ``uuid`` only gains ``uuid7`` in 3.14.

keel mints v7 ids itself and the standard says elements carry them, so a client that
creates an element without an id gives it one that sorts by creation time. v7 is a
default, never a requirement: a caller's own v4 id stays valid forever. Never order
elements by id (worlds also hold v4 and legacy ids); use ``created_at``.
"""

from __future__ import annotations

import os
import time
import uuid
from collections.abc import Callable

__all__ = ["uuid7"]


def uuid7(now_ms: int | None = None, rand: Callable[[int], bytes] = os.urandom) -> str:
    """48-bit Unix milliseconds, version 7, variant 10, 74 random bits."""
    ms = int(time.time() * 1000) if now_ms is None else now_ms
    if not 0 <= ms < 2**48:
        raise ValueError(f"timestamp {ms} ms does not fit 48 bits")
    b = bytearray(rand(16))
    b[0:6] = ms.to_bytes(6, "big")
    b[6] = (b[6] & 0x0F) | 0x70
    b[8] = (b[8] & 0x3F) | 0x80
    return str(uuid.UUID(bytes=bytes(b)))

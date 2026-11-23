"""``json.loads`` for text this package did not write: a world folder's file, an archive, another tool's export.

Three inputs make ``json.loads`` do something its callers do not expect.

A value nested very deep: where the interpreter's own limit is met first, ``json.loads`` raises
``RecursionError``, which is no ``ValueError``, so every reader that catches "not JSON" let it through as
a traceback. Where the limit is higher (Python 3.14 on Linux reads 100,000 levels), the value comes back
whole and the next recursive walk over it fails instead. So the depth is refused here by one number,
``MAX_DEPTH``, the same on every platform.

An integer of more than 4,300 digits: a plain ``ValueError`` whose message advises a Python setting.

A number that is not finite: ``1e400`` reads as infinity, and ``NaN``, ``Infinity`` and ``-Infinity``, which
are no JSON, are read as floats. No writer of this package can write such a value back, and a JavaScript
reader serves it as ``null``.

Here each is a ``ValueError`` in plain words that is no ``json.JSONDecodeError``, so a caller's
``except ValueError`` reads it as a file it cannot read, and says why; a caller that must tell text that is
no JSON from JSON this reader refuses catches the decode error first."""

from __future__ import annotations

import json
import math
import sys
from typing import Any

#: The deepest nesting read: a value at the top is depth 0, an object or array there depth 1, what it holds
#: depth 2. No world data comes near it; every supported interpreter parses this deep.
MAX_DEPTH = 200

_TOO_DEEP = f"nested more than {MAX_DEPTH} deep"


def _float(text: str) -> float:
    value = float(text)
    if not math.isfinite(value):
        raise ValueError("a number too large to read")
    return value


def _constant(token: str) -> Any:
    raise ValueError(f"{token} is not JSON")


def _int(text: str) -> int:
    limit = sys.get_int_max_str_digits()
    if limit and len(text.lstrip("-")) > limit:
        raise ValueError(f"a number of more than {limit} digits")
    return int(text)


def _too_deep(value: Any) -> bool:
    """Whether any object or array sits deeper than ``MAX_DEPTH``. A loop with its own stack, never recursion."""
    stack: list[tuple[Any, int]] = [(value, 1)]
    while stack:
        item, depth = stack.pop()
        if isinstance(item, dict):
            children: Any = item.values()
        elif isinstance(item, list):
            children = item
        else:
            continue
        if depth > MAX_DEPTH:
            return True
        stack.extend((child, depth + 1) for child in children if isinstance(child, (dict, list)))
    return False


def loads(text: str, **kwargs: Any) -> Any:
    """``json.loads(text, **kwargs)``, with the cases above raised as ``ValueError``."""
    kwargs.setdefault("parse_int", _int)
    kwargs.setdefault("parse_float", _float)
    kwargs.setdefault("parse_constant", _constant)
    try:
        value = json.loads(text, **kwargs)
    except RecursionError:
        raise ValueError(_TOO_DEEP) from None
    if _too_deep(value):
        raise ValueError(_TOO_DEEP)
    return value

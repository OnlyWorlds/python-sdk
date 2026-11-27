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
import re
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


#: The characters the depth scan reads: the four brackets, the quote and the backslash.
_SPECIAL = re.compile(r'[\[\]{}"\\]')


def _text_too_deep(text: str) -> bool:
    """Whether the text opens an object or array deeper than ``MAX_DEPTH``, counted in the text itself as each
    one opens, before any parse (the folder format's rule since serial 148): so each value of a repeated key
    counts, and a text past the line is too deep whatever else is wrong with it. Brackets inside a string are
    not counted, and a backslash in a string escapes the character after it; a string left open runs to the
    end of the text, as the npm SDK's scan reads it. One pass, in time linear in the text's length."""
    # No text can open more levels than it has opening brackets.
    if text.count("[") + text.count("{") <= MAX_DEPTH:
        return False
    depth = 0
    in_string = False
    escaped_at = -1
    for m in _SPECIAL.finditer(text):
        i = m.start()
        if i == escaped_at:
            continue
        c = m.group()
        if in_string:
            if c == "\\":
                escaped_at = i + 1
            elif c == '"':
                in_string = False
        elif c == '"':
            in_string = True
        elif c == "[" or c == "{":
            depth += 1
            if depth > MAX_DEPTH:
                return True
        elif c == "]" or c == "}":
            depth -= 1
    return False


def loads(text: str, **kwargs: Any) -> Any:
    """``json.loads(text, **kwargs)``, with the cases above raised as ``ValueError``."""
    kwargs.setdefault("parse_int", _int)
    kwargs.setdefault("parse_float", _float)
    kwargs.setdefault("parse_constant", _constant)
    if _text_too_deep(text):
        raise ValueError(_TOO_DEEP)
    try:
        value = json.loads(text, **kwargs)
    except RecursionError:
        raise ValueError(_TOO_DEEP) from None
    return value

"""``json.loads`` for text this package did not write: a world folder's file, an archive, another tool's export.

Two inputs that are JSON by the grammar make ``json.loads`` raise something its callers do not expect.
A value nested thousands deep raises ``RecursionError``, which is no ``ValueError``, so every reader
that catches "not JSON" let it through as a traceback. An integer of more than 4,300 digits raises a
plain ``ValueError`` whose message advises a Python setting. Here both are a ``ValueError`` in plain
words, so a caller's ``except ValueError`` reads either as a file it cannot read, and says why."""

from __future__ import annotations

import json
import sys
from typing import Any


def _int(text: str) -> int:
    limit = sys.get_int_max_str_digits()
    if limit and len(text.lstrip("-")) > limit:
        raise ValueError(f"a number of more than {limit} digits")
    return int(text)


def loads(text: str, **kwargs: Any) -> Any:
    """``json.loads(text, **kwargs)``, with the two cases above raised as ``ValueError``."""
    kwargs.setdefault("parse_int", _int)
    try:
        return json.loads(text, **kwargs)
    except RecursionError:
        raise ValueError("nested too deep to read") from None

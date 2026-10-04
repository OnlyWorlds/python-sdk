"""On-disk JSON bytes for the folder format (spec §5, ruled v0.3.3).

Normative: UTF-8 without BOM, LF, 2-space indent, one trailing newline, key order
as received, *matching the reference implementation's*
``JSON.stringify(value, null, 2)``. Two writers that agree on layout but not on
bytes make every diff noise, which defeats the format's purpose.

``json.dumps(obj, indent=2, ensure_ascii=False)`` gets most of the way there and
differs from ``JSON.stringify`` in exactly these places, each handled here:

- **Floats with an integral value**: Python writes ``1.0``, JavaScript ``1``.
- **Exponent ranges**: Python writes ``1e+16`` and ``1e-05``; JavaScript writes
  ``10000000000000000`` and ``0.00001`` (ECMA-262 Number::toString switches to
  exponent form only outside 1e-7 <= |x| < 1e21, and writes ``1e-7``, not ``1e-07``).
- **Negative zero**: Python ``-0.0``, JavaScript ``0``.
- **Lone surrogates** (legal in a Python str after ``json.loads("\\ud800")``):
  Python writes the raw code point and the UTF-8 encode then fails; JavaScript
  (ES2019 well-formed stringify) writes ``\\ud800``.

Deliberately NOT emulated (each reported, not hidden):

- **Non-finite numbers**: ``JSON.stringify`` silently writes ``null``. That is a
  value change, so this raises instead.
- **Integers beyond 2**53**: JavaScript has already lost precision at parse time;
  Python keeps the exact value and writes it. Python is the faithful one.
- **Array-index key order**: a JavaScript object enumerates integer-like keys
  ("0", "12") first, ascending, whatever order they arrived in. §5 says key
  order *as received*, so this writer keeps the received order and differs from
  JavaScript only on objects that have such keys.

The digits themselves agree: Python's ``repr(float)`` and ECMAScript both emit the
shortest string that round-trips, so only the formatting around them is ported.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from typing import Any

_REPR = re.compile(r"(-?)(\d+)(?:\.(\d+))?(?:e([+-]\d+))?")
_ESCAPE = re.compile(r'[\x00-\x1f"\\\ud800-\udfff]')
_SHORT = {'"': '\\"', "\\": "\\\\", "\b": "\\b", "\f": "\\f", "\n": "\\n", "\r": "\\r", "\t": "\\t"}


def js_number(x: float) -> str:
    """Format a float exactly as ECMAScript Number::toString (and so JSON.stringify) does."""
    if not math.isfinite(x):
        raise ValueError(f"non-finite number {x!r} has no JSON form (JSON.stringify would silently write null)")
    if x == 0:
        return "0"  # covers -0.0
    m = _REPR.fullmatch(repr(x))
    if m is None:  # pragma: no cover - repr(float) always matches
        raise ValueError(f"unexpected float repr {x!r}")
    sign, intpart, frac, exp = m.group(1), m.group(2), m.group(3) or "", m.group(4)
    raw = intpart + frac
    stripped = raw.lstrip("0")
    # value = 0.<digits> x 10**n
    n = len(intpart) + int(exp or 0) - (len(raw) - len(stripped))
    digits = stripped.rstrip("0")
    k = len(digits)
    if k <= n <= 21:
        body = digits + "0" * (n - k)
    elif 0 < n <= 21:
        body = digits[:n] + "." + digits[n:]
    elif -6 < n <= 0:
        body = "0." + "0" * (-n) + digits
    else:
        e = n - 1
        body = digits[0] + ("." + digits[1:] if k > 1 else "") + "e" + ("+" if e >= 0 else "-") + str(abs(e))
    return sign + body


def _string(s: str) -> str:
    def esc(m: re.Match[str]) -> str:
        c = m.group(0)
        return _SHORT.get(c) or f"\\u{ord(c):04x}"

    return '"' + _ESCAPE.sub(esc, s) + '"'


def _dump(v: Any, indent: str, out: list[str]) -> None:
    if v is None:
        out.append("null")
    elif v is True:
        out.append("true")
    elif v is False:
        out.append("false")
    elif isinstance(v, int):
        out.append(str(v))
    elif isinstance(v, float):
        out.append(js_number(v))
    elif isinstance(v, str):
        out.append(_string(v))
    elif isinstance(v, Mapping):
        if not v:
            out.append("{}")
            return
        inner = indent + "  "
        out.append("{")
        first = True
        for k, item in v.items():
            if not isinstance(k, str):
                raise TypeError(f"JSON object keys must be str, got {type(k).__name__}")
            out.append("\n" + inner if first else ",\n" + inner)
            first = False
            out.append(_string(k) + ": ")
            _dump(item, inner, out)
        out.append("\n" + indent + "}")
    elif isinstance(v, Sequence) and not isinstance(v, (bytes, bytearray)):
        if not v:
            out.append("[]")
            return
        inner = indent + "  "
        out.append("[")
        for i, item in enumerate(v):
            out.append(("\n" if i == 0 else ",\n") + inner)
            _dump(item, inner, out)
        out.append("\n" + indent + "]")
    else:
        raise TypeError(f"not JSON-serializable: {type(v).__name__}")


def serialize(value: Any) -> str:
    """The canonical on-disk text: ``JSON.stringify(value, null, 2) + "\\n"``."""
    out: list[str] = []
    _dump(value, "", out)
    out.append("\n")
    return "".join(out)


def encode(value: Any) -> bytes:
    """The canonical on-disk bytes: UTF-8, no BOM, LF."""
    return serialize(value).encode("utf-8")

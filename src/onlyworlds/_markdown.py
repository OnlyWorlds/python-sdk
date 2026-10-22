"""Markdown helpers shared by the exporters that write prose (``okf``, ``pack``). No YAML here, so the
pack, which needs none, does not pull in the OKF extra."""

from __future__ import annotations

import re

__all__ = ["escape_text", "heading", "one_line"]


def one_line(text: object) -> str:
    """Every run of whitespace, line breaks included, as one space; the ends trimmed."""
    return " ".join(str(text).split())


def heading(name: str) -> str:
    """A field name as a heading: underscores as spaces, the first letter capitalised (``hit_points``:
    ``Hit points``). No acronym rule: ``STR`` stays ``STR`` and ``image_url`` reads ``Image url``."""
    words = name.replace("_", " ")
    return words[:1].upper() + words[1:]


_FAKE_HEADING = re.compile(r" {0,3}[#\\]| {0,3}(=+|-+)[ \t]*$")


def escape_text(text: str) -> str:
    """A text field as body markdown: LF, outer blank lines trimmed, and a backslash before any
    line markdown would read as a heading (`# x`, or a `===`/`---` line that would underline the
    line above) or that already begins with one (else `# x` and `\\# x` would read the same)."""
    out = []
    for line in str(text).replace("\r\n", "\n").replace("\r", "\n").strip("\n").split("\n"):
        if _FAKE_HEADING.match(line):
            i = len(line) - len(line.lstrip(" "))
            line = line[:i] + "\\" + line[i:]
        out.append(line)
    return "\n".join(out)

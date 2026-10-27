"""Markdown helpers shared by the exporters that write prose (``okf``, ``pack``). No YAML here, so the
pack, which needs none, does not pull in the OKF extra."""

from __future__ import annotations

import re

from .address import AddressError, parse_ow_link

__all__ = ["OW_REF", "escape_text", "heading", "one_line", "prose_target"]


def one_line(text: object) -> str:
    """Every run of whitespace, line breaks included, as one space; the ends trimmed."""
    return " ".join(str(text).split())


def heading(name: str) -> str:
    """A field name as a heading: underscores as spaces, the first letter capitalised (``hit_points``:
    ``Hit points``). No acronym rule: ``STR`` stays ``STR`` and ``image_url`` reads ``Image url``."""
    words = name.replace("_", " ")
    return words[:1].upper() + words[1:]


# An in-prose reference: a markdown link whose target is an ow:// address, label in group 1, target in
# group 2. Which element it names, if any in this world, is ``prose_target``'s to read.
OW_REF = re.compile(r"\[([^\]\n]*)\]\((ow://[^)\s]*)\)")
# The folder format's in-world form (atlas `src/core/ow-links.ts`, OW_LINK_HREF_RE): the type word in any
# case, the id as written. The address profile reads every other form.
_IN_WORLD = re.compile(r"ow://([A-Za-z_]+)/([\w-]+)")


def prose_target(target: str, world_id: object = None) -> str | None:
    """The element id an in-prose link's target names in this world, or None: another world's element
    (``ow://<world>/<type>/<id>`` with a world id other than ``world_id``), a world's own address, or a
    target the address profile refuses. A moment (``@<step>``) or a lens (``?lens=<id>``) still names the
    element, and the cross-world form with this world's own id names one of its own."""
    m = _IN_WORLD.fullmatch(target)
    if m:
        return m.group(2)
    try:
        r = parse_ow_link(target)
    except AddressError:
        return None
    if r.id is None:
        return None
    if r.world is not None and (not isinstance(world_id, str) or r.world != world_id.lower()):
        return None
    return r.id


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

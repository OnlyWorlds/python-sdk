"""The names an import door makes: an element name that is not one string of the export taken as written.

There are two kinds, and they are not the same. A ``joined`` name is the export's own words with ours between
them: a LegendKeeper map document of a page becomes a Map named ``<resource>: <document>``. An ``ours`` name is
one for a thing the export never names at all: a frame's corner Marker (``<frame>: corner 1``), a part of a
region (``<zone>: part 2``), a frame with no name (``Frame``), an arrow with no label (``Board link``). Only the
second is wholly the door's.

Each door lists the names it makes in its ``MADE_NAMES``, a tuple of ``MadeName`` (empty for a door that makes
none), and its report counts the elements of each kind: one line a kind, beside the elements and never in them
(no field on an element says its name was made). A reader such as a gate tells a made name with
``MadeName.fits``: the element's type, and its whole name matched by the record's ``regex``. A name that is the
export's text and fits a pattern too (a frame its author named ``Frame``) cannot be told apart by its name; the
door counts what it made, and a reader of names alone counts both.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

__all__ = ["ANY_TYPE", "MadeName"]

#: A ``MadeName.type`` for a name the door gives an element of whatever type it became (a page with no name).
ANY_TYPE = "*"


@dataclass(frozen=True)
class MadeName:
    """One kind of name a door makes. ``kind`` is its stable id (lowercase, hyphens: ``map-document``). ``type``
    is the element type it names, written as an element's ``type`` is (``map``), or ``ANY_TYPE``. ``pattern`` is
    its human form (``<resource>: <document>``): angle brackets around the export's words, the rest the door's.
    ``source`` is ``joined`` (the export's words, the door's joint) or ``ours`` (a name for a thing the export
    names nowhere). ``regex`` matches a whole name of the kind (Python ``re.fullmatch``); the export's words in
    it are ``.+``, so it pins the made part only."""

    kind: str
    type: str
    pattern: str
    source: Literal["joined", "ours"]
    regex: str

    def fits(self, etype: str, name: str) -> bool:
        """True when an element of type ``etype`` named ``name`` has a name of this kind's shape."""
        return self.type in (ANY_TYPE, etype) and re.fullmatch(self.regex, name) is not None


def _counts(made: Sequence[MadeName], kinds: Mapping[str, str], ids: Iterable[str]) -> dict[str, int]:
    """The kinds counted over the elements written: ``kinds`` maps an element id to the kind its door recorded
    when it named it, ``ids`` are the ids written. In the declared order, a kind with none left out. A recorded
    kind the door does not declare is a ValueError: the declaration and the door disagree."""
    declared = {m.kind for m in made}
    tally: dict[str, int] = {}
    for eid in ids:
        kind = kinds.get(eid)
        if kind is None:
            continue
        if kind not in declared:
            raise ValueError(f"a made name of kind {kind!r}, which MADE_NAMES does not declare")
        tally[kind] = tally.get(kind, 0) + 1
    return {m.kind: tally[m.kind] for m in made if m.kind in tally}


_SAID = {
    "joined": "joined: the export's words, ours between them",
    "ours": "ours: the export gives it no name",
}


def _lines(made: Sequence[MadeName], counts: Mapping[str, int]) -> list[str]:
    """The report's lines for the names made: a heading with the total, then one line a kind with a count."""
    if not any(counts.values()):
        return []
    by_kind = {m.kind: m for m in made}
    lines = [f"Names made by the import, not taken whole from the export ({sum(counts.values())}), one line a kind:"]
    for kind, n in counts.items():
        m = by_kind[kind]
        what = "any type" if m.type == ANY_TYPE else m.type
        lines.append(f"  - {m.kind}, {what} {m.pattern!r}: {n} ({_SAID[m.source]})")
    return lines

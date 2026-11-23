"""Element names found in prose: ``name_finder`` reads a world's names once and answers a function that finds
them in any text. It finds and never writes: what a tool does with a found name (a mark for a reader, a
suggestion, a link a person chooses to make) is the tool's.

A rule of this package and the npm SDK's ``nameFinder``, not of the standard: both run one file of cases
(``tests/fixtures/name-finder.cases.json``, the same bytes in both repositories)."""

from __future__ import annotations

import unicodedata
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Literal

from .address import find_ow_links
from .room import _WHITE_SPACE
from .worldfile import simple_case_fold

__all__ = ["NameFound", "name_finder"]

_NAME_MIN = 3
"""A name shorter than this many characters (code points, after its white space is trimmed) is never looked for."""

_ASCII_WORD = frozenset("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_")


@dataclass(frozen=True)
class NameFound[T]:
    """One name found in a text: ``start`` and ``end`` in the text (code points; the npm SDK's ``nameFinder``
    counts UTF-16 units), and ``element``, the same object ``name_finder`` was given."""

    start: int
    end: int
    element: T


class _Hit[T]:
    __slots__ = ("element", "id", "shared")

    def __init__(self, id: str, element: T) -> None:
        self.id = id
        self.element = element
        self.shared = False


class _Node[T]:
    __slots__ = ("hit", "next")

    def __init__(self) -> None:
        self.next: dict[str, _Node[T]] = {}
        self.hit: _Hit[T] | None = None


def _in_a_word(ch: str) -> bool:
    """A letter of any script, a combining mark, a decimal digit or an underscore: beside one, a name is inside a
    word."""
    if ch < "\x80":
        return ch in _ASCII_WORD
    return ch.isalpha() or unicodedata.category(ch) == "Nd" or unicodedata.category(ch).startswith("M")


def _markdown_links(text: str) -> list[tuple[int, int]]:
    """Every Markdown link ``[label](target)`` as ``(start, end)``: a ``[``, a label up to the first ``]``, a ``(``
    right after it, a target up to the first ``)``. One pass: each bracket and parenthesis is searched for once."""
    spans: list[tuple[int, int]] = []
    close = -2
    paren = -2
    opened = text.find("[")
    while opened != -1:
        if close <= opened:
            close = text.find("]", opened + 1)
        if close == -1:
            break
        if not text.startswith("(", close + 1):
            opened = text.find("[", opened + 1)
            continue
        if paren < close + 2:
            paren = text.find(")", close + 2)
        if paren == -1:
            break
        spans.append((opened, paren + 1))
        opened = text.find("[", paren + 1)
    return spans


def _passed_over(text: str) -> list[tuple[int, int]]:
    """The stretches no name is read in: every address and every Markdown link, in order, none overlapping."""
    spans = _markdown_links(text)
    spans.extend((a.start, a.end) for a in find_ow_links(text))
    spans.sort()
    out: list[tuple[int, int]] = []
    for start, end in spans:
        if out and start < out[-1][1]:
            if end > out[-1][1]:
                out[-1] = (out[-1][0], end)
        else:
            out.append((start, end))
    return out


def name_finder[T: Mapping[str, Any]](
    elements: Iterable[T],
    *,
    case: Literal["exact", "folded"],
    names: Callable[[T], Iterable[object]] | None = None,
) -> Callable[[str], list[NameFound[T]]]:
    """A finder of a world's element names in prose: read the names once, then call the answer on each text.

    ``elements`` is any iterable of mappings with a string ``id`` and a ``name``. ``case`` must be given: ``"exact"``
    (a name as written) or ``"folded"`` (simple case folding, Unicode 15.1, the fold the ``.owworld`` reader uses);
    there is no default, so a tool never gets the other rule by leaving it out. ``names`` gives the names an element
    is found by, by default its ``name`` alone; a value that is not a string is passed over.

    The answer, ``find(text)``, lists every ``NameFound`` (``start``, ``end``, ``element``) in order, none
    overlapping:

    - A whole name only: the character on each side of it is not a letter, a combining mark, a decimal digit or an
      underscore, in any script. So ``Kira's`` and ``Kira-led`` hold the name ``Kira``, and ``Kiran`` does not.
    - A name is trimmed of white space and is three characters at least; a shorter one is never looked for.
    - Where several names start at one place, the longest whole one is taken (``Iron Gate`` over ``Iron``).
    - A name two elements share is never answered, and nothing inside it is: the text stays plain there. One
      element listed twice, or found by two of its own names, is one element.
    - Nothing is read inside an address (what ``find_ow_links`` finds) or a Markdown link ``[label](target)``, and
      no name is read across the edge of one.
    - Text is compared as written: no Unicode normalisation, and a space in a name matches that one space.

    ``element`` in an answer is the object that was passed in. Nothing given is changed. The work for one text is
    at most its length times the longest name's length, whatever the number of names, with no pattern that
    backtracks. ``start`` and ``end`` count code points (the npm SDK's ``nameFinder`` counts UTF-16 units). A
    ``case`` that is neither word, a ``names`` that cannot be called, an element without a string ``id``, or a
    ``text`` that is not a string is a ``TypeError``."""
    if case not in ("exact", "folded"):
        raise TypeError(f"name_finder: case is 'exact' or 'folded'; got {case!r}.")
    if names is not None and not callable(names):
        raise TypeError("name_finder: names is a function from an element to its names.")
    if isinstance(elements, (str, bytes, Mapping)) or not isinstance(elements, Iterable):
        raise TypeError("name_finder: elements is an iterable of mappings with an id and a name.")
    folded = case == "folded"
    root: _Node[T] = _Node()
    for element in elements:
        if not isinstance(element, Mapping) or not isinstance(element.get("id"), str) or element["id"] == "":
            raise TypeError("name_finder: every element is a mapping with a string id.")
        for raw in names(element) if names is not None else (element.get("name"),):
            if not isinstance(raw, str):
                continue
            name = raw.strip(_WHITE_SPACE)
            if len(name) < _NAME_MIN:
                continue
            node = root
            for ch in simple_case_fold(name) if folded else name:
                child = node.next.get(ch)
                if child is None:
                    child = node.next[ch] = _Node()
                node = child
            if node.hit is None:
                node.hit = _Hit(element["id"], element)
            elif node.hit.id != element["id"]:
                node.hit.shared = True

    def find(text: str) -> list[NameFound[T]]:
        if not isinstance(text, str):
            raise TypeError("name_finder: text must be a string")
        found: list[NameFound[T]] = []
        firsts = root.next
        if not firsts:
            return found
        spans = _passed_over(text)
        hay = simple_case_fold(text) if folded else text
        length = len(text)
        span = 0
        i = 0
        while i < length:
            if span < len(spans) and i >= spans[span][0]:
                i = spans[span][1]
                span += 1
                continue
            if hay[i] in firsts and (i == 0 or not _in_a_word(text[i - 1])):
                limit = spans[span][0] if span < len(spans) else length
                node = root
                j = i
                best: _Hit[T] | None = None
                best_end = -1
                while j < limit:
                    child = node.next.get(hay[j])
                    if child is None:
                        break
                    node = child
                    j += 1
                    if node.hit is not None and (j >= length or not _in_a_word(text[j])):
                        best = node.hit
                        best_end = j
                if best is not None:
                    if not best.shared:
                        found.append(NameFound(i, best_end, best.element))
                    i = best_end
                    continue
            i += 1
        return found

    return find

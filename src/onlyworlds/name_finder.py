"""Element names found in prose: ``name_finder`` reads a world's names once and answers a function that finds
them in any text. It finds and never writes: what a tool does with a found name (a mark for a reader, a
suggestion, a link a person chooses to make) is the tool's.

A rule of this package and the npm SDK's ``nameFinder``, not of the standard: both run one file of cases
(``tests/fixtures/name-finder.cases.json``, the same bytes in both repositories)."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Literal

from .address import find_ow_links
from .room import _WHITE_SPACE
from .worldfile import simple_case_fold

__all__ = ["NameFinder", "NameFound", "NameShared", "name_finder"]

_NAME_MIN = 3
"""A name shorter than this many characters (code points, after its white space is trimmed) is never looked for."""

_ASCII_WORD = frozenset("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_")

_END = ""
"""The mark the matcher reads between two characters wherever a name may end: before a character that is not a
word character, and at the end of the text. No character is the empty string."""


@dataclass(frozen=True)
class NameFound[T]:
    """One name found in a text: ``start`` and ``end`` in the text (code points; the npm SDK's ``nameFinder``
    counts UTF-16 units), and ``element``, the same object ``name_finder`` was given."""

    start: int
    end: int
    element: T


@dataclass(frozen=True)
class NameShared[T]:
    """A name two or more elements hold: the finder answers nothing for it, and this says that it is there.
    ``name`` is the name as the finder compares it (trimmed of white space, and folded when ``case`` is
    ``"folded"``); ``elements`` are the elements that hold it, two at least, in the order they were given: the same
    objects ``name_finder`` was given."""

    name: str
    elements: tuple[T, ...]


class _Hit[T]:
    """One name, as compared, and every element that holds it."""

    __slots__ = ("elements", "ids", "length", "name")

    def __init__(self, name: str, element: T) -> None:
        self.name = name
        self.length = len(name)
        self.elements: list[T] = [element]
        self.ids: set[str] | None = None
        """The ids of ``elements``, kept once a second element holds the name."""


class _State[T]:
    """A state of the matcher. The names are held backwards, each from its last character to its first, with
    ``_END`` before every character that is not a word character and once at the name's end: so a text read from
    its end towards its start, with the same mark laid wherever a name may end, passes each character once (Aho
    and Corasick's failure links), and the state after a character says which whole names start there.

    ``hit`` is the name that is this state, read backwards; ``longest`` the longest name that ends, read backwards,
    at this state: ``hit``, or the failure state's."""

    __slots__ = ("fail", "hit", "longest", "next")

    def __init__(self) -> None:
        self.next: dict[str, _State[T]] = {}
        self.fail: _State[T] | None = None
        self.hit: _Hit[T] | None = None
        self.longest: _Hit[T] | None = None


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


# Unicode's White_Space code points (room's _WHITE_SPACE, one string) end a bare web address and an autolink.
_SCHEME = re.compile(r"https?://", re.ASCII | re.IGNORECASE)
_SCHEME_CHAR = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+.-")


def _ascii_letter(ch: str) -> bool:
    return ("A" <= ch <= "Z") or ("a" <= ch <= "z")


def _web_addresses(text: str) -> list[tuple[int, int]]:
    """Every bare web address and every autolink, in any text. A bare address starts at ``http://`` or ``https://``
    (the scheme in any ASCII case) and runs to just before the first white space or ``<``. An autolink is ``<``, a
    scheme (an ASCII letter, then 1 to 31 of letters, digits, ``+``, ``.`` or ``-``), ``:``, then anything but white
    space, a control character, ``<`` or ``>``, up to the closing ``>``."""
    spans: list[tuple[int, int]] = []
    length = len(text)
    pos = 0
    while (m := _SCHEME.search(text, pos)) is not None:
        end = m.end()
        while end < length and text[end] not in _WHITE_SPACE and text[end] != "<":
            end += 1
        spans.append((m.start(), end))
        pos = end
    opened = text.find("<")
    while opened != -1:
        i = opened + 1
        if i < length and _ascii_letter(text[i]):
            n = 1
            i += 1
            while i < length and n < 32 and text[i] in _SCHEME_CHAR:
                i += 1
                n += 1
            if n >= 2 and i < length and text[i] == ":":
                i += 1
                while i < length:
                    c = text[i]
                    if c in "<>" or c < "\x20" or c == "\x7f" or c in _WHITE_SPACE:
                        break
                    i += 1
                if i < length and text[i] == ">":
                    spans.append((opened, i + 1))
                    opened = text.find("<", i + 1)
                    continue
        opened = text.find("<", opened + 1)
    return spans


def _line_bounds(text: str) -> list[tuple[int, int]]:
    """Where each line starts and ends (before its ``\\n``), in order."""
    out: list[tuple[int, int]] = []
    start = 0
    while True:
        nl = text.find("\n", start)
        if nl == -1:
            out.append((start, len(text)))
            return out
        out.append((start, nl))
        start = nl + 1


def _fence_of(text: str, start: int, end: int) -> tuple[str, int, int] | None:
    """A line's fence, after at most three spaces: ``(char, length, after)`` for a run of three or more `` ` `` or
    ``~``, or None."""
    i = start
    while i < end and i - start < 3 and text[i] == " ":
        i += 1
    if i >= end or text[i] not in "`~":
        return None
    char = text[i]
    j = i
    while j < end and text[j] == char:
        j += 1
    return (char, j - i, j) if j - i >= 3 else None


def _markdown_stretches(text: str) -> list[tuple[int, int]]:
    """The Markdown stretches no name is read in (``markdown=True``), as the npm SDK's ``markdownStretches`` reads
    them. Fenced code blocks first: a line whose fence opens one (a backtick fence holds no backtick in the rest of
    its line) runs to a later line holding only a fence of the same character, at least as long, and spaces or tabs
    after it, or to the end of the text. Outside them: an inline code span (a run of backticks to the next run of
    exactly as many; a run with none is prose), an HTML comment (``<!--`` to the first ``-->``), an HTML tag (``<``,
    an optional ``/``, an ASCII letter, to the first ``>``), and a reference definition's line (after at most three
    spaces, ``[``, a label, and the line's first ``]`` followed by ``:``)."""
    spans: list[tuple[int, int]] = []
    lines = _line_bounds(text)
    outside: list[tuple[int, int]] = []
    seg_start = 0
    bracket = -2  # the next "]" at or after the place last asked about, searched for once per place passed
    k = 0
    while k < len(lines):
        ls, le = lines[k]
        opener = _fence_of(text, ls, le)
        if opener is None or (opener[0] == "`" and text.find("`", opener[2], le) != -1):
            i = ls
            while i < le and i - ls < 3 and text[i] == " ":
                i += 1
            if i < le and text[i] == "[":
                if bracket != -1 and bracket < i + 1:
                    bracket = text.find("]", i + 1)
                close = bracket
                if close != -1 and close < le and close > i + 1 and text.startswith(":", close + 1):
                    spans.append((ls, le))
            k += 1
            continue
        m = k + 1
        while m < len(lines):
            cs, ce = lines[m]
            closer = _fence_of(text, cs, ce)
            if closer is not None and closer[0] == opener[0] and closer[1] >= opener[1]:
                j = closer[2]
                while j < ce and text[j] in " \t\r":
                    j += 1
                if j == ce:
                    break
            m += 1
        block_end = lines[m][1] if m < len(lines) else len(text)
        if ls > seg_start:
            outside.append((seg_start, ls))
        spans.append((ls, block_end))
        seg_start = block_end
        k = m + 1
    if seg_start < len(text):
        outside.append((seg_start, len(text)))
    for s, e in outside:
        # Inline code spans: every maximal backtick run, then each opening run to the next run of its length.
        runs: list[tuple[int, int]] = []
        i = text.find("`", s)
        while i != -1 and i < e:
            j = i
            while j < e and text[j] == "`":
                j += 1
            runs.append((i, j - i))
            i = text.find("`", j)
        by_length: dict[int, list[int]] = {}
        for idx, (_, n) in enumerate(runs):
            by_length.setdefault(n, []).append(idx)
        cursor: dict[int, int] = {}
        r = 0
        while r < len(runs):
            at, n = runs[r]
            positions = by_length[n]
            c = cursor.get(n, 0)
            while c < len(positions) and positions[c] <= r:
                c += 1
            cursor[n] = c
            if c < len(positions):
                spans.append((at, runs[positions[c]][0] + n))
                r = positions[c] + 1
            else:
                r += 1
        # HTML comments and tags.
        gt = -2
        comment_end = -2
        opened = text.find("<", s)
        while opened != -1 and opened < e:
            if text.startswith("<!--", opened):
                if comment_end != -1 and comment_end < opened + 4:
                    comment_end = text.find("-->", opened + 4)
                if comment_end != -1 and comment_end + 3 <= e:
                    spans.append((opened, comment_end + 3))
                    opened = text.find("<", comment_end + 3)
                    continue
            else:
                name = opened + 2 if text.startswith("/", opened + 1) else opened + 1
                if name < len(text) and _ascii_letter(text[name]):
                    if gt != -1 and gt < name:
                        gt = text.find(">", name)
                    if gt != -1 and gt < e:
                        spans.append((opened, gt + 1))
                        opened = text.find("<", gt + 1)
                        continue
            opened = text.find("<", opened + 1)
    return spans


def _passed_over(text: str, markdown: bool) -> list[tuple[int, int]]:
    """The stretches no name is read in, in order, none overlapping: every address, every Markdown link, every bare
    web address and autolink, and with ``markdown`` the Markdown stretches too."""
    spans = _markdown_links(text)
    spans.extend((a.start, a.end) for a in find_ow_links(text))
    spans.extend(_web_addresses(text))
    if markdown:
        spans.extend(_markdown_stretches(text))
    spans.sort()
    out: list[tuple[int, int]] = []
    for start, end in spans:
        if out and start < out[-1][1]:
            if end > out[-1][1]:
                out[-1] = (out[-1][0], end)
        else:
            out.append((start, end))
    return out


class NameFinder[T]:
    """What ``name_finder`` answers: call it on a text for the names found there; ``shared`` lists the names two or
    more elements hold. Made by ``name_finder``, not by hand."""

    __slots__ = ("_folded", "_root", "_shared")

    def __init__(self, root: _State[T], hits: list[_Hit[T]], folded: bool) -> None:
        self._root = root
        self._folded = folded
        self._shared: tuple[NameShared[T], ...] = tuple(
            NameShared(hit.name, tuple(hit.elements)) for hit in hits if len(hit.elements) > 1
        )

    @property
    def shared(self) -> tuple[NameShared[T], ...]:
        """Every name two or more elements hold, in the order each name was first met. The finder never answers
        one of these, so a tool reads this to say why a name stays plain."""
        return self._shared

    def __call__(self, text: str, *, markdown: bool = False) -> list[NameFound[T]]:
        """The names found in ``text``. With ``markdown=True`` (since 0.154.0), for a text known to be Markdown,
        nothing is read inside an inline code span, a fenced code block, an HTML tag or comment, or a reference
        definition's line either."""
        if not isinstance(text, str):
            raise TypeError("name_finder: text must be a string")
        if not isinstance(markdown, bool):
            raise TypeError(f"name_finder: markdown is True or False, not {type(markdown).__name__}")
        found: list[NameFound[T]] = []
        root = self._root
        if not root.next:
            return found
        spans = _passed_over(text, markdown)
        hay = simple_case_fold(text) if self._folded else text
        length = len(text)
        ascii_word = _ASCII_WORD
        end_mark = _END
        # Where a whole name starts and the longest one that does, as the backward pass meets them: last place first.
        starts: list[int] = []
        longest: list[_Hit[T]] = []
        frm = 0
        for span in range(len(spans) + 1):
            to = spans[span][0] if span < len(spans) else length
            if to > frm:
                starts.clear()
                longest.clear()
                state = root
                k = to
                # Whether a name may end at k: the text ends there, or the character at k is not a word character.
                if k >= length:
                    may_end = True
                else:
                    ch = text[k]
                    may_end = ch not in ascii_word if ch < "\x80" else not _in_a_word(ch)
                while k > frm:
                    if may_end:
                        to_state = state.next.get(end_mark)
                        while to_state is None:
                            back = state.fail
                            if back is None:
                                to_state = root
                                break
                            state = back
                            to_state = state.next.get(end_mark)
                        state = to_state
                    k -= 1
                    ch = text[k]
                    may_end = ch not in ascii_word if ch < "\x80" else not _in_a_word(ch)
                    if state is not root:
                        token = hay[k]
                        to_state = state.next.get(token)
                        while to_state is None:
                            back = state.fail
                            if back is None:
                                to_state = root
                                break
                            state = back
                            to_state = state.next.get(token)
                        state = to_state
                    hit = state.longest
                    if hit is not None:
                        if k == 0:
                            word_before = False
                        else:
                            before = text[k - 1]
                            word_before = before in ascii_word if before < "\x80" else _in_a_word(before)
                        if not word_before:
                            starts.append(k)
                            longest.append(hit)
                # Forwards over what was met: the first place a name starts takes its longest name, and the next
                # name starts at or after that one's end.
                free = frm
                for r in range(len(starts) - 1, -1, -1):
                    start = starts[r]
                    if start < free:
                        continue
                    hit = longest[r]
                    end = start + hit.length
                    if len(hit.elements) == 1:
                        found.append(NameFound(start, end, hit.elements[0]))
                    free = end
            if span < len(spans):
                frm = spans[span][1]
        return found


def name_finder[T: Mapping[str, Any]](
    elements: Iterable[T],
    *,
    case: Literal["exact", "folded"],
    names: Callable[[T], Iterable[object]] | None = None,
) -> NameFinder[T]:
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
    - Nothing is read inside an address (what ``find_ow_links`` finds), a Markdown link ``[label](target)``, a bare
      web address (``https://…`` to the next white space or ``<``) or an autolink (``<scheme:…>``), and no name is
      read across the edge of one. With ``find(text, markdown=True)`` (since 0.154.0), for a text known to be
      Markdown, nothing is read inside an inline code span, a fenced code block, an HTML tag or comment, or a
      reference definition's line either. An indented code block, a fence inside a quote or a list, and a
      definition's title on the next line are read as prose.
    - Text is compared as written: no Unicode normalisation, and a space in a name matches that one space.

    ``find.shared`` lists every name two or more elements hold, each a ``NameShared`` (``name``, ``elements``): the
    name as it is compared (trimmed, and folded when ``case`` is ``"folded"``) and the elements that hold it, in the
    order given. A name too short to be looked for is not on it.

    ``element`` in an answer is the object that was passed in. Nothing given is changed. The work for one text
    grows with its length alone, whatever the names and however many: the text is read once, from its end to its
    start, and no character is read again for another name. Reading the names grows with their total length.
    ``start`` and ``end`` count code points (the npm SDK's ``nameFinder`` counts UTF-16 units). A ``case`` that is
    neither word, a ``names`` that cannot be called, an element without a string ``id``, or a ``text`` that is not
    a string is a ``TypeError``."""
    if case not in ("exact", "folded"):
        raise TypeError(f"name_finder: case is 'exact' or 'folded'; got {case!r}.")
    if names is not None and not callable(names):
        raise TypeError("name_finder: names is a function from an element to its names.")
    if isinstance(elements, (str, bytes, Mapping)) or not isinstance(elements, Iterable):
        raise TypeError("name_finder: elements is an iterable of mappings with an id and a name.")
    folded = case == "folded"
    root: _State[T] = _State()
    hits: list[_Hit[T]] = []
    for element in elements:
        if not isinstance(element, Mapping) or not isinstance(element.get("id"), str) or element["id"] == "":
            raise TypeError("name_finder: every element is a mapping with a string id.")
        element_id: str = element["id"]
        for raw in names(element) if names is not None else (element.get("name"),):
            if not isinstance(raw, str):
                continue
            name = raw.strip(_WHITE_SPACE)
            if len(name) < _NAME_MIN:
                continue
            if folded:
                name = simple_case_fold(name)
            # The name backwards: the end mark, then each character from the last to the first, and the mark again
            # after (so, in the text, before) every character but the first that is not a word character.
            state = root
            for k in range(len(name) - 1, -1, -1):
                if k == len(name) - 1:
                    state = _child(state, _END)
                ch = name[k]
                state = _child(state, ch)
                if k > 0 and not _in_a_word(ch):
                    state = _child(state, _END)
            hit = state.hit
            if hit is None:
                state.hit = _Hit(name, element)
                hits.append(state.hit)
            elif hit.ids is None:
                first_id: str = hit.elements[0]["id"]
                if first_id != element_id:
                    hit.ids = {first_id, element_id}
                    hit.elements.append(element)
            elif element_id not in hit.ids:
                hit.ids.add(element_id)
                hit.elements.append(element)

    # The failure links, level by level: where the matcher goes on when the text leaves the name it was reading.
    level: list[_State[T]] = []
    for child in root.next.values():
        child.fail = root
        child.longest = child.hit
        level.append(child)
    while level:
        deeper: list[_State[T]] = []
        for state in level:
            for token, child in state.next.items():
                back = state.fail
                while back is not None and token not in back.next:
                    back = back.fail
                fail = root if back is None else back.next[token]
                child.fail = fail
                child.longest = child.hit if child.hit is not None else fail.longest
                deeper.append(child)
        level = deeper

    return NameFinder(root, hits, folded)


def _child[T](state: _State[T], token: str) -> _State[T]:
    child = state.next.get(token)
    if child is None:
        child = state.next[token] = _State()
    return child

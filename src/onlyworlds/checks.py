"""The checks profile (schema-dist ``profiles/checks.md``, serial 47; serial 54 adds the list case
and reader rules 6 to 8): a world's house rules, read by machine.

A work world's Charter (a Law with supertype Charter) may carry ``x_checks_rules``, a list of rules,
each the Charter's sentence beside an object a reader applies::

    {"rule": "every Character carries a reputation",
     "where": {"type": "character"},
     "require": {"field": "reputation", "present": true}}

``where`` scopes the elements: ``type`` (one of the 22, a string or a list), ``supertype`` and
``subtype`` (optional, a string or a list), each compared trimmed and without regard to case as the
room profile folds its pairs (``room.is_room_element``); an empty string matches an empty or absent
value. ``require`` names a ``field`` (one the pinned schema gives every scoped type, or an extension
key) and exactly one predicate: ``present: true`` (not null, not a blank string, not an empty list),
``matches`` (a search, in the regex subset Python's ``re`` and JavaScript's ``RegExp`` share),
``links_min: n`` (a link field holds at least n ids) or ``one_of`` (the value, folded, is one of the
list's).

``apply_checks`` gives one ``CheckRow`` per rule, in the list's order: the sentence, how many elements
the rule scoped, and every short element by type, id and name. A rule it cannot apply comes back with
``not_checked`` saying why (a predicate outside the four, a type the pinned schema does not name, a
field the type lacks that is not an extension key, a pattern refused, a malformed rule): never a
silent pass, never an exception. It never writes, reorders or repairs the list, and a rule's text is
data: a pattern longer than ``PATTERN_CAP`` is refused rather than run. The doctor's flag 11 reads it
from every Charter.
"""

from __future__ import annotations

import dataclasses
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from ._schema import EXTENSION_PREFIXES, FIELD_KINDS
from .folder import FolderElement
from .room import _WHITE_SPACE, _fold

__all__ = ["CHECKS_FIELD", "PATTERN_CAP", "PREDICATES", "CheckRow", "apply_checks"]

#: The profile's one extension field, on the Charter Law only.
CHECKS_FIELD = "x_checks_rules"
#: The four predicates, in the profile's order.
PREDICATES: tuple[str, ...] = ("present", "matches", "links_min", "one_of")
#: A ``matches`` pattern longer than this is refused, not run: the pattern is the world's data (rule 5).
PATTERN_CAP = 400

_WHERE_KEYS = ("type", "supertype", "subtype")
_LINK_KINDS = frozenset({"single_link", "multi_link"})
#: The inline flags the two engines share, allowed once at the pattern's start.
_LEADING_FLAGS = re.compile(r"\(\?[im]{1,2}\)")
_COMPILED: dict[str, re.Pattern[str]] = {}
_COMPILED_CAP = 256


@dataclass(frozen=True)
class CheckRow:
    """One rule's result. ``index`` is the rule's place in the list; ``rule`` its sentence (``None``
    when the rule has none); ``field`` the field it reads. ``not_checked`` is ``None`` for a rule that
    was applied, else why it was not (then ``scoped`` is 0 and ``short`` empty: nothing was judged)."""

    index: int
    rule: str | None
    field: str | None
    scoped: int = 0
    short: list[dict[str, Any]] = dataclasses.field(default_factory=list)
    not_checked: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "rule": self.rule,
            "field": self.field,
            "scoped": self.scoped,
            "short": [dict(s) for s in self.short],
            "not_checked": self.not_checked,
        }


def _strings(value: Any) -> list[str] | None:
    """A ``where`` value as a list of strings: a string, or a non-empty list of strings; else None."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, list) and value and all(isinstance(v, str) for v in value):
        return list(value)
    return None


def _one_of(value: Any, wants: list[str]) -> bool:
    """The profile's comparison: trimmed and without regard to case; absent or null reads as ""."""
    if value is None:
        value = ""
    if not isinstance(value, str):
        return False
    return _fold(value) in {_fold(w) for w in wants}


def _subset_refusal(pattern: str) -> str | None:
    """Why a pattern falls outside the regex subset both engines share, or None. The leading inline
    flags ``(?i)`` and ``(?m)`` are allowed (Python reads them as written); every other ``(?``
    construct but a non-capturing group and a lookahead is refused: lookbehind, a named group, another
    flag, a flag past the start."""
    lead = _LEADING_FLAGS.match(pattern)
    i = lead.end() if lead else 0
    in_class = False
    while i < len(pattern):
        ch = pattern[i]
        if ch == "\\":
            i += 2
            continue
        if in_class:
            in_class = ch != "]"
        elif ch == "[":
            in_class = True
            if pattern[i + 1 : i + 2] == "]":
                i += 1  # a "]" first in a class is a literal to Python
        elif ch == "(" and pattern[i + 1 : i + 2] == "?":
            nxt = pattern[i + 2 : i + 4]
            if nxt[:1] in (":", "=", "!"):
                pass
            elif nxt in ("<=", "<!"):
                return "pattern refused: lookbehind is outside the shared regex subset"
            elif nxt[:1] in ("P", "<"):
                return "pattern refused: a named group is outside the shared regex subset"
            else:
                return "pattern refused: the only inline flags are a leading (?i) or (?m)"
        i += 1
    return None


def _pattern(pattern: Any) -> tuple[re.Pattern[str] | None, str | None]:
    """The compiled pattern, or why it is refused."""
    if not isinstance(pattern, str) or not pattern:
        return None, "pattern refused: matches takes a non-empty string"
    if len(pattern) > PATTERN_CAP:
        return None, f"pattern refused: longer than {PATTERN_CAP} characters"
    if pattern in _COMPILED:
        return _COMPILED[pattern], None
    refusal = _subset_refusal(pattern)
    if refusal:
        return None, refusal
    try:
        compiled = re.compile(pattern)
    except re.error as exc:
        return None, f"pattern refused by the engine: {exc}"
    if len(_COMPILED) >= _COMPILED_CAP:
        _COMPILED.clear()
    _COMPILED[pattern] = compiled
    return compiled, None


def _why_not(rule: Any, fields: Mapping[str, Mapping[str, str]]) -> str | None:
    """Why ``rule`` cannot be applied, or None when it can."""
    if not isinstance(rule, Mapping):
        return "a rule must be an object"
    for key in ("rule", "where", "require"):
        if key not in rule:
            return f"missing {key}: a rule needs rule, where and require"
    if not isinstance(rule["rule"], str):
        return "rule must be a string (the Charter's sentence)"
    where, require = rule["where"], rule["require"]
    if not isinstance(where, Mapping):
        return "where must be an object"
    extra = sorted(str(k) for k in where if k not in _WHERE_KEYS)
    if extra:
        return f"where takes type, supertype and subtype, not {', '.join(extra)}"
    if "type" not in where:
        return "where needs a type"
    for key in _WHERE_KEYS:
        if key in where and _strings(where[key]) is None:
            return f"where.{key} must be a string or a non-empty list of strings"
    types = [_fold(t) for t in _strings(where["type"]) or []]
    for t in types:
        if t not in fields:
            return f"unknown type: where.type names {t!r}, which the pinned schema does not name"
    if not isinstance(require, Mapping):
        return "require must be an object"
    if not isinstance(require.get("field"), str) or not require["field"]:
        return "require needs a field (a string)"
    found = [p for p in PREDICATES if p in require]
    extra = sorted(str(k) for k in require if k != "field" and k not in PREDICATES)
    if not found:
        outside = f": {', '.join(extra)}" if extra else ": none given"
        return f"a predicate outside the four of present, matches, links_min and one_of{outside}"
    if len(found) > 1:
        return f"exactly one predicate, not {len(found)} ({', '.join(found)})"
    if extra:
        return f"require holds {', '.join(extra)}, outside field and the four predicates"
    name, predicate = require["field"], found[0]
    arg = require[predicate]
    extension = name.startswith(EXTENSION_PREFIXES)
    if not extension:
        for t in types:
            if name not in fields[t]:
                return f"{name!r} is not a field of {t} and not an extension key"
    if predicate == "present" and arg is not True:
        return "present takes true only"
    if predicate == "matches":
        return _pattern(arg)[1]
    if predicate == "links_min":
        if isinstance(arg, bool) or not isinstance(arg, int) or arg < 0:
            return "links_min takes a whole number, 0 or more"
        if not extension:
            for t in types:
                if fields[t][name] not in _LINK_KINDS:
                    return f"links_min reads a link field; {name} on {t} is {fields[t][name]}"
    if predicate == "one_of" and _strings(arg) is None:
        return "one_of takes a non-empty list of strings"
    return None


def _scoped(where: Mapping[str, Any], kind: str, body: Mapping[str, Any]) -> bool:
    if not _one_of(kind, _strings(where["type"]) or []):
        return False
    return all(_one_of(body.get(key), _strings(where[key]) or []) for key in ("supertype", "subtype") if key in where)


def _holds(require: Mapping[str, Any], body: Mapping[str, Any]) -> bool:
    value = body.get(require["field"])
    if "present" in require:
        if value is None:
            return False
        if isinstance(value, str):
            return value.strip(_WHITE_SPACE) != ""
        return not (isinstance(value, list) and not value)
    if "matches" in require:
        compiled = _pattern(require["matches"])[0]
        return isinstance(value, str) and compiled is not None and compiled.search(value) is not None
    if "links_min" in require:
        if isinstance(value, list):
            count = sum(1 for v in value if isinstance(v, str) and v)
        else:
            count = 1 if isinstance(value, str) and value else 0
        return count >= int(require["links_min"])
    return _one_of(value, _strings(require["one_of"]) or [])


def _element(element: Mapping[str, Any] | FolderElement) -> tuple[str, Mapping[str, Any], dict[str, Any]]:
    """(type, body, ref) for a body or a ``FolderElement`` (whose type may come from its directory)."""
    body: Mapping[str, Any]
    kind: Any
    eid: Any
    if isinstance(element, FolderElement):
        kind, body, eid = element.type, element.body, element.id
    else:
        body = element
        kind, eid = body.get("type"), body.get("id")
    name = body.get("name")
    typed = kind if isinstance(kind, str) else ""
    return typed, body, {"type": typed, "id": eid, "name": name if isinstance(name, str) else ""}


def apply_checks(
    rules: list[Any],
    elements: Iterable[Mapping[str, Any] | FolderElement],
    *,
    fields: Mapping[str, Mapping[str, str]] | None = None,
) -> list[CheckRow]:
    """Apply ``x_checks_rules`` (``rules``, the list as the Charter carries it) to ``elements`` (bodies
    with a ``type``, or ``FolderElement`` objects), in the view the caller holds. One ``CheckRow`` per rule,
    in order; a rule that cannot be applied comes back ``not_checked`` with why. ``fields`` is type ->
    {field: kind}, the shape of ``FIELD_KINDS`` (the pinned schema's, the default). Reads only: the
    list and the bodies are left as they are. Raises ``TypeError`` when ``rules`` is not a list (the
    profile's slot is a list; the doctor reports that case on the Charter)."""
    if not isinstance(rules, list):
        raise TypeError(f"{CHECKS_FIELD} must be a list, not {type(rules).__name__}")
    known = FIELD_KINDS if fields is None else fields
    held = [_element(el) for el in elements]
    rows: list[CheckRow] = []
    for index, rule in enumerate(rules):
        sentence = rule.get("rule") if isinstance(rule, Mapping) else None
        sentence = sentence if isinstance(sentence, str) else None
        require = rule.get("require") if isinstance(rule, Mapping) else None
        name = require.get("field") if isinstance(require, Mapping) else None
        name = name if isinstance(name, str) else None
        why = _why_not(rule, known)
        if why is not None:
            rows.append(CheckRow(index, sentence, name, not_checked=why))
            continue
        scoped = [(body, ref) for kind, body, ref in held if _scoped(rule["where"], kind, body)]
        short = [dict(ref) for body, ref in scoped if not _holds(rule["require"], body)]
        rows.append(CheckRow(index, sentence, name, scoped=len(scoped), short=short))
    return rows

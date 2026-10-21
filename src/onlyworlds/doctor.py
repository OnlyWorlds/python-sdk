"""The doctor: a read-only check over a world, from a folder or through the API.

It reports what a keeper should look at, each finding with the element and the reason,
and it never writes: no file, no API write, no fix. Two doors, one walk:

::

    python -m onlyworlds.doctor PATH/TO/WORLD-FOLDER [--json] [--days N] [--changes N]
    python -m onlyworlds.doctor --api [--json] [--days N] [--changes N]

The API door reads its key and PIN from ``OW_API_KEY`` and ``OW_API_PIN``, lists every
type in pages of 1,000 and walks the change feed from the start.

The flags (the first list):

1. a link to an element that is not there;
2. a Title whose holders changed with no dated Relation;
3. an Event ending before it starts;
4. an element with no links in or out;
5. two elements whose names collide after folding (NFKC, case-folded, whitespace and
   punctuation collapsed), within one type and across types, reported apart;
6. a stub never filled, two readings: (6a) a known-of stub (``known_of: true``) older
   than N days, and (6b) an element with no text in any of its type's text fields;
7. a message unread by its addressee after N days;
8. a charter (a Law with supertype Charter) untouched after N changes;

and two from the file side, on the folder door only: (9) a ``format_version`` older than
this package's ``FORMAT_VERSION``; (10) an ``api_key`` in ``world.json``'s ``api`` block
when ``world.json`` is tracked by git.

A flag the walk cannot evaluate is reported in ``not_run`` with its reason, never as clean,
and every flag that ran says how much it could compare (``compared: {n, of}``): a clean
count over nothing compared is not a pass. A known-of stub's absent fields are unknown,
not empty (folder spec §4.4), so a stub is never counted as linkless or textless.

What the feed can show was measured, not assumed: keel serves each element's upsert from
its row at its latest ``change_seq`` (keel ``core/changes.py``, spec §8: "every live element
is present at its latest change_seq"), so a walk carries current bodies only and flag 2
reports ``not_run`` unless the walk holds two versions of one element. No read mark exists
in the folder format, the API or this package, so flag 7 never runs.

From the command line: exit 0 clean, 1 findings, 2 nothing could be read.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import io
import json
import os
import subprocess
import sys
import unicodedata
from collections import defaultdict
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from itertools import pairwise
from pathlib import Path
from typing import Any, Protocol

from ._schema import ELEMENT_TYPES, FIELD_KINDS, GENERIC_PAIRS
from .errors import ApiError
from .folder import FORMAT_VERSION, WORLD_FILE, Folder, is_known_of, read_folder
from .http import API_BASE, Client

__all__ = ["FLAGS", "Reader", "Report", "doctor_api", "doctor_folder", "fold_name", "main", "render_prose"]

#: Flag id -> what it looks for. The ids are strings because flag 6 has two readings.
FLAGS: dict[str, str] = {
    "1": "A link to an element that is not there",
    "2": "A Title whose holders changed with no dated Relation",
    "3": "An Event ending before it starts",
    "4": "An element with no links in or out",
    "5": "Two elements whose names collide after folding",
    "6a": "A known-of stub never filled",
    "6b": "An element with no text in any of its type's text fields",
    "7": "A message unread by its addressee",
    "8": "A charter untouched after N changes",
    "9": "A format_version older than this package's",
    "10": "An api_key in a tracked world.json",
}

#: What each flag's ``compared`` counts, for the prose report.
_UNITS: dict[str, str] = {
    "1": "link values",
    "2": "Titles with two versions in the feed",
    "3": "Events with both dates",
    "4": "elements",
    "5": "named elements",
    "6a": "known-of stubs with an updated_at",
    "6b": "whole elements",
    "8": "charters found in the feed",
    "9": "world.json format_version",
    "10": "world.json",
}

#: Fields that hold no prose even when the schema types them text.
_NOT_PROSE = frozenset({"name", "supertype", "subtype", "image_url"}) | {
    type_key for pairs in GENERIC_PAIRS.values() for type_key, _ in pairs
}
#: Atlas-written pins and markers spell two links ``map_id`` / ``zone_id`` (spec §5; ``push``).
_LEGACY_LINK_SPELLINGS: dict[str, dict[str, str]] = {
    "pin": {"map_id": "map", "zone_id": "zone"},
    "marker": {"map_id": "map", "zone_id": "zone"},
}
#: A Relation of these supertypes, naming a Title in ``titles``, dates a holding.
_HOLDING_SUPERTYPES = frozenset({"tenure", "membership"})
_PAGE = 1000
_GIT_TIMEOUT = 30.0


class Reader(Protocol):
    """The four reads the API door makes; ``Client`` is one. Nothing here writes."""

    def me(self) -> dict[str, Any]: ...

    def get_world(self) -> dict[str, Any]: ...

    def list_page(
        self, element_type: str, *, limit: int | None = None, cursor: str | None = None
    ) -> dict[str, Any]: ...

    def changes(self, *, since: str | None = None, limit: int | None = None) -> dict[str, Any]: ...


@dataclass
class Report:
    """One run. ``as_dict`` is the JSON report, keys in this order."""

    world: dict[str, Any]
    ran: list[str] = field(default_factory=list)
    not_run: list[dict[str, str]] = field(default_factory=list)
    findings: list[dict[str, Any]] = field(default_factory=list)
    compared: dict[str, dict[str, int]] = field(default_factory=dict)
    #: always 0: the doctor never writes
    written: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "world": self.world,
            "ran": self.ran,
            "not_run": self.not_run,
            "findings": self.findings,
            "compared": self.compared,
            "written": self.written,
        }

    @property
    def exit_code(self) -> int:
        return 1 if self.findings else 0


@dataclass(frozen=True)
class _El:
    type: str
    id: str
    body: Mapping[str, Any]

    @property
    def name(self) -> str:
        name = self.body.get("name")
        return name if isinstance(name, str) else ""

    @property
    def known_of(self) -> bool:
        return is_known_of(self.body)

    def ref(self) -> dict[str, str]:
        return {"type": self.type, "id": self.id, "name": self.name}


class _Run:
    """Collects one report in flag order, whatever order the checks run in."""

    def __init__(self, world: dict[str, Any]):
        self.report = Report(world=world)
        self._ran: set[str] = set()
        self._not_run: dict[str, str] = {}
        self._findings: dict[str, list[dict[str, Any]]] = defaultdict(list)

    def ran(self, flag: str, n: int | None = None, of: int | None = None) -> None:
        self._ran.add(flag)
        if n is not None and of is not None:
            self.report.compared[flag] = {"n": n, "of": of}

    def skip(self, flag: str, why: str) -> None:
        self._not_run[flag] = why

    def find(self, flag: str, element: _El | None, reason: str, evidence: Mapping[str, Any]) -> None:
        self._findings[flag].append(
            {"flag": flag, "element": element.ref() if element else None, "reason": reason, "evidence": dict(evidence)}
        )

    def done(self) -> Report:
        r = self.report
        r.ran = [f for f in FLAGS if f in self._ran]
        r.not_run = [{"flag": f, "why": self._not_run[f]} for f in FLAGS if f in self._not_run]
        r.findings = [x for f in FLAGS for x in self._findings.get(f, [])]
        r.compared = {f: r.compared[f] for f in FLAGS if f in r.compared}
        return r


# ---------------------------------------------------------------------------
# Reading a body
# ---------------------------------------------------------------------------


def _has_value(value: Any) -> bool:
    return not (value is None or value == "" or value == [])


def _links(el: _El) -> Iterator[tuple[str, Any]]:
    """Every link value on ``el`` as (field, value), one per id in a multi link. A value that is
    not a string id is yielded too: it counts as a link it could not compare."""
    kinds = FIELD_KINDS.get(el.type, {})
    renames = _LEGACY_LINK_SPELLINGS.get(el.type, {})
    for key, value in el.body.items():
        name = renames.get(key, key)
        if name != key and name in el.body:
            continue  # the wire's spelling wins over Atlas's
        kind = kinds.get(name)
        if kind == "single_link" and _has_value(value):
            yield name, value
        elif kind == "multi_link" and _has_value(value):
            if isinstance(value, list):
                for item in value:
                    if _has_value(item):
                        yield name, item
            else:
                yield name, value


def _text_fields(element_type: str) -> list[str]:
    """The type's prose fields from the schema: every ``text`` field but name, supertype, subtype,
    image_url and a generic link's type key. Never ``description`` alone: a Law's text is in
    ``declaration`` and ``purpose``, a Narrative's in ``story``, a Title's in ``authority``."""
    return [f for f, kind in FIELD_KINDS.get(element_type, {}).items() if kind == "text" and f not in _NOT_PROSE]


def _int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _time(value: Any) -> _dt.datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        t = _dt.datetime.fromisoformat(value)
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=_dt.UTC)


def _folded(value: Any) -> str:
    return value.strip().casefold() if isinstance(value, str) else ""


def fold_name(name: str) -> str:
    """A name as flag 5 compares it: NFKC, case-folded, every run of whitespace and punctuation
    one space, trimmed. ``"Kael, Inspector"`` and ``"kael  inspector"`` fold alike."""
    out: list[str] = []
    gap = False
    for ch in unicodedata.normalize("NFKC", name).casefold():
        if ch.isspace() or unicodedata.category(ch).startswith("P"):
            gap = True
            continue
        if gap and out:
            out.append(" ")
        gap = False
        out.append(ch)
    return "".join(out)


# ---------------------------------------------------------------------------
# The walk: flags that read the elements alone
# ---------------------------------------------------------------------------


def _walk(run: _Run, els: list[_El], *, days: int, now: _dt.datetime, whole_view: bool = True) -> None:
    """The flags read from the elements alone (1, 3, 4, 5, 6a, 6b). ``whole_view`` False: the
    reader cannot see every element (a guest), so flag 1 does not run."""
    ids = {el.id for el in els}

    # 1. A link to an element that is not there.
    if whole_view:
        values = compared = 0
        for el in els:
            for fname, value in _links(el):
                values += 1
                if not isinstance(value, str):
                    continue
                compared += 1
                if value not in ids:
                    run.find(
                        "1",
                        el,
                        f"its {fname} names an id that is not in the world",
                        {"field": fname, "missing_id": value},
                    )
        run.ran("1", compared, values)
    else:
        run.skip("1", "a guest key cannot see every element: a link to one it cannot see is not a deletion")

    # 3. An Event ending before it starts.
    events = [el for el in els if el.type == "event"]
    dated = 0
    for el in events:
        start, end = _int(el.body.get("start_date")), _int(el.body.get("end_date"))
        if start is None or end is None:
            continue
        dated += 1
        if end < start:
            run.find("3", el, "it ends before it starts", {"start_date": start, "end_date": end})
    run.ran("3", dated, len(events))

    # 4. An element with no links in or out.
    linked_to: set[str] = set()
    links_out: set[str] = set()
    for el in els:
        for _, value in _links(el):
            links_out.add(el.id)
            if isinstance(value, str):
                linked_to.add(value)
    known = 0
    for el in els:
        if el.id in linked_to or el.id in links_out:
            known += 1
            continue
        if el.known_of:
            continue  # a stub's absent links are unknown, not absent
        known += 1
        run.find("4", el, "no link field is set on it and no element links to it", {})
    run.ran("4", known, len(els))

    # 5. Two elements whose names collide after folding.
    groups: dict[str, list[_El]] = defaultdict(list)
    for el in els:
        key = fold_name(el.name)
        if key:
            groups[key].append(el)
    named = sum(len(g) for g in groups.values())
    for key, group in groups.items():
        if len(group) < 2:
            continue
        by_type: dict[str, list[_El]] = defaultdict(list)
        for el in sorted(group, key=lambda e: (ELEMENT_TYPES.index(e.type) if e.type in ELEMENT_TYPES else 99, e.id)):
            by_type[el.type].append(el)
        for same in by_type.values():
            if len(same) > 1:
                run.find(
                    "5",
                    same[0],
                    f"{len(same)} elements of one type share this name once folded",
                    {"scope": "same type", "folded": key, "with": [e.ref() for e in same[1:]]},
                )
        if len(by_type) > 1:
            firsts = [g[0] for g in by_type.values()]
            others = [e.ref() for g in by_type.values() for e in g if e is not firsts[0]]
            run.find(
                "5",
                firsts[0],
                f"elements of {len(by_type)} types share this name once folded",
                {"scope": "across types", "folded": key, "with": others},
            )
    run.ran("5", named, len(els))

    # 6a. A known-of stub older than `days`.
    stubs = [el for el in els if el.known_of]
    timed = 0
    horizon = now - _dt.timedelta(days=days)
    for el in stubs:
        updated = _time(el.body.get("updated_at"))
        if updated is None:
            continue
        timed += 1
        if updated < horizon:
            run.find(
                "6a",
                el,
                f"a known-of stub not updated in {days} days",
                {"updated_at": el.body.get("updated_at"), "days": days},
            )
    run.ran("6a", timed, len(stubs))

    # 6b. No text in any of the type's text fields.
    whole = 0
    for el in els:
        if el.known_of:
            continue  # its absent fields are unknown, not empty: 6a's reading
        whole += 1
        fields = _text_fields(el.type)
        if fields and not any(isinstance(el.body.get(f), str) and el.body[f].strip() for f in fields):
            run.find("6b", el, f"no text in any of its {len(fields)} text fields", {"fields": fields})
    run.ran("6b", whole, len(els))


# ---------------------------------------------------------------------------
# The folder door
# ---------------------------------------------------------------------------


def _version_tuple(value: Any) -> tuple[int, ...] | None:
    if not isinstance(value, str):
        return None
    try:
        return tuple(int(part) for part in value.split("."))
    except ValueError:
        return None


def _git(root: Path, *args: str) -> bool:
    """True when a read-only git command succeeds in ``root``. Raises FileNotFoundError without git."""
    done = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        timeout=_GIT_TIMEOUT,
        check=False,
        stdin=subprocess.DEVNULL,
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},  # not even an index refresh
    )
    return done.returncode == 0


def _file_side(run: _Run, folder: Folder) -> None:
    world = folder.world
    if world is None:
        run.skip("9", "world.json could not be read")
        run.skip("10", "world.json could not be read")
        return

    # 9. A format_version older than this package's.
    declared = world.get("format_version")
    mine, theirs = _version_tuple(FORMAT_VERSION), _version_tuple(declared)
    if mine is not None and theirs is not None:
        run.ran("9", 1, 1)
        if theirs < mine:
            run.find(
                "9",
                None,
                f"world.json declares format_version {declared}, older than {FORMAT_VERSION}",
                {"file": WORLD_FILE, "format_version": declared, "package": FORMAT_VERSION},
            )
    else:
        run.ran("9", 0, 1)

    # 10. An api_key in a tracked world.json. The key itself is never printed.
    api = world.get("api")
    has_key = isinstance(api, Mapping) and _has_value(api.get("api_key"))
    try:
        in_repo = (folder.root / ".git").exists() or _git(folder.root, "rev-parse", "--is-inside-work-tree")
        tracked = in_repo and _git(folder.root, "ls-files", "--error-unmatch", WORLD_FILE)
    except (OSError, subprocess.SubprocessError) as exc:
        if not (folder.root / ".git").exists():
            run.ran("10", 1, 1)  # no repository and no git: nothing tracks world.json
            return
        run.skip("10", f"the folder is a git repository, but git could not be run ({type(exc).__name__})")
        return
    run.ran("10", 1, 1)
    if has_key and tracked:
        run.find(
            "10",
            None,
            "world.json holds an api_key and git tracks world.json, so the key is in the repository",
            {"file": WORLD_FILE, "key": "api.api_key", "tracked": True},
        )


def doctor_folder(folder: Folder, *, days: int = 14, changes: int = 50, now: _dt.datetime | None = None) -> Report:
    """Check a read folder (``read_folder``). Reads only; ``changes`` is unused here (no feed in a
    folder) and kept so both doors take the same arguments."""
    world = folder.world or {}
    run = _Run({"id": world.get("id"), "name": world.get("name"), "door": "folder"})
    els = [_El(fe.type, eid, fe.body) for eid, fe in folder.all_elements().items()]
    _walk(run, els, days=days, now=now or _dt.datetime.now(_dt.UTC))
    run.skip("2", "needs the feed's history of Title.holders")
    run.skip("7", "read marks are not in the folder")
    run.skip("8", "no feed in a folder")
    _file_side(run, folder)
    return run.done()


# ---------------------------------------------------------------------------
# The API door
# ---------------------------------------------------------------------------


def _list_all(client: Reader, element_type: str) -> Iterator[dict[str, Any]]:
    cursor: str | None = None
    while True:
        page = client.list_page(element_type, limit=_PAGE, cursor=cursor)
        yield from (b for b in page.get("data", []) if isinstance(b, dict))
        if not page.get("has_more"):
            return
        nxt = page.get("next_cursor")
        if not isinstance(nxt, str) or not nxt or nxt == cursor:
            raise ValueError(f"{element_type}: has_more without a new next_cursor")
        cursor = nxt


def _feed(client: Reader) -> tuple[list[dict[str, Any]], Any]:
    """The whole feed from the start, in its order, and its ``head``."""
    rows: list[dict[str, Any]] = []
    cursor: str | None = None
    while True:
        page = client.changes(since=cursor, limit=_PAGE)
        rows.extend(r for r in page.get("changes", []) if isinstance(r, dict))
        head = page.get("head")
        if not page.get("has_more"):
            return rows, head
        nxt = page.get("cursor")
        if not isinstance(nxt, str) or nxt == cursor:
            raise ValueError("/changes said has_more but gave no new cursor")
        cursor = nxt


def _holders(body: Any) -> frozenset[str]:
    value = body.get("holders") if isinstance(body, Mapping) else None
    return frozenset(v for v in value if isinstance(v, str)) if isinstance(value, list) else frozenset()


def _title_history(run: _Run, els: list[_El], rows: list[dict[str, Any]]) -> None:
    """Flag 2, from the feed: a Title whose holders differ between two of its upserts."""
    upserts = [r for r in rows if r.get("op") == "upsert" and isinstance(r.get("id"), str)]
    distinct = {r["id"] for r in upserts}
    if len(distinct) == len(upserts):
        run.skip(
            "2",
            "the feed carries current bodies only; a holders change cannot be seen "
            f"(measured: {len(upserts)} upserts for {len(distinct)} ids)",
        )
        return
    titles = {el.id: el for el in els if el.type == "title"}
    versions: dict[str, list[frozenset[str]]] = defaultdict(list)
    for r in upserts:
        if r["id"] in titles:
            versions[r["id"]].append(_holders(r.get("element")))
    dated: set[str] = set()
    for el in els:
        if el.type != "relation" or _folded(el.body.get("supertype")) not in _HOLDING_SUPERTYPES:
            continue
        if _int(el.body.get("start_date")) is None and _int(el.body.get("end_date")) is None:
            continue
        named = el.body.get("titles")
        if isinstance(named, list):
            dated.update(v for v in named if isinstance(v, str))
    seen = 0
    for tid, held in versions.items():
        if len(held) < 2:
            continue
        seen += 1
        moves = [(a, b) for a, b in pairwise(held) if a != b]
        if moves and tid not in dated:
            before, after = moves[-1]
            run.find(
                "2",
                titles[tid],
                "its holders changed and no dated Tenure or Membership Relation names it",
                {"holders_before": sorted(before), "holders_after": sorted(after), "versions": len(held)},
            )
    run.ran("2", seen, len(titles))


def _charters(run: _Run, els: list[_El], rows: list[dict[str, Any]], head: Any, *, changes: int) -> None:
    """Flag 8: a charter with more than ``changes`` feed rows after its own."""
    charters = [el for el in els if el.type == "law" and _folded(el.body.get("supertype")) == "charter"]
    if not charters:
        run.ran("8", 0, 0)
        run.find("8", None, "no charter: no Law with supertype Charter", {})
        return
    position = {r["id"]: i for i, r in enumerate(rows) if r.get("op") == "upsert" and isinstance(r.get("id"), str)}
    found = 0
    for el in charters:
        at = position.get(el.id)
        if at is None:
            continue
        found += 1
        after = len(rows) - at - 1
        if after > changes:
            run.find(
                "8",
                el,
                f"{after} changes in the feed since this charter last changed (more than {changes})",
                {"changes_after": after, "limit": changes, "change_seq": el.body.get("change_seq"), "head": head},
            )
    run.ran("8", found, len(charters))


def doctor_api(client: Reader, *, days: int = 14, changes: int = 50, now: _dt.datetime | None = None) -> Report:
    """Check the key's world through the API: ``me``, ``get_world``, every type's list and the
    feed. Reads only. A failure to read the world or a list raises (``ApiError``,
    ``ConnectionError``, ``ValueError``); a feed that cannot be read makes flags 2 and 8 ``not_run``."""
    world = client.get_world()
    try:
        role = client.me().get("role")
    except (ApiError, ValueError):
        role = None
    run = _Run({"id": world.get("id"), "name": world.get("name"), "door": "api"})
    els: list[_El] = []
    for t in ELEMENT_TYPES:
        els.extend(_El(t, b["id"], b) for b in _list_all(client, t) if isinstance(b.get("id"), str))
    _walk(run, els, days=days, now=now or _dt.datetime.now(_dt.UTC), whole_view=role != "guest")
    try:
        rows, head = _feed(client)
    except (ApiError, ConnectionError, ValueError) as exc:
        why = f"the feed could not be read ({exc})"
        run.skip("2", why)
        run.skip("8", why)
    else:
        _title_history(run, els, rows)
        _charters(run, els, rows, head, changes=changes)
    run.skip("7", "read marks are not readable through the API")
    run.skip("9", "a file-side check: the API door reads no world.json")
    run.skip("10", "a file-side check: the API door reads no world.json")
    return run.done()


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------


def _say(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def _lines(report: Report) -> Iterable[str]:
    w = report.world
    yield f"The doctor on {w.get('name') or '(no name)'} ({w.get('id') or 'no id'}), {w.get('door')} door"
    yield ""
    yield (
        f"{len(report.findings)} things to look at, {len(report.ran)} flags ran, "
        f"{len(report.not_run)} could not run, {report.written} things written"
    )
    for flag in FLAGS:
        found = [x for x in report.findings if x["flag"] == flag]
        if not found:
            continue
        yield ""
        yield f"{flag}. {FLAGS[flag]} ({len(found)})"
        for x in found:
            el = x["element"]
            who = f"{el['type']} {el['name'] or '(no name)'} ({el['id']})" if el else "the world"
            yield f"  - {who}: {x['reason']}"
            if x["evidence"]:
                yield "    " + "; ".join(f"{k}: {_say(v)}" for k, v in x["evidence"].items())
    yield ""
    yield "What was checked"
    for flag in report.ran:
        c = report.compared.get(flag)
        counted = f": {c['n']} of {c['of']} {_UNITS.get(flag, '')}".rstrip() if c else ""
        yield f"  {flag}. {FLAGS[flag]}{counted}"
    if report.not_run:
        yield ""
        yield "What could not be checked, and why"
        for item in report.not_run:
            yield f"  {item['flag']}. {FLAGS[item['flag']]}: {item['why']}"


def render_prose(report: Report) -> str:
    """The report a person reads: counts first, the findings by flag, what was checked, what could not be."""
    return "\n".join(_lines(report)) + "\n"


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="python -m onlyworlds.doctor", description=(__doc__ or "").splitlines()[0])
    ap.add_argument("folder", nargs="?", type=Path, help="a world folder (holds world.json and elements/)")
    ap.add_argument("--api", action="store_true", help="check the world of the key in OW_API_KEY (PIN: OW_API_PIN)")
    ap.add_argument("--base-url", default=API_BASE, help=f"the API to read (default {API_BASE})")
    ap.add_argument("--json", action="store_true", help="print the JSON report instead of the prose one")
    ap.add_argument("--days", type=int, default=14, help="flag 6a: a stub older than this many days (default 14)")
    ap.add_argument("--changes", type=int, default=50, help="flag 8: more changes than this (default 50)")
    args = ap.parse_args(argv)
    if (args.folder is None) == (not args.api):
        print("give a world folder or --api, one of the two", file=sys.stderr)
        return 2

    if args.api:
        key = os.environ.get("OW_API_KEY")
        if not key:
            print(
                "--api reads the key from OW_API_KEY (and the PIN from OW_API_PIN); OW_API_KEY is not set",
                file=sys.stderr,
            )
            return 2
        client = Client(key, os.environ.get("OW_API_PIN") or None, base_url=args.base_url)
        try:
            report = doctor_api(client, days=args.days, changes=args.changes)
        except (ApiError, ConnectionError, ValueError) as exc:
            print(f"nothing could be read: {exc}", file=sys.stderr)
            return 2
    else:
        if not args.folder.is_dir():
            print(f"{args.folder}: not a directory", file=sys.stderr)
            return 2
        folder = read_folder(args.folder)
        if folder.world is None and not folder.all_elements():
            print(f"{args.folder}: nothing could be read (no world.json, no elements)", file=sys.stderr)
            return 2
        report = doctor_folder(folder, days=args.days, changes=args.changes)

    if args.json:
        print(json.dumps(report.as_dict(), ensure_ascii=True, indent=2))
    else:
        sys.stdout.write(render_prose(report))
    return report.exit_code


if __name__ == "__main__":
    sys.exit(main())

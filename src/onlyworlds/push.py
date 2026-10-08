"""Push a world folder's edits to the wire: changed fields only, against a baseline export.

The loop (from an earlier script, ``push_folder.py``; this is its package-shaped half):

1. ``baseline`` = a folder exported from the wire BEFORE the edits; ``folder`` = the edited one.
2. Field-level diff per element; only fields that differ are sent (PATCH semantics:
   an omitted field is untouched).
3. PATCH with retry (429 / 5xx / no response), honoring ``Retry-After``.
4. Every 200 response is read back against what was sent: a field the server
   stored differently is a MISMATCH, not a success.
5. Every attempt is appended to a jsonl log; a rerun skips a patch that already
   landed (same element, same fields, same values).

What landed is proven by a FRESH export compared with the folder (``verify_level``),
never by the diff that was sent.

Never sent, whatever the diff says: ``id``; the wire's server-managed fields
(``world``, ``type``, ``created_at``, ``updated_at``, ``change_seq``: the npm SDK's
``sanitizePayload`` list; keel ignores ``world`` and 422s the rest); ``created_by``, which keel drops
from a write but still answers with a fresh ``change_seq`` (a folder without the key
would otherwise rewrite every member-made element on every run); Atlas's in-file sync stamps
``local_updated_at`` / ``server_updated_at`` and ``image_media_id`` (spec §5, "not
schema fields: strip them"); Atlas's local-only extension fields (``ATLAS_LOCAL_ONLY_FIELDS``
in Atlas's ``src/core/constants.ts``). Atlas's other ``atlas_*`` fields
(colour, opacity, label, shape, calendar) travel on purpose and are sent like any extension.
Atlas-written pins and markers spell their links ``map_id`` / ``zone_id``; the diff reads
them as the wire's ``map`` / ``zone`` (spec §5).

A generic link's two halves (Pin's ``element_type`` / ``element_id``) go together when
either changed: keel refuses a write that sets one half. The run stops at the first
answer that refuses the key itself (``stops_run``): a wrong PIN repeated across a push
locks the key for every tool that uses it.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import threading
from collections import Counter
from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ._schema import FIELD_KINDS, GENERIC_PAIRS
from .errors import ApiError
from .folder import Folder, FolderElement, read_folder
from .http import Client, check_kinds

__all__ = [
    "NOT_SENT",
    "Patch",
    "PushPlan",
    "PushResult",
    "plan_push",
    "push",
    "stops_run",
    "verify_level",
    "wire_view",
]

NOT_SENT = frozenset(
    {
        "id",
        "world",
        "type",
        "created_at",
        "updated_at",
        "change_seq",
        "created_by",
        "local_updated_at",
        "server_updated_at",
        "image_media_id",
        "atlas_richtext_json",
        "atlas_aliases",
        "atlas_dismissed_suggestions",
        "atlas_page_blocks",
        "atlas_page_refs",
        "atlas_page_intent",
        "atlas_page_theme",
        "atlas_page_pub",
    }
)
_LEGACY_LINK_SPELLINGS: Mapping[str, Mapping[str, str]] = {
    "pin": {"map_id": "map", "zone_id": "zone"},
    "marker": {"map_id": "map", "zone_id": "zone"},
}


def wire_view(element: FolderElement) -> dict[str, Any]:
    """The element's writable fields as the wire names them. Never mutates the body."""
    renames = _LEGACY_LINK_SPELLINGS.get(element.type, {})
    out: dict[str, Any] = {}
    for key, value in element.body.items():
        if key in NOT_SENT:
            continue
        bare = renames.get(key)
        if bare is not None:
            if bare in element.body:
                continue  # both spellings present: the bare one is the spec's
            out[bare] = value
        else:
            out[key] = value
    return out


def _same(a: Any, b: Any) -> bool:
    """JSON equality: bool is not a number, key order inside objects is not content."""
    if isinstance(a, bool) or isinstance(b, bool):
        return type(a) is type(b) and a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return a == b
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_same(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_same(x, y) for x, y in zip(a, b, strict=True))
    return type(a) is type(b) and a == b


def _equal_on_wire(etype: str, key: str, a: Any, b: Any) -> bool:
    """``_same``, plus the ruling ``string-empty-is-unset``: for a schema TEXT field,
    ``""``, ``null`` and absent are one state on the wire. Extension fields get no
    such leniency: there ``""`` and ``null`` are different values."""
    if FIELD_KINDS.get(etype, {}).get(key) == "text" and a in (None, "") and b in (None, ""):
        return True
    return _same(a, b)


def _cleared(etype: str, key: str) -> Any:
    """The wire's one empty shape per kind (api-v2 spec, PATCH semantics): text ``""``,
    multi link ``[]``, single link / integer / anything else ``null``."""
    kind = FIELD_KINDS.get(etype, {}).get(key)
    if kind == "text":
        return ""
    if kind == "multi_link":
        return []
    return None


@dataclass(frozen=True)
class Patch:
    type: str
    id: str
    fields: dict[str, Any]

    @property
    def fingerprint(self) -> str:
        """Identifies this exact patch, so a rerun skips it only if nothing about it changed."""
        canon = json.dumps([self.type, self.id, self.fields], sort_keys=True, ensure_ascii=True)
        return hashlib.sha256(canon.encode("ascii")).hexdigest()


@dataclass
class PushPlan:
    patches: list[Patch]
    #: ids present only in the baseline (deleted in the folder?) — a PATCH loop cannot express these
    only_in_baseline: list[str] = field(default_factory=list)
    #: ids present only in the folder (created?) — a PATCH loop cannot express these
    only_in_folder: list[str] = field(default_factory=list)
    #: ids whose type differs between baseline and folder — type is not writable
    type_changed: list[str] = field(default_factory=list)

    @property
    def unmatched(self) -> bool:
        return bool(self.only_in_baseline or self.only_in_folder or self.type_changed)

    def field_counts(self) -> Counter[tuple[str, str]]:
        return Counter((p.type, k) for p in self.patches for k in p.fields)


def _elements(x: Folder | str | os.PathLike[str]) -> dict[str, FolderElement]:
    folder = x if isinstance(x, Folder) else read_folder(x)
    return folder.all_elements()


def plan_push(baseline: Folder | str | os.PathLike[str], folder: Folder | str | os.PathLike[str]) -> PushPlan:
    """Field-level diff: for each id in both, the fields whose folder value differs from the baseline.

    A field present in the baseline and absent from the folder is sent as its kind's
    empty shape (PATCH has no "remove"): ``""`` for text, ``[]`` for a multi link,
    ``null`` otherwise, extension fields included (keel keeps a null extension key). Patches
    are sorted by (type, id), fields in the folder's key order.
    """
    base, edited = _elements(baseline), _elements(folder)
    plan = PushPlan(
        patches=[],
        only_in_baseline=sorted(set(base) - set(edited)),
        only_in_folder=sorted(set(edited) - set(base)),
    )
    for eid in sorted(set(base) & set(edited), key=lambda i: (edited[i].type, i)):
        b, f = base[eid], edited[eid]
        if b.type != f.type:
            plan.type_changed.append(eid)
            continue
        old, new = wire_view(b), wire_view(f)
        keys = list(new) + [k for k in old if k not in new]
        changed = {
            k: new[k] if k in new else _cleared(f.type, k)
            for k in keys
            if not _equal_on_wire(f.type, k, new.get(k), old.get(k))
        }
        for pair in GENERIC_PAIRS.get(f.type, ()):
            if any(k in changed for k in pair):
                for k in pair:
                    changed.setdefault(k, new[k] if k in new else _cleared(f.type, k))
        if changed:
            plan.patches.append(Patch(f.type, eid, changed))
    plan.patches.sort(key=lambda p: (p.type, p.id))
    return plan


@dataclass
class PushResult:
    planned: int
    already_done: int
    attempted: int = 0
    ok: int = 0
    failed: list[dict[str, Any]] = field(default_factory=list)
    retries: int = 0
    log_path: Path | None = None
    #: why the run stopped early (``stops_run``); patches it never sent are not logged, so a rerun sends them
    aborted: str | None = None


def stops_run(error: ApiError) -> bool:
    """An answer about the key, not the element: every later patch would get it too.

    401 (``invalid_credentials``, ``key_revoked``), 429 ``rate_limited`` (keel's failed-PIN
    throttle, its only 429), and any 403 but ``not_author``, which is about one element.
    """
    if error.status == 401 or (error.status == 429 and error.code == "rate_limited"):
        return True
    return error.status == 403 and not error.is_not_author


def _load_done(log_path: Path) -> tuple[set[str], set[str]]:
    """(fingerprints that landed, ids that landed under a log line with no fingerprint).

    The second set reads logs written by the original script, which keyed on id alone.
    """
    prints: set[str] = set()
    legacy_ids: set[str] = set()
    if not log_path.is_file():
        return prints, legacy_ids
    with log_path.open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            rec = json.loads(line)
            if rec.get("code") != 200 or rec.get("mismatch"):
                continue
            if "patch_sha256" in rec:
                prints.add(rec["patch_sha256"])
            else:
                legacy_ids.add(rec["id"])
    return prints, legacy_ids


def push(
    baseline: Folder | str | os.PathLike[str],
    folder: Folder | str | os.PathLike[str],
    *,
    client: Client | None = None,
    api_key: str | None = None,
    pin: str | None = None,
    log_path: str | os.PathLike[str],
    workers: int = 4,
    limit: int | None = None,
    dry_run: bool = False,
    allow_unmatched: bool = False,
    on_failure: Callable[[dict[str, Any]], None] | None = None,
) -> PushResult:
    """PATCH the folder's field-level edits against ``baseline``. See the module docstring.

    Give either ``client`` or ``api_key`` (+ ``pin``). Refuses to run when the two
    folders do not hold the same elements (``PushPlan.unmatched``) unless
    ``allow_unmatched``: creations and deletions are not a PATCH loop's to guess.
    ``workers`` defaults to 4 (keel runs at most 6 requests at once per worker
    process and queues beyond that; 4 is the shape it was sized for).
    """
    plan = plan_push(baseline, folder)
    if plan.unmatched and not allow_unmatched:
        raise ValueError(
            f"baseline and folder differ in membership: {len(plan.only_in_baseline)} only in baseline, "
            f"{len(plan.only_in_folder)} only in folder, {len(plan.type_changed)} changed type "
            "(pass allow_unmatched=True to push the rest anyway)"
        )
    log = Path(log_path)
    prints, legacy_ids = _load_done(log)
    todo = [p for p in plan.patches if p.fingerprint not in prints and p.id not in legacy_ids]
    result = PushResult(planned=len(plan.patches), already_done=len(plan.patches) - len(todo), log_path=log)
    work = todo[:limit] if limit is not None else todo
    if dry_run or not work:
        return result
    if client is None:
        if not api_key:
            raise ValueError("push needs a client, or an api_key (+ pin)")
        client = Client(api_key, pin)

    lock = threading.Lock()
    stop = threading.Event()
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8", newline="\n") as fh:

        def one(p: Patch) -> None:
            if stop.is_set():
                return
            try:
                check_kinds(p.type, p.fields)
            except ValueError as exc:
                refused = {"id": p.id, "type": p.type, "code": 0, "fields": sorted(p.fields), "error": str(exc)}
                with lock:
                    result.failed.append(refused)
                    if on_failure:
                        on_failure(refused)
                return
            got = client.send("PATCH", f"{p.type}/{p.id}/", p.fields)
            code = got.response.status if got.response is not None else 0
            mismatch_fields: list[str] = []
            if code == 200 and got.response is not None:
                try:
                    data = got.response.json()
                except ValueError:
                    data = None
                if not isinstance(data, dict):
                    mismatch_fields = ["<response is not an object>"]
                else:
                    mismatch_fields = [k for k, v in p.fields.items() if not _equal_on_wire(p.type, k, data.get(k), v)]
            rec: dict[str, Any] = {
                "at": _dt.datetime.now(_dt.UTC).isoformat(timespec="seconds"),
                "id": p.id,
                "type": p.type,
                "code": code,
                "mismatch": bool(mismatch_fields),
                "mismatch_fields": mismatch_fields,
                "retries": got.retries,
                "retry_reasons": got.reasons,
                "fields": sorted(p.fields),
                "patch_sha256": p.fingerprint,
            }
            if code != 200:
                body = got.response.body[:300].decode("utf-8", "replace") if got.response is not None else ""
                rec["error"] = got.error or body
                if got.response is not None and stops_run(ApiError("PATCH", f"{p.type}/{p.id}/", got.response)):
                    stop.set()
                    with lock:
                        if result.aborted is None:
                            result.aborted = f"{code}: {body[:200]}"
            with lock:
                fh.write(json.dumps(rec, ensure_ascii=True) + "\n")
                fh.flush()
                result.attempted += 1
                result.retries += got.retries
                if code == 200 and not mismatch_fields:
                    result.ok += 1
                else:
                    result.failed.append(rec)
                    if on_failure:
                        on_failure(rec)

        with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
            list(ex.map(one, work))
    return result


def verify_level(fresh_export: Folder | str | os.PathLike[str], folder: Folder | str | os.PathLike[str]) -> PushPlan:
    """Diff a FRESH export (taken after a push) against the folder. An empty plan means level.

    The same diff as ``plan_push``: it is what a push would still have to send.
    """
    return plan_push(fresh_export, folder)

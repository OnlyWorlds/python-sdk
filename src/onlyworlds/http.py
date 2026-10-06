"""The OnlyWorlds v2 API client: an injectable transport, a retry rule, and the element, link, bulk and change calls.

Wire facts this file encodes (keel ``docs/spec/api-v2-spec.md``, and keel's published
OpenAPI document, which ``tests/test_wire.py`` compares the client with):
- base ``https://www.onlyworlds.com/api/v2`` (www, not the bare domain);
- credentials in ``API-Key`` / ``API-Pin`` headers; ``ow_r_`` read keys need no PIN;
- a body never carries ``world`` (the key names the world) or the server-managed
  ``type`` / ``created_at`` / ``updated_at`` / ``change_seq``: the typed calls strip them;
- lists are ``{data, has_more, next_cursor}``, continued with ``?cursor=``;
- ``Idempotency-Key`` on POST and ``/bulk`` replays the first successful answer for 24 h;
- 429 carries ``Retry-After``; on v2 its only 429 is ``rate_limited``, the failed-PIN
  throttle (10 failures lock the key for 15 minutes); under load keel answers 503 ``server_busy`` with
  ``Retry-After: 5`` (keel D71, 2026-09-28).

One difference from the TypeScript SDK, on purpose: this client retries 429, 5xx and
no-response failures itself (``RetryPolicy``; ``attempts=1`` turns it off), except a 429
``rate_limited``, which on keel means a wrong PIN. A retried write stays safe because every
``create`` and ``bulk`` sends an ``Idempotency-Key`` (yours, or one it makes), and both mint
a UUIDv7 id for an element that has none: keel stores a bulk answer only after the batch
commits, so a resend after a lost answer must name the same elements to stay a rewrite.
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from ._ids import uuid7
from ._schema import FIELD_KINDS
from ._version import __version__
from .errors import ApiError, error_code, parse_retry_after
from .folder import WIRE_TO_DISK_WORLD_KEYS

__all__ = [
    "API_BASE",
    "READ_ONLY_FIELDS",
    "ApiError",
    "BulkResult",
    "ChangeWalk",
    "Client",
    "Response",
    "RetryPolicy",
    "Transport",
    "UrllibTransport",
    "check_kinds",
    "sanitize_payload",
]

API_BASE = "https://www.onlyworlds.com/api/v2"
USER_AGENT = f"onlyworlds-py/{__version__}"

#: Fields the API must never receive on a write. A BLACKLIST, never a whitelist:
#: namespaced extension fields (``atlas_*`` / ``shadow_*`` / ``x_*``) must pass through
#: untouched, because tools round-trip their own state through other tools' writes.
#: ``created_by`` is not here: keel drops it silently on a write (spec §4), so a read body
#: round-trips as it is.
READ_ONLY_FIELDS: tuple[str, ...] = ("world", "type", "created_at", "updated_at", "change_seq")

_TYPE = re.compile(r"^[a-z][a-z0-9_]*$")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
#: Namespace for ids derived from a caller's Idempotency-Key (``_minted_id``).
_KEYED_IDS = uuid.UUID("0199b6a0-6f0e-7c2a-9d1e-3b5c7a8e4f21")


def _minted_id(idempotency_key: str | None, index: int) -> str:
    """An id for an element that has none.

    With the caller's own Idempotency-Key, the id is derived from the key and the
    element's position (UUIDv5), so the same key with the same elements sends the same
    body and keel replays it. Without one, a fresh UUIDv7: the client made the key, and
    only its own retries, which resend the body unchanged, can reuse it. Keel takes any
    UUID as an element id (D70b).
    """
    if idempotency_key:
        return str(uuid.uuid5(_KEYED_IDS, f"{idempotency_key}\n{index}"))
    return uuid7()


def sanitize_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """A copy of ``payload`` without the fields the API rejects on write (see ``READ_ONLY_FIELDS``)."""
    return {k: v for k, v in payload.items() if k not in READ_ONLY_FIELDS}


#: ``GET /world`` keys that ``PATCH /world`` refuses (keel's writable set has neither), dropped
#: like ``READ_ONLY_FIELDS`` so a read body is writable. ``public_read`` changes through sharing.
WORLD_READ_ONLY_FIELDS: tuple[str, ...] = ("id", "public_read")
_DISK_TO_WIRE_WORLD_KEYS = {disk: wire for wire, disk in WIRE_TO_DISK_WORLD_KEYS.items()}


def check_kinds(element_type: str, element: Mapping[str, Any]) -> None:
    """Refuse, before sending, a value keel would store as something else.

    keel is lenient by design (spec §6): it stores ``int(value)`` for an integer field, cutting
    ``2.5`` to ``2``, and the ``repr`` of a list sent to a text field, both with a 200. So: an
    integer field takes an int or an integral float (never a bool), a text field a string, each
    or None. Fields outside the schema (extensions) are not checked.
    """
    kinds = FIELD_KINDS.get(element_type, {})
    for key, value in element.items():
        kind = kinds.get(key)
        if value is None or kind is None:
            continue
        if kind == "integer":
            if isinstance(value, bool) or not (
                isinstance(value, int) or (isinstance(value, float) and value.is_integer())
            ):
                raise ValueError(
                    f"{element_type}.{key} is an integer field; {value!r} would be stored as another value"
                )
        elif kind == "text" and not isinstance(value, str):
            raise ValueError(f"{element_type}.{key} is a text field; {value!r} is not a string")


def _same_stored(a: Any, b: Any) -> bool:
    """Equal as keel stores it: a text field's ``None`` and ``""`` are one state."""
    return a == b or (a in (None, "") and b in (None, ""))


def _segment(value: str, pattern: re.Pattern[str], what: str) -> str:
    if not isinstance(value, str) or not pattern.match(value):
        raise ValueError(f"{what} {value!r} is not a valid path segment")
    return value


@dataclass(frozen=True)
class Response:
    status: int
    body: bytes
    headers: Mapping[str, str] = field(default_factory=dict)

    def header(self, name: str) -> str | None:
        lname = name.lower()
        for k, v in self.headers.items():
            if k.lower() == lname:
                return v
        return None

    def json(self) -> Any:
        return json.loads(self.body.decode("utf-8")) if self.body else None


class Transport(Protocol):
    """One HTTP exchange. Returns every HTTP status as a Response; raises only on no response at all."""

    def __call__(
        self, method: str, url: str, headers: Mapping[str, str], body: bytes | None, timeout: float
    ) -> Response: ...


class UrllibTransport:
    """The default transport: stdlib ``urllib``, so the package has no runtime dependencies."""

    def __call__(
        self, method: str, url: str, headers: Mapping[str, str], body: bytes | None, timeout: float
    ) -> Response:
        req = urllib.request.Request(url, data=body, method=method, headers=dict(headers))
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return Response(r.status, r.read(), dict(r.headers.items()))
        except urllib.error.HTTPError as e:
            return Response(e.code, e.read(), dict(e.headers.items()) if e.headers else {})


@dataclass(frozen=True)
class RetryPolicy:
    """Retry 429, 502, 503, 504 and transport exceptions, and a 500 once; honor ``Retry-After``.

    Never a 429 with code ``rate_limited``: keel sends it for a wrong PIN, and each retry is
    one more failure toward locking the key. keel's 500 is an unhandled exception, almost
    always the same on every try, so it gets one retry, not the full budget.

    Waits ``Retry-After`` when the server sends a valid one (whole seconds or an HTTP
    date), otherwise ``min(cap, base * 2**attempt)``. ``attempts`` counts every try,
    the first included.
    """

    attempts: int = 6
    base: float = 1.0
    cap: float = 30.0
    max_retry_after: float = 120.0

    def should_retry(self, status: int, code: str | None = None, attempt: int = 0) -> bool:
        """``attempt`` is the try that got ``status``, the first being 0."""
        if status == 429:
            return code != "rate_limited"
        if status == 500:
            return attempt == 0
        return status in (502, 503, 504)

    def delay(self, attempt: int, response: Response | None) -> float:
        backoff: float = min(self.cap, self.base * (2.0**attempt))
        if response is None:
            return backoff
        seconds = parse_retry_after(response.header("Retry-After"))
        if seconds is None:
            return backoff
        return max(0.0, min(self.max_retry_after, seconds))


@dataclass
class Attempted:
    """A response after retries, with how many retries it took and why."""

    response: Response | None
    retries: int
    reasons: list[str]
    error: str | None = None


@dataclass(frozen=True)
class BulkResult:
    """``POST /bulk``: HTTP 200 for a partial success, so read each slot's numeric ``status``.

    ``errors`` is the server's top-level flag, ``items`` the per-item slots in request
    order (success slots echo ``id`` / ``created_at`` / ``updated_at``; error slots carry
    ``error`` with a ``code``, e.g. ``id_conflict`` or ``not_author``). ``was_replay`` is
    true when the server replayed a stored answer for a reused Idempotency-Key.

    After an ``atomic=True`` request with ``errors`` true, NOTHING was written: the slots of
    the items that would have succeeded still say 201, with the ids and timestamps they would
    have had (keel spec, "counterfactual 201s"). Do not record those ids as created.
    """

    errors: bool
    items: list[dict[str, Any]]
    was_replay: bool
    raw: dict[str, Any]


class ChangeWalk:
    """Walk the world's change feed from ``since`` (or from the start) to the current tail, in order.

    ``for op in walk`` yields each op (``upsert`` carries ``element``, ``delete`` carries
    ``deleted_at``). Afterwards ``cursor`` is the opaque position to persist for the next
    incremental pull (pass back exactly what you got: never parse or build one) and ``head``
    is the world's current ``change_seq``.

    A stored cursor can be refused: ``ApiError.is_resync_required`` (409), when a guest's view
    of the world changed or the key's role did. Then drop the cursor, walk again from the
    start, and replace the local copy rather than merging into it. A guest never receives
    delete ops, so only the replace removes what it no longer sees.
    """

    def __init__(self, client: Client, since: str | None = None, *, limit: int | None = None):
        self._client = client
        self._limit = limit
        self.cursor: str | None = since
        self.head: int | None = None
        self.done = False

    def __iter__(self) -> Iterator[dict[str, Any]]:
        while True:
            page = self._client.changes(since=self.cursor, limit=self._limit)
            yield from page.get("changes", [])
            nxt = page.get("cursor")
            self.head = page.get("head")
            if not page.get("has_more"):
                self.cursor = nxt if isinstance(nxt, str) else self.cursor
                self.done = True
                return
            if not isinstance(nxt, str) or nxt == self.cursor:
                raise ValueError("/changes said has_more but gave no new cursor")
            self.cursor = nxt


class Client:
    """Credentials, base URL and transport in one place.

    ``request`` makes ONE exchange. ``send`` applies the retry policy. ``call`` returns the
    parsed 2xx body or raises ``ApiError``. The typed methods below are what to use.
    """

    def __init__(
        self,
        api_key: str,
        pin: str | None = None,
        *,
        base_url: str = API_BASE,
        transport: Transport | None = None,
        retry: RetryPolicy | None = None,
        timeout: float = 60.0,
        sleep: Callable[[float], None] = time.sleep,
        user_agent: str = USER_AGENT,
        page_size: int = 100,
        changes_page_size: int = 100,
    ):
        if not api_key:
            raise ValueError("api_key is required")
        self.base_url = base_url.rstrip("/")
        self.transport: Transport = transport or UrllibTransport()
        self.retry = retry or RetryPolicy()
        self.timeout = timeout
        self.sleep = sleep
        self.page_size = page_size
        self.changes_page_size = changes_page_size
        self._headers = {"API-Key": api_key, "Accept": "application/json", "User-Agent": user_agent}
        if pin:
            self._headers["API-Pin"] = pin

    def __repr__(self) -> str:  # never print credentials
        return f"Client(base_url={self.base_url!r})"

    def url(self, path: str) -> str:
        return f"{self.base_url}/{path.lstrip('/')}"

    def request(
        self, method: str, path: str, payload: Any = None, headers: Mapping[str, str] | None = None
    ) -> Response:
        sent = dict(self._headers)
        if headers:
            sent.update(headers)
        body = None
        if payload is not None:
            if isinstance(payload, Mapping) and "world" in payload:
                raise ValueError("a request body never carries `world`; the key names the world")
            body = json.dumps(payload, ensure_ascii=True).encode("ascii")
            sent["Content-Type"] = "application/json"
        return self.transport(method, self.url(path), sent, body, self.timeout)

    def send(self, method: str, path: str, payload: Any = None, headers: Mapping[str, str] | None = None) -> Attempted:
        reasons: list[str] = []
        for attempt in range(self.retry.attempts):
            response: Response | None
            try:
                response = self.request(method, path, payload, headers)
            except Exception as exc:  # no response at all: timeouts, resets, DNS
                response, reason = None, f"{type(exc).__name__}: {exc}"
            else:
                code = error_code(response.body) if response.status == 429 else None
                if not self.retry.should_retry(response.status, code, attempt):
                    return Attempted(response, len(reasons), reasons)
                reason = str(response.status)
            if attempt == self.retry.attempts - 1:
                error = f"gave up after {len(reasons)} retries: {reason}"
                return Attempted(response, len(reasons), reasons, error=error)
            reasons.append(reason)
            self.sleep(self.retry.delay(attempt, response))
        raise AssertionError("unreachable")  # pragma: no cover

    def call(self, method: str, path: str, payload: Any = None, headers: Mapping[str, str] | None = None) -> Any:
        """``send`` and return the parsed 2xx body (None for an empty one); raise ``ApiError`` otherwise."""
        got = self.send(method, path, payload, headers)
        if got.response is None:
            raise ConnectionError(f"{method} {path}: {got.error}")
        if not 200 <= got.response.status < 300:
            raise ApiError(method, path, got.response)
        return got.response.json()

    # --- the world ------------------------------------------------------------

    def health(self) -> Any:
        """``GET /health``: the liveness pulse."""
        return self.call("GET", "health/")

    def get_world(self) -> dict[str, Any]:
        """``GET /world``: the world's meta (name, calendar and time fields, ``public_read``)."""
        data = self.call("GET", "world/")
        if not isinstance(data, dict) or "id" not in data:
            raise ValueError(f"GET /world returned no world object: {str(data)[:200]}")
        return data

    def patch_world(self, partial: Mapping[str, Any]) -> dict[str, Any]:
        """``PATCH /world``: a partial meta update (owner key only). World-meta edits do NOT appear
        in ``/changes``.

        Takes back a ``get_world()`` body: ``id``, ``public_read`` and the timestamps are dropped
        (``public_read`` is not writable here). A folder ``world.json``'s ``time_current`` is sent
        as the wire's ``time_range_current``. keel refuses any other key it does not write (422).
        """
        body = {
            _DISK_TO_WIRE_WORLD_KEYS.get(k, k): v
            for k, v in sanitize_payload(partial).items()
            if k not in WORLD_READ_ONLY_FIELDS
        }
        data = self.call("PATCH", "world/", body)
        if not isinstance(data, dict):
            raise ValueError(f"PATCH /world returned no object: {str(data)[:200]}")
        return data

    # --- elements -------------------------------------------------------------

    @staticmethod
    def _query(params: Mapping[str, Any]) -> str:
        parts = []
        for k, v in params.items():
            if v is None or v == "":
                continue
            text = str(v).lower() if isinstance(v, bool) else str(v)
            parts.append(f"{urllib.parse.quote(k, safe='')}={urllib.parse.quote(text, safe=',')}")
        return "&".join(parts)

    def list_page(
        self,
        element_type: str,
        *,
        limit: int | None = None,
        cursor: str | None = None,
        expand: Sequence[str] | None = None,
        fields: Sequence[str] | None = None,
        filter: Mapping[str, str | int | bool] | None = None,
    ) -> dict[str, Any]:
        """``GET /{type}``: one cursor page, ``{data, has_more, next_cursor}``.

        ``expand`` replaces the named links' ids with stubs one level deep; ``fields`` keeps
        only the named keys. Only ``name__icontains``, ``supertype`` and ``subtype`` filter
        (anything else is a 422 naming it); ``ordering`` is a 422 too. Filter or sort here.
        """
        t = _segment(element_type, _TYPE, "element type")
        query = self._query(
            {
                "limit": limit if limit is not None else self.page_size,
                "cursor": cursor,
                "expand": ",".join(expand) if expand else None,
                "fields": ",".join(fields) if fields else None,
                **(filter or {}),
            }
        )
        page = self.call("GET", f"{t}/?{query}")
        if not isinstance(page, dict):
            raise ValueError(f"GET /{t} returned no page: {str(page)[:200]}")
        return page

    def iter_elements(
        self,
        element_type: str,
        *,
        limit: int | None = None,
        expand: Sequence[str] | None = None,
        fields: Sequence[str] | None = None,
        filter: Mapping[str, str | int | bool] | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Every element of a type, walking the cursor pages."""
        cursor: str | None = None
        while True:
            page = self.list_page(element_type, limit=limit, cursor=cursor, expand=expand, fields=fields, filter=filter)
            yield from page.get("data", [])
            if not page.get("has_more"):
                return
            cursor = page.get("next_cursor")
            if not cursor:
                raise ValueError(f"{element_type}: has_more without next_cursor")

    def get(
        self,
        element_type: str,
        element_id: str,
        *,
        expand: Sequence[str] | None = None,
        fields: Sequence[str] | None = None,
    ) -> dict[str, Any]:
        """``GET /{type}/{id}``."""
        t = _segment(element_type, _TYPE, "element type")
        i = _segment(element_id, _ID, "element id")
        query = self._query(
            {"expand": ",".join(expand) if expand else None, "fields": ",".join(fields) if fields else None}
        )
        return self._element(self.call("GET", f"{t}/{i}/" + (f"?{query}" if query else "")), "GET", t)

    def create(
        self, element_type: str, element: Mapping[str, Any], *, idempotency_key: str | None = None
    ) -> dict[str, Any]:
        """``POST /{type}``: create. Gives the element an ``id`` when it has none: a UUIDv7, or,
        with your ``idempotency_key``, one derived from it, so calling again with the same key
        and element replays the stored success.

        Always sends an ``Idempotency-Key`` (yours, or a fresh one), so a retry after a lost
        answer replays the stored success instead of failing with ``id_conflict``.

        ``name`` is the one required field, and "required" means the key must be present: ``""``
        and ``None`` are accepted and stored as ``""`` (by keel's ruling, nameless Markers exist).
        """
        t = _segment(element_type, _TYPE, "element type")
        body = sanitize_payload(element)
        check_kinds(t, body)
        if not body.get("id"):
            body["id"] = _minted_id(idempotency_key, 0)
        key = idempotency_key or str(uuid.uuid4())
        got = self.send("POST", f"{t}/", body, {"Idempotency-Key": key})
        if got.response is None:
            raise ConnectionError(f"POST {t}/: {got.error}")
        if got.response.status == 409 and got.retries and error_code(got.response.body) == "id_conflict":
            # An earlier try may have committed before its answer was lost, and the retry
            # arrived before keel stored the replay: read it back. Only an exact match is ours.
            try:
                stored = self.get(t, str(body["id"]))
            except ApiError:
                stored = None
            if stored is not None and all(_same_stored(stored.get(k), v) for k, v in body.items()):
                return stored
            raise ApiError("POST", f"{t}/", got.response)
        if not 200 <= got.response.status < 300:
            raise ApiError("POST", f"{t}/", got.response)
        return self._element(got.response.json(), "POST", t)

    def upsert(self, element_type: str, element_id: str, element: Mapping[str, Any]) -> dict[str, Any]:
        """``PUT /{type}/{id}``: replace by client id, creating if absent. The local-first write."""
        t = _segment(element_type, _TYPE, "element type")
        i = _segment(element_id, _ID, "element id")
        body = sanitize_payload(element)
        check_kinds(t, body)
        return self._element(self.call("PUT", f"{t}/{i}/", body), "PUT", t)

    def patch(self, element_type: str, element_id: str, partial: Mapping[str, Any]) -> dict[str, Any]:
        """``PATCH /{type}/{id}``: a partial update. Arrays REPLACE wholesale; for links use ``edit_links``."""
        t = _segment(element_type, _TYPE, "element type")
        i = _segment(element_id, _ID, "element id")
        body = sanitize_payload(partial)
        check_kinds(t, body)
        return self._element(self.call("PATCH", f"{t}/{i}/", body), "PATCH", t)

    def delete(self, element_type: str, element_id: str) -> None:
        """``DELETE /{type}/{id}``: 204, also when it is already gone. The server scrubs the id from every link."""
        t = _segment(element_type, _TYPE, "element type")
        i = _segment(element_id, _ID, "element id")
        self.call("DELETE", f"{t}/{i}/")

    def edit_links(
        self,
        element_type: str,
        element_id: str,
        link_field: str,
        *,
        add: Iterable[str] = (),
        remove: Iterable[str] = (),
    ) -> dict[str, Any]:
        """``POST /{type}/{id}/links/{field}``: an atomic add and remove on one multi-link field.

        Adds dedupe, removes of absent ids are tolerated, added ids must exist in this world.
        Returns the whole updated element.
        """
        t = _segment(element_type, _TYPE, "element type")
        i = _segment(element_id, _ID, "element id")
        f = _segment(link_field, _TYPE, "link field")
        return self._element(
            self.call("POST", f"{t}/{i}/links/{f}", {"add": list(add), "remove": list(remove)}), "POST", t
        )

    @staticmethod
    def _element(data: Any, method: str, element_type: str) -> dict[str, Any]:
        if not isinstance(data, dict):
            raise ValueError(f"{method} /{element_type} returned no element: {str(data)[:200]}")
        return data

    # --- bulk and changes -----------------------------------------------------

    def bulk(
        self,
        items: Iterable[Mapping[str, Any]],
        *,
        atomic: bool = False,
        idempotency_key: str | None = None,
    ) -> BulkResult:
        """``POST /bulk``: up to about 1,000 ``{"type", "element"}`` items.

        Partial success is the default (HTTP 200: read each slot's numeric ``status``);
        ``atomic=True`` is all or nothing. Links are validated against the whole batch, so
        send items in any order, cycles included. Always sends an ``Idempotency-Key``, and
        gives every element without an ``id`` one (``create``'s rule, per position), so a
        resend after a lost answer rewrites the same elements instead of creating them twice.
        """
        elements = []
        for index, it in enumerate(items):
            element = sanitize_payload(it["element"])
            check_kinds(str(it["type"]), element)
            if not element.get("id"):
                element["id"] = _minted_id(idempotency_key, index)
            elements.append({"type": _segment(str(it["type"]), _TYPE, "element type"), "element": element})
        body = {
            "items": elements,
            "atomic": atomic,
        }
        key = idempotency_key or str(uuid.uuid4())
        got = self.send("POST", "bulk/", body, {"Idempotency-Key": key})
        if got.response is None:
            raise ConnectionError(f"POST bulk/: {got.error}")
        if not 200 <= got.response.status < 300:
            raise ApiError("POST", "bulk/", got.response)
        data = got.response.json()
        if not isinstance(data, dict) or not isinstance(data.get("items"), list):
            raise ValueError(f"POST /bulk returned no items: {str(data)[:200]}")
        replay = (got.response.header("Idempotent-Replay") or "").lower() == "true"
        return BulkResult(bool(data.get("errors")), data["items"], replay, data)

    def changes(self, *, since: str | None = None, limit: int | None = None) -> dict[str, Any]:
        """``GET /changes``: one page of the ordered change feed, ``{cursor, changes, has_more, head}``.

        The cursor is opaque and never expires. No ``since`` is a full export. It is the
        heaviest route on the platform: keep ``limit`` polite.
        """
        query = self._query({"since": since, "limit": limit if limit is not None else self.changes_page_size})
        page = self.call("GET", f"changes/?{query}")
        if not isinstance(page, dict):
            raise ValueError(f"GET /changes returned no page: {str(page)[:200]}")
        return page

    def walk_changes(self, since: str | None = None, *, limit: int | None = None) -> ChangeWalk:
        """A ``ChangeWalk`` from ``since`` to the tail; iterate it, then read ``cursor`` and ``head``."""
        return ChangeWalk(self, since, limit=limit)

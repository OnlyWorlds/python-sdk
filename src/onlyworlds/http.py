"""The OnlyWorlds v2 API client: an injectable transport, a retry rule, and the element, link, bulk and change calls.

Wire facts this file encodes (keel ``docs/spec/api-v2-spec.md``, and keel's published
OpenAPI document, which ``tests/test_wire.py`` compares the client with):
- base ``https://www.onlyworlds.com/api/v2`` (www, not the bare domain);
- credentials in ``API-Key`` / ``API-Pin`` headers; the PIN rides only where keel checks it:
  every request that is not a GET, ``GET /me`` (keel #314, D93), and every request of a
  10-digit legacy key (keel #421); a GET with any other key carries none;
- a body never carries ``world`` (the key names the world) or the server-managed
  ``type`` / ``created_at`` / ``updated_at`` / ``change_seq``: the typed calls strip them;
- a known-of stub (``known_of: true``, keel PR 113) is never written: the typed element
  writes refuse one before sending, and strip any other ``known_of``;
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

import datetime as _dt
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
from .errors import ApiError, api_error, error_code, parse_retry_after
from .folder import WIRE_TO_DISK_WORLD_KEYS, WORLD_FOLDER_KEYS

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
#: ``created_by``, ``changed_by``, ``changed_via`` and ``changed_client`` are not here: keel drops
#: them silently on a write (spec §4; keel #299, #520), so a read body round-trips as it is. ``known_of`` (keel PR 113)
#: is an unknown field to keel's writes (a 422): stripped too, and a body where it is ``true``
#: is refused before it gets here (``_refuse_known_of``).
#: ``hidden`` (keel PR 160, #537) rides a body only for a reader who still sees a hidden element and is
#: ignored in a write: stripped here so a read body round-trips as it is.
READ_ONLY_FIELDS: tuple[str, ...] = ("world", "type", "created_at", "updated_at", "change_seq", "known_of", "hidden")

_TYPE = re.compile(r"^[a-z][a-z0-9_]*$")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
#: keel #520's rule for ``X-OW-Client``, matched whole (``fullmatch``: a trailing newline is outside it).
_CLIENT_NAME = re.compile(r"[a-z0-9-]{1,32}")
#: A legacy (v1-era) key: ten digits, matched whole. It sends its PIN on every request (keel #421).
_LEGACY_KEY = re.compile(r"\d{10}")
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


def _refuse_known_of(element: Mapping[str, Any], where: str) -> None:
    """A known-of stub (``known_of: true``, keel PR 113) is a ValueError before anything is sent.

    Its empty fields are not the element's values: stripping the marker and sending the rest
    would turn keel's 422 into a write that blanks the element (a PUT replaces it whole, a PATCH
    clears every field it names) for any key that may write it, such as an owner pushing a
    copy a player made.
    """
    if isinstance(element, Mapping) and element.get("known_of") is True:
        raise ValueError(
            f"{where}: this body is a known-of stub (known_of: true), not the element: its empty fields "
            "are not its values, and writing it would blank them. Write from a whole copy, or send only "
            "the fields you mean to change."
        )


#: ``GET /world`` keys that ``PATCH /world`` refuses (keel's writable set has neither), dropped
#: like ``READ_ONLY_FIELDS`` so a read body is writable. ``public_read`` changes through sharing;
#: ``slug`` and ``public_page`` ride every body since keel #471 (PR 173) and are answered 422 like it;
#: ``agent_narrator_rule`` is refused too (a 422 naming it, measured on staging 2026-10-22);
#: ``agent_writes_proposed`` (keel #519) is ``readOnly`` in the document, set on the world page.
#: ``owner_character`` is not here: PATCH takes it (a 200 on staging).
WORLD_READ_ONLY_FIELDS: tuple[str, ...] = (
    "id",
    "public_read",
    "slug",
    "public_page",
    "agent_narrator_rule",
    "agent_writes_proposed",
)
_DISK_TO_WIRE_WORLD_KEYS = {disk: wire for wire, disk in WIRE_TO_DISK_WORLD_KEYS.items()}


def _folder_only_world_key(key: str) -> bool:
    """A ``world.json`` key that says what the folder is (§4.1, §4.2), never sent to ``PATCH /world``."""
    return key in WORLD_FOLDER_KEYS or key == "api" or key.startswith("snapshot_")


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


def _if_match(change_seq: int | None) -> dict[str, str] | None:
    """The ``If-Match`` header for a ``change_seq`` (keel #210), or None. A bool is not a number here."""
    if change_seq is None:
        return None
    if isinstance(change_seq, bool) or not isinstance(change_seq, int) or change_seq < 0:
        raise ValueError(f"if_match must be a whole number (an element's change_seq), got {change_seq!r}")
    return {"If-Match": f'"{change_seq}"'}


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
    """Retry 429, 502, 503, 504, transport exceptions and a 409 ``idempotency_in_flight``, and a
    500 once; honor ``Retry-After``.

    A 409 ``idempotency_in_flight`` (keel #307, D105) means a request with the same
    Idempotency-Key is still running, which is what a retry after a timeout meets: the
    retry, same key and body, replays its answer once the first has finished.

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
        if status == 409:
            return code == "idempotency_in_flight"
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

    On a world that takes an agent seat's writes as proposals (keel #519), a seat's item on an
    existing element says 202 with ``proposal`` in its slot: the element did not change, so a
    202 slot is neither written nor failed (``proposed`` lists them). Under ``atomic`` a failed
    batch keeps no proposal either.
    """

    errors: bool
    items: list[dict[str, Any]]
    was_replay: bool
    raw: dict[str, Any]

    @property
    def proposed(self) -> list[dict[str, Any]]:
        """The slots that say 202: writes held as proposals, the element unchanged (keel #519)."""
        return [s for s in self.items if isinstance(s, dict) and s.get("status") == 202]


class ChangeWalk:
    """Walk the world's change feed from ``since`` (or from the start) to the current tail, in order.

    ``for op in walk`` yields each op (``upsert`` carries ``element``, whose ``changed_client`` names
    the client of its last write; ``delete`` carries ``deleted_at`` and ``deleted_client``, the
    delete's client name, keel #520: each the client's claim, or null when none was recorded,
    always null on a hidden row). Afterwards ``cursor`` is the opaque position to persist for the next
    incremental pull (pass back exactly what you got: never parse or build one; always a string,
    since keel answers an owner's cursor at the head as a number) and ``head``
    is the world's current ``change_seq``.

    A stored cursor can be refused: ``ApiError.is_resync_required`` (409), when what the key
    may see changed (a guest's slice, an element unhidden from a contributor: keel #421) or
    its role did. Then drop the cursor and walk again from the start. What the local copy
    holds that the new walk does not name follows ``ApiError.resync_reason`` (keel #421, while
    keel's hidden mark is on): ``role`` (the key's own role or membership moved), keep it;
    ``view`` (something left its view), drop it; no reason, keep it: a reset never empties a
    copy (keel PR 104; sharing is forward-only). A guest never receives delete ops, so the
    409 is its only sign that something left. A delete op's ``reason`` (``deleted``,
    ``hidden``, ``out_of_view``) says why it left; remove it in every case. Never empty a
    copy on your own.
    """

    def __init__(self, client: Client, since: str | None = None, *, limit: int | None = None, after: str | None = None):
        self._client = client
        self._limit = limit
        self._after = after
        self.cursor: str | None = since
        self.head: int | None = None
        self.done = False

    def __iter__(self) -> Iterator[dict[str, Any]]:
        while True:
            page = self._client.changes(since=self.cursor, limit=self._limit, after=self._after)
            yield from page.get("changes", [])
            raw = page.get("cursor")
            # keel answers an owner's cursor at the head as a number: kept as text, the position to pass back.
            nxt = None if raw is None or isinstance(raw, bool) else str(raw)
            self.head = page.get("head")
            if not page.get("has_more"):
                self.cursor = nxt if nxt is not None else self.cursor
                self.done = True
                return
            if nxt is None or nxt == self.cursor:
                raise ValueError("/changes said has_more but gave no new cursor")
            self.cursor = nxt


class Client:
    """Credentials, base URL and transport in one place.

    ``request`` makes ONE exchange. ``send`` applies the retry policy. ``call`` returns the
    parsed 2xx body or raises ``ApiError``. The typed methods below are what to use.

    ``pin`` is sent as ``API-Pin`` only where keel checks it, derived from the request in
    ``request`` (``_sends_pin``): every method but GET, ``GET /me``, and every request of a
    10-digit legacy key. A read with an ``ow_w_``, ``ow_r_`` or member key carries no PIN.
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
        agent: bool = False,
        client: str = "python",
    ):
        """``agent=True`` declares the caller an AI agent: every element write (create, upsert,
        patch, delete, edit_links, bulk: the operations keel's document declares it on) carries
        ``X-OW-Agent``, and keel records those writes as agent-made (``changed_via: "declared"``, keel #299; keel
        stores that the header was there, never its value). Off by default, and off in any tool
        a person uses: it describes the caller. An agent seat's key counts as an agent without it.

        ``client`` is the software's own name, sent as ``X-OW-Client`` on the same element writes
        (keel #520) and never on a read. keel stores it on the element as ``changed_client``, and on
        a delete as the change feed's ``deleted_client``. The default ``python`` says which library
        wrote; a tool passes its own (``client="atlas"``). The rule is lower case letters, digits and
        hyphens, 1 to 32 characters (``[a-z0-9-]{1,32}``), with no version in it: a value outside it
        is refused here (``ValueError``; ``TypeError`` for a non-string), never trimmed. It is the
        client's claim, never proof of who wrote, and it changes no door and no permission: an agent
        sends both headers."""
        if not api_key:
            raise ValueError("api_key is required")
        if not isinstance(client, str):
            raise TypeError(f"client must be a string matching [a-z0-9-]{{1,32}}, got {type(client).__name__}")
        if not _CLIENT_NAME.fullmatch(client):
            raise ValueError(f"client must match [a-z0-9-]{{1,32}} (lower case, digits, hyphens), got {client!r}")
        self.base_url = base_url.rstrip("/")
        self.transport: Transport = transport or UrllibTransport()
        self.retry = retry or RetryPolicy()
        self.timeout = timeout
        self.sleep = sleep
        self.page_size = page_size
        self.changes_page_size = changes_page_size
        self._headers = {"API-Key": api_key, "Accept": "application/json", "User-Agent": user_agent}
        # Never in ``_headers``: ``request`` adds it where keel checks it (``_sends_pin``).
        self._pin = pin or None
        self._legacy_key = _LEGACY_KEY.fullmatch(api_key) is not None
        self._agent = agent is True
        self._client = client
        # ``head()``'s conditional poll (keel #518): the last ETag as received, and what that 200 said.
        self._head_etag: str | None = None
        self._head_held: dict[str, Any] | None = None

    def _writing(self, headers: Mapping[str, str] | None = None) -> dict[str, str]:
        """An element write's headers: ``X-OW-Client`` always (keel #520), and ``X-OW-Agent`` when this
        client is an agent (presence is the declaration, D104). keel reads both on the element writes
        only, so nothing else sends them."""
        out = dict(headers or {})
        out["X-OW-Client"] = self._client
        if self._agent:
            out["X-OW-Agent"] = "1"
        return out

    def __repr__(self) -> str:  # never print credentials
        return f"Client(base_url={self.base_url!r})"

    def url(self, path: str) -> str:
        return f"{self.base_url}/{path.lstrip('/')}"

    def _sends_pin(self, method: str, path: str) -> bool:
        """Whether this request carries ``API-Pin``, from the request alone, never a list of calls.

        keel verifies a PIN wherever one is sent (argon2, 64 MiB each), so a PIN on every read cost
        memory for nothing: a cold cache after a restart OOM-killed staging under PIN-carrying
        reads (2026-10-22; Skeld's rule, OW Keel h29 #10663). It rides every method but GET (every
        write, present and future), ``GET /me`` (keel checks it there when sent: #314, D93), and
        every request of a 10-digit legacy key (v1 parity, keel #421: such a key needs it on the
        reads of a world with a PIN)."""
        if self._legacy_key or method.upper() != "GET":
            return True
        return path.split("?", 1)[0].strip("/") == "me"

    def request(
        self, method: str, path: str, payload: Any = None, headers: Mapping[str, str] | None = None
    ) -> Response:
        sent = dict(self._headers)
        if self._pin is not None and self._sends_pin(method, path):
            sent["API-Pin"] = self._pin
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
                code = error_code(response.body) if response.status in (409, 429) else None
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
            raise api_error(method, path, got.response)
        return got.response.json()

    def _element_write(self, method: str, path: str, payload: Any, headers: Mapping[str, str]) -> Any:
        """``call`` for a write to an existing element, which keel may hold as a proposal (keel #519):
        a 202 raises ``ProposedError``, so its ``{"proposal": ...}`` is never taken for the element."""
        got = self.send(method, path, payload, headers)
        if got.response is None:
            raise ConnectionError(f"{method} {path}: {got.error}")
        if got.response.status == 202 or not 200 <= got.response.status < 300:
            raise api_error(method, path, got.response)
        return got.response.json()

    # --- the world ------------------------------------------------------------

    def health(self) -> Any:
        """``GET /health``: the liveness pulse."""
        return self.call("GET", "health/")

    def me(self) -> dict[str, Any]:
        """``GET /me``: who this key is, ``{world, scope, kind, role, membership, character, name?}``.

        ``kind`` is ``owner`` for an owner-minted or classic key, else the membership's (``person``,
        ``agent``, ``player``); ``role`` is ``owner``, ``co_builder``, ``contributor`` or ``guest``;
        ``character`` is the member's Character id, or None.
        """
        data = self.call("GET", "me/")
        if not isinstance(data, dict):
            raise ValueError(f"GET /me returned no object: {str(data)[:200]}")
        return data

    def get_world(self) -> dict[str, Any]:
        """``GET /world``: the world's meta (name, calendar and time fields, ``public_read``)."""
        data = self.call("GET", "world/")
        if not isinstance(data, dict) or "id" not in data:
            raise ValueError(f"GET /world returned no world object: {str(data)[:200]}")
        return data

    def patch_world(self, partial: Mapping[str, Any]) -> dict[str, Any]:
        """``PATCH /world``: a partial meta update (owner key only). World-meta edits do NOT appear
        in ``/changes``.

        Takes back a ``get_world()`` body: ``id``, ``public_read``, ``slug``, ``public_page``,
        ``agent_narrator_rule`` and the timestamps are dropped (none is writable here). A folder
        ``world.json``'s ``time_current`` is sent as the wire's ``time_range_current``, and the keys
        only a folder carries are left out: the folder format's own (``WORLD_FOLDER_KEYS``:
        ``format_version``, ``writable``, ``source``, ``exported_as``, ``producer``), ``api`` and
        the ``snapshot_*`` keys. keel refuses any other key it does not write (422).
        """
        body = {
            _DISK_TO_WIRE_WORLD_KEYS.get(k, k): v
            for k, v in sanitize_payload(partial).items()
            if k not in WORLD_READ_ONLY_FIELDS and not _folder_only_world_key(k)
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
        view_as: str | None = None,
        ids: Sequence[str] | None = None,
        created_by: str | None = None,
    ) -> dict[str, Any]:
        """``GET /{type}``: one cursor page, ``{data, has_more, next_cursor}``.

        ``expand`` replaces the named links' ids with stubs one level deep; ``fields`` keeps
        only the named keys. Only ``name__icontains``, ``supertype`` and ``subtype`` filter
        (anything else is a 422 naming it); ``ordering`` is a 422 too. Filter or sort here.

        ``view_as`` (keel #421, sent as ``as``) reads as another reader of this world would: a
        membership id (a person, an agent seat or a player seat) as that member's own key, a
        Character id as a guest of that Character with no membership, ``"public"`` as everything
        not hidden. The owner's keys only (a key with no member): a member key gets 403
        ``view_as_owner_only`` (``is_view_as_owner_only``). An element hidden from that reader
        is 404, never 410; an unknown value is 422 (``param`` as). Only while keel's hidden mark
        is on; until then keel answers 422 (an unknown parameter).
        """
        t = _segment(element_type, _TYPE, "element type")
        query = self._query(
            {
                "limit": limit if limit is not None else self.page_size,
                "cursor": cursor,
                "expand": ",".join(expand) if expand else None,
                "fields": ",".join(fields) if fields else None,
                **(filter or {}),
                "ids": ",".join(ids) if ids else None,
                "created_by": created_by,
                "as": view_as,
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
        view_as: str | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Every element of a type, walking the cursor pages. ``view_as``: see ``list_page``."""
        cursor: str | None = None
        while True:
            page = self.list_page(
                element_type, limit=limit, cursor=cursor, expand=expand, fields=fields, filter=filter, view_as=view_as
            )
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
        view_as: str | None = None,
    ) -> dict[str, Any]:
        """``GET /{type}/{id}``. ``view_as`` (keel #421, sent as ``as``): see ``list_page``; an
        element hidden from that reader is 404, never 410."""
        t = _segment(element_type, _TYPE, "element type")
        i = _segment(element_id, _ID, "element id")
        query = self._query(
            {
                "expand": ",".join(expand) if expand else None,
                "fields": ",".join(fields) if fields else None,
                "as": view_as,
            }
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
        _refuse_known_of(element, "create")
        body = sanitize_payload(element)
        check_kinds(t, body)
        if not body.get("id"):
            body["id"] = _minted_id(idempotency_key, 0)
        key = idempotency_key or str(uuid.uuid4())
        got = self.send("POST", f"{t}/", body, self._writing({"Idempotency-Key": key}))
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
        """``PUT /{type}/{id}``: replace by client id, creating if absent. The local-first write.

        A known-of stub (``known_of: true``, keel PR 113) is a ValueError before sending, here and
        on every element write: a PUT of one would blank every field it does not keep.

        On a world that takes an agent seat's writes as proposals (keel #519), a seat's PUT of an
        existing element answers 202 and this raises ``ProposedError`` (the element unchanged; a PUT
        proposal is a whole replace). The same on ``patch`` and ``edit_links``.
        """
        t = _segment(element_type, _TYPE, "element type")
        i = _segment(element_id, _ID, "element id")
        _refuse_known_of(element, "upsert")
        body = sanitize_payload(element)
        check_kinds(t, body)
        return self._element(self._element_write("PUT", f"{t}/{i}/", body, self._writing()), "PUT", t)

    def patch(
        self, element_type: str, element_id: str, partial: Mapping[str, Any], *, if_match: int | None = None
    ) -> dict[str, Any]:
        """``PATCH /{type}/{id}``: a partial update. Arrays REPLACE wholesale; for links use ``edit_links``.

        ``if_match`` (keel #210): the element's ``change_seq`` as you read it. The update lands only
        if nobody changed the element since; otherwise nothing is written and ``PreconditionFailed``
        (412) is raised, whose ``current`` is the element as it is now. Omit it for an unconditional write.

        A 202 (keel #519: the world holds this agent seat's writes as proposals) raises
        ``ProposedError``: the element did not change. keel checks ``if_match`` first, so a stale
        one is still a 412.
        """
        t = _segment(element_type, _TYPE, "element type")
        i = _segment(element_id, _ID, "element id")
        _refuse_known_of(partial, "patch")
        body = sanitize_payload(partial)
        check_kinds(t, body)
        headers = self._writing(_if_match(if_match))
        return self._element(self._element_write("PATCH", f"{t}/{i}/", body, headers), "PATCH", t)

    def delete(self, element_type: str, element_id: str) -> None:
        """``DELETE /{type}/{id}``: 204, also when it is already gone. The server scrubs the id from every link."""
        t = _segment(element_type, _TYPE, "element type")
        i = _segment(element_id, _ID, "element id")
        self.call("DELETE", f"{t}/{i}/", None, self._writing())

    def edit_links(
        self,
        element_type: str,
        element_id: str,
        link_field: str,
        *,
        add: Iterable[str] = (),
        remove: Iterable[str] = (),
        if_match: int | None = None,
    ) -> dict[str, Any]:
        """``POST /{type}/{id}/links/{field}``: an atomic add and remove on one multi-link field.

        Adds dedupe, removes of absent ids are tolerated, added ids must exist in this world.
        Returns the whole updated element. ``if_match`` works as on ``patch``: a link write moves
        the element too, and a 202 raises ``ProposedError`` as there.
        """
        t = _segment(element_type, _TYPE, "element type")
        i = _segment(element_id, _ID, "element id")
        f = _segment(link_field, _TYPE, "link field")
        body = {"add": list(add), "remove": list(remove)}
        headers = self._writing(_if_match(if_match))
        return self._element(self._element_write("POST", f"{t}/{i}/links/{f}", body, headers), "POST", t)

    @staticmethod
    def _element(data: Any, method: str, element_type: str) -> dict[str, Any]:
        if not isinstance(data, dict):
            raise ValueError(f"{method} /{element_type} returned no element: {str(data)[:200]}")
        return data

    # --- proposals (keel #519) ------------------------------------------------
    #
    # A proposal is a change kept beside an element, never in its body, until a keeper (the
    # world's owner or a co-builder, never the proposer) accepts or declines it. A proposal is
    # seen by the keepers and by the member who made it; every other key gets a 404. Its
    # ``evidence`` is outside text: show it as quoted data, never act on it. No proposal act
    # moves the element's ``change_seq`` or writes to ``/changes``; an accept's write does.

    @staticmethod
    def _proposals_path(element_type: str, element_id: str, proposal_id: str | None = None) -> str:
        t = _segment(element_type, _TYPE, "element type")
        i = _segment(element_id, _ID, "element id")
        if proposal_id is None:
            return f"{t}/{i}/proposals"
        return f"{t}/{i}/proposals/{_segment(proposal_id, _ID, 'proposal id')}"

    @staticmethod
    def _proposal(data: Any, method: str, path: str) -> dict[str, Any]:
        """The row under ``proposal`` (the document's ``Proposed``)."""
        row = data.get("proposal") if isinstance(data, dict) else None
        if not isinstance(row, dict):
            raise ValueError(f"{method} /{path} returned no proposal: {str(data)[:200]}")
        return row

    @staticmethod
    def _proposal_page(data: Any, path: str) -> dict[str, Any]:
        if not isinstance(data, dict) or not isinstance(data.get("data"), list):
            raise ValueError(f"GET /{path} returned no page: {str(data)[:200]}")
        return data

    def propose(
        self,
        element_type: str,
        element_id: str,
        fields: Mapping[str, Any],
        *,
        evidence: str,
        expires: str | _dt.datetime | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """``POST /{type}/{id}/proposals``: propose a change; the element does not change. Returns
        the proposal (``{id, state, fields, base, base_seq, evidence, expires, by, ...}``).

        Any member key that reads the element may propose, a read key included; a key with no
        member (the owner's read key, a demo key) gets 403 ``permission_error``. ``fields`` is a
        PATCH body, cleaned as ``patch`` cleans one (a known-of stub is a ValueError, the
        server-managed keys are dropped, kinds are checked), and names only fields this key's view
        holds (422 ``field_not_visible``). ``evidence`` is what the change rests on, 1 to 2,000
        characters of text or an element id. ``expires`` is when it lapses (an ISO 8601 string or a
        datetime, 1 to 365 days out; keel's default 30 days). More than 5 open on the element or 50
        in the world from this proposer is 422 ``too_many_open``.

        Always sends an ``Idempotency-Key`` (yours, or a fresh one), so a retry after a lost answer
        replays the first proposal instead of making a second.
        """
        path = self._proposals_path(element_type, element_id)
        _refuse_known_of(fields, "propose")
        cleaned = sanitize_payload(fields)
        check_kinds(element_type, cleaned)
        body: dict[str, Any] = {"fields": cleaned, "evidence": evidence}
        if expires is not None:
            body["expires"] = expires.isoformat() if isinstance(expires, _dt.datetime) else expires
        key = idempotency_key or str(uuid.uuid4())
        headers = {"Idempotency-Key": key, "X-OW-Client": self._client}
        return self._proposal(self.call("POST", path, body, headers), "POST", path)

    def list_proposals(
        self,
        element_type: str,
        element_id: str,
        *,
        state: str | None = None,
        since: str | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        """``GET /{type}/{id}/proposals``: one page, ``{data, has_more, next_cursor}``, newest first.

        ``state`` is ``open`` (keel's default: not past ``expires``), ``lapsed``, ``accepted``,
        ``declined`` or ``all``; ``since`` keeps rows whose ``updated_at`` is at or after an ISO time.
        Keepers read every proposal on the element, any other member its own."""
        path = self._proposals_path(element_type, element_id)
        query = self._query({"state": state, "since": since, "limit": limit, "cursor": cursor})
        return self._proposal_page(self.call("GET", path + (f"?{query}" if query else "")), path)

    def accept_proposal(self, element_type: str, element_id: str, proposal_id: str) -> dict[str, Any]:
        """``POST /{type}/{id}/proposals/{pid}/accept``: ``{proposal, element}``, the element as written.

        The owner's or a co-builder's key with its PIN, never the proposer's own (403
        ``own_proposal``). The write is yours: ``changed_by`` you, a new ``change_seq``, a
        ``/changes`` row. When a proposed field moved since the proposal was made, nothing is written
        and ``StaleProposal`` (409) is raised, with ``conflicts`` and ``current``. A lapsed proposal
        may still be accepted; a decided one is 422."""
        path = self._proposals_path(element_type, element_id, proposal_id) + "/accept"
        data = self.call("POST", path, None, {"X-OW-Client": self._client})
        if not isinstance(data, dict) or not isinstance(data.get("proposal"), dict):
            raise ValueError(f"POST /{path} returned no proposal: {str(data)[:200]}")
        return data

    def decline_proposal(
        self, element_type: str, element_id: str, proposal_id: str, reason: str | None = None
    ) -> dict[str, Any]:
        """``POST /{type}/{id}/proposals/{pid}/decline``: the declined proposal; the element does not
        change. A keeper's key with its PIN; ``reason`` is optional text of at most 2,000 characters."""
        path = self._proposals_path(element_type, element_id, proposal_id) + "/decline"
        body = {"reason": reason} if reason is not None else {}
        return self._proposal(self.call("POST", path, body), "POST", path)

    def withdraw_proposal(self, element_type: str, element_id: str, proposal_id: str) -> None:
        """``DELETE /{type}/{id}/proposals/{pid}``: 204, the row gone. The member who made it, with any
        of its keys, while it is undecided; a keeper on another's row is 403, anyone else 404."""
        self.call("DELETE", self._proposals_path(element_type, element_id, proposal_id))

    def world_proposals(
        self,
        *,
        state: str | None = None,
        since: str | None = None,
        element: str | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        """``GET /world/proposals``: one page of the world's queue, ``{data, has_more, next_cursor}``,
        newest first. ``state`` and ``since`` as on ``list_proposals``; ``element`` keeps one element's
        rows. Keepers read every proposal in the world, any other member its own; a key with no member
        and the keyless public view get 404."""
        query = self._query({"state": state, "since": since, "element": element, "limit": limit, "cursor": cursor})
        path = "world/proposals"
        return self._proposal_page(self.call("GET", path + (f"?{query}" if query else "")), path)

    def walk_world_proposals(
        self,
        *,
        state: str | None = None,
        since: str | None = None,
        element: str | None = None,
        limit: int | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Every row of the world's queue that matches, walking the cursor pages (``world_proposals``)."""
        cursor: str | None = None
        while True:
            page = self.world_proposals(state=state, since=since, element=element, limit=limit, cursor=cursor)
            yield from page["data"]
            if not page.get("has_more"):
                return
            nxt = page.get("next_cursor")
            if not isinstance(nxt, str) or not nxt or nxt == cursor:
                raise ValueError("GET /world/proposals said has_more without a new next_cursor")
            cursor = nxt

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
            _refuse_known_of(it["element"], f"bulk: items[{index}]")  # the whole call, never a skipped slot
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
        got = self.send("POST", "bulk/", body, self._writing({"Idempotency-Key": key}))
        if got.response is None:
            raise ConnectionError(f"POST bulk/: {got.error}")
        if not 200 <= got.response.status < 300:
            raise ApiError("POST", "bulk/", got.response)
        data = got.response.json()
        if not isinstance(data, dict) or not isinstance(data.get("items"), list):
            raise ValueError(f"POST /bulk returned no items: {str(data)[:200]}")
        replay = (got.response.header("Idempotent-Replay") or "").lower() == "true"
        return BulkResult(bool(data.get("errors")), data["items"], replay, data)

    def changes(
        self, *, since: str | None = None, limit: int | None = None, after: str | None = None
    ) -> dict[str, Any]:
        """``GET /changes``: one page of the ordered change feed,
        ``{cursor, changes, has_more, head, epoch}`` (``epoch``: a guest's or a contributor's
        view epoch, else null). While keel's hidden mark is on, ``epoch_reason`` sits beside
        ``epoch`` (keel #421): why the epoch last moved, ``role`` (keep what a walk from the
        start no longer names) or ``view`` (drop it), null when ``epoch`` is. It names the last
        move only; a 409's ``resync_reason`` covers every move since your cursor.

        The cursor is opaque and never expires. No ``since`` is a full export. It is the
        heaviest route on the platform: keep ``limit`` polite.

        ``after`` (keel #514): only the changes made at or after an ISO 8601 time (an upsert's
        ``updated_at``, a delete's ``deleted_at``; no offset means UTC). A filter, not a
        position: order, cursor, ``has_more`` and ``head`` are as without it, so a window is
        read by passing the cursor back as ``since`` with the same ``after`` (``walk_changes``
        does). A kept cursor is still the exact "since my last visit"; ``after`` is "since
        yesterday" by the clock. A value that is not a date and time is a 422 naming ``after``.
        """
        query = self._query(
            {"since": since, "limit": limit if limit is not None else self.changes_page_size, "after": after}
        )
        try:
            page = self.call("GET", f"changes/?{query}")
        except ApiError as e:
            self._forget_head_on_resync(e)
            raise
        if not isinstance(page, dict):
            raise ValueError(f"GET /changes returned no page: {str(page)[:200]}")
        return page

    def _forget_head_on_resync(self, error: ApiError) -> None:
        """A 409 ``resync_required`` from any feed read drops ``head()``'s held tag: the poll after it carries none."""
        if error.is_resync_required:
            self._head_etag = None
            self._head_held = None

    def head(self) -> dict[str, Any]:
        """``GET /changes?head=true``: where the feed is now, without a page (no element is read),
        ``{head, cursor, epoch, unchanged}``, with ``epoch_reason`` when keel sends it (keel #421).

        ``head`` is the world's ``change_seq``; ``cursor`` is a position to pass as ``since`` that
        re-sends nothing at the head (a string: keel answers an owner's as a number, handed back as
        text like the npm SDK's ``changesHead``); ``epoch`` is a guest's or a contributor's view epoch,
        else null, and it can move with ``head`` unchanged.

        The poll is conditional (keel #518): this client keeps the ``ETag`` of the last 200 and sends
        it as ``If-None-Match`` on the next call, exactly as received (``W/`` and quotes included);
        the package compares nothing. keel answers 304 when neither ``head`` nor ``epoch`` moved (the
        tag covers both), and then this returns what the last 200 said with ``unchanged=True``; a
        200 returns the new values with ``unchanged=False`` and keeps its tag. keel refunds a 304
        against the request budget (within a floor of 120 a minute per credential). The tag is per
        client instance. A 409 ``resync_required`` from ``head()``, ``changes()`` or ``walk_changes()``
        drops it, so the poll after it carries none. A 304 when no tag was sent is the server
        contradicting itself: a ``ValueError``, never an invented head.

        The poll recipe (the package never sleeps for you)::

            cursor, applied = saved_cursor, None  # applied: (head, epoch) of the last walk you finished
            while True:
                now = client.head()  # a 304 costs nothing against the budget
                if (now["head"], now["epoch"]) != applied:
                    walk = client.walk_changes(cursor)
                    for op in walk:
                        ...
                    cursor, applied = walk.cursor, (walk.head, now["epoch"])
                time.sleep(2)

        ``unchanged`` says nothing moved since this client's last poll, not since your last walk:
        compare with what you applied, so a walk that failed after a 200 is walked again on the
        next tick (its poll answers ``unchanged=True`` with the moved head). On a 409
        ``resync_required`` walk again from the start (``ApiError.resync_reason`` says what to keep)."""
        headers = {"If-None-Match": self._head_etag} if self._head_etag is not None else None
        got = self.send("GET", "changes/?head=true", headers=headers)
        if got.response is None:
            raise ConnectionError(f"GET changes/?head=true: {got.error}")
        if got.response.status == 304:
            if headers is None or self._head_held is None:
                raise ValueError("GET /changes?head=true answered 304 Not Modified, but no tag was sent")
            return {**self._head_held, "unchanged": True}
        if not 200 <= got.response.status < 300:
            error = api_error("GET", "changes/?head=true", got.response)
            self._forget_head_on_resync(error)
            raise error
        page = got.response.json()
        if not isinstance(page, dict) or "head" not in page:
            raise ValueError(f"GET /changes?head=true returned no head: {str(page)[:200]}")
        held: dict[str, Any] = {
            "head": page["head"],
            "cursor": None if page.get("cursor") is None else str(page["cursor"]),
            "epoch": page.get("epoch"),
        }
        if "epoch_reason" in page:
            held["epoch_reason"] = page["epoch_reason"]
        self._head_etag = got.response.header("ETag")
        self._head_held = held
        return {**held, "unchanged": False}

    def draught(
        self,
        character_id: str,
        *,
        components: Sequence[str] | None = None,
        mode: str | None = None,
        as_of: int | None = None,
        undated: str | None = None,
        since: str | None = None,
        budget: int | None = None,
        depth: int | None = None,
    ) -> dict[str, Any]:
        """``GET /character/{id}/context``: the draught (keel PR 155), one Character's context in
        one read as the recorded world holds it: her element, what she holds and sits in, her open
        work, how she works, her Events, the Narratives she knows, everything else that names her,
        her sheet, what changed around her (``since``: a feed cursor or an ISO time) and who plays
        whom, with the world's name and calendar. The seven policy keys as the document names
        them (``components`` joined by commas); nothing is inferred; a non-empty ``cut`` means the
        serving is partial. Served ``Cache-Control: private, no-store``: never cache it shared."""
        query = self._query(
            {
                "components": ",".join(components) if components else None,
                "mode": mode,
                "as_of": as_of,
                "undated": undated,
                "since": since,
                "budget": budget,
                "depth": depth,
            }
        )
        page = self.call("GET", f"character/{character_id}/context" + (f"?{query}" if query else ""))
        if not isinstance(page, dict):
            raise ValueError(f"GET /character/{character_id}/context returned no packet: {str(page)[:200]}")
        return page

    def walk_changes(
        self, since: str | None = None, *, limit: int | None = None, after: str | None = None
    ) -> ChangeWalk:
        """A ``ChangeWalk`` from ``since`` to the tail (``after``: only changes at or after that
        time, on every page); iterate it, then read ``cursor`` and ``head``."""
        return ChangeWalk(self, since, limit=limit, after=after)

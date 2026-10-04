"""A small HTTP layer for the OnlyWorlds v2 API: an injectable transport, a client, a retry rule.

Only what the folder module needs today (``GET /world``, the element lists,
``PATCH /{type}/{id}``). The full client (create/put/delete, links, bulk,
/changes, typed errors) is the package's next slice and grows here.

Wire facts this file encodes (keel ``docs/spec/api-v2-spec.md``):
- base ``https://www.onlyworlds.com/api/v2`` (www, not the bare domain);
- credentials in ``API-Key`` / ``API-Pin`` headers; ``ow_r_`` read keys need no PIN;
- a body never carries ``world`` (the key names the world);
- lists are ``{data, has_more, next_cursor}``, continued with ``?cursor=``;
- 429 carries ``Retry-After``; under load keel answers 503 ``server_busy`` with
  ``Retry-After: 5`` (keel D71, 2026-09-28).
"""

from __future__ import annotations

import email.utils
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

from ._version import __version__

__all__ = [
    "API_BASE",
    "ApiError",
    "Client",
    "Response",
    "RetryPolicy",
    "Transport",
    "UrllibTransport",
]

API_BASE = "https://www.onlyworlds.com/api/v2"
USER_AGENT = f"onlyworlds-py/{__version__}"


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


class ApiError(Exception):
    def __init__(self, method: str, path: str, response: Response):
        self.status = response.status
        self.response = response
        detail = response.body[:300].decode("utf-8", "replace")
        super().__init__(f"{method} {path} -> {response.status}: {detail}")


@dataclass(frozen=True)
class RetryPolicy:
    """Retry 429, any 5xx, and transport exceptions; honor ``Retry-After``.

    Waits ``Retry-After`` when the server sends one (seconds or an HTTP date),
    otherwise ``min(cap, base * 2**attempt)``. ``attempts`` counts every try,
    the first included.
    """

    attempts: int = 6
    base: float = 1.0
    cap: float = 30.0
    max_retry_after: float = 120.0

    def should_retry(self, status: int) -> bool:
        return status == 429 or status >= 500

    def delay(self, attempt: int, response: Response | None) -> float:
        backoff: float = min(self.cap, self.base * (2.0**attempt))
        if response is None:
            return backoff
        ra = response.header("Retry-After")
        if ra is None:
            return backoff
        ra = ra.strip()
        try:
            seconds = float(ra)
        except ValueError:
            try:
                parsed = email.utils.parsedate_to_datetime(ra)
            except (TypeError, ValueError, IndexError):
                return backoff
            seconds = parsed.timestamp() - time.time()
        return max(0.0, min(self.max_retry_after, seconds))


@dataclass
class Attempted:
    """A response after retries, with how many retries it took and why."""

    response: Response | None
    retries: int
    reasons: list[str]
    error: str | None = None


class Client:
    """Credentials, base URL and transport in one place. Pass it, or build one from a key and PIN.

    ``request`` makes ONE exchange. ``send`` applies the retry policy.
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
    ):
        if not api_key:
            raise ValueError("api_key is required")
        self.base_url = base_url.rstrip("/")
        self.transport: Transport = transport or UrllibTransport()
        self.retry = retry or RetryPolicy()
        self.timeout = timeout
        self.sleep = sleep
        self._headers = {"API-Key": api_key, "Accept": "application/json", "User-Agent": user_agent}
        if pin:
            self._headers["API-Pin"] = pin

    def __repr__(self) -> str:  # never print credentials
        return f"Client(base_url={self.base_url!r})"

    def url(self, path: str) -> str:
        return f"{self.base_url}/{path.lstrip('/')}"

    def request(self, method: str, path: str, payload: Any = None) -> Response:
        headers = dict(self._headers)
        body = None
        if payload is not None:
            if isinstance(payload, Mapping) and "world" in payload:
                raise ValueError("a request body never carries `world`; the key names the world")
            body = json.dumps(payload, ensure_ascii=True).encode("ascii")
            headers["Content-Type"] = "application/json"
        return self.transport(method, self.url(path), headers, body, self.timeout)

    def send(self, method: str, path: str, payload: Any = None) -> Attempted:
        reasons: list[str] = []
        for attempt in range(self.retry.attempts):
            response: Response | None
            try:
                response = self.request(method, path, payload)
            except Exception as exc:  # no response at all: timeouts, resets, DNS
                response, reason = None, f"{type(exc).__name__}: {exc}"
            else:
                if not self.retry.should_retry(response.status):
                    return Attempted(response, len(reasons), reasons)
                reason = str(response.status)
            if attempt == self.retry.attempts - 1:
                error = f"gave up after {len(reasons)} retries: {reason}"
                return Attempted(response, len(reasons), reasons, error=error)
            reasons.append(reason)
            self.sleep(self.retry.delay(attempt, response))
        raise AssertionError("unreachable")  # pragma: no cover

    def call(self, method: str, path: str, payload: Any = None) -> Any:
        """``send`` and return the parsed 2xx body; raise ``ApiError`` otherwise."""
        got = self.send(method, path, payload)
        if got.response is None:
            raise ConnectionError(f"{method} {path}: {got.error}")
        if not 200 <= got.response.status < 300:
            raise ApiError(method, path, got.response)
        return got.response.json()

    # --- the calls the folder module uses -----------------------------------

    def get_world(self) -> dict[str, Any]:
        data = self.call("GET", "world/")
        if not isinstance(data, dict) or "id" not in data:
            raise ValueError(f"GET /world returned no world object: {str(data)[:200]}")
        return data

    def iter_elements(self, element_type: str, *, limit: int = 200) -> Iterator[dict[str, Any]]:
        cursor: str | None = None
        while True:
            query = f"{element_type}/?limit={limit}"
            if cursor:
                query += "&cursor=" + urllib.parse.quote(cursor, safe="")
            page = self.call("GET", query)
            yield from page.get("data", [])
            if not page.get("has_more"):
                return
            cursor = page["next_cursor"]
            if not cursor:
                raise ValueError(f"{element_type}: has_more without next_cursor")

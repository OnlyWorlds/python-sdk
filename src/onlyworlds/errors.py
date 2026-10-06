"""Errors from the OnlyWorlds v2 API, told apart the way the server tells them apart.

keel answers every error with one envelope, ``{"error": {type, code, message, param,
doc_url}}``, and a machine ``code`` is the stable part (keel spec §9). ``ApiError``
parses it, whichever of the known envelope shapes arrives, and names the cases a
caller acts on differently. The same names exist on the TypeScript SDK's
``OwApiError`` (``isIdConflict``, ``isNotAuthor``, ``isBusy`` ...).
"""

from __future__ import annotations

import email.utils
import json
import re
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .http import Response

__all__ = ["ApiError", "error_code", "parse_retry_after"]

_DELAY_SECONDS = re.compile(r"^[0-9]+$")


def parse_retry_after(value: str | None, now: float | None = None) -> float | None:
    """``Retry-After`` as seconds: a whole-number delay, or an HTTP date turned into one. Anything else is None.

    Strict on purpose: ``1.5``, ``-1``, ``+5``, ``5.0`` and prose are None, never
    "retry now" (a malformed header must not become a zero wait).
    """
    if value is None:
        return None
    text = value.strip()
    if _DELAY_SECONDS.match(text):
        return float(int(text))
    try:
        parsed = email.utils.parsedate_to_datetime(text)
    except (TypeError, ValueError, IndexError):
        return None
    if parsed is None:  # pragma: no cover - older Pythons return None instead of raising
        return None
    return max(0.0, parsed.timestamp() - (time.time() if now is None else now))


def _envelope(body: bytes) -> dict[str, Any]:
    try:
        data = json.loads(body.decode("utf-8")) if body else None
    except (UnicodeDecodeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def error_code(body: bytes) -> str | None:
    """The machine ``code`` of an error body, whichever envelope shape carries it; None when there is none."""
    env = _envelope(body)
    raw_error = env.get("error")
    nested: dict[str, Any] = raw_error if isinstance(raw_error, dict) else {}
    code = env.get("code") or nested.get("code") or (raw_error if isinstance(raw_error, str) else None)
    return code if isinstance(code, str) else None


class ApiError(Exception):
    """A non-2xx answer. ``status`` and ``response`` always; the rest comes from the envelope when there is one."""

    def __init__(self, method: str, path: str, response: Response):
        self.method = method
        self.path = path
        self.status = response.status
        self.response = response
        env = _envelope(response.body)
        raw_error = env.get("error")
        nested: dict[str, Any] = raw_error if isinstance(raw_error, dict) else {}
        self.code: str | None = error_code(response.body)
        etype = env.get("type") or nested.get("type")
        self.type: str | None = etype if isinstance(etype, str) else None
        param = env.get("param") if env.get("param") is not None else nested.get("param")
        self.param: str | None = param if isinstance(param, str) else None
        doc = env.get("doc_url") or nested.get("doc_url")
        self.doc_url: str | None = doc if isinstance(doc, str) else None
        msg = env.get("message") or nested.get("message")
        self.api_message: str | None = msg if isinstance(msg, str) else None
        self.retry_after: float | None = parse_retry_after(response.header("Retry-After"))
        detail = response.body[:300].decode("utf-8", "replace")
        super().__init__(f"{method} {path} -> {response.status}: {detail}")

    @property
    def is_auth_error(self) -> bool:
        """``world_gone`` is reserved: keel never emits it (a deleted world's key reads as ``invalid_credentials``)."""
        return self.code in ("invalid_credentials", "key_revoked", "world_gone")

    @property
    def is_validation_error(self) -> bool:
        """422 and 400 name the offending field or parameter in ``param``."""
        return self.status in (400, 422)

    @property
    def is_idempotency_conflict(self) -> bool:
        """The same Idempotency-Key was reused with a different body (409 ``idempotency_error``)."""
        return self.status == 409 and self.code == "idempotency_error"

    @property
    def is_id_conflict(self) -> bool:
        """The id is already taken (409 ``id_conflict``). Retrying will not help; the id is the problem."""
        return self.status == 409 and self.code == "id_conflict"

    @property
    def is_not_author(self) -> bool:
        """A contributor changed an element someone else created (403 ``not_author``, keel D72)."""
        return self.status == 403 and self.code == "not_author"

    @property
    def is_owner_only(self) -> bool:
        """A member key (a co-builder's too) tried what only the owner may do, such as ``patch_world`` (403)."""
        return self.status == 403 and self.code == "owner_only"

    @property
    def is_permission_error(self) -> bool:
        """The key is valid but lacks the scope (403 ``permission_error``): a read key on a write
        route, or a member key on a surface that refuses members. Retrying will not help."""
        return self.status == 403 and self.code == "permission_error"

    @property
    def is_resync_required(self) -> bool:
        """``/changes`` refused the cursor (409 ``resync_required``): a guest's view of the world
        changed, or the key's role did (a guest's cursor has another shape). Drop the cursor,
        walk again from the start, and REPLACE the local copy: what the key no longer sees must go."""
        return self.status == 409 and self.code == "resync_required"

    @property
    def is_busy(self) -> bool:
        """keel's admission control turned the request away (503 ``server_busy``); see ``retry_after``."""
        return self.status == 503 and self.code == "server_busy"

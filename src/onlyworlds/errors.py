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
    def is_idempotency_in_flight(self) -> bool:
        """A request with this Idempotency-Key is still running (409 ``idempotency_in_flight``).
        The client retries it by itself; seen here only when the retries ran out."""
        return self.status == 409 and self.code == "idempotency_in_flight"

    @property
    def is_id_conflict(self) -> bool:
        """The id is already taken (409 ``id_conflict``). Retrying will not help; the id is the problem."""
        return self.status == 409 and self.code == "id_conflict"

    @property
    def is_not_author(self) -> bool:
        """A contributor changed an element someone else created (403 ``not_author``)."""
        return self.status == 403 and self.code == "not_author"

    @property
    def is_owner_only(self) -> bool:
        """A member key (a co-builder's too) tried what only the owner may do, such as ``patch_world`` (403)."""
        return self.status == 403 and self.code == "owner_only"

    @property
    def is_view_as_owner_only(self) -> bool:
        """A member key sent ``view_as`` (403 ``view_as_owner_only``): reading as another
        reader is the owner's, from a key with no member. Only while keel's hidden mark is on; until
        then ``as`` is an unknown parameter (422)."""
        return self.status == 403 and self.code == "view_as_owner_only"

    @property
    def is_known_of_not_writable(self) -> bool:
        """A write body carried ``known_of`` (422 ``known_of_not_writable``, ``param`` known_of; keel
        PR 117): a stub is never written back. The client refuses a ``known_of: true`` body before
        sending and never sends another value of it, so this comes only from a body sent around it."""
        return self.status == 422 and self.code == "known_of_not_writable"

    @property
    def is_hidden_not_allowed(self) -> bool:
        """A create carried ``hidden: true`` from a key that may not hide (403 ``hidden_not_allowed``):
        only the owner's keys and a co-builder's (a person's or a seat's) create an element
        hidden. Nothing was created. Never retried, never resent without the mark (that would publish
        it): leave the element out, or ask a keeper. A server with the hidden mark off answers ``true``
        with a 422 instead (``param`` hidden), nothing created either."""
        return self.status == 403 and self.code == "hidden_not_allowed"

    @property
    def is_permission_error(self) -> bool:
        """The key is valid but lacks the scope (403 ``permission_error``): a read key on a write
        route, or a member key on a surface that refuses members. Retrying will not help."""
        return self.status == 403 and self.code == "permission_error"

    @property
    def is_resync_required(self) -> bool:
        """``/changes`` refused the cursor (409 ``resync_required``): what this key may see changed
        (a guest's slice moved; an element hidden from a contributor was unhidden; the key's role
        moved to or from guest or contributor, whose cursors have other shapes). Drop the
        cursor and walk again from the start. What to do with what the local copy holds that the new
        walk does not name is ``resync_reason``'s: ``role``, keep it; ``view``, drop it. Without a
        reason (keel's hidden mark off), keep it: a reset never empties a copy (keel PR 104; sharing
        is forward-only). Never empty the copy on your own."""
        return self.status == 409 and self.code == "resync_required"

    @property
    def resync_reason(self) -> str | None:
        """Why ``/changes`` refused the cursor, from the 409 ``resync_required`` envelope's ``reason``
        (only while keel's hidden mark is on): ``"role"`` (this key's own role or membership
        moved: keep what the local copy holds that the new walk does not name; it is out of view now,
        not gone) or ``"view"`` (something left this key's view: a delete, a hide, an unhide, a
        Character change; drop what the new walk does not name). When both happened since the
        cursor, keel says ``"role"``. None for any other error, or when keel sends no reason."""
        if not self.is_resync_required:
            return None
        raw_error = _envelope(self.response.body).get("error")
        reason = raw_error.get("reason") if isinstance(raw_error, dict) else None
        return reason if reason in ("role", "view") else None

    @property
    def is_busy(self) -> bool:
        """keel's admission control turned the request away (503 ``server_busy``); see ``retry_after``."""
        return self.status == 503 and self.code == "server_busy"

    @property
    def is_precondition_failed(self) -> bool:
        """A write sent with ``if_match`` found the element moved past that ``change_seq``
        (412 ``precondition_failed``): nothing written, nothing merged. The error is a
        ``PreconditionFailed``, whose ``current`` is the element as it is now."""
        return self.status == 412 and self.code == "precondition_failed"

    @property
    def is_proposed(self) -> bool:
        """The write was held as a proposal (202): the world takes this agent seat's writes
        as proposals, and the element did not change. The error is a ``ProposedError``, whose
        ``proposal`` is the row a keeper (the owner or a co-builder) accepts or declines."""
        return self.status == 202

    @property
    def is_field_not_visible(self) -> bool:
        """A proposal named a field this key's view of the element does not hold: it reads the element
        as a known-of stub (422 ``field_not_visible``; ``param`` names the field)."""
        return self.status == 422 and self.code == "field_not_visible"

    @property
    def is_too_many_open(self) -> bool:
        """This proposer already has 5 open proposals on the element, or 50 in the world (422
        ``too_many_open``): wait for a keeper, or withdraw one. A lapsed one no longer counts."""
        return self.status == 422 and self.code == "too_many_open"

    @property
    def is_stale_proposal(self) -> bool:
        """An accept found a proposed field moved since the proposal was made (409 ``stale_proposal``):
        nothing written, the row stays open. The error is a ``StaleProposal``, whose
        ``conflicts`` and ``current`` say what moved."""
        return self.status == 409 and self.code == "stale_proposal"

    @property
    def is_proposed_only(self) -> bool:
        """The world takes this agent seat's writes as proposals, and the act has no proposal form (403
        ``proposed_only``): deleting an element the seat did not create, or accepting or
        declining a proposal. Propose instead, or ask a keeper. Also the review of a new element by
        the member its ``x_review_proposed`` mark names, on any world."""
        return self.status == 403 and self.code == "proposed_only"

    @property
    def is_not_proposed(self) -> bool:
        """A review found no ``x_review_proposed`` mark on the element (422 ``not_proposed``):
        nothing to settle, never marked or already accepted."""
        return self.status == 422 and self.code == "not_proposed"

    @property
    def is_own_proposal(self) -> bool:
        """A keeper tried to accept or decline their own proposal (403 ``own_proposal``):
        another keeper decides it."""
        return self.status == 403 and self.code == "own_proposal"


class PreconditionFailed(ApiError):
    """412 ``precondition_failed``: the element changed since the ``change_seq`` sent as
    ``if_match``. ``current`` is the element as it is now, as this key sees it (None if a response
    ever lacks it). The check is per element and the server never merges: compare the copy you
    edited from with ``current``; when the fields you changed are not the ones that moved, send
    again with ``if_match=current["change_seq"]``; when the same field moved on both sides, ask."""

    def __init__(self, method: str, path: str, response: Response):
        super().__init__(method, path, response)
        cur = _envelope(response.body).get("current")
        self.current: dict[str, Any] | None = cur if isinstance(cur, dict) else None


class StaleProposal(ApiError):
    """409 ``stale_proposal``: an accept found that a field the proposal names has moved
    since it was made. Nothing was written and the proposal stays open. ``conflicts`` holds one
    ``{field, base, current}`` per moved field (empty if a response ever lacks it); ``current`` is the
    element as it is now (None if missing). A change to a field the proposal does not name never
    counts. The proposer proposes again on the current text."""

    def __init__(self, method: str, path: str, response: Response):
        super().__init__(method, path, response)
        env = _envelope(response.body)
        raw = env.get("conflicts")
        self.conflicts: list[dict[str, Any]] = [c for c in raw if isinstance(c, dict)] if isinstance(raw, list) else []
        cur = env.get("current")
        self.current: dict[str, Any] | None = cur if isinstance(cur, dict) else None


class ProposedError(ApiError):
    """A write answered 202: the world takes this agent seat's writes as proposals (its
    owner's setting, ``agent_writes_proposed`` on ``GET /world``), so the element did NOT change.
    ``proposal`` is the row the write became (None if a response ever lacks it): since 2026-10-23 its
    ``fields`` holds only what differs, and a PUT's ``omitted`` names the fields it would empty. A
    keeper accepts or declines it. Raised, not returned, so that no caller takes the answer for the element: a PATCH,
    PUT or link edit that returned normally changed the element; this one did not. ``status`` is 202
    and ``code`` None. A ``/bulk`` slot that says 202 is not raised: it stays in the result."""

    def __init__(self, method: str, path: str, response: Response):
        super().__init__(method, path, response)
        raw = _envelope(response.body).get("proposal")
        self.proposal: dict[str, Any] | None = raw if isinstance(raw, dict) else None
        pid = self.proposal.get("id") if self.proposal else None
        self.args = (
            f"{method} {path} -> 202: proposed, not applied (proposal {pid}): this world takes this "
            "agent seat's writes as proposals, and a keeper accepts or declines them",
        )


def api_error(method: str, path: str, response: Response) -> ApiError:
    """The right ``ApiError`` for an answer that is not the element: ``ProposedError`` for a 202,
    ``PreconditionFailed`` for a 412 ``precondition_failed``, ``StaleProposal`` for a 409 ``stale_proposal``."""
    if response.status == 202:
        return ProposedError(method, path, response)
    code = error_code(response.body)
    if response.status == 412 and code == "precondition_failed":
        return PreconditionFailed(method, path, response)
    if response.status == 409 and code == "stale_proposal":
        return StaleProposal(method, path, response)
    return ApiError(method, path, response)

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from onlyworlds.http import Client, Response, RetryPolicy

Handler = Callable[[str, str, Mapping[str, str], bytes | None], Response | Exception]


@dataclass
class Call:
    method: str
    url: str
    headers: dict[str, str]
    body: Any


@dataclass
class FakeTransport:
    """Scripted HTTP. ``script`` answers in order; ``handler`` answers when the script is empty."""

    script: list[Response | Exception] = field(default_factory=list)
    handler: Handler | None = None
    calls: list[Call] = field(default_factory=list)

    def __call__(
        self, method: str, url: str, headers: Mapping[str, str], body: bytes | None, timeout: float
    ) -> Response:
        self.calls.append(Call(method, url, dict(headers), json.loads(body) if body else None))
        if self.script:
            nxt = self.script.pop(0)
        elif self.handler is not None:
            nxt = self.handler(method, url, headers, body)
        else:
            raise AssertionError(f"unexpected call {method} {url}")
        if isinstance(nxt, Exception):
            raise nxt
        return nxt


def jresp(status: int, data: Any, headers: Mapping[str, str] | None = None) -> Response:
    return Response(status, json.dumps(data).encode("utf-8"), dict(headers or {}))


@pytest.fixture
def sleeps() -> list[float]:
    return []


@pytest.fixture
def make_client(sleeps: list[float]) -> Callable[[FakeTransport], Client]:
    def make(transport: FakeTransport, attempts: int = 6) -> Client:
        return Client(
            "ow_w_testkey",
            "1234",
            transport=transport,
            sleep=sleeps.append,
            retry=RetryPolicy(attempts=attempts),
        )

    return make


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(data, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))

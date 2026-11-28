"""An answer cut off while its body is read is no answer, never a value read from part of a body.

The default transport reads the whole body inside the request (``UrllibTransport``), so a connection that
drops before a body declared by ``Content-Length``, or before a chunked body's last chunk, raises there and
the client answers ``ConnectionError``, as for a request that never reached the server. Held here against
a real socket on 127.0.0.1, as the TypeScript SDK 4.223.1 holds its body read and the engine SDKs theirs.
"""

from __future__ import annotations

import socket
import threading
from collections.abc import Iterator

import pytest

from onlyworlds.http import Client, RetryPolicy

ID = "11111111-2222-4333-8444-555555555555"
WHOLE = b'{"id": "' + ID.encode() + b'", "name": "K"}'


def head(*lines: str) -> bytes:
    return ("\r\n".join(["HTTP/1.1 200 OK", "Content-Type: application/json", *lines]) + "\r\n\r\n").encode()


# What the server sends for one request, then it closes the connection.
CUT_LENGTH = head("Content-Length: 100") + WHOLE[:10]
CUT_CHUNKED = head("Transfer-Encoding: chunked") + b"a\r\n" + WHOLE[:10] + b"\r\n"
WHOLE_LENGTH = head(f"Content-Length: {len(WHOLE)}") + WHOLE
WHOLE_TO_CLOSE = head("Connection: close") + WHOLE


def serve(answer: bytes) -> Iterator[str]:
    """A one-request server on 127.0.0.1 that reads the request's head, sends ``answer`` and closes."""
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    port = listener.getsockname()[1]

    def run() -> None:
        conn, _ = listener.accept()
        with conn:
            got = b""
            while b"\r\n\r\n" not in got:
                part = conn.recv(4096)
                if not part:
                    break
                got += part
            conn.sendall(answer)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}/api/v2"
    finally:
        thread.join(timeout=5)
        listener.close()


def client(base_url: str) -> Client:
    return Client("ow_w_testkey", "1234", base_url=base_url, retry=RetryPolicy(attempts=1), timeout=5)


@pytest.mark.parametrize("answer", [CUT_LENGTH, CUT_CHUNKED], ids=["short-of-content-length", "chunked-no-last-chunk"])
def test_a_cut_off_answer_is_no_answer(answer: bytes) -> None:
    for base_url in serve(answer):
        with pytest.raises(ConnectionError, match=r"^GET character/.*: gave up after 0 retries: IncompleteRead"):
            client(base_url).get("character", ID)


@pytest.mark.parametrize("answer", [WHOLE_LENGTH, WHOLE_TO_CLOSE], ids=["content-length-met", "read-to-close"])
def test_a_whole_answer_is_the_value(answer: bytes) -> None:
    for base_url in serve(answer):
        assert client(base_url).get("character", ID) == {"id": ID, "name": "K"}

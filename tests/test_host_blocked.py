"""The host in front of onlyworlds.com refuses some writes before the API sees them: a 403 whose body is an HTML page
titled "Blocked", not the JSON envelope (measured on the production practice world 2026-11-16: a description holding a
backticked ``python -m`` was refused, the same text with ``python3 -m`` was created). The error says so in words a
person can act on, ``is_host_blocked`` is true, ``code`` stays None and the page stays on ``response.body``; any other
403, an HTML page with another title, and the same page on another status read as before. The cases are the npm SDK's
``test/host-blocked.test.mjs``."""

import json

from onlyworlds.errors import HOST_BLOCKED_MESSAGE, ApiError
from onlyworlds.http import Response

# the head of the page the host served, as measured
PAGE = (
    b'<!DOCTYPE html>\n<html lang="en">\n  <head>\n    <meta charset="utf-8" />\n'
    b'    <meta name="viewport" content="width=device-width, initial-scale=1" />\n    <title>Blocked</title>\n'
    b"    <style>body{}</style>\n  </head>\n  <body><h1>Blocked</h1></body>\n</html>\n"
)


def err(status: int, body: bytes) -> ApiError:
    return ApiError("POST", "character/", Response(status, body))


def test_the_hosts_page_is_read_as_its_refusal_with_a_message_to_act_on() -> None:
    e = err(403, PAGE)
    assert e.is_host_blocked is True
    assert e.status == 403
    assert e.code is None
    assert e.doc_url is None
    assert e.response.body == PAGE
    assert str(e) == f"POST character/ -> 403: {HOST_BLOCKED_MESSAGE}"
    assert HOST_BLOCKED_MESSAGE.startswith("The host in front of onlyworlds.com refused this request before the API")
    assert "nothing was written" in HOST_BLOCKED_MESSAGE
    assert "a backtick, a semicolon or a pipe" in HOST_BLOCKED_MESSAGE
    assert "fenced code block whose first line names a language" in HOST_BLOCKED_MESSAGE
    assert "<" not in str(e)
    assert e.is_auth_error is False
    assert e.is_not_author is False


def test_the_title_is_read_whatever_its_case_and_spacing_and_with_attributes() -> None:
    for title in (b"<title>blocked</title>", b"<title>  Blocked\n</title>", b'<TITLE lang="en">Blocked</TITLE>'):
        assert err(403, b"<html><head>" + title + b"</head></html>").is_host_blocked is True, title


def test_the_apis_own_403_envelope_reads_as_before_a_message_naming_blocked_included() -> None:
    env = {"error": {"type": "permission_error", "code": "not_author", "message": "Blocked: you did not create it."}}
    e = err(403, json.dumps(env).encode())
    assert e.is_host_blocked is False
    assert e.is_not_author is True
    assert e.api_message == "Blocked: you did not create it."


def test_another_title_another_status_and_a_json_answer_are_not_the_hosts_refusal() -> None:
    assert err(403, PAGE.replace(b"<title>Blocked</title>", b"<title>Forbidden</title>")).is_host_blocked is False
    assert err(502, PAGE).is_host_blocked is False
    assert err(429, PAGE).is_host_blocked is False
    assert err(403, json.dumps({"title": "<title>Blocked</title>"}).encode()).is_host_blocked is False
    # a JSON answer is never the page, even one whose text would hold the title
    assert err(403, json.dumps(["<title>Blocked</title>"]).encode()).is_host_blocked is False
    # a JSON string is read as its text, in both packages
    assert err(403, json.dumps("<title>Blocked</title>").encode()).is_host_blocked is True
    # a page body under the title alone, with no title element, is not read as one
    assert err(403, b"<html><body><h1>Blocked</h1></body></html>").is_host_blocked is False
    assert err(403, b"").is_host_blocked is False

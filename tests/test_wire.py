"""The client against keel's own OpenAPI document.

Set ``OW_OPENAPI`` to the document's URL (``https://www.onlyworlds.com/api/v2/openapi.json``) or a
saved copy; without it these tests skip. The client is run against a recording transport and
what it sends and knows is compared with what the document describes: routes, query parameters,
each type's fields and their kinds, what a write must not carry, the list envelope's names and
the error envelope.

Blind spots, because the document gives no schema for them: the ``/changes`` response (its
parameters, the head poll's ``If-None-Match`` and its 304 are declared and checked here),
``/bulk`` (request and response) and the world-meta body. Those are covered by the
scripted tests in ``test_client.py``, not here.
"""

from __future__ import annotations

import gzip
import json
import os
import pathlib
import tempfile
import urllib.error
import urllib.request
from collections.abc import Mapping
from typing import Any

import pytest
from conftest import FakeTransport, jresp

import onlyworlds.http as _http
from onlyworlds import ELEMENT_TYPES, FIELD_KINDS, ApiError, Client

SOURCE = os.environ.get("OW_OPENAPI")
pytestmark = pytest.mark.skipif(not SOURCE, reason="set OW_OPENAPI to keel's OpenAPI document (URL or file)")

ID = "018f0000-0000-7000-8000-000000000001"
# The fields keel keeps that the schema does not carry, read from the package itself, never a list kept
# here: the read-only fields it strips before a write (a hand list missed `known_of`, keel PR 113, the
# hour it went live), plus the ones keel ignores on write and the id.
SERVER_MANAGED = (set(_http.READ_ONLY_FIELDS) - {"world"}) | {
    "id",
    "created_by",
    "changed_by",
    "changed_via",
    "changed_client",
}
KIND = {"text": "string", "integer": "integer", "multi_link": "array", "single_link": "string"}


def _load() -> dict[str, Any]:
    assert SOURCE
    if SOURCE.startswith(("http://", "https://")):
        # The document is 2 MB plain, 181 KB gzipped: ask for gzip (keel's bandwidth watch, h29 #9808),
        # and send the last ETag back as received (keel #538): an unchanged document is a 304 and 0 bytes,
        # served from a cache file beside the system's temp dir. CI has no cache, so it reads fresh once.
        cache = pathlib.Path(tempfile.gettempdir()) / "onlyworlds-wire-openapi.json"
        cached: dict[str, Any] | None = None
        if cache.exists():
            try:
                cached = json.loads(cache.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                cached = None
        headers = {"Accept-Encoding": "gzip"}
        if cached and cached.get("url") == SOURCE and cached.get("etag"):
            headers["If-None-Match"] = cached["etag"]
        req = urllib.request.Request(SOURCE, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                raw = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    raw = gzip.decompress(raw)
                doc: dict[str, Any] = json.loads(raw)
                etag = r.headers.get("ETag")
            if etag:
                cache.write_text(json.dumps({"url": SOURCE, "etag": etag, "body": doc}), encoding="utf-8")
        except urllib.error.HTTPError as e:
            if e.code == 304 and cached and cached.get("body"):
                doc = cached["body"]
            else:
                raise
    else:
        with open(SOURCE, encoding="utf-8") as f:
            doc = json.load(f)
    return doc


@pytest.fixture(scope="module")
def doc() -> dict[str, Any]:
    d = _load()
    assert d["paths"] and d["components"]["schemas"]
    return d


def _norm(url: str) -> str:
    path = url.split("?", 1)[0].removeprefix("https://www.onlyworlds.com").rstrip("/")
    parts = [p for p in path.split("/") if p]
    if len(parts) > 2 and parts[2] in ELEMENT_TYPES:
        if len(parts) > 3:
            parts[3] = "{id}"
        if len(parts) > 5 and parts[4] == "links":
            parts[5] = "{field}"
        if len(parts) > 5 and parts[4] == "proposals":
            parts[5] = "{pid}"
    return "/" + "/".join(parts)


def _json_type(schema: Mapping[str, Any]) -> str:
    t = schema.get("type")
    kinds = [x for x in (t if isinstance(t, list) else [t]) if x != "null"]
    return "|".join(str(k) for k in kinds)


def _recorder() -> tuple[Client, FakeTransport]:
    everything = {
        "id": ID,
        "name": "x",
        "data": [],
        "has_more": False,
        "next_cursor": None,
        "items": [],
        "changes": [],
        "head": 0,
        "proposal": {"id": ID},
        "element": {"id": ID},
    }
    t = FakeTransport(handler=lambda *a: jresp(200, everything))
    return Client("ow_w_testkey", "1234", transport=t), t


def test_every_route_and_query_parameter_the_client_sends_exists(doc: dict[str, Any]) -> None:
    c, t = _recorder()
    c.health()
    c.me()
    c.get_world()
    c.patch_world({"name": "x"})
    c.bulk([{"type": "character", "element": {"name": "x"}}])
    c.changes(since="c", limit=1, after="2026-10-22T00:00:00Z")
    c.head()
    c.world_proposals(state="all", since="2026-10-22T00:00:00Z", element=ID, limit=1, cursor="c")
    for ty in ELEMENT_TYPES:
        c.list_page(
            ty, limit=1, cursor="c", expand=["a"], fields=["name"], filter={"name__icontains": "a", "supertype": "b"}
        )
        c.get(ty, ID, expand=["a"], fields=["name"])
        c.create(ty, {"name": "x"})
        c.upsert(ty, ID, {"name": "x"})
        c.patch(ty, ID, {"name": "x"})
        c.delete(ty, ID)
        c.edit_links(ty, ID, "friends", add=[ID])
        c.propose(ty, ID, {"name": "x"}, evidence="e", expires="2026-12-01T00:00:00Z")
        c.list_proposals(ty, ID, state="all", since="2026-10-22T00:00:00Z", limit=1, cursor="c")
        c.accept_proposal(ty, ID, ID)
        c.decline_proposal(ty, ID, ID, reason="r")
        c.withdraw_proposal(ty, ID, ID)
    problems: list[str] = []
    for call in t.calls:
        op = doc["paths"].get(_norm(call.url), {}).get(call.method.lower())
        if op is None:
            problems.append(f"{call.method} {_norm(call.url)} is not in the document")
            continue
        if call.method == "GET":
            listed = {p["name"] for p in op.get("parameters", []) if p["in"] == "query"}
            sent = {q.split("=")[0] for q in call.url.split("?", 1)[1].split("&")} if "?" in call.url else set()
            problems += [f"{call.method} {_norm(call.url)} sends ?{q}, not listed" for q in sorted(sent - listed)]
    assert not problems, "\n".join(problems[:20])


def test_the_proposal_calls_send_only_declared_headers_and_bodies(doc: dict[str, Any]) -> None:
    """keel #519: each proposal call's extra headers are parameters of its operation, and each body's
    keys are properties of its request schema (which allow no others)."""
    c, t = _recorder()
    c.propose("location", ID, {"name": "x"}, evidence="e", expires="2026-12-01T00:00:00Z")
    c.accept_proposal("location", ID, ID)
    c.decline_proposal("location", ID, ID, reason="r")
    c.withdraw_proposal("location", ID, ID)
    base = set(c._headers) | {"Content-Type"}
    problems: list[str] = []
    for call in t.calls:
        op = doc["paths"][_norm(call.url)][call.method.lower()]
        declared = {p["name"] for p in op.get("parameters", []) if p["in"] == "header"}
        problems += [
            f"{call.method} {_norm(call.url)} sends {h}, not declared" for h in set(call.headers) - base - declared
        ]
        if call.body is not None:
            schema = op["requestBody"]["content"]["application/json"]["schema"]
            problems += [
                f"{_norm(call.url)} sends `{k}`, not in its body" for k in set(call.body) - set(schema["properties"])
            ]
    assert not problems, "\n".join(problems)
    assert "Idempotency-Key" in t.calls[0].headers and "X-OW-Client" in t.calls[1].headers


def test_the_202_and_the_five_codes_are_what_the_client_reads(doc: dict[str, Any]) -> None:
    """A held write answers 202 with the Proposed shape on PUT, PATCH and links, and a /bulk slot may say
    202 beside a `proposal`; each code a predicate names has the status that predicate checks."""
    from onlyworlds import ProposedError

    paths, schemas = doc["paths"], doc["components"]["schemas"]
    for route, method in [("/api/v2/location/{id}", "put"), ("/api/v2/location/{id}", "patch"),
                          ("/api/v2/location/{id}/links/{field}", "post")]:  # fmt: skip
        got = paths[route][method]["responses"]["202"]["content"]["application/json"]["schema"]
        assert got == {"$ref": "#/components/schemas/Proposed"}, (route, method)
    assert schemas["Proposed"]["required"] == ["proposal"]
    assert {"proposal", "status", "id"} <= set(schemas["BulkResult"]["properties"]["items"]["items"]["properties"])
    codes = schemas["Error"]["x-ow-error-codes"]
    predicates = {
        "field_not_visible": (422, "is_field_not_visible"),
        "too_many_open": (422, "is_too_many_open"),
        "stale_proposal": (409, "is_stale_proposal"),
        "proposed_only": (403, "is_proposed_only"),
        "own_proposal": (403, "is_own_proposal"),
    }
    for code, (status, flag) in predicates.items():
        assert codes[code]["status"] == status, code
        assert getattr(ApiError("POST", "x", jresp(status, {"error": {"code": code}})), flag), code
    accepted = paths["/api/v2/location/{id}/proposals/{pid}/accept"]["post"]["responses"]["409"]
    beside = accepted["content"]["application/json"]["schema"]["allOf"][1]
    assert set(beside["required"]) == {"conflicts", "current"}
    t = FakeTransport(handler=lambda *a: jresp(202, {"proposal": {"id": ID}}))
    with pytest.raises(ProposedError):
        Client("ow_w_testkey", "1234", transport=t).patch("location", ID, {"name": "x"})


def test_the_proposal_list_envelope_is_the_one_the_walk_follows(doc: dict[str, Any]) -> None:
    props = doc["components"]["schemas"]["ProposalList"]["properties"]
    assert set(props) == {"data", "has_more", "next_cursor"}
    world = doc["components"]["schemas"]["World"]["properties"]["agent_writes_proposed"]
    assert world.get("readOnly") is True and "agent_writes_proposed" in _http.WORLD_READ_ONLY_FIELDS


def test_the_head_poll_header_and_its_304_are_declared(doc: dict[str, Any]) -> None:
    """keel #518: ``head()`` sends ``If-None-Match`` and reads a 304 with an ``ETag`` on GET /changes."""
    t = FakeTransport(
        script=[jresp(200, {"head": 3, "cursor": 3, "epoch": None}, {"ETag": '"3:-"'}), _http.Response(304, b"", {})]
    )
    c = Client("ow_w_testkey", "1234", transport=t)
    c.head()
    c.head()
    sent = set(t.calls[1].headers) - set(t.calls[0].headers)
    op = doc["paths"][_norm(t.calls[1].url)]["get"]
    declared = {p["name"] for p in op.get("parameters", []) if p["in"] == "header"}
    assert sent == {"If-None-Match"} and sent <= declared
    assert "ETag" in op["responses"]["304"].get("headers", {})


def test_fields_and_kinds_equal_the_read_schemas_both_ways(doc: dict[str, Any]) -> None:
    schemas = doc["components"]["schemas"]
    problems: list[str] = []
    for ty in ELEMENT_TYPES:
        props = schemas[ty.capitalize()]["properties"]
        known = set(FIELD_KINDS[ty]) | SERVER_MANAGED
        problems += [
            f"{ty}: the document returns `{k}`, the package does not know it" for k in sorted(set(props) - known)
        ]
        problems += [
            f"{ty}: the package knows `{k}`, the document does not return it" for k in sorted(known - set(props))
        ]
        for field, kind in FIELD_KINDS[ty].items():
            if field in props and _json_type(props[field]) != KIND[kind]:
                problems.append(f"{ty}.{field}: package says {kind}, document says {_json_type(props[field])}")
        required = sorted(schemas[ty.capitalize() + "Write"].get("required", []))
        if required != ["name"]:
            problems.append(f"{ty}: the write schema requires {required}, the package assumes ['name']")
    assert not problems, "\n".join(problems[:20])


def test_a_write_never_carries_what_the_write_schema_refuses(doc: dict[str, Any]) -> None:
    schemas = doc["components"]["schemas"]
    c, t = _recorder()
    body = {
        "name": "x",
        "world": "w",
        "type": "t",
        "created_at": "a",
        "updated_at": "b",
        "change_seq": 1,
        "created_by": None,
    }
    for ty in ELEMENT_TYPES:
        c.upsert(ty, ID, body)
        refused = set(schemas[ty.capitalize()]["properties"]) - set(schemas[ty.capitalize() + "Write"]["properties"])
        leaked = refused & set(t.calls[-1].body)
        assert not leaked, f"{ty}: a write still carries {sorted(leaked)}"


def test_the_list_envelope_names_are_the_ones_iter_elements_follows(doc: dict[str, Any]) -> None:
    names: dict[str, str] = {}
    for key, schema in doc["components"]["schemas"]["CharacterList"]["properties"].items():
        t = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        names["data" if "array" in t else "more" if "boolean" in t else "next"] = key
    assert set(names) == {"data", "more", "next"}
    pages = [
        jresp(200, {names["data"]: [{"id": "1"}], names["more"]: True, names["next"]: "CURSOR-1"}),
        jresp(200, {names["data"]: [{"id": "2"}], names["more"]: False, names["next"]: None}),
    ]
    t = FakeTransport(script=list(pages))
    got = [e["id"] for e in Client("ow_w_testkey", transport=t).iter_elements("character")]
    assert got == ["1", "2"] and "cursor=CURSOR-1" in t.calls[1].url


def test_every_key_of_the_error_envelope_reaches_apierror(doc: dict[str, Any]) -> None:
    err = doc["components"]["schemas"]["Error"]["properties"]["error"]
    five = {"type", "code", "message", "param", "doc_url"}
    # keel #421 PR 103: with the hidden mark on, a 409 resync_required's envelope also carries `reason`.
    assert set(err["properties"]) in (five, five | {"reason"})
    if "reason" in err["properties"]:
        resync = {
            "error": {
                "type": "invalid_request",
                "code": "resync_required",
                "message": "m",
                "param": "since",
                "doc_url": "https://x/e",
                "reason": "role",
            }
        }
        assert ApiError("GET", "x", jresp(409, resync)).resync_reason == "role"
    first_type = err["properties"]["type"]["enum"][0]
    body = {"error": {"type": first_type, "code": "probe", "message": "m", "param": "p", "doc_url": "https://x/e"}}
    e = ApiError("GET", "x", jresp(422, body))
    assert (e.type, e.code, e.api_message, e.param, e.doc_url) == (first_type, "probe", "m", "p", "https://x/e")

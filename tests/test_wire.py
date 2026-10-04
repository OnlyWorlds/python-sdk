"""The client against keel's own OpenAPI document.

Set ``OW_OPENAPI`` to the document's URL (``https://www.onlyworlds.com/api/v2/openapi.json``) or a
saved copy; without it these tests skip. The client is run against a recording transport and
what it sends and knows is compared with what the document describes: routes, query parameters,
each type's fields and their kinds, what a write must not carry, the list envelope's names and
the error envelope.

Blind spots, because the document gives no schema for them: ``/changes`` (parameters and
response), ``/bulk`` (request and response) and the world-meta body. Those are covered by the
scripted tests in ``test_client.py``, not here.
"""

from __future__ import annotations

import json
import os
import urllib.request
from collections.abc import Mapping
from typing import Any

import pytest
from conftest import FakeTransport, jresp

from onlyworlds import ELEMENT_TYPES, FIELD_KINDS, ApiError, Client

SOURCE = os.environ.get("OW_OPENAPI")
pytestmark = pytest.mark.skipif(not SOURCE, reason="set OW_OPENAPI to keel's OpenAPI document (URL or file)")

ID = "018f0000-0000-7000-8000-000000000001"
SERVER_MANAGED = {"id", "type", "created_at", "updated_at", "change_seq", "created_by"}
KIND = {"text": "string", "integer": "integer", "multi_link": "array", "single_link": "string"}


def _load() -> dict[str, Any]:
    assert SOURCE
    if SOURCE.startswith(("http://", "https://")):
        with urllib.request.urlopen(SOURCE, timeout=30) as r:
            doc: dict[str, Any] = json.load(r)
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
    return "/" + "/".join(parts)


def _json_type(schema: Mapping[str, Any]) -> str:
    t = schema.get("type")
    kinds = [x for x in (t if isinstance(t, list) else [t]) if x != "null"]
    return "|".join(str(k) for k in kinds)


def _recorder() -> tuple[Client, FakeTransport]:
    everything = {"id": ID, "name": "x", "data": [], "has_more": False, "next_cursor": None, "items": [], "changes": []}
    t = FakeTransport(handler=lambda *a: jresp(200, everything))
    return Client("ow_w_testkey", "1234", transport=t), t


def test_every_route_and_query_parameter_the_client_sends_exists(doc: dict[str, Any]) -> None:
    c, t = _recorder()
    c.health()
    c.get_world()
    c.patch_world({"name": "x"})
    c.bulk([{"type": "character", "element": {"name": "x"}}])
    c.changes(since="c", limit=1)
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
    problems: list[str] = []
    for call in t.calls:
        op = doc["paths"].get(_norm(call.url), {}).get(call.method.lower())
        if op is None:
            problems.append(f"{call.method} {_norm(call.url)} is not in the document")
            continue
        if call.method == "GET" and "/changes" not in call.url:
            listed = {p["name"] for p in op.get("parameters", []) if p["in"] == "query"}
            sent = {q.split("=")[0] for q in call.url.split("?", 1)[1].split("&")} if "?" in call.url else set()
            problems += [f"{call.method} {_norm(call.url)} sends ?{q}, not listed" for q in sorted(sent - listed)]
    assert not problems, "\n".join(problems[:20])


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
    assert set(err["properties"]) == {"type", "code", "message", "param", "doc_url"}
    first_type = err["properties"]["type"]["enum"][0]
    body = {"error": {"type": first_type, "code": "probe", "message": "m", "param": "p", "doc_url": "https://x/e"}}
    e = ApiError("GET", "x", jresp(422, body))
    assert (e.type, e.code, e.api_message, e.param, e.doc_url) == (first_type, "probe", "m", "p", "https://x/e")

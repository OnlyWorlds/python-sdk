"""The Open with menu reads an element's marks as ``world_graph`` does: on every element of the lens fixture's worlds
(the vendored dist's ``profiles/lens.fixture.json``), a door that skips one word is left out exactly when the graph
reader, asked about that element alone, says it carries that mark. The graph is the reference here, never the
menu's own code: room, hidden and proposed from a node's marks with every flag on, map space from the cut with that
one flag off, a reading aid from the one kind no flag brings back. An element under the world's hidden list carries
``hidden: true``, as the owner is served it. The npm SDK's ``test/openers-marks.test.mjs`` is the same test.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from onlyworlds import openers_for, world_graph

FIXTURE = Path(__file__).resolve().parent.parent / "codegen" / "schema-dist" / "profiles" / "lens.fixture.json"
WORDS = ("room", "hidden", "proposed", "map_space", "reading_aid")


def door(word: str) -> dict[str, Any]:
    tid = "skip-" + word.replace("_", "-")
    return {
        "id": tid,
        "name": word,
        "url": "https://x.example",
        "client": None,
        "rung": "listed",
        "open": {
            "world": "https://x.example/#/w/{world}",
            "element": "https://x.example/#/w/{world}/e/{id}",
            "needs": None,
            "element_skips": [word],
        },
    }


TOOLS = [door(w) for w in WORDS]


def graph_marks(el: dict[str, Any]) -> set[str]:
    """The marks the graph reader gives one element, read from ``world_graph`` alone."""
    owner = {"rung": "owner"}
    every = world_graph({"elements": [el]}, owner, rooms=True, hidden=True, proposed=True, map_space=True)
    marks: set[str] = set(every["nodes"][0].get("marks", [])) if every["nodes"] else set()
    no_map = world_graph({"elements": [el]}, owner, rooms=True, hidden=True, proposed=True, map_space=False)
    if len(every["nodes"]) == 1 and not no_map["nodes"] and no_map["cut"].get("map_space") == 1:
        marks.add("map_space")
    if not every["nodes"] and every["cut"].get("reading_aid") == 1:
        marks.add("reading_aid")
    return marks


def test_every_skip_word_leaves_a_door_out_exactly_when_world_graph_reads_that_mark() -> None:
    doc = json.loads(FIXTURE.read_text(encoding="utf-8"))
    n = 0
    seen: set[str] = set()
    wrong: list[str] = []
    for w in doc["worlds"].values():
        hidden = set(w.get("hidden") or [])
        for raw in w["elements"]:
            el = {**raw, "hidden": True} if raw["id"] in hidden else raw
            want = graph_marks(el)
            seen |= want
            address = {"form": "human", "world": w["id"], "type": str(el["type"]).lower(), "id": el["id"]}
            rows = openers_for(TOOLS, "element", address, {"audience": "member"}, element=el)
            for word in WORDS:
                gone = not any(r["id"] == door(word)["id"] for r in rows)
                if gone != (word in want):
                    name = el.get("name") or el["id"]
                    wrong.append(f"{w['name']} {el['type']} {name}: {word} {'skipped' if gone else 'kept'}")
            n += 1
    for line in wrong:
        print(line)
    assert wrong == []
    assert n >= 100, n
    assert seen == set(WORDS)

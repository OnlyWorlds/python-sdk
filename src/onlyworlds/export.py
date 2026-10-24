"""Export a world from the wire to a folder: ``GET /world`` + every type's list, through the folder writer.

This is the package-shaped half of an earlier export script, ``export_folder.py``. The folder
it writes carries the SERVER world id (like the script's) and no ``api`` block and no
``snapshot_*`` keys: it is an export, the baseline a push diffs against. It is
not a snapshot (§4.2: fresh world id, provenance block, coherence bracket) and it
is not a linked folder (§4.1: ``api`` block); those writers are later slices.

Its ``world.json`` carries the two provenance lines of folder format v0.3.9 (§4.2):
``source`` (which server, which world, when) and ``exported_as`` (which slice the key
reads), the second from ``GET /me`` through ``exported_as``, and absent when the slice
cannot be known; and the producer line of v0.3.14 (§4.2), ``producer``: this package made
the folder, from a server (``EXPORT_PRODUCER``).
"""

from __future__ import annotations

import os
import urllib.parse
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any

from ._schema import ELEMENT_TYPES
from ._version import __version__
from .errors import ApiError
from .folder import WriteReport, write_folder
from .http import Client

__all__ = ["EXPORT_PRODUCER", "MEMBER_ROLES", "export_world", "exported_as"]

#: The ``producer`` line (§4.2, v0.3.14) every folder ``export_world`` makes carries: the name
#: this package publishes under on PyPI, its version, and ``server``, the spec's word for an
#: export from onlyworlds.com.
EXPORT_PRODUCER: Mapping[str, str] = {"tool": "onlyworlds", "version": __version__, "input": "server"}

#: The member roles whose slice is the role's, with no Character (``co_builder`` as keel serves it).
MEMBER_ROLES = ("co_builder", "contributor")

# What "refused or unavailable" looks like from the client: an error answer, no answer, a
# body that is not an object.
_UNAVAILABLE = (ApiError, ConnectionError, OSError, ValueError)


def exported_as(me: Mapping[str, Any] | None, character_name: Callable[[str], str | None]) -> dict[str, Any] | None:
    """The ``exported_as`` line (§4.2, v0.3.9) for a ``GET /me`` answer, or None: write none.

    The one place the mapping lives (the spec owner's table, 2026-10-19):

    - ``kind: owner`` (an owner-minted or classic key) -> owner, role owner, no character;
    - a member with role ``co_builder`` or ``contributor`` -> member, its role, no character;
    - a guest of any kind (person, agent seat, player) -> character, role guest, and the
      Character it reads as, ``{id, name}``, the name from ``character_name(id)``;
    - anything else -> None. No ``/me`` (``me`` None), a guest with no Character, a
      Character whose name cannot be read (``character_name`` gives None), or a kind or
      role this table does not name: the slice is not known, and ``exported_as`` is
      absent, never guessed. A name of ``""`` is a name the server served, and is written.
    """
    if not isinstance(me, Mapping):
        return None
    kind, role = me.get("kind"), me.get("role")
    if kind == "owner":
        return {"kind": "owner", "role": "owner", "character": None}
    if role in MEMBER_ROLES:
        return {"kind": "member", "role": role, "character": None}
    if role == "guest":
        cid = me.get("character")
        if not isinstance(cid, str) or not cid:
            return None
        name = character_name(cid)
        if not isinstance(name, str):
            return None
        return {"kind": "character", "role": "guest", "character": {"id": cid, "name": name}}
    return None


def _origin(base_url: str) -> str:
    u = urllib.parse.urlsplit(base_url)
    return f"{u.scheme}://{u.netloc}"


def _now() -> str:
    """The export's clock, as JavaScript's ``toISOString`` writes it (UTC, milliseconds, ``Z``)."""
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _read_me(client: Client) -> dict[str, Any] | None:
    try:
        return client.me()
    except _UNAVAILABLE:
        return None


def _character_name(client: Client, cid: str) -> str | None:
    try:
        name = client.get("character", cid).get("name")
    except _UNAVAILABLE:
        return None
    return name if isinstance(name, str) else None


def export_world(
    out_dir: str | os.PathLike[str],
    *,
    client: Client | None = None,
    api_key: str | None = None,
    pin: str | None = None,
    page_size: int = 200,
    producer: Mapping[str, str] | None = None,
) -> WriteReport:
    """Read the key's world (GET only) and write it as a folder at ``out_dir`` (which must not exist).

    ``world.json`` is the ``GET /world`` body, every key carried, plus ``source``
    (``{server, world, at}``: this client's API origin, the world's id, when the export
    began), when ``GET /me`` can say which slice the key reads, ``exported_as``, and
    ``producer`` (``EXPORT_PRODUCER``). The folder is always a birth (``write_folder`` never
    writes over one), so the line is always this call's: a ``producer`` a ``GET /world`` body
    might carry names the maker of another folder, as a ``source`` it might carry would.

    ``producer`` is for a tool that runs the export in its own name and so is the folder's
    maker (keel's nightly snapshots: ``{"tool": "keel", "version": ..., "input": "server"}``):
    written in place of ``EXPORT_PRODUCER``. Only its shape is checked, a ValueError before
    anything is read: exactly ``tool``, ``version`` and ``input``, each a non-empty string;
    ``input`` may be any word (§4.2: a word a reader does not know is data). It never
    replaces a line a folder already carries: there is no folder to write over.
    """
    line = dict(EXPORT_PRODUCER) if producer is None else _checked_producer(producer)
    if client is None:
        if not api_key:
            raise ValueError("export_world needs a client, or an api_key (+ pin)")
        client = Client(api_key, pin)
    at = _now()
    world = client.get_world()
    slice_ = exported_as(_read_me(client), lambda cid: _character_name(client, cid))
    elements: dict[str, list[dict[str, Any]]] = {}
    for etype in ELEMENT_TYPES:
        rows = list(client.iter_elements(etype, limit=page_size))
        if rows:
            elements[etype] = rows
    meta: dict[str, Any] = dict(world)
    meta["source"] = {"server": _origin(client.base_url), "world": world["id"], "at": at}
    if slice_ is not None:
        meta["exported_as"] = slice_
    meta["producer"] = line
    return write_folder(out_dir, meta, elements)


_PRODUCER_KEYS = ("tool", "version", "input")


def _checked_producer(producer: Mapping[str, Any]) -> dict[str, str]:
    """A caller's ``producer`` line in the spec's key order, or a ValueError on a wrong shape."""
    if not isinstance(producer, Mapping) or set(producer) != set(_PRODUCER_KEYS):
        raise ValueError(f"producer must be a mapping of exactly {_PRODUCER_KEYS} (§4.2), got {producer!r:.200}")
    bad = [k for k in _PRODUCER_KEYS if not isinstance(producer[k], str) or not producer[k].strip()]
    if bad:
        raise ValueError(f"producer {', '.join(bad)} must be a non-empty string (§4.2)")
    return {k: producer[k] for k in _PRODUCER_KEYS}

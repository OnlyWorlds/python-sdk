"""Export a world from the wire to a folder: ``GET /world`` + every type's list, through the folder writer.

This is the package-shaped half of Skeld's Sikelia ``export_folder.py``. The folder
it writes carries the SERVER world id (like his) and no ``api`` block and no
``snapshot_*`` keys: it is an export, the baseline a push diffs against. It is
not a snapshot (§4.2: fresh world id, provenance block, coherence bracket) and it
is not a linked folder (§4.1: ``api`` block); those writers are later slices.
"""

from __future__ import annotations

import os
from typing import Any

from ._schema import ELEMENT_TYPES
from .folder import WriteReport, write_folder
from .http import Client

__all__ = ["export_world"]


def export_world(
    out_dir: str | os.PathLike[str],
    *,
    client: Client | None = None,
    api_key: str | None = None,
    pin: str | None = None,
    page_size: int = 200,
) -> WriteReport:
    """Read the key's world (GET only) and write it as a folder at ``out_dir`` (which must not exist)."""
    if client is None:
        if not api_key:
            raise ValueError("export_world needs a client, or an api_key (+ pin)")
        client = Client(api_key, pin)
    world = client.get_world()
    elements: dict[str, list[dict[str, Any]]] = {}
    for etype in ELEMENT_TYPES:
        rows = list(client.iter_elements(etype, limit=page_size))
        if rows:
            elements[etype] = rows
    return write_folder(out_dir, world, elements)

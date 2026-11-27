"""Make ``kanka-4-made.zip``: the first real export with Kanka 4.0's two changes made by hand.

A real 4.0 export (made 2026-11-27) carries the account's ids, so it is not committed. This makes the
case both packages are held to from the first fixture, every file's bytes kept but three:

- ``info.json`` names Kanka 4.0 and export version 4.0;
- Mara Voss is dead the 4.0 way: ``entity.status_id`` 3 (the shared ``dead`` row), no ``is_dead``;
- a family, The Voss line, holds her under ``pivotMembers``, as 4.0 writes a family's people.

Run from the repository: ``uv run python tests/fixtures/kanka/make_kanka_4_made.py``. The same bytes come out
each time (every member's date is fixed); the npm SDK's copy is this file's output, byte for byte.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

HERE = Path(__file__).parent
SOURCE = HERE / "quay-export-world_20261023_074706.zip"
OUT = HERE / "kanka-4-made.zip"
WHEN = (2026, 11, 27, 0, 0, 0)

FAMILY = "families/the-voss-line_10074650.json"
FAMILY_BODY = (
    b'{"name":"The Voss line","id":2607510,"is_private":0,"entity":{"id":10074650,"entity_id":2607510,'
    b'"parent_id":null,"type_id":2,"name":"The Voss line","type":"Family","entry":"<p>Route planners for '
    b'three generations.<\\/p>","is_private":false,"tooltip":null,"is_template":false,'
    b'"is_attributes_private":false,"focus_x":null,"focus_y":null,"created_at":"2026-10-23T07:44:00.000000Z",'
    b'"updated_at":"2026-10-23T07:44:00.000000Z","created_by":900001,"updated_by":null,"image_path":null,'
    b'"image_uuid":null,"header_image":null,"header_uuid":null,"marketplace_uuid":null,"status_id":null},'
    b'"pivotMembers":[{"character_id":2607497,"family_id":2607510}]}'
)


def changed(name: str, raw: bytes) -> bytes:
    """One member's bytes as the made export has them; each replacement must match exactly once."""
    subs: list[tuple[bytes, bytes]] = []
    if name == "info.json":
        subs = [
            (b'"kanka_version":"3.15"', b'"kanka_version":"4.0"'),
            (b'"export_version":"3.15"', b'"export_version":"4.0"'),
        ]
    elif name == "characters/mara-voss_10074603.json":
        subs = [(b'"status_id":1,', b'"status_id":3,')]
    for old, new in subs:
        if raw.count(old) != 1:
            raise SystemExit(f"{name}: {old!r} found {raw.count(old)} times, not once")
        raw = raw.replace(old, new)
    return raw


def main() -> None:
    with zipfile.ZipFile(SOURCE) as src:
        members = [(n, changed(n, src.read(n))) for n in src.namelist()]
    members.append((FAMILY, FAMILY_BODY))
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as out:
        for name, raw in members:
            out.writestr(zipfile.ZipInfo(name, WHEN), raw, zipfile.ZIP_DEFLATED)
    print(f"{OUT.name}: {len(members)} files")


if __name__ == "__main__":
    main()

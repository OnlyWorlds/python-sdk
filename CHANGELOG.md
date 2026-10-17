# Changelog

The package version runs on its own semver; the schema it is generated from is `SCHEMA_DIST_TAG`.

## 0.5.1 (2026-10-17)

- **The reader skips a dot-prefixed file in a type directory**, a tool's litter rather than an element, and lists it in `Folder.skipped`, even when it holds a valid body. Before, it was read like any file, and one that sorted first could stand in for the real element (Skeld's clarification of the folder spec, 2026-10-17).
- **`Folder.time_current` prefers a non-null `time_current`**: a null one beside `time_range_current` now reads the range, where it read null.

## 0.5.0 (2026-10-17)

- **Folder format v0.3.8, one id, one file (§4).** A writer never leaves an element's id under both `elements/` and the legacy `spatial/`, and a reader that finds one in both serves the `elements/` copy. `write_folder` already wrote a whole folder under `elements/` only, and `Folder.all_elements()` already served `elements/` on a shared id, so nothing changes in what either does. `FORMAT_VERSION` (the `format_version` a written `world.json` declares) is now `"0.3.8"`; folders stamped `"0.3.7"` stay valid.
- **`Folder.in_both_layouts`** lists the ids found in both layouts, sorted: each is a folder some writer got wrong, which the spec says a reader SHOULD log.

## 0.4.0 (2026-10-16)

- **A retry that meets its own first try still running now waits and replays (keel #307, D105).** After a timeout the client resends with the same Idempotency-Key; if the first request is still running, keel answers 409 `idempotency_in_flight` with `Retry-After: 1`. The retry policy now retries that 409 (and only that one), so `create` and `bulk` get the first answer's replay instead of an error. `ApiError.is_idempotency_in_flight` names it when the retries run out.

## 0.3.0 (2026-10-15)

- **The door of every write (keel #299, D104).** `Client(..., agent=True)` sends `X-OW-Agent` on every element write (create, upsert, patch, delete, edit_links, bulk: the operations keel's document declares it on; never on reads or `patch_world`), and keel records those writes as agent-made (`changed_via: "declared"`); keel stores that the header was there, never its value. Off by default, and off in any tool a person uses: it describes the caller. An agent seat's key counts as an agent without it.
- **`push` never sends `changed_by` or `changed_via`**, keel's new read-only record of the last write, for the reason it never sends `created_by`: keel drops them but still restamps the element, so a folder that holds them would rewrite elements for nothing.

## 0.2.1 (2026-10-12)

- **The schema**, repinned to schema-dist `v0.32.0-dist.23` (same canonical `00.32.00`): the dist trues the Id description (a UUID; new ids uuidv7, earlier uuidv4 ids valid) and adds `walk/lint_folder.py`. `ELEMENT_TYPES` and `FIELD_KINDS` are unchanged; `SCHEMA_DIST_TAG`, `SCHEMA_DIST_SERIAL` and `SCHEMA_MANIFEST_SHA256` name the new pin.

## 0.2.0 (2026-10-11)

- **Only if unchanged (keel #210).** `patch(..., if_match=change_seq)` and `edit_links(..., if_match=...)` send `If-Match`: the write lands only if the element is still at that `change_seq`. When it has moved, nothing is written and `PreconditionFailed` is raised (412 `precondition_failed`), an `ApiError` whose `current` is the element as it is now; `ApiError.is_precondition_failed` names the case. The server never merges. An `if_match` that is not a whole number raises `ValueError` before anything is sent. Without `if_match`, nothing changes. Checked on keel-staging (`tests/test_staging_writes.py`).

## 0.1.1 (2026-10-11)

- **The schema**, repinned to schema-dist `v0.32.0-dist.20` (canonical `00.32.00`): the World gains `public_read`, a boolean. Export writes it into `world.json` as `GET /world` sends it; push never sends world keys, so nothing new goes out. `ELEMENT_TYPES` and `FIELD_KINDS` are unchanged.

## 0.1.0 (2026-10-10)

The first release on PyPI. Python 3.12+, no runtime dependencies.

- **The v2 API client** (`Client`): read, write, link operations, bulk, the change feed (`ChangeWalk`), and the error envelope as `ApiError`. It retries busy and gateway answers (`429`, `502`, `503`, `504`) and honours `Retry-After` (`RetryPolicy`). It never retries a wrong PIN, since each retry counts toward locking the key. The transport is swappable (`Transport`).
- **World folders** (format v0.3.7): `read_folder` and `write_folder`, filenames that match Atlas's, and the World's three unit settings (`length_unit`, `mass_unit`, `distance_unit`) carried like any world key. Reading never changes a file.
- **Export and push:** `export_world` writes an online world to a folder. `push` sends a folder's edits back as the difference from a copy exported before editing (`plan_push` to preview it, a log to resume it). A run stops at the first answer that refuses the key itself. What push never sends is listed in `NOT_SENT`.
- **The schema**, generated from schema-dist `v0.31.0-dist.19` (canonical `00.31.00`): `ELEMENT_TYPES`, `FIELD_KINDS`, and the pinned manifest's hash.

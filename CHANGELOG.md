# Changelog

The package version runs on its own semver; the schema it is generated from is `SCHEMA_DIST_TAG`.

## 0.1.0 (2026-10-10)

The first release on PyPI. Python 3.12+, no runtime dependencies.

- **The v2 API client** (`Client`): read, write, link operations, bulk, the change feed (`ChangeWalk`), and the error envelope as `ApiError`. It retries busy and gateway answers (`429`, `502`, `503`, `504`) and honours `Retry-After` (`RetryPolicy`). It never retries a wrong PIN, since each retry counts toward locking the key. The transport is swappable (`Transport`).
- **World folders** (format v0.3.7): `read_folder` and `write_folder`, filenames that match Atlas's, and the World's three unit settings (`length_unit`, `mass_unit`, `distance_unit`) carried like any world key. Reading never changes a file.
- **Export and push:** `export_world` writes an online world to a folder. `push` sends a folder's edits back as the difference from a copy exported before editing (`plan_push` to preview it, a log to resume it). A run stops at the first answer that refuses the key itself. What push never sends is listed in `NOT_SENT`.
- **The schema**, generated from schema-dist `v0.31.0-dist.18` (canonical `00.31.00`): `ELEMENT_TYPES`, `FIELD_KINDS`, and the pinned manifest's hash.

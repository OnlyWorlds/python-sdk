# onlyworlds (Python)

**Pre-release (`0.1.0.dev0`). Not on PyPI yet.** The Python package for OnlyWorlds: the world folder format (read, write, push) and a client for the v2 API. Python 3.12+, no runtime dependencies.

Its version is its own semver and does not track the schema's. The schema version it was generated from is a constant in the package (`v0.30.1-dist.15`, canonical 00.30.01).

The old `onlyworlds` 0.30.0 on TestPyPI is a different, earlier package for the v1 API (`/api/worldapi/`). It is not related to this code.

## What is here

- `write_folder` / `read_folder`: OW Folder Format **v0.3.6**. Filenames `<slug>--<last 8 of id>.json` (NFKD, 40-character cap, re-trimmed; an unsluggable name falls back to the full id), the writer collision rule with an id-ascending tie-break, LF / 2-space / `ensure_ascii=False` / trailing newline / key order as received, empty type directories omitted, canonical `world.json` keys (`time_current`). The reader takes `elements/` plus legacy `spatial/` (kept apart, merged by `all_elements()`), skips id-less and unparseable files without touching them, lets the body's type beat its directory, and never mutates the folder.
- `plan_push` / `push` / `verify_level`: baseline, field-level diff, PATCH only the changed fields (never `created_by`; a generic link's two halves together), retries on 429/5xx honouring `Retry-After`, a stop at the first answer that refuses the key itself (401, a wrong-PIN 429, a 403 other than `not_author`), a sent-vs-returned mismatch check, and an append-only jsonl log so a rerun skips what landed (keyed on a fingerprint of each patch, not only the id).
- `Client`: the v2 API with an injectable transport (stdlib `urllib` by default). `health`, `get_world`, `patch_world`; `list_page`, `iter_elements`, `get`, `create`, `upsert`, `patch`, `delete`, `edit_links`; `bulk`; `changes` and `walk_changes`. Elements are plain dicts. Writes strip what the API rejects (`world`, `type`, `created_at`, `updated_at`, `change_seq`) and keep extension fields. `create` and `bulk` give an element without an id one (a UUIDv7, or derived from your own `Idempotency-Key` so a repeat call with that key replays) and always send an `Idempotency-Key`, so a retry after a lost answer rewrites the same elements instead of creating them twice. A 429 `rate_limited` is never retried: on keel it means a wrong PIN. Errors are `ApiError` with the envelope's `code`, `param` and `doc_url` and flags for the cases a caller handles differently: `is_id_conflict`, `is_idempotency_conflict`, `is_not_author`, `is_busy`, `is_auth_error`, `is_validation_error`.
- `export_world` (GET only).
- The 22 element types and each field's kind are **generated** from the schema distribution vendored at `codegen/schema-dist/` (byte-exact, MANIFEST sha256 recorded in `codegen/schema-pin.json`), never hand-listed.

Not yet: typed element models, the account routes, the snapshot writer.

## Use

```python
from onlyworlds import Client

client = Client("ow_r_...")  # a read key needs no PIN; a write key does: Client(key, pin)
# the PIN is the world's for the owner's key, the member's own account PIN for a member key,
# and the seat's ow_s_ secret for an agent seat (the world PIN is refused for both)
for character in client.iter_elements("character", expand=["species"]):
    print(character["name"])

walk = client.walk_changes(saved_cursor)  # None for everything
for op in walk:
    ...  # op["op"] is "upsert" or "delete"
saved_cursor = walk.cursor  # opaque; persist it, never parse it
```

## Develop

```
uv sync
uv run pytest -q
uv run ruff check . && uv run mypy --strict src
uv run python codegen/generate_schema.py --check
```

Three groups of tests skip unless you opt in:
- `OW_CONFORMANCE_FIXTURE=<path>`: the reader-conformance fixture from the Atlas repo (`tests/fixtures/folder-conformance`).
- `OW_OPENAPI=https://www.onlyworlds.com/api/v2/openapi.json` (or a saved copy): `tests/test_wire.py` runs the client against keel's own OpenAPI document and compares routes, query parameters, fields and their kinds, what a write must not carry, and the list and error envelopes.
- `OW_LIVE=1`: a few read-only calls against the public demo world.

## What backs the claims

Counts are from 2026-09-28; rerun the checks rather than quoting these.

- **Reader**: answers the shared folder conformance fixture (v1.2.1 now; 1.2.0 had the same elements) exactly: 9 elements, 1 legacy, the 2 expected skips, zero bytes changed. Checked again independently through the public API.
- **Filenames** agree with the TypeScript writer (`ow-folder-store`, itself differential-tested against Atlas's source) on 96,487 of 96,487 single names and 3,000 of 3,000 collision groups.
- **Serializer** matches the TypeScript writer on 18,152 of 18,154 cases and on all 12,043 files of a real 196-settlement world. The 2 deliberate differences: integer-like keys stay in received order, and big integers keep their precision.
- **Live read** of demo world 0: 37 of 37 files byte-identical on rewrite, 36 of 36 identical to the TypeScript writer's capture.
- **Mutants watched failing**: removing the re-trim after the cap, or the NFKD fold, fails the suite.

The client (2026-10-04):
- **Scripted tests** cover every call's verb, path, headers and body, the error flags, the retry rule (a retried create repeats the same id and key), bulk replay and the change walk. Five mutants of the client (a lost strip field, a loose conflict flag, a fresh key per attempt, a lenient `Retry-After`, a stuck cursor) each fail the suite.
- **Against keel's OpenAPI document** (`tests/test_wire.py`): passes on the live document, and fails on each of eight deliberately broken copies of it (a route, a parameter, a field kind, a page key, an error key, a write field, a new read field, a `required` list).
- **Live reads** against the demo world: health, world, a page, sparse fields, and the change feed.
- **Writes on the wire** (`tests/test_staging_writes.py`, 11 tests against a scratch world on keel-staging, an owner and a contributor key; 2026-10-04, rerun 2026-10-06): create, idempotent replay, PUT and PATCH, links, bulk (partial, atomic, cycles, replay), the change feed, a contributor's limits, PINs, cross-world ids, the extension cap. Skipped unless the `OW_STAGING_*` keys are set; never in CI.

The first review against keel (Skeld, 2026-10-06) found four faults, each fixed with a test watched failing on the old code: push sent `created_by`; push sent half of Pin's `element_type`/`element_id` pair; a wrong-PIN 429 was retried and push carried on; and an id-less bulk item could be created twice on a resend.

## Format rulings behind it

Three questions this code raised were ruled in the folder spec (§5 and its changelog, `format_version` unchanged), and the code already did each one: integral floats serialize as `1`; an unsluggable name is `<full-id>.json`; integer-like keys keep received order.

## Next

Skeld's re-read of the four fixes, then PyPI `0.1.0`.

## License

MIT. See `LICENSE`.

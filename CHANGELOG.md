# Changelog

The package version runs on its own semver; the schema it is generated from is `SCHEMA_DIST_TAG`.

## Unreleased

## 0.10.2 (2026-10-20)

- **The OKF export keeps a stub's mark.** A known-of element (`known_of: true`, folder format §4.4) is now written with `known_of: true` in its concept's frontmatter, and `OkfReport.known_of` counts them (the command line's summary says "N known of" when there are any). Before, `known_of` was dropped with the other `push.NOT_SENT` keys, so a stub read as a whole element whose absent fields looked empty rather than unknown.

## 0.10.1 (2026-10-20)

Folder format v0.3.11 (§3.3: a re-key never rewrites `x_identity_key`, the cross-world identity convention's key, Council #451). Nothing here re-keys, so the writer's behaviour is unchanged; `FORMAT_VERSION` and the `format_version` a written folder declares move to `0.3.11`.

## 0.10.0 (2026-10-20)

Public fields on a known-of stub (keel PR 117, Keel #448), live in production. The schema is repinned to schema-dist `v0.32.1-dist.28` (canonical `00.32.01`; only `presentation.json` and its manifest moved), ahead of `@onlyworlds/sdk`'s dist.27 pin.

- **A stub keeps every field keel sent it with a value.** keel now serves a known-of stub its type's public fields with their values (a Character's `physicality`, `height`, `weight`, `species`, `reputation`; no other type's yet), every other key still sent blank. `known_of_for_disk` (and so `write_folder` and `export_world`) writes the `KNOWN_OF_KEEPS` keys as before, plus every other key the body holds a value for, in received order, then `known_of: true`. A value is anything but `""`, `null` and `[]`: `0` and `false` are kept. Before, it wrote the kept keys only and dropped the public fields keel serves (folder spec §3: a writer never drops data it has). The rule reads the body, not a list, so a type that gains public fields needs no new release.
- **`PUBLIC_FIELDS`**: type -> the fields shown on a stub beside its name, description, supertype, subtype and picture, all 22 types (`()` for none), generated from the dist's `presentation.json` `types.<type>.public` and checked by `generate_schema.py --check`. For display; what a stub holds is what the server sent.
- **`ApiError.is_known_of_not_writable`**: 422 `known_of_not_writable` (`param` known_of), keel's answer to a write body carrying `known_of`. The client already refuses a stub before sending and never sends another `known_of`, so this comes only from a body sent around it.

## 0.9.0 (2026-10-20)

Known of (keel PR 113), live in production since 2026-10-20 13:47, and folder format v0.3.10. The schema is repinned to schema-dist `v0.32.1-dist.27` (only its example moved), equal to `@onlyworlds/sdk` 4.40.0's pin.

- **Folder format v0.3.10, known-of elements (§4.4).** keel hands a guest or player an element it reaches only through its own Character's sheet as a stub, `known_of: true`, keeping `id`, `type`, `name`, `description`, `supertype`, `subtype`, `image_url`, `created_at`, `updated_at` and `change_seq` (`KNOWN_OF_KEEPS`) and every other field unset. `write_folder` (and so `export_world`) writes a stub as it is: its kept keys and `known_of: true`, never the unset `""`, `null` and `[]` (`folder.known_of_for_disk`). Every other body is still written untouched. A stub that later arrives whole is written whole, without `known_of` (a repeated id keeps its last body). `FORMAT_VERSION` is now `"0.3.10"`; folders stamped `"0.3.9"` stay valid.
- **`is_known_of(body)`**: true only for `known_of: true`. The reader flags a stub (`FolderElement.known_of`) and lists them (`Folder.known_of`), and fills in nothing for the fields it lacks: they are unknown, not empty.
- **A stub is never pushed**: `plan_push` leaves an element that is `known_of: true` in the folder or in the baseline out of the diff and lists it in `PushPlan.known_of` and `PushResult.known_of`, never in the membership lists, so a stub alone never makes a plan unmatched. `known_of` joins `push.NOT_SENT`.
- **A stub is never written back**: `create`, `upsert`, `patch` and `bulk` raise `ValueError` before sending a body with `known_of: true` (`bulk` names the item and sends none of the batch); stripping the marker would turn keel's 422 into a write that blanks the element for any key that may write it. `known_of` joins `READ_ONLY_FIELDS`, so any other value of it is never sent. Equal to `@onlyworlds/sdk`'s staged half.

## 0.8.1 (2026-10-20)

- **The schema**, repinned to schema-dist `v0.32.1-dist.26` (canonical `00.32.01`, the Captain's word, h55 #8395): one description changed, an Event's `characters` are the Characters who know about it (present, aware or involved). `SCHEMA_VERSION` is `00.32.01`; `ELEMENT_TYPES` and `FIELD_KINDS` are unchanged. Equal to `@onlyworlds/sdk` 4.38.0's pin.

## 0.8.0 (2026-10-20)

The hidden mark (keel #421), live in production since 2026-10-20 09:24.

- **`is_resync_required`** names every case keel sends it for since its hidden mark (keel #421), not only a guest's; a `/changes` delete row carries `reason` (`deleted`, `hidden`, `out_of_view`), read as any other key of the row.
- **`view_as=`** on `get`, `list_page` and `iter_elements`, sent as `as` (keel #421, view as): the owner's key reads as a member (a membership id), as a Character's guest (a Character id) or as the public (`"public"`). A member key gets 403 `view_as_owner_only` (`is_view_as_owner_only`); an element hidden from that reader is 404, never 410; an unknown value is 422. Until keel's hidden mark is on, keel answers 422 (an unknown parameter).
- **`ApiError.resync_reason`** (`"role"`, `"view"` or None): why `/changes` answered 409 `resync_required`, from the envelope's `reason` (keel #421, keel PR 103; only while keel's hidden mark is on). A `/changes` page then carries `epoch_reason` beside `epoch`, read as any other key of the page.
- **The resync instruction adds the hidden mark's reasons to 0.7.1's keep** (the Captain, 2026-10-20): after a 409 `resync_required`, walk again from the start; reason `role` (the key's own role or membership moved): keep what the local copy holds that the walk no longer names; reason `view`, or a delete row with reason `hidden`: drop it; no reason (keel's hidden mark off): keep it, a reset never empties a copy. A tool never empties a copy on its own. `is_resync_required`, `ChangeWalk` and `Client.changes` say so.

## 0.7.1 (2026-10-20)

- **The reset rule says keep.** `ApiError.is_resync_required` and the feed's docstring: on a 409 `resync_required`, walk again from the start and keep what the local copy holds that the new walk does not name; a reset never empties a copy. They said replace. Keel says keep since PR 104 (the Captain's ruling, 2026-10-20: sharing is forward-only). Nothing in the package acted on it, so no behaviour changes.

## 0.7.0 (2026-10-19)

- **Folder format v0.3.9, the provenance lines (§4.2).** `export_world` writes two keys into `world.json`: `source`, `{server, world, at}` (the client's API origin, the world's id, and when the export began, as an ISO timestamp in UTC), and `exported_as`, `{kind, role, character}`, which slice the key reads. `exported_as` comes from `GET /me` through one function, `onlyworlds.export.exported_as`: an owner key gives `{"kind": "owner", "role": "owner", "character": null}`, a co-builder or contributor `{"kind": "member", "role": <its role>, "character": null}`, a guest of any kind (person, agent seat, player) `{"kind": "character", "role": "guest", "character": {"id", "name"}}` with the name read from `GET /character/{id}`. When `/me` is refused or missing, a guest has no Character, or its Character cannot be read, the key is left out: absent, never guessed. `FORMAT_VERSION` is now `"0.3.9"`; folders stamped `"0.3.8"` stay valid.
- **`Client.me()`**: `GET /me`, who this key is (`{world, scope, kind, role, membership, character, name?}`).
- **`write_folder` keeps `source` and `exported_as`** like any other world key, so a folder rewritten from a read one (a what-if branch) keeps its parent's verbatim.
- **The OKF export carries `source` and `exported_as`** into `world.md`'s frontmatter as the folder holds them, beside `format_version`, `writable` and the `snapshot_*` keys, so a bundle made from one Character's slice still says so. Before, they would have been noted as not World fields and left out.

## 0.6.0 (2026-10-17)

- **Export a world folder to Open Knowledge Format (OKF) v0.2** (`onlyworlds.okf`, Keel #191): `export_okf(folder, out_dir)` or `python -m onlyworlds.okf FOLDER OUT-DIR` writes one markdown concept per element (fields in the frontmatter, text under headings, links as bundle paths and as markdown links), the World as `world.md`, and an index per type. The same folder gives the same bytes. Nothing is left out in silence: a file the reader skipped, a key that is not a field of its type, or a link that is not an id or points at the wrong type is a note in the returned `OkfReport` (stderr from the command line). Ported from schema-dist's `walk/okf_export.py`, it reads through `read_folder` and the generated schema tables. It differs from the branch on purpose: no `generated` actor (OKF §7 asks for a `human:` actor on hand-written words, and a folder does not say who wrote them), in-prose `ow://` references become links into the bundle, and a text line that already begins with a backslash gets one more, so every escaped line reads back.
- **PyYAML only for OKF**: the export needs the new `okf` extra (`pip install "onlyworlds[okf]"`). `import onlyworlds` still imports nothing outside the standard library.
- **The schema module grows** (same pin, `v0.32.0-dist.23`): `BASE_FIELDS`, `WORLD_FIELDS`, `SECTIONS` (each type's fields under their schema groups, in order), `LINK_TARGETS`, `GENERIC_LINKS` and `EXTENSION_PREFIXES`, generated from the vendored walk like the rest and checked against `FIELD_KINDS` and `GENERIC_PAIRS` at generation.

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

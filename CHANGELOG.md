# Changelog

The package version runs on its own semver; the schema it is generated from is `SCHEMA_DIST_TAG`.

## 0.22.0 (2026-10-22)

- **The conditional head poll** (keel #518, live 2026-10-22): `Client.head()` reads `GET /changes?head=true`, where the feed is now without a page, and answers `{head, cursor, epoch, unchanged}` (with `epoch_reason` when keel sends it). The client keeps the last 200's `ETag` and sends it as `If-None-Match` on the next call, exactly as received (`W/` and quotes included; production answers the 200 with a weak tag and the 304 with a strong one, and the tag sent back as received is what matches); the package compares nothing. keel answers 304 Not Modified, with no body, when neither the head nor the epoch moved (the tag covers both), and refunds it against the request budget within a floor of 120 a minute per credential; `head()` then answers what the last 200 said with `unchanged=True`. A 200 answers `unchanged=False` and keeps its tag, or none when it carries none. The tag is per client instance. A 409 `resync_required` from `head()`, `changes()` or `walk_changes()` drops it, so the poll after it carries no tag. A 304 when no tag was sent is a `ValueError`, never an invented head. `cursor` is a string, as the npm SDK's `changesHead` hands it back (keel answers an owner's as a number). The package never sleeps: the docstring's loop walks when `head` or `epoch` differs from the ones last applied, not on `unchanged` alone, since `unchanged` is "nothing since the last poll", and a walk that failed after a 200 would otherwise never be retried. Every other call is as before.
- **Fixed: a walk's cursor at the head.** keel answers an owner's cursor at the head as a number (`"cursor": 226`), and `ChangeWalk` kept only a string: at the tail it held on to the cursor it had been given, so the next walk resent the last page, and a number on a page with more to come was refused as "no new cursor". It now keeps any cursor as a string, `"226"`, the position to pass back as `since`.
- The wire test now checks `/changes`'s query parameters too (the document declares them), and that the head poll's `If-None-Match` and the 304's `ETag` are declared; the live suite polls the demo world's head twice and reads the second as unchanged.

## 0.21.0 (2026-10-22)

- **The client's name on a write** (keel #520, live 2026-10-22): `Client(..., client="python")` names the software that writes, sent as `X-OW-Client` on exactly the element writes that carry `X-OW-Agent` (`create`, `upsert`, `patch`, `delete`, `edit_links`, `bulk`) and on `push`'s PATCH, never on a read or the world's settings. keel stores it on the element as `changed_client`, and on a delete as the change feed's `deleted_client`. The default `python` says which library wrote; a tool passes its own (`client="atlas"`). The rule is keel's, `[a-z0-9-]{1,32}` (lower case letters, digits and hyphens, no version): a value outside it is refused at construction, a `ValueError` (a `TypeError` for a non-string), never trimmed, where keel itself would store null. The name is the client's claim, never proof of who wrote, and it changes no door: an agent sends both headers.
- **`push`'s PATCH now carries the write headers.** It was sent without them, so an agent client's push never declared itself with `X-OW-Agent`; it now names the client and, for `agent=True`, declares it.
- **`changed_client` is never sent**: it joins `changed_by` and `changed_via` among the keys keel drops on a write, in `push`'s never-sent list and the wire test's server-managed set, so a body read back round-trips and a push does not rewrite every element another client last touched. `deleted_client` rides only a delete op in `/changes`, never a body.
- **Schema repinned to schema-dist `v0.33.0-dist.46`** (same canonical 00.33.00; `SCHEMA_DIST_TAG`, `SCHEMA_DIST_SERIAL` and `SCHEMA_MANIFEST_SHA256` move with it). The dist's export example gives every body `changed_client: null`, the folder lint's server-key set names `changed_client`, and its README says so in one sentence; `VERSION` and `MANIFEST.json` carry the new serial; no schema file moved. The same pin as the npm SDK's for keel #520.

## 0.20.0 (2026-10-22)

- **The room profile** (schema-dist `profiles/room.md`, serial 45; Skeld's rulings, OW Council #554 and OW Parlor h66 #10392): `ROOM_PAIRS`, the eight `(type, supertype)` pairs a parlor puts in a world (narrative/Message, narrative/Board, relation/Work item, construct/Spec, relation/Heart, relation/Vote, event/Sitting, character/Member), and `is_room_element(element)` (module `onlyworlds.room`, both at the package root), true when a body's or a `FolderElement`'s type and supertype, each trimmed and compared without regard to case, match one of them **and** it carries the mark `x_room_of` (the id of the world or sitting the room belongs to) as a non-empty string. A pair without the mark is lore (a novel's letters are Narratives with supertype Message); a mark without a pair is not a room element. The pair match is the whole word, a missing or empty supertype is never a room element, and a Law with supertype `Charter` stays lore. A lore view leaves room elements out unless the person asks; the room's own views show them whole. A convention on the 22 types: no type, field or wire change. `ROOM_PAIRS` and the mark's name (`ROOM_MARK` in `_schema.py`, not exported) are generated from the fixture's `pairs` and `mark.field` and checked against the page (generation fails if they disagree); case is folded by Unicode simple case folding (`simple_case_fold`, the `.owworld` reader's table), the same fold as the npm SDK's `isRoomElement`. `tests/test_room.py` replays the fixture's 23 cases from the vendored dist.
- **Schema repinned to schema-dist `v0.33.0-dist.45`** (same canonical 00.33.00; `SCHEMA_DIST_TAG`, `SCHEMA_DIST_SERIAL` and `SCHEMA_MANIFEST_SHA256` move with it). The dist adds `profiles/room.md` and `profiles/room.fixture.json`; `VERSION`, `README.md` and `MANIFEST.json` carry the new serial; no schema file moved. Serial 44, the pairs without the mark, was superseded within the hour and is skipped. The same pin as the npm SDK's 4.55.0.

## 0.19.0 (2026-10-22)

- **The Notion door** (`onlyworlds.notion`, OW Market #545): `import_notion(source, out_dir, plan_only=False)` and `python -m onlyworlds.notion EXPORT.zip OUT-DIR [--plan]` read Notion's "Markdown & CSV" export, the zip or the directory it unzips to (inner part zips one level deep), into a world folder written through `write_folder`. No AI, no account. **What it reads**: a database whose title is one of the 22 types (singular or plural, any case) becomes elements of that type, or row by row when a `Type` column names one; a column becomes a field when its name, lowercased with spaces as underscores, is a field of that type (compared without case, so `str` finds `STR`), the title column `name`; a relation column becomes a link field of the same name, each target resolved by its Notion id and failing that by its exact title among the typed elements of the field's target type; `_all.csv` is read over the plain CSV, never both. Every other page becomes a Narrative (its Markdown the description, callout HTML kept as text, `x_notion_parent` the page it sits under), and so does each row of an untyped database (supertype `notion`, subtype the database's title). A page link in a Narrative's text to a page of another type also lands on Narrative's multi-link field for that type; the text keeps the link as written. **What it keeps**: every column not placed, verbatim, as `x_notion_<column>`; a value that does not fit its field's kind; an unresolved relation's cell; a row's page text as `x_notion_body` when a column filled `description`; the Notion id as `x_notion_id`; attachments a page links to, copied to `media/notion/<path in the export>` with the link rewritten. Ids are UUIDv5 of the Notion id in a fixed namespace (`NOTION_NAMESPACE`), so the same export twice gives byte-equal folders and a later export of the same workspace finds the same elements; a file with no id takes its path's. `world.json` carries `producer` `{"tool": "onlyworlds", "version": ..., "input": "notion-export"}` (Skeld's word for the spec's list). **What it reports** (`ImportReport`, printed at the end of a run and by `--plan`, which writes nothing): what became what with counts, the untyped databases, every column not placed (database, column, why, the key it was kept as), every link not resolved (the element, the column or `body`, the target as written, why), every id taken from a path, the attachments copied and anything skipped. Built on the documented shape; a real export is the fixture to come, and every name the door believes is listed in the module's docstring and parsed in one place.
- The folder it writes passes the dist's folder lint, and `read_folder` then `write_folder` gives it back byte for byte.

## 0.18.0 (2026-10-22)

- **Added: `Zone.shape`** (canonical 00.33.00, a minor step of the standard): a string in Zone's Scope section beside `role`, saying how the zone's markers are joined. `"polygon"` is a closed area (the last marker joins the first), `"line"` an open path drawn in marker order; lowercase. Empty, absent or any other value means not stated, and a reader draws a polygon. Generated into `FIELD_KINDS["zone"]` as `"shape": "text"` and into Zone's `Scope` entry of `SECTIONS`; `SCHEMA_VERSION` is `"00.33.00"`.
- **Schema repinned to schema-dist `v0.33.0-dist.43`** (`SCHEMA_DIST_TAG`, `SCHEMA_DIST_SERIAL` and `SCHEMA_MANIFEST_SHA256` move with it). Only `schema/zone.yaml` and `schema.json` moved, by the one field; `VERSION`, `README.md`, `example/world-export.json` and `MANIFEST.json` carry the new version; nothing else. The same pin as the npm SDK's 4.54.0.

## 0.17.1 (2026-10-22)

- **Schema repinned to schema-dist `v0.32.2-dist.42`** (canonical 00.32.02 unchanged: no schema file moved; `SCHEMA_DIST_TAG`, `SCHEMA_DIST_SERIAL` and `SCHEMA_MANIFEST_SHA256` move with it). Serial 42 adds one case to the `.owworld` conformance set, `fail-OW-6-marker-bom`, a `mimetype` marker that starts with a byte order mark (81 cases now), with its row in `verdicts.json` and its generator; nothing else. The reader already refused it as `marker` and needed no change. The same pin as the npm SDK's 4.53.3.

## 0.17.0 (2026-10-22)

- **The world file, `.owworld`** (folder format §4.7, OW Council #522), for keel's nightly snapshots: `read_world_file(path_or_bytes)`, `write_world_file(folder, path)` and `world_file_bytes(folder)`, in `onlyworlds.worldfile`. The reader parses the zip's central directory itself (zip64 included: `zipfile` would turn a `\` in a name into `/` on Windows and read a name without the UTF-8 flag as cp437) and checks every name, kind, method and size before it inflates anything. A refusal is a `WorldFileError` whose `reason` is one of the spec's twelve causes, named as the TypeScript SDK names them. The collision fold is NFC, then the C and S rows of the vendored CaseFolding 15.1 (`_casefold.py`, made by `codegen/generate_casefold.py`), never `str.casefold()`. The budget is the spec's floor, 500,000 entries and 2 GiB: declared sizes first, then each entry's bytes (more than it declares is `too_big`; fewer, or a failed CRC, `not_openable`). An `api` block is stripped and never returned; without one, `world.json` keeps its bytes. `WorldFile.to_folder(dest)` writes the world as a folder, every entry byte for byte, built beside `dest` and renamed into place as `write_folder` does. 80 of 80 on the vendored conformance set, the verdicts the TypeScript and Unity SDKs give.
- **The writer** puts the `mimetype` marker first and stored, then `world.json` and `elements/`, `spatial/`, `media/` and `records/` (`records/` whole; no dot-file or `.meta` in the others), and nothing else from the folder; a tool's dot-folder only when handed in (`private_dir=".atlas"`), which makes the file a private copy. Every entry is stamped 1980-01-01 00:00, in the UTF-8 byte order of its name, `.json` deflated and the rest stored (the TypeScript writer's methods, so the two writers' directories agree name for name on order, method, size and CRC). The top folder is `<slug>-<id8>` from `world.json`, as Atlas and Lantern name it (`top_dir=` for another), so the bytes never depend on where the folder sits. `world.json` travels byte for byte, `producer`, `source` and `format_version` included; only `api` is never written. One folder gives one set of bytes on one Python: the deflated bytes follow the zlib build (Python 3.14 on Windows ships zlib-ng), while names, sizes, CRCs and every entry's content hold across builds. zip64 when the archive needs it.

## 0.16.1 (2026-10-22)

- **Schema repinned to schema-dist `v0.32.2-dist.41`** (canonical 00.32.02 unchanged: no schema file moved; `SCHEMA_DIST_TAG`, `SCHEMA_DIST_SERIAL` and `SCHEMA_MANIFEST_SHA256` move with it). Serial 41 adds one case to the `.owworld` conformance set, `fail-OW-14-stored-short` (80 cases now), with its row in `verdicts.json` and its generator; nothing else. The same pin as the npm SDK's 4.53.1.

## 0.16.0 (2026-10-22)

- **The producer line** (folder format v0.3.14, §4.2, Keel #477): `export_world` writes `producer` beside `source`, `{"tool": "onlyworlds", "version": <this package's version>, "input": "server"}` (`EXPORT_PRODUCER`). An export is always a folder's birth (the writer never writes over a folder), so the line is always the export's own, also when a `GET /world` body carries another folder's. A folder written from a read one (a branch, a copy) keeps its maker's `producer` verbatim, and one with none gets none: a later writer never invents it. An `input` word the package does not know reads like any other. A tool that runs the export in its own name passes `producer=` (keel's nightly snapshots: `{"tool": "keel", "version": ..., "input": "server"}`), written in place of the package's line on the folder it makes; only the shape is checked (exactly `tool`, `version`, `input`, each a non-empty string, `input` any word), a ValueError before anything is read, and it never replaces a line a folder already carries. The OKF export carries `producer` into `world.md` beside `source` and `exported_as`.
- **`patch_world` never sends what only a folder carries**: handed a folder's `world.json`, it leaves out `format_version`, `writable`, `source`, `exported_as`, `producer`, `api` and the `snapshot_*` keys (`WORLD_FOLDER_KEYS`), where keel answered a 422 before. The push loop sends element writes only, never a world PATCH, as before.
- **Folder format v0.3.14**: `FORMAT_VERSION` moves to `0.3.14`, so a folder this package writes is stamped 0.3.14 at its birth (a carried stamp is kept, as before).
- **Schema repinned to schema-dist `v0.32.2-dist.40`** (canonical 00.32.02 unchanged: no schema file moved; `SCHEMA_DIST_TAG`, `SCHEMA_DIST_SERIAL` and `SCHEMA_MANIFEST_SHA256` move with it). Serial 40 adds one case to the `.owworld` conformance set, `fail-OW-14-crc` (an entry whose bytes fail its CRC is refused, 79 cases now), with its row in `verdicts.json` and its generator; nothing else. The same pin as the npm SDK's repin.

## 0.15.0 (2026-10-22)

- **Folder format v0.3.13**: §4.7, the `.owworld` archive, is RULED. `FORMAT_VERSION` moves to `0.3.13`, so a folder this package writes is stamped 0.3.13 at its birth (a stamp a folder already carries is kept, as before). Older stamps read as before; the doctor's flag 9 still names a folder stamped older than the package. This package reads and writes folders, not archives, so nothing else moved.
- **Schema repinned to schema-dist `v0.32.2-dist.39`** (canonical 00.32.02 unchanged: no schema file moved; `SCHEMA_DIST_TAG`, `SCHEMA_DIST_SERIAL` and `SCHEMA_MANIFEST_SHA256` move with it). The dist now carries the archive's 78-case conformance set at `fixtures/owworld/`, vendored in `codegen/` with the rest of the tree and not shipped in the wheel. Ahead of the npm SDK, whose main still pins dist.37.

## 0.14.3 (2026-10-22)

- **`hidden` is a read-only field** (keel PR 160, #537: `hidden: true` rides an element body only for a reader who still sees a hidden element). It joins `READ_ONLY_FIELDS` and the push loop's never-sent list, so a read body round-trips and a push never carries it. CI's wire test found it the hour keel shipped it.

## 0.14.2 (2026-10-22)

- **The doctor's flag 8 finds a charter on any type.** A world that files its charter as a Construct with supertype Charter (BrainBoost; TC's audit run, OW Industry #9814) read as "no charter". Now any element with supertype Charter is the charter for the staleness check, and one that is not a Law gets its own finding, since keel's world page and the parlor read a Law with supertype Charter. The "no charter" finding's words name the guidance.

## 0.14.1 (2026-10-22)

- **Schema repinned to schema-dist `v0.32.2-dist.37`** (canonical 00.32.02 unchanged: no type, field or link moved; `SCHEMA_DIST_TAG`, `SCHEMA_DIST_SERIAL` and `SCHEMA_MANIFEST_SHA256` move with it). The dist added `profiles/` (identity, calendar with its fixture, packet, review), its folder lint reads known-of stubs and never `records/`, and its export example carries `source` and `exported_as`. Equal to the npm SDK's pin (4.48.1).

## 0.14.0 (2026-10-22)

- **The draught** (keel PR 155, D143, live 2026-10-22 02:05): `Client.draught(character_id, components=, mode=, as_of=, undated=, since=, budget=, depth=)` reads `GET /character/{id}/context`, one Character's context in one read; the seven policy keys as the document names them.
- **`list_page(ids=, created_by=)`**: the same PR's two list filters (`ids` 1 to 200 in the list's own order; `created_by` a membership id or `owner`). Both were reachable through `filter` before.

## 0.13.0 (2026-10-22)

- **`after` on the feed** (keel #514, PR 152, D142, live 2026-10-22 00:55): `Client.changes(after=...)` and `walk_changes(..., after=...)` send `GET /changes?after=<ISO time>`, only the changes made at or after that time (an upsert's `updated_at`, a delete's `deleted_at`; no offset means UTC). A filter, not a position: order, cursor, `has_more` and `head` are unchanged, and the walk passes the cursor back as `since` with the same `after` on every page. A kept cursor is still the exact "since my last visit"; `after` is "since yesterday" by the clock. A bad value is a 422 naming `after`.

## 0.12.0 (2026-10-21)

- **The doctor's packet** (`--packet`, `onlyworlds.doctor.packets`): the findings as work packets in the `packet` extension profile (schema-dist `profiles/packet.md`, dist.36; OW Parlor #492, keel PR 148). A JSON array of Relations with supertype `Work item`, subtype `open` and no `id` (the tool that lands one mints it): `x_packet_elements` holds one entry per element, `{type, id, reason}`, in flag order, an element with several findings carrying their reasons joined; the same ids sit on the Relation's typed link fields for the types it has one for (not law, map, marker, pin, relation); `x_packet_source` is `{server, world}`, the API base the world was read from or `null` for a folder; `x_packet_producer` is `{"tool": "onlyworlds doctor", "version": ...}`. Only findings that are facts about the world with an element go in: `kind: "message"` findings and a finding on the world itself (no charter) stay in the report. Empty on a clean run; past `PACKET_CAP` bytes (60,000, under keel's 64 KB extension cap) of the three keys it splits into several packets named `(i of n)`, each complete. `--json` and `--packet` together is exit 2. The doctor still writes nothing: a packet is output, landing it is the reader's act. Measured on Moppetopia's frozen copy: 20 findings, 19 entries, one packet.

## 0.11.0 (2026-10-21)

- **The doctor** (`onlyworlds.doctor`): a read-only check over a world, from a folder (`python -m onlyworlds.doctor PATH`, `doctor_folder`) or through the API (`--api` with `OW_API_KEY` and `OW_API_PIN`, or the toolkit's `ONLYWORLDS_API_KEY` and `ONLYWORLDS_API_PIN`, `doctor_api`). It runs the eight universal flags (OW Industry #495, Skeld's list): a link to an element that is not there, a Title whose holders changed with no dated Relation, an Event ending before it starts, an element with no links in or out, two elements of one type whose names collide once folded (a name shared across types is the format's own convention, a Location and its Pin or Zone, and is not counted), a stub never filled in two readings (a known-of stub older than `--days`, 6a; an element with no text in any of its type's text fields from the schema, never `description` alone, 6b; it skips the types with fewer than two prose fields beside `description`, map, marker, pin and relation, named in `compared["6b"].skipped_types`), a message unread after N days, a charter untouched after `--changes` changes; and on the folder door two file-side ones, a `format_version` older than `FORMAT_VERSION` and an `api_key` in a git-tracked `world.json`. Each flag that ran says how much it compared (`compared: n of m`); one it cannot evaluate is listed in `not_run` with its reason, never as clean. Flag 7 never runs (no read mark exists in the folder, the API or this package), and flag 2 does not run on keel's feed today: each element's upsert comes from its row at its latest `change_seq`, so a walk holds current bodies only. A finding on a parlor- or message-shaped element (supertype Message, Board, Work item, Spec, Heart, Vote or Sitting) carries `"kind": "message"` (other findings have no `kind`); the prose lists those last, under "Messages and room things", outside the count of things to look at, and they still make the exit code 1. Prose or `--json` (`world`, `ran`, `not_run`, `findings`, `compared`, `written: 0`); exit 0 clean, 1 findings, 2 nothing could be read. It never writes: no file, no API write, no fix.

## 0.10.4 (2026-10-21)

Folder format v0.3.12 (§4.5 rule 3: the records manifest, `records/RECORDS.json`, is a bare JSON array of producer entries). Nothing here writes `records/`, so the writer's behaviour is unchanged; `FORMAT_VERSION` and the `format_version` a written folder declares move to `0.3.12`.

## 0.10.3 (2026-10-20)

- **The schema**, repinned to schema-dist `v0.32.2-dist.29` (canonical `00.32.02`, Skeld, OW Council h58 #8811): two descriptions changed, a Narrative's `start_date` is when it is first told or recorded and its `end_date` when it stops being told (empty while still told); the span it recounts lives on its events. `SCHEMA_VERSION` is `00.32.02`; `ELEMENT_TYPES`, `FIELD_KINDS` and `PUBLIC_FIELDS` are unchanged. Equal to `@onlyworlds/sdk` 4.42.0's pin.

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

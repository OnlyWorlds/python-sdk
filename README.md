# onlyworlds (Python)

OnlyWorlds is an open standard for worldbuilding data: 22 element types (characters, locations, events, laws and the rest) that any tool can read and write. This is a Python client for its API, and a reader and writer for OnlyWorlds world folders (a world as a folder of JSON files). Python 3.12+, no runtime dependencies (the optional OKF export needs PyYAML).

## Install

```bash
pip install onlyworlds
```

The newest unreleased code: `pip install git+https://github.com/OnlyWorlds/python-sdk`.

## First run

Moppetopia is a public demo world. Its read-only key, `0000000001`, needs no account:

```python
from onlyworlds import Client

client = Client("0000000001")
print(client.get_world()["name"])
for c in client.list_page("character", filter={"name__icontains": "fluffington"})["data"]:
    print(" ", c["name"])
```

```
Moppetopia
  Admiral Fluffington
```

## Your own world

Create a world at [onlyworlds.com](https://www.onlyworlds.com); its keys are on the world's page. A new key is shown once, so copy it then.

- An `ow_r_` key reads, with no PIN: `Client("ow_r_…")`.
- An `ow_w_` key reads and writes. Writes also send a PIN: `Client("ow_w_…", "…")`.
- For code that writes, give it its own [agent seat](https://onlyworlds.github.io/docs/development/agents), a key for one tool or script. The seat's key and its `ow_s_` secret (passed as the PIN) work in one world, and you can remove them without touching your account PIN.

Elements are plain dicts:

```python
writer = Client("ow_w_…", "ow_s_…")
peak = writer.create("location", {"name": "Dragon Peak"})
writer.patch("location", peak["id"], {"supertype": "Mountain"})

for character in client.iter_elements("character", expand=["species"]):
    print(character["name"])
```

## World folders

A world folder is one JSON file per element, in [the world folder format](https://onlyworlds.github.io/docs/schema/folders). [Atlas](https://atlas.onlyworlds.com), the OnlyWorlds editor, reads and writes the same format.

```python
from onlyworlds import export_world, read_folder

export_world("moppetopia", api_key="0000000001")
folder = read_folder("moppetopia")
print(folder.world["name"], len(folder.elements), "elements")
```

An exported folder's `world.json` says where it came from and which part of the world it holds: `source` names the server, the world's id and when it was exported, and `exported_as` says whether the key read the whole world as its owner, as a member (with its role), or as one Character (a guest's slice). When the server can't say which (`GET /me` refused or missing), `exported_as` is left out rather than guessed. `producer` says which tool made the folder and from what: `{"tool": "onlyworlds", "version": "<this package's version>", "input": "server"}`. A folder written from another folder (a branch, a copy) keeps its maker's `producer` as it found it, and one with none gets none.

`write_folder(root, world, elements)` writes a folder from a world dict and a dict of element lists by type, keeping every key the world dict has. Reading never changes a file, and a file without an id is skipped and left alone.

A whole world also travels as one file, an `.owworld` (a zip by another name, the folder format's §4.7):

```python
from onlyworlds import read_world_file, write_world_file

write_world_file("moppetopia", "moppetopia.owworld")
world = read_world_file("moppetopia.owworld")
world.to_folder("moppetopia-copy")
```

`write_world_file` carries `world.json` byte for byte (its `producer`, `source` and `format_version` included) and the folder's parts, `elements/`, `spatial/`, `media/` and `records/`, and nothing else: never an `api` block, never a tool's own folder unless you hand it in (`private_dir=".atlas"`, which makes the file a private copy rather than one to send around). The same folder gives the same bytes on one Python. `read_world_file` checks the whole archive before it unpacks anything and refuses a file it cannot open safely with a `WorldFileError`, whose `reason` names one of the spec's twelve causes (`unsafe_path`, `collision`, `too_big`, ...). It gives the same verdict as the TypeScript and Unity SDKs on every case of the format's conformance set.

To send a folder's edits back, keep a copy exported before you edited, then push the difference:

```python
from onlyworlds import push

result = push("moppetopia-before", "moppetopia", api_key="ow_w_…", pin="ow_s_…", log_path="push.jsonl")
```

`push` sends only the fields that changed, retries what the server asks it to retry, checks that what came back is what it sent, and logs every write, so running it again skips what already landed. `dry_run=True` shows the plan without sending it.

A world kept in Notion becomes a folder without retyping it. Export the workspace or page from Notion as "Markdown & CSV", then:

```bash
python -m onlyworlds.notion Export.zip my-world --plan   # what would become what; writes nothing
python -m onlyworlds.notion Export.zip my-world
```

```python
from onlyworlds.notion import import_notion

report = import_notion("Export.zip", "my-world")
print(report.render())
```

A database whose title is one of the 22 types (`Characters`, `Locations`, any case, singular or plural), or that has a `Type` column naming one per row, becomes elements of that type. A column becomes a field when its name matches the field's (`Birth Date` is `birth_date`), and a relation column becomes a link when it matches a link field and its pages are in the export. Every other page becomes a Narrative, and so does each row of a database whose type the door cannot tell (supertype `notion`, the database's name as subtype). Nothing is dropped: a column that doesn't fit is kept as `x_notion_<column>`, and attachments a page links to are copied into `media/notion/`. Ids come from Notion's page ids, so importing the same export twice gives the same folder. The run ends with a report naming every column it could not place and every link it could not resolve, so you can see what to rename in Notion before the next export. No AI, no account. It is built on Notion's documented export shape; no real export has been through it yet.

A world kept in LegendKeeper becomes a folder through LegendKeeper's own API, read-only. It needs your project's API key (Project Settings, Developers, API Keys; LegendKeeper gives the API to projects whose owner is on a paid plan) and the project's id:

```bash
export LEGENDKEEPER_API_KEY=lk_...                                          # or --key-file PATH
python -m onlyworlds.legendkeeper --project ID my-world --plan                # what would become what; writes nothing
python -m onlyworlds.legendkeeper --project ID --map faction=Institution my-world
```

```python
from onlyworlds.legendkeeper import ApiSource, import_legendkeeper

report = import_legendkeeper(ApiSource(key), "ID", "my-world", type_map={"faction": "institution"})
print(report.render())
```

LegendKeeper has no element types, so a page's type comes from its tags: a tag that is one of the 22 type names (`character`, `Location`) types it, `--map TAG=TYPE` adds your own tags, and every other page becomes a Narrative (supertype `legendkeeper`). The page text becomes the description as Markdown. A sidebar or infobox row becomes a field when its key matches one (`Height` is `height`), and a titled link list (`Allies`) becomes a link field when it matches one and its targets fit; otherwise each link becomes a Relation element named by the list's title. A timeline's events become Events with LegendKeeper's raw minutes and formatted dates kept beside them; their `start_date` is left for you to set against the world's own calendar. Hidden pages and secret blocks are left out unless you pass `--include-hidden` or `--include-secrets`. Nothing else is dropped: whatever has no field is kept as `x_legendkeeper_<key>`, and the report names every key, link, document and omission. Ids come from LegendKeeper's ids, so a second import of the same project gives the same elements. The key is sent to LegendKeeper only, never written or printed. No AI. Map and board documents are not imported yet, and the door has been walked on a test project, not yet on a real world.

## Export to OKF

A world folder can be exported as a valid [Open Knowledge Format](https://github.com/GoogleCloudPlatform/open-knowledge-format) (OKF) 0.2 bundle, as the spec stands at one pinned commit (`onlyworlds.okf.OKF_COMMIT`): one markdown file per element, with its fields in the frontmatter, its text under headings and its links (in-prose `ow://` references included) as markdown links, plus an index per type. This needs PyYAML, which the rest of the package does not:

```bash
pip install "onlyworlds[okf]"
python -m onlyworlds.okf moppetopia moppetopia-okf
```

```python
from onlyworlds.okf import export_okf

report = export_okf("moppetopia", "moppetopia-okf")
print(report.elements, "elements,", len(report.notes), "notes")
```

The output directory must not exist yet. Anything the export leaves out (a file that isn't an element, a key that isn't a field, a link to the wrong type) is listed in `report.notes`; the command prints these on stderr. The same folder always gives the same bytes. What a bundle never carries: the server's bookkeeping (`change_seq`, `created_at`, who wrote what) and the world's key, so a bundle is a copy to read elsewhere, not a folder to sync.

## The Markdown pack

A world as a few merged Markdown files, sized for an AI notebook with source caps (NotebookLM: 50 sources a notebook, 500,000 words a source; Claude Projects: 30 MB a file). No extra needed:

```bash
python -m onlyworlds.pack moppetopia moppetopia-pack          # a world folder
OW_API_KEY=ow_r_… python -m onlyworlds.pack --api moppetopia-pack   # the key's world
```

`00-world.md` says which kind of key made the pack (the owner's, a member's with its role, a Character's view; never the key), then holds the world's own fields and an index of every element; then one file per element type, each element a `## Name` section with its fields in schema order and every link written as the name and type of what it points to. Room elements and extension fields are left out unless asked (`--rooms`, `--extensions`); a file past a cap splits into parts, and small files merge when the parts would pass the source cap (`--words`, `--bytes`, `--files`). Nothing is invented and nothing is cut: an unresolved link stays as its id, an oversize element gets a file of its own. The output directory must not exist yet; the same world gives the same bytes. Beside it: the OKF bundle (above) is one file per element with frontmatter and links as paths, for knowledge tools that follow links; the pack is merged prose for a notebook that reads it whole.

## Proposed changes

A member can propose a change for a keeper to accept instead of writing it (keel #519), and a world's owner can make every AI seat work that way:

```python
row = client.propose("character", cid, {"reputation": "Feared"}, evidence="Chapter 12")
for p in client.walk_world_proposals(state="open"):  # newest first; keepers see every row, others their own
    ...
client.accept_proposal("character", cid, row["id"])  # the keeper's own write; StaleProposal when a proposed field moved
client.decline_proposal("character", cid, row["id"], reason="not yet")
client.withdraw_proposal("character", cid, row["id"])  # the proposer's
```

With **AI seats propose, a person accepts** on for the world (`agent_writes_proposed` on `get_world()`, read-only), a seat's `patch`, `upsert` or link edit raises `ProposedError` (`.proposal`) instead of returning a body that is not the element; `push` counts those as `proposed` and never resends one. The doctor's flag 12 reports the queue's open and lapsed rows.

## The doctor

The doctor checks a world and reports what its keeper should look at, each finding with the element and the reason. It only reads: it never changes a file or sends a write.

```bash
python -m onlyworlds.doctor moppetopia            # a world folder
OW_API_KEY=ow_r_… python -m onlyworlds.doctor --api   # the key's world (OW_API_PIN when the key needs one)
```

```python
from onlyworlds import read_folder
from onlyworlds.doctor import doctor_folder

report = doctor_folder(read_folder("moppetopia"))
for finding in report.findings:
    print(finding["flag"], finding["element"], finding["reason"])
```

It looks for links to elements that are not there, Events that end before they start, elements with no links in or out, two elements of one type whose names collide once case, character width, spacing and punctuation are folded (a name shared across types, such as a Location and its Pin, is not one), stubs never filled (a known-of element older than `--days`, or an element with no text in any of its type's text fields, on every type but map, marker, pin and relation), and a charter Law untouched after `--changes` changes in the feed. On a folder it also checks `world.json`: a `format_version` older than this package's (flag 9), and an `api_key` in a `world.json` that git tracks (flag 10). On both doors it reads the world's own house rules (flag 11, the checks profile: `x_checks_rules` on the Charter Law, applied by `onlyworlds.apply_checks`) and names every element a rule finds short, with each rule's scoped and short counts, and every rule it cannot apply, with why. Each check says how much it could compare, and one it cannot run (a folder has no change feed; nothing records whether a message was read) is listed with the reason, never counted as clean. A finding on a message or a room thing (supertype Message, Board, Work item, Spec, Heart, Vote or Sitting) is marked `"kind": "message"` and listed last, outside the count of things to look at. `--json` prints the same report for a tool, and `--packet` prints the findings as work packets (the `packet` extension profile: a Relation with supertype `Work item`, its elements with a reason each under `x_packet_elements`, a JSON array, empty when clean) for a tool that lands them in a world or a parlor. The exit code is 0 when there is nothing to look at, 1 when there is (a message finding too), 2 when nothing could be read.

The API door reads the key from `OW_API_KEY` and the PIN from `OW_API_PIN`, or from the toolkit's `ONLYWORLDS_API_KEY` and `ONLYWORLDS_API_PIN` when those are not set.

## Errors

A failed call raises `ApiError` with the API's `code`, `param` (the field that failed) and `doc_url`, and flags for the cases you handle differently: `is_validation_error`, `is_auth_error`, `is_not_author`, `is_owner_only`, `is_id_conflict`, `is_resync_required`, `is_busy`, `is_precondition_failed`.

To write only if nobody changed an element since you read it, pass its `change_seq`: `client.patch("character", el["id"], {"name": "Mine"}, if_match=el["change_seq"])` (on `edit_links` too). If it moved, nothing is written and `PreconditionFailed` is raised, whose `current` is the element as it is now. The server never merges: compare the copy you edited from with `current`, and send again with `if_match=current["change_seq"]` or ask which version to keep.

## The change feed

```python
walk = client.walk_changes(saved_cursor)  # None for everything
for op in walk:
    ...  # op["op"] is "upsert" or "delete"
saved_cursor = walk.cursor  # opaque: keep it, don't parse it
```

To poll for news, `client.head()` reads where the feed is now, `{head, cursor, epoch, unchanged}`, without a page. The client keeps the last answer's `ETag` and sends it back as `If-None-Match`, so a poll where nothing moved is a 304 that keel does not count against the request budget, and `head()` then answers what it last saw with `unchanged=True`. Walk when `head` or `epoch` differs from the ones you last applied, and sleep between polls yourself: the package never sleeps for you. The method's docstring has the loop.

## Schema

The 22 element types and each field's kind are generated from the published [schema distribution](https://github.com/OnlyWorlds/schema-dist); `onlyworlds.SCHEMA_VERSION` and `onlyworlds.SCHEMA_DIST_TAG` say which one. `onlyworlds.PUBLIC_FIELDS` names, per type, the fields OnlyWorlds shows on a known-of element (one a guest sees only one step out) beside its name and description. The package's own version doesn't track the schema's.

### The room

A parlor (a chat room on a world) keeps its lines, board entries, work items, specs, hearts, votes, sittings and member cards in the world as ordinary elements, told apart by type and supertype and marked with `x_room_of` (the id of the world or sitting the room belongs to). `onlyworlds.ROOM_PAIRS` is the room profile's list of those `(type, supertype)` pairs, and `onlyworlds.is_room_element(element)` is true when a body or a `FolderElement` matches one (trimmed, case-blind, the whole word) and carries the mark. A pair without the mark is lore: a novel's letters are Narratives with supertype Message.

```python
from onlyworlds import is_room_element

# a lore view, unless the person asks for the room
lore = [el for el in folder.all_elements().values() if not is_room_element(el)]
```

A lore view (a list, a count, search, a graph, a story's context, a survey) leaves room elements out unless the person asks; the room's own views show them whole, and a writer writes them like any element. A Law with supertype `Charter` is lore on purpose. The profile: [`profiles/room.md`](https://github.com/OnlyWorlds/schema-dist/blob/main/profiles/room.md) in the schema distribution.

### A world's own words

A world may name its types in its own words: in a work world a Character is an *Employee*. The map is `x_names` on the World (`world.json` in a folder), and only what a person reads changes; the API, the folder and every id keep the standard's names. `onlyworlds.type_word(world, element_type, supertype=None, many=False)` gives the word to print, or `None` for the standard's name:

```python
from onlyworlds import type_word

word = type_word(folder.world, "character", many=True) or "Characters"
```

The profile: [`profiles/names.md`](https://github.com/OnlyWorlds/schema-dist/blob/main/profiles/names.md).

Not yet: typed element models, the account routes, a snapshot writer.

## Develop

```bash
uv sync
uv run pytest -q
uv run ruff check . && uv run mypy --strict src
uv run python codegen/generate_schema.py --check
uv run python codegen/generate_casefold.py --check
```

Three groups of tests run only when asked:

- `OW_CONFORMANCE_FIXTURE=<path>`: the folder-format conformance fixture from the Atlas repo.
- `OW_OPENAPI=https://www.onlyworlds.com/api/v2/openapi.json` (or a saved copy): checks the client's routes, parameters and fields against the API's own OpenAPI document.
- `OW_LIVE=1`: read-only calls against the demo world.

`OKF_REFERENCE_SRC=<path>` (the `src/` of an open-knowledge-format checkout) also runs OKF's own parser and viewer over an exported bundle.


## License

MIT. See `LICENSE`.

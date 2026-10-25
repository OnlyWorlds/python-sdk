# onlyworlds (Python)

OnlyWorlds is an open standard for worldbuilding data: 22 element types (characters, locations, events, laws and the rest) that any tool can read and write. This is a Python client for its API, and a reader and writer for OnlyWorlds world folders (a world as a folder of JSON files). Python 3.12+, no runtime dependencies (the optional OKF export needs PyYAML).

**Who writes this repository.** The package is maintained by Kael, one of a crew of AI minds working with the OnlyWorlds founder, who answers for it. Kael reads and answers its issues and pull requests; until the crew posts from an identity of its own, those replies post from the founder's account, so a reply from `tmoosting` may be Kael's. `CHANGELOG.md` is the crew's record as it was written: its crew names, room references and keel items (keel #519, the API server's own tracker) point at records outside this repository.

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

An element can be created hidden from its first moment: `writer.create("narrative", {"name": "The plot", "hidden": True})`, and the same on `upsert` (a PUT whose id is new) and each `bulk` item. Only the owner's keys and a co-builder's may; any other key gets `ApiError` 403 `hidden_not_allowed` (`err.is_hidden_not_allowed`), and nothing is created. On an update the mark is never sent: `patch` leaves it out, a PUT that replaces ignores it, and an existing element is hidden or shown through its own route on the site.

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

`write_world_file` carries `world.json` byte for byte (its `producer`, `source` and `format_version` included) and the folder's parts, `elements/`, `spatial/`, `media/` and `records/`, and nothing else: never an `api` block, never a tool's own folder unless you hand it in (`private_dir=".atlas"`, which makes the file a private copy rather than one to send around), and never a producer's records its `records/RECORDS.json` entry marks `"private": true` unless you ask (`include_private_records=True`); the manifest itself always travels as it is. A hidden element (`hidden: true` in its file) travels byte for byte, since the file is a copy; for a file you hand to someone else, `include_hidden=False` leaves every hidden element's file out whole, and a list passed as `hidden_left_out=` receives their paths. Nothing else changes, so a link from a visible element to a hidden one keeps an id the file no longer holds. The same folder gives the same bytes on one Python. `read_world_file` checks the whole archive before it unpacks anything and refuses a file it cannot open safely with a `WorldFileError`, whose `reason` names one of the spec's twelve causes (`unsafe_path`, `collision`, `too_big`, ...). It gives the same verdict as the TypeScript and Unity SDKs on every case of the format's conformance set.

To send a folder's edits back, keep a copy exported before you edited, then push the difference:

```python
from onlyworlds import push

result = push("moppetopia-before", "moppetopia", api_key="ow_w_…", pin="ow_s_…", log_path="push.jsonl")
```

`push` sends only the fields that changed, retries what the server asks it to retry, checks that what came back is what it sent, and logs every write, so running it again skips what already landed. `dry_run=True` shows the plan without sending it. `push` patches elements that are in both folders; it creates and deletes nothing. It never sends the hidden mark: an element you marked `hidden: true` in the folder but not in the copy from before is already on the server, visible, so `push` sends nothing for it (`result.hidden`) until you hide it there; a new element goes through `create`, `upsert` or `bulk`, which carry the mark.

The world's `origin` is a world's birth line, written once: a push sets it only on a first fill from a folder made elsewhere, never from a folder exported from the same world, and never over a first import. When `get_world()` serves `origin` null in both keys and the folder's `source.world` is not that world (or the folder has no `source` line, as a converter's first output), `push` sends the folder's `source` and `producer` from `world.json` in one `PATCH /world` and reports it in `result.origin`. `patch_world` sends the two only when you name them (`source=`, `producer=`; `None` clears one); a folder `world.json` handed to it keeps its own pair home, since that pair names the folder's maker.

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

A database whose title is one of the 22 types (`Characters`, `Locations`, any case, singular or plural), or that has a `Type` column naming one per row, becomes elements of that type. A column becomes a field when its name matches the field's (`Birth Date` is `birth_date`), and a relation column becomes a link when it matches a link field and its pages are in the export. Every other page becomes a Narrative, and so does each row of a database whose type the door cannot tell (supertype `Article`, the database's name as subtype). Nothing is dropped: a column that doesn't fit is kept as `x_notion_<column>`, and attachments a page links to are copied into `media/notion/`. Ids come from Notion's page ids, so importing the same export twice gives the same folder. The run ends with a report naming every column it could not place and every link it could not resolve, so you can see what to rename in Notion before the next export. No AI, no account. It has read two real exports of one small workspace, one with folders for sub-pages and one flat (the door's test fixtures); a third layout, folders named by title and id, is built from Notion's documented shape and not yet seen in a real export.

A world kept in LegendKeeper becomes a folder from LegendKeeper's own export file (Project Settings, Export; the `.lk` file or the JSON one), with no key and no account:

```bash
python -m onlyworlds.legendkeeper --file my-world.lk my-world --plan   # what would become what; writes nothing
python -m onlyworlds.legendkeeper --file my-world.lk --map faction=Institution my-world
```

or through LegendKeeper's own API, read-only, with your project's API key (Project Settings, Developers, API Keys; LegendKeeper gives the API to projects whose owner is on a paid plan) and the project's id:

```bash
export LEGENDKEEPER_API_KEY=lk_...                                          # or --key-file PATH
python -m onlyworlds.legendkeeper --project ID my-world --plan
python -m onlyworlds.legendkeeper --project ID --map faction=Institution my-world
```

```python
from onlyworlds.legendkeeper import ApiSource, import_legendkeeper

report = import_legendkeeper("my-world.lk", out_dir="my-world")  # the export file
report = import_legendkeeper(ApiSource(key), "ID", "my-world", type_map={"faction": "institution"})
print(report.render())
```

A project written by an OnlyWorlds push (each element's id in an `onlyworlds-id` row, its supertype and subtype as `ow-supertype:` and `ow-subtype:` tags) comes back as the same elements: the id is the one the row names, the tags fill the two fields, and extension keys return under their own names. Both roads give the same elements. The export file names no project, so its ids are keyed on the project's first top-level page; pass `--project ID` with `--file` to key them on the project's own id, the same ids the API road gives. LegendKeeper's Markdown export is not read: it loses the tags, the properties and the hidden marks.

LegendKeeper has no element types, so a page's type comes from its tags: a tag that is one of the 22 type names (`character`, `Location`) types it, `--map TAG=TYPE` adds your own tags, and every other page becomes a Narrative (supertype `Article`). The page text becomes the description as Markdown. A sidebar or infobox row becomes a field when its key matches one (`Height` is `height`), and a titled link list (`Allies`) becomes a link field when it matches one and its targets fit; otherwise each link becomes a Relation element named by the list's title. A timeline becomes a Narrative with supertype `Timeline` that holds its Events, with a child Narrative for each lane; the events keep LegendKeeper's raw minutes and formatted dates beside them; their `start_date` is left for you to set against the world's own calendar. What LegendKeeper hides stays hidden: a hidden page is imported with `hidden: true` (and every page under it), a hidden tab on a visible page becomes its own hidden Narrative, and so does each Secret block, the page keeping only its visible text, so nothing is dropped and nothing secret turns public. Templates are imported marked `x_legendkeeper_template`, and the tutorial pages a new project starts with are imported like the rest, since nothing marks them. Whatever has no field is kept as `x_legendkeeper_<key>`, and the report names every key, link, document and hidden thing. Ids come from LegendKeeper's ids, so a second import of the same project gives the same elements. The key is sent to LegendKeeper only, never written or printed. No AI. From the export file or the API, a map becomes a Map (its width and height from the map's bounds; `image_url` the image's address as LegendKeeper gives it, so the picture loads only as long as it stays on LegendKeeper's host) and each pin on it a Pin placed on the element it links, its position in image pixels counted from the map's bottom left as OnlyWorlds counts it (LegendKeeper stores it at zoom 0, so it is scaled by 2^max_zoom, and the report names each map's scale; a map with no max_zoom gives its pins no position rather than a guess), LegendKeeper's own position, icon and label kept beside it. A board becomes a Map with supertype `Board` (no image; its width and height the canvas's extent, positions counted from its bottom left as on a map, each shape placed through the frames and groups it sits in), its records kept whole in the folder's `records/legendkeeper/boards/<document id>.json` (the Map names the file in `x_legendkeeper_board_record`; `records/RECORDS.json` marks them private when a board is hidden or shows a hidden page) so the canvas can be restored: each page card a Pin on the card's page (a card showing another board a Pin on that board's Map, which takes this one as its `parent_map`), each frame a Zone with a Marker at each corner, each arrow bound at both ends to page cards or frames a Relation with supertype `Board link` between them (one that links a thing to itself is counted instead), and each sticky note and text a Narrative (supertype `Note`) with a Pin; the rest (shapes, drawings, images, bookmarks, the other arrows) is counted in the report, and what the source hides stays hidden on a board too. A map feature that is not a pin is named and not read. Read on two real export files of one tutorial project (six pages typed by hand, then a map of its own with two pins, the placement measured on both); the API road has been walked on two test projects, and on its tutorial map the API puts the same 16 pins on the same pixels as the export file.

A campaign kept in Kanka becomes a folder from Kanka's own JSON export (Campaign, Settings, Data, Export, JSON; free campaigns get it):

```bash
python -m onlyworlds.kanka export.zip my-world --plan   # what would become what; writes nothing
python -m onlyworlds.kanka export.zip my-world
```

```python
from onlyworlds.kanka import import_kanka

report = import_kanka("export.zip", "my-world")
print(report.render())
```

Each Kanka module becomes its type: characters Characters, locations Locations, organisations Institutions, notes, quests and journals Narratives (the text in `story`), families, races, items, creatures, events, abilities and maps their types, and any other module a Narrative with supertype `Article` (the module's folder as subtype). The entry becomes the description as Markdown, with the posts after it under their own headings; a mention becomes the entity's name. A location's parent becomes `parent_location`, a character's places `location`, its appearance and personality traits `physicality` and `mentality`, and an attribute named like a field (`Architecture`) fills it. A relationship becomes a Relation, and a two-way one is one Relation, not two. Exact duplicates (the same relationship or post made twice) fold into one, and the report names each fold. What Kanka hides stays hidden: a private entity is imported with `hidden: true`, a private post becomes its own hidden Narrative, and a visible entity's private details go into one hidden Narrative beside it, so nothing is dropped and nothing private turns public. Kanka's starter entries (`[Your Character Name]`, ...) are imported like the rest, since nothing in the data marks them, and the report names them. A tag becomes a Narrative that links each element carrying it, except that a visible tag never links a hidden element (the report names it). An entity's picture is followed into Kanka's `gallery/`: the element keeps the upload's uuid, name and extension as `x_kanka_image` and the report lists it, but the image file itself is not imported, since the folder format has no place for image files yet. Everything without a field is kept as `x_kanka_<key>`. Ids come from Kanka's ids, so a second import of the same campaign gives the same elements. No AI. Read on two real Kanka 3.15 exports of characters, locations, organisations, notes, a tag and a gallery; the other modules are built on the same shape and have not been seen in a file yet.

A world kept in World Anvil becomes a folder from World Anvil's own export (world settings, Export World, Export this World; free accounts get it). It opens a page, not a download: save that page from the browser as HTML, then:

```bash
python -m onlyworlds.worldanvil --file the-quay-world-export.html my-world --plan   # what would become what; writes nothing
python -m onlyworlds.worldanvil --file the-quay-world-export.html my-world
```

```python
from onlyworlds.worldanvil import import_worldanvil

report = import_worldanvil("the-quay-world-export.html", "my-world")
print(report.render())
```

Each article becomes its template's type: Character a Character, Species a Species, Geographic Location a Location (and Settlement, Organization, Item, Ethnicity, Myth / Legend, Vehicle, Profession and a few more, by one table, `TEMPLATE_TYPES`); an article of any other template becomes a Narrative (supertype `Article`, the template's name as subtype). The body becomes the description as Markdown. A link to another article becomes its name in the text, with the linked element kept by id in `x_worldanvil_mentions`; a mention World Anvil left unresolved (`@Ada`) stays as you typed it, and the report names it. A template field named like a field (`Height`) fills it; every other (`Gender`, `Eyes`) is kept as `x_worldanvil_<field>`. The article's category is kept as `x_worldanvil_category`, and its creation, last update and publication dates as ISO dates (`x_worldanvil_created`, `_updated`, `_published`; a date the door cannot read exactly is kept as printed and named). The author is named in the report, never written into the world. What World Anvil hides stays hidden: an article that is not public is imported with `hidden: true`, and a Secret block becomes its own hidden Narrative, so nothing is dropped and nothing private turns public. The report names every field, link, mention and hidden article, and anything in the page the door did not read. Ids come from World Anvil's article ids, so a later export of the same world gives the same elements. No AI. Read on two real exports of a small world on a free account (three articles, links, a category); private articles and Secrets (a paid feature) have not been seen in a file yet.

A project kept in Campfire becomes a folder from Campfire's own export (File, Export Elements, the html format, Select all Elements; free accounts get it). It is a document, not data, and the door reads it as one:

```bash
python -m onlyworlds.campfire --file "Campfire Export.html" my-world --plan   # what would become what; writes nothing
python -m onlyworlds.campfire --file "Campfire Export.html" my-world --project "Harbour Town"
```

```python
from onlyworlds.campfire import import_campfire

report = import_campfire("Campfire Export.html", "my-world", project="Harbour Town")
print(report.render())
```

Each element heading becomes an element, its description the description. The file names no module, so the type is read from the template's own panel words (a Basic Information panel with Place of Residence is a Character, Location Details a Location; Species, Cultures, Items, Languages, Religions, Philosophies, Systems, Magic and Maps are mapped too, by one table, `MODULE_TYPES`); anything else becomes a Narrative (supertype `Article`). The report names, for each element, the panel words its type was read from. Every filled panel value is kept as `x_campfire_<panel>_<label>` (`x_campfire_basic_information_full_name`), a text panel as `x_campfire_<panel>`; an em dash is empty and not written. A document carries no ids, no links and no hidden marks, and the report says so each time: ids come from each element's type and name, so a later export gives the same elements only while the names hold. The file names no project either: `--project NAME` names the world and keys every id on it, so two projects exported under Campfire's default title, "Campfire Export", stay apart; without it the world takes the document's title. The one link made is a Character's Place of Residence that names a Location in the same export. No AI. Read on one real export (a Character and a Location); the other modules have not been seen in a file yet.

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

A hidden element (`hidden: true`) is hidden from whoever the world is handed to, and a bundle is handed on: it is left out unless you pass `--hidden` (`hidden=True`), and nothing of it is written, its name included (no file, no index line, links to it left out, an in-prose reference reduced to its own label); `report.hidden_left_out` and world.md's `onlyworlds_export` block count it. Kept, its frontmatter says `hidden: true` and every link to it `(hidden)`.

The output directory must not exist yet. Anything the export leaves out (a file that isn't an element, a key that isn't a field, a link to the wrong type) is listed in `report.notes`; the command prints these on stderr. The same folder always gives the same bytes. What a bundle never carries: the server's bookkeeping (`change_seq`, `created_at`, who wrote what) and the world's key, so a bundle is a copy to read elsewhere, not a folder to sync.

## The Markdown pack

A world as a few merged Markdown files, sized for an AI notebook with source caps (NotebookLM: 50 sources a notebook, 500,000 words a source; Claude Projects: 30 MB a file). No extra needed:

```bash
python -m onlyworlds.pack moppetopia moppetopia-pack          # a world folder
OW_API_KEY=ow_r_… python -m onlyworlds.pack --api moppetopia-pack   # the key's world
```

`00-world.md` says which kind of key made the pack (the owner's, a member's with its role, a Character's view; never the key), then holds the world's own fields and an index of every element; then one file per element type, each element a `## Name` section with its fields in schema order and every link written as the name and type of what it points to. Room elements, proposed elements, hidden elements and extension fields are left out unless asked (`--rooms`, `--proposed`, `--hidden`, `--extensions`). A hidden element (`hidden: true`) is hidden from whoever the world is handed to, never from you: left out, nothing of it is written, its name included (a link to it is left out, an in-prose reference keeps only its own words), and `00-world.md` counts it in its opening lines; with `--hidden` each kept one is labelled `hidden` under its heading, on its index line and on every link to it. A proposed element is an AI seat's new element not yet reviewed (it carries `x_review_proposed`) and is not canon: `00-world.md` counts the ones left out in its opening lines, and with `--proposed` each kept one is labelled `proposed, not yet reviewed` under its heading, on its index line and on every link to it; a file past a cap splits into parts, and small files merge when the parts would pass the source cap (`--words`, `--bytes`, `--files`). Nothing is invented and nothing is cut: an unresolved link stays as its id, an oversize element gets a file of its own. A world with its own words for the types (`x_names`, below) gets them on its headings and element lines, the standard's type in brackets for the AI: `### Employees (Character)`; file names keep the standard's slugs. The output directory must not exist yet; the same world gives the same bytes. Beside it: the OKF bundle (above) is one file per element with frontmatter and links as paths, for knowledge tools that follow links; the pack is merged prose for a notebook that reads it whole.

## Proposed changes

A member can propose a change for a keeper to accept instead of writing it, and a world's owner can make every AI seat work that way:

```python
row = client.propose("character", cid, {"reputation": "Feared"}, evidence="Chapter 12")
for p in client.walk_world_proposals(state="open"):  # newest first; keepers see every row, others their own
    ...
client.accept_proposal("character", cid, row["id"])  # the keeper's own write; StaleProposal when a proposed field moved
client.decline_proposal("character", cid, row["id"], reason="not yet")
client.withdraw_proposal("character", cid, row["id"])  # the proposer's
client.review_new_element("character", new_id, "accept")  # a marked new element; decline deletes it
```

With **AI seats propose, a person accepts** on for the world (`agent_writes_proposed` on `get_world()`, read-only), a seat's `patch`, `upsert` or link edit raises `ProposedError` (`.proposal`) instead of returning a body that is not the element; `push` counts those as `proposed` and never resends one. A seat's new element lands marked (`x_review_proposed`) and the queue lists it as a `kind: "new_element"` row beside the proposals (`kind: "proposal"`); a keeper settles it with `review_new_element` (422 `not_proposed`, `is_not_proposed`, when there is no mark). A proposal's `fields` holds only what differs from the element, and a PUT's `omitted` names the fields it would empty; a seat's write that changes nothing makes no row and answers 200. The doctor's flag 12 reports the queue's open and lapsed rows, the proposals and the marked new elements counted apart.

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

It looks for links to elements that are not there, Events that end before they start, elements with no links in or out, two elements of one type whose names collide once case, character width, spacing and punctuation are folded (a name shared across types, such as a Location and its Pin, is not one), stubs never filled (a known-of element older than `--days`, or an element with no text in any of its type's text fields, on every type but map, marker, pin and relation), and a charter Law untouched after `--changes` changes in the feed. On a folder it also checks `world.json`: a `format_version` older than this package's (flag 9), and an `api_key` in a `world.json` that git tracks (flag 10). On both doors it reads the world's own house rules (flag 11, the checks profile: `x_checks_rules` on the Charter Law, applied by `onlyworlds.apply_checks`) and names every element a rule finds short, with each rule's scoped and short counts, and every rule it cannot apply, with why. On a spine world (one where an element carries an `x_spine_` key), flag 13 reads each element with `read_spine_element` and names an off-list supertype on a listed type, every value the reader drops and a probe not in the probe form; then, on a source world, it checks that each row (an Object, Construct, Location or Law of a listed kind, the Charter too) is kept by exactly one Seat (a Title with supertype `Seat`, through its field for the row's type; any other Title neither owns nor counts), that every `x_spine_depends_on` id is in the world (not through a guest key), that a `legacy` or `provenance` row has an Event with supertype `Retirement` that names it in `x_spine_retires` and links it through its typed field where the type has one (`objects`, `constructs`, `locations`; an Event has no `laws` field, so a Law's retirement is attributed by the key alone; only through a key that sees every element, hidden ones too), that no row is still at `gone` (its retirement is unfinished), and that no two rows of one row type share a name once trimmed and folded for case (a Seat or any other element is outside that rule). Whether a probe passes and `x_spine_probed` are not checked, and the report says so. A projection (a public world built from a spine, each row naming its keeping Seat in `x_spine_owner`) is marked on its World with `x_spine_projection`, `{source, at}`: `source` the projected-from world's id as a string, a UUID that is no element's id in this world, and `at` the ISO 8601 time of the last rebuild, which must parse; each is a finding on the world otherwise. On a projection only the projection's own checks run: every row must carry `x_spine_owner` (the keeping Seat's name in the source, which need match nothing in the projection) and no element may be hidden; the source's checks do not run there, and the report names each. On an unmarked world `x_spine_owner` is a finding (the projection's third check), and a malformed mark is a finding on the world, which is then read as unmarked. Each check says how much it could compare, and one it cannot run (a folder has no change feed; nothing records whether a message was read) is listed with the reason, never counted as clean. A finding on a message or a room thing (supertype Message, Board, Work item, Spec, Heart, Vote or Sitting) is marked `"kind": "message"` and listed last, outside the count of things to look at. `--json` prints the same report for a tool, and `--packet` prints the findings as work packets (the `packet` extension profile: a Relation with supertype `Work item`, its elements with a reason each under `x_packet_elements`, a JSON array, empty when clean) for a tool that lands them in a world or a parlor. The exit code is 0 when there is nothing to look at, 1 when there is (a message finding too), 2 when nothing could be read.

The API door reads the key from `OW_API_KEY` and the PIN from `OW_API_PIN`, or from the toolkit's `ONLYWORLDS_API_KEY` and `ONLYWORLDS_API_PIN` when those are not set.

## The lint

The lint checks a world folder's shape against the schema: a file outside the 22 type folders, a missing or duplicate `id`, a key that is not a field of its type, a value of the wrong shape, a link that does not resolve inside the folder or points at the wrong type. The doctor reads what a world says; the lint reads how it is written down.

```bash
python -m onlyworlds.lint moppetopia
```

One line per problem, then the count it checked. Exit 0 when clean, 1 with problems, 2 when the folder is not a world folder. The checker is schema-dist's own `walk/lint_folder.py`, copied byte for byte at this package's schema pin and run on the dist's `schema.json`, so it gives the same report as the dist's command and needs no YAML library. From code: `onlyworlds.lint.lint(folder)` returns the report (`problems`, `warnings`, `summary`).

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

### The spine

A world may map a software ecosystem: what is built, where each thing lives, who keeps it and what it depends on. Each kind is a type with a supertype from a closed list (`onlyworlds.SPINE_KINDS`: a `Tool` or a `Package` is an Object, a `Repo` a Location, a `Seat` a Title), and `x_spine_*` keys carry the rest. `onlyworlds.read_spine_element(type, element)` reads one element as the profile does: its kind (or `off-list`), each key as read or `None`, and every value it left out, named in `dropped`.

```python
from onlyworlds import read_spine_element

read = read_spine_element("object", {"supertype": "Package", "x_spine_status": "live"})
read.kind, read.status  # ("Package", "live")
```

Whether a row has one owner, whether its dependencies resolve, whether a retired row's Event names it in `x_spine_retires` and links it, whether a row is still at `gone` and whether two rows share a name is the world's audit, not a reader of one element: the doctor's flag 13 does it. The profile: [`profiles/spine.md`](https://github.com/OnlyWorlds/schema-dist/blob/main/profiles/spine.md).

Not yet: typed element models, the account routes, a snapshot writer.

## Develop

```bash
uv sync
uv run pytest -q
uv run ruff check . && uv run mypy --strict src
uv run python codegen/generate_schema.py --check
uv run python codegen/generate_casefold.py --check
uv run python codegen/generate_nfc.py --check
```

Three groups of tests run only when asked:

- `OW_CONFORMANCE_FIXTURE=<path>`: the folder-format conformance fixture from the Atlas repo.
- `OW_OPENAPI=https://www.onlyworlds.com/api/v2/openapi.json` (or a saved copy): checks the client's routes, parameters and fields against the API's own OpenAPI document.
- `OW_LIVE=1`: read-only calls against the demo world.

`OKF_REFERENCE_SRC=<path>` (the `src/` of an open-knowledge-format checkout) also runs OKF's own parser and viewer over an exported bundle.


## Licence and contributions

The code is MIT (`LICENSE`). Issues are welcome: a bug, a wrong word, a thing you could not do. Pull requests are read; a small fix is usually taken as is, and a change to what the package does is better opened as an issue first, since it may already be built or ruled out. A reply can take a few days. A vulnerability goes privately, never in an issue: `SECURITY.md`. What we ask at the door, and what you can expect: [the code of conduct](https://github.com/OnlyWorlds/OnlyWorlds/blob/main/CODE_OF_CONDUCT.md).

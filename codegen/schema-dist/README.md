# OnlyWorlds schema-dist

The OnlyWorlds schema, packaged for tools: the YAML, the same schema decoded to JSON, a reference decoder, the rulings that settle what the YAML leaves open, an example world, and hashes to pin by.

The files here are generated. The OnlyWorlds platform rebuilds and publishes them after every schema change, so a fix belongs upstream: open an issue rather than a pull request. The standard itself lives in [OnlyWorlds/OnlyWorlds](https://github.com/OnlyWorlds/OnlyWorlds).

Each serial (one numbered publication of these files, tagged `v<schema version>-dist.<serial>`) has release notes that say what changed and date each ruling. What we ask at the door, and what you can expect: the [code of conduct](https://github.com/OnlyWorlds/OnlyWorlds/blob/main/CODE_OF_CONDUCT.md).

## Contents

| File | What it is |
|---|---|
| `schema.json` | the decoded schema: every field of every type with its kind, link target and description. Plain JSON, so any language or engine reads it without Python or a YAML parser |
| `schema/*.yaml` | the 22 element types, `base_properties` and `world`: the same content as the standard's YAML. The bytes differ (LF line endings, blank lines), the parsed data does not |
| `example/hyperion/` | Hyperion, the public example world, as a world folder. Every file in it passes the decoded schema |
| `example/world-export.json` | the world-export envelope (`format: onlyworlds-world-export`, the portal's one-file download) for one small fixed world: a single link, a multi-link, an extension field. It is the emitter's own output, pinned by a keel test, so a reader of the envelope tests against the real shape |
| `presentation.json` | default colour group and icon per type (`family` names the group by its colour: `blue`, `green`, `pink`, `amber`, a visual aid for drawing the 22 types, not part of the standard), and the four colours as light/dark pairs. Defaults: tools may override them. The colours were checked for colour-vision deficiency, so re-run that check before changing one. Each type also lists its `public` fields: what the platform shows of an element a reader knows of but does not see whole, beside its name and description |
| `pairs.json` | the link a drag between two types writes, for the pairs of the 22 types a tool may offer (same-kind pairs and fields that name a role are absent by ruling). Each key names the pair by its two type slugs in alphabetical order (`ability+character`); `on` is the type that carries the field, `field` the field's name, and `holds` whether the drop puts the dragged element inside the target (one square under the other) or only draws a line. Presentation, as `presentation.json` is, not part of the standard: a tool that offers drags reads this file and offers nothing else, and a pair absent here draws no line |
| `profiles/` | extension profiles: one page per named extension field that tools agree to read the same way (`x_identity_key`, one being in several worlds; `atlas_calendar`, a world's own calendar; `x_packet_*`, a work item's elements with a reason each; `x_review_*`, proposed and checked marks; `room`, a convention profile: the nine type-and-supertype pairs a parlor puts in a world, and the rule that a lore view leaves them out; `message`, a convention profile: a message between a world's members (a Narrative with supertype Message), to whom it is addressed, whether its sender is proved, and each reader's read mark; `checks`, machine-checkable house rules on a world's Charter; `x_names`, a world's own words for the 22 types, on the World; `spine`, a world that maps a software ecosystem: a closed list of kinds as supertypes, eleven `x_spine_*` keys, a day count from a stated day 0; `import-map`, per source tool, from that tool's own tags to the 22 types, which an import offers the user and never applies silently, LegendKeeper first; `address`, a convention profile: one element's three spellings, the site's address and the two `ow://` text forms, with an optional moment and lens, and the rule that a field holding one is public text, never resolved; `lens`, a convention profile: a saved way of reading a world (a Construct with supertype Lens), its links the anchors, `x_lens` the recipe (how far, which types, how far back, how much), and the one resolution every reader agrees on; `charter`, a convention profile: a world's reading aids, the Charter (the rules for people and AIs here), the Guide (start here) and the Domains (the places in the world), each marked with `x_charter_of`, and the one packet every tool shows first at a world's door; `strand`, a convention profile: one story in a world in miniature, a Narrative, one of its Events, that Event's place, the story's protagonist and where the hero is now, named on the World by `x_strand`'s three ids and read through four existing links, never one slot filled from another). What it holds, how a reader reads it, what a writer must keep. A profile may carry a data file beside its page (`import-map.json`, the table a door loads). A profile with a `<name>.fixture.json` beside it has a conformance fixture: cases a reader must pass |
| `walk/schema_walk.py` | the reference decoder, in Python: reads the YAML and returns each type's fields. `schema.json` is its output. One module; its only dependency is PyYAML |
| `walk/rulings.yaml` | rulings the YAML cannot carry (nullability, empty strings, extension fields). Code in any language should follow these rows |
| `walk/lint_folder.py` | the folder check: run it on a world folder and it names every key that is not a field of its type, every link that does not resolve or points at the wrong type, every value of the wrong shape, and a `world.json` that carries an `api` block while git tracks it (a linked folder is never committed, folder spec 4.6 d). The example world passes it at every publish |
| `fixtures/owworld/` | the `.owworld` conformance set (folder spec 4.7): 96 zips, one per check and one cause each, with `verdicts.json` saying what a reader must answer for every one (accept, or refuse with its cause from the one list) and what a writer may emit. A world-file reader in any language runs the set and compares; the Unity SDK, the TypeScript SDK and the reference checker give one verdict on all of it. `generate.py` rewrites every zip byte for byte (`python fixtures/owworld/generate.py --out fixtures/owworld`); `CaseFolding-15.1.0.txt` is Unicode's file as published, the C and S rows every reader folds names by, never a runtime's own fold |
| `VERSION` | three `key: value` lines: the canonical schema version, the dist serial, the publish date |
| `MANIFEST.json` | the sha256 of every file above (not of itself) |

## Reading schema.json

`base` lists the fields every element has; `types.<type>` lists each type's own fields, in the YAML's order; `world` lists the World's. An element's data is its base fields plus its type's fields.

Field names are the keys in element data, on the wire and in a world folder. They are lowercase (`id`, `name`, `image_url`), except the six ability scores on Character (`STR` to `CHA`). `base_properties.yaml` capitalises its names (`Id`, `Image_URL`); `schema.json` already gives them as data spells them.

Each field has a `kind`, explained in `kinds` at the top of the file:

- `scalar_str`: a string. The empty string means unset.
- `scalar_int`: an integer, or null for unset.
- `single`: one element's id, a UUID string, or null. `target` names the type it points to.
- `multi`: an array of UUID strings, possibly empty. `target` names their type.
- `generic`: a link to an element of any type. Only `pin.element` has it. In data it is two keys, `element_type` (the type's slug, such as `"character"`) and `element_id` (the UUID), both set or both null; `type_key` and `id_key` name them.
- `list`: an array (World fields only); `items` gives the kind of each entry.

A field whose YAML sets `minimum` or `maximum` carries them, as written (the 0 to 100 and -100 to 100 scales). They are advisory: the platform accepts any integer, so show them (a slider's range) and never reject a value past one (`walk/rulings.yaml`, `maximum-is-advisory-and-zero-means-unbounded`).

Only `id` and `name` are required. Element bodies read from the API also carry keys the schema does not declare: `type`, `created_at`, `updated_at`, `change_seq`, `created_by`, `changed_by`, `changed_via` and `changed_client`, all set by the server. Fields starting `x_` (and the tool prefixes `atlas_`, `shadow_`) are extensions, which a tool keeps and writes back unchanged. A few have a published meaning, one page each in `profiles/`. `walk/rulings.yaml` has the rest.

## The example world

`example/hyperion/` is a world folder: `world.json` for the world, and one JSON file per element at `elements/<type>/<name>--<id tail>.json`. The `id` inside a file is the element's identity; the filename is only for people. It needs no account or key: load it, check it against `schema.json`, and you have tested your reader on real data. The format is described at [World Folders](https://onlyworlds.github.io/docs/schema/folders). The folder format is at 0.3.21 (the spec's own version line); a folder stamps `format_version` from it.

## Using the walk (Python)

```bash
python walk/schema_walk.py schema > schema.json
```

That prints the decoded schema; it is the same bytes as the shipped `schema.json`. In code:

```python
from schema_walk import decode_schema, flatten_fields  # vendored from walk/

decoded = decode_schema("schema", note=print)    # base, types, world, as in schema.json
fields = decoded["types"]["character"]

import yaml
doc = yaml.safe_load(open("schema/character.yaml", encoding="utf-8"))
fields = flatten_fields(doc, "character", note=print)   # one type, the short form
# [{'name': 'physicality', 'kind': 'scalar_str'}, {'name': 'mentality', 'kind': 'scalar_str'}, ...]
```

Pass a `note` sink. A field type the walk does not know is skipped, and with the default sink it is skipped silently, so an older walk reading a newer schema would lose fields without a word. Extra output from `flatten_fields` is opt-in: `include_required`, `include_desc`, `include_sections`.

## Checking a world folder

```bash
python walk/lint_folder.py path/to/world-folder
```

One line per problem (`elements/creature/x.json: `characters` is not a field of creature`), then the count it checked. Exit 0 when clean, 1 with problems. Server keys, the folder format's own keys (`local_updated_at`, `server_updated_at`, `image_media_id`) and extension prefixes pass; any other undeclared key does not. A string may be null on disk (read as the unset string). It decodes the YAML through the walk beside it, so its view of the schema is the walk's; `--schema DIR` points it at another copy.

## Versions

`VERSION` holds `key: value` lines; it is not a bare version string. The canonical version is written zero-padded there and without the padding in tags: canonical `00.33.00` is tagged `v0.33.0-dist.<serial>`. The serial counts publishes of the same canonical version, such as a presentation fix or a new ruling.

## Pinning

Pin a tag for people and a hash for machines. Tags can move; hashes can't.

1. Fetch your pinned tag.
2. Record the hash of `MANIFEST.json` on your side (a lockfile, your CI config). Comparing a tree only against the manifest that came with it proves the two agree, not that they are the files you accepted.
3. In CI, check every listed file against the manifest and fail on a mismatch.
4. Print the pin's age from `VERSION`'s publish date and warn when it grows old. Warn, don't fail.

## Vendoring

Copying these files into your repo is supported, and it makes offline builds possible. Editing your copy is not: the walk is the one decoder of what the YAML means, and a patched copy is how one standard turns into several. If you need something the walk does not return, open an issue; the opt-in flags were added that way.

The list of element types is a literal inside the walk, so a 23rd type would arrive as a new dist.

## Links

[The standard](https://github.com/OnlyWorlds/OnlyWorlds) · [Docs](https://onlyworlds.github.io) · [Games and engines](https://onlyworlds.github.io/docs/development/games) · [TypeScript SDK](https://github.com/OnlyWorlds/sdk) · [Python SDK](https://github.com/OnlyWorlds/python-sdk) · [Unity SDK](https://github.com/OnlyWorlds/unity-sdk) · [Council](https://council.onlyworlds.com)

## Licence and contributions

MIT. See [LICENSE](LICENSE). The files here are generated, so a fix to the schema belongs upstream in [OnlyWorlds/OnlyWorlds](https://github.com/OnlyWorlds/OnlyWorlds); an issue here is right for a wrong hash, a reader that disagrees with a fixture, or a word in this README. Security reports: see [SECURITY.md](SECURITY.md). A reply can take a few days.

Maintained by Skeld, an AI agent working for Titus. Issues and pull requests are read and answered here.

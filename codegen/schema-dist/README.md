# OnlyWorlds schema-dist

The OnlyWorlds schema, packaged for tools: the YAML, the same schema decoded to JSON, a reference decoder, the rulings that settle what the YAML leaves open, an example world, and hashes to pin by.

The files here are generated. The OnlyWorlds platform rebuilds and publishes them after every schema change, so a fix belongs upstream: open an issue rather than a pull request. The standard itself lives in [OnlyWorlds/OnlyWorlds](https://github.com/OnlyWorlds/OnlyWorlds).

## Contents

| File | What it is |
|---|---|
| `schema.json` | the decoded schema: every field of every type with its kind, link target and description. Plain JSON, so any language or engine reads it without Python or a YAML parser |
| `schema/*.yaml` | the 22 element types, `base_properties` and `world`: the same content as the standard's YAML. The bytes differ (LF line endings, blank lines), the parsed data does not |
| `example/hyperion/` | Hyperion, the public example world, as a world folder. Every file in it passes the decoded schema |
| `presentation.json` | default family and icon per type, and the four family colours as light/dark pairs. Defaults: tools may override them. The colours were checked for colour-vision deficiency, so re-run that check before changing one |
| `walk/schema_walk.py` | the reference decoder, in Python: reads the YAML and returns each type's fields. `schema.json` is its output. One module; its only dependency is PyYAML |
| `walk/rulings.yaml` | rulings the YAML cannot carry (nullability, empty strings, extension fields). Code in any language should follow these rows |
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

Only `id` and `name` are required. Element bodies read from the API also carry keys the schema does not declare: `type`, `created_at`, `updated_at`, `change_seq` and `created_by`, all set by the server. Fields starting `x_` (and the tool prefixes `atlas_`, `shadow_`) are extensions, which a tool keeps and writes back unchanged. `walk/rulings.yaml` has the rest.

## The example world

`example/hyperion/` is a world folder: `world.json` for the world, and one JSON file per element at `elements/<type>/<name>--<id tail>.json`. The `id` inside a file is the element's identity; the filename is only for people. It needs no account or key: load it, check it against `schema.json`, and you have tested your reader on real data. The format is described at [World Folders](https://onlyworlds.github.io/docs/schema/folders).

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

## Versions

`VERSION` holds `key: value` lines; it is not a bare version string. The canonical version is written zero-padded there and without the padding in tags: canonical `00.31.00` is tagged `v0.31.0-dist.<serial>`. The serial counts publishes of the same canonical version, such as a presentation fix or a new ruling.

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

## Licence

MIT. See [LICENSE](LICENSE).

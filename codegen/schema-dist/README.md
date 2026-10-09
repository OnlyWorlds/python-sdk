# OnlyWorlds schema-dist

The OnlyWorlds schema, packaged for tools: the YAML, a reference decoder, the rulings that resolve what the YAML leaves open, and hashes to pin by.

The files here are generated. The OnlyWorlds platform rebuilds and publishes them after every schema change, so a fix belongs upstream: open an issue rather than a pull request. The standard itself lives in [OnlyWorlds/OnlyWorlds](https://github.com/OnlyWorlds/OnlyWorlds).

## Contents

| File | What it is |
|---|---|
| `schema/*.yaml` | the 22 element types, `base_properties` and `world`, byte-identical to the standard |
| `presentation.json` | default family and icon per type, and the four family colours as light/dark pairs. Defaults: tools may override them. The colours were checked for colour-vision deficiency, so re-run that check before changing one |
| `walk/schema_walk.py` | the reference decoder: reads the YAML and returns each type's fields. One module; its only dependency is PyYAML |
| `walk/rulings.yaml` | rulings the YAML cannot carry (nullability, extension fields, known divergences). Code generators in any language should follow these rows |
| `VERSION` | three `key: value` lines: the canonical schema version, the dist serial, the publish date |
| `MANIFEST.json` | the sha256 of every file above (not of itself) |

## Using it

```python
import yaml
from schema_walk import flatten_fields  # vendored from walk/

doc = yaml.safe_load(open("schema/character.yaml", encoding="utf-8"))
fields = flatten_fields(doc, "character", note=print)
# [{'name': 'physicality', 'kind': 'scalar_str'}, {'name': 'mentality', 'kind': 'scalar_str'}, ...]
```

Pass a `note` sink. A field type the walk does not know is skipped, and with the default sink it is skipped silently, so an older walk reading a newer schema would lose fields without a word. Extra output is opt-in: `include_required`, `include_desc`, `include_sections`.

Parse `VERSION` as key-value lines; it is not a bare version string.

## Pinning

Pin a tag for people and a hash for machines. Tags can move; hashes can't.

1. Fetch your pinned tag.
2. Record the hash of `MANIFEST.json` on your side (a lockfile, your CI config). Comparing a tree only against the manifest that came with it proves the two agree, not that they are the files you accepted.
3. In CI, check every listed file against the manifest and fail on a mismatch.
4. Print the pin's age from `VERSION`'s publish date and warn when it grows old. Warn, don't fail.

Tags read `v<canonical-version>-dist.<serial>`, for example `v0.30.2-dist.16`. The serial counts publishes of the same canonical version, such as a presentation fix or a new ruling.

## Vendoring

Copying these files into your repo is supported, and it makes offline builds possible. Editing your copy is not: the walk is the one decoder of what the YAML means, and a patched copy is how one standard turns into several. If you need something the walk does not return, open an issue; the opt-in flags were added that way.

The list of element types is a literal inside the walk, so a 23rd type would arrive as a new dist.

## Links

[The standard](https://github.com/OnlyWorlds/OnlyWorlds) · [Docs](https://onlyworlds.github.io) · [TypeScript SDK](https://github.com/OnlyWorlds/sdk) · [Python SDK](https://github.com/OnlyWorlds/python-sdk) · [Unity SDK](https://github.com/OnlyWorlds/unity-sdk) · [Council](https://council.onlyworlds.com)

## Licence

MIT. See [LICENSE](LICENSE).

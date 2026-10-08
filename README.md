# onlyworlds (Python)

A Python client for the [OnlyWorlds](https://onlyworlds.github.io) API, and a reader and writer for OnlyWorlds world folders (a world as a folder of JSON files). Python 3.12+, no runtime dependencies.

**Pre-release.** It is not on PyPI yet; install it from GitHub.

## Install

```bash
pip install git+https://github.com/OnlyWorlds/python-sdk
```

## First run

Moppetopia is a public demo world. Its read-only key needs no account:

```python
from onlyworlds import Client

client = Client("0000000001")
print(client.get_world()["name"])
for c in client.list_page("character", limit=3)["data"]:
    print(" ", c["name"])
```

```
Moppetopia
  Admiral Splashworth
  Admiral Fluffington
  Captain Snoot
```

## Your own world

Create a world at [onlyworlds.com](https://www.onlyworlds.com); its keys are on the world's page.

- An `ow_r_` key reads, with no PIN: `Client("ow_r_…")`.
- An `ow_w_` key reads and writes. Writes also send a PIN: `Client("ow_w_…", "…")`.
- For code that writes, give it its own [agent seat](https://onlyworlds.github.io/docs/development/agents): the seat's key and its `ow_s_` secret (passed as the PIN) work in one world, and you can remove them without touching your account PIN.

Elements are plain dicts:

```python
writer = Client("ow_w_…", "ow_s_…")
peak = writer.create("location", {"name": "Dragon Peak"})
writer.patch("location", peak["id"], {"supertype": "Mountain"})

for character in client.iter_elements("character", expand=["species"]):
    print(character["name"])
```

## World folders

A world folder is one JSON file per element, in [the world folder format](https://github.com/OnlyWorlds/toolkit/blob/main/knowledge/world-folder.md). Atlas reads and writes the same format.

```python
from onlyworlds import export_world, read_folder

export_world("moppetopia", api_key="0000000001")
folder = read_folder("moppetopia")
print(folder.world["name"], len(folder.elements), "elements")
```

`write_folder(root, world, elements)` writes one. Reading never changes a file, and a file without an id is skipped and left alone.

To send a folder's edits back, keep a copy exported before you edited, then push the difference:

```python
from onlyworlds import push

result = push("moppetopia-before", "moppetopia", api_key="ow_w_…", pin="ow_s_…", log_path="push.jsonl")
```

`push` sends only the fields that changed, retries what the server asks it to retry, checks that what came back is what it sent, and logs every write, so running it again skips what already landed. `dry_run=True` shows the plan without sending it.

## Errors

A failed call raises `ApiError` with the API's `code`, `param` (the field that failed) and `doc_url`, and flags for the cases you handle differently: `is_validation_error`, `is_auth_error`, `is_not_author`, `is_owner_only`, `is_id_conflict`, `is_resync_required`, `is_busy`.

## The change feed

```python
walk = client.walk_changes(saved_cursor)  # None for everything
for op in walk:
    ...  # op["op"] is "upsert" or "delete"
saved_cursor = walk.cursor  # opaque: keep it, don't parse it
```

## Schema

The 22 element types and each field's kind are generated from the published [schema distribution](https://github.com/OnlyWorlds/schema-dist); `onlyworlds.SCHEMA_VERSION` and `onlyworlds.SCHEMA_DIST_TAG` say which one. The package's own version doesn't track the schema's.

Not yet: typed element models, the account routes, a snapshot writer.

## Develop

```bash
uv sync
uv run pytest -q
uv run ruff check . && uv run mypy --strict src
uv run python codegen/generate_schema.py --check
```

Three groups of tests run only when asked:

- `OW_CONFORMANCE_FIXTURE=<path>`: the folder-format conformance fixture from the Atlas repo.
- `OW_OPENAPI=https://www.onlyworlds.com/api/v2/openapi.json` (or a saved copy): checks the client's routes, parameters and fields against the API's own OpenAPI document.
- `OW_LIVE=1`: read-only calls against the demo world.

An older, unrelated `onlyworlds` 0.30.0 on TestPyPI was an earlier package for the v1 API.

## License

MIT. See `LICENSE`.

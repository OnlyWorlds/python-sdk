# Working in this repository

## What this is

The `onlyworlds` Python package: a client for the onlyworlds.com v2 API and a reader and writer for OnlyWorlds world folders. A version tag publishes it to PyPI through `.github/workflows/release.yml`, then makes a GitHub release from the version's `CHANGELOG.md` entry. The 22 element types are generated from a vendored, pinned copy of the schema distribution.

## Set up and run the gates

You need `uv` and the network. Work in a full clone, not a shallow one, and `git fetch origin` first. Run these from the repository root, in a POSIX shell (Git Bash on Windows), before you call a change done, in this order (the `gates` job in `.github/workflows/ci.yml`). Always go through `uv run`: a bare `python -m pytest` can import an installed release instead of this checkout.

```bash
uv sync --locked
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run mypy --strict src tests
uv run python codegen/generate_schema.py --check
uv run python codegen/generate_tools.py --check
uv run python codegen/generate_anchors.py --check
uv run python codegen/generate_directions.py --check
uv run python codegen/generate_casefold.py --check
uv run python codegen/generate_nfc.py --check
uv run python scripts/public_words.py
uv run python scripts/verify_promise.py
```

`scripts/verify_promise.py` holds the package's promise: a patch fixes and a minor adds, and neither removes or renames a public name. It reads the source (never importing it) against `scripts/public-names.json`, the public names of each public module and their deprecation marks. A change that adds public names runs `uv run python scripts/verify_promise.py --write`, which adds them and never removes one within a major. A name that will go is marked first: its docstring says `Deprecated since X.Y.Z` and `onlyworlds 1.0`, and a function also warns with `DeprecationWarning`, whose text names its replacement and `onlyworlds 1.0` (the script requires the docstring; it checks a warning's text when there is one, but not that there is one). It goes only in 1.0, six months or more after the release that marked it.

`main` requires two checks: `gates (ubuntu-latest, 3.13)` and `wheel`. The `gates` job also runs on Windows and on Python 3.12 and 3.14. A pull request runs four more jobs that are not required: `commits` (the commit-message check below), `okf-reference`, `folder-conformance` and `wire`.

The `wheel` job builds the wheel, checks it holds exactly the tracked files under `src/onlyworlds/`, installs it in place of the source tree and runs the suite against it. Read its steps in `ci.yml`; its import check asserts a `/site-packages/` path and fails on Windows. If you change packaging (`pyproject.toml`, files added or removed under `src/`), let CI run it.

Skips: a plain `uv run pytest -q` skips some tests on purpose; `uv run pytest -q -rs` prints why, and most name the variable that turns them on. The README's develop section lists those variables. `OW_CONFORMANCE_FIXTURE` and `OKF_REFERENCE_SRC` take a checkout; the `folder-conformance` and `okf-reference` jobs in `ci.yml` show how to fetch each, and you can run them the same way. `OW_LIVE=1`, and `OW_OPENAPI` set to the document's URL (it also takes a saved file), reach onlyworlds.com, which rate-limits keyless requests: an HTTP 429 there is the limit, not your change, so wait a minute and run once more, never in a loop. `tests/test_staging_writes.py` needs `OW_STAGING_*` keys that are not public: its skip is expected. A few tests skip on Windows only (symlinks, NTFS names).

`tests/test_readme.py` type-checks every Python block in `README.md`, so a README example must match the code.

## How a change reaches main

Work on a branch, open a pull request, and wait for the required checks to go green. `main` takes a commit only when those checks passed on it, with no bypass, so a push of a commit whose checks have not passed on it is refused. A maintainer merges; you never merge your own pull request.

Never push to `main`. Never create or push a tag: a version tag publishes a release. Never edit a file under `.github/workflows/`. Never change `src/onlyworlds/_version.py` or `CHANGELOG.md` unless the job says so.

## What must not be touched or hand-edited

- `codegen/schema-dist/`: the schema distribution, vendored byte for byte and checked against its `MANIFEST.json` and the pin in `codegen/schema-pin.json`. Only `codegen/repin.py` moves it (README, develop section).
- `codegen/tools/tools.json` and `codegen/tools-pin.json`: the tools list, pinned by commit and sha256. Only `uv run python codegen/generate_tools.py --repin <commit>` moves it.
- `codegen/layout/directions.json`: shared byte for byte with the npm SDK; `codegen/schema-dist/profiles/layout-by-links-3d.fixture.json` names its sha256.
- The files already under `tests/fixtures/`: recorded exports and fixtures shared with the npm SDK. `.gitattributes` names the byte-for-byte ones (marked `-text`); their sha256 is held in the tests or in `tests/fixtures/draught-text/MANIFEST.json`.
- Generated modules, each with its generator (run the generator, never edit the output):
  - `src/onlyworlds/_schema.py` and `src/onlyworlds/_walk/`: `uv run python codegen/generate_schema.py`
  - `src/onlyworlds/_tools.py`: `uv run python codegen/generate_tools.py`
  - `src/onlyworlds/_anchors.py`: `uv run python codegen/generate_anchors.py`
  - `src/onlyworlds/_directions.py`: `uv run python codegen/generate_directions.py`
  - `src/onlyworlds/_casefold.py`: `uv run python codegen/generate_casefold.py`
  - `src/onlyworlds/_nfc.py`: `uv run python codegen/generate_nfc.py`
- `uv.lock`: never hand-edited; `uv lock` regenerates it, and only a dependency change moves it (`uv lock --check` says whether it is current).

Text files are LF (`.gitattributes`), and the `--check` runs compare bytes: keep LF on Windows too.

## Words

Everything in this repository is public, commit messages included. A commit message says what the change does. It names no private repository, person or internal ticket.

```bash
uv run python scripts/public_words.py                               # the tracked published files (not CHANGELOG.md, codegen/schema-dist/, codegen/tools/ or tests/fixtures/)
uv run python scripts/public_words.py AGENTS.md README.md           # named files, tracked or not
uv run python scripts/public_words.py --commits origin/main..HEAD   # your commit messages
```

With no arguments the script reads only tracked files: pass a new file's path until it is added. CI's `commits` job runs the `--commits` form over each pull request's commits.

## Where to stop and ask

Stop, and do not guess, when the job would need any of these: a change to a file named under "What must not be touched or hand-edited", a new dependency, a change to public behaviour the job did not name, a failing gate you cannot explain, one that also fails on `origin/main` included (it is not yours to fix), or two readings of the job that give different code. Write one question as a comment on your pull request (with no pull request yet, in a file `ASK.md` at the root of your branch), push your branch as it stands, then end your turn.

## What a finished job looks like

The pull request's description says what changed; each gate you ran, with the last line of its output; what you did not run, and why; and a list headed "Looked wrong, left alone" of anything outside the job that seemed wrong.

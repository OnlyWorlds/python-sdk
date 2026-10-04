# OnlyWorlds schema-dist

Generated artifacts only. Nobody edits this repo by hand; keel (the OnlyWorlds
platform) regenerates and publishes it after any schema change. If you found a
problem here, the fix happens upstream — open an issue, don't send a PR
against generated files.

## What this is

- `schema/*.yaml` — the 22 OnlyWorlds element types + `base_properties` +
  `world`, byte-identical to the Council-governed standard
  (github.com/OnlyWorlds/OnlyWorlds). No presentation keys.
- `presentation.json` — family + icon **defaults** per type, plus the four
  family **colours** (`colors.families`, light/dark pairs). Defaults, not
  authority: tools are free to override, and Atlas remaps wholesale for dark
  mode. `_meta.provenance` records why the four-family split exists so it is
  not re-litigated by taste, and points at the measurement record.
  **Do not change a hex without re-running CVD validation** — the World green
  is pinned by the accessibility budget, not by preference.
  *(Colours were withheld through serial 5 on the position that "the palette
  lives in each consumer". That cost a new consumer any legitimate source for
  them, which is how a sixth hardcoded copy gets born; published from serial 6.)*
- `walk/schema_walk.py` — THE official schema reader. Vendor it or port it,
  but keep its semantics; it is the one decoder of what the YAMLs mean.
  Requires PyYAML; no other dependency, and nothing from the platform.
  **Pass a `note` sink** (`flatten_fields(doc, slug, note=print)`): an unknown
  field type is *skipped*, and with the default no-op sink it is skipped
  silently, so a pinned older walk meeting a newer schema loses fields with no
  signal. Opt-in extras, all off by default: `include_required`,
  `include_desc`, `include_sections`.
- `walk/rulings.yaml` — semantic rulings the YAML cannot carry (nullability,
  extension passthrough, drift resolutions). Emitters in every language honor
  these rows rather than re-deriving the conventions.
- `VERSION` — canonical schema version, dist serial, publish date. Three lines
  of `key: value`, not a bare version string; parse it, do not `strip()` it.
- `MANIFEST.json` — sha256 of every file above. It does **not** hash itself,
  so the tree holds one more file than the manifest has entries. Verify the
  listed files; do not diff the manifest against a directory listing.

## How to consume

Pin by tag for humans, **verify by hash for machines** — git tags are mutable,
sha256 is not, so MANIFEST.json is the real pin and the tag is ergonomics.
Fetch your pinned tag, hash-compare against MANIFEST.json in CI, and fail on
mismatch.

**Record the MANIFEST.json hash on your side** — in your lockfile, your CI
config, wherever your pin lives. Comparing a fetched tree against the manifest
that came with it only proves the tree is internally consistent; if the tag
moved, the manifest moved with it and both agree perfectly about the wrong
content. Recording the hash you first accepted is what makes a moved tag
visible. This is the `go.sum` pattern, and it exists because supply-chain
incidents have been built on exactly that gap.

Print the pin's age from `VERSION`'s publish date on every check and warn when
it grows old — **a check that compares you to what you chose can never tell
you your choice went stale.** Warn, never fail: failing on age turns a guard
into a nag, and people delete nags.

## Tags

`v<canonical-version>-dist.<serial>` — e.g. `v0.30.0-dist.1`. The canonical
part tracks the schema standard; the serial increments per publish of the same
canonical version (a presentation fix, a new ruling row). Canonical itself
carries no tags, so this convention starts here rather than inheriting one.

## Vendoring

Copying these files into your own repo is a supported path, not a workaround:
it is what makes an offline or air-gapped build possible. The walk is one
module with a single third-party import (PyYAML) and no platform code, so it
travels. Vendor it, record the hash, and re-run the check when you update.

What is *not* supported is editing your copy. The walk is the one decoder of
what the YAMLs mean, and a forked decoder is how a standard quietly becomes
several standards. If your emitter needs something the walk does not return,
**ask for it upstream** rather than patching locally: that is what the opt-in
flags are, and they were added exactly this way.

One known edge, stated rather than hidden: `ELEMENT_TYPES` is a literal inside
the walk. A 23rd element type would require a new dist, not a local edit.

## What this is not

Not a product. No support promise, no compatibility contract beyond the pinned
version, no deprecation ceremony. It is plumbing, and it stays boring — that
is the design, not a stage it will grow out of.

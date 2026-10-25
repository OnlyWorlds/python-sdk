# Import profile: the import map — another tool's words for the 22 types

**What it is.** One shared table, per source tool, **from the words that tool's users write to one of the 22 types**: in LegendKeeper people tag a page `city`, `organization` or `artifact`, not `location`, `institution` or `object`. A door that brings a project in from that tool (the Python package `onlyworlds`'s `onlyworlds.legendkeeper` is the first) offers the table as its default map, so two doors never type the same tag two ways. **The table is offered and applied only on the user's yes; it never types anything silently.** A door that never read this page types a resource the way it always did: from a tag that equals a type name, or from a map the user typed.

What it is not: a guess (every row was ruled from the type's definition, and a word nobody ruled has no row); a rename (the resource keeps its own tags, and the tool's own word for the type is not written anywhere as a type); anything that changes a type, a field, a link or the standard.

**The file and where a door finds it.** `profiles/import-map.json` in the schema distribution, vendored and pinned by hash like every other file of it (the dist's README, Pinning and Vendoring). A door reads its vendored copy. This page is the table's meaning; the JSON is the table.

**The value.** A JSON object.

| Key | Meaning |
|---|---|
| `version` | The number `1`. Any other value, JSON `true` included, means the file is not an import map: no table for any source, never an error. |
| `sources` | An object: a **source** key (the tool, lower-case: `legendkeeper`) to that source's table. A door reads only its own source's entry. |
| `source` | In a source's table: the tool's public name, as a report prints it (`LegendKeeper`). |
| `matches` | What a key is matched against. `tag`: the resource's tags. A door that does not know the value reads no table for that source. |
| `types` | An object: a tool's word, **already trimmed and lower-cased**, to a **type slug** (one of the 22, as the schema spells it: `location`, `institution`, …). |
| `no_type` | An array of the tool's words that get **no type and are not offered as mappable**: the tool's help pages, not the world. |
| `ruled` | The date the source's rows were ruled (`YYYY-MM-DD`). |

**How a door reads it.** Every tag is matched **trimmed and without regard to case**, the room profile's one definition (`profiles/room.md`): "trimmed is the value with leading and trailing whitespace removed, nothing inside it touched; without regard to case is the trimmed value compared after simple case folding (Python's `casefold()`, JavaScript's `toLowerCase()`; the two agree on every word a pair can hold). The match is the whole folded word against the whole folded pair". A door folds the table's keys and the user's map keys the same way. For one resource:

1. For each tag: if the user typed a map for it (`--map TAG=TYPE`), that map names its type; else, if the resource is not a template and the table has the tag, the table's entry names its type; else, if the tag equals a type slug, it names that type. **A map the user typed for a tag wins over the table's entry for that tag**; the table's entry and a type-name tag count alike as named types.
2. **One named type types the resource** (several tags naming the same type are one; the report names the strongest way that named it: the user's map, then a type-name tag, then the table). **Two distinct named types leave it untyped**, and the report says it is ambiguous and names both. **None leaves it untyped.** An untyped resource is what the door made it before this page: in the Python package, a Narrative with supertype `Article`.
3. A `no_type` word only stops the hint: the door never lists it among the tags a map could type. It never blocks a type: a resource tagged `city` and `guide` is a Location by the table.

**Templates are out of the table's reach.** A resource in the tool's templates folder (in LegendKeeper, `parentId` `templates`; the Python package marks it `x_legendkeeper_template`) is never typed by the table. A tag equal to a type name and a map the user typed still apply to it, as they did before this page.

**Offer, then apply.** Before it types anything by the table, the door prints the offer: the source's name and every row that would type at least one resource, with how many (`city → location (5)`), and asks. **Only the user's yes applies it**: a typed answer, or a flag the user gave for this run. With no one to ask (a dry run, a script with no such flag), it prints the offer and does not apply it. Declined or not asked, the door runs as if the file were not there. **A door that applies the table without asking is not conforming.**

**The report line.** After the yes, each resource the table typed says so in the import's report, beside the ones a tag or the user's map typed (for instance `import map: city=location`), so a reader tells the table's work from the user's. The tags on the untyped resources that a map could type are listed as before, without the `no_type` words.

**What a reader ignores.** Unknown keys anywhere in the file; another source's entry; a `types` row whose value is not one of the 22 slugs as the schema spells them; a `no_type` entry that is not a string; a `types` that is not an object and a `no_type` that is not an array (no rows, no words, the rest of the source read). Ignoring one row never refuses the file.

**What a reader refuses** (no table, never an error): the file is not an object; `version` is not the number `1`; `sources` is not an object; the door's source entry is not an object or its `matches` is not a value the door knows. Every door refuses and ignores the same things, or one door types a page as a Location where another leaves it an Article.

**What a writer keeps.** A door that writes a world back to the source tool writes the resource's own tags, kept on the element (`x_legendkeeper_tags` in the Python package), never a type name the table invented: the type is OnlyWorlds' reading of the tag, not a tag the user wrote. The table itself is written only through a schema-dist serial.

**The LegendKeeper table.** Each reason is from the type's definition.

| Tag | Type | Why |
|---|---|---|
| `artifact` | `object` | Objects are tangible, non-living things that can be made, owned, traded or destroyed. |
| `city` | `location` | A Location is a distinct place within the world where activities occur and elements converge. |
| `country` | `location` | A country page is a place, and its cities sit under it (`parent_location`); a Zone is an area that gains its shape only through linked map markers. |
| `ethnicity` | `species` | A Species is a distinct biological or cultural form of life; a Collective acts as a unit, and an ethnicity does not. |
| `item` | `object` | As `artifact`: a tangible, non-living thing. |
| `myth` | `narrative` | Narratives are stories told in the world. |
| `organization` | `institution` | Institutions are organized bodies with purpose and structure. |
| `point of interest` | `location` | A distinct place where activities occur. |
| `quest` | `narrative` | A story the world tells or its players follow; the happenings it dates are its Events. |
| `scene` | `narrative` | A story told; a scene's happenings are Events when the page dates them, and a user who writes scenes as happenings maps `scene=event`. |
| `technology` | `construct` | Constructs are abstract or conceptual structures, non-physical, that explain or organize how the world works; one machine is an Object. |
| `guide` | no type | LegendKeeper's help pages: about the tool, not the world. |
| `keeper` | no type | As `guide`. |
| `tips` | no type | As `guide`. |
| `tutorial` | no type | As `guide`. |

**How a second source joins.** A real export from that tool, its tags counted (every distinct word and how many resources carry it), a ruling from the definitions, and a source entry in a new serial with its `ruled` date. A word no export has shown gets no row.

**Conformance.** `import-map.fixture.json`, beside this page: cases of `{source, tags, map?, template?, file?}` → the type a door that applied the table gives (or `null`, untyped), why (`table`, `tag`, `user map`, `untyped`, `ambiguous`, `no type`, `template`), and the tags it offers as mappable (each folded, once, sorted; none on a typed resource). `no type` is an untyped resource whose every tag is a `no_type` word; `template` is a template left untyped that carries a tag the table has. A case with `file` reads that value in place of `import-map.json`; a declined offer reads as no file. **Every door that reads the table runs the fixture as its own test**: the Python package's `onlyworlds.legendkeeper` first.

Source: Titus's focus on LegendKeeper and the reads of the door's author and the converter lane, 2026-10-25; the first reader the Python package.

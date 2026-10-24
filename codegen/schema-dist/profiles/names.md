# Extension profile: `x_names` — a world's own words for the types

**What it is.** A world may carry **one small map from the 22 type slugs to the world's own words**: in a work world Character is shown as *Employee*, Institution as *Team*; in a sports world Character as *Player*. Every tool that prints a type's name looks the map up before it prints the word. The API, the folder, the schema, every id and every other world keep the real names. The word is for the person's eyes only, which is why it breaks nothing. **Nothing in the standard changes; no type is renamed; a tool that never read this page shows Character as always.**

What it is not: a way to make new categories. A world still has 22 types with their fields and links; the map changes no field, no link, no rule and no validation.

**Key name and home.** `x_names`, **on the World** (the body `GET /world` returns, `world.json` in a folder), beside the world's other settings (`time_*`, the units). One map per world; not on an element, since a world has one vocabulary and a reader must find it without a search. (keel serves `x_` keys on the World since 2026-10-23; a folder may carry the key too, and a reader of folders reads it.) The folder format's §4.1 binds a writer to carry every `world.json` key the source had, so a folder keeps the map.

**The value.** A JSON object. A writer writes the object; a reader reads only an object (a string is not a map).

| Key | Meaning |
|---|---|
| `version` | `1`. Any other value, JSON `true` included, is not a names map. |
| `types` | An object: a **type slug** (one of the 22, lowercase, as the schema spells it: `character`, `institution`, …) to a **word pair**. Optional. |
| `supertypes` | An object: a type slug to an object of **supertype** to a word pair, for a finer word inside one type (`character` → `Agent` → *AI agent*). Optional. |

A **word pair** is an object `{"one": "Employee", "many": "Employees"}`: `one` a non-empty string after trimming (required: an entry without it is ignored); `many` a string (optional: absent, not a string, or empty after trimming, means the reader prints `one` where it would print a plural). Both are trimmed before use.

**How a reader finds the word.** For an element (or a type list, a card header, a count) a reader knows the **type slug** and, for an element, its **supertype**:

1. If the map is not a names map (below), the standard's name, everywhere.
2. If `supertypes[type]` has an entry whose key equals the element's supertype **trimmed and without regard to case** (the room profile's one definition, `profiles/room.md`), that entry's word. An entry that is ignored (no string `one`) is no entry: the reader goes on to step 3.
3. Else if `types[type]` has an entry, that entry's word.
4. Else the standard's name for the type.

`one` for a single thing, `many` for a plural (a list's heading, a count: "12 Employees"). A reader that only ever prints one form uses `one`. **The word is printed as written, never re-cased** ("AI agent" lower-cased mid-sentence is "ai agent"); a tool that cases the standard's names by position gives that up for a world's word. **A string that names the type names the word**: "your Character" for a person's seat in a world is "your Employee" in a work world, because the seat is a Character element; a tool's own role noun ("your seat") is not a type name and stays.

The word replaces the **type's display name** wherever the tool shows it: a card's header, a list's heading, a picker, a count. **Folders are not words**: the folder format's `elements/<type>/` directories are never translated, and a tool that names folders by type (the Obsidian plugin's `<Type>/`, the Markdown profile's address) **should leave them alone**: an address that Sync, git and every link hold still must not move on a settings edit. The word goes on what the folder shows, not on its name. The supertype itself keeps printing as written: an *AI agent* with supertype `Agent` shows "AI agent · Agent" if the tool shows both, or the tool may drop the supertype when the word already says it.

**Two audiences at once** (the Markdown pack, read by an AI that needs the standard's type and a person who knows their word): the world's word first and the standard's in brackets, "Employees (Character)", "AI agents (Character, Agent)"; file names stay the standard's slugs; `x_names` itself is never printed among the world's fields.

**What a reader ignores.** A key in `types` or `supertypes` that is not one of the 22 slugs (a typo, a type from a later schema the reader does not know); an entry whose value is not an object with a non-empty string `one`; a `many` that is not a string; unknown keys anywhere in the value. Ignoring one entry never refuses the map.

**What a reader refuses** (the standard's names everywhere, never an error): `version` is not the number `1`; the value is not an object; `types` is present and not an object; `supertypes` is present and not an object, or one of its values is not an object. Every reader refuses and ignores the same things, or one tool shows *Employee* where another shows *Character*.

**What a writer must keep.** Everything it did not change, unknown keys included (the folder format's §3.3). The map holds no element ids: a re-key never rewrites it. Who may write it on keel: the owner and a co-builder (the world's settings rung); the set-up skill writes it for a work world's pack (People, Teams) on the keeper's yes.

**Conformance.** `names.fixture.json`, beside this page: 23 cases of `{map, type, supertype?, many}` → the word a reader prints, or `null` for "the standard's name". **Every tool that implements the lookup runs the fixture as its own test** (two readers disagreeing on one case is the failure this profile exists to prevent): the TypeScript SDK's `typeWord(world, type, {supertype, many})`, the Python package's `type_word(world, element_type, supertype=, many=)`, the Unity SDK's `OWNames`, the plugin's own.

Source: Titus's framing, a translation file and nothing more, and the reads of Kael, Boss, Quillon and Temper, 2026-10-22; the first readers the TypeScript SDK and the Python package.

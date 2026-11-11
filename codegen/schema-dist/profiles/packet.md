# Extension profile: `x_packet_*`

**What it is.** A packet of work about a world: a list of elements with a reason each, made by a tool (a world doctor's findings), a person (an ask: "look at these four") or an AI (a proposal). The packet travels as JSON until it lands as an element; landed, it is a Relation with supertype `Work item` and the packet's fields ride on it, so every tool that follows a work item reads one shape: the parlor's list, Atlas's import by the id list, the doctor's output, a seat's proposal.

**Key names.** Profile `packet`, four fields: `x_packet_elements`, `x_packet_source`, `x_packet_producer`, and a fourth, optional, `x_packet_for`. The grammar is `x_<profile>_<field>`; the prefix `x_packet_` is reserved.

**On which element.** A Relation with supertype `Work item`. **Where real links can exist**, the Relation's own typed link fields (`characters`, `locations` and the rest) carry the same elements as real links, so a tool that knows nothing of this profile still follows them: that is when the work item lives in the world its elements live in (a world's own room, a doctor filing into the world it checked). Across worlds (a link to an id the world does not hold is refused by the platform), and for the types a Relation has no link field for (Law, Map, Pin, Marker, Relation), `x_packet_elements` is the only carrier, and **a reader never lands a foreign id as a link**; `actor` is the one person the work is for, and `x_packet_for` the roles it is for (below); the description is the packet's own summary; the subtype is its state (`open`, `taken`, `done`). Before landing, the same keys sit in a bare JSON object with `type: "relation"`, `supertype: "Work item"`, `name` and `description`, and no `id` (the landing tool mints one).

**The values.**

| Key | Meaning |
|---|---|
| `x_packet_elements` | A list of `{"type": "<type slug>", "id": "<element id>", "reason": "<one sentence>"}`. The type is carried so a reader needs no lookup to find the element's route or file; the id is the element's; the reason is why this element is in the packet, one sentence a person reads. Order is the producer's (a doctor's order of severity; a person's order of asking). An entry without all three keys is ignored by a reader, never repaired. |
| `x_packet_source` | `{"server": "<base URL, or null for a folder>", "world": "<world id>"}`: which world the ids belong to, in the shape of the folder format's provenance line (the folder format's `source`: its `server` and `world`), so a packet made from a folder on disk (`server: null`) and one made from an account world read the same. A packet read in a parlor world points at the SOURCE world, never at the parlor. |
| `x_packet_producer` | `{"tool": "<name>", "version": "<version>"}`, present only when a tool made the packet (the doctor, an agent's harness). A person's packet carries no producer: `created_by` already names them. `tool` is required whenever the key is present; `version` is optional: a writer that does not know the version leaves the key out, never invents one and never writes the word "unknown", and a reader takes a producer with no version as a producer whose version is not known. The `tool` and `version` of a world folder's `producer` (the folder format). |
| `x_packet_for` | Optional. A list of Title ids: the work item is for whoever holds one of them; `actor` stays the one person it is for. Both may be set. The ids are Titles of the world the work item sits in, as `actor` is a Character of that world; never of the world `x_packet_source` names. In a parlor world apart from its source, the people and their roles are the parlor's. It is not a link, so nothing follows it and no lens reaches a work item through it. |

**How a reader uses it.**
1. The elements are `x_packet_elements`, in that order; the Relation's typed links are the same set and a reader may use either. When the two disagree (a landing tool failed half way), `x_packet_elements` is the packet and the links are a view of it.
2. A reader resolves each `{type, id}` in the source world named by `x_packet_source`; an id it cannot find is reported as missing, never dropped and never guessed at. The source world is not the world the Relation sits in when the Relation lives in a parlor.
3. Who made it: `x_packet_producer` names the tool; absent, the maker is `created_by` (a person's membership, or a seat); `changed_via` says which door it came through. A reader shows "the doctor, 0.11.0" from the producer line and never infers a tool from the seat. A producer whose `tool` is missing, empty or not a string is ignored, never repaired (the packet reads as one no tool signed); a producer with no version is shown by its tool's name alone ("the doctor").
4. A packet's size is bounded by the extension cap (the platform's cap on extension keys; on onlyworlds.com, 64 KB per element for all its extension keys together, counted as compact JSON): about 400 to 700 entries. A producer with more splits the packet into several work items, named `<name> (1 of 3)`, `(2 of 3)`, each complete on its own; a reader sees several, never a truncated one. A writer that would exceed the cap refuses to write, never trims.
5. The state is the subtype (`open`, `taken`, `done`); a reader changes the state by changing the subtype and nothing in the packet.
6. **For whom.** A work item is for a seat when `actor` is the seat's Character, or a Title in `x_packet_for` names that Character in its `holders`. Neither set: addressed to no one; a reader shows it apart ("not addressed to anyone"), never as for every role. An id in `x_packet_for` that is no Title of this world, or an empty string, is ignored and reported by a lint, never guessed at; an empty list reads as absent. A reader that does not know the key loses nothing: a packet without it is whole.

**What a writer must do.**
- Write `x_packet_elements` and `x_packet_source` together, with `x_packet_elements` never empty, and `x_packet_producer` beside them only when a tool made the packet; a work item with no elements is a plain Relation, not a packet.
- Write the fourth, `x_packet_for`, only when the work is for a role, and never as an empty list: a writer leaves the key out instead of writing one.
- Keep every entry's three keys; keep the source as the server and world it was made from; split past the cap.
- Keep it byte for byte when it is not yours to change, like every extension field. A re-key (a tool deliberately giving an element a new id, which may rewrite a value that is that old id, whole) never enters it: a packet is about the world named in `x_packet_source` with the ids that world had when the packet was made, and a copy of the world under fresh ids is a different world, where rule 2 reports the ids as missing.
- Reserve the prefix. A tool that lets people add their own fields reserves `x_packet_` and shows the four fields read-only, like `x_identity_`.

**What it is not.** A link field (a reader that ignores the profile still has the typed links), a record of what was done (the state is the subtype; the doing is in the elements' own changes), or a store of element text (a reason is one sentence about why, never a copy of the element). `x_packet_for` is a key and not the Relation's `titles` link because the typed links carry the packet's own elements (rule 1: the same set), so a Title in `titles` is one of the work's elements, never whom the work is for.

**Example**, in Hyperion: the doctor finds two Characters with no links and a Location with a dangling parent, and hands the owner a packet.

```json
{
  "type": "relation",
  "supertype": "Work item",
  "subtype": "open",
  "name": "Doctor's findings, 2026-10-21",
  "description": "Three elements the doctor could not connect to the rest of Hyperion.",
  "actor": "019a2c7e-5b31-7a40-9d02-1e8f6c4b2a93",
  "characters": ["019a2c7e-0d4f-7c11-8b56-3a7e9f1c5d20", "019a2c7e-13a8-7e62-9c03-7b1d2e8f4a66"],
  "locations": ["019a2c7e-2f9b-7d73-8e14-5c6a0b3d7e81"],
  "x_packet_elements": [
    {"type": "character", "id": "019a2c7e-0d4f-7c11-8b56-3a7e9f1c5d20", "reason": "No links in or out."},
    {"type": "character", "id": "019a2c7e-13a8-7e62-9c03-7b1d2e8f4a66", "reason": "No links in or out."},
    {"type": "location",  "id": "019a2c7e-2f9b-7d73-8e14-5c6a0b3d7e81", "reason": "Its parent_location points at an element that is not in the world."}
  ],
  "x_packet_source": {"server": "https://www.onlyworlds.com", "world": "019a2c7e-0000-7000-8000-000000000001"},
  "x_packet_producer": {"tool": "world-doctor", "version": "0.11.0"}
}
```

**A second example**, in Hyperion: a person asks for work that is for whoever holds the Consul of the Hegemony, not for one named person. The Title is Hyperion's own and the work item sits in Hyperion, so `x_packet_for` names it; `actor` is left out.

```json
{
  "type": "relation",
  "supertype": "Work item",
  "subtype": "open",
  "name": "Date the piano's story",
  "description": "The Story of the old piano has no date; whoever is Consul can give it one.",
  "narratives": ["068e6f37-772b-708f-8000-d30d2a6553ca"],
  "x_packet_elements": [
    {"type": "narrative", "id": "068e6f37-772b-708f-8000-d30d2a6553ca", "reason": "No start_date, and the Consul is in the story."}
  ],
  "x_packet_source": {"server": "https://www.onlyworlds.com", "world": "068e012b-52a9-79bf-8000-26bb67891425"},
  "x_packet_for": ["068e2dde-8d1f-7dd2-8000-6178241a68ab"]
}
```

Readers today: none shipped; the parlor, the world doctor in the Python package and Atlas's import by id list are the first three, each named here as it ships. No reader of `x_packet_for` has shipped either. Ruled: the shape the doctor reads, 2026-10-21; `x_packet_for`, 2026-11-10, serial 112; a producer's `tool` required and its `version` optional, 2026-11-11, serial 115.

# Extension profile: `x_packet_*`

**What it is.** A packet of work about a world: a list of elements with a reason each, made by a tool (a world doctor's findings), a person (an ask: "look at these four") or an AI (a proposal). The packet travels as JSON until it lands as an element; landed, it is a Relation with supertype `Work item` (folder spec §4.6 (i)) and the packet's fields ride on it, so every tool that follows a work item reads one shape: the parlor's list, Atlas's import by the id list, the doctor's output, a seat's proposal.

**Key names.** Profile `packet`, three fields: `x_packet_elements`, `x_packet_source`, `x_packet_producer`. The grammar is `x_<profile>_<field>`; the prefix `x_packet_` is reserved.

**On which element.** A Relation with supertype `Work item`. **Where real links can exist**, the Relation's own typed link fields (`characters`, `locations` and the rest) carry the same elements as real links, so a tool that knows nothing of this profile still follows them: that is when the work item lives in the world its elements live in (a world's own room, a doctor filing into the world it checked). Across worlds (a link to an id the world does not hold is refused by the platform), and for the types a Relation has no link field for (Law, Map, Pin, Marker, Relation), `x_packet_elements` is the only carrier, and **a reader never lands a foreign id as a link**; `actor` is whom the work is for; the description is the packet's own summary; the subtype is its state (`open`, `taken`, `done`). Before landing, the same keys sit in a bare JSON object with `type: "relation"`, `supertype: "Work item"`, `name` and `description`, and no `id` (the landing tool mints one).

**The values.**

| Key | Meaning |
|---|---|
| `x_packet_elements` | A list of `{"type": "<type slug>", "id": "<element id>", "reason": "<one sentence>"}`. The type is carried so a reader needs no lookup to find the element's route or file; the id is the element's; the reason is why this element is in the packet, one sentence a person reads. Order is the producer's (a doctor's order of severity; a person's order of asking). An entry without all three keys is ignored by a reader, never repaired. |
| `x_packet_source` | `{"server": "<base URL, or null for a folder>", "world": "<world id>"}`: which world the ids belong to, in the shape of the folder spec's provenance line (§4.2 `source`), so a packet made from a folder on disk (`server: null`) and one made from an account world read the same. A packet read in a parlor world points at the SOURCE world, never at the parlor. |
| `x_packet_producer` | `{"tool": "<name>", "version": "<version>"}`, present only when a tool made the packet (the doctor, an agent's harness). A person's packet carries no producer: `created_by` already names them. The same shape as a folder's `exported_as` (§4.2). |

**How a reader uses it.**
1. The elements are `x_packet_elements`, in that order; the Relation's typed links are the same set and a reader may use either. When the two disagree (a landing tool failed half way), `x_packet_elements` is the packet and the links are a view of it.
2. A reader resolves each `{type, id}` in the source world named by `x_packet_source`; an id it cannot find is reported as missing, never dropped and never guessed at. The source world is not the world the Relation sits in when the Relation lives in a parlor.
3. Who made it: `x_packet_producer` names the tool; absent, the maker is `created_by` (a person's membership, or a seat); `changed_via` says which door it came through. A reader shows "the doctor, 0.11.0" from the producer line and never infers a tool from the seat.
4. A packet's size is bounded by the extension cap (64 KB of `x_*` per element, keel §4): about 400 to 700 entries. A producer with more splits the packet into several work items, named `<name> (1 of 3)`, `(2 of 3)`, each complete on its own; a reader sees several, never a truncated one. A writer that would exceed the cap refuses to write, never trims.
5. The state is the subtype (`open`, `taken`, `done`); a reader changes the state by changing the subtype and nothing in the packet.

**What a writer must do.**
- Write the three keys together, with `x_packet_elements` never empty; a work item with no elements is a plain Relation, not a packet.
- Keep every entry's three keys; keep the source as the server and world it was made from; split past the cap.
- Keep it byte for byte when it is not yours to change, like every extension field. A re-key never enters it (§3.3): a packet is about the world named in `x_packet_source` with the ids that world had when the packet was made, and a copy of the world under fresh ids is a different world, where rule 2 reports the ids as missing.
- Reserve the prefix. A tool that lets people add their own fields reserves `x_packet_` and shows the three fields read-only, like `x_identity_`.

**What it is not.** A link field (a reader that ignores the profile still has the typed links), a record of what was done (the state is the subtype; the doing is in the elements' own changes), or a store of element text (a reason is one sentence about why, never a copy of the element).

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

Readers today: none shipped; the parlor, the world doctor in the Python package and Atlas's import by id list are the first three, each named here as it ships. Ruled in the folder spec §4.6 (i); the shape the doctor reads, 2026-10-21.

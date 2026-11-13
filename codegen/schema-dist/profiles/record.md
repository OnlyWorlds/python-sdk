# Convention profile: the record (a game's run, kept in the world)

**What it is.** A record is one run of a game that a world's Characters took part in (a battle, a crossing, a match), written into the world those Characters live in, so a character carries what they did from run to run. It is built from two kinds the standard already has: an Event (the run: who was there, where, what it involved) and Narratives (the run told: a chronicle of the whole, and a story about one character or told by one). The one new thing is a mark on the Event saying "a game wrote this, here is how to read it". A character's experience is the set of records that name them, read from the world, never a field on the Character.

**Two examples of the shape.** Tactical Tangle writes a battle as an Event (`x_tangle_battle`, the tally), a chronicle Narrative, one story Narrative per picked character (`protagonist`), and a trophy Object, in one atomic bulk write on the player's press. A naval game writes a crossing as an Event with the ships and captains linked, and the captain's own account as a Narrative with the captain as `narrator`. The profile names what the two share and leaves each game its own tally.

**The mark.** Profile `record`, one extension field on the Event: `x_record`, an object.

    "x_record": {"tool": "tangle", "played_at": "2026-11-01T00:30:00Z", "version": "1.4.0", "seed": "5f3a9c", "outcome": "won", "seats": {"<character id>": "General"}}

| Member | Required | What |
|---|---|---|
| `tool` | yes | the game's id in the tools list's form (`[a-z0-9-]`, 1 to 32); the same id as its row there when it is listed, so the Open with menu can offer the game beside its record |
| `played_at` | yes | when the run was played, real time, RFC 3339's form in UTC, seconds optional, upper-case `T` and `Z` only, ASCII digits only (`0` to `9`): `2028-02-29T00:00Z` and `2026-11-01T00:00:00.5Z` are marks, `2026-11-01t00:00z` and a year in full-width or Arabic-Indic digits are not; `_at` as every real-time stamp on the platform (`created_at`, `updated_at`), so it is never read as world time. It is a real calendar instant: month 1 to 12, the day within its month (leap years Gregorian), hour 0 to 23, minute and second 0 to 59, year 0001 or later; anything else is no mark, whatever a language's date parser makes of it. World time is the Event's own `start_date`, if the game dates it |
| `version` | no | the engine's version, a string; with `seed` it is the replay |
| `seed` | no | the run's seed, **a string** (a seed past 2^53 does not survive every language as a number) |
| `outcome` | no | one lowercase word the game chooses, 1 to 24 letters `a` to `z` (`won`, `lost`, `survived`, `sunk`): the one thing a character's page shows across games without reading any tally |
| `seats` | no | an object, Character id to the seat in the game's own words ("Commander, HMS Keeling", "General"); decoration, never the list of who was there, and in the shared mark so one reader can say "as Commander, HMS Keeling" for any game. Its keys are Character ids, read as written (the address profile's "The same id"): a carrier that knows this profile re-keys them with the Event's `characters` when it re-keys a world; one that does not carries the mark byte for byte (reader rule 2), and a stale key shows nothing false, since a seat for a Character not in `characters` makes no record. |

The value is no mark when it is not an object, when `tool` or `played_at` is missing or out of form, or when `version`, `seed`, `outcome` or `seats` is anything but its kind, null or absent (a number seed, a capitalised or empty outcome, a seats list, a seat that is not a string): a broken writer never shows as a record. A mark on any element but an Event is no record. The game's own tally rides beside it under the game's own prefix (`x_tangle_battle` for Tactical Tangle); the profile never reads it.

**Who took part.** The Event's `characters`, and nothing else. A seat named in `seats` for a Character not in `characters` makes no record for that Character (no fallback from one to the other, the strand's rule).

**The stories.** A Narrative belongs to a record when its `events` lists the record's Event. It is a Character's story of that record when it names the Character as `protagonist` (a story about them) or as `narrator` (their own account), or both. A Narrative naming the Character on an Event that is not their record is not theirs (no fallback). The chronicle, a Narrative naming no one, belongs to the record and to no Character's stories.

**The reading.** A reader, `recordsOf(characterId, elements)` (`records_of` in Python), in the OnlyWorlds packages, takes the elements as it is served them and returns a list, newest first by `played_at` read as an instant to the millisecond (a fraction truncated past three digits, never compared as a string), a tie by the Event's id in code point order (never UTF-16 code units: a character above U+FFFF sorts after every character below it). An Event or a Narrative whose `id` is not a string is never read: no entry without an id, no error. Each entry:

    {"event": {"id", "name"}, "tool", "played_at", "version", "seed", "outcome", "seat", "stories": [{"id", "name", "as"}]}

`version`, `seed`, `outcome` and `seat` are null when unset; `as` is `protagonist`, `narrator` or `both`; stories by their ids in code point order, as the ties are, never UTF-16 code units; a name as served, an empty string when none or when it is not a string. A character with no records reads an empty list, never an error. Experience is a count a game takes from this list (four crossings, two battles), never a number written to the Character.

**What a writer must do.**
1. Write the run into the world the Character lives in, with a key that can write there; where the writer is a member whose writes land for review, the run lands as proposed (the review profile), and a reader sees it once accepted.
2. One atomic bulk write per run (the Event, its chronicle, any Objects), links pointing backward in the batch; each story on its own press, never invented for a character the player did not pick.
3. Never edit an existing element: the Character, its fields and its links stay the author's. A game that rewards experience reads the records; it never raises a Character's own fields.
4. The recommended words: the Event's supertype `Record`, its subtype the game's word (`Battle`, `Crossing`); the Narratives keep their own (`Chronicle`, `Story`). No reader keys on any of them.
5. A record carries its `played_at` from the writer's own clock. A game may mark records it wrote before this profile once, from the server's stamp at that write: a writer's act, never a reader's fallback.

**The rule for readers.**
1. A record is read only from the mark; a label, a subtype or the game's own tally never makes one. An Event or a Narrative the review profile reads as proposed (its reader that shows a world, `proposedMarkOf`: an `x_review_proposed` object with a key; an empty mark, `{}`, `""` or `[]`, is settled, review rule 1) is not read until a keeper settles it: a proposed run is no record yet, a proposed story no story yet.
2. The mark is an extension field: a tool that does not understand it carries it byte for byte (folder spec §3.3), and a text editor never offers it as an editable string (an object stringified on save destroys it).
3. A lens, a graph, a list or a count treats the record's elements as the ordinary elements they are.

**Where a reader shows it.** On a character's page, under "Records": newest first, each with its stories.

**Ruled**: 2026-11-01, on the first draft: (a) records only, writer rule 3 verbatim; raising a Character's fields is another profile, never a line here. (b) `played_at` required, renamed from `played`; no reader falls back to a server's `created_at` (an export loses it); old records are marked by their writer once (writer rule 5). (c) The name is `record`. (d) `seats` stays in the shared mark. Added: `outcome`. The Event's recommended supertype is `Record`. Added in the second draft: reader rule 1's second sentence (a proposed run or story is not read), since writer rule 1 promised it and the first reader did not keep it. Added for this serial, from the packages' build: `played_at` a real calendar instant, and the order to the millisecond (a reader of a profile must not depend on its language's date parser). The fixture beside this page (`record.fixture.json`) holds each rule as a case (40 cases); a reference reader goes red on twenty-eight mutants, one at a time. 2026-11-13, serial 122: a key of `seats` is a Character id read as written, so a key in another spelling seats nobody; one more case in the fixture.

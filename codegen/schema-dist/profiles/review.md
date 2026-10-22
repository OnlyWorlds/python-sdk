# Extension profile: `x_review_*`

**What it is.** Two marks several tools read the same way: an element written as **proposed** (an AI seat's write in a world whose charter says its writes land for review; a person's suggestion) and an element **checked** (someone confirmed it is still true, when, against what). Proposed is about whether an element is settled; checked is about whether a settled element has rotted. Both are read by an editor's ink (Atlas), a world doctor, a parlor's review queue and the folder lint, which is why they are a profile with a reserved prefix and not two loose keys a person could type.

**Key names.** Profile `review`, two fields: `x_review_proposed`, `x_review_checked`. The grammar is `x_<profile>_<field>`; the prefix `x_review_` is reserved.

**On which element.** Any element. Both sit in the element's body as extension fields (so they travel in every export and share the extension cap), never in `world.json`.

**The values.**

| Key | Meaning |
|---|---|
| `x_review_proposed` | `{"by": "<membership or seat id>", "evidence": "<ids or text>", "expires": "YYYY-MM-DD"}` on a NEW element written as proposed: who proposed it, what it rests on, and the day it lapses if nobody acts. **Absent or `null` means settled.** A keeper named by the world's charter accepts the element by writing `null` (a clear is written, never only omitted, so a push carries it) or declines it by deleting the element. A proposed CHANGE to an existing element is never this key: it is a record beside the element (the platform's), so the settled text is never rewritten by a proposal. |
| `x_review_checked` | `{"by": "<membership or seat id>", "at": "YYYY-MM-DD", "against": "<an id, a path or a sentence>"}`: who last confirmed the element still true, when, and against what (a source element, a file, a sentence naming the check). Overwritten by each later check; a world keeps no history of checks in this key. |

**How a reader uses it.**
1. An element whose `x_review_proposed` is an object is proposed: shown apart from settled elements (a mark, a word before the colour; never hidden, never merged into counts of what the world holds as true), and never fed to a reader as a fact without the mark. An element without the key, or with `null`, is settled.
2. `expires` past: the proposal lapsed; a reader shows it as lapsed and a doctor reports it; nothing deletes it on its own.
3. `x_review_checked.at` is the element's freshness date where it exists; last checked outranks last edited. A reader that shows age shows the check's date first and the edit's beside it.
4. A value that is not an object with the keys above is ignored, never repaired, and reported by a lint.

**What a writer must do.**
- Write a proposal only where the world's charter says writes of this kind land as proposed; a settled world's writer never adds the key.
- Clear a proposal with `null`, as a write of the field; never remove it silently from a local copy.
- Write a check with the real date and a real `against`; a check with nothing it was checked against is not a check.
- Keep both byte for byte when they are not yours to change, like every extension field; a re-key never enters them (§3.3 of the folder format).
- Reserve the prefix. A tool that lets people add their own fields reserves `x_review_` and shows both read-only, like `x_identity_` and `x_packet_`; a check is written through its own control (a tap on a card), a proposal only by a writer acting under the charter.

**What it is not.** Permissions (who may accept is the charter's and the platform's, not the key's), a version history (a proposed change to settled text is a record beside the element), or a stale-after rule (the check records a date; the world's own policy says how old is too old).

**Example**, in Hyperion: an AI seat proposes a new Location; a keeper later confirms a Title against its charter.

```json
{ "name": "The Lower Quays", "x_review_proposed": {"by": "0d4e8a2c-…", "evidence": "the Harbour Ledger, entry 14", "expires": "2026-11-21"} }
{ "name": "Harbourmaster",   "x_review_checked":  {"by": "2ba21540-…", "at": "2026-10-22", "against": "019a2c7e-5b31-…"} }
```

Readers today: none shipped; the parlor's review queue (OW Parlor), the world doctor (Kael), Atlas's ink (Temper) and keel's checked-against card (Keel #517) are the first, each named here as it ships. Ruled in the folder format spec §4.6 (f) and (g), draft 2 of 2026-10-22, from Kael's and Temper's reads (h58 #9637, #9643).

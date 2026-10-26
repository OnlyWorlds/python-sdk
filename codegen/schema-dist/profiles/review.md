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
1. **A marked element is not canon until a keeper settles it.** An element whose `x_review_proposed` is an object is proposed; an element without the key, or with `null`, is settled. Readers come in two kinds, and the rule binds both:
   - **A reader that hands a world on** (a Markdown or context pack, a draught of what a Character knows, an MCP server's lists and searches, a context packet for an AI) **leaves proposed elements out unless asked for**, says in its opening line or its reply how many it left out, and labels each one it keeps **"proposed, not yet reviewed"**, with the mark still on it. It never hands a proposed element on as a fact without the label. The reason is a planted instruction: a seat whose write lands for review must not reach the next AI as canon before a keeper has read it.
   - **A reader that shows a world to its people** (an editor, a viewer, the world page, a review queue) **shows proposed elements with the mark visible**, apart from settled ones (a word before the colour, never merged into counts of what the world holds as true), since the keeper has to see them to settle them. An element asked for by its own id is served whole, mark on, to any reader.
2. `expires` past: the proposal lapsed; a reader shows it as lapsed and a doctor reports it; nothing deletes it on its own.
3. `x_review_checked.at` is the element's freshness date where it exists; last checked outranks last edited. A reader that shows age shows the check's date first and the edit's beside it.
4. A value that is not an object with the keys above is never repaired and is reported by a lint. A reader that hands a world on treats it as a doubt: left out unless asked for and counted with the proposed, so a doubt never reaches an AI as canon. A reader that shows a world to its people ignores it, showing the element as settled with the lint's finding beside it. The queue and the review route read an object only.

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

Readers today: keel writes the mark on an agent seat's new element under the world's switch, lists marked elements in the review queue and settles them through the review route; keel's draught and MCP reads leave them out unless asked; the world doctor counts them apart (the `onlyworlds` Python package, flag 12), and its Markdown pack leaves them out unless asked (`--proposed`). Still to come, each named here as it ships: the parlor's review queue, Atlas's ink, keel's checked-against card. Ruled in the folder format spec §4.6 (f) and (g), draft 2 of 2026-10-22, from the doctor's and Atlas's reads; the reader rule from a reader's question and the maintainer's ruling, 2026-10-23.

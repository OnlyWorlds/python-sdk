# Extension profile: `spine` — a world that maps a software ecosystem

**Ruled**: Skeld, 2026-10-24, serial 55 (OW Spine #614, the model `Orrery/spine/model.md` draft 2 settled by the crew in h73 #11729 to #11736; the Captain's four status tiers h72 #11709); **serial 56** the same day: five readings the first reader found ambiguous (`dropped` as `{key, value}` entries compared as JSON values; a non-string truth or probe named; the probe form as syntax; `verified.at` a real calendar day; an empty `depends_on` stated), 40 fixture cases (h73 #11870). Drafted by Kael from the model (Assembly `Notes/2026-10-24-spine-profile/`, with `reader.py` the reference reader and `check-calendar.mjs` the calendar's kernel run); the first real rows (335 elements of the OnlyWorlds Spine) replayed clean through the reader before serial 55. The text and the fixture change together; a word added to the closed list is a new serial. The Python package reads it as `onlyworlds.spine` (0.44.0 on 55, 0.44.1 on 56).

**What it is.** A world may describe a software ecosystem: what is built, the contracts it speaks, where each thing lives, who keeps it and what it depends on. This profile fixes how such a world spells that, so any company can keep a spine of its own and any reader (an audit, a map, a generated card, a picture) reads one the same way. It adds no type and no field to the standard. Each kind is an element type with a supertype from a closed list; structure uses the standard's own links (`Object.location`, `Object.technology`, `Object.parent_object`, `Location.parent_location`, `Location.buildings`, `Construct.custodian`, `Law.author`, `Law.enforcers`, `Title.holders`); and eleven extension keys carry what no schema field holds (one of them, `x_spine_owner`, only on a projection). The prefix `x_spine_` is reserved for this profile.

**Ownership is the standard's.** A seat is a Title with supertype `Seat`; its `objects`, `constructs`, `locations` and `laws` are what it keeps, and its `holders` keep it. That is why every kind of row is one of those four types: a seat's whole remit is one read of its Title. No key on a row names its owner.

**The kinds: a closed list** (a supertype is compared trimmed and without regard to case, as the room profile defines it; a reader shows the list's own spelling):

| Type | Supertypes |
|---|---|
| Object | `Tool`, `Service`, `Package`, `Plugin`, `Cron`, `Gate`, `Switch`, `Hook`, `Engine`, `Doc`, `Skill` |
| Location | `Site`, `Page`, `Repo`, `Room`, `Channel`, `World`, `Ship` |
| Construct | `Standard`, `Profile`, `Route family`, `Calendar` |
| Law | `Policy`, `Project charter`, `Charter` |
| Title | `Seat` |
| Event | `Birth`, `Release`, `Retirement`, `Move`, `Incident`, `Ruling` |
| Narrative | `Trail`, `Stop` |
| Relation | `Seam` |

The list holds two groups. **The row kinds** (the Object, Location, Construct and Law words, and `Seat`) are the 25 a picture draws as marks, one each (the visual contract, `Studio/desk/docs/2026-10-24-visual-contract.md`, frozen at 25), plus `Charter`, the world's one Charter. **The structure kinds** (the Event words, `Trail`, `Stop`, `Seam`) are drawn as time, paths and seams, never as marks. A word added to either group is a new serial and a word for the contract first.

A Character, an Institution and a Collective take any supertype: they are drawn by their type. A supertype is in the list only with its own type (`Page` on an Object is off the list). An element of a listed type whose supertype is off the list, or empty, is **off-list**: a picture draws it as a plain dot and a key names it as missing, never silently. The subtype is the owner's finer word and free.

`Charter` is the one Law that is the world's Charter (keel's front door and the checks profile read the newest Law with that supertype made by the owner or a co-builder); a project's charter is `Project charter`, so it never becomes the world's.

**The keys.** Machine values are lowercase, and a reader compares them trimmed and without regard to case, as above.

| Key | Value | A reader |
|---|---|---|
| `x_spine_address` | a list of non-empty strings: how it is reached (a URL, `npm: <name>`, a route, a room id, a path), one entry or more | a value that is not a list, or a list with no non-empty string, is not stated; non-string or empty entries are dropped |
| `x_spine_truth` | a string: where its live truth is read when this element is stale | a blank string is not stated; a value that is not a string is not stated and named |
| `x_spine_access` | one of `public`, `members-only`, `crew-only`, `private` (`crew-only`: read by every member of the crew that keeps it, as a crew room is; `private`: by one, as a key is) | any other value is not stated |
| `x_spine_status` | one of `live`, `legacy`, `provenance`, `gone` | any other value is not stated |
| `x_spine_layer` | one of `standard`, `platform`, `interface`, `client`, `docs`, `community`, `crew` | any other value is not stated |
| `x_spine_audience` | an ordered list from `stranger`, `builder`, `player`, `agent`, `crew`, the primary first | unknown words are dropped and named; the primary is the first known word; no known word is not stated |
| `x_spine_depends_on` | a list of element ids in this world, set on the dependent only | a value that is not a list is not stated; non-string entries are dropped; an empty list is stated (no dependencies), unlike an empty address list; whether an id resolves is the world's audit, never the reader's |
| `x_spine_probe` | a string in the probe form below | a probe whose verb is not in the form is `unsupported`, never run; the form is syntax, matched as written (case-sensitive, single spaces); a value that is not a string is not stated and named |
| `x_spine_probed` | an object `{state, at, read?}`: `state` one of `ok`, `failed`, `unsupported`, `none`; `at` an ISO time; `read` what a version verb read | written by the probe gate only |
| `x_spine_owner` | a string: an anonymous key, stable per seat | **on the projection only**, written by the projector in place of the seat's name; never in the world it projects from; a reader of the projection groups by it and shows no name |
| `x_spine_verified` | an object `{at, by}`: `at` an ISO date (a real calendar day, `YYYY-MM-DD`, optionally followed by a `T` time), `by` the id of the Title whose seat checked the row | an `at` that is not a real day is not stated, and the object is named |

**The probe form** (closed; a new verb is added to this list and the gate, never typed into a row): `http GET <url> expect <status>` · `gh repo <owner/name>` · `gh release <owner/name>` · `npm <package>` · `pypi <package>` · `dns <name> <type>` · `room <id>` · `file <path>` · `none <why>`. **No credential in a probe**: a gated surface's probe is what a stranger gets (`http GET <url> expect 404`).

**Status, in time.** `live` is in use; `legacy` is kept running but no longer developed; `provenance` is a step along the way, shown in the history, not offered; `gone` is a state a row passes through: once its `Retirement` Event is written (naming the row in its text, its `consequences` naming every dependent's owner), the row is removed. A `legacy` or `provenance` row has a `Retirement` Event.

**Time.** A spine counts days: the World's `time_basic_unit` is the day and **day 0 is 2012-01-01** (each spine may choose its own day 0 and says so in the World's description). A Construct with supertype `Calendar` carries an `atlas_calendar` (the calendar profile) that reads the count as Gregorian dates; the one this profile ships, valid from 2012-01-01 to 2100-02-28 (the first drift is 2100-02-29: no century rule):

```json
{"version": 1, "grain": "day",
 "bundles": {"months": {"names": ["January","February","March","April","May","June","July","August","September","October","November","December"],
                        "lengths": [31,28,31,30,31,30,31,31,30,31,30,31]},
             "week": {"length": 7, "names": ["Sunday","Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"]}},
 "intercalary": [{"name": "29 February", "after_month": 2, "every_years": 4}],
 "eras": [{"name": "AD", "start": -734517, "restart": true, "year_base": 1}],
 "format": "{day} {month} {year}", "format_intercalary": "{intercalary} {year}"}
```

Validated by the SDK's calendar kernel (4.70.0) against JavaScript's UTC dates for every day from 2012-01-01: step 0 reads 1 January 2012 (a Sunday), step 5410 reads 24 October 2026. The ISO strings in `x_spine_probed` and `x_spine_verified` are tool metadata, not world time.

**Trails.** A trail is a Narrative with supertype `Trail`; each stop a Narrative with supertype `Stop`, `parent_narrative` the trail, the standard's own `order` field its place, the caption in its `description`, and the elements it stands on linked through its typed links. A trail's `story` is its promise to the reader. A reader orders stops by `order`, then by `id` for ties; a stop with no `order` comes last.

**What a reader ignores.** An `x_spine_` key it does not know (kept byte for byte, the folder format's §3.3).

**What a writer must keep.** Everything it did not change. One writer per key: the owner's seat writes every key but `x_spine_probed`, which only the probe gate writes.

**The audit, which this page does not do.** One owner per row (exactly one Title lists it), every `x_spine_depends_on` id resolving, a `legacy` or `provenance` row with its Retirement Event: these need the whole world and belong to the world's own audit, not to a reader of one element. What a Charter can check through the checks profile (an address present, a status one of four) it does there.

**Conformance.** `spine.fixture.json`, beside this page: cases of `{element}` → what a conforming reader of one element says: its kind (the list's spelling, or off-list), each key as read (or not stated), the audience's primary, the probe's verb (or unsupported), and `dropped`: every value it left out and named, each `{key, value}` with the value exactly as the element held it, in the order address, truth, access, status, layer, audience, depends_on, probe, verified (within a list, the list's order). A reader compares `dropped` as JSON values, never as text, so no language's way of writing JSON matters.

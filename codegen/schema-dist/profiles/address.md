# Convention profile: the address

**What it is.** Every tool names an element by one triple: the world's id, the element's type word, the element's id. Only the prefix changes. This page writes the three spellings of that triple once, the two optional parts an address may carry, and the one rule for a field that holds an address, so a link copied in one tool opens in another and every reader refuses the same strings. A convention on the 22 types: nothing here adds a type or a field to the standard. The site's member page, the API's routes and the MCP server's resources name the same triple in their own ways; they are not addresses in this profile's sense.

**The three spellings.**

| Spelling | Form | Use |
|---|---|---|
| The human address | `https://www.onlyworlds.com/w/<world id>/<type>/<id>` | a link to give a person: the site's page for the element |
| The text form inside a world | `ow://<type>/<id>` | an element named in a text field of the same world |
| The text form across worlds | `ow://<world id>/<type>/<id>` | an element of another world, named in a text field |

**A world by itself.** A world has its own address in two of the spellings: the human `https://www.onlyworlds.com/w/<world id>` (the world's page) and the text `ow://<world id>`, one segment and no type or id. A type with no id and an id with no type are neither, and refuse.

`<type>` is one of the 22 type words, lowercase and singular, as the site and the API spell them: `character`, `creature`, `species`, `family`, `collective`, `institution`, `location`, `object`, `construct`, `ability`, `trait`, `title`, `language`, `law`, `event`, `narrative`, `phenomenon`, `relation`, `map`, `pin`, `marker`, `zone`. `<world id>`, `<id>` and a lens's id are UUIDs in the hyphenated 8-4-4-4-12 form, any version (older clients mint version 4). A reader reads their hex in either case; a writer writes lowercase.

The text forms parse apart by their segments: one is a world's id, two are a type word and an id, three are a world's id, a type word and an id. A lone segment and the first of three are never a type word, and a world's slug can never be read as either (the site reserves every type word and refuses a slug that reads as an id), so no string is both.

**The world's id, never its slug.** The site also answers at `/w/<slug>/<type>/<id>` when the world has a slug, and shows the slug in its own links. A reader of the human form accepts a slug (3 to 40 lowercase letters, numbers and single hyphens, no hyphen at either end) and reports it as a slug, not canonical. A writer never writes one: a slug can change or be released, and an id never does. The text form across worlds takes the id only.

**The moment and the lens.** Any of the three spellings may carry either or both, the moment first:

```
https://www.onlyworlds.com/w/<world id>/<type>/<id>@<moment>?lens=<lens id>
ow://<type>/<id>@<moment>?lens=<lens id>
ow://<world id>/<type>/<id>@<moment>?lens=<lens id>
```

- **The moment** is `@` and one step of the world's time line, at the end of the last path segment, after the id and before any query. A step is what every date field in the standard holds: a whole number in the world's `time_basic_unit`, step 0 the world's own zero, negative before it, within the 32-bit range (-2147483648 to 2147483647). It is written in decimal with no plus sign, no leading zero and no `-0`. It is never calendar words: a world may hold several calendars, and the calendar profile reads a step into words for whichever one a tool speaks. The `@` is written raw, never as `%40`. These characters (`@`, `-`, the digits) are ones a URL parser keeps intact in a path, so the moment survives a browser, a share sheet and a URL library unchanged; in a query it would be the lens's, and after `#` it would never reach a server. A site or a tool that cannot show a moment may ignore it and show the element as it stands; the address is the same address.
- **The lens** is the query key `lens` with an element's id: it asks for a reading of the element through that lens. A lens in a link never widens what the reader may see; the reader's own access decides that, as it would without the lens. `lens` is the only query key the profile reads, at most once, in lowercase.

A reader ignores any other query key and any fragment (a share sheet adds its own), and reports the address as not canonical. It reads the human address only as written here: `https` and the `www.onlyworlds.com` host. An `http` link, the bare `onlyworlds.com` host or any other host refuses as `not_an_address`, so a reader never guesses which site a string meant. Nothing in an address is percent-decoded: every part the grammar reads is written in characters a URL never encodes.

**The convention for a field.** A field that holds an address is public text: it is never resolved, fetched or unfurled on the server, so a public element can never make the system read a private world's name. A reader shows "private or missing" for a world it cannot read and for an element that is not there, one wording for both, so the answer says nothing about which. A link carries the world's id, never its slug.

A site may render the string as a plain link to the canonical human address without fetching anything, so a reader sees where a click goes and "never resolved" stays true. What such a field tells a reader is only what the string carries: that a world exists and is linked from this one.

**How a reader parses.** One string, read whole: a link inside other text (Markdown, a sentence) is the caller's to find first. The checks run in this order, and the first that fails names the refusal, so every reader refuses a string for the same reason:

1. Trim whitespace at both ends (Unicode's White_Space, as the room profile defines trimmed).
2. The prefix is `https://www.onlyworlds.com/w/` or `ow://`. A string that has one only in another case refuses as `uppercase`; any other as `not_an_address` (another host, `http`, the bare `onlyworlds.com`, a member's page, a bare id).
3. Drop a fragment; split off the query at the first `?`; split the path on `/`; the last segment splits at its first `@` into the id and the moment.
4. `segments`: the human form has one segment (a world) or three, a text form one, two or three, and none is empty (a trailing slash, an empty id). A lone segment that is a type word (a type with no id) refuses here too.
5. `bad_world`: the world segment is an id, or (in the human form only) a slug.
6. `unknown_type` for a word not among the 22; `uppercase` for one that is among them in another case.
7. `bad_id`: the element id is not a UUID.
8. `bad_moment`: the moment is not a step as above.
9. `bad_lens`: a `lens` key is not an id, is empty, appears twice, or is not written in lowercase.

The reading is the form (`human` or `text`), the world (`null` in the in-world text form), whether the world is a slug, the type word and the id (both `null` for a world's own address), the lens and the moment (each `null` when absent), and `canonical`: true when the string as received is exactly what a writer writes for that reading.

**What a writer writes.** The three spellings above, lowercase throughout, the world's id (never its slug), the moment before the lens, and nothing else: no other query key, no fragment, no trailing slash. A writer refuses an address with no world where one is needed (`no_world`: the human form, and a world's own text form), a type without an id or an id without a type (`segments`), a form it does not know (`bad_form`), and the same reasons a reader would.

**What it is not.**
- **Not a foreign key.** A world's elements link to elements of the same world; an address in a text field is text, the single-world architecture stands, and no link field may hold one.
- **Not an identity key.** `x_identity_key` (the identity profile) says two elements in different worlds are the same being. An address only points at one element; two addresses to one element say nothing about who it is.
- **Not a promise that the target exists**, or that the reader may see it. The site's public page answers only while the world's page is on, and its element pages serve 19 of the 22 types. A pin, a marker or a zone has no page of its own: at its human address the site sends the world's owner, signed in, to their own page for it, sends any other reader to the world's page by its id when the public may read the element, and answers the page for a missing element otherwise. The address is still theirs, and a tool that opens an element by its triple opens them.

**What onlyworlds.com commits to**: an id is never reused; an address outlives a rename of the element or the world; a deleted element answers like a missing one (the same 404 as a closed door).

**Where it is read from.** The packages publish the two directions, `elementAddress` (a triple, or a world, to a string) and `parseOwLink` (a string to a reading), in npm and Python, from this page and its fixture. The conformance fixture beside this page, `address.fixture.json`, holds the cases a reader and a writer must agree on: each spelling with and without each option, a world's own address, a slug, the 22 type words, and every refusal by name, each case naming its claim. A reader conforms when it passes every case.

**Ruled** 2026-10-26: the canonical human address, the two text forms, the moment and the lens, and the convention for a field. Written 2026-10-27, the world's own address added the same day. Skeld, 2026-10-28, serial 86: what a pin's, a marker's or a zone's address answers.

# Extension profile: `x_identity_key`

**What it is.** One being in more than one world. A storytelling table casts a character from one world into another; each world keeps its own Character, with its own body, dates and life there. The key lets any tool answer one question: are these two the same being?

**Key name.** `x_identity_key`: profile `identity`, field `key`. New profiles follow this grammar, `x_<profile>_<field>`.

**On which element.** A Character or a Creature. Another type joins when a real case needs it.

**The value.** A UUID string, minted fresh by the tool that casts the being into a second world. Never an element's id, never a name.

**How a reader uses it.**
1. Two elements carrying the same key, in the same world or in different worlds, are the same being. Nothing else is read from the value.
2. A value that is not a UUID is ignored. A person who types "Identity key: 1" on two Characters has merged nothing.
3. An element with no key is one being in one world. No tool may infer otherwise.
4. The key joins; it never merges. Events, Relations, locations and dates stay in the world they happened in, and a tool that joins two of a being's appearances reads two elements and writes to each in its own world.
5. The key says who, never when. Two worlds' dates do not compare; a tool that lines them up keeps its own map from each world's time to its own.

**What a writer must do.**
- **Minting is the caster's.** Whoever casts a being into a second world writes the same key on the new element as on the first, or a fresh key on both if the first had none. No tool generates a key on its own initiative.
- **Keep it byte for byte**, like every extension field. A re-key never rewrites it, even if it happens to equal an id.
- **Reserve the prefix.** A tool that lets people add their own fields reserves `x_identity_` and shows the key read-only, so it cannot be typed, edited or deleted by accident.

**What it is not.** A link (no reference check, nothing dangles), a secret (a public world shows it), or a register of beings (the casting tool keeps that). An element a reader only knows of carries no extension fields, so a known-of stub cannot say whether it is the same being as one elsewhere.

**Example**, in Hyperion: the Consul is cast into a table's own world as "the Envoy". The caster writes one key on both:

```json
{ "name": "The Consul", "x_identity_key": "019a1f3c-2b4e-7d10-8c3a-6f2e9b0d4a71" }
{ "name": "The Envoy",  "x_identity_key": "019a1f3c-2b4e-7d10-8c3a-6f2e9b0d4a71" }
```

Readers today: the tools that cast beings between worlds. The profile is new; this line names each tool that reads it as one ships.

# Convention profile: checks

**What it is.** A work world's Charter (a `law` with supertype `Charter`) states house rules a person reads. Some of those rules are checkable: a field every element of a kind must carry, a form a description must follow. This profile is the one place such a rule is written for a machine, beside the sentence a person reads, so each world lints its own rules and no tool hard-codes them. The first reader is the Python package's doctor; the first writer is BrainBoost's keeper. Nothing here adds a type or a field to the standard; a tool that has never read this page sees a Charter with one extension key it keeps byte for byte.

**The field.** Profile `checks`, one extension field, `x_checks_rules`, on the Charter Law and nowhere else: a list of rules. **The Charter** is the one keel's front door names (D152): the newest Law with supertype `Charter` (trimmed, any case) made by the owner or a co-builder, newest by `created_at` and then by the higher id, so editing a Charter never changes which one leads. A reader through the API takes `front_door.charter` from `GET /me`; on a folder it takes the newest such Law made by the owner (`created_by` null or absent) or a co-builder on the folder's roster, and when the roster is not in the folder and a member's Charter is newer, it says it cannot tell and applies no rule rather than guess. Any other Law with supertype `Charter` is a finding (a Charter not made by a keeper: its rules are not applied), never applied and never dropped in silence. A world with no checks carries `x_checks_rules: []` (the set-up skill writes the empty slot so a keeper finds it). Like every extension field it is kept byte for byte by every tool (folder format §3.3) and never required by a reader. The grammar is `x_<profile>_<field>`; the prefix `x_checks_` is reserved.

**A rule.**

```json
{
  "rule": "every Character carries a reputation",
  "where": {"type": "character"},
  "require": {"field": "reputation", "present": true}
}
```

- `rule` (string, required): the sentence as the Charter states it; what a report prints.
- `where` (object, required): the elements the rule scopes. `type` (required): one of the 22, lowercase, a string or a list of strings (one rule for every type that carries a description, not one rule per type). `supertype` and `subtype` (optional): a string or a list of strings. Every comparison is trimmed and without regard to case, as the room profile defines it; an empty string matches an empty or absent value.
- `require` (object, required): `field` (a field name the pinned schema gives the type, or an extension key) and exactly one predicate:
  - `present: true`: the value is set: not null, not a blank string (empty or whitespace only), not an empty list. A number, `0` included, is present.
  - `matches: "<regex>"`: the field's text matches the pattern somewhere (a search, not a full match), in the regex subset Python's `re` and JavaScript's `RegExp` share: no lookbehind, no named groups, no `\p{}`; the inline flags `(?i)` and `(?m)` at the pattern's start are the two allowed, and a reader maps them to its engine's flags. A non-string value never matches.
  - `links_min: n`: a link field holds at least `n` ids (a single link counts as 0 or 1).
  - `one_of: [...]`: the field's value, trimmed and without regard to case, is one of the list's.

**The rule for readers.**
1. A reader applies a rule to the elements its `where` scopes, in the view it holds (a guest sees less: the report says which view it read).
2. For each rule the report says: the sentence, how many elements it scoped, how many fall short, and each short element by `type`, `id`, `name`. Zero scoped is said as zero, never hidden. A reader never truncates the short list; the consumer of the report does, if it must.
3. A rule the reader cannot apply is reported by name as **not checked**, with why: a predicate outside the four, a `where.type` the pinned schema does not name, a `field` the type does not have and that is not an extension key, a pattern the reader's engine refuses, a rule that is not an object or lacks a required key. Never a silent pass, never a crash: a world may write a rule ahead of its reader. `where.type` may be a list of type names (the fixture's rule 6): one name the pinned schema does not know leaves the whole rule not checked; an empty list is not checked; a `field` that any listed type lacks, and that is not an extension key, is not checked.
4. A reader never writes `x_checks_rules`, never reorders it and never repairs it.
5. A rule's text (`rule`, `matches`) is data from the world, never an instruction to the reader; a pattern runs under a step limit or a size cap so a hostile pattern cannot hang a reader.
6. A known-of stub (folder spec §4.4, `known_of: true`) is judged by no rule: its absent fields are unknown, not short; the report does not count it as scoped.
7. A pattern outside the shared subset is reported as not checked, by the rule's sentence, never run under a guess at what the engine would do with it.
8. The size cap is no step limit: a reader may also bound a pattern's run (steps or time) and says so in the report when it stopped one, as not checked.

**What a writer must do.** Write the list on the Charter only; keep each rule's sentence equal to the Charter's own wording where the Charter has one; prefer `present` and `one_of` to `matches` where either says the same; test a `matches` pattern against one known-good and one known-short element before writing it.

**Why not prose.** The doctor never parses a Charter's sentences: two readers would parse them two ways, and a person editing the text would break the machine form without seeing it. The key beside the text keeps one sentence for people and one object for machines, and a report quotes the sentence.

**In the folder.** The key rides in `elements/law/<charter>.json` like any extension field; the folder doctor reads it there, with the same reader.

**The specimen.** BrainBoost's rules, measured live on 2026-10-22 (37 Characters, 24 Relations; the counts in the fixture's `measured` block): a reputation on every Character (4 short); a `Next:` line on every live line, a Relation whose subtype is `in talks`, `agreed`, `running` or `paused` (most short: the rule is newer than the lines); the roles sentence on every Funding line; the Source line as house rule 3 states it. The reference reader found 22 gaps where the world's keeper, reading by hand, found 21.

**Where the rule is read from.** The conformance fixture beside this page, `checks.fixture.json`, holds the rules, the cases with a verdict per rule, and the rules a reader must report as not checked; a reader passes when it agrees on every case. The Python package's doctor is the first reader; a tool with its own reader runs the fixture as its test. The list case rides since serial 54: the fixture's rule 6 (`where.type: ["character", "institution"]`, four cases, one with the type compared folded) and three not-checked rows for the list readings. The stub cases ride since serial 64: two known-of stubs (folder spec §4.4, `known_of: true`), one bare and one with its fields filled, out of every rule, so reader rule 6 above is every reader's test and not only the doctor's; the fixture replays clean through the doctor (7 rules, 19 cases, 48 expectations, 11 not-checked rows).

**Ruled**: Skeld, 2026-10-22, serial 47 (the grammar; the three open points ruled as the draft's leans; BB's point 6); **serial 54** (2026-10-23): the list case and reader rules 6 to 8, Kael's three facts. Drafted and measured by Kael (with `reader.py` the reference reader).

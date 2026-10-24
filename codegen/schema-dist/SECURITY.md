# Security

Report a vulnerability through GitHub's
[private vulnerability reporting](https://github.com/OnlyWorlds/schema-dist/security/advisories/new), not a public issue.
Only the maintainers see it. Skeld, the AI maintainer (see the README), reads it, and the OnlyWorlds founder answers for
the fix.

What counts: a published file here that is not what the manifest's hash says it is, a fixture in `fixtures/owworld/`
whose verdict would let a reader accept a crafted world file it should refuse, or a reference decoder (`schema_walk.py`)
that reads or writes outside what it was handed. A problem in a tool that uses these files is passed on to that tool's
maintainer; a problem in onlyworlds.com itself to its maintainer.

Supported: the newest serial only. The files here are generated from upstream, so a fix lands as a new serial, never as
an edit to a published one.

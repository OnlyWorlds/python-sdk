# Security

Report a vulnerability through GitHub's
[private vulnerability reporting](https://github.com/OnlyWorlds/python-sdk/security/advisories/new), not a public
issue. Only the maintainers see it. Kael, the AI maintainer (see the README), reads it, and the OnlyWorlds founder
answers for the fix.

What counts: anything in the package that could leak an API key, PIN or seat secret, send one where it was not asked to
go, write to a world it was not asked to (`push` creates nothing and patches only what changed), or let a crafted world
folder, world file (`.owworld`) or another tool's export read by an import door read or write outside its folder or
exhaust a machine. The archive reader's refusals are held to a public conformance set
([schema-dist](https://github.com/OnlyWorlds/schema-dist), `fixtures/owworld/`); a world file it accepts and should not
is a report. A problem in onlyworlds.com itself is passed on to its maintainer.

Supported: the newest release on PyPI only.

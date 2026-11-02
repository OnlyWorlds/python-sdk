# Convention profile: the landing

**What it is.** A world's first picture at a door: when a person's world opens where they arrive (onlyworlds.com's landing shows an account's OnlyWorld), a real world shows its most-linked Characters, each with what it links, and a small world shows its gaps, each an invitation to make the world bigger. It adds nothing to the world: no field, no mark, nothing stored. It is a reading of the graph the lens profile defines, so it sees exactly what that graph holds and never more.

**The reading.** `landingOf(graph, options)`, one reader in the SDK and the Python package (`landing_of`), from the fixture beside this page. `graph` is what the lens profile's `worldGraph` answers for the visitor, so every leave-out is already made: the room, hidden and proposed elements, map space and the reading aids are not in it, and a reader that wants them back asks the graph, never this one. The answer is `{mode, size, clusters, unclustered, gaps}`. All five keys are always present, in that order. It holds structure only, never coordinates: a layout is the drawing tool's, keyed by id.

**Options**, each a whole number, refused by name when it is anything else. An option given as null takes its default, as in `worldGraph`, and an unknown key is refused by name before anything is read:
- `heads`: how many clusters at most. Default 5, at least 1. A whole number too large for the reader to hold reads as the largest it holds: any value past the node count means every head.
- `hops`: how far a head reaches. Default 1, at least 1.
- `size`: the node count at which the mode turns from gaps to graph. Default 24, at least 1.

**Degree** counts every edge, in or out, once at each node it touches. A mirror pair is two edges, and a link to itself counts once.

**The rules.**
1. **The mode.** `gaps` when the graph has fewer nodes than `size`, `graph` otherwise. The answer carries the `size` it was read at. Both parts are always read, and the mode says which one a door draws first.
2. **Heads.** The Characters with at least one edge, most linked first, ties by id in code point order, the first `heads` of them. A known-of node is never a head. A world with no linked Character has no clusters.
3. **Clusters.** A node within `hops` steps of a head joins the head it is fewest steps from. A step follows an edge either way, and a mirror pair is one step. When two heads are equally near, the node joins the higher-ranked one, so every node has one home. Each cluster is `{head, members}`, in the heads' order. A member is `{id, hops, degree}`: the head first at 0, then by hops, then by degree (highest first), then by id.
4. **Unclustered.** Every node no head reaches, as `{id, degree}`, by degree (highest first), then by id: the world around the clusters, which a drawing mutes.
5. **Gaps.** One entry per gap, `{kind, id}`, in the order of the kinds, then by id. A node can carry several. A known-of node is never a gap, since a stub carries no links. The kinds:
   - `orphan` and `near_orphan`: a node of degree 0, and one of degree 1, by the degree this page defines (an edge counted once at every node it touches: a link to itself once, each place in a list once), never by a report's own count.
   - `no_place`: a Character whose `location` names no Location node.
   - `nobody_here`: a Location that no Character's `location` names. Another type's `location` does not count.

   For the last two, the field a button fills is `location` on the Character. `no_place` reads from the graph the visitor is served: a Character whose place is hidden from them reads as having none, since the landing shows a person what they may see and nothing it must keep from them.
6. **A stable order.** The same graph and options give the same answer, byte for byte. Everything is counted in integers, and ids compare by code point, never by UTF-16 unit.

**Where it shows.** onlyworlds.com's landing, for a signed-in owner's OnlyWorld. Keel bakes the answer as a file of its own beside the world's graph file, carrying the mode and the size it was baked at, and the stage draws it. Any tool may draw it at its own door. Neither lenses as clusters nor graphs beyond one world are in this profile.

**The fixture.** `landing.fixture.json`: each case is a graph in `worldGraph`'s shape (only the keys the reader reads), its `options`, and a `want` that holds the keys the case tests. A case marked `whole` holds the entire answer, keys in order. A refusal is `{refused: <option>}`. The cases cover:
- a tie on degree, and ids above U+FFFF that UTF-16 order would sort the other way;
- the nearest head beating a higher-ranked one, and a tie on hops going to the higher-ranked;
- the default reach and a wider one, and the cap on heads;
- a Character with no link, and a known-of Character, as no head;
- a mirror pair and a self link;
- no Characters, and an empty graph;
- each gap kind, an Object's `location`, and a place the visitor may not see;
- the mode at, under and over the size, and null options;
- the refusals.

**Ruled**: 2026-11-01, on the first draft. 2026-11-02, serial 104: `orphan` and `near_orphan` by this page's degree (three engine ports read the toolkit's report count and the page's degree apart on a self link and a doubled target); a `heads` past the reader's integer range reads as the largest.

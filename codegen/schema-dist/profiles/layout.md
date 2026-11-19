# Convention profile: the default layouts

**What it is.** Three ways to draw a world nobody has laid out. `by-kind` and `around` read its graph alone. `by-kind` lays out a whole graph: each kind of element has its own place round a circle, links draw elements together, and the points come out the same every time. `around` lays out one element and what is linked to it, on rings. `by-links-3d` lays a whole graph out in three dimensions by its links, and where the world has a map, its pinned elements stand on it. The three differ on an element linked to no other: `by-kind` places it by its kind's anchor, `around` leaves it out of its answer unless it is the focus, and `by-links-3d` leaves it out unless it is pinned on a map, and lists it as `unplaced`. They add nothing to the world: no field, nothing stored. Each is a method word for the map-space profile's rule 8, so a Map whose Pins were made by one can say so.

**The promise.** The same input gives the same points in every tool and every language. For `by-kind` the input is the graph; for `around` the graph, the focus and `steps`; for `by-links-3d` the graph, the world's Maps and Pins, and `held` with `heldUnit`. `by-kind` to the last bit; `around` to within 1e-12 (an absolute difference, on each x and y); `by-links-3d` to the last bit for every element placed `centre`, `with` or `map` that does not stand on its ring and every element that stands at its held point, and to within 6e-8 (a billionth of a rest, an absolute difference on each x, y and z) for an element placed `arm` or `link` and for every element that stands on its ring, save the two tests its held points' rules (H6) and its ring (step 11) name. The promise is of points, numbers in a plane for `by-kind` and `around` and in space for `by-links-3d`, and not of a picture: which way a tool turns y on its screen, and how it looks at z, is the tool's. Where y grows downward, as on a screen, `around`'s angles run clockwise from the top. That is what the fixtures beside this page hold, and it is the reason every step below is written in its order. `by-kind` is sensitive: one number changed in its last place moves a large picture visibly, so a tool agrees with the fixture exactly or it is drawing something else.

**The graph.** `{nodes, edges}` as the lens profile's `worldGraph` answers it for the reader. A node is `{id, type, name}`: `type` is the element type's word in lower case (`character`), `name` a string, null or absent (only `around` reads it). An edge is `{source, target, field, index}`, by id; `field` and `index` may be absent. An edge whose `source` or `target` is not a node is passed over.

**The one order.** Before anything else the graph is put in one order, so the order it was handed in changes no point and no member of any answer (three answers below are listed in the handed order, and each says so):
- the nodes by `id`;
- the edges by `source`, then `field` (absent as the empty string), then `index` (absent as 0, by number), then `target`.

Every string is compared by Unicode code point, never by a locale. Below, node `i` means the node at place `i` in this order, counted from 0, and `n` is the number of nodes.

**The kinds' order.** The `groups` of `layout.fixture.json` give each of the 22 types its colour group, and its `group_order` puts the four groups in order. A type's rank is its group's place in `group_order`. Kinds are ordered by rank, then by the type word (code point order). The groups are the fixture's and no other: a node's own `family` or colour, where a graph carries one, is not read, and a method's word holds these groups for as long as the word is read. `by-links-3d` reads no kinds' order.

**Arithmetic.** Every number is an IEEE 754 double (one seed of `by-links-3d` apart, below). `by-kind` uses addition, subtraction, multiplication, division, square root, floor, the greater and the lesser of two numbers, and `mod`, and nothing else. Each expression below is evaluated as written: brackets first, multiplication and division before addition and subtraction, and operations of the same rank from left to right; nothing is regrouped, and no two operations are fused into one (a compiler that fuses a multiply and an add must be told not to). `around` uses addition, subtraction, multiplication, division, floor, the greater and the lesser of two numbers, cosine, sine and the double nearest pi (`PI`), and nothing else; its cosine and sine are why it is held to a tolerance and `by-kind` is not. `by-links-3d` uses what its own Arithmetic paragraph lists, and in its step 9 cosine, sine and `PI` and in its step 11 the arcsine, cosine, sine and `PI`, which is why its `arm` and `link` points and the points of its ring are held to a tolerance; its step 7 works each element's seed in whole numbers of 32 bits, as that step says.

What trips a port, each seen to turn fixture cases red:
- every `/` below divides doubles, also where both sides are whole numbers (`it / steps`, `len / 12`, `q / (c - 1)`);
- `floor` is toward minus infinity, not a cast that drops the fraction (a cell left of or above 0 differs);
- the generator needs unsigned or 64-bit whole numbers: a signed 32-bit one overflows;
- a sum regrouped (`ux * ux + (uy * uy + 0.000001)`) is another sum;
- the anchors are read as exact doubles: every digit `layout.fixture.json` prints, parsed with correct rounding.

## `by-kind`

It takes the graph, and places every node of it.

**1. The small cases.** With no node the answer has no points. With one node its point is 0, 0.

**2. The links.** Walk the edges in the one order. An edge whose two ends are both nodes and not the same node is a link `[a, b]`, the places of its source and its target. A link that appears twice is kept twice.

**3. The anchors.** List the types present among the nodes, in the kinds' order; let `k` be how many. The `anchors` of `layout.fixture.json` hold, for each `k` from 1 to 22, `k` points on the unit circle (it is a JSON object, so its keys are the strings `"1"` to `"22"`). The type at place `j` of the list has the anchor `anchors[k][j]`, an `[x, y]`. The table is read, never computed: these numbers are the method's, and a cosine worked out at run time may differ from them in the last place.

**4. The generator.** One whole number `g`, starting at 7. Each draw: `g = (g * 1664525 + 1013904223) mod 4294967296`, and the draw's value is `g / 4294967296`. (The product stays under 2^53, so a double holds it exactly.)

**5. The start.** For each node `i` in order, with `(ax, ay)` its type's anchor, drawing for x before y:

```
px[i] = ax * 0.8 + (draw() - 0.5) * 0.5
py[i] = ay * 0.8 + (draw() - 0.5) * 0.5
tx[i] = ax * 0.85
ty[i] = ay * 0.85
```

**6. The sizes.**

```
rest  = max(0.002, 0.9 / sqrt(n))
push  = rest * rest * 1.4
cell  = rest * 2.2
cell2 = cell * cell
steps = 160 when n > 2000, else 320
```

**7. The steps.** For `it` from 0 to `steps - 1`, with `t = 1 - it / steps`, and every `fx[i]`, `fy[i]` set to 0 at the start of the step:

*The cells.* Node `i` is in the cell `(floor(px[i] / cell), floor(py[i] / cell))`. Each cell lists its nodes in rising order of `i`.

*The push.* For each node `i` in order, with `(cx, cy)` its cell; for `dx` of -1, 0, 1 and inside that for `dy` of -1, 0, 1; take the cell `(cx + dx, cy + dy)` if any node is in it, and let `len` be how many.

When `len` is more than 12, the cell is sampled, and only node `i` is pushed:

```
off   = (i * 7 + it * 13) mod len
scale = len / 12
for q from 0 to 11:
    j = the cell's node at place (off + q) mod len
    if j is i: pass it over (its place among the 12 is not refilled)
    ux = px[i] - px[j]
    uy = py[i] - py[j]
    d2 = ux * ux + uy * uy + 0.000001
    if d2 > cell2: pass it over
    d = sqrt(d2)
    f = (push * scale) / d2
    fx[i] = fx[i] + (ux / d) * f
    fy[i] = fy[i] + (uy / d) * f
```

Otherwise, for each node `j` of the cell in rising order, only when `j` is greater than `i`, both are pushed:

```
ux = px[i] - px[j]
uy = py[i] - py[j]
d2 = ux * ux + uy * uy + 0.000001
if d2 > cell2: pass it over
d = sqrt(d2)
f = push / d2
fx[i] = fx[i] + (ux / d) * f
fy[i] = fy[i] + (uy / d) * f
fx[j] = fx[j] - (ux / d) * f
fy[j] = fy[j] - (uy / d) * f
```

The two branches are not symmetric (a node beside a crowded cell can be pushed by one of its nodes twice, or not at all). That is the method as it stands; the `a-crowded-cell` case of `layout.fixture.json` holds it.

*The links.* For each link `[a, b]` in order:

```
ux = px[b] - px[a]
uy = py[b] - py[a]
d = sqrt(ux * ux + uy * uy) + 0.000001
f = (d - rest) * 0.06
fx[a] = fx[a] + (ux / d) * f
fy[a] = fy[a] + (uy / d) * f
fx[b] = fx[b] - (ux / d) * f
fy[b] = fy[b] - (uy / d) * f
```

*The move.* For each node `i` in order:

```
fx[i] = fx[i] + (tx[i] - px[i]) * 0.06
fy[i] = fy[i] + (ty[i] - py[i]) * 0.06
m      = sqrt(fx[i] * fx[i] + fy[i] * fy[i])
cap    = 0.03 * t + 0.002
shrink = cap / m when m > cap, else 1
px[i] = px[i] + fx[i] * shrink
py[i] = py[i] + fy[i] * shrink
```

**8. The frame.** With `x0`, `x1` the least and greatest `px`, and `y0`, `y1` the least and greatest `py`:

```
span = max(x1 - x0, y1 - y0)
fit  = 2 / span when span > 0.000000001, else 1
mx = (x0 + x1) / 2
my = (y0 + y1) / 2
point of node i = ((px[i] - mx) * fit, (py[i] - my) * fit)
```

**9. The answer.** One point per node, in the order the nodes were handed in (not the one order), each with its `id`; and the method's word, `by-kind`. The points lie in a frame of -1 to 1 on the picture's longer axis, centred, proportions kept.

## `around`

It takes the graph, the `id` of one node (the focus) and `steps`, 1 or 2, and places the focus and every node within its steps. For a focus that is no node of the graph this page promises nothing.

**1. The neighbours.** Walk the edges in the one order. For an edge whose two ends are both nodes, with places `a` and `b`: `b` joins the end of `a`'s list, and when `a` is not `b`, `a` joins the end of `b`'s list.

**2. The reach.** The focus has depth 0. Then for depth 1, and for depth 2 when `steps` is 2: walk the nodes found at the depth before, in the order they were found, and each one's list in its order; a node met for the first time gets this depth, and remembers the node whose list it was met in (its parent). The order nodes are found in is kept.

**3. The first ring.** The nodes of depth 1, ordered by the kinds' order of their types, then by name (null or absent as the empty string, code point order), then by place in the one order. With none, the answer is the focus alone. Let `count` be how many.

```
first = min(count, 60)
r1    = max(0.34, first * 0.017)
gap   = (2 * PI * r1) / first
r     = r1
```

Then, until every node of the ring is placed: `room = max(1, floor((2 * PI * r) / gap))`; the next `room` nodes (or as many as are left; let `these` be how many) stand on a circle of radius `r`, the node at place `q` among them, counted from 0, at the angle

```
a = -PI / 2 + (2 * PI * (q + 0.5)) / these
point = (cos(a) * r, sin(a) * r)
```

and then `r = r + gap * 1.2`. When all are placed, `outer = r - gap * 1.2`: the radius of the last circle used.

**4. The second ring** (`steps` 2). The nodes of depth 2, grouped by parent, each group in the order its nodes were found. With `a0` the parent's angle (the `a` it was placed at) and `c` the size of its group:

```
spread = min(0.5, ((2 * PI) / max(1, count)) * 0.9)
a = a0                                    when c is 1
a = a0 + (q / (c - 1) - 0.5) * spread     for the node at place q of the group, otherwise
point = (cos(a) * outer * 1.8, sin(a) * outer * 1.8)
```

**5. The answer.** The focus at 0, 0 and every node within the steps, in the order the nodes were handed in, each with its `id` and its depth (0, 1 or 2); and the method's word, `around`. Nodes further out are not in the answer. The points are not fitted to a frame.

## `by-links-3d`

It takes the graph, the world's Maps and Pins where it has them, and optionally points it answered before (`held`, with `heldUnit`), and places in three dimensions every node of the graph that is linked to another node or pinned on a map. The body of the graph, its largest part that no single element's removal parts, is cut into groups round its most linked elements; the groups are packed apart, and seeded force steps settle each group round its point. What hangs off the body fans out from it, and when the Map of the world that holds the most of the graph's elements by a Pin holds three or more, that Map is a flat plate with each pinned element at its Pin, and a Map of a place on it can stand over it as a small plate (step 4). Each other piece of linked elements is laid out the same way on its own: one that holds a pinned or held element stands where those points put it, and the rest stand on a ring beside the main piece. An element linked to no other and pinned on no map is not placed; the answer lists it as `unplaced`.

Steps 1 to 9, with the held points' rules, are one run of the method on a graph. The method makes one run on the whole graph and one on each other piece that holds a pair (step 10), and step 11 sets the pieces on their ring.

**What it reads besides the graph.** The world's Maps and Pins, through the map-space profile's reading and nothing of its own: of each Map in its `maps` the `id`, `width`, `height` and `location` (a `width` or `height` that is no whole number, or none, is measured from the Map's own Markers and Pins, and is null when none of them is placed, that profile's rule 2); of each Pin in its `pins` the `pin`, `map`, `element_id`, `x` and `y`. A Map that the map-space profile's layout reading answers as a layout map (its rule 8) is left out, with its Pins, as that profile's rule 11 asks of a tool that picks a Map for the world's space: a saved layout never stands in for the world's own space. A Pin names its element by `element_id`; the reading answers it only when the Pin carries `element_type` too, and the type is not compared with the node's. A Pin's `z` is not read, and neither is a Map's `depth`: the plate is flat. With no Maps and Pins handed, the method reads the graph alone.

**Which graph.** The method lays out the graph it is given, every node of it that is linked to another node or pinned, of any type. Map, Pin and Marker elements are the world's space: the lens profile's graph leaves them out by default (without a lens its `map_space` flag brings them in; with a lens, only those the lens keeps are in, whatever the flag says), and a tool that makes its graph another way leaves those three types out of what it hands in. The method reads Maps and Pins as the world's space (step 4), and a Marker only where the map-space reading measures a Map's `width` or `height` (one that is no whole number, or none, its rule 2), and a Zone only where that reading asks whether a Marker's `zone` is served (a Marker whose `zone` is not served is `dangling`, its rule 4, and measures nothing). Left in the graph, each is a node like any other. A Zone stays, as for `by-kind`.

**The constants.** Each is written below by its name and is the double nearest the number here; an expression that multiplies two of them (`TILE * REST`) is worked out as written.

| name | value | |
|---|---|---|
| `REST` | 60 | a link's length at rest; the unit of every point |
| `STEPS` | 300 | the force steps |
| `MAX_CENTRES`, `MIN_GROUP` | 12, 3 | step 3 |
| `WAYS_CAP` | 4503599627370496 (2^52) | step 3 |
| `SPREAD`, `TILE` | 2, 0.4 | step 4 |
| `LOBE`, `GAP`, `CLEAR`, `PACK_STEPS` | 1.1, 1.25, 1.8, 600 | step 5 |
| `CROSS`, `PLATE`, `HOLD` | 0.25, 0.02, 0.12 | step 6 |
| `CAP0`, `CUTOFF` | 0.1, 3 | step 8 |
| `GOLD` | `PI * (3 - sqrt(5))` | step 9 |
| `LINE` | `REST / 8` | held points |
| `SNAP` | `REST / 1000000000` | held points |
| `HELD_BOX`, `FRAME_AGREE` | 768, 3 | held points |
| `RING_GAP` | `CLEAR * REST` | step 11 |
| `FIT`, `FIT_BAND` | 0.000001, 0.0000001 | step 11, in radians |

**Arithmetic.** The page's Arithmetic paragraph holds here as it is written: every number a double, each expression evaluated as written, brackets first, multiplication and division before addition and subtraction, and operations of the same rank from left to right, nothing regrouped and no two operations fused. The one place whole numbers are worked past what a double holds is step 7's seed, which that step writes out. Steps 1 to 8, that seed apart, and the held points' rules H1 to H5 use addition, subtraction, multiplication, division, square root, floor, the greater or the lesser of two numbers, and the `mod` of `by-kind`'s generator (step 7's draws), and nothing else. Step 9 also uses cosine, sine and `PI`, and so does H6, which works out step 9's places. Step 10 works out no number of its own, and step 11 uses addition, subtraction, multiplication, division, square root, the greater of two numbers, the arcsine (`asin`), cosine, sine and `PI`. So an element placed `centre`, `with` or `map` that does not stand on the ring, and every held element, has the same point to the last bit in every tool, and an element placed `arm` or `link`, and every element on the ring, the same to within 6e-8 on each of x, y and z. Two correct builds differ only by a few units in the last place of a cosine, a sine or an arcsine, so the points placed with them agree within the fixture's `compare.within`, that 6e-8. Every placed id, every `how`, `group`, `part`, `held`, `centres` and `unplaced` entry, the pieces, which of them stand on the ring, their order on it, and each one's ring are the same in every tool, save the tests step 11 and H6 name (a near test of H6 can move a point of a piece that is not moved, and so `Rmain` and the ring). A length is `sqrt(dx * dx + dy * dy + dz * dz)`, in that order.

**The directions table.** `layout-by-links-3d.directions.json`, beside the method's fixture `layout-by-links-3d.fixture.json`, holds, under its key `directions`, for each `K` from 1 to 37 a list of `K` unit vectors `[x, y, z]`, keyed by `K` as a string (`"1"` to `"37"`); its `k_max` is 37. `K`, the number of parts of a run (step 5), is never over 37: step 3 takes at most `MAX_CENTRES` centres on the body and at most `MAX_CENTRES` more, at most twice, on a group, and the plate is one part more (12 + 12 + 12 + 1). `dir(K, s)` below is row `s` of the list for `K`, counted from 0. The table is read, never computed (rule 3 of `by-kind` says why), every digit parsed with correct rounding; a zero written `-0.0` is read as it is written. The cases hold the table only for the counts of parts they reach: the z of `dir(3, 0)` read as the next double above 1 turns 34 of the 116 cases red, and the runs of the cases reach `K` of 1, 2, 3, 4, 5, 7, 8 and 12 alone (1 reads no row), so every other row is held by nothing but the hash. What holds the table whole is its sha256, which the fixture names as `table_sha256`: check the bytes you read against it.

**1. The one order, and the pairs.** With no node, the answer is empty (step 12). The nodes are put in the page's one order; node `i` is the node at place `i`, and `n` the number of nodes. An edge whose `source` or `target` is not a node is passed over. A pair is two different nodes joined by at least one edge, in either direction; each pair is listed once, as `(a, b)` with `a < b`, and the pairs are ordered by `a`, then `b`. A self-link makes no pair. A node's neighbours are the nodes it shares a pair with, and its degree is how many.

**2. The body.** Three readings of the pairs.

*The pieces.* Two nodes are in one piece when a path of pairs joins them. A piece holds a pair when it has two nodes or more. The main piece is the piece with the most nodes; of several that large, the one that holds the lowest node. Every node outside the main piece is `off`.

*The blocks.* When the main piece is one node, that node is the body. Otherwise the main piece's pairs fall into blocks: two pairs are in one block when one cycle that passes no node twice runs through both, and a pair on no cycle is a block alone. A block's members are the ends of its pairs. (These are the biconnected components, as the depth-first walk of Hopcroft and Tarjan finds them.) The body is the block with the most members. Of several that large: put each block's members in rising order and read two blocks member by member; at the first place where they differ, the block with the higher node wins. Two blocks share at most one node, so one always wins.

*What hangs.* Every node of the main piece outside the body reaches the body through exactly one body node, its cut; its depth is the number of pairs on the shortest path from the cut to it.

**3. The centres and their groups.** A set below is a set of nodes, and inside a set only the pairs with both ends in it are read.

*Reach*, for a set and its centres in rank order. Levels: every centre is at level 0; a node of the set is at level `d` when it is at no lower level and has a neighbour in the set at level `d - 1`. Each node carries one count for each centre: at level 0 a centre's count for itself is 1 and its other counts are 0; at level `d` a node's count for a centre is the sum of that count over its neighbours in the set at level `d - 1`, each sum taken as `min(WAYS_CAP, a + b)`. A centre is its own group. Any other node the levels reach joins the centre it has the greatest count for; among equal counts, the centre of lowest rank. A node the levels do not reach is in no group.

*Pick*, for a set of `size` nodes:
- `count(v)` is the number of `v`'s neighbours in the set. Rank the set by `count`, most first; among equals the lower node first.
- `least` is the smallest whole number `f` with `f * f >= size`, and never under 3.
- Walk the ranking. Stop at the first node whose `count` is under `least`, or when `MAX_CENTRES` are taken. A node `v` is taken when, for every centre `q` already taken, `2 * h < count(v)`, where `h` is the number of `v`'s neighbours in the set that are `q` or a neighbour of `q` in the set. The centres' rank is the order they were taken in: the first taken has rank 0, the lowest rank.
- When none was taken, the first node of the ranking is the one centre. A pick on a set of no nodes gives no centre.
- Reach. Then, while there is more than one centre and some group has fewer than `MIN_GROUP` members (its centre counted): of the centres of such groups, the one taken last (the greatest rank number) is no centre any more, the centres after it each take the rank before theirs, and reach is read again.

*The centres.* Pick on the body. Then at most twice: take the group with the most members, its centre counted (among equals, the lowest rank); when twice its members is not more than the body's size, stop. Otherwise pick on that group's members without its centre. When that gives fewer than two centres, stop. Otherwise the new centres are added after the old ones, in their own rank order. The reach that pick read last, on that group's members without its centre, is kept: reach is not read again on the body. Each member that reach reached joins its new centre; a member it did not reach stays with the old centre, whose group may now be smaller than `MIN_GROUP`, and stays a group.

The answer of this step: `k` centres in rank order, and for every body node its group `g`, the rank of its centre.

**4. The plate.** With no Maps and Pins, or when this step ends in "no plate", steps 5 to 9 run without one.

- *The maps* are the Maps of the map-space reading that are no layout map, each with its `width`, `height` and `location` as that reading answers them.
- *The pins.* Walk the reading's Pins by `pin` id (code point order). A Pin counts when its `map` is one of the maps and its `element_id` is a node. On each map an element keeps the first place a counted Pin gave it, `(x, y)`; a later Pin of the same element on the same map is passed over. Each map lists its elements in the order they were first placed.
- *The first map* is the map with the most elements; among equals, the one whose `id` is greater (code point order). With no counted Pin there is no plate. When the first map has fewer than three elements, or its `width` or `height` is not a number over 0, there is no plate: no other map is tried in its stead. The `width` and `height` are the map-space reading's (its rule 2: a whole number the Map carries is answered as that number, 0 and under 0 included; any other value, or none, is the largest x and y among the Map's own placed Markers and Pins, and null when none is placed), so a first map with no whole `width` of its own still has one, and one that carries 0 or under has no plate.
- *Its places.* With `W`, `H` the first map's `width` and `height` and `many` its number of elements:

```
scale = SPREAD * REST / sqrt(W * H / many)
m     = (x - W / 2, y - H / 2)                  the element's map place
place = (m.x * scale, m.y * scale, 0)
```

- *The small plates.* The other maps that hold a counted Pin, by `id` (code point order). Go through them in passes until a pass takes none; within a pass each is read in that order against the places as they stand at that moment. A map is taken when its `location` is the id of an element that has a place, its `width` and `height` are each a number over 0, it has three elements or more, and at least one of them has no place yet. With `cw`, `ch` its width and height, `many` the number of all its elements (those with a place already counted too), and `(lx, ly, lz)` its location's place, each of its elements that has no place yet, in the map's own order, gets:

```
sc    = TILE * REST / sqrt(cw * ch / many)
rise  = REST * 4 when many >= 20, else REST * 2
place = (lx + (x - cw / 2) * sc, ly + (y - ch / 2) * sc, lz + rise)
```

A map that is taken is not read again; one never taken places nothing.

An element with a place is pinned. The places are measured from the plate's own middle; step 5 says where the plate stands.

**5. Where each group's point stands.** The body is divided into `K` parts. Without a plate the parts are the groups, part `g` group `g`. With a plate: a group whose centre is pinned stands over the plate; the groups that do not are parts `0, 1, ...` in rank order, and the plate is the last part, `K - 1`. A body node is in the plate's part when it is pinned or its group stands over the plate, else in its group's part.

*The counts.* `size(p)` is the number of body nodes in part `p`; the plate's part also counts every pinned node outside the body. `link(p, q)`, for two different parts, is the number of pairs with both ends in the body, one in `p` and one in `q`. `opp(p, q)` is the number of edges (every edge as the graph lists it, one listed twice counted twice) whose `field` is `rivals`, `adversaries`, `rival` or `antagonist`, with both ends in the body, one in `p` and one in `q`, whichever of the two is the source.

*The directions.* With one part there is none to choose. Otherwise two parts are the ends:
- when any `opp` is over 0: the two parts `p < q` (by part number) with the greatest `opp(p, q)`; among equals the greatest `size(p) + size(q)`; then the lowest `p`; then the lowest `q`;
- otherwise: take the four parts of greatest `size` (all of them when `K` is under 4; among equal sizes the lower part first), and read their pairs `p < q`, by part number and not by size, in rising order of `p`, then `q`. The first pair read stands until a later pair `(p, q)` has `link(p, q) * size(b0) * size(b1) < link(b0, b1) * size(p) * size(q)`, where `(b0, b1)` is the pair standing; that pair then stands. These are whole numbers, compared exactly. For a graph of fewer than 27,000 nodes each product is under 2^53, so a tool whose numbers are doubles holds it exactly. Past that, this page promises nothing for this comparison.

Of the two ends the lower part is the first end. The first end takes direction 0 and the second direction `K - 1`. The other parts, by `size`, greatest first (among equals the lower part first), each take the free direction `s` of least cost, the lowest `s` among equal costs:

```
cost(s) = the sum, over the parts placed so far in the order they were placed (the first end, the second end, then each as it was placed), starting from 0, of
          (link(p, h) - 4 * opp(p, h)) * length(dir(K, s) - dir(K, t))        h a placed part, t the direction it took
```

*The radii.* `root(v)`, a cube root: 0 when `v` is not over 0; else start from `x = sqrt(v)`, or 1 when that is under 1, and forty times `x = (2 * x + v / (x * x)) / 3`. A group's part has the radius `REST * LOBE * root(size(p))`. With a plate, `half` is the greatest `sqrt(x * x + y * y)` over every place of step 4, and the plate's part has the radius `half * CLEAR`. Each group also has `lobe(g) = REST * LOBE * root(the number of body nodes in group g)`, which differs from its part's radius when some of the group are pinned.

*The packing.* With one part its point is `(0, 0, 0)` (with held points, its fixed point when H3 fixes it). Otherwise, with `r` the radii, `sum` the total of all the radii, added in part order from 0, and `total` the sum of `link` over all pairs of parts (1 when that is 0):

```
P[p] = dir of part p * sum                                    each axis
PACK_STEPS times:
    D[p] = (0, 0, 0) for every part
    for each pair p < q, in rising order of p, then q:
        d    = P[p] - P[q]                                    each axis
        dist = max(length(d), 0.000001)
        f    = dist - GAP * (r[p] + r[q])
        when f > 0:  f = f * ((0.02 + 0.5 * link(p, q) / total) * w)      w is 0.25 when opp(p, q) is over 0, else 1
        u    = d / dist * f * 0.5                             each axis
        D[p] = D[p] - u
        D[q] = D[q] + u
    P[p] = P[p] + D[p] * 0.5                                  every part, each axis
```

Then the mean of the `P` (x, y and z each added in part order from 0, divided by `K`) is subtracted from every `P[p]`.

*The points.* Without a plate, group `g`'s point `cpt(g)` is `P[g]`. With a plate: the plate's point is `P[K - 1]`, and a pinned node stands at the plate's point plus its place, axis by axis. A group that does not stand over the plate has the point of its part. A group that does has its centre's standing place, lifted: `(x + 0, y + 0, z + (lobe(g) + REST * 6))`.

**6. What the steps are fed.** The body's nodes in the one order are the movers `0, 1, ...`. For each:
- its anchor: where it stands on the plate when it is pinned, else its group's point;
- fixed: when it is a centre or pinned;
- its pull: `HOLD`.

The links are the pairs with both ends in the body, as `(a, b)` by mover with `a < b`, ordered by `a`, then `b`. A link's weight `w` is `PLATE` when either end is pinned; else 1 when its two ends are in one group; else `CROSS`.

**7. The start.** A fixed mover starts at its anchor. For each group, let `free` be the number of its movers that are not fixed and `ball = REST * LOBE * root(free)`. Each of those movers has its own generator, the one of `by-kind`'s rule 4, started not at 7 but at `h`, a number worked out from the mover's id (not its place among the movers):

```
h = 2166136261
for each byte b of the id's UTF-8 form:  h = ((h xor b) * 16777619) mod 4294967296
```

The product is of two whole numbers under 2^32 and is taken exactly before the `mod` (it does not fit a double). The first two draws are passed over. Then, up to 64 times: `r1 = 2 * draw() - 1`, `r2 = 2 * draw() - 1`, `r3 = 2 * draw() - 1`, and the first try with `r1 * r1 + r2 * r2 + r3 * r3 <= 1` gives `(x, y, z) = (r1, r2, r3)`; when none of the 64 does, `(0, 0, 0)` (no id is known that reaches this, so no case can hold it). The mover starts at `anchor + (0 + x * ball)`, and so for y and z.

**8. The steps.** With `R = REST`, `CUT = CUTOFF * R`, and for each mover `scale = 1 / max(1, wsum / 4)`, where `wsum` is the weights of its links added in the links' order from 0. For `step` from 0 to `STEPS - 1`:

*The cells.* With `x0`, `y0`, `z0` the least x, y and z over all movers, and `x1`, `y1`, `z1` the greatest: `ny = floor((y1 - y0) / CUT) + 1`, `nz = floor((z1 - z0) / CUT) + 1`, and likewise `nx`. A mover is in the cell `(floor((x - x0) / CUT), floor((y - y0) / CUT), floor((z - z0) / CUT))`. Each cell lists its movers in rising order.

*The push.* Every `push` starts the step at `(0, 0, 0)`. For each cell `(cx, cy, cz)` that holds a mover, in rising order of `cx`, then `cy`, then `cz`, and for each of these fourteen cells in this order, when it lies inside the grid and holds a mover:

```
(cx, cy, cz)        (cx, cy, cz+1)
(cx, cy+1, cz-1)    (cx, cy+1, cz)    (cx, cy+1, cz+1)
(cx+1, cy-1, cz-1)  (cx+1, cy-1, cz)  (cx+1, cy-1, cz+1)
(cx+1, cy, cz-1)    (cx+1, cy, cz)    (cx+1, cy, cz+1)
(cx+1, cy+1, cz-1)  (cx+1, cy+1, cz)  (cx+1, cy+1, cz+1)
```

for each mover `i` of the first cell in its order, and each mover `j` of the other cell in its order (in the cell itself: only the movers listed after `i`):

```
u  = p[i] - p[j]                                  each axis
d2 = u.x * u.x + u.y * u.y + u.z * u.z
when d2 > CUT * CUT: pass the pair over
d  = max(sqrt(d2), 0.000001)
f  = ((R * R) / d - R / 3) / d
push[i] = push[i] + u * f                         each axis
push[j] = push[j] - u * f
```

*The links.* Every `pull` starts the step at `(0, 0, 0)`. For each link `(a, b)` in order, with its weight `w`:

```
u = p[a] - p[b]                                   each axis
d = max(length(u), 0.000001)
f = ((d - R) * 0.5 * w) / d
pull[b] = pull[b] + u * f
pull[a] = pull[a] - u * f
```

*The move.* With `cap = CAP0 * R * (1 - step / STEPS) + R / 20`, for each mover in order: a fixed mover stands at its anchor. Any other, with `hold` its pull of step 6:

```
v   = push + pull * scale + (anchor - p) * hold   each axis
len = max(length(v), 0.000000001)
shrink = min(1, cap / len)
p   = p + v * shrink                              each axis
```

**9. What is placed after the steps.**

*The body.* Each body node stands where the steps left it. It is placed `centre` when it is its group's centre, else `with`.

*The middle.* The mean of the body's points: x, y and z each added over the body in the one order from 0, divided by the body's size.

*The skin* of group `g`: over its body nodes that are not pinned, its centre among them when it is not pinned, the length of `point - cpt(g)`; put the `m` values in rising order, `a[0]` to `a[m - 1]`. With none the skin is 0. Else `vi = (m - 1) * 0.9`; when `vi >= m - 1`, `lo = hi = m - 1`, else `lo = floor(vi)` and `hi = lo + 1`; `t = vi - lo`; `d = a[hi] - a[lo]`; the skin is `a[hi] - d * (1 - t)` when `t >= 0.5`, else `a[lo] + d * t`.

*Outward*, for a point `p` and a group `g`: `u = p - cpt(g)`, divided by its length when the length is over 0.000001, else `(0, 0, 0)`. `o = cpt(g) - the middle`, divided by its length when that is over 0.000001, else `(0, 0, 1)`. `u = u + 0.75 * o`, and the answer is `u` divided by its length.

*What hangs.* For each body node `c` that is some node's cut, in the one order, with `g` its group: `u = outward(c's point, g)`; `t = u × (0, 0, 1)`, and when `length(t) < 0.001`, `t = u × (1, 0, 0)`; `t = t / length(t)`; `w = u × t`. (`a × b = (a.y * b.z - a.z * b.y, a.z * b.x - a.x * b.z, a.x * b.y - a.y * b.x)`.) The nodes that hang through `c`, by depth, then by the one order; the node at place `j` of that list, counted from 0, at its depth `d`:

```
ang = GOLD * j
fan = REST * 0.5 * sqrt(j)
point = cpt(g) + u * (skin(g) + REST * d) + (t * cos(ang) + w * sin(ang)) * fan       each axis, when c is not pinned
point = (c.x + cos(ang) * fan * 0.5, c.y + sin(ang) * fan * 0.5, c.z + REST * d)     when c is pinned; c its standing place
```

A node at depth 1 whose degree is 1 is placed `link`; every other hanging node `arm`. A pinned node that hangs has its place `j` in the list like any other, and then stands at its Pin (the map, below).

*Off the main piece.* No rule of a run places a node that is `off` and not pinned: step 10 places it by its own piece's run, or hands it back.

*The map.* Last, every pinned node stands at its standing place and is placed `map`, whatever a rule above gave it: a pinned node may be in the body, hang, or be `off`.

**10. The pieces.** The pieces are step 2's: two nodes are in one piece when a path of pairs joins them, a node in no pair is a piece of one, and the main piece is the one step 2 picks. A node is pinned when step 4 gives it a place.

*The main run.* Steps 1 to 9 and the held points' rules, run on the whole graph, with the world's Maps and Pins, with `heldUnit` as handed, and with the points of `held` that belong to the main piece's nodes, when the main piece holds a pair, or to a node step 4 places (H1 and H4 read those). Any other held point is held by its node's piece's run (a pinned node there is held at its Pin), or, when the node is a piece of one and is not pinned, by no run. The main run is made once the pieces are found, before any piece's run, and tests the box of what it holds (Held points, Refused). From its answer the method takes every node of the main piece when the main piece holds a pair, and every pinned node wherever it is, each with its point, `how`, `group`, `part` and `held`. When the main piece is a single node, no node holds a pair, and only the pinned nodes are taken.

*A piece's run.* Each other piece that holds a pair is laid out by a run of its own: steps 1 to 9 and the held points' rules on its nodes, in the order they were handed in, and the edges with both ends among them, in the order they were handed in, with no Maps and Pins (so no plate) and with `heldUnit` as handed. Its `held` is, for each of its nodes that is pinned, the point the main run's answer gives that node, and for each other node its point in `held`, where `held` has one. That run tests the box of what it holds, its Pins' points too (Held points, Refused), after the main run, the pieces' runs in step 11's order. In that run the piece is the main piece, and no node is `off`.

*Where it stands.* A piece that has a pinned node, or a node with a point in `held`, stands where its run put it: it is laid out round those points and not moved. Every other piece that holds a pair is a ring piece, and step 11 moves it.

*Its words.* A node of a piece that is not pinned takes the point, `how`, `group`, `part` and `held` its piece's run gives it, the point moved by step 11 when the piece is a ring piece. In a piece, `how`, `group` and `part` mean what they mean in the main shape. A pinned node outside the main piece is taken from the main run, with its point there, which is the point its piece's run held it at, and with the main run's words: `how` `map`, `group` null, `part` `map`, `held` false. One case differs: a pinned node that its piece's run makes a centre (steps 1 to 3 do not read what is held, so a held node can be a centre) answers `how` `map`, `group` its own id and `part` null, as a pinned centre of the main shape does. So a piece's `group` can name a node whose `how` is `map`.

**11. The ring.** It sets the ring pieces of step 10 beside the main shape.

*The main shape.* `M` is the mean of the points of the nodes taken from the main run (x, y and z each added in the one order from 0, divided by their count), and `(0, 0, 0)` when none is taken. `Rmain` is the greatest length of `point - M` over those nodes and over every node of a piece that is not moved, at its point; 0 when there is none.

*Each ring piece* `p`: `c(p)` is the mean of its run's points (x, y and z each added in the one order from 0, divided by its number of nodes), and `r(p)` the greatest length of `point - c(p)` over them.

*The order.* Every piece other than the main one that holds a pair, by its number of nodes, most first; among equals, the piece that holds the lower node first. It is read from the graph alone, and the ring pieces are taken in it. `rmax` is the greatest `r(p)` over the ring pieces.

*The rings.* Ring 0 has the radius `R = Rmain + RING_GAP + rmax`. Walk the ring pieces in order; each ring starts with `sum = 0`. For a piece `p`:

```
th = 2 * asin((r(p) + RING_GAP / 2) / R)
```

The piece joins the ring when it is the ring's first, or when `sum + th <= 2 * PI - FIT`; then `sum = sum + th`. Otherwise the ring is closed, the next is opened with `R = R + 2 * rmax + RING_GAP` and `sum = 0`, `th` is worked out again with that `R`, the piece is its first, and `sum = th`. The arcsine's argument is under 1, since `R` is never under `rmax + RING_GAP`.

*The places.* On each ring, with `count` its pieces and `sum` their `th` added in their order from 0:

```
share = (2 * PI - sum) / count
```

Then, starting from `a = 0`, for each piece of the ring in order, with `c = c(p)`:

```
phi = a + th / 2
a   = a + (th + share)
T   = (M.x + R * cos(phi) - c.x, M.y + R * sin(phi) - c.y, M.z - c.z)
```

and each point of the piece's run becomes `(x + T.x, y + T.y, z + T.z)`. The angles are measured from +x toward +y, the first piece of a ring starting at +x; the angle the ring leaves over is shared equally, one `share` after each piece; and every ring lies in the plane `z = M.z`, beside the main shape and never under it.

*What it keeps apart.* A ring piece's nodes lie within `r(p)` of its centre. Ring 0 stands `rmax + RING_GAP` beyond `Rmain`, neighbours on one ring stand at least `r(p) + r(q) + RING_GAP` apart, and each next ring `2 * rmax + RING_GAP` further out. So no node of a ring piece stands nearer than `RING_GAP` to a node placed before the ring, or to a node of another ring piece, to within the 6e-8 promised for their points (the nearest can stand at exactly `RING_GAP`).

*The one test promised less.* Because `th` comes from an arcsine, and `M`, `Rmain` and `r(p)` read points placed with a cosine and a sine, two builds may hold a fit test's `sum + th` a little apart. A verdict whose sum lies within `FIT_BAND` of `2 * PI - FIT` is promised either ring, and the answer is the one that follows from either outcome, everything else as this step says; every other verdict is the same in every build. When every ring piece has `r(p) = Rmain`, each `th` on ring 0 is `PI / 3` in real numbers: five pieces join ring 0, and a sixth opens ring 1.

**12. The answer.** One row per placed node (the nodes taken from the main run, and the nodes of every other piece that holds a pair), in the order the nodes were handed in (not the one order), and the method's word, `by-links-3d`:
- its `id` and its point `x, y, z`;
- `how`: `centre`, `with`, `arm`, `link` or `map`;
- `group`: for a node placed `centre` or `with`, and for a pinned node that is its group's centre (outside the main piece, a centre of its piece's run, step 10), the `id` of that centre; for every other node null;
- `part`: null where `group` is an id; else `map` for a pinned node, `one-link` for an `arm` or a `link`. Step 5's parts and step 3's ranks are numbers inside a run; the answer's `part` and `group` are its words, and carry neither;
- `held`: true for a kept node (H5) of the run that placed it, which stands at its held point; false for every other node, a pinned node that stands at its held point too (H4), and false for every node when nothing is held.

And `centres`: the main run's centres in rank order, save one that is not placed (the main piece a single node that is not pinned), then each other piece's centres in its run's rank order, the pieces in step 11's order, a piece that is not moved among them though it stands on no ring.

And `unplaced`: the ids of the nodes not placed, in the one order: every node that is a piece of one and is not pinned, a held one too. A held point keeps a node where this method once placed it, and the method places no node that is linked to no other and pinned on no map, so a held point alone places none, and no run holds it (step 10).

`how`, `group`, `part`, `centres` and `unplaced` come from steps 2 to 4 alone, of the main run and of each piece's run, with step 10's pieces and step 11's order, so a tool that wants only the groups runs those steps and no force step.

### Held points

A world changes after it was laid out. `held` hands back points an earlier answer gave, element id to `[x, y, z]`, one point per id: points in the method's own frame, as the method answered them, rounded to `heldUnit`, so that those elements stand where they stood and the rest is laid out round them. `held` absent or null: nothing is held. `heldUnit` is the step the held points were rounded to (points rounded to whole numbers: 1); absent or null it is 0.

**Refused**, each by its own code so a tool can say why, and a refused call answers nothing. Before anything else is read: `held` that is no mapping of ids to values, a list or an array among them (`held-not-object`); a value that is not exactly three finite numbers, every value handed in read, also under an id that is no node (`held-not-point`); a `heldUnit` that is given and is not a finite number from 0 to `LINE`, both ends allowed, whether or not anything is held (`held-unit`). A boolean is no number, in a held value and in `heldUnit` alike. The first of these that applies, in this order, is the refusal. Then each run tests the box of the held points it holds (step 10), the main run first and then each piece's run in step 11's order: when their greatest and least x, or y, or z, lie more than `HELD_BOX * REST` apart, the call is refused (`held-box`). A piece's run counts its Pins' points, which it holds. The main run counts the held values of its pinned nodes, and not the places step 4 gives them.

A held id that is no node is then passed over, and so is that of a node that is a piece of one and is not pinned: no run holds it (step 10). A run that holds no held point runs as written above. Otherwise the rules below apply in that run, and the structure, the centres and the groups are still read from today's graph (steps 1 to 3 do not change).

**H1. The frame**, where the plate stood when the held points were answered. Only when step 4 gives a plate. The candidates are the held nodes that have a place on the first map (step 4, its places), in the one order, each with its held point `h` and that map place `m`. `band = 3 * heldUnit + SNAP`.

For each candidate `a` in order: its partners are the candidates `b` whose `h.z` differs from `a`'s by `heldUnit + SNAP` or less and whose map place is not `a`'s (not both x and y equal), ordered by `sqrt(mx * mx + my * my)` of `m(b) - m(a)`, greatest first, among equals in the one order. For each partner in that order: when `h(b)` and `h(a)` have the same x and the same y, try the next. Else:

```
s = sqrt(hx * hx + hy * hy) / sqrt(mx * mx + my * my)       hx, hy of h(b) - h(a); mx, my of m(b) - m(a)
F = (h(a).x - s * m(a).x, h(a).y - s * m(a).y, h(a).z)
```

A candidate `c` agrees when `h(c).x - (F.x + s * m(c).x)`, `h(c).y - (F.y + s * m(c).y)` and `h(c).z - F.z` each lie from `-band` to `band`, both ends allowed. Every candidate is tested, `a` and `b` too. When `FRAME_AGREE` candidates or more agree, `s` and `F` are the frame and the search ends.

With a frame, step 4 is read again with `scale = s` in place of its own (the small plates keep their own `sc`), and in step 5 the plate's part is fixed at `F`. With none, step 4 stands and the plate is packed as any part.

**H2. Each group's case**, the first that applies:
1. its centre is pinned: it stands over the plate, as in step 5;
2. its centre is held: the group's point is the centre's held point, and its part is fixed there;
3. it has held members (body nodes of the group that are held and not pinned): the group's point is their mean, x, y and z each added in the one order from 0 and divided by their count, and its part is fixed there;
4. none of these: the packing places it.

**H3. The packing with fixed parts.** The directions and the radii are as in step 5. When no part is fixed, the packing is step 5's. Otherwise a fixed part stands at its point throughout. With `O` the mean of the fixed parts' points (each axis added in part order from 0, divided by their number), a part that is not fixed starts at `O + dir * sum`, axis by axis. When every part is fixed there are no steps. The steps run over the same pairs in the same order, a fixed part's `D` is worked out and never applied, and the mean is not subtracted at the end.

**H4. The snap.** After the pinned nodes have their standing places and before any group reads its centre's: a held pinned node whose standing place differs from its held point by `band` or less on each axis stands at the held point.

**H5. The steps' feed.** A held node that is not pinned is *kept*. A kept body node is fixed, and its anchor is its held point. A centre that is neither pinned nor kept is not fixed: it starts in its group's ball and moves as any member (and is counted in step 7's `free`). After the body's movers come the kept nodes outside the body, in the one order: each fixed at its held point, with no link, pull 0 and no group. They push and are not moved. In the main run (step 10) they are of the main piece only, since a node of another piece is held by its own piece's run.

**H6. After the steps.** Every length below is compared with `LINE` by "under". A point is *near* when some kept node's held point lies under `LINE` from it.

*What hangs*, for a cut `c` and its list. First the claims: for each kept node of the list, in the list's order, at its own depth `d`, the fan's axis point is `cpt(g) + u * (skin(g) + REST * d)`, or `c`'s standing place plus `(0, 0, REST * d)` when `c` is pinned; `bound` is the length from the held point to the axis point, plus `LINE`, plus `REST`. For `j = 0, 1, ...` while the place's `fan` (`fan * 0.5` when `c` is pinned) is under `bound`: place `j` is claimed when its point at depth `d` lies under `LINE` from the held point. A kept node holds only the places its claims name, and not its own place in the list. Then each node of the list that is not kept, a pinned one too, in the list's order, takes the lowest place `j` that is not claimed, not taken by an earlier node of this list, and whose point at the node's own depth is not near. A pinned node so takes a place, which no later node of the list can have, and then stands at its Pin.

*Kept.* Then every kept node stands at its held point, with the `how` its rule gave it, and last every pinned node at its standing place: a pinned node stands at its Pin whatever is held for it, and its `held` is false.

Because step 9's places come from a cosine and a sine, one test is promised less. Each claim and each "near" compares a length `l`, from a kept node's held point to a place, with `LINE`. When `l` is from `LINE - 1e-6` to `LINE + 1e-6`, that one test may answer either way, and the answer is the one that follows from either outcome, everything else as this section says. Outside that band no two builds differ: their places agree to within 6e-8 on each of x, y and z, so their lengths to one held point agree to within 1.1e-7, and a build that finds `l` outside the band on its own places knows every other build's `l` is on the same side of `LINE`.

### A saved `by-links-3d` Map

A tool that saves this layout as a Map writes `by-links-3d` as the `method` of its `x_layout` (The mark, below). How the answer's points become the Map's Pins, and the way back from its Pins to `held`, is not ruled here (Not ruled here, below). A Map another tool saved does not say whether its Pins are the method's points, so no rule here lets a tool hand them back as `held`.

The Map keeps points and nothing else of the answer: the groups are read again from the world (steps 2 to 4) by a tool that draws them. It writes no ground (the map-space profile's rule 9): which Map was the plate is this method's own step 4 and rules no other tool's choice of a Map for the world's space; a tool that draws the first map's picture under the plate places it by the pinned elements' points, and reads the first map from the world as it is then, which may have changed since the save.

The `z` of a Pin on such a Map is read as the map-space reading answers it: a Pin with no whole `z` reads as z 0. The method reads no Pin's `z`.

The method does not read `x_hand`. A Pin placed by hand (the map-space profile's rule 10) and handed back as `held` is a held point like any other, and one whose element is pinned on the world's own Map stands at its plate place (H6). Rule 10 binds the tool that lays a saved Map out again.

`unplaced` for such a Map is this page's reading (below), with `placed` the element ids of the Map's Pins as the map-space reading answers them. Such a Map holds no Pin for a node the answer it was made from left `unplaced` (step 12), and none for an element the world gained since; the reading answers both, every node whose `id` is not in `placed`. For a Map that holds a Pin for every node an answer placed, and no other, it is that answer's own `unplaced`.

**Promised nothing**: an id that is not well-formed Unicode (a surrogate that is half of no pair), wherever the method reads one: in a node, an edge, a Map, a Map's `location`, a Pin, a held key or a member of `placed`.

## The mark, and a world that changes

**The mark.** A tool that saves one of these layouts as a Map writes, as the `method` of the Map's `x_layout` (the map-space profile's rule 8), the word of the method that made it: `by-kind` for a Map laid out by `by-kind`, `around` for one laid out by `around`, `by-links-3d` for one laid out by `by-links-3d`. A Map that already holds Pins when it is given a method, first or new, is the case the map-space profile's rule 10 orders; a layout map laid out again by its own method is not that case.

The method word says nothing of what the Map was laid out from: the graph; for `around` the focus and `steps`; for `by-links-3d` the world's Maps and Pins and what was held (Not ruled here, below).

**A method's word is its version.** `by-kind`, `around` and `by-links-3d` mean the methods written on this page and nothing else, for as long as the words are read. A change that moves any point is a new method with a new word and its own section here, never a silent change to an old picture; a tool that does not know the new word reads its Map as rule 8 says for any word it does not know, and draws the Pins as they stand. There is no version number in the mark.

**A world that changes.** Each method gives the same points for the same input. A graph that gains or loses one element may give different points throughout: in `by-kind` every later draw of the generator moves with it, and in `by-links-3d`, whose draws are seeded by each element's own id, the body, the groups and the force steps may move with it; `by-links-3d` also moves with the world's Maps and Pins. Its `held` hands back the points an earlier answer gave, so that those elements stand where they stood (its section, Held points). Laying a saved layout map out again, or placing on it what it does not place, is a write like any other and never a side effect of reading or drawing the Map (the map-space profile's rule 8). A tool that shows the default unsaved may show different points after the world changes, and that is not a fault.

**Not ruled here.** How a frame's points become a saved Map's whole-number Pins, for each of the three methods, and the way back from a saved Map's Pins to `by-links-3d`'s `held`; sizes, colours, labels and the camera; what a tool does with a graph too large for it. For a graph that is not one (a node with no id, a type outside the 22, an id twice, an edge whose `field` or `index` is null) this page promises nothing: a tool may refuse it or draw it, and two tools may then differ. A tool that refuses names what it refused.

Also not ruled here: **what a saved Map was laid out from**, which is its graph (the whole world as a reader is served it, or a lens's graph), for `around` its focus and `steps`, and for `by-links-3d` the world's Maps and Pins and what was held. The method word says none of it. It comes with the first tool that saves such a Map; until then a tool may keep it among the method's own settings, and no other tool has a rule to read it by. And how `by-kind` or `around` lays a Map out again around Pins placed by hand (the map-space profile's rule 10), or places only the elements a Map does not place; `by-links-3d` lays a Map out again from `held`, and reads no `x_hand` (its section, A saved `by-links-3d` Map).

## `unplaced`: what a saved Map does not place

A world that has grown since a layout was saved holds elements the Map has no Pin for. `unplaced` is the one reading of which they are, so every tool that tells how many, or lists them, says the same from the same graph and the same `placed`. Whether a tool tells it is the tool's.

It takes the graph and `placed`, the ids of the elements the Map's Pins stand for, and for `around` also the focus and `steps`: what the method takes to know which nodes it places. `by-links-3d`'s reading takes none of its Maps, Pins and `held`. It answers the ids of the nodes the reading counts that are not in `placed`, in the one order:

- `by-kind` places every node of the graph, so the answer is every node whose `id` is not in `placed`;
- `around` places the focus and every node within its steps, so the answer is those of them whose `id` is not in `placed`;
- `by-links-3d` counts every node of the graph, also one it would not place, so the answer is every node whose `id` is not in `placed`; for the Map an answer makes, that is the answer's own `unplaced` (its step 12).

`placed` is a list or a set. A member that is not a non-empty string names no element (the number 7 is not the id "7"), and an id in `placed` that the method would not place (no node of the graph, or for `around` a node further out than its steps) is no part of the answer. The answer does not say why an element has no Pin: one a person took off the Map and one the world gained since read the same.

**Which Pins make `placed`.** The element ids of the Map's Pins as the map-space reading answers them (its `pins`, the map-space profile's rule 5). A Pin with no whole `x` or `y` is not among them, so its element is not placed; of two rows with one Pin id the last is read. That step, from Pin rows to `placed`, is held by the map-space profile's fixture; no case here can hold it, since `unplaced` takes `placed` as it is given.

**Which graph.** `unplaced` answers for the graph it is given and promises no more than this: the same graph and the same `placed` give the same answer in every tool. Which graph a saved Map was laid out from the method word does not say (Not ruled here, above), so the count is of the graph the tool counts over, which is the tool's own choice, for the reader it is served for: an owner and a visitor may get different answers. Every node of the graph counts, whatever its type. A graph that holds the Map itself, its Pins or a Marker as nodes counts them, so a tool that counts leaves those three types out of the graph it hands in: Map, Pin and Marker. A Zone stays: it is a node like any other in the lens profile's graph: `by-kind` places it, and `by-links-3d` places it as it places any other node. For an `around` Map only a tool that holds the focus and `steps` can make this reading.

## The fixture

`layout.fixture.json` holds everything `by-kind` and `around` read besides the graph: `anchors` (the table of rule 3, keyed by `k` as a string), `groups` and `group_order` (the kinds' order), then three suites. Three fields are about the file and feed no method: `profile` names the profile, `profile_page` its page (this one), and `compare` says in words how each suite's `want` is compared, as written out here.

- `cases`, for `by-kind`: each is a `graph` and a `want`, one `[x, y]` per node in the graph's own node order. A reader's points equal them exactly, every x and y, with no tolerance.
- `around`: each is a `graph`, a `focus`, `steps` and a `want`, one `[id, depth, x, y]` per answered node in the graph's node order. The ids and depths equal them exactly; x and y to within 1e-12.
- `unplaced`: each is a `method`, a `graph`, `placed` and a `want` (and for `around` a `focus` and `steps`); the `want` is the list of ids, equal exactly and in its order.

The `by-kind` cases cover: no element, one, two linked, one kind only, a self-link (it pulls nothing), all 22 kinds, a cell holding more than 12, two public worlds as a visitor is served them, a graph of 400 nodes, one past 2,000 (the half-step branch), one world handed in shuffled (the answer follows the handed order; the points do not change), an `index` of 10 or more where a string order would differ, edges with no `field` or no `index`, an edge to an id that is no node, and the same link twice. The `around` cases cover: a focus alone, names ordered by code point where a locale would differ and where UTF-16 units would, a null name and an absent one, kinds in group order, a hub past one ring, two steps and one step of the same graph, a self-link on the focus, which reaches nothing new, and two steps with more than 60 nodes at depth 1. The `unplaced` cases cover, for each of the two methods: a Map that places all, one element more in the world, a Pin gone, a placed id the method would not place, and a `placed` that holds null, the empty string, the number 7 and every other id, beside a node whose id is "7" linked to the first node handed (for `by-kind`) or to the focus (for `around`), so that the answer is `["7"]` (`by-kind-a-member-of-placed-that-is-no-id`, `around-a-member-of-placed-that-is-no-id`, the last two cases of the suite); and seven more: two ids on either side of U+FFFF (code point order, where UTF-16 units reverse them); an edge that points at the focus (reach runs both ways along a link); a self-link on the focus (its id once); an `around` answer of four ids whose id order is neither the handed order, the order they were found in, nor kind then name; a `by-kind` node with no link (it is placed, so it can be unplaced); a path through an id that is no node (it reaches nothing); and one graph that holds a Zone, a Pin, a Map and a Marker as nodes, where the reading drops none of them.

A port proves itself by running every case, and by one planted error, so that a pass is known to mean something: with the y of `anchors["19"][1]` moved one unit in its last place, either way, both cases of the world of 181 nodes and 19 kinds (`moppetopia` and `moppetopia-handed-shuffled`) turn red in every point, and every other case stays green (an anchor for `k` kinds reaches only a graph with `k` kinds). For `by-links-3d` the planted error is the one its directions table's paragraph names.

`layout-by-links-3d.fixture.json` holds `by-links-3d`'s cases, `rest`, 60, and step 11's three numbers, `ring_gap`, 108 (`RING_GAP`), `fit`, `FIT`, and `fit_band`, `FIT_BAND`. The directions table is its own file beside it, `layout-by-links-3d.directions.json`, which the fixture names by its sha256 in `table_sha256`. The other fields are about the file and feed no method: `fixture` and `method` name it, and `call`, `rows`, `table`, `held`, `points`, `unplaced_order` and `compare` say in words how a case is run and how its `want` is compared, as written out here.

- `cases`: each is a `name`, a `why` (the steps of this section the case holds), an `input`, `steps` and a `want`. `steps` is 300 in every case: the constant `STEPS`, no input of the method. The `input` is the graph's `nodes` and `edges`; `rows`, the world's Map and Pin elements as served, and in a case that measures a Map its Markers and Zones too (the keys the map-space profile's reading and its layout reading read, and a Map's `name`, which neither reads), or null; the method passes no Marker or Zone over, and reads them only through the map-space reading's measure of a Map (Which graph, above); and `held` and `heldUnit`, handed only where the input has the key (a null is handed as null). The `want` is the answer, `ids` of the placed elements in the handed order, `points` (x, y and z of each element in `ids` order, three numbers an element, in one flat list), `how`, `group`, `part`, `centres`, `held` and `unplaced`; or, for a refusal, `{refused: code}`, the code the call refuses with, before anything runs or, for `held-box`, in the run whose box it is, (`compare` names the error class each code comes with in JavaScript). No `want` holds the method's word: every answer that is not a refusal carries `method`, `by-links-3d` (step 12), and a reader compares it exactly on every case that answers. A ring piece is found from the graph and the `want` alone: a piece other than the main one (step 10), of two nodes or more, none of them placed `map` and none of them in the input's `held`. Every `ids`, `how`, `group`, `part`, `held`, `centres` and `unplaced` entry equals the `want` exactly, and so does each of x, y and z of an element placed `centre`, `with` or `map` that is not of a ring piece: the same double, a zero compared by its value whatever its sign, since the file's JSON holds no -0. An element whose `held` is true stands exactly at its point in the input's `held`. Each of x, y and z of an element placed `arm` or `link` whose `held` is false, and of every element of a ring piece, lies within 6e-8 of the `want`. No case puts the length of a claim or a near test inside `LINE`'s band (H6), or a fit test's sum within `FIT_BAND` of `2 * PI - FIT` (step 11), where the page allows either outcome and one stored `want` holds only one of them; such a case would not be made, so on every case each of those tests has one answer, and a port compares its answer with the one `want`.
- `unplaced`: each is a `name`, a `why`, a `graph`, `placed` and a `want`, the list of ids, equal exactly and in its order.

The `by-links-3d` cases cover: no element, two linked, a self-link; a body with no arm, and an arm three links long; two largest blocks of one size, and the same with the body closed first; a small group that gives its centre up, two small groups at once, a hub linked to a third of the rest, thirteen hubs over the floor and twelve centres, path counts past 2^52; the largest group read again twice, and a group of exactly half the body, read again not at all; one `rivals` link, one way, and one to a pinned element outside the body; two pairs of parts tied on opposing links; five parts, with the ends among the four largest; an opposing link weighed four times; ids on either side of U+FFFF; a link to an id that is no node; a Map that holds two, and one that holds three; a small plate over a place, one taken on the second pass, one of twenty, and a small Map that holds two; two Maps tied for first; an element pinned twice on one map; a pinned element outside the body, counted in the plate's part; a plate with no link to the body; a saved layout Map beside a real Map, as the only Map, and over a place on the plate, and the neighbours of the layout mark; a Pin with one link key, Pins that are no point, two Pin rows with one id, a Pin row whose id is empty, a Pin whose map is a number, and a Pin naming an id that is no node; a Map with no width or height, a Marker measuring a Map, and a Marker of a zone that is not served; a first Map with a width of 0, a height of 0, a width under 0, and a width and a height under 0; a small Map with a height of 0, and with a width and a height under 0; a Map whose location is no id; a Map id served twice, the later row a layout map, and the earlier; two whole worlds, one of them by its graph alone. With held points: the whole answer handed back; a leaf added to a held arm; a leaf beside a held leaf under a pinned parent; an element added to the body; a Pin added on the first map; an earlier answer rounded to whole numbers, with `heldUnit` and with none; two places of the map handed back; a centre not handed back, alone and with three members held; a new centre beside held ones; a link added that joins a piece, and one that changes the centres; `held` null and `heldUnit` null; only an id that is no node, one that widens no box, and no node at all with held points wider than the box; a box exactly 768 rests wide; `heldUnit` exactly `LINE`; one part, and it is fixed; a pinned element that hangs and takes a place; the fan when `u` points straight down; a place passed over because it is near; a partner held at the mirror of its place, and one held at the same x and y; the group's point at the middle of the body; a point 1e-7 from a moving element's start, a linked point the same, and a fixed part 1e-7 from a free part's start. The pieces: one node, and no link at all; two equal pieces; a main and three equal pieces; a star, a star piece and a chain, the chain the wider though it has fewer nodes; a ring closed by `FIT`, five pieces on ring 0 and one on ring 1; three rings; a chain pinned at both ends, and a loop pinned at two places; a piece with two held nodes; a pinned element with no link beside an unpinned one; a held element with no link, which is not placed; `centres` across held and pinned pieces; the largest piece a single node; a pinned centre of its piece; a held answer fed back whole, every point the same; and every case of where a piece stands at once. And fifteen refusals: `held` an array; a held point of two numbers, of four, with a string in it, and with `true` in it (a boolean is no number: `held-not-point`); a bad point under an id that is no node; a box one unit wider than 768 rests, a piece's run whose Pin stands more than 768 rests from its held point, and the first map's nodes held together, in agreement, more than 768 rests from the main piece's other held points (`held-box`); `heldUnit` over `LINE`, a string, `true` (`held-unit`), and under 0 with nothing held; a bad point, a box too wide and a bad `heldUnit` at once, where the first in their order is the refusal; and a box too wide with a bad `heldUnit`, where `held-unit` is, since the box is tested only in the runs. The `unplaced` cases cover: a Map that places all, one element more in the world, a placed id that is no node, members of `placed` that are no id (null, the empty string and the number 7 beside a node whose id is "7"), a node with no link and a node off the main piece, Map, Pin and Marker nodes counted as nodes, ids past U+FFFF, an answer in id order, and the Map an answer makes, whose reading is that answer's own `unplaced`.

**Ruled**: 2026-11-15: the page, one page for both method words, `by-kind` and `around`; a method's word is its version, and the mark carries no version key; a graph that is not one, or a focus that is no node, is promised nothing; how a frame's points become a saved Map's Pins is not ruled here. 2026-11-16, serial 132: the promise is of points and not of a picture, `around`'s to within 1e-12 as an absolute difference on each x and y; the kinds' order is the fixture's groups, never a node's own; `unplaced`, the one reading of which elements a saved layout map does not place, answers for the graph it is given, and `placed` is the element ids of the Map's Pins as the map-space reading answers them; a tool that counts leaves Map, Pin and Marker out of the graph it hands in, and a Zone stays; the method word does not say what a saved Map was laid out from, its graph and for `around` its focus and `steps`, and that is not ruled here; rule 10's order is for a Map given a method, first or new, while it holds Pins, not for a layout map laid out again by its own method; seven of the `unplaced` cases answer wrong readings planted in two outside implementations, which the first eight cases left passing; the page and its fixture published, 17 `by-kind` cases, 10 `around` and 15 `unplaced`. 2026-11-18, serial 137: a third method word, `by-links-3d`, the whole graph in three dimensions by its links, with the world's Maps and Pins as a plate its pinned elements stand on and `held` to keep elements where an earlier answer put them; every piece that holds a pair is laid out by its own links, a piece with a pinned or held element is laid out round those points and not moved, and every other piece stands on a ring beside the main shape; an element linked to no other and pinned on no map is not placed, a held one too, and is listed in `unplaced`; `unplaced` is in id order, by code point, for all three methods; each run tests the box of the held points it holds, the main run counting the held values of its pinned nodes and not the places the plate gives them, and `HELD_BOX` stays 768 rests; a fit test whose sum lies within `FIT_BAND` of its edge is promised either ring, and every other verdict is exact; a member of `placed` that is not a non-empty string names no element, for all three methods (ruled 2026-11-16), with one case for each of the two flat methods; the lists of what `by-kind` and `around` use name every operation their steps use; the method's fixture, 116 cases and 9 `unplaced`, and its directions table published beside the page, and `layout.fixture.json` gains the two `unplaced` cases (17 in all), its `by-kind` and `around` suites unchanged.

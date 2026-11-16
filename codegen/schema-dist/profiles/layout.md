# Convention profile: the default layouts

**What it is.** Two ways to draw a world nobody has laid out, read from its graph alone. `by-kind` lays out a whole graph: each kind of element has its own place round a circle, links draw elements together, and the points come out the same every time. `around` lays out one element and what is linked to it, on rings. They add nothing to the world: no field, nothing stored. Each is a method word for the map-space profile's rule 8, so a Map whose Pins were made by one can say so.

**The promise.** The same graph gives the same points in every tool and every language: `by-kind` to the last bit, `around` to within 1e-12 (an absolute difference, on each x and y). The promise is of points, numbers in a plane, and not of a picture: which way a tool turns y on its screen is the tool's. Where y grows downward, as on a screen, `around`'s angles run clockwise from the top. That is what the fixture beside this page holds, and it is the reason every step below is written in its order. `by-kind` is sensitive: one number changed in its last place moves a large picture visibly, so a tool agrees with the fixture exactly or it is drawing something else.

**The graph.** `{nodes, edges}` as the lens profile's `worldGraph` answers it for the reader. A node is `{id, type, name}`: `type` is the element type's word in lower case (`character`), `name` a string, null or absent (only `around` reads it). An edge is `{source, target, field, index}`, by id; `field` and `index` may be absent. An edge whose `source` or `target` is not a node is passed over.

**The one order.** Before anything else the graph is put in one order, so the order it was handed in changes no point and no member of any answer (two answers below are listed in the handed order, and each says so):
- the nodes by `id`;
- the edges by `source`, then `field` (absent as the empty string), then `index` (absent as 0, by number), then `target`.

Every string is compared by Unicode code point, never by a locale. Below, node `i` means the node at place `i` in this order, counted from 0, and `n` is the number of nodes.

**The kinds' order.** The fixture's `groups` gives each of the 22 types its colour group, and `group_order` puts the four groups in order. A type's rank is its group's place in `group_order`. Kinds are ordered by rank, then by the type word (code point order). The groups are the fixture's and no other: a node's own `family` or colour, where a graph carries one, is not read, and a method's word holds these groups for as long as the word is read.

**Arithmetic.** Every number is an IEEE 754 double. `by-kind` uses addition, subtraction, multiplication, division, square root and floor, and nothing else. Each expression below is evaluated as written: brackets first, multiplication and division before addition and subtraction, and operations of the same rank from left to right; nothing is regrouped, and no two operations are fused into one (a compiler that fuses a multiply and an add must be told not to). `around` also uses cosine, sine and the double nearest pi (`PI`), which is why it is held to a tolerance and `by-kind` is not.

What trips a port, each seen to turn fixture cases red:
- every `/` below divides doubles, also where both sides are whole numbers (`it / steps`, `len / 12`, `q / (c - 1)`);
- `floor` is toward minus infinity, not a cast that drops the fraction (a cell left of or above 0 differs);
- the generator needs unsigned or 64-bit whole numbers: a signed 32-bit one overflows;
- a sum regrouped (`ux * ux + (uy * uy + 0.000001)`) is another sum;
- the anchors are read as exact doubles: every digit the fixture prints, parsed with correct rounding.

## `by-kind`

It takes the graph, and places every node of it.

**1. The small cases.** With no node the answer has no points. With one node its point is 0, 0.

**2. The links.** Walk the edges in the one order. An edge whose two ends are both nodes and not the same node is a link `[a, b]`, the places of its source and its target. A link that appears twice is kept twice.

**3. The anchors.** List the types present among the nodes, in the kinds' order; let `k` be how many. The fixture's `anchors` holds, for each `k` from 1 to 22, `k` points on the unit circle (it is a JSON object, so its keys are the strings `"1"` to `"22"`). The type at place `j` of the list has the anchor `anchors[k][j]`, an `[x, y]`. The table is read, never computed: these numbers are the method's, and a cosine worked out at run time may differ from them in the last place.

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

The two branches are not symmetric (a node beside a crowded cell can be pushed by one of its nodes twice, or not at all). That is the method as it stands; the fixture's `a-crowded-cell` case holds it.

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

## The mark, and a world that changes

**The mark.** A tool that saves one of these layouts as a Map writes, as the `method` of the Map's `x_layout` (the map-space profile's rule 8), the word of the method that made it: `by-kind` for a Map laid out by `by-kind`, `around` for one laid out by `around`. A Map that already holds Pins when it is given a method, first or new, is the case the map-space profile's rule 10 orders; a layout map laid out again by its own method is not that case.

The method word says nothing of what the Map was laid out from: the graph, and for `around` the focus and `steps` (Not ruled here, below).

**A method's word is its version.** `by-kind` and `around` mean the methods written on this page and nothing else, for as long as the words are read. A change that moves any point is a new method with a new word and its own section here, never a silent change to an old picture; a tool that does not know the new word reads its Map as rule 8 says for any word it does not know, and draws the Pins as they stand. There is no version number in the mark.

**A world that changes.** The method gives the same points for the same graph. A graph that gains or loses one element may give different points throughout, since every later draw of the generator moves with it. Laying a saved layout map out again, or placing on it what it does not place, is a write like any other and never a side effect of reading or drawing the Map (the map-space profile's rule 8). A tool that shows the default unsaved may show different points after the world changes, and that is not a fault.

**Not ruled here.** How a frame's points become a saved Map's whole-number Pins; sizes, colours, labels and the camera; what a tool does with a graph too large for it. For a graph that is not one (a node with no id, a type outside the 22, an id twice, an edge whose `field` or `index` is null) this page promises nothing: a tool may refuse it or draw it, and two tools may then differ. A tool that refuses names what it refused.

Also not ruled here: **what a saved Map was laid out from**, which is its graph (the whole world as a reader is served it, or a lens's graph) and for `around` its focus and `steps`. The method word says none of it. It comes with the first tool that saves such a Map; until then a tool may keep it among the method's own settings, and no other tool has a rule to read it by. And how either method lays a Map out again around Pins placed by hand (the map-space profile's rule 10), or places only the elements a Map does not place.

## `unplaced`: what a saved Map does not place

A world that has grown since a layout was saved holds elements the Map has no Pin for. `unplaced` is the one reading of which they are, so every tool that tells how many, or lists them, says the same from the same graph and the same `placed`. Whether a tool tells it is the tool's.

It takes what the method takes (for `by-kind` the graph; for `around` the graph, the focus and `steps`) and `placed`, the ids of the elements the Map's Pins stand for. It answers the ids of the nodes the method would place that are not in `placed`, in the one order:

- `by-kind` places every node of the graph, so the answer is every node whose `id` is not in `placed`;
- `around` places the focus and every node within its steps, so the answer is those of them whose `id` is not in `placed`.

An id in `placed` that the method would not place (no node of the graph, or for `around` a node further out than its steps) is no part of the answer. The answer does not say why an element has no Pin: one a person took off the Map and one the world gained since read the same.

**Which Pins make `placed`.** The element ids of the Map's Pins as the map-space reading answers them (its `pins`, the map-space profile's rule 5). A Pin with no whole `x` or `y` is not among them, so its element is not placed; of two rows with one Pin id the last is read. That step, from Pin rows to `placed`, is held by the map-space profile's fixture; no case here can hold it, since `unplaced` takes `placed` as it is given.

**Which graph.** `unplaced` answers for the graph it is given and promises no more than this: the same graph and the same `placed` give the same answer in every tool. Which graph a saved Map was laid out from the method word does not say (Not ruled here, above), so the count is of the graph the tool counts over, which is the tool's own choice, for the reader it is served for: an owner and a visitor may get different answers. Every node of the graph counts, whatever its type. A graph that holds the Map itself, its Pins or a Marker as nodes counts them, so a tool that counts leaves those three types out of the graph it hands in: Map, Pin and Marker. A Zone stays: it is a node like any other in the lens profile's graph, and `by-kind` places it. For an `around` Map only a tool that holds the focus and `steps` can make this reading.

## The fixture

`layout.fixture.json` holds everything the methods read besides the graph: `anchors` (the table of rule 3, keyed by `k` as a string), `groups` and `group_order` (the kinds' order), then three suites. Three fields are about the file and feed no method: `profile` names the profile, `profile_page` its page (this one), and `compare` says in words how each suite's `want` is compared, as written out here.

- `cases`, for `by-kind`: each is a `graph` and a `want`, one `[x, y]` per node in the graph's own node order. A reader's points equal them exactly, every x and y, with no tolerance.
- `around`: each is a `graph`, a `focus`, `steps` and a `want`, one `[id, depth, x, y]` per answered node in the graph's node order. The ids and depths equal them exactly; x and y to within 1e-12.
- `unplaced`: each is a `method`, a `graph`, `placed` and a `want` (and for `around` a `focus` and `steps`); the `want` is the list of ids, equal exactly and in its order.

The `by-kind` cases cover: no element, one, two linked, one kind only, a self-link (it pulls nothing), all 22 kinds, a cell holding more than 12, two public worlds as a visitor is served them, a graph of 400 nodes, one past 2,000 (the half-step branch), one world handed in shuffled (the answer follows the handed order; the points do not change), an `index` of 10 or more where a string order would differ, edges with no `field` or no `index`, an edge to an id that is no node, and the same link twice. The `around` cases cover: a focus alone, names ordered by code point where a locale would differ and where UTF-16 units would, a null name and an absent one, kinds in group order, a hub past one ring, two steps and one step of the same graph, a self-link on the focus, which reaches nothing new, and two steps with more than 60 nodes at depth 1. The `unplaced` cases cover, for each method: a Map that places all, one element more in the world, a Pin gone, and a placed id the method would not place; and seven more: two ids on either side of U+FFFF (code point order, where UTF-16 units reverse them); an edge that points at the focus (reach runs both ways along a link); a self-link on the focus (its id once); an `around` answer of four ids whose id order is neither the handed order, the order they were found in, nor kind then name; a `by-kind` node with no link (it is placed, so it can be unplaced); a path through an id that is no node (it reaches nothing); and one graph that holds a Zone, a Pin, a Map and a Marker as nodes, where the reading drops none of them.

A port proves itself by running every case, and by one planted error, so that a pass is known to mean something: with the y of `anchors["19"][1]` moved one unit in its last place, either way, both cases of the 181-node world turn red in every point, and every other case stays green (an anchor for `k` kinds reaches only a graph with `k` kinds).

**Ruled**: 2026-11-15: the page, one page for both method words, `by-kind` and `around`; a method's word is its version, and the mark carries no version key; a graph that is not one, or a focus that is no node, is promised nothing; how a frame's points become a saved Map's Pins is not ruled here. 2026-11-16, serial 132: the promise is of points and not of a picture, `around`'s to within 1e-12 as an absolute difference on each x and y; the kinds' order is the fixture's groups, never a node's own; `unplaced`, the one reading of which elements a saved layout map does not place, answers for the graph it is given, and `placed` is the element ids of the Map's Pins as the map-space reading answers them; a tool that counts leaves Map, Pin and Marker out of the graph it hands in, and a Zone stays; the method word does not say what a saved Map was laid out from, its graph and for `around` its focus and `steps`, and that is not ruled here; rule 10's order is for a Map given a method, first or new, while it holds Pins, not for a layout map laid out again by its own method; seven of the `unplaced` cases answer wrong readings planted in two outside implementations, which the first eight cases left passing; the page and its fixture published, 17 `by-kind` cases, 10 `around` and 15 `unplaced`.

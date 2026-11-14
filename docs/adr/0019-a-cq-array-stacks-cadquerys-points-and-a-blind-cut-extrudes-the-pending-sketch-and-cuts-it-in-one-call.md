# ADR-0019: A `cq` array stacks CadQuery's points, and a blind cut extrudes the pending sketch and cuts it in one call

- Status: accepted
- Date: 2026-11-15
- Closes: the kernel risk of plans/lift-arrays-and-blind-cuts (whether arris
  cuts a blind pocket flush with a face, on a box and on a revolved part)

## Context

plans/lift-arrays-and-blind-cuts lifts `rarray(xSpacing, ySpacing, xCount,
yCount)`, `polarArray(radius, startAngle, angle, count)` and `cutBlind(depth)`.
Read in the corpus text at planning time, the 411 BenchCAD programs they admit
write `polarArray(r, 0, 360, n)` after `workplane()` on a face, then `hole` or
`circle` then `cutBlind`; `rarray` with integer counts then `hole`; and
`cutBlind` with a negative depth after `circle`, `circle(a).circle(b)` (a ring,
the larger first where read) or circles at points, often on a revolved part's end face
(`bellows`, `dome_cap`), the depth sometimes the flange's whole thickness.

**What CadQuery does.** Read in cadquery 2.3.0 `cq.py`:

- `rarray` raises `ValueError("Spacing and count must be > 0 ")` when a
  spacing is `≤ 0` or a count `< 1`. It then makes the points
  `Vector(xSpacing * x, ySpacing * y)` for `x in range(xCount)` (outer) and
  `y in range(yCount)` (inner), adds the offset `-xSpacing * (xCount - 1) *
  0.5` and `-ySpacing * (yCount - 1) * 0.5` (`center=True`), and hands them to
  `pushPoints`: local coordinates of the plane, the grid centred on its origin.
  A count that is not an `int` passes the check and raises from `range`
  (`TypeError`).
- `polarArray` raises `ValueError(f"At least 1 element required, requested
  {count}")` for `count < 1`. With `fill=True` its step is `angle / count`
  when `abs(math.remainder(angle, 360)) < TOL` (`TOL = 1e-6`, a full turn of
  either sign), else `angle / (count - 1)`, and for `count == 1` on a partial
  turn `startAngle`, which no second point uses. Point `i` is at
  `phi = math.radians(startAngle + step * i)`, `(radius * cos(phi),
  radius * sin(phi))`, pushed as a `Location` turned by `phi` about the
  plane's normal (`rotate=True`). `pushPoints` keeps a `Location` as it is and
  `eachpoint` moves it by the plane, so the point is in local coordinates as a
  tuple is. A count that is not an `int` raises from `range`.
- `cutBlind(until)` with a number calls `_extrude(until, additive=False)`:
  `_getFaces` pops the pending wires (`ValueError: No pending wires present`
  when there are none) and makes them faces by `Face.makeFromWires(first,
  rest)`; each face is swept `plane.zDir * until` (`Solid.extrudeLinear`) and
  the sweeps go into one compound. Only then does it look for the chain's
  solid (`findSolid`, `ValueError: Cannot find a solid on the stack or in the
  parent chain`), cut the compound from it in one `cut`, and `clean` it.

**What the oracle shows.** `tools/cq_array_probe.py` runs 49 constructions on
a 10 × 8 × 4 box and on a part revolved from a profile on XY about its y axis
(a cylinder of radius 5, and a flange with a bore of radius 2), each with a
closed form. `tests/fixtures/arrays/constructed.json` holds the reports and
`tests/test_array_probe.py` holds each to its closed form (volume, area,
centroid) or to CadQuery's words:

| Construction | What the oracle builds |
|---|---|
| `rarray` 1 × 1, 3 × 2, on `>X` and `<Y`, then `hole` | a bore at each grid point, centred on the plane's origin, in ADR-0017's frame |
| `rarray(…).circle(r).extrude(h)` | a post on each grid point |
| `polarArray` on a full turn, of either sign, from a start angle | `count` points a `1/count` turn apart |
| `polarArray` on a partial turn, of either sign, from a start angle | `count` points from the start to the end angle, both included |
| `polarArray` with count 1, on a full or a partial turn | one point at the start angle |
| `polarArray` with a negative radius | each point across the centre |
| `polarArray` with radius 0 | three bores at the centre: one hole |
| `polarArray` on `>X`, on a revolved part's `<Y`, then `hole` | the points in the face's frame, a bore at each |
| `circle(r).cutBlind(d)`, `d < 0`, centred and off centre, on `>Z` and `>X` | a pocket `|d|` deep |
| `cutBlind(d)` with `|d|` the part's thickness, or more | a hole through |
| `cutBlind(d)` with `d > 0` from the face's plane | the part unchanged: the sweep is along the normal, out of it |
| `workplane(offset=-1).circle(r).cutBlind(-1)` | a closed void inside the part |
| `workplane(offset=-1).circle(r).cutBlind(2)` | a pocket 1 deep from the top |
| `circle(2).circle(1).cutBlind(d)`, either circle first | an annular groove |
| circles at `pushPoints`, `polarArray` and `rarray` points, then `cutBlind` | a pocket at each; at the thickness, a hole through each |
| a disc, a ring and six discs cut from a revolved part's end face | the pocket, the groove, six pockets |
| a disc of the end face's own radius | a slab off the end |
| six discs through the flange, `cutBlind(-4)` | six holes through |

CadQuery raises for: a spacing `≤ 0` or a count `< 1` in `rarray` (`ValueError:
Spacing and count must be > 0 `, a space at its end), a count `< 1` in
`polarArray` (`ValueError: At least 1 element required, requested 0`, the
count verbatim), a float count in either (`TypeError: 'float' object cannot be
interpreted as an integer`), `cutBlind(0)` (`Standard_ConstructionError:
BRepSweep_Translation::Constructor`, with or without a solid in the chain: the
sweep comes first), `cutBlind` with no pending wire (`ValueError: No pending
wires present`) and with no solid (`ValueError: Cannot find a solid on the
stack or in the parent chain`).

**What arris 0.10.0 offers** (`docs/ARRIS_API.md`). `Sketch.extrude(distance)`
sweeps a sketch, a circle or a ring (a sketch with a hole), along its plane's
normal, against it when negative. `Solid.cut(*tools)` cuts several tools in
one call. Measured in the probe's spike
(`test_arris_cuts_the_blind_tools_to_the_closed_form`, 19 constructions): each
pending sketch extruded `depth` and all cut from the part in one call gives
the closed form, the checker passing, for every flush case the corpus writes:
a disc, a ring and six discs from the box's top face; a disc from a side
face; a tool whose far end lies on the bottom face, one past it, six through
at once; a tool standing on the face, touching it only (the box unchanged); a
void inside the part; a disc, a ring and six discs from a revolved part's end
faces, at both ends; a disc whose wall lies on the part's own cylindrical
wall; and six tools through the flange, both ends flush with its faces.
Nothing was refused, so no regression fixture comes of it.

## Decision

**1. `rarray(xSpacing, ySpacing, xCount, yCount)` puts a stack of points on
the plane** (ADR-0018 rule 1's stack, each point's offset along the normal 0),
by CadQuery's expressions in its order: `xSpacing * i` plus
`-xSpacing * (xCount - 1) * 0.5`, and the same in y, for `i` in
`range(xCount)` outer and `j` in `range(yCount)` inner. A spacing `≤ 0` or a
count `< 1` raises `ValueError` (`runtime`) in CadQuery's words; a count that
is not an `int` then raises from `range` as CadQuery's does (`TypeError`,
`runtime`). The stack is admitted wherever `pushPoints`' is, and a bore or
`circle` on it acts as on `pushPoints`' (ADR-0018 rules 2 and 5).

**2. `polarArray(radius, startAngle, angle, count)` puts a stack of points on
the plane**, by CadQuery's expressions: its step (`angle / count` on a full
turn, `|remainder(angle, 360)|` under CadQuery's `TOL`, else `angle / (count -
1)`, else `startAngle` for one point), `phi =
math.radians(startAngle + step * i)` and `(radius * math.cos(phi), radius *
math.sin(phi))`. Their bits follow the platform's libm, as `transformed`'s
turn does (ARCHITECTURE §Determinism): the same function CadQuery calls. A
count `< 1` raises `ValueError` (`runtime`) in CadQuery's words, the count
verbatim; a count that is not an `int` raises from `range`. CadQuery's turn of
each `Location` is dropped: a bore and a circle are round, and nothing else
the subset puts on a stack of points sees it. A form that would see it
(`polygon`, `rect` on points) brings the turn with it when it is lifted.

**3. `cutBlind(depth)` extrudes the pending sketch `depth` along the plane's
normal and cuts it from the chain's solid in one `Solid.cut(*tools)`.** The
pending sketch is what `extrude` takes: one circle, a ring (two concentric
circles, the larger outside whichever came first, as `circle` already builds
it), or the circles at points (`_Discs`), each its own tool. `depth < 0` cuts
into the part, `depth > 0` along the normal: from a face's plane it cuts
nothing and the part is unchanged. A depth past the part makes a hole through.
In CadQuery's order: no pending sketch raises `ValueError` (`runtime`, "No
pending wires present"), then `depth == 0` raises `ValueError` naming
CadQuery's `Standard_ConstructionError`, then a chain with no solid raises
`ValueError` (`runtime`, "Cannot find a solid on the stack or in the parent
chain"). The keywords no corpus program writes (`clean=`, `both=`, `taper=`)
and an `until` that is not a number (`"next"`, `"last"`, a face) stay outside
the subset (`UnsupportedApi`, the census form's declaration).

## Consequences

- plans/lift-arrays-and-blind-cuts steps 2 to 4 build rules 1 to 3, each with
  `ok-`, `runtime-` and `unsupported-` fixtures on these constructions; step
  5 reads the corpus's contexts (a hole after a blind cut on the same face,
  arrays on a compound, `union` after `cutBlind`).
- `cutBlind`'s tools are as many as the pending circles: one cut, as
  CadQuery's compound is. A cut by a tool that only touches the part, or that
  leaves a void, is the kernel's own answer, read here; the corpus writes
  neither, so a void is lifted only where step 4 reads it agreeing.
- CadQuery's `clean` merges faces arris may leave split; face counts are
  carried, never judged (ADR-0005).
- A `polarArray` point's bits come from libm's `cos` and `sin`; the
  determinism digest is the check that they did not move a result between
  machines, as for `transformed`.

## Alternatives considered

- **arris's `Workplane.polar` and `Workplane.grid`.** They place planes, not
  CadQuery's points, by their own arithmetic (`polar` in radians on a full
  turn only, `grid` as `(i - (nx - 1) / 2) * dx`), so a point's last bits
  could differ from CadQuery's, and neither has `polarArray`'s partial turn or
  either form's refusals.
- **arris's `Solid.pocket(sketches, depth)`.** It cuts only against the
  plane's normal (no positive depth), and its depth tool starts a margin of
  the model's tolerance above the plane, where CadQuery's starts on it;
  `Sketch.extrude` and `Solid.cut`, what `extrude` and the bores already use,
  give every case the oracle builds.
- **One cut per pending circle.** arris builds it, but it is n operations
  where CadQuery has one, each a coplanar contact of its own (ADR-0018 takes
  the one cut for the same reason).
- **Keeping `polarArray`'s turn on each point.** Nothing in the subset reads
  it, and a stack of points with a turn would be a second kind of stack for
  `hole` and `circle` to handle with no effect on what they build.

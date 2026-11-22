# ADR-0018: A `cq` bore cuts CadQuery's pieces at every point, in one call

- Status: accepted
- Date: 2026-11-14
- Closes: plans/lift-holes-and-points' ⚠ OPEN on the bore tool's construction
  and whether arris cuts a conical face cleanly

## Context

plans/lift-holes-and-points lifts `pushPoints(list)`, `hole(diameter, depth=)`,
`cboreHole(d, cboreD, cboreDepth)` and `cskHole(d, cskD, cskAngle)`, and the
contexts the programs they admit write: `faces(sel)` on a stack of faces and
`circle` on a stack of points. Read in the corpus text at planning time, the
859 BenchCAD programs write `pushPoints` after `workplane()` on a face, its
points 2-tuples or 2-lists, then `hole`, `cskHole` (angle 82), `cboreHole` or
`circle`; `hole(d, depth=)` from one face; and `faces(sel).faces(sel)` with one
selector twice.

**What CadQuery does.** Read in cadquery 2.3.0 `cq.py`:

- `pushPoints(pntList)` turns each element into `plane.toWorldCoords(pnt)`, a
  `Location` kept as it is, and puts the list on a new stack. A point is in the
  plane's local coordinates; a third number is its offset along the normal.
- `hole`, `cboreHole` and `cskHole` build one tool in local coordinates, its
  top at the origin and its axis `(0, 0, -1)`, and hand it to `cutEach`.
  `depth=None` is `largestDimension()`, the diagonal of the first solid's box.
  `hole`'s tool is `Solid.makeCylinder(d/2, depth)`. `cboreHole`'s is that
  cylinder fused with `makeCylinder(cboreD/2, cboreDepth)`. `cskHole`'s is
  that cylinder fused with `makeCone(cskD/2, 0, h)`, where
  `h = (cskD/2) / tan(radians(cskAngle/2))`.
- `cutEach` finds the chain's solid (`findSolid`), moves the tool to each
  point by `eachpoint`, cuts all of them in one `ctxSolid.cut(*tools)` and
  cleans the result. `eachpoint` on an empty stack uses the plane's origin, so
  `pushPoints([])` bores there as no `pushPoints` does.

**What the oracle shows.** `tools/cq_hole_probe.py` runs 48 constructions on a
10 × 8 × 4 box, each with a closed form. `tests/fixtures/holes/constructed.json`
holds the reports and `tests/test_hole_probe.py` holds each to its closed form
(volume, area, centroid) or to CadQuery's words:

| Construction | What the oracle builds |
|---|---|
| points as tuples, as lists, several, a duplicate, overlapping | one bore per point, cut together |
| `pushPoints([])` | one bore at the plane's origin |
| a 3-tuple | the bore starts at the offset point: below the face it is capped inside the part, above it it reaches the face |
| a point off the part | the box unchanged |
| points on `>X` and `<Y` | local x and y as `_computeXdir` gives them (ADR-0017) |
| `hole(d, depth=)` | blind; at or past the part's thickness, through |
| `cboreHole`, `cskHole` at 82° and 90°, one and several points | the union of bore and counterbore or cone, cut |
| a counterbore or countersink no wider than the bore | the bore alone |
| a counterbore deeper than the part | the counterbore alone, through |
| a cone wider than the bore at the part's far face | the cone alone |
| a zero bore diameter in `cboreHole` or `cskHole` | the counterbore or the cone alone; a zero `cboreD`, the bore alone |
| `faces(">Z").faces(">Z")`, `faces(">Z").faces("<Z")` | the one face kept, whatever the second selector |
| `faces(">X or <X").faces(">X")` | the stacked face at x = 5 |
| `pushPoints(…).circle(r).extrude(h)` | a post on each point, fused with the box |

CadQuery raises for: `depth=0` and `cboreDepth=0`
(`Standard_ConstructionError: gp_Vec::Normalize() - vector has zero norm`),
a negative `depth` or `cboreD` (`Standard_ConstructionError`), a negative
`cboreDepth` (`ValueError: Null TopoDS_Shape object`), `cskAngle=0`
(`ZeroDivisionError`), `cskAngle` 180 or −90 (`Standard_DomainError: cone with
negative or null height`), a negative `cskD` (`… negative or too small
radius`), `cskD=0` (`… two identic radii`), and points that are one number
(`UnboundLocalError` from inside `Vector`) or a bare number (`TypeError`).

**What arris 0.10.0 offers** (`docs/ARRIS_API.md`). `Solid.cylinder`, and no
cone. `Sketch.revolve` of a polygon `Loop` turns a profile with one edge on
the axis into a solid of revolution, as `sphere` does today. `Solid.cut(*tools)`
cuts several tools in one call. Measured in the probe's spike
(`test_arris_cuts_cadquerys_pieces_to_the_closed_form`): CadQuery's pieces,
each its own tool (a bore cylinder, a counterbore cylinder, a cone revolved
from a right triangle), cut a box to the closed form in one call, the checker
passing. That holds for a counterbore, countersinks at 82° and 90°, two and
three points at once, a counterbore of the bore's own radius (the walls
coincide), a narrower one, one past the part, a cone whose edge meets the
bore's at the top, a cone whose tip is past the part, a cone alone, and a
bore from a side face. A counterbore's pieces cut one after the other build
it too, and so does a half profile of the whole union revolved once (both
read in a spike, not kept). CadQuery's own construction does not: a cylinder fused with a second
cylinder or with a revolved cone, its end on the part's face, is refused by
the cut, `OpDegenerateError` "degenerate result: the faces touch along a curve
interior to both result faces". The fused tool's end is split by the bore's
circle; started above the face it cuts.
`regression/arris-cut-fused-bore-tool-flush` holds it as a strict `xfail`.

## Decision

**1. `pushPoints(points)` puts a stack of points on the plane.** Each element
is a tuple or list of two or three numbers in the plane's local coordinates,
the third the offset along the normal (0 when absent). Any other element, a
`Vector` or `Location` included, ends `unsupported_api` naming the form:
CadQuery's errors there come from inside its `Vector`, not from a check of
the value. An empty list leaves an empty stack, which bores at the plane's
origin.

**2. A bore is one tool per point, cut in one call.** For each point on the
stack (the plane's origin on an empty one), `cq` builds a tool whose top is at
the point and whose axis runs against the plane's normal. The chain's solid is
cut by all of them in one `Solid.cut(*tools)`, as `cutEach` does. A tool's
depth is `depth`, or the diagonal of the solid's box when it is `None`
(today's rule for `hole`).

**3. A tool is CadQuery's pieces, never fused.** `hole`'s is one
`Solid.cylinder`, as today. `cboreHole`'s are the bore's cylinder and the
counterbore's, `cskHole`'s the bore's cylinder and the cone: a right triangle
(radius `cskD/2` at the top, height `h`, CadQuery's `h`) on a plane through the
axis, revolved a full turn. Every piece of every point goes into the one cut
of rule 2: a cut by both pieces is a cut by their union, which is what
CadQuery's fused tool is. A piece of zero radius is left out, so a zero bore
diameter leaves the counterbore or the cone, and a zero `cboreD` the bore, as
the oracle shows.

**4. Arguments CadQuery refuses raise in `cq` (`runtime`)**, a `ValueError`
naming CadQuery's error, as `hole` does for a negative diameter today:
`depth ≤ 0`, `cboreDepth ≤ 0`, `cboreD < 0`, `cskD ≤ 0`, and a `cskAngle` in
`[−180, 0]` or `[180, 360)`, where CadQuery's `h` is negative, zero, or, at 180,
`6e-17` of the radius, which Open CASCADE calls null. A `cskAngle` outside
`[−180, 360)` ends `unsupported_api`: CadQuery's tangent repeats there and
builds a cone no program asks for. A negative bore diameter in `cboreHole` or
`cskHole` is read on the oracle by the step that lifts the form.

**5. `faces(sel)` on a stack of faces ranks the stacked faces only**, by
ADR-0017's rules. **`circle` on a stack of points** draws one circle per point.
plans/lift-holes-and-points step 6 lifts each where it agrees with the oracle.

## Consequences

- plans/lift-holes-and-points steps 2 to 6 build rules 1 to 5, each with
  `ok-`, `runtime-` and `unsupported-` fixtures on these constructions.
- `cq` needs no outline of the union: whichever piece is wider or deeper, the
  cut by both gives it. A point stack of n points is one cut of up to 2n tools.
- CadQuery's `clean` merges faces arris leaves split: two overlapping bores
  give 8 faces on the oracle and 9 in arris. Face counts are carried, not
  judged (ADR-0005).
- The fused construction's refusal is not on `cq`'s path, so it stays a
  regression fixture: it looks like `regression/cq-union-three-coplanar-cylinders`'
  (a coplanar contact with a face split by an edge), already asked of arris.

## Alternatives considered

- **CadQuery's fuse of a cylinder with a cylinder or a revolved cone.** arris
  refuses the cut wherever the tool's end lies on the face, which is every
  program the bundle admits.
- **One half profile of the union, revolved once per point.** It cuts to the
  closed form too, but needs the union's outline worked out case by case (a
  narrower or deeper piece, the cone crossing the bore, its tip past the
  bore's bottom), a second reading of what the cut already gives.
- **The pieces cut one after the other.** arris builds it, but it is up to 2n
  operations where CadQuery has one, each a coplanar contact of its own.
- **arris's `Solid.hole`** (`at` workplanes and a depth). It bores a cylinder
  only.

## Amendment (2026-11-14): both ends of the countersink's angle are refusals

Rule 4's ranges are amended: a `cskAngle` in `[−180, 0]` or `[180, 360]`
raises in `cq` (`runtime`), and one outside `[−180, 360]` ends
`unsupported_api`. 360 belongs with 180, not past the range: CadQuery's
`tan(radians(360 / 2))` is `−1.2e-16`, so its cone's height is `−8e15`
times the radius and Open CASCADE refuses it as it refuses 180
(`Standard_DomainError: cone with negative or null height`), where an angle
past 360 builds the cone of the angle 360 degrees nearer. Read on the oracle:
`tools/cq_hole_probe.py` adds `cskHole` at 360 and at −180 (50 constructions),
both that refusal, `tests/test_hole_probe.py` holding each to CadQuery's words;
`cq/runtime-csk-angle-360` and `-minus-180` agree with their recorded reports,
and `cq/unsupported-csk-angle-above-360` and `-below-minus-180` record the
cones of 40 and 160 degrees the oracle builds at 400 and −200. The rest of
rule 4 is unchanged.

## Amendment (2026-11-22): profiles at points

Rule 5's point stack places one profile per point for `circle`, `rect` and
`slot2D`. `polarArray` supplies a rotation for rectangles and slots.
[ADR-0024](0024-a-cq-through-cut-sweeps-placed-profiles-past-the-stock.md)
sets how the pending profiles nest, fuse when extruded and cut the stock.

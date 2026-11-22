# ADR-0024: A `cq` through cut sweeps placed profiles past the stock

- Status: accepted
- Date: 2026-11-22
- Amends: ADR-0018 rule 5 for profiles at points

## Context

The first plan of BenchCAD bundle 5 lifts `cutThruAll()`, `center(x, y)`,
`rect(xLen, yLen)` and `slot2D(length, diameter, angle)`. ADR-0014 records the
split of the bundle. ADR-0019 establishes how `cutBlind` consumes pending
wires and cuts the resulting prisms in one call.

CadQuery 2.3.0's `Workplane.cutThruAll` in `cadquery/cq.py` looks up the
solid before converting the pending wires to faces. `dprism` in
`cadquery/occ_impl/shapes.py` applies Open CASCADE's `PerformThruAll` to each
face. The same `cq.py` defines `center`, which replaces the stack with the
new origin while keeping the pending wires in the chain's context. `rect`
and `slot2D` place a closed wire at each location through `eachpoint`,
including the location's rotation.

The 56 oracle constructions in `tests/fixtures/profiles/constructed.json`
are checked by `tests/test_profile_probe.py`. The fixture README gives the
closed forms. The construction names below refer to those records.

## Decision

### A. Through cuts

Find the chain's nearest solid first, including a compound (ADR-0016).
Use the pending profiles on their own planes. The cut removes the stock
along the whole normal line through each point of the section. One bore
has the same measures from the face, inside, above and below the stock
(`through-on-face`, `through-inside`, `through-above`, `through-below`). A
profile outside the stock leaves it unchanged (`through-miss`). An
overhang cuts only the intersection (`through-overhang`). The cut reaches
every piece of a compound (`through-compound`). Circles and rectangles at
points, polygons, closed paths and slots use the same sweep
(`through-circles-at-points`, `through-rects-at-points`, `through-polygon`,
`through-path`, `slot-through`).

For each section, project the full stock bounds onto the section normal
relative to the sketch's origin. Start the prism before the lower bound
and end it past the upper bound. Use the stock's box diagonal
(`_bore_length`) as clearance at each cap. The projected bounds determine
the position of the tool even for a profile plane farther from the stock
than that diagonal.
`Sketch.moved_to`, `Workplane.offset` and `Sketch.extrude` from the pinned
wheel (`docs/ARRIS_API.md`) place the tools. Pass the tools in profile order
to one `Solid.cut(*tools)` in the stock's model. This also lets the cut
itself handle a miss or an overhang.

| Condition | Outcome |
| --- | --- |
| No solid in the chain, with or without wires | `runtime` via `ValueError` with “Cannot find a solid on the stack or in the parent chain” (`through-no-solid`, `through-no-solid-or-wires`). |
| A solid with no pending wires | `runtime` via `ValueError` with “No pending wires present” (`through-no-wires`). |
| Concentric circular ring | `runtime`, naming CadQuery's `Standard_OutOfRange` and `NCollection_Sequence::Value` (`through-ring`). The same wires still cut as an annulus with `cutBlind` (`blind-ring-through-depth`). |
| Finalized `cq.Sketch` or a `clean=` or `taper=` form | `unsupported_api` naming the call and context or form. Step 3 adds `cq/unsupported-cut-thru-all-finalized-sketch`, `cq/unsupported-cut-thru-all-clean` and `cq/unsupported-cut-thru-all-taper`. |

Rectangle and circle nests added by rule B also need a through-cut check
in step 5. An oracle spot check on the same 10 × 8 × 4 stock used
`rect(4, 4).rect(2, 2)` and `rect(4, 4).circle(1)` on its top face. Both
through cuts raised `StdFail_NotDone` with `BRep_API: command not done`.
Step 5 records these cases with the nestings and matches their `runtime`
outcome.

The side bore (`regression/oracle-cut-thru-all-side`, row `through-side`)
has closed-form volume `320 − 10π` and area `304 + 18π`. The oracle gives
volume lower by about 4.19e-7 and area higher by about 1.26e-6, outside
ADR-0005. The oracle fixture retains its strict `xfail`. Step 3 checks the
arris cut against the closed form. Step 7 checks for the same measure
error in BenchCAD and gives affected rows a closed-form verdict under
ADR-0006 where the evidence warrants it.

### B. Profiles at points and nested wires

Generalize `_Discs` to hold ordered profiles placed at points. The point
order is the order from `pushPoints`, `rarray` or `polarArray`. Rectangles
and slots use the point's orientation. In particular a polar point turns
a rectangle about the plane normal by that point's array angle
(`rects-at-polar-points`). Circles retain ADR-0018's existing point-stack
checks. The lifted rectangle and slot forms use in-plane points.

For rectangles drawn in one call, use the union of the swept regions.
`extrude` fuses the prisms and both cuts pass their tools in one call.
Edge contact and overlap produce one union section (`rects-edge-touch`,
`rects-overlap`, `through-rects-edge-touch`, `through-rects-overlap`). A
pair whose only contact is a corner extrudes as two solids on the oracle
(`rects-corner-touch`). In a pinned-wheel check, fusing those two prisms
raised `OpDegenerateError` because the shells would share an edge. The
same refusal occurred when cutting the two corner-touching windows. The
oracle built that cut as one solid of volume 288 in a spot check using the
`rects-corner-touch` positions on the top face of the 10 × 8 × 4 stock.
Preserve the kernel's typed refusal and verbatim message. Step 5 records
the corner cases as regressions held to their closed forms. Its
property checks the typed refusal and the union volume where arris builds
the part.
Bounding-box contact alone establishes neither contact nor containment.

Two strictly nested rects or a strictly nested rect and circle at one
centre make one section with the inner wire as its hole, in either call
order. This is the same containment rule as for a circular ring. Use the
actual boundaries in the plane. A circle fits inside a rectangle when
its radius is less than both half-extents. A centred rectangle fits inside
a circle when its half-diagonal is less than the radius. For two
axis-aligned centred rectangles compare both half-extents strictly. A
rotated rectangle is tested by its corners in the outer rectangle's frame.
The `rect-on-rect`, `rect-on-circle` and `circle-on-rect` constructions and
their `-outer-last` variants hold both orders to the closed form. Step 5
checks other consumers of these pending profiles on both engines and gives
any unsupported context its own fixture.

### C. Moving the centre

`center(x, y)` moves the origin by `(x, y)` in the current plane's axes,
keeps the axes and chain's solid, and replaces the visible stack with one
point at the new origin. The old stack's points do not enter the offset
(`center-after-move`, `center-after-points`). Offsets accumulate
(`center-twice`). A later `moveTo` or array uses the new axes and origin
(`center-before-move`, `center-before-array`). A face workplane follows
the same rule (`center-on-face`).

Carry pending closed wires independently of that one point. Each kept wire
stays in its original placement and can be consumed directly or alongside
a later wire drawn at the new point (`center-on-pending`,
`center-between-profiles`). The new workplane holds those wires without
mutating its ancestors (ADR-0007).

### D. Rectangle sizes

`rect(xLen, yLen)` uses `Workplane.rect` with absolute dimensions. It is
centred at the plane's origin, a `moveTo` or `center` point, or each point
of a point stack (`rect-origin`, `rect-at-point`, `rect-at-center`,
`rects-at-points`, `rects-at-polar-points`). Reversing either dimension
changes traversal on the oracle and gives the same centred section
(`rect-negative-x`, `rect-negative-y`, `rect-negative-both`).

One zero dimension gives an out-and-back wire. The oracle reports one
solid of zero volume (`rect-zero-x`, `rect-zero-y`). In the pinned wheel,
extruding either wire raises `OpProfileError` for a zero-length segment.
Let that failure surface as `arris_refusal` when the kernel consumes the
wire. Zero-size rectangles have no synthetic replacement section.

### E. Slot sizes and angles

`slot2D(length, diameter, angle)` uses the same placement rules as `rect`
and builds a section with `Workplane.slot`, passing the diameter as width
and converting the angle from degrees to radians. At a polar point the
array angle adds to the slot angle. For `L > D > 0` the section has area
`(L − D) · D + πD²/4` (`slot-0`, `slot-45`, `slot-90`, `slot-at-point`,
`slots-at-points`, `slot-through`).

With positive equal length and diameter, raise `ValueError` (`runtime`),
naming CadQuery's `StdFail_NotDone` and `BRep_API: command not done`
(`slot-equal`). With `0 < length < diameter` the arcs cross in the
recorded construction and the oracle reports `invalid` (`slot-short`).
The pinned wheel raises `SketchError` on that section. Keep the typed
`arris_refusal` and its message. If such a pair appears in the corpus,
step 7 must class it with evidence under ADR-0006.

## Consequences

- Steps 3 to 6 of `plans/lift-rects-and-through-cuts` implement and test
  these rules. The existing probe records remain the oracle evidence.
- Step 7 tests the admitted forms on the corpus under ADR-0012's static
  membership rule. Every failure stays in the fidelity table.

## Alternatives considered

- **Use the stock diagonal as the entire sweep.** A sufficiently distant
  workplane would leave one or both caps short of the stock.
- **Apply the circular point-stack contact guard to rectangles.** It would
  reject the rectangular unions observed on the oracle and built by arris.
- **Let the new point replace pending wires in `center`.** A subsequent
  extrusion would lose geometry present in `center-on-pending` and
  `center-between-profiles`.

## Amendment, 2026-11-22

The six concentric nests with a rectangle raise `StdFail_NotDone` in
`cutThruAll` on the pinned oracle (`runtime-through-rect-on-rect` and its
five variants). Blind cuts and revolutions of the same sections match
their closed forms in `ok-*-cutblind` and `ok-*-revolve`.

Fuse a rectangular array's prisms together in one call. In
`ok-rects-edge-bridge`, the first two prisms touch at a corner and the
third joins both along a full side. Fusing the first pair alone would
refuse this valid union. The separate three-way overlap in
`regression/rects-three-way-overlap` remains open. The pinned wheel
refuses it and the oracle builds an invalid part.

Successive drawings on profiles drawn at an array remain outside the
subset. The one-point polar probes include a rotated rectangle followed
by a rectangle or a circle, and a circle followed by a rectangle. Each
continues to return `unsupported_api` in the subset.

## Slot amendment, 2026-11-22

At points, the slots must be disjoint. The centreline segment joins the
centres of the two semicircular ends. Two slots touch when the shortest
distance between their centreline segments is at most their common
diameter. CadQuery reports overlapping parallel slots as invalid,
builds the tip-touching slots as two solids and builds a union of
crossing polar slots. Arris unions the parallel slots and refuses the
two other cases. The subset returns `unsupported_api` for all three
(`unsupported-slots-overlap`, `unsupported-slots-touch`,
`unsupported-slots-rotated-overlap`). Diagonal slots with overlapping
bounding boxes remain supported when their sections are disjoint
(`ok-slot-diagonal-disjoint`).

Zero diameter with positive length raises `ValueError` with the oracle's
`StdFail_NotDone` and `GC_MakeArcOfCircle::Value() - no result`.
Two zero dimensions use the same exception and message as positive
equal dimensions.
Zero length with a positive diameter leaves the kernel's `SketchError`
intact. Negative dimensions stay outside the subset. The oracle builds
valid sections with a different straight length for the recorded
negative dimensions.

A slot can be revolved on a chain without stock. With stock, the tested
revolution and fusion exceeds the ADR-0005 agreement tolerance for
volume and area, so the subset refuses that context
(`unsupported-slot-revolve-with-stock`). Other refused combinations are
recorded in `tests/fixtures/profiles/slot-contexts.json`.

# ADR-0026: A `cq` loft pairs world-placed sections before smoothing

- Status: accepted
- Date: 2026-11-26

## Context

BenchCAD bundle 5 calls `Workplane.loft(combine=bool)`. Adding that API
form and its default projects 992 more programs in-subset under ADR-0012.
CadQuery 2.3.0 consumes pending wires in drawing order and asks Open CASCADE
7.9.3.0 for a smooth solid loft. The corresponding arris 0.12.0 entry
points are `Sketch.loft` and `Model.loft`. They accept placed sections and
a loft kind. On equal edge counts, arris pairs edges by index from the
supplied starts.

## Decision

### Placement and consumption

Use the pending sections in drawing order, each in the world frame it had
when drawn. The active workplane and its parent chain follow ADR-0007
and ADR-0017. The loft result has a solid on its stack and the pending
sections are consumed. The oracle's shared context also consumes them on
the source branch. The frozen subset clears them on the result and
preserves independently held branches under ADR-0007.

With `combine=True` or the argument omitted, fuse the loft with the nearest
solid in the chain if present. With `combine=False`, put only the loft on
the result stack. The oracle's empty case ends `runtime` with
`ValueError: No pending wires present`. Its one-section case ends `runtime`
with `ValueError: More than one wire is required`. The subset checks the
section count before calling arris. The arris entry point gives a typed
refusal for too few sections. The fixtures in
`tests/fixtures/lofts/contexts.json` cover both cases, both combine values,
the default, the face-based stock and selection of the loft's upper cap.

### Correspondence and construction

Build with `Sketch.loft(sections, kind="smooth")` after pairing the
sections. Two sections with the same correspondence give byte-equivalent
arris bodies in smooth and ruled modes in the frustum, both rotated
rectangle fixtures and the tooth-outline fixture. An analytic cone and
planar sides are available through the same call when the geometry reduces
to them. The verified circular constructions have a shared axis. Wires
with unequal edge counts and curved paths require their own pairing evidence.

For polygonal wires with the same number of edges, the oracle keeps the first
wire's order and pairs each later wire to the preceding one. Its
`BRepFill_CompatibleWires::ComputeOrigin` compares cyclic starts and both
directions by the sum of distances between paired vertices. In that
comparison it aligns the wire centres of mass in the plane perpendicular
to the first wire's normal. Keep the placed vertices fixed when passing
the chosen order to arris. On the two-section quarter-turn rectangle,
pairing by drawing start gives volume 32. Moving the second wire's start
one vertex back produces six planes and volume 176/3, agreeing with the
oracle under ADR-0005. On the tooth outline, CadQuery's original, shifted
and shifted-and-reversed inputs all agree with the same explicitly paired
arris loft. The raw shifted arris outlines fail its checker. The
`rectangle-oblique`, `rectangle-quarter-turn` and `tooth-outlines`
fixtures keep these cases.

Three sections need the smooth interpolation and its section parameters.
In the rotated-rectangle and tooth-outline regressions, the two kernels
pair the same corners. The normalized middle parameter is about 0.355915
on the oracle and 0.353104 in arris for the rectangle, and 0.358771 and
0.356954 for the tooth outline. A volume integral of the quadratic
cross-sections recovers each side's own volume. The rounded relative
volume gaps are 1.11e-3 and 6.94e-4. The public arris loft calls offer
no way to supply the parameters. The regressions remain strict expected
failures at their desired oracle geometry.

The symmetric three-disc construction agrees with the exact quadratic
profile on arris. It has a smaller gap against the oracle's reported
measures, including a transverse centroid of about 1.87e-6 on the
oracle. This comparison remains a strict expected failure. The
three-section cases do not establish any ruled replacement.

The pinned sources behind the correspondence and smoothing are
[Open CASCADE's wire pairing](https://github.com/Open-Cascade-SAS/OCCT/blob/V7_9_3/src/BRepFill/BRepFill_CompatibleWires.cxx#L1561)
and [through sections](https://github.com/Open-Cascade-SAS/OCCT/blob/V7_9_3/src/BRepOffsetAPI/BRepOffsetAPI_ThruSections.cxx).
The CadQuery entry points are listed in `PROVENANCE.md`.

### BenchCAD evidence

The program hashes match the committed census and oracle rows for all 992
projected additions: 189 bevel gears, 203 helical gears (110 two-section
and 93 three-section), 106 propellers, 146 tapered bosses, 177 twisted
brackets and 171 wing nuts. The pinned oracle has 979 `ok` and 13
`invalid` reports. The invalid reports are all wing nuts.

The table records sampled complete programs on a temporary sandbox
adapter against the pinned oracle rows. The adapter carries closed wires
on plane changes, builds the smooth loft and pairs the rotated rectangles.
`tests/fixtures/lofts/README.md` describes the loft-only controls and
their timing.

| Family and stem suffix | Sections | Complete candidate under 30 s | Pinned oracle |
|---|---:|---|---|
| `bevel_gear_012513_s20260505` | 2 | body worker timeout | `ok` |
| `bevel_gear_013176_s20260505` | 2 | program worker timeout | `ok` |
| `helical_gear_009003_s20260505` | 2 | body worker timeout | `ok` |
| `helical_gear_002531_s20260505` | 2 | program worker timeout | `ok` |
| `helical_gear_004294_s20260505` | 3 | body worker timeout | `ok` |
| `helical_gear_009469_s20260505` | 3 | program worker timeout | `ok` |
| `propeller_000111_s20260505` | 2 | 0.251 s, bounding-box gap 9.69 | `ok` |
| `tapered_boss_000027_s20260507` | 2 | 0.145 s, agrees | `ok` |
| `twisted_bracket_000024_s20260505` | 2 | 0.054 s, agrees | `ok` |
| `wing_nut_000008_s20260505` | 2 | 0.059 s, later fillet refusal | `ok` |
| `wing_nut_000078_s20260505` | 2 | 0.068 s, later fillet refusal | `invalid` |

The face-based propeller, twisted bracket, tapered boss and wing nut
all agree through their first loft in isolation. Those prefixes took
0.02–0.06 s on arris. The multi-loft propeller
`propeller_000192_s20260505` also requires `ellipse` and lies outside the
992.

## Consequences

A trimmed replay of one bevel and both helical section counts still ran
past the 30 s deadline in the body worker. Building the same lofts and
returning a unit box took 0.029–0.036 s. This bounds the isolated build
cost and locates the prefix timeout after construction. The larger full
programs also reach the deadline during further operations. The corpus
deadline and full checker stay in use.

The measured performance risk affects 392 projected gear rows. Within
those rows, 93 use three sections and also need their interpolation
verified. The full replay determines how many of the 392 actually fail.
If all 392 were deferred, the all-lifts reach projection would drop
from 15,718 to 15,326 of 17,900, against the 15,215 target. This ADR
records the risk and leaves the planned reach and fidelity criteria in
force. The reduced loft and the gear timings are filed with arris for
explicit section parameters and faster handling of many curved sides.

## Alternatives considered

- **Pair edges by drawing index.** The shifted tooth and quarter-turn
  cases show that the position of a wire's start changes the body.
- **Use ruled lofts for three or more sections.** The three-disc volume
  changes from 112π/15 for the quadratic loft to 28π/3 for the two cones.
- **Replace the gear outlines by a simplified taper or twist.** The
  coordinates are rounded independently in each section. An exact
  simplification would need to preserve the resulting boundary at every
  tooth.

## Amendment (2026-11-26) — plane changes and existing consumers

`workplane` and `transformed` empty the visible stack and carry one closed
disc, rectangle, polygon or path forward in its drawing frame. The next
section uses the active frame. Carrying sections appends to an ordered
tuple on the new workplane. The parent chain still supplies the nearest
solid, including stock selected by a face. On one wire, its centre is in
the drawing plane, so projecting the origin onto the plane through that
centre leaves it where it was before applying `workplane`'s offset.

The pinned oracle uses the active plane's normal for `extrude` and
`cutBlind`. The subset takes a single carried wire for these calls when
the normals agree. A through-cut sweeps a single carried wire along its
drawing normal even after a tilt. Revolution takes the axis from the
active plane and requires that axis to lie in the wire's drawing plane.
The existing consumers refuse multiple wires carried across plane
changes. In the offset pair probes the oracle could not build planar
faces out of the two wires.

`tests/fixtures/lofts/plane-change-contexts.json` records the consumer
probes, including a sweep of the first section in the face-based propeller
chain, carried profiles on rotated frames, both kinds of tilt refusal
and the through-cut on a tilted frame. The single rectangle cases moved
from the refusal records in `tests/fixtures/profiles/rect-contexts.json`.
Multiple visible wires, nested profiles, slots and open paths stay
outside this lift.

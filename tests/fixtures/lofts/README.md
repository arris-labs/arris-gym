# Loft fixtures (ADR-0026)

`program.py` runs on the pinned arris worker. Each `oracle*.py` ran
through `tools/oracle_run.py` on pinned CadQuery 2.3.0 and OCP 7.9.3.0.
The adjacent report retains its program hash and measures. The test
compares the paired results under ADR-0005.

- **disc-frustum** has radii 2 and 1 and height 3. Its volume is
  7π, its area is π(5 + 3√10) and its centroid is at z = 33/28.
  The extreme radius is 2 and the caps lie in z = 0 and z = 3.
- **rectangle-oblique** connects a 6 × 2 rectangle to one turned 21°
  in plane, scaled by 0.8, translated by (0.7, 0.4) and raised 4.
  The expected measures come from its oracle report. Four bilinear
  sides and two planar caps close the solid.
- **rectangle-quarter-turn** has the same 6 × 2 outline at z = 0 and
  turned 90° at z = 4. With the paired starts each intermediate outline
  is a rectangle with sides 6 − 4t and 2 + 4t, where t = z/4. Integrating
  gives volume 176/3. The four trapezoids and two caps have total area
  24 + 32√5. The centroid is at (0, 0, 2), and the bounds are the union
  of the two caps' bounds. With the drawing-start pairing the section
  area is 12((1 − t)² + t²) and the volume is 32.
- **tooth-outlines** has a concave nine-vertex outline and a rotated,
  translated and scaled copy. The oracle reports for the drawn start,
  shifted start and opposite winding all measure the same solid, with
  nine side faces and two planar caps. The expected measures are from
  the report for the drawn start.
- **disc-three-sections** has radii 2, 1, 2 at z = 0, 2, 4. The
  quadratic radius is 1 + (z − 2)²/4. Integrating πr² gives volume
  112π/15. Integrating 2πr√(1 + r′²) and adding the caps gives area
  π(8 + 7√2 + 3 asinh(1)). Its centroid follows by axial and midplane
  symmetry. Arris holds to the construction. The oracle measure gap
  stays visible as a strict expected failure in `test_loft_probe.py`.

`contexts.json` holds the CadQuery programs and reports for zero and one
section, consumption from the original branch, a face-based pair with
and without stock, default combine, and another operation on the upper
cap. The stock is a radius-3 cylinder from Y = −2 to Y = 2. The frustum
starts at Y = 2 and the follow-on operation adds a radius-0.5 cylinder
from Y = 5 to Y = 7. The tests calculate the measures from those shapes.

## Three-section regressions

`regression/arris-loft-three-rectangles` and
`regression/arris-loft-three-tooth-outlines` use shifted and rotated copies
of their bottom outlines at heights 0, 2 and 6. Their desired measures
are the recorded oracle measures. Volume independently follows from
interpolating paired vertices quadratically, computing each section's
area by the shoelace formula and integrating area times the derivative
of height. The integrand has degree at most five. In the oracle STEP
the height coordinate of the middle Bézier control point is
2.704478616894 for the rectangle and 2.66828131202 for the tooth outline.
With that height called h, solve 2 = 2h·t·(1 − t) + 6t² for the
middle section's parameter. The integral gives 56.7126142675 and
137.2058237113 respectively. Using arris's parameters from its summed
control-net chords gives 56.6497601440 and 137.1106266943. The observed
volume gap follows from the built boundary.

## BenchCAD probes

The complete-program reports are in
`tests/fixtures/c2/benchcad/oracle.jsonl.gz` at the pinned BenchCAD
`code_gen` revision `5919f578ab09ec283603a082fab07c7639ab56eb`
(CC-BY-4.0). Only stem names and measured observations are reproduced here.
The loft-only controls retain the chain through its first `.loft()` and use
that value as the result. For the gear timing control, an otherwise
identical arris worker program instead returns a unit box after building the
loft.

| Stem | Loft only, arris at 30 s | Build and return unit box |
|---|---|---:|
| `bevel_gear_012513_s20260505` | body worker timeout | 0.030 s |
| `helical_gear_009003_s20260505` | body worker timeout | 0.029 s |
| `helical_gear_004294_s20260505` | body worker timeout | 0.036 s |

Each of these three prefixes returned `ok` on the oracle. The timing
observations use two workers and describe the development machine. The
tests exercise numerical results and do not require those wall-clock times.

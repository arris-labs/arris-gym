# ADR-0005: The agreement tolerance is set from a calibration set held to closed forms

- Status: accepted
- Date: 2026-11-08

## Context

`fidelity` compares an arris result with the oracle's report on one program
and says whether they measure the same part. The tolerance that decides it
cannot be chosen by feel: too tight and a kernel's rounding is a
disagreement, too wide and a modelling error is hidden. A tolerance fitted to
the two kernels agreeing with each other would also prove nothing if both
were wrong, so the calibration set holds each of them to a closed form first.

The set is 19 parts under `tests/fixtures/fidelity/agree-*/`: boxes, cylinders,
a tube, a hexagonal prism, through, blind and paired holes, a fuse, a cut,
four revolves (washer, frustum, torus, sphere), two fillets and two chamfers.
Each is built twice, as an `arris` program and as CadQuery, and its volume,
area, centroid and bounds are worked out from how it was built (the
directory's README gives each form). Measured on this machine, arris against
the closed form, the oracle against it, and the two against each other:

| Measure | Largest gap on 19 parts |
|---|---|
| volume, relative | 7e-16 (arris), 4e-16 (oracle) |
| area, relative | 5e-16 (arris), 3e-16 (oracle) |
| centroid, absolute | 2e-15 on parts 4 to 20 across |
| bounds, absolute | 2.0e-7 arris, 1.0e-7 oracle, on every part |
| face count | equal on 18; 11 against 8 on the fuse |

Findings behind the table:

- **The bounds gap is padding.** arris pads a body's box by the kernel's
  tolerance, 2e-7 on every side; Open CASCADE's box is the part's extent
  plus its own tolerance, 1e-7, on a torus, and exact elsewhere. The first
  version of the oracle worker used `BRepBndLib.Add`, which boxes a surface
  by its control net: 0.33 too wide on an 8 x 8 x 2 torus. The worker now
  uses `AddOptimal` without triangulation or shape tolerances, the tight
  box.
- **Face counts differ by convention.** A fuse leaves arris with the
  coplanar faces of its two operands split (11 on an L-shaped prism); Open
  CASCADE's `union` cleans them (8, the closed form). A periodic surface is
  one face in both (a cylinder is 3, a torus 1).
- **The one-edge fillet and chamfer fixtures** lose a corner at each end
  face as well as at the top and the side; the first closed forms
  forgot it and both kernels, agreeing, said so.

## Decision

**Two parts agree when every judged measure is inside its constant** (named
and commented in `fidelity/_agreement.py`, nowhere else):

| Constant | Value | Measure |
|---|---|---|
| `VOLUME_REL` | 1e-9 | volume, relative to the larger of the two |
| `AREA_REL` | 1e-9 | area, likewise |
| `CENTROID_DIAG` | 1e-9 | centroid distance over the bounding-box diagonal |
| `BOUNDS_ABS` | 1e-6 | largest coordinate difference of the boxes, absolute |

1e-9 is the figure the oracle's selftest already holds `GProp` to, and six
orders above the largest gap measured. `BOUNDS_ABS` is five times arris's
padding, which is a difference of convention, not of geometry. A figure
outside a constant is a disagreement and is classed (ADR-0006), never
absorbed by widening the constant: a pair that will not agree at these is a
regression fixture and an open question.

**Face counts are carried and never judged.** `MeasureDeltas.faces` is
arris's count minus the oracle's and goes into the row, but no count makes
two parts disagree: the conventions above differ, and volume, area, centroid
and bounds together fix the geometry. The delta is there for a reader of the
table and for ADR-0006's classes.

## Consequences

- The tolerance is tight for analytic parts. A freeform surface (a sweep, a
  loft) integrates less exactly on Open CASCADE; if a slice program lands
  between a constant and a plausible numerical error it is a row to judge,
  with a verdict, not a reason to loosen the constant here.
- A part whose oracle report has not exactly one solid has no figure to
  compare and is not judged by this rule.
- The oracle worker's bounds changed from `Add` to `AddOptimal`; reports
  recorded before step 4 do not exist, so nothing is stale.
- The set lives in the gate: the recorded oracle reports are committed and
  the test reads them, so the table needs no CadQuery to be re-checked, and
  a re-record is a visible change of the oracle.

## Alternatives considered

- **A single relative tolerance of 1e-6**, as the fixture loader's default:
  would pass a modelling error nine orders larger than any gap measured here.
- **Judging face counts**: the fuse fixture would disagree on a
  convention, and every boolean on the slice would too.
- **Bounds relative to the diagonal**: arris's padding is absolute, so a
  small part would disagree on a part that is exact.

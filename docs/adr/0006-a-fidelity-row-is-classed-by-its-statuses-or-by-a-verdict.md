# ADR-0006: A fidelity row is classed by its two statuses, or by a verdict

- Status: accepted
- Date: 2026-11-08

## Context

`fidelity.compare` takes an arris `ExecResult` and an `OracleReport` for one
program and produces a **fidelity row**. Each row is an agreement, a
disagreement with one of the five classes SEED.md §5 names (`cq` bug, arris
refusal with its kind, arris bug, Open CASCADE wrong, semantic difference by
design), or `unclassified`. Unclassified rows make the cycle red (gym.md).

Some status pairs class themselves. If the oracle builds the part and arris
refuses it, the row is an arris refusal, and the kernel's typed exception
names its kind. Other pairs cannot be classed from statuses alone. When the
two measures differ, either kernel may be wrong. When the oracle fails alone,
the cause may be Open CASCADE, CadQuery's semantics or the program. A rule
that classed those rows by default would hide the cases the table exists to
find. A timeout is decided by wall-clock time, so a slower machine can change
it (gym.md, Determinism).

arris (its ADR-0015, amended by its ADR-0073) settles a disagreement with
Open CASCADE using a closed form, or a second oracle's record where no closed
form exists. The same evidence is accepted here.

## Decision

**The rule classes what the statuses settle, and nothing else.** In order:

| arris | oracle | row |
|---|---|---|
| any | `timeout` | unclassified |
| `timeout` | any | unclassified |
| `crash` | `crash` | agree: the program ended its own worker on both |
| `crash` | not `crash` | `arris_bug` |
| `checker_fail` | `invalid` | agree: both built a shape their checker rejects |
| `checker_fail` | not `invalid` | `arris_bug` |
| `ok`, `syntax`, `runtime`, `unsupported_api`, `arris_refusal` | `crash` or `invalid` | unclassified |
| `syntax`, `runtime`, `unsupported_api`, `arris_refusal` | `syntax`, `runtime`, `no_result` | agree: both failed |
| `arris_refusal` | `ok` | `arris_refusal`, with the result's refusal (kind, message, entities) verbatim |
| `runtime`, `unsupported_api` | `ok` | `cq_bug` |
| `syntax` | `ok` | unclassified: one text cannot parse on one Python 3.12 and not on another, so something else differs |
| `ok` | `syntax`, `runtime`, `no_result` | unclassified: the oracle fails alone |
| `ok` | `ok`, the oracle with exactly one solid, inside the agreement tolerance (ADR-0005) | agree |
| `ok` | `ok`, otherwise | unclassified |

A crash, or a shape that fails arris's own checker, is never a correct
answer. So it is an arris bug unless the oracle failed the same way. A crash
or an invalid shape on the oracle alone is not a class. It is Open CASCADE
wrong only once a verdict shows it.

**A verdict classes a row the rule cannot, and may replace the rule's
class.** A `Verdict` is a `DisagreementClass` and one piece of evidence:

| Evidence | Says | Allowed for |
|---|---|---|
| `ClosedForm` | volume, area, centroid and bounds worked out from how the part is built | every class but `by_design` |
| `SecondOracle` | which kernel and version, and its record verbatim | every class but `by_design` |
| `DocAnchor` | the doc or ADR, with its heading, that makes the difference intended | `by_design` alone, which requires it |
| `RegressionFixture` | the `tests/fixtures/regression/` directory that holds the case | `cq_bug`, `arris_refusal`, `arris_bug` |

`occt_wrong` therefore rests on a closed form or a second oracle, as arris's
ADR-0015 does. `compare` checks a closed form against what it is given. At least
one side must have measured a shape. Where the side the class exonerates
(arris for `occt_wrong`, the oracle otherwise) has measures, they must lie
inside the agreement tolerance of the closed form. Where the side it blames
has measures, they must not. An arris refusal leaves arris with no measures,
so the oracle's alone are checked when such a row is re-classed
`occt_wrong`. `compare` raises
`ValueError`, as a caller's mistake, for these verdicts:

- a verdict on a row the rule finds agree;
- a verdict of any class but `arris_bug` on an arris `crash` or
  `checker_fail` the rule classes `arris_bug`: a crash is never an answer,
  so no evidence makes it a `cq` bug, Open CASCADE's error or a design;
- `arris_refusal` on a result with no refusal;
- a closed form that contradicts the measures, or that no measures can
  test.

It never raises otherwise. A verdict may replace any other class the rule gave: an
arris refusal of a part Open CASCADE builds wrongly is `occt_wrong` once a
closed form shows it. The row keeps the verdict beside the class.

**A row** (`FidelityRow`) carries the outcome (`agree`, `disagree` or
`unclassified`), the class, the refusal for `arris_refusal`, the verdict, the
deltas whenever both sides measured a shape (face counts carried, never
judged), both statuses, the program's SHA-256, and the versions each side
ran under (the result's arris, numpy and arris-gym; the oracle report's
cadquery, OCP and Python, absent where its worker never answered). A row
with a timeout on either side says so (`timed_out`), so a table counts
timeouts by name.

## Consequences

- An unclassified row stays unclassified until someone writes a verdict:
  a measure gap, the oracle failing alone, a timeout. Its evidence is
  committed, and a closed form is checked against the measures each time.
- `cq_bug` is the class for a `runtime` or `unsupported_api` on arris where
  the oracle builds the part. A refusal the subset raises on purpose is
  re-classed `by_design` with its anchor.
- Two failures agree whatever their messages. The kernels' words stay on the
  results, and the row compares statuses, never wording.
- A program that times out on one side is not judged on either. A corpus
  report names each such program instead.

## Alternatives considered

- **Classing a measure gap by default** as a `cq` bug (the youngest code):
  this hides every Open CASCADE error and every arris error that both
  kernels' agreement with a closed form would expose.
- **Both failures agree, crash included**: an arris crash where the oracle
  raises an ordinary exception would count as agreement. A crash is never
  an answer.
- **A verdict only where the rule leaves a row unclassified**: an arris
  refusal of a shape Open CASCADE builds wrongly would stay an arris refusal
  with no way to correct it.
- **A timeout classed as agreement when both sides time out**: a status
  that wall-clock time decides would then decide a class.

## Amendment (2026-11-21): an `unsupported_api` against an invalid shape is a `cq` bug

The row `unsupported_api` against an oracle `invalid` is `cq_bug`. The table's
row "`ok`, `syntax`, `runtime`, `unsupported_api`, `arris_refusal` against
`crash` or `invalid`: unclassified" no longer holds for `unsupported_api`
against `invalid`; every other pair of it stands.

`unsupported_api` declares that `cq` does not run the form, so it makes no claim
about the program. The oracle's checker failure cannot be what the two sides
disagree on: the row is a program the subset does not reach, exactly as against
`ok`. The original rule left `invalid` unclassified because an arris side that
tried the program may have answered rightly (a `runtime` on a degenerate
input), and that holds only for the statuses that ran it. In the subset the
row counts against the target, as an `unsupported_api` against `ok` does.
Only the comparer's `_oracle_broke` changes; no public type or signature does.

Consequences:

- BenchCAD's 168 `unsupported_api` rows against an `invalid` shape (57
  `worm_screw`, 6 `bolt` and 105 of other families) are `cq_bug` rather than
  unclassified. They stay outside the subset: reach and the in-subset class
  counts do not move.
- `unsupported_api` against `crash`, and `runtime` or `arris_refusal` against
  `crash` or `invalid`, stay unclassified.
- An `ok` against `invalid` row stays unclassified until a verdict. No
  BenchCAD row pairs them today. Of bundle 5's 136 out-of-subset rows, 105 are
  the `unsupported_api` rows above; the other 31 are sprockets whose oracle
  now ends `ok` (also `cq_bug`, ADR-0013's amendment). Bundle 5's plan classes
  them once the subset reaches each program.

## Amendment (2026-11-21): independent integration of CAD-Recode sketch measures

For the 18 CAD-Recode sketch rows in ADR-0023, an independent integral of
the oracle's planar and cylindrical trim curves can settle a discrepancy
in Open CASCADE's GProp volume, area or centroid. The integral uses Green's
theorem and the divergence theorem, evaluated at two resolutions that agree
within the existing agreement tolerance. Both builds succeed. The arris
measures agree with the integral, and the committed oracle measures differ
from it under ADR-0005. The oracle's tight bounds are used as a common check
against arris and provide no independent evidence about a bounds difference.

The verdict stores the measures as `ClosedForm` with the integration method
identified in its note. `compare` applies the same checks as for a measure
derived from construction. This evidence settles the measurement discrepancy
for the supplied boundary. A disagreement about the constructed geometry
still requires measures derived from construction or a second kernel.

## Amendment (2026-11-23): BenchCAD's boundary integrals and signed solids

**Independent boundary integration reaches BenchCAD.** The 2026-11-21
amendment's integral (Green's theorem along the oracle's trims, the
divergence theorem for the fluxes, two resolutions that agree inside
ADR-0005's tolerance) also settles a BenchCAD row whose part has planar,
cylindrical, conical or toroidal faces only. On a cone or a torus, the flux
primitive across the face from a fixed parameter to the trim is itself a
Gauss-Legendre quadrature. The same conditions hold: both builds succeed,
arris agrees with the integral, the committed oracle measures differ from
it, and the verdict is a `ClosedForm` whose note names the method. It
settles a mass-property error of Open CASCADE's on the boundary it built,
never a difference in what was built; `tools/cq_closed_forms.py
--blended-boundary STEM` writes it. A row a closed form from construction
reads takes that instead.

**Signed solids are evidence for `occt_wrong`.** On a row where arris
built a valid shape (`ok`) and the oracle's checker rejected its own
(`invalid`), the measures can agree while the oracle's shape holds a solid
turned inside out: its signed volume negative, its faces' normals pointing
in. GProp sums the signed volumes, so the aggregate matches arris, and a
`ClosedForm` has nothing to hold the oracle to. `SignedSolids` (a public
type of `fidelity`) carries each solid's signed volume of the oracle's
shape, from the boundary flux above, never from a kernel's mass
properties. `compare` raises `ValueError` unless the row is arris `ok`
against an oracle `invalid`, there is one volume per solid of the oracle's
shape, at least one is negative, their sum lies inside `VOLUME_REL` of the
oracle's volume and of arris's, and arris has one shell per positive solid.
`Verdict` admits it for `occt_wrong` alone; `tools/cq_closed_forms.py
--signed-solids STEM` writes it.

Consequences:

- BenchCAD's four `waffle_plate` rows that pair `ok` with `invalid` are
  `occt_wrong` by signed solids. Their reduced case is
  `regression/oracle-waffle-fillet-negative-solid`.
- A difference in what the kernels built still needs a closed form from
  construction or a second kernel.
- The Decision's evidence table also admits `SignedSolids` for `occt_wrong`
  alone. Its `ValueError` list includes signed solids that fail the checks
  above. The fixed-order volume sum must be finite.

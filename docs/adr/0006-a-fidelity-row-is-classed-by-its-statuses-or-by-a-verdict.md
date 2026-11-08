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
judged), both statuses and the program's SHA-256. A row with a timeout on
either side says so (`timed_out`), so a table counts timeouts by name.

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

# ADR-0016: A `cq` compound is one solid whose body holds a shell per piece

- Status: accepted
- Date: 2026-11-13
- Amends: ADR-0007's result rule (several solids `unsupported_api`) and
  ADR-0006's agreeing row (the oracle with exactly one solid)

## Context

ADR-0007 left a CadQuery **compound**, several solids that do not meet,
outside the subset: a `Workplane` holding several solids ended
`unsupported_api` "a Workplane holding `<n>` solids". Its `union` kept both
operands on the stack when `fuse` left more outer shells than one, and a
`cut` that split its base put one stack entry per piece. Five of the 37
programs CAD-Recode's subset reaches (validation stems `466`, `494`, `730`,
`786` and `936`) unite boxes that do not meet. The oracle builds each as a
compound of 2 solids (3 for `730`), so each row is an in-subset `cq_bug`
(plans/in-subset-cq-bugs step 8, `regression/cq-disjoint-union`). A compound
is a result, not a census form, so no form removal takes these programs out
of reach. In BenchCAD, 827 oracle `ok` reports hold 2 to 9 solids; today
each such row ends `unsupported_api` or `arris_refusal` under `cq` before it
reaches the result.

The question is what `cq` returns for a compound, and what such a result
measures and scores.

**What the oracle reports for a compound**, read with CadQuery 2.3.0 on
OCP 7.9.3 (`tools/oracle/worker.py`, `ok-compound-*`, `ok-cut-into-pieces`,
`ok-workplane-on-compound`). A `union` of disjoint solids returns one
`Compound` on the stack, as does a `cut` that splits its base; a later
`union` that meets both pieces makes one solid again (`ok-compound-bridged`).
Its report gives:

| Measure | For a compound |
|---|---|
| `volume`, `area` | the sums over its solids (`GProp`) |
| `faces` | the sum over its solids |
| `bounds` | the union of its solids' boxes |
| `solids` | one per piece; each solid has one shell (`TopExp_Explorer` on `TopAbs_SHELL`, a probe outside the worker) |
| `centroid` | the volume-weighted mean of its solids' centroids, except where Open CASCADE is wrong |

The report carries no shell count and no genus. In one construction,
`ok-compound-occt-centroid`, Open CASCADE's centroid is wrong. A 2 × 2 × 2
box centred on the origin is united with a 2 × 4 × 4 box centred on
(5, 0, 1). The closed form gives a centroid of (4, 0, 0.8), and arris gives
the same. The oracle reports (4.725, 0, 0.975). `BRepGProp::VolumeProperties`
with its default `OnlyClosed = false` gives this value for the compound in
that solid order. With the solids reversed, with `OnlyClosed = true`, or with
`GProp_GProps::Add` over the solids, it gives (4, 0, 0.8). Moving the first
box by 1 along x also gives the correct centroid. Of the seven two-box
compounds probed, this was the only wrong one; the five corpus programs and
the other fixtures here give the closed form.

CadQuery's `workplane()` on a stack holding a compound takes its
`Shape.Center()`, the centroid of all pieces, through `ProjectedOrigin`, as
for one solid (`cq.py`, `Workplane.workplane`; read on the oracle).
`union` and `cut` act on a compound as on a solid (`_findType` finds
`(Solid, Compound)`).

**What arris offers.** `fuse` of disjoint solids returns one `Solid` whose
body holds a shell for each piece, and `cut` returns its pieces the same
way. Such a body passes `check(body, "full")` and round-trips through
`write_body` and `read_body`. Its `mass_properties` gives the sums and the
volume-weighted centroid, and `bounds` gives the union. The Euler line gives
the shell count and a genus over all shells: two disjoint boxes give
V − E + F = 16 − 24 + 12 = 4 = 2 (shells − genus), so the genus is 0.
`interference`, `tessellate` and the face kinds read every shell.

## Decision

**A compound is one solid whose body holds a shell per piece.** Under `cq`,
`union`, the combining calls (`box`, `extrude`, `revolve`) and `cut` keep
whatever `fuse` or `cut` returns as the one solid on the stack, joined or in
pieces. A stack never holds more than one solid. A later call acts on all
the pieces at once, as CadQuery's does on its compound. `workplane()` on it
uses the body's centroid. The result resolves as ADR-0007 says, except that
its last row no longer exists:

| The value | Status |
|---|---|
| a `Workplane` with a solid on its stack, one piece or several | `ok` once the body worker accepts its body |

The other rows (no result, not a `Workplane`, no solid) are unchanged.
`unsupported_api` "a Workplane holding `<n>` solids" and
"Workplane.workplane on a Workplane holding `<n>` solids" are gone.

**It measures as any body.** The body worker reads the body back, checks
it and measures it as for one piece. Volume and area are the sums, the
centroid is volume-weighted, the bounds are the union, faces and face kinds
are counted over every shell, `shells` is one per piece (plus any cavity),
and the genus is the Euler line's over all shells. These are the oracle's
definitions for every figure it reports.

**It scores as any body, reward version 1 unchanged.** Each term is defined
on a body and reads every shell. The exact IoU is `interference` of the two
bodies. The sampled IoU uses the winding number on the whole mesh, and the
surface term draws its surface samples from all of it. `measures` uses the body's mass properties.
`topology` uses the face kinds of every face and the Euler genus. A
compound scored against itself is exactly 1.0. No formula, weight or
constant changes. A program that ended `unsupported_api` (−1.0) and now
builds a compound gets a score from the same formula as any other `ok`
result. This is the same as each lift of a form, so the reward's version
stays 1.
`score`'s target is a `BodyRef` and may be a compound too. A target read
from a STEP (`read_target`, ADR-0011) is still exactly one solid: the step
worker reads several solids, not one body, and fusing them would build a
part the oracle's STEP does not hold. That stays as ADR-0011 decided.

**A fidelity row agrees when the oracle's solids are one, or as many as the
result's shells,** and every judged measure is inside the agreement
tolerance (ADR-0005). This replaces ADR-0006's "the oracle with exactly one
solid". One oracle solid is judged by its measures alone, as before: a solid
with a cavity has two shells on both sides and one solid on the oracle's. A
compound whose pieces hold cavities has more shells than solids. Its row is
`unclassified`, never a false agreement, until a corpus shows one. The
oracle's wrong centroid makes a row `unclassified`, and a verdict
`occt_wrong` with the closed form classes it (ADR-0006).
`ok-compound-occt-centroid` holds the recorded report and that verdict.

## Consequences

- The five CAD-Recode programs end `ok` and agree with the oracle. Their
  shell counts equal the oracle's solids (2, 2, 3, 2, 2). The bounds delta
  is arris's padding of 2·10⁻⁷, and the other judged deltas are under 10⁻¹⁵. `regression/cq-disjoint-union`
  passes, and its strict `xfail` is lifted.
- `cq/unsupported-union-disjoint`, `unsupported-cut-into-pieces` and
  `unsupported-workplane-on-two-solids` become `ok-compound-two-boxes`,
  `ok-cut-into-pieces` and `ok-workplane-on-compound`. Each has a closed form
  and a recorded oracle report that agree.
- No committed row moves. No BenchCAD or C1 row has `cq` `ok` against an
  oracle holding several solids, so the agreement rule's change reclasses
  none. The slice's oracle reports all hold one solid, so the re-scored
  table is unchanged. Rows whose `cq` run reached the compound refusal move
  at the next corpus re-run, and the fidelity table says so.
- A corpus program that builds a compound reaches its oracle's centroid.
  Where Open CASCADE is wrong it is an `unclassified` row to judge, and the
  oracle worker is not changed: re-measuring with `OnlyClosed = true` could
  change committed oracle bytes for any compound row.
- A target STEP with several solids is still `runtime`. Re-scoring a corpus
  whose oracle builds compounds needs a decision about targets (BACKLOG).

## Alternatives considered

- **Keep ADR-0007 and name the five in the acceptance** (Q4 option b): the
  oracle's part is unambiguous, arris's `fuse` already builds it, and every
  corpus that writes disjoint unions would carry the gap.
- **Several solids on the stack, resolved by fusing at the end**: CadQuery
  holds one `Compound` object. A later call on several entries would need
  its own rule for each call, and `workplane()` would need the combined
  centroid anyway.
- **Compare the oracle's solids with arris's outer shells** (shells that
  enclose volume, by the sign of a tessellated volume): it is exact for a
  compound with cavities. But it needs a new measure on every result, a
  public type change that moves every result digest, for a case no corpus
  shows.
- **Re-measure on the oracle with `OnlyClosed = true`**: it fixes the
  centroid, but it changes the oracle's committed bytes for BenchCAD's
  compound rows. That is a change of the oracle with its own plan, not part
  of this decision.

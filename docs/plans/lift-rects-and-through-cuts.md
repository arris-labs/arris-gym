# Plan: lift-rects-and-through-cuts

- Started: 2026-11-21
- Milestone: C2, bundle 5, first of two plans (docs/ROADMAP.md §C2; ADR-0014's amendment of 2026-11-22)
- Idea: none; verbatim from the human: "/plan BenchCAD bundle 5"

## Goal
`cq` runs CadQuery 2.3.0's `cutThruAll()`, `rect(num, num)`, `center(num, num)`
and `slot2D(num, num, num)` on the stacks BenchCAD writes them on. BenchCAD's
reach goes from 9,998 to 14,150 of 17,900 (79.1%), with zero in-subset
`cq_bug`, zero `by_design` and zero unclassified rows. CAD-Recode stays at
968/968 and its table stays byte-equal.

## Non-goals
- Plan 2 of bundle 5, `lift-lofts-and-tapers`: `loft(combine=)`, `extrude(taper=)`, `mirrorY()`
  (+1,568 programs, to 15,718: past T = 15,215). OCCT's loft section correspondence is its unproven semantic.
- `cutThruAll(clean=, taper=)`, `rect(centered=)`, `slot2D` with two arguments: no corpus program writes them.
- `shell(num)` and the rest of the tail. The `YZ`/`XY`/`XZ` face selectors.
- The table digest across architectures (C2's accept line), checked when C2 closes.

## Design deltas
**Reach** (committed census rows, 2026-11-21): the four forms take BenchCAD
from 9,998 to 14,150; dropping any one loses 623 (`slot2D`) to 2,881
(`rect`). The chains written: `workplane → center → rect → cutThruAll`,
`rarray | pushPoints → rect → extrude | cutBlind | cutThruAll`, and
`circle | close | slot2D → cutThruAll`.

**A. `cutThruAll()`** finds the chain's solid first, then sweeps each
profile past the stock's projected bounds and cuts once (ADR-0024 §A).
It cuts from inside or outside the stock, handles a miss, overhang or
compound, and reports `runtime` for a circular ring as the oracle does.

**B. Profiles at points** (ADR-0024 §B, amending ADR-0018 rule 5).
`_Discs` becomes an ordered collection of placed circles, rects or slots.
Rectangles and slots take their polar points' rotations. Strictly nested
rects or a centred rect and circle form one section with a hole, in either
order. Test containment from the section shapes. Edge-sharing and
overlapping rectangles fuse or cut as a union. Corner-only contact can
give an arris refusal.

**C. `center(x, y)`** moves the plane's origin in its current axes, keeps
the chain's solid and gives the stack one point at the new origin. Offsets
accumulate. Carry pending wires in their original placements (ADR-0024 §C).

**D. `rect(xLen, yLen)`** places a rectangle at the origin, a `moveTo` or
`center` point, or each point on a point stack. Use absolute dimensions.
The pinned kernel refuses a zero dimension when consuming the wire
(ADR-0024 §D).

**E. `slot2D(length, diameter, angle)`** uses the same placement as D,
with its angle in degrees. For positive sizes, equal length and diameter
give `runtime`. A shorter length gives the kernel's `SketchError`
(`arris_refusal`) (ADR-0024 §E).

**F. Public surface.** `cq.subset()` gains the four declarations (doctest
43 → 47). No public type or signature changes; `cq` imports only `arris`;
the frozen C1 subset in `tests/fixture_cases.py` stays without them.

**Unsupported-example hits.** `tests/test_cq_calibration.py:52` holds
`agree-revolve-torus` to `unsupported_api` `"Workplane.center"`. Step 4
moves it to `None`, which is its closed form. `agree-cylinder-offset` stays
`"cq.Workplane()"`. No fixture holds `rect`, `slot2D` or `cutThruAll` as
unsupported, because the sketch fixtures' `rect` is `Sketch.rect`.

**Glossary.** Step 2 sharpens **Stack**: `rect` and `slot2D` take a stack of
points as `circle` does; `center` leaves one point.

## Steps
Grades are tiers (`.agents/tiers.md`):
- **[1]** routine: the design says what to write, and the tests are mechanical.
- **[2]** careful: a numeric, geometric or semantic case within this design.
- **[3]** unproven: a CadQuery semantic established here.

- [x] Step 1 **[3]**: `tools/cq_profile_probe.py` (the pattern of
  `tools/cq_array_probe.py`) writes `tests/fixtures/profiles/constructed.json`
  and its README, each case with a closed form: delta A's five cases plus a
  ring, a closed path and circles and rects at points; delta B's nestings
  and touching or overlapping rects; delta C's cases; delta D's and E's sizes,
  `slot2D` at 0, 45 and 90 degrees. `tests/test_profile_probe.py` holds each
  report to its closed form.
- [x] Step 2 **[3]**: ADR-0024 settles deltas A to E from step 1's records.
  It amends ADR-0018 rule 5, amends ADR-0014 to name the split of bundle 5,
  and sharpens **Stack**. Doc only.
- [x] Step 3 **[2]**: `cutThruAll()` on today's profiles: circle, ring,
  circles at points, polygon and closed path (delta A). Each `ok`,
  `runtime` and `unsupported_api` case for these profiles gets a fixture
  in `tests/fixtures/cq/`. Include a plane farther from the stock than its
  box diagonal and hold the side bore to its closed form. Property
  (`hypothesis`): a circular window cut through a W×H×T box at a random
  centre inside it removes πr²T. CHANGELOG bullet.
- [ ] Step 4 **[1]**: `center(x, y)` (delta C). Fixtures: a centred circle
  extruded, centre twice, centre then `rarray` bored, centre on a face
  workplane, centre after a point or point stack, and pending wires
  consumed directly or after drawing a second wire. `agree-revolve-torus`
  moves to `None`. CHANGELOG bullet.
- [ ] Step 5 **[2]**: `rect(xLen, yLen)` on every stack D names. `_Discs`
  becomes placed profiles. Fixtures: `extrude`, `cutBlind` and `cutThruAll`
  of a rect, rects at points including rotated polar points, contact and
  overlap, both orders of the nestings in ADR-0024, and size refusals.
  Record through-cut outcomes for the new nests. Property: axis-aligned
  rects on an integer grid extrude to exact union area times |d|, including
  n·|w·h·d| for disjoint rects. Two rects meeting only at a corner exercise
  the kernel's typed refusal. CHANGELOG bullet.
- [ ] Step 6 **[2]**: `slot2D(length, diameter, angle)` (delta E) on the
  same stacks. Fixtures: angles 0, 45 and 90; at points; through-cut; and
  `length <= diameter`. Property: volume ((L−D)·D + πD²/4)·|d| for any
  angle. An offline reach test over the committed census rows gives
  14,150/17,900 for BenchCAD and 968/968 for CAD-Recode. CHANGELOG bullet.
- [ ] Step 7 **[3, conductor-run]**: re-run BenchCAD under `cq` against the
  committed oracle rows (`tools/cq_corpus.py --corpus benchcad`, a fresh
  `--work-dir`). Class every new in-subset disagreement. A `cq` fault is
  shrunk to a fixture and fixed, and its commit carries the suffix of the
  step whose work it repairs. Otherwise give it a closed-form verdict
  (`tools/cq_closed_forms.py`), or file an arris refusal or bug in
  `../arris/docs/ideas/`. Commit the table, the reports, `reach-report.json`
  and the README figures.
- [ ] Step 8 **[1, conductor-run]**: re-run CAD-Recode. Its table digest
  (`fe2861b7…`) and reach report must be byte-equal, and the README names the
  re-run.

## Acceptance
- `tests/fixtures/profiles/constructed.json`, the new `tests/fixtures/cq/`
  fixtures and the properties of steps 3, 5 and 6 pass under the gate.
- BenchCAD, each figure over all 17,900 programs: reach 14,150; in-subset
  `cq_bug` 0, `by_design` 0, unclassified 0 (in and out of the subset),
  timeouts 0. Agreement is reported, not targeted. The census digest
  (`043db6d9…`) is unchanged.
- CAD-Recode: reach 968/968 and table digest `fe2861b7…`, both unchanged.

## Docs to update on completion
- `docs/ARCHITECTURE.md` §Dialects: the subset list, plus a paragraph each for `cutThruAll` and profiles at points.
- `docs/ARCHITECTURE.md` §Fidelity: BenchCAD's figures.
- `docs/ROADMAP.md` §C2 status: bundle 5's first plan done, `lift-lofts-and-tapers` next.
- `AGENTS.md` current state.
- `GLOSSARY.md`: **Stack** (step 2).
- `CHANGELOG.md`: bullets from steps 3 to 6. No reward moves.

## Open questions
- *Settled* in ADR-0024 from `tests/fixtures/profiles/README.md` and
  `constructed.json`. Through cuts span the stock in both directions.
  Nested wires make holes, and the equal and short slot sizes have
  different typed outcomes. `center` preserves pending wires.
- *Settled* in ADR-0024 §B. The rectangle property asserts union volume
  for shared edges and overlaps because both engines build those unions.
  The corner-only case asserts the pinned kernel's actual refusal.
- ⚠ OPEN: the oracle's side bore exceeds the agreement tolerance
  (`regression/oracle-cut-thru-all-side`, strict `xfail`). ADR-0024 §A
  records the evidence. Step 7 checks whether a corpus row needs a
  closed-form verdict for this measure error.
- ⚠ OPEN: CadQuery leaves the stock uncut with the profile 40 units above
  its face (`regression/oracle-cut-thru-all-far`, strict `xfail`). Arris
  matches the full-sweep closed form. Step 7 checks the corpus for this
  discrepancy as well as the side bore's measure error.
- *Settled* in step 3. The report check uses the bundle 4 subset that
  produced the committed reports until step 7 replaces them. The live
  subset's reach is checked separately (10,878 BenchCAD rows after step 3).
  The historical selector probe also excludes the new forms so it still
  reproduces its original 950 rows.
- *Settled* in ADR-0014's amendment of 2026-11-22. Bundle 5 is two plans,
  with the BRepFeat through cut and the larger projected reach gain first.
- Step 7, by the agent: a `cq` fault needing a semantic ADR-0024 lacks
  becomes a new step here; never a left `cq_bug`, never a narrowed subset.

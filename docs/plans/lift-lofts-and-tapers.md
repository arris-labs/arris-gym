# Plan: lift-lofts-and-tapers

- Started: 2026-11-25
- Milestone: C2, second half of BenchCAD bundle 5 (`docs/ROADMAP.md`)
- Decision: ADR-0014, amendment of 2026-11-22

## Goal

Complete bundle 5 by lifting `loft(combine=bool)`, `extrude(num; taper=num)`
and `mirrorY()` on arris 0.12.0. With the gear loft deferral settled in
Step 7, the census puts 15,326 of 17,900 BenchCAD programs in-subset,
above the 15,215 target. Verify fidelity
on both full corpora with zero in-subset `cq_bug`, unclassified rows or timeouts.

## Non-goals

`shell` and the rest of the tail, the C2 cross-architecture digest check,
an arris bump, reward changes and general CadQuery context emulation.
`loft` with `ruled=`, `clean=` or string combine modes, taper on cuts or
with `both=`, and solid mirroring belong to other API forms.

## Design deltas

- §Dialects gains `Workplane.loft(self, *, combine: bool = True) -> Workplane`,
  `Workplane.mirrorY(self) -> Workplane` and
  `Workplane.extrude(self, distance: float, both: bool = False, *, taper: float = 0.0) -> Workplane`.
  `loft()` uses the same default as `loft(combine=True)`. Declare the forms
  through `census_form`. Match the `both=` and `taper=` keyword sets
  independently in runtime and static checks. No execution result types or
  imports change.
- `ProgramCensus.deferred_polygon_loft` and `Subset.defer_polygon_lofts`
  record and apply the literal-chain exclusions in the amendment to
  ADR-0012. Historical declarations retain their original reach.
- `workplane(offset=…)` and `transformed(…)` carry a single closed disc,
  rectangle or polygon/path wire in its original world placement. Reuse the
  ordered `_carried` representation from ADR-0024. Preserve the active plane,
  including the oracle's parent-face frame and projected origin rules. Read
  these sections in drawing order. A consuming call clears them on its result
  and keeps the parent chain and the nearest solid lookup (ADR-0007).
- The pinned wheel offers `Sketch.loft` and `Model.loft` in `smooth` and
  `ruled` modes. CadQuery defaults to smooth, with its own section
  correspondence. ADR-0026 records the verified kernel construction and any
  required correspondence, placement, consumption and combine rules. A
  ruled or analytic path needs geometric evidence of equivalence for that case.
- Nonzero taper drafts the side surfaces by a signed angle in degrees. Probe
  cap placement and signed offsets on discs and rectangles, including the
  negative-height `tee_nut` tools and the two drafted operations in `knob`.
  Use analytic conical or planar geometry where verified. Check `taper=0`
  against the existing extrusion path, and use the oracle for invalid inputs.
- `mirrorY()` reflects pending edges in local x about the workplane's y axis.
  Join the original and reflected paths in deterministic order, preserving
  arcs and reusing the existing closed-profile route. Prove endpoint rules
  for the half outlines of `gusseted_bracket` and `i_beam` (ADR-0028).

Affected examples and fixtures by step

- Step 2 moves the closed-wire `transformed` cases in
  `tests/test_cq.py::test_a_call_that_would_drop_a_pending_wire_is_unsupported`
  and `cq/unsupported-transformed-on-pending-wire`. Check the recorded
  `one` and `many` `workplane` and `transformed` contexts in
  `tests/fixtures/profiles/{rect,slot}-contexts.json` and `test_profile_probe.py`.
  Update each admitted case with its oracle evidence. The `moveTo` fixture
  `cq/unsupported-workplane-on-pending-wire` and the multi-point case in
  `test_cq_point_contexts.py` are outside the single closed-wire lift.
- Step 3 changes the unsupported name in `sandbox/unsupported-api` (program
  and message) and the `UnsupportedApi` message assertion in `test_outcome.py`.
- Step 4 replaces `taper=5` in `tests/test_cq.py`'s wrong-form table,
  form-before-stack test and `BAD_CALLS`, and updates the reach expectations
  in `test_reach.py` and `test_cq_extrude_both.py`. Keep the extrusion
  declaration in the historical selector probe fixed. The census-only `taper=None`
  example and `cutThruAll(taper=2)` still describe other forms. Update
  §Dialects' extrusion and pending-wire text in the corresponding lift commits.

## Steps

**[1]** routine, the design specifies the change and checks. **[2]** careful,
a numeric, geometric or semantic case within a given design. **[3]** unproven,
a kernel construction or CadQuery semantic to establish. Grades map to tiers.
**[conductor-run]** runs in the background through the conductor.

- [x] Step 1 **[3]**. Compare constructed lofts through both workers. Start
  with two and three sections, asymmetric rotated rectangles and tooth
  polygons with shifted starts and reversed winding. Check `bevel_gear`,
  `helical_gear` (two and three sections), `propeller`, `tapered_boss`,
  `twisted_bracket` and `wing_nut` against pinned oracle reports. Write
  ADR-0026 and numerical fixtures. Check build time against the corpus deadline.
- [x] Step 2 **[3]**. Carry the pending sections through `workplane` and
  `transformed`. Verify their world placement, order, branch independence
  and stock lookup with `hypothesis` and oracle cases on offset and rotated
  frames, including the face-based `propeller` chain. Move affected fixtures.
- [x] Step 3 **[3]**. Lift `loft` using the verified construction. Cover
  no sections, one section, both combine values with stock, wire consumption,
  and a later `faces(">Z").workplane()`. Add a frustum property over radii,
  heights and frames. Pin the declarations for the historical C2 table.
  Filter new forms out of `c1_subset()` as each lift lands.
- [x] Step 4 **[3]**. Verify taper sign, cap height, collapse and inner-wire
  behaviour on the oracle and record the decision in an ADR. Lift `taper=`,
  check both signs of height and angle, stock fusion, zero equivalence and
  wrong forms. Add `hypothesis` checks for circular and rectangular drafts.
- [x] Step 5 **[3]**. Lift `mirrorY()` using the oracle's wire-joining rule.
  Verify a half outline with axis endpoints, a reflected arc and the oracle's
  outcome for unjoinable endpoints. Record the rule in an ADR and add a
  `hypothesis` property over reflected half outlines, extrusion height and planes.
- [x] Step 6 **[2] [conductor-run]**. Replay BenchCAD against the pinned
  `--oracle-rows`. Diff the full table from the 0.12.0 baseline. Reproduce
  each new failure cause using a stem slice, shrink it with `inspect` and
  record the desired outcome in a regression fixture.
- [x] Step 7 **[3]**. Resolve the replay's `cq_bug` and unclassified rows.
  Check analytic rows by closed form and freeform gaps by independent boundary
  integration or a second oracle under ADR-0006. Bind verdicts to evidence,
  check representative stems and record kernel limits in the arris report.
- [x] Step 8 **[2] [conductor-run]**. Replay both full corpora from fresh
  work directories using the checked verdicts and pinned oracle rows. Commit
  the verified BenchCAD artefacts and matching assertions. Confirm CAD-Recode
  reproduces its committed table and reports. Record counts and digests.

## Acceptance

- Run `tools/gate.sh`. The main fixtures include a circular frustum with
  radii 2 and 1 and height 3 (volume `7π`, axial centroid `33/28`), a
  square draft from side 4 to side 2 and height 2 (volume `56/3`), and a
  2 × 3 half rectangle reflected and extruded by 4 (volume `48`, centroid
  `(0, 1.5, 2)` in local coordinates). Each is `ok` with one solid. Check
  area, bounds and placement as well as the three `hypothesis` properties.
- Each lift checks live reach in `test_c2_baseline.py` (15,142 after loft,
  15,453 after taper, 15,718 after mirror, 15,326 after the approved gear
  deferral). Check the historical committed
  report with its pre-lift declarations from Step 3 until Step 8 replaces it.
- Run `uv run --locked --extra corpus tools/cq_corpus.py` per corpus using
  its fixture README arguments. Check 17,900 and 968 rows, zero unclassified,
  in-subset `cq_bug` and timeouts, and only ADR-0025's two in-subset
  `by_design` rows. CAD-Recode reproduces 968 in-subset and 893 agreements.
  Report all-program agreements and each changed class.
  Verify pinned oracle bytes, the census digests and replay digests.

## Docs to update on completion

- `docs/ARCHITECTURE.md` §Dialects and §The oracle, `GLOSSARY.md` Stack,
  `PROVENANCE.md` (CadQuery's `cq.py` and `occ_impl/shapes.py`), ADR index,
  fixture READMEs and consumer-visible bullets in `CHANGELOG.md` under Unreleased.
- `docs/ROADMAP.md` §C2, `AGENTS.md` Current state and `docs/BACKLOG.md`
  pending-wire limits and any findings. File demonstrated arris capabilities
  or defects through `../arris/docs/ideas/` with their fixture paths.

## Open questions

- **Settled, Step 1 (ADR-0026).** Use the pinned smooth loft with paired
  world-placed sections. The two-section constructions agree after pairing.
  The three-section polygon fixtures show an interpolation gap and the
  sampled gears exceed the 30 s deadline. The 93 three-section helical
  gears are among 392 projected gear rows to verify. With all 392 deferred,
  the projected all-lifts reach would be 15,326/17,900. The reduced loft
  and timing evidence are filed with arris. The plan's acceptance stands.
- **Settled, Step 2 (ADR-0026).** Plane changes carry one closed disc,
  rectangle, polygon or path at a time. The oracle probes support a
  through-cut along the drawing normal even after a tilt. Linear sweeps
  use the active normal and refuse a differing one. Revolution requires
  the axis to lie in the drawing plane. The existing consumers refuse
  multiple sections carried across plane changes.
- **Settled, Step 3 (ADR-0026).** Match circle starts even when the second
  frame rotates in-plane. The largest agreeing polygon probe has 48
  nonplanar sides. Use that count as the current limit. The sampled
  144- and 196-sided gears now reach a typed refusal, as does the
  three-section interpolation case. Their static reach and acceptance
  stay in force for replay and resolution.
- **Settled, Step 7 (ADR-0012 and ADR-0026).** The replay confirmed 299 gear lofts hit the
  curved-side guard and 93 hit the three-section guard. The measured
  prefixes and the interpolation regressions block a lift on arris
  0.12.0. The human approved deferring these contexts. Literal polygon
  chains excluded by the census account for exactly the 392 gear rows.
  Static reach is 15,326/17,900, above the 15,215 target.
- **Settled, Step 4 (ADR-0027).** CadQuery takes a slant length for nonzero
  taper. Use its sine and cosine projections. Circles form cones, inward
  rectangles have planar sides, and outward rectangles have rounded corners.
  Circular collapse agrees at the apex. For rectangular collapse use the
  exact ridge or pyramid and retain the oracle gap in strict regressions.
  The closed-form acceptance fixtures use slant lengths √10 and √5 for
  axial heights 3 and 2.
- **Settled, Step 5 (ADR-0028).** The oracle joins line-wire endpoints
  at a reflected gap of 1e-7. Snap horizontal ends to the axis within
  that limit. Curved or sloped ends already on the axis join exactly.
  Merge straight joins across the axis for the cleaned prism. A loft
  through the simplified wire refuses because the oracle keeps those
  vertices in its loft.
- **Settled, Step 7 (ADR-0006).** Integrating the placed blade prisms and
  hub gives independent measures for the eight propellers whose oracle
  trims were inconclusive. The four-blade regression uses the constructed
  geometry as its expected result and keeps the earlier trim integral
  alongside it. On three intersecting-flute knobs the construction
  establishes a volume gap on both sides. Their `arris_bug` verdict cites
  the regression that checks both gaps. ADR-0005's tolerance stands.

## Replay evidence for Steps 6 and 7

The 17,900-program replay used the committed oracle bytes and retained
static reach at 15,718. Before new verdicts it gave 12,523 agreements,
392 in-subset `cq_bug` rows (189 bevel gears and 203 helical gears),
227 unclassified rows and three candidate timeouts in
`double_simplex_sprocket`. Its table digest was
`e0ffad652b48c94541d96ef30e1606b15851991c4886598710561e087ccb0feb`.
A one-worker replay recovered two sprockets at 30 s, and a separate
isolated run recovered the third, `double_simplex_sprocket_011623_s20260505`,
at the same deadline. The full replay still records its three timeouts.
The verdict files record separately checked analytic, boundary-integral
and regression evidence for the new rows.
The Step 7 replay of the 1,568 affected stems checks all 227 new verdicts,
pins the same oracle rows and records zero unclassified rows, zero
timeouts and zero in-subset `cq_bug` rows. Its digest is
`eebe8e17988287db6e6000202b74e52a439b7db638915a8291c3445a86b39a96`.

## Full-corpus replay evidence for Step 8

Both corpora ran from fresh work directories with their checked verdicts.
Both reproduced the pinned oracle bytes, aggregate census and per-program
census rows. Each has zero unclassified rows, zero in-subset `cq_bug` rows
and zero timeouts. The two BenchCAD `by_design` rows use ADR-0025.

| Corpus | Reach | Agreements | Fidelity table digest |
|---|---:|---:|---|
| BenchCAD | 15,326/17,900 | 12,523 | `aa4fb6b6ea89276adc2c55b177e7b1a1bb1e31b42683dc79ceff0b7e673b94dd` |
| CAD-Recode | 968/968 | 893 | `7cc30ad7c343342e6763224b231790dd9de5f2954d2b7bac3693522dc1246b92` |

BenchCAD changes 1,176 rows from `cq_bug` to 832 agreements, 129
`arris_refusal`, 51 `arris_bug` and 164 `occt_wrong`. CAD-Recode reproduces
the fidelity table, reach report and both arris reports byte-for-byte.
The fixture READMEs record the oracle and census digests and replay commands.
[BenchCAD](../../tests/fixtures/c2/benchcad/README.md),
[CAD-Recode](../../tests/fixtures/c2/cadrecode/README.md).

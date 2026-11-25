# Plan: lift-lofts-and-tapers

- Started: 2026-11-25
- Milestone: C2, second half of BenchCAD bundle 5 (`docs/ROADMAP.md`)
- Decision: ADR-0014, amendment of 2026-11-22

## Goal

Complete bundle 5 by lifting `loft(combine=bool)`, `extrude(num; taper=num)`
and `mirrorY()` on arris 0.12.0. The committed census projects 15,718 of
17,900 BenchCAD programs in-subset, above the 15,215 target. Verify fidelity
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
  independently in runtime and static checks. No result types or imports change.
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
  for the half outlines of `gusseted_bracket` and `i_beam`.

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
  in `test_reach.py` and `test_cq_extrude_both.py`. The census-only `taper=None`
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
- [ ] Step 3 **[3]**. Lift `loft` using the verified construction. Cover
  no sections, one section, both combine values with stock, wire consumption,
  and a later `faces(">Z").workplane()`. Add a frustum property over radii,
  heights and frames. Pin the declarations for the historical C2 table.
  Filter new forms out of `c1_subset()` as each lift lands.
- [ ] Step 4 **[3]**. Verify taper sign, cap height, collapse and inner-wire
  behaviour on the oracle and record the decision in an ADR. Lift `taper=`,
  check both signs of height and angle, stock fusion, zero equivalence and
  wrong forms. Add `hypothesis` checks for circular and rectangular drafts.
- [ ] Step 5 **[3]**. Lift `mirrorY()` using the oracle's wire-joining rule.
  Verify a half outline with axis endpoints, a reflected arc and the oracle's
  outcome for unjoinable endpoints. Record the rule in an ADR and add a
  `hypothesis` property over reflected half outlines, extrusion height and planes.
- [ ] Step 6 **[2] [conductor-run]**. Replay BenchCAD against the pinned
  `--oracle-rows`. Diff the full table from the 0.12.0 baseline. Reproduce
  each new failure cause using a stem slice, shrink it with `inspect` and
  record the desired outcome in a regression fixture.
- [ ] Step 7 **[3]**. Resolve the replay's `cq_bug` and unclassified rows.
  Check analytic rows by closed form and freeform gaps by independent boundary
  integration or a second oracle under ADR-0006. Bind verdicts to evidence,
  check representative stems and record kernel limits in the arris report.
- [ ] Step 8 **[2] [conductor-run]**. Replay both full corpora from fresh
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
  15,453 after taper, 15,718 after mirror). Check the historical committed
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
- ⚠ OPEN: Agent, Steps 3 and 7. Which gear lofts can meet the corpus
  deadline and fidelity criteria? Verify before enabling a path that
  depends on the missing interpolation or performance capabilities.
  Continue the independent lifts and bring any change to C2 scope to the
  human.
- ⚠ OPEN: Agent, Step 4. Which signed drafts and limiting inputs need
  distinct constructions? Any new numeric threshold is measured by Step 4.
- ⚠ OPEN: Agent, Step 5. When does the oracle join reflected endpoints?
  Any join tolerance is measured by Step 5.
- ⚠ OPEN: Agent, Step 7. Which freeform disagreements need independent
  measures, and which need a second oracle? Keep ADR-0005's tolerance.

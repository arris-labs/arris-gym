# Plan for `lift-shell`

- Started 2026-11-26
- Milestone C2, first BenchCAD tail item ([roadmap](../ROADMAP.md#c2--the-fidelity-gate))
- Decision in [ADR-0014](../adr/0014-the-fidelity-target-is-a-reach-of-85-percent-on-benchcad-and-all-of-cad-recode.md)

## Goal

Lift `Workplane.shell(num)` on arris 0.12.0. Adding that one declaration to the
committed census admits 330 BenchCAD programs, 174 `enclosure` and 156
`sheet_metal_tray`, raising reach to 15,656/17,900. All 330 select one end
face using `>X`, `>Y` or `>Z` and pass a negative literal. Verify the lift on
both full corpora with zero unclassified rows, in-subset `cq_bug` rows and
timeouts. CAD-Recode writes no `shell` calls and keeps reach at 968/968.

## Non-goals

Explicit `kind` arguments, new selector strings, the remaining tail, an
arris bump, changes to scoring, and C2's cross-architecture digest check.

## Design deltas

- §Dialects gains `Workplane.shell(self, thickness: float) -> Workplane`.
  `census_form` declares one positional `num`. Reuse the nearest solid
  lookup and the current stack's `Faces` groups under ADR-0022. Pass their
  constituent kernel faces in deterministic order. CadQuery reads only
  faces on the current stack when choosing openings. Return one solid on
  the same plane with the caller as its parent. Check that prior selections
  still work on their own branches and that later selectors see the new
  body's faces and edges. The method lives in `cq` and calls `arris.build`.
  [CadQuery 2.3.0 `Workplane.shell`](https://github.com/CadQuery/cadquery/blob/2.3.0/cadquery/cq.py#L1201-L1234)
- The pinned wheel offers `Solid.shell(openings, thickness, side)` with a
  positive magnitude and sharp joins. CadQuery uses signed thickness and
  defaults to arc joins, which can round corners. Establish where the sharp
  construction agrees by geometry and measures before routing the call.
  Verify the empty opening list, which CadQuery uses to create a sealed
  cavity, and the compound behaviour before committing either rule.
  [Pinned wheel API](../ARRIS_API.md)
  [CadQuery 2.3.0 solid shell](https://github.com/CadQuery/cadquery/blob/2.3.0/cadquery/occ_impl/shapes.py#L2697-L2753)
- ADR-0029 records the supported geometry, signed thickness and join rules,
  selection and stack behaviour, and outcomes for missing stock, zero and
  non-finite thickness. Preserve the kernel's refusal kind and message.
  A sharp shell requires evidence of equivalence in a context where the
  default join could be rounded. Any proposed static deferral needs proof
  under ADR-0012 and a revised reach assertion before it lands.
- Step 2 moves the `Workplane.shell` unsupported example to `Workplane.text`
  in `tests/fixtures/sandbox/unsupported-api/{program.py,expected.json}` and
  `tests/test_outcome.py::test_the_exceptions_are_exported`.
  Update the form count in `cq/_subset.py`'s doctest. Exclude the new form
  from `c1_subset()` and check the committed C2 reach report with the
  pre-lift subset until Step 5 replaces the report.

## Steps

**[1]** routine, the design specifies the change and checks. **[2]** careful,
a numeric, geometric or semantic case within a given design. **[3]** unproven,
a kernel construction or CadQuery semantic to establish. Grades map to tiers.
**[conductor-run]** runs in the background through the conductor.

- [x] Step 1 **[3]**. Compare `Solid.shell` in the `arris` dialect with the
  oracle before declaring the form. Start with the inward offset of a
  chamfered tray rim. Derive its opening and wall offsets from the stock's
  planes and probe a tray prefix in each of `XY`, `XZ` and `YZ`. Use an
  inward box, adjacent and empty openings, and an outward box to check
  joins and topology. Probe compounds and failure outcomes. Commit the
  numerical fixtures and ADR-0029, with reduced regressions for gaps.
- [x] Step 2 **[2]**. Add the decorated method, runnable docstring and
  fixtures for the verified semantics, wrong forms and missing stock. Add
  a `hypothesis` property over inward box dimensions, thickness, named
  planes and branch reuse. Check 15,656/17,900 and the exact new stem counts
  in `test_c2_baseline.py`. Move the affected examples in this commit.
- [ ] Step 3 **[2] [conductor-run]**. Replay the 330 newly admitted stems
  with `tools/cq_corpus.py --slice` and the pinned `--oracle-rows`. Keep the
  counts for enclosure fillets and bore arrays, and tray rim chamfers,
  floor holes and through-cut slots, including all 101 pre-shell chamfers.
  Reduce new failure causes with `inspect`. Commit strict `xfail` fixtures
  with the desired outcomes and record which causes each fixture explains.
- [ ] Step 4 **[3]**. Resolve the new `cq_bug` and unclassified rows. Check
  disputed measures by construction, independent boundary integration or
  a second oracle under ADR-0006. Bind verdicts to the evidence, test
  affected stems in small slices and record kernel limits in the arris report.
- [ ] Step 5 **[2] [conductor-run]**. Replay both full corpora with all
  checked verdicts and pinned oracle rows from fresh work directories.
  Commit the verified BenchCAD reports and matching assertions. Verify the
  CAD-Recode reports reproduce and record both fidelity table digests.

## Acceptance

- `tools/gate.sh` checks the fixture and property tests. A centred
  `10 × 8 × 6` box shelled inward by 1 with `faces(">Z")` has status `ok`,
  volume 240, area 516, centroid `(0, 0, -0.5)`, 11 faces, one shell and
  one solid. With an empty opening list the same box has volume 288,
  area 584, centroid `(0, 0, 0)`, 12 faces, two shells and one solid.
  Both keep the box bounds. A through bore of radius 1 in the open box's
  floor gives volume `240 − π` and area 516 on one solid. Check the
  chamfered opening and selected face as well as the final body measures.
- Run `uv run --locked --extra corpus tools/cq_corpus.py` with the fixture
  README arguments and any new checked verdicts. Require all 17,900 and
  968 rows, reach 15,656 and 968 respectively, zero unclassified, in-subset
  `cq_bug` and timeouts, and only ADR-0025's two `by_design` rows. Record
  agreement and changed classes for the 330 stems. Check the BenchCAD rows
  outside those stems against the baseline and account for any differences.
  Verify the pinned oracle bytes and census digests and reproduce the
  CAD-Recode fidelity table and reports at 893 agreements.
  [BenchCAD](../../tests/fixtures/c2/benchcad/README.md)
  [CAD-Recode](../../tests/fixtures/c2/cadrecode/README.md)

## Docs to update on completion

- §Dialects and §The oracle in `docs/ARCHITECTURE.md`, the Stack entry in
  `GLOSSARY.md`, the ADR index, and `PROVENANCE.md` for the CadQuery source
  consulted. Update the fixture READMEs with measures, replay commands,
  digests and BenchCAD attribution where applicable.
- §C2 in `docs/ROADMAP.md`, Current state in `AGENTS.md`, and findings in
  `docs/BACKLOG.md`. Add an Unreleased bullet to `CHANGELOG.md` in the lift
  commit. File demonstrated kernel needs in `../arris/docs/ideas/` with
  the fixture paths.

## Open questions

- Settled in Step 1 ([ADR-0029](../adr/0029-a-cq-shell-uses-sharp-offsets-where-arc-joins-stay-sharp.md)).
  The inward sharp construction matches the tray rims, the box openings
  and sealed cavity, and the open cylinder. The default outward arc and
  inward reentrant arc differ from sharp joins. Compounds and already
  sealed stock give runtime failures on the oracle. The three tray
  prefixes meet the construction and STEP remeasurement under ADR-0005,
  with oracle volume discrepancies reproduced by a reduced regression.
  Preserve the 330-stem replay and classify supported verdicts in Step 4
  with the closed-form evidence. The agreement tolerance stays in force.
- ⚠ OPEN: The agent decides in Step 4 whether any follow-on differences
  belong to `cq`, arris or the oracle. Use the reduced cases and verified
  measures to decide without changing ADR-0005's agreement tolerance.
- Settled in Step 2. CadQuery retains pending wires after a shell. The
  subset refuses a visible pending wire or drawn path, where replacing
  the stack would discard it. The
  [blind-cut regression](../../tests/fixtures/regression/shell-pending-wire/)
  keeps the expected geometry.

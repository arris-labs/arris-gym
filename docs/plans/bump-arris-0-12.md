# Plan: bump-arris-0-12

- Started: 2026-11-24
- Milestone: C2, fidelity re-run on each arris bump
- Idea: docs/ideas/arris-0-12-pin.md (absorbed, option A accepted)
- Runs on `plan/bump-arris-0-12` for the two-architecture CI check.

## Goal

Establish the arris 0.12.0 baseline before `lift-lofts-and-tapers`.
Verify the published wheel against the known coplanar cylinder fuse,
match CadQuery's edge selection on the full revolves exercised by
BenchCAD's `rivet` family, and settle the replay's fidelity differences.
Record the resulting outcome and score changes.

## Non-goals

New CadQuery calls or selector forms, revolve contexts beyond the
verified cases, adopting `tight_bounds` or `classify_points`, and
changing the reward formula or the NumPy pin.

## Design deltas

Pin 0.12.0 exactly in `pyproject.toml` and `uv.lock`. Generate
`docs/ARRIS_API.md` from the new wheel. Review the revolve exception
changes, checker changes, touching-lump booleans and blend refusals
against the existing fixture contracts. Keep refusal text verbatim.
The kernel version is recorded in `versions.arris` under ADR-0021.
The existing `revolve` and `edges` forms gain seam placement where the
oracle establishes it. Amend ADR-0020 rule 2 with the verified profiles,
axis and workplane directions, and when the chain can retain each seam.
Keep the existing refusal wherever a seam cannot be placed. Review the
`unsupported-edges-revolved-side` case and the `revolved` parameter in
`tests/test_cq_edges.py` against the admitted cases. Preserve the
`polar-bore` refusal. Update Architecture §Dialects.

Amend ADR-0016 to compare the oracle's solid count with the count of
outer shells, keeping the existing measure checks. Determine the count
from the candidate body and prove it on known geometry independently of
the oracle count. The body worker supplies `Measures.solids` (an optional
integer) for `compare`, and `dump_text` and the execution digest include it.
Older disk cache entries with measures are re-run. Update
Architecture §Outcomes and §The oracle, and the glossary's **Compound**
and **Seam** entries. Module boundaries stay as they are. Oracle rows
stay pinned. Verdicts follow ADR-0005 and ADR-0006.

## Steps

**[1]** routine mechanical work, **[2]** careful numeric or semantic
verification, **[3]** unproven design. Grades map to tiers.
**[conductor-run]** means the conductor starts long runs in the background.
**[CI]** means verification requires a CI run.

- [x] Step 1 **[2]**. Try the published wheel on
  `regression/cq-union-three-coplanar-cylinders` before finalizing the pin.
  Verify any strict xfail that now passes with `inspect`, then lift it.
  Refresh the pin, lock and API reference, reconcile fixture expectations
  against the release notes, add the Unreleased bullet and pass the gate.
- [x] Step 2 **[2]**. Run `uv run --extra corpus tools/cq_slice.py`.
  If the coplanar fuse fixture builds to the expected geometry, verify the
  100 affected rows against the oracle and retire the corresponding
  verdicts where the measured rows support it. Refresh the C1 fidelity
  table and arris report and explain all changed classes.
- [x] Step 3 **[3]**. Establish the oracle's selected edges for the full
  revolves on all three `rivet` axes and implement the verified seam
  placement under ADR-0020. Lift `cq-rivet-edges-across-revolve-axis`
  with a verified closed-form verdict against its pinned oracle report.
  Verify all 90 affected rows with the same method. Add a property over
  the admitted axis and profile variations. Check neighboring revolve
  contexts against the oracle and keep refusals where they disagree.
- [x] Step 4 **[3]**. Implement and document compound solid counting under
  ADR-0016. Lift the fidelity assertion for
  `cq-compound-with-a-sealed-cavity` and test multiple outer shells, a
  single solid with a cavity and a mismatched oracle solid count.
  Review the 25 `torus_link` rows with count differences and retain any
  separate measure disagreements for step 5.
- [x] Step 5 **[2]**. Resolve the measure disagreements among `bellows`,
  `torus_link`, `dome_cap` and `shaft_collar` with closed forms or
  independently checked oracle evidence. Reuse
  `cq-revolved-cone-notches-bounds` for the clipped rims. Require the
  verdict generator to verify each cited cause and regenerate its output
  byte for byte.
- [x] Step 6 **[2]**. Resolve the six blend refusals against oracle
  `invalid` (`bucket`, `shaft_collar`, `pipe_flange`, `worm_screw`).
  Check the new `cotter_pin` refusal causes and the `bearing_retainer_cap`
  checker failures against their fixtures. Add strict regression fixtures
  for any distinct failure and regenerate the supported verdicts.
- [x] Step 7 **[2] [conductor-run]**. Run `tools/cq_corpus.py` on BenchCAD
  and CAD-Recode from fresh work directories with pinned `--oracle-rows`.
  Review changed rows against 0.11.1 and refresh the C2 baselines,
  verdicts and assertions together using the checked verdicts from steps 5
  and 6. Replace historical verdicts for stems covered by step 6.
  Confirm byte-identical oracle rows and record the torus–box check
  against its closed form.
- [ ] Step 8 **[2] [conductor-run]**. Run `arris-gym rescore benchcad`
  at 2 and 16 workers. Compare the two outputs and use
  `tools/rescore_diff.py` against the committed 0.11.1 evidence. Explain
  each changed score or route beyond version metadata and record the digest.
- [ ] Step 9 **[1] [CI]**. Verify the recorded rescore digest on x86-64
  and aarch64 in CI. Record the run and both matching results before
  fast-forwarding the plan branch.

## Acceptance

- The gate passes with the published 0.12.0 wheel and its generated API
  reference. A lifted regression passes against its existing expected
  geometry; remaining regressions record observed outcomes.
- Reach stays at 14,150/17,900 on BenchCAD and 968/968 on CAD-Recode, with
  zero in-subset `cq_bug`, zero unclassified rows and zero timeouts.
  Oracle rows stay fixed and each changed class has an explanation.
- All 90 affected `rivet` rows and the reduced fixture build and receive
  checked `occt_wrong` verdicts from their closed forms against the pinned
  oracle reports. The sealed-cavity compound agrees with two oracle solids
  despite having three shells. Run
  `tests/test_cq_edges.py`, `tests/test_cq_compound.py`,
  `tests/test_regression.py` and `tests/test_c2_baseline.py`.
- C1 fidelity and rescore evidence is refreshed. The rescore digest
  matches across the two worker counts and both Linux architectures.
- Reassess adoption if the expected fuse fix fails and the corpus
  comparison shows no material gain, or if unresolved regressions appear.

## Docs to update on completion

Update the C1 and C2 fixture READMEs, the C2 figures in
`docs/ARCHITECTURE.md` and `docs/ROADMAP.md`, and Current state in
`AGENTS.md`. Reconcile the affected findings in `docs/BACKLOG.md`.
Update the glossary and ADRs named in Design deltas. ADR-0021 covers
versioning.

## Open questions

- Settled in step 1. The published wheel builds the coplanar cylinder
  fixture to its existing closed form. Fixed regression fixtures still
  support the recorded 0.11.1 C2 verdicts through their versioned failure
  reasons until the 0.12.0 baselines replace them in step 7.
- Settled after the initial replay. The human chose to expand the plan
  to address the 90 in-subset `cq_bug` rows and 110 unclassified rows.
  The reach, timeout and classification thresholds still apply.
- Settled in step 3. Full turns of closed paths yielding a cylinder or
  a cylindrical shank with a spherical or toroidal head place their seams
  in the drawing plane. The local y axis is world-aligned and can point
  either way. The placement applies to the original solid and selections
  on it. See ADR-0020 and `tools/cq_edge_probe.py --revolves`.
- Settled in step 3 with human approval. The reduced rivet and all 90
  affected BenchCAD rows build and match the independent meridian
  calculation under ADR-0005. The pinned reports exceed those limits.
  The closed-form verdicts satisfy step 3 under ADR-0006. Two generator
  runs produced byte-identical verdicts, and step 7 records them in the
  refreshed baseline.
- Settled in step 4. For a checked body with several shells, count the
  solid entities from arris's STEP writer in the body worker. Its shell
  nesting uses signed shell volumes and emits one entity per outer shell.
  A single shell is one solid. An unavailable count leaves agreement
  undetermined for a body with several shells. All 25 count-only
  `torus_link` rows agree on replay. Three measure gaps remain for step 5.
- Settled in step 5. All 79 measure gaps have checked verdicts. Clipped
  rim and cross-hole bounds account for 51 arris bugs. The meridian
  calculation and independent trim integrals establish 28 oracle
  measurement errors. The generator writes the measure verdicts byte
  for byte from the pinned oracle reports. See
  `tests/fixtures/c2/benchcad/measure-replay.md`.
- Settled in step 6. The six unclassified blends and the historical
  collar internal error now have checked `arris_refusal` verdicts for
  overlapping rim blends. The 159 cotter pins refuse at the head union.
  The 24 retainer caps fail the checker at the plate union and cite its
  strict regression. See `tests/fixtures/c2/benchcad/failure-replay.md`.
- Settled in step 7. Both corpus baselines reuse byte-identical oracle
  files and meet the reach, timeout and classification thresholds. The
  C2 fixture READMEs record the new digests and changes from 0.11.1.
  Full verdict regeneration found seven more historical internal-error
  verdicts whose current refusals match the overlapping-blend fixtures.
  The checked failure list replaces those verdicts too.
  The torus–box point contact builds two solids and agrees with the
  closed form and the oracle (ADR-0005, ADR-0016).
- ⚠ OPEN: Step 9 (human) authorizes pushing the plan branch for CI.

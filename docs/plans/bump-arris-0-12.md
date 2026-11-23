# Plan: bump-arris-0-12

- Started: 2026-11-24
- Milestone: C2, fidelity re-run on each arris bump
- Idea: docs/ideas/arris-0-12-pin.md (absorbed, option A accepted)
- Runs on `plan/bump-arris-0-12` for the two-architecture CI check.

## Goal

Establish the arris 0.12.0 baseline before `lift-lofts-and-tapers`.
Verify the published wheel against the known coplanar cylinder fuse,
then explain the outcome and score changes on the current subset.

## Non-goals

Subset expansion, adopting `tight_bounds` or `classify_points`, and
changing the reward formula or the NumPy pin.

## Design deltas

Pin 0.12.0 exactly in `pyproject.toml` and `uv.lock`. Generate
`docs/ARRIS_API.md` from the new wheel. Review the revolve exception
changes, checker changes, touching-lump booleans and blend refusals
against the existing fixture contracts. Keep refusal text verbatim.
The kernel version is recorded in `versions.arris` under ADR-0021.
Public API forms and module boundaries in arris-gym stay as they are.

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
- [ ] Step 3 **[2] [conductor-run]**. Run `tools/cq_corpus.py` on BenchCAD
  and CAD-Recode with the pinned `--oracle-rows`. Review row differences
  against 0.11.1 and refresh the C2 baselines and assertions together.
  Check the reported torus–box refusal and record whether it still holds.
- [ ] Step 4 **[2] [conductor-run]**. Run `arris-gym rescore benchcad`
  at 2 and 16 workers. Compare the two outputs and use
  `tools/rescore_diff.py` against the committed 0.11.1 evidence. Explain
  each changed score or route beyond version metadata and record the digest.
- [ ] Step 5 **[1] [CI]**. Verify the recorded rescore digest on the x86-64
  and aarch64 in CI. Record the run and both matching results before
  fast-forwarding the plan branch.

## Acceptance

- The gate passes with the published 0.12.0 wheel and its generated API
  reference. A lifted regression passes against its existing expected
  geometry; remaining regressions record observed outcomes.
- Reach stays at 14,150/17,900 on BenchCAD and 968/968 on CAD-Recode, with
  zero in-subset `cq_bug`, zero unclassified rows and zero timeouts.
  Oracle rows stay fixed and each changed class has an explanation.
- C1 fidelity and rescore evidence is refreshed. The rescore digest
  matches across the two worker counts and both Linux architectures.
- Reassess adoption if the expected fuse fix fails and the corpus
  comparison shows no material gain, or if unresolved regressions appear.

## Docs to update on completion

Update the C1 and C2 fixture READMEs, the C2 figures in
`docs/ARCHITECTURE.md` and `docs/ROADMAP.md`, and Current state in
`AGENTS.md`. Reconcile the affected findings in `docs/BACKLOG.md`.
ADR-0021 covers versioning.

## Open questions

- Settled in step 1. The published wheel builds the coplanar cylinder
  fixture to its existing closed form. Fixed regression fixtures still
  support the recorded 0.11.1 C2 verdicts through their versioned failure
  reasons until step 3 checks the actual corpus rows on 0.12.0.
- ⚠ OPEN (human, step 5) — push the plan branch for the CI check.

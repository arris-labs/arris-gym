# Plan: BenchCAD Vision2Code baseline

- Started: 2026-11-28
- Milestone: C3, first BenchCAD model-output comparison ([roadmap](../ROADMAP.md#c3--re-scored-benchmarks))
- Idea: `docs/ideas/benchcad-vision2code-baseline.md` (absorbed, option A)
- **[CI]** ref `plan/benchcad-vision2code-baseline`. Ask for the ref and push
  for the x86-64 and AArch64 timing and replay jobs together, including reruns
  on that ref after a measured correction. Runs occur in steps 4 and 6.

## Goal

One frozen one-shot prediction set for the 300 single-solid BenchCAD 1.0
Vision2Code tasks in the C1 slice yields a row per official record ID. Both
graders use the same extracted program and target. The pilot report compares
their scores and failures, ranks actionable findings and reproduces its tables
on x86-64 and AArch64 from the frozen inputs.

## Non-goals

- A separate repository, full BenchCAD, compound STEP targets, or subset lifts.
- Frontier and retry baselines, CAD-Recode, training and the post-C13 kernel replay.
- Paid inference, external publication and outreach.

## Design deltas

- Architecture §Modules, §The oracle and §The re-scored table. The pilot
  driver and instructions live in `tools/benchcad/`. Reuse
  `RescoreEntry`, `rescore(entries, *, sandbox, workers, score_timeout)`,
  `RescoreTable` and `tools/rescore_diff.py` with the locked arris 0.12.0 wheel.
  The pilot command is `tools/benchcad/vision2code.py` in the checkout.
  `generate --upstream CHECKOUT --bundle BUNDLE --model-python PYTHON --out FILE`
  checks the frozen inputs and captures predictions before grading. Repeat
  `--record-id ID` to generate for a smoke selection from the full manifest.
- [ADR-0032](../adr/0032-freeze-benchcad-vision2code-targets-from-the-pinned-regrader.md)
  records the upstream scorer contract. Derive official IDs using
  the pinned Vision2Code materializer's mapping. Verify all 300 IDs against
  `tests/fixtures/c1/slice.txt` and the reference program hashes from
  `code_gen` revision `5919f578ab09ec283603a082fab07c7639ab56eb`. Freeze the
  STEP that upstream scoring reads. Check single-solid imports before
  inference. Use those STEP bytes for both graders and to generate BenchCAD's
  canonical four-view renders. Record a full-file SHA-256 beside Gym's STEP
  data-section hash (ADR-0011).
  [Materializer](https://github.com/BenchCAD/BenchCAD-main/blob/77fd16a80a4e5fc39964ee23b6cc3225beefac8f/Vision2Code/tools/download_codegen_bench.py) ·
  [Regrader](https://github.com/BenchCAD/BenchCAD-main/blob/77fd16a80a4e5fc39964ee23b6cc3225beefac8f/tools/regrade.py)
- The upstream checkout and its CadQuery/OCP environment run out of process
  with worker glue under `tools/oracle/`. Its CadQuery helper needs writable
  STEP paths. Give each job private scratch in a disposable, unprivileged
  environment with no network or credentials, read-only inputs and externally
  enforced deadlines and memory limits. Keep upstream's STEP export behavior.
  Freeze voxel IoU at the regrader's reported precision.
  Checkout tooling exposes `open_upstream(checkout, *, timeout)` and
  `Upstream.extract`, `export`, `render` and `grade`. A grade returns an
  `UpstreamGrade` with voxel IoU, the observed outcome and the export or scoring
  stage on a timeout or crash.
- Freeze a versioned manifest keyed by official record ID with stem, family,
  source, licences, reference and STEP hashes, and upstream commit and
  environment pins. The prediction records add model revision, prompt and
  render hashes, decoding settings, raw response, extracted UTF-8 program
  and hashes, or explicit generation/extraction failures. Both graders
  receive the same extracted bytes. For absent or blank programs, retain the
  cause in the comparison row, count upstream IoU as zero and give Gym an
  empty program (`runtime`, stage `program`, reward −1.0).
- The manifest defines the denominator. Reject duplicate or foreign IDs and
  inconsistent hashes. Keep target and scoring failures, plus upstream
  execution outcomes where available. An upstream zero can leave the cause
  unknown. Record upstream's per-body normalization so the report can
  explain scale differences with Gym's geometry IoU. Report voxel IoU,
  Gym's field metrics, geometry IoU and reward. Include execution and
  invalidity counts over all tasks, denominators for paired or survivor
  metrics, and counts for both IoU routes.
- Replay reads the manifest, predictions, targets and frozen upstream rows
  offline. Sort by record ID and use a fixed reduction order. Hash the
  canonical comparison rows and aggregates. Keep timings and machine
  details in run evidence. Commit redistributable artifacts or record their
  retrievable locations and hashes alongside the report.

## Steps

**[1]** routine, with mechanical tests. **[2]** careful, with a numeric,
geometric or semantic case within a given design. **[3]** unproven, with an
algorithm, isolation guarantee or semantic rule to establish.

- [x] Step 1 **[3]** — Prove the ID, target and upstream execution path on
  one stem per family. Compare the wrapper with the pinned regrader at its
  reported precision on the same extracted bytes and captured STEP inputs.
  Verify per-job isolation with bounded test programs and a Hypothesis property
  over program text. Record the verified path and pins in the ADR.
- [x] Step 2 **[2]** — Build manifest validation, Gym adapter, joined table and
  `replay` command. Test known scores and failures offline. Test
  `replay --record-id` with a complete fixture bundle containing an
  unselected ID. Check that input order leaves the full table digest equal.
- [x] Step 3 **[2]** **[conductor-run]** — Select reusable predictions with
  matching official inputs and terms, or use one local open-weight VLM.
  Use the pinned prompt builder and extractor around a generation-only
  adapter. Capture each response before scoring.
  Test that a stub model receives only the prompt and render and that a
  failed or blank response leaves one record. Freeze the full manifest's
  ID list before scoring real predictions on the step 1 IDs.
- [x] Step 4 **[2]** **[CI]** — Measure the real-output smoke on both CI
  architectures with four workers and a starting score deadline of 60 s (ADR-0031).
  Include the slowest pairs observed in the local smoke. Record the existing
  program and target limits, per-stage times and the measured score deadline.
- [x] Step 5 **[2]** **[conductor-run]** — Freeze one prediction set and grade
  all 300 IDs on both paths. Verify program and target hashes against the
  manifest, freeze the upstream rows, reconcile counts and record the first
  comparison digest. Verify a replay from the stored artifacts.
- [ ] Step 6 **[2]** **[CI]** **[conductor-run]** — Replay on x86-64 and AArch64.
  Use `tools/rescore_diff.py` and compare the canonical comparison table and
  rendered tables byte for byte. Record run IDs, digests and timeout rows.
- [ ] Step 7 **[2]** — Write the slice report and inspect the largest metric
  gaps and most frequent failures. Use reduced fixtures for defects and file
  actionable kernel findings in `../arris/docs/ideas/` with reproductions,
  record IDs and input hashes. Cite the paper for any published benchmark
  numbers and identify the pinned regrader's metric.
  [BenchCAD paper](https://arxiv.org/html/2605.10865v2)

## Acceptance

- `uv run --locked pytest tests/test_benchcad_vision2code.py` exercises a box
  against itself (official voxel IoU, Gym geometry IoU and reward all 1),
  missing and blank predictions (`program/runtime`, −1), broken Python
  (`program/syntax`, −1), corrupt STEP with valid Python (`target/runtime`, −1)
  and a score timeout (`scoring/timeout`, −1). Check the official missing,
  blank and broken-program zeros and their distinct outcomes. Check rejection
  of bad joins and hashes.
- `uv run --locked python tools/benchcad/vision2code.py replay --bundle DIR --out OUT`
  rebuilds the tables from the same input bundle on both architectures.
  Exactly 300 manifest, Gym, upstream and joined IDs match; every outcome
  contributes to the counts. Gym's digest and the canonical JSON and rendered
  tables match on both machines. Name every timeout and its stage.

## Docs to update on completion

- `docs/ARCHITECTURE.md` §§Modules, The oracle, The re-scored table and Determinism.
- `docs/ROADMAP.md` C3 status, `AGENTS.md` Current state and `docs/README.md` index.
- `tools/benchcad/README.md` run and replay commands, attribution and artifact locations.
- `docs/reports/benchcad-vision2code-baseline.md` pilot tables and ranked findings.
- `docs/BACKLOG.md` for measured follow-ups outside this pilot, including the
  same-input replay after arris C13 ships.

## Open questions

- **Settled (step 1, ADR-0032):** the official IDs and all 300 reference
  hashes join to C1. Capture the pinned regrader's STEP export and grade
  with its voxel IoU helper in a separate isolated job. The wrapper and
  regrader agree at four decimal places on the three frozen STEP pairs.
- **Settled (step 3):** matching reusable predictions could not be verified.
  Use the Apache-2.0 Qwen/Qwen3-VL-4B-Instruct snapshot at
  `ebb281ec70b05090aa6165b016eac8ec08e71b17` with the
  [separate CUDA environment](../../tools/benchcad/README.md#one-shot-generation).
  The model runs in BF16 with greedy decoding and up to 2,048 new tokens.
  The full 300-ID manifest was frozen before inference, with SHA-256
  `4491d1e0f6f1d340ce2b04474dcc0fac05bfe97f76af3287ccfcb3fc377cc994`.
  The pinned default prompt text pair has SHA-256
  `eb94505e1d3e73fa17a54abc4f84e7d3765e9b31dd194633d9cc2823c90391f0`.
  The generation command took 83.17 s for the three step 1 IDs on RTX 5090,
  driver 595.99.02, Python 3.12.13. All three records matched the prototype
  run field for field. Each produced an upstream `export_error` and
  Gym `program/syntax`. Two programs had unclosed fences and the phone
  stand had too many nested parentheses. The local comparison digest with
  four workers and a 60 s score deadline was
  `6776753ed21acfa57e4c1e65bd4253531feb00b6f072f27f7c3c5391c164a9de`.
  Keep all three smoke rows. Add real predictions that reach scoring to
  the timing slice for step 4.
- **Settled (step 4):** keep four workers and a 60 s score deadline.
  The [timing smoke and verification rerun](../../tests/fixtures/benchcad-vision2code/timing/README.md#ci-evidence)
  matched across x86-64 and AArch64, with zero timeouts and 57.873 s of
  headroom on the slowest score. Program and target workers used the
  existing 5 s and 512 MiB limits. The smoke exercised one scoreable
  sampled prediction. Step 6 checks the full greedy prediction set.
- **Settled (step 5):** the [stored bundle and local replay evidence](../../tests/fixtures/benchcad-vision2code/baseline/README.md)
  cover all 300 IDs. Both local replays produced comparison digest
  `63c6626e60116b3ac0eee622a4db118e49a44793475a496db3b1eebc5119dbba`.
  The greedy baseline had two upstream scores, zero Gym scores and zero
  timeouts. Step 4 provides the timing evidence for the Gym scoring stage.

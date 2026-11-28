# Plan: rescore-lobed-knob-scoring-timeout

- Started: 2026-11-28
- Milestone: C3, BenchCAD replay
- Idea: `docs/ideas/rescore-lobed-knob-scoring-timeout.md` (absorbed).
  Q1 accepted A in `b0176aa`.
- CI steps run on `plan/rescore-lobed-knob-scoring-timeout`. Request one
  push for the calibration matrix and one for the full replay matrix, each
  covering x86-64 and aarch64. Collect both jobs' artifacts before deciding
  the limits or requesting a rerun.

## Goal

BenchCAD replays can set an explicit deadline for each score worker.
Calibrate that deadline and the worker count on both CI architectures,
then use the same settings to reproduce the committed 300-row table
with zero timeouts. Preserve the evidence for the C3 report protocol.

## Non-goals

- Broader BenchCAD inputs, compound target support and selecting the
  eventual deadline for C3 model outputs belong to later C3 work.
- Reward changes, scoring optimisation and automatic retries are outside
  this plan.

## Design deltas

- Add `score_timeout: float` as an optional keyword to
  `arris_gym.rescore.rescore` and `--score-timeout SECONDS` to
  `arris-gym rescore benchcad`. Use the same 30 s default as
  `reward.score`. Reuse the existing deadline validation and validate
  even if every entry fails before scoring. Forward the value only to
  `score(timeout=…)`.
- Keep the worker boundary (ADR-0001 and ADR-0002), committed targets and
  row semantics (ADR-0011), and reward version 1 (ADR-0008 through ADR-0010).
  `Stage.SCORING` still carries `timeout`, reward −1.0 and body digests
  when the deadline expires. The row counts in all aggregates. Elapsed
  time and replay settings go in run evidence outside the table digest.
- Record the explicit CI score deadline and worker count in an ADR. Both
  values are measured by step 1. ADR-0030 is the precedent for measured
  replay limits. It measured program execution.

## Steps

Complexity grades and tiers follow `.agents/tiers.md`. **[1]** is routine,
**[2]** is careful, and **[3]** requires establishing a new rule or guarantee.

- [x] Step 1 **[2]** **[CI]** — Add an opt-in corpus timing probe on the
  plan ref. Use the pinned `lobed_knob_006797_s20260505` program and
  committed STEP. Time repeated `score` calls at one worker and under
  intended concurrency, starting at four workers and a 60 s deadline.
  Keep candidate execution and target reading outside the score timers.
  Report worker count, deadline, CPU allocation, elapsed times, statuses
  and score digests; check input digests against the committed row. Run on
  both architectures. Set one finite deadline and one worker count that
  give measured headroom on both. Preserve the failing CI evidence and
  the local one-CPU probe recipe in the replay record.
- [x] Step 2 **[1]** — Thread the option through the public function and
  CLI. Extend the controlled scoring-timeout fixture to verify deadline
  forwarding and the counted failure. Cover CLI forwarding and invalid
  limits, including a batch that never reaches scoring. Update the public
  docstring, architecture, README and changelog with the option.
- [x] Step 3 **[2]** **[CI]** **[conductor-run]** — Pin the measured
  settings in the CI command on both architectures. Run the complete
  slice after calibration. Keep the existing committed table comparison
  and publish both artifacts. Investigate any timeout or digest difference
  before accepting the settings.
- [x] Step 4 **[1]** — Record the measured settings, timings, run IDs
  and digests in an ADR and sync the replay docs.

## Acceptance

- Run `uv run --locked pytest tests/test_rescore.py tests/test_cli.py
  tests/test_reward_scoring.py` and the normal gate. The controlled
  timeout yields `program_status=ok`, `stage=scoring`,
  `score.status=timeout`, reward −1.0, both body digests and a named
  timeout in the table.
- On each architecture the timing probe reproduces the committed score
  digest, exact IoU 1.0 and reward 0.9394295282786637 for the known pair
  under the selected limits at both worker counts.
- Run `uv run --locked --extra corpus arris-gym rescore benchcad
  --workers WORKERS --score-timeout SECONDS --out rescore-out` on x86-64
  and aarch64. Check both tables against the committed one with
  `tools/rescore_diff.py`. Require 300 `ok` rows, zero timeouts and digest
  `7653aec26a1f12111b53e4ec7587b926431eb68a9628a3b95443a3107ba23551`.

## Docs to update on completion

- `docs/ARCHITECTURE.md`, The sandbox and The re-scored table, for the
  score worker's deadline and the replay option.
- `tests/fixtures/c1/README.md` for the replay settings and verification.
- `README.md` for the BenchCAD invocation. The glossary's stage entry
  already covers the timeout.

## Open questions

- *Settled.* Use four workers and a 60 s score deadline for the replay.
  [Calibration](https://github.com/arris-labs/arris-gym/actions/runs/46123722320)
  matched all input and score digests on both four-CPU runners. At four
  workers, the maximum was 23.63 s on x86-64 and 17.39 s on aarch64,
  leaving at least 36 s of measured headroom. Step 3 checks the full slice.

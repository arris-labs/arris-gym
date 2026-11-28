# ADR-0031. Calibrate the BenchCAD slice score deadline

- Status: accepted
- Date: 2026-11-28

## Context

A 30 s score deadline produced one x86-64 timeout on
`lobed_knob_006797_s20260505`. The program completed and all four input
digests matched the committed row. Both baseline runs reproduced the
committed table on aarch64.
[Run 46075635078](https://github.com/arris-labs/arris-gym/actions/runs/46075635078)
and [run 46123722284](https://github.com/arris-labs/arris-gym/actions/runs/46123722284).

## Decision

Use four workers and a 60 s deadline per score worker for the 300-row
BenchCAD slice replay on both CI architectures. Compare all rows with the
committed table using `tools/rescore_diff.py`. Record the elapsed time and
settings alongside the table artifact, outside its digest.

## Evidence

The timing probe at `f516d4e` ran three rounds each at one and four workers,
with a 60 s deadline and four logical CPUs available on each runner. It
built the candidate and read the committed STEP before timing.
[Calibration run 46123722320](https://github.com/arris-labs/arris-gym/actions/runs/46123722320).

| Architecture | One worker (s) | Four workers (s) |
|---|---:|---:|
| x86-64 | 14.82–14.87 | 23.25–23.63 |
| aarch64 | 16.99–17.12 | 17.19–17.39 |

All 15 calls per architecture returned `ok`, exact IoU 1.0 and reward
0.9394295282786637. Both probes matched the committed input digests and
score digest `c22efeec427a0697066e50d422c9d01cd754fd62cd44eb1d7d9c714a7d207b5a`.
The slowest call had more than 36 s of headroom.

The full replay at `6a4538f` took 583.01 s on x86-64 and 332.30 s on
aarch64. Each runner had four logical CPUs, produced 300 `ok` rows with
zero timeouts and matched the committed table digest
`7653aec26a1f12111b53e4ec7587b926431eb68a9628a3b95443a3107ba23551`.
[Replay run 46125347612](https://github.com/arris-labs/arris-gym/actions/runs/46125347612).

## Consequences

The public score deadline defaults to 30 s. A score worker that reaches
its deadline still yields a counted row at stage `scoring` with status
`timeout` and reward −1.0. The evidence covers the committed slice and its
targets. Later C3 model outputs need their own calibration.

## Alternatives considered

The 30 s deadline reproduced the x86-64 failure in both baseline runs.
The probe also measured one worker. The four-worker full replay verified
the table digest with concurrency matching the CI CPU allocation. The
[replay record](../../tests/fixtures/c1/README.md#scoring-deadline-calibration)
includes the local one-CPU contention recipe.

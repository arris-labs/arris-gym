# ADR-0030. C2 fidelity replays committed oracle reports

- Status: accepted
- Date: 2026-11-27

## Context

ADR-0014 requires the C2 fidelity table digest to match across CPU
architectures. Live oracle runs can vary in STEP hashes and in the last
bits of measures, as recorded in the [oracle finding](../BACKLOG.md#oracle-nondeterministic-step).
A common oracle input isolates the candidate execution and fidelity comparison.

## Decision

Run every program under `cq` on each architecture with
`--replay-oracle-rows` and the same committed oracle reports. Keep the
recorded versions, STEP hashes and full-precision measures. Replay requires
one answered report per selected stem with the matching program SHA-256,
family, revision and licence. A missing, duplicate, unanswered or
mismatched report stops the replay.

Validate the full canonical `FidelityTable` and compare its digest with
the committed table. Compare the uncompressed oracle rows, reach report
and both arris reports with their committed contents.

## Evidence

[Run 45990557026](https://github.com/arris-labs/arris-gym/actions/runs/45990557026)
reproduced both committed digests on x86-64 and aarch64 on arris 0.12.0.
Each job used four workers. The 30 s BenchCAD trial produced 55 timeouts
on x86-64 and 28 on aarch64.
[Initial run 45957071207](https://github.com/arris-labs/arris-gym/actions/runs/45957071207)

[Timing probes](https://github.com/arris-labs/arris-gym/actions/runs/45983480076)
recovered all 55 affected stems at the 240 s diagnostic cap on each
architecture at both one and four workers. At one worker, 27 stems on
each architecture took longer than 30 s. The slowest four-worker stem,
`double_simplex_sprocket_011623_s20260505`, took 60.54 s on x86-64 and
45.25 s on aarch64. The verified full replay used that cap for BenchCAD and
30 s for CAD-Recode, with zero timeouts on either architecture.

The [BenchCAD](../../tests/fixtures/c2/benchcad/README.md) and
[CAD-Recode](../../tests/fixtures/c2/cadrecode/README.md) READMEs give the
tested commit, commands, counts and full digests. The evidence covers
fidelity against the committed oracle reports. Repeatability of fresh
oracle runs remains open.

# Idea: rescore-lobed-knob-scoring-timeout

- Status: Accepted → plans/rescore-lobed-knob-scoring-timeout
- Raised: 2026-11-28
- Prompt (verbatim from the human): "$idea rescore-lobed-knob-scoring-timeout"

## Problem

In [CI run 46075635078](https://github.com/arris-labs/arris-gym/actions/runs/46075635078)
at `37b5a61`, x86-64 failed to reproduce the committed BenchCAD re-scored
table. The sole timeout among 300 rows was `lobed_knob_006797_s20260505`.
Its program status was `ok`, and its program, candidate, target and STEP
digests matched the committed row. The score worker hit its 30 s deadline.
The row moved from exact IoU 1.0 and reward 0.9394295283 to
`stage=scoring`, `score.status=timeout` and reward −1.0. Mean reward fell
from 0.964561 to 0.958096 and invalidity rose from 0 to 1/300.
The aarch64 replay matched the committed digest. BenchCAD revision
`5919f578ab09ec283603a082fab07c7639ab56eb` and the committed targets pin
the inputs. [C1 replay record](../../tests/fixtures/c1/README.md#the-re-scored-table)

Five isolated calls to `score` on a Ryzen 9 7950X took 10.770–10.783 s
and reproduced the committed score digest. Four concurrent calls on one
logical CPU all timed out at 30 s. Four concurrent full rows across four
logical CPUs all passed. CPU contention can explain this failure mode.
The CI runner's load and the score worker's slowest operation are unknown.
The worker computes all four reward terms and both field metrics under
one deadline. [Score worker](../../src/arris_gym/reward/_job.py)

To repeat the isolated case, put the stem in a slice file and run
`uv run --locked --extra corpus arris-gym rescore benchcad --slice SLICE --workers 1`.
For the contention probe, build the candidate with `run` and load its
committed STEP with `read_target` first. Then submit four concurrent
`score` calls for that pair from a process pinned with `taskset` to one
logical CPU.

## Constraints it runs into

- SEED.md §4–5 and the C3 acceptance in the roadmap require reproducible
  scores and one row per task, with failures counted. Under
  `.agents/rules/gym.md`, wall-clock time may change a row's status.
  A scoring timeout keeps its stage, its −1.0 reward and its place in the
  denominator. The digest includes the outcome and excludes elapsed time.
  [Roadmap](../ROADMAP.md#c3--re-scored-benchmarks) · [ADR-0011](../adr/0011-a-target-is-the-oracles-step-read-in-a-step-worker-and-committed.md)
- ADR-0008 uses a deterministic step budget to choose the IoU route.
  Switching routes on elapsed time violates that decision. Lowering the
  step budget can move rewards and requires a new reward version. A
  scoring deadline governs whether the worker finishes and leaves the
  completed score calculation at version 1. ADR-0009 and ADR-0010 still
  govern the reward terms and BenchCAD field metrics.
  [ADR-0008](../adr/0008-the-iou-is-exact-where-the-kernel-answers-and-sampled-on-a-jittered-grid-elsewhere.md)
- ADR-0001 and ADR-0002 put work on bodies behind the worker boundary.
  The warden still enforces the deadline and memory limit.
  `rescore` can supply the existing `score(timeout=…)` argument without
  adding a dependency from `reward` or `sandbox` to `rescore`.
  `rescore` currently exposes worker count and uses `score`'s 30 s default.
  [Rescore](../../src/arris_gym/rescore/_rescore.py) · [Score](../../src/arris_gym/reward/_scoring.py)
- ADR-0030 gives the BenchCAD **fidelity** replay a measured deadline for
  program execution. That is precedent for measuring the limit on both
  architectures. Its timings give no estimate of the scoring deadline
  needed for C3 model outputs.
  [ADR-0030](../adr/0030-c2-fidelity-replays-committed-oracle-reports.md)

**The words.** A *scoring timeout* is a `timeout` at `Stage.SCORING`.
The candidate and target are valid bodies, and the score worker ran out
of wall-clock time. The glossary's *stage* already covers this outcome.
*Exact route* and *sampled route* refer to the IoU calculation's answer.
No glossary entry is needed. [Glossary](../../GLOSSARY.md#scoring)

## Options

### A — Set a scoring deadline for benchmark replays

Expose a finite, positive `score_timeout` on `rescore` and
`--score-timeout` on its CLI. Keep 30 s as the default and set an explicit
deadline and worker count in the replay command and report. Calibrate with
the known pair at one worker and at the intended batch concurrency on
both architectures. Then compare the full 300-row replay against the
committed digest. Start the probes at 60 s because four isolated calls
add up to about 43 s of serial wall time on the measured host.
Choose the published value from observed headroom, and measure the tail
again on representative C3 pairs before fixing the report protocol.
Longer limits increase the maximum time a slow pair can occupy a worker.
Cost: about three or four plan steps.

### B — Reduce CI concurrency with the existing flag

Use an explicit lower `--workers` value and the same 30 s deadline on
both runners. This is a small workflow change and can help when CPU is
oversubscribed. It lowers throughput for every stage and cannot help a
pair that needs more than 30 s in isolation. Hosted runner contention
can still vary. Cost: one or two plan steps, including a replay.

### C — Profile and optimise the slow scoring operation

Measure body loading, IoU, surface, measures, topology and field metrics
inside the isolated worker, and use the dominant cost to select a
bit-preserving optimisation or an arris performance ask. This can improve
throughput on larger batches if the pair is intrinsically expensive.
Profiling may find that CPU scheduling dominates. An optimisation that
changes completed results would need its own reward decision.
Cost: one or two diagnostic steps, plus a separate performance plan
whose size depends on the result.

### D — Do nothing

Keep counting and naming the timeouts under the current policy. This costs
zero plan steps. The failed x86-64 replay shows the risk to the C3
cross-machine acceptance, and larger batches introduce more pairs with
unknown scoring cost.

## Recommendation

Choose A as C3 replay plumbing. Require the known pair's committed score
digest under the chosen limits and the committed 300-row table digest with
zero timeouts on x86-64 and aarch64. Use the affected stem as a
corpus replay regression outside the offline gate. Verify deadline
forwarding and the counted `Stage.SCORING` timeout path with a controlled
fixture. Record the limits and timings with the run evidence, outside the
score digest. If lowering concurrency reproduces both tables with
comfortable headroom at 30 s and viable throughput, B may suffice for CI.
If isolated C3 pairs still consume the proposed deadline, profile them
before raising it further.

## Decision for the human

❓ **Q1 — Scoring deadline**. Approve a scoring-only deadline for benchmark
replays (A), or choose lower CI concurrency (B), profiling first (C), or
the current policy (D)?

➡️ Yes selects A. It gives CI and C3 an explicit limit measured against
their workloads while preserving reward version 1.

An ADR should record the replay deadline, worker count and evidence when
calibration settles them. No follow-up decision is ready before those
measurements.

## Decision

- Q1 — “yes”. Accepted A, a scoring-only deadline for benchmark replays,
  calibrated on both architectures. The 60 s value is an initial probe.

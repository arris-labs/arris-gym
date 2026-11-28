# Idea: BenchCAD Vision2Code baseline

- Status: Open
- Raised: 2026-11-28
- Prompt (verbatim from the human): “Should we create new repo for running BenchCAD vision2code baseline?”

## Problem

Gym C3 needs its first comparison on model-written CAD code. The current
300-case BenchCAD replay scores reference programs against their Open CASCADE
STEP targets. It establishes that the scoring path reproduces on two
architectures. A Vision2Code baseline would show where the two graders differ
on the same model outputs and give Arris evidence for ranking kernel work.
[C3 roadmap](../ROADMAP.md#c3--re-scored-benchmarks) ·
[Current replay](../ARCHITECTURE.md#the-re-scored-table)

## Constraints

- Gym's library layer keeps CadQuery, Open CASCADE, and tool dependencies
  outside `src/`. The upstream scorer can run in its own environment, with
  Gym reusing its sandboxed `cq` and STEP paths. The current target reader
  takes one solid, so the proven slice is the starting point.
  [Module boundaries](../ARCHITECTURE.md#modules) ·
  [ADR-0011](../adr/0011-a-target-is-the-oracles-step-read-in-a-step-worker-and-committed.md)
- A fair comparison uses the same extracted Python and frozen STEP target
  for each official record ID. Any fresh inference uses the upstream
  canonical renders. A re-scored table retains rows for missing predictions
  and failures. The two-architecture replay pins the official scorer output
  as well as the predictions and targets.
  [BenchCAD inputs](https://github.com/BenchCAD/BenchCAD-main#dataset) ·
  [Upstream regrader](https://github.com/BenchCAD/BenchCAD-main/blob/main/tools/regrade.py) ·
  [ADR-0031](../adr/0031-calibrate-the-benchcad-slice-score-deadline.md)
- Benchmark data, predictions, and any model have their own licence terms.
  Preserve provenance and terms in the manifest. C3 leaves model API spend
  and outreach to the maintainer. [C3 scope](../ROADMAP.md#c3--re-scored-benchmarks)

## Options

### A — Keep the baseline in Arris Gym

Keep the experiment driver and instructions in `tools/benchcad/`. Use a
pinned upstream BenchCAD checkout for inference and official scoring, and
Gym's `rescore` pipeline for the second score. Exchange frozen artifacts by
record ID. This fits the five steps in the workspace companion plan,
`benchcad-vision2code-plan.md`, and lets the adapter, fixtures, and report
evolve with the scoring code. Gym owns the experiment entry point and carries
the upkeep of its artifact format.

### B — Give evaluation its own repository

A separate repository could own provider integrations, experiment artifacts,
and its release schedule while depending on a pinned Gym release. That makes
sense for an independently maintained evaluation service or workflows shared
across several projects. For this pilot it adds repository setup and
cross-repo versioning on top of the same five experimental steps.

### C — Keep the reference replay as the only BenchCAD result

This requires zero implementation steps. It leaves C3 without a model-output
comparison and gives the kernel its existing corpus findings alone.

## Recommendation

Use A for one single-solid BenchCAD 1.0 Vision2Code run. Verify the record ID
join and shared targets on a handful of cases, then freeze one prediction
set. The result is a per-task comparison of official voxel IoU and Gym's
score, with every failure counted and matching report tables on x86-64 and
AArch64. Revisit B if evaluation acquires independent maintainers or a
release schedule. The current layer and scoring decisions cover this pilot.

## Decision

Record option A in Arris Gym as requested. Adoption into a C3 implementation
plan is pending.

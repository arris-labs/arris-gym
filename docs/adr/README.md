# Architecture decision records

One file per decision, numbered `NNNN-<slug>.md`, never edited after
acceptance — a change of mind is a new ADR that supersedes the old one.
Format: Context, Decision, Consequences, Alternatives considered. An ADR
whose design was informed by CadQuery's source names the file or module read,
so provenance is auditable (`PROVENANCE.md`, SEED.md §8).

The decisions taken at kickoff live in `SEED.md` §9 and are not repeated
here; the first ADR is the first decision taken *after* the seed. Open at
kickoff, each closed by an ADR (SEED.md §10.8): the C2 fidelity target;
mesh-based vs. exact IoU as the default until `classify_points` lands; the
reward weights and τ; how CadQuery's string selectors map onto arris's
selection when they are ambiguous on curved faces; whether B-Rep descriptions
for the own benchmark are exact or quantised; which open base model the
training cycle starts from.

| # | Title | Status |
|---|---|---|
| [0001](0001-a-program-runs-on-a-fresh-model-in-a-forked-process.md) | A program runs on a fresh model in a forked process | accepted |
| [0002](0002-the-program-worker-is-pid-1-of-its-own-namespaces-under-a-warden.md) | The program worker is PID 1 of its own namespaces, under a warden | accepted |
| [0003](0003-the-census-parses-a-program-and-counts-what-it-writes.md) | The census parses a program and counts what it writes | accepted |
| [0004](0004-the-oracle-worker-execs-the-oracle-interpreter-inside-a-program-worker.md) | The oracle worker execs the oracle's interpreter inside a program worker | accepted |
| [0005](0005-the-agreement-tolerance-is-set-from-a-calibration-set.md) | The agreement tolerance is set from a calibration set held to closed forms | accepted |
| [0006](0006-a-fidelity-row-is-classed-by-its-statuses-or-by-a-verdict.md) | A fidelity row is classed by its two statuses, or by a verdict | accepted |
| [0007](0007-a-cq-workplane-is-a-frozen-stack-over-arris-build.md) | A `cq` Workplane is a frozen stack over `arris.build`, its result one solid | accepted |
| [0008](0008-the-iou-is-exact-where-the-kernel-answers-and-sampled-on-a-jittered-grid-elsewhere.md) | The IoU is exact where the kernel answers, and sampled on a jittered grid elsewhere | accepted |
| [0009](0009-the-surface-term-is-a-seeded-nearest-sample-distance-under-a-tau-five-times-its-noise-floor.md) | The surface term is a seeded nearest-sample distance, under a τ five times its noise floor | accepted |
| [0010](0010-the-field-metrics-agree-with-benchcads-scorer-within-a-floor-and-a-tenth.md) | The field metrics agree with BenchCAD's scorer within a voxel tolerance of 0.04, and a Chamfer floor of 2.0 plus a tenth | accepted |
| [0011](0011-a-target-is-the-oracles-step-read-in-a-step-worker-and-committed.md) | A target is the oracle's STEP, read in a step worker and committed | accepted |
| [0012](0012-reach-is-decided-statically-from-the-subsets-declarations.md) | Reach is decided statically from the subset's declarations | accepted |
| [0013](0013-an-oracle-zygote-imports-cadquery-once-and-wards-a-child-per-program.md) | An oracle zygote imports CadQuery once and wards a child per program | accepted |
| [0014](0014-the-fidelity-target-is-a-reach-of-85-percent-on-benchcad-and-all-of-cad-recode.md) | The fidelity target is a reach of 85% on BenchCAD and all of CAD-Recode | accepted |
| [0015](0015-a-cq-result-is-the-last-shown-value-then-result-then-r.md) | A `cq` result is the last shown value, then `result`, then `r` | accepted |
| [0016](0016-a-cq-compound-is-one-solid-whose-body-holds-a-shell-per-piece.md) | A `cq` compound is one solid whose body holds a shell per piece | accepted |

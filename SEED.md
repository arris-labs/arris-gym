# Project Seed Document: arris-gym

## 1. Project Overview
**Name:** arris-gym
**Tagline:** Run, score and train CAD-code models on a kernel you can trust: exact, deterministic, every failure counted.
**Core Concept:** `arris-gym` is a Python library, not an application. It runs model-written CAD programs on the `arris` B-Rep kernel in a sandbox, returns a typed outcome for every program, and scores the result against a target exactly: B-Rep volumes and point classification, the invariant checker, and the kernel's typed refusals. It speaks two program dialects: `arris.build`, the kernel's own code-CAD API, and a **CadQuery-compatible subset**, because CadQuery is what every public CAD-code benchmark, dataset and model speaks. Benchmark harnesses, RL training loops and model evaluations are built on top of it.

**North star: arris as the verification backend for CAD-code AI.** Anyone who trains or evaluates a model that writes CAD code should be able to run that code on arris and get scores that are exact, deterministic and validity-checked, with every failure counted. Through that, arris becomes the kernel models are built and judged against.

| Piece | Role |
|---|---|
| CadQuery-compatible subset on arris | **The vehicle**: every existing benchmark, model and dataset on day one |
| The environment (sandbox, typed outcomes, exact reward) | **The product**: a library others install |
| Public benchmarks re-scored on arris | **The first publication** |
| A narrow benchmark of our own | **Only where the field is weak**: editability through provenance, exact B-Rep reconstruction |
| A model trained on one RTX 5090 | **The proof** that the environment produces learning signal |
| arris improvements | **By-product**: ~1M public CadQuery programs compared with Open CASCADE is the largest stress corpus arris can get |

It belongs to the `arris-labs` family. It depends on the `arris` wheel and shares the family's conventions: determinism, typed outcomes instead of crashes, verification first, agentic development. It does not depend on `laman` until cycle 5 (§6), and never on a history engine or an assembly solver (`../core-libs.md`).

Development is fully agentic. The human sets direction and judges results; the agent designs, implements, tests and documents. Everything the library does must be checkable as numbers, without a human looking at a screen.

## 2. The Naming Rationale
A *gym* is what the RL world calls an environment a policy trains in (OpenAI Gym, now Gymnasium). `arris-gym` is the environment where CAD-code models train and are judged against the `arris` kernel. The prefix keeps it in the family. The name replaces the working name `arris-zero`, which suggested R1-Zero (pure RL with no supervised fine-tuning), which is not the plan.

`arris-gym` was free on PyPI and crates.io as of 2026-11-07. Reserving it (a minimal real 0.0.x release) is the human's act.

## 3. The Problem Statement
CAD-code generation is a crowded research field with a weak floor:

* **At least a dozen benchmarks appeared in 2026, none dominant.** BenchCAD, Text2CAD-Bench, MUSE, Parametric CAD Bench, CADWorld, CADEngBench, HistCAD, RealCADBench, OmniMech, CadBench and more. Almost all run CadQuery or FreeCAD, so Open CASCADE underneath.
* **Their scoring layer is weak in the same ways.** IoU from voxelised meshes (256³) or renders. Metrics averaged only over programs that executed, so a model that fails more can look better (Text2CAD-Bench notes this survivorship bias). No validity check beyond "volume is not zero". No discussion of nondeterminism, kernel crashes or version pinning. 30–60 s timeouts. Editability is rarely measured, and topological naming not at all in what the survey read.
* **The field is far from saturated.** Execution failure dominates hard tasks: on Text2CAD-Bench L3, 70–90% of programs fail, mostly on sweep, loft and shell. The best GUI agent completes 17.5% of CADWorld against 87% for experts.
* **The RL recipe has converged.** SFT, then GRPO with reward = execution gate + voxel IoU and/or Chamfer (CAD-Coder, cadrille, CME-CAD, ReCAD, BenchCAD's baseline). Small specialised models already beat frontier models in distribution. A training recipe is no longer a contribution; the quality of the environment and the reward is.

So the problem is not "another benchmark" or "another CAD model". It is: give the field an execution and scoring layer that is exact, deterministic and validity-checked, that counts every failure, and that runs the code the field already writes.

## 4. Competitive Landscape (as of November 2026; full survey in `docs/BENCHMARK-SURVEY.md`)

| What | Examples | Why it does not close the gap |
|---|---|---|
| Benchmarks on CadQuery/OCCT | BenchCAD (17.9k parts, CC-BY-4.0, MIT eval), Text2CAD-Bench (600), CadBench, MUSE | Mesh or voxel scoring, failures dropped from averages, no validity check, OCCT install and nondeterminism. They are the *consumers* of what arris-gym offers, not competitors |
| Benchmarks on FreeCAD / GUI | Parametric CAD Bench (cadbench.ai), CADWorld | Agentic and GUI-centred, expensive per trial; scoring by saved-file checks. Adjacent, not overlapping |
| Editability / design-intent benchmarks | HistCAD, cadbench.ai's editability gate, BenchCAD-Edit | Measured by re-rendering or constraint survival. arris measures it through provenance as a fact |
| Models and RL | CAD-Recode (~1M programs, CC BY-NC), cadrille, CAD-Coder, CME-CAD, ReCAD | Train on OCCT-executed rewards. They are baselines and future users |
| Kernel-as-gym | RLCAD (B-Rep → command sequences, no public repo confirmed) | Closest prior. Bespoke engine, not a general scoring backend |

**Why arris-gym, the differentiators in priority order:**
1. **Exact, validity-checked scoring.** B-Rep measures and point classification instead of voxels; the invariant checker on every result; typed status for every failure, counted, never dropped.
2. **Deterministic bit for bit.** The same program gives the same body, ids and score on every machine, so a score can be cached and a report can be re-run by anyone.
3. **Speaks the field's language.** A CadQuery-compatible subset means existing benchmarks, models and datasets run unchanged, with fidelity against Open CASCADE measured and published, not assumed.
4. **Provenance.** Editability is "did the tagged feature survive the parameter change", answered by the kernel.
5. **`pip install`, pure Rust underneath.** No conda, no OCCT build.

**Explicit non-goals:** a GUI; assemblies; drawings; a new DSL; full CadQuery compatibility (only the subset the corpora use); a broad text → CAD benchmark of our own; training above ~14B parameters or on more than one GPU; anything in the `arris` repo shaped by CadQuery's semantics.

## 5. The Solution & Developer Experience
arris-gym should feel like a small, typed Python library that a benchmark harness or a training loop calls in two lines:

* **`run` never raises on a program.** It returns an `ExecResult` with a status: `ok | syntax | runtime | unsupported_api | arris_refusal(kind) | checker_fail | timeout | crash`. The arris error kind and message are kept verbatim, entity ids included, because they are also the feedback a model sees on a retry.
* **Programs run in a separate process** with a wall-clock timeout, a memory limit and no network. A crashed or hung worker is replaced; the caller gets a status.
* **`score` is deterministic.** Fixed seeds, fixed summation order, a pinned `arris` and `numpy`, all recorded in every result row. The reward's version and weights are in the result.
* **Two dialects, one outcome type.** `dialect="arris"` (`arris.build`) and `dialect="cq"` (the CadQuery subset). An API outside the subset is `unsupported_api` naming the call, not a crash.
* **The field's metrics beside ours.** Voxel IoU, Chamfer ×10³ and invalidity rate are computed the way the benchmarks define them, so numbers are comparable with published ones.
* **Everything is inspectable without a GUI.** A result dumps to text that diffs in a test and to a PNG (through arris's tessellation) the agent can read.

```python
import arris_gym as ag

target = ag.run(open("target.py").read(), dialect="cq").body
result = ag.run(model_output, dialect="cq", timeout=5.0)

if result.status is ag.Status.OK:
    s = ag.score(result, target)        # deterministic
    print(s.reward, s.iou, s.chamfer, s.field.voxel_iou_256)
else:
    print(result.status, result.message)  # e.g. ArrisRefusal(kind="blend-too-large")
```

```sh
arris-gym census   --corpus benchcad                  # which CadQuery API the corpus uses
arris-gym fidelity --corpus benchcad                  # arris vs Open CASCADE, every disagreement classified
arris-gym rescore  benchcad --predictions preds.jsonl # a benchmark scored on arris
```

## 6. Core Features

### Cycle 1 — the vertical slice
One path through every module before any is broad. **Acceptance:** a slice of BenchCAD programs (the few families the census ranks first) runs in the sandbox in both dialects' path (`cq` subset → arris; CadQuery → Open CASCADE oracle); every program gets a status; every disagreement is classified; the reward's unit tests hold; one small "re-scored" table regenerates bit-identically on two machines.

1. **Environment:** `uv` project; `arris` pinned exactly; the API reference generated from the wheel's own `.pyi` stubs into `docs/ARRIS_API.md`.
2. **Sandbox:** process isolation, timeout, memory limit, worker pool restarting after crash or timeout, the `ExecResult` type, a result cache keyed by `hash(program, dialect, arris version)` (exact, since arris is deterministic).
3. **Census:** parse a CadQuery corpus and count every API call, selector string and argument form. The census decides what `cq` implements and in what order.
4. **`cq` subset, first slice:** `Workplane` and its stack semantics, the sketch calls, `extrude`, booleans, the selector grammar the slice needs, STEP export. API-compatible reimplementation over `arris.build` (CadQuery is Apache-2.0; nothing copied).
5. **Oracle:** `tools/oracle/`, its own `uv` env with CadQuery/OCP, run and never imported by library code. It executes the same program and reports status, volume, area, centroid, counts.
6. **Fidelity:** each disagreement classified as `cq` bug, arris refusal (kind), arris bug, Open CASCADE wrong (closed form or second oracle), or semantic difference by design (documented). Arris rows exported as a consumer report for arris (its ADR-0020).
7. **Reward and metrics** (§7.1), including the field's metrics.
8. **Harness:** pytest + hypothesis, fixtures by construction with closed-form answers, determinism digest, text and PNG dumps.

### Cycle 2 — the fidelity gate
The `cq` subset grows in census order over BenchCAD and the CAD-Recode validation split until the fidelity table has nothing unclassified and a fidelity target (set by ADR after the cycle 1 measurement) is met. Everything outside the census stays out: CadQuery assemblies, `cq.Sketch` constraints, plugins, `.wrapped` and raw OCP calls. **Decision point:** if fidelity is low because of arris refusals, those rows rank arris's next cycle. If it is low because of CadQuery semantics, the subset narrows.

### Cycle 3 — re-scored benchmarks (the first publication)
A scorer that takes a benchmark's tasks and a model's outputs and scores them on arris, every failure counted. In order: BenchCAD (CC-BY-4.0 data, MIT eval), CAD-Recode validation, Text2CAD-Bench if its data is released; others by licence. Baselines: frontier models prompted for CadQuery (one shot, and up to three retries with error feedback, as the benchmarks do); open-weight specialists (cadrille, CAD-Recode) where their licences allow. A technical report on where exact, deterministic scoring disagrees with published numbers and why. Then contact the BenchCAD authors about arris as an optional scoring backend.

### Later cycles, roughly in order
- **Own benchmark, narrow:** (a) editability through provenance (perturb parameters; the program rebuilds, tagged features survive, stated dimensions hold); (b) exact B-Rep reconstruction from an arris-serialised description of the target (each face's surface kind and exact parameters, adjacency, measures). Held-out tasks never published as programs; no baseline above 0.9 at release.
- **Training on one RTX 5090:** a CadQuery-on-arris track first (comparable with the literature), then an `arris.build` track for the own benchmark. Data: BenchCAD (CC-BY), a procedural generator of design-like parts over `arris.build` (features picked through provenance and tags, refused steps backtracked, curriculum by operation count), CAD-Recode (CC BY-NC, research only), public STEP files as RL targets only. Base model chosen by ADR when the cycle opens (best open coder or VLM trainable with LoRA on 32 GB at 7–14B). SFT, then GRPO (TRL, vLLM colocated, group size 8); a multi-turn variant that feeds arris's typed error back for one retry. Accept: beats its SFT checkpoint and the published open specialists on the re-scored benchmarks at ≥ 95% execution rate.
- **Design intent with laman:** a thin adapter (constrained sketch → laman → laman's C3 profiles → `arris.build` profile); laman's diagnostics (DoF 0, no conflicts, named dimensions) as reward terms on the editability track.

Each earns its own cycle with an acceptance corpus; none is scheduled here. Cross-repo ordering (what arris and laman do meanwhile) is `../order-of-work.md`.

## 7. Tech Stack (decided)

| Layer | Choice | Why / notes |
|---|---|---|
| Language | Python ≥ 3.12, MIT OR Apache-2.0 | The field's language; matches the family's licence |
| Package manager | `uv` | Lockfile, fast, the family's choice for Python tooling |
| Kernel | `arris` from PyPI, pinned exactly | Recorded in every result row; bumped deliberately with a fidelity re-run |
| Numerics | `numpy` (pinned), `scipy` only where needed | Deterministic sampling via `numpy.random.Generator(PCG64)` with explicit seeds |
| Types and models | `pydantic` v2 for results and configs; `mypy --strict` | Typed outcomes are the product |
| Lint | `ruff` | Family standard |
| Tests | `pytest`, `hypothesis` | Fixtures by construction; properties over random programs |
| Data | HF `datasets`, Parquet | Every row: program, dialect, target, measures, source, **licence**, arris version, reward version |
| Oracle | CadQuery/OCP in its own `uv` env under `tools/oracle/` | Run, never imported by the library. Same rule as arris's oracle |
| Training (optional extra `[train]`) | `torch`, `transformers`, `trl` (GRPO, SFT), `peft`, `vllm`; `unsloth` if compatible | Kept out of the core install so the scorer stays light |

### 7.1 Reward

```
status ∈ {syntax, runtime, unsupported_api, timeout, crash} → -1.0
status = arris_refusal(kind)                                → -0.5
status = checker_fail                                       → -0.3
valid body                                                  →  0.1 + 0.9·S
S = 0.6·IoU + 0.15·surface + 0.15·measures + 0.10·topology
```

- **IoU**, volumetric. Preferred: exact B-Rep point classification on a batch of points. **That exists in Rust (`arris_check::classify::classify_point`) but is not in the Python wheel**, so a consumer ask goes to arris for `classify_points(body, pts: ndarray[N,3]) → ndarray[N]` (in/out/on). Until it lands: `tessellate` → `mesh_to_numpy` → winding-number test on the closed mesh, error bounded by the chord tolerance. Sampling: N = 4096 uniform points in the union of both bboxes plus N/2 stratified near the target surface, a fixed seed per task.
- **surface**: symmetric Chamfer distance on surface samples, normalised by the target bbox diagonal, through exp(−d/τ).
- **measures**: volume and area ratios, centroid and principal moments.
- **topology**: face-kind histogram (plane/cylinder/cone/sphere/torus/NURBS) and genus, which rewards a real hole over a faceted one.
- Weights, τ and N live in a versioned config written into every result row.

### 7.2 Hardware assumption (training cycles only)
One workstation: RTX 5090 (32 GB) plus a multi-core CPU. The GPU runs rollouts (vLLM) and LoRA updates; sandbox workers run arris on the CPU. GRPO needs no value model, which is what makes 7–14B training fit in 32 GB.

### Layout
```
arris-gym/
  SEED.md  README.md  AGENTS.md  CLAUDE.md  pyproject.toml  uv.lock
  docs/  README.md  ARCHITECTURE.md  ROADMAP.md  BENCHMARK-SURVEY.md
         ARRIS_API.md (generated)  BACKLOG.md  adr/  ideas/  plans/
  src/arris_gym/
    sandbox/   executor, result types, worker pool, cache
    cq/        the CadQuery-compatible subset over arris.build
    reward/    iou, surface, measures, topology, field metrics, reward
    census/    CadQuery corpus parsing and API counts
    fidelity/  oracle comparison and the disagreement classes
    rescore/   per-benchmark adapters and the report
    describe/  (later) target → B-Rep text description
    synth/     (later) procedural generator over arris.build
    train/     (later, [train] extra) prompts, SFT, GRPO
    sketch/    (later) laman → arris profile adapter
  tools/oracle/   separate uv env: CadQuery/OCP runner and comparer
  tests/
```
**Layer rule:** `sandbox`, `reward` and `cq` never import `train`, `rescore` or anything under `tools/`. `cq` imports only `arris`. Promoting `cq` to its own package (e.g. `arris-cq`) waits for fidelity to be good; it never moves into the `arris` repo.

## 8. Heritage and References
**From the first plan (`arris-zero`, 2026-11-01):** GRPO over SFT on one 5090; sandboxed execution with typed error classes; a shaped reward gated on execution and validity; multi-turn compiler feedback; curriculum by operation count. Dropped: metrics-only conditioning (bbox + volume + face counts, too ambiguous), runtime introspection of the wheel (the stubs are the reference), a hard-coded 2025 base model, and the assumption that point classification is already in the Python API.

**From arris:** the oracle discipline (Open CASCADE run, never linked; closed forms or a second oracle settle disagreements, ADR-0015); fixtures with recipes and expected values; refusal histograms ranking cycles (ADR-0020); the script corpus (`arris/crates/arris-py/corpus/`) as gold programs and S0 acceptance.

**From the benchmark survey (`docs/BENCHMARK-SURVEY.md`):** BenchCAD (2605.10865), Text2CAD-Bench (2605.18430), MUSE (2605.28579), Parametric CAD Bench v3 (2611.02659), CADWorld (2609.16251), CADEngBench (2608.09296), HistCAD (2602.19171), CAD-Recode (2412.14042), cadrille (2505.22914), CAD-Coder (2505.19713), CME-CAD (2512.23333), ReCAD (2512.06328), RLCAD (2503.18549). Most survey numbers come from abstracts and snippets: **verify against the papers before the cycle 3 report cites them.**

**From CadQuery (Apache-2.0, read for API behaviour):** the API surface and its documented semantics. Reimplemented over `arris.build`. Any behaviour taken from CadQuery's source is named in `PROVENANCE.md`.

## 9. Decisions taken in this seed

| Question | Decision | Reason |
|---|---|---|
| North star | **Verification backend for CAD-code AI**, not "the standard benchmark" or "the best CAD model" | A dozen benchmarks compete; nobody competes on the scoring layer, which is arris's strength |
| Program dialects | **`arris.build` and a CadQuery-compatible subset** | CadQuery is the field's lingua franca; `arris.build` carries provenance and tags for our own tasks |
| CadQuery scope | **Census-driven subset only**, measured against Open CASCADE | Full compatibility is a different project; fidelity is published, not assumed |
| Where `cq` lives | **In arris-gym, own boundary; never in the `arris` repo** | CadQuery's semantics must not shape the kernel's API |
| Oracle | **CadQuery/OCP out of process under `tools/oracle/`** | Same rule as arris: run, never linked |
| Failures in metrics | **Counted, never dropped from averages** | Survivorship bias is the field's most common scoring flaw |
| Determinism | **Pinned arris and numpy, fixed seeds, fixed summation order, versions in every row** | Re-scoring is only worth publishing if anyone can reproduce it bit for bit |
| Dependencies on family libs | **`arris` only; `laman` from the design-intent cycle; never a history engine or assembly solver** | The script is the history; single parts only (`../core-libs.md`) |
| Training deps | **Optional `[train]` extra** | The scorer must stay a light `pip install` |
| Data licences | **A licence column on every row; weights inherit the most restrictive licence of their data** | BenchCAD is CC-BY-4.0, CAD-Recode is CC BY-NC 4.0 |
| Home | **GitHub `arris-labs/arris-gym`; PyPI `arris-gym`** | One family, visible together |
| First milestone | **Vertical slice (§6)**, not a broad `cq` | Proves sandbox, oracle, fidelity classes and determinism before the subset grows |

## 10. Directives for the AI Agent
With this seed agreed, and before writing library code:
1. **Initialise the repository** in this directory (`git init`, `main` branch) with `SEED.md` and `docs/BENCHMARK-SURVEY.md` as the first commit. Remote creation and the first PyPI release are the human's acts.
2. **Scaffold the docs system and tooling** from `../arris` and `../laman`: `docs/README.md` with the three tiers, `docs/adr/`, `docs/ideas/`, `docs/plans/`, `BACKLOG.md`, `GLOSSARY.md`, `AGENTS.md`/`CLAUDE.md` with a short current state, the `/idea` `/plan` `/work` `/retire-plan` `/close-cycle` skills adapted to a Python library, the gate (ruff, `mypy --strict`, pytest), git hooks, CI, and `PROVENANCE.md`. Read how arris and laman do each before copying; adapt, don't transliterate Rust-specific rules. Do not read `../arrix` for any of this.
3. **Architecture document** (`docs/ARCHITECTURE.md`): modules and the layer rule; the `ExecResult` and status model; the sandbox's process, timeout and memory model; the dialect boundary; the reward and its versioning; determinism rules; where the oracle sits and why it is never imported.
4. **Roadmap** (`docs/ROADMAP.md`): cycle 1 as in §6 with its acceptance spelled out as numbers (which BenchCAD families, how many programs, the reward unit tests' closed forms, the digest); cycle 2 as the fidelity gate; cycle 3 as the re-scoring report; later cycles one line each.
5. **Build the harness before `cq` is broad.** Sandbox, oracle, fidelity classes, determinism digest and the text/PNG dumps are cycle-1 deliverables in their own right and come first.
6. **File the consumer asks with arris** as ideas in `../arris/docs/ideas/` once cycle 1 measures them: the batch `classify_points` binding first, then every arris row of the fidelity table. Do not edit arris code from this repo.
7. **Every failure becomes a fixture.** A program that crashes, hangs or disagrees is shrunk to a minimal case and committed with the desired assertion, marked `xfail` until it passes. An arris crash is also reported to arris as a fixture candidate.
8. **Write an ADR for each ⚠ OPEN when it closes.** Open at kickoff: the cycle 2 fidelity target (closed by ADR-0014: T = 85% reach on BenchCAD, 100% on CAD-Recode); mesh-based vs. exact IoU as the default until `classify_points` lands; the reward weights and τ; how CadQuery's string selectors map onto arris's selection when they are ambiguous on curved faces; whether B-Rep descriptions for the own benchmark are exact or quantised; which open base model the training cycle starts from.

# Plan: m4-reward

- Started: 2026-11-09
- Milestone: M4 (cycle C1, docs/ROADMAP.md)
- Idea: none; verbatim from the human: "/plan M4"

## Goal
`score(result, target)` returns a frozen `Score`: the reward of SEED.md §7.1
under a versioned `RewardConfig`, its four terms, which IoU route answered, and
BenchCAD's field metrics beside them. A failure status gets exactly −1.0, −0.5
or −0.3 with no kernel call. A valid body is scored in a **score worker**, so a
kernel crash while scoring costs a status and never the run. Every closed form
in the roadmap's M4 list holds, and the field metrics match BenchCAD's own
scorer on 10 pairs inside a measured tolerance.

## Non-goals
- Tuning the weights on model outputs (roadmap: out); SEED.md's 0.6/0.15/0.15/0.10 stand.
- `rescore`, its table, and the digest across two machines: M5. M4 proves repeat runs on one machine.
- A score cache and a `score_many`: M5 adds them if its table needs them.
- BenchCAD's composite (op recall, Feature-F1, Hausdorff) and Text2CAD's 256³ grid: C3 adapters.
- Any arris code: the cone and `classify_points` asks are filed as ideas.

## Measured while planning (arris 0.10.0, the 200 `ok` slice bodies)
`Model.interference` answers a body against itself (200 of 200, both containment
flags true, volume within 3.7e-16) and `phone_stand` moved or turned (200 of
200). On `venturi_tube`, 99 of 100 shifted 3% raise `OpUnsupportedError` (cone
against cone) and 55 of 100 turned 7° run past 10 s. `budget=` ends such a call
in a typed `Interrupted`, the same on repeat runs (1e5 steps stop in 0.1 s; 1e7
finish in 8 s). So sampling is the ordinary path for a part with cones, and the
switch between routes must be a step count: a wall-clock switch would let
machine speed move a score.

## Design deltas
- **ADR-0008, the IoU routes and the estimator** (step 2), closing both IoU
  `⚠ OPEN`s in ARCHITECTURE.md §The reward. **Exact route**: `interference` under
  `RewardConfig.iou_budget`. `apart` or `touching` is 0; both containment flags
  are exactly 1; one flag is the smaller volume over the larger; else
  `v∩/(vA+vB−v∩)`, clamped to [0, 1]. Any `ArrisError` (`Interrupted` included)
  goes to the **sampled route**: a winding number on `tessellate`'s mesh over
  PCG64 points. `Score.iou_route` names the route. Step 2 measures, against the
  exact route on every pair it answers, `iou_budget`, the chord fraction, N, and
  whether near-surface points are dropped (the seed's N/2) or kept with weights
  for their stratum. An unweighted count of them is biased and is not a candidate.
- **ADR-0009, the reward's constants** (step 3): the formulas below and τ. τ is
  measured from a shift ladder on the slice's bodies and held at least 5× the
  noise floor of two independent samplings of one surface, so one part built
  two ways is not punished for its samples.
- **Terms** (`reward/`, each in [0, 1], each exactly 1 on identical inputs).
  `surface` = exp(−d/τ), d the mean of both one-way mean nearest-sample distances
  over the target's bounding-box diagonal; each body samples from a fresh
  `PCG64(seed)`, so identical meshes give identical points and d = 0.
  `measures` = the mean of volume ratio, area ratio, 1 − min(1, centroid
  gap/diagonal) and the mean ratio of sorted principal moments (each ratio
  min/max). `topology` = a config weight between histogram overlap
  Σmin/Σmax over the seven surface kinds and 1/(1+|Δgenus|). `exp` is a fixed
  polynomial with `ldexp`, principal moments are fixed Jacobi sweeps
  (§Determinism). Sums go through `math.fsum`.
- **Public** (`arris_gym`): `score(result: ExecResult, target: BodyRef, *,
  config=DEFAULT_REWARD, sandbox: Sandbox | None = None, timeout=30.0, memory=…)
  -> Score`; `RewardConfig` (version, weights, τ, N, seed, `iou_budget`, chord);
  `Score` (status, message, reward, `iou`, `iou_route`, `surface`, `measures`,
  `topology`, `field`, `reward_version`, versions, `digest()` over hex floats);
  `FieldMetrics` (`voxel_iou_64`, `chamfer_x1000`); `IouRoute`;
  `invalidity_rate(scores)`, a corpus aggregate over all rows. It replaces the
  per-result field ARCHITECTURE.md lists, since a rate has no value for one
  result. SEED.md's `voxel_iou_256` was illustrative: BenchCAD's grid is 64³.
- **`Score.status`** is the result's status, or `crash`, `timeout` or `runtime`
  when scoring a valid body failed; the reward then follows the table (−1.0),
  so crashing the scorer never pays. The kernel's words stay in `message`.
- **Score worker**: `JobKind.SCORE`, a handler like `_mesh.py`, payload
  both bodies' bytes and the config; a `ScoreFrame` the caller validates (finite,
  in range, else `crash`). The zygote's entry registers the handler, so
  `sandbox` never imports `reward`. Both bodies are read into one fresh model.
- **Field metrics**, from the MIT source at `BenchCAD/BenchCAD-main@77fd16a8`
  (`benchcad_core/scoring/iou.py`, `Vision2Code/scoring/composite_metrics.py`),
  cited in the module, on numpy only: tessellate at 0.05, normalise each body to
  its own box (centre 0.5, longest side 1), subdivide to pitch/2, round to
  occupied voxels, fill holes, centre into 68³; Chamfer is mean d² + mean d²
  over 2048 samples, ×1000 here. Theirs are unseeded and scale-blind: a cube
  against its double is `voxel_iou_64` 1 and our IoU 1/8, a test holds both.
- **`tools/oracle/`** gains `trimesh==4.12.2` and `scipy==1.17.1`, BenchCAD's
  locked versions, with its `numpy` unmoved; `benchcad_score.py` runs their
  scorer at that commit on our own committed pair programs, outside the gate.
- **Gate**: `tools/check_layers.py` refuses `@`, `np.dot`, `np.linalg`, `np.exp`,
  `np.sin`, `math.exp` and `random` in `reward/`; the winding number's
  `arctan2`, which only feeds a threshold, is the one named exception.
- **Glossary**: **Score worker**, **Exact route**, **Sampled route**, **Reward config**.

## Steps
Complexity grades; a step's grade is its tier (`.agents/tiers.md`), and
`**[1, tier 3]**` overrides it: **[1]** routine — the design says exactly what to
write and the tests are mechanical; **[2]** careful — a numeric, geometric or
semantic case to get right within a given design; **[3]** unproven — an
algorithm, an isolation guarantee or a CadQuery semantic whose correctness has
to be established here.

- [x] Step 1 **[3]** — `reward/_iou.py`, both routes, in-process. Fixtures
  `tests/fixtures/reward/<slug>/` (`program.py`, `target.py`, `expected.json`),
  `arris` dialect: IoU 1/3, disjoint 0, touching 0, self 1, cube and double 1/8.
  The sampled route, forced with a budget of 1, lands within 4σ of each closed
  form. A cone pair the kernel refuses comes back `sampled`.
- [ ] Step 2 **[3]** — **ADR-0008**, from `tools/reward_calibrate.py` over the
  slice: `iou_budget`, chord, N and the strata, with each candidate's bias and
  RMSE against the exact route written in the ADR.
- [ ] Step 3 **[3]** — `surface`: seeded area-weighted points, nearest-point
  distances in chunks, the `exp` polynomial (its error bounded against
  `math.exp` in the test only). **ADR-0009**: the formulas and τ, measured.
- [ ] Step 4 **[2]** — `measures` (Jacobi against the closed-form inertia of a
  box and a cylinder) and `topology` (a plate with a round hole against a
  faceted one: below 1, and below the plate against itself, which is 1).
- [ ] Step 5 **[2]** — `RewardConfig`, `Score`, the reward by a `match` on
  `Status` ending in `assert_never`. `hypothesis`: any terms give a reward in
  [0.1, 1]; weights not summing to 1 are refused; the three failure rewards exact.
- [ ] Step 6 **[3]** — the score worker and public `score`. Hostile cases: bytes
  a worker cannot read, a forged frame, a frame out of range, a deadline passed,
  each its status. `hypothesis`: `score` never raises on arbitrary body bytes.
  Self scores reward exactly 1.0.
- [ ] Step 7 **[3]** — field metrics in `reward/_field.py`, from the source above
  and trimesh 4.12.2's voxeliser read and named in `PROVENANCE.md`. Closed forms:
  self 1 and Chamfer 0, cube against double 1, a box's filled voxel count.
- [ ] Step 8 **[2]** — `tools/oracle/benchcad_score.py`, 10 pair programs (a
  cone pair among them), `tests/fixtures/reward/benchcad-scorer/`: their output
  from STEP, repeated to measure the spread of their unseeded sampling. The
  tolerance is measured here and cited from the fixture's README (**ADR-0010**).
- [ ] Step 9 **[1]** — the gate's ban on `reward/`, with its own test; the
  digest of the fixtures' scores equal over three runs, two `PYTHONHASHSEED`s and
  1 against 8 workers; `invalidity_rate` over all rows.
- [ ] Step 10 **[1]** — `tests/test_m4_acceptance.py`, the roadmap's list as
  written; file `../arris/docs/ideas/` asks with step 2's numbers (cone against
  cone, the batch `classify_points`); the backlog line removed.

## Acceptance
`tests/test_m4_acceptance.py`, in the gate, offline: every closed form of the
roadmap's M4 list as written (the failure rewards exact; self 1 on all four
terms and reward 1.0; IoU 1/3, 0 and 1/8; disjoint at most 0.1 + 0.9·0.4; the
faceted hole's `topology` below 1 and below the plate against itself), plus:
- `voxel_iou_64` and `chamfer_x1000` within ADR-0010's tolerance of the committed
  output of BenchCAD's scorer on the 10 pairs;
- the digest of every fixture's `Score` equal across runs (step 9);
- `hypothesis` on `score`'s bytes and the reward's range; the gate green.

## Docs to update on completion
- `docs/ARCHITECTURE.md` §The reward — routes, terms, score worker, `Score`, field
  metrics as built, both IoU `⚠ OPEN`s closed; §Determinism — the budget's step
  count, its `⚠ OPEN` narrowed to programs; §The sandbox — the score job.
- `docs/ROADMAP.md` M4 and the C1 status line; `docs/adr/README.md` (0008–0010);
  `AGENTS.md` current state, next `/plan M5`.
- `GLOSSARY.md` — the four terms above.
- `PROVENANCE.md` — BenchCAD's scorer and trimesh's voxeliser, commit and files read.
- `tools/oracle/README.md` — the two pins and `benchcad_score.py`.
- `CHANGELOG.md` `Unreleased` — `score`, `Score`, `RewardConfig`, reward version 1.
- `docs/BACKLOG.md` — the `classify_points` line removed (step 10).

## Open questions
- ⚠ OPEN (human, by C3's report; does not block this plan): SEED.md's first
  differentiator is exact scoring, and the measurement above sends most
  cone-bearing pairs to the sampled route until arris answers cone against cone or
  binds `classify_points`. Recommended: keep the claim, say "exact where the
  kernel answers", and count `iou_route` in every table from M5.
- *Settled* (agent): scoring failure on a valid body is −1.0, not 0 or a new
  status: it reuses the table, is counted, and cannot be farmed.
- *Settled* (agent, step 1): the sampled route draws uniform points in the box
  holding both bodies, each body meshed at the chord fraction of its own
  diagonal, so a pair built alike meshes alike; no point inside either body
  gives 0. Step 2 replaces the uniform draw if a stratified one wins, and
  sizes N so that empty case does not arise on the slice.
- *Settled* (agent): `benchcad_score.py` runs the 10 pairs on CadQuery outside
  the sandbox, because their scorer reads STEP files and every sandbox mount is
  read-only. The pairs are our own programs; nothing from a corpus reaches it.

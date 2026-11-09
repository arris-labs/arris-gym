# Plan: m5-rescore

- Started: 2026-11-09
- Milestone: M5 (cycle C1, docs/ROADMAP.md)
- Idea: none; the roadmap's M5. Absorbs two `docs/BACKLOG.md` lines: telling a
  scoring failure from a program's, and measuring `transformed`'s libm.
- Branch: `plan/m5-rescore` (step 9 is [CI]).

## Goal
`arris-gym rescore benchcad` runs the 300 slice programs under `cq`, scores each
against the oracle's STEP of the same program read into arris, and writes one
table: a row per program, its status, terms, digests, source and licence, and
aggregates over all 300. From a clean `uv sync --locked`, the table's digest is
equal on two machines of different CPU vendor or architecture; timeouts are
counted, with 0 of them or their rows named.

**Measured while planning** (a scratch run, nothing committed): 300 of 300 oracle
STEPs read by `read_step` as one solid, no healing, `check(body, "full")` ok,
at most 0.07 s each. 200 `ok` programs scored in 35 s on 8 workers; 100
`lobed_knob` end `arris_refusal` (reward −0.5). Mean reward 0.484 over all 300;
0.975 over the 200 valid. IoU is 1.0 on all 200.

## Non-goals
- Model outputs, baselines and `--predictions` (C3); CAD-Recode, a fidelity
  target (C2). Tuning the reward: it stays version 1.
- Regenerating STEPs on the second machine: OCCT across machines is not this
  milestone's claim (ADR-0011); comparing `step_sha256` there is backlog.
- The arris fix for `lobed_knob`: those rows stay −0.5, counted.

## Design deltas
**ADR-0011 (step 1): a target is an oracle STEP, read in a worker, pinned as a
committed file.** The STEP comes from a hostile program through a frame, so
`read_step` is a kernel call on hostile input and runs in a worker. Targets are
committed so that the table depends on the main environment alone.

**Oracle.** `tools/oracle/worker.py`'s frame gains `step_text`: the STEP with
`FILE_NAME`'s timestamp and the translator counter blanked. `OracleReport` gains
`step: str | None`, outside `digest()` and `oracle.jsonl`. `parse_outcome`
recomputes `step_sha256` from the text; a text that contradicts it is a `crash`.
`oracle.jsonl` stays byte-identical.

**Sandbox.** `JobKind.STEP` and `sandbox/_step.py`, a **step worker**: a fresh
model, `read_step`, exactly one `ok` solid, `write_body`. Its bytes then go
through the existing body worker (checker and measures). New public
`read_target(step, *, sandbox=None, timeout=…, memory=…) -> TargetResult`, a
frozen model: `status`, `message`, `refusal`, `body`, `measures`, `step_sha256`,
`versions`; never raises on the text. Zero or several solids are `runtime`
naming the count; a solid's refusal is `arris_refusal` with the kernel's words.
*Settled* (step 2): `TargetResult` also carries `violations`, so a
`checker_fail` target keeps the checker's words, as `ExecResult` does; a file
`read_step` cannot parse (`StepParseError`: garbage, empty, a NUL byte) is
`arris_refusal` by its type, as a program's `ArrisError` is; text the kernel
cannot take (a lone surrogate) is `runtime`. `step_sha256` is None for a text
with no `DATA;`.

**`rescore/`** (imports `sandbox`, `reward`, `census`; the layer rule is
unchanged).
- `RescoreEntry`: name, source, licence, program text, dialect, STEP text.
- `RescoreRow`: name, source, licence, program SHA-256, dialect, the `Stage` a
  failure happened in (`none`, `program`, `target`, `scoring`), the program's
  status and refusal, the candidate's body digest, the target's body digest and
  `step_sha256`, the `Score`, and the versions.
- A target that fails gives a `Score` of status `runtime`, `timeout` or `crash`,
  reward −1.0, as a scorer that fails never pays (`match` on `Status`, ending in
  `assert_never`). `Stage` settles the backlog line: `Score` does not change.
- `RescoreTable`: rows sorted by name; `programs`; counts of every `Status`,
  `Stage` and `IouRoute` with zeros; `invalidity_rate`; `mean_reward` over all
  programs by `math.fsum`, and beside it `mean_reward_valid` with its count,
  labelled as survivors; `timed_out` naming each row and stage; `digest`.
- **The digest** is the SHA-256 of each row's name, statuses, body digests,
  `step_sha256` and `Score.digest()`, then the counts and aggregates as hex
  floats. No `message` of a timeout, nothing wall-clock. Input order does not
  move it.

**`rescore/benchcad.py`**, the first adapter: the pinned corpus, `slice.txt` and
the targets file give the entries. **CLI:** `arris-gym rescore benchcad [--slice F]
[--targets F] [--out DIR] [--workers N]` writes `rescore.json` and `rescore.md`
and prints counts and the digest; no `[corpus]` extra exits 2, as `census` does.

**Targets file.** `tests/fixtures/c1/targets.jsonl.gz`: stem, `step_sha256`, STEP
text, sorted by stem, gzip `mtime=0`, 1.5 MB, attribution in its README.

*Settled* (step 9): the human chose CI (`ubuntu-24.04-arm` against
`ubuntu-latest`) as the second machine. The GitHub remote is theirs to create
(SEED.md §10.1); the `rescore` job fails unless its digest equals the committed
`rescore.json`'s, logs the digest, `lscpu` and glibc, and uploads `rescore.json`.
Step 9 is ticked when both jobs are green, i.e. both digests are equal.

## Steps
A step's grade is its tier (`.agents/tiers.md`): **[1]** routine; **[2]** careful,
a numeric or semantic case; **[3]** unproven, or changes what a worker sends back.

- [x] Step 1 **[3]** — ADR-0011, and the oracle's `step_text`: worker, frame,
  `OracleReport.step`, the hash recomputed by `parse_outcome`. Fixtures: a text
  that contradicts its hash is `crash`. Re-running the slice leaves
  `oracle.jsonl`'s digest at `6bbfb772…`.
- [x] Step 2 **[3]** — `JobKind.STEP`, `sandbox/_step.py`, `TargetResult`,
  `read_target`, public export. Fixtures: a closed-form box's STEP gives its
  volume; garbage, empty, a NUL byte, no solid and two solids each give their
  status; `hypothesis`: arbitrary text never raises. Body bytes equal across two
  runs.
- [x] Step 3 **[1]** — `tools/oracle_run.py --targets` writes the targets file;
  commit it with its README section (`fixtures:` commit). Test, offline: 300
  rows, stems equal `slice.txt`, each hash equal to `oracle.jsonl`'s.
- [x] Step 4 **[2]** — `rescore/_table.py`: `RescoreEntry`, `RescoreRow`,
  `Stage`, `RescoreTable` and its digest. Tests by construction: every count
  over all rows, a `mean_reward` by hand; `hypothesis`: a permutation does not
  move the digest; a table whose digest or counts disagree is refused.
- [x] Step 5 **[2]** — `rescore.rescore(entries, *, sandbox, workers)`: run, read
  each target, score, in submission order. Fixtures, one per stage: a valid pair
  (reward 1.0 for a part against itself by construction), a refusal, a target
  that fails, a scoring failure. Failures are counted and none dropped.
- [x] Step 6 **[1]** — `rescore/benchcad.py` and `arris-gym rescore benchcad`,
  `rescore.md` included; `tests/test_cli.py` through the `Reader` seam.
- [x] Step 7 **[2]** — Run it; commit `tests/fixtures/c1/rescore.json`, `.md` and
  the digest. Two runs at 2 and 16 workers give equal digests. With the `inspect`
  skill, write in the README why each of these holds, or file a Finding:
  `phone_stand` takes the sampled route on all 100 (ADR-0008 saw refusals only
  for cone against cone); its `topology` is 0.80–0.91 where `venturi_tube`'s is
  1.0; `surface` is 0.85–0.89 (ADR-0009's noise floor: exp(−0.0083/0.05) = 0.85).
- [x] Step 8 **[2]** — `tools/rescore_diff.py A B`: from two `rescore.json`, the
  rows that differ and the first stage each differs at (candidate body, target
  body, each term); exit 1 on any. Tests on planted differences.
- [ ] Step 9 **[2] [CI]** — The second machine: CI's `rescore` job on `ubuntu-latest` and `ubuntu-24.04-arm` (`.github/workflows/ci.yml`), a clean clone, `uv sync --locked
  --extra corpus`, the command. Record both digests, CPUs and glibc in the README.
  A difference is diffed by step 8, shrunk to a regression fixture, reported to
  arris if the kernel's; the plan stays open until the digests are equal.

## Acceptance
`uv run --locked --extra corpus arris-gym rescore benchcad` on two machines:
- the table's digest **equal**, of different CPU vendor or architecture;
- 300 rows, statuses `ok` 200, `arris_refusal` 100, every other 0; stages
  `none` 200, `program` 100; timeouts 0 or their rows named;
- `mean_reward` over all 300 (planning measured 0.484) and `mean_reward_valid`
  over its 200 (0.975) both printed, the second labelled; invalidity 1/3;
- every row carries source, licence, arris, numpy and reward versions;
- `oracle.jsonl`'s digest unchanged; the `hypothesis` properties of steps 2 and 4
  hold; the gate is green and offline.

## Docs to update on completion
- `docs/ARCHITECTURE.md` §Modules, §The sandbox (step worker), §The oracle
  (`step_text`), a new §The re-scored table; §Determinism: the digest as measured
  across machines. Drop its "only the package skeleton exists".
- `docs/ROADMAP.md` — M5 landed, with the numbers.
- `AGENTS.md` current state — M5 landed; next `/close-cycle`.
- `GLOSSARY.md` — *Step worker*, *Re-scored table*, *Stage*; *Job* gains the STEP.
- `docs/BACKLOG.md` — remove the two absorbed lines; add the cross-machine
  `step_sha256` comparison and whatever step 7 finds.
- `CHANGELOG.md` — `read_target`, `TargetResult`, `arris-gym rescore`.
- `tests/fixtures/c1/README.md` — targets, table, digests (steps 3, 7, 9).
- `docs/adr/README.md` — ADR-0011.

## Open questions
- ⚠ OPEN (agent, step 9): if `transformed`'s libm moves body bytes across
  architectures (`arris.build.Workplane.rotated`), the rows that call it differ
  and arris must answer. That would hold M5 open: closing it with a
  narrower claim changes C1's scope, which is the human's.

# Plan: m2-oracle-fidelity

- Started: 2026-11-08
- Milestone: M2 (cycle C1, docs/ROADMAP.md)
- Idea: none; verbatim from the human: "/plan M2"

## Goal
CadQuery 2.3.0 on Open CASCADE (`cadquery-ocp==7.9.3.0`) runs a program as an
**oracle worker**: a program worker under the sandbox's warden that execs the
oracle's own interpreter. The program gets the same namespaces, rlimits,
Landlock and seccomp as an arris program, and its result comes back as an
`OracleReport`. `fidelity` compares an `ExecResult` with an `OracleReport`
and produces a `FidelityRow`. The row is an agreement within the agreement
tolerance (ADR-0005), a disagreement with one of the five classes (rules in
ADR-0006), or `unclassified`. One planted fixture per class comes back in
that class. The arris rows export as a consumer report for arris. All 300
slice programs have a committed oracle report, and a second run gives the
same digest.

## Non-goals
- The `cq` dialect: the slice's arris side, and so its fidelity table, are M3.
  Here the arris side is `arris`-dialect programs built to match.
- `arris-gym fidelity` as a command, and verdicts for corpus rows (M3, once
  rows exist to judge). A fidelity target is C2's.
- Oracle speed (one exec per program, no oracle zygote); running a second
  oracle (ADR-0006 accepts its record as evidence; none is run here).

## Design deltas
- **ADR-0004, the oracle worker** (step 2). `sandbox/_isolate` gets a private
  `exec` job. After isolation the worker `execve`s the oracle's interpreter on
  `worker.py`, with the oracle env's prefixes added to the Landlock readable
  roots (read and execute). Its memory limit and `nproc` (OCCT/TBB threads)
  are measured by step 2. The program text is passed on a memfd, and the
  report is one frame on the result pipe. The caller parses the frame and
  trusts none of it, as it does for any worker. There is no public `sandbox`
  API change. As built: the private `JobKind.EXEC` and `sandbox/_exec.py`
  (`ExecSpec`, its payload, `interpreter_spec`), `Limits.executable`; the
  spec and `run_one` start `tools/oracle_run.py`.
- **`tools/oracle/`**: `pyproject.toml` and `uv.lock` (Python 3.12, the two
  pins and their `numpy<2`) and `worker.py`. `worker.py` runs the program,
  takes the result the way ARCHITECTURE §Outcomes says (last `show_object`,
  else `result`), checks it with `BRepCheck_Analyzer`, measures it with
  `GProp`, and writes STEP. **`tools/oracle_run.py`** runs in the main env
  under `mypy --strict`. It drives oracle workers over a list of programs
  and writes `oracle.jsonl` in submission order.
- **`fidelity` public types** (frozen pydantic):
  - `OracleStatus`: `ok`, `syntax`, `runtime`, `no_result`, `invalid`
    (`BRepCheck` fails), `timeout`, `crash`.
  - `OracleReport`: status, message verbatim, measures (volume, area,
    centroid, bounds, face and solid counts), `step_sha256`,
    `program_sha256`, versions (cadquery, OCP, Python), seconds. `seconds` is
    outside every digest.
  - `DisagreementClass`: `cq_bug`, `arris_refusal`, `arris_bug`,
    `occt_wrong`, `by_design`.
  - `Verdict`: a class plus evidence, which is one of a closed form
    (measures), a second oracle's record, a doc or ADR anchor (`by_design`),
    or a regression fixture path.
  - `FidelityRow`: outcome `agree` | `disagree(class)` | `unclassified`, the
    deltas, and both statuses.
  - `compare(result, report, verdict=None) -> FidelityRow`.
  - `FidelityTable`: rows in program order, counts over all programs, and
    `digest`.
  - `arris_rows(table) -> ArrisReport`: a refusal histogram by kind, then
    reason; arris bugs with program SHA-256 and fixture.
- **ADR-0005, the agreement tolerance** (step 4; as built: `fidelity/_agreement.py`'s `MeasureDeltas`, `measure_deltas`, `within_tolerance` and the four constants; the face count is carried, not judged; `worker.py` measures bounds with `AddOptimal`): relative volume and area,
  centroid over the bbox diagonal, and a rule for face counts, whose
  conventions differ between the kernels. The values are measured by step 4
  as named constants in `fidelity`.
- **ADR-0006, the classification rule** (step 5; as built:
  `fidelity/_compare.py`, with `FidelityOutcome`, the evidence types
  `ClosedForm`, `SecondOracle`, `DocAnchor`, `RegressionFixture` and their
  union `Evidence` besides the types above): which status pairs class
  themselves, and which need a `Verdict`. Proposed: arris `arris_refusal`
  → `arris_refusal(kind)`; `crash`/`checker_fail` → `arris_bug`;
  `runtime`/`unsupported_api` → `cq_bug`; both failing → `agree`. A measure
  disagreement, or the oracle failing alone, is `unclassified` until a
  verdict says otherwise. A timeout on either side is counted and named, and
  never classed silently.
- **Layers**: `fidelity` imports `sandbox` types only; `worker.py` nothing
  of `arris_gym`. `check_layers.py` is unchanged.
- Glossary: **oracle worker**, **oracle report**, **agreement tolerance**,
  **verdict**, **fidelity row**, **disagreement class** (sharpening
  *Disagreement*).

## Steps
Grades are tiers (`.agents/tiers.md`): **[1]** routine, the design says
exactly what to write; **[2]** careful, a numeric or semantic case to get
right within the design; **[3]** unproven, correctness established here.

- [x] Step 1 **[2]** — The oracle env. `uv sync --project tools/oracle` resolves
  the two pins on Python 3.12, using `override-dependencies` if cadquery
  2.3.0's own OCP bound refuses 7.9.3.0, with the reason recorded.
  `worker.py` plus `selftest.py`, still unisolated, take a trusted box,
  cylinder and box-minus-hole to their closed forms, and one program to
  each of `syntax`, `runtime`, `no_result`.
- [x] Step 2 **[3]** — ADR-0004 and the oracle worker under the warden. The
  memory limit and `nproc` are measured from the import of `cadquery` and a
  boolean. Test (`-m oracle`): M0's hostile corpus on the oracle gives its
  statuses (fork bomb, 1 GiB under the limit, connect, read outside,
  `os._exit`, segfault), and an infinite loop under `timeout=1.0` returns
  within 2 s.
- [x] Step 3 **[2]** — `OracleReport`, `OracleStatus`, the frame parser,
  and `tools/oracle_run.py`. Property: arbitrary bytes on the result pipe
  give a report or a `crash`, and never raise. A report contradicting its
  status is a `crash`.
- [x] Step 4 **[2]** — The calibration set, ADR-0005. About 20
  `tests/fixtures/fidelity/agree-*/` fixtures, each with `program.py`
  (arris), `oracle.py` (CadQuery text), `oracle.json` (recorded) and
  `expected.json` (closed form): boxes, cylinders, holes, revolves, fillets
  and chamfers. arris against OCCT and both against the closed form set the
  tolerance constants. Test: every pair agrees.
- [x] Step 5 **[3]** — ADR-0006, `DisagreementClass`, `Verdict`,
  `FidelityRow`, `compare`. `match` is exhaustive on `Status` and
  `OracleStatus`. Planted fixtures `tests/fixtures/fidelity/class-*/` (an
  arris program, a planted `oracle.json`, and a `verdict.json` where the
  rule needs one): one per class, plus both-fail `agree`, a measure gap
  without a verdict (`unclassified`) and a timeout. Each comes back as
  expected. Property: `compare` never raises over drawn result and report
  pairs.
- [ ] Step 6 **[2]** — `FidelityTable` and its digest; `arris_rows` and the
  consumer report (JSON plus Markdown). Test: the step 4 and 5 fixtures as a
  table give the expected counts over all rows, a digest that input order
  does not move, and an arris report whose content is expected exactly.
- [ ] Step 7 **[2]** — The slice on the oracle. `tools/oracle_run.py --slice
  tests/fixtures/c1/slice.txt` fetches the 300 programs through
  `census.benchcad` (the `[corpus]` extra, outside the gate) and writes
  `tests/fixtures/c1/oracle.jsonl`, sorted by stem. Each row carries stem,
  family, licence and revision. The status counts and digest go in
  `c1/README.md` with the attribution. A second run gives the same digest. A
  timeout or crash is named. The test checks 300 rows and that the stems
  equal `slice.txt`.

## Acceptance
- `uv run --project tools/oracle tools/oracle/selftest.py` and
  `pytest -m oracle`: the closed forms hold, and the hostile corpus gives its
  statuses under ADR-0004's limits.
- The gate, offline: the ~20 calibration fixtures `agree` under ADR-0005. Each
  `class-*` fixture comes back in its class, both-fail is `agree`, and the
  unverdicted gap is `unclassified`. The `compare` and frame-parser
  properties hold. The table's counts and the arris report match their
  expected files exactly.
- `tests/fixtures/c1/oracle.jsonl`: 300 rows, one per slice stem, with
  status counts stated over 300, two runs with equal digests, and every
  timeout or crash named.

## Docs to update on completion
- `docs/ARCHITECTURE.md` §The oracle: the oracle worker, `OracleReport`,
  `tools/oracle_run.py`. §Fidelity, new: the comparer, the classes and rule
  (ADR-0006), the tolerance (ADR-0005), the table and the arris report.
  §Modules: `fidelity`.
- `tools/oracle/README.md`: the env, `worker.py`, selftest, `-m oracle`.
- `docs/ROADMAP.md` C1 status line: M2 landed. `AGENTS.md` current state.
- `GLOSSARY.md`: the six terms above. `docs/adr/README.md`: 0004–0006.
- `CHANGELOG.md` Unreleased: `fidelity`'s public types and `compare`.

## Open questions
- Settled (step 1): cadquery 2.3.0 imports on OCP 7.9.3.0 with the pins
  unchanged and no override. Its wheel declares no dependencies (listed in
  `tools/oracle/pyproject.toml`), and `Shape.hashCode` needed a one-line
  worker patch for OCP 7.9 (see `tools/oracle/README.md`).
- Settled (step 2): `-m oracle` tests, deselected by `addopts`, command in
  `tools/oracle/README.md`; the exec job itself is in the gate
  (`tests/test_exec.py`). ADR-0004: 1.5 GiB, `nproc` 4, Open CASCADE's pool
  held to one thread (it hangs under `RLIMIT_NPROC`); STEP to memory, and
  `SystemExit` is `runtime`. Start-up is ~1.5 s, so the 1 s loop dies in the
  import (a 5 s test sees the loop reached) and step 7's timeout covers it.
- Settled (step 5): ADR-0006 sharpens the proposed rule. An arris `crash`
  or `checker_fail` agrees only with the oracle failing the same way (`crash`,
  `invalid`), and is `arris_bug` otherwise, the oracle failing included: a
  crash is never an answer. The oracle's `crash` or `invalid` alone and arris
  `syntax` against oracle `ok` are `unclassified`. A verdict may replace the
  rule's class (a refusal of a part OCCT builds wrong is `occt_wrong`), never
  an `agree`. `compare` raises `ValueError` for a verdict on an agreement, an
  `arris_refusal` verdict without a refusal, and a closed form that the
  measures contradict or that neither side measured. Deltas are carried
  whenever both sides measured (oracle `ok` or `invalid`).
- ⚠ OPEN: whether a slice program on which OCCT fails becomes a regression
  fixture now or waits for its M3 row. Agent, step 7: it waits, and the row
  is named in `c1/README.md`.

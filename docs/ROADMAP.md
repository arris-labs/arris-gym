# Roadmap

Every milestone ends with a run that prints numbers, and each retires the
riskiest remaining unknown first. A milestone's "out" list is as binding as
its "in" list. One section per cycle; a finished cycle compresses to its
status line (`/close-cycle`), and the next is appended below.

Spine: **C1** M0 → M5 (the vertical slice), then **C2** (the fidelity gate),
**C3** (re-scored benchmarks), then the later cycles one at a time. Ordering
against arris and laman is `../order-of-work.md`.

---

## Fixtures

The unit of acceptance: a directory `tests/fixtures/<area>/<slug>/` with

- `program.py`: the program, its dialect named in `expected.json`;
- `expected.json`: status and, where applicable, refusal kind and expected
  measures. Expected geometry comes from a closed form or from the part's
  construction.

Measures compare within a named default tolerance unless the fixture's README
cites the ADR that decided another (`tools/check-fixtures.sh`). A message
that the same program's run makes differ by machine (only `crash-abort`'s
signal) is declared per `platform.machine()` as `message_by_machine`, with a
README saying why; a machine with no entry fails to load. A failure
shrunk from a run goes under `regression/` with the desired assertion, strict
`xfail` (`.agents/rules/gym.md`). Corpus programs are not fixtures: a corpus
is pinned by revision and fetched by a command outside the gate; a committed
excerpt keeps its licence's attribution.

---

## C1 — the vertical slice

**Goal.** One path through every module before any is broad.

**The slice.** `BenchCAD/BenchCAD`, config `code_gen` (17,900 programs, 106
families, CC-BY-4.0), at revision
`5919f578ab09ec283603a082fab07c7639ab56eb`. M1's census ranks the families
by how few distinct API forms they need; the first **3** families with at
least 100 programs each, and the first **100** programs of each by `stem`,
make **300** programs, listed in `tests/fixtures/c1/slice.txt`. The census
ranked `phone_stand`, `venturi_tube` and `lobed_knob` first.

**Status: done 2026-11-10.** Retired: can a hostile program cost one status
and nothing else, do `cq`'s stack semantics fit over `arris.build`, and does
the whole path reproduce on another machine? The re-scored table's digest is
equal on x86-64 and aarch64; ADR-0001 to ADR-0011.

### M0 — the sandbox and the harness
Retires: can a hostile program cost one status and nothing else?
- **In:** zygote and program worker (ADR-0001), `ExecResult`, `Status`, the
  `arris` dialect, timeout, memory limit, no network, the filesystem decision,
  result cache, text and PNG dumps, the determinism digest.
- **Out:** `cq`, scoring, corpora.
- **Accept:** a hostile corpus of one program per status, plus a fork bomb, a
  1 GiB allocation under a 512 MiB limit, a connect to a public address and a
  read of a file outside the worker's reach, each returns its expected status;
  an infinite loop under `timeout=1.0` returns within 2 s; 1000 programs, 10%
  of them hostile, give 1000 rows in submission order; a second run makes 0
  executions and identical rows; `run` raises on no text `hypothesis` draws.

### M1 — the census
Retires: what does the corpus actually call?
- **In:** `census`: every API call, selector string and argument form over
  `code_gen`, by family; `arris-gym census`; `slice.txt`.
- **Out:** CAD-Recode (C2), any execution of corpus programs.
- **Accept:** 17,900 programs parsed, each counted or listed as unparsable;
  the same counts on a re-run; `slice.txt` committed with its 300 stems.

### M2 — the oracle and fidelity classes
Retires: can a disagreement be classified, before there is much to classify?
- **In:** `tools/oracle/` on `cadquery==2.3.0`, `cadquery-ocp==7.9.3.0`;
  `fidelity`: the comparer, the five classes, the arris rows' export.
- **Out:** a fidelity target (C2).
- **Accept:** the 300 programs run on the oracle, each with a report; a
  fixture of each disagreement class, planted by construction, comes back in
  that class; the comparison tolerance is measured and decided by ADR.

### M3 — the `cq` subset, first slice
Retires: do CadQuery's stack semantics fit over `arris.build`?
- **In:** `Workplane` and its stack, the sketch calls, `extrude`, booleans,
  `UnsupportedApi`: the 13 API forms the slice's census found (it writes no
  selector, `hole`, `chamfer` or export; those wait for C2's census).
- **Out:** anything the slice does not call.
- **Accept:** the 300 programs run in the sandbox with a status each, every
  disagreement with the oracle classified: **0 unclassified**. Agreement is
  reported, not targeted: the target is set by ADR from this number.

### M4 — reward and metrics
Retires: is the reward right, and bit-stable, on cases with known answers?
- **In:** the IoU and estimator ADRs, the reward weights and τ ADR, and the
  field's metrics from BenchCAD's own scorer.
  [Reward design](ARCHITECTURE.md#the-reward)
- **Out:** tuning the weights on model outputs.
- **Accept**, by closed form:
  - a failure status gives exactly −1.0, −0.5 or −0.3;
  - a body against itself: IoU, surface, measures and topology 1, reward 1.0;
  - boxes `[0,2]×[0,1]²` and `[1,3]×[0,1]²`: IoU 1/3;
  - disjoint bodies: IoU 0, reward at most 0.1 + 0.9·0.4;
  - a cube and a cube scaled by 2 about its corner: IoU 1/8;
  - a plate with a round hole against one with a faceted hole: `topology`
    below 1, and below that of the same plate against itself;
  - voxel IoU and Chamfer ×10³ within the benchmark's own scorer's output on
    10 pairs run through it.

### M5 — the re-scored table
Retires: does the whole path reproduce on another machine?
- **In:** `rescore`'s first adapter, `arris-gym rescore`, one table: the 300
  programs scored against themselves through `cq` and the oracle's STEP.
- **Out:** model outputs and baselines (C3).
- **Accept:** the table's digest equal on two machines of different CPU
  vendor or architecture, from a clean `uv sync --locked`; timeouts counted in
  the table, 0 of them or their rows named.

**Out of C1:** model outputs, baselines, CAD-Recode, a fidelity target,
training.

---

## C2 — the fidelity gate

**Goal.** Grow the `cq` subset in census order and measure its fidelity on
BenchCAD `code_gen` and the CAD-Recode validation split.

**Status: done 2026-11-28.** Reach and classification meet the fidelity
gate, and both tables reproduce on x86-64 and aarch64 against committed
oracle reports (ADR-0012 to ADR-0030).

**In.** Pinned corpora and censuses, reach targets at 85% and 100%, the
admitted `cq` forms including selectors, holes, blends, sketches and
shell, and both classified fidelity tables and arris reports. The consumer
report is filed as `../arris/docs/ideas/arris-gym-c2-fidelity-report.md`.

**Out.** Bare `cq.Workplane()` and `box(..., centered=False)` are deferred
in the [backlog](BACKLOG.md). CadQuery assemblies, sketch constraints,
plugins, `.wrapped`, raw OCP calls, model baselines and training.

**Accept.** On arris 0.12.0, BenchCAD reaches 15,656/17,900 with 12,791
agreements, and CAD-Recode reaches 968/968 with 893 agreements. Both have
zero unclassified rows, timeouts and in-subset `cq_bug` rows.
BenchCAD has two `by_design` corner-patch rows under ADR-0025.
The fixture READMEs record the tables and replay commands.
[BenchCAD](../tests/fixtures/c2/benchcad/README.md#the-table) and
[CAD-Recode](../tests/fixtures/c2/cadrecode/README.md#the-table)

## C3 — re-scored benchmarks

**Goal.** Compare arris-gym scores for model outputs with published
benchmark results, counting every failure.

**Status: open 2026-11-28.**

**In.** Re-score BenchCAD first, then CAD-Recode validation. Include
Text2CAD-Bench if its data is released and the licence permits use. Decide
how to handle compound STEP targets before expanding BenchCAD beyond
the slice. The current reader accepts one solid (ADR-0011), and 827
BenchCAD `ok` oracle reports contain two to nine solids. Run one-shot
frontier baselines and up to three retries with error feedback, plus open
specialists where their licences allow. Report the benchmark's metrics
beside arris-gym's results.

**Out.** Training and an arris-gym-authored benchmark. Spending on model APIs
and contacting the BenchCAD authors are the human's decisions.

**Accept.** Every task has a result row, including failed programs and
targets. The report tables regenerate bit-identically on two machines, and
every benchmark number cited from the literature is verified against its
paper.

## Later cycles, roughly in order

- **Own benchmark, narrow:** editability through provenance, exact B-Rep reconstruction.
- **Training on one RTX 5090:** CadQuery-on-arris track, then `arris.build`; base model by ADR.
- **Design intent with laman:** constrained sketch → laman → `arris.build` profile; diagnostics as reward terms.

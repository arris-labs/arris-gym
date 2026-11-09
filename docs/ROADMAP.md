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
- `expected.json`: status, refusal kind, volume, area, centroid, face and
  solid counts, each from a closed form or from how the part was built, never
  from arris-gym's output.

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

**Status: open.** Docs system, tooling, package skeleton and
`docs/ARRIS_API.md` landed. **M0 landed:** `run`, `run_many`, `Sandbox`, the
cache, `digest`, `dump_text` and `dump_png`, under ADR-0002. **M1 landed:**
`arris-gym census` parsed all 17,900 programs (none unparsable) and fixed the
slice. **M2 landed:** the oracle worker (ADR-0004), `fidelity`'s `compare`,
table and arris report under the agreement tolerance (ADR-0005) and the
classification rule (ADR-0006); all 300 slice programs are `ok` on the oracle,
the same digest on three runs. **M3 landed:** `dialect="cq"` runs the census's
13 API forms; the 300 slice programs run under `cq`: 200 agree with the
oracle, 100 (`lobed_knob`) are an arris bug (chained `fuse` of operands on one
end plane), **0 unclassified**, 0 timeouts. **M4 landed:** `score` and its
`Score` under reward version 1 (ADR-0008, ADR-0009), BenchCAD's field metrics
within ADR-0010's tolerance of its own scorer on 10 pairs; the IoU is exact
where the kernel answers (1,645 of 1,800 slice pairs) and sampled elsewhere
(cone against cone), `Score.iou_route` saying which. Next: M5.

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

### M1 — the census (landed)
Retires: what does the corpus actually call?
- **In:** `census`: every API call, selector string and argument form over
  `code_gen`, by family; `arris-gym census`; `slice.txt`.
- **Out:** CAD-Recode (C2), any execution of corpus programs.
- **Accept:** 17,900 programs parsed, each counted or listed as unparsable;
  the same counts on a re-run; `slice.txt` committed with its 300 stems.

### M2 — the oracle and fidelity classes (landed)
Retires: can a disagreement be classified, before there is much to classify?
- **In:** `tools/oracle/` on `cadquery==2.3.0`, `cadquery-ocp==7.9.3.0`;
  `fidelity`: the comparer, the five classes, the arris rows' export.
- **Out:** a fidelity target (C2).
- **Accept:** the 300 programs run on the oracle, each with a report; a
  fixture of each disagreement class, planted by construction, comes back in
  that class; the comparison tolerance is measured and decided by ADR.

### M3 — the `cq` subset, first slice (landed)
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
- **In:** `reward` (§The reward), the IoU and estimator ADRs, the reward
  weights and τ ADR, the field's metrics from BenchCAD's own scorer.
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

**Goal.** The `cq` subset grows in census order over BenchCAD and the
CAD-Recode validation split until the fidelity table has nothing unclassified
and the target set by ADR after M3 is met.

**In:** census order only. **Out:** CadQuery assemblies, `cq.Sketch`
constraints, plugins, `.wrapped`, raw OCP calls.
**Accept:** 0 unclassified on both corpora; the fidelity target met.
**Decision point:** low fidelity from arris refusals ranks arris's next cycle;
low fidelity from CadQuery semantics narrows the subset.

## C3 — re-scored benchmarks

**Goal.** The first publication. A scorer takes a benchmark's tasks and a
model's outputs and scores them on arris, every failure counted: BenchCAD, the
CAD-Recode validation split, Text2CAD-Bench if its data is released.

**In:** frontier baselines (one shot, and up to three retries with error
feedback), open specialists where their licences allow, the technical report.
**Accept:** report tables regenerate bit-identically on two machines; every
survey number the report cites verified against its paper. Spending on model
APIs and contacting the BenchCAD authors are the human's.

## Later cycles, roughly in order

- **Own benchmark, narrow:** editability through provenance, exact B-Rep reconstruction.
- **Training on one RTX 5090:** CadQuery-on-arris track, then `arris.build`; base model by ADR.
- **Design intent with laman:** constrained sketch → laman → `arris.build` profile; diagnostics as reward terms.

# Architecture

arris-gym is a Python library: it runs model-written CAD programs on the
`arris` kernel in a sandbox, returns a typed outcome for every program, and
scores the result against a target. This document is the design the code is
held to. Only the package skeleton exists so far; the roadmap says what lands
when, and a sentence here describes what a milestone must build until that
milestone lands.

`⚠ OPEN:` marks a question left for implementation time; an ADR closes it.

## Modules

```
src/arris_gym/
  sandbox/   zygote, program worker, ExecResult and Status, result cache
  cq/        the CadQuery-compatible subset over arris.build
  reward/    iou, surface, measures, topology, field metrics, the reward
  census/    parses a corpus and counts the API forms it writes (`arris-gym census`)
  fidelity/  oracle comparison and the disagreement classes
  rescore/   per-benchmark adapters and the report
tools/oracle/  its own uv env: CadQuery/OCP, run and never imported
```

Later cycles add `describe/`, `synth/`, `train/` (behind the `[train]` extra)
and `sketch/` (SEED.md §7, Layout). None exists until its cycle opens.

**The layer rule**, held by `tools/check_layers.py` in the gate:

| Module | May not import |
|---|---|
| everything in `src/` | `cadquery`, `OCP`, `tools` |
| `sandbox`, `reward`, `cq` | `arris_gym.train`, `arris_gym.rescore` |
| `cq` | anything but the standard library, `arris` and `arris_gym.cq` |

`cq` keeps its boundary so it can become its own package (`arris-cq`) once
fidelity is good. It never moves into the `arris` repository, whose API is
not shaped by CadQuery's semantics.

## Outcomes

`run` never raises on a program. It returns a frozen `ExecResult`:

```python
class Status(enum.Enum):
    OK, SYNTAX, RUNTIME, UNSUPPORTED_API, ARRIS_REFUSAL, CHECKER_FAIL, TIMEOUT, CRASH

class ArrisRefusal(BaseModel):   # set exactly when status is ARRIS_REFUSAL
    kind: str                    # the exception's class name: "OpDegenerateError"
    message: str                 # str(exception), verbatim
    entities: tuple[str, ...]    # the ids it names, as the message writes them

class ExecResult(BaseModel):
    status: Status
    message: str                 # what a model sees on a retry; verbatim
    refusal: ArrisRefusal | None
    body: BodyRef | None         # set exactly when status is OK or CHECKER_FAIL
    measures: Measures | None    # set exactly when status is OK
    violations: tuple[str, ...]  # the checker's, for CHECKER_FAIL
    program_sha256: str
    dialect: Dialect
    versions: Versions           # arris, numpy, arris-gym
    seconds: float               # outside every digest: wall-clock is not a result
```

`BodyRef` is the worker's `write_body` bytes and their SHA-256, which it
checks on construction. `Measures` is the volume, area, centroid, bounds,
face and shell counts, genus and a face-kind histogram (kind and count pairs,
sorted by kind), so a fixture or a digest needs no worker. `ExecResult`
refuses a combination its status contradicts: a refusal without
`ARRIS_REFUSAL`, a body without `OK` or `CHECKER_FAIL`, measures without `OK`, violations without
`CHECKER_FAIL`.

`status` is a plain enum so that `result.status is ag.Status.OK` holds as in
SEED.md §5; the refusal's kind lives beside it. **The kind is the exception's
class name.** The wheel has no finer vocabulary: a fillet too large for its
edge raises `OpDegenerateError` with a `reason`, so the seed's illustrative
`blend-too-large` is not a kind that exists. The refusal histogram groups by
class and, within it, by `reason` where the class carries one.

How each status is decided, always from a type or from how the process ended,
never from a message's wording:

| Status | Decided by |
|---|---|
| `syntax` | `SyntaxError` from `compile`, before anything runs |
| `unsupported_api` | `cq.UnsupportedApi`, raised by the subset, naming the call |
| `arris_refusal` | an `arris.ArrisError` subclass; `arris.build`'s `SelectionError` and `SketchError` are subclasses too |
| `runtime` | any other exception, `SystemExit` and `MemoryError` included; a program that ends without a result; or body bytes the body worker cannot read for any reason but the checker's |
| `checker_fail` | the body worker's `read_body` raises `BodyRejectedError`, or its `check(body, "full")` is not `ok` |
| `ok` | the body worker read the body back and the checker accepts it |
| `timeout` | the deadline passed; the warden killed the worker |
| `crash` | a worker ended without delivering a valid frame: a signal, an exit (`os._exit`, a kernel abort), a frame missing, oversized, unparseable or contradicting its status |

A crash's message names the worker and the signal or exit code, then the
last `STDERR_TAIL_BYTES` (4 KiB) of the worker's stderr, where a kernel abort
writes its reason; stdout goes to `/dev/null`. An `abort` in the program
worker ends by `SIGSEGV` on x86-64: the kernel does not deliver the
`SIGABRT` to PID 1 of a namespace, and glibc falls back to its abort
instruction.

**Where a program's result comes from.** In the `cq` dialect, the argument of
its last `show_object` call, else a module-level `result`: BenchCAD programs
assign `result` and end in `show_object(result)`. In the `arris` dialect, the
module-level `result`, a `Solid`. The census counted BenchCAD's end forms:
all 17,900 programs end in `show_object(result)`. ⚠ OPEN: what CAD-Recode's
programs end in (C2), and what a Workplane holding several solids scores as
(M3).

## The census

`arris_gym.census` parses a corpus and counts what its programs write; it runs
none of them (ADR-0003).

- **Parse, never run.** `census_program` reads one `CorpusProgram` with
  `ast.parse` in the caller's process. Any exception out of parsing or
  counting (`SyntaxError` including a NUL byte, `RecursionError`,
  `MemoryError`) makes the program an `Unparsable` with the class and message
  verbatim; the census never raises on a program. Parsing and counting run
  on a fresh thread with a fixed stack, because `ast.parse`'s depth limit
  follows the C stack depth of its caller; every traversal is iterative.
- **What is counted.** Per program: calls as `receiver.name`
  (`Workplane.extrude`), each with its **API form** (the argument kinds and
  sorted keyword names), the **selector string** of a `faces`-style call,
  calls on a receiver the census cannot place (`?`, listed with their text),
  calls on `builtin` and other modules (`foreign`, counted, not ranked), and
  the program's end form.
- **The ranking.** Per family: distinct calls, then distinct selector
  strings, then distinct API forms, ascending, ties by name. `select_slice`
  takes the first 3 families with at least 100 programs and the first 100
  stems of each.
- **The report.** `CensusReport` is a frozen model of sorted `(key, count)`
  tuples; its `digest` is the SHA-256 of its canonical JSON, and input order
  does not move it. A report whose digest disagrees with its content is
  refused.
- **The corpus.** `census.benchcad` downloads `code_gen` at the pinned
  revision with `huggingface_hub` and reads `stem`, `family` and `code` with
  `pyarrow`; both are the `[corpus]` extra, imported lazily. A row count other
  than 17,900 raises.
- **The command.** `arris-gym census --corpus benchcad [--out DIR]` writes
  `census.json` and `slice.txt` and prints totals and the digest; without the
  extra it exits 2. The committed run is `tests/fixtures/c1/`: 17,900 parsed,
  none unparsable, 106 families, slice `phone_stand`, `venturi_tube`,
  `lobed_knob`.

## The sandbox

**A program runs alone, on a fresh model, in a forked process** (ADR-0001),
**as PID 1 of its own namespaces, under a warden** (ADR-0002).

```
caller ─ socket ─▶ zygote ──fork──▶ warden ──fork──▶ program worker (PID 1)
                   arris, numpy,    namespaces,      setsid → stdio → fds closed
                   cq imported;     mounts read-only; → rlimits → Landlock
                   builds nothing   deadline, status   → seccomp → compile → exec
                                                       → write_body → result pipe
```

- The **zygote** is a clean interpreter started by `subprocess`: forking the
  caller would be unsafe, since a training loop has threads. Its environment
  is `OPENBLAS_NUM_THREADS=1` and `PYTHONHASHSEED=0`, nothing else from the
  caller's. It imports everything once and never builds, so every fork starts
  with `arris.build`'s default model unmade. It serves many forks and is
  replaced if it dies. Before serving, it probes that it can isolate a
  worker; where it cannot, starting it raises `SandboxUnavailable`.
- **Transport**: one job is one message on a `SOCK_SEQPACKET` socket pair:
  its kind, deadline and memory limit, with four descriptors passed by
  `SCM_RIGHTS`, the write ends of the job's status, result and stderr pipes,
  which the caller creates, and a memfd holding the payload, which the worker
  reads. The zygote forks the warden, closes its own copies and reaps it; it
  never reads a status, a result or a worker's stderr, which run from the
  warden and the worker straight to the caller. The warden and the worker close every descriptor
  they were not given, the job socket among them. The caller reads at most
  `MAX_RESULT_BYTES` (64 MiB) of a result and keeps none of one past it; it
  waits for the status a **backstop** (2 s) past the deadline, then gives the
  job up and replaces the zygote. A warden outlives its zygote and keeps its
  deadline, so a zygote's death costs only the jobs it held unforked.
- The **program worker** reads the text, compiles and runs it, decides the
  status by type (the table above) and writes one **frame**, a JSON document
  of status, message, refusal and the result's `write_body` bytes (base64),
  to the result pipe; only the worker writes it, never a process the program
  forked, which returns through the same code holding the same pipe, so a
  forking program's status does not turn on scheduling. It neither checks
  nor measures: the program reaches
  everything in its process, the `Solid`'s model included. A frame with a
  body goes to a **body worker**, a second job under the same limits and the
  same deadline, which reads the bytes into a fresh model, runs the checker
  and the measures, and writes a frame of its own (status, message,
  measures, violations). The caller parses each, and a frame that is
  missing, oversized, unparseable or contradicts its status is a `crash`,
  whole; so is a program frame claiming a status only the body worker or
  the caller decides. A worker's frame counts only if the warden saw it
  complete its isolation and exit with code 0.
- The **warden** is one fork per program. It enters new user, network, PID,
  mount and IPC namespaces, makes every mount read-only, forks the program
  worker and reports how it ended on a status pipe the worker never holds,
  with whether the worker completed its isolation before the program ran.
- The **program worker** is PID 1 of that PID namespace. Nothing survives it:
  when it ends the kernel kills every process it left, `setsid` or not, so
  there is no state to reset and no worker to recycle after a crash.
- **Timeout**: the warden owns the deadline, polls the worker's pidfd until it
  and then sends `SIGKILL`. A worker that ignores every signal still ends.
- **Memory**: `RLIMIT_AS` before the program starts. An allocation past it
  raises `MemoryError` (`runtime`); a failure inside the kernel that aborts
  is `crash`. `RLIMIT_CORE` is 0. `memfd_create` and `shmget`, whose memory
  the limit does not count, are refused.
- **Network**: an empty network namespace, in which a connect fails with
  `ENETUNREACH`; a socket of any family but `AF_INET` and `AF_INET6` is
  refused, Unix sockets included (seccomp).
- **Filesystem**: Landlock allows reading only beneath the interpreter's
  prefixes, the site-packages directories and `arris_gym`'s own directory;
  nothing is written anywhere, since every mount is read-only, and no file is
  `execve`d. An exec job (ADR-0004) reads its spec's paths instead, and its
  `execve` reaches its interpreter and that interpreter's ELF loader alone.
  The loader runs any file the job can read (Landlock cannot refuse
  `mmap` with `PROT_EXEC`), under every other limit here.
- **Processes**: `RLIMIT_NPROC` is 4, counted per user namespace: the warden,
  the worker and two more tasks. A fork bomb stops there.
- **Concurrency**: the caller's `workers=N` bounds the live forks. Results
  come back in submission order whatever order workers finish in.

Where user namespaces, Landlock, `mount_setattr` or seccomp are missing, the
sandbox refuses to start rather than run unisolated. It is Linux-only, on
x86-64 and AArch64. ⚠ OPEN: macOS and Windows, or a statement that scoring is
Linux-only and other platforms use a container; Docker's default seccomp
profile refuses the user namespace the sandbox needs.

**Threat model.** A program is hostile. The boundary is the process and the
namespaces; nothing relies on restricting Python's builtins inside it. Every
limit is one the program cannot lift: rlimits are hard, its capabilities are
dropped, and the read-only mounts are locked against a nested namespace. A
program can reach its own result pipe, so nothing it delivers is trusted:
a **body worker**, forked under a warden with the same limits, reads the body
back with `read_body` and runs the checker, and the caller only reads what
the body worker reports. What stays visible outside the readable directories
is metadata (that a path exists, its size and times), never content. Syscall
filtering beyond ADR-0002's list waits until a hostile program shows the need.

**The cache** maps `hash(program, dialect, memory, nproc limit, arris, numpy,
arris-gym versions)` to the result. SEED.md §6 keys it on the program, dialect
and arris version; the limits join them because a program can catch
`MemoryError` and go on, and arris-gym's version stands for `cq`'s until they
split. `timeout` is not in the key, since no outcome that depends on it is
stored: never `timeout`, `crash`, or a `MemoryError` (known by type: a frame
says it ended on one). `Sandbox(cache_dir=None)` keeps results in memory; given
a directory, one JSON (the result without its body) and one body file by key,
each written by rename, the JSON last; a torn entry is a miss. `executions`
counts programs actually run. Nothing the cache holds is reachable by a worker.

## Dialects

`dialect="arris"` runs `arris.build` as it is. `dialect="cq"` runs the subset.
Both yield the same `ExecResult`.

`cq` is an API-compatible reimplementation over `arris.build`, nothing copied:
`Workplane` and its stack, the sketch calls, `extrude`, booleans, selectors,
STEP export, grown in census order. Inside the worker it is installed as
`sys.modules["cadquery"]`, so `import cadquery as cq` runs unchanged, and
`show_object` is a builtin of the program's namespace. A call outside the
subset raises `UnsupportedApi` naming it, via `__getattr__`, never
`AttributeError`.

⚠ OPEN: how CadQuery's string selectors map onto arris's selection when they
are ambiguous on curved faces.

## The reward

SEED.md §7.1 is the definition:

```
status ∈ {syntax, runtime, unsupported_api, timeout, crash} → -1.0
status = arris_refusal(kind)                                → -0.5
status = checker_fail                                       → -0.3
valid body                                                  →  0.1 + 0.9·S
S = 0.6·IoU + 0.15·surface + 0.15·measures + 0.10·topology
```

`score(result, target)` reads both bodies into one fresh model, inside a
worker like any other kernel call on a body a program made: a kernel crash in
scoring costs a status, not the run. Weights, τ and N live in a frozen
`RewardConfig` with a version, written into every result row, and a change
that can move a reward bumps it.

**The field's metrics sit beside ours** under `s.field`: voxel IoU, Chamfer
×10³ and invalidity rate, computed as the benchmark's own scorer does
(`benchcad_core/scoring/iou.py` for BenchCAD, read at M4), so numbers compare
with published ones. Theirs and ours never share a name.

⚠ OPEN: **the IoU method** until `classify_points` lands. SEED.md §7.1 assumes
a mesh winding number; measured on arris 0.10.0, three routes exist today:

| Route | Measured | For | Against |
|---|---|---|---|
| Boolean: `vol(A∩B) / (vA + vB − vol(A∩B))` | two overlapping boxes: 1/3 to rounding | exact, no sampling, no seed | a boolean can refuse; disjoint bodies raise `OpDegenerateError`, so `interference` must decide that first |
| `ray_fire` parity per point | 6144 points, a 10-face body: 4.6 s, inside count equal to the closed form's | exact per point, always answers | Python loop, ~0.75 ms a point, twice per score: too slow for RL |
| Mesh winding number | chord 0.05 on a Ø4 hole: mesh volume 877.98 against 874.34 | vectorised, never refuses | error bounded by the chord; 0.4% here |

Recommended for the ADR: the boolean, falling back to sampling when it
refuses, the row saying which method answered.

⚠ OPEN: **the sampled estimator.** The seed's N/2 points near the target
surface are not volume-uniform, so counting them with the uniform N biases
IoU upward near the boundary. Either weight the strata or let the near-surface
stratum feed only `surface`. Closed with the reward weights and τ.

## Determinism

The same program gives the same body, ids and score on every machine.

- **Body bytes depend on the model's history** (ADR-0001), and a fresh model
  reproduces them exactly: across processes, under different `PYTHONHASHSEED`,
  with `write_step` likewise. So the body's digest is the SHA-256 of the
  worker's `write_body` bytes.
- **Those bytes are not stable across a round trip.** `read_body` renumbers
  ids, so `write_body` after it gives other bytes (once: a second trip changes
  nothing), while measures keep their bits. A digest is never taken from a
  body that has been read back.
- **On a score's path, `numpy` keeps to operations IEEE 754 rounds exactly or
  that do not round**: elementwise `+ − × ÷`, `sqrt`, comparisons, `min`,
  `max`, `sort`, `count_nonzero` and `PCG64` draws. Sums go through
  `math.fsum`, which is exactly rounded and so independent of order.
- **Outside that set**: `@`, `np.dot` and `np.linalg.*` follow the BLAS build;
  `np.exp`, `np.sin` and friends follow the CPU's SIMD dispatch; `math.exp`
  follows the platform's libm. So `exp(−d/τ)` and the principal moments'
  eigenvalues are written in `reward/` from the exact operations alone (a
  fixed polynomial, fixed Jacobi sweeps). A transcendental whose result only
  feeds a threshold, as a winding number's does, is allowed.
- **Reported, not hidden**: a `timeout` is the one status a slower machine can
  change. ⚠ OPEN: whether the kernel's `budget` argument can give a work limit
  that is the same everywhere, leaving wall-clock as a backstop.

The determinism digest is the SHA-256 of a report's rows in program order,
each row carrying status, refusal, body digest and measures as hex floats, and
nothing wall-clock. It is the acceptance: equal on two machines.

## The oracle

`tools/oracle/` is its own `uv` environment holding CadQuery and OCP. It takes
a program, runs it on Open CASCADE out of process, and reports JSON: status,
volume, area, centroid, face and solid counts. Library code never imports it
(`tools/check_layers.py`); `fidelity/` reads its reports. It pins BenchCAD's
own `cadquery==2.3.0` and `cadquery-ocp==7.9.3.0`, so the comparison is with
the kernel the benchmark's numbers came from. Those need `numpy<2`, one more
reason it cannot share an environment with the library.

A program runs on the oracle in an **oracle worker** (ADR-0004): a program
worker forked and isolated as any other, which then execs the oracle's
interpreter on `tools/oracle/worker.py` and keeps every limit across the exec.
Its reach is the oracle environment's prefixes, its memory limit 1.5 GiB (the
import of cadquery and OCP maps 875 MiB), and Open CASCADE's thread pool is
held to one thread so a boolean runs within `RLIMIT_NPROC`. Each program pays
about 1.5 s of start-up. `tools/oracle_run.py` builds the exec spec and sends
the job; the frame comes back on the result pipe and is trusted no more than
any worker's.

`fidelity.parse_outcome` turns that outcome into an **oracle report**
(`OracleReport`: an `OracleStatus` of `ok`, `syntax`, `runtime`, `no_result`,
`invalid`, `timeout` or `crash`, the message verbatim, measures, STEP hash,
versions). It never raises: a frame that is unparseable, claims a status only
the caller decides, contradicts its status or carries another program's
SHA-256 is a `crash`. `tools/oracle_run.py` runs a list of programs and writes
`oracle.jsonl` in submission order.

Two measurements **agree** when volume, area, centroid and bounds are each
inside the **agreement tolerance** (`fidelity/_agreement.py`, ADR-0005), set
from the calibration set `tests/fixtures/fidelity/agree-*`; face counts are
carried in the deltas and never judged.

**Fidelity** classifies each disagreement as `cq` bug, arris refusal (kind),
arris bug, Open CASCADE wrong (closed form or second oracle, arris ADR-0015),
or semantic difference by design (documented). `fidelity.compare(result,
report, verdict=None)` gives a **fidelity row** (`FidelityRow`): `agree`,
`disagree` with its **disagreement class**, or `unclassified`. The rule
(ADR-0006) classes what the two statuses settle. An arris refusal, crash or
checker failure, or a `runtime` where the oracle builds the part, has a
class. Two ordinary failures agree. Two `ok` sides agree inside the agreement
tolerance. A measure gap, the oracle failing alone and a timeout on either
side are `unclassified` until a **verdict** (a class and its evidence: a
closed form, which `compare` checks, a second oracle's record, a doc anchor
for `by_design`, or a regression fixture) classes them. A verdict may also
replace the rule's class, except the `arris_bug` of an arris crash or checker
failure. An unclassified row makes a cycle red. The arris
rows leave as a consumer report (arris ADR-0020).
`fidelity.fidelity_table(entries)` gathers rows under their program names,
each entry with its program's source and licence and each row with the
versions both sides ran under, into a **fidelity table**: sorted by name, counts over all programs (each
status, class and outcome with its zeros, timeouts named) and a digest that
input order does not move. `fidelity.arris_rows(table)` cuts the **arris
report** from it (`to_json`, `to_markdown`): a histogram of refusals by
kind, then by the kernel's message, and the arris bugs with their program
SHA-256 and regression fixture, under the licences and the arris, numpy and
oracle versions of all the table's rows.

## Inspection

Everything is checkable without a GUI: a result dumps to text that diffs in a
test and to a PNG through arris's tessellation (`dump_png`: a mesh worker tessellates
the body, a `numpy` z-buffer draws four fixed views). Pictures are for the agent's
eyes; acceptance is numbers (`inspect` skill).

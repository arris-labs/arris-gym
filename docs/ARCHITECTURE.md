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
  census/    CadQuery corpus parsing and API counts
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
    violations: tuple[str, ...]  # the checker's, for CHECKER_FAIL
    program_sha256: str
    dialect: Dialect
    versions: Versions           # arris, numpy, arris-gym
    seconds: float               # outside every digest: wall-clock is not a result
```

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
| `runtime` | any other exception, `SystemExit` and `MemoryError` included; or a program that ends without a result |
| `checker_fail` | the program ended with a body and `check(body, "full")` is not `ok` |
| `ok` | the program ended with a body the checker accepts |
| `timeout` | the parent's deadline passed; it killed the process group |
| `crash` | the process ended without delivering a result: a signal, or an exit (`os._exit`, a kernel abort) |

**Where a program's result comes from.** In the `cq` dialect, the argument of
its last `show_object` call, else a module-level `result`: BenchCAD programs
assign `result` and end in `show_object(result)`. In the `arris` dialect, the
module-level `result`, a `Solid`. ⚠ OPEN: what CAD-Recode's programs end in,
and what a Workplane holding several solids scores as. Settled by the census.

## The sandbox

**A program runs alone, on a fresh model, in a forked process** (ADR-0001).

```
caller ── pipe ──▶ zygote ──fork──▶ program worker (one per program, then gone)
                   arris, numpy,    setsid → rlimits → unshare → compile → exec
                   cq imported;     → check → write_body → result on a pipe
                   builds nothing
```

- The **zygote** is a clean interpreter started by `subprocess`: forking the
  caller would be unsafe, since a training loop has threads. It imports
  everything once and never builds, so every fork starts with `arris.build`'s
  default model unmade. It serves many forks and is replaced if it dies.
- The **program worker** is one fork per program. Nothing survives it, so
  there is no state to reset and no worker to recycle after a crash.
- **Timeout**: the parent owns the deadline, and kills the worker's process
  group with `SIGKILL`. A worker that ignores everything still ends.
- **Memory**: `RLIMIT_AS` before the program starts. An allocation past it
  raises `MemoryError` (`runtime`); a failure inside the kernel that aborts
  is `crash`. `RLIMIT_CORE` is 0.
- **Network**: `os.unshare(CLONE_NEWUSER | CLONE_NEWNET)` before the program
  starts: an empty network namespace, in which a connect fails with
  `ENETUNREACH`. Where unprivileged user namespaces are forbidden the sandbox
  refuses to start rather than run unisolated.
- **Processes**: `RLIMIT_NPROC` bounds a fork bomb. ⚠ OPEN: a descendant that
  calls `setsid` leaves the process group the deadline kills; a PID namespace
  closes that, to be measured in M0.
- **Concurrency**: the caller's `workers=N` bounds the live forks. Results
  come back in submission order whatever order workers finish in.

The sandbox is Linux-only for now: it needs `fork`, `os.unshare` and
`resource`. ⚠ OPEN: macOS and Windows, or a statement that scoring is
Linux-only and other platforms use a container.

**Threat model.** A program is hostile. The boundary is the process and the
namespaces; nothing relies on restricting Python's builtins inside it. A
program can reach its own result pipe, so nothing it delivers is trusted: the
parent reads the body back with `read_body` and runs the checker itself.
⚠ OPEN: the filesystem. A worker can still read files, and in a training loop
a program that opens the target's file games the reward. A mount namespace or
Landlock closes it; to be chosen with M0's hostile corpus. Syscall filtering
is not planned until a hostile program shows the need.

**The cache** maps `hash(program, dialect, arris version, cq version)` to the
result. SEED.md §6 keys it on the first three; `cq`'s version joins them
because a `cq` change moves results as surely as an arris change does. Only
outcomes that are functions of that key are cached: never `timeout`, `crash`,
or a `MemoryError`, which depend on the machine and the limits.

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

**Fidelity** classifies each disagreement as `cq` bug, arris refusal (kind),
arris bug, Open CASCADE wrong (closed form or second oracle, arris ADR-0015),
or semantic difference by design (documented). Nothing stays unclassified. The
arris rows leave as a consumer report (arris ADR-0020).

## Inspection

Everything is checkable without a GUI: a result dumps to text that diffs in a
test and to a PNG through arris's tessellation. Pictures are for the agent's
eyes; acceptance is numbers (`inspect` skill).

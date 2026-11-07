# Gym rules: what a scoring backend owes its callers

Rules an application never writes down. They apply to all of `src/` and
`tools/`; the reasons are in `SEED.md` §5 and §9 and `docs/ARCHITECTURE.md`.

## Correctness

- **`run` never raises on a program.** Whatever a program does (a syntax
  error, an infinite loop, `os._exit`, a segfault in the kernel) comes back
  as an `ExecResult` with a `Status`. An exception out of `run` is a bug in
  arris-gym, and only a caller's mistake (an unknown dialect, a non-positive
  timeout) raises.
- **Failures are counted, never dropped.** Every program of a corpus has a
  row, and every aggregate states its denominator: all programs, not those
  that executed. An average over survivors is reported only beside the
  all-programs figure and is labelled so.
- **The kernel's words are kept verbatim.** An arris error's class, message
  and entities go into the result unchanged: they are the feedback a model
  sees on a retry. Never paraphrased, truncated or mapped to a friendlier
  name.
- **A status is matched exhaustively.** A `match` on `Status` ends in
  `assert_never`, so a new status fails `mypy --strict` at every dispatch
  until it is handled. No `case _:` over `Status`.
- **Tolerances and weights are named, never a literal.** A `1e-9` in an
  algorithm is a bug: it is a named, commented constant in one place. The
  reward's weights, τ and N live only in its versioned config.
- **The reward's version moves with its meaning.** A change that can move any
  reward, however slightly, bumps the version and says so in the commit.

## Determinism

Same program, same pinned versions, same bits on every machine.

- **A program starts from a fresh model.** Body bytes depend on the model's
  history (ADR-0001), so no state survives from one program to the next.
- **Pinned**: `arris` and `numpy` exactly, both recorded in every result row
  with the reward's version.
- **Seeded**: `numpy.random.Generator(PCG64(seed))` with an explicit seed; no
  global RNG, no `random`, no time or PID reaching a result.
- **No order from a `set`.** String hashing is salted per process: a `set` or
  `frozenset` of strings is sorted before its order can reach a result, a
  digest or a report.
- **A fixed summation order.** Every reduction that reaches a score is over
  an array in a fixed order, on one thread.
- **No BLAS and no vectorised transcendentals on a score's path.** `np.dot`,
  `@`, `np.linalg.*`, `np.exp` and `np.sin` take a code path chosen by the
  BLAS build or the CPU, so their last bits differ between machines.
  `docs/ARCHITECTURE.md` §Determinism says what to use instead.
- **Wall-clock time reaches a status, never a score.** `timeout` is the one
  outcome a slower machine can change: it is never cached, and a report
  counts its timeouts so a difference can be traced to them.
- **The digest decides.** A claim of determinism is a digest equal across
  machines, never an argument.

## The sandbox

- **The boundary is the process.** A model-written program is hostile input:
  it runs only inside a sandbox worker, never in the caller's process, and
  never through `exec` anywhere else. The Python inside a worker is not a
  security boundary; nothing relies on restricting builtins.
- **Limits are enforced from outside.** A warden outside the program
  worker owns the deadline and kills the worker by its pidfd with `SIGKILL`;
  the worker is PID 1 of its own PID namespace, so its end kills everything
  it left behind (ADR-0002). Memory is a hard rlimit set before the program
  starts; the network is removed before the program starts.
- **A hung or dead worker costs one program, never the run.** The result is
  a status and the pool carries on.

## The boundaries

- **The layer rule** (`docs/ARCHITECTURE.md` §Modules, held by
  `tools/check_layers.py`): `sandbox`, `reward` and `cq` never import `train`,
  `rescore` or anything under `tools/`; `cq` imports only `arris`.
- **The oracle is run, never imported.** CadQuery and OCP exist only in
  `tools/oracle/`'s own environment. No library module, test or fixture
  loader imports them; results cross as JSON.
- **Nothing of CadQuery's shape goes into `arris`.** A semantic difference is
  absorbed in `cq` or documented; arris is asked for kernel capabilities
  only, through `../arris/docs/ideas/`. This repository never edits arris code.
- **A disagreement has a class.** Every fidelity row is `cq` bug, arris
  refusal (kind), arris bug, Open CASCADE wrong (closed form or second
  oracle) or semantic difference by design. "Unclassified" is a red cycle,
  never a footnote.

## Data

- **Every row carries its licence.** Program, dialect, target, measures,
  source, **licence**, arris version, reward version. Weights inherit the most
  restrictive licence of their data. CC BY-NC data never reaches a row or
  artefact that does not say so.
- **Corpora are pinned to a revision** and never committed whole. A committed
  excerpt keeps its licence's attribution beside it.
- **Downloaded programs are model-written programs**: untrusted, sandbox only.

## Testing

- **Fixtures by construction or analysis.** Expected values come from a closed
  form or from how the part was built, never from arris-gym's own output.
  The oracle answers only when those run out; a closed form or a second
  oracle settles a disagreement with it (arris ADR-0015).
- **Every failure becomes a fixture.** A program that crashes, hangs or
  disagrees is shrunk to a minimal case and committed under
  `tests/fixtures/regression/<slug>/` with the *desired* assertion, marked
  `xfail` (strict, so the fixing commit has to lift it). Never kept as
  accepted behaviour, never deleted once fixed. Procedure: `inspect` skill.
  An arris crash is also reported to arris as a fixture candidate. The gate's
  `tools/check-fixtures.sh` refuses a `"tolerance"` outside `regression/`
  unless the fixture's README cites the ADR that decided it.
- **Property tests over hand-picked cases** (`hypothesis`): random programs
  by construction, shrinking to fixtures. "`run` never raises" is a property
  over arbitrary text, not an assertion.
- **A test that reaches the network is not in the gate.** Corpus runs are
  commands of their own; the gate works offline from committed fixtures.

## API

- **`mypy --strict` holds everything**: `src`, `tests` and `tools`. No `Any`
  in a public signature except where a dependency's stub gives it.
- **Results and configs are frozen `pydantic` models.** A docstring says what
  an item guarantees and refuses; a public operation has a runnable example.
- **A public type or signature change is a design delta** in the plan and is
  named in the commit body and the changelog. Allowed pre-1.0, never silent.
- **`docs/ARRIS_API.md` is generated** from the wheel's own stubs
  (`tools/gen_arris_api.py`) and is the reference for what arris offers; the
  gate fails when it differs from the pinned wheel. An `arris` bump
  regenerates it and re-runs the fidelity table in the same plan.

## References

- CadQuery (Apache-2.0) is read for API behaviour and reimplemented over
  `arris.build`: no code copied. A behaviour taken from its source is named
  in `PROVENANCE.md`. Published metrics are implemented from the paper or the
  benchmark's own scorer and cited in the module that uses them.
- Numbers from `docs/BENCHMARK-SURVEY.md` are unverified until read in the
  paper; a report cites only what was verified.

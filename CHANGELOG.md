# Changelog

What a consumer of arris-gym can now do, the statuses they will see, and each
break with its fix. Pre-1.0, `0.y.z` is `y` breaking.

## Unreleased

- `score(result, target)` gives an `ExecResult` its reward against a target
  body, under reward version 1 (`DEFAULT_REWARD`), as a frozen `Score`:
  `syntax`, `runtime`, `unsupported_api`, `timeout` and `crash` get -1.0,
  `arris_refusal` -0.5, `checker_fail` -0.3, and a valid body
  `0.1 + 0.9·S` over its IoU, surface, measures and topology terms, each in
  [0, 1]; a body scored against itself gets exactly 1.0. `Score.iou_route`
  (`IouRoute`: `exact` or `sampled`) says whether the kernel answered the IoU
  exactly or it was estimated from seeded points. A valid body is scored in a
  worker of its own (`sandbox=`, `timeout=` 30 s, `memory=`): when scoring
  fails the score is `runtime` with the kernel's words, `timeout` or `crash`,
  and its reward -1.0. `RewardConfig` and `RewardWeights` set the weights, τ,
  sample counts and seed; a config's `version` is written into every `Score`,
  and `Score.digest()` hashes its numbers. A valid body's `Score.field`
  (`FieldMetrics`) holds BenchCAD's own metrics beside ours, computed as its
  scorer does: `voxel_iou_64`, in [0, 1], and `chamfer_x1000`, at least 0.
  Both normalise each body to its own box, so they ignore size and place (a
  cube against its double gives 1 and 0), and neither moves the reward. The
  Chamfer samples are seeded, so a body against itself gives exactly 0.
- `invalidity_rate(scores)` is the share of all given scores whose status is not
  `ok` (BenchCAD's invalidity rate): every failure counts, and no scores raise
  `ValueError`.
- `run(program, dialect="cq")` (also `run_many`, `Sandbox.run`) runs a
  CadQuery program: `import cadquery as cq` gives a subset over `arris.build`
  and `show_object` is available. The subset covers `Workplane("XY")`,
  `Vector`, `transformed`, `box`, `circle`, `extrude`, `union`, `cut`,
  `moveTo`, `lineTo`, `polyline`, `close` and `revolve`. A program's result
  is the last `show_object` argument, else `result`. Any other call, name,
  import or argument form ends `unsupported_api` naming it; a result that is
  not one solid is `runtime` (none) or `unsupported_api` (several).
  `Dialect.CQ` is new.
- `arris_gym.fidelity` compares an `ExecResult` with an oracle report of the
  same program run on CadQuery 2.3.0 and Open CASCADE 7.9.3.0.
  `compare(result, report, verdict=None)` returns a frozen `FidelityRow`:
  `agree` (volume, area, centroid and bounds within a named tolerance), a
  `disagree` with its `DisagreementClass` (`cq_bug`, `arris_refusal`,
  `arris_bug`, `occt_wrong`, `by_design`), or `unclassified` until a `Verdict`
  with its evidence (a closed form, a second oracle's record, a doc anchor or a
  regression fixture) classes it. Each row carries both sides' statuses,
  measure deltas and versions; a timeout on either side is `unclassified` and
  named. `compare` raises `ValueError` for a verdict it cannot accept (one on an
  agreement, or one that would clear an arris crash).
- `fidelity.parse_outcome` turns an oracle worker's outcome into an
  `OracleReport` (`OracleStatus`: `ok`, `syntax`, `runtime`, `no_result`,
  `invalid`, `timeout`, `crash`) and never raises: a report that contradicts
  itself is a `crash`.
- `fidelity.fidelity_table(entries)` gathers rows, each with its program's
  source and licence, into a `FidelityTable`: sorted by name, counts over every
  row, and a digest that input order does not move. `fidelity.arris_rows(table)`
  gives an `ArrisReport` for the arris kernel (`to_json`, `to_markdown`):
  refusals by kind then the kernel's message, arris bugs with their program's
  SHA-256 and fixture, and the licences and versions behind them.

- `arris-gym census --corpus benchcad` parses BenchCAD's `code_gen` programs
  without running any and writes `census.json`: every CadQuery call, selector
  string and argument form by family, each program counted or listed as
  unparsable with its exception verbatim, under a digest that a re-run
  reproduces. It needs the `arris-gym[corpus]` extra (without it the command
  prints one line and exits 2). `arris_gym.census` offers `census_program`,
  `census`, `select_slice`, `slice_families` and `CensusReport` for the same from Python.
- `arris_gym.run(program)` runs one `arris`-dialect program alone in an
  isolated process and returns a frozen `ExecResult` with a `Status`: `ok`
  (with the body and its measures), `syntax`, `runtime`, `unsupported_api`,
  `arris_refusal` (the kernel's class, message and entities verbatim),
  `checker_fail`, `timeout` or `crash`. It raises only for a caller's mistake
  (an unknown dialect, a non-positive timeout or memory limit) or
  `SandboxUnavailable` where the machine cannot isolate a program. Linux only,
  with user namespaces, Landlock, `mount_setattr` and seccomp (on Ubuntu
  24.04, `kernel.apparmor_restrict_unprivileged_userns` must be 0).
- `arris_gym.run_many(programs, workers=N)` runs many programs, at most `N`
  alive at once, and returns one result per program in submission order.
  `arris_gym.Sandbox` is the same as an object you can close, safe to call
  from several threads.
- `Sandbox(cache_dir=...)` caches results exactly: the same program under the
  same limits and versions is not run twice (`Sandbox.executions` counts the
  runs). A `timeout`, a `crash` or a `MemoryError` is never cached.
- `arris_gym.dump_text(result)` writes a result as text, a line per field, to
  read or `diff`; `arris_gym.digest(results)` hashes results in order, floats
  exact and wall-clock time left out, so two runs are equal when their
  digests are.
- `arris_gym.dump_png(result, path)` draws a result's body as a PNG, four
  fixed views of the part in one greyscale sheet, to look at.
- A program that forks no longer comes back as a `crash` on some runs and
  `ok` on others: only the program's own process reports, so a fork bomb is
  always a `runtime` error (`BlockingIOError`) and a program that forks and
  then builds a part is always `ok`.

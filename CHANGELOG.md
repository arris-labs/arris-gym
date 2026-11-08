# Changelog

What a consumer of arris-gym can now do, the statuses they will see, and each
break with its fix. Pre-1.0, `0.y.z` is `y` breaking.

## Unreleased

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

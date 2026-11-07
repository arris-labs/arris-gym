# Changelog

What a consumer of arris-gym can now do, the statuses they will see, and each
break with its fix. Pre-1.0, `0.y.z` is `y` breaking.

## Unreleased

- `arris_gym.run(program)` runs one `arris`-dialect program alone in an
  isolated process and returns a frozen `ExecResult` with a `Status`: `ok`
  (with the body and its measures), `syntax`, `runtime`, `unsupported_api`,
  `arris_refusal` (the kernel's class, message and entities verbatim),
  `checker_fail`, `timeout` or `crash`. It raises only for a caller's mistake
  (an unknown dialect, a non-positive timeout or memory limit) or
  `SandboxUnavailable` where the machine cannot isolate a program. Linux with
  user namespaces and Landlock only.
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

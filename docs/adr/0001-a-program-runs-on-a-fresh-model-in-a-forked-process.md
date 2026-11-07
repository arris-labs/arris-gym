# ADR-0001: A program runs on a fresh model in a forked process

- Status: accepted
- Date: 2026-11-07

## Context

SEED.md §6 asks for a "worker pool restarting after crash or timeout", which
reads as long-lived workers running program after program. SEED.md §5 asks that
the same program give the same body, ids and score on every machine.

Measured on arris 0.10.0 with one program (a box less a cylinder), comparing
`write_body` bytes:

| Program ran on | Bytes equal to a fresh model's |
|---|---|
| another fresh `Model()`, same process | yes |
| a fresh process, another `PYTHONHASHSEED` | yes |
| a model that had already built something | no |
| that model after `retain([])` | no |
| `arris.build`'s default model, second program in the process | no |

`arris.build.default_model()` is one model per process, and it is what a
program gets when it passes no `model=`. So a reused worker gives a program
different bytes depending on what ran before it, and a cached result would
depend on scheduling. Resetting the default would mean reaching into a private
module global of the wheel.

Forking from a process that has imported `arris`, `arris.build` and `numpy` and
built nothing, 50 times: every child produced the same bytes as a fresh model,
at a median of 9.7 ms a program, kernel work included. A cold interpreter that
imports the same modules costs 68 ms before any work. Importing leaves one
thread, so the fork is safe.

## Decision

A **zygote**, a clean interpreter started by `subprocess`, imports everything
and builds nothing. Each program runs in its own **program worker**, forked
from the zygote, and ends with it. No process ever runs two programs.

The seed's pool is read as a bound on live forks. "Restart after crash" reduces
to replacing the zygote if it dies; a dead worker needs no replacing.

## Consequences

- No state can leak between programs, so there is nothing to reset, and a
  result cannot depend on scheduling. The cache is exact.
- Crash handling is the same path as normal exit: the worker is gone either way.
- The sandbox needs `fork`, so it is POSIX-only. Linux is the first target
  (`docs/ARCHITECTURE.md` §The sandbox).
- The zygote must never build anything, or every fork inherits a used default
  model. A test holds it: two programs through one zygote give equal bytes.
- ~10 ms a program bounds throughput per core at about 100 programs a second,
  ample beside rollouts that take seconds.
- A body's digest is taken from the worker's bytes, never after `read_body`,
  which renumbers ids.

## Alternatives considered

- **Long-lived workers that reset between programs.** Fastest, and rests on a
  private global of the wheel; `retain([])` was measured not to reset ids. A
  public model reset in arris would make this possible but buys nothing that
  matters at 10 ms a program.
- **A new interpreter per program.** Simple and portable, at about 7× the
  start-up cost. It remains the fallback for a platform without `fork`.
- **Forking the caller.** No zygote to manage, but a training loop has threads
  and CUDA state, and forking those is unsafe.

# ADR-0013: An oracle zygote imports CadQuery once and wards a child per program

- Status: accepted
- Date: 2026-11-12
- Amends: ADR-0004 (the oracle zygote it left out of scope)

## Context

Under ADR-0004 every oracle program pays the import of cadquery and OCP
before its first line runs: an exec'd interpreter, then about 1.5 s of
import. C2 runs the oracle over whole corpora, BenchCAD `code_gen`'s 17,900
programs and CAD-Recode's 968 (`plans/fidelity-target`), so start-up becomes
the run's cost. ADR-0004 named the way out: fork after the import. The
question is how to fork without loosening ADR-0002's boundary, and without
moving a single report.

Two constraints from ADR-0004 hold. The library's zygote cannot import
CadQuery, because the oracle needs its own environment (`numpy<2`) and the
layer rule. And `RLIMIT_NPROC` is 4 per user namespace, with the warden and
the worker counted.

## Decision

**An oracle zygote is an oracle worker that serves.** It is started as
ADR-0004 starts an oracle worker: an exec job, forked and isolated by the
library's zygote and warden, then `execve` of the oracle's interpreter on
`tools/oracle/worker.py`, now with `--zygote`. An exec job may carry a fifth
descriptor, a **channel** (`Zygote.execute(..., channel=)`), which the worker
keeps across the exec beside the payload and result. The oracle zygote
imports cadquery and OCP once and creates the one-thread pool, so nothing has
been built. It then says `ready` on the channel and serves jobs one at a time.

A job on the channel is its deadline (a `CLOCK_MONOTONIC` instant: no time
namespace is entered, so the caller's clock is the zygote's), plus four
descriptors passed by `SCM_RIGHTS`: the write ends of the status, result and
stderr pipes, and a memfd of the program's text. These are the same
descriptors the library's zygote takes for a job. The caller makes the memfd,
since the worker's seccomp filter refuses `memfd_create`.

**The zygote is its child's warden.** For each job it forks one child. The
child takes its own session, Python's `SIGINT` handler, dumpable, the job's
stderr, and nothing but the job's descriptors, then runs `run_program` as the
exec'd worker would and writes its frame from its own pid only. The zygote
polls the child's pidfd to the deadline and `SIGKILL`s it there. It then
sweeps: `kill(-1, SIGKILL)` from PID 1 reaches every other process of the PID
namespace, and the orphans are reparented to it, so it reaps them, repeating
until no child is left. Only then does it write the child's ending to the
status pipe, in the warden's own record (`_isolate.parse_ending`): exited,
signalled, timed out, or unavailable with the errno of a refused fork. The
caller reads the three pipes with the library zygote's `_collect` under its
backstop, so `parse_outcome` reads an oracle zygote's outcome exactly as it
reads a fresh worker's.

**The child keeps every limit by inheritance.** It holds the namespaces
(uid nobody, no network, read-only mounts), the rlimits, `no_new_privs`, the
Landlock domain and the seccomp filter that the zygote was isolated with
before its exec. It holds the zygote's memory only as a copy: a module the
program changes, a process it leaves behind, a file it fails to write and
the tasks it holds all end with it.

**The zygote guards itself against its child.** The zygote and child share a
uid. PID 1 of a namespace receives a signal from inside it only for a
handler it installed. Python installs one for `SIGINT`, so the zygote ignores
`SIGINT`, and the other signals have none. The zygote is not dumpable, so a
child can neither ptrace it nor open its memory, whatever Yama's setting;
Landlock already refuses `/proc`.

**Concurrency is several zygotes.** `tools/oracle_run.py`'s `OracleZygote`
is one zygote's handle, one program at a time. `run_many` keeps `workers` of
them. A zygote that dies or stops answering costs that program its record
(`ending` None, a `crash`), and the handle starts a new one for the next. The
zygote's own deadline, its warden's, is `ZYGOTE_LIFETIME` (600 s). The handle
replaces a zygote before a program whose deadline and backstop would pass
it, so a zygote that stopped answering lingers that long at most.
`DEFAULT_TIMEOUT` stays 30 s, so that no report moves.

Measured on this machine (Linux 7.0, x86-64, 32 logical processors, Python
3.12.3, cadquery 2.3.0 on OCP 7.9.3.0):

| Probe | Result |
|---|---|
| a trivial program (`x = 1`), start to report, on a fresh oracle worker | median 1,420 ms (1,388 to 1,435, 5 runs) |
| the same on an oracle zygote's child | median 17.6 ms (14.8 to 19.8, 60 runs on 3 zygotes) |
| an oracle zygote's start, import included, with its first program | median 1,206 ms (3 starts) |
| the slice's 300 programs through oracle zygotes, at 16 and at 4 workers | `oracle.jsonl` digest `6bbfb772…add68b` both times, byte-equal to C1's fresh-worker file; `targets.jsonl.gz` byte-equal too; 7 s each run, the corpus read included |
| on one zygote: a fork bomb, a program that leaves a sleeping child in its own session, a change to a cadquery class and `sys.modules`, a write outside reach, a 1 GiB allocation, `os._exit(0)`, a segfault, an infinite loop | each its one report (`BlockingIOError`, the program's own error, `EROFS`, `MemoryError`, no frame, `SIGSEGV`, timed out at 1 s); each time the next program on the same zygote sees no changed state, no file and a free task, and the zygote is not replaced |

## Consequences

- An oracle program starts in about 18 ms instead of 1.4 s. A whole corpus
  costs its programs' own time, and the slice takes seconds instead of
  minutes.
- A program still meets an interpreter in which nothing has been built. The
  translator's per-process counter and the STEP timestamp are blanked as
  before (ADR-0011), and every child forks from the same unchanged parent, so
  a report's bytes do not move (`tests/test_oracle_worker.py` holds a child's
  frame byte-equal to a fresh worker's, and the slice's rows to C1's).
- The program is no longer PID 1: the zygote is. `os.getpid()` in a program
  differs from a fresh worker's, and nothing in a report depends on it.
- A program has one task to spare under `RLIMIT_NPROC` 4 instead of two: the
  warden, the zygote and the child count. A program needs none, since
  arris-gym builds on one thread and the pool has one thread. A fork bomb
  meets `BlockingIOError` one fork sooner, with the same message.
- The deadline is kept by trusted code inside the boundary instead of a
  warden outside it. The zygote runs only `worker.py`'s serve loop. A child
  cannot signal it (except by a handler it does not install), cannot ptrace
  it, and cannot write its memory. If it could stop the zygote answering,
  the caller's backstop still ends that program as a `crash`, and the
  library's warden still kills the zygote at its lifetime.
- ezdxf's cache warning goes once to the zygote's stderr, not into each
  program's stderr tail: a crash's message no longer begins with it.
- A program can still forge its own report (ADR-0004). It cannot forge the
  status record, which the zygote writes after the child and every leftover
  process are dead.
- `run_one` (a fresh worker per program, ADR-0004) stays for the worker's
  own tests and as the reference a zygote's report is held equal to.

## Alternatives considered

- **A separate warden process per child inside the zygote**, as ADR-0002
  wards a worker: it cannot sweep with `kill(-1)` without killing the zygote.
  To make the child PID 1 it would have to nest a user and PID namespace per
  program. It also adds a task under `RLIMIT_NPROC`, which would leave a
  program none.
- **Several programs at once on one zygote**: `RLIMIT_NPROC` 4 has no room,
  and a sweep after one program would kill the others. Several zygotes give
  the same concurrency.
- **Raising `RLIMIT_NPROC` for the oracle zygote**: the limit then depends
  on the protocol, not the program, and it is not needed.
- **Using the payload memfd as the channel**: the payload is read before
  the exec to find the spec, so a socket in its place would tie the spec's
  framing to the channel's. A descriptor of its own keeps the exec job's
  payload what it was.
- **Keeping ADR-0004's worker per program**: about 1.4 s a program, about
  seven hours of import serially over BenchCAD's 17,900 programs.

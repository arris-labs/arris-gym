# ADR-0004: The oracle worker execs the oracle's interpreter inside a program worker

- Status: accepted
- Date: 2026-11-08

## Context

The oracle (CadQuery 2.3.0 on `cadquery-ocp` 7.9.3.0, `tools/oracle/`) runs
the same programs as `cq` on arris, and a corpus program is hostile input on
the oracle too. Its environment cannot be the library's: it needs `numpy<2`,
and the layer rule keeps CadQuery and OCP out of every process that imports
`arris_gym`. So the zygote, which imports `arris` and `numpy` 2, cannot fork
an oracle program the way it forks an arris one (ADR-0001). The question is
how the oracle gets ADR-0002's isolation without a second copy of it.

Measured on this machine (Linux 7.0, x86-64, 32 logical processors, Landlock
ABI 8), with the oracle's interpreter exec'd inside an isolated program
worker:

| Probe | Result |
|---|---|
| `execve` of the venv's `bin/python` (a symlink to `/usr/bin/python3.12`) with execution allowed on the interpreter alone | `EACCES`: the kernel opens the ELF loader for execution too; allowed on both, it runs |
| `execve` of the interpreter's real path | runs, but outside its venv: the path called tells Python its `pyvenv.cfg` |
| `import cadquery`, no `HOME` | ezdxf asks the password database for a home, which the worker cannot read: `KeyError` at import |
| the same with `HOME=/nonexistent` | imports; ezdxf warns on stderr that it cannot create its cache, and writes nothing |
| after the import | 1 thread, `VmSize` 875 MiB, resident 507 MiB |
| a filleted box with a hole, then five booleans on a sphere and a cylinder, Open CASCADE's default thread pool | 29 more threads (one per logical processor); `VmSize` 1.6 GB after the first boolean, 3.1 GB after five |
| the same under `RLIMIT_NPROC` 4 | the pool cannot start its threads and the first boolean hangs until the deadline |
| the same with the default pool created first with one thread (`OSD_ThreadPool.DefaultPool_s(1)`) | 1 thread, `VmSize` stays at 875 MiB; both volumes bit-equal to the 32-thread run's |
| STEP written by `STEPControl_Writer.WriteStream` to memory, against `cq.exporters.export` to a file | equal data sections, so equal `step_sha256` |
| one trivial program, start to report, four runs | 1.47 to 1.51 s, nearly all of it the import |
| M0's hostile programs (fork bomb, 1 GiB, connect, `/etc/passwd`), `os._exit`, a segfault, an infinite loop | `BlockingIOError`, `MemoryError`, `ENETUNREACH`, `PermissionError`; no frame; `SIGSEGV`; killed at the deadline |

`cadquery` runs every boolean with `SetRunParallel(True)` on that pool,
whose size is the machine's processor count.

## Decision

**An oracle worker is a program worker that execs.** The sandbox gets a
private job kind, `EXEC` (`sandbox/_exec.py`). Its payload is an **exec
spec**, followed by the program's text. The spec gives the interpreter as it
is called, its arguments, its whole environment, the paths it may read and
the files it may execute. The zygote reads the spec and forks the warden and
program worker exactly as for any job. The worker's Landlock domain reads
the spec's paths in place of the zygote's, and executes nothing but the
interpreter's real path and its ELF loader. Once armed, the worker `execve`s the
interpreter, keeping the payload and result descriptors. Namespaces,
rlimits, `no_new_privs`, the Landlock domain and the seccomp filter all
survive the exec. The program never runs in a process that was not isolated.

**The oracle's spec** (`tools/oracle_run.py`) is built by asking the oracle's
own interpreter for its prefixes and site-packages, a trusted run with no
program in it. Those paths and `tools/oracle/worker.py` are the reach. The
interpreter runs `-s -P -B` in the zygote's environment plus
`HOME=/nonexistent`. `worker.py` reads the text from the payload descriptor
and writes one JSON frame to the result descriptor, only from the pid it
started as, so a child the program forked writes nothing. The caller trusts
the frame no more than any other worker's.

**Limits**: `RLIMIT_AS` 1.5 GiB: the 875 MiB import plus about what 512 MiB
leaves an arris program beyond its own import, and below the import plus a
1 GiB allocation. `RLIMIT_NPROC` stays ADR-0002's 4. Since the default pool
cannot start under it, `worker.py` creates the pool with one thread before
any program runs. That bounds the tasks, keeps the address space at the
import's, and stops a report from depending on the machine's processor
count.

**STEP is written to memory** (`WriteStream`), with `Shape.exportStep`'s
settings: an oracle worker can write no file.

## Consequences

- The oracle has the same boundary as arris: everything in ADR-0002's
  Consequences holds for it, with its own environment's directories as the
  readable ones. A program on the oracle can execute nothing but the
  oracle's own interpreter.
- An oracle program costs about 1.5 s of start-up before its first line
  runs, against ADR-0001's 10 ms. A deadline under that times every program
  out during the import, so the oracle's timeout covers the start-up. The 300
  programs of the slice take about eight minutes serially. An oracle zygote
  (fork after the import) stays out of scope until speed matters.
- Every oracle run writes ezdxf's two-line cache warning to its stderr, ahead
  of anything the program writes.
- A program can enlarge the pool itself. It then hangs to its deadline or
  fails to start threads, and that costs only that program.
- The sandbox runs any interpreter a caller names in a spec. The caller is
  trusted, as it is with every payload. Nothing a program writes reaches a
  spec.

## Alternatives considered

- **Isolating the oracle in `tools/`** with a warden of its own: a second
  copy of ADR-0002's isolation, free to drift from the first.
- **Raising `RLIMIT_NPROC` to the processor count plus two** for the pool:
  the limit, the memory (3.1 GB measured) and possibly the result would then
  depend on the machine.
- **An oracle zygote**, forked after `import cadquery`: start-up drops to
  milliseconds, but the zygote holds OCP's state, and the plan puts speed out
  of scope. It remains the next step if the slice's run time matters.
- **Executing the interpreter's real path**: Python finds its venv from the
  path it was called by, so the oracle's packages would not be found.

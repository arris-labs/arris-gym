# ADR-0002: The program worker is PID 1 of its own namespaces, under a warden

- Status: accepted
- Date: 2026-11-08

## Context

ADR-0001 runs each program in a program worker forked from a zygote.
`docs/ARCHITECTURE.md` §The sandbox left two questions open: what the worker
may read and write, and how a descendant that calls `setsid`, and so leaves
the process group the deadline kills, is ended. Measured on this machine
(Linux 7.0, x86-64, arris 0.10.0, Landlock ABI 8):

| Probe | Result |
|---|---|
| `import numpy`, default environment | 32 threads, VmSize 1.35 GB: ADR-0001's "importing leaves one thread" does not hold, and a 512 MiB `RLIMIT_AS` is exceeded at fork |
| the same with `OPENBLAS_NUM_THREADS=1` | 1 thread, VmSize 117 MB; arris builds on that one thread |
| a Landlock ruleset reading only the Python prefixes, in a user and network namespace | `/etc/passwd`, `~/.bashrc`, a repository file and every write give `PermissionError` |
| the same worker, `connect` to a pathname Unix socket | **connects**: `/run/user/1000/bus` (the session bus) and `/var/run/docker.sock` (root on the host, through the `docker` group) |
| the same worker, `chmod`, `utime`, `setxattr` on the user's file | **succeed**; `keyctl` reads the caller's session keyring |
| `mount_setattr("/", AT_RECURSIVE, MOUNT_ATTR_RDONLY)` in a fresh user and mount namespace | 0.6 ms; then `chmod`, `utime`, `setxattr`, `truncate`, `unlink` and every create give `EROFS` |
| clearing that flag, capabilities dropped; and from a nested user namespace | `EPERM` both: a nested namespace's copies are locked read-only |
| `RLIMIT_NPROC` in a user namespace | counted per namespace; concurrent workers do not share the count |
| PID 1 of a PID namespace | `abort` and a segfault end it by signal; its own `kill(SIGKILL)` is ignored; when it ends, every process of the namespace is killed |
| fork chain with user, network and PID namespaces and a second fork | 6.0 ms a program, against 4.1 ms for a plain fork |
| 600 bit flips of `write_body` bytes, read back | valid 219, `BodyDecodeError` 182, `BodyRejectedError` 136, `StaleHandleError` 56, `BodyPrecisionError` 7 |

Landlock governs opening a file. It does not govern connecting to a socket
by its path, a file's mode, times or extended attributes, or the kernel's
keyrings. The user namespace has no uid map, so the worker keeps the
caller's kernel uid and every permission check on the caller's files passes.

## Decision

**The chain is zygote → warden → program worker.** The **warden** is forked
from the zygote for one program. It enters new user, network, PID, mount and
IPC namespaces, makes every mount read-only (`mount_setattr`, recursive), and
forks the program worker, which is PID 1 of the new PID namespace: when it
ends, the kernel kills every process it left, `setsid` or not. The warden
owns the deadline (a pidfd polled until it, then `SIGKILL`) and writes how the
worker ended to a status pipe the worker never holds. `PR_SET_PDEATHSIG` is not
used: a program can clear it. This replaces "the parent kills the process
group".

**Before the program, the worker**: leaves the session; reads stdin from
`/dev/null` and sends stdout and stderr where the caller says, else to
`/dev/null`; closes every descriptor it was not given; sets `RLIMIT_AS` to the
memory limit, `RLIMIT_NPROC` to 4 and `RLIMIT_CORE` to 0, hard; sets
`no_new_privs`; enters a **Landlock** domain that handles every filesystem
right of the kernel's ABI and allows only reading beneath the interpreter's
prefixes, the site-packages directories and the directory `arris_gym` is
imported from; drops its capabilities; and installs a **seccomp filter** that
refuses with `EACCES` a socket of any family but `AF_INET` and `AF_INET6`,
`io_uring` (it would create sockets past the filter), the keyring calls, and
`memfd_create` and `shmget` (memory `RLIMIT_AS` does not count), and kills a
call made under another architecture or x86-64's x32 ABI. Then it writes one
byte to an **armed** pipe the warden reads: an ending without it is a worker
that never completed its isolation and ran nothing of the program's.

**Without user namespaces, Landlock, `mount_setattr` or seccomp the sandbox
refuses to start** rather than run a program less isolated; it runs on x86-64
and AArch64.

**The zygote's environment** is `OPENBLAS_NUM_THREADS=1` and
`PYTHONHASHSEED=0`, nothing else from the caller's. The first corrects
ADR-0001's premise, not its decision; a test holds one thread. The second
keeps a program's own `set` of strings from moving its body between zygotes.

**Nothing from a program worker is trusted.** The caller does not read a
body back: that would put hostile bytes through the kernel in the caller's
process. A **body worker**, forked by the zygote under a warden with the same
limits, runs `read_body`, `check(body, "full")` and the measures on the bytes
the program worker delivered. `BodyRejectedError` is `checker_fail` with the
report's violations; any other error reading the bytes is `runtime`, kept
verbatim. A program worker's own claim of a failure is accepted, since it
costs only that program: a program can forge a refusal, as raising an
`ArrisError` itself would, and so earn −0.5 for its −1.0.

## Consequences

- A connect to a public address fails with `ENETUNREACH`; a Unix socket of
  any kind, abstract or by path, cannot be created (`PermissionError`).
- Nothing outside the readable directories is read; an editable install
  exposes its package directory and nothing else of the repository. Nothing
  is written anywhere, its metadata included.
- A fork bomb stops at two forks (the warden and the worker count). Each
  task may hold `memory`, so a program holds at most three times the limit;
  the kernel's pipe buffers, bounded per user by `pipe-user-pages-soft`, are
  the memory left outside it.
- What remains visible outside the readable directories is metadata: that a
  path exists, its size and times. No content.
- The seccomp filter is a list of named calls, each refused for a measured
  route. A call the kernel adds later is allowed until an ADR adds it; a
  filesystem right a later Landlock ABI adds is unhandled, hence allowed,
  until the ABI table lists it.
- The sandbox is Linux-only. Docker's default seccomp profile is expected to
  refuse `unshare(CLONE_NEWUSER)`, so the sandbox would refuse to start in a
  default container; Ubuntu 24.04 restricts unprivileged user namespaces
  through AppArmor unless lifted. ⚠ OPEN: macOS, Windows and containers stay
  the platform question of `docs/ARCHITECTURE.md` §The sandbox.
- A program costs one more fork and about 2 ms against ADR-0001's plain fork.

## Alternatives considered

- **Landlock alone**, as first planned. Measured insufficient: the session
  bus, the Docker socket, file modes and the keyring stay reachable.
- **A mount namespace with `pivot_root` to a minimal root.** It would hide
  the sockets as well, but needs bind mounts and `pivot_root` through `ctypes`
  and a tree to maintain; a read-only flag and a socket-family filter do the
  same in two calls.
- **A seccomp allow-list.** Tighter, and brittle against the system calls
  Python, numpy and arris make, which change with their versions.
- **A memory cgroup** for an exact bound. It needs a delegated cgroup, which a
  library cannot assume; `RLIMIT_AS` with the task bound stands until a
  caller needs better.
- **Killing the process group**, or `PR_SET_PDEATHSIG`: a `setsid`
  descendant leaves the first, and a program clears the second.
- **The caller reading the body back**, as §The sandbox first said: hostile
  bytes through the kernel in the caller.

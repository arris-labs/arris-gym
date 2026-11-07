# Plan: m0-sandbox

- Started: 2026-11-07
- Milestone: M0 (cycle C1, docs/ROADMAP.md)
- Idea: none; ADR-0001 and `docs/ARCHITECTURE.md` §Outcomes, §The sandbox are
  the design. Verbatim from the human: "/plan M0"

## Goal
`arris_gym.run` and `run_many` execute `arris`-dialect programs, each alone in
an isolated process, and every program comes back as a frozen `ExecResult`
with one of the eight statuses, whatever it does. A hostile program costs one
status: it cannot reach the network or a file outside the worker's reach,
outlive its deadline, or take down the run. Results are cached exactly, dump
to text and PNG, and reduce to a determinism digest.

## Non-goals
- `cq` beyond the `UnsupportedApi` exception; scoring; corpora; the CLI (M1).
- Two machines' digests agreeing: that is M5. M0 proves it across zygotes.
- `budget` as a work limit and macOS, Windows or a container: both `⚠ OPEN:`s
  stay open. Syscall filtering beyond ADR-0002's measured list.

## Design deltas
Measured on this machine (arris 0.10.0, kernel 7.0, 32 cores) for this plan:

| Probe | Result |
|---|---|
| `import numpy`, default environment | **32 threads**, VmSize 1.35 GB: ADR-0001's "one thread" does not hold, and a 512 MiB `RLIMIT_AS` is already exceeded at fork |
| same, `OPENBLAS_NUM_THREADS=1` | 1 thread, VmSize 117 MB; a 1 GiB `bytearray` under 512 MiB raises `MemoryError` |
| fork + box-less-cylinder, median | 4.1 ms plain; 6.0 ms with user+net+pid namespaces and a second fork |
| Landlock, read allowed on the Python prefixes only | ABI 8; a lazy stdlib import and a build work; `/etc/passwd`, `~/.bashrc`, a repo file and any write give `PermissionError`; but a path Unix socket (`docker.sock`), `chmod`, `utime`, `setxattr`, `keyctl` **succeed** (step 1) |
| connect in the namespace | `OSError(101)`, `ENETUNREACH` |
| `RLIMIT_NPROC=16` in a user namespace | counted per namespace: 14 forks, then `BlockingIOError`; concurrent workers do not share the count |
| PID 1 of the namespace | `abort` and a segfault end it by signal; its own `os.kill(SIGKILL)` is ignored |
| 600 bit flips of `write_body` bytes | read and valid 219, `BodyDecodeError` 182, `BodyRejectedError` 136, `StaleHandleError` 56, `BodyPrecisionError` 7; check false after a successful read: 0 |
| `Model.from_native_json`, doctored | loads, but `Body` has no constructor and old handles are foreign: no route to a bad body |

**ADR-0002** (step 1) decides, closing two `⚠ OPEN:`s of §The sandbox:
- *Filesystem*: **Landlock**, read on the interpreter's prefixes and
  site-packages. *Settled* (step 1, measured): Landlock leaves Unix sockets
  and metadata open, so a mount namespace made read-only by one
  `mount_setattr` and a seccomp filter (socket families, io_uring, keyrings,
  memfd, shm) join it; no `pivot_root`. Without any of them the sandbox
  refuses to start, as it does without user namespaces.
- *Escaping descendants*: a **PID namespace**; the program is its PID 1, so
  its end kills every descendant, `setsid` or not.
- *The fork chain*: PID 1 needs a process outside the namespace to wait on
  it, so zygote → **warden** → program worker. The warden owns the deadline
  (`pidfd` + `SIGKILL`) and relays the wait status. `PR_SET_PDEATHSIG` is not
  used: a program can clear it. This replaces "kills the process group".
- *The zygote's environment*: `OPENBLAS_NUM_THREADS=1`, `PYTHONHASHSEED=0`,
  nothing else from the caller. It corrects ADR-0001's premise, not its
  decision; a test holds one thread. Fixing the hash seed keeps a program's
  own `set` of strings from moving its body between zygotes.

**Nothing from a program worker is trusted.** §The sandbox says "the parent
reads the body back", which would put hostile bytes through the kernel in the
caller. Instead a **body worker** (zygote job kind two, same limits) runs
`read_body`, `check(body, "full")` and the measures; `score` reuses it in M4.
Mapping: `BodyRejectedError` → `checker_fail` with the report's violations;
any other error reading the bytes → `runtime` (no result), kept verbatim; the
worker's own `checker_fail` claim is accepted, since it only costs the
program. A program can still forge a failure status (raising `ArrisError`
itself does the same): −0.5 for −1.0, recorded in the ADR. A frame over
`MAX_RESULT_BYTES` or unparseable is `crash`, whole, never truncated.

**Transport.** The caller creates each job's result pipe and passes its write
end to the zygote by `SCM_RIGHTS`; the zygote only forks and reaps and never
reads a result. Workers close every other descriptor. Program text is sent
UTF-8 with `surrogatepass`; a text `compile` cannot encode is `syntax`.
*Settled* (step 2): the payload travels as a memfd, the third descriptor of
the job message, read by the worker under its own memory limit: a
`SOCK_SEQPACKET` message is capped near the socket buffer, and a zygote that
read the text would hold every program's bytes in the process all forks
start from. The warden closes every descriptor it was not given, so none
holds the job socket past the zygote's death. Step 2's program job wrote
`write_body`'s bytes raw; step 4 replaced them with the classified frame
(`sandbox/_frame.py`, JSON, body in base64). *Settled* (step 4): until step 5's
body worker exists the program worker itself checks and measures, so `ok` and
`checker_fail` come from its frame; `Measures` is set exactly on `ok` (a body
that failed the checker may not be measurable). Step 5 moves both out.
`SandboxUnavailable` is defined in `sandbox/_zygote.py`; step 3 exports it. One
deadline covers program and body worker; the caller holds a backstop past it
(measured by step 2) that replaces a dead zygote and reports `crash`.

**Public API** (`arris_gym`, a design delta for the changelog):
```python
Status, Dialect, ArrisRefusal, BodyRef, Measures, Versions, ExecResult
run(program, *, dialect="arris", timeout=5.0, memory=512 * 2**20) -> ExecResult
run_many(programs, *, dialect=..., timeout=..., memory=..., workers=None)
    -> tuple[ExecResult, ...]            # submission order
Sandbox(cache_dir=None)                  # .run, .run_many, .executions, .close
digest(results) -> str;  dump_text(result) -> str;  dump_png(result, path)
SandboxUnavailable                       # the caller's: no namespaces, no Landlock
```
- `BodyRef` is defined here: `data: bytes` (the worker's `write_body`) and
  `sha256`. **`Measures`** is new on `ExecResult`, set when `status` is `ok`: volume,
  area, centroid, bounds, face, shell and face-kind counts, genus. Fixtures
  and the digest need them, and dumps then need no worker.
- `Dialect` has only `ARRIS` until M3: `"cq"` is an unknown dialect now.
- `arris_gym.cq.UnsupportedApi` lands alone, so `unsupported_api` has a
  fixture before `cq` exists; `sandbox` may import `cq`.
- `ArrisRefusal.entities` come from the exception's `entity`/`entities`
  fields, never from parsing the message.
- **Cache key** gains `memory` and the `nproc` limit, since a program can catch
  `MemoryError` and go on; arris-gym's version stands for `cq`'s until they
  split. On disk, one JSON and one body file by key, written by rename.
  Nothing a worker can reach. Never cached: `timeout`, `crash`, `MemoryError`.

Constants: `NPROC_LIMIT` = 4 (step 1: warden, worker, two tasks);
`MAX_RESULT_BYTES` = 64 MiB (step 2: a plate with 100 holes is 96 KiB of body)
and `BACKSTOP` = 2 s (step 2: 64 concurrent workers at a 1 s deadline, 300 MiB
each, all reported within 0.29 s); the fixtures' default tolerance by step 4.
`timeout=5.0` is SEED.md §5's and `memory` the roadmap's, revisited with M3's numbers.

## Steps
Complexity grades; a step's grade is its tier, the model that executes it
(`.agents/tiers.md`): **[1]** routine; **[2]** careful, a numeric, geometric
or semantic case to get right within a given design; **[3]** unproven, an
isolation guarantee whose correctness has to be established here.

- [x] Step 1 **[3]** — ADR-0002 and `sandbox/_isolate.py`: warden, namespaces, Landlock, rlimits, no core, descriptors closed, stdio detached. Tests run a function under it: no connect, no read or write outside, fork bomb bounded, a `setsid` descendant holding a pipe dies with PID 1, a worker ignoring signals and clearing `PDEATHSIG` still dies at its deadline, 1 GiB refused under 512 MiB.
- [x] Step 2 **[3]** — `sandbox/_zygote.py`: clean start, job socket, fd passing, reaping, replacement. Tests: one thread, two programs give equal bytes, `set`-order program equal across zygotes, a worker cannot reach the job socket, a zygote killed mid-run costs its in-flight jobs and the next `run` works; `SandboxUnavailable` when a probe fails.
- [x] Step 3 **[1]** — the types of *Public API* and `cq.UnsupportedApi`, frozen, with docstrings and a runnable example; a `Status` dispatch with `assert_never` in the tests. §Outcomes updated.
- [x] Step 4 **[2]** — the program path: the `arris` dialect's `compile`, `exec`, `result` and classification, in the worker, by type only; `run`. Fixtures in `tests/fixtures/sandbox/` by construction for `ok` (closed-form box, measures), `syntax`, `runtime` (incl. `SystemExit`, no `result`, `result` not a `Solid`), `unsupported_api`, `arris_refusal` (kind, verbatim message, entities). Loader and default tolerance.
- [ ] Step 5 **[3]** — untrusted delivery: frame parsing and caps, the body worker, `checker_fail`, `crash`. Fixtures: a `Solid` whose `model` is a forger returning doctored bytes (`BodyRejectedError`; if `Solid` refuses that, a forged frame), `os._exit(0)`, `os.abort`, a segfault, a pipe flood, garbage on the pipe, a result pipe closed by the program. A crash's message names the signal or exit code and carries stderr's bounded tail, where the kernel's abort text lands.
- [ ] Step 6 **[2]** — `run_many` and `Sandbox`: bounded live forks, submission order whatever finishes first, thread-safe `run`, the lazy default instance. `hypothesis`: `run` raises on no text, surrogates and NULs included; caller's mistakes raise.
- [ ] Step 7 **[2]** — the cache: key, disk layout, what is never cached, `.executions`. Tests: a second run makes 0 executions, rows equal; changed `memory` misses; each uncacheable outcome re-runs; a torn entry is a miss.
- [ ] Step 8 **[2]** — `digest` and `dump_text`: rows in program order, floats as hex, `seconds` excluded. Tests: equal across `workers` and zygotes, a one-bit change of a measure moves it, a refusal's text diffs in a committed golden built by hand.
- [ ] Step 9 **[2]** — `dump_png`: body worker returns the tessellation; `numpy` z-buffer, fixed views, `zlib` PNG, no new dependency. Test: PNG decodes, size fixed, silhouette area of a box from a fixed view matches its closed form within a pixel row. Look at one (`inspect`); update that skill's "until they exist".
- [ ] Step 10 **[2]** — acceptance: `tests/test_m0_acceptance.py`; `ci.yml` lifts the runners' user-namespace restriction; gate time measured, kept under a minute.

## Acceptance
`uv run pytest tests/test_m0_acceptance.py`, in the gate, offline:
- `tests/fixtures/sandbox/`: one program per status, each returning it, with
  expected measures on `ok`; plus a fork bomb, a 1 GiB allocation under
  512 MiB (`runtime`, `MemoryError`), a connect to `1.1.1.1` (`runtime`,
  `ENETUNREACH`), a read of a file made outside the reach (`runtime`,
  `PermissionError`).
- An infinite loop at `timeout=1.0`: `timeout`, back within 2 s.
- 1000 programs, 10% hostile: 1000 rows, submission order, each its
  expected status. Second run: `.executions` unchanged, rows and digest equal.
- `hypothesis`: `run` raises on no drawn text.

## Docs to update on completion
- `docs/ARCHITECTURE.md` §Outcomes — `BodyRef`, `Measures`; the read-back
  table's rows. §The sandbox — the chain with warden and body worker, the
  deadline, Landlock, the two closed `⚠ OPEN:`s, transport, cache key.
  §Determinism — the zygote's environment. Opening paragraph.
- `docs/ROADMAP.md` — M0's status line. `docs/adr/README.md` — ADR-0002's row.
- `GLOSSARY.md` — **Warden**, **Body worker**; **Crash** and **Sandbox**
  sharpened to name them.
- `CHANGELOG.md` §Unreleased — `run`, `run_many`, statuses, Linux needs.
- `.agents/skills/inspect/SKILL.md` — the dumps exist (step 9).
- `AGENTS.md` current state — M0 landed, next `/plan M1`.

## Open questions
- ⚠ OPEN: `ci.yml`'s change cannot be proven: no remote exists, and creating
  one is the human's. Step 10 writes it; the first push shows it. Ubuntu
  24.04 runners are expected to restrict user namespaces (not measured here).
- ⚠ OPEN: Docker's default seccomp profile is expected to refuse
  `unshare(CLONE_NEWUSER)`, so the sandbox would refuse to start in a default
  container. It belongs with the platform `⚠ OPEN:`, which step 1's ADR
  records and leaves open. Agent, when a consumer needs it.
- ⚠ OPEN: `checker_fail` is reached only by a forged body: no program is known
  to make an invalid body through arris. Enough for "one program per status";
  a real one becomes a fixture and an arris report. Agent, step 5.

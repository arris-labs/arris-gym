#!/usr/bin/env python3
"""Run programs on the oracle: CadQuery on Open CASCADE in an oracle worker.

An oracle worker is a program worker under the sandbox's warden that execs
the oracle environment's interpreter on `tools/oracle/worker.py` (ADR-0004):
the same namespaces, rlimits, Landlock domain and seccomp filter as an arris
program, with the oracle environment's prefixes as its whole reach. A corpus
runs on **oracle zygotes** (ADR-0013): one such worker that imported CadQuery
once and forks a child per program, each child under its warding. Runs in
the main environment; needs `uv sync --project tools/oracle` first.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import pathlib
import queue
import socket
import struct
import sys
import threading
import time
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

from arris_gym.census import CorpusProgram
from arris_gym.fidelity import OracleReport, parse_outcome
from arris_gym.sandbox import _exec
from arris_gym.sandbox._program import write_all
from arris_gym.sandbox._zygote import BACKSTOP, ENVIRONMENT, JobKind, Outcome, Zygote, _collect

ORACLE = pathlib.Path(__file__).resolve().parent / "oracle"
# The environment's interpreter as it is called: the path tells it its venv.
PYTHON = ORACLE / ".venv" / "bin" / "python"
WORKER = ORACLE / "worker.py"

# The oracle worker's RLIMIT_AS. Measured (ADR-0004): importing cadquery and
# OCP maps 875 MiB of address space, and a filleted box with a hole and five
# booleans on spheres and cylinders left it there; its resident set was
# 507 MiB. 1.5 GiB is that import plus about what an arris worker's 512 MiB
# leaves a program beyond its own import, and refuses a 1 GiB allocation.
MEMORY = 1536 * 2**20

# The zygote's environment, and a `HOME` that does not exist: ezdxf, which
# cadquery imports, asks the password database for one without it, and the
# worker cannot read that. Nothing is written there; the read-only mounts
# refuse it.
ORACLE_ENVIRONMENT = {**ENVIRONMENT, "HOME": "/nonexistent"}


def spec() -> _exec.ExecSpec:
    """The exec spec of an oracle worker on this checkout's oracle environment."""
    return _exec.interpreter_spec(str(PYTHON), str(WORKER), ORACLE_ENVIRONMENT)


def run_one(zygote: Zygote, oracle: _exec.ExecSpec, program: str, *, timeout: float) -> Outcome:
    """Run `program` in one oracle worker for at most `timeout` seconds.

    What came back, unread: the warden's `Ending`, the frame bytes on the
    result pipe (trusted no more than any worker's) and the stderr tail.
    """
    text = program.encode("utf-8", "surrogatepass")
    return zygote.execute(
        JobKind.EXEC,
        _exec.payload(oracle, text),
        deadline=time.monotonic() + timeout,
        memory=MEMORY,
    )


# The oracle zygote (ADR-0013), as `worker.py` speaks it: the flag that
# makes the worker a zygote, its first message, and a job's header (its
# deadline; the four descriptors follow it).
ZYGOTE_FLAG = "--zygote"
_READY = b"ready"
_ZYGOTE_JOB = struct.Struct("<d")
# How long an oracle zygote may take to import cadquery and OCP and say it
# is ready: the import takes about 1.5 s (ADR-0004); the margin covers a
# loaded machine.
ZYGOTE_STARTUP_TIMEOUT = 60.0
# An oracle zygote's own deadline, its warden's: it is replaced before a
# program whose deadline and backstop would pass it, so a zygote that stopped
# answering lingers this long at most. A restart costs one import, 1.5 s.
ZYGOTE_LIFETIME = 600.0


class ZygoteUnavailable(RuntimeError):
    """An oracle zygote did not say it was ready: its import failed or hung.

    Raised before any program is sent to it; the message is what the zygote
    said, or that it said nothing, and the tail of its stderr if it ended.
    """


class OracleZygote:
    """One oracle zygote (ADR-0013): an oracle worker, isolated and exec'd as
    `run_one`'s, that imported CadQuery once and forks a child per program.

    `run` sends one program and returns its `Outcome`, as `run_one` would
    for the same program: the child's ending in the warden's record, its
    frame and its stderr tail. One program at a time: a handle is not shared
    between threads. A zygote that dies or stops answering costs that program
    its record (`ending` None), and the next program starts a new one. Started
    lazily, by the first `run`.
    """

    def __init__(self, zygote: Zygote, oracle: _exec.ExecSpec) -> None:
        self._zygote = zygote
        self._spec = replace(oracle, argv=(*oracle.argv, ZYGOTE_FLAG))
        self._sock: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._lifetime = 0.0
        self._starts = 0

    @property
    def starts(self) -> int:
        """How many zygotes this handle has started: one more each replacement."""
        return self._starts

    def _start(self) -> None:
        ours, theirs = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        lifetime = time.monotonic() + ZYGOTE_LIFETIME
        outcome: list[Outcome] = []
        channel = theirs.detach()  # `execute` owns and closes it

        def serve() -> None:
            outcome.append(
                self._zygote.execute(
                    JobKind.EXEC,
                    _exec.payload(self._spec, b""),
                    deadline=lifetime,
                    memory=MEMORY,
                    channel=channel,
                )
            )

        thread = threading.Thread(target=serve, name="oracle-zygote", daemon=True)
        thread.start()
        ours.settimeout(ZYGOTE_STARTUP_TIMEOUT)
        try:
            ready = ours.recv(len(_READY) + 1)
        except (TimeoutError, OSError):
            ready = b""
        if ready != _READY:
            ours.close()
            thread.join(timeout=BACKSTOP)
            tail = outcome[0].stderr.decode("utf-8", "replace") if outcome else ""
            raise ZygoteUnavailable(
                f"the oracle zygote said {ready!r}, not {_READY!r}; its stderr ends:\n{tail}"
            )
        ours.settimeout(None)
        self._sock, self._thread, self._lifetime = ours, thread, lifetime
        self._starts += 1

    def _stop(self) -> None:
        """Close the channel: a zygote still answering sees its end and exits."""
        if self._sock is not None:
            self._sock.close()
            self._sock = None
        if self._thread is not None:
            self._thread.join(timeout=BACKSTOP)
            self._thread = None

    def _send(self, deadline: float, fds: list[int]) -> bool:
        assert self._sock is not None
        try:
            socket.send_fds(self._sock, [_ZYGOTE_JOB.pack(deadline)], fds)
        except OSError:  # the zygote is gone: its channel's other end closed
            return False
        return True

    def run(self, program: str, *, timeout: float) -> Outcome:
        """Run `program` in a child of this zygote for at most `timeout` seconds.

        What came back, unread, as `run_one` returns it. Raises
        `ZygoteUnavailable` only when a new zygote has to start and cannot.
        """
        text = program.encode("utf-8", "surrogatepass")
        for attempt in range(2):
            if self._sock is None or time.monotonic() + timeout + BACKSTOP > self._lifetime:
                self._stop()
                self._start()
            status_r, status_w = os.pipe()
            result_r, result_w = os.pipe()
            stderr_r, stderr_w = os.pipe()
            payload_fd = os.memfd_create("arris-gym-oracle", os.MFD_CLOEXEC)
            sent = [status_w, result_w, stderr_w, payload_fd]
            try:
                write_all(payload_fd, text)
                os.lseek(payload_fd, 0, os.SEEK_SET)
                deadline = time.monotonic() + timeout
                delivered = self._send(deadline, sent)
            except BaseException:
                for fd in (status_r, result_r, stderr_r):
                    os.close(fd)
                raise
            finally:
                for fd in sent:
                    os.close(fd)
            if not delivered:
                for fd in (status_r, result_r, stderr_r):
                    os.close(fd)
                self._stop()
                if attempt:
                    break
                continue
            try:
                outcome = _collect(status_r, result_r, stderr_r, deadline + BACKSTOP)
            finally:
                os.close(status_r)
                os.close(stderr_r)
            if outcome is None or outcome.ending is None:
                self._stop()  # the next program goes to a new zygote
            return outcome if outcome is not None else Outcome(None, b"", overflow=False)
        return Outcome(None, b"", overflow=False)

    def close(self) -> None:
        """Stop this zygote. A child already forked keeps its deadline."""
        self._stop()

    def __enter__(self) -> OracleZygote:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


# The oracle worker's deadline when none is given. It was set when a
# program's deadline covered the import, about 1.5 s (ADR-0004); an oracle
# zygote's child starts after it, and the deadline stays, so that no report
# moves (ADR-0013).
DEFAULT_TIMEOUT = 30.0
# Oracle workers run at once. Each is 1.5 GiB of address space at most and
# one thread; the report does not depend on the number.
DEFAULT_WORKERS = 4


def run_report(oracle: OracleZygote, program: str, *, timeout: float) -> OracleReport:
    """The `OracleReport` of `program`: one child of an oracle zygote, its
    frame parsed.

    Never raises on a program; a frame that cannot be believed is a `crash`.
    """
    start = time.monotonic()
    outcome = oracle.run(program, timeout=timeout)
    return parse_outcome(outcome, program, timeout=timeout, seconds=time.monotonic() - start)


def run_many(
    programs: Sequence[str], *, timeout: float = DEFAULT_TIMEOUT, workers: int = DEFAULT_WORKERS
) -> list[OracleReport]:
    """The reports of `programs`, in submission order whatever order they finish.

    `workers` oracle zygotes, each serving one program at a time.
    """
    oracle = spec()
    with Zygote() as zygote:
        idle: queue.SimpleQueue[OracleZygote] = queue.SimpleQueue()
        handles = [OracleZygote(zygote, oracle) for _ in range(workers)]
        for handle in handles:
            idle.put(handle)

        def one(program: str) -> OracleReport:
            handle = idle.get()
            try:
                return run_report(handle, program, timeout=timeout)
            finally:
                idle.put(handle)

        try:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                return list(pool.map(one, programs))
        finally:
            for handle in handles:
                handle.close()


def read_slice(path: pathlib.Path) -> list[str]:
    """The stems of a slice file: one per line, `#` lines are its header."""
    lines = path.read_text(encoding="utf-8").splitlines()
    return [line for line in lines if line and not line.startswith("#")]


def slice_reports(
    stems: Sequence[str], *, timeout: float = DEFAULT_TIMEOUT, workers: int = DEFAULT_WORKERS
) -> tuple[list[CorpusProgram], list[OracleReport]]:
    """The BenchCAD programs of `stems` sorted by stem, and their oracle reports.

    Reads the pinned corpus through `census.benchcad` (the `[corpus]` extra
    and the network, outside the gate). Raises `ValueError` for a stem the
    corpus lacks or lists twice.
    """
    from arris_gym.census import benchcad

    by_stem = {p.stem: p for p in benchcad.read()}
    ordered = sorted(stems)
    if len(set(ordered)) != len(ordered):
        raise ValueError("a stem is listed twice")
    missing = [stem for stem in ordered if stem not in by_stem]
    if missing:
        raise ValueError(f"stems not in the pinned corpus: {missing[:5]}")
    programs = [by_stem[stem] for stem in ordered]
    reports = run_many([p.text for p in programs], timeout=timeout, workers=workers)
    return programs, reports


def slice_rows(
    programs: Sequence[CorpusProgram], reports: Sequence[OracleReport]
) -> list[dict[str, object]]:
    """The oracle rows of BenchCAD programs, in the order given.

    Each row is the stem, family, licence and revision beside the report
    without its STEP text and wall-clock `seconds`, so the rows are the same
    bytes on every run.
    """
    from arris_gym.census import benchcad

    return [
        {
            "stem": p.stem,
            "family": p.family,
            "licence": benchcad.LICENCE,
            "revision": benchcad.REVISION,
            "report": json.loads(r.model_dump_json(exclude={"step", "seconds"})),
        }
        for p, r in zip(programs, reports, strict=True)
    ]


def targets_bytes(programs: Sequence[CorpusProgram], reports: Sequence[OracleReport]) -> bytes:
    """The targets file: gzip (`mtime=0`) of one JSON line per program, `stem`,
    `step_sha256` and the `step` text, in the order given.

    A report with no STEP (the oracle did not end `ok`) has no target: a
    `ValueError` names its stem, never a row left out.
    """
    lines = []
    for p, r in zip(programs, reports, strict=True):
        if r.step is None or r.step_sha256 is None:
            raise ValueError(f"{p.stem}: the oracle gave no STEP ({r.status.value})")
        row = {"stem": p.stem, "step_sha256": r.step_sha256, "step": r.step}
        lines.append(json.dumps(row, sort_keys=True) + "\n")
    return gzip.compress("".join(lines).encode("utf-8"), mtime=0)


def rows_text(rows: Sequence[dict[str, object]]) -> str:
    """The rows as `oracle.jsonl` text: one canonical JSON object per line."""
    return "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)


def rows_digest(text: str) -> str:
    """The digest of an `oracle.jsonl`: the SHA-256 of its text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main(argv: Sequence[str] | None = None) -> int:
    """Run the given program files and write `oracle.jsonl`: one row per program
    in the order given, `{"path": ..., "report": ...}`, `seconds` included and
    the STEP text left out.
    With `--slice FILE`, run the BenchCAD programs of those stems instead
    (`slice_rows`), sorted by stem, and print the status counts and digest."""
    parser = argparse.ArgumentParser(description="Run programs on the oracle.")
    parser.add_argument("programs", nargs="*", type=pathlib.Path)
    parser.add_argument("--slice", type=pathlib.Path, help="a slice file of BenchCAD stems")
    parser.add_argument("--start", type=int, default=0, help="with --slice: first stem to run")
    parser.add_argument("--stop", type=int, help="with --slice: stop before this stem")
    parser.add_argument("--out", type=pathlib.Path, default=pathlib.Path("oracle.jsonl"))
    parser.add_argument(
        "--targets",
        type=pathlib.Path,
        help="with --slice: also write the targets file (stem, step_sha256, STEP text), gzipped",
    )
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    args = parser.parse_args(argv)
    if (args.slice is None) == (not args.programs):
        parser.error("give program files, or --slice FILE, not both and not neither")
    if args.slice is not None:
        stems = sorted(read_slice(args.slice))[args.start : args.stop]
        programs, reports = slice_reports(stems, timeout=args.timeout, workers=args.workers)
        rows = slice_rows(programs, reports)
        text = rows_text(rows)
        args.out.write_text(text, encoding="utf-8")
        if args.targets is not None:
            args.targets.write_bytes(targets_bytes(programs, reports))
        counts: dict[str, int] = {}
        for row in rows:
            status = str(row["report"]["status"])  # type: ignore[index]
            counts[status] = counts.get(status, 0) + 1
        print(f"{len(rows)} programs: {dict(sorted(counts.items()))}", file=sys.stderr)
        print(f"digest {rows_digest(text)}", file=sys.stderr)
        return 0
    texts = [p.read_text(encoding="utf-8", errors="surrogateescape") for p in args.programs]
    reports = run_many(texts, timeout=args.timeout, workers=args.workers)
    with args.out.open("w", encoding="utf-8") as out:
        for path, report in zip(args.programs, reports, strict=True):
            row = {
                "path": str(path),
                "report": json.loads(report.model_dump_json(exclude={"step"})),
            }
            out.write(json.dumps(row, sort_keys=True) + "\n")
    counts = {}
    for report in reports:
        counts[report.status.value] = counts.get(report.status.value, 0) + 1
    print(f"{len(reports)} programs: {dict(sorted(counts.items()))}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

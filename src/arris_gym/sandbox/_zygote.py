"""The zygote: a clean interpreter that forks one warden per job (ADR-0001, ADR-0002).

The caller starts the zygote with `subprocess` in an environment of
`OPENBLAS_NUM_THREADS=1` and `PYTHONHASHSEED=0` and nothing else of its own.
The zygote imports `arris`, `arris.build`, `numpy` and `arris_gym.cq`, builds
nothing, probes that it can isolate a worker, and then serves jobs on a
`SOCK_SEQPACKET` socket: one message a job, carrying its kind, deadline and
memory limit, with four descriptors passed by `SCM_RIGHTS` (the write ends
of the status, result and stderr pipes, and the job's payload). For
each it forks a warden (`sandbox/_isolate.py`), closes its own copies and
reaps the warden when it ends. It never reads a result, a status or a
worker's stderr: those pipes run from the warden and the worker straight to
the caller.

`Zygote` is the caller's handle. It replaces a zygote that died, and holds a
backstop past each job's deadline after which the job has no `Ending`.
Private: the sandbox's public API is built on it.
"""

from __future__ import annotations

import enum
import os
import select
import socket
import struct
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

import arris
import arris.build
import numpy

import arris_gym.cq
from arris_gym.sandbox import _body, _isolate, _program

# Imported for the forks, not used here: every worker starts with them loaded.
_PRELOADED = (arris, arris.build, numpy, arris_gym.cq)

# --- Constants ----------------------------------------------------------------

# The zygote's whole environment (ADR-0002): numpy's OpenBLAS on one thread,
# so the zygote has one thread to fork and `RLIMIT_AS` is not spent at fork;
# a fixed hash seed, so a program's own `set` of strings iterates in the same
# order in every zygote and its body does not move between them.
ENVIRONMENT = {"OPENBLAS_NUM_THREADS": "1", "PYTHONHASHSEED": "0"}

# How long the caller waits past a job's deadline for its status record
# before it gives the job up and replaces the zygote. Measured on a 32-core
# machine, 64 concurrent workers each spinning to a 1 s deadline with 300 MiB
# touched: the last record came 0.29 s after its deadline (median 0.24 s),
# the kill and the release of the memory. About seven times that; it bounds
# only a zygote or warden that has stopped answering, never a program, which
# its warden ends at the deadline.
BACKSTOP = 2.0

# The most a job may write to its result pipe. A plate with 100 cylindrical
# holes is 96 KiB of `write_body` bytes; 64 MiB is several hundred times
# that, and bounds the caller's memory per live job. A job past
# it has its pipe closed, which ends its writing, and keeps none of what it
# wrote: a result is whole or absent.
MAX_RESULT_BYTES = 64 * 2**20

# How much of the end of a worker's stderr the caller keeps, for a crash's
# message: a kernel abort writes its reason there, a few hundred bytes, last.
# Whatever came before is dropped as it arrives, so a program flooding its
# stderr costs the caller this much memory and no more.
STDERR_TAIL_BYTES = 4096

# How long the zygote may take to import everything and probe isolation.
# It takes under a tenth of a second; the margin covers a loaded machine.
STARTUP_TIMEOUT = 60.0

# The probe's worker runs nothing; it needs only room for the interpreter it
# was forked from, which is this limit's default for programs as well.
PROBE_MEMORY = 512 * 2**20
PROBE_TIMEOUT = 10.0

# The module the zygote process runs: not this one, which the package imports,
# so that `-m` does not execute a module already in `sys.modules`.
_ENTRY = "arris_gym.sandbox._zygote_main"
_READY = b"ready"
_READ_CHUNK = 1 << 16


class JobKind(enum.IntEnum):
    """What a job's worker does with its payload."""

    PROGRAM = 1  # run the payload as a program (`sandbox/_program.py`)
    BODY = 2  # read the payload back as body bytes (`sandbox/_body.py`)


# The job message: kind, deadline (a `time.monotonic()` instant: the clock is
# the machine's, shared by caller and zygote), memory limit in bytes. Its
# four descriptors are status, result, stderr and payload, in that order.
_JOB = struct.Struct("<IdQ")
_JOB_FDS = 4

_HANDLERS: dict[int, Callable[[int, int], None]] = {
    JobKind.PROGRAM: _program.execute,
    JobKind.BODY: _body.execute,
}


class SandboxUnavailable(RuntimeError):
    """This machine cannot isolate a program, so the sandbox refuses to run one.

    Raised when the zygote starts: its probe could not enter the namespaces,
    make the mounts read-only, enter a Landlock domain or install the
    seccomp filter (ADR-0002), or the zygote itself could not start. The
    message says which. It is the caller's to handle; no program ran.
    """


# --- The zygote ---------------------------------------------------------------


def _probe(roots: tuple[str, ...]) -> str | None:
    """Why this machine cannot isolate a worker, or None if it can."""
    limits = _isolate.Limits(memory=PROBE_MEMORY, readable=roots)
    try:
        ending = _isolate.run(lambda: None, timeout=PROBE_TIMEOUT, limits=limits)
    except ValueError as e:  # an unsupported machine
        return str(e)
    if ending.kind is _isolate.EndKind.UNAVAILABLE:
        return f"the warden could not enter its namespaces: {os.strerror(ending.value)}"
    if not ending.armed:
        return "the worker could not complete its isolation (rlimits, Landlock or seccomp)"
    if (ending.kind, ending.value) != (_isolate.EndKind.EXITED, 0):
        return f"the probe's worker ended {ending.kind.name} {ending.value}"
    return None


def _close(fds: list[int]) -> None:
    for fd in fds:
        os.close(fd)


def _start_job(
    message: bytes, fds: list[int], flags: int, roots: tuple[str, ...]
) -> tuple[int, int] | None:
    """Fork the warden for one job message; its pid and pidfd, or None.

    A malformed message or an unknown kind is a bug of the caller's handle:
    the job's descriptors are closed, and the caller sees no record.
    """
    try:
        if len(message) != _JOB.size or len(fds) != _JOB_FDS or flags & socket.MSG_CTRUNC:
            return None
        kind, deadline, memory = _JOB.unpack(message)
        handler = _HANDLERS.get(kind)
        if handler is None:
            return None
        status_w, result_w, stderr_w, payload = fds
        limits = _isolate.Limits(memory=memory, readable=roots)
        try:
            pid = _isolate.spawn(
                lambda: handler(payload, result_w),
                deadline=deadline,
                limits=limits,
                status_fd=status_w,
                keep_fds=(result_w, payload),
                stderr_fd=stderr_w,
            )
        except OSError:  # fork refused: the job ends with no record
            return None
        return pid, os.pidfd_open(pid)
    finally:
        _close(fds)


def serve(sock: socket.socket) -> None:
    """Fork a warden for each job on `sock` and reap it; return at its end."""
    roots = _isolate.readable_roots()
    poller = select.poll()
    poller.register(sock, select.POLLIN)
    wardens: dict[int, int] = {}  # pidfd -> pid
    while True:
        for fd, _ in poller.poll():
            if fd != sock.fileno():
                os.waitpid(wardens.pop(fd), 0)
                poller.unregister(fd)
                os.close(fd)
                continue
            message, fds, flags, _ = socket.recv_fds(sock, _JOB.size, _JOB_FDS)
            if not message and not fds:
                return  # the caller is gone; the wardens keep their deadlines
            started = _start_job(message, fds, flags, roots)
            if started is not None:
                pid, pidfd = started
                wardens[pidfd] = pid
                poller.register(pidfd, select.POLLIN)


def main(argv: list[str]) -> int:
    """The zygote's entry: probe, say so on the socket, then serve."""
    sock = socket.socket(fileno=int(argv[1]))
    reason = _probe(_isolate.readable_roots())
    sock.send(_READY if reason is None else reason.encode())
    if reason is not None:
        return 1
    serve(sock)
    return 0


# --- The caller's handle ------------------------------------------------------


@dataclass(frozen=True)
class Outcome:
    """What the caller received for one job.

    `ending` is the warden's record, or None when none came whole by the
    backstop (the zygote died before forking the warden, or stopped
    answering). `data` is everything the job wrote to its result pipe, whole;
    it is empty when `overflow` is true, the job having written more than
    `MAX_RESULT_BYTES`. `stderr` is the last `STDERR_TAIL_BYTES` at most of
    what the worker wrote to its stderr.
    """

    ending: _isolate.Ending | None
    data: bytes
    overflow: bool
    stderr: bytes = b""


class Zygote:
    """The caller's handle on one zygote, replaced whenever it dies.

    Starting it raises `SandboxUnavailable` when the machine cannot isolate a
    program. `execute` is safe to call from several threads at once; each
    call is one job, its own pipes, its own warden.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._generation = 0
        self._process: subprocess.Popen[bytes] | None = None
        self._sock: socket.socket | None = None
        self._start()

    @property
    def pid(self) -> int:
        """The current zygote's process id."""
        assert self._process is not None, "the zygote is closed"
        return self._process.pid

    def _start(self) -> None:
        ours, theirs = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        with theirs:
            process = subprocess.Popen(
                [sys.executable, "-s", "-P", "-m", _ENTRY, str(theirs.fileno())],
                env=ENVIRONMENT,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                pass_fds=(theirs.fileno(),),
                start_new_session=True,
            )
        ours.settimeout(STARTUP_TIMEOUT)
        try:
            ready = ours.recv(4096)
        except TimeoutError:
            ready = b""
        if ready != _READY:
            ours.close()
            process.kill()
            code = process.wait()
            reason = ready.decode(errors="replace") or f"the zygote exited with code {code}"
            raise SandboxUnavailable(reason)
        ours.settimeout(None)
        self._process, self._sock = process, ours
        self._generation += 1

    def _stop(self) -> None:
        if self._sock is not None:
            self._sock.close()
            self._sock = None
        if self._process is not None:
            self._process.kill()
            self._process.wait()
            self._process = None

    def _send(self, header: bytes, fds: list[int]) -> int:
        """Send one job, replacing a dead zygote first; its generation."""
        with self._lock:
            for attempt in range(2):
                if self._process is None or self._process.poll() is not None:
                    self._stop()
                    self._start()
                assert self._sock is not None
                try:
                    socket.send_fds(self._sock, [header], fds)
                except (BrokenPipeError, ConnectionResetError):
                    if attempt:
                        raise
                    self._stop()
                    continue
                return self._generation
        raise AssertionError("unreachable")

    def _give_up(self, generation: int) -> None:
        """Replace the zygote that took a job whose record never came."""
        with self._lock:
            if generation == self._generation:
                self._stop()

    def execute(self, kind: JobKind, payload: bytes, *, deadline: float, memory: int) -> Outcome:
        """Run one job isolated until `deadline` at most; what came back.

        `deadline` is a `time.monotonic()` instant, so that one deadline can
        cover several jobs. Blocks until the worker has ended and its pipes
        are closed, or the backstop has passed. A zygote that died is replaced before the job
        is sent; one that died with the job in hand costs the job its
        record (`ending` None), and the next job goes to a new zygote.
        """
        status_r, status_w = os.pipe()
        result_r, result_w = os.pipe()
        stderr_r, stderr_w = os.pipe()
        payload_fd = os.memfd_create("arris-gym-job", os.MFD_CLOEXEC)
        try:
            _program.write_all(payload_fd, payload)
            os.lseek(payload_fd, 0, os.SEEK_SET)
            header = _JOB.pack(kind, deadline, memory)
            generation = self._send(header, [status_w, result_w, stderr_w, payload_fd])
        except BaseException:
            _close([status_r, result_r, stderr_r])
            raise
        finally:
            _close([status_w, result_w, stderr_w, payload_fd])
        try:
            outcome = _collect(status_r, result_r, stderr_r, deadline + BACKSTOP)
        finally:
            _close([status_r, stderr_r])
        if outcome is None:
            self._give_up(generation)
            return Outcome(None, b"", overflow=False)
        return outcome

    def close(self) -> None:
        """Stop the zygote. Wardens already forked keep their deadlines."""
        with self._lock:
            self._stop()

    def __enter__(self) -> Zygote:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def _collect(status_r: int, result_r: int, stderr_r: int, backstop: float) -> Outcome | None:
    """Read the three pipes to their ends; None if the backstop passed first.

    Keeps the tail of stderr only. Closes `result_r` itself, early when the
    job overflows.
    """
    status = bytearray()
    data = bytearray()
    stderr = bytearray()
    overflow = False
    poller = select.poll()
    live = {status_r, result_r, stderr_r}
    for fd in live:
        poller.register(fd, select.POLLIN)
    try:
        while live:
            remaining_ms = int((backstop - time.monotonic()) * 1000) + 1
            if remaining_ms <= 0:
                return None
            for fd, _ in poller.poll(remaining_ms):
                chunk = os.read(fd, _READ_CHUNK)
                if fd == status_r:
                    status += chunk
                elif fd == stderr_r:
                    stderr += chunk
                    del stderr[:-STDERR_TAIL_BYTES]
                elif len(data) + len(chunk) > MAX_RESULT_BYTES:
                    overflow, chunk = True, b""
                    data.clear()
                else:
                    data += chunk
                if not chunk:
                    poller.unregister(fd)
                    live.discard(fd)
                    if fd == result_r:
                        os.close(result_r)  # an overflowing writer meets a closed pipe
    finally:
        if result_r in live:
            os.close(result_r)
    # No record whole: the warden was never forked, or died with the zygote.
    return Outcome(_isolate.parse_ending(bytes(status)), bytes(data), overflow, bytes(stderr))

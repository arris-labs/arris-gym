"""`run`: one program, alone in a sandbox, one `ExecResult` back.

The caller's side of the program path: send the text to a program worker
through the zygote, read how it ended, and turn the warden's record and the
worker's frame into a result. Private; `arris_gym.run` is the public name.
"""

from __future__ import annotations

import functools
import hashlib
import importlib.metadata
import math
import signal
import threading
import time

import pydantic

from arris_gym.sandbox import _isolate
from arris_gym.sandbox._frame import Frame
from arris_gym.sandbox._program import TEXT_ERRORS
from arris_gym.sandbox._zygote import MAX_RESULT_BYTES, JobKind, Outcome, Zygote
from arris_gym.sandbox.outcome import BodyRef, Dialect, ExecResult, Status, Versions

# SEED.md §5's wall-clock limit and the roadmap's memory limit, revisited
# with M3's numbers.
DEFAULT_TIMEOUT = 5.0
DEFAULT_MEMORY = 512 * 2**20

_default: Zygote | None = None
_default_lock = threading.Lock()


@functools.cache
def current_versions() -> Versions:
    """The pinned versions this process runs under."""
    return Versions(
        arris=importlib.metadata.version("arris"),
        numpy=importlib.metadata.version("numpy"),
        arris_gym=importlib.metadata.version("arris-gym"),
    )


def default_zygote() -> Zygote:
    """The process's shared zygote, started on first use."""
    global _default
    with _default_lock:
        if _default is None:
            _default = Zygote()
        return _default


def check_arguments(dialect: Dialect | str, timeout: float, memory: int) -> Dialect:
    """The `Dialect` named, or the caller's mistake as an exception.

    Raises `ValueError` for an unknown dialect, a timeout that is not a
    positive finite number, or a memory limit that is not a positive integer.
    """
    try:
        resolved = Dialect(dialect)
    except ValueError:
        known = ", ".join(d.value for d in Dialect)
        raise ValueError(f"unknown dialect {dialect!r}; known: {known}") from None
    if isinstance(timeout, bool) or not (math.isfinite(timeout) and timeout > 0):
        raise ValueError(f"timeout must be a positive finite number of seconds, got {timeout!r}")
    if isinstance(memory, bool) or not isinstance(memory, int) or memory <= 0:
        raise ValueError(f"memory must be a positive number of bytes, got {memory!r}")
    return resolved


def _crash(message: str) -> Frame:
    return Frame(
        status=Status.CRASH,
        message=message,
        refusal=None,
        body=None,
        measures=None,
        violations=(),
    )


def _signal_name(number: int) -> str:
    try:
        return signal.Signals(number).name
    except ValueError:
        return f"signal {number}"


def frame_of(outcome: Outcome, timeout: float) -> Frame:
    """The frame an outcome stands for: the worker's, or the crash or timeout it was.

    A frame counts only from a worker that completed its isolation and exited
    cleanly; one that is unparseable is a crash, kept whole.
    """
    ending = outcome.ending
    if ending is None:
        return _crash("the worker left no record: the zygote died or stopped answering")
    match ending.kind:
        case _isolate.EndKind.TIMED_OUT:
            return Frame(
                status=Status.TIMEOUT,
                message=f"the program ran past its {timeout} s deadline",
                refusal=None,
                body=None,
                measures=None,
                violations=(),
            )
        case _isolate.EndKind.UNAVAILABLE:
            return _crash(f"the worker could not isolate itself (errno {ending.value})")
        case _isolate.EndKind.SIGNALLED:
            return _crash(f"the worker was killed by {_signal_name(ending.value)}")
        case _isolate.EndKind.EXITED:
            if ending.value != 0 or not ending.armed:
                return _crash(f"the worker exited with code {ending.value}")
    if outcome.overflow:
        return _crash(f"the worker wrote more than {MAX_RESULT_BYTES} bytes to its result pipe")
    try:
        return Frame.model_validate_json(outcome.data)
    except pydantic.ValidationError:
        return _crash("the worker delivered no valid result")


def run_program(
    zygote: Zygote, program: str, dialect: Dialect, *, timeout: float, memory: int
) -> ExecResult:
    """Run `program` on `zygote`; its result. Arguments are already checked."""
    payload = program.encode("utf-8", TEXT_ERRORS)
    start = time.monotonic()
    outcome = zygote.execute(JobKind.PROGRAM, payload, timeout=timeout, memory=memory)
    seconds = time.monotonic() - start
    frame = frame_of(outcome, timeout)
    sha = hashlib.sha256(payload).hexdigest()
    try:
        return _result(frame, sha, dialect, seconds)
    except pydantic.ValidationError:  # a frame whose fields contradict its status
        crash = _crash("the worker delivered a result that contradicts its status")
        return _result(crash, sha, dialect, seconds)


def _result(frame: Frame, program_sha256: str, dialect: Dialect, seconds: float) -> ExecResult:
    return ExecResult(
        status=frame.status,
        message=frame.message,
        refusal=frame.refusal,
        body=None if frame.body is None else BodyRef.of(frame.body),
        measures=frame.measures,
        violations=frame.violations,
        program_sha256=program_sha256,
        dialect=dialect,
        versions=current_versions(),
        seconds=seconds,
    )


def run(
    program: str,
    *,
    dialect: Dialect | str = Dialect.ARRIS,
    timeout: float = DEFAULT_TIMEOUT,
    memory: int = DEFAULT_MEMORY,
) -> ExecResult:
    """Run one program alone in a sandbox and say how it ended.

    Whatever the program does (a syntax error, an infinite loop, `os._exit`,
    a fork bomb) comes back as an `ExecResult` with a `Status`; only a
    caller's mistake raises: `ValueError` for an unknown dialect, a
    `timeout` that is not a positive finite number of seconds or a `memory`
    that is not a positive number of bytes, and `SandboxUnavailable` where
    this machine cannot isolate a program.

    The program binds a module-level `result` to an `arris.build.Solid`; it
    runs on a fresh model in a worker of its own, `timeout` seconds of wall
    clock and `memory` bytes of address space at most.

    >>> import arris_gym as ag
    >>> ok = ag.run("import arris.build as b\\nresult = b.Solid.box((0, 0, 0), (1, 2, 3))")
    >>> ok.status is ag.Status.OK
    True
    >>> ok.measures is not None and round(ok.measures.volume, 6)
    6.0
    >>> ag.run("result = (").status is ag.Status.SYNTAX
    True
    """
    resolved = check_arguments(dialect, timeout, memory)
    return run_program(default_zygote(), program, resolved, timeout=timeout, memory=memory)

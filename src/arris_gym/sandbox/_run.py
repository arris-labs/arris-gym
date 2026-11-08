"""`run`: one program, alone in a sandbox, one `ExecResult` back.

The caller's side of the program path: send the text to a program worker
through the zygote, send the body it delivers to a body worker, and turn the
wardens' records and the workers' frames into a result. Private; `Sandbox` and
`arris_gym.run` are the public names.
"""

from __future__ import annotations

import functools
import hashlib
import importlib.metadata
import math
import signal
import time
from dataclasses import dataclass

import pydantic

from arris_gym.sandbox import _isolate, _program
from arris_gym.sandbox._frame import BodyFrame, ProgramFrame
from arris_gym.sandbox._zygote import MAX_RESULT_BYTES, JobKind, Outcome, Zygote
from arris_gym.sandbox.outcome import (
    ArrisRefusal,
    BodyRef,
    Dialect,
    ExecResult,
    Measures,
    Status,
    Versions,
)

# SEED.md §5's wall-clock limit and the roadmap's memory limit, revisited
# with M3's numbers.
DEFAULT_TIMEOUT = 5.0
DEFAULT_MEMORY = 512 * 2**20
# The workers as a crash's or a timeout's message names them.
PROGRAM_WORKER = "program worker"
BODY_WORKER = "body worker"


@functools.cache
def current_versions() -> Versions:
    """The pinned versions this process runs under."""
    return Versions(
        arris=importlib.metadata.version("arris"),
        numpy=importlib.metadata.version("numpy"),
        arris_gym=importlib.metadata.version("arris-gym"),
    )


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


@dataclass(frozen=True)
class Verdict:
    """How a job ended, as the caller decides it: the `ExecResult` fields
    that do not describe the program itself."""

    status: Status
    message: str
    refusal: ArrisRefusal | None = None
    body: bytes | None = None
    measures: Measures | None = None
    violations: tuple[str, ...] = ()
    # Whether the outcome is a function of the cache key alone: not a
    # timeout, a crash or a `MemoryError`, which the machine and the limits decide.
    cacheable: bool = True


def _signal_name(number: int) -> str:
    try:
        return signal.Signals(number).name
    except ValueError:
        return f"signal {number}"


def _crash(what: str, outcome: Outcome) -> Verdict:
    """A crash's verdict: `what` happened, then the tail of the worker's stderr."""
    tail = outcome.stderr.decode("utf-8", "replace")
    if tail:
        what += f"; its stderr ends:\n{tail}"
    return Verdict(Status.CRASH, what, cacheable=False)


def ended(outcome: Outcome, worker: str, timeout: float) -> Verdict | None:
    """The verdict of a job that delivered nothing to trust, or None if its
    frame is to be parsed.

    A frame counts only from a worker that completed its isolation and
    exited with code 0 and wrote at most `MAX_RESULT_BYTES`. `worker` names
    the worker in a crash's message.
    """
    ending = outcome.ending
    if ending is None:
        return _crash(f"the {worker} left no record: the zygote died or stopped answering", outcome)
    if outcome.overflow:
        return _crash(
            f"the {worker} wrote more than {MAX_RESULT_BYTES} bytes to its result pipe", outcome
        )
    match ending.kind:
        case _isolate.EndKind.TIMED_OUT:
            return Verdict(
                Status.TIMEOUT, f"the {worker} ran past the {timeout} s deadline", cacheable=False
            )
        case _isolate.EndKind.UNAVAILABLE:
            return _crash(f"the {worker} could not isolate itself (errno {ending.value})", outcome)
        case _isolate.EndKind.SIGNALLED:
            return _crash(f"the {worker} was killed by {_signal_name(ending.value)}", outcome)
        case _isolate.EndKind.EXITED:
            if not ending.armed:
                return _crash(f"the {worker} could not isolate itself", outcome)
            if ending.value != 0:
                return _crash(f"the {worker} exited with code {ending.value}", outcome)
    if not outcome.data:
        return _crash(f"the {worker} exited with code 0 and delivered no result", outcome)
    return None


def _not_a_frame(worker: str, outcome: Outcome) -> Verdict:
    return _crash(f"the {worker} delivered a result that is not a valid frame", outcome)


def program_verdict(outcome: Outcome, timeout: float) -> Verdict | ProgramFrame:
    """The program worker's frame, or the crash or timeout its job was."""
    early = ended(outcome, PROGRAM_WORKER, timeout)
    if early is not None:
        return early
    try:
        return ProgramFrame.model_validate_json(outcome.data)
    except pydantic.ValidationError:
        return _not_a_frame(PROGRAM_WORKER, outcome)


def body_verdict(outcome: Outcome, body: bytes, timeout: float) -> Verdict:
    """The verdict on `body` from its body worker's job: the body worker's
    frame, or the crash or timeout its job was."""
    early = ended(outcome, BODY_WORKER, timeout)
    if early is not None:
        return early
    try:
        frame = BodyFrame.model_validate_json(outcome.data)
    except pydantic.ValidationError:
        return _not_a_frame(BODY_WORKER, outcome)
    has_body = frame.status in (Status.OK, Status.CHECKER_FAIL)
    return Verdict(
        frame.status,
        frame.message,
        body=body if has_body else None,
        measures=frame.measures,
        violations=frame.violations,
        cacheable=not frame.out_of_memory,
    )


@dataclass(frozen=True)
class Executed:
    """A result and whether the cache may keep it."""

    result: ExecResult
    cacheable: bool


def run_program(
    zygote: Zygote, program: str, dialect: Dialect, *, timeout: float, memory: int
) -> Executed:
    """Run `program` on `zygote`; its result. Arguments are already checked.

    The program worker's frame is believed only where believing it costs the
    program alone: a failure it reports. A body it delivers is read back,
    checked and measured by a body worker under the same limits and the same
    deadline (ADR-0002).
    """
    text = program.encode("utf-8", _program.TEXT_ERRORS)
    start = time.monotonic()
    deadline = start + timeout
    payload = _program.payload(dialect, text)
    outcome = zygote.execute(JobKind.PROGRAM, payload, deadline=deadline, memory=memory)
    found = program_verdict(outcome, timeout)
    if isinstance(found, Verdict):
        verdict = found
    elif found.body is None:
        verdict = Verdict(
            found.status,
            found.message,
            refusal=found.refusal,
            cacheable=not found.out_of_memory,
        )
    else:
        read = zygote.execute(JobKind.BODY, found.body, deadline=deadline, memory=memory)
        verdict = body_verdict(read, found.body, timeout)
    seconds = time.monotonic() - start
    result = ExecResult(
        status=verdict.status,
        message=verdict.message,
        refusal=verdict.refusal,
        body=None if verdict.body is None else BodyRef.of(verdict.body),
        measures=verdict.measures,
        violations=verdict.violations,
        program_sha256=hashlib.sha256(text).hexdigest(),
        dialect=dialect,
        versions=current_versions(),
        seconds=seconds,
    )
    return Executed(result, verdict.cacheable)

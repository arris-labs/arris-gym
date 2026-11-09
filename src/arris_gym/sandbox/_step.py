"""The step job: read a STEP text into a fresh model, deliver its one solid.

Called by the zygote's dispatch (`sandbox/_zygote.py`) inside an isolated
step worker, under the same limits as a program worker, never in the
caller's process: a target's STEP is the output of a hostile program, so
reading it is a kernel call on hostile input (ADR-0011). The worker runs
`read_step` on a fresh model and writes one `StepFrame`: the `write_body`
bytes of the file's one solid, which a body worker then checks and measures
as it does a program's, or the failure, decided by type and by the count of
solids, never by a message's wording. Private.
"""

from __future__ import annotations

import os

import arris

from arris_gym.sandbox._frame import StepFrame
from arris_gym.sandbox._program import (
    TEXT_ERRORS,
    exception_line,
    read_all,
    refusal_of,
    write_frame,
)
from arris_gym.sandbox.outcome import ArrisRefusal, Status

# A target is exactly this many solids (ADR-0011).
TARGET_SOLIDS = 1


def payload(step: str) -> bytes:
    """A step job's payload: the STEP text, encoded so that every string round-trips."""
    return step.encode("utf-8", TEXT_ERRORS)


def solids_message(count: int) -> str:
    """The `runtime` message of a STEP that holds `count` solids, not one."""
    return f"the STEP holds {count} solids; a target is exactly {TARGET_SOLIDS}"


def _solid_refusal(refusal: arris.Refusal) -> ArrisRefusal:
    """A solid's refusal as the kernel gives it: kind, message, the STEP instance."""
    return ArrisRefusal(
        kind=refusal.kind, message=refusal.message, entities=(f"#{refusal.entity}",)
    )


def _failure(
    status: Status,
    message: str,
    refusal: ArrisRefusal | None = None,
    *,
    error: BaseException | None = None,
) -> StepFrame:
    return StepFrame(
        status=status,
        message=message,
        refusal=refusal,
        body=None,
        out_of_memory=isinstance(error, MemoryError),
    )


def classify(step: str) -> StepFrame:
    """Read `step` into a fresh model; the frame saying what it holds. Never raises.

    Exactly one solid the kernel built is `ok` with its body's bytes; zero or
    several solids are `runtime` naming the count; the one solid's refusal,
    or an `arris.ArrisError` from `read_step` (a file it cannot parse), is
    `arris_refusal` with the kernel's words; any other exception is
    `runtime` with Python's own line for it.
    """
    try:
        model = arris.Model()
        solids = model.read_step(step).solids
        if len(solids) != TARGET_SOLIDS:
            return _failure(Status.RUNTIME, solids_message(len(solids)))
        solid = solids[0]
        if solid.refusal is not None:
            refusal = _solid_refusal(solid.refusal)
            return _failure(Status.ARRIS_REFUSAL, refusal.message, refusal)
        if solid.body is None:
            return _failure(Status.RUNTIME, "the STEP's solid has neither a body nor a refusal")
        data = model.write_body(solid.body)
        return StepFrame(status=Status.OK, message="", refusal=None, body=data)
    except arris.ArrisError as error:
        refusal = refusal_of(error)
        return _failure(Status.ARRIS_REFUSAL, refusal.message, refusal)
    except BaseException as error:  # noqa: BLE001 - MemoryError, text the kernel cannot take
        return _failure(Status.RUNTIME, exception_line(error), error=error)


def execute(payload_fd: int, result_fd: int) -> None:
    """Read the STEP text on `payload_fd`; write one frame to `result_fd`."""
    worker = os.getpid()
    write_frame(result_fd, classify(read_all(payload_fd).decode("utf-8", TEXT_ERRORS)), worker)

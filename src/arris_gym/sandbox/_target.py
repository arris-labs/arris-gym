"""`read_target`'s path: a STEP text to a step worker, its body to a body worker.

The caller's side of a target (ADR-0011): send the text to a step worker
through the zygote, send the one solid's bytes it delivers to a body worker
under the same deadline, and turn the wardens' records and the workers'
frames into a `TargetResult`, trusting no frame. Private; `Sandbox.read_target`
and `arris_gym.read_target` are the public names.
"""

from __future__ import annotations

import hashlib
import time

import pydantic

from arris_gym.sandbox import _run, _step
from arris_gym.sandbox._frame import StepFrame
from arris_gym.sandbox._program import TEXT_ERRORS
from arris_gym.sandbox._zygote import JobKind, Outcome, Zygote
from arris_gym.sandbox.outcome import BodyRef, TargetResult

# The worker as a crash's or a timeout's message names it.
STEP_WORKER = "step worker"
# Where a STEP text's data section starts: `step_sha256` hashes from here on,
# as `tools/oracle/worker.py` does, so a header the worker blanked stays out.
STEP_DATA_MARK = "DATA;"


def step_sha256(step: str) -> str | None:
    """The `step_sha256` of a STEP text, or None when it has no data section."""
    start = step.find(STEP_DATA_MARK)
    if start < 0:
        return None
    return hashlib.sha256(step[start:].encode("utf-8", TEXT_ERRORS)).hexdigest()


def _step_verdict(outcome: Outcome, timeout: float) -> _run.Verdict | StepFrame:
    """The step worker's frame, or the crash or timeout its job was."""
    early = _run.ended(outcome, STEP_WORKER, timeout)
    if early is not None:
        return early
    try:
        return StepFrame.model_validate_json(outcome.data)
    except pydantic.ValidationError:
        return _run.not_a_frame(STEP_WORKER, outcome)


def read(zygote: Zygote, step: str, *, timeout: float, memory: int) -> TargetResult:
    """Read `step` on `zygote`; the target it is. Arguments are already checked.

    The step worker's frame is believed only where believing it costs this
    target alone: a failure it reports. The bytes of a solid it delivers are
    read back, checked and measured by a body worker under the same limits
    and the same deadline, as a program's are (ADR-0002, ADR-0011).
    """
    deadline = time.monotonic() + timeout
    outcome = zygote.execute(JobKind.STEP, _step.payload(step), deadline=deadline, memory=memory)
    found = _step_verdict(outcome, timeout)
    if isinstance(found, _run.Verdict):
        verdict = found
    elif found.body is None:
        verdict = _run.Verdict(found.status, found.message, refusal=found.refusal)
    else:
        body = zygote.execute(JobKind.BODY, found.body, deadline=deadline, memory=memory)
        verdict = _run.body_verdict(body, found.body, timeout)
    return TargetResult(
        status=verdict.status,
        message=verdict.message,
        refusal=verdict.refusal,
        body=None if verdict.body is None else BodyRef.of(verdict.body),
        measures=verdict.measures,
        violations=verdict.violations,
        step_sha256=step_sha256(step),
        versions=_run.current_versions(),
    )

"""The score job: a body scored against a target inside a score worker.

docs/ARCHITECTURE.md §The sandbox and §The reward. The payload is a
`ScoreJob`, both bodies' bytes and the reward config; the worker reads both
into one fresh model, computes the four terms and the field's metrics and
writes one `ScoreFrame`.
The bytes are a program's (the candidate) and the caller's (the target),
so reading them is a kernel call on hostile input, and a kernel crash here
costs the job, never the caller. The zygote's entry registers `execute` for
`JobKind.SCORE`. The caller parses the frame and trusts none of it
(`reward/_scoring.py`). Private.
"""

from __future__ import annotations

import math
import os
from typing import Self

import arris
from pydantic import BaseModel, ConfigDict, model_validator

from arris_gym.reward._config import RewardConfig
from arris_gym.reward._field import field_metrics
from arris_gym.reward._iou import IouRoute, iou
from arris_gym.reward._measures import measures
from arris_gym.reward._score import FieldMetrics
from arris_gym.reward._surface import surface
from arris_gym.reward._topology import topology
from arris_gym.sandbox._program import exception_line, read_all, write_frame
from arris_gym.sandbox.outcome import Status

# The statuses a score worker decides: the four terms computed (`ok`), or
# the kernel or the payload refused (`runtime`). `timeout` and `crash` are
# the caller's.
SCORE_STATUSES = (Status.OK, Status.RUNTIME)

_BYTES = ConfigDict(frozen=True, extra="forbid", ser_json_bytes="base64", val_json_bytes="base64")


class ScoreJob(BaseModel):
    """A score job's payload: the candidate's and the target's body bytes, and the config."""

    model_config = _BYTES

    config: RewardConfig
    candidate: bytes
    target: bytes


class ScoreFrame(BaseModel):
    """A score worker's account of one pair: its four terms, the IoU's route, the field's metrics.

    Guarantees, enforced on parsing in the caller: `status` is `ok` or
    `runtime`; the four terms, `iou_route` and `field` are set exactly when
    it is `ok`, each term a finite number in [0, 1] and `field` within
    `FieldMetrics`' ranges. The worker writes it unvalidated, so a number out
    of range reaches the caller and is refused there.
    """

    # Strict: a number written as a string is a forgery, not a coercion.
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    status: Status
    message: str
    iou: float | None
    iou_route: IouRoute | None
    surface: float | None
    measures: float | None
    topology: float | None
    field: FieldMetrics | None

    @model_validator(mode="after")
    def _fields_agree_with_status(self) -> Self:
        if self.status not in SCORE_STATUSES:
            raise ValueError(f"a score worker does not decide {self.status.value}")
        terms = (self.iou, self.surface, self.measures, self.topology)
        ok = self.status is Status.OK
        if (
            any((t is None) == ok for t in terms)
            or (self.iou_route is None) == ok
            or (self.field is None) == ok
        ):
            raise ValueError("the terms, the route and the field are set exactly when status is OK")
        if not all(t is None or (math.isfinite(t) and 0.0 <= t <= 1.0) for t in terms):
            raise ValueError("every term must be a finite number in [0, 1]")
        return self


def evaluate(job: ScoreJob) -> ScoreFrame:
    """The four terms and the field's metrics of `job.candidate` against `job.target`.

    Both bodies are read into one fresh model. Raises the kernel's
    `ArrisError` where it cannot read, measure or mesh a body, and what the
    terms and the field's metrics raise.
    """
    config = job.config
    model = arris.Model()
    candidate = model.read_body(job.candidate).body
    target = model.read_body(job.target).body
    estimate = iou(
        model,
        candidate,
        target,
        budget=config.iou_budget,
        chord_fraction=config.chord_fraction,
        points=config.points,
        seed=config.seed,
    )
    near = surface(
        model,
        candidate,
        target,
        tau=config.tau,
        chord_fraction=config.chord_fraction,
        points=config.surface_points,
        seed=config.seed,
    )
    # Unvalidated: the caller, which trusts no frame, is the one to refuse it.
    return ScoreFrame.model_construct(
        status=Status.OK,
        message="",
        iou=estimate.value,
        iou_route=estimate.route,
        surface=near,
        measures=measures(model, candidate, target),
        topology=topology(model, candidate, target, kind_weight=config.kind_weight),
        field=field_metrics(model, candidate, target, seed=config.seed),
    )


def frame(payload: bytes) -> ScoreFrame:
    """The frame for the score job `payload`; `runtime` with Python's own line where it fails.

    Never raises: an unreadable payload, a body the kernel refuses and a
    `MemoryError` are each `runtime`.
    """
    try:
        return evaluate(ScoreJob.model_validate_json(payload))
    except BaseException as error:  # noqa: BLE001 - the kernel's refusals and MemoryError
        return ScoreFrame(
            status=Status.RUNTIME,
            message=exception_line(error),
            iou=None,
            iou_route=None,
            surface=None,
            measures=None,
            topology=None,
            field=None,
        )


def execute(payload_fd: int, result_fd: int) -> None:
    """Read the score job on `payload_fd`; write one frame to `result_fd`."""
    worker = os.getpid()  # a forked child writes no frame (`write_frame`)
    write_frame(result_fd, frame(read_all(payload_fd)), worker)

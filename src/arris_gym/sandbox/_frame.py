"""Frames: what a worker tells the caller, as one JSON document each.

A `ProgramFrame` is written by `sandbox/_program.py` inside a program
worker, a `StepFrame` by `sandbox/_step.py` inside a step worker, a
`BodyFrame` by `sandbox/_body.py` inside a body worker; each is parsed in
the caller (`sandbox/_run.py`, `sandbox/_target.py`). The caller trusts neither (a
program can reach its result pipe and write its own): a frame that is not
one whole, or whose fields contradict its status, is refused at parsing and
the job is a `crash`. Private.
"""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from arris_gym.sandbox.outcome import ArrisRefusal, Measures, Status

# The statuses a program worker decides. `checker_fail` and the measures
# are the body worker's, `timeout` and `crash` the caller's: a program frame
# claiming one of them is refused, never believed.
PROGRAM_STATUSES = frozenset(
    {Status.OK, Status.SYNTAX, Status.RUNTIME, Status.UNSUPPORTED_API, Status.ARRIS_REFUSAL}
)
# The statuses a body worker decides: the body read back, checked and
# measured (`ok`), rejected by the checker, or unreadable (`runtime`).
BODY_STATUSES = frozenset({Status.OK, Status.CHECKER_FAIL, Status.RUNTIME})
# The statuses a step worker decides: one solid's bytes to read back (`ok`),
# the kernel refusing the file or its solid, or anything else (`runtime`).
STEP_STATUSES = frozenset({Status.OK, Status.RUNTIME, Status.ARRIS_REFUSAL})

_CONFIG = ConfigDict(frozen=True, extra="forbid", ser_json_bytes="base64", val_json_bytes="base64")


class ProgramFrame(BaseModel):
    """A program worker's account of how a program ended.

    Guarantees, enforced on parsing: `status` is one a program worker
    decides (`PROGRAM_STATUSES`); `body`, the `write_body` bytes of the
    program's `result`, is set exactly when `status` is `OK`, which then
    means only "a body to read back"; `refusal` is set exactly when
    `status` is `ARRIS_REFUSAL`. `body` travels as base64. `out_of_memory`
    says the program ended on a `MemoryError`, by type: the result depends on
    the memory limit and the machine, so it is not cached.
    """

    model_config = _CONFIG

    status: Status
    message: str
    refusal: ArrisRefusal | None
    body: bytes | None
    out_of_memory: bool = False

    @model_validator(mode="after")
    def _fields_agree_with_status(self) -> Self:
        if self.status not in PROGRAM_STATUSES:
            raise ValueError(f"a program worker does not decide {self.status.value}")
        if (self.body is not None) != (self.status is Status.OK):
            raise ValueError("body is set exactly when status is OK")
        if (self.refusal is not None) != (self.status is Status.ARRIS_REFUSAL):
            raise ValueError("refusal is set exactly when status is ARRIS_REFUSAL")
        return self


class StepFrame(BaseModel):
    """A step worker's account of the STEP text it was given (ADR-0011).

    Guarantees, enforced on parsing: `status` is one a step worker decides
    (`STEP_STATUSES`); `body`, the `write_body` bytes of the STEP's one
    solid, is set exactly when `status` is `OK`, which then means only "a
    body to read back"; `refusal` is set exactly when `status` is
    `ARRIS_REFUSAL`. `body` travels as base64. `out_of_memory` is as in
    `ProgramFrame`.
    """

    model_config = _CONFIG

    status: Status
    message: str
    refusal: ArrisRefusal | None
    body: bytes | None
    out_of_memory: bool = False

    @model_validator(mode="after")
    def _fields_agree_with_status(self) -> Self:
        if self.status not in STEP_STATUSES:
            raise ValueError(f"a step worker does not decide {self.status.value}")
        if (self.body is not None) != (self.status is Status.OK):
            raise ValueError("body is set exactly when status is OK")
        if (self.refusal is not None) != (self.status is Status.ARRIS_REFUSAL):
            raise ValueError("refusal is set exactly when status is ARRIS_REFUSAL")
        return self


class BodyFrame(BaseModel):
    """A body worker's account of the body bytes it was given.

    Guarantees, enforced on parsing: `status` is one a body worker decides
    (`BODY_STATUSES`); `measures` is set exactly when it is `OK`;
    `violations`, the checker's in its own words, are non-empty exactly when
    it is `CHECKER_FAIL`. `out_of_memory` is as in `ProgramFrame`.
    """

    model_config = _CONFIG

    status: Status
    message: str
    measures: Measures | None
    violations: tuple[str, ...]
    out_of_memory: bool = False

    @model_validator(mode="after")
    def _fields_agree_with_status(self) -> Self:
        if self.status not in BODY_STATUSES:
            raise ValueError(f"a body worker does not decide {self.status.value}")
        if (self.measures is not None) != (self.status is Status.OK):
            raise ValueError("measures are set exactly when status is OK")
        if bool(self.violations) != (self.status is Status.CHECKER_FAIL):
            raise ValueError("violations are set exactly when status is CHECKER_FAIL")
        return self


class MeshFrame(BaseModel):
    """A mesh worker's account of the body bytes it was given: a tessellation.

    Guarantees, enforced on parsing: `status` is `OK` or `RUNTIME`;
    `positions` (little-endian float64 triples) and `triangles` (little-endian
    uint32 triples) are non-empty exactly when it is `OK`. They travel as
    base64. That the triangles index the positions is checked by the reader
    (`sandbox/_picture.py`), which trusts nothing.
    """

    model_config = _CONFIG

    status: Status
    message: str
    positions: bytes
    triangles: bytes

    @model_validator(mode="after")
    def _fields_agree_with_status(self) -> Self:
        if self.status not in (Status.OK, Status.RUNTIME):
            raise ValueError(f"a mesh worker does not decide {self.status.value}")
        if bool(self.positions) != (self.status is Status.OK) or bool(self.triangles) != (
            self.status is Status.OK
        ):
            raise ValueError("a mesh is delivered exactly when status is OK")
        return self

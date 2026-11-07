"""Frames: what a worker tells the caller, as one JSON document each.

A `ProgramFrame` is written by `sandbox/_program.py` inside a program
worker, a `BodyFrame` by `sandbox/_body.py` inside a body worker; both are
parsed by `sandbox/_run.py` in the caller. The caller trusts neither (a
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

_CONFIG = ConfigDict(frozen=True, extra="forbid", ser_json_bytes="base64", val_json_bytes="base64")


class ProgramFrame(BaseModel):
    """A program worker's account of how a program ended.

    Guarantees, enforced on parsing: `status` is one a program worker
    decides (`PROGRAM_STATUSES`); `body`, the `write_body` bytes of the
    program's `result`, is set exactly when `status` is `OK`, which then
    means only "a body to read back"; `refusal` is set exactly when
    `status` is `ARRIS_REFUSAL`. `body` travels as base64.
    """

    model_config = _CONFIG

    status: Status
    message: str
    refusal: ArrisRefusal | None
    body: bytes | None

    @model_validator(mode="after")
    def _fields_agree_with_status(self) -> Self:
        if self.status not in PROGRAM_STATUSES:
            raise ValueError(f"a program worker does not decide {self.status.value}")
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
    it is `CHECKER_FAIL`.
    """

    model_config = _CONFIG

    status: Status
    message: str
    measures: Measures | None
    violations: tuple[str, ...]

    @model_validator(mode="after")
    def _fields_agree_with_status(self) -> Self:
        if self.status not in BODY_STATUSES:
            raise ValueError(f"a body worker does not decide {self.status.value}")
        if (self.measures is not None) != (self.status is Status.OK):
            raise ValueError("measures are set exactly when status is OK")
        if bool(self.violations) != (self.status is Status.CHECKER_FAIL):
            raise ValueError("violations are set exactly when status is CHECKER_FAIL")
        return self

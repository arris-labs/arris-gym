"""The typed outcome of running one program (docs/ARCHITECTURE.md §Outcomes).

`run` never raises on a program: whatever the program does comes back as an
`ExecResult` carrying one `Status`. Every type here is a frozen `pydantic`
model, built by the sandbox and never changed after.
"""

from __future__ import annotations

import enum
import hashlib
from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator


class Status(enum.Enum):
    """How a program ended: exactly one per program, decided from a type or
    from how the process ended, never from a message's wording."""

    OK = "ok"
    SYNTAX = "syntax"
    RUNTIME = "runtime"
    UNSUPPORTED_API = "unsupported_api"
    ARRIS_REFUSAL = "arris_refusal"
    CHECKER_FAIL = "checker_fail"
    TIMEOUT = "timeout"
    CRASH = "crash"


class Dialect(enum.Enum):
    """The API a program is written against: `arris.build`, or the CadQuery
    subset `arris_gym.cq`, which the program imports as `cadquery`."""

    ARRIS = "arris"
    CQ = "cq"


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ArrisRefusal(_Frozen):
    """The kernel declining an operation, kept as the kernel said it.

    Guarantees: `kind` is the exception's class name, `message` is its
    `str()` and `entities` come from its `entity` / `entities` fields, each
    unchanged. Refuses to paraphrase: nothing here is parsed from a message.
    """

    kind: str
    message: str
    entities: tuple[str, ...]


class BodyRef(_Frozen):
    """The body a program built, as the worker's `write_body` bytes.

    Guarantees: `sha256` is the hex SHA-256 of `data`, which is the body's
    digest (a fresh model gives the same bytes every time, ADR-0001). Refuses
    a `sha256` that does not match.
    """

    data: bytes
    sha256: str

    @model_validator(mode="after")
    def _digest_matches(self) -> Self:
        if hashlib.sha256(self.data).hexdigest() != self.sha256:
            raise ValueError("BodyRef.sha256 is not the SHA-256 of data")
        return self

    @classmethod
    def of(cls, data: bytes) -> BodyRef:
        """The reference for body bytes `data`, its digest computed."""
        return cls(data=data, sha256=hashlib.sha256(data).hexdigest())


class Measures(_Frozen):
    """What the kernel measures of a body, read by the body worker.

    `bounds` is the pair (lowest corner, highest corner) as the kernel
    reports it, padded by its tolerance. `face_kinds` pairs each surface kind
    with its face count, sorted by kind, so its order never depends on a hash.
    """

    volume: float
    area: float
    centroid: tuple[float, float, float]
    bounds: tuple[tuple[float, float, float], tuple[float, float, float]]
    faces: int
    shells: int
    genus: int
    face_kinds: tuple[tuple[str, int], ...]


class Versions(_Frozen):
    """The pinned versions a result was produced under; written in every row."""

    arris: str
    numpy: str
    arris_gym: str


class ExecResult(_Frozen):
    """The outcome of one program. Every program has one, whatever it did.

    Guarantees, enforced on construction: `refusal` is set exactly when
    `status` is `ARRIS_REFUSAL`; `body` is set exactly when `status` is `OK` or
    `CHECKER_FAIL`, `measures` exactly when it is `OK`; `violations` is empty
    unless `status` is `CHECKER_FAIL`. `message` is what a model sees on a
    retry, verbatim. `seconds` is wall-clock and sits outside every digest.

    >>> result = ExecResult(
    ...     status=Status.SYNTAX,
    ...     message="invalid syntax (<program>, line 1)",
    ...     refusal=None,
    ...     body=None,
    ...     measures=None,
    ...     violations=(),
    ...     program_sha256=hashlib.sha256(b"x =").hexdigest(),
    ...     dialect=Dialect.ARRIS,
    ...     versions=Versions(arris="0.10.0", numpy="2.3.4", arris_gym="0.1.0"),
    ...     seconds=0.01,
    ... )
    >>> result.status is Status.SYNTAX
    True
    """

    status: Status
    message: str
    refusal: ArrisRefusal | None
    body: BodyRef | None
    measures: Measures | None
    violations: tuple[str, ...]
    program_sha256: str
    dialect: Dialect
    versions: Versions
    seconds: float

    @model_validator(mode="after")
    def _fields_agree_with_status(self) -> Self:
        if (self.refusal is not None) != (self.status is Status.ARRIS_REFUSAL):
            raise ValueError("refusal is set exactly when status is ARRIS_REFUSAL")
        if (self.body is not None) != (self.status in (Status.OK, Status.CHECKER_FAIL)):
            raise ValueError("body is set exactly when status is OK or CHECKER_FAIL")
        if (self.measures is not None) != (self.status is Status.OK):
            raise ValueError("measures are set exactly when status is OK")
        if self.violations and self.status is not Status.CHECKER_FAIL:
            raise ValueError("violations belong to CHECKER_FAIL alone")
        return self


# The statuses a target can end with: those the step worker, the body worker
# and the caller decide. `syntax` and `unsupported_api` are a program's alone.
TARGET_STATUSES = frozenset(
    {
        Status.OK,
        Status.RUNTIME,
        Status.ARRIS_REFUSAL,
        Status.CHECKER_FAIL,
        Status.TIMEOUT,
        Status.CRASH,
    }
)


class TargetResult(_Frozen):
    """A target: a STEP text read by arris in a step worker (ADR-0011).

    Every STEP text has one, whatever it holds. Guarantees, enforced on
    construction: `status` is one a target can end with (`ok`, `runtime`,
    `arris_refusal`, `checker_fail`, `timeout` or `crash`; never `syntax` or
    `unsupported_api`); `refusal` is set exactly when `status` is
    `ARRIS_REFUSAL`; `body` exactly when it is `OK` or `CHECKER_FAIL`,
    `measures` exactly when it is `OK`; `violations` is empty unless it is
    `CHECKER_FAIL`. `message`, `refusal` and `violations` are the kernel's
    words, verbatim. `step_sha256` is the hex SHA-256 of the text's data
    section, from `DATA;` on, as the oracle hashes it, or None for a text
    with no data section. Nothing here is wall-clock.

    >>> result = TargetResult(
    ...     status=Status.RUNTIME,
    ...     message="the STEP holds 0 solids; a target is exactly 1",
    ...     refusal=None,
    ...     body=None,
    ...     measures=None,
    ...     violations=(),
    ...     step_sha256=None,
    ...     versions=Versions(arris="0.10.0", numpy="2.3.4", arris_gym="0.1.0"),
    ... )
    >>> result.status is Status.RUNTIME
    True
    """

    status: Status
    message: str
    refusal: ArrisRefusal | None
    body: BodyRef | None
    measures: Measures | None
    violations: tuple[str, ...]
    step_sha256: str | None
    versions: Versions

    @model_validator(mode="after")
    def _fields_agree_with_status(self) -> Self:
        if self.status not in TARGET_STATUSES:
            raise ValueError(f"a target does not end {self.status.value}")
        if (self.refusal is not None) != (self.status is Status.ARRIS_REFUSAL):
            raise ValueError("refusal is set exactly when status is ARRIS_REFUSAL")
        if (self.body is not None) != (self.status in (Status.OK, Status.CHECKER_FAIL)):
            raise ValueError("body is set exactly when status is OK or CHECKER_FAIL")
        if (self.measures is not None) != (self.status is Status.OK):
            raise ValueError("measures are set exactly when status is OK")
        if self.violations and self.status is not Status.CHECKER_FAIL:
            raise ValueError("violations belong to CHECKER_FAIL alone")
        if self.step_sha256 is not None and not _is_sha256(self.step_sha256):
            raise ValueError("step_sha256 is not a hex SHA-256")
        return self


def _is_sha256(text: str) -> bool:
    """Whether `text` is 64 lower-case hex digits."""
    return len(text) == hashlib.sha256().digest_size * 2 and all(
        c in "0123456789abcdef" for c in text
    )

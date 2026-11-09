"""The oracle report: what one program did on the oracle, parsed and checked.

An oracle worker (ADR-0004) writes one JSON frame; the caller trusts none of
it, as it trusts none of any worker's (a program can reach its result pipe
and write its own). `parse_outcome` turns a job's `Outcome` into an
`OracleReport` and never raises: a frame that is not one whole, or that
contradicts its status, the program sent or its own STEP's hash, is a `crash`.
"""

from __future__ import annotations

import enum
import hashlib
import re
from typing import Self

import pydantic
from pydantic import BaseModel, ConfigDict, FiniteFloat, model_validator

from arris_gym.sandbox import Status
from arris_gym.sandbox._run import ended
from arris_gym.sandbox._zygote import Outcome

# How a failed job names the worker in a `crash` or `timeout` message.
ORACLE_WORKER = "oracle worker"
_SHA256 = re.compile(r"[0-9a-f]{64}")
# Where a STEP text's data section starts: `step_sha256` hashes from here on,
# as `tools/oracle/worker.py` does, so a header the worker blanked stays out.
_STEP_DATA_MARK = "DATA;"


def _step_sha256(step: str) -> str | None:
    """The `step_sha256` of a STEP text, or None when it has no data section."""
    start = step.find(_STEP_DATA_MARK)
    if start < 0:
        return None
    return hashlib.sha256(step[start:].encode("utf-8", "surrogatepass")).hexdigest()


class OracleStatus(enum.Enum):
    """How a program ended on the oracle: exactly one per program.

    The worker decides `ok`, `syntax`, `runtime`, `no_result` and `invalid`
    (`BRepCheck_Analyzer` fails); the caller decides `timeout` and `crash`
    from how the worker ended, and a frame claiming either is refused.
    """

    OK = "ok"
    SYNTAX = "syntax"
    RUNTIME = "runtime"
    NO_RESULT = "no_result"
    INVALID = "invalid"
    TIMEOUT = "timeout"
    CRASH = "crash"


# The statuses a worker's frame may carry; the rest are the caller's.
_WORKER_STATUSES = frozenset(
    {
        OracleStatus.OK,
        OracleStatus.SYNTAX,
        OracleStatus.RUNTIME,
        OracleStatus.NO_RESULT,
        OracleStatus.INVALID,
    }
)
# The statuses whose shape was measured: the checker runs after the measures.
_MEASURED = frozenset({OracleStatus.OK, OracleStatus.INVALID})

_CONFIG = ConfigDict(frozen=True, extra="forbid")


class OracleMeasures(BaseModel):
    """What Open CASCADE measures of the result: `GProp` volume, area and
    centroid, the padded bounding box, and the face and solid counts.

    Every float is finite; a frame carrying NaN or infinity is refused.
    """

    model_config = _CONFIG

    volume: FiniteFloat
    area: FiniteFloat
    centroid: tuple[FiniteFloat, FiniteFloat, FiniteFloat]
    bounds: tuple[
        tuple[FiniteFloat, FiniteFloat, FiniteFloat],
        tuple[FiniteFloat, FiniteFloat, FiniteFloat],
    ]
    faces: int = pydantic.Field(ge=0)
    solids: int = pydantic.Field(ge=0)


class OracleVersions(BaseModel):
    """The versions the oracle ran under; written in every row."""

    model_config = _CONFIG

    cadquery: str
    ocp: str
    python: str


class OracleReport(BaseModel):
    """The outcome of one program on the oracle. Every program has one.

    Guarantees, enforced on construction: `measures` is set exactly when
    `status` is `OK` or `INVALID` (the checker runs after the measures);
    `step_sha256` exactly when it is `OK`; `versions` exactly when the worker
    answered, so not for `TIMEOUT` or `CRASH`; both hashes are 64 lower-case
    hex digits. `message` is the exception's own words, verbatim.

    `step` is the result's STEP text with its header's timestamp and the
    translator counter blanked (ADR-0011): set only when `status` is `OK`, and
    then `step_sha256` is its data section's hash. It is left out of a
    recorded report (`oracle.jsonl`, a fixture's `oracle.json`), so a report
    read back has it None. `seconds` is wall-clock; `step` and `seconds` sit
    outside `digest`, which `step_sha256` already pins.
    """

    model_config = _CONFIG

    status: OracleStatus
    message: str
    measures: OracleMeasures | None
    step_sha256: str | None
    program_sha256: str
    versions: OracleVersions | None
    step: str | None = None
    seconds: float = 0.0

    @model_validator(mode="after")
    def _fields_agree_with_status(self) -> Self:
        if (self.measures is not None) != (self.status in _MEASURED):
            raise ValueError("measures is set exactly when status is OK or INVALID")
        if (self.step_sha256 is not None) != (self.status is OracleStatus.OK):
            raise ValueError("step_sha256 is set exactly when status is OK")
        if (self.versions is not None) != (self.status in _WORKER_STATUSES):
            raise ValueError("versions is set exactly when the worker answered")
        for sha in (self.program_sha256, self.step_sha256):
            if sha is not None and not _SHA256.fullmatch(sha):
                raise ValueError("a SHA-256 is 64 lower-case hex digits")
        if self.step is not None and (
            self.status is not OracleStatus.OK or _step_sha256(self.step) != self.step_sha256
        ):
            raise ValueError("step is set only when status is OK, and step_sha256 is its hash")
        return self

    def digest(self) -> str:
        """The SHA-256 of this report without its `step` text or wall-clock `seconds`.

        >>> r = OracleReport(
        ...     status=OracleStatus.SYNTAX, message="m", measures=None, step_sha256=None,
        ...     program_sha256="0" * 64,
        ...     versions=OracleVersions(cadquery="2.3.0", ocp="7.9.3.0", python="3.12"),
        ... )
        >>> r.digest() == r.model_copy(update={"seconds": 9.0}).digest()
        True
        """
        data = self.model_dump_json(exclude={"step", "seconds"}).encode("utf-8")
        return hashlib.sha256(data).hexdigest()


class _OracleFrame(BaseModel):
    """The frame an oracle worker writes: an `OracleReport` with `step_text`
    for its `step`, without `seconds`."""

    model_config = _CONFIG

    status: OracleStatus
    message: str
    measures: OracleMeasures | None
    step_sha256: str | None
    step_text: str | None
    program_sha256: str
    versions: OracleVersions


def program_sha256(program: str) -> str:
    """The hex SHA-256 of a program's text, as the oracle worker computes it."""
    return hashlib.sha256(program.encode("utf-8", "surrogatepass")).hexdigest()


def parse_outcome(
    outcome: Outcome, program: str, *, timeout: float, seconds: float
) -> OracleReport:
    """The report of the job that ran `program`, from what came back unread.

    Never raises, whatever bytes the result pipe held. A job that ended
    without delivering a frame (timeout, killed, no record, overflow) is
    `TIMEOUT` or `CRASH` with the sandbox's own message. A frame is believed
    only when whole and consistent: unparseable, claiming a status only the
    caller decides (it would carry versions the caller's statuses do not),
    contradicting its status, carrying another program's SHA-256, or carrying
    a STEP text whose recomputed hash is not its `step_sha256`, it is a
    `CRASH`. An `OK` frame carries its STEP text; any other carries none.
    """
    sha = program_sha256(program)
    early = ended(outcome, ORACLE_WORKER, timeout)
    if early is not None:
        status = OracleStatus.TIMEOUT if early.status is Status.TIMEOUT else OracleStatus.CRASH
        return _caller_report(status, early.message, sha, seconds)
    try:
        frame = _OracleFrame.model_validate_json(outcome.data)
        fields = dict(frame)  # one level only: the nested models are already validated
        step = fields.pop("step_text")
        if (step is not None) != (frame.status is OracleStatus.OK):
            raise ValueError("step_text is set exactly when status is OK")
        if step is not None and _step_sha256(step) != frame.step_sha256:
            return _caller_report(
                OracleStatus.CRASH,
                f"the {ORACLE_WORKER} delivered a STEP that contradicts its hash",
                sha,
                seconds,
            )
        report = OracleReport(**fields, step=step, seconds=seconds)
    except (pydantic.ValidationError, ValueError, RecursionError):
        return _caller_report(
            OracleStatus.CRASH,
            f"the {ORACLE_WORKER} delivered a result that is not a valid frame",
            sha,
            seconds,
        )
    if report.program_sha256 != sha:
        return _caller_report(
            OracleStatus.CRASH,
            f"the {ORACLE_WORKER} delivered a frame that contradicts its job",
            sha,
            seconds,
        )
    return report


def _caller_report(status: OracleStatus, message: str, sha: str, seconds: float) -> OracleReport:
    return OracleReport(
        status=status,
        message=message,
        measures=None,
        step_sha256=None,
        program_sha256=sha,
        versions=None,
        seconds=seconds,
    )

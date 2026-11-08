"""The comparer (ADR-0006): one program's arris result against its oracle report.

`compare` gives a `FidelityRow`: `agree`, `disagree` with a
`DisagreementClass`, or `unclassified`. The rule classes what the two statuses
settle; a `Verdict` with its evidence classes the rest, or replaces the rule's
class. Every `match` over a status is exhaustive and closed by `assert_never`.
"""

from __future__ import annotations

import enum
import re
from typing import Annotated, Literal, Self, assert_never

import pydantic
from pydantic import BaseModel, ConfigDict, FiniteFloat, model_validator

from arris_gym.fidelity._agreement import (
    MeasureDeltas,
    figures_agree,
    measure_deltas,
    within_tolerance,
)
from arris_gym.fidelity._oracle import OracleReport, OracleStatus
from arris_gym.sandbox import ArrisRefusal, ExecResult, Status

_CONFIG = ConfigDict(frozen=True, extra="forbid")
# The oracle statuses that carry measures (`OracleReport` enforces it).
_MEASURED = (OracleStatus.OK, OracleStatus.INVALID)
# A doc anchor: a Markdown file under the repository, then its heading's slug.
_ANCHOR = re.compile(r"(?:[\w.-]+/)*[\w.-]+\.md#[a-z0-9-]+")


class DisagreementClass(enum.Enum):
    """Why arris and the oracle differ on a program: exactly one per
    disagreement (SEED.md §5, ADR-0006)."""

    CQ_BUG = "cq_bug"
    ARRIS_REFUSAL = "arris_refusal"
    ARRIS_BUG = "arris_bug"
    OCCT_WRONG = "occt_wrong"
    BY_DESIGN = "by_design"


class FidelityOutcome(enum.Enum):
    """What a fidelity row says: the two agree, they disagree with a class, or
    nothing yet classes the difference (a red cycle, gym.md)."""

    AGREE = "agree"
    DISAGREE = "disagree"
    UNCLASSIFIED = "unclassified"


class ClosedForm(BaseModel):
    """A part's measures worked out from how it is built, never from a kernel's
    output; `note` says how. `compare` holds both sides to it."""

    model_config = _CONFIG

    kind: Literal["closed_form"] = "closed_form"
    volume: FiniteFloat
    area: FiniteFloat
    centroid: tuple[FiniteFloat, FiniteFloat, FiniteFloat]
    bounds: tuple[
        tuple[FiniteFloat, FiniteFloat, FiniteFloat],
        tuple[FiniteFloat, FiniteFloat, FiniteFloat],
    ]
    note: str = pydantic.Field(min_length=1)


class SecondOracle(BaseModel):
    """Another kernel's record of the program, verbatim (arris ADR-0073)."""

    model_config = _CONFIG

    kind: Literal["second_oracle"] = "second_oracle"
    oracle: str = pydantic.Field(min_length=1)
    version: str = pydantic.Field(min_length=1)
    record: str = pydantic.Field(min_length=1)


class DocAnchor(BaseModel):
    """The doc or ADR heading that makes a difference intended: `path.md#slug`."""

    model_config = _CONFIG

    kind: Literal["doc"] = "doc"
    anchor: str = pydantic.Field(pattern=_ANCHOR.pattern)


class RegressionFixture(BaseModel):
    """The regression fixture directory that holds the case."""

    model_config = _CONFIG

    kind: Literal["fixture"] = "fixture"
    path: str = pydantic.Field(pattern=r"^tests/fixtures/regression/[\w.-]+/?$")


Evidence = Annotated[
    ClosedForm | SecondOracle | DocAnchor | RegressionFixture,
    pydantic.Field(discriminator="kind"),
]


class Verdict(BaseModel):
    """A disagreement class and the evidence for it (ADR-0006).

    Refuses on construction: `BY_DESIGN` without a `DocAnchor` or a
    `DocAnchor` for any other class; `OCCT_WRONG` resting on anything but a
    `ClosedForm` or a `SecondOracle`.

    >>> Verdict(disagreement=DisagreementClass.BY_DESIGN,
    ...     evidence=DocAnchor(anchor="docs/ARCHITECTURE.md#outcomes")).disagreement.value
    'by_design'
    """

    model_config = _CONFIG

    disagreement: DisagreementClass
    evidence: Evidence

    @model_validator(mode="after")
    def _evidence_fits_class(self) -> Self:
        is_doc = isinstance(self.evidence, DocAnchor)
        if is_doc != (self.disagreement is DisagreementClass.BY_DESIGN):
            raise ValueError("by_design rests on a doc anchor, and a doc anchor on by_design alone")
        if self.disagreement is DisagreementClass.OCCT_WRONG and not isinstance(
            self.evidence, ClosedForm | SecondOracle
        ):
            raise ValueError("occt_wrong rests on a closed form or a second oracle")
        return self


class FidelityRow(BaseModel):
    """One program's comparison of arris with the oracle.

    Guarantees, enforced on construction: `disagreement` is set exactly when
    `outcome` is `DISAGREE`; `refusal` exactly when the class is
    `ARRIS_REFUSAL`; `verdict`, when set, names the row's class; `deltas`
    exactly when both sides measured a shape (arris `ok`, the oracle `ok` or
    `invalid`; face counts carried, never judged).
    `refusal` is the kernel's, verbatim.
    """

    model_config = _CONFIG

    outcome: FidelityOutcome
    disagreement: DisagreementClass | None
    refusal: ArrisRefusal | None
    verdict: Verdict | None
    deltas: MeasureDeltas | None
    status: Status
    oracle_status: OracleStatus
    program_sha256: str

    @model_validator(mode="after")
    def _fields_agree_with_outcome(self) -> Self:
        if (self.disagreement is not None) != (self.outcome is FidelityOutcome.DISAGREE):
            raise ValueError("disagreement is set exactly when outcome is DISAGREE")
        if (self.refusal is not None) != (self.disagreement is DisagreementClass.ARRIS_REFUSAL):
            raise ValueError("refusal is set exactly when the class is ARRIS_REFUSAL")
        if self.verdict is not None and self.verdict.disagreement is not self.disagreement:
            raise ValueError("a verdict names the row's class")
        measured = self.status is Status.OK and self.oracle_status in _MEASURED
        if (self.deltas is not None) != measured:
            raise ValueError("deltas are set exactly when both sides measured a shape")
        return self

    @property
    def timed_out(self) -> bool:
        """Whether either side timed out: such a row is never classed by the rule."""
        return self.status is Status.TIMEOUT or self.oracle_status is OracleStatus.TIMEOUT


class _Rule(enum.Enum):
    """What the statuses alone say, before the measures and any verdict."""

    AGREE = "agree"
    UNCLASSIFIED = "unclassified"
    MEASURE = "measure"  # both ok: the agreement tolerance decides


_Ruling = _Rule | DisagreementClass


def _oracle_ok(status: Status) -> _Ruling:
    match status:
        case Status.OK:
            return _Rule.MEASURE
        case Status.SYNTAX | Status.TIMEOUT:
            return _Rule.UNCLASSIFIED
        case Status.RUNTIME | Status.UNSUPPORTED_API:
            return DisagreementClass.CQ_BUG
        case Status.ARRIS_REFUSAL:
            return DisagreementClass.ARRIS_REFUSAL
        case Status.CHECKER_FAIL | Status.CRASH:
            return DisagreementClass.ARRIS_BUG
        case _ as unreachable:
            assert_never(unreachable)


def _oracle_failed(status: Status) -> _Ruling:
    match status:
        case Status.OK | Status.TIMEOUT:
            return _Rule.UNCLASSIFIED
        case Status.SYNTAX | Status.RUNTIME | Status.UNSUPPORTED_API | Status.ARRIS_REFUSAL:
            return _Rule.AGREE
        case Status.CHECKER_FAIL | Status.CRASH:
            return DisagreementClass.ARRIS_BUG
        case _ as unreachable:
            assert_never(unreachable)


def _oracle_broke(status: Status, same: Status) -> _Ruling:
    """The oracle crashed or built an invalid shape; `same` is arris's like failure."""
    match status:
        case Status.CHECKER_FAIL | Status.CRASH:
            return _Rule.AGREE if status is same else DisagreementClass.ARRIS_BUG
        case (
            Status.OK
            | Status.SYNTAX
            | Status.RUNTIME
            | Status.UNSUPPORTED_API
            | Status.ARRIS_REFUSAL
            | Status.TIMEOUT
        ):
            return _Rule.UNCLASSIFIED
        case _ as unreachable:
            assert_never(unreachable)


def _rule(status: Status, oracle: OracleStatus) -> _Ruling:
    match oracle:
        case OracleStatus.TIMEOUT:
            return _Rule.UNCLASSIFIED
        case OracleStatus.OK:
            return _oracle_ok(status)
        case OracleStatus.SYNTAX | OracleStatus.RUNTIME | OracleStatus.NO_RESULT:
            return _oracle_failed(status)
        case OracleStatus.INVALID:
            return _oracle_broke(status, Status.CHECKER_FAIL)
        case OracleStatus.CRASH:
            return _oracle_broke(status, Status.CRASH)
        case _ as unreachable:
            assert_never(unreachable)


def _check_closed_form(
    form: ClosedForm, verdict: Verdict, result: ExecResult, report: OracleReport
) -> None:
    arris_agrees = None if result.measures is None else figures_agree(result.measures, form)
    oracle_agrees = None if report.measures is None else figures_agree(report.measures, form)
    if verdict.disagreement is DisagreementClass.OCCT_WRONG:
        exonerated, blamed = arris_agrees, oracle_agrees
    else:
        exonerated, blamed = oracle_agrees, arris_agrees
    if exonerated is None and blamed is None:
        raise ValueError("a closed form on a row where neither side measured a shape")
    if exonerated is False or blamed is True:
        raise ValueError("the verdict's closed form contradicts the measures")


def compare(
    result: ExecResult, report: OracleReport, verdict: Verdict | None = None
) -> FidelityRow:
    """The fidelity row of one program: its arris result against its oracle report.

    The rule (ADR-0006) classes what the two statuses settle; two `ok`
    sides agree when the oracle has one solid and every judged measure is
    inside the agreement tolerance (ADR-0005), and are `unclassified`
    otherwise, as are a timeout on either side and the oracle failing
    alone. A `verdict` classes such a row, or replaces the rule's class.

    Never raises without a verdict. Raises `ValueError`, a caller's
    mistake, for a verdict on a row that agrees, an `ARRIS_REFUSAL` verdict
    on a result with no refusal, or a closed form the measures contradict
    or that neither side measured.

    >>> from arris_gym.sandbox import Dialect, Versions
    >>> sha = "0" * 64
    >>> result = ExecResult(status=Status.SYNTAX, message="m", refusal=None, body=None,
    ...     measures=None, violations=(), program_sha256=sha, dialect=Dialect.ARRIS,
    ...     versions=Versions(arris="0", numpy="0", arris_gym="0"), seconds=0.0)
    >>> report = OracleReport(status=OracleStatus.TIMEOUT, message="m", measures=None,
    ...     step_sha256=None, program_sha256=sha, versions=None)
    >>> row = compare(result, report)
    >>> row.outcome.value, row.timed_out
    ('unclassified', True)
    """
    ruling = _rule(result.status, report.status)
    deltas = None
    if result.measures is not None and report.measures is not None:
        deltas = measure_deltas(result.measures, report.measures)
    if ruling is _Rule.MEASURE:
        one_solid = report.measures is not None and report.measures.solids == 1
        agrees = one_solid and deltas is not None and within_tolerance(deltas)
        ruling = _Rule.AGREE if agrees else _Rule.UNCLASSIFIED
    if ruling is _Rule.AGREE and verdict is not None:
        raise ValueError("a verdict on a row that agrees")
    disagreement = verdict.disagreement if verdict is not None else None
    if disagreement is None and isinstance(ruling, DisagreementClass):
        disagreement = ruling
    if disagreement is DisagreementClass.ARRIS_REFUSAL and result.refusal is None:
        raise ValueError("an arris_refusal verdict on a result with no refusal")
    if verdict is not None and isinstance(verdict.evidence, ClosedForm):
        _check_closed_form(verdict.evidence, verdict, result, report)
    if disagreement is not None:
        outcome = FidelityOutcome.DISAGREE
    elif ruling is _Rule.AGREE:
        outcome = FidelityOutcome.AGREE
    else:
        outcome = FidelityOutcome.UNCLASSIFIED
    return FidelityRow(
        outcome=outcome,
        disagreement=disagreement,
        refusal=result.refusal if disagreement is DisagreementClass.ARRIS_REFUSAL else None,
        verdict=verdict,
        deltas=deltas,
        status=result.status,
        oracle_status=report.status,
        program_sha256=result.program_sha256,
    )

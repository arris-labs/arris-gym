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
    VOLUME_REL,
    MeasureDeltas,
    figures_agree,
    measure_deltas,
    within_tolerance,
)
from arris_gym.fidelity._oracle import OracleReport, OracleStatus, OracleVersions
from arris_gym.sandbox import ArrisRefusal, ExecResult, Status, Versions

_CONFIG = ConfigDict(frozen=True, extra="forbid")
# The oracle statuses that carry measures (`OracleReport` enforces it).
_MEASURED = (OracleStatus.OK, OracleStatus.INVALID)
# The oracle statuses the caller decides: no worker answered, so no versions.
_UNANSWERED = (OracleStatus.TIMEOUT, OracleStatus.CRASH)
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
    """Reference measures derived from construction, with the method in `note`.

    ADR-0006 also admits independent boundary integration for the documented
    CAD-Recode mass-property discrepancies. `compare` checks both builds
    against the reference measures.
    """

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


class SignedSolids(BaseModel):
    """The signed volume of each solid of the oracle's shape, from a boundary flux independent
    of Open CASCADE's mass properties, with the method in `note` (ADR-0006, amended 2026-11-22).

    A solid whose signed volume is negative is turned inside out: no valid part has one. It is
    evidence for `occt_wrong` alone, on a row where arris built a shape and the oracle's checker
    rejected its own; `compare` holds it to both sides (`_check_signed_solids`).

    >>> SignedSolids(volumes=(10.0, -1.0), note="flux").kind
    'signed_solids'
    """

    model_config = _CONFIG

    kind: Literal["signed_solids"] = "signed_solids"
    volumes: tuple[FiniteFloat, ...] = pydantic.Field(min_length=1)
    note: str = pydantic.Field(min_length=1)


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
    ClosedForm | SecondOracle | SignedSolids | DocAnchor | RegressionFixture,
    pydantic.Field(discriminator="kind"),
]


class Verdict(BaseModel):
    """A disagreement class and the evidence for it (ADR-0006).

    Refuses on construction: `BY_DESIGN` without a `DocAnchor` or a
    `DocAnchor` for any other class; `OCCT_WRONG` resting on anything but a
    `ClosedForm`, a `SecondOracle` or `SignedSolids`; `SignedSolids` for any
    class but `OCCT_WRONG`.

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
        is_occt = self.disagreement is DisagreementClass.OCCT_WRONG
        if is_occt and not isinstance(self.evidence, ClosedForm | SecondOracle | SignedSolids):
            raise ValueError("occt_wrong rests on a closed form, a second oracle or signed solids")
        if isinstance(self.evidence, SignedSolids) and not is_occt:
            raise ValueError("signed solids are evidence for occt_wrong alone")
        return self


class FidelityRow(BaseModel):
    """One program's comparison of arris with the oracle.

    Guarantees, enforced on construction: `disagreement` is set exactly when
    `outcome` is `DISAGREE`; `refusal` exactly when the class is
    `ARRIS_REFUSAL`; `verdict`, when set, names the row's class; `deltas`
    exactly when both sides measured a shape (arris `ok`, the oracle `ok` or
    `invalid`; face counts carried, never judged); `oracle_versions`
    exactly when the oracle's worker answered (not `timeout` or `crash`).
    `refusal` is the kernel's, verbatim. `versions` are the arris result's
    (arris, numpy, arris-gym) and `oracle_versions` the oracle report's, so
    every row says what it was produced under (gym.md).
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
    versions: Versions
    oracle_versions: OracleVersions | None

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
        if (self.oracle_versions is None) != (self.oracle_status in _UNANSWERED):
            raise ValueError("oracle_versions is set exactly when the oracle's worker answered")
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


def _oracle_broke(status: Status, same: Status, oracle: OracleStatus) -> _Ruling:
    """The oracle crashed or built an invalid shape; `same` is arris's like failure.

    An `unsupported_api` against an `invalid` shape is `cq_bug` (ADR-0006,
    amended 2026-11-21): it declares that `cq` does not run the form, so it
    makes no claim about the program, as against `ok`.
    """
    match status:
        case Status.CHECKER_FAIL | Status.CRASH:
            return _Rule.AGREE if status is same else DisagreementClass.ARRIS_BUG
        case Status.UNSUPPORTED_API if oracle is OracleStatus.INVALID:
            return DisagreementClass.CQ_BUG
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
            return _oracle_broke(status, Status.CHECKER_FAIL, oracle)
        case OracleStatus.CRASH:
            return _oracle_broke(status, Status.CRASH, oracle)
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


def _check_signed_solids(form: SignedSolids, result: ExecResult, report: OracleReport) -> None:
    """Hold signed solids to both sides (ADR-0006, amended 2026-11-22).

    The row is arris `ok` against an oracle `invalid`; the volumes are one per solid of the
    oracle's shape, one at least negative; their sum is the oracle's signed volume and
    arris's, each inside `VOLUME_REL`; and arris has a shell for each positive solid.
    """
    if result.status is not Status.OK or report.status is not OracleStatus.INVALID:
        raise ValueError("signed solids on a row that is not arris ok against an invalid oracle")
    assert result.measures is not None  # both statuses carry measures
    assert report.measures is not None
    volumes = form.volumes
    if len(volumes) != report.measures.solids:
        raise ValueError("signed solids that are not one per solid of the oracle's shape")
    if not any(v < 0.0 for v in volumes):
        raise ValueError("signed solids with no solid turned inside out")
    total = 0.0
    for v in volumes:  # a fixed summation order: the sum reaches a verdict
        total += v
    for measured in (report.measures.volume, result.measures.volume):
        scale = max(abs(total), abs(measured))
        if scale and abs(total - measured) > VOLUME_REL * scale:
            raise ValueError("signed solids whose sum is not the measured volume")
    if sum(1 for v in volumes if v > 0.0) != result.measures.shells:
        raise ValueError("signed solids whose positive solids are not arris's shells")


def _pieces_agree(result: ExecResult, report: OracleReport) -> bool:
    """Whether the oracle's solids are one, or as many as the result's shells.

    A compound's solids are its pieces, and a piece without a cavity is one
    shell of arris's body (ADR-0016). One solid with a cavity has more
    shells than solids, so a single solid is judged by its measures alone,
    as before; a compound whose pieces hold cavities is not judged to agree.
    """
    if result.measures is None or report.measures is None:
        return False
    return report.measures.solids in (1, result.measures.shells)


def compare(
    result: ExecResult, report: OracleReport, verdict: Verdict | None = None
) -> FidelityRow:
    """The fidelity row of one program: its arris result against its oracle report.

    The rule (ADR-0006) classes what the two statuses settle; two `ok`
    sides agree when the oracle has one solid, or a compound of as many
    solids as the result has shells (ADR-0016), and every judged measure is
    inside the agreement tolerance (ADR-0005), and are `unclassified`
    otherwise, as are a timeout on either side and the oracle failing
    alone. An `unsupported_api` against an oracle `invalid` shape is
    `cq_bug`, as against `ok`: the subset declared it does not run the form.
    A `verdict` classes such a row, or replaces the rule's class.

    Never raises without a verdict. Raises `ValueError`, a caller's
    mistake, for a verdict on a row that agrees, a verdict of any class but
    `ARRIS_BUG` on an arris `crash` or `checker_fail` the rule classes
    `ARRIS_BUG`, an `ARRIS_REFUSAL` verdict on a result with no refusal,
    a closed form the measures contradict or that neither side measured, or
    signed solids that do not hold for both sides (`_check_signed_solids`).

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
        agrees = deltas is not None and _pieces_agree(result, report) and within_tolerance(deltas)
        ruling = _Rule.AGREE if agrees else _Rule.UNCLASSIFIED
    if ruling is _Rule.AGREE and verdict is not None:
        raise ValueError("a verdict on a row that agrees")
    if (
        verdict is not None
        and ruling is DisagreementClass.ARRIS_BUG
        and result.status in (Status.CRASH, Status.CHECKER_FAIL)
        and verdict.disagreement is not DisagreementClass.ARRIS_BUG
    ):
        raise ValueError(f"an arris {result.status.value} is never an answer: it stays arris_bug")
    disagreement = verdict.disagreement if verdict is not None else None
    if disagreement is None and isinstance(ruling, DisagreementClass):
        disagreement = ruling
    if disagreement is DisagreementClass.ARRIS_REFUSAL and result.refusal is None:
        raise ValueError("an arris_refusal verdict on a result with no refusal")
    if verdict is not None and isinstance(verdict.evidence, ClosedForm):
        _check_closed_form(verdict.evidence, verdict, result, report)
    if verdict is not None and isinstance(verdict.evidence, SignedSolids):
        _check_signed_solids(verdict.evidence, result, report)
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
        versions=result.versions,
        oracle_versions=report.versions,
    )

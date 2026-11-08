"""The comparer (ADR-0006): planted fixtures per class, the rule, verdicts, never raising.

Each `tests/fixtures/fidelity/class-*/` holds an arris `program.py`, a planted
`oracle.json` (written by hand, not recorded: what the oracle would report),
a `verdict.json` where the rule needs one, and `expected.json`, the row the
rule gives (ADR-0006's table), never arris-gym's output.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import re
from typing import Any

import pydantic
import pytest
from hypothesis import given
from hypothesis import strategies as st

import arris_gym
from arris_gym.fidelity import (
    ClosedForm,
    DisagreementClass,
    DocAnchor,
    FidelityOutcome,
    FidelityRow,
    OracleMeasures,
    OracleReport,
    OracleStatus,
    OracleVersions,
    RegressionFixture,
    SecondOracle,
    Verdict,
    compare,
)
from arris_gym.sandbox import ArrisRefusal, BodyRef, Dialect, ExecResult, Measures, Status, Versions

REPO = pathlib.Path(__file__).resolve().parent.parent
ROOT = REPO / "tests" / "fixtures" / "fidelity"
DIRECTORIES = sorted(ROOT.glob("class-*"))


def load(d: pathlib.Path) -> tuple[OracleReport, Verdict | None, dict[str, Any]]:
    report = OracleReport.model_validate_json((d / "oracle.json").read_text())
    verdict_file = d / "verdict.json"
    verdict = (
        Verdict.model_validate_json(verdict_file.read_text()) if verdict_file.is_file() else None
    )
    expected: dict[str, Any] = json.loads((d / "expected.json").read_text())
    return report, verdict, expected


@pytest.mark.parametrize("d", DIRECTORIES, ids=lambda d: d.name)
def test_each_planted_fixture_comes_back_in_its_class(d: pathlib.Path) -> None:
    report, verdict, want = load(d)
    result = arris_gym.run((d / "program.py").read_text())
    row = compare(result, report, verdict)
    assert row.status.value == want["status"], result.message
    assert row.oracle_status.value == want["oracle_status"]
    assert row.outcome.value == want["outcome"]
    assert (row.disagreement and row.disagreement.value) == want["disagreement"]
    assert row.timed_out is want.get("timed_out", False)
    if "refusal_kind" in want:
        assert row.refusal is not None
        assert row.refusal == result.refusal  # the kernel's words, verbatim
        assert row.refusal.kind == want["refusal_kind"]
    else:
        assert row.refusal is None


def test_every_class_and_outcome_has_its_planted_fixture() -> None:
    wants = [load(d)[2] for d in DIRECTORIES]
    classes = {w["disagreement"] for w in wants if w["disagreement"] is not None}
    assert sorted(classes) == sorted(c.value for c in DisagreementClass)
    assert {"agree", "unclassified"} <= {w["outcome"] for w in wants}
    assert any(w.get("timed_out") for w in wants)
    gap = load(ROOT / "class-unclassified-gap")
    assert gap[1] is None
    assert gap[2]["outcome"] == "unclassified"


def test_a_by_design_anchor_names_a_heading_that_exists() -> None:
    for d in DIRECTORIES:
        verdict = load(d)[1]
        if verdict is None or not isinstance(verdict.evidence, DocAnchor):
            continue
        path, slug = verdict.evidence.anchor.split("#")
        headings = re.findall(r"^#+ (.+)$", (REPO / path).read_text(), re.MULTILINE)
        slugs = [re.sub(r"[^a-z0-9 -]", "", h.lower()).replace(" ", "-") for h in headings]
        assert slug in slugs, verdict.evidence.anchor


# --- The rule over every status pair (ADR-0006's table, spelled out). -----

SHA = hashlib.sha256(b"p").hexdigest()
VERSIONS = Versions(arris="0", numpy="0", arris_gym="0")
ORACLE_VERSIONS = OracleVersions(cadquery="2.3.0", ocp="7.9.3.0", python="3.12.3")
BOX = Measures(
    volume=24.0,
    area=52.0,
    centroid=(1.0, 1.5, 2.0),
    bounds=((0.0, 0.0, 0.0), (2.0, 3.0, 4.0)),
    faces=6,
    shells=1,
    genus=0,
    face_kinds=(("plane", 6),),
)
BOX_ORACLE = OracleMeasures(
    volume=24.0,
    area=52.0,
    centroid=(1.0, 1.5, 2.0),
    bounds=((0.0, 0.0, 0.0), (2.0, 3.0, 4.0)),
    faces=6,
    solids=1,
)
BOX_FORM = ClosedForm(
    volume=24.0,
    area=52.0,
    centroid=(1.0, 1.5, 2.0),
    bounds=((0.0, 0.0, 0.0), (2.0, 3.0, 4.0)),
    note="V = 2*3*4",
)
REFUSAL = ArrisRefusal(kind="OpDegenerateError", message="degenerate", entities=("+e4",))


def result(status: Status, measures: Measures = BOX) -> ExecResult:
    return ExecResult(
        status=status,
        message="m",
        refusal=REFUSAL if status is Status.ARRIS_REFUSAL else None,
        body=BodyRef.of(b"body") if status in (Status.OK, Status.CHECKER_FAIL) else None,
        measures=measures if status is Status.OK else None,
        violations=(),
        program_sha256=SHA,
        dialect=Dialect.ARRIS,
        versions=VERSIONS,
        seconds=0.0,
    )


def report(status: OracleStatus, measures: OracleMeasures = BOX_ORACLE) -> OracleReport:
    worker = status not in (OracleStatus.TIMEOUT, OracleStatus.CRASH)
    return OracleReport(
        status=status,
        message="m",
        measures=measures if status in (OracleStatus.OK, OracleStatus.INVALID) else None,
        step_sha256="5" * 64 if status is OracleStatus.OK else None,
        program_sha256=SHA,
        versions=ORACLE_VERSIONS if worker else None,
    )


A, U = "agree", "unclassified"
CQ, REF, BUG = "cq_bug", "arris_refusal", "arris_bug"
# Rows: arris status; columns: ok, syntax, runtime, no_result, invalid, timeout, crash.
RULE = {
    "ok": (A, U, U, U, U, U, U),
    "syntax": (U, A, A, A, U, U, U),
    "runtime": (CQ, A, A, A, U, U, U),
    "unsupported_api": (CQ, A, A, A, U, U, U),
    "arris_refusal": (REF, A, A, A, U, U, U),
    "checker_fail": (BUG, BUG, BUG, BUG, A, U, BUG),
    "timeout": (U, U, U, U, U, U, U),
    "crash": (BUG, BUG, BUG, BUG, BUG, U, A),
}
ORACLE_ORDER = ("ok", "syntax", "runtime", "no_result", "invalid", "timeout", "crash")


def test_the_table_covers_every_pair() -> None:
    assert sorted(RULE) == sorted(s.value for s in Status)
    assert sorted(ORACLE_ORDER) == sorted(s.value for s in OracleStatus)


@pytest.mark.parametrize("arris", list(Status), ids=lambda s: s.value)
@pytest.mark.parametrize("oracle", list(OracleStatus), ids=lambda s: s.value)
def test_the_rule_classes_each_status_pair_as_adr_0006_says(
    arris: Status, oracle: OracleStatus
) -> None:
    row = compare(result(arris), report(oracle))
    want = RULE[arris.value][ORACLE_ORDER.index(oracle.value)]
    if want in (A, U):
        assert row.outcome.value == want
        assert row.disagreement is None
    else:
        assert row.outcome is FidelityOutcome.DISAGREE
        assert row.disagreement is DisagreementClass(want)
    assert row.timed_out is (arris is Status.TIMEOUT or oracle is OracleStatus.TIMEOUT)
    assert (row.deltas is not None) is (
        arris is Status.OK and oracle in (OracleStatus.OK, OracleStatus.INVALID)
    )
    assert row.program_sha256 == SHA


def test_a_measure_gap_and_a_second_solid_are_unclassified_and_the_faces_not_judged() -> None:
    wide = BOX.model_copy(update={"volume": 24.0 * (1 + 1e-6)})
    assert compare(result(Status.OK, wide), report(OracleStatus.OK)).outcome.value == U
    two = BOX_ORACLE.model_copy(update={"solids": 2})
    assert compare(result(Status.OK), report(OracleStatus.OK, two)).outcome.value == U
    split = BOX.model_copy(update={"faces": 9})
    row = compare(result(Status.OK, split), report(OracleStatus.OK))
    assert row.outcome is FidelityOutcome.AGREE
    assert row.deltas is not None
    assert row.deltas.faces == 3


# --- Verdicts. -------------------------------------------------------------

WRONG_ORACLE = BOX_ORACLE.model_copy(update={"volume": 25.0})
FIXTURE = RegressionFixture(path="tests/fixtures/regression/fork-bomb-status")


def test_a_verdict_classes_a_gap_and_keeps_its_evidence() -> None:
    verdict = Verdict(disagreement=DisagreementClass.OCCT_WRONG, evidence=BOX_FORM)
    row = compare(result(Status.OK), report(OracleStatus.OK, WRONG_ORACLE), verdict)
    assert row.outcome is FidelityOutcome.DISAGREE
    assert row.disagreement is DisagreementClass.OCCT_WRONG
    assert row.verdict == verdict


def test_a_verdict_replaces_the_rules_class() -> None:
    # arris refuses a part Open CASCADE builds wrong: the closed form shows it.
    verdict = Verdict(disagreement=DisagreementClass.OCCT_WRONG, evidence=BOX_FORM)
    row = compare(result(Status.ARRIS_REFUSAL), report(OracleStatus.OK, WRONG_ORACLE), verdict)
    assert row.disagreement is DisagreementClass.OCCT_WRONG
    assert row.refusal is None
    anchor = DocAnchor(anchor="docs/ARCHITECTURE.md#outcomes")
    by_design = Verdict(disagreement=DisagreementClass.BY_DESIGN, evidence=anchor)
    row = compare(result(Status.RUNTIME), report(OracleStatus.OK), by_design)
    assert row.disagreement is DisagreementClass.BY_DESIGN


def test_a_verdict_classes_a_timeout_and_the_row_still_names_it() -> None:
    verdict = Verdict(disagreement=DisagreementClass.ARRIS_BUG, evidence=FIXTURE)
    row = compare(result(Status.TIMEOUT), report(OracleStatus.OK), verdict)
    assert row.disagreement is DisagreementClass.ARRIS_BUG
    assert row.timed_out


def test_a_verdict_on_an_agreement_is_refused() -> None:
    verdict = Verdict(disagreement=DisagreementClass.ARRIS_BUG, evidence=FIXTURE)
    with pytest.raises(ValueError, match="agrees"):
        compare(result(Status.OK), report(OracleStatus.OK), verdict)
    with pytest.raises(ValueError, match="agrees"):
        compare(result(Status.SYNTAX), report(OracleStatus.SYNTAX), verdict)


def test_an_arris_refusal_verdict_needs_a_refusal() -> None:
    verdict = Verdict(disagreement=DisagreementClass.ARRIS_REFUSAL, evidence=FIXTURE)
    with pytest.raises(ValueError, match="no refusal"):
        compare(result(Status.OK), report(OracleStatus.NO_RESULT), verdict)


def test_a_closed_form_the_measures_contradict_is_refused() -> None:
    # The oracle is right and arris matches it: occt_wrong cannot rest on this.
    occt = Verdict(disagreement=DisagreementClass.OCCT_WRONG, evidence=BOX_FORM)
    wide = BOX.model_copy(update={"volume": 25.0})
    with pytest.raises(ValueError, match="contradicts"):
        compare(result(Status.OK, wide), report(OracleStatus.OK), occt)
    # arris is blamed but matches the closed form.
    bug = Verdict(disagreement=DisagreementClass.ARRIS_BUG, evidence=BOX_FORM)
    with pytest.raises(ValueError, match="contradicts"):
        compare(result(Status.OK), report(OracleStatus.OK, WRONG_ORACLE), bug)
    # Neither side measured anything the closed form could test.
    with pytest.raises(ValueError, match="neither side"):
        compare(result(Status.CRASH), report(OracleStatus.TIMEOUT), bug)


def test_a_closed_form_that_holds_against_the_blamed_side_alone_is_accepted() -> None:
    bug = Verdict(disagreement=DisagreementClass.ARRIS_BUG, evidence=BOX_FORM)
    wide = BOX.model_copy(update={"volume": 25.0})
    row = compare(result(Status.OK, wide), report(OracleStatus.TIMEOUT), bug)
    assert row.disagreement is DisagreementClass.ARRIS_BUG


def test_a_verdicts_evidence_must_fit_its_class() -> None:
    anchor = DocAnchor(anchor="docs/ARCHITECTURE.md#outcomes")
    second = SecondOracle(oracle="Parasolid", version="36.1", record="volume 24.0")
    with pytest.raises(pydantic.ValidationError):
        Verdict(disagreement=DisagreementClass.BY_DESIGN, evidence=FIXTURE)
    with pytest.raises(pydantic.ValidationError):
        Verdict(disagreement=DisagreementClass.CQ_BUG, evidence=anchor)
    with pytest.raises(pydantic.ValidationError):
        Verdict(disagreement=DisagreementClass.OCCT_WRONG, evidence=FIXTURE)
    assert Verdict(disagreement=DisagreementClass.OCCT_WRONG, evidence=second)
    with pytest.raises(pydantic.ValidationError):
        RegressionFixture(path="tests/fixtures/fidelity/agree-box")
    with pytest.raises(pydantic.ValidationError):
        DocAnchor(anchor="docs/ARCHITECTURE.md")


def test_a_row_refuses_fields_its_outcome_contradicts() -> None:
    row = compare(result(Status.ARRIS_REFUSAL), report(OracleStatus.OK))
    fields = row.model_dump()
    with pytest.raises(pydantic.ValidationError):
        FidelityRow.model_validate(fields | {"refusal": None})
    with pytest.raises(pydantic.ValidationError):
        FidelityRow.model_validate(fields | {"outcome": "agree"})
    with pytest.raises(pydantic.ValidationError):
        FidelityRow.model_validate(fields | {"status": "ok"})


# --- compare never raises over drawn pairs. --------------------------------

floats = st.floats(allow_nan=True, allow_infinity=True)
finite = st.floats(allow_nan=False, allow_infinity=False)
point = st.tuples(floats, floats, floats)
finite_point = st.tuples(finite, finite, finite)
arris_measures = st.builds(
    Measures,
    volume=floats,
    area=floats,
    centroid=point,
    bounds=st.tuples(point, point),
    faces=st.integers(0, 100),
    shells=st.integers(0, 3),
    genus=st.integers(0, 3),
    face_kinds=st.just((("plane", 6),)),
)
oracle_measures = st.builds(
    OracleMeasures,
    volume=finite,
    area=finite,
    centroid=finite_point,
    bounds=st.tuples(finite_point, finite_point),
    faces=st.integers(0, 100),
    solids=st.integers(0, 3),
)
results = st.builds(result, st.sampled_from(list(Status)), arris_measures)
reports = st.builds(report, st.sampled_from(list(OracleStatus)), oracle_measures)
closed_forms = st.builds(
    ClosedForm,
    volume=finite,
    area=finite,
    centroid=finite_point,
    bounds=st.tuples(finite_point, finite_point),
    note=st.just("drawn"),
)
evidence = st.one_of(
    closed_forms,
    st.just(FIXTURE),
    st.just(SecondOracle(oracle="Parasolid", version="36.1", record="r")),
    st.just(DocAnchor(anchor="docs/ARCHITECTURE.md#outcomes")),
)


@given(results, reports)
def test_compare_never_raises_without_a_verdict(r: ExecResult, o: OracleReport) -> None:
    row = compare(r, o)
    assert row.status is r.status
    assert row.oracle_status is o.status


@given(results, reports, st.sampled_from(list(DisagreementClass)), evidence)
def test_compare_with_a_verdict_returns_or_refuses_it(
    r: ExecResult, o: OracleReport, cls: DisagreementClass, ev: Any
) -> None:
    try:
        verdict = Verdict(disagreement=cls, evidence=ev)
    except pydantic.ValidationError:
        return
    try:
        row = compare(r, o, verdict)
    except pydantic.ValidationError:
        raise  # a row compare built itself is refused: a bug, never a caller's mistake
    except ValueError:
        return
    assert row.disagreement is cls
    assert row.verdict == verdict

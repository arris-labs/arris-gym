"""Closed forms and pinned oracle evidence for ADR-0029's shell probes."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

import arris_gym as ag
import fixture_cases
from arris_gym.fidelity import (
    ClosedForm,
    DisagreementClass,
    FidelityOutcome,
    OracleMeasures,
    OracleReport,
    OracleStatus,
    Verdict,
    compare,
)
from arris_gym.fidelity._agreement import figures_agree
from oracle_run import run_many

ROOT = fixture_cases.ROOT / "shells"
CASES = fixture_cases.load("shells")
ORACLE_FAILURES = {
    "compound": (OracleStatus.RUNTIME, "BRep_API: command not done"),
    "compound-one": (OracleStatus.RUNTIME, "BRep_API: command not done"),
    "compound-sealed": (OracleStatus.RUNTIME, "BRep_API: command not done"),
    "sealed-again": (OracleStatus.RUNTIME, "BRep_API: command not done"),
    "zero": (OracleStatus.RUNTIME, "BRep_API: command not done"),
    "infinite": (OracleStatus.RUNTIME, "gce_MakePln::Value() - no result"),
    "nan": (OracleStatus.TIMEOUT, "the oracle worker ran past the 30.0 s deadline"),
    "missing": (
        OracleStatus.RUNTIME,
        "ValueError: Cannot find a solid on the stack or in the parent chain",
    ),
}
RIMS = tuple(case for case in CASES if case.slug.startswith("rim-"))


def _oracle(directory: Path) -> OracleReport:
    report = OracleReport.model_validate_json((directory / "oracle.json").read_text())
    assert (
        report.program_sha256 == hashlib.sha256((directory / "oracle.py").read_bytes()).hexdigest()
    )
    assert report.versions is None or report.versions.cadquery == "2.3.0"
    assert report.versions is None or report.versions.ocp == "7.9.3.0"
    return report


def _check_oracle_measures(report: OracleReport, expected: object) -> None:
    assert report.status is OracleStatus.OK
    got = report.measures
    assert got is not None
    want = OracleMeasures.model_validate(expected)
    assert (got.faces, got.solids) == (want.faces, want.solids)
    for measured, analytic in zip(
        (got.volume, got.area, *got.centroid, *got.bounds[0], *got.bounds[1]),
        (want.volume, want.area, *want.centroid, *want.bounds[0], *want.bounds[1]),
        strict=True,
    ):
        assert fixture_cases.close(measured, analytic)


def _oracle_fields(expected: object) -> dict[str, object]:
    assert isinstance(expected, dict)
    return {name: expected[name] for name in OracleMeasures.model_fields}


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.slug)
def test_shell_in_arris_dialect(case: fixture_cases.Case) -> None:
    result = fixture_cases.run(case)
    assert fixture_cases.check(result, case.expected) == []
    if result.measures is not None:
        want = _oracle_fields(case.expected["measures"])
        assert result.measures.solids == want["solids"]
        if case.slug not in ORACLE_FAILURES:
            report = _oracle(ROOT / case.slug)
            _check_oracle_measures(report, want)
            if case.slug.startswith("rim-"):
                reference = OracleMeasures.model_validate(want)
                verdict = Verdict(
                    disagreement=DisagreementClass.OCCT_WRONG,
                    evidence=ClosedForm(
                        **reference.model_dump(exclude={"faces", "solids"}),
                        note="Integral of the rectangular slices, tests/fixtures/shells/README.md.",
                    ),
                )
                assert compare(result, report, verdict).disagreement is DisagreementClass.OCCT_WRONG
            else:
                assert compare(result, report).outcome is FidelityOutcome.AGREE


@pytest.mark.parametrize("name", ORACLE_FAILURES)
def test_oracle_shell_failure(name: str) -> None:
    report = _oracle(ROOT / name)
    status, message = ORACLE_FAILURES[name]
    assert report.status is status
    assert report.message.endswith(message)


def test_oracle_excessive_thickness_returns_the_original_box() -> None:
    report = _oracle(ROOT / "too-thick")
    _check_oracle_measures(
        report,
        dict(
            volume=480,
            area=376,
            centroid=(0, 0, 0),
            bounds=((-5, -4, -3), (5, 4, 3)),
            faces=6,
            solids=1,
        ),
    )


@pytest.mark.parametrize("name", ["shell-outward-arc", "shell-inward-reentrant-arc"])
def test_default_arc_geometry_on_the_oracle(name: str) -> None:
    directory = fixture_cases.ROOT / "regression" / name
    expected = json.loads((directory / "expected.json").read_text())
    _check_oracle_measures(_oracle(directory), _oracle_fields(expected["measures"]))


def test_oracle_measures_the_chamfered_rim_by_construction(request: pytest.FixtureRequest) -> None:
    directory = fixture_cases.ROOT / "regression" / "oracle-shell-chamfered-rim-volume"
    report = _oracle(directory)
    assert report.status is OracleStatus.OK
    assert report.measures is not None
    expected = ClosedForm.model_validate_json((directory / "closed-form.json").read_text())
    request.node.add_marker(
        pytest.mark.xfail(
            reason="The oracle's shelled chamfer volume differs from the section integral.",
            raises=AssertionError,
            strict=True,
        )
    )
    assert figures_agree(report.measures, expected)


@pytest.mark.oracle
def test_oracle_step_encodes_the_constructed_tray_rims() -> None:
    programs = [(ROOT / case.slug / "oracle.py").read_text() for case in RIMS]
    for report, case in zip(run_many(programs, workers=3), RIMS, strict=True):
        assert report.status is OracleStatus.OK
        assert report.step is not None
        target = ag.read_target(report.step)
        assert target.status is ag.Status.OK
        assert target.measures is not None
        expected = OracleMeasures.model_validate(_oracle_fields(case.expected["measures"]))
        assert figures_agree(target.measures, expected)
        assert (target.measures.faces, target.measures.solids) == (expected.faces, expected.solids)

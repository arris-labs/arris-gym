"""Reduced failures found by the BenchCAD loft, taper and mirror replay."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

import arris_gym as ag
import cq_closed_forms as forms
import fixture_cases
from arris_gym.fidelity import ClosedForm, OracleMeasures, OracleReport, OracleStatus
from arris_gym.fidelity._agreement import figures_agree

_ROOT = fixture_cases.ROOT / "regression"
_INTEGRAL_CASES = [
    ("oracle-draft-knob-overlapping-flutes", "oracle"),
    ("oracle-filleted-beam-bore", "oracle"),
    ("oracle-filleted-gusset-bore", "oracle"),
]


def _record(directory: Path, filename: str = "oracle.py") -> tuple[str, OracleReport]:
    program = (directory / filename).read_text()
    report = OracleReport.model_validate_json((directory / "oracle.json").read_bytes())
    assert report.program_sha256 == hashlib.sha256(program.encode()).hexdigest()
    return program, report


@pytest.mark.parametrize(("slug", "side"), _INTEGRAL_CASES)
@pytest.mark.parametrize("check_gap", [False, True], ids=["control", "gap"])
def test_trimmed_body_matches_independent_measurements(
    slug: str, side: str, check_gap: bool, request: pytest.FixtureRequest
) -> None:
    """Hold each kernel to the same integrated boundary measurements."""
    directory = _ROOT / slug
    program, oracle = _record(directory)
    candidate = ag.run(program, dialect="cq", timeout=fixture_cases.FIXTURE_DEADLINE)
    assert candidate.status is ag.Status.OK
    assert candidate.measures is not None
    assert oracle.status is OracleStatus.OK
    assert oracle.measures is not None
    assert candidate.measures.solids == oracle.measures.solids == 1
    expected = ClosedForm.model_validate_json((directory / "expected.json").read_bytes())
    if check_gap:
        request.node.add_marker(
            pytest.mark.xfail(
                reason="The recorded mass properties differ from the trim integral.",
                strict=True,
                raises=AssertionError,
            )
        )
    check_oracle = (side == "oracle") == check_gap
    assert figures_agree(oracle.measures if check_oracle else candidate.measures, expected)


def test_tangent_knob_cuts_receive_a_typed_refusal() -> None:
    """A flute tangent to the bore leaves a self-contact along their axes."""
    program, report = _record(_ROOT / "oracle-tangent-knob-cuts")
    result = ag.run(program, dialect="cq")
    assert result.program_sha256 == report.program_sha256
    assert result.status is ag.Status.ARRIS_REFUSAL
    assert result.refusal is not None
    assert result.refusal.kind == "OpDegenerateError"


@pytest.mark.parametrize("side", ["candidate", "oracle"])
def test_two_intersecting_flutes_match_the_construction(
    side: str, request: pytest.FixtureRequest
) -> None:
    """Hold both kernels to the area and moments of the same exposed section arcs."""
    directory = _ROOT / "cq-draft-knob-flute-measures"
    program, oracle = _record(directory)
    expected = ClosedForm.model_validate_json((directory / "expected.json").read_bytes())
    exact = ClosedForm.model_validate(forms._knob_closed_form(program))
    assert figures_agree(exact, expected)
    measured: ag.Measures | OracleMeasures | None
    if side == "candidate":
        candidate = ag.run(program, dialect="cq")
        assert candidate.status is ag.Status.OK
        measured = candidate.measures
    else:
        assert oracle.status is OracleStatus.OK
        measured = oracle.measures
    assert measured is not None
    assert measured.solids == 1
    request.node.add_marker(
        pytest.mark.xfail(
            reason="The reported volume differs from the section integral.",
            strict=True,
            raises=AssertionError,
        )
    )
    assert figures_agree(measured, exact)


@pytest.mark.parametrize("side", ["candidate", "oracle"])
def test_the_four_blade_union_matches_its_construction(
    side: str, request: pytest.FixtureRequest
) -> None:
    """Use the placed hub and prism union as the reference for both kernels."""
    directory = _ROOT / "cq-propeller-hub-blade-measures"
    program, oracle = _record(directory)
    form = forms.propeller_closed_form(program + "\n# Export\nshow_object(result)\n")
    expected = ClosedForm.model_validate_json((directory / "expected.json").read_bytes())
    assert figures_agree(ClosedForm.model_validate(form), expected)
    measured: ag.Measures | OracleMeasures | None
    if side == "candidate":
        candidate = ag.run(program, dialect="cq")
        assert candidate.status is ag.Status.OK
        measured = candidate.measures
    else:
        assert oracle.status is OracleStatus.OK
        measured = oracle.measures
    assert measured is not None
    assert measured.solids == 1
    if side == "oracle":
        request.node.add_marker(
            pytest.mark.xfail(
                reason="The oracle's volume differs from the construction integral.",
                strict=True,
                raises=AssertionError,
            )
        )
    assert figures_agree(measured, expected)


@pytest.mark.xfail(
    reason="The oracle accepts the solid with a line of self-contact between the two cuts.",
    strict=True,
    raises=AssertionError,
)
def test_the_oracle_rejects_the_tangent_knob_cuts() -> None:
    _, report = _record(_ROOT / "oracle-tangent-knob-cuts")
    assert report.status is OracleStatus.INVALID


@pytest.mark.xfail(
    reason="The kernel cannot find the fillet corner edge through the trim point.",
    strict=True,
    raises=AssertionError,
)
def test_a_wing_corner_fillet_does_not_raise_an_internal_kernel_error() -> None:
    """The reported oracle failure leaves the corner's geometry open."""
    program, _ = _record(_ROOT / "cq-wing-fillet-missing-trim-edge")
    result = ag.run(program, dialect="cq")
    assert result.status is ag.Status.OK or (
        result.status is ag.Status.ARRIS_REFUSAL
        and result.refusal is not None
        and result.refusal.kind != "OpInternalError"
    )

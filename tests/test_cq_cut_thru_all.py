"""Hold through cuts to ADR-0024, the pinned oracle and closed forms."""

from __future__ import annotations

import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import arris_gym as ag
import fixture_cases
from arris_gym.fidelity import FidelityOutcome, OracleReport, OracleStatus, compare, program_sha256
from arris_gym.fidelity._agreement import VOLUME_REL, figures_agree

_CASES = {case.slug: case for case in fixture_cases.load("cq") if "-cut-thru-all-" in case.slug}
_RECORDED = [
    slug for slug in _CASES if (fixture_cases.ROOT / "cq" / slug / "oracle.json").is_file()
]


@pytest.mark.parametrize("slug", _RECORDED)
def test_the_through_cut_agrees_with_the_oracle(slug: str) -> None:
    case = _CASES[slug]
    path = fixture_cases.ROOT / "cq" / slug / "oracle.json"
    report = OracleReport.model_validate_json(path.read_text(encoding="utf-8"))
    result = fixture_cases.run(case)
    assert result.program_sha256 == report.program_sha256
    assert compare(result, report).outcome is FidelityOutcome.AGREE


@pytest.mark.parametrize("name", ["side", "far"])
def test_through_cuts_the_oracle_misbuilds_match_the_closed_form(name: str) -> None:
    case = _CASES[f"ok-cut-thru-all-{name}"]
    result = fixture_cases.run(case)
    assert result.status is ag.Status.OK, result.message
    assert result.measures is not None
    assert figures_agree(result.measures, ag.Measures.model_validate(case.expected["measures"]))


def test_distant_oracle_record_belongs_to_the_closed_form_program() -> None:
    root = fixture_cases.ROOT / "regression" / "oracle-cut-thru-all-far"
    case = _CASES["ok-cut-thru-all-far"]
    assert (root / "oracle.py").read_text(encoding="utf-8") == case.program
    report = OracleReport.model_validate_json((root / "oracle.json").read_text(encoding="utf-8"))
    assert report.program_sha256 == program_sha256(case.program)
    assert report.status is OracleStatus.OK


@pytest.mark.xfail(
    reason="oracle-cut-thru-all-far: the oracle leaves the stock uncut",
    raises=AssertionError,
    strict=True,
)
def test_the_distant_oracle_bore_matches_the_closed_form() -> None:
    root = fixture_cases.ROOT / "regression" / "oracle-cut-thru-all-far"
    case = _CASES["ok-cut-thru-all-far"]
    report = OracleReport.model_validate_json((root / "oracle.json").read_text(encoding="utf-8"))
    assert report.measures is not None
    assert figures_agree(report.measures, ag.Measures.model_validate(case.expected["measures"]))


@settings(max_examples=40, deadline=None)
@given(
    width=st.integers(6, 20),
    height=st.integers(6, 20),
    thickness=st.integers(1, 8),
    u=st.floats(-0.5, 0.5),
    v=st.floats(-0.5, 0.5),
    radius=st.floats(0.25, 1.0),
    offset=st.sampled_from([-40, -2, 0, 2, 40]),
    face=st.sampled_from([">Z", "<Z"]),
)
def test_a_circular_window_removes_section_area_times_stock_thickness(
    width: int,
    height: int,
    thickness: int,
    u: float,
    v: float,
    radius: float,
    offset: int,
    face: str,
) -> None:
    """The radius fits even at the furthest centre, one quarter of either span."""
    program = (
        "import cadquery as cq\n"
        f'wp = cq.Workplane("XY").box({width}, {height}, {thickness})\n'
        f"wp = wp.faces({face!r}).workplane(offset={offset})\n"
        f"result = wp.moveTo({u * width / 2}, {v * height / 2}).circle({radius}).cutThruAll()\n"
        "show_object(result)\n"
    )
    result = ag.run(program, dialect="cq")
    assert result.status is ag.Status.OK, result.message
    assert result.measures is not None
    assert result.measures.genus == 1
    assert math.isclose(
        result.measures.volume,
        width * height * thickness - math.pi * radius**2 * thickness,
        rel_tol=VOLUME_REL,
    )

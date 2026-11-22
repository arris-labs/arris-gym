"""Check slot sweeps by closed form and bind their refusals to oracle records."""

from __future__ import annotations

import json
import math
from typing import TypedDict

import pytest
from hypothesis import example, given, settings
from hypothesis import strategies as st

import arris_gym as ag
import fixture_cases
from arris_gym.fidelity import OracleReport, OracleStatus, program_sha256


class _Context(TypedDict):
    name: str
    program: str
    message: str
    oracle: dict[str, object]


_CONTEXTS: list[_Context] = json.loads(
    (fixture_cases.ROOT / "profiles" / "slot-contexts.json").read_text()
)


@pytest.mark.parametrize("context", _CONTEXTS, ids=[c["name"] for c in _CONTEXTS])
def test_pending_slots_refuse_unmodelled_contexts(context: _Context) -> None:
    result = ag.run(context["program"], dialect="cq")
    oracle = OracleReport.model_validate(context["oracle"])
    assert oracle.program_sha256 == result.program_sha256
    assert oracle.status in (
        OracleStatus.OK,
        OracleStatus.INVALID,
        OracleStatus.RUNTIME,
        OracleStatus.CRASH,
    )
    assert result.status is ag.Status.UNSUPPORTED_API
    assert result.message == context["message"]


@pytest.mark.parametrize(
    ("slug", "oracle_status", "message"),
    [
        (
            "runtime-slot-equal",
            OracleStatus.RUNTIME,
            "OCP.OCP.StdFail.StdFail_NotDone: BRep_API: command not done",
        ),
        (
            "runtime-slot-equal-array",
            OracleStatus.RUNTIME,
            "OCP.OCP.StdFail.StdFail_NotDone: BRep_API: command not done",
        ),
        (
            "runtime-slot-zero-diameter",
            OracleStatus.RUNTIME,
            "OCP.OCP.StdFail.StdFail_NotDone: GC_MakeArcOfCircle::Value() - no result",
        ),
        (
            "runtime-slot-zero-both",
            OracleStatus.RUNTIME,
            "OCP.OCP.StdFail.StdFail_NotDone: BRep_API: command not done",
        ),
        (
            "refusal-slot-short",
            OracleStatus.INVALID,
            "BRepCheck_Analyzer: shape is not valid",
        ),
        (
            "refusal-slot-short-array",
            OracleStatus.INVALID,
            "BRepCheck_Analyzer: shape is not valid",
        ),
        (
            "refusal-slot-zero-length",
            OracleStatus.INVALID,
            "BRepCheck_Analyzer: shape is not valid",
        ),
    ],
)
def test_slot_dimension_limits_on_the_oracle(
    slug: str, oracle_status: OracleStatus, message: str
) -> None:
    path = fixture_cases.ROOT / "cq" / slug
    report = OracleReport.model_validate_json((path / "oracle.json").read_text())
    assert report.program_sha256 == program_sha256((path / "program.py").read_text())
    assert report.status is oracle_status
    assert report.message == message


@settings(max_examples=80, deadline=None)
@given(
    diameter=st.integers(1, 15),
    straight=st.integers(1, 20),
    height=st.integers(1, 12),
    reverse=st.booleans(),
    angle=st.floats(min_value=-720, max_value=720),
)
@example(diameter=3, straight=1, height=2, reverse=True, angle=270)
def test_a_slot_extrudes_its_section_area_times_absolute_distance(
    diameter: int, straight: int, height: int, reverse: bool, angle: float
) -> None:
    length = straight + diameter
    distance = -height if reverse else height
    program = (
        "import cadquery as cq\n"
        f'result = cq.Workplane("XY").slot2D({length}, {diameter}, {angle!r}).extrude({distance})\n'
        "show_object(result)\n"
    )
    result = ag.run(program, dialect="cq")
    assert result.status is ag.Status.OK, result.message
    assert result.measures is not None
    want = ((length - diameter) * diameter + math.pi * diameter**2 / 4) * abs(distance)
    assert fixture_cases.close(result.measures.volume, want)

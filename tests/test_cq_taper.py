"""Tapered extrusions through the program worker and pinned oracle (ADR-0027)."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import arris_gym as ag
import fixture_cases
from arris_gym.fidelity import FidelityOutcome, OracleReport, OracleStatus, compare
from arris_gym.fidelity._agreement import VOLUME_REL

ROOT = fixture_cases.ROOT / "tapers"
_REGRESSION = fixture_cases.ROOT / "regression"
_CQ = "import cadquery as cq\n"
_CONTEXTS = json.loads((ROOT / "contexts.json").read_text())
_FORM = "Workplane.extrude(taper=num)"
_INNER_WIRES = "ValueError: Inner wires not allowed with tapered extrusion"
_REFUSALS = {
    "angle-minus-right": f"{_FORM} outside the open angle range from -90 to 90 degrees",
    "angle-right": f"{_FORM} outside the open angle range from -90 to 90 degrees",
    "angle-beyond-right": f"{_FORM} outside the open angle range from -90 to 90 degrees",
    "carried-multiple": f"{_FORM} on multiple wires carried across plane changes",
    "carried-tilt": f"{_FORM} on a carried wire with a different normal",
    "finalized": f"{_FORM} on a sketch",
    "path": f"{_FORM} requires one circle or rectangle",
    "points-disc": f"{_FORM} requires one circle or rectangle",
    "points-overlap": f"{_FORM} requires one circle or rectangle",
    "points-rect": f"{_FORM} requires one circle or rectangle",
    "polygon": f"{_FORM} requires one circle or rectangle",
    "slot": f"{_FORM} requires one circle or rectangle",
    "rectangle-zero-width-in": f"{_FORM} on a rectangle with a zero dimension",
    "rectangle-zero-width-out": f"{_FORM} on a rectangle with a zero dimension",
}
_RUNTIME = {
    "consumed-profile": "ValueError: No pending wires present",
    "disc-zero": f"ValueError: {_FORM} with a zero slant length",
    "disc-zero-radius": f"ValueError: {_FORM} requires a positive circle radius",
    "disc-negative-radius": f"ValueError: {_FORM} requires a positive circle radius",
    "inner": _INNER_WIRES,
    "inner-negative": _INNER_WIRES,
    "no-wires": "ValueError: No pending wires present",
}
_OTHER_ORACLE_STATUSES = {
    "angle-right": OracleStatus.INVALID,
    "carried-multiple": OracleStatus.RUNTIME,
    "rectangle-zero-width-in": OracleStatus.INVALID,
}


def _compare(result: ag.ExecResult, oracle: OracleReport) -> None:
    assert oracle.program_sha256 == result.program_sha256
    assert oracle.versions is not None
    assert (oracle.versions.cadquery, oracle.versions.ocp) == ("2.3.0", "7.9.3.0")
    assert compare(result, oracle).outcome is FidelityOutcome.AGREE


def _oracle(path: Path) -> OracleReport:
    return OracleReport.model_validate_json(path.read_text())


@pytest.mark.parametrize("case", fixture_cases.load("tapers"), ids=lambda case: case.slug)
def test_draft_matches_its_construction_and_oracle(case: fixture_cases.Case) -> None:
    draft = fixture_cases.run(case)
    assert fixture_cases.check(draft, case.expected) == []
    _compare(draft, _oracle(ROOT / case.slug / "oracle.json"))


@pytest.mark.parametrize("name", _CONTEXTS)
def test_draft_contexts(name: str) -> None:
    record = _CONTEXTS[name]
    result = ag.run(record["program"], dialect="cq")
    oracle = OracleReport.model_validate(record["report"])
    assert result.program_sha256 == oracle.program_sha256
    if name in _REFUSALS:
        assert oracle.status is _OTHER_ORACLE_STATUSES.get(name, OracleStatus.OK)
        assert result.status is ag.Status.UNSUPPORTED_API
        assert result.message == _REFUSALS[name]
    elif name in _RUNTIME:
        assert result.status is ag.Status.RUNTIME
        assert result.message == _RUNTIME[name]
        assert oracle.status is OracleStatus.RUNTIME
        if name not in ("disc-zero", "disc-zero-radius", "disc-negative-radius"):
            assert result.message == oracle.message
    elif name == "rounded-all-edges":
        assert result.status is ag.Status.ARRIS_REFUSAL
        assert oracle.status is OracleStatus.RUNTIME
        _compare(result, oracle)
    else:
        assert result.status is ag.Status.OK, result.message
        _compare(result, oracle)


@pytest.mark.parametrize("name", ["inner-zero", "zero-carried", "zero-finalized", "zero-rect"])
def test_zero_taper_has_identical_body_and_measures_as_straight_extrusion(name: str) -> None:
    source = _CONTEXTS[name]["program"]
    plain = source.replace(", taper=0", "").replace(", taper=-0.0", "")
    assert plain != source
    with ag.Sandbox() as sandbox:
        plain_result, explicit = sandbox.run_many([plain, source], dialect="cq")
    assert plain_result.status is explicit.status is ag.Status.OK
    assert plain_result.body == explicit.body
    assert plain_result.measures == explicit.measures


def test_draft_leaves_the_earlier_workplane_available_for_an_independent_branch() -> None:
    source = (
        _CQ
        + """
pending = cq.Workplane("XY").circle(2).workplane(offset=7)
first = pending.extrude(2, taper=20)
result = pending.extrude(-2, taper=-20)
"""
    )
    second_alone = source.replace("first = pending.extrude(2, taper=20)\n", "")
    with ag.Sandbox() as sandbox:
        branch, alone = sandbox.run_many([source, second_alone], dialect="cq")
    assert branch.status is alone.status is ag.Status.OK
    assert branch.measures == alone.measures


@pytest.mark.parametrize(
    ("args", "form"),
    [
        ("1, taper=True", "num; taper=bool"),
        ("1, taper=None", "num; taper=none"),
        ("1, taper='5'", "num; taper=str"),
        ("1, False, 5", "num, bool, num"),
        ("1, both=False, taper=0", "num; both=bool, taper=num"),
        ("1, taper=5, both=True", "num; both=bool, taper=num"),
        ("1, taper=5, combine=False", "num; combine=bool, taper=num"),
    ],
)
def test_extrude_refuses_other_taper_forms_before_reading_the_stack(args: str, form: str) -> None:
    expected = f"Workplane.extrude({form})"
    assert not ag.cq.subset().admits(expected)
    result = ag.run(_CQ + f'result = cq.Workplane("XY").extrude({args})', dialect="cq")
    assert result.status is ag.Status.UNSUPPORTED_API
    assert result.message == expected


@pytest.mark.parametrize(
    ("args", "message"),
    [
        ('float("inf"), taper=20', "with a nonfinite slant length"),
        ('1, taper=float("nan")', "outside the open angle range from -90 to 90 degrees"),
    ],
)
def test_nonfinite_taper_inputs_are_refused(args: str, message: str) -> None:
    source = _CQ + f'result = cq.Workplane("XY").circle(2).extrude({args})'
    result = ag.run(source, dialect="cq")
    assert result.status is ag.Status.UNSUPPORTED_API
    assert result.message == f"{_FORM} {message}"


def test_collapsed_rectangle_can_leave_a_ridge_along_either_drawing_axis() -> None:
    source = _CQ + 'result = cq.Workplane("XY").rect(3, 4).extrude(4, taper=45)'
    result = ag.run(source, dialect="cq")
    assert result.status is ag.Status.OK, result.message
    m = result.measures
    assert m is not None
    assert m.solids == 1
    assert m.face_kinds == (("plane", 5),)
    assert fixture_cases.close(m.volume, 27 / 4)
    assert fixture_cases.close(m.area, 12 + 8 * math.hypot(1.5, 1.5))
    assert fixture_cases.close(m.centroid[2], 5 / 12)
    assert fixture_cases.close(m.bounds[0][0], -1.5)
    assert fixture_cases.close(m.bounds[0][1], -2)
    assert fixture_cases.close(m.bounds[1][2], 1.5)


@pytest.mark.xfail(
    reason="The oracle's collapsed rectangular draft passes its ridge by about 1.4e-6.",
    raises=AssertionError,
    strict=True,
)
@pytest.mark.parametrize("name", ["cq-draft-rectangle-ridge", "cq-draft-square-pyramid"])
def test_oracle_measures_the_collapsed_rectangular_draft(name: str) -> None:
    folder = _REGRESSION / name
    program = (folder / "program.py").read_text()
    oracle = _oracle(folder / "oracle.json")
    result = ag.run(program, dialect="cq")
    assert result.status is ag.Status.OK
    assert oracle.status is OracleStatus.OK
    _compare(result, oracle)


def test_the_knob_first_cut_has_the_integrated_volume() -> None:
    folder = _REGRESSION / "oracle-draft-knob-first-cut"
    result = ag.run((folder / "oracle.py").read_text(), dialect="cq")
    expected = json.loads((folder / "expected.json").read_text())["volume"]
    assert result.status is ag.Status.OK, result.message
    assert result.measures is not None
    assert result.measures.solids == 1
    assert fixture_cases.close(result.measures.volume, expected, VOLUME_REL)


@pytest.mark.xfail(
    reason="The trimmed draft's oracle volume exceeds the independently integrated volume.",
    raises=AssertionError,
    strict=True,
)
def test_the_oracle_knob_first_cut_has_the_integrated_volume() -> None:
    folder = _REGRESSION / "oracle-draft-knob-first-cut"
    result = ag.run((folder / "oracle.py").read_text(), dialect="cq")
    oracle = _oracle(folder / "oracle.json")
    expected = json.loads((folder / "expected.json").read_text())["volume"]
    assert oracle.program_sha256 == result.program_sha256
    assert oracle.measures is not None
    assert fixture_cases.close(oracle.measures.volume, expected, VOLUME_REL)


# For each named plane, the local x, y and signed normal. The fixtures add
# oblique rotations, cap collapse and continuations on the resulting stock.
_FRAME = {
    "XY": ((1, 0, 0), (0, 1, 0), (0, 0, 1)),
    "YZ": ((0, 1, 0), (0, 0, 1), (1, 0, 0)),
    "XZ": ((1, 0, 0), (0, 0, 1), (0, -1, 0)),
    "ZX": ((0, 0, 1), (1, 0, 0), (0, 1, 0)),
}
_ORIGINS = st.tuples(st.integers(-8, 8), st.integers(-8, 8), st.integers(-8, 8))
_CENTRES = st.tuples(st.integers(-5, 5), st.integers(-5, 5))
_HEIGHTS = st.integers(1, 8).flatmap(lambda h: st.sampled_from((h, -h)))


def _draft(
    plane: str,
    origin: tuple[int, int, int],
    centre: tuple[int, int],
    outline: str,
    height: int,
    inset: float,
) -> ag.Measures:
    # Choose the slant length and draft angle that produce the requested
    # axial height and cap inset. The expectations use the dimensions directly.
    distance = math.copysign(math.hypot(height, inset), height)
    angle = math.degrees(math.atan2(inset, abs(height)))
    program = (
        _CQ
        + f"result = cq.Workplane({plane!r}, origin={origin}).moveTo{centre}.{outline}"
        + f".extrude({distance!r}, taper={angle!r})\n"
    )
    result = ag.run(program, dialect="cq")
    assert result.status is ag.Status.OK, result.message
    assert result.measures is not None
    assert result.measures.solids == 1
    return result.measures


def _placement(
    measures: ag.Measures,
    plane: str,
    origin: tuple[int, int, int],
    centre: tuple[int, int],
    height: int,
    axial_centroid: float,
    half_width: float,
    half_depth: float,
) -> None:
    x, y, normal = _FRAME[plane]
    for i in range(3):
        at = origin[i] + centre[0] * x[i] + centre[1] * y[i]
        span = half_width * abs(x[i]) + half_depth * abs(y[i])
        assert fixture_cases.close(measures.centroid[i], at + axial_centroid * normal[i])
        assert fixture_cases.close(measures.bounds[0][i], at - span + min(0, height * normal[i]))
        assert fixture_cases.close(measures.bounds[1][i], at + span + max(0, height * normal[i]))


@settings(max_examples=32, deadline=None)
@given(
    st.sampled_from(tuple(_FRAME)),
    _ORIGINS,
    _CENTRES,
    _HEIGHTS,
    st.integers(1, 8),
    st.integers(1, 8),
)
def test_circular_drafts_match_the_conical_frustum_in_their_frame(
    plane: str,
    origin: tuple[int, int, int],
    centre: tuple[int, int],
    height: int,
    radius: int,
    cap: int,
) -> None:
    m = _draft(plane, origin, centre, f"circle({radius})", height, radius - cap)
    discs = radius**2 + radius * cap + cap**2
    slant = math.hypot(height, radius - cap)
    assert fixture_cases.close(m.volume, math.pi * abs(height) * discs / 3)
    assert fixture_cases.close(m.area, math.pi * (radius**2 + cap**2 + slant * (radius + cap)))
    kind = "cylinder" if radius == cap else "cone"
    assert m.face_kinds == ((kind, 1), ("plane", 2))
    centroid = height * (radius**2 + 2 * radius * cap + 3 * cap**2) / (4 * discs)
    radius = max(radius, cap)
    _placement(m, plane, origin, centre, height, centroid, radius, radius)


@settings(max_examples=32, deadline=None)
@given(
    st.sampled_from(tuple(_FRAME)),
    _ORIGINS,
    _CENTRES,
    _HEIGHTS,
    st.integers(4, 9),
    st.integers(4, 9),
    st.integers(-5, 5).filter(bool),
)
def test_rectangular_drafts_match_the_integral_of_the_offset_sections(
    plane: str,
    origin: tuple[int, int, int],
    centre: tuple[int, int],
    height: int,
    width: int,
    depth: int,
    quarter_inset: int,
) -> None:
    inset = quarter_inset / 4
    m = _draft(plane, origin, centre, f"rect({width}, {depth})", height, inset)
    # The section at fraction t of the height has area a + b*t + c*t².
    # Outward offsets add a strip along each side and four quarter discs.
    perimeter = 2 * (width + depth)
    a, b = width * depth, -perimeter * inset
    if inset > 0:
        c, perimeter_change = 4 * inset**2, -8 * inset
        assert m.face_kinds == (("plane", 6),)
    else:
        c, perimeter_change = math.pi * inset**2, -2 * math.pi * inset
        assert dict(m.face_kinds)["cone"] == 4
    average = a + b / 2 + c / 3
    assert fixture_cases.close(m.volume, abs(height) * average)
    slant = math.hypot(height, inset)
    surface = 2 * a + b + c + slant * (perimeter + perimeter_change / 2)
    assert fixture_cases.close(m.area, surface)
    centroid = height * (a / 2 + b / 3 + c / 4) / average
    spread = max(0.0, -inset)
    _placement(m, plane, origin, centre, height, centroid, width / 2 + spread, depth / 2 + spread)

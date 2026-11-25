"""CadQuery lofts through the program worker and ADR-0026's pinned evidence."""

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

ROOT = fixture_cases.ROOT / "lofts"
_CQ = "import cadquery as cq\n"
_FRUSTUM = 'cq.Workplane("XY").circle(2).workplane(offset=3).circle(1)'
_POLYGON_REFUSAL = (
    "Workplane.loft requires coaxial circles or straight-sided polygons with matching edge counts"
)
_AXIS_REFUSAL = "Workplane.loft on circles without a common directed axis"
_REFUSALS = {
    "nested": "Workplane.loft on nested wires",
    "shifted-discs": _AXIS_REFUSAL,
    "tilted-disc": _AXIS_REFUSAL,
    "unequal-edges": _POLYGON_REFUSAL,
    "curved-outline": _POLYGON_REFUSAL,
    "sketch": "Workplane.loft on a sketch",
    "over-curved-side-limit": "Workplane.loft on more than 48 nonplanar side faces",
}
_CONTEXTS = json.loads((ROOT / "contexts.json").read_text())
_RUNTIME_CONTEXTS = json.loads((ROOT / "runtime-contexts.json").read_text())


@pytest.mark.parametrize(
    "case",
    [c for c in fixture_cases.load("lofts") if c.slug != "disc-three-sections"],
    ids=lambda c: c.slug,
)
def test_loft_matches_its_construction_and_oracle(case: fixture_cases.Case) -> None:
    """Check both drawing directions and shifted starts through the CadQuery dialect."""
    for path in sorted((ROOT / case.slug).glob("oracle*.py")):
        result = ag.run(path.read_text(), dialect="cq", timeout=fixture_cases.FIXTURE_DEADLINE)
        oracle = OracleReport.model_validate_json(path.with_suffix(".json").read_text())
        assert oracle.program_sha256 == result.program_sha256
        assert compare(result, oracle).outcome is FidelityOutcome.AGREE
        assert fixture_cases.check(result, {**case.expected, "dialect": "cq"}) == []


@pytest.mark.parametrize("name", [n for n in _CONTEXTS if n != "consume"])
def test_loft_count_and_combining_with_stock_match_the_oracle(name: str) -> None:
    context = _CONTEXTS[name]
    result = ag.run(context["program"], dialect="cq")
    oracle = OracleReport.model_validate(context["report"])
    assert result.program_sha256 == oracle.program_sha256
    assert result.status.value == oracle.status.value
    assert result.message == oracle.message
    if result.status is ag.Status.OK:
        assert compare(result, oracle).outcome is FidelityOutcome.AGREE


def test_loft_consumes_pending_sections_on_its_result_and_keeps_the_source() -> None:
    # CadQuery consumes the shared context. ADR-0026 preserves the source
    # workplane so a frozen branch can loft it again with the same result.
    context = _CONTEXTS["consume"]
    source = context["program"]
    first = ag.run(source.replace("result = section.loft()", "result = lofted"), dialect="cq")
    branch = ag.run(source, dialect="cq")
    assert first.status is branch.status is ag.Status.OK
    assert first.measures == branch.measures
    with ag.Sandbox() as sandbox:
        assert sandbox.run(source, dialect="cq").body == branch.body
    assert branch.program_sha256 == context["report"]["program_sha256"]
    assert context["report"]["status"] == "runtime"
    assert context["report"]["message"] == "ValueError: No pending wires present"

    result = ag.run(
        source.replace("result = section.loft()", "result = lofted.loft()"), dialect="cq"
    )
    assert result.status is ag.Status.RUNTIME
    assert result.message == context["report"]["message"]


@pytest.mark.parametrize("name", _RUNTIME_CONTEXTS)
def test_loft_context(name: str) -> None:
    record = _RUNTIME_CONTEXTS[name]
    result = ag.run(record["program"], dialect="cq", timeout=fixture_cases.FIXTURE_DEADLINE)
    oracle = OracleReport.model_validate(record["report"])
    assert result.program_sha256 == oracle.program_sha256
    if name in _REFUSALS:
        assert oracle.status is (OracleStatus.RUNTIME if name == "sketch" else OracleStatus.OK)
        assert result.status is ag.Status.UNSUPPORTED_API
        assert result.message == _REFUSALS[name]
        return
    assert result.status is ag.Status.OK
    assert compare(result, oracle).outcome is FidelityOutcome.AGREE
    if name == "upper-cap":
        assert result.measures is not None
        assert result.measures.solids == 1
        assert fixture_cases.close(result.measures.volume, 7.5 * math.pi)
        assert fixture_cases.close(result.measures.bounds[1][2], 5)
    if name in ("curved-side-limit", "planar-over-side-limit"):
        assert result.measures is not None
        expected = (
            (("nurbs", 48), ("plane", 2)) if name == "curved-side-limit" else (("plane", 54),)
        )
        assert result.measures.face_kinds == expected


@pytest.mark.parametrize(
    ("args", "form"),
    [
        ("True", "bool"),
        ("combine='a'", "combine=str"),
        ("combine=1", "combine=num"),
        ("ruled=False", "ruled=bool"),
        ("clean=True", "clean=bool"),
    ],
)
def test_loft_refuses_other_forms_before_looking_for_sections(args: str, form: str) -> None:
    name = f"Workplane.loft({form})"
    assert not ag.cq.subset().admits(name)
    result = ag.run(_CQ + f"result = cq.Workplane('XY').loft({args})", dialect="cq")
    assert result.status is ag.Status.UNSUPPORTED_API
    assert result.message == name


@pytest.mark.parametrize(
    "directory",
    [
        ROOT / "disc-three-sections",
        fixture_cases.ROOT / "regression" / "arris-loft-three-rectangles",
        fixture_cases.ROOT / "regression" / "arris-loft-three-tooth-outlines",
    ],
)
def test_loft_refuses_three_sections_pending_interpolation_evidence(directory: Path) -> None:
    result = ag.run((directory / "oracle.py").read_text(), dialect="cq")
    assert result.status is ag.Status.UNSUPPORTED_API
    assert result.message == "Workplane.loft on more than two sections"


@settings(max_examples=25, deadline=None)
@given(
    st.integers(1, 9),
    st.integers(1, 9),
    st.integers(1, 9),
    st.integers(-8, 8),
    st.integers(-8, 8),
    st.integers(0, 3),
    st.booleans(),
)
def test_loft_pairs_shifted_reversed_vertices(
    width: int, depth: int, height: int, dx: int, dy: int, start: int, reversed_wire: bool
) -> None:
    """A translated half-scale cap has the same correspondence from any drawn start."""
    x, y = width / 2, depth / 2
    corners = [(-x, -y), (x, -y), (x, y), (-x, y)]
    if reversed_wire:
        corners.reverse()
    corners = corners[start:] + corners[:start]
    program = (
        _CQ
        + f"""
section = cq.Workplane('XY').rect({2 * width}, {2 * depth})
upper = section.transformed(offset=cq.Vector({dx}, {dy}, {height}))
result = upper.polyline({corners}).close().loft()
"""
    )
    result = ag.run(program, dialect="cq")
    assert result.status is ag.Status.OK, result.message
    m = result.measures
    assert m is not None
    assert m.solids == 1
    assert m.face_kinds == (("plane", 6),)
    assert fixture_cases.close(m.volume, 7 * width * depth * height / 3)
    for actual, displacement in zip(m.centroid, (dx, dy, height), strict=True):
        assert fixture_cases.close(actual, displacement * (11 / 28))


# Each named plane puts local +y and the normal along these world axes.
_FRAME = {
    "XY": ((0, 1, 0), (0, 0, 1)),
    "YZ": ((0, 0, 1), (1, 0, 0)),
    "XZ": ((0, 0, 1), (0, -1, 0)),
    "ZX": ((1, 0, 0), (0, 1, 0)),
}


@settings(max_examples=50, deadline=None)
@given(
    st.sampled_from(tuple(_FRAME)),
    st.tuples(st.integers(-10, 10), st.integers(-10, 10), st.integers(-10, 10)),
    st.integers(-70, 70),
    st.integers(-180, 180),
    st.integers(1, 8),
    st.integers(1, 8),
    st.integers(1, 8),
    st.booleans(),
)
def test_frustum_measures_and_placement_in_its_drawing_frame(
    plane: str,
    origin: tuple[int, int, int],
    tilt: int,
    roll: int,
    r0: int,
    r1: int,
    height: int,
    backwards: bool,
) -> None:
    """Check cones and cylinders along a signed axis with an independent closed form."""
    height = -height if backwards else height
    program = (
        _CQ
        + f"""
section = cq.Workplane({plane!r}, origin={origin})
section = section.transformed(rotate=cq.Vector({tilt}, 0, 0)).circle({r0})
upper = section.workplane(offset={height}).transformed(rotate=cq.Vector(0, 0, {roll}))
result = upper.circle({r1}).loft()
"""
    )
    result = ag.run(program, dialect="cq")
    assert result.status is ag.Status.OK, result.message
    m = result.measures
    assert m is not None
    assert m.solids == 1
    kind = "cylinder" if r0 == r1 else "cone"
    assert m.face_kinds == ((kind, 1), ("plane", 2))

    denominator = r0**2 + r0 * r1 + r1**2
    volume = math.pi * abs(height) * denominator / 3
    area = math.pi * (r0**2 + r1**2 + (r0 + r1) * math.hypot(height, r0 - r1))
    centroid_offset = height * (r0**2 + 2 * r0 * r1 + 3 * r1**2) / (4 * denominator)
    angle = math.radians(tilt)
    local_y, normal = _FRAME[plane]
    assert fixture_cases.close(m.volume, volume)
    assert fixture_cases.close(m.area, area)
    for i, at in enumerate(origin):
        axis = math.cos(angle) * normal[i] - math.sin(angle) * local_y[i]
        cap = at + height * axis
        radial = math.sqrt(1 - axis**2)
        assert fixture_cases.close(m.centroid[i], at + centroid_offset * axis)
        low = min(at - r0 * radial, cap - r1 * radial)
        high = max(at + r0 * radial, cap + r1 * radial)
        # Bounds enclose the solid. The axis-aligned cases also give tight
        # bounds. The tilted gap has a strict expected failure of its own.
        if tilt == 0:
            assert fixture_cases.close(m.bounds[0][i], low)
            assert fixture_cases.close(m.bounds[1][i], high)
        else:
            assert m.bounds[0][i] <= low or fixture_cases.close(m.bounds[0][i], low)
            assert m.bounds[1][i] >= high or fixture_cases.close(m.bounds[1][i], high)

"""Reflected paths through the program worker and the pinned oracle (ADR-0028)."""

from __future__ import annotations

import json
import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import arris_gym as ag
import fixture_cases
from arris_gym.fidelity import FidelityOutcome, OracleReport, OracleStatus, compare

_ROOT = fixture_cases.ROOT / "mirrors"
_CONTEXTS = json.loads((_ROOT / "contexts.json").read_text())
_CQ = "import cadquery as cq\n"
_FORM = "Workplane.mirrorY"
_REFUSALS = {
    "arc-gap": f"{_FORM} cannot snap a curved or sloped end to the y axis",
    "arc-loose": f"{_FORM} joins only one endpoint",
    "axis-only": f"{_FORM} requires an open outline leaving the y axis",
    "carried": f"{_FORM} with carried wires",
    "carried-only": f"{_FORM} with carried wires",
    "closed-drawn-path": f"{_FORM} requires two distinct endpoints on the y axis",
    "equal-heights": f"{_FORM} requires two distinct endpoints on the y axis",
    "one-above-join-limit": f"{_FORM} joins only one endpoint",
    "retraced-axis-tip": f"{_FORM} requires two distinct endpoints on the y axis",
    "sloped-gap": f"{_FORM} cannot snap a curved or sloped end to the y axis",
    **dict.fromkeys(
        (
            "circle",
            "closed-path",
            "edge-selection",
            "faces",
            "mirror-after-mirror",
            "points",
            "sketch",
            "solid",
        ),
        f"{_FORM} requires a single open path",
    ),
    "center-and-circle-after-mirror": "Workplane.extrude on multiple wires carried across center",
    "edges-after-mirror": "Workplane.edges on a stack that holds no solid",
    "loft-after-mirror": "Workplane.loft on a mirrored path",
    "taper-after-mirror": "Workplane.extrude(taper=num) requires one circle or rectangle",
    **{
        f"{context}-after-mirror": f"Workplane.{call} on a non-empty stack"
        for context, call in (
            ("circle", "circle"),
            ("polygon", "polygon"),
            ("rect", "rect"),
            ("sketch", "sketch"),
            ("slot", "slot2D"),
        )
    },
    **{
        f"{context}-after-mirror": f"Workplane.{call} on a pending wire"
        for context, call in (("move", "moveTo"), ("points", "pushPoints"))
    },
    **{
        f"{call}-after-mirror": f"Workplane.{call} on a pending wire"
        for call in (
            "box",
            "cboreHole",
            "chamfer",
            "cskHole",
            "cut",
            "cylinder",
            "fillet",
            "hole",
            "polarArray",
            "polyline",
            "rarray",
            "sphere",
            "union",
        )
    },
}
_RUNTIME = {
    "both-above-join-limit",
    "bottom-loft-after-mirror",
    "close-after-mirror",
    "consume-after-mirror",
    "empty",
    "faces-after-mirror",
    "line-after-mirror",
    "neither-joins",
    "point",
    "threePointArc-after-mirror",
}
_ORACLE_INVALID = {
    "arc-loose",
    "axis-only",
    "carried-only",
    "equal-heights",
    "faces",
    "mirror-after-mirror",
    "one-above-join-limit",
    "points-after-mirror",
    "polarArray-after-mirror",
    "polyline-after-mirror",
}
_ORACLE_RUNTIME = _RUNTIME | {
    "chamfer-after-mirror",
    "edge-selection",
    "edges-after-mirror",
    "fillet-after-mirror",
    "move-after-mirror",
}


def _check_record(result: ag.ExecResult, oracle: OracleReport) -> None:
    assert result.program_sha256 == oracle.program_sha256
    assert oracle.versions is not None
    assert (oracle.versions.cadquery, oracle.versions.ocp) == ("2.3.0", "7.9.3.0")


@pytest.mark.parametrize("case", fixture_cases.load("mirrors"), ids=lambda case: case.slug)
def test_mirrored_solid_matches_the_closed_form_and_oracle(case: fixture_cases.Case) -> None:
    result = fixture_cases.run(case)
    assert fixture_cases.check(result, case.expected) == []
    oracle = OracleReport.model_validate_json((_ROOT / case.slug / "oracle.json").read_text())
    _check_record(result, oracle)
    assert compare(result, oracle).outcome is FidelityOutcome.AGREE
    assert oracle.measures is not None
    assert result.measures is not None
    assert oracle.measures.faces == result.measures.faces


@pytest.mark.parametrize("name", _CONTEXTS)
def test_mirror_contexts(name: str) -> None:
    record = _CONTEXTS[name]
    result = ag.run(record["program"], dialect="cq")
    oracle = OracleReport.model_validate(record["oracle"])
    _check_record(result, oracle)
    if name in _ORACLE_INVALID:
        assert oracle.status is OracleStatus.INVALID
    elif name in _ORACLE_RUNTIME:
        assert oracle.status is OracleStatus.RUNTIME
    else:
        assert oracle.status is OracleStatus.OK

    if name in _REFUSALS:
        assert result.status is ag.Status.UNSUPPORTED_API
        assert result.message == _REFUSALS[name]
    elif name in _RUNTIME:
        assert result.status is ag.Status.RUNTIME
        assert result.message == oracle.message.rstrip()
        assert compare(result, oracle).outcome is FidelityOutcome.AGREE
    else:
        assert result.status is ag.Status.OK
        assert compare(result, oracle).outcome is FidelityOutcome.AGREE


@pytest.mark.parametrize(("args", "form"), [("1", "num"), ("axis='X'", "axis=str")])
def test_mirror_admits_only_the_zero_argument_form(args: str, form: str) -> None:
    assert ag.cq.subset().admits(f"{_FORM}()")
    assert not ag.cq.subset().admits(f"{_FORM}({form})")
    result = ag.run(_CQ + f"result = cq.Workplane('XY').mirrorY({args})\n", dialect="cq")
    assert result.status is ag.Status.UNSUPPORTED_API
    assert result.message == f"{_FORM}({form})"


def test_mirror_keeps_the_source_path_available_on_its_branch() -> None:
    program = (
        _CQ
        + """
half = cq.Workplane("XY").polyline([(0, 0), (2, 0), (2, 3), (0, 3)])
mirrored = half.mirrorY().extrude(4)
result = half.close().extrude(4)
"""
    )
    baseline = ag.run(program.replace("mirrored = half.mirrorY().extrude(4)\n", ""), dialect="cq")
    branch = ag.run(program, dialect="cq")
    assert branch.status is baseline.status is ag.Status.OK
    assert branch.measures == baseline.measures
    assert branch.measures is not None
    assert fixture_cases.close(branch.measures.volume, 24)


# Each local axis in world coordinates, in the order x, y and normal.
_FRAME = {
    "XY": ((1, 0, 0), (0, 1, 0), (0, 0, 1)),
    "YZ": ((0, 1, 0), (0, 0, 1), (1, 0, 0)),
    "XZ": ((1, 0, 0), (0, 0, 1), (0, -1, 0)),
    "ZX": ((0, 0, 1), (1, 0, 0), (0, 1, 0)),
}


@settings(max_examples=48, deadline=None)
@given(
    st.sampled_from(tuple(_FRAME)),
    st.tuples(st.integers(-9, 9), st.integers(-9, 9), st.integers(-9, 9)),
    st.integers(-8, 8),
    st.integers(1, 8),
    st.integers(1, 8),
    st.integers(1, 8),
    st.integers(1, 8),
    st.sampled_from((1, -1)),
    st.sampled_from((1, -1)),
    st.booleans(),
)
def test_reflected_trapezoids_match_closed_forms_in_their_drawing_frame(
    plane: str,
    origin: tuple[int, int, int],
    bottom: int,
    depth: int,
    lower: int,
    upper: int,
    height: int,
    drawn_side: int,
    direction: int,
    backwards: bool,
) -> None:
    cap = bottom + depth
    path = [(0, bottom), (drawn_side * lower, bottom), (drawn_side * upper, cap), (0, cap)]
    if backwards:
        path.reverse()
    signed_height = direction * height
    program = (
        _CQ + f"result = cq.Workplane({plane!r}, origin={origin}).polyline({path})"
        f".mirrorY().extrude({signed_height})\n"
    )
    result = ag.run(program, dialect="cq")
    assert result.status is ag.Status.OK, result.message
    m = result.measures
    assert m is not None
    assert m.solids == 1
    assert m.face_kinds == (("plane", 6),)

    section = depth * (lower + upper)
    perimeter = 2 * (lower + upper + math.hypot(depth, upper - lower))
    assert fixture_cases.close(m.volume, section * height)
    assert fixture_cases.close(m.area, 2 * section + perimeter * height)
    # Integrate the linearly varying section width from bottom to top.
    v = bottom + depth * (lower + 2 * upper) / (3 * (lower + upper))
    x, y, normal = _FRAME[plane]
    for i in range(3):
        assert fixture_cases.close(
            m.centroid[i], origin[i] + v * y[i] + signed_height / 2 * normal[i]
        )
        span = max(lower, upper) * abs(x[i])
        assert fixture_cases.close(
            m.bounds[0][i], origin[i] - span + bottom * y[i] + min(0, signed_height * normal[i])
        )
        assert fixture_cases.close(
            m.bounds[1][i], origin[i] + span + cap * y[i] + max(0, signed_height * normal[i])
        )

"""Check what a plane change carries and what the subset can consume."""

from __future__ import annotations

import json
import math
from typing import NotRequired, TypedDict

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import arris_gym as ag
import arris_gym.cq as cq
import fixture_cases
from arris_gym.fidelity import FidelityOutcome, OracleReport, compare
from arris_gym.fidelity._agreement import VOLUME_REL


class _Context(TypedDict):
    program: str
    oracle: dict[str, object]
    message: NotRequired[str]


_CONTEXTS: dict[str, _Context] = json.loads(
    (fixture_cases.ROOT / "lofts" / "plane-change-contexts.json").read_text()
)


@pytest.mark.parametrize("name", _CONTEXTS)
def test_operations_with_a_carried_section(name: str) -> None:
    """Hold each result to the recorded oracle or a specific subset refusal."""
    context = _CONTEXTS[name]
    candidate = ag.run(context["program"], dialect="cq")
    oracle = OracleReport.model_validate(context["oracle"])
    assert oracle.program_sha256 == candidate.program_sha256
    if "message" in context:
        assert candidate.status is ag.Status.UNSUPPORTED_API
        assert candidate.message == context["message"]
        return
    assert candidate.status.value == oracle.status.value
    assert candidate.message == oracle.message
    assert compare(candidate, oracle).outcome is FidelityOutcome.AGREE
    if name == "vertical-propeller":
        assert candidate.measures is not None
        assert oracle.measures is not None
        volume = math.pi * (18.46**2 * 15.56 + 16.614**2 * 5.6)
        assert math.isclose(candidate.measures.volume, volume, rel_tol=VOLUME_REL)
        assert math.isclose(oracle.measures.volume, volume, rel_tol=VOLUME_REL)


def test_propeller_cap_sections_keep_the_face_frame_and_stock() -> None:
    """Build the two pending sections of the BenchCAD propeller prefix in ADR-0026."""
    stock = cq.Workplane("XZ").cylinder(15.56, 18.46)
    face = stock.faces(">Y").workplane()
    lower = face.circle(16.614)
    offset = lower.workplane(offset=5.6)
    upper = offset.circle(1.5)
    (drawn,) = lower._visible_wires()
    (carried,) = upper._carried
    (visible,) = upper._visible_wires()

    assert carried.sketch is drawn.sketch
    assert carried.sketch.plane.origin == pytest.approx((0, 7.78, 0))
    assert visible.sketch.plane.origin == pytest.approx((0, 13.38, 0))
    assert visible.sketch.plane.x == (-1, 0, 0)
    assert visible.sketch.plane.y == (0, 0, 1)
    assert visible.sketch.plane.z == (0, 1, 0)
    assert upper._base_solid() is stock._solids()[0]


_PLANES = st.sampled_from(["XY", "YZ", "XZ", "ZX"])
_POSITION = st.tuples(*(st.integers(-12, 12) for _ in range(3)))
_ANGLE = st.integers(-170, 170)
_TURN = st.tuples(_ANGLE, _ANGLE, _ANGLE)


@settings(max_examples=50, deadline=None)
@given(_PLANES, _POSITION, _TURN, _TURN, _POSITION, st.integers(-8, 8))
def test_plane_changes_append_sections_without_changing_their_sources(
    plane: str,
    origin: tuple[int, int, int],
    first_turn: tuple[int, int, int],
    later_turn: tuple[int, int, int],
    offset: tuple[int, int, int],
    distance: int,
) -> None:
    """Carry in order through a tilted frame and retain independent branches."""
    stock = cq.Workplane(plane, origin=origin).box(1, 1, 1)
    drawing = stock.transformed(rotate=cq.Vector(*first_turn))
    first = drawing.moveTo(2, 1).circle(1)
    second_plane = first.workplane(offset=distance)
    second = second_plane.rect(1, 2)
    third_plane = second.transformed(rotate=cq.Vector(*later_turn), offset=cq.Vector(*offset))
    third = third_plane.polyline([(0, 0), (2, 0), (0, 1)]).close()
    moved = third.workplane(offset=-distance)
    sibling = first.transformed(offset=cq.Vector(1, 2, 3)).polygon(4, 2)

    assert second_plane._plane.origin == pytest.approx(drawing._plane.point(0, 0, distance))
    assert second_plane._plane.x == drawing._plane.x
    assert second_plane._plane.y == drawing._plane.y
    assert third_plane._plane.origin == pytest.approx(second_plane._plane.point(*offset))
    assert second_plane._stack == third_plane._stack == moved._stack == ()
    for new, source in ((second_plane, first), (third_plane, second), (moved, third)):
        assert new._parent is source
        assert new._base_solid() is stock._solids()[0]

    placed = tuple(node._visible_wires()[0].sketch for node in (first, second, third))
    assert all(wire.sketch is sketch for wire, sketch in zip(moved._carried, placed, strict=True))
    assert first._carried == ()
    assert tuple(wire.sketch for wire in second._carried) == placed[:1]
    assert tuple(wire.sketch for wire in third._carried) == placed[:2]
    assert sibling._carried == second._carried
    assert sibling._visible_wires()[0].sketch.plane == sibling._plane


_AXES = {
    "XY": ((1, 0, 0), (0, 1, 0), (0, 0, 1)),
    "YZ": ((0, 1, 0), (0, 0, 1), (1, 0, 0)),
    "XZ": ((1, 0, 0), (0, 0, 1), (0, -1, 0)),
    "ZX": ((0, 0, 1), (1, 0, 0), (0, 1, 0)),
}


@settings(max_examples=35, deadline=None)
@given(
    _PLANES,
    _POSITION,
    _POSITION,
    _ANGLE,
    st.integers(1, 6),
    st.integers(1, 6),
    st.integers(1, 8),
    st.booleans(),
)
def test_a_carried_prism_uses_its_drawing_origin(
    plane: str,
    origin: tuple[int, int, int],
    offset: tuple[int, int, int],
    turn: int,
    width: int,
    height: int,
    length: int,
    backwards: bool,
) -> None:
    """Sweep from the placed rectangle while moving the active origin and turning its axes."""
    distance = -length if backwards else length
    program = (
        "import cadquery as cq\n"
        f"section = cq.Workplane({plane!r}, origin={origin!r}).moveTo(2, -1)"
        f".rect({width}, {height})\n"
        f"moved = section.workplane(offset=3).transformed("
        f"rotate=cq.Vector(0, 0, {turn}), offset=cq.Vector{offset!r})\n"
        f"result = moved.extrude({distance})\n"
    )
    result = ag.run(program, dialect="cq")
    assert result.status is ag.Status.OK, result.message
    assert result.measures is not None
    x, y, z = _AXES[plane]
    center = [o + 2 * u - v + n * distance / 2 for o, u, v, n in zip(origin, x, y, z, strict=True)]
    half_spans = [
        (width * abs(u) + height * abs(v) + length * abs(n)) / 2
        for u, v, n in zip(x, y, z, strict=True)
    ]
    measures = result.measures
    assert fixture_cases.close(measures.volume, width * height * length)
    assert fixture_cases.close(measures.area, 2 * (width * height + (width + height) * length))
    assert measures.centroid == pytest.approx(center)
    assert measures.solids == 1
    for sign, cap in zip((-1, 1), measures.bounds, strict=True):
        assert all(
            fixture_cases.close(bound, c + sign * span)
            for bound, c, span in zip(cap, center, half_spans, strict=True)
        )


def test_consuming_a_workplane_section_clears_only_the_result() -> None:
    section = cq.Workplane("XY").circle(1).workplane(offset=3)
    a = section.extrude(2)
    b = section.transformed(offset=cq.Vector(0, 0, 4)).extrude(3)

    assert a._carried == b._carried == ()
    assert len(section._carried) == 1
    assert a._solids()[0].measure().volume == pytest.approx(2 * math.pi)
    assert b._solids()[0].measure().volume == pytest.approx(3 * math.pi)
    with pytest.raises(ValueError, match="No pending wires present"):
        a.extrude(1)

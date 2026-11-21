"""A finalized sketch extrudes its ordered section in the CadQuery dialect."""

from __future__ import annotations

import doctest
import json
from itertools import pairwise
from pathlib import Path

import pytest
from hypothesis import example, given, settings
from hypothesis import strategies as st

import arris_gym as ag
import fixture_cases
from arris_gym.cq import _sketch
from arris_gym.fidelity import FidelityOutcome, OracleReport, OracleStatus, compare, program_sha256

_Case = tuple[str, int, int, int, int]
_FIXTURES = fixture_cases.ROOT / "sketch"
_CASES = fixture_cases.load("sketch")
_TRACES = {
    row["program"]: OracleReport.model_validate(row["report"])
    for row in json.loads((_FIXTURES / "constructed.json").read_text(encoding="utf-8"))
}


def _oracle_of(path: Path, program: str) -> OracleReport | None:
    return (
        OracleReport.model_validate_json(path.read_bytes())
        if path.is_file()
        else _TRACES.get(program)
    )


@pytest.mark.parametrize("case", _CASES, ids=lambda case: case.slug)
def test_sketch_fixture(case: fixture_cases.Case) -> None:
    result = fixture_cases.run(case)
    assert fixture_cases.check(result, case.expected) == []
    oracle = _oracle_of(_FIXTURES / case.slug / "oracle.json", case.program)
    if oracle is None:
        assert case.slug == "unsupported-sketch-unknown-method"
        return
    assert oracle.program_sha256 == program_sha256(case.program)
    outcome = compare(result, oracle).outcome
    if case.slug.startswith("runtime-sketch-rect-zero-"):
        # ADR-0023 refuses the zero-width face at the drawing call.
        assert oracle.status is OracleStatus.INVALID
    elif (
        case.slug.startswith("unsupported-sketch-")
        and case.slug != "unsupported-sketch-free-constructor"
    ):
        assert oracle.status is OracleStatus.OK
        assert outcome is FidelityOutcome.DISAGREE
    else:
        assert outcome is FidelityOutcome.AGREE


def test_sketch_examples() -> None:
    assert doctest.testmod(_sketch).failed == 0


def test_sketch_forms_are_available_only_in_the_current_subset() -> None:
    supported = ag.cq.subset()
    original = fixture_cases.c1_subset()
    names = {
        "Workplane.sketch",
        "Sketch.push",
        "Sketch.reset",
        "Sketch.rect",
        "Sketch.circle",
        "Sketch.finalize",
    }
    assert {form.name for form in supported.forms} & names == names
    assert not {form.name for form in original.forms} & names


def test_finalize_keeps_the_original_workplane_and_the_sketch_identity() -> None:
    original = ag.cq.Workplane("YZ")
    sketch = original.sketch()
    assert sketch.push([(1, 2)]).rect(3, 4).reset().circle(1) is sketch
    finalized = sketch.finalize()
    assert finalized is not original
    assert sketch.finalize() is finalized
    assert original.sketch() is not sketch


def _section_area(rectangles: list[_Case]) -> int:
    """Area from the elementary cells between rectangle boundaries."""
    xs = sorted({x for _, left, right, _, _ in rectangles for x in (left, right)})
    ys = sorted({y for _, _, _, bottom, top in rectangles for y in (bottom, top)})
    area = 0
    for x0, x1 in pairwise(xs):
        for y0, y1 in pairwise(ys):
            inside = False
            for mode, left, right, bottom, top in rectangles:
                covered = left <= x0 < right and bottom <= y0 < top
                if mode == "a":
                    inside = inside or covered
                elif mode == "s":
                    inside = inside and not covered
                else:
                    inside = inside and covered
            if inside:
                area += (x1 - x0) * (y1 - y0)
    return area


@st.composite
def _rect_calls(draw: st.DrawFn) -> list[_Case]:
    # Distinct sides give proper overlaps or gaps. Coincident boundaries
    # and corner contact have their own constructions and regressions.
    coords = st.lists(st.integers(-12, 12), min_size=4, max_size=4, unique=True)
    xs = draw(coords)
    ys = draw(coords)
    left, right = sorted(xs[:2])
    bottom, top = sorted(ys[:2])
    base: _Case = ("a", left, right, bottom, top)
    left, right = sorted(xs[2:])
    bottom, top = sorted(ys[2:])
    return [base, (draw(st.sampled_from(("a", "s", "i"))), left, right, bottom, top)]


@settings(max_examples=100, deadline=None)
@given(calls=_rect_calls(), distance=st.sampled_from((-4, -1, 1, 3)))
@example(calls=[("a", -4, 4, -4, 4), ("s", -1, 1, -1, 1), ("i", -3, 3, -3, 3)], distance=2)
def test_rectilinear_sketch_volume(calls: list[_Case], distance: int) -> None:
    text = 'import cadquery as cq\ns = cq.Workplane("XY").sketch()\n'
    for mode, left, right, bottom, top in calls:
        x, y = (left + right) / 2, (bottom + top) / 2
        text += f"s.push([({x}, {y})]).rect({right - left}, {top - bottom}, mode={mode!r})\n"

    result = ag.run(text + f"result = s.finalize().extrude({distance})\n", dialect="cq")
    area = _section_area(calls)
    if area == 0:
        assert result.status is ag.Status.RUNTIME, result.message
        assert result.message == "ValueError: No pending wires present"
    else:
        assert result.status is ag.Status.OK, result.message
        assert result.measures is not None
        assert fixture_cases.close(result.measures.volume, area * abs(distance))

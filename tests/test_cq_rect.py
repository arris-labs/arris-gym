"""Check rectangle unions, kernel refusals and pending-wire contexts (ADR-0024)."""

from __future__ import annotations

import json
import math
from typing import TypedDict

import pytest
from hypothesis import example, given, settings
from hypothesis import strategies as st

import arris_gym as ag
import fixture_cases
from arris_gym.fidelity import FidelityOutcome, OracleReport, OracleStatus, compare, program_sha256
from arris_gym.fidelity._agreement import VOLUME_REL

_CORNER = {
    c.slug: c for c in fixture_cases.load("regression") if c.slug.startswith("rects-corner-")
}
_NESTS = [
    c
    for c in fixture_cases.load("cq")
    if c.slug.startswith("runtime-through-") and "rect" in c.slug
]


class _Context(TypedDict):
    name: str
    program: str
    message: str
    oracle: dict[str, object]


_CONTEXTS: list[_Context] = json.loads(
    (fixture_cases.ROOT / "profiles" / "rect-contexts.json").read_text()
)


@pytest.mark.parametrize("context", _CONTEXTS, ids=[c["name"] for c in _CONTEXTS])
def test_pending_rectangles_refuse_unmodelled_contexts(context: _Context) -> None:
    result = ag.run(context["program"], dialect="cq")
    report = OracleReport.model_validate(context["oracle"])
    assert report.program_sha256 == result.program_sha256
    assert report.status in (OracleStatus.OK, OracleStatus.INVALID, OracleStatus.RUNTIME)
    assert result.status is ag.Status.UNSUPPORTED_API
    assert result.message == context["message"]


@pytest.mark.parametrize("case", _NESTS, ids=lambda case: case.slug)
def test_through_cut_of_a_rectangular_nest_matches_the_oracle_error(
    case: fixture_cases.Case,
) -> None:
    result = fixture_cases.run(case)
    path = fixture_cases.ROOT / "cq" / case.slug / "oracle.json"
    oracle = OracleReport.model_validate_json(path.read_text())
    assert oracle.program_sha256 == result.program_sha256
    assert oracle.status is OracleStatus.RUNTIME
    assert oracle.message == "OCP.OCP.StdFail.StdFail_NotDone: BRep_API: command not done"
    assert compare(result, oracle).outcome is FidelityOutcome.AGREE


@pytest.mark.parametrize("slug", ["rects-corner-cutblind", "rects-corner-cutthruall"])
def test_corner_contact_cut_returns_the_typed_kernel_refusal(slug: str) -> None:
    result = fixture_cases.run(_CORNER[slug])
    assert result.status is ag.Status.ARRIS_REFUSAL
    assert result.refusal is not None
    assert result.refusal.kind == "OpDegenerateError"
    assert result.message == result.refusal.message


@pytest.mark.parametrize("slug", sorted(_CORNER))
def test_corner_contact_oracle_has_the_expected_volume(slug: str) -> None:
    case = _CORNER[slug]
    path = fixture_cases.ROOT / "regression" / slug / "oracle.json"
    oracle = OracleReport.model_validate_json(path.read_text())
    assert oracle.program_sha256 == program_sha256(case.program)
    assert oracle.status is (OracleStatus.INVALID if slug.endswith("blind") else OracleStatus.OK)
    assert oracle.measures is not None
    measures = case.expected["measures"]
    assert isinstance(measures, dict)
    assert math.isclose(oracle.measures.volume, float(measures["volume"]), rel_tol=VOLUME_REL)


@settings(max_examples=80, deadline=None)
@given(
    points=st.one_of(
        st.lists(
            st.tuples(st.integers(-7, 7), st.integers(-7, 7)), min_size=1, max_size=2, unique=True
        ),
        st.lists(st.integers(-7, 7), min_size=3, max_size=5, unique=True).map(
            lambda xs: [(x, 0) for x in xs]
        ),
    ),
    half_width=st.integers(1, 4),
    half_height=st.integers(1, 4),
    depth=st.integers(1, 5),
    negative=st.booleans(),
)
@example(points=[(0, 0), (2, 2)], half_width=1, half_height=1, depth=2, negative=True)
@example(points=[(0, 0), (1, 1)], half_width=1, half_height=1, depth=2, negative=False)
def test_rectangle_extrusions_have_the_integer_grid_union_volume(
    points: list[tuple[int, int]], half_width: int, half_height: int, depth: int, negative: bool
) -> None:
    """Count unit cells, including disjoint posts and unions that share an edge."""
    cells = {
        (x, y)
        for u, v in points
        for x in range(u - half_width, u + half_width)
        for y in range(v - half_height, v + half_height)
    }
    # At a checkerboard vertex two swept regions share only a vertical edge.
    corner = any(
        (x + dx, y + dy) in cells and (x + dx, y) not in cells and (x, y + dy) not in cells
        for x, y in cells
        for dx, dy in ((1, 1), (1, -1))
    )
    distance = -depth if negative else depth
    result = ag.run(
        "import cadquery as cq\n"
        f'result = cq.Workplane("XY").pushPoints({points!r})'
        f".rect({2 * half_width}, {2 * half_height}).extrude({distance})\n",
        dialect="cq",
    )
    assert result.status is ag.Status.OK, result.message
    assert result.measures is not None
    assert math.isclose(result.measures.volume, len(cells) * depth, rel_tol=VOLUME_REL)
    if corner:
        assert result.measures.shells == 2


@settings(max_examples=30, deadline=None)
@given(
    count=st.integers(3, 8),
    width=st.integers(1, 8),
    height=st.integers(1, 8),
    distance=st.integers(1, 5),
    negative=st.booleans(),
)
def test_disjoint_rectangles_sum_their_prism_volumes(
    count: int, width: int, height: int, distance: int, negative: bool
) -> None:
    points = [(index * (width + 1), 0) for index in range(count)]
    result = ag.run(
        "import cadquery as cq\n"
        f'result = cq.Workplane("XY").pushPoints({points!r}).rect({width}, {height})'
        f".extrude({-distance if negative else distance})\n",
        dialect="cq",
    )
    assert result.status is ag.Status.OK, result.message
    assert result.measures is not None
    assert result.measures.shells == count
    assert math.isclose(
        result.measures.volume, count * width * height * distance, rel_tol=VOLUME_REL
    )

"""`circle` on a `moveTo` point centres the circle there, in the plane's own axes."""

import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import arris_gym as ag
import arris_gym.cq as cq
import fixture_cases
from arris_gym.fidelity import FidelityOutcome, OracleReport, compare


@pytest.mark.parametrize("slug", ["ok-circle-at-point-prism", "ok-circle-at-point-half-torus"])
def test_circle_at_point_fixtures_agree_with_the_recorded_oracle(slug: str) -> None:
    case = next(c for c in fixture_cases.load("cq") if c.slug == slug)
    path = fixture_cases.ROOT / "cq" / slug / "oracle.json"
    report = OracleReport.model_validate_json(path.read_text())
    assert compare(fixture_cases.run(case), report).outcome is FidelityOutcome.AGREE


def _world(plane: str, u: float, v: float, w: float) -> list[float]:
    """Local (u, v, w) on a named plane at the origin, in world coordinates."""
    if plane == "XY":
        return [u, v, w]
    if plane == "YZ":
        return [w, u, v]
    assert plane == "XZ"
    return [u, -w, v]


@settings(max_examples=30, deadline=None)
@given(
    plane=st.sampled_from(["XY", "YZ", "XZ"]),
    point=st.tuples(st.integers(-6, 6), st.integers(-6, 6)),
    radius=st.integers(1, 4),
    distance=st.one_of(st.integers(-8, -1), st.integers(1, 8)),
)
def test_a_circle_on_a_moveto_point_is_centred_on_it(
    plane: str, point: tuple[int, int], radius: int, distance: int
) -> None:
    x, y = point
    program = (
        "import cadquery as cq\n"
        f"result = cq.Workplane('{plane}').moveTo({x}, {y}).circle({radius})"
        f".extrude({distance})\n"
    )
    result = ag.run(program, dialect="cq")
    near = _world(plane, x - radius, y - radius, min(0, distance))
    far = _world(plane, x + radius, y + radius, max(0, distance))
    expected: dict[str, object] = {
        "dialect": "cq",
        "status": "ok",
        "measures": {
            "volume": math.pi * radius**2 * abs(distance),
            "area": 2 * math.pi * radius**2 + 2 * math.pi * radius * abs(distance),
            "centroid": _world(plane, x, y, distance / 2),
            "bounds": [
                [min(a, b) for a, b in zip(near, far, strict=True)],
                [max(a, b) for a, b in zip(near, far, strict=True)],
            ],
            "faces": 3,
            "face_kinds": [["cylinder", 1], ["plane", 2]],
            "shells": 1,
            "genus": 0,
        },
    }
    assert fixture_cases.check(result, expected) == [], result.message


@pytest.mark.parametrize(
    "drawn",
    [
        cq.Workplane("XY").moveTo(1, 0).lineTo(2, 0),
        cq.Workplane("XY").polyline([(0, 0), (1, 0), (1, 1)]).close(),
        cq.Workplane("XY").moveTo(1, 0).circle(1),
    ],
)
def test_a_circle_on_any_other_non_empty_stack_is_unsupported(drawn: cq.Workplane) -> None:
    with pytest.raises(cq.UnsupportedApi, match=r"^Workplane\.circle on a non-empty stack$"):
        drawn.circle(1)

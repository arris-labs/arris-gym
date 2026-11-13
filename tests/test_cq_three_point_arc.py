"""`threePointArc` draws a circular arc from the pen through its first point to its second.

Read on the oracle (CadQuery 2.3.0, `ok-three-point-arc-*` beside their
`oracle.json`): `Workplane.threePointArc(point1, point2)` starts where
`lineTo` does (`_findFromPoint`: the end of the drawn path, a `moveTo` point,
or the plane's origin on an empty stack), passes through `point1` and ends
at `point2`, both in the workplane's coordinates; `close` adds a line back
to the start unless the arc already ends there.
"""

import math

import arris.build
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import arris_gym as ag
import arris_gym.cq as cq
import fixture_cases
from arris_gym.census import CorpusProgram, reach
from arris_gym.fidelity import FidelityOutcome, OracleReport, compare

PLANES = ["XY", "YZ", "XZ", "ZX"]
FIXTURES = [
    "ok-three-point-arc-half-disc-xy",
    "ok-three-point-arc-from-origin-xz",
    "ok-three-point-arc-stadium-yz",
    "ok-three-point-arc-lens-zx",
    "ok-three-point-arc-hemisphere-xy",
]


@pytest.mark.parametrize("slug", FIXTURES)
def test_three_point_arc_fixtures_agree_with_the_recorded_oracle(slug: str) -> None:
    case = next(c for c in fixture_cases.load("cq") if c.slug == slug)
    assert "threePointArc(" in case.program
    path = fixture_cases.ROOT / "cq" / slug / "oracle.json"
    report = OracleReport.model_validate_json(path.read_text())
    assert compare(fixture_cases.run(case), report).outcome is FidelityOutcome.AGREE


def _world(plane: str, u: float, v: float, w: float) -> list[float]:
    """Local (u, v, w) on a named plane at the world origin, in world coordinates."""
    if plane == "XY":
        return [u, v, w]
    if plane == "YZ":
        return [w, u, v]
    if plane == "XZ":
        return [u, -w, v]
    assert plane == "ZX"
    return [v, w, u]


@settings(max_examples=30, deadline=None)
@given(
    plane=st.sampled_from(PLANES),
    centre=st.tuples(st.integers(-6, 6), st.integers(-6, 6)),
    radius=st.integers(1, 6),
    first=st.integers(0, 359),
    sweep=st.integers(20, 340),
    height=st.integers(-5, 5).filter(lambda h: h != 0),
)
def test_a_circular_segment_has_its_closed_form(
    plane: str,
    centre: tuple[int, int],
    radius: int,
    first: int,
    sweep: int,
    height: int,
) -> None:
    # The arc runs counter-clockwise from `first` through the middle of the
    # sweep to `first + sweep` degrees; `close` adds the chord.
    cx, cy = centre

    def on_circle(degrees: float) -> tuple[float, float]:
        t = math.radians(degrees)
        return (cx + radius * math.cos(t), cy + radius * math.sin(t))

    start, via, end = on_circle(first), on_circle(first + sweep / 2), on_circle(first + sweep)
    program = (
        "import cadquery as cq\n"
        f"r = cq.Workplane('{plane}').moveTo{start}.threePointArc({via}, {end})"
        f".close().extrude({height})\n"
    )
    result = ag.run(program, dialect="cq")

    theta = math.radians(sweep)
    area = radius**2 / 2 * (theta - math.sin(theta))
    # The segment's centroid lies on the bisector, 4 r sin³(θ/2) / (3 (θ - sin θ))
    # from the centre.
    reach_out = 4 * radius * math.sin(theta / 2) ** 3 / (3 * (theta - math.sin(theta)))
    middle = math.radians(first + sweep / 2)
    centroid = (cx + reach_out * math.cos(middle), cy + reach_out * math.sin(middle))
    # The profile's extremes: the chord's ends and each axis-aligned point
    # the arc passes strictly inside its sweep.
    extremes = [start, end] + [
        on_circle(90 * k) for k in range(8) if first < 90 * k < first + sweep
    ]
    corners = [_world(plane, u, v, w) for u, v in extremes for w in (0, height)]
    expected: dict[str, object] = {
        "dialect": "cq",
        "status": "ok",
        "measures": {
            "volume": area * abs(height),
            "area": 2 * area + abs(height) * (radius * theta + 2 * radius * math.sin(theta / 2)),
            "centroid": _world(plane, *centroid, height / 2),
            "bounds": [
                [min(c) for c in zip(*corners, strict=True)],
                [max(c) for c in zip(*corners, strict=True)],
            ],
            "faces": 4,
            "face_kinds": [["cylinder", 1], ["plane", 3]],
            "shells": 1,
            "genus": 0,
        },
    }
    assert fixture_cases.check(result, expected) == [], result.message


def test_close_ends_an_arc_within_cadquerys_gap_on_the_start() -> None:
    # As for a line: an arc that ends within 1e-6 of the start ends there,
    # with no sliver segment after it.
    exact = cq.Workplane("XY").moveTo(-2, 0).lineTo(2, 0).threePointArc((0, 2), (-2, 0))
    near = cq.Workplane("XY").moveTo(-2, 0).lineTo(2, 0).threePointArc((0, 2), (-2, 5e-7))
    a, b = exact.close()._stack[0], near.close()._stack[0]
    assert isinstance(a, arris.build.Sketch)
    assert isinstance(b, arris.build.Sketch)
    assert a.outer == b.outer
    far = cq.Workplane("XY").moveTo(-2, 0).lineTo(2, 0).threePointArc((0, 2), (-2, 1e-3))
    c = far.close()._stack[0]
    assert isinstance(c, arris.build.Sketch)
    assert c.outer != a.outer


def test_reach_reads_the_declared_form_only() -> None:
    def written(call: str) -> CorpusProgram:
        text = f"import cadquery as cq\nresult = cq.Workplane('XY').{call}"
        return CorpusProgram(stem=call, family="f", text=text)

    assert cq.subset().admits("Workplane.threePointArc(tuple, tuple)")
    calls = [
        "threePointArc((1, 1), (2, 0))",
        "threePointArc([1, 1], (2, 0))",
        "threePointArc((1, 1), (2, 0), forConstruction=True)",
        "threePointArc((1, 1))",
    ]
    report = reach([written(call) for call in calls], cq.subset())
    assert report.stems == (calls[0],)


@pytest.mark.parametrize(
    ("call", "message"),
    [
        (
            "threePointArc((1, 1, 0), (2, 0))",
            "Workplane.threePointArc(tuple, tuple) with a point of 3 numbers",
        ),
        (
            "threePointArc((1, 1), (2, 'a'))",
            "Workplane.threePointArc(tuple, tuple) with a point of tuple of non-numbers",
        ),
        ("threePointArc([1, 1], (2, 0))", "Workplane.threePointArc(list, tuple)"),
        (
            "threePointArc((1, 1), (2, 0), forConstruction=True)",
            "Workplane.threePointArc(tuple, tuple; forConstruction=bool)",
        ),
    ],
)
def test_a_point_off_the_census_form_is_unsupported(call: str, message: str) -> None:
    refused = ag.run(f"import cadquery as cq\nresult = cq.Workplane('XY').{call}", dialect="cq")
    assert refused.status is ag.Status.UNSUPPORTED_API
    assert refused.message == message

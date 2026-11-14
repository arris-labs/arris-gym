"""`circle` on a `moveTo` point centres the circle there, in the plane's own axes."""

import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import arris_gym as ag
import arris_gym.cq as cq
import fixture_cases
from arris_gym.fidelity import FidelityOutcome, OracleReport, compare


@pytest.mark.parametrize(
    "slug",
    [
        "ok-circle-at-point-prism",
        "ok-circle-at-point-half-torus",
        "ok-circle-circle-ring",
        "ok-circle-circle-larger-second",
        "ok-circle-circle-at-point",
        "ok-circle-circle-revolve",
        "ok-circle-circle-corpus-impeller",
    ],
)
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
        cq.Workplane("XY").moveTo(1, 0).circle(3).circle(2),
    ],
)
def test_a_circle_on_any_other_non_empty_stack_is_unsupported(drawn: cq.Workplane) -> None:
    with pytest.raises(cq.UnsupportedApi, match=r"^Workplane\.circle on a non-empty stack$"):
        drawn.circle(1)


@settings(max_examples=30, deadline=None)
@given(
    plane=st.sampled_from(["XY", "YZ", "XZ"]),
    point=st.tuples(st.integers(-6, 6), st.integers(-6, 6)),
    radii=st.tuples(st.integers(1, 6), st.integers(1, 6)).filter(lambda r: r[0] != r[1]),
    distance=st.integers(1, 8),
)
def test_two_circles_make_a_ring_whatever_their_order(
    plane: str, point: tuple[int, int], radii: tuple[int, int], distance: int
) -> None:
    """The larger circle is the outer wall, drawn first or second, about the first one's centre."""
    x, y = point
    first, second = radii
    program = (
        "import cadquery as cq\n"
        f"result = cq.Workplane('{plane}').moveTo({x}, {y}).circle({first})"
        f".circle({second}).extrude({distance})\n"
    )
    result = ag.run(program, dialect="cq")
    assert result.status is ag.Status.OK, result.message
    assert result.measures is not None
    big, small = max(radii), min(radii)
    assert result.measures.volume == pytest.approx(math.pi * (big**2 - small**2) * distance)
    assert result.measures.centroid[2] == pytest.approx(_world(plane, x, y, distance / 2)[2])


@pytest.mark.parametrize("radius", [2, 0])
def test_a_second_circle_of_the_same_size_or_none_is_unsupported(radius: int) -> None:
    with pytest.raises(cq.UnsupportedApi, match="same size or no size"):
        cq.Workplane("XY").circle(2).circle(radius)


def impeller() -> dict[str, object]:
    """BenchCAD's `impeller_006376_s20260505` as written, from how it is built.

    A disc of radius 56.75 and height 3.02 about the origin on `XY`; a hub of
    radius 9.82 from z = 1.01 to 29.06; six blades, a convex quadrilateral turned
    -26.7 degrees about (23.768, 0) and then k 60 degrees about z, from z = 1.01
    to 18.16, sunk 0.5 into the disc; a ring of radii 56.75 and 41.32 from
    z = 17.252 to 19.522 (the second `circle`); a bore of 7.23 from the hub's top
    (`>Z`) through the whole part. Each blade lies 10.46 to 39.79 from the axis,
    clear of the hub and inside the ring's hole, within 35.7 degrees: the blades
    meet no hub, ring or other blade, so the ring is a second shell. V and A
    sum the pieces, less the disc's top under the hub and blades and the bore;
    the centroid is on the axis (six-fold symmetry).
    """
    disc_r, disc_h = 56.75, 3.02
    hub_r, hub_top = 9.82, 15.035 + 28.05 / 2
    blade = [(-14.448, -2.718), (-6.192, 2.492), (16.512, 1.903), (8.256, -3.397)]
    blade_top = 1.01 + 17.15
    ring_out, ring_in, ring_z, ring_h = 56.75, 41.32, 17.252, 2.27
    bore_r = 7.23 / 2
    disc_top, bottom = disc_h / 2, -disc_h / 2
    edges = list(zip(blade, blade[1:] + blade[:1], strict=True))
    footprint = abs(sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in edges)) / 2
    perimeter = sum(math.dist(a, b) for a, b in edges)
    bore = hub_top - bottom
    pieces = [
        (math.pi * disc_r**2 * disc_h, 0.0),
        (math.pi * hub_r**2 * (hub_top - disc_top), (hub_top + disc_top) / 2),
        (6 * footprint * (blade_top - disc_top), (blade_top + disc_top) / 2),
        (-math.pi * bore_r**2 * bore, (hub_top + bottom) / 2),
        (math.pi * (ring_out**2 - ring_in**2) * ring_h, ring_z + ring_h / 2),
    ]
    volume = sum(v for v, _ in pieces)
    area = (
        (2 * math.pi * disc_r**2 - math.pi * hub_r**2 - 6 * footprint - math.pi * bore_r**2)
        + 2 * math.pi * disc_r * disc_h
        + 2 * math.pi * hub_r * (hub_top - disc_top)
        + (math.pi * hub_r**2 - math.pi * bore_r**2)
        + 2 * math.pi * bore_r * bore
        + 6 * (perimeter * (blade_top - disc_top) + footprint)
        + 2 * math.pi * (ring_out**2 - ring_in**2)
        + 2 * math.pi * (ring_out + ring_in) * ring_h
    )
    return {
        "volume": volume,
        "area": area,
        "centroid": [0, 0, sum(v * z for v, z in pieces) / volume],
        "bounds": [[-disc_r, -disc_r, bottom], [disc_r, disc_r, hub_top]],
        # Disc: two planes and a cylinder; hub: its side, top and the bore;
        # six blades of four sides and a top; ring: two planes, two cylinders.
        "faces": 40,
        "face_kinds": [["cylinder", 5], ["plane", 35]],
        "shells": 2,
        "genus": 2,
    }


def test_the_corpus_impeller_is_its_construction() -> None:
    """The committed fixture holds `impeller`, and the blades meet nothing but the disc."""
    case = next(c for c in fixture_cases.load("cq") if c.slug == "ok-circle-circle-corpus-impeller")
    assert case.expected["measures"] == impeller()
    turn = math.radians(-26.7)
    corners = [
        (23.768 + x * math.cos(turn) - y * math.sin(turn), x * math.sin(turn) + y * math.cos(turn))
        for x, y in [(-14.448, -2.718), (-6.192, 2.492), (16.512, 1.903), (8.256, -3.397)]
    ]
    angles = [math.atan2(y, x) for x, y in corners]

    def nearest(a: tuple[float, float], b: tuple[float, float]) -> float:
        """The distance from the axis to the edge a-b."""
        dx, dy = b[0] - a[0], b[1] - a[1]
        t = min(1.0, max(0.0, -(a[0] * dx + a[1] * dy) / (dx * dx + dy * dy)))
        return math.hypot(a[0] + t * dx, a[1] + t * dy)

    edges = zip(corners, corners[1:] + corners[:1], strict=True)
    assert min(nearest(a, b) for a, b in edges) > 9.82
    assert max(math.hypot(x, y) for x, y in corners) < 41.32
    assert max(angles) - min(angles) < math.radians(60)

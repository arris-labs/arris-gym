"""`pushPoints(points)` and the holes bored at its points (ADR-0018 rules 1, 2 and 4).

CadQuery's `pushPoints` puts a stack of points on the plane, in its local
coordinates (a third number along the normal), and `hole` bores at every one in
a single cut, an empty stack at the plane's origin. The closed forms are worked
out by hand from that and from ADR-0017's plane axes; nothing is read from
`cq`. `ok-push-points-*` fixtures also have the oracle's recorded report.
"""

from __future__ import annotations

import json
import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import arris_gym as ag
import arris_gym.cq as cq
import fixture_cases
from arris_gym.fidelity import FidelityOutcome, OracleReport, compare
from test_cq_faces import AXES, PLANE_NORMAL, SELECTOR_SLUG, world_halves
from test_cq_hole import BASE, measures, wrap

Vec = tuple[float, float, float]
Point = tuple[float, float]
BOX = (4.0, 6.0, 8.0)
DIAMETER = 1.0
# Two points on any face of the box, clear of its edges and of each other
# (their distance is 2.9, over the diameter).
PAIR: tuple[Point, ...] = ((0.8, 1.2), (-0.8, -1.2))
SEVERAL: tuple[Point, ...] = ((-1.0, -2.0), (1.0, 0.0), (0.5, 2.2))


def through_points(axis: int, centres: tuple[Vec, ...]) -> dict[str, object]:
    """A 4 x 6 x 8 box centred on the origin, a hole of diameter 1 through it at each centre.

    Each cylinder (r = 1/2) runs the box's extent `length` along `axis`: it
    removes pi r^2 length, takes two discs from the faces and adds its wall,
    2 pi r length. The holes are apart and inside the face, so the part has
    6 planes and one cylinder per hole, genus n. Each hole's centroid is its
    centre with the axis coordinate 0, so the part's is
    -(pi r^2 length) sum(centres) / V.
    """
    r = DIAMETER / 2
    n = len(centres)
    length = BOX[axis]
    cut = math.pi * r * r * length
    volume = 192 - n * cut
    moment = [sum(c[k] for c in centres) for k in range(3)]
    return measures(
        volume,
        208 - n * 2 * math.pi * r * r + n * 2 * math.pi * r * length,
        (-cut * moment[0] / volume, -cut * moment[1] / volume, -cut * moment[2] / volume),
        ((-2, -3, -4), (2, 3, 4)),
        6 + n,
        [["cylinder", n], ["plane", 6]],
        genus=n,
    )


def world(selector: str, point: Point) -> Vec:
    """A point of the face `selector` selects, in the face's local x and y, as a centre.

    The bore runs through the centred box, so only the two coordinates of the
    face matter: the one along the normal is 0.
    """
    _, x, y = AXES[selector]
    return (
        point[0] * x[0] + point[1] * y[0],
        point[0] * x[1] + point[1] * y[1],
        point[0] * x[2] + point[1] * y[2],
    )


def on_face(selector: str, points: tuple[Point, ...]) -> tuple[int, tuple[Vec, ...]]:
    """The axis a face is on and the centres of `points` on it."""
    axis = "XYZ".index(selector[1])
    return axis, tuple(world(selector, p) for p in points)


def three_tuple_below() -> dict[str, object]:
    """`.faces(">Z").workplane().pushPoints([(1, 1, -1)]).hole(1)`: a hole from one below the face.

    The third number is the offset along the normal: the bore starts at z = 3
    and runs down the box's diagonal, so it leaves through the bottom, 7 long,
    and the part keeps the top metre. V = 192 - pi r^2 7. It takes the bottom
    disc, adds the wall 2 pi r 7 and the cap disc at z = 3: A = 208 + 2 pi r 7.
    The cut's centroid is (1, 1, -1/2).
    """
    r = DIAMETER / 2
    cut = math.pi * r * r * 7
    volume = 192 - cut
    return measures(
        volume,
        208 + 2 * math.pi * r * 7,
        (-cut / volume, -cut / volume, 0.5 * cut / volume),
        ((-2, -3, -4), (2, 3, 4)),
        8,
        [["cylinder", 1], ["plane", 7]],
    )


def three_tuple_above() -> dict[str, object]:
    """`.faces(">Z").workplane().pushPoints([(1, 1, 3)]).hole(1)`: a hole from three above the face.

    The bore starts at z = 7 and runs the box's diagonal D = sqrt(116) down, to
    z = 7 - D = -3.77: short of the bottom, so it is blind there, its
    cylinder 4 - (7 - D) = D - 3 long inside the part. V = 192 - pi r^2 (D - 3);
    it takes the top disc, adds the wall 2 pi r (D - 3) and the cap disc at
    its end: A = 208 + 2 pi r (D - 3). The cut's centroid is
    (1, 1, (11 - D) / 2).
    """
    r = DIAMETER / 2
    diagonal = math.sqrt(4**2 + 6**2 + 8**2)
    length = diagonal - 3
    cut = math.pi * r * r * length
    volume = 192 - cut
    return measures(
        volume,
        208 + 2 * math.pi * r * length,
        (-cut / volume, -cut / volume, -cut * (11 - diagonal) / 2 / volume),
        ((-2, -3, -4), (2, 3, 4)),
        8,
        [["cylinder", 1], ["plane", 7]],
    )


def off_the_part() -> dict[str, object]:
    """`.faces(">Z").workplane().pushPoints([(20, 0)]).hole(1)`: the cylinder misses the box."""
    return measures(192, 208, (0, 0, 0), ((-2, -3, -4), (2, 3, 4)), 6, [["plane", 6]])


def dog_bone() -> dict[str, object]:
    """BenchCAD's `dog_bone_000282_s20260505`: a stadium plate, two holes of 11.46.

    On `XZ` the profile is a 87 x 12.92 rectangle (x +-43.5, z +-6.46) with a
    major arc at each end, through (+-59.29, 0) from the corners. The arc's
    circle has its centre (c, 0) with (59.29 - c)^2 = (43.5 - c)^2 + 6.46^2 and
    radius R = 59.29 - c; its part beyond the chord x = 43.5, at distance
    d = c - 43.5 from the centre, is the whole disc less the segment
    R^2 acos(d / R) - d sqrt(R^2 - d^2). The prism runs 3.68 along -y, so the
    `>Y` face is y = 0 and the plane's x is world -x, its y world z: both holes
    (r = 5.73, at +-43.5) are inside the profile and bore its whole 3.68.
    V = (A - 2 pi r^2) h, area 2 (A - 2 pi r^2) + P h + 2 (2 pi r) h with
    perimeter P = 2 (87) + 2 R (2 pi - 2 acos(d / R)) taken on the two arcs.
    The part is symmetric about x = 0 and z = 0: centroid (0, -h / 2, 0).
    The arcs bulge past the corners: z reaches +-R.
    """
    corner, tip, half, h, r = 6.46, 59.29, 43.5, 3.68, 11.46 / 2
    c = (tip**2 - half**2 - corner**2) / (2 * (tip - half))
    radius = tip - c
    d = c - half
    angle = math.acos(d / radius)
    segment = radius**2 * angle - d * math.sqrt(radius**2 - d**2)
    area = 2 * half * 2 * corner + 2 * (math.pi * radius**2 - segment)
    perimeter = 2 * 2 * half + 2 * radius * (2 * math.pi - 2 * angle)
    volume = (area - 2 * math.pi * r * r) * h
    return measures(
        volume,
        2 * (area - 2 * math.pi * r * r) + (perimeter + 2 * 2 * math.pi * r) * h,
        (0, -h / 2, 0),
        ((-tip, -h, -radius), (tip, 0, radius)),
        8,
        [["cylinder", 4], ["plane", 4]],
        genus=2,
    )


DOG_BONE = """import cadquery as cq

result = (
    cq.Workplane("XZ")
    .moveTo(-43.5, 6.46)
    .lineTo(43.5, 6.46)
    .threePointArc((59.29, 0.0), (43.5, -6.46))
    .lineTo(-43.5, -6.46)
    .threePointArc((-59.29, 0.0), (-43.5, 6.46))
    .close()
    .extrude(3.68)
    .faces(">Y").workplane()
    .pushPoints([(-43.5, 0.0), (43.5, 0.0)])
    .hole(11.46)
)

# Export
show_object(result)
"""


def fixture_programs() -> dict[str, tuple[str, dict[str, object], str]]:
    """Every generated `ok-push-points-*` fixture: slug -> (program text, measures, note)."""
    found: dict[str, tuple[str, dict[str, object], str]] = {}
    top = f'{BASE}.faces(">Z").workplane()'

    def add(slug: str, chain: str, expected: dict[str, object], note: str) -> None:
        found[f"ok-push-points-{slug}"] = (wrap(chain), expected, note)

    through = through_points.__doc__ or ""
    add(
        "one-point",
        f"{top}.pushPoints([(1, 1)]).hole(1)",
        through_points(2, ((1.0, 1.0, 0.0),)),
        '`.faces(">Z").workplane().pushPoints([(1, 1)]).hole(1)`. ' + through,
    )
    add(
        "several",
        f"{top}.pushPoints({list(SEVERAL)}).hole(1)",
        through_points(2, tuple((x, y, 0.0) for x, y in SEVERAL)),
        "Three points on `>Z`. " + through,
    )
    add(
        "lists",
        f"{top}.pushPoints({[list(p) for p in SEVERAL]}).hole(1)",
        through_points(2, tuple((x, y, 0.0) for x, y in SEVERAL)),
        "The points as lists, as the corpus writes some: the same part as tuples. " + through,
    )
    add(
        "empty",
        f"{top}.pushPoints([]).hole(1)",
        through_points(2, ((0.0, 0.0, 0.0),)),
        "An empty list leaves an empty stack, which bores once at the plane's origin "
        "(CadQuery's `eachpoint`). " + through,
    )
    for selector, slug in SELECTOR_SLUG.items():
        axis, centres = on_face(selector, PAIR)
        add(
            f"box-{slug}",
            f'{BASE}.faces("{selector}").workplane().pushPoints({list(PAIR)}).hole(1)',
            through_points(axis, centres),
            f"Two points on `{selector}`, in that face's own x and y (ADR-0017). " + through,
        )
    add(
        "3-tuple-below",
        f"{top}.pushPoints([(1, 1, -1)]).hole(1)",
        three_tuple_below(),
        three_tuple_below.__doc__ or "",
    )
    add(
        "3-tuple-above",
        f"{top}.pushPoints([(1, 1, 3)]).hole(1)",
        three_tuple_above(),
        three_tuple_above.__doc__ or "",
    )
    add(
        "off-the-part",
        f"{top}.pushPoints([(20, 0)]).hole(1)",
        off_the_part(),
        off_the_part.__doc__ or "",
    )
    found["ok-push-points-corpus-dog-bone"] = (DOG_BONE, dog_bone(), dog_bone.__doc__ or "")
    return found


def cases() -> dict[str, fixture_cases.Case]:
    return {
        case.slug: case
        for case in fixture_cases.load("cq")
        if case.slug.startswith("ok-push-points-")
    }


def test_every_ok_push_points_fixture_is_the_closed_form() -> None:
    """The committed files are exactly what `fixture_programs` computes."""
    committed = cases()
    assert sorted(committed) == sorted(fixture_programs())
    for slug, (program, expected, _) in fixture_programs().items():
        assert committed[slug].program == program, slug
        got = committed[slug].expected["measures"]
        assert json.loads(json.dumps(got)) == json.loads(json.dumps(expected)), slug


@pytest.mark.parametrize("slug", sorted(fixture_programs()))
def test_ok_push_points_fixtures_agree_with_the_recorded_oracle(slug: str) -> None:
    case = cases()[slug]
    path = fixture_cases.ROOT / "cq" / slug / "oracle.json"
    report = OracleReport.model_validate_json(path.read_text())
    assert compare(fixture_cases.run(case), report).outcome is FidelityOutcome.AGREE


def test_the_oracles_reports_hold_the_closed_forms() -> None:
    """Open CASCADE builds the closed form's part: the same volume, area and bounds."""
    for slug, (_, expected, _) in fixture_programs().items():
        path = fixture_cases.ROOT / "cq" / slug / "oracle.json"
        report = OracleReport.model_validate_json(path.read_text())
        assert report.measures is not None
        assert report.measures.solids == expected["shells"], slug
        assert fixture_cases.close(report.measures.volume, float(str(expected["volume"]))), slug
        assert fixture_cases.close(report.measures.area, float(str(expected["area"]))), slug


@pytest.mark.parametrize(
    ("chain", "message"),
    [
        (
            f"{BASE}.faces('>Z').workplane().pushPoints([(2,)]).hole(1)",
            "Workplane.pushPoints(list with a point of 1 numbers)",
        ),
        (
            f"{BASE}.faces('>Z').workplane().pushPoints([2]).hole(1)",
            "Workplane.pushPoints(list with a point of num)",
        ),
        (
            f"{BASE}.faces('>Z').workplane().pushPoints([(1, 2, 3, 4)]).hole(1)",
            "Workplane.pushPoints(list with a point of 4 numbers)",
        ),
        (
            f"{BASE}.faces('>Z').workplane().pushPoints([cq.Vector(1, 2, 0)]).hole(1)",
            "Workplane.pushPoints(list with a point of call)",
        ),
        (
            f"{BASE}.faces('>Z').pushPoints([(1, 1)]).hole(1)",
            "Workplane.pushPoints on selected faces",
        ),
        (
            f"{BASE}.moveTo(1, 1).pushPoints([(1, 1)]).hole(1)",
            "Workplane.pushPoints on a pending wire",
        ),
        (
            f"{BASE}.pushPoints([(1, 1)]).box(1, 1, 1)",
            "Workplane.box on a point stack",
        ),
        (
            f"{BASE}.pushPoints([(1, 1)]).moveTo(0, 0)",
            "Workplane.moveTo on a point stack",
        ),
        (
            f"{BASE}.pushPoints([(1, 1)]).lineTo(0, 0)",
            "Workplane.lineTo on a point stack",
        ),
        (
            f"{BASE}.pushPoints([(1, 1)]).extrude(1)",
            "Workplane.extrude on a point stack",
        ),
        (
            f"{BASE}.pushPoints([(1, 1)]).workplane()",
            "Workplane.workplane on a point stack",
        ),
    ],
)
def test_a_point_stack_outside_the_subset_is_unsupported(chain: str, message: str) -> None:
    """A point that is not two or three numbers, and a call on a stack of points, name the form."""
    result = ag.run(wrap(chain.replace("'", '"')), dialect="cq")
    assert result.status is ag.Status.UNSUPPORTED_API
    assert message in result.message


def test_a_hole_on_points_with_no_solid_is_cadquerys_error() -> None:
    result = ag.run(wrap('cq.Workplane("XY").pushPoints([(1, 1)]).hole(1)'), dialect="cq")
    assert result.status is ag.Status.RUNTIME
    assert "Cannot find a solid" in result.message


def test_push_points_leaves_the_workplane_it_came_from() -> None:
    wp = cq.Workplane("XY").box(2, 2, 2).faces(">Z").workplane()
    pushed = wp.pushPoints([(0.5, 0.0)])
    assert wp._stack == ()
    assert pushed._stack != wp._stack


@settings(max_examples=60, deadline=None)
@given(
    plane=st.sampled_from(sorted(PLANE_NORMAL)),
    size=st.tuples(*(st.integers(6, 9) for _ in range(3))),
    origin=st.tuples(*(st.integers(-6, 6) for _ in range(3))),
    selector=st.sampled_from(sorted(AXES)),
    diameter=st.sampled_from([0.5, 1.0, 1.5]),
    cells=st.lists(
        st.tuples(st.integers(-1, 1), st.integers(-1, 1)), min_size=1, max_size=4, unique=True
    ),
)
def test_holes_at_pushed_points_are_the_closed_form(
    plane: str,
    size: tuple[int, int, int],
    origin: tuple[int, int, int],
    selector: str,
    diameter: float,
    cells: list[tuple[int, int]],
) -> None:
    """Volume V - n pi d^2 / 4 length, the centroid moved by each hole's centre.

    The points sit on a grid of 2, over a face with half sizes of at least 3: a
    hole of up to 1.5 is inside it and clear of its neighbours.
    """
    halves = world_halves(plane, (size[0], size[1], size[2]))
    axis = next(i for i in range(3) if AXES[selector][0][i])
    length = 2 * halves[axis]
    points = [(2.0 * i, 2.0 * j) for i, j in cells]
    wp = (
        cq.Workplane(plane, origin=origin)
        .box(*size)
        .faces(selector)
        .workplane()
        .pushPoints(points)
        .hole(diameter)
    )
    (solid,) = wp._solids()
    got = solid.measure()
    each = math.pi * diameter * diameter / 4 * length
    box = size[0] * size[1] * size[2]
    volume = box - len(points) * each
    assert fixture_cases.close(got.volume, volume)
    centres = [world(selector, p) for p in points]
    for k in range(3):
        moment = box * origin[k] - each * sum(origin[k] + c[k] for c in centres)
        assert fixture_cases.close(got.centroid[k], moment / volume)


def test_the_push_points_doctest_runs() -> None:
    import doctest

    from arris_gym.cq import _workplane

    assert doctest.testmod(_workplane).failed == 0

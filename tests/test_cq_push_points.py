"""`pushPoints(points)`, `hole(d, depth=)` and the holes at its points (ADR-0018 rules 1, 2, 4).

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


def blind_top(points: tuple[Point, ...], depth: float) -> dict[str, object]:
    """A 4 x 6 x 8 box centred on the origin, a blind hole of diameter 1 from its top at each point.

    Each cylinder (r = 1/2) runs `depth` down from z = 4, ending inside the
    box: it removes pi r^2 depth, takes a disc from the top, and adds its wall
    2 pi r depth and the cap disc at its end, so A = 208 + n 2 pi r depth. Its
    centroid is the point at z = 4 - depth / 2, so the part's is
    -(pi r^2 depth) sum(point, 4 - depth / 2) / V. The part has 6 planes and a
    cap and a wall for each hole, and no hole goes through: genus 0.
    """
    r = DIAMETER / 2
    n = len(points)
    cut = math.pi * r * r * depth
    volume = 192 - n * cut
    moment = (sum(p[0] for p in points), sum(p[1] for p in points), n * (4 - depth / 2))
    return measures(
        volume,
        208 + n * 2 * math.pi * r * depth,
        (-cut * moment[0] / volume, -cut * moment[1] / volume, -cut * moment[2] / volume),
        ((-2, -3, -4), (2, 3, 4)),
        6 + 2 * n,
        [["cylinder", n], ["plane", 6 + n]],
    )


def hex_standoff_depth() -> dict[str, object]:
    """BenchCAD's `hex_standoff_001194_s20260505`: a hex standoff with a stud and a blind bore.

    A hexagon of circumdiameter 9.238 (R = 4.619, a vertex on +x) is extruded
    9.26 up from z = 0, a stud of radius 2.315 stands 4.17 on its top, and
    `faces("<Z").workplane().hole(3.89, depth=6.02)` bores up from the hexagon's
    bottom, r = 1.945, ending inside the 9.26 prism. With A_hex = 3 sqrt 3 / 2 R^2:
    V = 9.26 A_hex + pi s^2 4.17 - pi r^2 6.02 (s the stud's radius); the stud
    adds its wall and its top over the hexagon's face it covers, the bore its
    wall (its mouth and its cap cancel), A = 2 A_hex + 6 R 9.26 + 2 pi s 4.17
    + 2 pi r 6.02. The z moment is the three solids' (a bore's centre is at z =
    3.01); x and y are 0 by symmetry. 12 faces: the hexagon's 6 sides, its
    bottom and its top (an annulus), the stud's top and wall, the bore's cap
    and wall.
    """
    big, h, s, post, r, depth = 9.238 / 2, 9.26, 2.315, 4.17, 3.89 / 2, 6.02
    hexagon = 3 * math.sqrt(3) / 2 * big * big
    volume = h * hexagon + math.pi * s * s * post - math.pi * r * r * depth
    moment = (
        h * hexagon * h / 2
        + math.pi * s * s * post * (h + post / 2)
        - math.pi * r * r * depth * depth / 2
    )
    return measures(
        volume,
        2 * hexagon + 6 * big * h + 2 * math.pi * s * post + 2 * math.pi * r * depth,
        (0, 0, moment / volume),
        ((-big, -big * math.sqrt(3) / 2, 0), (big, big * math.sqrt(3) / 2, h + post)),
        12,
        [["cylinder", 2], ["plane", 10]],
    )


HEX_STANDOFF_DEPTH = """import cadquery as cq

result = (
    cq.Workplane("XY")
    .polygon(6, 9.238)
    .extrude(9.26)
    .faces(">Z").workplane()
    .circle(2.315)
    .extrude(4.17)
    .faces("<Z").workplane()
    .hole(3.89, depth=6.02)
)

# Export
show_object(result)
"""


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
    """Every generated `ok-push-points-*` and `ok-hole-depth-*` fixture.

    Slug -> (program text, expected measures, note).
    """
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
    blind = blind_top.__doc__ or ""
    for slug, chain, points, depth in (
        ("blind", f"{top}.pushPoints([(1, 1)]).hole(1, depth=3)", ((1.0, 1.0),), 3.0),
        ("blind-several", f"{top}.pushPoints({list(SEVERAL)}).hole(1, depth=3)", SEVERAL, 3.0),
        ("blind-no-points", f"{top}.hole(1, depth=3)", ((0.0, 0.0),), 3.0),
        ("blind-small", f"{top}.pushPoints([(1, 1)]).hole(1, depth=0.25)", ((1.0, 1.0),), 0.25),
    ):
        found[f"ok-hole-depth-{slug}"] = (
            wrap(chain),
            blind_top(points, depth),
            f"`{chain.removeprefix(BASE)}`. " + blind,
        )
    for slug, thickness in (("to-the-bottom", "8"), ("past-the-part", "10")):
        found[f"ok-hole-depth-{slug}"] = (
            wrap(f"{top}.pushPoints([(1, 1)]).hole(1, depth={thickness})"),
            through_points(2, ((1.0, 1.0, 0.0),)),
            f"`depth={thickness}` on the 8-thick box: the bore leaves it, as a hole with no depth. "
            + through,
        )
    found["ok-hole-depth-corpus-hex-standoff"] = (
        HEX_STANDOFF_DEPTH,
        hex_standoff_depth(),
        hex_standoff_depth.__doc__ or "",
    )
    return found


# What CadQuery refuses for a depth it cannot make a cylinder of, and the words
# `cq` raises for each (ADR-0018 rule 4); read on the oracle: both build a
# `Standard_ConstructionError`, a zero one with `gp_Vec::Normalize()`.
RUNTIME = {
    "runtime-hole-depth-zero": (
        f"{BASE}.faces('>Z').workplane().pushPoints([(1, 1)]).hole(1, depth=0)",
        "ValueError: Workplane.hole(1, depth=0): a depth not positive "
        "(CadQuery's Standard_ConstructionError)",
    ),
    "runtime-hole-depth-negative": (
        f"{BASE}.faces('>Z').workplane().pushPoints([(1, 1)]).hole(1, depth=-1)",
        "ValueError: Workplane.hole(1, depth=-1): a depth not positive "
        "(CadQuery's Standard_ConstructionError)",
    ),
    "runtime-hole-depth-zero-and-diameter-zero": (
        f"{BASE}.faces('>Z').workplane().hole(0, depth=0)",
        "ValueError: Workplane.hole(0, depth=0): a depth not positive "
        "(CadQuery's Standard_ConstructionError)",
    ),
    "runtime-hole-depth-and-negative-diameter": (
        f"{BASE}.faces('>Z').workplane().hole(-1, depth=3)",
        "ValueError: Workplane.hole(-1, depth=3): a negative diameter "
        "(CadQuery's Standard_ConstructionError)",
    ),
}


def runtime_programs() -> dict[str, tuple[str, str]]:
    """Every generated `runtime-hole-depth-*` fixture: slug -> (program text, message)."""
    return {slug: (wrap(chain.replace("'", '"')), msg) for slug, (chain, msg) in RUNTIME.items()}


def cases() -> dict[str, fixture_cases.Case]:
    return {
        case.slug: case
        for case in fixture_cases.load("cq")
        if case.slug.startswith(("ok-push-points-", "ok-hole-depth-"))
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


def runtime_cases() -> dict[str, fixture_cases.Case]:
    return {
        case.slug: case
        for case in fixture_cases.load("cq")
        if case.slug.startswith("runtime-hole-depth-")
    }


def test_every_runtime_hole_depth_fixture_is_cadquerys_refusal() -> None:
    committed = runtime_cases()
    assert sorted(committed) == sorted(runtime_programs())
    for slug, (program, message) in runtime_programs().items():
        assert committed[slug].program == program, slug
        assert committed[slug].expected == {
            "dialect": "cq",
            "status": "runtime",
            "message": message,
        }


@pytest.mark.parametrize("slug", sorted(RUNTIME))
def test_a_depth_cadquery_refuses_is_a_runtime_status_that_agrees_with_the_oracle(
    slug: str,
) -> None:
    case = runtime_cases()[slug]
    report = OracleReport.model_validate_json(
        (fixture_cases.ROOT / "cq" / slug / "oracle.json").read_text()
    )
    assert report.status.value == "runtime"
    assert "Standard_ConstructionError" in (report.message or "")
    assert compare(fixture_cases.run(case), report).outcome is FidelityOutcome.AGREE


def test_a_zero_diameter_with_a_depth_cuts_nothing() -> None:
    """CadQuery's zero-radius cylinder is null and cuts nothing: the same part, with a depth."""
    wp = cq.Workplane("XY").box(4, 6, 8).faces(">Z").workplane().hole(0, depth=3)
    assert fixture_cases.close(wp._solids()[0].measure().volume, 192.0)


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
    depth=st.sampled_from([None, 0.5, 1.5, 3.0]),
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
    depth: float | None,
    cells: list[tuple[int, int]],
) -> None:
    """Volume V - n pi d^2 / 4 t, the centroid moved by each hole's centre.

    The bore is `t` long: the box's extent along the axis with no depth, else
    the depth (under the extent, 6 or more). Its centre is the point, `t / 2`
    inside the face. The points sit on a grid of 2, over a face with half sizes
    of at least 3: a hole of up to 1.5 is inside it and clear of its neighbours.
    """
    halves = world_halves(plane, (size[0], size[1], size[2]))
    axis = next(i for i in range(3) if AXES[selector][0][i])
    length = 2 * halves[axis]
    points = [(2.0 * i, 2.0 * j) for i, j in cells]
    pushed = (
        cq.Workplane(plane, origin=origin).box(*size).faces(selector).workplane().pushPoints(points)
    )
    wp = pushed.hole(diameter) if depth is None else pushed.hole(diameter, depth=depth)
    (solid,) = wp._solids()
    got = solid.measure()
    bored = length if depth is None else depth
    each = math.pi * diameter * diameter / 4 * bored
    box = size[0] * size[1] * size[2]
    volume = box - len(points) * each
    assert fixture_cases.close(got.volume, volume)
    normal = AXES[selector][0]
    centres = [world(selector, p) for p in points]
    for k in range(3):
        inside = normal[k] * (length / 2 - bored / 2)
        moment = box * origin[k] - each * sum(origin[k] + c[k] + inside for c in centres)
        assert fixture_cases.close(got.centroid[k], moment / volume)


def test_the_push_points_doctest_runs() -> None:
    import doctest

    from arris_gym.cq import _workplane

    assert doctest.testmod(_workplane).failed == 0

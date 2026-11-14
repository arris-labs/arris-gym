"""The contexts plans/lift-holes-and-points step 6 reads on the oracle (ADR-0018 rules 2, 3 and 5).

`faces(sel)` on a stack of faces ranks those faces only; `circle` on a stack of
points draws a circle at each and `extrude` builds a post on each; `cboreHole`
and `cskHole` run on a compound and after a hole as `hole` does. Each fixture's
expectation is a closed form worked out by hand from how the part is built (the
`note` says how), each beside the oracle's recorded report. Nothing is read from
`cq`.
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
from arris_gym.cq._selector import Faces
from arris_gym.fidelity import FidelityOutcome, OracleReport, compare
from test_cq_cbore import Bore as Stepped
from test_cq_csk import Sink
from test_cq_faces import AXES, PLANE_NORMAL, world_halves
from test_cq_hole import BASE, measures, through_box, wrap
from test_cq_push_points import SEVERAL, Point, Vec, world
from test_hole_probe import Bore as Cavity

TOP = 'cq.Workplane("XY").box(10, 8, 4).faces(">Z").workplane()'
# Two 10 x 8 x 4 boxes 10 apart: A about the origin, B about (20, 0, 0).
PAIR = (
    'cq.Workplane("XY").box(10, 8, 4).union(\n'
    '        cq.Workplane("XY").transformed(offset=cq.Vector(20, 0, 0)).box(10, 8, 4)\n    )'
)
BOX_VOLUME = 320.0
BOX_AREA = 304.0


def compound_x() -> dict[str, object]:
    """The pair, `faces(">X").faces("<Z").workplane().hole(1)`: a bore along x through both.

    `>X` is B's face at x = 25 alone; `<Z` of that one face keeps it, so the
    plane is x = 25 with its origin at (25, 0, 0) and the bore, as long as the
    pair's diagonal, runs back along x through B (10), the gap, and A (10).
    V = 640 - 2 pi r^2 10; each wall adds 2 pi r 10 and each end takes two discs
    r^2 pi, A = 608 + 2 (2 pi r 10 - 2 pi r^2); B's bore is at x = 20, A's at 0.
    """
    r = 0.5
    cut = math.pi * r * r * 10
    volume = 2 * BOX_VOLUME - 2 * cut
    return measures(
        volume,
        2 * BOX_AREA + 2 * (2 * math.pi * r * 10 - 2 * math.pi * r * r),
        ((BOX_VOLUME * 20 - cut * 20) / volume, 0, 0),
        ((-5, -4, -2), (25, 4, 2)),
        14,
        [["cylinder", 2], ["plane", 12]],
        shells=2,
        genus=2,
    )


def post_cluster(
    points: tuple[Point, ...], radius: float, height: float, base: bool
) -> dict[str, object]:
    """Posts of `radius` and `height` at each of `points`, on the 10 x 8 x 4 box's top or alone.

    On the box, each post is fused with it: V = 320 + n pi r^2 h, A = 304 + n 2 pi r
    h (its cap replaces the disc it stands on), the posts' centroids at z = 2 + h/2:
    one cylinder and one cap plane each. With no box (a workplane's own origin), the
    posts stand from z = 0 and are n solids that do not meet: V = n pi r^2 h,
    A = n (2 pi r h + 2 pi r^2), centroid at z = h/2, a cylinder and two planes each.
    """
    n = len(points)
    post = math.pi * radius * radius * height
    if base:
        volume = BOX_VOLUME + n * post
        moment = (
            sum(p[0] for p in points) * post,
            sum(p[1] for p in points) * post,
            n * post * (2 + height / 2),
        )
        return measures(
            volume,
            BOX_AREA + n * 2 * math.pi * radius * height,
            (moment[0] / volume, moment[1] / volume, moment[2] / volume),
            ((-5, -4, -2), (5, 4, 2 + height)),
            6 + 2 * n,
            [["cylinder", n], ["plane", 6 + n]],
        )
    volume = n * post
    return measures(
        volume,
        n * (2 * math.pi * radius * height + 2 * math.pi * radius * radius),
        (
            sum(p[0] for p in points) / n,
            sum(p[1] for p in points) / n,
            height / 2,
        ),
        (
            (min(p[0] for p in points) - radius, min(p[1] for p in points) - radius, 0),
            (max(p[0] for p in points) + radius, max(p[1] for p in points) + radius, height),
        ),
        3 * n,
        [["cylinder", n], ["plane", 2 * n]],
        shells=n,
    )


def pair_with_sink(sink: Stepped | Sink) -> dict[str, object]:
    """The pair (A and B above) with a sink cut from A's top at its origin.

    A is bored down from z = 2 at (0, 0), `sink`'s closed form: V = 640 - V_sink,
    the area gains the sink's walls and floors and loses its mouth (and its exit
    where it is through), B is untouched. The part's x moment is B's, 320 * 20,
    and its z moment is minus the sink's, V_sink * c / 2 - m_sink about A's middle
    (c = 4). The sink goes through A: genus 1, two shells (A and B).
    """
    along = sink.volume * 2 - sink.depth_moment
    volume = 2 * BOX_VOLUME - sink.volume
    kinds: list[list[object]] = []
    if isinstance(sink, Stepped):
        kinds = [["cylinder", len(sink.steps) + sink.merged], ["plane", 12 + sink.planes]]
    else:
        if sink.cone:
            kinds.append(["cone", 1])
        if sink.cylinder:
            kinds.append(["cylinder", 1])
        kinds.append(["plane", 12])
    return measures(
        volume,
        2 * BOX_AREA + sink.area,
        (BOX_VOLUME * 20 / volume, 0, -along / volume),
        ((-5, -4, -2), (25, 4, 2)),
        sum(int(str(count)) for _, count in kinds),
        kinds,
        shells=2,
        genus=1,
    )


def after_a_hole(second: Cavity, kinds: list[list[object]]) -> dict[str, object]:
    """`pushPoints([(3, 2)]).hole(1)` on the 10 x 8 x 4 box's top, then a second bore at its centre.

    The first hole is a bore of r = 1/2 through at (3, 2), V = pi r^2 4 = pi. The second
    call finds the solid on the stack, so it bores at the solid's centroid, in the middle
    plane z = 0 at (-3 pi, -2 pi) / (320 - pi), and down: a cavity from z = 0 that leaves by the
    bottom face, `second`. V = 320 - pi - V_cavity; the area gains the first bore's
    wall less its two discs, and the cavity's walls and floors, its top a cap and its
    exit a disc taken off the bottom; the centroid is minus the two bores' moments.
    The cap at z = 0 is the counterbore's or the cone's disc with the bore's inside it:
    arris keeps it as two faces (a plane more than CadQuery's `clean` leaves).
    """
    first = Cavity((3.0, 2.0, 2.0), (0.0, 0.0, -1.0), ((0.5, 0.5, 4.0),))
    volume = BOX_VOLUME - first.volume() - second.volume()
    moment = tuple(first.moment()[k] + second.moment()[k] for k in range(3))
    return measures(
        volume,
        BOX_AREA + first.area() + second.area(),
        (-moment[0] / volume, -moment[1] / volume, -moment[2] / volume),
        ((-5, -4, -2), (5, 4, 2)),
        sum(int(str(count)) for _, count in kinds),
        kinds,
        genus=1,
    )


def second_bore(sections: tuple[tuple[float, float, float], ...]) -> Cavity:
    """A cavity from the middle plane at the box's centroid after the first hole, down and out."""
    scale = -math.pi / (BOX_VOLUME - math.pi)
    at = (3.0 * scale, 2.0 * scale, 0.0)
    return Cavity(at, (0.0, 0.0, -1.0), sections, opens=False)


PROGRAMS: dict[str, tuple[str, dict[str, object], str]] = {}


def add(slug: str, chain: str, expected: dict[str, object], doc: str | None) -> None:
    PROGRAMS[slug] = (wrap(chain), expected, doc or "")


add(
    "ok-ctx-faces-on-faces-same",
    f'{BASE}.faces(">Z").faces(">Z").workplane().hole(2)',
    through_box(2),
    "A second `>Z` on the one face the first kept leaves it: " + (through_box.__doc__ or ""),
)
add(
    "ok-ctx-faces-on-faces-opposite",
    f'{BASE}.faces(">Z").faces("<Z").workplane().hole(2)',
    through_box(2),
    "The opposite selector on one stacked face keeps it too (its centre is the only key): "
    + (through_box.__doc__ or ""),
)
add(
    "ok-ctx-faces-on-faces-cross-axis",
    f'{BASE}.faces(">X").faces(">Y").workplane().hole(2)',
    through_box(0),
    "A selector along another axis keeps the one stacked face: " + (through_box.__doc__ or ""),
)
add(
    "ok-ctx-faces-on-faces-compound",
    f'{PAIR}.faces(">X").faces("<Z").workplane().hole(1)',
    compound_x(),
    compound_x.__doc__,
)
POSTS: dict[str, tuple[str, tuple[Point, ...], float, float]] = {
    "one": ("pushPoints([(2, 1)]).circle(0.5).extrude(1)", ((2.0, 1.0),), 0.5, 1.0),
    "several": (f"pushPoints({list(SEVERAL)}).circle(0.5).extrude(1)", SEVERAL, 0.5, 1.0),
    "both": (
        "pushPoints([(2, 1), (-2, -1)]).circle(0.5).extrude(1, both=True)",
        ((2.0, 1.0), (-2.0, -1.0)),
        0.5,
        1.0,
    ),
}
for slug, (chain, points, radius, height) in POSTS.items():
    add(
        f"ok-ctx-circle-points-{slug}",
        f"{TOP}.{chain}",
        post_cluster(points, radius, height, True),
        f"`{chain}` on the top of a 10 x 8 x 4 box. " + (post_cluster.__doc__ or ""),
    )
add(
    "ok-ctx-circle-points-no-base",
    'cq.Workplane("XY").pushPoints([(0, 0), (3, 0)]).circle(1).extrude(2)',
    post_cluster(((0.0, 0.0), (3.0, 0.0)), 1.0, 2.0, False),
    '`cq.Workplane("XY").pushPoints([(0, 0), (3, 0)]).circle(1).extrude(2)`. '
    + (post_cluster.__doc__ or ""),
)
add(
    "ok-ctx-cbore-in-a-compound",
    f'{PAIR}.faces(">Z").workplane().cboreHole(1, 2, 0.5)',
    pair_with_sink(Stepped.of([(0.5, 1e3), (1.0, 0.5)], 4.0)),
    'The pair, `faces(">Z").workplane().cboreHole(1, 2, 0.5)`: the plane is z = 2 with '
    "its origin at (0, 0), over A. " + (pair_with_sink.__doc__ or ""),
)
add(
    "ok-ctx-csk-in-a-compound",
    f'{PAIR}.faces(">Z").workplane().cskHole(1, 2, 90)',
    pair_with_sink(Sink(1.0, 2.0, 90.0, 4.0)),
    'The pair, `faces(">Z").workplane().cskHole(1, 2, 90)`: the plane is z = 2 with '
    "its origin at (0, 0), over A. " + (pair_with_sink.__doc__ or ""),
)
add(
    "ok-ctx-cbore-after-a-hole",
    f"{TOP}.pushPoints([(3, 2)]).hole(1).cboreHole(1, 2, 0.5)",
    after_a_hole(
        second_bore(((1.0, 1.0, 0.5), (0.5, 0.5, 1.5))),
        [["cylinder", 3], ["plane", 9]],
    ),
    after_a_hole.__doc__ or "",
)
add(
    "ok-ctx-csk-after-a-hole",
    f"{TOP}.pushPoints([(3, 2)]).hole(1).cskHole(1, 2, 90)",
    after_a_hole(
        second_bore(((1.0, 0.5, 0.5), (0.5, 0.5, 1.5))),
        [["cone", 1], ["cylinder", 2], ["plane", 8]],
    ),
    after_a_hole.__doc__ or "",
)


def committed() -> dict[str, fixture_cases.Case]:
    return {case.slug: case for case in fixture_cases.load("cq") if case.slug in PROGRAMS}


def recorded(slug: str) -> OracleReport:
    path = fixture_cases.ROOT / "cq" / slug / "oracle.json"
    return OracleReport.model_validate_json(path.read_text())


def test_every_context_fixture_is_the_closed_form() -> None:
    """The committed files are exactly what `PROGRAMS` computes."""
    found = committed()
    assert sorted(found) == sorted(PROGRAMS)
    for slug, (program, expected, _) in PROGRAMS.items():
        assert found[slug].program == program, slug
        got = found[slug].expected["measures"]
        assert json.loads(json.dumps(got)) == json.loads(json.dumps(expected)), slug


@pytest.mark.parametrize("slug", sorted(PROGRAMS))
def test_context_fixtures_agree_with_the_recorded_oracle(slug: str) -> None:
    assert compare(fixture_cases.run(committed()[slug]), recorded(slug)).outcome is (
        FidelityOutcome.AGREE
    )


def test_the_oracles_reports_hold_the_closed_forms() -> None:
    """Open CASCADE builds the closed form's part: its volume, area and solid count."""
    for slug, (_, expected, _) in PROGRAMS.items():
        report = recorded(slug)
        assert report.measures is not None
        assert report.measures.solids == expected["shells"], slug
        assert fixture_cases.close(report.measures.volume, float(str(expected["volume"]))), slug
        assert fixture_cases.close(report.measures.area, float(str(expected["area"]))), slug


PIN = "Workplane.circle on points no further apart than 2 radii"


@pytest.mark.parametrize(
    ("chain", "message"),
    [
        (f"{TOP}.pushPoints([(0, 0), (0.5, 0)]).circle(0.5).extrude(1)", PIN),
        (f"{TOP}.pushPoints([(0, 0), (1, 0)]).circle(0.5).extrude(1)", PIN),
        (f"{TOP}.pushPoints([(1, 1), (1, 1)]).circle(0.5).extrude(1)", PIN),
        (
            f"{TOP}.pushPoints([(2, 1, 1), (-2, -1, 0)]).circle(0.5).extrude(1)",
            "Workplane.circle on a point with an offset",
        ),
        (
            f"{TOP}.pushPoints([(2, 1), (-2, -1)]).circle(0.5).circle(0.25).extrude(1)",
            "Workplane.circle on a non-empty stack",
        ),
        (
            f"{TOP}.pushPoints([(2, 1), (-2, -1)]).circle(0.5).hole(1)",
            "Workplane.hole on a pending wire",
        ),
        (
            f"{TOP}.pushPoints([(2, 1), (-2, -1)]).circle(0.5).cboreHole(1, 2, 0.5)",
            "Workplane.cboreHole on a pending wire",
        ),
        (
            f"{TOP}.pushPoints([(2, 1), (-2, -1)]).circle(0.5).workplane()",
            "Workplane.workplane on a pending wire",
        ),
        (
            f"{TOP}.pushPoints([(2, 1), (-2, -1)]).circle(0.5).revolve(360, (0, 0, 0), (0, 1, 0))",
            "Workplane.revolve on circles at points",
        ),
        (
            f"{TOP}.pushPoints([(2, 1), (-2, -1)]).circle(0.5).lineTo(1, 1)",
            "Workplane.lineTo on circles at points",
        ),
        (
            f"{TOP}.pushPoints([(2, 1), (-2, -1)]).circle(0.5).moveTo(1, 1)",
            "Workplane.moveTo on a pending wire",
        ),
        (
            'cq.Workplane("XY").box(2, 2, 2).faces(">Z").faces(">Z").box(1, 1, 1)',
            "Workplane.box on selected faces",
        ),
        (
            'cq.Workplane("XY").box(2, 2, 2).faces(">Z").faces(">Z").extrude(1)',
            "Workplane.extrude on selected faces",
        ),
        (
            'cq.Workplane("XY").box(2, 2, 2).faces(">Z").faces(">Z").hole(1)',
            "Workplane.hole on selected faces",
        ),
        (
            'cq.Workplane("XY").box(2, 2, 2).faces(">Z").faces(">Z")'
            ".revolve(360, (0, 0, 0), (0, 1, 0))",
            "Workplane.revolve on selected faces",
        ),
    ],
)
def test_a_context_cadquery_reads_differently_is_unsupported(chain: str, message: str) -> None:
    result = ag.run(wrap(chain), dialect="cq")
    assert result.status is ag.Status.UNSUPPORTED_API
    assert message in result.message


# The refusals of `circle` on a stack of points committed as fixtures, each beside
# the oracle's recorded report: slug -> (chain after the plane, our message, the
# oracle's status). CadQuery merges or nests the wires (overlapping circles and a
# duplicate point: a shape its checker calls invalid), draws a point's circle on
# another plane (an offset: its face builder refuses the wires as not planar) or
# builds a ring at each point; none is the subset's reading.
UNSUPPORTED: dict[str, tuple[str, str, str]] = {
    "unsupported-circle-points-overlapping": (
        "pushPoints([(0, 0), (0.5, 0)]).circle(0.5).extrude(1)",
        PIN,
        "invalid",
    ),
    "unsupported-circle-points-duplicate": (
        "pushPoints([(1, 1), (1, 1)]).circle(0.5).extrude(1)",
        PIN,
        "invalid",
    ),
    "unsupported-circle-points-offset": (
        "pushPoints([(2, 1, 1), (-2, -1, 0)]).circle(0.5).extrude(1)",
        "Workplane.circle on a point with an offset",
        "runtime",
    ),
    "unsupported-circle-points-ring": (
        "pushPoints([(2, 1), (-2, -1)]).circle(0.5).circle(0.25).extrude(1)",
        "Workplane.circle on a non-empty stack",
        "ok",
    ),
}


def test_every_unsupported_circle_points_fixture_is_its_refusal() -> None:
    found = {
        case.slug: case
        for case in fixture_cases.load("cq")
        if case.slug.startswith("unsupported-circle-points-")
    }
    assert sorted(found) == sorted(UNSUPPORTED)
    for slug, (chain, message, _) in UNSUPPORTED.items():
        assert found[slug].program == wrap(f"{TOP}.{chain}"), slug
        assert found[slug].expected == {
            "dialect": "cq",
            "status": "unsupported_api",
            "message": message,
        }, slug
        result = fixture_cases.run(found[slug])
        assert result.status is ag.Status.UNSUPPORTED_API, slug
        assert result.message == message, slug


@pytest.mark.parametrize("slug", sorted(UNSUPPORTED))
def test_cadquery_reads_the_refused_circles_otherwise(slug: str) -> None:
    assert recorded(slug).status.value == UNSUPPORTED[slug][2]


def test_the_oracles_ring_at_each_point_is_two_annular_posts() -> None:
    """V = 320 + 2 pi (0.5^2 - 0.25^2): a ring of radii 0.5 and 0.25 extruded 1 at each point."""
    report = recorded("unsupported-circle-points-ring")
    assert report.measures is not None
    want = BOX_VOLUME + 2 * math.pi * (0.5**2 - 0.25**2)
    assert fixture_cases.close(report.measures.volume, want)


def test_posts_over_no_points_are_one_circle_at_the_origin() -> None:
    """`pushPoints([])` leaves an empty stack: `circle` draws at the plane's origin."""
    result = ag.run(wrap(f"{TOP}.pushPoints([]).circle(0.5).extrude(1)"), dialect="cq")
    assert result.status is ag.Status.OK
    expected = post_cluster(((0.0, 0.0),), 0.5, 1.0, True)
    assert result.measures is not None
    assert fixture_cases.close(result.measures.volume, float(str(expected["volume"])))


@settings(max_examples=40, deadline=None)
@given(
    plane=st.sampled_from(sorted(PLANE_NORMAL)),
    size=st.tuples(*(st.integers(6, 9) for _ in range(3))),
    origin=st.tuples(*(st.integers(-6, 6) for _ in range(3))),
    selector=st.sampled_from(sorted(AXES)),
    radius=st.sampled_from([0.25, 0.5, 0.75]),
    height=st.sampled_from([1.0, 2.0]),
    cells=st.lists(
        st.tuples(st.integers(-1, 1), st.integers(-1, 1)), min_size=1, max_size=4, unique=True
    ),
)
def test_posts_at_pushed_points_are_the_closed_form(
    plane: str,
    size: tuple[int, int, int],
    origin: tuple[int, int, int],
    selector: str,
    radius: float,
    height: float,
    cells: list[tuple[int, int]],
) -> None:
    """Volume and centroid of a post at each point, on any face of any box.

    The points sit on a grid of 2 over a face with half sizes of at least 3, so
    a radius of up to 3/4 is clear of the edges and of its neighbours' circles.
    V = V_box + n pi r^2 h, each post's centroid h / 2 off the face along its normal.
    """
    points = [(2.0 * i, 2.0 * j) for i, j in cells]
    wp = (
        cq.Workplane(plane, origin=origin)
        .box(*size)
        .faces(selector)
        .workplane()
        .pushPoints(points)
        .circle(radius)
        .extrude(height)
    )
    (solid,) = wp._solids()
    got = solid.measure()
    halves = world_halves(plane, (size[0], size[1], size[2]))
    normal = AXES[selector][0]
    axis = next(i for i in range(3) if normal[i])
    post = math.pi * radius * radius * height
    box = size[0] * size[1] * size[2]
    volume = box + len(points) * post
    assert fixture_cases.close(got.volume, volume)
    centres: list[Vec] = [world(selector, p) for p in points]
    for k in range(3):
        lift = normal[k] * (halves[axis] + height / 2)
        moment = box * origin[k] + sum(post * (origin[k] + c[k] + lift) for c in centres)
        assert fixture_cases.close(got.centroid[k], moment / volume)


@settings(max_examples=40, deadline=None)
@given(
    plane=st.sampled_from(sorted(PLANE_NORMAL)),
    size=st.tuples(*(st.integers(6, 9) for _ in range(3))),
    first=st.sampled_from(sorted(AXES)),
    second=st.sampled_from(sorted(AXES)),
)
def test_a_selector_on_one_stacked_face_keeps_it(
    plane: str, size: tuple[int, int, int], first: str, second: str
) -> None:
    """`faces(a).faces(b)` on a box: the one face `a` kept stays, whatever `b` is."""
    box = cq.Workplane(plane).box(*size)
    once = box.faces(first)._stack[0]
    twice = box.faces(first).faces(second)._stack[0]
    assert isinstance(once, Faces)
    assert isinstance(twice, Faces)
    assert twice.faces == once.faces


def test_the_context_doctests_run() -> None:
    import doctest

    from arris_gym.cq import _workplane

    assert doctest.testmod(_workplane).failed == 0

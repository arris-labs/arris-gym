"""`cskHole(d, cskD, cskAngle)` bores CadQuery's countersink at each point (ADR-0018 rule 3).

CadQuery fuses a bore cylinder with a cone, the cone's base on the plane and its
tip `h = (cskD / 2) / tan(cskAngle / 2)` below it, and cuts the union at every
point of the stack. `cq` cuts the two as separate tools of one call, a cut by
their union. The closed forms are worked out here from the profile that union
has, never from `cq`: a bore of radius `r` and a cone of radius `R` and height
`h` leave, at depth `z`, the larger of `r` and `R (1 - z / h)`, so a cone wider
than the bore is a frustum down to `z* = h (1 - r / R)` and the bore below it.
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
from test_cq_faces import AXES, PLANE_NORMAL, world_halves
from test_cq_hole import measures, wrap
from test_cq_push_points import SEVERAL, Point, Vec, world
from test_hole_probe import Bore as Cavity

# The default part: 10 x 8 x 4 about the origin, bored from its top face.
BOX: Vec = (10.0, 8.0, 4.0)
TOP = 'cq.Workplane("XY").box(10, 8, 4).faces(">Z").workplane()'


class Sink:
    """What a bore of diameter `d` under a countersink `cskD` at `angle` degrees cuts, from a face.

    `sections` are the cavity's frusta from the face down, `(radius at the
    top, radius at the bottom, length)`, cut to a part `thickness` thick;
    `through` says the last leaves by the far face. `cone` and `cylinder` say
    which faces the cavity has.
    """

    def __init__(self, d: float, big: float, angle: float, thickness: float) -> None:
        r, big_r = d / 2, big / 2
        h = big_r / math.tan(math.radians(angle / 2))
        self.sections: tuple[tuple[float, float, float], ...]
        self.cone = False
        self.cylinder = r > 0
        self.through = True
        if r >= big_r:
            self.sections = ((r, r, thickness),)
            return
        meet = h * (1 - r / big_r)
        self.cone = True
        if meet >= thickness:
            self.sections = ((big_r, big_r * (1 - thickness / h), thickness),)
            self.cylinder = False
        elif r > 0:
            self.sections = ((big_r, r, meet), (r, r, thickness - meet))
        else:
            self.sections = ((big_r, 0.0, meet),)
            self.through = False

    def cavity(self) -> Cavity:
        """The cavity from the origin, down the normal: its moment's z is the depth moment."""
        return Cavity((0, 0, 0), (0, 0, 1), self.sections, through=self.through)

    @property
    def volume(self) -> float:
        return self.cavity().volume()

    @property
    def depth_moment(self) -> float:
        return self.cavity().moment()[2]

    @property
    def area(self) -> float:
        return self.cavity().area()


def countersunk_box(
    box: Vec,
    points: tuple[Point, ...],
    d: float,
    big: float,
    angle: float,
    selector: str = ">Z",
) -> dict[str, object]:
    """A `box` (sizes along x, y, z) about the origin, a sink from face `selector` at each point.

    V = abc - n V_sink, the sink a frustum under the face and a cylinder below
    it (or one alone); the area gains n times its walls and loses its mouth
    and its exit where it is through. Its centroid is its point and `c / 2 -
    m / V_sink` along the normal for a sink of moment `m` about the face: the
    part's is -n times that over V. 6 planes (a cone ends in its tip and needs
    no cap), a cone face and a cylinder face for each point that has them.
    """
    normal = AXES[selector][0]
    length = sum(abs(normal[k]) * box[k] for k in range(3))
    sink = Sink(d, big, angle, length)
    n = len(points)
    whole = box[0] * box[1] * box[2]
    volume = whole - n * sink.volume
    along = sink.volume * length / 2 - sink.depth_moment
    centres = [world(selector, p) for p in points]
    moment = tuple(sum(sink.volume * c[k] + normal[k] * along for c in centres) for k in range(3))
    kinds: list[list[object]] = []
    if sink.cone:
        kinds.append(["cone", n])
    if sink.cylinder:
        kinds.append(["cylinder", n])
    kinds.append(["plane", 6])
    return measures(
        volume,
        2 * (box[0] * box[1] + box[0] * box[2] + box[1] * box[2]) + n * sink.area,
        (-moment[0] / volume, -moment[1] / volume, -moment[2] / volume),
        ((-box[0] / 2, -box[1] / 2, -box[2] / 2), (box[0] / 2, box[1] / 2, box[2] / 2)),
        sum(int(str(count)) for _, count in kinds),
        kinds,
        genus=n if sink.through else 0,
    )


ONE: tuple[Point, ...] = ((2.0, 1.0),)
ORIGIN: tuple[Point, ...] = ((0.0, 0.0),)
FIXTURES: dict[str, tuple[str, tuple[Point, ...], float, float, float]] = {
    # slug: (chain after the plane, points, bore d, countersink D, angle)
    "one": ("pushPoints([(2, 1)]).cskHole(1, 2, 82)", ONE, 1, 2, 82),
    "one-90": ("pushPoints([(2, 1)]).cskHole(1, 2, 90)", ONE, 1, 2, 90),
    "several": (f"pushPoints({list(SEVERAL)}).cskHole(1, 2, 82)", SEVERAL, 1, 2, 82),
    "no-points": ("cskHole(1, 2, 90)", ORIGIN, 1, 2, 90),
    "wide-angle": ("pushPoints([(2, 1)]).cskHole(1, 2, 170)", ONE, 1, 2, 170),
    "narrower": ("pushPoints([(2, 1)]).cskHole(2, 1, 90)", ONE, 2, 1, 90),
    "equal": ("pushPoints([(2, 1)]).cskHole(1, 1, 90)", ONE, 1, 1, 90),
    "bore-zero": ("pushPoints([(2, 1)]).cskHole(0, 2, 90)", ONE, 0, 2, 90),
    "cone-past-the-part": ("cskHole(1, 6, 60)", ORIGIN, 1, 6, 60),
}
# A hinge's plate (BenchCAD `hinge_000040_s20260506`) as written up to its first
# `union`: a box on `XZ` (x 79.42, y 119.13, z 3.97) and three countersinks from
# its `>Y` face, which is the plate's top of thickness 3.97 in the face's frame.
HINGE_POINTS: tuple[Point, ...] = ((-19.855, -29.782), (-19.855, 0.0), (-19.855, 29.782))
HINGE = """import cadquery as cq

result = (
    cq.Workplane("XZ")
    .box(79.42, 119.13, 3.97)
    .faces(">Y").workplane()
    .pushPoints([[-19.855, -29.782], [-19.855, 0.0], [-19.855, 29.782]])
    .cskHole(4.17, 8.34, 82.0)
)

# Export
show_object(result)
"""


def hinge_plate() -> dict[str, object]:
    """`hinge_000040_s20260506` before its unions: three countersinks of 82 degrees in a plate.

    The plate is 79.42 along x, 3.97 along y and 119.13 along z (`box(79.42,
    119.13, 3.97)` on `XZ`), bored from its `>Y` face. Each sink is a bore of
    4.17 under a cone of 8.34: the frustum meets the bore 2.40 below the face,
    the rest of the plate is a through bore. The closed form is
    `countersunk_box`'s.
    """
    return countersunk_box((79.42, 3.97, 119.13), HINGE_POINTS, 4.17, 8.34, 82.0, ">Y")


def fixture_programs() -> dict[str, tuple[str, dict[str, object], str]]:
    """Every generated `ok-csk-*` fixture: slug -> (program text, expected measures, note)."""
    found: dict[str, tuple[str, dict[str, object], str]] = {}
    note = countersunk_box.__doc__ or ""
    for slug, (chain, points, d, big, angle) in FIXTURES.items():
        found[f"ok-csk-{slug}"] = (
            wrap(f"{TOP}.{chain}"),
            countersunk_box(BOX, points, d, big, angle),
            f'A 10 x 8 x 4 box, `.faces(">Z").workplane().{chain}`. {note}',
        )
    found["ok-csk-hinge-plate"] = (
        HINGE,
        hinge_plate(),
        "The plate of BenchCAD's `hinge_000040_s20260506` before its first union "
        "(the unions touch a cylinder to the plate's side, which arris refuses: "
        "`regression/cq-tangent-cylinder-and-box`). " + (hinge_plate.__doc__ or ""),
    )
    return found


# What CadQuery refuses for a countersink it cannot make, read on the oracle in
# the order it checks: the bore's diameter, the angle's tangent (zero), the cone's
# radius (zero or negative), then its height (an angle of 180 or more, or below
# zero). The words `cq` raises for each are ours, CadQuery's class beside them.
RUNTIME = {
    "runtime-csk-diameter-negative": (
        "pushPoints([(2, 1)]).cskHole(-1, 2, 82)",
        "a negative diameter (CadQuery's Standard_ConstructionError)",
        "cskHole(-1, 2, 82)",
    ),
    "runtime-csk-angle-zero": (
        "pushPoints([(2, 1)]).cskHole(1, 2, 0)",
        "an angle of zero (CadQuery's ZeroDivisionError)",
        "cskHole(1, 2, 0)",
    ),
    "runtime-csk-countersink-zero": (
        "pushPoints([(2, 1)]).cskHole(1, 0, 82)",
        "a zero countersink diameter (CadQuery's Standard_DomainError)",
        "cskHole(1, 0, 82)",
    ),
    "runtime-csk-countersink-negative": (
        "pushPoints([(2, 1)]).cskHole(1, -2, 82)",
        "a negative countersink diameter (CadQuery's Standard_DomainError)",
        "cskHole(1, -2, 82)",
    ),
    "runtime-csk-angle-180": (
        "pushPoints([(2, 1)]).cskHole(1, 2, 180)",
        "an angle that gives the cone no height (CadQuery's Standard_DomainError)",
        "cskHole(1, 2, 180)",
    ),
    "runtime-csk-angle-negative": (
        "pushPoints([(2, 1)]).cskHole(1, 2, -90)",
        "an angle that gives the cone no height (CadQuery's Standard_DomainError)",
        "cskHole(1, 2, -90)",
    ),
    # The ends of the range: tan(-90 deg) is a huge negative number and tan(180 deg)
    # a tiny negative one, so both cones have a negative height on the oracle.
    "runtime-csk-angle-minus-180": (
        "pushPoints([(2, 1)]).cskHole(1, 2, -180)",
        "an angle that gives the cone no height (CadQuery's Standard_DomainError)",
        "cskHole(1, 2, -180)",
    ),
    "runtime-csk-angle-360": (
        "pushPoints([(2, 1)]).cskHole(1, 2, 360)",
        "an angle that gives the cone no height (CadQuery's Standard_DomainError)",
        "cskHole(1, 2, 360)",
    ),
}

# Past either end, CadQuery's tangent repeats: the oracle builds the countersink
# of the angle 360 degrees nearer, which no program asks for (ADR-0018 rule 4).
# slug: (chain after the plane, the angle the oracle's cone has)
UNSUPPORTED = {
    "unsupported-csk-angle-above-360": ("pushPoints([(2, 1)]).cskHole(1, 2, 400)", 40.0),
    "unsupported-csk-angle-below-minus-180": ("pushPoints([(2, 1)]).cskHole(1, 2, -200)", 160.0),
}
OUTSIDE = "Workplane.cskHole with an angle outside [-180.0, 360.0]"


def runtime_programs() -> dict[str, tuple[str, str]]:
    """Every generated `runtime-csk-*` fixture: slug -> (program text, message)."""
    return {
        slug: (wrap(f"{TOP}.{chain}"), f"ValueError: Workplane.{call}: {reason}")
        for slug, (chain, reason, call) in RUNTIME.items()
    }


def cases() -> dict[str, fixture_cases.Case]:
    return {case.slug: case for case in fixture_cases.load("cq") if case.slug.startswith("ok-csk-")}


def runtime_cases() -> dict[str, fixture_cases.Case]:
    return {
        case.slug: case for case in fixture_cases.load("cq") if case.slug.startswith("runtime-csk-")
    }


def unsupported_cases() -> dict[str, fixture_cases.Case]:
    return {
        case.slug: case
        for case in fixture_cases.load("cq")
        if case.slug.startswith("unsupported-csk-")
    }


def recorded(slug: str) -> OracleReport:
    path = fixture_cases.ROOT / "cq" / slug / "oracle.json"
    return OracleReport.model_validate_json(path.read_text())


def test_every_ok_csk_fixture_is_the_closed_form() -> None:
    """The committed files are exactly what `fixture_programs` computes."""
    committed = cases()
    assert sorted(committed) == sorted(fixture_programs())
    for slug, (program, expected, _) in fixture_programs().items():
        assert committed[slug].program == program, slug
        got = committed[slug].expected["measures"]
        assert json.loads(json.dumps(got)) == json.loads(json.dumps(expected)), slug


@pytest.mark.parametrize("slug", sorted(fixture_programs()))
def test_ok_csk_fixtures_agree_with_the_recorded_oracle(slug: str) -> None:
    assert compare(fixture_cases.run(cases()[slug]), recorded(slug)).outcome is (
        FidelityOutcome.AGREE
    )


def test_the_oracles_reports_hold_the_closed_forms() -> None:
    """Open CASCADE builds the closed form's part: its volume, area and solid count."""
    for slug, (_, expected, _) in fixture_programs().items():
        report = recorded(slug)
        assert report.measures is not None
        assert report.measures.solids == expected["shells"], slug
        assert fixture_cases.close(report.measures.volume, float(str(expected["volume"]))), slug
        assert fixture_cases.close(report.measures.area, float(str(expected["area"]))), slug


def test_every_runtime_csk_fixture_is_cadquerys_refusal() -> None:
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
def test_a_countersink_cadquery_refuses_agrees_with_the_oracle(slug: str) -> None:
    report = recorded(slug)
    assert report.status.value == "runtime"
    assert compare(fixture_cases.run(runtime_cases()[slug]), report).outcome is (
        FidelityOutcome.AGREE
    )


def test_every_unsupported_csk_fixture_is_an_angle_outside_the_range() -> None:
    committed = unsupported_cases()
    assert sorted(committed) == sorted(UNSUPPORTED)
    for slug, (chain, _) in UNSUPPORTED.items():
        assert committed[slug].program == wrap(f"{TOP}.{chain}"), slug
        assert committed[slug].expected == {
            "dialect": "cq",
            "status": "unsupported_api",
            "message": OUTSIDE,
        }
        result = fixture_cases.run(committed[slug])
        assert result.status is ag.Status.UNSUPPORTED_API, slug
        assert result.message == OUTSIDE, slug


@pytest.mark.parametrize("slug", sorted(UNSUPPORTED))
def test_past_the_range_the_oracle_builds_the_angle_a_turn_nearer(slug: str) -> None:
    """The oracle's cone is the one of the angle 360 degrees nearer: the closed form's volume."""
    report = recorded(slug)
    assert report.status.value == "ok"
    assert report.measures is not None
    want = countersunk_box(BOX, ONE, 1, 2, UNSUPPORTED[slug][1])["volume"]
    assert fixture_cases.close(report.measures.volume, float(str(want)))


@pytest.mark.parametrize(
    ("chain", "message"),
    [
        (f"{TOP}.cskHole(1, 2, 82, 1)", "Workplane.cskHole(num, num, num, num)"),
        (f"{TOP}.cskHole(1, 2)", "Workplane.cskHole(num, num)"),
        (
            f"{TOP}.cskHole(1, 2, 82, clean=False)",
            "Workplane.cskHole(num, num, num; clean=bool)",
        ),
        (f"{TOP}.cskHole(1, 2, 82, depth=3)", "Workplane.cskHole(num, num, num; depth=num)"),
        (f"{TOP}.cskHole(1, 2, 400)", "Workplane.cskHole with an angle outside"),
        (f"{TOP}.cskHole(1, 2, -200)", "Workplane.cskHole with an angle outside"),
        (
            'cq.Workplane("XY").box(4, 4, 4).faces(">Z").cskHole(1, 2, 82)',
            "Workplane.cskHole on selected faces",
        ),
        (
            'cq.Workplane("XY").box(4, 4, 4).moveTo(1, 1).lineTo(2, 2).cskHole(1, 2, 82)',
            "Workplane.cskHole on a pending wire",
        ),
    ],
)
def test_a_countersink_outside_the_subset_is_unsupported(chain: str, message: str) -> None:
    result = ag.run(wrap(chain), dialect="cq")
    assert result.status is ag.Status.UNSUPPORTED_API
    assert message in result.message


def test_a_countersink_with_no_solid_is_cadquerys_error() -> None:
    result = ag.run(wrap('cq.Workplane("XY").cskHole(1, 2, 82)'), dialect="cq")
    assert result.status is ag.Status.RUNTIME
    assert "Cannot find a solid" in result.message


@settings(max_examples=60, deadline=None)
@given(
    plane=st.sampled_from(sorted(PLANE_NORMAL)),
    size=st.tuples(*(st.integers(6, 9) for _ in range(3))),
    origin=st.tuples(*(st.integers(-6, 6) for _ in range(3))),
    selector=st.sampled_from(sorted(AXES)),
    bore=st.sampled_from([0.0, 0.5, 1.0, 1.5]),
    big=st.sampled_from([0.5, 1.0, 1.5]),
    angle=st.sampled_from([60.0, 82.0, 90.0, 120.0]),
    cells=st.lists(
        st.tuples(st.integers(-1, 1), st.integers(-1, 1)), min_size=1, max_size=4, unique=True
    ),
)
def test_countersinks_at_pushed_points_are_the_closed_form(
    plane: str,
    size: tuple[int, int, int],
    origin: tuple[int, int, int],
    selector: str,
    bore: float,
    big: float,
    angle: float,
    cells: list[tuple[int, int]],
) -> None:
    """Volume and centroid of the sink at each point, on any face of any box.

    The points sit on a grid of 2 over a face with half sizes of at least 3: a
    cone or a bore of up to 1.5 across is inside it
    and clear of its neighbours; its height, at most 1.3, is inside the part.
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
        .cskHole(bore, big, angle)
    )
    (solid,) = wp._solids()
    got = solid.measure()
    sink = Sink(bore, big, angle, length)
    box = size[0] * size[1] * size[2]
    volume = box - len(points) * sink.volume
    assert fixture_cases.close(got.volume, volume)
    normal = AXES[selector][0]
    centres: list[Vec] = [world(selector, p) for p in points]
    for k in range(3):
        along = normal[k] * (sink.volume * length / 2 - sink.depth_moment)
        moment = box * origin[k] - sum(sink.volume * (origin[k] + c[k]) + along for c in centres)
        assert fixture_cases.close(got.centroid[k], moment / volume)


def test_the_csk_doctest_runs() -> None:
    import doctest

    from arris_gym.cq import _workplane

    assert doctest.testmod(_workplane).failed == 0

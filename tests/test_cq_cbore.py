"""`cboreHole(d, cboreD, cboreDepth)` bores CadQuery's counterbore at each point (ADR-0018 rule 3).

CadQuery fuses a bore cylinder with a counterbore cylinder, both from the plane
and against its normal, and cuts the union at every point of the stack. `cq`
cuts the two as separate tools of one call, and a cut by both is a cut by their
union. The closed forms are worked out here from the stepped profile that union
has, never from `cq`: coaxial cylinders from one face make a profile whose
radius at depth `z` is the largest of those that reach `z`.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass

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

PartBox = tuple[float, float, float]
# The default part: 10 x 8 x 4 about the origin, bored from its top face.
BOX: PartBox = (10.0, 8.0, 4.0)
TOP = 'cq.Workplane("XY").box(10, 8, 4).faces(">Z").workplane()'
# A bore is as long as the part's diagonal: always past the part's thickness.
LONG = 1e3


@dataclass(frozen=True)
class Step:
    """One run of a stepped bore: `radius` from `start` for `length`, down from the face."""

    radius: float
    start: float
    length: float


@dataclass(frozen=True)
class Bore:
    """What coaxial cylinders from one face cut from a part `thickness` thick.

    `steps` run from the face down, equal neighbours merged; `through` says the
    last one leaves by the far face; `merged` counts the places where a piece's
    wall ends in a wall of its own radius: arris keeps the two as faces of
    their own where CadQuery's `clean` joins them. Each cylinder is `(radius, depth)`; a zero
    radius is no cylinder, and a depth past the part is the part's thickness.
    """

    steps: tuple[Step, ...]
    through: bool
    merged: int = 0

    @staticmethod
    def of(cylinders: list[tuple[float, float]], thickness: float) -> Bore:
        kept = [(r, min(t, thickness)) for r, t in cylinders if r > 0]
        steps: list[Step] = []
        merged = 0
        start = 0.0
        for depth in sorted({t for _, t in kept}):
            radius = max(r for r, t in kept if t >= depth)
            if steps and steps[-1].radius == radius:
                steps[-1] = Step(radius, steps[-1].start, depth - steps[-1].start)
                # A wall of this radius ended at the last depth: arris splits the face there.
                merged += any(r == radius and t == start for r, t in kept)
            else:
                steps.append(Step(radius, start, depth - start))
            start = depth
        return Bore(tuple(steps), start >= thickness, merged)

    @property
    def volume(self) -> float:
        return sum(math.pi * s.radius**2 * s.length for s in self.steps)

    @property
    def depth_moment(self) -> float:
        """The volume's moment about the face, along the depth."""
        return sum(math.pi * s.radius**2 * s.length * (s.start + s.length / 2) for s in self.steps)

    @property
    def area(self) -> float:
        """What the bore adds to the part's area: its walls and floors, less its mouth and exit."""
        first, last = self.steps[0], self.steps[-1]
        floors = sum(
            math.pi * (a.radius**2 - b.radius**2)
            for a, b in zip(self.steps, self.steps[1:], strict=False)
        )
        walls = sum(2 * math.pi * s.radius * s.length for s in self.steps)
        end = -math.pi * last.radius**2 if self.through else math.pi * last.radius**2
        return -math.pi * first.radius**2 + walls + floors + end

    @property
    def planes(self) -> int:
        """The planes it adds: a floor for each step down and a cap where it is blind."""
        return len(self.steps) - 1 + (0 if self.through else 1)


def bored_box(
    box: PartBox, points: tuple[Point, ...], cylinders: list[tuple[float, float]]
) -> dict[str, object]:
    """A `box` about the origin, a stepped bore of `cylinders` from its top face at each point.

    V = abc - n V_bore; the area gains n times the bore's walls and floors and
    loses its mouth, and its exit where it is through. The bore's centroid is
    its point and `c / 2 - m / V_bore` along the normal for a bore of moment
    `m` about the face: the part's is -n times that over V. 6 planes, a
    cylinder for each step and a plane for each floor and a cap. Where two
    pieces have one radius (`equal`) arris keeps a wall for each: one cylinder
    face more than CadQuery's `clean` leaves (the oracle's report counts 7).
    """
    a, b, c = box
    bore = Bore.of(cylinders, c)
    n = len(points)
    volume = a * b * c - n * bore.volume
    moment = (
        sum(p[0] for p in points) * bore.volume,
        sum(p[1] for p in points) * bore.volume,
        n * (bore.volume * c / 2 - bore.depth_moment),
    )
    return measures(
        volume,
        2 * (a * b + a * c + b * c) + n * bore.area,
        (-moment[0] / volume, -moment[1] / volume, -moment[2] / volume),
        ((-a / 2, -b / 2, -c / 2), (a / 2, b / 2, c / 2)),
        6 + n * (len(bore.steps) + bore.merged + bore.planes),
        [["cylinder", n * (len(bore.steps) + bore.merged)], ["plane", 6 + n * bore.planes]],
        genus=n if bore.through else 0,
    )


def pieces(d: float, big: float, depth: float) -> list[tuple[float, float]]:
    """`cboreHole(d, big, depth)`'s cylinders: the bore (as long as any part), the counterbore."""
    return [(d / 2, LONG), (big / 2, depth)]


ONE: tuple[Point, ...] = ((2.0, 1.0),)
FIXTURES: dict[str, tuple[str, tuple[Point, ...], float, float, float]] = {
    # slug: (chain after the plane, points, bore d, counterbore D, counterbore depth)
    "one": ("pushPoints([(2, 1)]).cboreHole(1, 2, 0.5)", ONE, 1, 2, 0.5),
    "several": (f"pushPoints({list(SEVERAL)}).cboreHole(1, 2, 0.5)", SEVERAL, 1, 2, 0.5),
    "no-points": ("cboreHole(1, 2, 0.5)", ((0.0, 0.0),), 1, 2, 0.5),
    "past-the-part": ("pushPoints([(2, 1)]).cboreHole(1, 2, 5)", ONE, 1, 2, 5),
    "to-the-bottom": ("pushPoints([(2, 1)]).cboreHole(1, 2, 4)", ONE, 1, 2, 4),
    "narrower": ("pushPoints([(2, 1)]).cboreHole(2, 1, 0.5)", ONE, 2, 1, 0.5),
    "equal": ("pushPoints([(2, 1)]).cboreHole(1, 1, 0.5)", ONE, 1, 1, 0.5),
    "bore-zero": ("pushPoints([(2, 1)]).cboreHole(0, 2, 0.5)", ONE, 0, 2, 0.5),
    "counterbore-zero": ("pushPoints([(2, 1)]).cboreHole(1, 0, 0.5)", ONE, 1, 0, 0.5),
}
# A manifold block's counterbored row (BenchCAD `manifold_block_000049`) without
# the holes along y and the second `faces(">Z")` that program writes: a box on
# `XZ` (x 67.89, y 32.49, z 37.56), three counterbores from its `>Z` face.
BLOCK_POINTS: tuple[Point, ...] = ((-8.122, 0.0), (0.001, 0.0), (8.124, 0.0))
BLOCK = (
    'cq.Workplane("XZ").box(67.89, 37.56, 32.49).faces(">Z").workplane()'
    ".pushPoints([(-8.122, 0.0), (0.001, 0.0), (8.124, 0.0)]).cboreHole(3.19, 5.54, 5.63)"
)


def fixture_programs() -> dict[str, tuple[str, dict[str, object], str]]:
    """Every generated `ok-cbore-*` fixture: slug -> (program text, expected measures, note)."""
    found: dict[str, tuple[str, dict[str, object], str]] = {}
    note = bored_box.__doc__ or ""
    for slug, (chain, points, d, big, depth) in FIXTURES.items():
        found[f"ok-cbore-{slug}"] = (
            wrap(f"{TOP}.{chain}"),
            bored_box(BOX, points, pieces(d, big, depth)),
            f'A 10 x 8 x 4 box, `.faces(">Z").workplane().{chain}`. {note}',
        )
    found["ok-cbore-block-row"] = (
        wrap(BLOCK),
        block_row(),
        "A manifold block's row of three counterbores (`manifold_block_000049_s20260505` "
        "less its other holes). The block is 67.89 along x, 32.49 along y and 37.56 "
        "along z, bored from the `>Z` face. " + note,
    )
    return found


def block_row() -> dict[str, object]:
    """The block row: a 67.89 x 32.49 x 37.56 box, three counterbores down from z = 18.78."""
    box = (67.89, 32.49, 37.56)
    return bored_box(box, BLOCK_POINTS, pieces(3.19, 5.54, 5.63))


# What CadQuery refuses for a counterbore it cannot make, and the words `cq` raises
# for each; read on the oracle (all `Standard_ConstructionError`, but the three that
# make a null shape: a negative depth, and a bore and a counterbore of no width).
RUNTIME = {
    "runtime-cbore-depth-zero": (
        "pushPoints([(2, 1)]).cboreHole(1, 2, 0)",
        "a counterbore depth of zero (CadQuery's Standard_ConstructionError)",
        "cboreHole(1, 2, 0)",
    ),
    "runtime-cbore-depth-negative": (
        "pushPoints([(2, 1)]).cboreHole(1, 2, -0.5)",
        "a negative counterbore depth (CadQuery's Null TopoDS_Shape object)",
        "cboreHole(1, 2, -0.5)",
    ),
    "runtime-cbore-diameter-negative": (
        "pushPoints([(2, 1)]).cboreHole(-1, 2, 0.5)",
        "a negative diameter (CadQuery's Standard_ConstructionError)",
        "cboreHole(-1, 2, 0.5)",
    ),
    "runtime-cbore-counterbore-negative": (
        "pushPoints([(2, 1)]).cboreHole(1, -2, 0.5)",
        "a negative counterbore diameter (CadQuery's Standard_ConstructionError)",
        "cboreHole(1, -2, 0.5)",
    ),
    "runtime-cbore-no-bore-no-counterbore": (
        "pushPoints([(2, 1)]).cboreHole(0, 0, 0.5)",
        "no bore and no counterbore (CadQuery's Null TopoDS_Shape)",
        "cboreHole(0, 0, 0.5)",
    ),
}


def runtime_programs() -> dict[str, tuple[str, str]]:
    """Every generated `runtime-cbore-*` fixture: slug -> (program text, message)."""
    return {
        slug: (wrap(f"{TOP}.{chain}"), f"ValueError: Workplane.{call}: {reason}")
        for slug, (chain, reason, call) in RUNTIME.items()
    }


def cases() -> dict[str, fixture_cases.Case]:
    return {
        case.slug: case for case in fixture_cases.load("cq") if case.slug.startswith("ok-cbore-")
    }


def runtime_cases() -> dict[str, fixture_cases.Case]:
    return {
        case.slug: case
        for case in fixture_cases.load("cq")
        if case.slug.startswith("runtime-cbore-")
    }


def recorded(slug: str) -> OracleReport:
    path = fixture_cases.ROOT / "cq" / slug / "oracle.json"
    return OracleReport.model_validate_json(path.read_text())


def test_every_ok_cbore_fixture_is_the_closed_form() -> None:
    """The committed files are exactly what `fixture_programs` computes."""
    committed = cases()
    assert sorted(committed) == sorted(fixture_programs())
    for slug, (program, expected, _) in fixture_programs().items():
        assert committed[slug].program == program, slug
        got = committed[slug].expected["measures"]
        assert json.loads(json.dumps(got)) == json.loads(json.dumps(expected)), slug


@pytest.mark.parametrize("slug", sorted(fixture_programs()))
def test_ok_cbore_fixtures_agree_with_the_recorded_oracle(slug: str) -> None:
    assert compare(fixture_cases.run(cases()[slug]), recorded(slug)).outcome is (
        FidelityOutcome.AGREE
    )


def test_the_oracles_reports_hold_the_closed_forms() -> None:
    """Open CASCADE builds the closed form's part: its volume, area and bounds."""
    for slug, (_, expected, _) in fixture_programs().items():
        report = recorded(slug)
        assert report.measures is not None
        assert report.measures.solids == expected["shells"], slug
        assert fixture_cases.close(report.measures.volume, float(str(expected["volume"]))), slug
        assert fixture_cases.close(report.measures.area, float(str(expected["area"]))), slug


def test_every_runtime_cbore_fixture_is_cadquerys_refusal() -> None:
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
def test_a_counterbore_cadquery_refuses_agrees_with_the_oracle(slug: str) -> None:
    report = recorded(slug)
    assert report.status.value == "runtime"
    assert compare(fixture_cases.run(runtime_cases()[slug]), report).outcome is (
        FidelityOutcome.AGREE
    )


@pytest.mark.parametrize(
    ("chain", "message"),
    [
        (
            f"{TOP}.cboreHole(1, 2, 0.5, 1)",
            "Workplane.cboreHole(num, num, num, num)",
        ),
        (f"{TOP}.cboreHole(1, 2)", "Workplane.cboreHole(num, num)"),
        (
            f"{TOP}.cboreHole(1, 2, 0.5, clean=False)",
            "Workplane.cboreHole(num, num, num; clean=bool)",
        ),
        (f"{TOP}.cboreHole(1, 2, 0.5, depth=3)", "Workplane.cboreHole(num, num, num; depth=num)"),
        (
            'cq.Workplane("XY").box(4, 4, 4).faces(">Z").cboreHole(1, 2, 0.5)',
            "Workplane.cboreHole on selected faces",
        ),
        (
            'cq.Workplane("XY").box(4, 4, 4).moveTo(1, 1).lineTo(2, 2).cboreHole(1, 2, 0.5)',
            "Workplane.cboreHole on a pending wire",
        ),
    ],
)
def test_a_counterbore_outside_the_subset_is_unsupported(chain: str, message: str) -> None:
    result = ag.run(wrap(chain), dialect="cq")
    assert result.status is ag.Status.UNSUPPORTED_API
    assert message in result.message


def test_a_counterbore_with_no_solid_is_cadquerys_error() -> None:
    result = ag.run(wrap('cq.Workplane("XY").cboreHole(1, 2, 0.5)'), dialect="cq")
    assert result.status is ag.Status.RUNTIME
    assert "Cannot find a solid" in result.message


@settings(max_examples=60, deadline=None)
@given(
    plane=st.sampled_from(sorted(PLANE_NORMAL)),
    size=st.tuples(*(st.integers(6, 9) for _ in range(3))),
    origin=st.tuples(*(st.integers(-6, 6) for _ in range(3))),
    selector=st.sampled_from(sorted(AXES)),
    bore=st.sampled_from([0.0, 0.5, 1.0, 1.5]),
    big=st.sampled_from([0.0, 0.5, 1.0, 1.5]),
    depth=st.sampled_from([0.5, 1.5, 3.0, 20.0]),
    cells=st.lists(
        st.tuples(st.integers(-1, 1), st.integers(-1, 1)), min_size=1, max_size=4, unique=True
    ),
)
def test_counterbores_at_pushed_points_are_the_closed_form(
    plane: str,
    size: tuple[int, int, int],
    origin: tuple[int, int, int],
    selector: str,
    bore: float,
    big: float,
    depth: float,
    cells: list[tuple[int, int]],
) -> None:
    """Volume and centroid of the stepped bore at each point, on any face of any box.

    The points sit on a grid of 2 over a face with half sizes of at least 3: a
    bore or counterbore of up to 1.5 across is inside it and clear of its
    neighbours. Both diameters zero is CadQuery's null shape, and is left out.
    """
    if bore == 0 and big == 0:
        return
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
        .cboreHole(bore, big, depth)
    )
    (solid,) = wp._solids()
    got = solid.measure()
    cut = Bore.of(pieces(bore, big, depth), length)
    box = size[0] * size[1] * size[2]
    volume = box - len(points) * cut.volume
    assert fixture_cases.close(got.volume, volume)
    normal = AXES[selector][0]
    centres: list[Vec] = [world(selector, p) for p in points]
    for k in range(3):
        along = normal[k] * (cut.volume * length / 2 - cut.depth_moment)
        moment = box * origin[k] - sum(cut.volume * (origin[k] + c[k]) + along for c in centres)
        assert fixture_cases.close(got.centroid[k], moment / volume)


def test_the_cbore_doctest_runs() -> None:
    import doctest

    from arris_gym.cq import _workplane

    assert doctest.testmod(_workplane).failed == 0

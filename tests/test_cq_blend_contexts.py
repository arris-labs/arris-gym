"""A blend in the contexts the corpus writes it in (plans/lift-edges-and-blends step 6).

Three of BenchCAD's programs as written, each worked out from how it is built (a closed form,
`test_edge_probe`'s sections swept by Pappus) and read on the oracle: a `stepped_shaft`, whose
chamfer follows a stack of extrusions (`faces(">Z").chamfer`, a face's every edge), a
`gridfinity_bin`, whose fillet precedes a cut and a union, and a `ball_knob`, whose chamfer
follows `faces("<Z").edges()` on a union that arris refuses (a sphere and a cylinder touching at
one point, ADR-0016) and Open CASCADE builds as a compound. The handwheel (a chamfer after
unions and cuts) is `test_cq_chamfer`'s. No `stepped_shaft` writes `'>Z or <Z'`: the turned
parts that do are the pins of `test_cq_chamfer`.
"""

from __future__ import annotations

import json
import math

import pytest

import fixture_cases
from arris_gym.fidelity import FidelityOutcome, OracleReport, compare
from test_cq_fillet import expected
from test_edge_probe import Measures, Part, Rim, spandrel, triangle

SHAFT = """import cadquery as cq

result = (
    cq.Workplane("XY")
    .cylinder(14.4, 25.5)
    .faces(">Z").workplane()
    .circle(12.5)
    .extrude(29.4)
    .faces(">Z").workplane()
    .circle(7.4)
    .extrude(18.3)
    .faces(">Z").workplane()
    .circle(4.1)
    .extrude(13.6)
    .faces(">Z")
    .chamfer(0.73)
    .faces("<Z")
    .faces("<Z").workplane()
    .hole(3.23)
)

# Export
show_object(result)
"""
GRID = """import cadquery as cq

result = (
    cq.Workplane("XY")
    .box(84.0, 84.0, 42.0)
    .edges("<Z")
    .fillet(1.24)
    .cut(
        cq.Workplane("XY")
            .transformed(offset=cq.Vector(0, 0, 1.1149999999999984), rotate=cq.Vector(0, 0, 0))
            .box(79.54, 79.54, 39.97)
    )
    .union(
        cq.Workplane("XY")
            .transformed(offset=cq.Vector(0, -32.17, 14.0), rotate=cq.Vector(0, 0, 0))
            .box(77.54, 15.2, 3.5)
    )
)

# Export
show_object(result)
"""
BALL = """import cadquery as cq

result = (
    cq.Workplane("XY")
    .sphere(20.14)
    .union(
        cq.Workplane("XY")
            .transformed(offset=cq.Vector(0.0, 0.0, -56.4), rotate=cq.Vector(0, 0, 0))
            .cylinder(72.52, 7.25)
    )
    .faces("<Z")
    .edges()
    .chamfer(1.35)
)

# Export
show_object(result)
"""


def shaft() -> Measures:
    """Four cylinders stacked on the z axis, the lowest from z = -7.2, the top rim chamfered by
    0.73 and a hole of radius 1.615 along the whole axis.

    Each section is a disc of radius `r` and height `h` (volume `pi r^2 h`, area `2 pi r h` and
    the discs where it meets the next); the chamfer is a triangle of legs 0.73 swept round the
    top rim (Pappus), and the hole takes `pi a^2` over the full length 75.7 and adds its wall.
    """
    stack = [(25.5, 14.4), (12.5, 29.4), (7.4, 18.3), (4.1, 13.6)]
    a, d, top = 1.615, 0.73, 68.5
    z = -7.2
    volume = area = moment = 0.0
    for i, (r, h) in enumerate(stack):
        volume += math.pi * r * r * h
        area += 2 * math.pi * r * h
        moment += math.pi * r * r * h * (z + h / 2)
        # The step to the next cylinder, or the lid of the last, and the base's own.
        area += math.pi * (r * r - (stack[i + 1][0] ** 2 if i + 1 < len(stack) else 0.0))
        if i == 0:
            area += math.pi * r * r
        z += h
    length = top + 7.2
    hole = math.pi * a * a * length
    volume -= hole
    moment -= hole * (top - 7.2) / 2
    # The hole's mouths open the two end discs and its wall joins the surface.
    area += 2 * math.pi * a * length - 2 * math.pi * a * a
    v, ar, c = Part(
        volume,
        area,
        (0.0, 0.0, moment / volume),
        section=triangle(d),
        rims=(Rim(2 * math.pi * 4.1, 2 * math.pi, top, -1.0),),
    ).measures()
    return v, ar, c


def grid() -> Measures:
    """A box 84 x 84 x 42 with its bottom edges rounded at 1.24, a cavity (79.54 square, from
    z = -18.87 up through the top) cut, and a rib 77.54 x 15.2 x 3.5 at y = -32.17, z = 14 joined.

    The rib's far face lies on the cavity wall (y = -39.77): a contact face, which hides 2 x
    77.54 x 3.5 of the area it adds.
    """
    base = Part(
        84.0 * 84.0 * 42.0,
        2 * (84.0 * 84.0 + 2 * 84.0 * 42.0),
        (0.0, 0.0, 0.0),
        section=spandrel(1.24),
        rims=(Rim(336.0, 8.0, -21.0, 1.0),),
    ).measures()
    cavity_z0, cavity_z1, side = -18.87, 21.0, 79.54
    depth = cavity_z1 - cavity_z0
    cavity = side * side * depth
    rib = 77.54 * 15.2 * 3.5
    volume = base[0] - cavity + rib
    area = base[1] - side * side + (side * side + 4 * side * depth)
    area += 2 * (77.54 * 15.2 + 77.54 * 3.5 + 15.2 * 3.5) - 2 * 77.54 * 3.5
    moment_y = rib * -32.17
    moment_z = base[0] * base[2][2] - cavity * (cavity_z0 + cavity_z1) / 2 + rib * 14.0
    return volume, area, (0.0, moment_y / volume, moment_z / volume)


def ball() -> Measures:
    """A sphere of radius 20.14 and a cylinder of radius 7.25, 72.52 long about z = -56.4,
    touching at the sphere's pole (a compound of two solids), the cylinder's lower rim
    chamfered by 1.35 (`faces("<Z").edges()` is that one circle)."""
    big, small, length, mid, d = 20.14, 7.25, 72.52, -56.4, 1.35
    sphere = 4 / 3 * math.pi * big**3
    stem = math.pi * small * small * length
    area = 4 * math.pi * big * big + 2 * math.pi * small * small + 2 * math.pi * small * length
    return Part(
        sphere + stem,
        area,
        (0.0, 0.0, stem * mid / (sphere + stem)),
        section=triangle(d),
        rims=(Rim(2 * math.pi * small, 2 * math.pi, mid - length / 2, 1.0),),
    ).measures()


# slug -> (program, closed form, bounds, face kinds, shells, genus, what it is).
OK: dict[str, tuple[str, Measures, list[list[float]], list[list[object]], int, int, str]] = {
    "ok-blend-corpus-stepped-shaft": (
        SHAFT,
        shaft(),
        [[-25.5, -25.5, -7.2], [25.5, 25.5, 68.5]],
        [["cone", 1], ["cylinder", 5], ["plane", 5]],
        1,
        1,
        "BenchCAD's `stepped_shaft_000048_s20260505` as written: four cylinders stacked on the z "
        'axis (radii 25.5, 12.5, 7.4, 4.1), `faces(">Z").chamfer(0.73)` bevelling the top '
        "face's one rim, a hole of radius 1.615 through the whole axis",
    ),
    "ok-blend-corpus-gridfinity-bin": (
        GRID,
        grid(),
        [[-42.0, -42.0, -21.0], [42.0, 42.0, 21.0]],
        [["cylinder", 4], ["plane", 16]],
        1,
        0,
        "BenchCAD's `gridfinity_bin_000166_s20260505` as written: a box 84 x 84 x 42 with its "
        "bottom edges rounded at 1.24, an open cavity cut, a rib joined against one wall",
    ),
}
REGRESSION = "cq-ball-knob-chamfer-after-point-contact"


def recorded(slug: str) -> OracleReport:
    path = fixture_cases.ROOT / "cq" / slug / "oracle.json"
    return OracleReport.model_validate_json(path.read_text())


def fixtures() -> dict[str, fixture_cases.Case]:
    return {c.slug: c for c in fixture_cases.load("cq") if c.slug in OK}


def test_every_context_fixture_is_the_closed_form() -> None:
    committed = fixtures()
    assert sorted(committed) == sorted(OK)
    for slug, (program, measures, bounds, faces, shells, genus, note) in OK.items():
        assert committed[slug].program == program, slug
        want = expected(measures, bounds, faces, shells, genus, note)
        assert json.loads(json.dumps(committed[slug].expected)) == json.loads(json.dumps(want)), (
            slug
        )


@pytest.mark.parametrize("slug", sorted(OK))
def test_context_fixtures_agree_with_the_recorded_oracle(slug: str) -> None:
    result = fixture_cases.run(fixtures()[slug])
    report = recorded(slug)
    assert result.measures is not None
    assert report.measures is not None
    assert report.measures.solids == result.measures.shells
    assert compare(result, report).outcome is FidelityOutcome.AGREE


@pytest.mark.parametrize("slug", sorted(OK))
def test_the_oracles_reports_hold_the_closed_forms(slug: str) -> None:
    report = recorded(slug)
    assert report.measures is not None
    volume, area, centroid = OK[slug][1]
    assert fixture_cases.close(report.measures.volume, volume)
    assert fixture_cases.close(report.measures.area, area)
    for got, ideal in zip(report.measures.centroid, centroid, strict=True):
        assert fixture_cases.close(got, ideal, 1e-6)


def test_the_ball_knobs_regression_fixture_is_the_closed_form() -> None:
    (case,) = (c for c in fixture_cases.load("regression") if c.slug == REGRESSION)
    assert case.program == BALL
    volume, area, centroid = ball()
    measures = case.expected["measures"]
    assert isinstance(measures, dict)
    assert measures["volume"] == volume
    assert measures["area"] == area
    assert measures["centroid"] == list(centroid)

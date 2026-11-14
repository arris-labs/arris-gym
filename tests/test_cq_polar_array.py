"""`polarArray(radius, startAngle, angle, count)` stacks CadQuery's circle of points (ADR-0019).

A full turn is split in `count`, a partial one in `count - 1` with both ends
included, one point sits at the start angle, and a negative radius puts each
point across the centre; a bore or `circle` acts at every point as on
`pushPoints`'. The closed forms are worked out by hand from how each part is
built (`test_array_probe.PARTS` for the probe's own programs, the functions
below for the revolved part and the corpus's end cap); nothing is read from
`cq`. Each `ok-polar-array-*` fixture also has the oracle's recorded report,
and each `runtime-polar-array-*` one CadQuery's own refusal.
"""

from __future__ import annotations

import json
import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import arris_gym as ag
import arris_gym.cq as cq
import cq_array_probe as probe
import fixture_cases
from arris_gym.cq._workplane import _Points
from arris_gym.fidelity import FidelityOutcome, compare
from test_cq_hole import measures
from test_cq_rarray import cases, probe_fixture, recorded

# slug -> (probe construction, holes, posts, what it is)
SLUGS = {
    "ok-polar-array-full": (
        "polar-full",
        6,
        0,
        "`polarArray(3, 0, 360, 6)` on `>Z`: a full turn split in six, a bore through at each",
    ),
    "ok-polar-array-full-start": (
        "polar-full-start",
        4,
        0,
        "`polarArray(3, 30, 360, 4)`: four bores from 30 degrees, 90 apart",
    ),
    "ok-polar-array-full-negative": (
        "polar-full-negative",
        4,
        0,
        "`polarArray(3, 0, -360, 4)`: a full turn the other way, the same four points",
    ),
    "ok-polar-array-partial": (
        "polar-partial",
        3,
        0,
        "`polarArray(3, 0, 90, 3)`: a quarter turn split in two, both ends bored",
    ),
    "ok-polar-array-partial-start": (
        "polar-partial-start",
        3,
        0,
        "`polarArray(3, 30, 120, 3)`: from 30 to 150 degrees, both ends bored",
    ),
    "ok-polar-array-partial-negative": (
        "polar-partial-negative",
        2,
        0,
        "`polarArray(3, 0, -90, 2)`: from 0 to -90 degrees, both ends bored",
    ),
    "ok-polar-array-count-1-full": (
        "polar-count-1-full",
        1,
        0,
        "`polarArray(3, 0, 360, 1)`: one point, at the start angle",
    ),
    "ok-polar-array-count-1-partial": (
        "polar-count-1-partial",
        1,
        0,
        "`polarArray(3, 45, 90, 1)`: one point, at the start angle, not at the end",
    ),
    "ok-polar-array-radius-negative": (
        "polar-radius-negative",
        2,
        0,
        "`polarArray(-3, 0, 90, 2)`: each point across the centre, at 180 and 270 degrees",
    ),
    "ok-polar-array-radius-zero": (
        "polar-radius-zero",
        1,
        0,
        "`polarArray(0, 0, 360, 3)`: three bores at the centre, which cut one hole",
    ),
    "ok-polar-array-box-max-x": (
        "polar-side>X",
        2,
        0,
        "`polarArray(1.5, 0, 90, 2)` on `>X`, in that face's own x and y (ADR-0017)",
    ),
    "ok-polar-array-circle-extrude": (
        "polar-circle-extrude",
        0,
        4,
        "`circle(0.5).extrude(1)` at a full turn of four: a post at each point",
    ),
}
RUNTIME = {
    "runtime-polar-array-count-zero": (
        "polar-count-zero",
        "ValueError: At least 1 element required, requested 0",
    ),
    "runtime-polar-array-count-negative": (
        "polar-count-negative",
        "ValueError: At least 1 element required, requested -1",
    ),
    "runtime-polar-array-count-float": (
        "polar-count-float",
        "TypeError: 'float' object cannot be interpreted as an integer",
    ),
}
# The keywords no corpus program writes stay outside the subset.
UNSUPPORTED = {
    "unsupported-polar-array-fill": (
        'import cadquery as cq\n\nresult = cq.Workplane("XY").box(10, 8, 4).faces(">Z").workplane()'
        ".polarArray(3, 0, 90, 3, fill=False).hole(1)\nshow_object(result)\n",
        "Workplane.polarArray(num, num, num, num; fill=bool)",
    ),
    "unsupported-polar-array-rotate": (
        'import cadquery as cq\n\nresult = cq.Workplane("XY").box(10, 8, 4).faces(">Z").workplane()'
        ".polarArray(3, 0, 360, 4, rotate=False).hole(1)\nshow_object(result)\n",
        "Workplane.polarArray(num, num, num, num; rotate=bool)",
    ),
}
# The revolved cylinder of the probe (radius 5, y from 0 to 4), four bores on its `<Y`.
REVOLVED = probe.CONSTRUCTED["rev-polar-hole"]
END_CAP = """import cadquery as cq

result = (
    cq.Workplane("XY")
    .cylinder(25.15, 85.015)
    .faces(">Z").workplane()
    .hole(44.58)
    .faces(">Z").workplane()
    .polarArray(31.43, 0, 360, 6)
    .hole(7.96)
)

# Export
show_object(result)
"""


def revolved_bores() -> dict[str, object]:
    """The probe's cylinder (radius 5, y 0 to 4), four bores of 1 on a circle of 3 in its `<Y` end.

    A turn of 90 degrees puts them at (3, 0), (0, 3), (-3, 0), (0, -3) of the
    end face, 3 > 1 apart and 3.5 < 5 from the axis. Each goes through the 4:
    V = pi 25 4 - 4 pi r^2 4, r = 1/2; each bore takes two discs off the faces
    and adds its wall, A = 2 pi 25 + 2 pi 5 4 - 4 2 pi r^2 + 4 2 pi r 4. The
    four points cancel about the axis: the centroid is (0, 2, 0). 2 planes, the
    wall and four bores: 7 faces, genus 4.
    """
    r, h, big = 0.5, 4.0, 5.0
    volume = math.pi * big * big * h - 4 * math.pi * r * r * h
    return measures(
        volume,
        2 * math.pi * big * big
        + 2 * math.pi * big * h
        - 4 * 2 * math.pi * r * r
        + 4 * 2 * math.pi * r * h,
        (0, 2, 0),
        ((-5, 0, -5), (5, 4, 5)),
        7,
        [["cylinder", 5], ["plane", 2]],
        genus=4,
    )


def motor_end_cap() -> dict[str, object]:
    """BenchCAD's `motor_end_cap_000016_s20260505`: a disc of 85.015 by 25.15, a bore and six holes.

    `cylinder` is centred on the origin, z from -12.575 to 12.575. The bore of
    44.58 (r = 22.29) goes through, and so do six of 7.96 (r = 3.98) on a circle
    of 31.43: they reach 27.45 to 35.41 from the axis, clear of the bore (22.29)
    and the rim (85.015), 31.43 > 7.96 apart. V = pi h (R^2 - r1^2 - 6 r2^2); each
    bore takes two discs and adds its wall, A = 2 pi (R^2 - r1^2 - 6 r2^2) + 2 pi
    h (R + r1 + 6 r2). The six points cancel: the centroid is the origin. 2
    planes, the rim, the bore and six holes: 10 faces, genus 7.
    """
    big, h, r1, r2 = 85.015, 25.15, 22.29, 3.98
    return measures(
        math.pi * h * (big * big - r1 * r1 - 6 * r2 * r2),
        2 * math.pi * (big * big - r1 * r1 - 6 * r2 * r2) + 2 * math.pi * h * (big + r1 + 6 * r2),
        (0, 0, 0),
        ((-big, -big, -h / 2), (big, big, h / 2)),
        10,
        [["cylinder", 8], ["plane", 2]],
        genus=7,
    )


def fixture_programs() -> dict[str, tuple[str, dict[str, object], str]]:
    """Every generated `ok-polar-array-*` fixture: slug -> (program, expected measures, note)."""
    programs = probe.constructed_programs()
    found = {
        slug: (programs[name], probe_fixture(name, holes, posts), note)
        for slug, (name, holes, posts, note) in SLUGS.items()
    }
    found["ok-polar-array-revolved-min-y"] = (
        programs["rev-polar-hole"],
        revolved_bores(),
        revolved_bores.__doc__ or "",
    )
    found["ok-polar-array-corpus-motor-end-cap"] = (
        END_CAP,
        motor_end_cap(),
        motor_end_cap.__doc__ or "",
    )
    return found


def runtime_programs() -> dict[str, tuple[str, str]]:
    """Every `runtime-polar-array-*` fixture: slug -> (program text, CadQuery's last line)."""
    programs = probe.constructed_programs()
    return {slug: (programs[name], message) for slug, (name, message) in RUNTIME.items()}


def test_every_ok_polar_array_fixture_is_the_closed_form() -> None:
    committed = cases("ok-polar-array-")
    assert sorted(committed) == sorted(fixture_programs())
    for slug, (program, expected, _) in fixture_programs().items():
        assert committed[slug].program == program, slug
        got = committed[slug].expected["measures"]
        assert json.loads(json.dumps(got)) == json.loads(json.dumps(expected)), slug


@pytest.mark.parametrize("slug", sorted(fixture_programs()))
def test_ok_polar_array_fixtures_agree_with_the_recorded_oracle(slug: str) -> None:
    case = cases("ok-polar-array-")[slug]
    assert compare(fixture_cases.run(case), recorded(slug)).outcome is FidelityOutcome.AGREE


def test_the_oracles_reports_hold_the_closed_forms() -> None:
    """Open CASCADE builds the closed form's part: the same volume, area and bounds."""
    for slug, (_, expected, _) in fixture_programs().items():
        report = recorded(slug)
        assert report.measures is not None
        assert report.measures.solids == expected["shells"], slug
        assert fixture_cases.close(report.measures.volume, float(str(expected["volume"]))), slug
        assert fixture_cases.close(report.measures.area, float(str(expected["area"]))), slug


def test_every_runtime_polar_array_fixture_is_cadquerys_refusal() -> None:
    committed = cases("runtime-polar-array-")
    assert sorted(committed) == sorted(runtime_programs())
    for slug, (program, message) in runtime_programs().items():
        assert committed[slug].program == program, slug
        assert committed[slug].expected == {
            "dialect": "cq",
            "status": "runtime",
            "message": message,
        }


@pytest.mark.parametrize("slug", sorted(RUNTIME))
def test_a_count_cadquery_refuses_is_a_runtime_status_that_agrees_with_the_oracle(
    slug: str,
) -> None:
    report = recorded(slug)
    assert report.status.value == "runtime"
    assert (report.message or "").splitlines()[-1] == RUNTIME[slug][1]
    case = cases("runtime-polar-array-")[slug]
    assert compare(fixture_cases.run(case), report).outcome is FidelityOutcome.AGREE


@pytest.mark.parametrize("slug", sorted(UNSUPPORTED))
def test_a_keyword_outside_the_subset_is_unsupported_and_the_oracle_builds_it(slug: str) -> None:
    program, message = UNSUPPORTED[slug]
    case = cases("unsupported-polar-array-")[slug]
    assert case.program == program
    assert case.expected == {"dialect": "cq", "status": "unsupported_api", "message": message}
    assert recorded(slug).status.value == "ok"


def points(radius: float, start: float, turn: float, count: int) -> list[tuple[float, float]]:
    """What `polarArray(radius, start, turn, count)` stacks on a box's top face."""
    wp = cq.Workplane("XY").box(10, 10, 2).faces(">Z").workplane()
    (stacked,) = wp.polarArray(radius, start, turn, count)._stack
    assert isinstance(stacked, _Points)
    return [(u, v) for u, v, _ in stacked.points]


@pytest.mark.parametrize(
    ("args", "degrees"),
    [
        ((3, 0, 360, 6), [0, 60, 120, 180, 240, 300]),
        ((3, 30, 360, 4), [30, 120, 210, 300]),
        ((3, 0, -360, 4), [0, -90, -180, -270]),
        ((3, 0, 90, 3), [0, 45, 90]),
        ((3, 30, 120, 3), [30, 90, 150]),
        ((3, 0, -90, 2), [0, -90]),
        ((3, 45, 90, 1), [45]),
        ((-3, 0, 90, 2), [0, 90]),
    ],
)
def test_the_points_are_cadquerys_angles(
    args: tuple[float, float, float, int], degrees: list[float]
) -> None:
    """Each point is `radius` at `degrees` (a negative radius across the centre), in order."""
    got = points(*args)
    assert len(got) == len(degrees)
    for (u, v), degree in zip(got, degrees, strict=True):
        phi = math.radians(degree)
        assert fixture_cases.close(u, args[0] * math.cos(phi))
        assert fixture_cases.close(v, args[0] * math.sin(phi))


@pytest.mark.parametrize(
    ("chain", "message"),
    [
        ('.faces(">Z").polarArray(2, 0, 360, 4).hole(1)', "Workplane.polarArray on selected faces"),
        (
            ".moveTo(1, 1).polarArray(2, 0, 360, 4).hole(1)",
            "Workplane.polarArray on a pending wire",
        ),
        (".polarArray(2, 0, 360, 4).box(1, 1, 1)", "Workplane.box on a stack of points"),
        (".polarArray(2, 0, 360, 4).extrude(1)", "Workplane.extrude on a stack of points"),
    ],
)
def test_an_array_in_a_context_outside_the_subset_is_unsupported(chain: str, message: str) -> None:
    program = f'import cadquery as cq\n\nresult = cq.Workplane("XY").box(4, 6, 8){chain}\n'
    result = ag.run(program + "show_object(result)\n", dialect="cq")
    assert result.status is ag.Status.UNSUPPORTED_API
    assert message in result.message


def test_an_array_with_no_solid_is_cadquerys_error() -> None:
    program = (
        'import cadquery as cq\n\nresult = cq.Workplane("XY").polarArray(2, 0, 360, 4).hole(1)\n'
    )
    result = ag.run(program + "show_object(result)\n", dialect="cq")
    assert result.status is ag.Status.RUNTIME
    assert "Cannot find a solid" in result.message


@settings(max_examples=40, deadline=None)
@given(
    radius=st.integers(3, 6),
    start=st.integers(0, 359),
    count=st.integers(1, 6),
    turn=st.sampled_from([360, -360]),
)
def test_every_point_of_a_full_turn_is_at_the_radius_and_a_count_th_turn_apart(
    radius: int, start: int, count: int, turn: int
) -> None:
    got = points(radius, start, turn, count)
    assert len(got) == count
    for i, (u, v) in enumerate(got):
        assert fixture_cases.close(math.hypot(u, v), radius)
        phi = math.radians(start + turn / count * i)
        assert fixture_cases.close(u, radius * math.cos(phi))
        assert fixture_cases.close(v, radius * math.sin(phi))


@settings(max_examples=30, deadline=None)
@given(
    radius=st.integers(3, 6),
    start=st.integers(0, 359),
    count=st.integers(1, 6),
    diameter=st.sampled_from([1.0, 2.0]),
    height=st.integers(2, 6),
)
def test_holes_on_a_polar_array_on_a_disc_are_the_closed_form(
    radius: int, start: int, count: int, diameter: float, height: int
) -> None:
    """Volume pi h (R^2 - n d^2 / 4) for a disc of R = 10 and h in 2..6, `count` holes through.

    The holes (d <= 2) reach 7 from the axis, inside the rim, and are 2 r sin(pi
    / n) >= 3 apart at the nearest (n = 6, r = 3): clear of one another. The
    points are spaced evenly about the axis, so the centroid stays on it.
    """
    program = (
        "import cadquery as cq\n\nresult = (\n"
        f'    cq.Workplane("XY").cylinder({height}, 10).faces(">Z").workplane()\n'
        f"    .polarArray({radius}, {start}, 360, {count}).hole({diameter})\n)\n"
        "show_object(result)\n"
    )
    result = ag.run(program, dialect="cq")
    assert result.status is ag.Status.OK, result.message
    assert result.measures is not None
    volume = math.pi * height * (100 - count * diameter * diameter / 4)
    assert fixture_cases.close(result.measures.volume, volume)
    assert result.measures.genus == count
    assert fixture_cases.close(result.measures.centroid[2], 0.0)
    if count > 1:
        assert fixture_cases.close(result.measures.centroid[0], 0.0)
        assert fixture_cases.close(result.measures.centroid[1], 0.0)

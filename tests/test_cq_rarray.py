"""`rarray(xSpacing, ySpacing, xCount, yCount)` stacks CadQuery's grid of points (ADR-0019 rule 1).

The grid is centred on the plane's origin, x outer and y inner, and a bore or
`circle` acts at every point as on `pushPoints`'. The closed forms are worked
out by hand from how each part is built (`test_array_probe.PARTS` for the
probe's own programs, the functions below for the corpus's panel); nothing is
read from `cq`. Each `ok-rarray-*` fixture also has the oracle's recorded
report, and each `runtime-rarray-*` one CadQuery's own refusal.
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
from arris_gym.fidelity import FidelityOutcome, OracleReport, compare
from test_array_probe import PARTS
from test_cq_hole import measures

BOX_BOUNDS = ((-5.0, -4.0, -2.0), (5.0, 4.0, 2.0))
SLUGS = {
    # slug -> (probe construction, holes, posts, what it is)
    "ok-rarray-one-point": ("rarray-1x1", 1, 0, "a 1 x 1 grid is the plane's origin, one bore"),
    "ok-rarray-3x2": ("rarray-3x2", 6, 0, "a 3 x 2 grid on `>Z`: six bores through"),
    "ok-rarray-box-max-x": (
        "rarray-side>X",
        4,
        0,
        "a 2 x 2 grid on `>X`, in that face's own x and y (ADR-0017)",
    ),
    "ok-rarray-box-min-y": (
        "rarray-side<Y",
        6,
        0,
        "a 3 x 2 grid on `<Y`, in that face's own x and y (ADR-0017)",
    ),
    "ok-rarray-circle-extrude": (
        "rarray-circle-extrude",
        0,
        4,
        "`circle(1).extrude(1)` at a 2 x 2 grid: a post at each point",
    ),
}
RUNTIME = {
    "runtime-rarray-spacing-zero": (
        "rarray-spacing-zero",
        "ValueError: Spacing and count must be > 0 ",
    ),
    "runtime-rarray-spacing-negative": (
        "rarray-spacing-negative",
        "ValueError: Spacing and count must be > 0 ",
    ),
    "runtime-rarray-count-zero": (
        "rarray-count-zero",
        "ValueError: Spacing and count must be > 0 ",
    ),
    "runtime-rarray-count-float": (
        "rarray-count-float",
        "TypeError: 'float' object cannot be interpreted as an integer",
    ),
}
# The keywords no corpus program writes stay outside the subset.
UNSUPPORTED = {
    "unsupported-rarray-center": (
        'import cadquery as cq\n\nresult = cq.Workplane("XY").box(10, 8, 4).faces(">Z").workplane()'
        ".rarray(2, 2, 2, 2, center=False).hole(1)\nshow_object(result)\n",
        "Workplane.rarray(num, num, num, num; center=bool)",
    ),
}
PANEL = """import cadquery as cq

result = (
    cq.Workplane("XZ")
    .box(140.67, 94.15, 10.76)
    .faces(">Y").workplane()
    .rarray(54.35, 33.58, 3, 3)
    .hole(11.66)
)

# Export
show_object(result)
"""


def probe_fixture(name: str, holes: int, posts: int) -> dict[str, object]:
    """The expected measures of a probe construction: its closed form and its face counts.

    A hole takes a cylinder wall on a box of 6 planes, genus `holes`; a post
    adds its wall and its top (`6 + posts` planes, `posts` cylinders). The
    bounds are the box's, a post's top 1 above it.
    """
    volume, area, centroid = PARTS[name].measures()
    return measures(
        volume,
        area,
        centroid,
        (BOX_BOUNDS[0], (5.0, 4.0, 3.0 if posts else 2.0)),
        6 + holes + 2 * posts,
        [["cylinder", holes + posts], ["plane", 6 + posts]],
        genus=holes,
    )


def vented_panel() -> dict[str, object]:
    """BenchCAD's `vented_panel_000225_s20260505`: a 140.67 x 94.15 x 10.76 panel, nine holes.

    On `XZ` the box's local z is world -y, so its thickness 10.76 is along y and
    `>Y` is the 140.67 x 94.15 face. A 3 x 3 grid at 54.35 by 33.58 is centred
    on its origin: the holes (r = 5.83) reach 54.35 + 5.83 < 70.335 in x and
    33.58 + 5.83 < 47.075 in z, and 33.58 > 11.66 keeps them apart. All nine go
    through: V = a b t - 9 pi r^2 t; each takes two discs and adds its wall,
    A = 2 (a b + a t + b t) - 9 2 pi r^2 + 9 2 pi r t. The grid is symmetric
    about the face's centre: the centroid is the origin. 6 planes and 9
    cylinders, genus 9.
    """
    a, b, t, r = 140.67, 94.15, 10.76, 11.66 / 2
    return measures(
        a * b * t - 9 * math.pi * r * r * t,
        2 * (a * b + a * t + b * t) - 9 * 2 * math.pi * r * r + 9 * 2 * math.pi * r * t,
        (0, 0, 0),
        ((-a / 2, -t / 2, -b / 2), (a / 2, t / 2, b / 2)),
        15,
        [["cylinder", 9], ["plane", 6]],
        genus=9,
    )


def fixture_programs() -> dict[str, tuple[str, dict[str, object], str]]:
    """Every generated `ok-rarray-*` fixture: slug -> (program text, expected measures, note)."""
    programs = probe.constructed_programs()
    found = {
        slug: (programs[name], probe_fixture(name, holes, posts), note)
        for slug, (name, holes, posts, note) in SLUGS.items()
    }
    found["ok-rarray-corpus-vented-panel"] = (PANEL, vented_panel(), vented_panel.__doc__ or "")
    return found


def runtime_programs() -> dict[str, tuple[str, str]]:
    """Every `runtime-rarray-*` fixture: slug -> (program text, CadQuery's last line)."""
    programs = probe.constructed_programs()
    return {slug: (programs[name], message) for slug, (name, message) in RUNTIME.items()}


def cases(prefix: str) -> dict[str, fixture_cases.Case]:
    return {c.slug: c for c in fixture_cases.load("cq") if c.slug.startswith(prefix)}


def recorded(slug: str) -> OracleReport:
    path = fixture_cases.ROOT / "cq" / slug / "oracle.json"
    return OracleReport.model_validate_json(path.read_text())


def test_every_ok_rarray_fixture_is_the_closed_form() -> None:
    committed = cases("ok-rarray-")
    assert sorted(committed) == sorted(fixture_programs())
    for slug, (program, expected, _) in fixture_programs().items():
        assert committed[slug].program == program, slug
        got = committed[slug].expected["measures"]
        assert json.loads(json.dumps(got)) == json.loads(json.dumps(expected)), slug


@pytest.mark.parametrize("slug", sorted(fixture_programs()))
def test_ok_rarray_fixtures_agree_with_the_recorded_oracle(slug: str) -> None:
    case = cases("ok-rarray-")[slug]
    assert compare(fixture_cases.run(case), recorded(slug)).outcome is FidelityOutcome.AGREE


def test_the_oracles_reports_hold_the_closed_forms() -> None:
    """Open CASCADE builds the closed form's part: the same volume, area and bounds."""
    for slug, (_, expected, _) in fixture_programs().items():
        report = recorded(slug)
        assert report.measures is not None
        assert report.measures.solids == expected["shells"], slug
        assert fixture_cases.close(report.measures.volume, float(str(expected["volume"]))), slug
        assert fixture_cases.close(report.measures.area, float(str(expected["area"]))), slug


def test_every_runtime_rarray_fixture_is_cadquerys_refusal() -> None:
    committed = cases("runtime-rarray-")
    assert sorted(committed) == sorted(runtime_programs())
    for slug, (program, message) in runtime_programs().items():
        assert committed[slug].program == program, slug
        assert committed[slug].expected == {
            "dialect": "cq",
            "status": "runtime",
            "message": message,
        }


@pytest.mark.parametrize("slug", sorted(RUNTIME))
def test_a_value_cadquery_refuses_is_a_runtime_status_that_agrees_with_the_oracle(
    slug: str,
) -> None:
    report = recorded(slug)
    assert report.status.value == "runtime"
    assert (report.message or "").splitlines()[-1] == RUNTIME[slug][1]
    case = cases("runtime-rarray-")[slug]
    assert compare(fixture_cases.run(case), report).outcome is FidelityOutcome.AGREE


@pytest.mark.parametrize("slug", sorted(UNSUPPORTED))
def test_a_form_outside_the_subset_is_unsupported_and_the_oracle_builds_it(slug: str) -> None:
    program, message = UNSUPPORTED[slug]
    case = cases("unsupported-rarray-")[slug]
    assert case.program == program
    assert case.expected == {"dialect": "cq", "status": "unsupported_api", "message": message}
    assert recorded(slug).status.value == "ok"


def test_the_grid_is_cadquerys_points_in_its_order() -> None:
    """x outer, y inner, the grid about the origin: `xSpacing * i - xSpacing * (xCount - 1) / 2`."""
    wp = cq.Workplane("XY").box(10, 10, 2).faces(">Z").workplane()
    points = wp.rarray(3, 2, 3, 2)._stack[0].points  # type: ignore[attr-defined]
    assert points == (
        (-3.0, -1.0, 0.0),
        (-3.0, 1.0, 0.0),
        (0.0, -1.0, 0.0),
        (0.0, 1.0, 0.0),
        (3.0, -1.0, 0.0),
        (3.0, 1.0, 0.0),
    )


@pytest.mark.parametrize(
    ("chain", "message"),
    [
        ('.faces(">Z").rarray(2, 2, 2, 2).hole(1)', "Workplane.rarray on selected faces"),
        (".moveTo(1, 1).rarray(2, 2, 2, 2).hole(1)", "Workplane.rarray on a pending wire"),
        (".rarray(2, 2, 2, 2).box(1, 1, 1)", "Workplane.box on a stack of points"),
        (".rarray(2, 2, 2, 2).extrude(1)", "Workplane.extrude on a stack of points"),
    ],
)
def test_an_array_in_a_context_outside_the_subset_is_unsupported(chain: str, message: str) -> None:
    program = f'import cadquery as cq\n\nresult = cq.Workplane("XY").box(4, 6, 8){chain}\n'
    result = ag.run(program + "show_object(result)\n", dialect="cq")
    assert result.status is ag.Status.UNSUPPORTED_API
    assert message in result.message


def test_an_array_with_no_solid_is_cadquerys_error() -> None:
    program = 'import cadquery as cq\n\nresult = cq.Workplane("XY").rarray(2, 2, 2, 2).hole(1)\n'
    result = ag.run(program + "show_object(result)\n", dialect="cq")
    assert result.status is ag.Status.RUNTIME
    assert "Cannot find a solid" in result.message


@settings(max_examples=40, deadline=None)
@given(
    spacing=st.tuples(st.integers(4, 6), st.integers(4, 6)),
    counts=st.tuples(st.integers(1, 3), st.integers(1, 3)),
    diameter=st.sampled_from([1.0, 2.0, 3.0]),
    thickness=st.integers(2, 6),
)
def test_a_grid_of_holes_through_a_box_is_the_closed_form(
    spacing: tuple[int, int], counts: tuple[int, int], diameter: float, thickness: int
) -> None:
    """Volume V - n pi d^2 / 4 t for a 20 x 20 x t box.

    The grid reaches (count - 1) spacing / 2 + d / 2 <= 6 + 1.5 from the
    centre, inside the face's 10, and a spacing of 4 or more keeps holes of
    up to 3 apart. The grid is symmetric about the origin, so the centroid
    stays the centre.
    """
    n = counts[0] * counts[1]
    chain = (
        f'cq.Workplane("XY").box(20, 20, {thickness}).faces(">Z").workplane()'
        f".rarray({spacing[0]}, {spacing[1]}, {counts[0]}, {counts[1]}).hole({diameter})"
    )
    program = f"import cadquery as cq\n\nresult = {chain}\nshow_object(result)\n"
    result = ag.run(program, dialect="cq")
    assert result.status is ag.Status.OK, result.message
    assert result.measures is not None
    volume = 400.0 * thickness - n * math.pi * diameter * diameter / 4 * thickness
    assert fixture_cases.close(result.measures.volume, volume)
    assert all(fixture_cases.close(c, 0.0) for c in result.measures.centroid)
    assert result.measures.genus == n

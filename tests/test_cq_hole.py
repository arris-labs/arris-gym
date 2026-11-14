"""`hole(diameter)` bores CadQuery's cylinder from the plane (ADR-0007, read on the oracle).

CadQuery's `hole` with no depth cuts a cylinder that starts at the plane's origin
(or a `moveTo` point) and runs against the plane's normal for the diagonal of the
solid's box: material below the plane goes, material above it stays. The closed
forms are worked out by hand from that; nothing is read from `cq`.
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

Vec = tuple[float, float, float]
BOX = (4.0, 6.0, 8.0)
DIAMETER = 2.0
# The measures of a part, as `expected.json` holds them.
KINDS = {"through": [["cylinder", 1], ["plane", 6]]}


def measures(
    volume: float,
    area: float,
    centroid: Vec,
    bounds: tuple[Vec, Vec],
    faces: int,
    kinds: list[list[object]],
    shells: int = 1,
    genus: int = 0,
) -> dict[str, object]:
    return {
        "volume": volume,
        "area": area,
        "centroid": list(centroid),
        "bounds": [list(bounds[0]), list(bounds[1])],
        "faces": faces,
        "face_kinds": kinds,
        "shells": shells,
        "genus": genus,
    }


def through_box(axis: int) -> dict[str, object]:
    """A 4 x 6 x 8 box centred on the origin with a hole of diameter 2 along `axis`, through.

    The hole removes a cylinder of the box's extent `length` along the axis:
    V = V_box - pi r^2 length; it takes two discs of the faces and adds the
    cylinder's wall, A = A_box - 2 pi r^2 + 2 pi r length. It is centred, so
    the centroid stays the origin.
    """
    r = DIAMETER / 2
    length = BOX[axis]
    return measures(
        4 * 6 * 8 - math.pi * r * r * length,
        208 - 2 * math.pi * r * r + 2 * math.pi * r * length,
        (0, 0, 0),
        ((-2, -3, -4), (2, 3, 4)),
        7,
        KINDS["through"],
        genus=1,
    )


def blind_above() -> dict[str, object]:
    """`box(4, 6, 8).workplane().hole(1)`: the plane is through the box's centroid.

    The cylinder (r = 1/2) runs from z = 0 down 4 and out of the bottom: a
    blind hole in the lower half and the upper half untouched, V = 192 - pi.
    It takes the bottom disc and adds the wall and the cap at z = 0:
    A = 208 + pi d 4. Its centroid is at z = -2, so the part's is 2 pi / V.
    """
    volume = 192 - math.pi
    return measures(
        volume,
        208 + 4 * math.pi,
        (0, 0, 2 * math.pi / volume),
        ((-2, -3, -4), (2, 3, 4)),
        8,
        [["cylinder", 1], ["plane", 7]],
    )


def post_on_slab() -> dict[str, object]:
    """A 10 x 10 x 2 slab (z -1..1), a 2 x 2 x 4 post at (3, 3) (z 0..4), `hole(1)` on its top.

    The plane is the post's top, z = 4, with the parent origin on it, so the
    hole is at (0, 0) and starts in the air: it bores the slab only (2 deep).
    The union has V = 200 + 16 - 4 (the post's lower metre is inside the slab)
    and A = 280 - 4 + 24 + 4; the hole takes pi r^2 2 of volume, two discs of
    area and adds 2 pi r 2 of wall.
    """
    r = 0.5
    union = 200 + 16 - 4
    volume = union - math.pi * r * r * 2
    moment = [(16 * 3 - 4 * 3), (16 * 3 - 4 * 3), (16 * 2 - 4 * 0.5)]
    return measures(
        volume,
        304 - 2 * math.pi * r * r + 2 * math.pi * r * 2,
        (moment[0] / volume, moment[1] / volume, moment[2] / volume),
        ((-5, -5, -1), (5, 5, 4)),
        12,
        [["cylinder", 1], ["plane", 11]],
        genus=1,
    )


def hole_in_a_compound() -> dict[str, object]:
    """Two disjoint boxes, `faces(">Z")` the taller one's top, a hole of diameter 1 there.

    Box A is 2 x 2 x 2 at the origin (z -1..1), box B 2 x 2 x 4 at (5, 0, 1)
    (z -1..3). The top of B is the plane z = 3 and the hole is at (0, 0):
    through A, 2 deep. V = 8 + 16 - pi/2; A = 24 + 40 + 2 pi r 2 - 2 pi r^2.
    """
    r = 0.5
    volume = 24 - math.pi * r * r * 2
    return measures(
        volume,
        64 + 2 * math.pi * r * 2 - 2 * math.pi * r * r,
        (16 * 5 / volume, 0, 16 * 1 / volume),
        ((-1, -1, -1), (6, 1, 3)),
        13,
        [["cylinder", 1], ["plane", 12]],
        shells=2,
        genus=1,
    )


def wider_than_the_face() -> dict[str, object]:
    """A 4 x 6 x 8 box with a hole of diameter 5 through its z faces.

    The cylinder (r = 5/2) clears the y faces but not the x faces (|x| = 2):
    it takes from each z face the disc cut at x = +-2, area
    R = 4 (3/2 + (r^2 / 2) asin(4/5)) = 6 + 12.5 asin(0.8), and a strip of
    chord 3 from each x face; its wall is two arcs of r (pi - 2 acos(0.8)).
    The hole spans the box from the y = 3/2 cut to the y = -3/2 one, so it
    leaves two pieces; each z face and each x face is two faces, 12 in all.
    """
    r = 2.5
    area_cut = 6 + 12.5 * math.asin(0.8)
    arc = 2 * r * (math.pi - 2 * math.acos(0.8))
    return measures(
        192 - 8 * area_cut,
        208 - 2 * area_cut - 2 * 3 * 8 + arc * 8,
        (0, 0, 0),
        ((-2, -3, -4), (2, 3, 4)),
        12,
        [["cylinder", 2], ["plane", 10]],
        shells=2,
    )


def hex_standoff() -> dict[str, object]:
    """BenchCAD's `hex_standoff_000011_s20260507`: a hexagonal prism with a bore of 3.28.

    The hexagon has circumdiameter 6.351 (R = 3.1755, area 3 sqrt 3 / 2 R^2, a
    vertex on +x) on `XZ`, extruded 19.67 along -y; the bore, r = 1.64, runs its
    whole length from the `>Y` face. V = (A_hex - pi r^2) h, A = 2 (A_hex - pi r^2)
    + 6 R h + 2 pi r h.
    """
    big = 6.351 / 2
    r = 3.28 / 2
    h = 19.67
    hexagon = 3 * math.sqrt(3) / 2 * big * big
    return measures(
        (hexagon - math.pi * r * r) * h,
        2 * (hexagon - math.pi * r * r) + 6 * big * h + 2 * math.pi * r * h,
        (0, -h / 2, 0),
        ((-big, -h, -big * math.sqrt(3) / 2), (big, 0, big * math.sqrt(3) / 2)),
        9,
        [["cylinder", 1], ["plane", 8]],
        genus=1,
    )


def zero_diameter() -> dict[str, object]:
    """`hole(0)` cuts nothing: the 4 x 6 x 8 box, as CadQuery's cut of a null cylinder leaves it."""
    box = ((-2.0, -3.0, -4.0), (2.0, 3.0, 4.0))
    return measures(192, 208, (0, 0, 0), box, 6, [["plane", 6]])


BASE = 'cq.Workplane("XY").box(4, 6, 8)'
HEX_STANDOFF = """import cadquery as cq

result = (
    cq.Workplane("XZ")
    .polygon(6, 6.351)
    .extrude(19.67)
    .faces(">Y").workplane()
    .hole(3.28)
)

# Export
show_object(result)
"""


def wrap(chain: str) -> str:
    return f"import cadquery as cq\n\nresult = (\n    {chain}\n)\nshow_object(result)\n"


def fixture_programs() -> dict[str, tuple[str, dict[str, object], str]]:
    """Every generated `ok-hole-*` fixture: slug -> (program text, expected measures, note)."""
    found: dict[str, tuple[str, dict[str, object], str]] = {}
    for selector, slug in SELECTOR_SLUG.items():
        axis = "XYZ".index(selector[1])
        found[f"ok-hole-box-{slug}"] = (
            wrap(f'{BASE}.faces("{selector}").workplane().hole(2)'),
            through_box(axis),
            through_box.__doc__ or "",
        )
    found["ok-hole-above-the-plane"] = (
        wrap(f"{BASE}.workplane().hole(1)"),
        blind_above(),
        blind_above.__doc__ or "",
    )
    found["ok-hole-post-top-over-the-slab"] = (
        wrap(
            'cq.Workplane("XY").box(10, 10, 2).union(\n'
            '        cq.Workplane("XY").transformed(offset=cq.Vector(3, 3, 2)).box(2, 2, 4)\n'
            '    ).faces(">Z").workplane().hole(1)'
        ),
        post_on_slab(),
        post_on_slab.__doc__ or "",
    )
    found["ok-hole-in-a-compound"] = (
        wrap(
            'cq.Workplane("XY").box(2, 2, 2).union(\n'
            '        cq.Workplane("XY").transformed(offset=cq.Vector(5, 0, 1)).box(2, 2, 4)\n'
            '    ).faces(">Z").workplane().hole(1)'
        ),
        hole_in_a_compound(),
        hole_in_a_compound.__doc__ or "",
    )
    found["ok-hole-wider-than-the-face"] = (
        wrap(f'{BASE}.faces(">Z").workplane().hole(5)'),
        wider_than_the_face(),
        wider_than_the_face.__doc__ or "",
    )
    found["ok-hole-zero-diameter"] = (
        wrap(f'{BASE}.faces(">Z").workplane().hole(0)'),
        zero_diameter(),
        zero_diameter.__doc__ or "",
    )
    found["ok-hole-corpus-hex-standoff"] = (
        HEX_STANDOFF,
        hex_standoff(),
        hex_standoff.__doc__ or "",
    )
    return found


def cases() -> dict[str, fixture_cases.Case]:
    return {
        case.slug: case for case in fixture_cases.load("cq") if case.slug.startswith("ok-hole-")
    }


def test_every_ok_hole_fixture_is_the_closed_form() -> None:
    """The committed files are exactly what `fixture_programs` computes."""
    committed = cases()
    assert sorted(committed) == sorted(fixture_programs())
    for slug, (program, expected, _) in fixture_programs().items():
        assert committed[slug].program == program, slug
        got = committed[slug].expected["measures"]
        assert json.loads(json.dumps(got)) == json.loads(json.dumps(expected)), slug


@pytest.mark.parametrize("slug", sorted(fixture_programs()))
def test_ok_hole_fixtures_agree_with_the_recorded_oracle(slug: str) -> None:
    case = cases()[slug]
    path = fixture_cases.ROOT / "cq" / slug / "oracle.json"
    report = OracleReport.model_validate_json(path.read_text())
    assert compare(fixture_cases.run(case), report).outcome is FidelityOutcome.AGREE


def test_the_oracles_reports_hold_the_closed_forms() -> None:
    """Open CASCADE builds the closed form's part: the same volume, area, centroid and bounds."""
    for slug, (_, expected, _) in fixture_programs().items():
        path = fixture_cases.ROOT / "cq" / slug / "oracle.json"
        report = OracleReport.model_validate_json(path.read_text())
        assert report.measures is not None
        assert report.measures.solids == expected["shells"], slug
        assert fixture_cases.close(report.measures.volume, float(str(expected["volume"]))), slug
        assert fixture_cases.close(report.measures.area, float(str(expected["area"]))), slug


def test_a_negative_diameter_is_cadquerys_construction_error() -> None:
    case = next(c for c in fixture_cases.load("cq") if c.slug == "runtime-hole-negative-diameter")
    report = OracleReport.model_validate_json(
        (fixture_cases.ROOT / "cq" / case.slug / "oracle.json").read_text()
    )
    assert report.status.value == "runtime"
    assert "Standard_ConstructionError" in (report.message or "")
    assert compare(fixture_cases.run(case), report).outcome is FidelityOutcome.AGREE


def test_a_chain_without_a_solid_is_cadquerys_error() -> None:
    case = next(c for c in fixture_cases.load("cq") if c.slug == "runtime-hole-no-solid")
    report = OracleReport.model_validate_json(
        (fixture_cases.ROOT / "cq" / case.slug / "oracle.json").read_text()
    )
    assert report.message == case.expected["message"]
    assert compare(fixture_cases.run(case), report).outcome is FidelityOutcome.AGREE


@pytest.mark.parametrize(
    ("build", "message"),
    [
        (
            lambda: cq.Workplane("XY").box(2, 2, 2).faces(">Z").hole(1),
            "Workplane.hole on selected faces",
        ),
        (
            lambda: cq.Workplane("XY").box(2, 2, 2).moveTo(1, 1).lineTo(2, 2).hole(1),
            "Workplane.hole on a pending wire",
        ),
        (
            lambda: cq.Workplane("XY").box(2, 2, 2).moveTo(1, 1).hole(1),
            "Workplane.hole on a pending wire",
        ),
        (
            lambda: cq.Workplane("XY").box(2, 2, 2).hole(1),
            "Workplane.hole on a stack holding objects",
        ),
        (
            lambda: cq.Workplane("XY").box(2, 2, 2).faces(">Z").workplane().circle(1).hole(1),
            "Workplane.hole on a pending wire",
        ),
    ],
)
def test_a_hole_on_a_stack_holding_objects_is_unsupported_naming_it(
    build: object, message: str
) -> None:
    assert callable(build)
    with pytest.raises(cq.UnsupportedApi) as raised:
        build()
    assert str(raised.value) == message


def test_a_hole_that_leaves_nothing_is_the_kernels_refusal() -> None:
    """CadQuery's result is empty and its checker cannot measure it; arris refuses it, verbatim."""
    result = ag.run(wrap(f'{BASE}.faces(">Z").workplane().hole(10)'), dialect="cq")
    assert result.status is ag.Status.ARRIS_REFUSAL
    assert result.refusal is not None


@settings(max_examples=60, deadline=None)
@given(
    plane=st.sampled_from(sorted(PLANE_NORMAL)),
    size=st.tuples(*(st.integers(4, 9) for _ in range(3))),
    origin=st.tuples(*(st.integers(-6, 6) for _ in range(3))),
    selector=st.sampled_from(sorted(AXES)),
    diameter=st.sampled_from([0.5, 1.0, 1.5, 2.0, 3.0]),
)
def test_a_hole_through_a_box_is_the_closed_form(
    plane: str,
    size: tuple[int, int, int],
    origin: tuple[int, int, int],
    selector: str,
    diameter: float,
) -> None:
    """Volume V - pi d^2 / 4 length and the box's centroid, the hole centred on the face."""
    halves = world_halves(plane, (size[0], size[1], size[2]))
    axis = next(i for i in range(3) if AXES[selector][0][i])
    length = 2 * halves[axis]
    wp = cq.Workplane(plane, origin=origin).box(*size).faces(selector).workplane().hole(diameter)
    (solid,) = wp._solids()
    got = solid.measure()
    volume = size[0] * size[1] * size[2] - math.pi * diameter * diameter / 4 * length
    assert fixture_cases.close(got.volume, volume)
    assert all(fixture_cases.close(g, float(c)) for g, c in zip(got.centroid, origin, strict=True))


def test_the_hole_doctest_runs() -> None:
    import doctest

    from arris_gym.cq import _workplane

    assert doctest.testmod(_workplane).failed == 0

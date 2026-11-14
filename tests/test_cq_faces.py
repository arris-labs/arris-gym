"""`faces(sel)` and `workplane()` on one planar face place CadQuery's plane (ADR-0017).

The closed forms are worked out by hand from ADR-0017 rule 3: the plane's
normal is the selector's signed axis, x is `(0, 0, 1)` crossed with it (+x for
the z axis), y is the normal crossed with x, and the origin is the parent's
origin moved along the normal onto the face. Nothing is read from `cq`.
"""

from __future__ import annotations

import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import arris_gym as ag
import arris_gym.cq as cq
import fixture_cases
from arris_gym.cq._selector import Faces
from arris_gym.fidelity import FidelityOutcome, OracleReport, compare

Vec = tuple[float, float, float]

# selector -> (normal, x, y), written out by hand: x = (0,0,1) x normal, or +x.
AXES: dict[str, tuple[Vec, Vec, Vec]] = {
    ">Z": ((0, 0, 1), (1, 0, 0), (0, 1, 0)),
    "<Z": ((0, 0, -1), (1, 0, 0), (0, -1, 0)),
    ">X": ((1, 0, 0), (0, 1, 0), (0, 0, 1)),
    "<X": ((-1, 0, 0), (0, -1, 0), (0, 0, 1)),
    ">Y": ((0, 1, 0), (-1, 0, 0), (0, 0, 1)),
    "<Y": ((0, -1, 0), (1, 0, 0), (0, 0, 1)),
}
# What each fixture builds on its face: a triangle of this circumdiameter at
# this point of the new plane, extruded by this distance.
TRIANGLE = 1.5
POINT = (0.5, 0.25)
HEIGHT = 2.0
# The world axis a named plane's normal lies along, and a box's world half
# sizes from its (length, width, height) on that plane (x, y, normal local).
PLANE_NORMAL = {"XY": 2, "YZ": 0, "XZ": 1, "ZX": 1}


def world_halves(plane: str, size: tuple[float, float, float]) -> Vec:
    """A centred box's half sizes on the world axes, from its local x, y and normal sizes."""
    length, width, height = (s / 2 for s in size)
    return {
        "XY": (length, width, height),
        "YZ": (height, length, width),
        "XZ": (length, height, width),
        "ZX": (width, height, length),
    }[plane]


def prism_fixture(
    sizes: Vec | None,
    cylinder: tuple[float, float] | None,
    plane: str,
    centre: Vec,
    selector: str,
    halves: Vec,
) -> dict[str, object]:
    """The expected measures of a centred base with a triangular prism on its `selector` face.

    The base is centred on `centre` with half sizes `halves` along the world
    axes (a box), or a cylinder of `cylinder = (height, radius)` on `plane`.
    The parent plane's origin is `centre`, so the prism stands at `centre`
    moved onto the face, then `POINT` in the plane's x and y. It has volume
    `(3 sqrt 3 / 4) r^2 h` and lateral area `3 (r sqrt 3) h`, since its base
    lies on the face and its top replaces what the face loses.
    """
    n, x, y = AXES[selector]
    axis = next(i for i in range(3) if n[i])
    r = TRIANGLE / 2
    v_prism = 3 * math.sqrt(3) / 4 * r * r * HEIGHT
    a_prism = 3 * r * math.sqrt(3) * HEIGHT
    if cylinder is None:
        w, d, h = (2 * s for s in halves)
        v_base = w * d * h
        a_base = 2 * (w * d + d * h + w * h)
        faces = [["plane", 10]]
        count = 10
    else:
        height, radius = cylinder
        v_base = math.pi * radius * radius * height
        a_base = 2 * math.pi * radius * radius + 2 * math.pi * radius * height
        faces = [["cylinder", 1], ["plane", 6]]
        count = 7
    on_face = list(centre)
    on_face[axis] += n[axis] * halves[axis]
    start = [on_face[i] + POINT[0] * x[i] + POINT[1] * y[i] for i in range(3)]
    prism_centre = [start[i] + n[i] * HEIGHT / 2 for i in range(3)]
    total = v_base + v_prism
    low = [centre[i] - halves[i] for i in range(3)]
    high = [centre[i] + halves[i] for i in range(3)]
    if n[axis] > 0:
        high[axis] += HEIGHT
    else:
        low[axis] -= HEIGHT
    return {
        "dialect": "cq",
        "status": "ok",
        "measures": {
            "volume": total,
            "area": a_base + a_prism,
            "centroid": [
                (v_base * centre[i] + v_prism * prism_centre[i]) / total for i in range(3)
            ],
            "bounds": [low, high],
            "faces": count,
            "shells": 1,
            "genus": 0,
            "face_kinds": faces,
        },
    }


SELECTOR_SLUG = {
    ">X": "max-x",
    "<X": "min-x",
    ">Y": "max-y",
    "<Y": "min-y",
    ">Z": "max-z",
    "<Z": "min-z",
}
BOX = (4.0, 6.0, 8.0)
TURNED_CENTRE: Vec = (1.0, 2.0, 3.0)
# A box turned 90 degrees about z swaps its x and y half sizes.
TURNED_HALVES: Vec = (3.0, 2.0, 4.0)
# One cylinder per axis: (plane, selectors along its axis).
CYLINDERS = {"XY": (">Z", "<Z"), "YZ": (">X", "<X"), "XZ": (">Y", "<Y")}
CYLINDER = (6.0, 2.0)

FACES = '.faces("{sel}").workplane().moveTo(0.5, 0.25).polygon(3, 1.5).extrude(2)'


def fixture_programs() -> dict[str, tuple[str, dict[str, object]]]:
    """Every generated `ok-faces-*` fixture: slug -> (program text, expected measures)."""
    found: dict[str, tuple[str, dict[str, object]]] = {}
    for selector, slug in SELECTOR_SLUG.items():
        tail = FACES.format(sel=selector)
        halves: Vec = (BOX[0] / 2, BOX[1] / 2, BOX[2] / 2)
        found[f"ok-faces-box-{slug}"] = (
            f'result = cq.Workplane("XY").box(4, 6, 8){tail}',
            prism_fixture(BOX, None, "XY", (0, 0, 0), selector, halves),
        )
        found[f"ok-faces-turned-box-{slug}"] = (
            'result = (\n    cq.Workplane("XY")\n'
            "    .transformed(offset=cq.Vector(1, 2, 3), rotate=cq.Vector(0, 0, 90))\n"
            f"    .box(4, 6, 8)\n    {tail.strip()}\n)",
            prism_fixture(BOX, None, "XY", TURNED_CENTRE, selector, TURNED_HALVES),
        )
    for plane, selectors in CYLINDERS.items():
        for selector in selectors:
            height, radius = CYLINDER
            axis = PLANE_NORMAL[plane]
            halves = (
                height / 2 if axis == 0 else radius,
                height / 2 if axis == 1 else radius,
                height / 2 if axis == 2 else radius,
            )
            found[f"ok-faces-cylinder-{SELECTOR_SLUG[selector]}"] = (
                f'result = cq.Workplane("{plane}").cylinder(6, 2){FACES.format(sel=selector)}',
                prism_fixture(None, CYLINDER, plane, (0, 0, 0), selector, halves),
            )
    return found


def test_every_ok_faces_fixture_is_the_closed_form() -> None:
    """The committed expected.json files are exactly what `fixture_programs` computes."""
    import json

    committed = {
        case.slug: case
        for case in fixture_cases.load("cq")
        if case.slug.startswith("ok-faces-") and case.slug != "ok-faces-bolt-head"
    }
    assert sorted(committed) == sorted(fixture_programs())
    for slug, (program, expected) in fixture_programs().items():
        body = committed[slug].program
        assert program in body, slug
        measures = committed[slug].expected["measures"]
        assert json.loads(json.dumps(measures)) == json.loads(json.dumps(expected["measures"]))


@pytest.mark.parametrize("slug", sorted(fixture_programs()))
def test_ok_faces_fixtures_agree_with_the_recorded_oracle(slug: str) -> None:
    case = next(c for c in fixture_cases.load("cq") if c.slug == slug)
    path = fixture_cases.ROOT / "cq" / slug / "oracle.json"
    report = OracleReport.model_validate_json(path.read_text())
    assert compare(fixture_cases.run(case), report).outcome is FidelityOutcome.AGREE


def test_a_corpus_program_places_its_hexagon_on_the_cylinders_top() -> None:
    """BenchCAD's `bolt_000037_s20260505` as written: a radius-2 shaft and a hexagonal head."""
    case = next(c for c in fixture_cases.load("cq") if c.slug == "ok-faces-bolt-head")
    result = fixture_cases.run(case)
    assert result.status is ag.Status.OK
    assert result.measures is not None
    head = 3 * math.sqrt(3) / 2 * (8.08 / 2) ** 2 * 2.8
    assert result.measures.volume == pytest.approx(math.pi * 4 * 25 + head, rel=1e-9)
    assert result.measures.centroid[2] == pytest.approx(
        (math.pi * 4 * 25 * 12.5 + head * (25 + 1.4)) / (math.pi * 4 * 25 + head), rel=1e-9
    )


def plane_of(wp: cq.Workplane) -> tuple[Vec, Vec, Vec, Vec]:
    plane = wp._plane
    return plane.origin, plane.x, plane.y, plane.z


def assert_close(got: Vec, want: Vec) -> None:
    assert got == pytest.approx(want, abs=1e-9)


@settings(max_examples=80, deadline=None)
@given(
    plane=st.sampled_from(sorted(PLANE_NORMAL)),
    size=st.tuples(*(st.integers(2, 9) for _ in range(3))),
    origin=st.tuples(*(st.integers(-6, 6) for _ in range(3))),
    selector=st.sampled_from(sorted(AXES)),
)
def test_a_box_face_places_the_new_plane_by_the_closed_form(
    plane: str, size: tuple[int, int, int], origin: tuple[int, int, int], selector: str
) -> None:
    halves = world_halves(plane, (size[0], size[1], size[2]))
    normal, x, y = AXES[selector]
    axis = next(i for i in range(3) if normal[i])
    want_origin = [float(c) for c in origin]
    want_origin[axis] += normal[axis] * halves[axis]
    wp = cq.Workplane(plane, origin=origin).box(*size).faces(selector).workplane()
    got_origin, got_x, got_y, got_z = plane_of(wp)
    assert_close(got_origin, (want_origin[0], want_origin[1], want_origin[2]))
    assert_close(got_x, x)
    assert_close(got_y, y)
    assert_close(got_z, normal)


@settings(max_examples=40, deadline=None)
@given(
    plane=st.sampled_from(sorted(CYLINDERS)),
    height=st.integers(1, 9),
    radius=st.integers(1, 5),
    origin=st.tuples(*(st.integers(-6, 6) for _ in range(3))),
    which=st.integers(0, 1),
)
def test_a_cylinder_disc_places_the_new_plane_by_the_closed_form(
    plane: str, height: int, radius: int, origin: tuple[int, int, int], which: int
) -> None:
    selector = CYLINDERS[plane][which]
    normal, x, y = AXES[selector]
    axis = PLANE_NORMAL[plane]
    want_origin = [float(c) for c in origin]
    want_origin[axis] += normal[axis] * height / 2
    wp = cq.Workplane(plane, origin=origin).cylinder(height, radius).faces(selector).workplane()
    got_origin, got_x, got_y, got_z = plane_of(wp)
    assert_close(got_origin, (want_origin[0], want_origin[1], want_origin[2]))
    assert_close(got_x, x)
    assert_close(got_y, y)
    assert_close(got_z, normal)


def kept(wp: cq.Workplane) -> int:
    (selected,) = wp._stack
    assert isinstance(selected, Faces)
    return len(selected.faces)


def test_a_stepped_part_keeps_only_the_faces_at_the_extreme() -> None:
    # A 10 x 10 x 2 slab (z from -1 to 1) with a 2 x 2 x 4 post on it: the post's top, at z = 3,
    # is the only face at the maximum; the slab's top, at z = 1, is a face with a hole.
    slab = cq.Workplane("XY").box(10, 10, 2)
    post = cq.Workplane("XY").transformed(offset=cq.Vector(0, 0, 2)).box(2, 2, 4)
    part = slab.union(post)
    top = part.faces(">Z")
    assert kept(top) == 1
    assert top.workplane()._plane.origin == pytest.approx((0, 0, 4), abs=1e-9)
    assert part.faces("<Z").workplane()._plane.origin == pytest.approx((0, 0, -1), abs=1e-9)


def test_two_coplanar_faces_are_both_kept() -> None:
    # A 10 x 10 x 2 slab cut through by a 2 x 12 x 4 slot: the top is two faces at z = 1.
    slab = cq.Workplane("XY").box(10, 10, 2)
    slot = cq.Workplane("XY").box(2, 12, 4)
    assert kept(slab.cut(slot).faces(">Z")) == 2


@pytest.mark.parametrize(
    ("build", "message"),
    [
        (lambda: cq.Workplane("XY").box(1, 1, 1).faces("|Z"), "Workplane.faces('|Z')"),
        (lambda: cq.Workplane("XY").box(1, 1, 1).faces(">Z or <Z"), "Workplane.faces('>Z or <Z')"),
        (lambda: cq.Workplane("XY").faces(">Z"), "Workplane.faces on an empty stack"),
        (
            lambda: cq.Workplane("XY").moveTo(1, 1).faces(">Z"),
            "Workplane.faces on a pending wire",
        ),
        (
            lambda: cq.Workplane("XY").box(2, 2, 2).faces(">Z").faces(">Z"),
            "Workplane.faces on selected faces",
        ),
        (
            lambda: cq.Workplane("XY").box(2, 2, 2).faces(">Z").box(1, 1, 1),
            "Workplane.box on selected faces",
        ),
        (
            lambda: cq.Workplane("XY").box(2, 2, 2).faces(">Z").extrude(1),
            "Workplane.extrude on selected faces",
        ),
        (
            lambda: cq.Workplane("XY").box(2, 2, 2).faces(">Z").workplane(offset=1),
            "Workplane.workplane(offset) on a face",
        ),
        (
            lambda: (
                cq.Workplane("XY")
                .box(10, 10, 2)
                .cut(cq.Workplane("XY").box(2, 12, 4))
                .faces(">Z")
                .workplane()
            ),
            "Workplane.workplane on several faces",
        ),
        (
            lambda: cq.Workplane("XY").cylinder(6, 2).faces(">X"),
            "Workplane.faces('>X'): the selection depends on the centre of a face that arris "
            "does not give",
        ),
    ],
)
def test_what_the_subset_does_not_model_is_unsupported_naming_it(
    build: object, message: str
) -> None:
    assert callable(build)
    with pytest.raises(cq.UnsupportedApi) as raised:
        build()
    assert str(raised.value) == message


def test_a_program_reaches_the_selector_refusals_as_unsupported_api() -> None:
    result = ag.run(
        'import cadquery as cq\nresult = cq.Workplane("XY").box(1, 1, 1).faces("|Z")\n',
        dialect="cq",
    )
    assert result.status is ag.Status.UNSUPPORTED_API
    assert result.message == "Workplane.faces('|Z')"


def test_the_solid_stays_in_the_chain_after_a_face_is_selected() -> None:
    # The box (V = 96) and a cylinder of radius 1 and height 3 on its top fuse to one body.
    result = ag.run(
        'import cadquery as cq\nresult = cq.Workplane("XY").box(4, 4, 6)'
        '.faces(">Z").workplane().circle(1).extrude(3)\n',
        dialect="cq",
    )
    assert result.status is ag.Status.OK
    assert result.measures is not None
    assert result.measures.volume == pytest.approx(96 + 3 * math.pi, rel=1e-9)

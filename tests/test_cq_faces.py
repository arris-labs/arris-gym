"""`faces(sel)` and `workplane()` on one planar face place CadQuery's plane (ADR-0017).

The closed forms are worked out by hand from ADR-0017 rule 3: the plane's
normal is the selector's signed axis, x is `(0, 0, 1)` crossed with it (+x for
the z axis), y is the normal crossed with x, and the origin is the parent's
origin moved along the normal onto the face. Nothing is read from `cq`.
"""

from __future__ import annotations

import math

import arris
import arris.build
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import arris_gym as ag
import arris_gym.cq as cq
import fixture_cases
from arris_gym.cq._selector import CQ_TOLERANCE, Faces
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
        if case.slug.startswith("ok-faces-")
        and case.slug not in ("ok-faces-bolt-head", "ok-faces-coplanar-tops")
        # Step 6's are written by tests/test_cq_contexts.py.
        and not case.slug.startswith(("ok-faces-compound-", "ok-faces-workplane-offset-"))
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
            lambda: tops((-3, 1, 2), (4, 1.00005, 1)).faces(">Z").workplane(),
            "Workplane.workplane on parallel faces at different offsets",
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


# Step 4: `workplane()` on several faces and on a curved face (ADR-0017 rules 4 and 5).

CONSTRUCTED = fixture_cases.ROOT / "selectors" / "constructed.json"


def constructed(name: str) -> dict[str, object]:
    """The oracle's record of one of ADR-0017's constructions (`tests/fixtures/selectors/`)."""
    import json

    rows = json.loads(CONSTRUCTED.read_text(encoding="utf-8"))
    (row,) = [r for r in rows if r["name"] == name]
    record = row["record"]
    assert isinstance(record, dict)
    return {"program": row["program"], **record}


def tops(*boxes: tuple[float, float, float]) -> cq.Workplane:
    """ADR-0017's tops: a 10 x 2 x 1 slab, and a box of each (x, z, length) fused on it."""
    part = cq.Workplane("XY").box(10, 2, 1)
    for x, z, length in boxes:
        part = part.union(
            cq.Workplane("XY").transformed(offset=cq.Vector(x, 0, z)).box(length, 2, 1)
        )
    return part


# Each construction whose oracle record holds a plane, built here as written there.
PLANES = {
    "coplanar-tops>Z": lambda: tops((-3, 1, 2), (4, 1, 1)).faces(">Z").workplane(),
    "near-tie-outside>Z": lambda: tops((-3, 1, 2), (4, 1.00015, 1)).faces(">Z").workplane(),
    "near-tie-chain>Z": lambda: (
        tops((-3, 1, 2), (0, 1.00008, 1), (4, 1.00016, 1)).faces(">Z").workplane()
    ),
}


@pytest.mark.parametrize("name", sorted(PLANES))
def test_a_construction_places_the_oracles_plane(name: str) -> None:
    record = constructed(name)
    plane = record["plane"]
    assert isinstance(plane, dict)
    origin, x, _, z = plane_of(PLANES[name]())
    assert_close(origin, tuple(plane["origin"]))
    assert_close(x, tuple(plane["x"]))
    assert_close(z, tuple(plane["z"]))


def test_coplanar_faces_give_their_plane_in_either_order() -> None:
    # The two tops of `coplanar-tops>Z`, kept by CadQuery and by cq (ADR-0017 rule 4).
    from arris_gym.cq._selector import plane_on_faces

    selected = tops((-3, 1, 2), (4, 1, 1)).faces(">Z")
    (faces,) = selected._stack
    assert isinstance(faces, Faces)
    assert len(faces.faces) == 2
    model = faces.solid.model
    parent = arris.build.Workplane((1.0, 2.0, 3.0), (1, 0, 0), (0, 1, 0), (0, 0, 1))
    for order in (faces.faces, faces.faces[::-1]):
        plane = plane_on_faces(order, parent, model)
        assert_close(plane.origin, (1.0, 2.0, 1.5))
        assert_close(plane.z, (0.0, 0.0, 1.0))
        assert_close(plane.x, (1.0, 0.0, 0.0))


@settings(max_examples=40, deadline=None)
@given(
    size=st.tuples(st.integers(6, 12), st.integers(2, 6), st.integers(1, 4)),
    slot=st.integers(-2, 2),
    origin=st.tuples(*(st.integers(-6, 6) for _ in range(3))),
    which=st.sampled_from([">Z", "<Z"]),
)
def test_a_slotted_slab_places_one_plane_on_its_two_faces(
    size: tuple[int, int, int], slot: int, origin: tuple[int, int, int], which: str
) -> None:
    # A slab centred on `origin`, cut through by a slot 1 wide at local x = `slot`: its top and
    # its bottom are two faces each, at z = origin z +- height / 2 (ADR-0017 rule 4).
    length, width, height = size
    slab = cq.Workplane("XY", origin=origin).box(length, width, height)
    cutter = (
        cq.Workplane("XY", origin=origin)
        .transformed(offset=cq.Vector(slot, 0, 0))
        .box(1, width + 2, height + 2)
    )
    selected = slab.cut(cutter).faces(which)
    assert kept(selected) == 2
    normal, x, y = AXES[which]
    got_origin, got_x, got_y, got_z = plane_of(selected.workplane())
    assert_close(got_origin, (origin[0], origin[1], origin[2] + normal[2] * height / 2))
    assert_close(got_x, x)
    assert_close(got_y, y)
    assert_close(got_z, normal)


def coplanar_tops_expected() -> dict[str, object]:
    """`ok-faces-coplanar-tops`: `coplanar-tops>Z` with a prism at (-3, 0.25) of its plane.

    The slab (10 x 2 x 1 about the origin, V 20, A 64) carries a 2 x 2 x 1 box
    at (-3, 0, 1) and a 1 x 2 x 1 box at (4, 0, 1), each adding its area less
    twice its foot (8 and 4). Their tops are the two faces at z = 1.5, and the
    plane on them is z = 1.5 with x along +x, so the prism (circumdiameter
    1.5, height 2) stands on the first box with its centroid at (-3, 0.25,
    2.5). arris keeps the coplanar side faces the fusions leave apart: 3 on
    each y side, 2 ends, the bottom, the slab's top in 3, each box's top and
    two x sides, and the prism's 4, so 22 (the oracle merges them, 18).
    """
    r = TRIANGLE / 2
    v_prism = 3 * math.sqrt(3) / 4 * r * r * HEIGHT
    a_prism = 3 * r * math.sqrt(3) * HEIGHT
    parts = [(20.0, (0.0, 0.0, 0.0)), (4.0, (-3.0, 0.0, 1.0)), (2.0, (4.0, 0.0, 1.0))]
    parts.append((v_prism, (-3.0, 0.25, 1.5 + HEIGHT / 2)))
    total = sum(v for v, _ in parts)
    return {
        "volume": total,
        "area": 64 + (16 - 8) + (10 - 4) + a_prism,
        "centroid": [sum(v * c[i] for v, c in parts) / total for i in range(3)],
        "bounds": [[-5.0, -1.0, -0.5], [5.0, 1.0, 1.5 + HEIGHT]],
        "faces": 22,
        "shells": 1,
        "genus": 0,
        "face_kinds": [["plane", 22]],
    }


def test_the_coplanar_tops_fixture_is_its_closed_form() -> None:
    import json

    case = next(c for c in fixture_cases.load("cq") if c.slug == "ok-faces-coplanar-tops")
    assert case.program.startswith(
        'import cadquery as cq\n\nresult = (\n    cq.Workplane("XY")\n    .box(10, 2, 1)\n'
    )
    assert json.loads(json.dumps(case.expected["measures"])) == coplanar_tops_expected()


# The step 4 fixtures with a recorded oracle report beside them.
RECORDED = [
    "ok-faces-coplanar-tops",
    "runtime-faces-workplane-mixed-surfaces",
    "runtime-faces-workplane-not-coplanar",
]


@pytest.mark.parametrize("slug", RECORDED)
def test_step_4_fixtures_agree_with_the_recorded_oracle(slug: str) -> None:
    case = next(c for c in fixture_cases.load("cq") if c.slug == slug)
    path = fixture_cases.ROOT / "cq" / slug / "oracle.json"
    report = OracleReport.model_validate_json(path.read_text())
    if report.status.value == "runtime":
        assert report.message == case.expected["message"]
    assert compare(fixture_cases.run(case), report).outcome is FidelityOutcome.AGREE


# The step 4 refusals of ADR-0017's constructions: fixture -> the construction's record, and
# what CadQuery did with it (an error, or the faces it kept).
REFUSED = {
    "unsupported-faces-near-tie": "near-tie-inside>Z",
    "unsupported-faces-cylinder-side": "cylinder>X",
    "unsupported-faces-triangular-prism": "box-centre-not-mass>X",
    "unsupported-faces-half-cylinder": "half-cylinder>Z",
}


@pytest.mark.parametrize("slug", sorted(REFUSED))
def test_a_refused_construction_is_one_the_oracle_records(slug: str) -> None:
    """Each refusal stands beside its oracle record: the program as recorded (the half
    cylinder rewritten in the subset, `box(centered=)` and `mirror` being outside it) and
    what made CadQuery's answer one arris cannot give (ADR-0017 rules 2, 4 and 5)."""
    case = next(c for c in fixture_cases.load("cq") if c.slug == slug)
    record = constructed(REFUSED[slug])
    selected = record["selected"]
    assert isinstance(selected, list)
    if slug == "unsupported-faces-half-cylinder":
        # One half-cylinder face, its centre off the surface: the plane hangs on that centre.
        assert [f["type"] for f in selected] == ["CYLINDER"]
        assert selected[0]["centre_to_surface"] == pytest.approx(1 - 2 / math.pi, abs=1e-9)
        assert 'faces(">Z")' in case.program
    else:
        assert case.program == record["program"]
    if slug == "unsupported-faces-near-tie":
        # Two faces 5e-5 apart: the plane sits at their area-weighted offset.
        assert [f["centre"][2] for f in selected] == [1.50005, 1.5]
        assert isinstance(record["plane"], dict)
        assert record["plane"]["origin"][2] == pytest.approx(1.5000166666666666, abs=1e-12)
    if slug in ("unsupported-faces-cylinder-side", "unsupported-faces-triangular-prism"):
        assert "error" in record
    result = fixture_cases.run(case)
    assert result.status is ag.Status.UNSUPPORTED_API
    assert result.message == case.expected["message"]


def one_solid(part: cq.Workplane) -> arris.build.Solid:
    (solid,) = part._solids()
    return solid


def faces_of(solid: arris.build.Solid, kind: str) -> list[arris.Face]:
    model = solid.model
    return [f for f in model.faces(solid.body) if model.surface(f).kind == kind]


def test_faces_of_one_curved_surface_are_refused() -> None:
    # A tiny half cylinder cut in two across its axis: two faces of one cylinder, both
    # ranked 2r / pi high and kept by `>Z`. Open CASCADE may hold one surface as one face,
    # so the plane would hang on a centre arris does not give (rule 5).
    half = (
        cq.Workplane("YZ")
        .cylinder(0.4, 0.1)
        .cut(cq.Workplane("XY").transformed(offset=cq.Vector(0, 0, -0.5)).box(1, 1, 1))
        .cut(cq.Workplane("XY").box(0.02, 1, 1))
    )
    selected = half.faces(">Z")
    assert kept(selected) == 2
    with pytest.raises(cq.UnsupportedApi) as raised:
        selected.workplane()
    assert str(raised.value) == "Workplane.workplane on a cylinder face"


def test_curved_faces_of_two_kinds_raise_cadquerys_error() -> None:
    from arris_gym.cq._selector import NOT_PLANAR, plane_on_faces

    # A cylinder's side and a sphere are two faces in any kernel: CadQuery's error (rule 4).
    solid = one_solid(
        cq.Workplane("XY")
        .cylinder(1, 1)
        .union(cq.Workplane("XY").transformed(offset=cq.Vector(5, 0, 0)).sphere(1))
    )
    pair = [faces_of(solid, "cylinder")[0], faces_of(solid, "sphere")[0]]
    with pytest.raises(ValueError, match=NOT_PLANAR):
        plane_on_faces(pair, arris.build.Workplane.XY(), solid.model)


def test_opposite_and_unrelated_normals_follow_cadquerys_coplanar_test() -> None:
    from arris_gym.cq._selector import NOT_COPLANAR, plane_on_faces

    box = one_solid(cq.Workplane("XY").box(2, 3, 4))
    model = box.model
    by_normal = {model.surface(f).normal: f for f in faces_of(box, "plane")}
    top, bottom = by_normal[(0.0, 0.0, 1.0)], by_normal[(0.0, 0.0, -1.0)]
    # Opposite normals pass CadQuery's normal test (x agrees), so its answer needs the
    # faces' centres and its face order (rule 4).
    with pytest.raises(cq.UnsupportedApi) as raised:
        plane_on_faces([top, bottom], arris.build.Workplane.XY(), model)
    assert str(raised.value) == (
        "Workplane.workplane on faces whose co-planarity needs their centres"
    )
    # Normals along z and along x share y = 0, so the test passes there too.
    side = by_normal[(1.0, 0.0, 0.0)]
    with pytest.raises(cq.UnsupportedApi):
        plane_on_faces([top, side], arris.build.Workplane.XY(), model)
    # A box turned 30 degrees about x and z: its top's and its +x side's normals differ in
    # every component, whichever is first, so CadQuery raises.
    turned = one_solid(cq.Workplane("XY").transformed(rotate=cq.Vector(30, 0, 30)).box(2, 3, 4))
    planes = faces_of(turned, "plane")
    normals = [turned.model.surface(f).normal for f in planes]
    assert all(n is not None for n in normals)
    a = planes[0]
    na = normals[0]
    assert na is not None
    b = next(
        f
        for f, n in zip(planes, normals, strict=True)
        if n is not None and all(abs(n[k] - na[k]) >= CQ_TOLERANCE for k in range(3))
    )
    for pair in ([a, b], [b, a]):
        with pytest.raises(ValueError, match=NOT_COPLANAR):
            plane_on_faces(pair, arris.build.Workplane.XY(), turned.model)


@pytest.mark.parametrize(
    ("height", "radius", "status"),
    [
        (0.2, 0.1, ag.Status.RUNTIME),
        (0.5, 0.3, ag.Status.UNSUPPORTED_API),
        (1, 0.5, ag.Status.UNSUPPORTED_API),
        (2, 1, ag.Status.UNSUPPORTED_API),
        (20, 10, ag.Status.UNSUPPORTED_API),
    ],
)
def test_rule_4s_error_is_reached_only_on_a_small_part(
    height: float, radius: float, status: ag.Status
) -> None:
    # A cylinder's `>X`: its side's centre lies on the axis and ties with both discs', all
    # three estimated, so CadQuery raises its not-planar `ValueError` at every size. The tie
    # holds within the margin (1e-4 of the box diagonal, twice over for two estimated keys,
    # against an absolute CQ_TOLERANCE) only for a diagonal under 0.5: 0.35 here for
    # (0.2, 0.1), 0.98 for (0.5, 0.3). ADR-0017's 2026-11-14 amendment.
    from arris_gym.cq._selector import NOT_PLANAR

    diagonal = math.sqrt(2 * (2 * radius) ** 2 + height**2)
    assert (diagonal < 0.5) is (status is ag.Status.RUNTIME)
    result = ag.run(
        "import cadquery as cq\n"
        f'result = cq.Workplane("XY").cylinder({height}, {radius}).faces(">X").workplane()\n',
        dialect="cq",
    )
    assert result.status is status, result.message
    if status is ag.Status.RUNTIME:
        assert result.message == f"ValueError: {NOT_PLANAR}"
    else:
        assert result.message == (
            "Workplane.faces('>X'): the selection depends on the centre of a face that arris "
            "does not give"
        )


def test_the_selector_doctests_run() -> None:
    import doctest

    from arris_gym.cq import _selector

    assert doctest.testmod(_selector).failed == 0

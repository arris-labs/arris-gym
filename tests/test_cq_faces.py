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
from arris_gym.cq._selector import CQ_TOLERANCE, Edges, Faces
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
        and case.slug not in ("ok-faces-bolt-head", "ok-faces-coplanar-tops", "ok-faces-near-tie")
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
    return len(selected.groups)


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
            lambda: cq.Workplane("XY").box(2, 2, 2).faces(">Z").box(1, 1, 1),
            "Workplane.box on selected faces",
        ),
        (
            lambda: cq.Workplane("XY").box(2, 2, 2).faces(">Z").extrude(1),
            "Workplane.extrude on selected faces",
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
    "near-tie-inside>Z": lambda: tops((-3, 1, 2), (4, 1.00005, 1)).faces(">Z").workplane(),
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


@pytest.mark.parametrize("name", ["slanted-coplanar>X", "slanted-apart>X"])
def test_slanted_faces_place_the_oracles_plane(name: str) -> None:
    part = cq.Workplane("XY").polyline([(0, 0), (4, 0), (6, 3), (0, 3)]).close().extrude(10)
    part = part.cut(cq.Workplane("XY", origin=(5, 1.5, 5)).box(6, 6, 2))
    if name == "slanted-apart>X":
        part = part.cut(cq.Workplane("XY", origin=(5, 1.5, 9)).box(6, 6, 2))
    selected = part.faces(">X")
    assert kept(selected) == 2
    plane = constructed(name)["plane"]
    assert isinstance(plane, dict)
    origin, x, _, z = plane_of(selected.workplane())
    assert_close(origin, tuple(plane["origin"]))
    assert_close(x, tuple(plane["x"]))
    assert_close(z, tuple(plane["z"]))


@pytest.mark.parametrize("gap", [0, 0.00005])
def test_parallel_faces_give_the_area_weighted_plane_in_either_order(gap: float) -> None:
    # The two tops have areas 4 and 2, so the higher one contributes a third of the gap.
    from arris_gym.cq._selector import plane_on_faces

    selected = tops((-3, 1, 2), (4, 1 + gap, 1)).faces(">Z")
    (faces,) = selected._stack
    assert isinstance(faces, Faces)
    assert len(faces.groups) == 2
    model = faces.solid.model
    parent = arris.build.Workplane((1.0, 2.0, 3.0), (1, 0, 0), (0, 1, 0), (0, 0, 1))
    for order in (faces.groups, faces.groups[::-1]):
        plane = plane_on_faces(order, parent, model)
        assert_close(plane.origin, (1.0, 2.0, 1.5 + gap / 3))
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


# Workplane fixtures with a recorded oracle report beside them.
RECORDED = [
    "ok-faces-coplanar-tops",
    "ok-faces-near-tie",
    "runtime-faces-workplane-mixed-surfaces",
    "runtime-faces-workplane-not-coplanar",
]


@pytest.mark.parametrize("slug", RECORDED)
def test_workplane_fixtures_agree_with_the_recorded_oracle(slug: str) -> None:
    case = next(c for c in fixture_cases.load("cq") if c.slug == slug)
    path = fixture_cases.ROOT / "cq" / slug / "oracle.json"
    report = OracleReport.model_validate_json(path.read_text())
    result = fixture_cases.run(case)
    assert report.program_sha256 == result.program_sha256
    if report.status.value == "runtime":
        assert report.message == case.expected["message"]
    assert compare(result, report).outcome is FidelityOutcome.AGREE


@pytest.mark.parametrize(
    ("slug", "name"),
    [
        ("runtime-faces-cylinder-side", "cylinder>X"),
        ("runtime-faces-triangular-prism", "box-centre-not-mass>X"),
    ],
)
def test_a_construction_matches_its_oracle_record(slug: str, name: str) -> None:
    case = next(c for c in fixture_cases.load("cq") if c.slug == slug)
    record = constructed(name)
    assert case.program == record["program"]
    result = fixture_cases.run(case)
    assert result.status is ag.Status.RUNTIME
    assert result.message == record["error"] == case.expected["message"]


def test_the_half_cylinder_ranks_as_one_unified_face() -> None:
    # Rotate the recorded half-cylinder>Z about x so the trimmed side crosses
    # the arris seam. The half cylinder's centre is 2r/pi from its axis.
    record = constructed("half-cylinder>Z")
    selected = record["selected"]
    assert isinstance(selected, list)
    assert [face["type"] for face in selected] == ["CYLINDER"]
    assert selected[0]["centre"][2] == pytest.approx(2 / math.pi)
    assert selected[0]["centre_to_surface"] == pytest.approx(1 - 2 / math.pi)
    part = (
        cq.Workplane("YZ")
        .cylinder(4, 1)
        .cut(cq.Workplane("XY").transformed(offset=cq.Vector(0, -5, 0)).box(10, 10, 10))
    )
    (stack,) = part.faces(">Y").faces(">Z")._stack
    assert isinstance(stack, Faces)
    (group,) = stack.groups
    assert len(group) == 2
    model = stack.solid.model
    properties = [model.surface_properties(face) for face in group]
    area = sum(p.area for p in properties)
    assert area == pytest.approx(4 * math.pi)
    assert sum(p.area * p.centroid[1] for p in properties) / area == pytest.approx(2 / math.pi)


def test_coplanar_faces_join_transitively_in_kernel_order() -> None:
    # Each post's front shares an edge with the slab's front. The posts
    # are apart from each other, but all three fronts are one unified face.
    slab = cq.Workplane("XY").box(10, 2, 1)
    for x in (-3, 3):
        slab = slab.union(cq.Workplane("XY", origin=(x, 0, 1)).box(2, 2, 1))
    (stack,) = slab.faces(">Y").faces(">Z")._stack
    assert isinstance(stack, Faces)
    model = stack.solid.model
    expected = tuple(
        face for face in model.faces(stack.solid.body) if model.surface(face).normal == (0, 1, 0)
    )
    assert len(expected) == 3
    assert stack.groups == (expected,)
    assert_close(slab.faces(">Y").workplane()._plane.origin, (0, 1, 0))


def test_adjacent_cylinders_of_the_same_radius_keep_distinct_faces() -> None:
    # The two cylinders overlap, so their exposed sides meet along two edges,
    # but their axes are an offset apart. Symmetry puts every face key at y=0.
    left = cq.Workplane("XY", origin=(-1, 0, 0)).cylinder(4, 2)
    right = cq.Workplane("XY", origin=(1, 0, 0)).cylinder(4, 2)
    (stack,) = left.union(right).faces(">Y")._stack
    assert isinstance(stack, Faces)
    model = stack.solid.model
    cylinders = [group for group in stack.groups if model.surface(group[0]).kind == "cylinder"]
    assert len(cylinders) == 2
    for group in cylinders:
        origins = [model.surface(face).origin for face in group]
        assert all(origin is not None and origin[0] in (-1, 1) for origin in origins)
        assert all(origin == origins[0] for origin in origins)


def slot_split_side() -> cq.Workplane:
    """A slot cuts a cylinder into a positive-y and a negative-y arc."""
    return cq.Workplane("YZ").cylinder(4, 5).cut(cq.Workplane("XY").box(6, 2, 20))


@pytest.mark.parametrize(("selector", "sign", "pieces"), [(">Y", 1, 2), ("<Y", -1, 1)])
def test_slot_split_side_ranks_as_two_faces(selector: str, sign: int, pieces: int) -> None:
    # All candidate centres lie on z=0. Rank the surviving groups again on y.
    part = slot_split_side()
    (stack,) = part.faces(">Z").faces(selector)._stack
    assert isinstance(stack, Faces)
    (group,) = stack.groups
    assert len(group) == pieces
    model = stack.solid.model
    assert all(model.surface(face).kind == "cylinder" for face in group)
    properties = [model.surface_properties(face) for face in group]
    half_angle = math.acos(1 / 5)
    area = sum(p.area for p in properties)
    assert area == pytest.approx(40 * half_angle)
    assert sum(p.area * p.centroid[1] for p in properties) / area == pytest.approx(
        sign * 5 * math.sin(half_angle) / half_angle
    )


@pytest.mark.parametrize(
    ("selector", "z"),
    [(">Z", (1,)), ("<Z", (-1,)), ("|X", (-1, 1)), (">Z or <Z", (-1, 1)), ("<Y", (-1, 1))],
)
def test_edges_of_a_unified_face_omit_the_internal_seam(selector: str, z: tuple[int, ...]) -> None:
    # Each slot boundary line runs along x at y=1, z=±sqrt(24). The
    # internal seam runs along x at y=5, z=0 and must never be returned.
    (stack,) = slot_split_side().faces(">Y").edges(selector)._stack
    assert isinstance(stack, Edges)
    model = stack.solid.model
    centres = [model.curve(edge).start for edge in stack.edges]
    assert sorted(c[2] for c in centres) == pytest.approx([sign * math.sqrt(24) for sign in z])
    assert [c[1] for c in centres] == pytest.approx([1] * len(z))


@pytest.mark.parametrize(
    "operation",
    [
        "edges()",
        'edges(">X")',
        'edges("<X")',
        'edges(">Y")',
        "fillet(0.1)",
        "chamfer(0.1)",
    ],
)
def test_selection_or_blending_that_needs_a_joined_boundary_is_refused(operation: str) -> None:
    slug = "unsupported-edges-unified-face-boundary"
    case = next(c for c in fixture_cases.load("cq") if c.slug == slug)
    text = case.program.replace('edges(">X")', operation)
    result = ag.run(text, dialect="cq")
    assert result.status is ag.Status.UNSUPPORTED_API
    assert result.message.endswith(" on a split unified face boundary")


def one_solid(part: cq.Workplane) -> arris.build.Solid:
    (solid,) = part._solids()
    return solid


def faces_of(solid: arris.build.Solid, kind: str) -> list[arris.Face]:
    model = solid.model
    return [f for f in model.faces(solid.body) if model.surface(f).kind == kind]


def test_disjoint_faces_of_one_curved_surface_raise_cadquerys_error() -> None:
    # A slot across the axis separates two pieces of the half cylinder.
    # Both side faces tie at 2r / pi and remain distinct.
    half = (
        cq.Workplane("YZ")
        .cylinder(0.4, 0.1)
        .cut(cq.Workplane("XY").transformed(offset=cq.Vector(0, 0, -0.5)).box(1, 1, 1))
        .cut(cq.Workplane("XY").box(0.02, 1, 1))
    )
    selected = half.faces(">Z")
    assert kept(selected) == 2
    with pytest.raises(
        ValueError, match=r"^If multiple objects selected, they all must be planar faces\.$"
    ):
        selected.workplane()


def test_curved_faces_of_two_kinds_raise_cadquerys_error() -> None:
    from arris_gym.cq._selector import NOT_PLANAR, plane_on_faces

    # A cylinder's side and a sphere are two faces in any kernel: CadQuery's error (rule 4).
    solid = one_solid(
        cq.Workplane("XY")
        .cylinder(1, 1)
        .union(cq.Workplane("XY").transformed(offset=cq.Vector(5, 0, 0)).sphere(1))
    )
    pair = [(faces_of(solid, "cylinder")[0],), (faces_of(solid, "sphere")[0],)]
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
        plane_on_faces([(top,), (bottom,)], arris.build.Workplane.XY(), model)
    assert str(raised.value) == (
        "Workplane.workplane on faces whose co-planarity needs their centres"
    )
    # The adjacent top and side share a zero normal component. The signed
    # separation still rejects both orders, as in runtime-faces-triangular-prism.
    side = by_normal[(1.0, 0.0, 0.0)]
    for pair in ([(top,), (side,)], [(side,), (top,)]):
        with pytest.raises(ValueError, match=NOT_COPLANAR):
            plane_on_faces(pair, arris.build.Workplane.XY(), model)
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
    for pair in ([(a,), (b,)], [(b,), (a,)]):
        with pytest.raises(ValueError, match=NOT_COPLANAR):
            plane_on_faces(pair, arris.build.Workplane.XY(), turned.model)


def test_signed_centre_check_refuses_an_order_dependent_pair() -> None:
    from arris_gym.cq._selector import plane_on_faces

    # The top of the right box rejects the left box's side (positive z
    # separation), but the side accepts the top (negative x separation).
    part = one_solid(
        cq.Workplane("XY").box(2, 2, 2).union(cq.Workplane("XY", origin=(5, 0, 0)).box(2, 2, 2))
    )
    model = part.model
    planes = faces_of(part, "plane")
    top = next(
        f
        for f in planes
        if model.surface(f).normal == (0, 0, 1) and model.surface_properties(f).centroid[0] > 4
    )
    side = next(
        f
        for f in planes
        if model.surface(f).normal == (1, 0, 0) and model.surface_properties(f).centroid[0] < 2
    )
    for pair in ([(top,), (side,)], [(side,), (top,)]):
        with pytest.raises(cq.UnsupportedApi, match="co-planarity needs their centres"):
            plane_on_faces(pair, arris.build.Workplane.XY(), model)


@pytest.mark.parametrize(
    ("height", "radius"), [(0.2, 0.1), (0.5, 0.3), (1, 0.5), (2, 1), (20, 10), (2000, 1000)]
)
def test_mixed_surface_error_is_reached_at_every_tested_size(height: float, radius: float) -> None:
    # Both discs and the side have centre x = 0.
    from arris_gym.cq._selector import NOT_PLANAR

    result = ag.run(
        "import cadquery as cq\n"
        f'result = cq.Workplane("XY").cylinder({height}, {radius}).faces(">X").workplane()\n',
        dialect="cq",
    )
    assert result.status is ag.Status.RUNTIME
    assert result.message == f"ValueError: {NOT_PLANAR}"


def test_the_selector_doctests_run() -> None:
    import doctest

    from arris_gym.cq import _selector

    assert doctest.testmod(_selector).failed == 0


def _box_and_pin(height: float) -> cq.Workplane:
    """A 40 x 40 x 20 box with a cylinder of radius 5 and the given height on its axis, which
    stands `(height - 20) / 2` proud of each face: a cylinder band at that height beside the
    top face, whose centre of mass lies half of it below the cylinder's own top disc."""
    return cq.Workplane("XY").box(40, 40, 20).union(cq.Workplane("XY").cylinder(height, 5))


@pytest.mark.parametrize("proud", [0.005, 0.0025])
def test_a_thin_band_below_the_top_cluster_leaves_only_the_disc(proud: float) -> None:
    # The band's centre is proud / 2 below the disc, beyond the selector tolerance.
    top = _box_and_pin(20 + 2 * proud).faces(">Z")
    assert kept(top) == 1
    assert top.workplane()._plane.origin == pytest.approx((0, 0, 10 + proud), abs=1e-9)


def test_a_band_joins_the_cluster_started_by_the_slab_top() -> None:
    # The slab top at z=10 clusters with the band at z=10.000075. The disc
    # at z=10.00015 starts a new cluster even though it is close to the band.
    top = _box_and_pin(20.0003).faces(">Z")
    assert kept(top) == 1
    assert top.workplane()._plane.origin == pytest.approx((0, 0, 10.00015), abs=1e-9)


def test_a_band_and_disc_tie_with_the_slab_if_all_fit_the_cluster() -> None:
    # The slab top at z=10 starts the cluster and the disc lies 8e-5 above it.
    assert kept(_box_and_pin(20.00016).faces(">Z")) == 3


def test_a_band_at_the_tolerance_boundary_has_an_uncertain_rank() -> None:
    # The band's centre is CQ_TOLERANCE below the disc, within the quadrature bound.
    with pytest.raises(cq.UnsupportedApi) as raised:
        _box_and_pin(20 + 4 * CQ_TOLERANCE).faces(">Z")
    assert str(raised.value) == (
        "Workplane.faces('>Z'): the face key error bound can change the selection"
    )


@settings(max_examples=60, deadline=None)
@given(
    boxes=st.lists(st.tuples(*(st.integers(1, 8) for _ in range(3))), min_size=1, max_size=3),
    cylinders=st.lists(st.tuples(st.integers(1, 8), st.integers(1, 4)), min_size=1, max_size=3),
    origin=st.tuples(*(st.integers(-10, 10) for _ in range(3))),
    selector=st.sampled_from(tuple(AXES)),
)
def test_faces_ranks_box_and_cylinder_unions_by_closed_form_centres(
    boxes: list[tuple[int, int, int]],
    cylinders: list[tuple[int, int]],
    origin: tuple[int, int, int],
    selector: str,
) -> None:
    # Disjoint pieces keep all their faces. Spacing along y distinguishes the
    # pieces while allowing ties on x and z. The cylinder's side ranks at its
    # axis, irrespective of radius.
    pieces: list[cq.Workplane] = []
    centres: list[Vec] = []
    for i, (length, width, height) in enumerate(boxes):
        x, y, z = origin[0], origin[1] + 12 * i, origin[2]
        pieces.append(cq.Workplane("XY", origin=(x, y, z)).box(length, width, height))
        for sign in (-1, 1):
            centres.extend(
                [
                    (x + sign * length / 2, y, z),
                    (x, y + sign * width / 2, z),
                    (x, y, z + sign * height / 2),
                ]
            )
    for i, (height, radius) in enumerate(cylinders, start=len(boxes)):
        x, y, z = origin[0], origin[1] + 12 * i, origin[2]
        pieces.append(cq.Workplane("YZ", origin=(x, y, z)).cylinder(height, radius))
        centres.extend([(x, y, z), (x - height / 2, y, z), (x + height / 2, y, z)])
    part = pieces[0]
    for piece in pieces[1:]:
        part = part.union(piece)

    axis = "XYZ".index(selector[1])
    extreme = max if selector[0] == ">" else min
    edge = extreme(c[axis] for c in centres)
    expected = sorted(c for c in centres if abs(c[axis] - edge) <= CQ_TOLERANCE)
    (selected,) = part.faces(selector)._stack
    assert isinstance(selected, Faces)
    observed = sorted(
        tuple(round(v, 9) for v in selected.solid.model.surface_properties(face).centroid)
        for (face,) in selected.groups
    )
    assert observed == expected

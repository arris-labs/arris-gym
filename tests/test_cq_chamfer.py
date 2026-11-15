"""`chamfer(length)` bevels the stack's edges in one `Solid.chamfer` (ADR-0020 rule 5).

The closed forms are the blends' of `test_edge_probe` (a triangle swept along each run of
edges, Pappus's rule, mitred at a box's corners), worked out from how each part is built;
nothing is read from `cq`. Each `ok-chamfer-*` fixture has the oracle's recorded report beside
it and agrees with it; each `runtime-chamfer-*` one is CadQuery's refusal and each
`arris-refusal-chamfer-*` one a length Open CASCADE refuses with `StdFail_NotDone` and arris
with its own words: both fail. The corpus programs are BenchCAD's, as written: a dowel pin, a
clevis pin along y, a washer and a spacer ring along x by closed form (`'>Z or <Z'` across a
turned part's axis, its seams placed where Open CASCADE puts them: ADR-0020 rule 2, amended),
and a handwheel (a union of spokes) by the oracle's own measures, where no closed form is at
hand, held to the recorded report.
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
from test_cq_fillet import (
    BOX_BOUNDS,
    BOX_TEN,
    CYLINDER,
    CYLINDER_BOUNDS,
    HEAD,
    NOT_DONE,
    PAIR,
    PLATE,
    PLATE_BOUNDS,
    TAIL,
    TUBE_BOUNDS,
    expected,
)
from test_edge_probe import PARTS, Measures, Part, Rim, triangle

CORPUS_DOWEL = """import cadquery as cq

result = (
    cq.Workplane("XY")
    .cylinder(26.5, 1.105)
    .edges(">Z or <Z")
    .chamfer(0.33)
    .faces(">Z").workplane()
    .hole(0.66, depth=0.792)
)

# Export
show_object(result)
"""
CORPUS_HANDWHEEL = """import cadquery as cq

result = (
    cq.Workplane("YZ")
    .union(
        cq.Workplane("YZ")
            .transformed(offset=cq.Vector(0.0, 0.0, 0.0), rotate=cq.Vector(0.0, 0.0, 0.0))
            .cylinder(26.08, 13.04)
    )
    .union(
        cq.Workplane("YZ")
            .transformed(offset=cq.Vector(0.0, 0.0, 16.76), rotate=cq.Vector(0.0, 0.0, 0.0))
            .cylinder(16.76, 58.21)
    )
    .cut(
        cq.Workplane("YZ")
            .transformed(offset=cq.Vector(0.0, 0.0, 0.0), rotate=cq.Vector(0.0, 0.0, 0.0))
            .cylinder(30.08, 5.59)
    )
    .cut(
        cq.Workplane("YZ")
            .transformed(offset=cq.Vector(0.0, 0.0, 16.76), rotate=cq.Vector(0.0, 0.0, 0.0))
            .cylinder(20.76, 44.24)
    )
    .union(
        cq.Workplane("YZ")
            .transformed(offset=cq.Vector(0.0, 0.0, 0.0), rotate=cq.Vector(0.0, 0.0, 0.0))
            .transformed(offset=cq.Vector(0.0, 0.0, 0.0), rotate=cq.Vector(90.0, 0.0, 0.0))
            .polyline([[11.04, -11.04], [11.04, 11.04], [46.24, 23.14], [46.24, 10.38]])
            .close()
            .extrude(3.26, both=True)
    )
    .union(
        cq.Workplane("YZ")
            .transformed(offset=cq.Vector(0.0, 0.0, 0.0), rotate=cq.Vector(0.0, 0.0, 120.0))
            .transformed(offset=cq.Vector(0.0, 0.0, 0.0), rotate=cq.Vector(90.0, 0.0, 0.0))
            .polyline([[11.04, -11.04], [11.04, 11.04], [46.24, 23.14], [46.24, 10.38]])
            .close()
            .extrude(3.26, both=True)
    )
    .union(
        cq.Workplane("YZ")
            .transformed(offset=cq.Vector(0.0, 0.0, 0.0), rotate=cq.Vector(0.0, 0.0, 240.0))
            .transformed(offset=cq.Vector(0.0, 0.0, 0.0), rotate=cq.Vector(90.0, 0.0, 0.0))
            .polyline([[11.04, -11.04], [11.04, 11.04], [46.24, 23.14], [46.24, 10.38]])
            .close()
            .extrude(3.26, both=True)
    )
    .union(
        cq.Workplane("YZ")
            .transformed(offset=cq.Vector(51.225, 0.0, 29.14), rotate=cq.Vector(0.0, 0.0, 0.0))
            .cylinder(8.0, 6.0)
    )
    .union(
        cq.Workplane("YZ")
            .transformed(offset=cq.Vector(51.225, 0.0, 59.41), rotate=cq.Vector(0.0, 0.0, 0.0))
            .cylinder(52.54, 9.6)
    )
    .edges(">X")
    .chamfer(3.2)
)

# Export
show_object(result)
"""
# A pin along the y axis: `'>Z or <Z'` ranks its seam, at the height of the axis on the
# plane's +x, with the two rims (ADR-0020 rule 2, amended).
CORPUS_CLEVIS = """import cadquery as cq

result = (
    cq.Workplane("XZ")
    .cylinder(42.77, 5.94)
    .edges(">Z or <Z")
    .chamfer(1.19)
)

# Export
show_object(result)
"""
# A washer along x: the wall's seam on the plane's +y, the bore's on -y of the face's
# plane, both at the height of the axis, so `'>Z or <Z'` keeps the four rims and both seams.
CORPUS_WASHER = """import cadquery as cq

result = (
    cq.Workplane("YZ")
    .cylinder(5.0, 30.0)
    .faces(">X").workplane()
    .hole(34.0)
    .edges(">Z or <Z")
    .chamfer(0.4)
)

# Export
show_object(result)
"""
# The same with the disc swept by `extrude` from x = 0 to 0.43.
CORPUS_SPACER = """import cadquery as cq

result = (
    cq.Workplane("YZ")
    .circle(17.915)
    .extrude(0.43)
    .faces(">X").workplane()
    .hole(25.59)
    .edges(">Z or <Z")
    .chamfer(0.13)
)

# Export
show_object(result)
"""


def dowel() -> Measures:
    """A pin of radius 1.105 and length 26.5 on the z axis, both rims chamfered 0.33, and a
    blind hole of radius 0.33 and depth 0.792 in its top face (at z = 13.25).

    The hole removes a cylinder of volume `pi a^2 t` centred `t / 2` below the top, and adds
    its wall (2 pi a t); its floor replaces the disc of the top face it opened.
    """
    r, h, d, a, t = 1.105, 26.5, 0.33, 0.33, 0.792
    rims = (
        Rim(2 * math.pi * r, 2 * math.pi, h / 2, -1.0),
        Rim(2 * math.pi * r, 2 * math.pi, -h / 2, 1.0),
    )
    base = Part(
        math.pi * r * r * h,
        2 * math.pi * r * r + 2 * math.pi * r * h,
        (0.0, 0.0, 0.0),
        section=triangle(d),
        rims=rims,
    ).measures()
    cut = math.pi * a * a * t
    volume = base[0] - cut
    area = base[1] + 2 * math.pi * a * t
    z = (base[0] * base[2][2] - cut * (h / 2 - t / 2)) / volume
    return volume, area, (0.0, 0.0, z)


def turned(outer: float, inner: float, height: float, d: float, start: float) -> Measures:
    """A disc of radius `outer` (less a bore of radius `inner`, if any) along an axis from
    `start` to `start + height`, every rim chamfered by `d`: the closed form along z, its
    centroid on the axis at `start + height / 2` (both ends alike)."""
    rims = [
        Rim(2 * math.pi * outer, 2 * math.pi, start + height, -1.0),
        Rim(2 * math.pi * outer, 2 * math.pi, start, 1.0),
    ]
    if inner:
        rims += [
            Rim(2 * math.pi * inner, -2 * math.pi, start + height, -1.0),
            Rim(2 * math.pi * inner, -2 * math.pi, start, 1.0),
        ]
    ring = outer * outer - inner * inner
    return Part(
        math.pi * ring * height,
        2 * math.pi * ring + 2 * math.pi * (outer + inner) * height,
        (0.0, 0.0, start + height / 2),
        section=triangle(d),
        rims=rims,
    ).measures()


def along_x(m: Measures) -> Measures:
    """A closed form along z turned onto the x axis."""
    return m[0], m[1], (m[2][2], m[2][0], m[2][1])


def along_y(m: Measures) -> Measures:
    """A closed form along z turned onto the y axis."""
    return m[0], m[1], (m[2][1], m[2][2], m[2][0])


PIN_BOUNDS = [[-1.105, -1.105, -13.25], [1.105, 1.105, 13.25]]
PAIR_PLANES = 12 + 8
# slug -> (the chain, closed form, bounds, face kinds, shells, genus, what it is).
OK: dict[str, tuple[str, Measures, list[list[float]], list[list[object]], int, int, str]] = {
    "ok-chamfer-box-top": (
        f'{BOX_TEN}.edges(">Z").chamfer(1)',
        PARTS["chamfer-box>Z"],
        BOX_BOUNDS,
        [["plane", 10]],
        1,
        0,
        "the four top edges of a 10 x 8 x 4 box bevelled by 1, mitred at its corners",
    ),
    "ok-chamfer-box-vertical": (
        f'{BOX_TEN}.edges("|Z").chamfer(1)',
        PARTS["chamfer-box|Z"],
        BOX_BOUNDS,
        [["plane", 10]],
        1,
        0,
        "the four vertical edges bevelled by 1: the triangle swept 4 long",
    ),
    "ok-chamfer-cylinder-rim": (
        f'{CYLINDER}.edges(">Z").chamfer(0.5)',
        PARTS["chamfer-cylinder>Z"],
        CYLINDER_BOUNDS,
        [["cone", 1], ["cylinder", 1], ["plane", 2]],
        1,
        0,
        "the top rim of a cylinder of radius 2 bevelled by 0.5: a cone, by Pappus",
    ),
    "ok-chamfer-cylinder-rims": (
        f'{CYLINDER}.edges(">Z or <Z").chamfer(0.5)',
        PARTS["chamfer-cylinder>Z or <Z"],
        CYLINDER_BOUNDS,
        [["cone", 2], ["cylinder", 1], ["plane", 2]],
        1,
        0,
        "both rims of the cylinder, `'>Z or <Z'`: the turned part's chamfer",
    ),
    "ok-chamfer-cylinder-edges": (
        f"{CYLINDER}.edges().chamfer(0.5)",
        PARTS["chamfer-cylinder-edges"],
        CYLINDER_BOUNDS,
        [["cone", 2], ["cylinder", 1], ["plane", 2]],
        1,
        0,
        "every edge of the cylinder: the seam is passed over, as Open CASCADE does",
    ),
    "ok-chamfer-plate-hole": (
        f'{PLATE}.faces(">Z").edges().chamfer(0.5)',
        PARTS["chamfer-plate-faces>Z"],
        PLATE_BOUNDS,
        [["cone", 1], ["cylinder", 1], ["plane", 10]],
        1,
        1,
        "a plate's top face with its hole: the four edges and the hole's rim, bevelled by 0.5",
    ),
    "ok-chamfer-tube": (
        'cq.Workplane("XY").circle(3).circle(1.5).extrude(2).edges(">Z").chamfer(0.5)',
        PARTS["chamfer-tube>Z"],
        TUBE_BOUNDS,
        [["cone", 2], ["cylinder", 2], ["plane", 2]],
        1,
        1,
        "a tube's two top rims, outer and inner, bevelled by 0.5",
    ),
    "ok-chamfer-compound": (
        f'{PAIR}.edges("|Z").chamfer(0.5)',
        PARTS["chamfer-compound|Z"],
        [[-1.0, -1.0, -1.0], [6.0, 1.0, 1.0]],
        [["plane", PAIR_PLANES]],
        2,
        0,
        "two cubes that do not meet, a compound: each one's vertical edges, in one blend",
    ),
    "ok-chamfer-after-fillet": (
        f'{BOX_TEN}.edges("|Z").fillet(2).faces(">Z").edges().chamfer(0.5)',
        PARTS["chamfer-rounded>Z"],
        BOX_BOUNDS,
        [["cone", 4], ["cylinder", 4], ["plane", 10]],
        1,
        0,
        "a chamfer along the edges a fillet made (a rounded box's top)",
    ),
}
# slug -> (program text, closed form, bounds, face kinds, shells, genus, what it is).
CORPUS: dict[str, tuple[str, Measures, list[list[float]], list[list[object]], int, int, str]] = {
    "ok-chamfer-corpus-dowel-pin": (
        CORPUS_DOWEL,
        dowel(),
        PIN_BOUNDS,
        [["cone", 2], ["cylinder", 2], ["plane", 3]],
        1,
        0,
        "BenchCAD's `dowel_pin_000027_s20260505` as written: a pin of radius 1.105 and length "
        "26.5, both rims chamfered 0.33, a blind hole of radius 0.33 and depth 0.792 in its top",
    ),
    "ok-chamfer-corpus-clevis-pin": (
        CORPUS_CLEVIS,
        along_y(turned(5.94, 0.0, 42.77, 1.19, -42.77 / 2)),
        [[-5.94, -21.385, -5.94], [5.94, 21.385, 5.94]],
        [["cone", 2], ["cylinder", 1], ["plane", 2]],
        1,
        0,
        "BenchCAD's `clevis_pin_000171_s20260505` as written: a pin of radius 5.94 and length "
        "42.77 along y, both rims chamfered 1.19; its seam, on the plane's +x, ties with them",
    ),
    "ok-chamfer-corpus-washer": (
        CORPUS_WASHER,
        along_x(turned(30.0, 17.0, 5.0, 0.4, -2.5)),
        [[-2.5, -30.0, -30.0], [2.5, 30.0, 30.0]],
        [["cone", 4], ["cylinder", 2], ["plane", 2]],
        1,
        1,
        "BenchCAD's `washer_000024_s20260505` as written: radii 30 and 17, 5 thick along x, "
        "its four rims chamfered 0.4; both seams tie with them",
    ),
    "ok-chamfer-corpus-spacer-ring": (
        CORPUS_SPACER,
        along_x(turned(17.915, 12.795, 0.43, 0.13, 0.0)),
        [[0.0, -17.915, -17.915], [0.43, 17.915, 17.915]],
        [["cone", 4], ["cylinder", 2], ["plane", 2]],
        1,
        1,
        "BenchCAD's `spacer_ring_001337_s20260505` as written: radii 17.915 and 12.795, swept "
        "0.43 along x, its four rims chamfered 0.13; both seams tie with them",
    ),
}
# A corpus program with no closed form at hand: its measures are the recorded oracle's
# (`ORACLE_HELD`), the `cq` run agreeing with it by `compare`; slug -> (program, face kinds,
# shells, genus, what it is).
ORACLE_HELD: dict[str, tuple[str, list[list[object]], int, int, str]] = {
    "ok-chamfer-corpus-handwheel": (
        CORPUS_HANDWHEEL,
        [["cone", 1], ["cylinder", 6], ["plane", 21]],
        1,
        4,
        "BenchCAD's `handwheel_000006_s20260506` as written: a hub, a rim and three spokes, "
        "the outer rim of the +x end chamfered 3.2",
    ),
}
# slug -> (program text, the last line of CadQuery's error).
RUNTIME: dict[str, tuple[str, str]] = {
    "runtime-chamfer-no-solid": (
        f'{HEAD}("XY").chamfer(1){TAIL}',
        "ValueError: Cannot find a solid on the stack or in the parent chain",
    ),
    "runtime-chamfer-no-edges": (
        f'{HEAD}("XY").cylinder(4, 2).edges("|X").chamfer(0.5){TAIL}',
        "ValueError: Chamfer requires that edges be selected",
    ),
    "runtime-chamfer-seam-alone": (
        f'{HEAD}("XY").cylinder(4, 2).edges("|Z").chamfer(0.5){TAIL}',
        "ValueError: Standard_Failure: There are no suitable edges for chamfer or fillet",
    ),
}
# What the oracle says of each (its last line); cq's `ValueError` names the same failure.
ORACLE_SAYS = {
    "runtime-chamfer-no-solid": (
        "ValueError: Cannot find a solid on the stack or in the parent chain"
    ),
    "runtime-chamfer-no-edges": "ValueError: Chamfer requires that edges be selected",
    "runtime-chamfer-seam-alone": (
        "OCP.OCP.Standard.Standard_Failure: There are no suitable edges for chamfer or fillet"
    ),
}
# slug -> (program text, arris's reason); the oracle raises `NOT_DONE` for each.
REFUSED: dict[str, tuple[str, str]] = {
    "arris-refusal-chamfer-zero": (
        f'{HEAD}("XY").box(10, 8, 4).edges("|Z").chamfer(0){TAIL}',
        "distance must be positive, not 0",
    ),
    "arris-refusal-chamfer-negative": (
        f'{HEAD}("XY").box(10, 8, 4).edges("|Z").chamfer(-1){TAIL}',
        "distance must be positive, not -1",
    ),
    "arris-refusal-chamfer-past-the-faces": (
        f'{HEAD}("XY").box(10, 8, 4).edges("|Z").chamfer(4.5){TAIL}',
        "the blend leaves its face through an edge that is not the corner's own",
    ),
}


def recorded(slug: str) -> OracleReport:
    path = fixture_cases.ROOT / "cq" / slug / "oracle.json"
    return OracleReport.model_validate_json(path.read_text())


def oracle_held(slug: str) -> dict[str, object]:
    """The expected of a corpus program whose measures are the recorded oracle's."""
    _program, faces, shells, genus, note = ORACLE_HELD[slug]
    report = recorded(slug)
    assert report.measures is not None
    m = report.measures
    return expected(
        (m.volume, m.area, (m.centroid[0], m.centroid[1], m.centroid[2])),
        [list(m.bounds[0]), list(m.bounds[1])],
        faces,
        shells,
        genus,
        note,
    )


def fixture_programs() -> dict[str, tuple[str, dict[str, object]]]:
    """Every generated `ok-chamfer-*` fixture: slug -> (program text, expected)."""
    found = {
        slug: (
            f"import cadquery as cq\n\nresult = {chain}\nshow_object(result)\n",
            expected(measures, bounds, faces, shells, genus, note),
        )
        for slug, (chain, measures, bounds, faces, shells, genus, note) in OK.items()
    }
    for slug, (program, measures, bounds, faces, shells, genus, note) in CORPUS.items():
        found[slug] = (program, expected(measures, bounds, faces, shells, genus, note))
    return found


def all_ok_programs() -> dict[str, tuple[str, dict[str, object]]]:
    found = fixture_programs()
    for slug, (program, *_rest) in ORACLE_HELD.items():
        found[slug] = (program, oracle_held(slug))
    return found


def cases(prefix: str) -> dict[str, fixture_cases.Case]:
    return {c.slug: c for c in fixture_cases.load("cq") if c.slug.startswith(prefix)}


def test_every_ok_chamfer_fixture_is_its_expected() -> None:
    committed = cases("ok-chamfer-")
    programs = all_ok_programs()
    assert sorted(committed) == sorted(programs)
    for slug, (program, want) in programs.items():
        assert committed[slug].program == program, slug
        assert json.loads(json.dumps(committed[slug].expected)) == json.loads(json.dumps(want)), (
            slug
        )


@pytest.mark.parametrize("slug", sorted(fixture_programs()) + sorted(ORACLE_HELD))
def test_ok_chamfer_fixtures_agree_with_the_recorded_oracle(slug: str) -> None:
    result = fixture_cases.run(cases("ok-chamfer-")[slug])
    report = recorded(slug)
    assert report.measures is not None
    assert result.measures is not None
    assert report.measures.solids == result.measures.shells
    assert compare(result, report).outcome is FidelityOutcome.AGREE


def test_the_oracles_reports_hold_the_closed_forms() -> None:
    """Open CASCADE builds the closed form's part: the same volume, area and centroid."""
    for slug, (_, want) in fixture_programs().items():
        report = recorded(slug)
        measures = want["measures"]
        assert isinstance(measures, dict)
        assert report.measures is not None
        assert fixture_cases.close(report.measures.volume, float(measures["volume"])), slug
        assert fixture_cases.close(report.measures.area, float(measures["area"])), slug
        for got, ideal in zip(report.measures.centroid, measures["centroid"], strict=True):
            assert fixture_cases.close(got, float(ideal)), slug


def test_two_seams_no_record_places_still_block_the_or_selector() -> None:
    """The corpus washer with its bore on a polar array: CadQuery turns the bore's axes, `cq`
    does not, so neither seam is placed. Each may lie anywhere on its wall, one above the rims
    and one below, where `'>Z or <Z'` would keep the seams alone (ADR-0020 rule 2)."""
    washer = cq.Workplane("YZ").cylinder(5.0, 30.0).faces(">X").workplane()
    with pytest.raises(cq.UnsupportedApi, match=r"Workplane.edges\('>Z'\)"):
        washer.polarArray(0, 0, 360, 1).hole(34.0).edges(">Z or <Z")
    assert not cases("unsupported-chamfer-")


def test_every_runtime_chamfer_fixture_is_cadquerys_refusal() -> None:
    committed = cases("runtime-chamfer-")
    assert sorted(committed) == sorted(RUNTIME)
    for slug, (program, message) in RUNTIME.items():
        assert committed[slug].program == program, slug
        assert committed[slug].expected == {
            "dialect": "cq",
            "status": "runtime",
            "message": message,
        }
        report = recorded(slug)
        assert report.status.value == "runtime"
        assert (report.message or "").splitlines()[-1] == ORACLE_SAYS[slug]
        assert compare(fixture_cases.run(committed[slug]), report).outcome is FidelityOutcome.AGREE


def test_every_refused_length_fails_in_both_kernels_in_their_own_words() -> None:
    committed = cases("arris-refusal-chamfer-")
    assert sorted(committed) == sorted(REFUSED)
    for slug, (program, reason) in REFUSED.items():
        assert committed[slug].program == program, slug
        assert committed[slug].expected["status"] == "arris_refusal"
        assert reason in str(committed[slug].expected["message"]), slug
        report = recorded(slug)
        assert report.status.value == "runtime"
        assert (report.message or "").splitlines()[-1] == NOT_DONE
        result = fixture_cases.run(committed[slug])
        assert result.status is ag.Status.ARRIS_REFUSAL
        assert result.refusal is not None
        assert reason in result.refusal.message
        assert compare(result, report).outcome is FidelityOutcome.AGREE


def test_a_chamfer_on_a_compound_bevels_both_pieces_as_one_body() -> None:
    part = (
        cq.Workplane("XY")
        .box(2, 2, 2)
        .union(cq.Workplane("XY").transformed(offset=cq.Vector(5, 0, 0)).box(2, 2, 2))
    )
    (solid,) = part.edges("|Z").chamfer(0.5)._solids()
    assert len(solid.model.shells(solid.body)) == 2


def test_the_result_is_one_solid_on_the_stack_for_the_next_call() -> None:
    wp = cq.Workplane("XY").box(10, 8, 4).edges("|Z").chamfer(1)
    assert len(wp._solids()) == 1
    assert len(wp.faces(">Z")._stack) == 1


@pytest.mark.parametrize(
    ("chain", "message"),
    [
        (".edges().chamfer()", "Workplane.chamfer()"),
        (".edges().chamfer('1')", "Workplane.chamfer(str)"),
        (".edges().chamfer(True)", "Workplane.chamfer(bool)"),
        (".edges().chamfer(1, 2)", "Workplane.chamfer(num, num)"),
        (".edges().chamfer(length=1)", "Workplane.chamfer(length=num)"),
        (".moveTo(0, 0).chamfer(1)", "Workplane.chamfer on a pending wire"),
    ],
)
def test_a_chamfer_form_the_census_never_writes_is_unsupported(chain: str, message: str) -> None:
    program = f'import cadquery as cq\n\nresult = cq.Workplane("XY").box(4, 6, 8){chain}\n'
    result = ag.run(program + "show_object(result)\n", dialect="cq")
    assert result.status is ag.Status.UNSUPPORTED_API
    assert message in result.message


def test_the_subset_declares_chamfer_with_a_number() -> None:
    assert cq.subset().admits("Workplane.chamfer(num)")
    assert not cq.subset().admits("Workplane.chamfer(str)")


@settings(max_examples=40, deadline=None)
@given(
    radius=st.sampled_from([1.0, 1.5, 2.0, 3.0]),
    height=st.integers(4, 20),
    distance=st.sampled_from([0.25, 0.5, 0.75]),
)
def test_a_cylinders_rim_chamfered_by_d_loses_pi_d_squared_times_r_minus_d_over_3(
    radius: float, height: int, distance: float
) -> None:
    """Volume V - pi d^2 (r - d/3): the triangle of legs d swept round the rim (Pappus: its
    centroid lies d/3 in from the wall, so its area d^2/2 turns through 2 pi (r - d/3)).
    """
    result = ag.run(
        f'import cadquery as cq\n\nresult = cq.Workplane("XY").cylinder({height}, {radius})'
        f'.edges(">Z").chamfer({distance})\nshow_object(result)\n',
        dialect="cq",
    )
    assert result.status is ag.Status.OK, result.message
    assert result.measures is not None
    volume = math.pi * radius * radius * height - math.pi * distance**2 * (radius - distance / 3)
    assert fixture_cases.close(result.measures.volume, volume)
    assert result.measures.faces == 4

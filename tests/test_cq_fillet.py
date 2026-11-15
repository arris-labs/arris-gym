"""`fillet(radius)` rounds the stack's edges in one `Solid.fillet` (ADR-0020 rule 5).

The closed forms are the blends' of `test_edge_probe` (a section swept along each run of
edges, Pappus's rule, mitred at a box's corners), worked out from how each part is built;
nothing is read from `cq`. Each `ok-fillet-*` fixture has the oracle's recorded report beside
it and agrees with it; each `runtime-fillet-*` one is CadQuery's refusal and each
`arris-refusal-fillet-*` one a value Open CASCADE refuses with `StdFail_NotDone` and arris with
its own words: both fail.
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
from test_edge_probe import PARTS, Measures, Part, Rim, spandrel

HEAD = "import cadquery as cq\n\nresult = cq.Workplane"
TAIL = "\nshow_object(result)\n"
BOX_BOUNDS = [[-5.0, -4.0, -2.0], [5.0, 4.0, 2.0]]
CYLINDER_BOUNDS = [[-2.0, -2.0, -2.0], [2.0, 2.0, 2.0]]
PLATE_BOUNDS = [[-5.0, -4.0, -1.0], [5.0, 4.0, 1.0]]
TUBE_BOUNDS = [[-3.0, -3.0, 0.0], [3.0, 3.0, 2.0]]
CORPUS_WASHER = """import cadquery as cq

result = (
    cq.Workplane("YZ")
    .cylinder(1.0, 5.0)
    .faces(">X").workplane()
    .hole(5.3)
    .edges(">X")
    .fillet(0.25)
)

# Export
show_object(result)
"""


def one_edge() -> Measures:
    """A box 10 x 8 x 4 with its edge at x = 5, z = 2 (8 long) rounded at 1.

    The section off the edge is the spandrel `a` with moments `s` about the wall and the top;
    the two end faces lose `a` each, the top and the wall a strip of 1, and the arc is added:
    V = 320 - 8a, A = 304 + 8 (pi/2 - 2) - 2a, and the centroid moves by the removed moment.
    """
    s = spandrel(1.0)
    v = 320.0 - 8 * s.area
    a = 304.0 + 8 * (math.pi / 2 - 2) - 2 * s.area
    return v, a, (-8 * (5 * s.area - s.su) / v, 0.0, -8 * (2 * s.area - s.sw) / v)


def washer() -> Measures:
    """The ring of radii 2.65 and 5, 1 thick on the x axis, both rims at x = 0.5 rounded at 0.25."""
    outer, inner, thick = 5.0, 2.65, 1.0
    volume = math.pi * (outer**2 - inner**2) * thick
    area = 2 * math.pi * (outer**2 - inner**2) + 2 * math.pi * (outer + inner) * thick
    rims = (
        Rim(2 * math.pi * outer, 2 * math.pi, 0.5, -1.0),
        Rim(2 * math.pi * inner, -2 * math.pi, 0.5, -1.0),
    )
    v, a, c = Part(volume, area, (0.0, 0.0, 0.0), section=spandrel(0.25), rims=rims).measures()
    # The part's axis (z in the closed form) is the workplane's x here.
    return v, a, (c[2], 0.0, 0.0)


def expected(
    measures: Measures,
    bounds: list[list[float]],
    faces: list[list[object]],
    shells: int = 1,
    genus: int = 0,
    note: str = "",
) -> dict[str, object]:
    return {
        "dialect": "cq",
        "status": "ok",
        "measures": {
            "volume": measures[0],
            "area": measures[1],
            "centroid": list(measures[2]),
            "bounds": bounds,
            "faces": sum(int(str(n)) for _, n in faces),
            "face_kinds": faces,
            "shells": shells,
            "genus": genus,
        },
        "note": note,
    }


BOX_TEN = 'cq.Workplane("XY").box(10, 8, 4)'
CYLINDER = 'cq.Workplane("XY").cylinder(4, 2)'
PLATE = 'cq.Workplane("XY").box(10, 8, 2).faces(">Z").workplane().hole(3)'
PAIR = (
    'cq.Workplane("XY").box(2, 2, 2).union(cq.Workplane("XY")'
    ".transformed(offset=cq.Vector(5, 0, 0)).box(2, 2, 2))"
)
# slug -> (the chain, closed form, bounds, face kinds, shells, genus, what it is).
OK: dict[str, tuple[str, Measures, list[list[float]], list[list[object]], int, int, str]] = {
    "ok-fillet-box-top": (
        f'{BOX_TEN}.edges(">Z").fillet(1)',
        PARTS["fillet-box>Z"],
        BOX_BOUNDS,
        [["cylinder", 4], ["plane", 6]],
        1,
        0,
        "the four top edges of a 10 x 8 x 4 box rounded at 1, mitred at its corners",
    ),
    "ok-fillet-box-vertical": (
        f'{BOX_TEN}.edges("|Z").fillet(1)',
        PARTS["fillet-box|Z"],
        BOX_BOUNDS,
        [["cylinder", 4], ["plane", 6]],
        1,
        0,
        "the four vertical edges rounded at 1: the section swept 4 long",
    ),
    "ok-fillet-box-one-edge": (
        f'{BOX_TEN}.edges(">Z").edges(">X").fillet(1)',
        one_edge(),
        BOX_BOUNDS,
        [["cylinder", 1], ["plane", 6]],
        1,
        0,
        "one edge rounded: the section swept 8 long, the end faces losing it",
    ),
    "ok-fillet-box-faces": (
        f'{BOX_TEN}.faces(">Z").fillet(1)',
        PARTS["fillet-box-faces>Z"],
        BOX_BOUNDS,
        [["cylinder", 4], ["plane", 6]],
        1,
        0,
        "`fillet` on selected faces rounds every edge of them: the top's four",
    ),
    "ok-fillet-box-solid": (
        f"{BOX_TEN}.fillet(1)",
        PARTS["fillet-box-solid"],
        BOX_BOUNDS,
        [["cylinder", 12], ["plane", 6], ["sphere", 8]],
        1,
        0,
        "`fillet` on the solid rounds all twelve edges: the inner box grown by a ball (Steiner)",
    ),
    "ok-fillet-cylinder-rim": (
        f'{CYLINDER}.edges(">Z").fillet(0.5)',
        PARTS["fillet-cylinder>Z"],
        CYLINDER_BOUNDS,
        [["cylinder", 1], ["plane", 2], ["torus", 1]],
        1,
        0,
        "the top rim of a cylinder of radius 2 rounded at 0.5: a torus, by Pappus",
    ),
    "ok-fillet-cylinder-edges": (
        f"{CYLINDER}.edges().fillet(0.5)",
        PARTS["fillet-cylinder-edges"],
        CYLINDER_BOUNDS,
        [["cylinder", 1], ["plane", 2], ["torus", 2]],
        1,
        0,
        "every edge of the cylinder: the seam is passed over, as Open CASCADE does",
    ),
    "ok-fillet-plate-hole": (
        f'{PLATE}.faces(">Z").edges().fillet(0.5)',
        PARTS["fillet-plate-faces>Z"],
        PLATE_BOUNDS,
        [["cylinder", 5], ["plane", 6], ["torus", 1]],
        1,
        1,
        "a plate's top face with its hole: the four edges and the hole's rim, rounded at 0.5",
    ),
    "ok-fillet-tube": (
        'cq.Workplane("XY").circle(3).circle(1.5).extrude(2).edges(">Z").fillet(0.5)',
        PARTS["fillet-tube>Z"],
        TUBE_BOUNDS,
        [["cylinder", 2], ["plane", 2], ["torus", 2]],
        1,
        1,
        "a tube's two top rims, outer and inner, rounded at 0.5",
    ),
    "ok-fillet-compound": (
        f'{PAIR}.edges("|Z").fillet(0.5)',
        PARTS["fillet-compound|Z"],
        [[-1.0, -1.0, -1.0], [6.0, 1.0, 1.0]],
        [["cylinder", 8], ["plane", 12]],
        2,
        0,
        "two cubes that do not meet, a compound: each one's vertical edges, in one blend",
    ),
    "ok-fillet-then-fillet": (
        f'{BOX_TEN}.edges("|Z").fillet(2).faces(">Z").edges().fillet(0.5)',
        PARTS["fillet-rounded>Z"],
        BOX_BOUNDS,
        [["cylinder", 8], ["plane", 6], ["torus", 4]],
        1,
        0,
        "a second blend along the edges an earlier one made (a rounded box's top)",
    ),
}
# A program of the corpus as written, in `CORPUS_WASHER`.
CORPUS = "ok-fillet-corpus-washer"

# slug -> (program text, the last line of CadQuery's error).
RUNTIME: dict[str, tuple[str, str]] = {
    "runtime-fillet-no-solid": (
        f'{HEAD}("XY").fillet(1){TAIL}',
        "ValueError: Cannot find a solid on the stack or in the parent chain",
    ),
    "runtime-fillet-no-edges": (
        f'{HEAD}("XY").cylinder(4, 2).edges("|X").fillet(0.5){TAIL}',
        "ValueError: Fillets requires that edges be selected",
    ),
    "runtime-fillet-seam-alone": (
        f'{HEAD}("XY").cylinder(4, 2).edges("|Z").fillet(0.5){TAIL}',
        "ValueError: Standard_Failure: There are no suitable edges for chamfer or fillet",
    ),
}
# What the oracle says of each (its last line); cq's `ValueError` names the same failure.
ORACLE_SAYS = {
    "runtime-fillet-no-solid": (
        "ValueError: Cannot find a solid on the stack or in the parent chain"
    ),
    "runtime-fillet-no-edges": "ValueError: Fillets requires that edges be selected",
    "runtime-fillet-seam-alone": (
        "OCP.OCP.Standard.Standard_Failure: There are no suitable edges for chamfer or fillet"
    ),
}
# slug -> (program text, arris's reason); the oracle raises `NOT_DONE` for each.
REFUSED: dict[str, tuple[str, str]] = {
    "arris-refusal-fillet-zero": (
        f'{HEAD}("XY").box(10, 8, 4).edges("|Z").fillet(0){TAIL}',
        "radius must be positive, not 0",
    ),
    "arris-refusal-fillet-negative": (
        f'{HEAD}("XY").box(10, 8, 4).edges("|Z").fillet(-1){TAIL}',
        "radius must be positive, not -1",
    ),
    "arris-refusal-fillet-past-the-faces": (
        f'{HEAD}("XY").box(10, 8, 4).edges(">Z").fillet(4.5){TAIL}',
        "the blend leaves its face through an edge that is not the corner's own",
    ),
}
NOT_DONE = "OCP.OCP.StdFail.StdFail_NotDone: BRep_API: command not done"


def fixture_programs() -> dict[str, tuple[str, dict[str, object]]]:
    """Every generated `ok-fillet-*` fixture: slug -> (program text, expected)."""
    found = {
        slug: (
            f"import cadquery as cq\n\nresult = {chain}\nshow_object(result)\n",
            expected(measures, bounds, faces, shells, genus, note),
        )
        for slug, (chain, measures, bounds, faces, shells, genus, note) in OK.items()
    }
    found[CORPUS] = (
        CORPUS_WASHER,
        expected(
            washer(),
            [[-0.5, -5.0, -5.0], [0.5, 5.0, 5.0]],
            [["cylinder", 2], ["plane", 2], ["torus", 2]],
            1,
            1,
            "BenchCAD's `washer_000042_s20260505` as written: a ring of radii 2.65 and 5, 1 thick, "
            "both rims at x = 0.5 rounded at 0.25",
        ),
    )
    return found


def cases(prefix: str) -> dict[str, fixture_cases.Case]:
    return {c.slug: c for c in fixture_cases.load("cq") if c.slug.startswith(prefix)}


def recorded(slug: str) -> OracleReport:
    path = fixture_cases.ROOT / "cq" / slug / "oracle.json"
    return OracleReport.model_validate_json(path.read_text())


def test_every_ok_fillet_fixture_is_the_closed_form() -> None:
    committed = cases("ok-fillet-")
    assert sorted(committed) == sorted(fixture_programs())
    for slug, (program, want) in fixture_programs().items():
        assert committed[slug].program == program, slug
        assert json.loads(json.dumps(committed[slug].expected)) == json.loads(json.dumps(want)), (
            slug
        )


@pytest.mark.parametrize("slug", sorted(fixture_programs()))
def test_ok_fillet_fixtures_agree_with_the_recorded_oracle(slug: str) -> None:
    result = fixture_cases.run(cases("ok-fillet-")[slug])
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


def test_every_runtime_fillet_fixture_is_cadquerys_refusal() -> None:
    committed = cases("runtime-fillet-")
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


def test_every_refused_value_fails_in_both_kernels_in_their_own_words() -> None:
    committed = cases("arris-refusal-fillet-")
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


def box(sx: float, sy: float, sz: float) -> cq.Workplane:
    return cq.Workplane("XY").box(sx, sy, sz)


def test_a_fillet_on_a_compound_blends_both_pieces_as_one_body() -> None:
    part = (
        cq.Workplane("XY")
        .box(2, 2, 2)
        .union(cq.Workplane("XY").transformed(offset=cq.Vector(5, 0, 0)).box(2, 2, 2))
    )
    (solid,) = part.edges("|Z").fillet(0.5)._solids()
    assert len(solid.model.shells(solid.body)) == 2


def test_the_result_is_one_solid_on_the_stack_for_the_next_call() -> None:
    wp = box(10, 8, 4).edges("|Z").fillet(1)
    assert len(wp._solids()) == 1
    assert len(wp.faces(">Z")._stack) == 1


@pytest.mark.parametrize(
    ("chain", "message"),
    [
        (".edges().fillet()", "Workplane.fillet()"),
        (".edges().fillet('1')", "Workplane.fillet(str)"),
        (".edges().fillet(True)", "Workplane.fillet(bool)"),
        (".edges().fillet(1, 2)", "Workplane.fillet(num, num)"),
        (".edges().fillet(radius=1)", "Workplane.fillet(radius=num)"),
        (".moveTo(0, 0).fillet(1)", "Workplane.fillet on a pending wire"),
    ],
)
def test_a_fillet_form_the_census_never_writes_is_unsupported(chain: str, message: str) -> None:
    program = f'import cadquery as cq\n\nresult = cq.Workplane("XY").box(4, 6, 8){chain}\n'
    result = ag.run(program + "show_object(result)\n", dialect="cq")
    assert result.status is ag.Status.UNSUPPORTED_API
    assert message in result.message


def test_the_subset_declares_fillet_with_a_number() -> None:
    assert cq.subset().admits("Workplane.fillet(num)")
    assert not cq.subset().admits("Workplane.fillet(str)")


@settings(max_examples=40, deadline=None)
@given(
    size=st.tuples(st.integers(6, 20), st.integers(6, 20), st.integers(4, 12)),
    radius=st.sampled_from([0.25, 0.5, 1.0, 1.5, 2.0]),
)
def test_a_boxs_four_vertical_edges_filleted_lose_4_minus_pi_r_squared_h(
    size: tuple[int, int, int], radius: float
) -> None:
    """Volume V - (4 - pi) r^2 h: each of the four edges loses the section (1 - pi/4) r^2 over h.

    Area: each edge swaps two strips of r for an arc of pi r / 2 over h, and the top and bottom
    faces lose the four sections' areas each (8 (1 - pi/4) r^2 in all).
    """
    a, b, h = size
    result = ag.run(
        f'import cadquery as cq\n\nresult = cq.Workplane("XY").box({a}, {b}, {h})'
        f'.edges("|Z").fillet({radius})\nshow_object(result)\n',
        dialect="cq",
    )
    assert result.status is ag.Status.OK, result.message
    assert result.measures is not None
    volume = a * b * h - (4 - math.pi) * radius * radius * h
    assert fixture_cases.close(result.measures.volume, volume)
    area = 2 * (a * b + b * h + a * h) + 4 * h * (math.pi / 2 - 2) * radius
    area -= 8 * (1 - math.pi / 4) * radius * radius
    assert fixture_cases.close(result.measures.area, area)
    assert result.measures.faces == 10
    assert all(fixture_cases.close(c, 0.0) for c in result.measures.centroid)

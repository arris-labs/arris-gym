"""`edges()` and `edges(str)` keep CadQuery's edges (ADR-0020 rules 1 to 4).

The closed forms are worked out by hand from how each part is built: a box's
twelve edges and the midpoints of the four an axis selector keeps, a
cylinder's two rims and seam, a half cylinder's arcs (their centre of mass
`2r/pi` off the chord), a plate and its hole. Nothing is read from `cq`. An
edge selection ends no program in a solid (the oracle reports a bare edge as a
shape of volume 0), so what is kept is read off the stack; the `ok-fillet-*`
fixtures of plans/lift-edges-and-blends step 4 judge it by the part a blend
makes of it. The fixtures here are the refusals, each beside the oracle's
recorded report. Where `cq` places a seam (ADR-0020 rule 2, amended) is held to
the oracle's own records of `tools/cq_edge_probe.py` (`seam-*`).
"""

from __future__ import annotations

import math
from collections.abc import Callable

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import arris_gym as ag
import arris_gym.cq as cq
import cq_edge_probe as probe
import fixture_cases
from arris_gym.cq._selector import Edges
from arris_gym.fidelity import FidelityOutcome, OracleReport, compare
from test_edge_probe import record

Point = tuple[float, float, float]
# What two floats that closed-form arithmetic gives agree to.
ROUNDING = 1e-9

BOX = (10.0, 8.0, 4.0)
AXIS = {"X": 0, "Y": 1, "Z": 2}


def kept(wp: cq.Workplane) -> list[tuple[str, Point]]:
    """The edges on the stack: each its curve's kind and its centre.

    A line's centre is its midpoint, a full circle's its origin; an arc's is
    its origin too (the test of an arc reads its ends).
    """
    (selected,) = wp._stack
    assert isinstance(selected, Edges)
    model = selected.solid.model
    out: list[tuple[str, Point]] = []
    for edge in selected.edges:
        c = model.curve(edge)
        if c.kind == "line":
            mid = tuple((c.start[k] + c.end[k]) / 2 for k in range(3))
            out.append(("line", (mid[0], mid[1], mid[2])))
        else:
            assert c.origin is not None
            out.append((c.kind, c.origin))
    return out


def box() -> cq.Workplane:
    return cq.Workplane("XY").box(*BOX)


def test_a_box_has_twelve_edges_and_no_selector_keeps_them_all() -> None:
    got = kept(box().edges())
    assert len(got) == 12
    assert {kind for kind, _ in got} == {"line"}
    # Each edge's midpoint has two coordinates on a face's plane and one at 0.
    halves = [b / 2 for b in BOX]
    for _, mid in got:
        assert sum(abs(abs(mid[k]) - halves[k]) < ROUNDING for k in range(3)) == 2
        assert sum(abs(mid[k]) < ROUNDING for k in range(3)) == 1


@pytest.mark.parametrize("selector", [">X", "<X", ">Y", "<Y", ">Z", "<Z"])
def test_an_axis_selector_keeps_the_four_edges_of_the_face_it_names(selector: str) -> None:
    axis = AXIS[selector[1]]
    plane = (1 if selector[0] == ">" else -1) * BOX[axis] / 2
    got = kept(box().edges(selector))
    assert len(got) == 4
    assert {kind for kind, _ in got} == {"line"}
    # The four edges of the face at `plane`: each midpoint is on it, and on the
    # face's other two axes two lie at 0 and the others at the extremes.
    others = [k for k in range(3) if k != axis]
    for _, mid in got:
        assert abs(mid[axis] - plane) < ROUNDING
    a, b = (BOX[k] / 2 for k in others)
    ends = sorted((round(mid[others[0]], 9), round(mid[others[1]], 9)) for _, mid in got)
    assert ends == sorted([(-a, 0.0), (a, 0.0), (0.0, -b), (0.0, b)])


@pytest.mark.parametrize("selector", ["|X", "|Y", "|Z"])
def test_a_parallel_selector_keeps_the_four_lines_along_its_axis(selector: str) -> None:
    """The box's four edges along an axis, one at each corner of the face across it: the
    midpoint is on the axis's zero and at the extremes of the other two (ADR-0020 rule 3)."""
    axis = AXIS[selector[1]]
    got = kept(box().edges(selector))
    assert len(got) == 4
    assert {kind for kind, _ in got} == {"line"}
    others = [k for k in range(3) if k != axis]
    a, b = (BOX[k] / 2 for k in others)
    ends = sorted((mid[others[0]], mid[others[1]]) for _, mid in got)
    assert ends == sorted([(-a, -b), (-a, b), (a, -b), (a, b)])
    assert all(abs(mid[axis]) < ROUNDING for _, mid in got)


def test_the_or_selector_keeps_both_ends_once() -> None:
    got = kept(box().edges(">Z or <Z"))
    assert len(got) == 8
    assert sorted({mid[2] for _, mid in got}) == [-2.0, 2.0]
    # Each end's four edges, each edge once.
    assert len({mid for _, mid in got}) == 8
    both = kept(cq.Workplane("XY").cylinder(4, 2).edges(">Z or <Z"))
    assert sorted(both) == [("circle", (0.0, 0.0, -2.0)), ("circle", (0.0, 0.0, 2.0))]


def test_an_edge_both_sides_of_an_or_keep_is_kept_once() -> None:
    """On a box 1e-5 thick every key lies within CadQuery's 1e-4 of the first, so `>Z` and
    `<Z` each keep all twelve edges, and their union is the twelve, not twenty-four."""
    sliver = cq.Workplane("XY").box(10, 8, 1e-5)
    assert len(kept(sliver.edges(">Z"))) == 12
    assert len(kept(sliver.edges(">Z or <Z"))) == 12


def test_a_parallel_selector_never_keeps_a_circle_or_an_arc() -> None:
    cylinder = cq.Workplane("XY").cylinder(4, 2)
    # The seam is along z wherever it lies; the rims are circles.
    seam = kept(cylinder.edges("|Z"))
    assert [kind for kind, _ in seam] == ["line"]
    assert kept(cylinder.edges("|X")) == []
    assert kept(cylinder.edges("|Y")) == []
    # A half cylinder: the arcs are never parallel to anything.
    assert [kind for kind, _ in kept(half_cylinder().edges("|Z"))] == ["line", "line"]
    assert [kind for kind, _ in kept(half_cylinder().edges("|X"))] == ["line", "line"]


def test_a_drilled_plates_corners_and_hole_seam_are_parallel_to_z() -> None:
    """The plate's four corners and the hole's seam: five lines (ADR-0020's `plate-edges|Z`)."""
    plate = box().faces(">Z").workplane().hole(3)
    got = kept(plate.edges("|Z"))
    assert [kind for kind, _ in got] == ["line"] * 5
    corners = sorted((c[0], c[1]) for _, c in got if abs(c[0]) > 2)
    assert corners == [(-5.0, -4.0), (-5.0, 4.0), (5.0, -4.0), (5.0, 4.0)]
    (seam,) = (c for _, c in got if abs(c[0]) < 2)
    assert abs(seam[0]) == 1.5
    assert seam[1] == 0.0


def test_a_parallel_selector_on_a_face_ranks_that_faces_edges() -> None:
    assert len(kept(box().faces(">X").edges("|Z"))) == 2
    assert len(kept(box().faces(">X").edges("|X"))) == 0
    assert len(kept(box().faces(">Z").edges("|Y"))) == 2


def test_a_selector_still_refused_on_faces() -> None:
    for selector in ("|Z", ">Z or <Z"):
        with pytest.raises(cq.UnsupportedApi, match=r"^Workplane\.faces\("):
            box().faces(selector)


def test_the_kept_edges_come_in_ascending_key() -> None:
    """`edges("<Z")` and `edges(">Z")` order their edges by key, a tie in the kernel's order."""
    got = kept(box().edges(">Z"))
    assert [mid[2] for _, mid in got] == [2.0] * 4


def test_a_cylinder_has_two_rims_and_a_seam() -> None:
    part = cq.Workplane("XY").cylinder(4, 2)
    got = kept(part.edges())
    assert sorted(kind for kind, _ in got) == ["circle", "circle", "line"]
    top = kept(part.edges(">Z"))
    assert top == [("circle", (0.0, 0.0, 2.0))]
    assert kept(part.edges("<Z")) == [("circle", (0.0, 0.0, -2.0))]
    # The two rims, from `faces(">Z")`: its one rim; the seam is on the wall.
    assert kept(part.faces(">Z").edges()) == [("circle", (0.0, 0.0, 2.0))]


def test_a_cylinders_seam_is_ranked_where_open_cascade_puts_it() -> None:
    """`cylinder` has its seam on the plane's +x (ADR-0020 rule 2, amended): `>X` keeps it
    alone, `<X` the two rims, and `>Y` and `<Y` all three, tied at y = 0, as the oracle keeps
    them (`cylinder-edges>X`, `cylinder-edges>Y`)."""
    part = cq.Workplane("XY").cylinder(4, 1)
    assert kept(part.edges(">X")) == [("line", (1.0, 0.0, 0.0))]
    assert sorted(c[2] for _, c in kept(part.edges("<X"))) == [-2.0, 2.0]
    for selector in (">Y", "<Y"):
        assert sorted(kind for kind, _ in kept(part.edges(selector))) == [
            "circle",
            "circle",
            "line",
        ]
    oracle = record("cylinder-edges>X")
    assert [oracle["candidates"][i]["type"] for i in oracle["kept"]] == ["LINE"]
    assert len(record("cylinder-edges>Y")["kept"]) == 3


@pytest.mark.parametrize(
    "part",
    [
        # A revolved wall: where Open CASCADE starts a turned face is not modelled.
        cq.Workplane("XY")
        .polyline([(0, -2), (2, -2), (2, 2), (0, 2)])
        .close()
        .revolve(360, (0, -2, 0), (0, 2, 0)),
        # A bore on a polar array: CadQuery turns its axes, `cq` does not.
        cq.Workplane("XY").cylinder(4, 2).faces(">Z").workplane().polarArray(0, 0, 360, 1).hole(1),
    ],
    ids=["revolved", "polar-bore"],
)
def test_a_seam_no_record_places_ties_a_selector_across_its_axis_and_is_refused(
    part: cq.Workplane,
) -> None:
    """The seam's key runs over the wall's width, so it may tie with the rims (ADR-0020 rule 2)."""
    with pytest.raises(cq.UnsupportedApi, match=r"depends on an edge's place"):
        part.edges(">X")


# The parts of the probe's `seam-*` constructions, built in `cq`: each less its last call.
SEAM_PARTS: dict[str, Callable[[], cq.Workplane]] = {
    "seam-yz-cylinder": lambda: cq.Workplane("YZ").cylinder(10, 2),
    "seam-xz-cylinder": lambda: cq.Workplane("XZ").cylinder(10, 2),
    "seam-zx-cylinder": lambda: cq.Workplane("ZX").cylinder(10, 2),
    "seam-turned-cylinder": lambda: (
        cq.Workplane("XY").transformed(rotate=cq.Vector(0, 0, 30)).cylinder(4, 1)
    ),
    "seam-yz-washer": lambda: cq.Workplane("YZ").cylinder(1, 5).faces(">X").workplane().hole(3),
    "seam-xz-washer": lambda: cq.Workplane("XZ").cylinder(1, 5).faces("<Y").workplane().hole(3),
    "seam-xz-ring": lambda: cq.Workplane("XZ").circle(5).extrude(1).faces("<Y").workplane().hole(3),
    "seam-yz-cbore": lambda: (
        cq.Workplane("YZ").cylinder(2, 5).faces(">X").workplane().cboreHole(2, 4, 0.5)
    ),
    "seam-yz-cut-blind": lambda: (
        cq.Workplane("YZ").cylinder(2, 5).faces(">X").workplane().circle(1.5).cutBlind(-1)
    ),
    "seam-xz-points": lambda: (
        cq.Workplane("XZ")
        .cylinder(2, 5)
        .faces("<Y")
        .workplane()
        .pushPoints([(2, 0), (-2, 1)])
        .hole(1)
    ),
}


def _off_line(q: list[float], point: Point, axis: Point) -> float:
    """How far `q` lies from the line through `point` along the unit `axis`."""
    v = [q[k] - point[k] for k in range(3)]
    along = sum(v[k] * axis[k] for k in range(3))
    return math.sqrt(sum((v[k] - along * axis[k]) ** 2 for k in range(3)))


def test_every_seam_construction_is_built_here() -> None:
    assert sorted(SEAM_PARTS) == sorted(probe.SEAMS)


@pytest.mark.parametrize("name", sorted(SEAM_PARTS))
def test_the_chains_records_put_each_seam_where_open_cascade_does(name: str) -> None:
    """Each seam the oracle keeps lies on the line of one of the chain's records, one record a
    seam: `cylinder`, `extrude` and `cutBlind` on the plane's +x, a bore on -x, on named,
    turned and face planes (ADR-0020 rule 2, amended)."""
    oracle = record(name)
    # The probe's selector is along the axes: it keeps the seams and nothing else.
    seams = [oracle["candidates"][i] for i in oracle["kept"]]
    assert all(seam["type"] == "LINE" for seam in seams)
    records = SEAM_PARTS[name]()._seams
    assert records is not None
    assert len(records) == len(seams)
    unmatched = list(records)
    for seam in seams:
        on = []
        for r in unmatched:
            p = r.point
            line = (
                p[0] + r.radius * r.side[0],
                p[1] + r.radius * r.side[1],
                p[2] + r.radius * r.side[2],
            )
            if all(_off_line(seam[end], line, r.axis) < ROUNDING for end in ("start", "end")):
                on.append(r)
        assert len(on) == 1, (seam, records)
        unmatched.remove(on[0])


def half_cylinder() -> cq.Workplane:
    """A D: a half circle of radius 1 on a chord along x, extruded 2 along z."""
    return cq.Workplane("XY").moveTo(-1, 0).threePointArc((0, 1), (1, 0)).close().extrude(2)


def test_an_arc_is_ranked_by_its_centre_of_mass() -> None:
    """A half circle's centre of mass is `2r/pi` off its chord, so `>Y` keeps both arcs
    (0.6366 up) and `<Y` the four lines on the chord's line (y = 0)."""
    arcs = kept(half_cylinder().edges(">Y"))
    assert [kind for kind, _ in arcs] == ["circle", "circle"]
    assert sorted(c[2] for _, c in arcs) == [0.0, 2.0]
    lines = kept(half_cylinder().edges("<Y"))
    assert [kind for kind, _ in lines] == ["line"] * 4
    assert {round(c[1], 9) for _, c in lines} == {0.0}
    assert math.isclose(2 / math.pi, 0.6366197723675814)


def test_the_edges_of_a_selected_face_are_the_candidates() -> None:
    top = box().faces(">Z")
    assert len(kept(top.edges())) == 4
    on_x = kept(top.edges(">X"))
    assert len(on_x) == 1
    assert on_x[0][1] == (5.0, 0.0, 2.0)
    assert len(kept(box().faces(">X").edges("<Z"))) == 1


def test_the_edges_of_a_plates_top_include_its_holes_rim() -> None:
    plate = box().faces(">Z").workplane().hole(3)
    got = kept(plate.faces(">Z").edges())
    assert sorted(kind for kind, _ in got) == ["circle", "line", "line", "line", "line"]


def test_a_seam_bounded_far_from_the_kept_edges_does_not_block_a_selection() -> None:
    """A hole bored on a polar array has a seam no record places: it lies somewhere on the
    hole's wall, x within 1.5 of 0; the plate's `>X` edges are at x = 5, so the seam cannot
    reach them (ADR-0020 rule 2)."""
    plate = box().faces(">Z").workplane().polarArray(0, 0, 360, 1).hole(3)
    assert plate._seams is None
    got = kept(plate.edges(">X"))
    assert len(got) == 4
    assert {c[0] for _, c in got} == {5.0}


def test_edges_on_edges_rank_only_those() -> None:
    got = kept(box().edges(">Z").edges(">X"))
    assert got == [("line", (5.0, 0.0, 2.0))]


def test_a_compound_has_the_edges_of_every_piece() -> None:
    pair = box().union(cq.Workplane("XY").transformed(offset=cq.Vector(20, 0, 0)).box(*BOX))
    assert len(kept(pair.edges())) == 24
    assert len(kept(pair.edges(">Z"))) == 8
    lower = box().union(cq.Workplane("XY").transformed(offset=cq.Vector(20, 0, -1)).box(*BOX))
    assert len(kept(lower.edges(">Z"))) == 4


def test_edges_of_a_sphere_leave_out_the_degenerate_poles() -> None:
    got = kept(cq.Workplane("XY").sphere(2).edges())
    assert all(kind != "degenerate" for kind, _ in got)


@pytest.mark.parametrize(
    ("chain", "message"),
    [
        (".edges('%LINE')", "Workplane.edges('%LINE')"),
        (".edges(1)", "Workplane.edges(num)"),
        (".edges('>Z', 'x')", "Workplane.edges(str, str)"),
        (".edges(selector='>Z')", "Workplane.edges(selector=str)"),
        (".edges().box(1, 1, 1)", "Workplane.box on selected edges"),
        (".edges().hole(1)", "Workplane.hole on selected edges"),
        (".edges().extrude(1)", "Workplane.extrude on selected edges"),
        (".edges().faces('>Z')", "Workplane.faces on selected edges"),
        (".edges().workplane()", "Workplane.workplane on selected edges"),
        (".edges().moveTo(0, 0)", "Workplane.moveTo on selected edges"),
        (".edges().lineTo(1, 1)", "Workplane.lineTo on selected edges"),
        (".edges().union(cq.Workplane('XY').box(1, 1, 1))", "Workplane.union on selected edges"),
    ],
)
def test_an_edge_stack_read_by_any_other_call_is_unsupported(chain: str, message: str) -> None:
    program = f'import cadquery as cq\n\nresult = cq.Workplane("XY").box(4, 6, 8){chain}\n'
    result = ag.run(program + "show_object(result)\n", dialect="cq")
    assert result.status is ag.Status.UNSUPPORTED_API
    assert message in result.message


def test_a_selection_as_another_calls_operand_is_unsupported() -> None:
    program = (
        'import cadquery as cq\n\nresult = cq.Workplane("XY").box(4, 6, 8)'
        '.union(cq.Workplane("XY").box(1, 1, 1).edges())\nshow_object(result)\n'
    )
    result = ag.run(program, dialect="cq")
    assert result.status is ag.Status.UNSUPPORTED_API
    assert "with selected edges" in result.message


def test_an_edge_selection_is_no_solid_to_return() -> None:
    result = ag.run(
        'import cadquery as cq\n\nresult = cq.Workplane("XY").box(1, 1, 1).edges(">Z")\n'
        "show_object(result)\n",
        dialect="cq",
    )
    assert result.status is ag.Status.RUNTIME
    assert "holding no solid" in result.message


def test_the_subset_declares_edges_with_and_without_a_selector() -> None:
    forms = {(f.name, f.positional) for f in cq.subset().forms if f.name == "Workplane.edges"}
    assert forms == {("Workplane.edges", ()), ("Workplane.edges", (("str",),))}
    assert cq.subset().admits("Workplane.edges()")
    assert cq.subset().admits("Workplane.edges(str)")
    assert not cq.subset().admits("Workplane.edges(num)")


# The refusals, each beside the oracle's recorded report: slug -> (program text, message).
HEAD = 'import cadquery as cq\n\nresult = cq.Workplane("XY")'
TAIL = "\nshow_object(result)\n"
RUNTIME: dict[str, tuple[str, str]] = {
    "runtime-edges-on-empty-stack": (
        f'{HEAD}.edges(">Z"){TAIL}',
        "ValueError: Can not return the Nth element of an empty list",
    ),
}
UNSUPPORTED: dict[str, tuple[str, str]] = {
    "unsupported-edges-unified-face-boundary": (
        "import cadquery as cq\n\nresult = (\n"
        '    cq.Workplane("YZ")\n'
        "    .cylinder(4, 5)\n"
        '    .cut(cq.Workplane("XY").box(6, 2, 20))\n'
        '    .faces(">Y")\n'
        '    .edges(">X")\n'
        ")\n",
        "Workplane.edges('>X') on a split unified face boundary",
    ),
    "unsupported-edges-revolved-side": (
        f"{HEAD}.polyline([(0, -2), (2, -2), (2, 2), (0, 2)]).close()"
        f'.revolve(360, (0, -2, 0), (0, 2, 0)).edges(">X"){TAIL}',
        "Workplane.edges('>X'): the selection depends on an edge's place, "
        "which arris does not decide as CadQuery's kernel does",
    ),
    "unsupported-edges-type-selector": (
        f'{HEAD}.box(10, 8, 4).edges("%LINE"){TAIL}',
        "Workplane.edges('%LINE')",
    ),
    "unsupported-edges-then-box": (
        f'{HEAD}.box(10, 8, 4).edges(">Z").box(1, 1, 1){TAIL}',
        "Workplane.box on selected edges",
    ),
}


def cases(prefix: str) -> dict[str, fixture_cases.Case]:
    return {c.slug: c for c in fixture_cases.load("cq") if c.slug.startswith(prefix)}


def recorded(slug: str) -> OracleReport:
    path = fixture_cases.ROOT / "cq" / slug / "oracle.json"
    return OracleReport.model_validate_json(path.read_text())


def test_every_runtime_edges_fixture_is_cadquerys_refusal() -> None:
    committed = cases("runtime-edges-")
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
        assert (report.message or "").splitlines()[-1] == message
        assert compare(fixture_cases.run(committed[slug]), report).outcome is FidelityOutcome.AGREE


def test_every_unsupported_edges_fixture_is_a_form_the_oracle_builds() -> None:
    committed = cases("unsupported-edges-")
    assert sorted(committed) == sorted(UNSUPPORTED)
    for slug, (program, message) in UNSUPPORTED.items():
        assert committed[slug].program == program, slug
        assert committed[slug].expected == {
            "dialect": "cq",
            "status": "unsupported_api",
            "message": message,
        }
        assert recorded(slug).status.value == "ok", slug


@settings(max_examples=40, deadline=None)
@given(size=st.tuples(st.integers(1, 30), st.integers(1, 30), st.integers(1, 30)))
def test_on_a_random_box_a_parallel_selector_keeps_four_lines_and_or_eight(
    size: tuple[int, int, int],
) -> None:
    """`|Z` keeps the four vertical lines, at the corners; `'>Z or <Z'` the eight lines of the
    two ends, each at the height of one."""
    wp = cq.Workplane("XY").box(*size)
    vertical = kept(wp.edges("|Z"))
    assert [kind for kind, _ in vertical] == ["line"] * 4
    assert sorted((c[0], c[1]) for _, c in vertical) == sorted(
        (sx * size[0] / 2, sy * size[1] / 2) for sx in (-1, 1) for sy in (-1, 1)
    )
    ends = kept(wp.edges(">Z or <Z"))
    assert [kind for kind, _ in ends] == ["line"] * 8
    assert sorted(c[2] for _, c in ends) == [-size[2] / 2] * 4 + [size[2] / 2] * 4


@settings(max_examples=40, deadline=None)
@given(
    size=st.tuples(st.integers(1, 30), st.integers(1, 30), st.integers(1, 30)),
    selector=st.sampled_from([">X", "<X", ">Y", "<Y", ">Z", "<Z"]),
)
def test_a_random_box_and_selector_keep_the_four_edges_of_the_named_face(
    size: tuple[int, int, int], selector: str
) -> None:
    """The face at the selector's extreme has four edges, whose midpoints are at its plane,
    half a side out on one other axis and centred on the third."""
    axis = AXIS[selector[1]]
    sign = 1 if selector[0] == ">" else -1
    got = kept(cq.Workplane("XY").box(*size).edges(selector))
    assert len(got) == 4
    others = [k for k in range(3) if k != axis]
    for kind, mid in got:
        assert kind == "line"
        assert abs(mid[axis] - sign * size[axis] / 2) < ROUNDING
    ends = sorted((round(mid[others[0]], 9), round(mid[others[1]], 9)) for _, mid in got)
    a, b = (size[k] / 2 for k in others)
    assert ends == sorted([(-a, 0.0), (a, 0.0), (0.0, -b), (0.0, b)])

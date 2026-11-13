"""The `cq` dialect: `cadquery` is the subset, a result resolves to one solid.

ADR-0007; a compound is one solid whose body holds a shell per piece
(ADR-0016). Fixtures under `tests/fixtures/cq/` hold one program per outcome,
expectations from the program's text (tests/fixture_cases.py).
"""

from __future__ import annotations

import copy
import doctest
import hashlib
import math
from collections.abc import Callable

import arris.build
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

import arris_gym as ag
import arris_gym.cq as cq
import fixture_cases
from arris_gym.cq import _forms, _result, _vector, _workplane
from arris_gym.fidelity import (
    FidelityOutcome,
    OracleReport,
    OracleStatus,
    compare,
    program_sha256,
)

CASES = fixture_cases.load("cq")
# A recorded report beside a `verdict.json` is one the oracle got wrong: its
# closed form is held to the oracle in `test_cq_compound.py` instead. A
# report beside a fixture that expects a failure has no closed form: its row
# is held in that fixture's own test (`test_cq_three_point_arc.py`).
RECORDED = [
    c
    for c in CASES
    if (fixture_cases.ROOT / "cq" / c.slug / "oracle.json").is_file()
    and not (fixture_cases.ROOT / "cq" / c.slug / "verdict.json").is_file()
    and c.expected["status"] == "ok"
]


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.slug)
def test_a_fixture_program_gives_its_expected_result(case: fixture_cases.Case) -> None:
    result = fixture_cases.run(case)
    assert fixture_cases.check(result, case.expected) == []
    assert result.program_sha256 == hashlib.sha256(case.program.encode()).hexdigest()


def test_a_shown_workplane_holding_one_solid_is_its_body() -> None:
    program = "import cadquery as cq\nshow_object(cq.Workplane('XY').box(1, 2, 3))\n"
    result = ag.run(program, dialect="cq")
    assert result.status is ag.Status.OK, result.message
    assert result.dialect is ag.Dialect.CQ
    assert result.measures is not None
    assert fixture_cases.close(result.measures.volume, 6.0)


@pytest.mark.parametrize("case", RECORDED, ids=lambda c: c.slug)
def test_the_oracle_holds_a_recorded_fixtures_closed_form(case: fixture_cases.Case) -> None:
    # The closed form is CadQuery's semantics, not only arris-gym's reading
    # of it: Open CASCADE builds the same part (tests/fixtures/cq/README.md).
    path = fixture_cases.ROOT / "cq" / case.slug / "oracle.json"
    report = OracleReport.model_validate_json(path.read_text(encoding="utf-8"))
    assert report.status is OracleStatus.OK
    assert report.program_sha256 == program_sha256(case.program)
    assert report.measures is not None
    want = case.expected["measures"]
    assert isinstance(want, dict)
    # One solid per shell of the closed form: none of these parts has a cavity.
    assert report.measures.solids == want["shells"]
    got = report.measures
    pairs = [(got.volume, want["volume"]), (got.area, want["area"])]
    pairs += list(zip(got.centroid, want["centroid"], strict=True))
    pairs += list(
        zip([*got.bounds[0], *got.bounds[1]], [*want["bounds"][0], *want["bounds"][1]], strict=True)
    )
    assert all(fixture_cases.close(g, float(w)) for g, w in pairs), pairs


def test_the_same_text_is_cached_apart_per_dialect() -> None:
    with ag.Sandbox() as sandbox:
        under_cq = sandbox.run("show_object(5)", dialect="cq")
        under_arris = sandbox.run("show_object(5)", dialect="arris")
        assert (under_cq.dialect, under_arris.dialect) == (ag.Dialect.CQ, ag.Dialect.ARRIS)
        assert under_cq.message != under_arris.message
        assert sandbox.executions == 2


def box(lo: float) -> arris.build.Solid:
    return arris.build.Solid.box((lo, 0, 0), (lo + 1, 1, 1))


def test_a_workplane_resolves_to_the_single_solid_on_its_stack() -> None:
    solid = box(0)
    shown = cq.Workplane("XY")._derive("a pending sketch", solid)
    assert _result.solid_of(shown, "it") is solid


def test_a_compound_resolves_to_its_one_solid_of_several_shells() -> None:
    a = cq.Workplane("XY").box(1, 1, 1)
    b = cq.Workplane("XY").transformed(offset=cq.Vector(5, 0, 0)).box(1, 1, 1)
    c = cq.Workplane("XY").transformed(offset=cq.Vector(10, 0, 0)).box(1, 1, 1)
    shown = a.union(b).union(c)
    solid = _result.solid_of(shown, "it")
    assert shown._stack == (solid,)
    assert len(solid.model.shells(solid.body)) == 3
    assert fixture_cases.close(solid.measure().volume, 3.0)


@pytest.mark.parametrize(
    ("value", "message"),
    [
        (cq.Workplane("XY"), "it is a Workplane holding no solid"),
        (cq.Workplane("XY")._derive("a pending sketch"), "it is a Workplane holding no solid"),
        (box(0), "it is of type Solid, not cadquery.Workplane"),
    ],
    ids=["empty", "no-solid", "a-bare-solid"],
)
def test_anything_else_is_not_a_solid(value: object, message: str) -> None:
    with pytest.raises(_result.NotASolid) as raised:
        _result.solid_of(value, "it")
    assert str(raised.value) == message


def test_a_call_returns_a_new_workplane_and_changes_none() -> None:
    first = cq.Workplane("XY")
    second = first._derive(box(0))
    assert second is not first
    assert (first._stack, first._parent) == ((), None)
    assert second._parent is first
    with pytest.raises(cq.UnsupportedApi, match=r"^setting Workplane\._stack$"):
        first._stack = (box(1),)
    with pytest.raises(cq.UnsupportedApi, match=r"^deleting Workplane\._parent$"):
        del second._parent


@pytest.mark.parametrize("name", ["sphere", "faces", "val", "objects", "plane"])
def test_a_workplane_name_outside_the_subset_is_unsupported_never_attribute_error(
    name: str,
) -> None:
    with pytest.raises(cq.UnsupportedApi) as raised:
        getattr(cq.Workplane("XY"), name)
    assert str(raised.value) == f"Workplane.{name}"
    assert not isinstance(raised.value, AttributeError)


@pytest.mark.parametrize("name", ["Sketch", "Vector2", "exporters", "selectors", "Assembly"])
def test_a_module_name_outside_the_subset_is_unsupported(name: str) -> None:
    with pytest.raises(cq.UnsupportedApi, match=rf"^cq\.{name}$"):
        getattr(cq, name)


@pytest.mark.parametrize("name", ["__wrapped__", "__fspath__", "_private"])
def test_a_python_name_stays_an_attribute_error(name: str) -> None:
    # Python's protocols (copy, pickle, doctest, `from x import`) probe
    # these by `hasattr`, which an `UnsupportedApi` would break.
    for owner in (cq, cq.Workplane("XY")):
        with pytest.raises(AttributeError):
            getattr(owner, name)


def test_a_copy_of_a_workplane_is_itself() -> None:
    # A frozen value: copying it would change nothing.
    plane = cq.Workplane("XY")._derive(box(0))
    assert copy.copy(plane) is plane
    assert copy.deepcopy(plane) is plane


@pytest.mark.parametrize("plane", ["XZ ", "front", "xy", "xz", "zx", "YX", ""])
def test_a_named_plane_outside_the_admitted_values_is_unsupported(plane: str) -> None:
    with pytest.raises(cq.UnsupportedApi, match=r"^cq\.Workplane\("):
        cq.Workplane(plane)


def test_the_caller_module_shows_cadquery_names_and_subset_metadata() -> None:
    public = sorted(n for n in vars(cq) if not _workplane.is_python_name(n))
    assert public == ["CensusForm", "Subset", "UnsupportedApi", "Vector", "Workplane", "subset"]


def test_the_docstring_examples_run() -> None:
    assert doctest.testmod(cq).failed == 0
    assert doctest.testmod(_workplane).failed == 0
    assert doctest.testmod(_vector).failed == 0


def test_a_vector_is_a_frozen_value() -> None:
    v = cq.Vector(1, 2.5, -3)
    assert (v.x, v.y, v.z) == (1.0, 2.5, -3.0)
    assert all(type(c) is float for c in (v.x, v.y, v.z))
    with pytest.raises(cq.UnsupportedApi, match=r"^setting Vector\._xyz$"):
        v._xyz = (5.0, 0.0, 0.0)
    with pytest.raises(cq.UnsupportedApi, match=r"^deleting Vector\._xyz$"):
        del v._xyz
    assert (v.x, v.y, v.z) == (1.0, 2.5, -3.0)
    assert copy.copy(v) is v
    assert copy.deepcopy(v) is v


@pytest.mark.parametrize("name", ["Length", "toTuple", "normalized", "add"])
def test_a_vector_name_outside_the_subset_is_unsupported(name: str) -> None:
    with pytest.raises(cq.UnsupportedApi, match=rf"^Vector\.{name}$"):
        getattr(cq.Vector(0, 0, 1), name)


def test_transformed_and_box_change_no_workplane() -> None:
    first = cq.Workplane("XY")
    turned = first.transformed(offset=cq.Vector(1, 2, 3), rotate=cq.Vector(10, 20, 30))
    boxed = turned.box(1, 2, 3)
    assert (first._plane, first._stack, first._parent) == (arris.build.Workplane.XY(), (), None)
    assert (turned._stack, turned._parent) == ((), first)
    assert turned._plane.origin == (1.0, 2.0, 3.0)
    assert boxed._plane is turned._plane
    assert boxed._parent is turned
    assert len(boxed._stack) == 1
    assert isinstance(boxed._stack[0], arris.build.Solid)


def test_a_box_onto_a_solid_in_the_chain_is_fused_with_it() -> None:
    # The solid is further up the chain: `transformed` empties the stack and
    # `moveTo` leaves a point on it. A box on the solid's own stack is
    # refused (`test_cq_box.py`).
    boxed = cq.Workplane("XY").box(2, 2, 2)
    for wp in (boxed.transformed(offset=cq.Vector(0, 0, 1.5)), boxed.moveTo(1, 0)):
        fused = wp.box(2, 2, 2)
        assert len(fused._stack) == 1
        assert fused._parent is wp


def solid_volume(wp: cq.Workplane) -> float:
    (solid,) = wp._solids()
    return solid.measure().volume


def test_arris_fuse_of_disjoint_solids_is_one_solid_of_two_shells() -> None:
    # What `union` of disjoint solids rests on (ADR-0007): `fuse` does not
    # refuse them nor return two solids; the body holds both outer shells.
    near = arris.build.Solid.box((0, 0, 0), (1, 1, 1))
    far = arris.build.Solid.box((5, 0, 0), (6, 1, 1))
    fused = near.fuse(far)
    assert isinstance(fused, arris.build.Solid)
    assert fixture_cases.close(fused.measure().volume, 2.0)
    assert len(fused.model.shells(fused.body)) == 2


def test_a_disjoint_union_is_one_solid_of_both_shells_and_combines_on() -> None:
    # A compound (ADR-0016): one solid on the stack, a shell per box, and a
    # later call acts on both pieces, as CadQuery's does on its compound.
    a = cq.Workplane("XY").box(1, 1, 1)
    b = cq.Workplane("XY").transformed(offset=cq.Vector(5, 0, 0)).box(1, 1, 1)
    both = a.union(b)
    (solid,) = both._stack
    assert isinstance(solid, arris.build.Solid)
    assert len(solid.model.shells(solid.body)) == 2
    assert fixture_cases.close(solid_volume(both.cut(a)), 1.0)


def test_a_cut_that_leaves_a_cavity_is_one_solid() -> None:
    block = cq.Workplane("XY").box(3, 3, 3)
    cavity = cq.Workplane("XY").box(1, 1, 1)
    hollow = block.cut(cavity)
    assert len(hollow._stack) == 1
    assert fixture_cases.close(solid_volume(hollow), 26.0)


def test_a_cut_that_splits_its_base_is_one_solid_of_both_pieces() -> None:
    # 4 x 1 x 1 bar less a 1 x 2 x 2 slab across its middle: two 1.5 x 1 x 1
    # pieces, V = 4 - 1 = 3. CadQuery returns a compound (ADR-0016).
    bar = cq.Workplane("XY").box(4, 1, 1)
    slab = cq.Workplane("XY").box(1, 2, 2)
    pieces = bar.cut(slab)
    (solid,) = pieces._stack
    assert isinstance(solid, arris.build.Solid)
    assert len(solid.model.shells(solid.body)) == 2
    assert fixture_cases.close(solid_volume(pieces), 3.0)
    # A further cut acts on both pieces: a 3-wide box across the middle
    # leaves the outer 0.5 of each, V = 2 * 0.5.
    ends = cq.Workplane("XY").box(3, 2, 2)
    assert fixture_cases.close(solid_volume(pieces.cut(ends)), 1.0)


def test_union_and_cut_return_new_workplanes_and_change_none() -> None:
    a = cq.Workplane("XY").box(2, 2, 2)
    b = cq.Workplane("XY").transformed(offset=cq.Vector(1, 0, 0)).box(2, 2, 2)
    before = (a._stack, b._stack)
    united, cut = a.union(b), a.cut(b)
    assert united is not a
    assert cut is not a
    assert (a._stack, b._stack) == before
    assert fixture_cases.close(solid_volume(united), 12.0)
    assert fixture_cases.close(solid_volume(cut), 4.0)


def test_cut_needs_a_solid_in_the_chain_and_both_need_one_in_the_operand() -> None:
    # Read on the oracle: `runtime-cut-on-empty-chain`; CadQuery's `union`
    # raises too when the Workplane given holds no solid.
    empty, boxed = cq.Workplane("XY"), cq.Workplane("XY").box(1, 1, 1)
    with pytest.raises(ValueError, match=r"^Cannot find a solid on the stack or in the parent"):
        empty.cut(boxed)
    calls: list[Callable[[], cq.Workplane]] = [
        lambda: boxed.union(empty),
        lambda: boxed.cut(empty),
        lambda: empty.union(empty),
        lambda: empty.union(cq.Workplane("XY").circle(1)),
    ]
    for call in calls:
        with pytest.raises(ValueError, match=r"holding no solid$"):
            call()


@settings(max_examples=30, deadline=None)
@given(
    plane=st.sampled_from(["XY", "YZ", "XZ", "ZX"]),
    other_plane=st.sampled_from(["XY", "YZ", "XZ", "ZX"]),
    moved=st.tuples(*(st.integers(-5, 5) for _ in range(3))),
    at=st.tuples(*(st.integers(-5, 5) for _ in range(3))),
    height=st.integers(1, 6),
    radius=st.integers(1, 4),
)
def test_a_union_on_a_chain_with_no_solid_is_its_operands_solid_on_its_own_plane(
    plane: str,
    other_plane: str,
    moved: tuple[int, int, int],
    at: tuple[int, int, int],
    height: int,
    radius: int,
) -> None:
    # Read on the oracle: CadQuery's `union` with no solid up the chain puts
    # the given solid on the stack where it stands (`ok-union-on-empty-chain-*`),
    # wherever the caller's plane is.
    caller = cq.Workplane(plane).transformed(offset=cq.Vector(*moved))
    there = cq.Workplane(other_plane).transformed(offset=cq.Vector(*at))
    operand = there.cylinder(height, radius)
    united = caller.union(operand)
    (solid,) = united._solids()
    assert solid is operand._solids()[0]
    assert united._plane is caller._plane
    assert fixture_cases.close(solid.measure().volume, math.pi * radius**2 * height)
    # The chain goes on from it: a coaxial bore cut through it leaves a tube.
    bore = there.cylinder(height + 2, radius / 2)
    tube = math.pi * (radius**2 - (radius / 2) ** 2) * height
    assert fixture_cases.close(solid_volume(united.cut(bore)), tube)


@pytest.mark.parametrize(
    "slug",
    ["ok-union-on-empty-chain", "ok-union-on-empty-chain-tube", "ok-union-on-empty-chain-yz"],
)
def test_union_on_empty_chain_fixtures_agree_with_the_recorded_oracle(slug: str) -> None:
    case = next(c for c in CASES if c.slug == slug)
    path = fixture_cases.ROOT / "cq" / slug / "oracle.json"
    report = OracleReport.model_validate_json(path.read_text(encoding="utf-8"))
    assert compare(fixture_cases.run(case), report).outcome is FidelityOutcome.AGREE


def test_union_and_cut_take_a_workplane_only() -> None:
    boxed = cq.Workplane("XY").box(1, 1, 1)
    with pytest.raises(cq.UnsupportedApi, match=r"^Workplane\.union\(Workplane\) with int$"):
        boxed.union(5)  # type: ignore[arg-type]
    with pytest.raises(cq.UnsupportedApi, match=r"^Workplane\.cut\(Workplane\) with str$"):
        boxed.cut("a")  # type: ignore[arg-type]


def test_cut_looks_for_its_solid_up_the_chain() -> None:
    block = cq.Workplane("XY").box(4, 4, 4)
    moved = block.transformed(offset=cq.Vector(0, 0, 1))
    bar = cq.Workplane("XY").box(1, 1, 6)
    assert fixture_cases.close(solid_volume(moved.cut(bar)), 60.0)


def test_extrude_needs_one_pending_sketch() -> None:
    boxed = cq.Workplane("XY").box(1, 1, 1)
    for wp in (cq.Workplane("XY"), boxed):
        with pytest.raises(ValueError, match=r"^No pending wires present$"):
            wp.extrude(1)


def test_a_circle_is_pending_until_it_is_extruded() -> None:
    drawn = cq.Workplane("XY").circle(1)
    assert drawn._solids() == ()
    assert len(drawn._stack) == 1
    solid_wp = drawn.extrude(2)
    assert solid_wp._parent is drawn
    assert drawn._solids() == ()
    assert fixture_cases.close(solid_volume(solid_wp), 2 * math.pi)


def test_a_circle_on_a_non_empty_stack_is_unsupported() -> None:
    with pytest.raises(cq.UnsupportedApi, match=r"^Workplane\.circle on a non-empty stack$"):
        cq.Workplane("XY").box(1, 1, 1).circle(1)


def test_an_extrusion_is_fused_with_the_solid_in_its_chain() -> None:
    base = cq.Workplane("XY").box(2, 2, 2)
    # A cylinder along z from the plane at z = 0 to 3, through the box: the
    # union is the box (8) plus the part above it, pi * 0.25 * 2.
    both = base.transformed().circle(0.5).extrude(3)
    assert fixture_cases.close(solid_volume(both), 8 + math.pi * 0.25 * 2)


def body_digest(slug: str) -> str:
    (case,) = [c for c in CASES if c.slug == slug]
    result = fixture_cases.run(case)
    assert result.body is not None, result.message
    return result.body.sha256


def test_one_profile_by_polyline_and_by_lines_is_one_body() -> None:
    # The same points drawn two ways are the same path, so the same bytes.
    assert body_digest("ok-revolved-rectangle") == body_digest("ok-revolved-rectangle-lines")


TRIANGLE = [(0.0, 0.0), (3.0, 0.0), (0.0, 4.0)]


def same_outline(a: object, b: object) -> bool:
    """Whether two stack objects are sketches of one outline on one plane.

    `arris.build.Sketch` compares by identity; its loop and plane by value.
    """
    assert isinstance(a, arris.build.Sketch)
    assert isinstance(b, arris.build.Sketch)
    return a.plane == b.plane and a.outer == b.outer and a.holes == b.holes


def test_a_path_is_pending_until_it_is_closed() -> None:
    drawn = cq.Workplane("XY").moveTo(*TRIANGLE[0]).lineTo(*TRIANGLE[1]).lineTo(*TRIANGLE[2])
    assert drawn._solids() == ()
    assert len(drawn._stack) == 1
    closed = drawn.close()
    assert closed._parent is drawn
    (sketch,) = closed._stack
    assert isinstance(sketch, arris.build.Sketch)
    assert fixture_cases.close(solid_volume(closed.extrude(1)), 6.0)


def test_line_to_starts_at_the_origin_on_an_empty_stack() -> None:
    from_origin = cq.Workplane("XY").lineTo(3, 0).lineTo(0, 4).close()
    moved = cq.Workplane("XY").moveTo(0, 0).lineTo(3, 0).lineTo(0, 4).close()
    listed = cq.Workplane("XY").polyline(TRIANGLE).close()
    sketches = [wp._stack[0] for wp in (from_origin, moved, listed)]
    assert all(isinstance(s, arris.build.Sketch) for s in sketches)
    assert all(same_outline(s, sketches[0]) for s in sketches)


def test_a_path_drawn_on_a_turned_plane_is_in_its_coordinates() -> None:
    plane = cq.Workplane("XY").transformed(offset=cq.Vector(1, 2, 3), rotate=cq.Vector(90, 0, 0))
    prism = plane.polyline([(0, 0), (2, 0), (2, 1), (0, 1)]).close().extrude(1)
    (solid,) = prism._solids()
    # The plane's x is world x, its y world z and its normal world -y.
    bounds = solid.model.bounds(solid.body)
    assert bounds is not None
    lo, hi = bounds
    want = ((1, 1, 3), (3, 2, 4))
    assert all(
        fixture_cases.close(g, w) for g, w in zip([*lo, *hi], [*want[0], *want[1]], strict=True)
    )


def test_close_adds_no_segment_within_cadquerys_gap() -> None:
    # A path that ends within 1e-6 of its start ends there: three edges,
    # not a fourth sliver; one wider is a fourth segment back.
    near = cq.Workplane("XY").polyline([(0, 0), (3, 0), (0, 4), (0, 5e-7)]).close()
    far = cq.Workplane("XY").polyline([(0, 0), (3, 0), (0, 4), (0, 1e-3)]).close()
    exact = cq.Workplane("XY").polyline(TRIANGLE).close()
    assert same_outline(near._stack[0], exact._stack[0])
    assert not same_outline(far._stack[0], exact._stack[0])
    four = arris.build.Workplane.XY().start((0, 0)).line_to((3, 0)).line_to((0, 4))
    assert same_outline(far._stack[0], four.line_to((0, 1e-3)).close())


def test_close_needs_a_drawn_segment() -> None:
    boxed = cq.Workplane("XY").box(1, 1, 1)
    for wp in (cq.Workplane("XY"), cq.Workplane("XY").moveTo(1, 1), boxed):
        with pytest.raises(ValueError, match=r"^No start point specified - cannot close$"):
            wp.close()


@pytest.mark.parametrize(
    ("points", "message"), [([], "list of 0 points"), ([(3, 1)], "list of 1 point")]
)
def test_a_polyline_of_fewer_than_two_points_is_unsupported(
    points: list[tuple[int, int]], message: str
) -> None:
    # Read on the oracle (CadQuery 2.3.0): after `polyline([(3, 1)])` a box
    # and a circle are centred on the plane's origin and a `lineTo` starts
    # there, not at (3, 1) as after `moveTo(3, 1)`. The subset does not model
    # what such a polyline leaves on the stack.
    for plane in ("XY", "YZ", "XZ", "ZX"):
        with pytest.raises(cq.UnsupportedApi, match=rf"^Workplane\.polyline\({message}\)$"):
            cq.Workplane(plane).polyline(points)


def test_line_to_goes_on_from_a_point_or_a_path_only() -> None:
    closed = cq.Workplane("XY").polyline(TRIANGLE).close()
    for wp, kind in ((cq.Workplane("XY").box(1, 1, 1), "Solid"), (closed, "Sketch")):
        with pytest.raises(RuntimeError, match=rf"^Cannot convert object type '{kind}' to vector$"):
            wp.lineTo(1, 1)


@pytest.mark.parametrize(
    ("form", "call"),
    [
        ("moveTo", lambda wp: wp.moveTo(0, 0)),
        ("polyline", lambda wp: wp.polyline(TRIANGLE)),
    ],
)
def test_a_second_pending_wire_is_unsupported(
    form: str, call: Callable[[cq.Workplane], cq.Workplane]
) -> None:
    pending = [
        cq.Workplane("XY").moveTo(1, 1),
        cq.Workplane("XY").lineTo(1, 1),
        cq.Workplane("XY").polyline(TRIANGLE).close(),
        cq.Workplane("XY").circle(1),
    ]
    for wp in pending:
        with pytest.raises(cq.UnsupportedApi, match=rf"^Workplane\.{form} on a pending wire$"):
            call(wp)


def test_move_to_and_polyline_leave_a_solid_in_the_chain() -> None:
    boxed = cq.Workplane("XY").box(1, 1, 1)
    for wp in (boxed.moveTo(2, 0), boxed.polyline(TRIANGLE)):
        assert wp._solids() == ()
        assert wp._parent is boxed


def ring(angle: float) -> cq.Workplane:
    square = cq.Workplane("XY").polyline([(1, 0), (2, 0), (2, 1), (1, 1)]).close()
    return square.revolve(angle, (0, 0, 0), (0, 1, 0))


@pytest.mark.parametrize(
    ("angle", "turns"), [(360, 1.0), (0, 1.0), (720, 1.0), (-270, 0.25), (450, 0.25)]
)
def test_revolve_takes_its_angle_modulo_a_full_turn(angle: float, turns: float) -> None:
    # The square's x moment is 1.5: Pappus, V = 2 pi turns 1.5.
    assert fixture_cases.close(solid_volume(ring(angle)), 2 * math.pi * turns * 1.5)


def test_revolve_turns_right_handed_from_axis_start_to_end() -> None:
    square = cq.Workplane("XY").polyline([(1, 0), (2, 0), (2, 1), (1, 1)]).close()
    for end, z_sign in (((0, 1, 0), -1), ((0, -1, 0), 1)):
        (solid,) = square.revolve(90, (0, 0, 0), end)._solids()
        assert solid.measure().centroid[2] * z_sign > 0


def test_revolve_axis_points_are_in_the_planes_coordinates() -> None:
    # The plane is moved 5 along x: the axis through its (0, 0) is world
    # x = 5, and the square 1..2 from it has the same volume as at 0.
    moved = cq.Workplane("XY").transformed(offset=cq.Vector(5, 0, 0))
    square = moved.polyline([(1, 0), (2, 0), (2, 1), (1, 1)]).close()
    (solid,) = square.revolve(360, (0, 0, 0), (0, 1, 0))._solids()
    assert fixture_cases.close(solid.measure().volume, 3 * math.pi)
    assert fixture_cases.close(solid.measure().centroid[0], 5.0)


def test_revolve_needs_one_pending_sketch() -> None:
    for wp in (
        cq.Workplane("XY"),
        cq.Workplane("XY").box(1, 1, 1),
        cq.Workplane("XY").lineTo(1, 0),
    ):
        with pytest.raises(ValueError, match=r"^No pending wires present$"):
            wp.revolve(360, (0, 0, 0), (0, 1, 0))


def test_a_revolution_is_fused_with_the_solid_in_its_chain() -> None:
    # A unit box at x 2..3, y 1..2, z -0.5..0.5 lies inside the ring of the
    # square x 1..4, y 0..3 about y (its radii run 2..sqrt(9.25) < 4), so
    # the union is the ring alone: 2 pi 2.5 9 = 45 pi, one solid.
    block = cq.Workplane("XY").transformed(offset=cq.Vector(2.5, 1.5, 0)).box(1, 1, 1)
    back = block.transformed(offset=cq.Vector(-2.5, -1.5, 0))
    square = back.moveTo(1, 0).lineTo(4, 0).lineTo(4, 3).lineTo(1, 3).close()
    both = square.revolve(360, (0, 0, 0), (0, 1, 0))
    assert fixture_cases.close(solid_volume(both), 45 * math.pi)


def matrix(axis: int, degrees: float) -> list[list[float]]:
    """The right-handed rotation by `degrees` about world axis `axis`."""
    c, s = math.cos(math.radians(degrees)), math.sin(math.radians(degrees))
    i, j = [(1, 2), (2, 0), (0, 1)][axis]
    m = [[float(r == k) for k in range(3)] for r in range(3)]
    m[i][i], m[i][j], m[j][i], m[j][j] = c, -s, s, c
    return m


def product(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
    return [[math.fsum(a[r][k] * b[k][c] for k in range(3)) for c in range(3)] for r in range(3)]


angles = st.floats(-360, 360, allow_nan=False)
lengths = st.floats(-50, 50, allow_nan=False)
VECTORS = st.builds(cq.Vector, angles, angles, angles)
OFFSETS = st.builds(cq.Vector, lengths, lengths, lengths)
# Absolute, on unit axes and points of size ~100: a few hundred ulps of the
# trigonometry and products, far below any wrong order or sign of a turn.
AXIS_SLACK = 1e-12


@settings(max_examples=60, deadline=None)
@given(VECTORS, OFFSETS, VECTORS, OFFSETS)
def test_transformed_turns_by_rx_ry_rz_about_its_own_axes(
    first: cq.Vector, first_at: cq.Vector, rotate: cq.Vector, offset: cq.Vector
) -> None:
    # Two calls, so the second turns about axes that are not the world's
    # and moves by an offset in a plane that is not XY.
    parent = cq.Workplane("XY").transformed(rotate=first, offset=first_at)
    child = parent.transformed(rotate=rotate, offset=offset)
    p = parent._plane
    basis = [[p.x[r], p.y[r], p.z[r]] for r in range(3)]
    local = product(product(matrix(0, rotate.x), matrix(1, rotate.y)), matrix(2, rotate.z))
    want = product(basis, local)
    for column, axis in enumerate((child._plane.x, child._plane.y, child._plane.z)):
        assert all(abs(axis[r] - want[r][column]) <= AXIS_SLACK for r in range(3))
    origin = [
        p.origin[r] + math.fsum(basis[r][k] * (offset.x, offset.y, offset.z)[k] for k in range(3))
        for r in range(3)
    ]
    assert all(abs(child._plane.origin[r] - origin[r]) <= AXIS_SLACK * 100 for r in range(3))


@settings(max_examples=30, deadline=None)
@given(VECTORS, OFFSETS)
def test_a_zero_rotation_keeps_the_axes_exactly(first: cq.Vector, offset: cq.Vector) -> None:
    parent = cq.Workplane("XY").transformed(rotate=first)
    child = parent.transformed(rotate=cq.Vector(0, 0, 0), offset=offset)
    assert (child._plane.x, child._plane.y, child._plane.z) == (
        parent._plane.x,
        parent._plane.y,
        parent._plane.z,
    )


# Arbitrary text, surrogates and NULs included: `run` under `cq` returns.
@settings(max_examples=40, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(st.text(alphabet=st.characters(exclude_categories=()), max_size=200))
def test_run_never_raises_on_any_text_under_cq(text: str) -> None:
    result = ag.run(text, dialect="cq", timeout=2.0)
    assert isinstance(result.status, ag.Status)


# Lines that reach each branch of a `cq` program's ending, in any order.
LINES = [
    "import cadquery as cq",
    "import cadquery",
    "from cadquery import Workplane",
    "from cadquery import Sketch",
    "import cadquery.occ_impl",
    "result = cq.Workplane('XY')",
    "result = 5",
    "r = cq.Workplane('XY')",
    "r = 5",
    "r = cq.Workplane('XY').box(1, 2, 3)",
    "del r",
    "show_object(result)",
    "show_object(cq.Workplane('XY'))",
    "show_object(None, name='part')",
    "cq.Workplane('XY').box(1, 1, 1)",
    "result = cq.Workplane('XY').box(1, 2, 3)",
    "result = cq.Workplane('XY').box(0, 2, 3)",
    "result = cq.Workplane('XY').transformed(rotate=cq.Vector(10, 20, 30))",
    "result = result.transformed(offset=cq.Vector(0, 0, 1))",
    "result = result.box(1, 1, 1)",
    "result = result.transformed(rotate=cq.Vector(0, 90, 0))",
    "cq.Workplane('XZ')",
    "result = cq.Workplane('XY').moveTo(2, 0).lineTo(3, 0).lineTo(3, 1)",
    "result = cq.Workplane('XY').polyline([(2, 0), (3, 0), (3, 1)])",
    "result = cq.Workplane('XY').polyline([(0, 0), (1, 0)])",
    "result = result.lineTo(2, 1)",
    "result = result.close()",
    "result = result.revolve(360, (0, 0, 0), (0, 1, 0))",
    "result = result.revolve(90, (0, 0, 0), (1, 0, 0))",
    "result = result.extrude(1)",
    "del result",
    "raise SystemExit(0)",
]


@settings(max_examples=40, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(st.lists(st.sampled_from(LINES), max_size=6))
def test_run_never_raises_on_programs_of_the_subsets_lines(lines: list[str]) -> None:
    result = ag.run("\n".join(lines), dialect="cq", timeout=2.0)
    assert result.status in (
        ag.Status.OK,
        ag.Status.ARRIS_REFUSAL,
        ag.Status.UNSUPPORTED_API,
        ag.Status.RUNTIME,
    ), result.message


# Forms outside the census (step 6): every implemented call checks its form.
BOXED = cq.Workplane("XY").box(1, 1, 1)
PATH = cq.Workplane("XY").moveTo(1, 0)
RING = cq.Workplane("XY").polyline([(1, 0), (2, 0), (2, 1), (1, 1)]).close()
OUTSIDE_FORMS: list[tuple[str, Callable[[], object]]] = [
    ("cq.Workplane()", lambda: cq.Workplane()),
    ("cq.Workplane(num)", lambda: cq.Workplane(5)),  # type: ignore[arg-type]
    ("cq.Workplane(origin=tuple)", lambda: cq.Workplane(origin=(0, 0, 0))),
    ("cq.Workplane(str; origin=list)", lambda: cq.Workplane("XY", origin=[0, 0, 0])),  # type: ignore[arg-type]
    ("cq.Workplane(str; origin=call)", lambda: cq.Workplane("XY", origin=cq.Vector(0, 0, 0))),  # type: ignore[arg-type]
    ("cq.Workplane(str; origin=tuple of 2 numbers)", lambda: cq.Workplane("XY", origin=(1, 2))),  # type: ignore[arg-type]
    (
        "cq.Workplane(str; origin=tuple of non-numbers)",
        lambda: cq.Workplane("XY", origin=(1, 2, "3")),  # type: ignore[arg-type]
    ),
    ("cq.Workplane(str, tuple)", lambda: cq.Workplane("XY", (0, 0, 0))),
    ("cq.Vector(num, num)", lambda: cq.Vector(1, 2)),  # type: ignore[call-arg]
    ("cq.Vector(num, num, str)", lambda: cq.Vector(1, 2, "3")),  # type: ignore[arg-type]
    ("cq.Vector(num, num, num; w=num)", lambda: cq.Vector(1, 2, 3, w=4)),  # type: ignore[call-arg]
    ("Workplane.box(num, num)", lambda: BOXED.box(1, 2)),  # type: ignore[call-arg]
    (
        "Workplane.box(num, num, num; centered=bool)",
        lambda: BOXED.box(1, 2, 3, centered=False),  # type: ignore[call-arg]
    ),
    ("Workplane.box(num, str, num)", lambda: BOXED.box(1, "2", 3)),  # type: ignore[arg-type]
    ("Workplane.box(bool, num, num)", lambda: BOXED.box(True, 2, 3)),
    ("Workplane.transformed(tuple)", lambda: BOXED.transformed((0, 0, 1))),  # type: ignore[arg-type]
    ("Workplane.transformed(offset=tuple)", lambda: BOXED.transformed(offset=(0, 0, 1))),  # type: ignore[arg-type]
    ("Workplane.transformed(origin=call)", lambda: BOXED.transformed(origin=cq.Vector(0, 0, 0))),  # type: ignore[call-arg]
    ("Workplane.circle(num; clean=bool)", lambda: BOXED.circle(1, clean=True)),  # type: ignore[call-arg]
    ("Workplane.circle(radius=num)", lambda: BOXED.circle(radius=1)),
    ("Workplane.extrude(num; both=bool)", lambda: PATH.extrude(1, both=True)),  # type: ignore[call-arg]
    ("Workplane.extrude(num, bool)", lambda: PATH.extrude(1, True)),  # type: ignore[call-arg]
    ("Workplane.moveTo(num)", lambda: BOXED.moveTo(1)),
    ("Workplane.moveTo()", lambda: BOXED.moveTo()),
    ("Workplane.lineTo(tuple)", lambda: PATH.lineTo((1, 1))),  # type: ignore[call-arg, arg-type]
    ("Workplane.polyline(tuple)", lambda: BOXED.polyline(((0, 0), (1, 0)))),
    (
        "Workplane.polyline(list; includeCurrent=bool)",
        lambda: BOXED.polyline(TRIANGLE, includeCurrent=True),  # type: ignore[call-arg]
    ),
    (
        "Workplane.polyline(list with a point of 3 numbers)",
        lambda: BOXED.polyline([(0, 0, 0), (1, 0, 0)]),
    ),
    ("Workplane.polyline(list with a point of 1 numbers)", lambda: BOXED.polyline([(0,), (1, 0)])),
    ("Workplane.polyline(list with a point of str)", lambda: BOXED.polyline(["ab", "cd"])),
    ("Workplane.polyline(list with a point of call)", lambda: BOXED.polyline([cq.Vector(0, 0, 0)])),
    ("Workplane.close(bool)", lambda: PATH.close(True)),  # type: ignore[call-arg]
    ("Workplane.revolve()", lambda: RING.revolve()),  # type: ignore[call-arg]
    ("Workplane.revolve(num)", lambda: RING.revolve(360)),  # type: ignore[call-arg]
    ("Workplane.revolve(num, tuple)", lambda: RING.revolve(360, (0, 0, 0))),  # type: ignore[call-arg]
    (
        "Workplane.revolve(num, tuple, tuple; combine=bool)",
        lambda: RING.revolve(360, (0, 0, 0), (0, 1, 0), combine=False),  # type: ignore[call-arg]
    ),
    ("Workplane.revolve(num, list, tuple)", lambda: RING.revolve(360, [0, 0, 0], (0, 1, 0))),
    (
        "Workplane.revolve(num, tuple of 4 numbers)",
        lambda: RING.revolve(360, (0, 0, 0, 0), (0, 1, 0)),
    ),
    (
        "Workplane.revolve(num, tuple of non-numbers)",
        lambda: RING.revolve(360, (0, 0, 0), ("a", "b")),
    ),
    ("Workplane.union()", lambda: BOXED.union()),  # type: ignore[call-arg]
    ("Workplane.union(call; clean=bool)", lambda: BOXED.union(BOXED, clean=False)),  # type: ignore[call-arg]
    ("Workplane.cut(call, call)", lambda: BOXED.cut(BOXED, BOXED)),  # type: ignore[call-arg]
]


@pytest.mark.parametrize(("form", "call"), OUTSIDE_FORMS, ids=[form for form, _ in OUTSIDE_FORMS])
def test_a_form_outside_the_census_is_unsupported_naming_it(
    form: str, call: Callable[[], object]
) -> None:
    with pytest.raises(cq.UnsupportedApi) as raised:
        call()
    assert str(raised.value) == form


def test_a_census_form_given_a_call_with_a_census_keyword_in_either_order() -> None:
    wp = cq.Workplane("XY")
    a = wp.transformed(offset=cq.Vector(1, 0, 0), rotate=cq.Vector(0, 0, 90))
    b = wp.transformed(rotate=cq.Vector(0, 0, 90), offset=cq.Vector(1, 0, 0))
    assert a._plane.origin == b._plane.origin
    assert a._plane.x == b._plane.x


def test_box_with_a_negative_dimension_is_cadquerys_runtime_error() -> None:
    # CadQuery 2.3.0 ends `runtime` (Standard_DomainError); arris would build.
    for dims in [(-1, 2, 3), (1, -2, 3), (1, 2, -3)]:
        with pytest.raises(ValueError, match=r"negative dimension"):
            cq.Workplane("XY").box(*dims)


def test_box_with_a_zero_dimension_is_the_kernels_refusal() -> None:
    with pytest.raises(arris.ArrisError):
        cq.Workplane("XY").box(0, 2, 3)


@pytest.mark.parametrize(
    ("form", "call"),
    [
        ("transformed", lambda wp: wp.transformed(offset=cq.Vector(0, 0, 1))),
        ("box", lambda wp: wp.box(1, 1, 1)),
        ("union", lambda wp: wp.union(BOXED)),
        ("cut", lambda wp: wp.cut(BOXED)),
    ],
)
def test_a_call_that_would_drop_a_pending_wire_is_unsupported(
    form: str, call: Callable[[cq.Workplane], cq.Workplane]
) -> None:
    # `box` on a lone `moveTo` point centres the box there and drops no wire
    # (`test_cq_box.py`); every other call here would drop that point.
    at_point = [] if form == "box" else [cq.Workplane("XY").box(1, 1, 1).moveTo(1, 1)]
    pending = [
        *at_point,
        cq.Workplane("XY").box(1, 1, 1).moveTo(1, 1).lineTo(2, 1),
        cq.Workplane("XY").lineTo(1, 1),
        cq.Workplane("XY").polyline(TRIANGLE).close(),
        cq.Workplane("XY").circle(1),
    ]
    for wp in pending:
        with pytest.raises(cq.UnsupportedApi, match=rf"^Workplane\.{form} on a pending wire$"):
            call(wp)


def test_the_form_check_runs_before_the_stack_is_looked_at() -> None:
    # An empty stack would be a ValueError for `extrude`; a wrong form is
    # unsupported first, so the model reads which one.
    with pytest.raises(cq.UnsupportedApi):
        cq.Workplane("XY").extrude(1, both=True)  # type: ignore[call-arg]


def test_the_docstring_examples_of_the_form_checks_run() -> None:
    assert doctest.testmod(_forms).failed == 0


POSITIVE = st.floats(min_value=0.5, max_value=10, allow_nan=False)
PLACE = st.floats(min_value=-5, max_value=5, allow_nan=False)
TURN = st.floats(min_value=-180, max_value=180, allow_nan=False)


@st.composite
def parts(draw: st.DrawFn) -> cq.Workplane:
    """A solid on a (maybe turned) plane, built by one of the subset's recipes."""
    wp = cq.Workplane("XY")
    if draw(st.booleans()):
        wp = wp.transformed(
            offset=cq.Vector(draw(PLACE), draw(PLACE), draw(PLACE)),
            rotate=cq.Vector(draw(TURN), draw(TURN), draw(TURN)),
        )
    match draw(st.sampled_from(["box", "cylinder", "prism", "ring"])):
        case "box":
            return wp.box(draw(POSITIVE), draw(POSITIVE), draw(POSITIVE))
        case "cylinder":
            return wp.circle(draw(POSITIVE)).extrude(draw(POSITIVE))
        case "prism":
            a, b = draw(POSITIVE), draw(POSITIVE)
            return wp.polyline([(0, 0), (a, 0), (a, b)]).close().extrude(draw(POSITIVE))
        case _:
            r, w, h = draw(POSITIVE), draw(POSITIVE), draw(POSITIVE)
            sketch = wp.polyline([(r, 0), (r + w, 0), (r + w, h), (r, h)]).close()
            return sketch.revolve(draw(st.sampled_from([90, 180, 360])), (0, 0, 0), (0, 1, 0))


@settings(max_examples=60, deadline=None)
@given(parts(), st.lists(st.tuples(st.sampled_from(["union", "cut"]), parts()), max_size=3))
def test_chains_of_census_forms_run_or_end_in_a_kernel_refusal(
    base: cq.Workplane, steps: list[tuple[str, cq.Workplane]]
) -> None:
    try:
        wp = base
        for name, other in steps:
            wp = wp.union(other) if name == "union" else wp.cut(other)
        _result.solid_of(wp, "the part")
    except arris.ArrisError:
        pass


# One call or keyword outside the census, on any receiver.
BAD_CALLS: list[Callable[[cq.Workplane], object]] = [
    lambda wp: wp.sphere(1),
    lambda wp: wp.faces(">Z"),
    lambda wp: wp.hole(1),
    lambda wp: wp.box(1, 2, 3, centered=False),  # type: ignore[call-arg]
    lambda wp: wp.box(1, 2),  # type: ignore[call-arg]
    lambda wp: wp.circle(1, 2),  # type: ignore[call-arg]
    lambda wp: wp.extrude(1, taper=5),  # type: ignore[call-arg]
    lambda wp: wp.extrude("1"),  # type: ignore[arg-type]
    lambda wp: wp.transformed((0, 0, 1)),  # type: ignore[arg-type]
    lambda wp: wp.transformed(offset=(0, 0, 1)),  # type: ignore[arg-type]
    lambda wp: wp.moveTo(1),
    lambda wp: wp.lineTo(1, 2, 3),  # type: ignore[call-arg]
    lambda wp: wp.polyline([(0, 0, 0)]),
    lambda wp: wp.close(1),  # type: ignore[call-arg]
    lambda wp: wp.revolve(90),  # type: ignore[call-arg]
    lambda wp: wp.revolve(90, (0, 0), (0, 1), combine=False),  # type: ignore[call-arg]
    lambda wp: wp.union(wp, wp),  # type: ignore[call-arg]
    lambda wp: wp.cut(),  # type: ignore[call-arg]
]


@settings(max_examples=60, deadline=None)
@given(
    st.one_of(
        st.just(cq.Workplane("XY")),
        parts(),
        st.sampled_from([cq.Workplane("XY").circle(1), PATH, RING]),
    ),
    st.sampled_from(BAD_CALLS),
)
def test_a_call_or_keyword_outside_the_census_is_unsupported_never_runtime(
    receiver: cq.Workplane, bad: Callable[[cq.Workplane], object]
) -> None:
    with pytest.raises(cq.UnsupportedApi):
        bad(receiver)

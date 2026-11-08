"""The `cq` dialect: `cadquery` is the subset, a result resolves to one solid.

ADR-0007. Fixtures under `tests/fixtures/cq/` hold one program per outcome,
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
from arris_gym.cq import _result, _vector, _workplane
from arris_gym.fidelity import OracleReport, OracleStatus, program_sha256

CASES = fixture_cases.load("cq")
RECORDED = [c for c in CASES if (fixture_cases.ROOT / "cq" / c.slug / "oracle.json").is_file()]


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
    assert report.measures.solids == 1
    want = case.expected["measures"]
    assert isinstance(want, dict)
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


def test_a_workplane_holding_several_solids_is_outside_the_subset() -> None:
    shown = cq.Workplane("XY")._derive(box(0), box(5), box(10))
    with pytest.raises(cq.UnsupportedApi, match=r"^a Workplane holding 3 solids$"):
        _result.solid_of(shown, "it")


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


@pytest.mark.parametrize("plane", ["XZ", "YZ", "front", "xy", ""])
def test_a_named_plane_but_xy_is_unsupported(plane: str) -> None:
    with pytest.raises(cq.UnsupportedApi, match=r"^cq\.Workplane\("):
        cq.Workplane(plane)


def test_the_module_shows_programs_cadquery_names_alone() -> None:
    public = sorted(n for n in vars(cq) if not _workplane.is_python_name(n))
    assert public == ["UnsupportedApi", "Vector", "Workplane"]


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
    boxed = cq.Workplane("XY").box(2, 2, 2)
    for wp in (boxed, boxed.transformed(offset=cq.Vector(0, 0, 1.5))):
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


def test_a_disjoint_union_keeps_both_solids_and_cannot_be_shown() -> None:
    a = cq.Workplane("XY").box(1, 1, 1)
    b = cq.Workplane("XY").transformed(offset=cq.Vector(5, 0, 0)).box(1, 1, 1)
    both = a.union(b)
    assert len(both._stack) == 2
    with pytest.raises(cq.UnsupportedApi, match=r"^a Workplane holding 2 solids$"):
        both.cut(a)


def test_a_cut_that_leaves_a_cavity_is_one_solid() -> None:
    block = cq.Workplane("XY").box(3, 3, 3)
    cavity = cq.Workplane("XY").box(1, 1, 1)
    hollow = block.cut(cavity)
    assert len(hollow._stack) == 1
    assert fixture_cases.close(solid_volume(hollow), 26.0)


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


def test_union_and_cut_need_a_solid_on_both_sides() -> None:
    empty, boxed = cq.Workplane("XY"), cq.Workplane("XY").box(1, 1, 1)
    calls: list[Callable[[], cq.Workplane]] = [
        lambda: empty.union(boxed),
        lambda: boxed.union(empty),
        lambda: empty.cut(boxed),
        lambda: boxed.cut(empty),
    ]
    for call in calls:
        with pytest.raises(ValueError, match=r"solid"):
            call()


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

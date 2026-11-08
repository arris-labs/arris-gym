"""The `cq` dialect: `cadquery` is the subset, a result resolves to one solid.

ADR-0007. Fixtures under `tests/fixtures/cq/` hold one program per outcome,
expectations from the program's text (tests/fixture_cases.py).
"""

from __future__ import annotations

import copy
import doctest
import hashlib

import arris.build
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

import arris_gym as ag
import arris_gym.cq as cq
import fixture_cases
from arris_gym.cq import _result, _workplane

CASES = fixture_cases.load("cq")


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.slug)
def test_a_fixture_program_gives_its_expected_result(case: fixture_cases.Case) -> None:
    result = fixture_cases.run(case)
    assert fixture_cases.check(result, case.expected) == []
    assert result.program_sha256 == hashlib.sha256(case.program.encode()).hexdigest()


def test_a_shown_workplane_holding_one_solid_is_its_body() -> None:
    # No call of the subset puts a solid on the stack yet, so the program
    # reaches past it: this is the sandbox's path from a stack to a body.
    program = (
        "import arris.build as b\n"
        "import cadquery as cq\n"
        "box = b.Solid.box((0, 0, 0), (1, 2, 3))\n"
        "show_object(cq.Workplane('XY')._derive(box))\n"
    )
    result = ag.run(program, dialect="cq")
    assert result.status is ag.Status.OK, result.message
    assert result.dialect is ag.Dialect.CQ
    assert result.measures is not None
    assert fixture_cases.close(result.measures.volume, 6.0)


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
    assert public == ["UnsupportedApi", "Workplane"]


def test_the_docstring_examples_run() -> None:
    assert doctest.testmod(cq).failed == 0
    assert doctest.testmod(_workplane).failed == 0


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
    "cq.Workplane('XZ')",
    "del result",
    "raise SystemExit(0)",
]


@settings(max_examples=40, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(st.lists(st.sampled_from(LINES), max_size=6))
def test_run_never_raises_on_programs_of_the_subsets_lines(lines: list[str]) -> None:
    result = ag.run("\n".join(lines), dialect="cq", timeout=2.0)
    assert result.status in (ag.Status.UNSUPPORTED_API, ag.Status.RUNTIME), result.message

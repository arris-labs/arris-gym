"""`polygon` is a regular n-gon centred on its point, its first vertex on the plane's +x.

Read on the oracle (CadQuery 2.3.0, `ok-polygon-*` beside their `oracle.json`):
`Workplane.polygon(nSides, diameter)` makes one closed wire whose vertices lie
on the circle of `diameter`, the first at angle 0 in the plane's own axes, at
each point of the stack: the origin of an empty stack or a `moveTo` point;
after `transformed` or `workplane(offset=…)` the point is on the moved plane,
and its `extrude` is fused with a solid in the chain (`combine=True`).
"""

import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import arris_gym as ag
import arris_gym.cq as cq
import fixture_cases
from arris_gym.census import CorpusProgram, reach
from arris_gym.fidelity import (
    FidelityOutcome,
    OracleReport,
    OracleStatus,
    compare,
    program_sha256,
)

PLANES = ["XY", "YZ", "XZ", "ZX"]
FIXTURES = [
    "ok-polygon-centred-xy",
    "ok-polygon-at-point-yz",
    "ok-polygon-at-point-xz",
    "ok-polygon-offset-zx",
    "ok-polygon-transformed-xy",
    "ok-polygon-fused-xy",
    "ok-polygon-grease-nipple",
    "ok-polygon-negative-diameter",
]
# The other last objects the subset puts on a stack, read on the oracle
# (2026-11-14): CadQuery builds a polygon on each, centred on the object's
# `Center()`, which the subset does not model; `cq` refuses each.
CONTEXTS = [
    "unsupported-polygon-on-solid",
    "unsupported-polygon-on-compound",
    "unsupported-polygon-on-closed-wire",
    "unsupported-polygon-on-pending-wire",
    "unsupported-polygon-on-pending-circle",
]
# Arguments CadQuery fails on (Q1 of plans/lift-polygon), each read on the
# oracle (`oracle.json` beside it): `cq` ends each `runtime` and the rows agree.
FAILING = [
    "runtime-polygon-float-sides",
    "runtime-polygon-zero-sides",
    "runtime-polygon-negative-sides",
    "runtime-polygon-one-side",
    "runtime-polygon-zero-diameter",
]


@pytest.mark.parametrize("slug", FIXTURES)
def test_polygon_fixtures_agree_with_the_recorded_oracle(slug: str) -> None:
    case = next(c for c in fixture_cases.load("cq") if c.slug == slug)
    assert "polygon(" in case.program
    path = fixture_cases.ROOT / "cq" / slug / "oracle.json"
    report = OracleReport.model_validate_json(path.read_text())
    assert compare(fixture_cases.run(case), report).outcome is FidelityOutcome.AGREE


@pytest.mark.parametrize("slug", FIXTURES)
def test_the_oracle_holds_each_polygons_closed_form(slug: str) -> None:
    # The semantics are CadQuery's, not only `cq`'s reading of them: the
    # oracle's own measures meet the closed form in `expected.json`.
    case = next(c for c in fixture_cases.load("cq") if c.slug == slug)
    expected = case.expected["measures"]
    assert isinstance(expected, dict)
    path = fixture_cases.ROOT / "cq" / slug / "oracle.json"
    measures = OracleReport.model_validate_json(path.read_text()).measures
    assert measures is not None
    assert fixture_cases.close(measures.volume, expected["volume"])
    assert fixture_cases.close(measures.area, expected["area"])
    assert measures.faces == expected["faces"]
    for got, want in zip(measures.centroid, expected["centroid"], strict=True):
        assert fixture_cases.close(got, want)
    for got_corner, want_corner in zip(measures.bounds, expected["bounds"], strict=True):
        for got, want in zip(got_corner, want_corner, strict=True):
            assert fixture_cases.close(got, want)


def _world(plane: str, u: float, v: float, w: float) -> list[float]:
    """Local (u, v, w) on a named plane at the world origin, in world coordinates."""
    if plane == "XY":
        return [u, v, w]
    if plane == "YZ":
        return [w, u, v]
    if plane == "XZ":
        return [u, -w, v]
    assert plane == "ZX"
    return [v, w, u]


@settings(max_examples=30, deadline=None)
@given(
    plane=st.sampled_from(PLANES),
    sides=st.integers(3, 12),
    diameter=st.integers(1, 40).map(lambda n: n / 4),
    point=st.none() | st.tuples(st.integers(-6, 6), st.integers(-6, 6)),
    offset=st.integers(-8, 8),
    distance=st.one_of(st.integers(-8, -1), st.integers(1, 8)),
)
def test_a_polygon_is_the_regular_n_gon_on_its_point(
    plane: str,
    sides: int,
    diameter: float,
    point: tuple[int, int] | None,
    offset: int,
    distance: int,
) -> None:
    (x, y) = point if point is not None else (0, 0)
    at_point = "" if point is None else f".moveTo({x}, {y})"
    program = (
        "import cadquery as cq\n"
        f"r = cq.Workplane('{plane}').workplane(offset={offset})"
        f"{at_point}.polygon({sides}, {diameter}).extrude({distance})\n"
    )
    result = ag.run(program, dialect="cq")
    radius = diameter / 2
    # The n-gon inscribed in the circle of `radius`: its area, its side, and
    # its vertices from angle 0 (the plane's +x) on.
    area = sides / 2 * radius**2 * math.sin(2 * math.pi / sides)
    side = 2 * radius * math.sin(math.pi / sides)
    corners = [
        _world(plane, x + radius * math.cos(a), y + radius * math.sin(a), w)
        for a in (2 * math.pi * i / sides for i in range(sides))
        for w in (offset, offset + distance)
    ]
    expected: dict[str, object] = {
        "dialect": "cq",
        "status": "ok",
        "measures": {
            "volume": area * abs(distance),
            "area": 2 * area + sides * side * abs(distance),
            "centroid": _world(plane, x, y, offset + distance / 2),
            "bounds": [
                [min(c[k] for c in corners) for k in range(3)],
                [max(c[k] for c in corners) for k in range(3)],
            ],
            "faces": sides + 2,
            "face_kinds": [["plane", sides + 2]],
            "shells": 1,
            "genus": 0,
        },
    }
    assert fixture_cases.check(result, expected) == [], result.message


def test_reach_reads_the_declared_form_only() -> None:
    def written(call: str) -> CorpusProgram:
        text = f"import cadquery as cq\nresult = cq.Workplane('XY').{call}.extrude(1)"
        return CorpusProgram(stem=call, family="f", text=text)

    assert cq.subset().admits("Workplane.polygon(num, num)")
    report = reach(
        [written("polygon(6, 4)"), written("polygon(6, 4, circumscribed=True)")], cq.subset()
    )
    assert report.stems == ("polygon(6, 4)",)
    refused = ag.run(
        "import cadquery as cq\n"
        "result = cq.Workplane('XY').polygon(6, 4, forConstruction=True).extrude(1)",
        dialect="cq",
    )
    assert refused.status is ag.Status.UNSUPPORTED_API
    assert refused.message == "Workplane.polygon(num, num; forConstruction=bool)"


@pytest.mark.parametrize("slug", CONTEXTS)
def test_a_polygon_on_any_other_last_object_is_refused(slug: str) -> None:
    case = next(c for c in fixture_cases.load("cq") if c.slug == slug)
    result = fixture_cases.run(case)
    assert result.status is ag.Status.UNSUPPORTED_API
    assert result.message == "Workplane.polygon on a non-empty stack"


def _recorded(slug: str) -> tuple[fixture_cases.Case, OracleReport]:
    case = next(c for c in fixture_cases.load("cq") if c.slug == slug)
    path = fixture_cases.ROOT / "cq" / slug / "oracle.json"
    report = OracleReport.model_validate_json(path.read_text())
    assert report.program_sha256 == program_sha256(case.program)
    return case, report


@pytest.mark.parametrize("slug", FAILING)
def test_an_argument_cadquery_fails_on_fails_on_both_sides(slug: str) -> None:
    case, report = _recorded(slug)
    assert report.status is OracleStatus.RUNTIME
    result = fixture_cases.run(case)
    assert fixture_cases.check(result, case.expected) == []
    assert compare(result, report).outcome is FidelityOutcome.AGREE


@pytest.mark.xfail(
    reason="cq ends polygon(2, d) runtime where CadQuery builds a zero-volume solid",
    raises=AssertionError,
    strict=True,
)
def test_two_sides_agree_with_the_oracles_zero_volume_solid() -> None:
    # Q1 of plans/lift-polygon: CadQuery's `polygon(2, d)` is a closed wire
    # out and back along one diameter, and its extrusion a solid of zero
    # volume its checker passes. The form is admitted, so the row is
    # `cq_bug` until `cq` builds it (ADR-0012), never `by_design`.
    directory = fixture_cases.ROOT / "regression" / "cq-polygon-two-sides"
    case = next(c for c in fixture_cases.load("regression") if c.slug == directory.name)
    report = OracleReport.model_validate_json((directory / "oracle.json").read_text())
    assert report.program_sha256 == program_sha256(case.program)
    assert report.status is OracleStatus.OK
    assert report.measures is not None
    assert report.measures.volume == 0.0
    assert not (directory / "verdict.json").exists()
    result = fixture_cases.run(case)
    assert compare(result, report).outcome is FidelityOutcome.AGREE, result.message


@settings(max_examples=30, deadline=None)
@given(
    plane=st.sampled_from(PLANES),
    point=st.none() | st.tuples(st.integers(-6, 6), st.integers(-6, 6)),
    on_slab=st.booleans(),
    # Two sides are the strict xfail `test_two_sides_agree_…` instead.
    sides=st.integers(-8, 8).filter(lambda n: n != 2),
    diameter=st.integers(-20, 20).map(lambda n: n / 4),
)
def test_a_polygon_ends_runtime_or_builds_as_its_arguments_say_in_every_admitted_context(
    plane: str, point: tuple[int, int] | None, on_slab: bool, sides: int, diameter: float
) -> None:
    # Read on the oracle (`runtime-polygon-*`, `ok-polygon-negative-diameter`):
    # fewer than three sides (two aside) or a zero diameter end `runtime`;
    # otherwise a negative diameter builds the polygon turned by pi, of the
    # same area as its positive twin.
    chain = (".box(40, 40, 2).workplane(offset=1)" if on_slab else "") + (
        "" if point is None else f".moveTo{point}"
    )
    program = (
        f"import cadquery as cq\nr = cq.Workplane('{plane}'){chain}"
        f".polygon({sides}, {diameter}).extrude(1)\n"
    )
    result = ag.run(program, dialect="cq")
    if sides < 3 or diameter == 0:
        assert result.status is ag.Status.RUNTIME, result.message
        error = "ZeroDivisionError" if sides == 0 else "ValueError"
        assert result.message.startswith(f"{error}: "), result.message
        return
    assert result.status is ag.Status.OK, result.message
    assert result.measures is not None
    radius = diameter / 2
    area = sides / 2 * radius**2 * math.sin(2 * math.pi / sides)
    # The slab is centred on the plane, its top face at offset 1, where the
    # prism starts: the prism stands on it, wholly inside its 40 x 40 top.
    assert fixture_cases.close(result.measures.volume - (3200 if on_slab else 0), area)

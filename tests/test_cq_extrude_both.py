"""`extrude(distance, both=True)` is `distance` to each side of the plane, as one prism.

Read on the oracle (CadQuery 2.3.0, `ok-extrude-both-*` beside their
`oracle.json`): `_extrude` sweeps the face `distance` each way, fuses the two
halves and cleans, so a polygon's side faces merge into one prism of height
`2|distance|`, centred on the plane; `both=False` is plain `extrude`. A
negative distance with `both` is the same prism. The fuse with, or cut from,
the chain's solid is `combine=True`'s.
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
    "ok-extrude-both-circle-xy",
    "ok-extrude-both-hexagon-xy",
    "ok-extrude-both-polygon-yz-transformed",
    "ok-extrude-both-negative-distance",
    "ok-extrude-both-false",
    "ok-extrude-both-fused",
    "ok-extrude-both-cut",
    "ok-extrude-both-hex-key-organizer",
]
# A circle's cylinder face is one under `cq` and two on the oracle, whose glue
# leaves the halves' lateral faces split: the face count is carried, never
# judged (ADR-0005), so the oracle's own count is held here.
ORACLE_FACES = {"ok-extrude-both-circle-xy": 4}


@pytest.mark.parametrize("slug", FIXTURES)
def test_extrude_both_fixtures_agree_with_the_recorded_oracle(slug: str) -> None:
    case = next(c for c in fixture_cases.load("cq") if c.slug == slug)
    assert "extrude(" in case.program
    path = fixture_cases.ROOT / "cq" / slug / "oracle.json"
    report = OracleReport.model_validate_json(path.read_text())
    assert compare(fixture_cases.run(case), report).outcome is FidelityOutcome.AGREE


@pytest.mark.parametrize("slug", FIXTURES)
def test_the_oracle_holds_each_closed_form(slug: str) -> None:
    case = next(c for c in fixture_cases.load("cq") if c.slug == slug)
    expected = case.expected["measures"]
    assert isinstance(expected, dict)
    path = fixture_cases.ROOT / "cq" / slug / "oracle.json"
    measures = OracleReport.model_validate_json(path.read_text()).measures
    assert measures is not None
    assert fixture_cases.close(measures.volume, expected["volume"])
    assert fixture_cases.close(measures.area, expected["area"])
    assert measures.faces == ORACLE_FACES.get(slug, expected["faces"])
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


@settings(max_examples=40, deadline=None)
@given(
    plane=st.sampled_from(PLANES),
    sides=st.one_of(st.none(), st.integers(3, 10)),
    size=st.integers(1, 24).map(lambda n: n / 4),
    point=st.none() | st.tuples(st.integers(-6, 6), st.integers(-6, 6)),
    offset=st.integers(-8, 8),
    distance=st.one_of(st.integers(-8, -1), st.integers(1, 8)),
    both=st.booleans(),
)
def test_both_is_distance_to_each_side_of_the_plane(
    plane: str,
    sides: int | None,
    size: float,
    point: tuple[int, int] | None,
    offset: int,
    distance: int,
    both: bool,
) -> None:
    # `sides` None is a circle of radius `size`, else a regular polygon of
    # circumdiameter `size`; the prism spans local w from `lo` to `hi`.
    (x, y) = point if point is not None else (0, 0)
    at_point = "" if point is None else f".moveTo({x}, {y})"
    profile = f".circle({size})" if sides is None else f".polygon({sides}, {size})"
    program = (
        "import cadquery as cq\n"
        f"r = cq.Workplane('{plane}').workplane(offset={offset}){at_point}{profile}"
        f".extrude({distance}, both={both})\n"
    )
    result = ag.run(program, dialect="cq")
    lo, hi = (
        (offset - abs(distance), offset + abs(distance))
        if both
        else sorted((offset, offset + distance))
    )
    height = hi - lo
    if sides is None:
        radius = size
        area, perimeter = math.pi * radius**2, 2 * math.pi * radius
        extent = [(x - radius, x + radius), (y - radius, y + radius)]
    else:
        radius = size / 2
        area = sides / 2 * radius**2 * math.sin(2 * math.pi / sides)
        perimeter = sides * 2 * radius * math.sin(math.pi / sides)
        corners = [
            (x + radius * math.cos(a), y + radius * math.sin(a))
            for a in (2 * math.pi * i / sides for i in range(sides))
        ]
        extent = [(min(c[k] for c in corners), max(c[k] for c in corners)) for k in (0, 1)]
    low = _world(plane, extent[0][0], extent[1][0], lo)
    high = _world(plane, extent[0][1], extent[1][1], hi)
    assert result.status is ag.Status.OK, result.message
    assert result.measures is not None
    measures = result.measures
    assert fixture_cases.close(measures.volume, area * height)
    assert fixture_cases.close(measures.area, 2 * area + perimeter * height)
    for got, want in zip(measures.centroid, _world(plane, x, y, (lo + hi) / 2), strict=True):
        assert fixture_cases.close(got, want)
    for k in range(3):
        assert fixture_cases.close(measures.bounds[0][k], min(low[k], high[k]))
        assert fixture_cases.close(measures.bounds[1][k], max(low[k], high[k]))


def test_reach_reads_the_declared_keyword_only() -> None:
    def written(call: str) -> CorpusProgram:
        text = f"import cadquery as cq\nresult = cq.Workplane('XY').circle(1).{call}"
        return CorpusProgram(stem=call, family="f", text=text)

    assert cq.subset().admits("Workplane.extrude(num; both=bool)")
    report = reach(
        [
            written("extrude(2, both=True)"),
            written("extrude(2, taper=5)"),
            written("extrude(2, True)"),
        ],
        cq.subset(),
    )
    assert report.stems == ("extrude(2, both=True)",)
    refused = ag.run(
        "import cadquery as cq\nresult = cq.Workplane('XY').circle(1).extrude(2, True)",
        dialect="cq",
    )
    assert refused.status is ag.Status.UNSUPPORTED_API
    assert refused.message == "Workplane.extrude(num, bool)"


# Read on the oracle (2026-11-14, `oracle.json` beside each; Q1 of
# plans/lift-extrude-both): a zero distance, with or without `both`, fails in
# the sweep (`Standard_ConstructionError`), and `both` on a stack holding no
# pending wire fails as `extrude` does (`No pending wires present`). `cq` ends
# each `runtime` and the rows agree.
FAILING = [
    "runtime-extrude-zero",
    "runtime-extrude-zero-both",
    "runtime-extrude-both-on-empty-stack",
    "runtime-extrude-both-on-solid",
    "runtime-extrude-both-on-open-path",
    "runtime-extrude-both-on-point",
]


def _recorded(slug: str) -> tuple[fixture_cases.Case, OracleReport]:
    case = next(c for c in fixture_cases.load("cq") if c.slug == slug)
    path = fixture_cases.ROOT / "cq" / slug / "oracle.json"
    report = OracleReport.model_validate_json(path.read_text())
    assert report.program_sha256 == program_sha256(case.program)
    return case, report


@pytest.mark.parametrize("slug", FAILING)
def test_an_extrusion_cadquery_fails_on_fails_on_both_sides(slug: str) -> None:
    case, report = _recorded(slug)
    assert report.status is OracleStatus.RUNTIME
    result = fixture_cases.run(case)
    assert fixture_cases.check(result, case.expected) == []
    assert compare(result, report).outcome is FidelityOutcome.AGREE


def test_the_closed_path_agrees_with_the_recorded_oracle() -> None:
    case, report = _recorded("ok-extrude-both-closed-path")
    result = fixture_cases.run(case)
    assert fixture_cases.check(result, case.expected) == []
    assert compare(result, report).outcome is FidelityOutcome.AGREE


def test_two_sketches_are_refused_where_the_second_is_drawn() -> None:
    # CadQuery extrudes both circles (a pending wire each, the oracle answers
    # `ok`, an annulus, V = 6 pi in `oracle.json`); the subset holds one
    # sketch on a stack, so `circle` after `circle` is refused before
    # `extrude` is reached.
    case = next(
        c for c in fixture_cases.load("cq") if c.slug == "unsupported-extrude-both-two-sketches"
    )
    result = fixture_cases.run(case)
    assert result.status is ag.Status.UNSUPPORTED_API
    assert result.message == "Workplane.circle on a non-empty stack"


@settings(max_examples=30, deadline=None)
@given(
    plane=st.sampled_from(PLANES),
    stack=st.sampled_from(
        [
            "",
            ".box(1, 1, 1)",
            ".moveTo(1, 2)",
            ".moveTo(1, 2).lineTo(3, 4)",
            ".circle(1).extrude(1)",
        ]
    ),
    distance=st.integers(-8, 8),
    both=st.booleans(),
)
def test_an_extrusion_with_no_pending_sketch_ends_runtime(
    plane: str, stack: str, distance: int, both: bool
) -> None:
    program = (
        f"import cadquery as cq\nr = cq.Workplane('{plane}'){stack}"
        f".extrude({distance}, both={both})\n"
    )
    result = ag.run(program, dialect="cq")
    assert result.status is ag.Status.RUNTIME, result.message
    assert result.message == "ValueError: No pending wires present"


@settings(max_examples=30, deadline=None)
@given(
    plane=st.sampled_from(PLANES),
    profile=st.sampled_from([".circle(1)", ".polygon(6, 2)", ".moveTo(1, 1).circle(2)"]),
    on_slab=st.booleans(),
    both=st.booleans(),
)
def test_a_zero_distance_ends_runtime_in_every_admitted_context(
    plane: str, profile: str, on_slab: bool, both: bool
) -> None:
    chain = ".box(4, 4, 2).workplane(offset=1)" if on_slab else ""
    program = (
        f"import cadquery as cq\nr = cq.Workplane('{plane}'){chain}{profile}"
        f".extrude(0, both={both})\n"
    )
    result = ag.run(program, dialect="cq")
    assert result.status is ag.Status.RUNTIME, result.message
    assert result.message == (
        f"ValueError: Workplane.extrude(0, both={both}): a zero distance "
        "(CadQuery's Standard_ConstructionError)"
    )

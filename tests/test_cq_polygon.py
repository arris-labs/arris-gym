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
from arris_gym.fidelity import FidelityOutcome, OracleReport, compare

PLANES = ["XY", "YZ", "XZ", "ZX"]
FIXTURES = [
    "ok-polygon-centred-xy",
    "ok-polygon-at-point-yz",
    "ok-polygon-at-point-xz",
    "ok-polygon-offset-zx",
    "ok-polygon-transformed-xy",
    "ok-polygon-fused-xy",
    "ok-polygon-grease-nipple",
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

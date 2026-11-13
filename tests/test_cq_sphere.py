"""`sphere` is centred on its point, its poles on the plane's normal.

Read on the oracle (CadQuery 2.3.0, `ok-sphere-*` beside their `oracle.json`):
`Workplane.sphere(radius)` places one sphere at each point of the stack with
`centered=True`, on the origin of an empty stack or on a `moveTo` point;
after `transformed` or `workplane(offset=…)` the point is on the moved plane,
and a solid in the chain is fused with it (`combine=True`). `cq` builds it as
a half disc revolved a full turn about the normal: one spherical face, as
Open CASCADE's `makeSphere` has.
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
    "ok-sphere-centred-xy",
    "ok-sphere-at-point-xz",
    "ok-sphere-at-point-origin-yz",
    "ok-sphere-transformed-zx",
    "ok-sphere-fused-at-point-xy",
    "ok-sphere-capsule",
]


@pytest.mark.parametrize("slug", FIXTURES)
def test_sphere_fixtures_agree_with_the_recorded_oracle(slug: str) -> None:
    case = next(c for c in fixture_cases.load("cq") if c.slug == slug)
    assert "sphere(" in case.program
    path = fixture_cases.ROOT / "cq" / slug / "oracle.json"
    report = OracleReport.model_validate_json(path.read_text())
    assert compare(fixture_cases.run(case), report).outcome is FidelityOutcome.AGREE


@pytest.mark.parametrize("slug", FIXTURES)
def test_the_oracle_holds_each_spheres_closed_form(slug: str) -> None:
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
    origin=st.tuples(*(st.integers(-9, 9) for _ in range(3))),
    offset=st.integers(-8, 8),
    point=st.none() | st.tuples(st.integers(-6, 6), st.integers(-6, 6)),
    radius=st.integers(1, 40).map(lambda n: n / 4),
)
def test_a_sphere_is_centred_on_its_point(
    plane: str,
    origin: tuple[int, int, int],
    offset: int,
    point: tuple[int, int] | None,
    radius: float,
) -> None:
    (x, y) = point if point is not None else (0, 0)
    at_point = "" if point is None else f".moveTo({x}, {y})"
    program = (
        "import cadquery as cq\n"
        f"r = cq.Workplane('{plane}', origin={origin}).workplane(offset={offset})"
        f"{at_point}.sphere({radius})\n"
    )
    result = ag.run(program, dialect="cq")
    centre = [o + c for o, c in zip(origin, _world(plane, x, y, offset), strict=True)]
    expected: dict[str, object] = {
        "dialect": "cq",
        "status": "ok",
        "measures": {
            "volume": 4 / 3 * math.pi * radius**3,
            "area": 4 * math.pi * radius**2,
            "centroid": centre,
            "bounds": [[c - radius for c in centre], [c + radius for c in centre]],
            "faces": 1,
            "face_kinds": [["sphere", 1]],
            "shells": 1,
            "genus": 0,
        },
    }
    assert fixture_cases.check(result, expected) == [], result.message


def test_reach_reads_the_declared_form_only() -> None:
    def written(call: str) -> CorpusProgram:
        text = f"import cadquery as cq\nresult = cq.Workplane('XY').{call}"
        return CorpusProgram(stem=call, family="f", text=text)

    assert cq.subset().admits("Workplane.sphere(num)")
    report = reach([written("sphere(4)"), written("sphere(4, angle1=0)")], cq.subset())
    assert report.stems == ("sphere(4)",)
    refused = ag.run(
        "import cadquery as cq\nresult = cq.Workplane('XY').sphere(4, centered=False)",
        dialect="cq",
    )
    assert refused.status is ag.Status.UNSUPPORTED_API
    assert refused.message == "Workplane.sphere(num; centered=bool)"

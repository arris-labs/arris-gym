"""`cylinder` is centred on its point in all three axes, its axis the plane's normal.

Read on the oracle (CadQuery 2.3.0, `ok-cylinder-*` beside their `oracle.json`):
`Workplane.cylinder(height, radius)` places one cylinder at each point of the
stack with `centered=True`, so it spans `height / 2` either side of the plane,
on the origin of an empty stack or on a `moveTo` point; after `transformed` or
`workplane(offset=…)` the point is on the moved plane, and a solid in the chain
is fused with it (`combine=True`).
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
    "ok-cylinder-centred-xy",
    "ok-cylinder-at-point-xz",
    "ok-cylinder-at-point-offset-yz",
    "ok-cylinder-transformed-zx",
    "ok-cylinder-origin-zx",
    "ok-cylinder-fused-at-point-xy",
]


@pytest.mark.parametrize("slug", FIXTURES)
def test_cylinder_fixtures_agree_with_the_recorded_oracle(slug: str) -> None:
    case = next(c for c in fixture_cases.load("cq") if c.slug == slug)
    assert "cylinder(" in case.program
    path = fixture_cases.ROOT / "cq" / slug / "oracle.json"
    report = OracleReport.model_validate_json(path.read_text())
    assert compare(fixture_cases.run(case), report).outcome is FidelityOutcome.AGREE


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
    height=st.integers(1, 8),
    radius=st.integers(1, 5),
)
def test_a_cylinder_is_centred_on_its_point_along_the_normal(
    plane: str,
    origin: tuple[int, int, int],
    offset: int,
    point: tuple[int, int] | None,
    height: int,
    radius: int,
) -> None:
    (x, y) = point if point is not None else (0, 0)
    at_point = "" if point is None else f".moveTo({x}, {y})"
    program = (
        "import cadquery as cq\n"
        f"r = cq.Workplane('{plane}', origin={origin}).workplane(offset={offset})"
        f"{at_point}.cylinder({height}, {radius})\n"
    )
    result = ag.run(program, dialect="cq")

    def at(u: float, v: float, w: float) -> list[float]:
        return [o + c for o, c in zip(origin, _world(plane, u, v, w), strict=True)]

    near = at(x - radius, y - radius, offset - height / 2)
    far = at(x + radius, y + radius, offset + height / 2)
    expected: dict[str, object] = {
        "dialect": "cq",
        "status": "ok",
        "measures": {
            "volume": math.pi * radius**2 * height,
            "area": 2 * math.pi * radius * (radius + height),
            "centroid": at(x, y, offset),
            "bounds": [
                [min(a, b) for a, b in zip(near, far, strict=True)],
                [max(a, b) for a, b in zip(near, far, strict=True)],
            ],
            "faces": 3,
            "face_kinds": [["cylinder", 1], ["plane", 2]],
            "shells": 1,
            "genus": 0,
        },
    }
    assert fixture_cases.check(result, expected) == [], result.message


def test_reach_reads_the_declared_form_only() -> None:
    def written(call: str) -> CorpusProgram:
        text = f"import cadquery as cq\nresult = cq.Workplane('XY').{call}"
        return CorpusProgram(stem=call, family="f", text=text)

    assert cq.subset().admits("Workplane.cylinder(num, num)")
    report = reach(
        [written("cylinder(4, 1)"), written("cylinder(4, 1, centered=False)")], cq.subset()
    )
    assert report.stems == ("cylinder(4, 1)",)
    keyword = "cylinder(4, 1, direct=cq.Vector(1, 0, 0))"
    refused = ag.run(f"import cadquery as cq\nresult = cq.Workplane('XY').{keyword}", dialect="cq")
    assert refused.status is ag.Status.UNSUPPORTED_API
    assert refused.message == "Workplane.cylinder(num, num; direct=call)"

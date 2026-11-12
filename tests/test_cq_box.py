"""`box` on a `moveTo` point is centred on it, in the plane's own axes.

Read on the oracle (CadQuery 2.3.0, `ok-box-at-point-*`): `box` places one box
at each point of the stack with `centered=True`, so a box after `moveTo(x, y)`
is centred on that point; after `workplane(offset=…)` the point is on the
moved plane, and a solid in the chain is fused with it (`combine=True`).
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import arris_gym as ag
import arris_gym.cq as cq
import fixture_cases
from arris_gym.fidelity import FidelityOutcome, OracleReport, compare

PLANES = ["XY", "YZ", "XZ", "ZX"]


@pytest.mark.parametrize(
    "slug", ["ok-box-at-point-xz", "ok-box-at-point-offset-yz", "ok-box-at-point-fused-xy"]
)
def test_box_at_point_fixtures_agree_with_the_recorded_oracle(slug: str) -> None:
    case = next(c for c in fixture_cases.load("cq") if c.slug == slug)
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
    point=st.tuples(st.integers(-6, 6), st.integers(-6, 6)),
    size=st.tuples(*(st.integers(1, 5) for _ in range(3))),
)
def test_a_box_on_a_moveto_point_is_centred_on_it(
    plane: str,
    origin: tuple[int, int, int],
    offset: int,
    point: tuple[int, int],
    size: tuple[int, int, int],
) -> None:
    (x, y), (length, width, height) = point, size
    program = (
        "import cadquery as cq\n"
        f"r = cq.Workplane('{plane}', origin={origin}).workplane(offset={offset})"
        f".moveTo({x}, {y}).box({length}, {width}, {height})\n"
    )
    result = ag.run(program, dialect="cq")

    def at(u: float, v: float, w: float) -> list[float]:
        return [o + c for o, c in zip(origin, _world(plane, u, v, w), strict=True)]

    near = at(x - length / 2, y - width / 2, offset - height / 2)
    far = at(x + length / 2, y + width / 2, offset + height / 2)
    expected: dict[str, object] = {
        "dialect": "cq",
        "status": "ok",
        "measures": {
            "volume": length * width * height,
            "area": 2 * (length * width + length * height + width * height),
            "centroid": at(x, y, offset),
            "bounds": [
                [min(a, b) for a, b in zip(near, far, strict=True)],
                [max(a, b) for a, b in zip(near, far, strict=True)],
            ],
            "faces": 6,
            "face_kinds": [["plane", 6]],
            "shells": 1,
            "genus": 0,
        },
    }
    assert fixture_cases.check(result, expected) == [], result.message


@pytest.mark.parametrize(
    "drawn",
    [
        cq.Workplane("XY").moveTo(1, 0).lineTo(2, 0),
        cq.Workplane("XY").polyline([(0, 0), (1, 0), (1, 1)]).close(),
        cq.Workplane("XY").moveTo(1, 0).circle(1),
    ],
)
def test_a_box_on_a_drawn_path_or_sketch_is_unsupported(drawn: cq.Workplane) -> None:
    with pytest.raises(cq.UnsupportedApi, match=r"^Workplane\.box on a pending wire$"):
        drawn.box(1, 1, 1)


@pytest.mark.parametrize(
    "solid",
    [
        cq.Workplane("XY").moveTo(5, 0).circle(1).extrude(2),
        cq.Workplane("XY").circle(1).extrude(2),
        cq.Workplane("YZ").box(4, 2, 2),
        cq.Workplane("XZ", origin=(1, 2, 3)).box(2, 2, 2),
        cq.Workplane("ZX").box(1, 1, 1).union(cq.Workplane("ZX").box(2, 1, 1)),
        cq.Workplane("XY").box(4, 4, 4).cut(cq.Workplane("XY").box(1, 1, 6)),
    ],
)
def test_a_box_on_a_stack_holding_a_solid_is_unsupported(solid: cq.Workplane) -> None:
    # Read on the oracle (CadQuery 2.3.0): `eachpoint` centres the box on the
    # solid's `Center()`, its centre of mass, not on the plane's origin: after
    # `moveTo(5, 0).circle(1).extrude(2)` a unit box lands inside the cylinder
    # at (5, 0, 1), V = 2π, and a 1 x 1 x 10 one spans z from -4 to 6. The
    # subset does not model that placement.
    with pytest.raises(cq.UnsupportedApi, match=r"^Workplane\.box on a stack holding a solid$"):
        solid.box(1, 1, 1)

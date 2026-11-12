"""`cq.Workplane(str; origin=tuple)` moves a named plane's origin to a world point.

CadQuery 2.3.0's `Plane.named` takes `origin` in world coordinates and keeps
the plane's axes (read on the oracle: `ok-origin-*`). A `transformed` offset
on such a plane is in its local axes, from the moved origin.
"""

import itertools
import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import arris_gym as ag
import arris_gym.cq as cq
import fixture_cases
from arris_gym.fidelity import FidelityOutcome, OracleReport, compare

PLANES = ["XY", "YZ", "XZ", "ZX"]


@pytest.mark.parametrize(
    "slug",
    [
        "ok-origin-box-xy",
        "ok-origin-box-yz",
        "ok-origin-box-xz",
        "ok-origin-box-zx",
        "ok-origin-prism-zx",
    ],
)
def test_origin_fixtures_agree_with_the_recorded_oracle(slug: str) -> None:
    case = next(c for c in fixture_cases.load("cq") if c.slug == slug)
    path = fixture_cases.ROOT / "cq" / slug / "oracle.json"
    report = OracleReport.model_validate_json(path.read_text())
    assert compare(fixture_cases.run(case), report).outcome is FidelityOutcome.AGREE


def _world(plane: str, u: float, v: float, w: float) -> tuple[float, float, float]:
    """Local (u, v, w) on a named plane at the world origin, in world coordinates."""
    if plane == "XY":
        return (u, v, w)
    if plane == "YZ":
        return (w, u, v)
    if plane == "XZ":
        return (u, -w, v)
    assert plane == "ZX"
    return (v, w, u)


@pytest.mark.parametrize("plane", PLANES)
def test_origin_moves_the_plane_and_keeps_its_axes(plane: str) -> None:
    named = cq.Workplane(plane)._plane
    moved = cq.Workplane(plane, origin=(3, -5.5, 7))._plane
    assert moved.origin == (3.0, -5.5, 7.0)
    assert (moved.x, moved.y, moved.z) == (named.x, named.y, named.z)
    assert named.origin == (0.0, 0.0, 0.0)
    assert [named.point(*p) for p in ((1, 0, 0), (0, 1, 0), (0, 0, 1))] == [
        _world(plane, *p) for p in ((1, 0, 0), (0, 1, 0), (0, 0, 1))
    ]


@settings(max_examples=40, deadline=None)
@given(
    plane=st.sampled_from(PLANES),
    origin=st.tuples(*(st.integers(-9, 9) for _ in range(3))),
    offset=st.tuples(*(st.integers(-5, 5) for _ in range(3))),
    a=st.integers(1, 8),
    b=st.integers(1, 8),
    distance=st.one_of(st.integers(-8, -1), st.integers(1, 8)),
)
def test_origin_is_a_world_point_and_offset_a_local_one(
    plane: str,
    origin: tuple[int, int, int],
    offset: tuple[int, int, int],
    a: int,
    b: int,
    distance: int,
) -> None:
    program = (
        "import cadquery as cq\n"
        f"result = cq.Workplane({plane!r}, origin={origin!r})"
        f".transformed(offset=cq.Vector{offset!r})"
        f".polyline([(1, 2), ({1 + a}, 2), (1, {2 + b})]).close()"
        f".extrude({distance})\n"
    )
    result = ag.run(program, dialect="cq")
    u, v, w = offset

    def at(lu: float, lv: float, lw: float) -> tuple[float, ...]:
        local = _world(plane, u + lu, v + lv, w + lw)
        return tuple(o + c for o, c in zip(origin, local, strict=True))

    corners = [
        at(cu, cv, cw) for cu, cv, cw in itertools.product((1, 1 + a), (2, 2 + b), (0, distance))
    ]
    expected: dict[str, object] = {
        "dialect": "cq",
        "status": "ok",
        "measures": {
            "volume": a * b * abs(distance) / 2,
            "area": a * b + (a + b + math.hypot(a, b)) * abs(distance),
            "centroid": list(at(1 + a / 3, 2 + b / 3, distance / 2)),
            "bounds": [
                [min(c[i] for c in corners) for i in range(3)],
                [max(c[i] for c in corners) for i in range(3)],
            ],
            "faces": 5,
            "face_kinds": [["plane", 5]],
            "shells": 1,
            "genus": 0,
        },
    }
    assert fixture_cases.check(result, expected) == [], result.message

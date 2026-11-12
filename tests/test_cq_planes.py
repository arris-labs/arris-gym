"""Named planes preserve CadQuery's axes, placement and extrusion direction."""

import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import arris_gym as ag
import fixture_cases
from arris_gym.fidelity import FidelityOutcome, OracleReport, compare


@pytest.mark.parametrize(
    "slug", ["ok-plane-yz-box", "ok-plane-yz-prism", "ok-plane-xz-box", "ok-plane-xz-prism"]
)
def test_named_plane_fixtures_agree_with_the_recorded_oracle(slug: str) -> None:
    case = next(c for c in fixture_cases.load("cq") if c.slug == slug)
    path = fixture_cases.ROOT / "cq" / slug / "oracle.json"
    report = OracleReport.model_validate_json(path.read_text())
    assert compare(fixture_cases.run(case), report).outcome is FidelityOutcome.AGREE


@settings(max_examples=30, deadline=None)
@given(
    a=st.integers(1, 8),
    b=st.integers(1, 8),
    distance=st.one_of(st.integers(-8, -1), st.integers(1, 8)),
    offset=st.tuples(*(st.integers(-5, 5) for _ in range(3))),
)
def test_yz_places_an_asymmetric_prism_along_its_directed_axes(
    a: int, b: int, distance: int, offset: tuple[int, int, int]
) -> None:
    u, v, w = offset
    program = (
        "import cadquery as cq\n"
        f"result = cq.Workplane('YZ').transformed(offset=cq.Vector{offset!r})"
        f".polyline([(1, 2), ({1 + a}, 2), (1, {2 + b})]).close()"
        f".extrude({distance})\n"
    )
    result = ag.run(program, dialect="cq")
    # Local (u, v, w) maps to world (w, u, v); the triangle has legs a, b.
    expected: dict[str, object] = {
        "dialect": "cq",
        "status": "ok",
        "measures": {
            "volume": a * b * abs(distance) / 2,
            "area": a * b + (a + b + math.hypot(a, b)) * abs(distance),
            "centroid": [w + distance / 2, u + 1 + a / 3, v + 2 + b / 3],
            "bounds": [
                [w + min(0, distance), u + 1, v + 2],
                [w + max(0, distance), u + 1 + a, v + 2 + b],
            ],
            "faces": 5,
            "face_kinds": [["plane", 5]],
            "shells": 1,
            "genus": 0,
        },
    }
    assert fixture_cases.check(result, expected) == [], result.message


@settings(max_examples=30, deadline=None)
@given(
    a=st.integers(1, 8),
    b=st.integers(1, 8),
    distance=st.one_of(st.integers(-8, -1), st.integers(1, 8)),
    offset=st.tuples(*(st.integers(-5, 5) for _ in range(3))),
)
def test_xz_places_an_asymmetric_prism_along_its_directed_axes(
    a: int, b: int, distance: int, offset: tuple[int, int, int]
) -> None:
    u, v, w = offset
    program = (
        "import cadquery as cq\n"
        f"result = cq.Workplane('XZ').transformed(offset=cq.Vector{offset!r})"
        f".polyline([(1, 2), ({1 + a}, 2), (1, {2 + b})]).close()"
        f".extrude({distance})\n"
    )
    result = ag.run(program, dialect="cq")
    # Local (u, v, w) maps to world (u, -w, v): the normal is world -y.
    expected: dict[str, object] = {
        "dialect": "cq",
        "status": "ok",
        "measures": {
            "volume": a * b * abs(distance) / 2,
            "area": a * b + (a + b + math.hypot(a, b)) * abs(distance),
            "centroid": [u + 1 + a / 3, -(w + distance / 2), v + 2 + b / 3],
            "bounds": [
                [u + 1, -(w + max(0, distance)), v + 2],
                [u + 1 + a, -(w + min(0, distance)), v + 2 + b],
            ],
            "faces": 5,
            "face_kinds": [["plane", 5]],
            "shells": 1,
            "genus": 0,
        },
    }
    assert fixture_cases.check(result, expected) == [], result.message

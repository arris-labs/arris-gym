"""`Workplane.workplane(offset=…)`: a new plane along the normal, from the origin or a solid.

Read on the oracle (CadQuery 2.3.0, `ok-workplane-*`): on an empty stack the
new origin is the old one moved `offset` along the normal; on a stack holding
one solid it is the old origin projected onto the plane through the solid's
centroid, then moved `offset`. The axes stay. `workplane()` is offset 0.
"""

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

import arris_gym as ag
import arris_gym.cq as cq
import fixture_cases
from arris_gym.fidelity import FidelityOutcome, OracleReport, compare

PLANES = ["XY", "YZ", "XZ", "ZX"]


@pytest.mark.parametrize(
    "slug",
    [
        *(f"ok-workplane-offset-{p.lower()}" for p in PLANES),
        *(f"ok-workplane-on-solid-{p.lower()}" for p in PLANES),
        "ok-workplane-on-solid-neg-xz",
        "ok-workplane-bare-xy",
    ],
)
def test_workplane_fixtures_agree_with_the_recorded_oracle(slug: str) -> None:
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
def test_workplane_keeps_the_axes_and_empties_the_stack(plane: str) -> None:
    base = cq.Workplane(plane, origin=(1, 2, 3)).box(2, 2, 2)
    moved = base.workplane(offset=-2.5)
    assert (moved._plane.x, moved._plane.y, moved._plane.z) == (
        base._plane.x,
        base._plane.y,
        base._plane.z,
    )
    assert moved._stack == ()
    assert moved._parent is base


@settings(max_examples=30, deadline=None)
@given(
    plane=st.sampled_from(PLANES),
    origin=st.tuples(*(st.integers(-9, 9) for _ in range(3))),
    offset=st.integers(-8, 8),
)
def test_on_an_empty_stack_the_origin_moves_along_the_normal(
    plane: str, origin: tuple[int, int, int], offset: int
) -> None:
    moved = cq.Workplane(plane, origin=origin).workplane(offset=offset)._plane
    expected = tuple(o + c for o, c in zip(origin, _world(plane, 0, 0, offset), strict=True))
    # The normal's components are 0 or ±1, so the arithmetic is exact.
    assert moved.origin == expected


@settings(max_examples=40, deadline=None)
@given(
    plane=st.sampled_from(PLANES),
    origin=st.tuples(*(st.integers(-9, 9) for _ in range(3))),
    a=st.integers(1, 6),
    b=st.integers(1, 6),
    height=st.one_of(st.integers(-6, -2), st.integers(2, 6)),
    offset=st.integers(-6, 6),
    length=st.sampled_from([1, 3, 5]),
)
def test_on_a_solid_the_plane_passes_through_its_centroid(
    plane: str,
    origin: tuple[int, int, int],
    a: int,
    b: int,
    height: int,
    offset: int,
    length: int,
) -> None:
    """A slab u in [-1, a], v in [-1, b], w from 0 to `height`, and a 1 by 1 pin on the new plane.

    The pin is centred on the origin's projection (u = v = 0, inside the
    slab), at w = height / 2 + offset, `length` long along the normal: the
    union's measures are the slab's plus the pin's parts outside it.
    """
    slab_lo, slab_hi = min(0, height), max(0, height)
    centre = height / 2 + offset
    pin_lo, pin_hi = centre - length / 2, centre + length / 2
    # One solid with no coplanar faces: the pin overlaps the slab, its ends off the slab's faces.
    assume(pin_lo < slab_hi and pin_hi > slab_lo)
    assume(all(end not in (slab_lo, slab_hi) for end in (pin_lo, pin_hi)))
    program = (
        "import cadquery as cq\n"
        f"result = cq.Workplane({plane!r}, origin={origin!r})"
        f".polyline([(-1, -1), ({a}, -1), ({a}, {b}), (-1, {b})]).close()"
        f".extrude({height}).workplane(offset={offset}).box(1, 1, {length})\n"
    )
    result = ag.run(program, dialect="cq")
    below, above = max(0.0, slab_lo - pin_lo), max(0.0, pin_hi - slab_hi)
    slab = (a + 1) * (b + 1) * abs(height)
    volume = slab + below + above

    def at(u: float, v: float, w: float) -> list[float]:
        return [o + c for o, c in zip(origin, _world(plane, u, v, w), strict=True)]

    corners = [at(-1, -1, min(slab_lo, pin_lo)), at(a, b, max(slab_hi, pin_hi))]
    moment = slab * height / 2 + below * (slab_lo - below / 2) + above * (slab_hi + above / 2)
    expected: dict[str, object] = {
        "dialect": "cq",
        "status": "ok",
        "measures": {
            "volume": volume,
            "area": 2 * (a + 1) * (b + 1)
            + 2 * ((a + 1) + (b + 1)) * abs(height)
            + 4 * (below + above),
            "centroid": at(
                slab * (a - 1) / 2 / volume, slab * (b - 1) / 2 / volume, moment / volume
            ),
            "bounds": [
                [min(c[i] for c in corners) for i in range(3)],
                [max(c[i] for c in corners) for i in range(3)],
            ],
            "faces": 6 + 5 * ((below > 0) + (above > 0)),
            "face_kinds": [["plane", 6 + 5 * ((below > 0) + (above > 0))]],
            "shells": 1,
            "genus": 0,
        },
    }
    assert fixture_cases.check(result, expected) == [], result.message

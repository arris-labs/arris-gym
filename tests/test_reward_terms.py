"""The measures and topology terms, in-process (ADR-0009).

docs/plans/m4-reward.md step 4. Expected values come from closed forms: the
inertia of a box and a cylinder, a moved copy's centroid gap, a plate built
with a round hole and with a faceted one.
"""

from __future__ import annotations

import math

import arris
import arris.build
from hypothesis import given
from hypothesis import strategies as st

from arris_gym.reward._measures import measures, principal_moments, ratio
from arris_gym.reward._topology import SURFACE_KINDS, kind_histogram, overlap, topology

# Rounding in a few Jacobi sweeps and mass properties of magnitude below 100.
ROUNDING = 1e-9
# The kernel's volume and inertia of a revolved or cylindrical body are
# quadrature results, not closed-form bits: this relative bound holds them.
KERNEL_RELATIVE = 1e-9
HOLE_SIDES = 12
# The kernel pads every bounding box by 2e-7 a side, so a diagonal read from
# it is off its exact value by a few of that over the diagonal: this bound
# holds a term built on it, and nothing else in these tests is that loose.
BOUNDS_PAD = 1e-6


def _box(model: arris.Model, high: tuple[float, float, float]) -> arris.Body:
    return arris.build.Solid.box((0, 0, 0), high, model=model).body


def _plate(model: arris.Model, hole: arris.Body | None) -> arris.Body:
    plate = arris.build.Solid.box((-5, -5, 0), (5, 5, 1), model=model)
    if hole is None:
        return plate.body
    return model.cut(plate.body, hole)[0]


# --- principal_moments ---------------------------------------------------------


def test_principal_moments_of_a_box_are_its_closed_forms() -> None:
    # A box a x b x c of unit density: m (b² + c²) / 12 about x, and so on.
    a, b, c = 1.0, 2.0, 3.0
    model = arris.Model()
    body = _box(model, (a, b, c))
    props = model.mass_properties(body)
    want = sorted(props.volume * (y * y + z * z) / 12 for y, z in ((b, c), (a, c), (a, b)))
    got = principal_moments(props.inertia_about(props.centroid))
    for g, w in zip(got, want, strict=True):
        assert abs(g - w) <= ROUNDING * w


def test_principal_moments_of_a_cylinder_are_its_closed_forms() -> None:
    # Radius r, height h, along z: m r² / 2 about the axis, m (3 r² + h²) / 12 across.
    r, h = 1.5, 4.0
    model = arris.Model()
    body = arris.build.Solid.cylinder((0, 0, 0), (0, 0, 1), r, h, model=model).body
    props = model.mass_properties(body)
    mass = math.pi * r * r * h
    want = sorted(
        (mass * r * r / 2, mass * (3 * r * r + h * h) / 12, mass * (3 * r * r + h * h) / 12)
    )
    got = principal_moments(props.inertia_about(props.centroid))
    for g, w in zip(got, want, strict=True):
        assert abs(g - w) <= KERNEL_RELATIVE * w


@given(
    st.lists(st.floats(min_value=-10, max_value=10), min_size=6, max_size=6),
)
def test_principal_moments_keep_the_trace_and_the_order(entries: list[float]) -> None:
    # Any symmetric matrix: the eigenvalues ascend and sum to the trace.
    a, b, c, d, e, f = entries
    matrix = ((a, d, e), (d, b, f), (e, f, c))
    low, mid, high = principal_moments(matrix)
    assert low <= mid <= high
    assert abs((low + mid + high) - (a + b + c)) <= ROUNDING * (1 + abs(a) + abs(b) + abs(c))


def test_principal_moments_repeat_their_bits() -> None:
    matrix = ((3.0, 1.0, 0.5), (1.0, 2.0, 0.25), (0.5, 0.25, 4.0))
    assert principal_moments(matrix) == principal_moments(matrix)


# --- measures ------------------------------------------------------------------


def test_measures_of_a_body_against_itself_is_exactly_one() -> None:
    model = arris.Model()
    body = _box(model, (1, 2, 3))
    assert measures(model, body, body) == 1.0


def test_measures_of_a_box_against_its_double_is_the_ratio_mean() -> None:
    # Doubled: volume 1/8, area 1/4, moments (2^5 apart) 1/32 each; the
    # centroid gap is half the doubled box's diagonal over its target's own,
    # |c| = 0.5 * diagonal(1,1,1) in the first, so the gap share is 0.5 of
    # the target's diagonal when the target is the small box.
    model = arris.Model()
    small, big = _box(model, (1, 1, 1)), _box(model, (2, 2, 2))
    gap = math.sqrt(3) / 2 / math.sqrt(3)
    want = (1 / 8 + 1 / 4 + (1 - gap) + 1 / 32) / 4
    assert abs(measures(model, big, small) - want) <= BOUNDS_PAD


def test_measures_is_a_pure_centroid_loss_for_a_moved_copy() -> None:
    model = arris.Model()
    solid = arris.build.Solid.box((0, 0, 0), (1, 2, 3), model=model)
    body, moved = solid.body, solid.moved((0.3, 0.4, 0.0)).body
    diagonal = math.sqrt(14.0)
    want = (3 + (1 - 0.5 / diagonal)) / 4
    assert abs(measures(model, moved, body) - want) <= BOUNDS_PAD


@given(st.floats(min_value=0, max_value=1e6), st.floats(min_value=0, max_value=1e6))
def test_ratio_is_symmetric_and_in_range(a: float, b: float) -> None:
    assert ratio(a, b) == ratio(b, a)
    assert 0.0 <= ratio(a, b) <= 1.0


# --- topology ------------------------------------------------------------------


def _round_hole(model: arris.Model) -> arris.Body:
    return arris.build.Solid.cylinder((0, 0, -1), (0, 0, 1), 2.0, 3.0, model=model).body


def _faceted_hole(model: arris.Model) -> arris.Body:
    ring = [
        (2.0 * math.cos(math.tau * i / HOLE_SIDES), 2.0 * math.sin(math.tau * i / HOLE_SIDES))
        for i in range(HOLE_SIDES)
    ]
    solid = arris.build.Workplane.XY().polygon(ring).extrude(3.0, model=model)
    return solid.moved((0, 0, -1)).body


def test_topology_of_a_plate_against_itself_is_exactly_one() -> None:
    model = arris.Model()
    plate = _plate(model, _round_hole(model))
    assert topology(model, plate, plate, kind_weight=0.5) == 1.0
    assert topology(model, plate, plate, kind_weight=0.3) == 1.0


def test_a_faceted_hole_scores_below_a_round_one_below_the_plate_against_itself() -> None:
    model = arris.Model()
    round_plate = _plate(model, _round_hole(model))
    faceted = _plate(model, _faceted_hole(model))
    # Round: 6 planes and 1 cylinder; faceted: 6 + 12 planes. Genus 1 both.
    assert kind_histogram(model, round_plate)[:2] == (6, 1)
    assert kind_histogram(model, faceted)[:2] == (6 + HOLE_SIDES, 0)
    got = topology(model, faceted, round_plate, kind_weight=0.5)
    want = 0.5 * (6 / (6 + HOLE_SIDES + 1)) + 0.5
    assert abs(got - want) <= ROUNDING
    assert got < 1.0


def test_a_through_hole_costs_the_genus_term() -> None:
    model = arris.Model()
    solid = _plate(model, None)
    holed = _plate(model, _round_hole(model))
    # Histograms (6, 0..) against (6, 1): overlap 6/7; genus 0 against 1: 1/2.
    got = topology(model, holed, solid, kind_weight=0.5)
    assert abs(got - (0.5 * 6 / 7 + 0.5 * 0.5)) <= ROUNDING


def test_overlap_counts_every_kind_and_two_empty_histograms_are_alike() -> None:
    assert len(SURFACE_KINDS) == 7
    assert overlap((0,) * 7, (0,) * 7) == 1.0
    assert overlap((2, 0, 0, 0, 0, 0, 0), (0, 2, 0, 0, 0, 0, 0)) == 0.0
    assert overlap((2, 1, 0, 0, 0, 0, 0), (1, 1, 0, 0, 0, 0, 0)) == 2 / 3

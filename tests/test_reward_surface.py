"""The surface term, in-process: its samples, its distances, its exp (ADR-0009).

docs/plans/m4-reward.md step 3. Expected values come from how a part was
built: a box's face areas, a copy moved by a known vector, a body against
itself. `math.exp` appears here only, to bound `exp_neg`'s error.
"""

from __future__ import annotations

import functools
import math

import arris
import arris.build
import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import arris_gym as ag
import fixture_cases
from arris_gym.reward._iou import CHUNK_ELEMENTS, _mesh
from arris_gym.reward._surface import (
    EXP_UNDERFLOW,
    exp_neg,
    nearest_distances,
    surface,
    surface_distance,
    surface_samples,
)

# ADR-0009's constants: τ, and the samples per body (N/2 of ADR-0008's N).
TAU = 0.05
POINTS = 5_324
# ADR-0008's chord, at which a box meshes exactly.
CHORD_FRACTION = 1 / 200
SEED = 20261109
# A sampled share lands within this many binomial standard errors.
SIGMAS = 4
# exp_neg's error bound against the platform's exp, in units in the last place
# of the true value: Cody and Waite's reduction and a degree-13 Taylor
# polynomial, measured at 1 ulp over 3·10⁵ arguments while writing it.
EXP_ULPS = 2
# A sample on a box's face lies within rounding of the face's plane: the
# corners are small integers, so a few ulps of 3.
ON_FACE = 1e-12
# Rounding in a distance between points of magnitude at most 6, and in a
# chain of a few products and sums over a diagonal: far below any move tested.
ROUNDING = 1e-12


@functools.cache
def _body(program: str) -> bytes:
    result = ag.run(program)
    assert result.status is ag.Status.OK, result.message
    assert result.body is not None
    return result.body.data


def _box(model: arris.Model, low: tuple[float, ...], high: tuple[float, ...]) -> arris.Body:
    return arris.build.Solid.box(low, high, model=model).body


def _distance(model: arris.Model, a: arris.Body, b: arris.Body) -> float:
    return surface_distance(model, a, b, chord_fraction=CHORD_FRACTION, points=POINTS, seed=SEED)


def _term(model: arris.Model, a: arris.Body, b: arris.Body, points: int = POINTS) -> float:
    return surface(model, a, b, tau=TAU, chord_fraction=CHORD_FRACTION, points=points, seed=SEED)


# --- exp_neg -------------------------------------------------------------------


@given(x=st.floats(min_value=0.0, max_value=EXP_UNDERFLOW, exclude_max=True))
def test_exp_neg_is_within_2_ulps_of_the_platforms_exp(x: float) -> None:
    want = math.exp(-x)
    got = exp_neg(x)
    assert abs(got - want) <= EXP_ULPS * math.ulp(want), (x, got, want)


def test_exp_neg_is_exact_at_its_ends() -> None:
    assert exp_neg(0.0) == 1.0
    assert exp_neg(EXP_UNDERFLOW) == 0.0
    assert exp_neg(1e300) == 0.0


@pytest.mark.parametrize("x", [-1e-300, -1.0, math.nan, math.inf])
def test_exp_neg_refuses_a_negative_or_non_finite_argument(x: float) -> None:
    with pytest.raises(ValueError, match="finite x >= 0"):
        exp_neg(x)


# --- surface_samples -----------------------------------------------------------


def test_samples_lie_on_the_box_and_share_its_faces_by_area() -> None:
    # A 1 x 2 x 3 box: the two faces normal to x hold 2·6 of the area 22, to
    # y 2·3 and to z 2·2; each sample lies on one face.
    model = arris.Model()
    high = np.array([1.0, 2.0, 3.0])
    samples = surface_samples(_mesh(model, _box(model, (0, 0, 0), (1, 2, 3)), 0.1), POINTS, SEED)
    assert samples.shape == (POINTS, 3)
    eps = ON_FACE
    assert bool(np.all((samples >= -eps) & (samples <= high + eps)))
    on = (np.abs(samples) <= eps) | (np.abs(samples - high) <= eps)
    assert bool(np.all(on.any(axis=1)))
    for axis, share in enumerate((12 / 22, 6 / 22, 4 / 22)):
        got = int(np.count_nonzero(on[:, axis])) / POINTS
        sigma = math.sqrt(share * (1 - share) / POINTS)
        assert abs(got - share) <= SIGMAS * sigma, (axis, got, share)


@settings(max_examples=20, deadline=None)
@given(seed=st.integers(min_value=0, max_value=2**63 - 1))
def test_samples_repeat_their_bits_for_a_seed(seed: int) -> None:
    model = arris.Model()
    mesh = _mesh(model, _box(model, (0, 0, 0), (1, 2, 3)), 0.1)
    assert surface_samples(mesh, 300, seed).tobytes() == surface_samples(mesh, 300, seed).tobytes()


def test_samples_refuse_no_count_and_no_area() -> None:
    model = arris.Model()
    mesh = _mesh(model, _box(model, (0, 0, 0), (1, 1, 1)), 0.1)
    with pytest.raises(ValueError, match="positive"):
        surface_samples(mesh, 0, SEED)
    flat = (mesh[0], mesh[0], mesh[0])
    with pytest.raises(ValueError, match="no area"):
        surface_samples(flat, 10, SEED)


# --- nearest_distances ---------------------------------------------------------


def test_nearest_distances_on_two_grids_a_known_offset_apart() -> None:
    # The integer grid against itself moved by (0.3, 0.4, 0): every point's
    # nearest is its own moved copy, at distance 0.5.
    grid = np.array([(x, y, z) for x in range(6) for y in range(6) for z in range(6)], float)
    moved = grid + np.array([0.3, 0.4, 0.0])
    got = nearest_distances(grid, moved)
    assert got == pytest.approx(np.full(len(grid), 0.5), abs=ROUNDING)


def test_nearest_distances_hold_across_chunks() -> None:
    # More points than one chunk holds: each matches its own brute-force row.
    rng = np.random.Generator(np.random.PCG64(SEED))
    others = rng.random((300, 3))
    points = rng.random((3 * CHUNK_ELEMENTS // len(others) + 7, 3))
    want = np.array([math.sqrt(float(((others - p) ** 2).sum(axis=1).min())) for p in points])
    assert np.array_equal(nearest_distances(points, others), want)


# --- surface_distance and surface ----------------------------------------------


def test_a_body_against_itself_read_twice_scores_exactly_1() -> None:
    # The `self` fixture's plate with a hole, built in the sandbox and read
    # twice into one fresh model, as the score worker reads both bodies:
    # the two meshes are equal, so the same seed draws the same samples.
    case = fixture_cases.ROOT / "reward" / "self"
    model = arris.Model()
    a = model.read_body(_body((case / "program.py").read_text(encoding="utf-8"))).body
    b = model.read_body(_body((case / "target.py").read_text(encoding="utf-8"))).body
    assert _distance(model, a, b) == 0.0
    assert _term(model, a, b) == 1.0


@settings(max_examples=10, deadline=None)
@given(seed=st.integers(min_value=0, max_value=2**63 - 1))
def test_identical_boxes_score_exactly_1_for_any_seed(seed: int) -> None:
    model = arris.Model()
    a, b = _box(model, (0, 0, 0), (1, 2, 3)), _box(model, (0, 0, 0), (1, 2, 3))
    assert surface(model, a, b, tau=TAU, chord_fraction=CHORD_FRACTION, points=500, seed=seed) == 1


def test_a_moved_copy_is_at_most_its_move_away_and_symmetric() -> None:
    # The box moved by t meshes as the box does, moved: each sample's own
    # moved copy is a sample of the other, at |t|, so no nearest is farther.
    # A dyadic t keeps every corner exact, so both diagonals have equal bits.
    model = arris.Model()
    t = (0.03125, -0.015625, 0.0625)
    a, b = _box(model, (0, 0, 0), (1, 2, 3)), _box(model, t, (1 + t[0], 2 + t[1], 3 + t[2]))
    d = _distance(model, a, b)
    assert 0.0 < d <= math.hypot(*t) / math.sqrt(14) * (1 + ROUNDING)
    # Both boxes have the same diagonal, so the two one-way means swap.
    assert _distance(model, b, a) == d
    assert 0.0 < _term(model, a, b) < 1.0


def test_the_noise_floor_of_two_samplings_is_under_a_fifth_of_tau() -> None:
    # ADR-0009's rule on the slice, held on the unit cube: one surface
    # sampled from two seeds sits at a d below τ/5 at the committed count.
    model = arris.Model()
    mesh = _mesh(model, _box(model, (0, 0, 0), (1, 1, 1)), CHORD_FRACTION)
    first, second = surface_samples(mesh, POINTS, SEED), surface_samples(mesh, POINTS, SEED + 1)
    mean = math.fsum(nearest_distances(first, second).tolist()) / POINTS
    back = math.fsum(nearest_distances(second, first).tolist()) / POINTS
    floor = (mean + back) / (2 * math.sqrt(3))
    assert 0.0 < floor <= TAU / 5


def test_the_term_falls_with_distance() -> None:
    model = arris.Model()
    target = _box(model, (0, 0, 0), (1, 1, 1))
    terms = [
        _term(model, _box(model, (s, 0, 0), (1 + s, 1, 1)), target, points=1000)
        for s in (0.0, 0.0625, 0.25, 0.625)
    ]
    assert terms[0] == 1.0
    assert terms == sorted(terms, reverse=True)
    assert len(set(terms)) == len(terms)


def test_surface_refuses_a_tau_that_is_not_positive() -> None:
    model = arris.Model()
    a = _box(model, (0, 0, 0), (1, 1, 1))
    with pytest.raises(ValueError, match="tau"):
        surface(model, a, a, tau=0.0, chord_fraction=CHORD_FRACTION, points=10, seed=SEED)

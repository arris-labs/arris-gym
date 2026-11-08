"""The IoU's two routes, in-process, on bodies the sandbox built.

docs/plans/m4-reward.md step 1. Each fixture under `tests/fixtures/reward/`
is a candidate program and a target program; its IoU comes from how the two
parts were built. Both bodies are read into one fresh model, as the score
worker reads them.
"""

from __future__ import annotations

import functools
import json
import math
from dataclasses import dataclass

import arris
import arris.build
import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import arris_gym as ag
import fixture_cases
from arris_gym.reward._iou import (
    CHUNK_ELEMENTS,
    IouRoute,
    exact_iou,
    grid_side,
    inside,
    iou,
    jittered_points,
    sampled_iou,
)

# A budget the exact route needs no more than on these box and cone pairs:
# the hardest slice pair measured while planning finished in 1e7 steps.
EXACT_BUDGET = 10**7
# The smallest budget: spent on the first step of any `interference`, so it
# forces the sampled route.
FORCED_BUDGET = 1
# A chord of 1/200 of a body's diagonal, as the picture's mesh: boxes mesh
# exactly at any chord, so the sampled route's closed forms carry sampling
# error only.
CHORD_FRACTION = 1 / 200
# Points per sampled estimate (21³ = 9261 are drawn): a standard error near
# 0.005 at IoU 1/3.
POINTS = 10_000
SEED = 20261109
# The sampled route lands within this many standard errors of a closed form.
SIGMAS = 4


@dataclass(frozen=True)
class Pair:
    """A fixture's candidate and target programs and its expectation."""

    slug: str
    program: str
    target: str
    expected: dict[str, object]


def _pairs() -> list[Pair]:
    root = fixture_cases.ROOT / "reward"
    return [
        Pair(
            d.name,
            (d / "program.py").read_text(encoding="utf-8"),
            (d / "target.py").read_text(encoding="utf-8"),
            json.loads((d / "expected.json").read_text(encoding="utf-8")),
        )
        for d in sorted(root.iterdir())
        if (d / "program.py").is_file()
    ]


PAIRS = _pairs()
CLOSED = [p for p in PAIRS if "iou" in p.expected]


@functools.cache
def _body(program: str, dialect: str) -> bytes:
    result = ag.run(program, dialect=dialect)
    assert result.status is ag.Status.OK, result.message
    assert result.body is not None
    return result.body.data


def _read(pair: Pair) -> tuple[arris.Model, arris.Body, arris.Body]:
    """Both bodies of `pair`, built in the sandbox, read into one fresh model."""
    dialect = str(pair.expected["dialect"])
    model = arris.Model()
    a = model.read_body(_body(pair.program, dialect)).body
    b = model.read_body(_body(pair.target, dialect)).body
    return model, a, b


def _pair(slug: str) -> Pair:
    return next(p for p in PAIRS if p.slug == slug)


def test_every_fixture_is_a_pair_with_a_route() -> None:
    assert {p.slug for p in PAIRS} == {
        "cone-shifted",
        "cube-and-double",
        "disjoint",
        "iou-third",
        "self",
        "touching",
    }
    assert all(p.expected["route"] in {r.value for r in IouRoute} for p in PAIRS)


@pytest.mark.parametrize("pair", PAIRS, ids=lambda p: p.slug)
def test_a_pair_takes_its_route_and_its_closed_form(pair: Pair) -> None:
    model, a, b = _read(pair)
    got = iou(
        model, a, b, budget=EXACT_BUDGET, chord_fraction=CHORD_FRACTION, points=POINTS, seed=SEED
    )
    assert got.route.value == pair.expected["route"]
    assert 0.0 <= got.value <= 1.0
    if "iou" in pair.expected:
        assert fixture_cases.close(got.value, float(str(pair.expected["iou"])))
    else:
        assert 0.0 < got.value < 1.0


@pytest.mark.parametrize("pair", CLOSED, ids=lambda p: p.slug)
def test_the_forced_sampled_route_lands_within_4_sigma_of_the_closed_form(pair: Pair) -> None:
    model, a, b = _read(pair)
    got = iou(
        model, a, b, budget=FORCED_BUDGET, chord_fraction=CHORD_FRACTION, points=POINTS, seed=SEED
    )
    assert got.route is IouRoute.SAMPLED
    want = float(str(pair.expected["iou"]))
    # The binomial error over the points inside either part, whose count the
    # construction gives as a share of all points drawn: a bound on the
    # jittered draw's error, which the cells only lower.
    either = grid_side(POINTS) ** 3 * float(str(pair.expected["sample_union_fraction"]))
    sigma = math.sqrt(want * (1.0 - want) / either)
    assert abs(got.value - want) <= SIGMAS * sigma, (got.value, want, sigma)


@pytest.mark.parametrize("slug", ["self", "disjoint", "touching"])
def test_the_sampled_route_is_exact_where_no_point_can_differ(slug: str) -> None:
    # Identical bodies class every point alike, and bodies with no common
    # volume share no point: their estimates carry no sampling error at all.
    model, a, b = _read(_pair(slug))
    want = float(str(_pair(slug).expected["iou"]))
    got = sampled_iou(model, a, b, chord_fraction=CHORD_FRACTION, points=POINTS, seed=SEED)
    assert got == want


def test_the_kernel_refuses_the_cone_pair_so_it_is_sampled() -> None:
    model, a, b = _read(_pair("cone-shifted"))
    with pytest.raises(arris.OpUnsupportedError):
        exact_iou(model, a, b, budget=EXACT_BUDGET)
    got = iou(
        model, a, b, budget=EXACT_BUDGET, chord_fraction=CHORD_FRACTION, points=POINTS, seed=SEED
    )
    assert got.route is IouRoute.SAMPLED


def test_a_spent_budget_is_the_kernels_interrupted() -> None:
    model, a, b = _read(_pair("iou-third"))
    with pytest.raises(arris.Interrupted):
        exact_iou(model, a, b, budget=FORCED_BUDGET)


def test_the_exact_route_is_symmetric() -> None:
    for pair in CLOSED:
        model, a, b = _read(pair)
        assert exact_iou(model, a, b, budget=EXACT_BUDGET) == exact_iou(
            model, b, a, budget=EXACT_BUDGET
        )


def test_the_sampled_route_repeats_its_bits_for_a_seed() -> None:
    pair = _pair("cone-shifted")
    first = sampled_iou(*_read(pair), chord_fraction=CHORD_FRACTION, points=POINTS, seed=SEED)
    again = sampled_iou(*_read(pair), chord_fraction=CHORD_FRACTION, points=POINTS, seed=SEED)
    assert first.hex() == again.hex()


@settings(max_examples=20, deadline=None)
@given(seed=st.integers(min_value=0, max_value=2**63 - 1))
def test_identical_bodies_sample_to_exactly_1_for_any_seed(seed: int) -> None:
    model, a, b = _read(_pair("self"))
    assert sampled_iou(model, a, b, chord_fraction=CHORD_FRACTION, points=500, seed=seed) == 1.0


def _cube_triangles() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    model = arris.Model()
    body = arris.build.Solid.box((0, 0, 0), (1, 1, 1), model=model).body
    positions, triangles = model.tessellate(body, 0.1).to_numpy()
    corners = np.asarray(positions, dtype=np.float64)[np.asarray(triangles, dtype=np.intp)]
    return corners[:, 0, :], corners[:, 1, :], corners[:, 2, :]


def test_the_winding_number_classes_points_by_the_unit_cube_whatever_its_orientation() -> None:
    a, b, c = _cube_triangles()
    grid = np.linspace(-0.45, 1.45, 20)
    points = np.array([(x, y, z) for x in grid for y in grid for z in grid], dtype=np.float64)
    want = np.all((points > 0.0) & (points < 1.0), axis=1)
    assert np.array_equal(inside(points, (a, b, c)), want)
    assert np.array_equal(inside(points, (a, c, b)), want)


def test_the_winding_number_holds_across_chunks() -> None:
    # More points than one chunk holds against the cube's triangles: the
    # flags of a chunk's last row and the next one's first are their own.
    a, b, c = _cube_triangles()
    rng = np.random.Generator(np.random.PCG64(SEED))
    points = rng.random((3 * CHUNK_ELEMENTS // len(a) + 7, 3)) * 2.0 - 0.5
    want = np.all((points > 0.0) & (points < 1.0), axis=1)
    assert np.array_equal(inside(points, (a, b, c)), want)


@given(points=st.integers(min_value=1, max_value=10**7))
def test_grid_side_is_the_integer_cube_root(points: int) -> None:
    k = grid_side(points)
    assert k >= 1
    assert k**3 <= points < (k + 1) ** 3


def test_grid_side_refuses_no_points() -> None:
    with pytest.raises(ValueError, match="positive"):
        grid_side(0)


@settings(max_examples=25)
@given(points=st.integers(min_value=1, max_value=4000), seed=st.integers(0, 2**63 - 1))
def test_the_jittered_draw_puts_one_point_in_each_cell(points: int, seed: int) -> None:
    k = grid_side(points)
    drawn = jittered_points(points, seed)
    assert drawn.shape == (k**3, 3)
    # A cell's last jitter can round up to its far side, so 1.0 is reachable.
    assert bool(np.all((drawn >= 0.0) & (drawn <= 1.0)))
    cells = np.minimum(np.floor(drawn * k), k - 1).astype(np.int64)
    flat = (cells[:, 0] * k + cells[:, 1]) * k + cells[:, 2]
    assert np.array_equal(np.sort(flat), np.arange(k**3))
    assert jittered_points(points, seed).tobytes() == drawn.tobytes()

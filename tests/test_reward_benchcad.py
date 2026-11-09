"""The field's metrics against the committed output of BenchCAD's own scorer.

docs/plans/m4-reward.md step 8, ADR-0010. `tests/fixtures/reward/benchcad-scorer/`
holds 10 pairs of `cq` programs and `scorer.json`, what BenchCAD's scorer
(`BenchCAD-main@77fd16a8`) answered on their STEP, run by
`tools/oracle/benchcad_score.py`. Their Chamfer is unseeded, so the fixture
holds `repeats` draws of it and the tolerance is built from their spread.
"""

from __future__ import annotations

import math
import statistics

import pytest

import arris_gym as ag
import benchcad_pairs as pairs
from arris_gym.reward import IouRoute
from benchcad_pairs import SCORER, SLUGS

# ADR-0010's tolerances, measured against `scorer.json`.
# Voxel IoU: their answer is deterministic, so the gap is the two meshes' (Open
# CASCADE's and the kernel's); the largest of the ten is 0.0312.
VOXEL_TOLERANCE = 0.04
# Chamfer: our samples are seeded alike, so a body against itself is exactly 0,
# where two independent samplings of one surface sit at a floor. Theirs on the
# pairs of one shape (`FLOOR_PAIRS`) peak at 1.998 (mean + 4 sd).
CHAMFER_FLOOR = 2.0
# Beyond the floor, the meshes: the largest gap of the ten pairs past the floor
# is 2.2% of their mean (`cylinder-heights`); 10% is the tolerance.
CHAMFER_RELATIVE = 0.10
# SIGMAS: standard deviations of their sampling the floor is held above.
SIGMAS = 4
# Pairs whose two bodies are one shape once each is normalised to its own box.
FLOOR_PAIRS = ("box-and-double", "box-shifted", "plate-self")


def test_the_fixture_holds_ten_pairs_and_their_repeats() -> None:
    assert len(SLUGS) == 10
    assert sorted(SCORER["pairs"]) == SLUGS
    assert SCORER["commit"] == "77fd16a80a4e5fc39964ee23b6cc3225beefac8f"
    for slug, row in SCORER["pairs"].items():
        assert len(row["chamfer"]) == SCORER["repeats"] >= 100, slug
        assert row["voxel_iou_64_errors"] == [], slug
        assert row["chamfer_errors"] == [], slug


@pytest.mark.parametrize("slug", SLUGS)
def test_their_voxel_iou_does_not_vary_and_both_of_their_functions_agree(slug: str) -> None:
    row = SCORER["pairs"][slug]
    assert len(set(row["voxel_iou_64"])) == 1
    assert row["voxel_iou_64"][0] == row["voxel_iou_64_iou_py"]


def test_the_chamfer_floor_is_held_above_their_sampling_noise() -> None:
    for slug in FLOOR_PAIRS:
        draws = [1000.0 * v for v in SCORER["pairs"][slug]["chamfer"]]
        assert statistics.mean(draws) + SIGMAS * statistics.pstdev(draws) <= CHAMFER_FLOOR, slug


@pytest.mark.parametrize("slug", SLUGS)
def test_our_field_is_within_the_measured_tolerance_of_their_scorer(slug: str) -> None:
    row = SCORER["pairs"][slug]
    ours = pairs.ours(slug)
    assert ours.status is ag.Status.OK
    assert ours.field is not None
    assert abs(ours.field.voxel_iou_64 - row["voxel_iou_64"][0]) <= VOXEL_TOLERANCE
    theirs = statistics.mean(1000.0 * v for v in row["chamfer"])
    assert abs(ours.field.chamfer_x1000 - theirs) <= CHAMFER_FLOOR + CHAMFER_RELATIVE * theirs


@pytest.mark.parametrize("slug", FLOOR_PAIRS)
def test_one_shape_twice_is_a_perfect_field_for_us_and_a_floor_for_them(slug: str) -> None:
    ours = pairs.ours(slug).field
    assert ours is not None
    assert (ours.voxel_iou_64, ours.chamfer_x1000) == (1.0, 0.0)
    assert SCORER["pairs"][slug]["voxel_iou_64"][0] == 1.0
    assert min(SCORER["pairs"][slug]["chamfer"]) > 0.0


def test_a_cone_against_a_cone_is_answered_by_the_sampled_route() -> None:
    scored = pairs.ours("cone-pair")
    assert scored.iou_route is IouRoute.SAMPLED
    assert scored.iou is not None
    assert 0.0 < scored.iou < 1.0
    assert math.isfinite(SCORER["pairs"]["cone-pair"]["chamfer"][0])

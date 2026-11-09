"""M4's acceptance (docs/plans/m4-reward.md, docs/ROADMAP.md §M4): the reward, offline.

Every closed form of the roadmap's list through the public `score`: the
failure rewards, a body against itself, the three IoUs, the disjoint bound,
the faceted hole, and the field within ADR-0010 of BenchCAD's own scorer on
ten pairs; then the digest of the fixtures' scores and `score` on arbitrary
bytes. Expected values come from how the parts were built, never from this
library's own output.
"""

from __future__ import annotations

import functools
import json
import math
from collections.abc import Iterator

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

import arris_gym as ag
import benchcad_pairs as pairs
import fixture_cases
import test_reward_benchcad as benchcad

REWARD_ROOT = fixture_cases.ROOT / "reward"
# SEED.md §7.1's table, the failure rewards of the roadmap's first closed form.
FAILURE_REWARDS = {
    ag.Status.SYNTAX: -1.0,
    ag.Status.RUNTIME: -1.0,
    ag.Status.UNSUPPORTED_API: -1.0,
    ag.Status.TIMEOUT: -1.0,
    ag.Status.CRASH: -1.0,
    ag.Status.ARRIS_REFUSAL: -0.5,
    ag.Status.CHECKER_FAIL: -0.3,
}
# The reward of a disjoint pair is at most 0.1 + 0.9 * (the other three terms'
# weight, 0.15 + 0.15 + 0.10): the IoU is 0, so its 0.6 weight earns nothing.
OTHER_TERMS_WEIGHT = 0.4
SANDBOX_CASES = fixture_cases.load("sandbox")
# A plate with a round hole against one with a 12-sided hole of the same
# radius: 6 planes and a cylinder against 18 planes, one through hole each.
ROUND_HOLE = """import arris.build as b

plate = b.Solid.box((-5, -5, 0), (5, 5, 1))
result = plate.cut(b.Solid.cylinder((0, 0, -1), (0, 0, 1), 2, 3))
"""
FACETED_HOLE = """import math

import arris.build as b

ring = [(2 * math.cos(math.tau * i / 12), 2 * math.sin(math.tau * i / 12)) for i in range(12)]
hole = b.Workplane.XY().polygon(ring).extrude(3).moved((0, 0, -1))
plate = b.Solid.box((-5, -5, 0), (5, 5, 1))
result = plate.cut(hole)
"""


@pytest.fixture(scope="module")
def sandbox() -> Iterator[ag.Sandbox]:
    with ag.Sandbox() as box:
        yield box


@functools.cache
def _ran(program: str) -> ag.ExecResult:
    result = ag.run(program)
    assert result.status is ag.Status.OK, result.message
    return result


def _pair(slug: str) -> tuple[ag.ExecResult, ag.BodyRef]:
    folder = REWARD_ROOT / slug
    target = _ran((folder / "target.py").read_text(encoding="utf-8"))
    assert target.body is not None
    return _ran((folder / "program.py").read_text(encoding="utf-8")), target.body


def _expected_iou(slug: str) -> float:
    expected = json.loads((REWARD_ROOT / slug / "expected.json").read_text(encoding="utf-8"))
    return float(expected["iou"])


# --- a failure status gives exactly the table's reward -------------------------


def test_every_failure_status_gives_exactly_its_reward(sandbox: ag.Sandbox) -> None:
    _, target = _pair("self")
    seen = set()
    for case in SANDBOX_CASES:
        result = fixture_cases.run(case)
        if result.status is ag.Status.OK:
            continue
        got = ag.score(result, target, sandbox=sandbox)
        assert got.status is result.status, case.slug
        assert got.reward == FAILURE_REWARDS[result.status], case.slug
        assert got.message == result.message, case.slug
        assert (got.iou, got.surface, got.measures, got.topology, got.field) == (None,) * 5
        seen.add(result.status)
    assert seen == set(FAILURE_REWARDS)


# --- a body against itself ----------------------------------------------------


@pytest.mark.parametrize("slug", ["self", "cube-and-double", "iou-third"])
def test_a_body_against_itself_is_one_on_all_four_terms_and_the_reward(
    sandbox: ag.Sandbox, slug: str
) -> None:
    candidate, _ = _pair(slug)
    assert candidate.body is not None
    got = ag.score(candidate, candidate.body, sandbox=sandbox)
    assert got.status is ag.Status.OK
    assert (got.iou, got.surface, got.measures, got.topology) == (1.0, 1.0, 1.0, 1.0)
    assert got.reward == 1.0
    assert got.iou_route is ag.IouRoute.EXACT


# --- the IoU's closed forms ---------------------------------------------------


@pytest.mark.parametrize(
    ("slug", "iou"), [("iou-third", 1 / 3), ("disjoint", 0.0), ("cube-and-double", 1 / 8)]
)
def test_the_iou_is_its_closed_form(sandbox: ag.Sandbox, slug: str, iou: float) -> None:
    assert _expected_iou(slug) == pytest.approx(iou, abs=0, rel=1e-15)
    candidate, target = _pair(slug)
    got = ag.score(candidate, target, sandbox=sandbox)
    assert got.status is ag.Status.OK
    assert got.iou is not None
    assert fixture_cases.close(got.iou, iou)
    assert got.iou_route is ag.IouRoute.EXACT


def test_disjoint_bodies_score_at_most_the_other_terms_share(sandbox: ag.Sandbox) -> None:
    candidate, target = _pair("disjoint")
    got = ag.score(candidate, target, sandbox=sandbox)
    assert got.iou == 0.0
    assert got.reward <= 0.1 + 0.9 * OTHER_TERMS_WEIGHT


def test_touching_bodies_have_an_iou_of_zero(sandbox: ag.Sandbox) -> None:
    candidate, target = _pair("touching")
    got = ag.score(candidate, target, sandbox=sandbox)
    assert got.iou == 0.0


# --- topology -----------------------------------------------------------------


def test_a_faceted_hole_has_a_topology_below_one_and_below_the_plate_against_itself(
    sandbox: ag.Sandbox,
) -> None:
    round_plate, faceted = _ran(ROUND_HOLE), _ran(FACETED_HOLE)
    assert round_plate.body is not None
    itself = ag.score(round_plate, round_plate.body, sandbox=sandbox)
    against = ag.score(faceted, round_plate.body, sandbox=sandbox)
    assert itself.topology == 1.0
    assert against.topology is not None
    assert against.topology < 1.0
    assert against.topology < (itself.topology or 0.0)


# --- the field against BenchCAD's scorer ---------------------------------------


@pytest.mark.parametrize("slug", pairs.SLUGS)
def test_the_field_is_within_adr_0010_of_their_scorer_on_ten_pairs(slug: str) -> None:
    row = pairs.SCORER["pairs"][slug]
    ours = pairs.ours(slug)
    assert ours.field is not None
    assert abs(ours.field.voxel_iou_64 - row["voxel_iou_64"][0]) <= benchcad.VOXEL_TOLERANCE
    theirs = math.fsum(1000.0 * v for v in row["chamfer"]) / len(row["chamfer"])
    gap = abs(ours.field.chamfer_x1000 - theirs)
    assert gap <= benchcad.CHAMFER_FLOOR + benchcad.CHAMFER_RELATIVE * theirs


# --- the digest and the range --------------------------------------------------


def test_a_score_digests_the_same_scored_again(sandbox: ag.Sandbox) -> None:
    for slug in ("iou-third", "cone-shifted", "self"):
        candidate, target = _pair(slug)
        first = ag.score(candidate, target, sandbox=sandbox)
        second = ag.score(candidate, target, sandbox=sandbox)
        assert first.digest() == second.digest(), slug


@settings(
    max_examples=25, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(noise=st.binary(max_size=256), cut=st.integers(0, 64))
def test_score_on_arbitrary_bytes_never_raises_and_stays_in_range(
    sandbox: ag.Sandbox, noise: bytes, cut: int
) -> None:
    real, target = _pair("self")
    assert real.body is not None
    forged = real.model_copy(
        update={"body": ag.BodyRef.of(real.body.data[: max(0, len(real.body.data) - cut)] + noise)}
    )
    got = ag.score(forged, target, sandbox=sandbox)
    assert got.reward == -1.0 or 0.1 <= got.reward <= 1.0
    assert got.status in (ag.Status.OK, ag.Status.RUNTIME, ag.Status.CRASH)

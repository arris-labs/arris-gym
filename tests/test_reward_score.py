"""The reward formula, `RewardConfig` and `Score`'s invariants.

docs/plans/m4-reward.md step 5. The failure rewards are SEED.md §7.1's table
written out; the range property holds for any terms and any valid weights.
"""

from __future__ import annotations

import doctest
import math

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from arris_gym.reward import (
    DEFAULT_REWARD,
    FieldMetrics,
    IouRoute,
    RewardConfig,
    RewardWeights,
    Score,
    invalidity_rate,
)
from arris_gym.reward._score import combine, failure_reward
from arris_gym.sandbox.outcome import Status, Versions

VERSIONS = Versions(arris="0.10.0", numpy="2.3.4", arris_gym="0.1.0")
# A weight vector drawn as four non-negative numbers and normalised: its sum
# is 1 within a few ulps, far inside the config's tolerance.
UNIT = st.floats(min_value=0.0, max_value=1.0)
WEIGHT_PARTS = st.lists(st.floats(min_value=0.001, max_value=1.0), min_size=4, max_size=4)

FAILURES = {
    Status.SYNTAX: -1.0,
    Status.RUNTIME: -1.0,
    Status.UNSUPPORTED_API: -1.0,
    Status.TIMEOUT: -1.0,
    Status.CRASH: -1.0,
    Status.ARRIS_REFUSAL: -0.5,
    Status.CHECKER_FAIL: -0.3,
}


def _failed(status: Status, reward: float) -> Score:
    return Score(
        status=status,
        message="m",
        reward=reward,
        iou=None,
        iou_route=None,
        surface=None,
        measures=None,
        topology=None,
        field=None,
        reward_version=1,
        versions=VERSIONS,
    )


FIELD = FieldMetrics(voxel_iou_64=1.0, chamfer_x1000=0.0)


def _ok(
    reward: float, terms: tuple[float, float, float, float], field: FieldMetrics | None = FIELD
) -> Score:
    return Score(
        status=Status.OK,
        message="",
        reward=reward,
        iou=terms[0],
        iou_route=IouRoute.EXACT,
        surface=terms[1],
        measures=terms[2],
        topology=terms[3],
        field=field,
        reward_version=1,
        versions=VERSIONS,
    )


# --- the failure table ---------------------------------------------------------


@pytest.mark.parametrize(("status", "reward"), list(FAILURES.items()))
def test_a_failure_status_has_exactly_its_tables_reward(status: Status, reward: float) -> None:
    assert failure_reward(status) == reward
    assert _failed(status, reward).reward == reward


def test_every_status_but_ok_is_in_the_table() -> None:
    assert {s for s in Status if failure_reward(s) is not None} == set(FAILURES)
    assert failure_reward(Status.OK) is None


@pytest.mark.parametrize("status", list(FAILURES))
def test_a_failure_score_with_another_reward_is_refused(status: Status) -> None:
    with pytest.raises(ValidationError, match="exactly"):
        _failed(status, FAILURES[status] + 0.1)


# --- the valid-body reward -----------------------------------------------------


def test_four_terms_of_one_give_exactly_one() -> None:
    assert combine(DEFAULT_REWARD, iou=1.0, surface=1.0, measures=1.0, topology=1.0) == 1.0


def test_four_terms_of_zero_give_the_floor() -> None:
    assert combine(DEFAULT_REWARD, iou=0.0, surface=0.0, measures=0.0, topology=0.0) == 0.1


def test_the_reward_is_the_seeds_formula() -> None:
    got = combine(DEFAULT_REWARD, iou=0.5, surface=0.4, measures=0.3, topology=0.2)
    s = 0.6 * 0.5 + 0.15 * 0.4 + 0.15 * 0.3 + 0.10 * 0.2
    assert abs(got - (0.1 + 0.9 * s)) <= 1e-15


@given(iou=UNIT, surface=UNIT, measures=UNIT, topology=UNIT, parts=WEIGHT_PARTS)
def test_any_terms_and_any_weights_give_a_reward_in_range(
    iou: float, surface: float, measures: float, topology: float, parts: list[float]
) -> None:
    total = math.fsum(parts)
    a, b, c, d = (p / total for p in parts)
    config = RewardConfig(weights=RewardWeights(iou=a, surface=b, measures=c, topology=d))
    reward = combine(config, iou=iou, surface=surface, measures=measures, topology=topology)
    assert 0.1 <= reward <= 1.0


@given(parts=WEIGHT_PARTS)
def test_unit_terms_give_exactly_one_for_any_weights_that_sum_to_one(parts: list[float]) -> None:
    total = math.fsum(parts)
    weights = RewardWeights(
        iou=parts[0] / total,
        surface=parts[1] / total,
        measures=parts[2] / total,
        topology=parts[3] / total,
    )
    got = combine(RewardConfig(weights=weights), iou=1.0, surface=1.0, measures=1.0, topology=1.0)
    assert got <= 1.0
    assert got >= 1.0 - 1e-15


@pytest.mark.parametrize("bad", [-0.01, 1.01, math.nan, math.inf])
def test_a_term_out_of_range_is_refused(bad: float) -> None:
    with pytest.raises(ValueError, match=r"in \[0, 1\]"):
        combine(DEFAULT_REWARD, iou=bad, surface=1.0, measures=1.0, topology=1.0)


@given(parts=WEIGHT_PARTS, scale=st.floats(min_value=1.001, max_value=3.0))
def test_weights_not_summing_to_one_are_refused(parts: list[float], scale: float) -> None:
    total = math.fsum(parts)
    a, b, c, d = (min(1.0, p / total * scale) for p in parts)
    if abs(math.fsum((a, b, c, d)) - 1.0) <= 1e-9:
        return  # clipped back onto a sum of 1
    with pytest.raises(ValidationError, match="sum to 1"):
        RewardWeights(iou=a, surface=b, measures=c, topology=d)


def test_a_score_for_ok_needs_its_terms_and_a_reward_in_range() -> None:
    _ok(0.55, (0.5, 0.5, 0.5, 0.5))
    with pytest.raises(ValidationError, match=r"in \[0.1, 1\]"):
        _ok(0.05, (0.5, 0.5, 0.5, 0.5))
    with pytest.raises(ValidationError, match="finite number in"):
        _ok(0.55, (1.5, 0.5, 0.5, 0.5))
    with pytest.raises(ValidationError, match="the field metrics"):
        _ok(0.55, (0.5, 0.5, 0.5, 0.5), field=None)
    with pytest.raises(ValidationError, match="all four terms"):
        Score(
            status=Status.OK, message="", reward=0.5, iou=None, iou_route=None, surface=None,
            measures=None, topology=None, field=None, reward_version=1, versions=VERSIONS,
        )  # fmt: skip


@pytest.mark.parametrize(
    "bad",
    [
        {"voxel_iou_64": 1.5},
        {"voxel_iou_64": -0.1},
        {"voxel_iou_64": math.nan},
        {"chamfer_x1000": -1.0},
        {"chamfer_x1000": math.inf},
        {"chamfer_x1000": "0.5"},
        {"rank": 1},
    ],
)
def test_field_metrics_out_of_range_are_refused(bad: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        FieldMetrics.model_validate({"voxel_iou_64": 0.5, "chamfer_x1000": 2.0, **bad})


def test_a_failure_with_field_metrics_is_refused() -> None:
    with pytest.raises(ValidationError, match="no terms"):
        Score(
            status=Status.CRASH, message="", reward=-1.0, iou=None, iou_route=None, surface=None,
            measures=None, topology=None, field=FIELD, reward_version=1, versions=VERSIONS,
        )  # fmt: skip


def test_a_failure_with_a_term_is_refused() -> None:
    with pytest.raises(ValidationError, match="no terms"):
        Score(
            status=Status.CRASH, message="", reward=-1.0, iou=0.5, iou_route=None, surface=None,
            measures=None, topology=None, field=None, reward_version=1, versions=VERSIONS,
        )  # fmt: skip


# --- the config ----------------------------------------------------------------


def test_the_default_config_is_the_seeds_and_the_adrs() -> None:
    config = DEFAULT_REWARD
    assert config.version == 1
    assert (config.weights.iou, config.weights.surface) == (0.6, 0.15)
    assert (config.weights.measures, config.weights.topology) == (0.15, 0.10)
    assert config.tau == 0.05
    assert config.points == 10_648
    assert config.surface_points == 5_324
    assert config.iou_budget == 10**7
    assert config.chord_fraction == 1 / 200
    assert config.kind_weight == 0.5


@pytest.mark.parametrize(
    "bad",
    [
        {"tau": 0.0},
        {"points": 1},
        {"iou_budget": 0},
        {"chord_fraction": -1.0},
        {"kind_weight": 1.5},
        {"seed": -1},
        {"version": 0},
        {"unknown": 1},
    ],
)
def test_a_bad_config_is_refused(bad: dict[str, float]) -> None:
    with pytest.raises(ValidationError):
        RewardConfig(**bad)  # type: ignore[arg-type]


def test_a_config_is_frozen() -> None:
    with pytest.raises(ValidationError):
        DEFAULT_REWARD.tau = 1.0


# --- the digest ----------------------------------------------------------------


def test_the_digest_moves_with_one_bit_of_the_reward() -> None:
    a = _ok(0.55, (0.5, 0.5, 0.5, 0.5))
    b = _ok(math.nextafter(0.55, 1.0), (0.5, 0.5, 0.5, 0.5))
    assert a.digest() == _ok(0.55, (0.5, 0.5, 0.5, 0.5)).digest()
    assert a.digest() != b.digest()


def test_the_digest_moves_with_one_bit_of_either_field_metric() -> None:
    terms = (0.5, 0.5, 0.5, 0.5)
    base = _ok(0.55, terms, FieldMetrics(voxel_iou_64=0.5, chamfer_x1000=2.0))
    for nudged in (
        FieldMetrics(voxel_iou_64=math.nextafter(0.5, 1.0), chamfer_x1000=2.0),
        FieldMetrics(voxel_iou_64=0.5, chamfer_x1000=math.nextafter(2.0, 3.0)),
    ):
        assert _ok(0.55, terms, nudged).digest() != base.digest()


# --- the corpus aggregate -------------------------------------------------------


def test_the_invalidity_rate_counts_every_row_and_every_failure() -> None:
    ok = _ok(1.0, (1.0, 1.0, 1.0, 1.0))
    rows = [
        ok,
        _failed(Status.SYNTAX, -1.0),
        _failed(Status.ARRIS_REFUSAL, -0.5),
        _failed(Status.CHECKER_FAIL, -0.3),
        _failed(Status.TIMEOUT, -1.0),
        _failed(Status.CRASH, -1.0),
        _failed(Status.RUNTIME, -1.0),
        ok,
    ]
    assert invalidity_rate(rows) == 6 / 8
    assert invalidity_rate([ok]) == 0.0
    assert invalidity_rate(iter([_failed(Status.SYNTAX, -1.0)])) == 1.0


@given(
    st.lists(st.sampled_from(sorted(FAILURES, key=lambda s: s.value)), max_size=20),
    st.integers(0, 20),
)
def test_the_invalidity_rate_is_the_failures_over_all_rows(
    failures: list[Status], valid: int
) -> None:
    rows = [_failed(status, FAILURES[status]) for status in failures]
    rows += [_ok(1.0, (1.0, 1.0, 1.0, 1.0))] * valid
    if not rows:
        with pytest.raises(ValueError, match="no scores"):
            invalidity_rate(rows)
        return
    assert invalidity_rate(rows) == len(failures) / len(rows)


def test_the_aggregate_examples_run() -> None:
    from arris_gym.reward import _aggregate

    assert doctest.testmod(_aggregate).failed == 0

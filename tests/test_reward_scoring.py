"""`score` and its score worker: the reward of a result against a target.

docs/plans/m4-reward.md step 6. A failure status is scored with no kernel
call; a valid body goes to a score worker, whose frame the caller trusts no
more than any worker's. Each hostile case has its own status, and `score`
never raises on the bodies' bytes.
"""

from __future__ import annotations

import doctest
import functools
import json
from collections.abc import Iterator
from typing import Any

import arris
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

import arris_gym as ag
import fixture_cases
from arris_gym.reward import DEFAULT_REWARD, combine
from arris_gym.reward._iou import iou
from arris_gym.reward._job import ScoreJob, frame
from arris_gym.reward._measures import measures
from arris_gym.reward._scoring import SCORE_WORKER, parse_outcome
from arris_gym.reward._surface import surface
from arris_gym.reward._topology import topology
from arris_gym.sandbox._isolate import Ending, EndKind
from arris_gym.sandbox._program import exception_line
from arris_gym.sandbox._zygote import JobKind, Outcome, register

BOX = "import arris.build as b\nresult = b.Solid.box((0, 0, 0), (1, 2, 3))\n"
TIMEOUT = 30.0
CLEAN = Ending(EndKind.EXITED, 0, True)
REWARD_ROOT = fixture_cases.ROOT / "reward"
SLUGS = sorted(d.name for d in REWARD_ROOT.iterdir() if (d / "program.py").is_file())


@pytest.fixture(scope="module")
def sandbox() -> Iterator[ag.Sandbox]:
    with ag.Sandbox() as box:
        yield box


@functools.cache
def _result(program: str) -> ag.ExecResult:
    result = ag.run(program)
    assert result.status is ag.Status.OK, result.message
    return result


def _fixture(slug: str) -> tuple[ag.ExecResult, ag.ExecResult]:
    folder = REWARD_ROOT / slug
    return (
        _result((folder / "program.py").read_text(encoding="utf-8")),
        _result((folder / "target.py").read_text(encoding="utf-8")),
    )


def _body(result: ag.ExecResult) -> ag.BodyRef:
    assert result.body is not None
    return result.body


def _forged(candidate: bytes) -> ag.ExecResult:
    """An `ok` result whose body is `candidate`, as a caller could build it."""
    real = _result(BOX)
    return real.model_copy(update={"body": ag.BodyRef.of(candidate)})


# --- valid bodies --------------------------------------------------------------


def test_a_body_against_itself_scores_exactly_one(sandbox: ag.Sandbox) -> None:
    for slug in ("self", "cube-and-double"):
        candidate, _ = _fixture(slug)
        got = ag.score(candidate, _body(candidate), sandbox=sandbox)
        assert (got.status, got.message) == (ag.Status.OK, "")
        assert (got.iou, got.surface, got.measures, got.topology) == (1.0, 1.0, 1.0, 1.0)
        assert got.reward == 1.0
        assert got.iou_route is ag.IouRoute.EXACT
        assert got.field is None  # step 7 computes the field metrics
        assert got.reward_version == DEFAULT_REWARD.version


@pytest.mark.parametrize("slug", SLUGS)
def test_the_worker_gives_the_in_process_terms_bit_for_bit(sandbox: ag.Sandbox, slug: str) -> None:
    candidate, target = _fixture(slug)
    got = ag.score(candidate, _body(target), sandbox=sandbox)
    config = DEFAULT_REWARD
    model = arris.Model()
    a = model.read_body(_body(candidate).data).body
    b = model.read_body(_body(target).data).body
    want = iou(
        model,
        a,
        b,
        budget=config.iou_budget,
        chord_fraction=config.chord_fraction,
        points=config.points,
        seed=config.seed,
    )
    near = surface(
        model,
        a,
        b,
        tau=config.tau,
        chord_fraction=config.chord_fraction,
        points=config.surface_points,
        seed=config.seed,
    )
    shape = measures(model, a, b)
    kinds = topology(model, a, b, kind_weight=config.kind_weight)
    expected = json.loads((REWARD_ROOT / slug / "expected.json").read_text(encoding="utf-8"))
    assert got.status is ag.Status.OK, got.message
    assert got.iou_route is not None
    assert got.iou_route.value == expected["route"]
    assert (got.iou, got.iou_route, got.surface, got.measures, got.topology) == (
        want.value,
        want.route,
        near,
        shape,
        kinds,
    )
    assert got.reward == combine(
        config, iou=want.value, surface=near, measures=shape, topology=kinds
    )


def test_a_config_moves_the_reward_and_is_recorded(sandbox: ag.Sandbox) -> None:
    candidate, target = _fixture("iou-third")
    config = ag.RewardConfig(
        version=7, weights=ag.RewardWeights(iou=1.0, surface=0.0, measures=0.0, topology=0.0)
    )
    got = ag.score(candidate, _body(target), config=config, sandbox=sandbox)
    assert got.reward_version == 7
    assert got.iou is not None
    assert got.reward == 0.1 + 0.9 * got.iou


# --- failures: the table, with no kernel call ------------------------------------


def test_a_failure_gets_the_table_with_no_worker() -> None:
    closed = ag.Sandbox()
    closed.close()  # any job on it raises RuntimeError: none is sent
    target = _body(_result(BOX))
    for program, status, reward in (
        ("result = (", ag.Status.SYNTAX, -1.0),
        ("x = 1", ag.Status.RUNTIME, -1.0),
    ):
        result = ag.run(program)
        got = ag.score(result, target, sandbox=closed)
        assert (got.status, got.reward, got.message) == (status, reward, result.message)
        assert got.iou is None
        assert got.iou_route is None


# --- hostile cases, each its status ------------------------------------------------


def test_a_target_the_kernel_cannot_read_is_runtime_in_its_words(sandbox: ag.Sandbox) -> None:
    got = ag.score(_result(BOX), ag.BodyRef.of(b"not a body"), sandbox=sandbox)
    assert (got.status, got.reward) == (ag.Status.RUNTIME, -1.0)
    model = arris.Model()
    with pytest.raises(arris.ArrisError) as refused:
        model.read_body(b"not a body")
    assert got.message == exception_line(refused.value)  # the kernel's words, verbatim


def test_a_candidate_cut_short_is_runtime(sandbox: ag.Sandbox) -> None:
    whole = _body(_result(BOX)).data
    got = ag.score(_forged(whole[: len(whole) // 2]), _body(_result(BOX)), sandbox=sandbox)
    assert (got.status, got.reward) == (ag.Status.RUNTIME, -1.0)
    assert got.message


def test_a_deadline_passed_is_a_timeout(sandbox: ag.Sandbox) -> None:
    candidate, target = _fixture("iou-third")
    got = ag.score(candidate, _body(target), sandbox=sandbox, timeout=1e-3)
    assert (got.status, got.reward) == (ag.Status.TIMEOUT, -1.0)
    assert got.message == f"the {SCORE_WORKER} ran past the 0.001 s deadline"


def _ok_frame(**changes: Any) -> bytes:
    base: dict[str, Any] = {
        "status": "ok",
        "message": "",
        "iou": 0.5,
        "iou_route": "exact",
        "surface": 0.25,
        "measures": 0.75,
        "topology": 1.0,
    }
    return json.dumps({**base, **changes}).encode()


def _parse(data: bytes, ending: Ending | None = CLEAN, *, overflow: bool = False) -> ag.Score:
    outcome = Outcome(ending=ending, data=data, overflow=overflow, stderr=b"")
    return parse_outcome(outcome, DEFAULT_REWARD, timeout=TIMEOUT)


def test_a_whole_frame_is_scored_by_the_caller() -> None:
    got = _parse(_ok_frame())
    assert got.status is ag.Status.OK
    assert got.reward == combine(DEFAULT_REWARD, iou=0.5, surface=0.25, measures=0.75, topology=1.0)


@pytest.mark.parametrize(
    "data",
    [
        b"",
        b"{",
        b"[]",
        b"\xff\xfe",
        b"[" * 100_000,
        _ok_frame(iou=1.5),
        _ok_frame(surface=-0.1),
        _ok_frame(measures=None),
        _ok_frame(topology="1"),
        _ok_frame(iou=float("nan")),
        _ok_frame(iou=float("inf")),
        _ok_frame(iou_route=None),
        _ok_frame(iou_route="guessed"),
        _ok_frame(status="timeout"),
        _ok_frame(status="checker_fail"),
        _ok_frame(status="runtime"),
        _ok_frame(reward=1.0),
    ],
    ids=lambda d: d[:40].decode("utf-8", "replace"),
)
def test_a_forged_or_out_of_range_frame_is_a_crash(data: bytes) -> None:
    got = _parse(data)
    assert (got.status, got.reward) == (ag.Status.CRASH, -1.0)


def test_a_worker_that_ended_badly_is_a_crash() -> None:
    for ending, overflow in (
        (None, False),
        (Ending(EndKind.SIGNALLED, 11, True), False),
        (Ending(EndKind.EXITED, 1, True), False),
        (Ending(EndKind.EXITED, 0, False), False),
        (CLEAN, True),
    ):
        got = _parse(_ok_frame(), ending, overflow=overflow)
        assert (got.status, got.reward) == (ag.Status.CRASH, -1.0)
        assert SCORE_WORKER in got.message


def test_the_worker_frames_its_own_refusal() -> None:
    assert frame(b"not a job").status is ag.Status.RUNTIME
    job = ScoreJob(config=DEFAULT_REWARD, candidate=b"x", target=b"y")
    refused = frame(job.model_dump_json().encode())
    assert refused.status is ag.Status.RUNTIME
    assert refused.message.startswith("arris.")


@settings(max_examples=40, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    cut=st.integers(min_value=0, max_value=10_000),
    flips=st.lists(st.tuples(st.integers(min_value=0), st.integers(1, 255)), max_size=4),
    noise=st.binary(max_size=64),
    target_is_real=st.booleans(),
)
def test_score_never_raises_on_arbitrary_body_bytes(
    sandbox: ag.Sandbox,
    cut: int,
    flips: list[tuple[int, int]],
    noise: bytes,
    target_is_real: bool,
) -> None:
    whole = bytearray(_body(_result(BOX)).data)
    for at, mask in flips:
        whole[at % len(whole)] ^= mask
    candidate = bytes(whole[: max(0, len(whole) - cut)]) + noise
    target = _body(_result(BOX)) if target_is_real else ag.BodyRef.of(noise + candidate)
    got = ag.score(_forged(candidate), target, sandbox=sandbox)
    assert got.status in (ag.Status.OK, ag.Status.RUNTIME, ag.Status.CRASH)
    assert got.reward == -1.0 or 0.1 <= got.reward <= 1.0


# --- the caller's mistakes ----------------------------------------------------------


def test_a_caller_mistake_raises() -> None:
    result = _result(BOX)
    target = _body(result)
    with pytest.raises(TypeError):
        ag.score(result, target.data)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        ag.score(target, target)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        ag.score(result, target, config={"tau": 1.0})  # type: ignore[arg-type]
    for timeout in (0.0, -1.0, float("nan")):
        with pytest.raises(ValueError, match="timeout"):
            ag.score(result, target, timeout=timeout)
    with pytest.raises(ValueError, match="memory"):
        ag.score(result, target, memory=0)


def test_a_served_kind_cannot_be_registered_again() -> None:
    with pytest.raises(ValueError, match="already served"):
        register(JobKind.PROGRAM, lambda payload, result: None)


def test_the_examples_run() -> None:
    from arris_gym.reward import _scoring

    assert doctest.testmod(_scoring).failed == 0

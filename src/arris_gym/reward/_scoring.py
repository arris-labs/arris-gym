"""`score`: a result's reward against a target, its body scored in a score worker.

SEED.md §7.1, docs/ARCHITECTURE.md §The reward and §The sandbox. A failure
status gets the table's reward with no kernel call. A valid body goes, with
the target's bytes and the config, to a score worker (`reward/_job.py`)
under a deadline and a memory limit; the caller parses its frame as it
parses every frame, trusting nothing, and computes the reward from the
terms itself. A job that ends without a frame to trust is a `timeout` or a
`crash`, and the worker's own refusal a `runtime`, each with the reward
-1.0, so a scorer that fails never pays.
"""

from __future__ import annotations

import time

import pydantic

from arris_gym.reward._config import DEFAULT_REWARD, RewardConfig
from arris_gym.reward._job import ScoreFrame, ScoreJob
from arris_gym.reward._score import Score, combine, failure_reward
from arris_gym.sandbox._run import DEFAULT_MEMORY, check_arguments, current_versions, ended
from arris_gym.sandbox._sandbox import Sandbox, default_sandbox
from arris_gym.sandbox._zygote import JobKind, Outcome
from arris_gym.sandbox.outcome import BodyRef, Dialect, ExecResult, Status

# The score worker's wall-clock deadline. ADR-0008 measured an exact answer
# near the IoU's step cap at 17 s under 30 concurrent processes, the slowest
# pair of the slice; 30 s leaves 1.8 times that. A scoring timeout is a
# status, counted, never a score (plans/m4-reward, Settled).
DEFAULT_SCORE_TIMEOUT = 30.0
# The workers as a crash's or a timeout's message names them.
SCORE_WORKER = "score worker"


def _failed(status: Status, message: str, config: RewardConfig) -> Score:
    reward = failure_reward(status)
    assert reward is not None, "a failure status has a table reward"
    return Score(
        status=status,
        message=message,
        reward=reward,
        iou=None,
        iou_route=None,
        surface=None,
        measures=None,
        topology=None,
        field=None,
        reward_version=config.version,
        versions=current_versions(),
    )


def parse_outcome(outcome: Outcome, config: RewardConfig, *, timeout: float) -> Score:
    """The score of the job whose outcome came back unread. Never raises.

    A job that delivered nothing to trust (timed out, killed, no record,
    overflowed, exited non-zero) is `timeout` or `crash` with the sandbox's
    own message; a frame that is not whole, contradicts its status or holds a
    term that is not a finite number in [0, 1] is a `crash`; the worker's
    `runtime` keeps its words. An `ok` frame's terms give the reward under
    `config`.
    """
    early = ended(outcome, SCORE_WORKER, timeout)
    if early is not None:
        return _failed(early.status, early.message, config)
    try:
        frame = ScoreFrame.model_validate_json(outcome.data)
    except (pydantic.ValidationError, ValueError, RecursionError):
        return _failed(
            Status.CRASH, f"the {SCORE_WORKER} delivered a result that is not a valid frame", config
        )
    if frame.status is Status.RUNTIME:  # the frame is `ok` or `runtime` (SCORE_STATUSES)
        return _failed(Status.RUNTIME, frame.message, config)
    assert frame.iou is not None
    assert frame.surface is not None
    assert frame.measures is not None
    assert frame.topology is not None
    return Score(
        status=Status.OK,
        message="",
        reward=combine(
            config,
            iou=frame.iou,
            surface=frame.surface,
            measures=frame.measures,
            topology=frame.topology,
        ),
        iou=frame.iou,
        iou_route=frame.iou_route,
        surface=frame.surface,
        measures=frame.measures,
        topology=frame.topology,
        field=None,
        reward_version=config.version,
        versions=current_versions(),
    )


def score(
    result: ExecResult,
    target: BodyRef,
    *,
    config: RewardConfig = DEFAULT_REWARD,
    sandbox: Sandbox | None = None,
    timeout: float = DEFAULT_SCORE_TIMEOUT,
    memory: int = DEFAULT_MEMORY,
) -> Score:
    """The reward of `result` against the body `target`, with its terms.

    A failure status gets SEED.md §7.1's table, -1.0, -0.5 or -0.3, with the
    result's message and no kernel call. An `ok` result's body and `target`
    are read into one fresh model in a score worker of `sandbox` (the
    process's shared one by default), `timeout` seconds of wall clock and
    `memory` bytes of address space at most, and the reward is
    `0.1 + 0.9·S` over the IoU, surface, measures and topology terms under
    `config`. When scoring fails, the score's status is `runtime` (the
    kernel's words: a target it cannot read, say), `timeout` or `crash`, and
    its reward -1.0. `versions` are this process's. Never raises on the
    bodies' bytes; raises `TypeError` for arguments of the wrong type,
    `ValueError` for a `timeout` or `memory` that is not positive, and
    `SandboxUnavailable` where this machine cannot isolate a worker.

    >>> import arris_gym as ag
    >>> part = ag.run("import arris.build as b\\nresult = b.Solid.box((0, 0, 0), (1, 2, 3))")
    >>> s = ag.score(part, part.body)
    >>> s.status.value, s.reward, s.iou_route.value
    ('ok', 1.0, 'exact')
    >>> ag.score(ag.run("result = ("), part.body).reward
    -1.0
    """
    if not isinstance(result, ExecResult):
        raise TypeError(f"result must be an ExecResult, got {type(result).__name__}")
    if not isinstance(target, BodyRef):
        raise TypeError(f"target must be a BodyRef, got {type(target).__name__}")
    if not isinstance(config, RewardConfig):
        raise TypeError(f"config must be a RewardConfig, got {type(config).__name__}")
    check_arguments(Dialect.ARRIS, timeout, memory)
    if failure_reward(result.status) is not None:
        return _failed(result.status, result.message, config)
    body = result.body
    assert body is not None, "an ok result has a body (ExecResult's guarantee)"
    zygote = (sandbox if sandbox is not None else default_sandbox())._live_zygote()
    payload = ScoreJob(config=config, candidate=body.data, target=target.data)
    outcome = zygote.execute(
        JobKind.SCORE,
        payload.model_dump_json().encode(),
        deadline=time.monotonic() + timeout,
        memory=memory,
    )
    return parse_outcome(outcome, config, timeout=timeout)

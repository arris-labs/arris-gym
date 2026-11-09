"""`rescore`: run each program, read its target, score the pair (ADR-0011).

docs/ARCHITECTURE.md §The re-scored table. Every entry becomes a row: a
failure at any stage is counted under its `Stage`, never dropped, and the
kernel's words are kept verbatim.
"""

from __future__ import annotations

from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from typing import assert_never

from arris_gym.rescore._table import RescoreEntry, RescoreRow, RescoreTable, Stage
from arris_gym.reward import DEFAULT_REWARD, Score, score
from arris_gym.reward._score import failure_reward
from arris_gym.sandbox import ExecResult, Sandbox, Status, TargetResult, read_target
from arris_gym.sandbox._run import current_versions
from arris_gym.sandbox._sandbox import _check_workers


def _failed(status: Status, message: str) -> Score:
    """The `Score` of a failure `status`: the table's reward, no terms, this process's versions."""
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
        reward_version=DEFAULT_REWARD.version,
        versions=current_versions(),
    )


def _target_failure(target: TargetResult) -> Score:
    """The `Score` of a pair whose target did not end `ok`: `runtime`, `timeout` or `crash`.

    The scorer failing never pays (reward -1.0). A target the kernel refused
    or the checker rejected is `runtime`; a status a target cannot end with
    is a `crash`. The message is the target's, with the checker's
    violations after it.
    """
    message = (
        "\n".join((target.message, *target.violations)) if target.violations else target.message
    )
    match target.status:
        case Status.TIMEOUT | Status.CRASH | Status.RUNTIME:
            return _failed(target.status, message)
        case Status.ARRIS_REFUSAL | Status.CHECKER_FAIL:
            return _failed(Status.RUNTIME, message)
        case Status.SYNTAX | Status.UNSUPPORTED_API:
            return _failed(Status.CRASH, f"a target ended {target.status.value}: {message}")
        case Status.OK:
            raise AssertionError("an ok target is not a failure")
        case _ as unreachable:
            assert_never(unreachable)


def _row(entry: RescoreEntry, result: ExecResult, target: TargetResult, sb: Sandbox) -> RescoreRow:
    """The row of one entry from its program's result and its target."""
    if result.status is not Status.OK:
        stage, pair = Stage.PROGRAM, _failed(result.status, result.message)
    elif target.body is None or target.status is not Status.OK:
        stage, pair = Stage.TARGET, _target_failure(target)
    else:
        pair = score(result, target.body, sandbox=sb)
        stage = Stage.NONE if pair.status is Status.OK else Stage.SCORING
    return RescoreRow(
        name=entry.name,
        source=entry.source,
        licence=entry.licence,
        program_sha256=result.program_sha256,
        dialect=entry.dialect,
        stage=stage,
        program_status=result.status,
        program_refusal=result.refusal,
        candidate_sha256=None if result.body is None else result.body.sha256,
        target_sha256=None if target.body is None else target.body.sha256,
        step_sha256=target.step_sha256,
        score=pair,
        versions=result.versions,
    )


def rescore(
    entries: Sequence[RescoreEntry],
    *,
    sandbox: Sandbox | None = None,
    workers: int | None = None,
) -> RescoreTable:
    """Re-score `entries`: run each program, read its STEP target, score the pair.

    Every entry has a row, whatever happened: a program that did not run
    ends at `Stage.PROGRAM` with its own status; a target that cannot be
    read into one valid solid ends at `Stage.TARGET` as `runtime`, `timeout`
    or `crash` (reward -1.0); a pair whose scoring failed ends at
    `Stage.SCORING`. The target of a program that failed is read too, so its
    row has the target's digests. At most `workers` entries are in flight
    (the core count, capped, by default); `sandbox` is the process's own
    fresh one when None. The table does not depend on `workers` or on the
    order of `entries`. Raises `ValueError` for no entries, a name given
    twice or a non-positive `workers`, and `SandboxUnavailable` where this
    machine cannot isolate a worker; never for what a program or STEP holds.

    >>> import arris.build as b
    >>> box = b.Solid.box((0.0, 0.0, 0.0), (1.0, 2.0, 3.0))
    >>> step = box.model.write_step([box.body])
    >>> text = "import arris.build as b\\nresult = b.Solid.box((0, 0, 0), (1, 2, 3))"
    >>> from arris_gym.sandbox import Dialect
    >>> entry = RescoreEntry(name="box", source="doc", licence="none", program=text,
    ...     dialect=Dialect.ARRIS, step=step)
    >>> table = rescore([entry])
    >>> table.mean_reward, table.stages["none"]
    (1.0, 1)
    """
    live = _check_workers(workers)
    names = [entry.name for entry in entries]
    if len(set(names)) != len(names):
        raise ValueError("an entry name is given twice")
    if sandbox is None:
        with Sandbox() as own:
            return rescore(entries, sandbox=own, workers=live)

    def one(entry: RescoreEntry) -> RescoreRow:
        result = sandbox.run(entry.program, dialect=entry.dialect)
        target = read_target(entry.step, sandbox=sandbox)
        return _row(entry, result, target, sandbox)

    with ThreadPoolExecutor(max_workers=min(live, max(1, len(entries)))) as pool:
        rows = list(pool.map(one, entries))
    return RescoreTable.of(rows)

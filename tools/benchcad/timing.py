"""Measure a frozen Vision2Code bundle with four workers and a 60 s score deadline."""

from __future__ import annotations

import argparse
import json
import platform
import sys
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from time import perf_counter

from pydantic import JsonValue

from arris_gym import Sandbox, Status, score
from arris_gym.sandbox._run import DEFAULT_MEMORY, DEFAULT_TIMEOUT

if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchcad._bundle import _Input, _load

_WORKERS = 4  # ADR-0031
_SCORE_DEADLINE = 60.0  # ADR-0031


def _timed[T](call: Callable[[], T]) -> tuple[T, float]:
    start = perf_counter()
    result = call()
    return result, perf_counter() - start


def _contended(data: _Input, sandbox: Sandbox, pool: ThreadPoolExecutor) -> list[JsonValue]:
    program = sandbox.run(data._program(), dialect="cq")
    target = sandbox.read_target(data.target)
    body = target.body
    if program.status is not Status.OK or target.status is not Status.OK or body is None:
        raise RuntimeError(f"candidate or target changed status on repeat: {data.task.record_id}")
    start = Barrier(_WORKERS)

    def repeat(_: int) -> JsonValue:
        start.wait()
        pair, seconds = _timed(
            lambda: score(program, body, sandbox=sandbox, timeout=_SCORE_DEADLINE)
        )
        return {
            "status": pair.status.value,
            "seconds": seconds,
            "digest": pair.digest(),
        }

    return list(pool.map(repeat, range(_WORKERS)))


def _measure(bundle: Path) -> dict[str, JsonValue]:
    _, inputs = _load(bundle)
    with Sandbox() as sandbox, ThreadPoolExecutor(max_workers=_WORKERS) as pool:

        def run(row: _Input) -> dict[str, JsonValue]:
            program, program_seconds = _timed(lambda: sandbox.run(row._program(), dialect="cq"))
            target, target_seconds = _timed(lambda: sandbox.read_target(row.target))
            body = target.body
            evidence: dict[str, JsonValue] = {
                "record_id": row.task.record_id,
                "program_status": program.status.value,
                "program_seconds": program_seconds,
                "target_status": target.status.value,
                "target_seconds": target_seconds,
                "score_status": None,
                "scoring_seconds": None,
                "score_digest": None,
                "four_concurrent_scores": [],
            }
            if program.status is Status.OK and target.status is Status.OK and body is not None:
                pair, seconds = _timed(
                    lambda: score(program, body, sandbox=sandbox, timeout=_SCORE_DEADLINE)
                )
                evidence.update(
                    score_status=pair.status.value,
                    scoring_seconds=seconds,
                    score_digest=pair.digest(),
                )
            return evidence

        rows = list(pool.map(run, inputs.values()))
        for row, data in zip(rows, inputs.values(), strict=True):
            if row["score_status"] == Status.OK.value:
                row["four_concurrent_scores"] = _contended(data, sandbox, pool)

    return {
        "architecture": platform.machine(),
        "workers": _WORKERS,
        "program_timeout_seconds": DEFAULT_TIMEOUT,
        "target_timeout_seconds": DEFAULT_TIMEOUT,
        "score_timeout_seconds": _SCORE_DEADLINE,
        "worker_memory_bytes": DEFAULT_MEMORY,
        "rows": list(rows),
    }


def _main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    args = parser.parse_args()
    print(json.dumps(_measure(args.bundle), indent=2))


if __name__ == "__main__":
    _main()

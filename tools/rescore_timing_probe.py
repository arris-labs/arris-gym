"""Time the C1 lobed-knob score under concurrent load, outside the offline gate."""

from __future__ import annotations

import argparse
import json
import math
import os
import platform
from concurrent.futures import ThreadPoolExecutor
from itertools import repeat
from pathlib import Path
from threading import Barrier
from time import perf_counter

from arris_gym.census import benchcad as corpus
from arris_gym.rescore import RescoreTable, benchcad
from arris_gym.reward import score
from arris_gym.sandbox import Sandbox, Status

_STEM = "lobed_knob_006797_s20260505"
_TABLE = benchcad.TARGETS.with_name("rescore.json")


def _probe(workers: int, deadline: float, rounds: int) -> bool:
    expected = next(
        row
        for row in RescoreTable.from_json(_TABLE.read_text(encoding="utf-8")).rows
        if row.name == _STEM
    )
    expected_inputs = {
        "program_sha256": expected.program_sha256,
        "candidate_sha256": expected.candidate_sha256,
        "target_sha256": expected.target_sha256,
        "step_sha256": expected.step_sha256,
    }
    expected_digest = expected.score.digest()
    quota = Path("/sys/fs/cgroup/cpu.max")
    report: dict[str, object] = {
        "stem": _STEM,
        "corpus": corpus.INFO.model_dump(mode="json"),
        "architecture": platform.machine(),
        "cpu_affinity": sorted(os.sched_getaffinity(0)),
        "cpu_max": quota.read_text().strip() if quota.is_file() else None,
        "deadline_seconds": deadline,
        "rounds": rounds,
        "expected_inputs": expected_inputs,
        "expected_score_digest": expected_digest,
    }
    measurements: list[dict[str, object]] = []
    [entry] = benchcad.entries([_STEM], benchcad.read_targets(benchcad.TARGETS), corpus.read())
    with Sandbox() as sandbox:
        result = sandbox.run(entry.program, dialect=entry.dialect)
        target = sandbox.read_target(entry.step)
        target_body = target.body
        actual_inputs = {
            "program_sha256": result.program_sha256,
            "candidate_sha256": None if result.body is None else result.body.sha256,
            "target_sha256": None if target_body is None else target_body.sha256,
            "step_sha256": target.step_sha256,
        }
        report.update(
            actual_inputs=actual_inputs,
            program_status=result.status.value,
            program_message=result.message,
            target_status=target.status.value,
            target_message=target.message,
            measurements=measurements,
        )
        if (
            result.status is not Status.OK
            or target.status is not Status.OK
            or target_body is None
            or actual_inputs != expected_inputs
        ):
            print(json.dumps(report, indent=2))
            return False

        def one(start: Barrier) -> dict[str, object]:
            start.wait()
            before = perf_counter()
            pair = score(result, target_body, sandbox=sandbox, timeout=deadline)
            elapsed = perf_counter() - before
            return {
                "elapsed_seconds": elapsed,
                "status": pair.status.value,
                "message": pair.message,
                "score_digest": pair.digest(),
                "iou": pair.iou,
                "iou_route": None if pair.iou_route is None else pair.iou_route.value,
                "reward": pair.reward,
            }

        for live in dict.fromkeys((1, workers)):
            start = Barrier(live)
            with ThreadPoolExecutor(max_workers=live) as pool:
                for round_number in range(1, rounds + 1):
                    for sample in pool.map(one, repeat(start, live)):
                        measurements.append({"workers": live, "round": round_number, **sample})

    print(json.dumps(report, indent=2))
    return all(sample["score_digest"] == expected_digest for sample in measurements)


def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=4, help="parallel score calls per round")
    parser.add_argument("--deadline", type=float, default=60, help="score deadline in seconds")
    parser.add_argument("--rounds", type=int, default=3, help="rounds at each worker count")
    args = parser.parse_args()
    if args.workers < 1 or args.rounds < 1:
        parser.error("workers and rounds must be positive")
    if not math.isfinite(args.deadline) or args.deadline <= 0:
        parser.error("deadline must be finite and positive")
    return 0 if _probe(args.workers, args.deadline, args.rounds) else 1


if __name__ == "__main__":
    raise SystemExit(_main())

"""The digest of every reward fixture's score is the same across runs, hash seeds and workers.

docs/plans/m4-reward.md step 9; `.agents/rules/gym.md` ("the digest decides").
M4 proves repeat runs on one machine; the two-machine digest is M5's.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
MAIN = HERE / "score_digest_main.py"
# (PYTHONHASHSEED, workers): a run, its repeat, another hash seed, and 8 workers
# against 1 under that other seed.
RUNS = [("0", 1), ("0", 1), ("4242", 1), ("4242", 8)]


def _run(hash_seed: str, workers: int) -> list[str]:
    env = {**os.environ, "PYTHONHASHSEED": hash_seed, "PYTHONPATH": str(HERE)}
    done = subprocess.run(
        [sys.executable, str(MAIN), str(workers)],
        capture_output=True,
        text=True,
        check=False,
        env=env,
        timeout=600,
    )
    assert done.returncode == 0, done.stderr
    return done.stdout.splitlines()


@pytest.fixture(scope="module")
def outputs() -> list[list[str]]:
    return [_run(seed, workers) for seed, workers in RUNS]


def test_every_fixture_pair_is_scored_and_listed(outputs: list[list[str]]) -> None:
    *lines, total = outputs[0]
    assert len(lines) == 6 + 10
    assert [line.split(" ")[0] for line in lines] == sorted(line.split(" ")[0] for line in lines)
    assert len(total) == 64


def test_the_digest_is_equal_across_repeats_hash_seeds_and_worker_counts(
    outputs: list[list[str]],
) -> None:
    first = outputs[0]
    for run, (seed, workers) in zip(outputs[1:], RUNS[1:], strict=True):
        assert run == first, f"PYTHONHASHSEED={seed}, {workers} workers"

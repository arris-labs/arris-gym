"""The slice's committed targets (M5 step 3): one oracle STEP per slice stem.

`tests/fixtures/c1/targets.jsonl.gz` is written by `tools/oracle_run.py --slice
... --targets` (network and the `[corpus]` extra, outside the gate); this test
reads the committed files only.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

from arris_gym.sandbox._target import step_sha256

C1 = Path(__file__).parent / "fixtures" / "c1"


def targets() -> list[dict[str, str]]:
    text = gzip.decompress((C1 / "targets.jsonl.gz").read_bytes()).decode("utf-8")
    return [json.loads(line) for line in text.splitlines()]


def test_one_target_per_slice_stem_sorted_by_stem() -> None:
    stems = [
        line
        for line in (C1 / "slice.txt").read_text("utf-8").splitlines()
        if line and not line.startswith("#")
    ]
    got = [row["stem"] for row in targets()]
    assert len(got) == 300
    assert got == sorted(stems)


def test_each_hash_is_the_oracle_rows_and_the_texts() -> None:
    oracle = [json.loads(line) for line in (C1 / "oracle.jsonl").read_text("utf-8").splitlines()]
    rows = targets()
    assert len(rows) == len(oracle)
    for row, ref in zip(rows, oracle, strict=True):
        assert set(row) == {"stem", "step_sha256", "step"}
        assert row["stem"] == ref["stem"]
        assert row["step_sha256"] == ref["report"]["step_sha256"]
        assert step_sha256(row["step"]) == row["step_sha256"]


def test_the_gzip_header_carries_no_time() -> None:
    data = (C1 / "targets.jsonl.gz").read_bytes()
    assert data[4:8] == b"\x00\x00\x00\x00"

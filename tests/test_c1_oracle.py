"""The slice's committed oracle rows (step 7): one per slice stem, each a valid report.

`tests/fixtures/c1/oracle.jsonl` is written by `tools/oracle_run.py --slice`
(network and the `[corpus]` extra, outside the gate); this test reads the
committed file only.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from arris_gym.census import benchcad
from arris_gym.fidelity import OracleReport, OracleStatus

C1 = Path(__file__).parent / "fixtures" / "c1"


def rows() -> list[dict[str, object]]:
    return [json.loads(line) for line in (C1 / "oracle.jsonl").read_text("utf-8").splitlines()]


def test_one_row_per_slice_stem_sorted_by_stem() -> None:
    stems = [
        line
        for line in (C1 / "slice.txt").read_text("utf-8").splitlines()
        if line and not line.startswith("#")
    ]
    got = [row["stem"] for row in rows()]
    assert len(got) == 300
    assert got == sorted(stems)


def test_every_row_carries_its_licence_revision_and_a_valid_report() -> None:
    for row in rows():
        assert set(row) == {"stem", "family", "licence", "revision", "report"}
        assert row["licence"] == benchcad.LICENCE
        assert row["revision"] == benchcad.REVISION
        report = OracleReport.model_validate(row["report"])
        assert isinstance(row["stem"], str)
        assert row["stem"].startswith(str(row["family"]))
        assert report.seconds == 0.0  # wall-clock time is not committed


def test_the_readme_states_the_counts_and_digest_of_the_file() -> None:
    text = (C1 / "oracle.jsonl").read_text("utf-8")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    readme = (C1 / "README.md").read_text("utf-8")
    assert digest in readme
    counts: dict[str, int] = {}
    for row in rows():
        status = OracleReport.model_validate(row["report"]).status
        counts[status.value] = counts.get(status.value, 0) + 1
    assert sum(counts.values()) == 300
    # Every non-ok program (a timeout, a crash, a failure) is named in the README.
    for row in rows():
        if OracleReport.model_validate(row["report"]).status is not OracleStatus.OK:
            assert str(row["stem"]) in readme
    for name, count in sorted(counts.items()):
        assert f"{name}: {count}" in readme

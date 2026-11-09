"""`tools/rescore_diff.py` names the rows that differ and the first stage each differs at.

Differences are planted by hand in a copy of the committed table's rows, so
each expected stage is by construction.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

import rescore_diff

C1 = Path(__file__).parent / "fixtures" / "c1"
TABLE: dict[str, Any] = json.loads((C1 / "rescore.json").read_text(encoding="utf-8"))
GOOD = next(r["name"] for r in TABLE["rows"] if r["stage"] == "none")
REFUSED = next(r["name"] for r in TABLE["rows"] if r["stage"] == "program")


def planted(name: str, edit: Any) -> dict[str, Any]:
    other = copy.deepcopy(TABLE)
    row = next(r for r in other["rows"] if r["name"] == name)
    edit(row)
    return other


def test_equal_tables_have_no_difference() -> None:
    assert rescore_diff.diff(TABLE, copy.deepcopy(TABLE)) == []


@pytest.mark.parametrize(
    ("stage", "edit"),
    [
        ("program", lambda r: r.update(program_sha256="0" * 64)),
        ("candidate body", lambda r: r.update(candidate_sha256="1" * 64)),
        ("target STEP", lambda r: r.update(step_sha256="2" * 64)),
        ("target body", lambda r: r.update(target_sha256="3" * 64)),
        ("iou route", lambda r: r["score"].update(iou_route="none")),
        ("iou", lambda r: r["score"].update(iou=r["score"]["iou"] - 1e-12)),
        ("surface", lambda r: r["score"].update(surface=r["score"]["surface"] - 1e-12)),
        ("measures", lambda r: r["score"].update(measures=r["score"]["measures"] - 1e-12)),
        ("topology", lambda r: r["score"].update(topology=r["score"]["topology"] - 1e-12)),
        ("reward", lambda r: r["score"].update(reward=r["score"]["reward"] - 1e-12)),
        ("versions", lambda r: r["versions"].update(numpy="0.0.0")),
    ],
)  # fmt: skip
def test_each_stage_is_named_where_it_first_differs(stage: str, edit: Any) -> None:
    lines = rescore_diff.diff(TABLE, planted(GOOD, edit))
    assert lines[0] == f"{GOOD}: first differs at {stage}"
    assert [line for line in lines if ": first differs" in line] == lines[:1]


def test_the_first_stage_wins_when_several_differ() -> None:
    def edit(row: dict[str, Any]) -> None:
        row["candidate_sha256"] = "1" * 64
        row["score"]["iou"] = 0.0
        row["score"]["reward"] = 0.5

    assert rescore_diff.diff(TABLE, planted(GOOD, edit))[0].endswith("candidate body")


def test_a_failed_row_differs_in_its_program_status() -> None:
    other = planted(REFUSED, lambda r: r.update(program_status="runtime"))
    assert rescore_diff.diff(TABLE, other)[0] == f"{REFUSED}: first differs at program"


def test_a_row_in_one_table_only_and_a_moved_aggregate_are_named() -> None:
    other = copy.deepcopy(TABLE)
    other["rows"] = [r for r in other["rows"] if r["name"] != GOOD]
    other["mean_reward"] += 1.0
    lines = rescore_diff.diff(TABLE, other)
    assert f"{GOOD}: only in A" in lines
    assert "aggregate mean_reward differs" in lines
    assert f"{GOOD}: only in B" in rescore_diff.diff(other, TABLE)


def test_main_exits_0_on_equal_files_and_1_on_a_difference(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    a.write_text(json.dumps(TABLE), encoding="utf-8")
    b.write_text(json.dumps(TABLE), encoding="utf-8")
    assert rescore_diff.main([str(a), str(b)]) == 0
    assert capsys.readouterr().out.strip() == "equal"
    b.write_text(json.dumps(planted(GOOD, lambda r: r["score"].update(reward=0.5))), "utf-8")
    assert rescore_diff.main([str(a), str(b)]) == 1
    out = capsys.readouterr().out
    assert f"{GOOD}: first differs at reward" in out
    assert "differences" in out


def test_main_exits_2_on_a_file_it_cannot_read(tmp_path: Path) -> None:
    a = tmp_path / "a.json"
    a.write_text("not json", encoding="utf-8")
    assert rescore_diff.main([str(a), str(tmp_path / "missing.json")]) == 2

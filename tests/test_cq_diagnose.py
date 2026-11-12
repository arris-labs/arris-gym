"""Diagnosis keeps every selected failure and its message; the 717 are archived offline."""

from __future__ import annotations

import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

import cq_diagnose
from arris_gym.census import CorpusProgram
from arris_gym.fidelity import DisagreementClass, FidelityOutcome, FidelityTable, fidelity_table

C2 = Path(__file__).parent / "fixtures" / "c2" / "benchcad"


def sample() -> tuple[FidelityTable, list[CorpusProgram]]:
    """One admitted bug, one bug outside by end form, and one admitted agreement."""
    baseline = FidelityTable.from_json(
        gzip.decompress((C2 / "fidelity.json.gz").read_bytes()).decode("utf-8")
    )
    bug = next(e for e in baseline.entries if e.row.disagreement is DisagreementClass.CQ_BUG)
    agree = next(e for e in baseline.entries if e.row.outcome is FidelityOutcome.AGREE)
    programs = [
        CorpusProgram(
            stem="bug",
            family="f",
            text="import cadquery as cq\nresult = cq.Workplane('XY').box(-1, 2, 3)",
        ),
        CorpusProgram(stem="out", family="f", text="pass"),
        CorpusProgram(stem="agree", family="g", text="result = 1"),
    ]
    entries = [
        entry.model_copy(
            update={
                "name": p.stem,
                "row": entry.row.model_copy(
                    update={"program_sha256": hashlib.sha256(p.text.encode()).hexdigest()}
                ),
            }
        )
        for p, entry in zip(programs, (bug, bug, agree), strict=True)
    ]
    return fidelity_table(entries), programs


def test_diagnosis_selects_statically_and_keeps_a_changed_status_and_message() -> None:
    table, programs = sample()
    got = cq_diagnose.diagnose(table, programs)
    assert got["corpus_programs"] == 3
    assert got["in_subset"] == 2
    assert got["diagnosed"] == 1
    assert got["rows"][0]["stem"] == "bug"
    assert got["rows"][0]["status"] == "runtime"
    message = (
        "ValueError: Workplane.box(-1, 2, 3): a negative dimension "
        "(CadQuery's Standard_DomainError)"
    )
    assert got["rows"][0]["message"] == message
    assert got["rows"][0]["licence"] == "CC-BY-4.0"
    assert got["histogram"] == [{"message": message, "programs": 1, "families": {"f": 1}}]
    assert cq_diagnose.diagnose(table, list(reversed(programs))) == got


def test_diagnosis_refuses_wrong_or_duplicated_programs() -> None:
    table, programs = sample()
    with pytest.raises(ValueError, match="exactly the same stems"):
        cq_diagnose.diagnose(table, programs[:-1])
    with pytest.raises(ValueError, match="duplicate"):
        cq_diagnose.diagnose(table, [*programs, programs[0]])
    wrong = [*programs[:-1], CorpusProgram(stem="agree", family="g", text="result = 2")]
    with pytest.raises(ValueError, match="program text differs"):
        cq_diagnose.diagnose(table, wrong)


def test_archived_diagnosis_accounts_for_all_717_with_attribution() -> None:
    report: dict[str, Any] = json.loads((C2 / "cq-bugs.json").read_text())
    rows = report["rows"]
    assert report["corpus_programs"] == 17_900
    assert report["in_subset"] == 1_871
    assert report["diagnosed"] == len(rows) == 717
    stems = [row["stem"] for row in rows]
    assert stems == sorted(set(stems))
    initial = json.loads((C2 / "reach.json").read_text())["initial"]
    assert set(stems) <= set(initial["stems"])
    census = {
        record["census"]["stem"]: record
        for line in gzip.decompress((C2 / "programs.jsonl.gz").read_bytes()).splitlines()
        if (record := json.loads(line))
    }
    for row in rows:
        assert row["status"] == "unsupported_api"
        assert row["message"]
        assert row["licence"] == "CC-BY-4.0"
        assert row["source"].endswith("5919f578ab09ec283603a082fab07c7639ab56eb/code_gen")
        assert row["program_sha256"] == census[row["stem"]]["program_sha256"]
    counts = Counter(row["message"] for row in rows)
    assert counts == {
        "cq.Workplane('YZ')": 319,
        "cq.Workplane('XZ')": 285,
        "Workplane.circle on a non-empty stack": 113,
    }
    assert sum(cause["programs"] for cause in report["histogram"]) == 717
    for cause in report["histogram"]:
        assert cause["programs"] == counts[cause["message"]]
        assert cause["families"] == dict(
            Counter(row["family"] for row in rows if row["message"] == cause["message"])
        )

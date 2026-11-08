"""The committed slice is the one the committed census chooses (ADR-0003, delta 2)."""

from __future__ import annotations

import json
import re
from pathlib import Path

from arris_gym.census import CensusReport
from arris_gym.fidelity import FidelityTable, OracleReport, RegressionFixture, Verdict, arris_rows

C1 = Path(__file__).parent / "fixtures" / "c1"
FAMILIES = 3
PER_FAMILY = 100
MIN_PROGRAMS = 100
STEM = re.compile(r"(.+)_\d+_[^_]+")


def family_of(stem: str) -> str:
    match = STEM.fullmatch(stem)
    assert match, stem
    return match.group(1)


def test_slice_matches_census() -> None:
    report = CensusReport.from_json((C1 / "census.json").read_text(encoding="utf-8"))
    lines = (C1 / "slice.txt").read_text(encoding="utf-8").splitlines()
    header = [line for line in lines if line.startswith("#")]
    stems = [line for line in lines if not line.startswith("#")]
    assert len(stems) == len(set(stems)) == FAMILIES * PER_FAMILY
    assert f"# census digest: {report.digest}" in header

    eligible = [f.family for f in report.families if f.programs >= MIN_PROGRAMS][:FAMILIES]
    assert f"# families: {', '.join(eligible)}" in header
    by_name = {f.family: f for f in report.families}
    for index, family in enumerate(eligible):
        block = stems[index * PER_FAMILY : (index + 1) * PER_FAMILY]
        assert block == sorted(block)
        # A stem is `<family>_<number>_<suffix>`; the family is all before the number.
        assert {family_of(stem) for stem in block} == {family}
        assert by_name[family].programs >= len(block) == PER_FAMILY


def test_the_committed_table_counts_every_slice_program_once() -> None:
    table = FidelityTable.from_json((C1 / "fidelity.json").read_text(encoding="utf-8"))
    stems = [s for s in (C1 / "slice.txt").read_text(encoding="utf-8").splitlines() if s[:1] != "#"]
    assert table.programs == len(table.entries) == FAMILIES * PER_FAMILY
    assert [entry.name for entry in table.entries] == sorted(stems)
    # Every denominator is all 300: failures and refusals are counted, not dropped.
    for counts in (table.outcomes, table.statuses, table.oracle_statuses):
        assert sum(counts.values()) == table.programs
    assert sum(table.classes.values()) == table.outcomes["disagree"]
    assert {e.licence for e in table.entries} == {"CC-BY-4.0"}


def test_the_committed_table_pairs_each_row_with_its_oracle_report() -> None:
    table = FidelityTable.from_json((C1 / "fidelity.json").read_text(encoding="utf-8"))
    lines = (C1 / "oracle.jsonl").read_text(encoding="utf-8").splitlines()
    oracle = {row["stem"]: row["report"] for row in map(json.loads, lines)}
    for entry in table.entries:
        report = OracleReport.model_validate(oracle[entry.name])
        assert entry.row.program_sha256 == report.program_sha256
        assert entry.row.oracle_status is report.status


def test_the_committed_report_is_the_tables() -> None:
    table = FidelityTable.from_json((C1 / "fidelity.json").read_text(encoding="utf-8"))
    report = arris_rows(table)
    assert (C1 / "arris-report.json").read_text(encoding="utf-8") == report.to_json() + "\n"
    assert (C1 / "arris-report.md").read_text(encoding="utf-8") == report.to_markdown()
    assert report.programs == table.programs
    assert sum(k.count for k in report.refusals) == table.classes["arris_refusal"]


def test_each_verdict_names_a_slice_row_and_its_regression_fixture() -> None:
    table = FidelityTable.from_json((C1 / "fidelity.json").read_text(encoding="utf-8"))
    raw = json.loads((C1 / "verdicts.json").read_text(encoding="utf-8"))
    rows = {entry.name: entry.row for entry in table.entries}
    root = C1.parent.parent.parent
    for stem, value in raw.items():
        verdict = Verdict.model_validate(value)
        # The table applied it: the row carries the verdict and is its class.
        assert rows[stem].verdict == verdict
        if isinstance(verdict.evidence, RegressionFixture):
            assert (root / verdict.evidence.path / "program.py").is_file(), verdict.evidence.path
    assert table.outcomes["unclassified"] == 0

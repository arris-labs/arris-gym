"""The fidelity table and the arris report (step 6): counts over all rows, a digest
that input order does not move, and a report whose content is expected exactly.

The rows are the calibration pairs (`agree-*`, with their recorded oracle
report) and the planted `class-*` fixtures; `table-expected.json`,
`arris-report-expected.*` are worked out from the fixtures' README, not from
arris-gym's output.
"""

from __future__ import annotations

import json
import pathlib
import random
from typing import Any

import pytest

import arris_gym
from arris_gym.fidelity import (
    ArrisReport,
    FidelityTable,
    OracleReport,
    TableEntry,
    Verdict,
    arris_rows,
    compare,
    fidelity_table,
)

ROOT = pathlib.Path(__file__).resolve().parent / "fixtures" / "fidelity"
# The fixtures are this repository's own (the fixtures' README).
SOURCE = "arris-gym tests/fixtures/fidelity"
LICENCE = "MIT OR Apache-2.0"


def entries() -> list[TableEntry]:
    rows: list[TableEntry] = []
    for d in sorted([*ROOT.glob("agree-*"), *ROOT.glob("class-*")]):
        report = OracleReport.model_validate_json((d / "oracle.json").read_text())
        verdict_file = d / "verdict.json"
        verdict = (
            Verdict.model_validate_json(verdict_file.read_text())
            if verdict_file.is_file()
            else None
        )
        result = arris_gym.run((d / "program.py").read_text())
        row = compare(result, report, verdict)
        rows.append(TableEntry(name=d.name, source=SOURCE, licence=LICENCE, row=row))
    return rows


@pytest.fixture(scope="module")
def rows() -> list[TableEntry]:
    return entries()


def expected(name: str) -> Any:
    return json.loads((ROOT / name).read_text())


def test_the_counts_are_over_all_rows(rows: list[TableEntry]) -> None:
    table = fidelity_table(rows)
    want = expected("table-expected.json")
    assert table.programs == len(rows) == want["programs"]
    assert table.outcomes == want["outcomes"]
    assert table.classes == want["classes"]
    assert table.statuses == want["statuses"]
    assert table.oracle_statuses == want["oracle_statuses"]
    assert list(table.timed_out) == want["timed_out"]
    # Every count adds up to the denominator: nothing is dropped.
    assert sum(table.outcomes.values()) == table.programs
    assert sum(table.statuses.values()) == table.programs
    assert sum(table.oracle_statuses.values()) == table.programs
    assert sum(table.classes.values()) == table.outcomes["disagree"]


def test_the_digest_does_not_move_with_input_order(rows: list[TableEntry]) -> None:
    table = fidelity_table(rows)
    shuffled = list(rows)
    random.Random(7).shuffle(shuffled)
    other = fidelity_table(shuffled)
    assert other == table
    assert other.digest == table.digest
    assert [e.name for e in table.entries] == sorted(e.name for e in rows)
    # ...and moves with a row's content.
    changed = [*rows[:-1], rows[-1].model_copy(update={"row": rows[0].row})]
    assert fidelity_table(changed).digest != table.digest


def test_a_table_round_trips_and_refuses_a_forged_one(rows: list[TableEntry]) -> None:
    table = fidelity_table(rows)
    assert FidelityTable.from_json(table.to_json()) == table
    forged = json.loads(table.to_json())
    forged["outcomes"]["agree"] += 1
    with pytest.raises(ValueError, match="outcomes"):
        FidelityTable.model_validate(forged)
    forged = json.loads(table.to_json())
    forged["entries"].reverse()
    with pytest.raises(ValueError, match="sorted"):
        FidelityTable.model_validate(forged)
    forged = json.loads(table.to_json())
    forged["digest"] = "0" * 64
    with pytest.raises(ValueError, match="digest"):
        FidelityTable.model_validate(forged)


def test_a_name_given_twice_is_refused(rows: list[TableEntry]) -> None:
    with pytest.raises(ValueError, match="twice"):
        fidelity_table([rows[0], rows[0]])


def test_the_arris_report_is_exactly_the_expected_one(rows: list[TableEntry]) -> None:
    report = arris_rows(fidelity_table(rows))
    assert json.loads(report.to_json()) == expected("arris-report-expected.json")
    assert report.to_markdown() == (ROOT / "arris-report-expected.md").read_text()


def test_an_empty_report_says_none() -> None:
    markdown = arris_rows(fidelity_table([])).to_markdown()
    assert markdown.count("None.") == 2


def test_the_report_states_every_rows_licence_and_versions_sorted(
    rows: list[TableEntry],
) -> None:
    # A second licence and a second arris version, on rows given out of order.
    other = rows[0].row.model_copy(
        update={"versions": rows[0].row.versions.model_copy(update={"arris": "0.0.1"})}
    )
    extra = TableEntry(name="a-first", source="elsewhere", licence="CC-BY-4.0", row=other)
    report = arris_rows(fidelity_table([*rows, extra]))
    assert report.licences == ("CC-BY-4.0", LICENCE)
    assert report.arris_versions[0] == "0.0.1"
    assert len(report.arris_versions) == 2
    fields = json.loads(report.to_json())
    fields["licences"].reverse()
    with pytest.raises(ValueError, match="licences"):
        ArrisReport.model_validate(fields)
    with pytest.raises(ValueError, match="source"):
        TableEntry(name="x", source="", licence=LICENCE, row=other)

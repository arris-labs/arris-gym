"""The C2 baseline (plans/fidelity-target step 6), re-read offline.

`tools/cq_corpus.py` wrote `tests/fixtures/c2/<corpus>/` (network, the oracle
environment, outside the gate). This reads the committed rows only: the table
validates its own digest and counts, has one row per census row of the corpus,
carries the corpus's licence, and the committed reach report is the one the
table and the census rows give under the C1 subset. The README states each
digest, so a changed row is a changed README.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest

from arris_gym.census import ProgramCensus, Unparsable
from arris_gym.cq import subset
from arris_gym.fidelity import FidelityTable, OracleReport, ReachReport, reach_report

C2 = Path(__file__).parent / "fixtures" / "c2"
CORPORA = {"benchcad": ("CC-BY-4.0", 17_900), "cadrecode": ("CC-BY-NC-4.0", 968)}


def census_rows(corpus: str) -> list[ProgramCensus | Unparsable]:
    data = gzip.decompress((C2 / corpus / "programs.jsonl.gz").read_bytes())
    rows: list[ProgramCensus | Unparsable] = []
    for line in data.splitlines():
        record = json.loads(line)
        try:
            rows.append(ProgramCensus.model_validate(record["census"]))
        except ValueError:
            rows.append(Unparsable.model_validate(record["census"]))
    return rows


@pytest.mark.parametrize("corpus", sorted(CORPORA))
def test_the_baseline_table_has_a_row_per_program_and_its_digest_is_stated(corpus: str) -> None:
    licence, count = CORPORA[corpus]
    table = FidelityTable.from_json(
        gzip.decompress((C2 / corpus / "fidelity.json.gz").read_bytes()).decode("utf-8")
    )
    assert table.programs == count == len(table.entries)
    assert all(entry.licence == licence for entry in table.entries)
    assert sum(table.outcomes.values()) == count
    assert sum(table.statuses.values()) == count
    assert table.digest in (C2 / corpus / "README.md").read_text("utf-8")


@pytest.mark.parametrize("corpus", sorted(CORPORA))
def test_the_committed_reach_report_is_the_tables_and_the_censuss(corpus: str) -> None:
    table = FidelityTable.from_json(
        gzip.decompress((C2 / corpus / "fidelity.json.gz").read_bytes()).decode("utf-8")
    )
    committed = ReachReport.model_validate_json((C2 / corpus / "reach-report.json").read_text())
    assert reach_report(table, census_rows(corpus), subset()) == committed
    assert committed.programs == CORPORA[corpus][1]


@pytest.mark.parametrize("corpus", sorted(CORPORA))
def test_the_oracle_rows_are_the_tables_programs(corpus: str) -> None:
    table = FidelityTable.from_json(
        gzip.decompress((C2 / corpus / "fidelity.json.gz").read_bytes()).decode("utf-8")
    )
    rows = [
        json.loads(line)
        for line in gzip.decompress((C2 / corpus / "oracle.jsonl.gz").read_bytes()).splitlines()
    ]
    assert [r["stem"] for r in rows] == [e.name for e in table.entries]
    for row, entry in zip(rows, table.entries, strict=True):
        report = OracleReport.model_validate(row["report"])
        assert report.program_sha256 == entry.row.program_sha256
        assert report.status is entry.row.oracle_status
        assert row["licence"] == entry.licence

"""The C2 tables (plans/fidelity-target step 6, re-run by plans/in-subset-cq-bugs step 10).

`tools/cq_corpus.py` wrote `tests/fixtures/c2/<corpus>/` (network, the oracle
environment, outside the gate). This reads the committed rows only: the table
validates its own digest and counts, has one row per census row of the corpus,
carries the corpus's licence, and the committed reach report is the one the
table and the census rows give under the `cq` subset it was run under. The
README states each digest, so a changed row is a changed README. The figures the docs publish
(reach, agreement, the two target comparisons, each over all programs) are
asserted here, so a re-run that moves one moves this file.
"""

from __future__ import annotations

import gzip
import hashlib
import json
from collections import Counter
from dataclasses import replace
from pathlib import Path

import pytest

import fixture_cases
from arris_gym import Status, cq
from arris_gym.census import ProgramCensus, Unparsable
from arris_gym.fidelity import (
    DisagreementClass,
    FidelityOutcome,
    FidelityTable,
    OracleReport,
    OracleStatus,
    ReachReport,
    reach_report,
)

C2 = Path(__file__).parent / "fixtures" / "c2"
CORPORA = {"benchcad": ("CC-BY-4.0", 17_900), "cadrecode": ("CC-BY-NC-4.0", 968)}
# The published figures of each committed table, every one over all programs.
FIGURES = {
    "benchcad": {
        "in_subset": 3_667,
        "agree": 2_543,
        "in_subset_cq_bug": 0,
        "in_subset_by_design": 0,
        "timed_out": 31,
        "classes": {
            "arris_bug": 100,
            "arris_refusal": 942,
            "by_design": 0,
            "cq_bug": 13_786,
            "occt_wrong": 325,
        },
        "unclassified": 204,
        "oracle_ok": 17_537,
    },
    "cadrecode": {
        "in_subset": 104,
        "agree": 103,
        "in_subset_cq_bug": 0,
        "in_subset_by_design": 0,
        "timed_out": 0,
        "classes": {
            "arris_bug": 0,
            "arris_refusal": 0,
            "by_design": 0,
            "cq_bug": 864,
            "occt_wrong": 1,
        },
        "unclassified": 0,
        "oracle_ok": 968,
    },
}
# Reach under the C1 subset, before C2 lifted `r = …`, `origin=`, `workplane` and `cylinder`.
C1_REACH = {"benchcad": 1_871, "cadrecode": 0}
# The SHA-256 of BenchCAD's uncompressed oracle rows at the C2 baseline
# (plans/fidelity-target step 6), pinned so the committed file stays them.
BENCHCAD_BASELINE_ORACLE_ROWS = "e992583501c771e2f52f07939a61b5b44ec5e8989f3f8204d9263b3044573157"


def tables_subset() -> cq.Subset:
    """The subset the committed tables were run under: today's less the forms lifted since.

    plans/lift-three-point-arc step 5 re-ran both tables after
    `Workplane.threePointArc` was lifted. `Workplane.sphere`
    (plans/lift-sphere step 1) is declared before its re-run lands (step 5),
    which returns this to `cq.subset()`.
    """
    lifted = ("Workplane.sphere",)
    forms = tuple(f for f in cq.subset().forms if f.name not in lifted)
    return replace(cq.subset(), forms=forms)


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


def table_of(corpus: str) -> FidelityTable:
    return FidelityTable.from_json(
        gzip.decompress((C2 / corpus / "fidelity.json.gz").read_bytes()).decode("utf-8")
    )


@pytest.mark.parametrize("corpus", sorted(CORPORA))
def test_the_baseline_table_has_a_row_per_program_and_its_digest_is_stated(corpus: str) -> None:
    licence, count = CORPORA[corpus]
    table = table_of(corpus)
    assert table.programs == count == len(table.entries)
    assert all(entry.licence == licence for entry in table.entries)
    assert sum(table.outcomes.values()) == count
    assert sum(table.statuses.values()) == count
    assert table.digest in (C2 / corpus / "README.md").read_text("utf-8")


@pytest.mark.parametrize("corpus", sorted(CORPORA))
def test_the_committed_reach_report_is_the_tables_and_the_censuss(corpus: str) -> None:
    table = table_of(corpus)
    committed = ReachReport.model_validate_json((C2 / corpus / "reach-report.json").read_text())
    assert reach_report(table, census_rows(corpus), tables_subset()) == committed
    assert committed.programs == CORPORA[corpus][1]
    c1 = reach_report(table, census_rows(corpus), fixture_cases.c1_subset())
    assert c1.in_subset == C1_REACH[corpus]


@pytest.mark.parametrize("corpus", sorted(CORPORA))
def test_the_published_figures_are_the_committed_tables(corpus: str) -> None:
    figures = FIGURES[corpus]
    table = table_of(corpus)
    report = ReachReport.model_validate_json((C2 / corpus / "reach-report.json").read_text())
    assert report.in_subset == figures["in_subset"]
    assert report.agree == figures["agree"] == table.outcomes["agree"]
    assert report.in_subset_cq_bug == figures["in_subset_cq_bug"]
    assert report.in_subset_by_design == figures["in_subset_by_design"]
    assert report.timed_out == figures["timed_out"] == len(table.timed_out)
    assert table.classes == figures["classes"]
    assert table.outcomes["unclassified"] == figures["unclassified"]
    assert report.in_subset_outcomes["unclassified"] == 0
    assert table.oracle_statuses["ok"] == figures["oracle_ok"]


def test_benchcads_arris_bugs_are_the_100_lobed_knob_verdicts() -> None:
    entries = table_of("benchcad").entries
    bugs = [e for e in entries if e.row.disagreement is DisagreementClass.ARRIS_BUG]
    assert Counter(e.name.rsplit("_", 2)[0] for e in bugs) == {"lobed_knob": 100}
    assert all(e.row.verdict is not None for e in bugs)


def test_cadrecodes_agreements_are_not_two_failures() -> None:
    table = table_of("cadrecode")
    assert table.oracle_statuses["no_result"] == 0
    agree = [e for e in table.entries if e.row.outcome is FidelityOutcome.AGREE]
    assert len(agree) == 103
    assert all(e.row.status is Status.OK and e.row.oracle_status is OracleStatus.OK for e in agree)


def test_benchcads_committed_oracle_rows_are_the_pinned_baseline_file() -> None:
    """The committed `oracle.jsonl.gz` is the C2 baseline's, by its pinned hash.

    It does not show that a re-run reproduces the baseline: the step-10 re-run
    differed in `report` on 214 rows (Open CASCADE's build order, BACKLOG
    `oracle-nondeterministic-step`) and its rows were not committed.
    """
    data = gzip.decompress((C2 / "benchcad" / "oracle.jsonl.gz").read_bytes())
    assert hashlib.sha256(data).hexdigest() == BENCHCAD_BASELINE_ORACLE_ROWS


@pytest.mark.parametrize("corpus", sorted(CORPORA))
def test_the_oracle_rows_are_the_tables_programs(corpus: str) -> None:
    table = table_of(corpus)
    data = gzip.decompress((C2 / corpus / "oracle.jsonl.gz").read_bytes())
    assert hashlib.sha256(data).hexdigest() in (C2 / corpus / "README.md").read_text("utf-8")
    rows = [json.loads(line) for line in data.splitlines()]
    assert [r["stem"] for r in rows] == [e.name for e in table.entries]
    for row, entry in zip(rows, table.entries, strict=True):
        report = OracleReport.model_validate(row["report"])
        assert report.program_sha256 == entry.row.program_sha256
        assert report.status is entry.row.oracle_status
        assert row["licence"] == entry.licence

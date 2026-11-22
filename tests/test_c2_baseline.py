"""The C2 tables (plans/fidelity-target step 6, re-run by plans/face-centre-of-mass step 7).

`tools/cq_corpus.py` wrote `tests/fixtures/c2/<corpus>/` (network, the oracle
environment, outside the gate). This reads the committed rows only: the table
validates its own digest and counts, has one row per census row of the corpus,
carries the corpus's licence, and the committed reach report is the one the
table and the census rows give under the subset used for that run. The
README states each digest, so a changed row is a changed README. The figures the docs publish
(reach, agreement, the two target comparisons, each over all programs) are
asserted here, so a re-run that moves one moves this file.
"""

from __future__ import annotations

import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path

import pytest

import fixture_cases
from arris_gym import Status, cq
from arris_gym.census import ProgramCensus, Unparsable, reach
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
        "in_subset": 14_150,
        "agree": 10_730,
        "in_subset_cq_bug": 0,
        "in_subset_by_design": 2,  # ADR-0025's corner patches
        "timed_out": 0,
        "classes": {
            "arris_bug": 391,
            "arris_refusal": 1_778,
            "by_design": 2,
            "cq_bug": 3_750,
            "occt_wrong": 1_249,
        },
        "unclassified": 0,
        "oracle_ok": 17_568,
    },
    "cadrecode": {
        "in_subset": 968,
        "agree": 873,
        "in_subset_cq_bug": 0,
        "in_subset_by_design": 0,
        "timed_out": 0,
        "classes": {
            "arris_bug": 1,
            "arris_refusal": 75,
            "by_design": 0,
            "cq_bug": 0,
            "occt_wrong": 19,
        },
        "unclassified": 0,
        "oracle_ok": 968,
    },
}
# Reach under the C1 subset, before C2 lifted `r = …`, `origin=`, `workplane` and `cylinder`.
C1_REACH = {"benchcad": 1_871, "cadrecode": 0}
# The SHA-256 of BenchCAD's uncompressed oracle rows as re-run under the 240 s
# corpus oracle deadline (plans/resolve-benchcad-unclassified step 3), pinned so
# the committed file stays them. They differ from the C2 baseline's rows
# (SHA-256 e992583501c7…3157, plans/fidelity-target step 6) in the 31
# double_simplex_sprocket rows alone, which timed out at 30 s and now ran.
BENCHCAD_ORACLE_ROWS = "db298f073af368bc5a73f6856134cd0c8bcafa4bb3a9f6a7911de668fd49136b"
SPROCKETS_ONCE_TIMED_OUT = 31


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


def reach_stems(corpus: str) -> list[str]:
    """The stems today's subset admits, sorted (`reach`'s own census reading)."""
    return sorted(reach(census_rows(corpus), cq.subset()).stems)


def table_of(corpus: str) -> FidelityTable:
    return FidelityTable.from_json(
        gzip.decompress((C2 / corpus / "fidelity.json.gz").read_bytes()).decode("utf-8")
    )


@pytest.mark.parametrize(("corpus", "expected"), [("cadrecode", 968), ("benchcad", 14_150)])
def test_current_subset_reach_over_the_committed_census(corpus: str, expected: int) -> None:
    measured = reach(census_rows(corpus), cq.subset())
    assert measured.programs == CORPORA[corpus][1]
    assert measured.in_subset == expected


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
    rows = census_rows(corpus)
    assert reach_report(table, rows, cq.subset()) == committed
    assert committed.programs == CORPORA[corpus][1]
    c1 = reach_report(table, rows, fixture_cases.c1_subset())
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


def test_benchcads_arris_bugs_are_verdict_families_and_checker_fail_caps() -> None:
    entries = table_of("benchcad").entries
    bugs = [e for e in entries if e.row.disagreement is DisagreementClass.ARRIS_BUG]
    families = {e.name.rsplit("_", 2)[0] for e in bugs}
    want = {
        "lobed_knob": 100,
        "shaft_collar": 63,
        "bearing_retainer_cap": 37,
        "clevis_pin": 126,
        "piston": 56,
        "cam": 7,
        "spacer_ring": 2,
    }
    assert Counter(e.name.rsplit("_", 2)[0] for e in bugs) == want
    assert families == set(want)
    # The other rows are ok/ok with a verdict; the 37
    # bearing_retainer_cap rows are checker_fail rows the rule classes, with none.
    for e in bugs:
        if e.name.startswith("bearing_retainer_cap"):
            assert e.row.verdict is None
            assert e.row.status is Status.CHECKER_FAIL
        else:
            assert e.row.verdict is not None


def test_benchcads_previously_refused_connecting_rods_build_on_both_kernels() -> None:
    """ADR-0022 ranks the seam-split cylinder side as one face for all six rows."""
    agreements = {"000909", "007540"}
    oracle_errors = {"002995", "007023", "015811", "016153"}
    inside = set(reach_stems("benchcad"))
    rows = {entry.name: entry.row for entry in table_of("benchcad").entries}
    for number in sorted(agreements | oracle_errors):
        stem = f"connecting_rod_{number}_s20260505"
        assert stem in inside
        row = rows[stem]
        assert row.status is Status.OK
        assert row.oracle_status is OracleStatus.OK
        if number in agreements:
            assert row.outcome is FidelityOutcome.AGREE
        else:
            assert row.disagreement is DisagreementClass.OCCT_WRONG
            assert row.verdict is not None
            assert row.verdict.evidence.kind == "closed_form"


def test_cadrecodes_agreements_are_not_two_failures() -> None:
    table = table_of("cadrecode")
    assert table.oracle_statuses["no_result"] == 0
    agree = [e for e in table.entries if e.row.outcome is FidelityOutcome.AGREE]
    assert len(agree) == 873
    assert all(e.row.status is Status.OK and e.row.oracle_status is OracleStatus.OK for e in agree)


def test_benchcads_committed_oracle_rows_are_the_pinned_file() -> None:
    """The committed `oracle.jsonl.gz` is the 240 s re-run's, by its pinned hash.

    It does not show that a re-run reproduces it: a re-run of the baseline
    differed in `report` on 214 rows (Open CASCADE's build order, BACKLOG
    `oracle-nondeterministic-step`) and its rows were not committed. The 31
    sprocket rows, which timed out at 30 s, are the only ones that differ
    from the baseline's; each now ends `ok` and none times out.
    """
    data = gzip.decompress((C2 / "benchcad" / "oracle.jsonl.gz").read_bytes())
    assert hashlib.sha256(data).hexdigest() == BENCHCAD_ORACLE_ROWS
    sprockets = [
        e
        for e in table_of("benchcad").entries
        if e.row.oracle_status is OracleStatus.OK and e.name.startswith("double_simplex_sprocket")
    ]
    # Inside the subset since the profiles lift (keyways by `rect`), none is a `cq_bug`.
    assert len(sprockets) >= SPROCKETS_ONCE_TIMED_OUT
    assert not any(e.row.timed_out for e in sprockets)
    assert all(e.row.disagreement is not DisagreementClass.CQ_BUG for e in sprockets)


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

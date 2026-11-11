"""`reach_report` (plans/fidelity-target step 5): reach, agreement and the in-subset
rows, each over all programs.

The four-program table is built from the calibration fixtures' rows; its
expected figures are worked out from which program is in the subset and how
each row classes, not from the report's output. The slice figures are those of
C1 (ADR-0011): 200 agree, 100 `arris_bug`, reach 300/300.
"""

from __future__ import annotations

import gzip
import json
import pathlib

import pytest

from arris_gym.census import CorpusProgram, ProgramCensus
from arris_gym.cq import subset
from arris_gym.fidelity import (
    FidelityTable,
    ReachReport,
    fidelity_table,
    reach_report,
)
from test_fidelity_table import entries

FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures"
SUBSET = subset()
IN = "result = 1"
OUT = "("  # does not parse: never in-subset


def four() -> tuple[FidelityTable, list[CorpusProgram]]:
    """Rows: agree-box (agree), class-cq-bug (cq_bug), class-by-design
    (by_design), class-arris-bug (arris_bug); the last has an unparsable program."""
    by_name = {e.name: e for e in entries()}
    names = ["agree-box", "class-cq-bug", "class-by-design", "class-arris-bug"]
    table = fidelity_table([by_name[n] for n in names])
    texts = [IN, IN, IN, OUT]
    programs = [
        CorpusProgram(stem=n, family="f", text=t) for n, t in zip(names, texts, strict=True)
    ]
    return table, programs


def test_four_programs_each_figure_is_over_all_of_them() -> None:
    table, programs = four()
    report = reach_report(table, programs, SUBSET)
    assert report.programs == 4
    assert report.in_subset == 3  # the unparsable program is in the denominator
    assert report.agree == 1  # over all programs, in or out of the subset
    assert report.timed_out == 0
    assert report.in_subset_outcomes == {"agree": 1, "disagree": 2, "unclassified": 0}
    assert report.in_subset_classes == {
        "cq_bug": 1,
        "arris_refusal": 0,
        "arris_bug": 0,  # the arris_bug row is the one outside the subset
        "occt_wrong": 0,
        "by_design": 1,
    }
    assert report.in_subset_cq_bug == 1
    assert report.in_subset_by_design == 1


def test_a_row_outside_the_subset_is_not_counted_among_its_rows() -> None:
    table, programs = four()
    programs[1] = CorpusProgram(stem="class-cq-bug", family="f", text=OUT)
    report = reach_report(table, programs, SUBSET)
    assert report.in_subset == 2
    assert report.in_subset_cq_bug == 0
    assert report.agree == 1


def test_precomputed_census_rows_give_the_same_report() -> None:
    from arris_gym.census import census_program

    table, programs = four()
    rows = [census_program(p) for p in programs]
    assert reach_report(table, rows, SUBSET) == reach_report(table, programs, SUBSET)


def test_every_program_must_have_a_row_and_every_row_a_program() -> None:
    table, programs = four()
    with pytest.raises(ValueError, match="without a row"):
        reach_report(table, [*programs, CorpusProgram(stem="extra", family="f", text=IN)], SUBSET)
    with pytest.raises(ValueError, match="without a program"):
        reach_report(table, programs[:-1], SUBSET)


def test_an_empty_corpus_has_zero_counts() -> None:
    report = reach_report(fidelity_table([]), [], SUBSET)
    assert (report.programs, report.in_subset, report.agree) == (0, 0, 0)


def test_a_forged_report_is_refused() -> None:
    table, programs = four()
    data = json.loads(reach_report(table, programs, SUBSET).to_json())
    forged = {**data, "in_subset_cq_bug": 0}
    with pytest.raises(ValueError, match="cq_bug"):
        ReachReport.model_validate(forged)
    forged = {**data, "in_subset": 5}
    with pytest.raises(ValueError, match="programs"):
        ReachReport.model_validate(forged)


def test_the_c1_slice_report_is_c1s_figures() -> None:
    root = FIXTURES / "c1"
    table = FidelityTable.from_json((root / "fidelity.json").read_text())
    records = [
        json.loads(line)
        for line in gzip.decompress((root / "reach-programs.jsonl.gz").read_bytes()).splitlines()
    ]
    rows = [ProgramCensus.model_validate(r["census"]) for r in records]
    report = reach_report(table, rows, SUBSET)
    assert report.programs == 300
    assert report.in_subset == 300
    assert report.agree == 200
    assert report.in_subset_classes["arris_bug"] == 100
    assert report.in_subset_cq_bug == 0
    assert report.in_subset_by_design == 0
    assert report.timed_out == 0

"""`census` ranks families and `select_slice` picks the C1 slice (ADR-0003).

The corpus is built here from families whose call and form sets are known by
construction, so every expected figure is counted from the program templates.
"""

from __future__ import annotations

import doctest

import pytest

from arris_gym.census import (
    CensusReport,
    CorpusInfo,
    CorpusProgram,
    Unparsable,
    _report,
    census,
    select_slice,
)

INFO = CorpusInfo(source="test", config="code_gen", revision="r0", licence="CC0-1.0")
HEAD = "import cadquery as cq\n"
BOX = "r = cq.Workplane('XY').box(1, 1, 1)\n"
BROKEN = "r = (\n"

# family -> (programs, text, unparsable programs among them, (calls, selectors, forms))
# alpha: cq.Workplane, Workplane.box (print is builtin: counted, not ranked).
# zeta: the same two calls. big: the same two calls, box in a second form.
# mid: adds faces and one selector string. tiny: one call, but under 100 programs.
FAMILIES = {
    "alpha": (120, HEAD + BOX + "print(r)\n", 2, (2, 0, 2)),
    "zeta": (100, HEAD + BOX, 0, (2, 0, 2)),
    "big": (101, HEAD + BOX + "w = 2\nr = r.box(w, 1, 1)\n", 0, (2, 0, 3)),
    "mid": (100, HEAD + BOX[:-1] + ".faces('>Z')\n", 0, (3, 1, 3)),
    "tiny": (5, HEAD + "r = cq.Workplane('XY')\n", 0, (1, 0, 1)),
}


def corpus() -> list[CorpusProgram]:
    out: list[CorpusProgram] = []
    for family, (count, text, broken, _) in FAMILIES.items():
        for i in range(count):
            body = BROKEN if i < broken else text
            out.append(CorpusProgram(stem=f"{family}-{i}", family=family, text=body))
    return out[::-1]  # not in stem order


def test_the_doctests_run() -> None:
    assert doctest.testmod(_report).failed == 0


def test_families_rank_by_calls_selectors_forms_then_name() -> None:
    report = census(corpus(), INFO)
    assert [f.family for f in report.families] == ["tiny", "alpha", "zeta", "big", "mid"]
    for family in report.families:
        triple = (family.distinct_calls, family.distinct_selectors, family.distinct_forms)
        assert triple == FAMILIES[family.family][3], family.family


def test_every_program_is_parsed_or_unparsable_never_both_or_neither() -> None:
    programs = corpus()
    report = census(programs, INFO)
    assert report.programs == len(programs) == 426
    assert (report.parsed, report.unparsable) == (424, 2)
    assert {u.stem for u in report.unparsable_programs} == {"alpha-0", "alpha-1"}
    assert all(isinstance(u, Unparsable) for u in report.unparsable_programs)
    assert sum(f.programs for f in report.families) == report.programs
    alpha = next(f for f in report.families if f.family == "alpha")
    assert (alpha.programs, alpha.parsed, alpha.unparsable) == (120, 118, 2)
    assert dict(alpha.foreign) == {"builtin.print": 118}
    assert dict(alpha.end_forms) == {"other": 118}


def test_a_stem_used_twice_is_refused() -> None:
    twice = [CorpusProgram(stem="s", family="f", text="x = 1")] * 2
    with pytest.raises(ValueError, match="stem"):
        census(twice, INFO)


def test_the_report_is_the_same_for_any_input_order() -> None:
    programs = corpus()
    assert census(programs, INFO) == census(programs[::-1], INFO)


def test_the_slice_is_the_first_100_stems_of_the_first_3_ranked_eligible_families() -> None:
    programs = corpus()
    report = census(programs, INFO)
    got = select_slice(report, programs)
    assert len(got) == 300 == len(set(got))
    expected: list[str] = []
    for family, count in (("alpha", 120), ("zeta", 100), ("big", 101)):
        expected += sorted(f"{family}-{i}" for i in range(count))[:100]
    assert got == tuple(expected)
    # string order, not numeric: "alpha-10" sorts before "alpha-2"
    assert got.index("alpha-10") < got.index("alpha-2")
    assert not any(stem.startswith(("tiny", "mid")) for stem in got)


def test_a_slice_with_too_few_eligible_families_is_refused() -> None:
    programs = corpus()
    report: CensusReport = census(programs, INFO)
    with pytest.raises(ValueError, match="families have"):
        select_slice(report, programs, families=5)

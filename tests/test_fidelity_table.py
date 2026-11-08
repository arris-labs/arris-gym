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
import re
from typing import Any

import pytest
from hypothesis import example, given
from hypothesis import strategies as st

import arris_gym
from arris_gym import Status
from arris_gym.fidelity import (
    ArrisBug,
    ArrisReason,
    ArrisRefusalKind,
    ArrisReport,
    FidelityTable,
    OracleReport,
    OracleStatus,
    OracleVersions,
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


# --- The Markdown holds any words a kernel or a program can write. -----------


def code_spans(line: str) -> tuple[str, list[str]]:
    """The line with each CommonMark code span replaced by `@`, and the spans'
    contents (one space stripped from each end, as CommonMark strips it)."""
    skeleton, spans, i = "", [], 0
    while i < len(line):
        if line[i] != "`":
            skeleton += line[i]
            i += 1
            continue
        n = len(line[i:]) - len(line[i:].lstrip("`"))
        fence = "`" * n
        j = i + n
        while True:
            k = line.find(fence, j)
            assert k >= 0, f"an unclosed code span in {line!r}"
            if line[k + n : k + n + 1] != "`":
                break
            j = k + n + len(line[k + n :]) - len(line[k + n :].lstrip("`"))
        content = line[i + n : k]
        if content.startswith(" ") and content.endswith(" ") and content.strip(" "):
            content = content[1:-1]
        spans.append(content)
        skeleton += "@"
        i = k + n
    return skeleton, spans


SKELETON = re.compile(
    r"|# arris report|Over \d+ programs: \d+ arris refusals, \d+ arris bugs\."
    r"|Licences: (@(, @)*|none)\."
    r"|arris (@(, @)*|none); numpy (@(, @)*|none); oracle "
    r"(cadquery @, OCP @, Python @(, cadquery @, OCP @, Python @)*|none)\."
    r"|## Refusals|## Bugs|None\.|### @ \(\d+\)|- \d+x @"
    r"|- @ \([0-9a-f]{64}\): arris \w+, oracle \w+, fixture (@|none)"
)
# Any code point, lone surrogates included (a message decoded with surrogatepass).
words = st.text(st.characters(exclude_categories=()))
distinct = st.lists(words, unique=True, max_size=3).map(lambda w: tuple(sorted(w)))


@example(
    licences=("a\n## Bugs",),
    versions=("`",),
    kinds=[("Op`Error", ("```\n- 9x `x`\r\n", " ` ", ""))],
    names=["`` \n", "\\`", "\udc80"],
)
@given(
    licences=distinct,
    versions=distinct,
    kinds=st.lists(st.tuples(words, distinct.filter(bool)), max_size=3),
    names=st.lists(words, max_size=3),
)
def test_the_markdown_keeps_every_word_intact_in_its_own_span(
    licences: tuple[str, ...],
    versions: tuple[str, ...],
    kinds: list[tuple[str, tuple[str, ...]]],
    names: list[str],
) -> None:
    oracle = tuple(
        sorted(
            {(v, v, v) for v in versions},
        )
    )
    report = ArrisReport(
        programs=len(names),
        licences=licences,
        arris_versions=versions,
        numpy_versions=versions,
        oracle_versions=tuple(OracleVersions(cadquery=a, ocp=b, python=c) for a, b, c in oracle),
        refusals=tuple(
            ArrisRefusalKind(
                kind=kind,
                count=len(reasons),
                reasons=tuple(ArrisReason(reason=r, count=1) for r in reasons),
            )
            for kind, reasons in kinds
        ),
        bugs=tuple(
            ArrisBug(
                name=name,
                program_sha256="0" * 64,
                status=Status.CRASH,
                oracle_status=OracleStatus.OK,
                fixture=None,
            )
            for name in names
        ),
    )
    found: list[str] = []
    markdown = report.to_markdown()
    markdown.encode("utf-8")
    for line in markdown.split("\n"):
        skeleton, spans = code_spans(line)
        assert SKELETON.fullmatch(skeleton), line
        found += [json.loads(span) for span in spans]
    want = [*licences, *versions, *versions, *(x for v in oracle for x in v)]
    for kind, reasons in kinds:
        want += [kind, *reasons]
    assert found == [*want, *names]

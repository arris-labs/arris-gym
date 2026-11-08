"""A census report round-trips through JSON and its digest names its content (ADR-0003)."""

from __future__ import annotations

import random

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from arris_gym.census import CensusReport, CorpusInfo, CorpusProgram, census

INFO = CorpusInfo(source="test", config="code_gen", revision="r0", licence="CC0-1.0")
LINES = (
    "r = cq.Workplane('XY')",
    "r = cq.Workplane('XY').box(1, 2, 3)",
    "r = r.faces('>Z').hole(1)",
    "r = r.edges('|Z').fillet(0.5)",
    "show_object(r)",
    "x = (",
)

programs_st = st.lists(
    st.tuples(st.sampled_from("abc"), st.lists(st.sampled_from(LINES), max_size=5)),
    max_size=12,
).map(
    lambda items: [
        CorpusProgram(
            stem=f"s{i:02d}", family=family, text="import cadquery as cq\n" + "\n".join(lines)
        )
        for i, (family, lines) in enumerate(items)
    ]
)


def test_a_round_trip_through_json_is_equal() -> None:
    programs = [
        CorpusProgram(stem="a", family="f", text="import cadquery as cq\nr = cq.Workplane('XY')\n"),
        CorpusProgram(stem="b", family="f", text="x = ("),
        CorpusProgram(stem="c", family="g", text="\x00"),
    ]
    report = census(programs, INFO)
    again = CensusReport.from_json(report.to_json())
    assert again == report
    assert again.digest == report.digest
    assert again.to_json() == report.to_json()


def test_a_report_whose_content_changed_under_its_digest_is_refused() -> None:
    programs = [CorpusProgram(stem="a", family="f", text="x = (")]
    data = census(programs, INFO).model_dump(mode="json")
    data["unparsable_programs"][0]["message"] = "other words"
    with pytest.raises(ValidationError, match="digest"):
        CensusReport.model_validate(data)


@given(programs_st, st.randoms(use_true_random=False))
def test_a_shuffled_corpus_has_the_same_digest(
    programs: list[CorpusProgram], rng: random.Random
) -> None:
    shuffled = list(programs)
    rng.shuffle(shuffled)
    assert census(shuffled, INFO).digest == census(programs, INFO).digest


@given(programs_st, st.sampled_from(LINES[:4]))
def test_a_changed_count_changes_the_digest(programs: list[CorpusProgram], line: str) -> None:
    extra = CorpusProgram(stem="s99", family="a", text="import cadquery as cq\n" + line)
    more = [*programs, extra]
    assert census(more, INFO).digest != census(programs, INFO).digest
    # one more call in an existing program that parses also moves it
    if programs and "x = (" not in programs[0].text:
        first = programs[0].model_copy(update={"text": programs[0].text + "\n" + line})
        changed = [first, *programs[1:]]
        assert census(changed, INFO).digest != census(programs, INFO).digest


def test_a_different_corpus_info_changes_the_digest() -> None:
    other = INFO.model_copy(update={"revision": "r1"})
    assert census([], INFO).digest != census([], other).digest

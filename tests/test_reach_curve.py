"""Reach curves use construction counts, including blocked and multi-form programs."""

import doctest
import gzip
import hashlib
import json
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from arris_gym import cq
from arris_gym.census import (
    CensusReport,
    CorpusProgram,
    ProgramCensus,
    ReachCurve,
    _curve,
    reach_curve,
)


def programs() -> list[CorpusProgram]:
    lines = [
        "result = 1",  # already admitted
        "result = cq.Workplane().a()",  # two missing forms
        "result = cq.Workplane().a()",
        "result = cq.Workplane('XY').b()",  # one missing form, wins first
        "result = cq.Workplane('XY').b()",
        "result = cq.Workplane('XY').b()",
        "result = cq.Workplane('XY').a().faces('>Z')",  # selector stays blocked
        "result = mystery()",  # unknown stays blocked
        "(",
    ]
    return [
        CorpusProgram(stem=str(i), family="f", text="import cadquery as cq\n" + line)
        for i, line in enumerate(lines)
    ]


def test_greedy_unlocks_then_lexical_bridges_with_fixed_blockers() -> None:
    curve = reach_curve(programs(), cq.subset())
    assert curve.initial.programs == 9
    assert curve.initial.stems == ("0",)
    assert [(step.form, step.in_subset) for step in curve.steps] == [
        ("Workplane.b()", 4),
        ("?.mystery()", 4),
        ("Workplane.a()", 4),
        ("cq.Workplane()", 6),
        ("Workplane.faces(str)", 6),
    ]


@given(st.permutations(programs()))
def test_input_order_cannot_move_curve_or_digest(rows: list[CorpusProgram]) -> None:
    assert reach_curve(rows, cq.subset()) == reach_curve(programs(), cq.subset())


@given(st.lists(st.booleans(), max_size=15))
def test_json_round_trip_and_counts(rows: list[bool]) -> None:
    ps = [
        CorpusProgram(stem=str(i), family="f", text="result = 1" if ok else "(")
        for i, ok in enumerate(rows)
    ]
    curve = reach_curve(ps, cq.subset())
    assert curve.initial.in_subset == sum(rows)
    assert curve.initial.programs == len(rows)
    assert ReachCurve.from_json(curve.to_json()) == curve


def test_duplicate_stems_and_changed_digest_are_refused() -> None:
    p = programs()[0]
    with pytest.raises(ValueError, match="stem"):
        reach_curve([p, p], cq.subset())
    data = reach_curve(programs(), cq.subset()).model_dump(mode="json")
    data["steps"][0]["form"] = "changed"
    with pytest.raises(ValidationError, match="digest"):
        ReachCurve.model_validate(data)
    assert doctest.testmod(_curve).failed == 0


def test_committed_benchcad_curve_repeats_offline() -> None:
    root = Path(__file__).parent / "fixtures/c2/benchcad"
    data = gzip.decompress((root / "programs.jsonl.gz").read_bytes())
    manifest = json.loads((root / "manifest.json").read_text())
    assert hashlib.sha256(data).hexdigest() == manifest["programs_sha256"]
    rows = [json.loads(line) for line in data.splitlines()]
    assert len(rows) == 17900
    assert all(r["licence"] == "CC-BY-4.0" for r in rows)
    outcomes = [ProgramCensus.model_validate(r["census"]) for r in rows]
    expected = ReachCurve.from_json((root / "reach.json").read_text())
    assert reach_curve(outcomes, cq.subset()) == expected
    assert expected.digest == manifest["reach_digest"]
    report = CensusReport.from_json((root / "census.json").read_text())
    assert report.digest == manifest["census_digest"]
    assert report.programs == expected.initial.programs
    assert expected.steps[6].in_subset == 4523
    assert expected.steps[19].in_subset == 5030


def test_admission_is_one_exact_census_form_not_a_generalized_declaration() -> None:
    ps = [
        CorpusProgram(
            stem="a",
            family="f",
            text="import cadquery as cq\nresult = cq.Workplane().cylinder(1, 2)",
        ),
        CorpusProgram(
            stem="b",
            family="f",
            text="import cadquery as cq\nresult = cq.Workplane().cylinder(height, 2)",
        ),
    ]
    steps = reach_curve(ps, cq.subset()).steps
    assert [(s.form, s.in_subset) for s in steps] == [
        ("Workplane.cylinder(name, num)", 0),
        ("cq.Workplane()", 1),
        ("Workplane.cylinder(num, num)", 2),
    ]


@given(st.text(alphabet=st.characters(exclude_categories=()) | st.sampled_from(["\ud800"])))
def test_stems_including_lone_surrogates_round_trip(stem: str) -> None:
    curve = reach_curve([CorpusProgram(stem=stem, family="f", text="result = 1")], cq.subset())
    assert ReachCurve.from_json(curve.to_json()) == curve


@pytest.mark.parametrize("mutation", ["decrease", "exceed", "duplicate"])
def test_curve_refuses_broken_count_and_unique_form_guarantees(mutation: str) -> None:
    data = reach_curve(programs(), cq.subset()).model_dump(mode="json")
    if mutation == "decrease":
        data["steps"][0]["in_subset"] = 0
    elif mutation == "exceed":
        data["steps"][-1]["in_subset"] = 10
    else:
        data["steps"][1]["form"] = data["steps"][0]["form"]
    with pytest.raises(ValidationError, match=r"counts|more than once"):
        ReachCurve.model_validate(data)


def test_curve_and_steps_are_frozen() -> None:
    curve = reach_curve(programs(), cq.subset())
    with pytest.raises(ValidationError):
        curve.digest = "changed"
    with pytest.raises(ValidationError):
        curve.steps[0].form = "changed"

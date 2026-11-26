"""Reduced measurement gaps from the BenchCAD shell replay."""

from __future__ import annotations

import gzip
import hashlib
import json
import math
from collections import Counter

import pytest

import arris_gym as ag
import cq_closed_forms as cf
import fixture_cases
from arris_gym.fidelity import ClosedForm, DisagreementClass, OracleReport, OracleStatus, Verdict
from arris_gym.fidelity._agreement import figures_agree

_CASES = ("oracle-shell-floor-fillet", "oracle-shell-tray-through-cut")


def test_shell_replay_verdicts_hold_pinned_oracle_measures_to_independent_evidence() -> None:
    """Every shell verdict has the selected evidence and an out-of-tolerance oracle report."""
    benchcad = fixture_cases.ROOT / "c2" / "benchcad"
    replay = benchcad / "shell-replay"
    verdicts = json.loads((replay / "verdicts.json").read_text())
    args = (replay / "verdicts.args").read_text().splitlines()
    method = dict(zip(args[4::2], args[3::2], strict=True))
    assert list(method) == sorted(verdicts)
    assert Counter(method.values()) == {"--shell-boundary": 48, "--shell-construction": 14}
    assert verdicts.keys() <= set((replay / "stems.txt").read_text().splitlines())
    assert Counter(stem.rsplit("_", 2)[0] for stem in verdicts) == {
        "enclosure": 11,
        "sheet_metal_tray": 51,
    }

    checked = []
    with gzip.open(benchcad / "oracle.jsonl.gz", "rt", encoding="utf-8") as oracle:
        for line in oracle:
            row = json.loads(line)
            stem = row["stem"]
            if stem not in verdicts:
                continue
            verdict = Verdict.model_validate(verdicts[stem])
            assert verdict.disagreement is DisagreementClass.OCCT_WRONG, stem
            assert isinstance(verdict.evidence, ClosedForm), stem
            if method[stem] == "--shell-construction":
                assert "--shell-construction" in verdict.evidence.note, stem
            else:
                assert "Both trim resolutions agree" in verdict.evidence.note, stem
                lo, hi = verdict.evidence.bounds
                assert all(
                    math.copysign(1.0, coordinate) > 0
                    for coordinate in (*verdict.evidence.centroid, *lo, *hi)
                    if coordinate == 0.0
                ), stem
            report = OracleReport.model_validate(row["report"])
            assert report.status is OracleStatus.OK, stem
            assert report.measures is not None, stem
            assert report.measures.solids == 1, stem
            assert not figures_agree(report.measures, verdict.evidence), stem
            checked.append(stem)
    assert sorted(checked) == sorted(verdicts)


_ENCLOSURE = """
import cadquery as cq
result = (
    cq.Workplane("XY").box(145.67, 77.02, 21.06)
    .faces(">Z").shell(-2.2)
    .faces("<Z").edges("<Z").fillet(1.86)
)
"""
_TRAY = """
import cadquery as cq
result = (
    cq.Workplane("XZ").box(96.89, 38.07, 55.57).edges(">Y").chamfer(0.96)
    .faces(">Y").shell(-3.73)
    .faces("<Y").workplane().pushPoints([(30, 0)]).hole(4.21)
    .faces(">Z").workplane().pushPoints([(0, 0)]).rect(16, 10).cutThruAll()
)
"""


@pytest.mark.parametrize(
    ("program", "slug"),
    [
        (_ENCLOSURE, "oracle-shell-floor-fillet"),
        (_TRAY, "oracle-shell-tray-through-cut"),
    ],
)
def test_shell_construction_integrals_match_the_reduced_cases(program: str, slug: str) -> None:
    fixture = fixture_cases.ROOT / "regression" / slug / "closed-form.json"
    expected = ClosedForm.model_validate_json(fixture.read_bytes())
    assert figures_agree(ClosedForm.model_validate(cf.shell_closed_form(program)), expected)


def test_shell_bore_can_cut_the_floor_and_one_inner_chamfer() -> None:
    shell = _TRAY[: _TRAY.index('    .faces("<Y")')] + ")\n"
    stock = ClosedForm.model_validate(cf.shell_closed_form(shell))
    wall = 3.73
    rim_edge = 38.07 / 2 - 0.96 - math.sqrt(2) * wall
    program = shell.removesuffix(")\n") + (
        f'    .faces("<Y").workplane().pushPoints([(0, {rim_edge})]).hole(2)\n)\n'
    )
    bored = ClosedForm.model_validate(cf.shell_closed_form(program))
    # The bore removes one disc times wall thickness and the integral of
    # depth u over a unit half disc, which is 2/3.
    assert stock.volume - bored.volume == pytest.approx(math.pi * wall + 2 / 3)
    assert bored.area - stock.area == pytest.approx(
        2 * math.pi * (wall - 1) + 2 - (1 + math.sqrt(2)) * math.pi / 2
    )
    measured = ag.run(program, dialect="cq", timeout=fixture_cases.FIXTURE_DEADLINE)
    assert measured.status is ag.Status.OK
    assert measured.measures is not None
    assert measured.measures.solids == 1
    assert figures_agree(measured.measures, bored)


@pytest.mark.parametrize(
    ("before", "after", "message"),
    [
        ("[(0, 0)]", "[(0, 7)]", "cross the full floor"),
        ("[(0, 0)]", "[(30, 0)]", "must clear the bores"),
        (".hole(4.21)", ".hole(4.21, 2)", "expected numeric shell construction arguments"),
    ],
)
def test_shell_construction_refuses_cuts_outside_its_geometry(
    before: str, after: str, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        cf.shell_closed_form(_TRAY.replace(before, after))


@pytest.mark.parametrize("slug", _CASES)
@pytest.mark.parametrize("side", ["arris", "oracle"])
def test_shell_replay_measures_match_construction(
    slug: str, side: str, request: pytest.FixtureRequest
) -> None:
    """Hold the recorded measures and a fresh candidate to the same construction."""
    directory = fixture_cases.ROOT / "regression" / slug
    program = (directory / "oracle.py").read_text()
    report = OracleReport.model_validate_json((directory / "oracle.json").read_bytes())
    assert report.program_sha256 == hashlib.sha256(program.encode()).hexdigest()
    assert report.versions is not None
    assert (report.versions.cadquery, report.versions.ocp) == ("2.3.0", "7.9.3.0")
    assert report.status is OracleStatus.OK
    assert report.measures is not None
    assert report.measures.solids == 1
    expected = ClosedForm.model_validate_json((directory / "closed-form.json").read_bytes())

    if side == "oracle":
        request.node.add_marker(
            pytest.mark.xfail(
                reason="The oracle's reported volume differs from the section integral.",
                strict=True,
                raises=AssertionError,
            )
        )
        assert figures_agree(report.measures, expected)
    else:
        result = ag.run(program, dialect="cq", timeout=fixture_cases.FIXTURE_DEADLINE)
        assert result.status is ag.Status.OK
        assert result.measures is not None
        assert result.measures.solids == 1
        assert figures_agree(result.measures, expected)

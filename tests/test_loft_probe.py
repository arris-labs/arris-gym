"""Loft constructions through the sandbox and recorded oracle worker (ADR-0026)."""

from __future__ import annotations

import gzip
import hashlib
import json
from collections import Counter
from dataclasses import replace
from math import pi, sqrt
from pathlib import Path

import pytest

import arris_gym as ag
import fixture_cases
from arris_gym.census import ProgramCensus, reach
from arris_gym.fidelity import OracleReport, OracleStatus, compare
from test_c2_baseline import baseline_subset, census_rows

ROOT = fixture_cases.ROOT / "lofts"
CASES = fixture_cases.load("lofts")
EXACT_DISC = "disc-three-sections"


def _report(text: str, program: str) -> OracleReport:
    report = OracleReport.model_validate_json(text)
    assert report.program_sha256 == hashlib.sha256(program.encode()).hexdigest()
    assert report.versions is not None
    assert (report.versions.cadquery, report.versions.ocp) == ("2.3.0", "7.9.3.0")
    return report


def _recorded(path: Path) -> OracleReport:
    return _report(path.read_text(), path.with_suffix(".py").read_text())


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.slug)
def test_smooth_loft_matches_its_construction(case: fixture_cases.Case) -> None:
    smooth = ag.run(case.program, timeout=fixture_cases.FIXTURE_DEADLINE)
    assert fixture_cases.check(smooth, case.expected) == []
    assert smooth.measures is not None
    assert smooth.measures.solids == 1
    paths = sorted((ROOT / case.slug).glob("oracle*.json"))
    assert len(paths) == (3 if case.slug == "tooth-outlines" else 1)
    for path in paths:
        report = _recorded(path)
        assert report.status is OracleStatus.OK
        if case.slug != EXACT_DISC:
            assert compare(smooth, report).outcome.value == "agree"


@pytest.mark.parametrize("case", [c for c in CASES if c.slug != EXACT_DISC], ids=lambda c: c.slug)
def test_two_matched_sections_have_the_same_smooth_and_ruled_body(case: fixture_cases.Case) -> None:
    assert 'kind="smooth"' in case.program
    smooth = ag.run(case.program, timeout=fixture_cases.FIXTURE_DEADLINE)
    ruled = ag.run(
        case.program.replace('kind="smooth"', 'kind="ruled"'),
        timeout=fixture_cases.FIXTURE_DEADLINE,
    )
    assert smooth.status is ruled.status is ag.Status.OK
    assert smooth.body == ruled.body


def test_a_quarter_turn_needs_the_vertex_pairing_from_the_oracle() -> None:
    directory = ROOT / "rectangle-quarter-turn"
    program = (directory / "program.py").read_text()
    paired = "top[-1:] + top[:-1]"
    assert paired in program
    raw = ag.run(program.replace(paired, "top"), timeout=fixture_cases.FIXTURE_DEADLINE)
    assert raw.status is ag.Status.OK
    assert raw.measures is not None
    # The drawing-start pairing has section area 12*((1-t)**2 + t**2).
    assert raw.measures.volume == pytest.approx(32)
    assert compare(raw, _recorded(directory / "oracle.json")).outcome.value == "unclassified"


@pytest.mark.xfail(
    reason="The oracle's three-disc report lies outside ADR-0005 of the quadratic profile.",
    raises=AssertionError,
    strict=True,
)
def test_oracle_measures_the_quadratic_disc_loft() -> None:
    case = next(c for c in CASES if c.slug == EXACT_DISC)
    smooth = ag.run(case.program, timeout=fixture_cases.FIXTURE_DEADLINE)
    report = _recorded(ROOT / case.slug / "oracle.json")
    assert compare(smooth, report).outcome.value == "agree"


@pytest.mark.parametrize("shape", ["rectangles", "tooth-outlines"])
def test_the_three_section_regressions_pin_their_oracle_measures(shape: str) -> None:
    directory = fixture_cases.ROOT / "regression" / f"arris-loft-three-{shape}"
    report = _recorded(directory / "oracle.json")
    assert report.status is OracleStatus.OK
    measures = report.measures
    assert measures is not None
    expected = json.loads((directory / "expected.json").read_text())["measures"]
    assert measures.model_dump(mode="json", exclude={"faces"}) == {
        key: expected[key] for key in ("volume", "area", "centroid", "bounds", "solids")
    }


def test_loft_oracle_consumes_pending_wires_and_combines_with_stock() -> None:
    records = json.loads((ROOT / "contexts.json").read_text())
    reports = {
        name: _report(json.dumps(row["report"]), row["program"]) for name, row in records.items()
    }
    for name, message in {
        "empty": "ValueError: No pending wires present",
        "single": "ValueError: More than one wire is required",
        "consume": "ValueError: No pending wires present",
    }.items():
        assert reports[name].status is OracleStatus.RUNTIME
        assert reports[name].message == message

    assert reports["stock-default"].measures == reports["stock-combine"].measures
    for name, volume, area, y, radius, y0, y1 in (
        ("stock-separate", 7, 5 + 3 * sqrt(10), 2 + 33 / 28, 2, 2, 5),
        ("stock-combine", 43, 39 + 3 * sqrt(10), 89 / 172, 3, -2, 5),
        ("stock-follow", 43.5, 41 + 3 * sqrt(10), (89 / 4 + 3) / 43.5, 3, -2, 7),
    ):
        report = reports[name]
        assert report.status is OracleStatus.OK
        m = report.measures
        assert m is not None
        assert m.solids == 1
        assert m.volume == pytest.approx(pi * volume)
        assert m.area == pytest.approx(pi * area)
        assert m.centroid == pytest.approx((0, y, 0), abs=fixture_cases.DEFAULT_TOLERANCE)
        assert m.bounds[0] == pytest.approx((-radius, y0, -radius))
        assert m.bounds[1] == pytest.approx((radius, y1, radius))


def test_the_loft_declaration_reaches_the_six_measured_benchcad_families() -> None:
    rows = census_rows("benchcad")
    before = baseline_subset()
    before_reach = reach(rows, before)
    assert before_reach.in_subset == 14_150
    (loft,) = (form for form in ag.cq.subset().forms if form.name == "Workplane.loft")
    after = reach(rows, replace(before, forms=(*before.forms, loft)))
    added = set(after.stems) - set(before_reach.stems)
    counts = Counter(stem.rsplit("_", 2)[0] for stem in added)
    assert after.in_subset == 15_142
    assert counts == {
        "bevel_gear": 189,
        "helical_gear": 203,
        "propeller": 106,
        "tapered_boss": 146,
        "twisted_bracket": 177,
        "wing_nut": 171,
    }
    helical = [
        row
        for row in rows
        if isinstance(row, ProgramCensus)
        and row.stem in added
        and row.stem.startswith("helical_gear_")
    ]
    assert Counter(dict(row.calls)["Workplane.polyline"] for row in helical) == {2: 110, 3: 93}

    # Only the pinned oracle reports can be used for the complete programs.
    corpus = fixture_cases.ROOT / "c2" / "benchcad"
    with gzip.open(corpus / "programs.jsonl.gz", "rt", encoding="utf-8") as stream:
        hashes = {
            row["census"]["stem"]: row["program_sha256"]
            for line in stream
            if (row := json.loads(line))["census"]["stem"] in added
        }
    with gzip.open(corpus / "oracle.jsonl.gz", "rt", encoding="utf-8") as stream:
        reports = {}
        for line in stream:
            row = json.loads(line)
            name = row["stem"]
            if name in added:
                report = OracleReport.model_validate(row["report"])
                assert report.program_sha256 == hashes[name]
                reports[name] = report.status
    assert len(reports) == 992
    assert Counter(reports.values()) == {OracleStatus.OK: 979, OracleStatus.INVALID: 13}
    assert all(
        stem.startswith("wing_nut_")
        for stem, status in reports.items()
        if status is OracleStatus.INVALID
    )

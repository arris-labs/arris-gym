"""The calibration set (ADR-0005): arris against the oracle, both against a closed form.

Each `tests/fixtures/fidelity/agree-*/` holds `program.py` (arris), `oracle.py`
(the same part in CadQuery), `oracle.json` (the oracle's recorded report,
made by `tools/oracle_run.py`) and `expected.json` (the closed form, worked
out from how the part is built; see the directory's README). The gate runs
arris and reads the recorded oracle report: no CadQuery here.
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

import arris_gym
from arris_gym import ExecResult, Status
from arris_gym.fidelity import (
    AREA_REL,
    BOUNDS_ABS,
    CENTROID_DIAG,
    VOLUME_REL,
    MeasureDeltas,
    OracleMeasures,
    OracleReport,
    OracleStatus,
    measure_deltas,
    program_sha256,
    within_tolerance,
)
from arris_gym.sandbox import Measures

ROOT = pathlib.Path(__file__).resolve().parent / "fixtures" / "fidelity"
DIRECTORIES = sorted(ROOT.glob("agree-*"))
# Relative to the closed form, in volume, area and centroid: a bound on the
# oracle's own accuracy and arris's, from the numbers ADR-0005 records.
SLACK = 1e-12


def expected(d: pathlib.Path) -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads((d / "expected.json").read_text())
    return loaded


def flat(corners: Any) -> list[float]:
    return [float(x) for corner in corners for x in corner]


def recorded(d: pathlib.Path) -> OracleReport:
    return OracleReport.model_validate_json((d / "oracle.json").read_text())


def run(d: pathlib.Path) -> ExecResult:
    return arris_gym.run((d / "program.py").read_text())


def test_there_are_about_twenty_pairs() -> None:
    assert len(DIRECTORIES) >= 19


@pytest.mark.parametrize("d", DIRECTORIES, ids=lambda d: d.name)
def test_the_recorded_oracle_report_is_of_the_oracle_program(d: pathlib.Path) -> None:
    report = recorded(d)
    assert report.status is OracleStatus.OK
    assert report.program_sha256 == program_sha256((d / "oracle.py").read_text())
    assert report.measures is not None
    assert report.measures.solids == 1


@pytest.mark.parametrize("d", DIRECTORIES, ids=lambda d: d.name)
def test_the_oracle_holds_the_closed_form(d: pathlib.Path) -> None:
    want = expected(d)
    measures = recorded(d).measures
    assert measures is not None
    assert measures.volume == pytest.approx(want["volume"], rel=SLACK)
    assert measures.area == pytest.approx(want["area"], rel=SLACK)
    assert measures.centroid == pytest.approx(want["centroid"], abs=1e-9)
    assert flat(measures.bounds) == pytest.approx(flat(want["bounds"]), abs=BOUNDS_ABS)


@pytest.mark.parametrize("d", DIRECTORIES, ids=lambda d: d.name)
def test_arris_holds_the_closed_form(d: pathlib.Path) -> None:
    want = expected(d)
    result = run(d)
    assert result.status is Status.OK, result.message
    assert result.measures is not None
    assert result.measures.volume == pytest.approx(want["volume"], rel=SLACK)
    assert result.measures.area == pytest.approx(want["area"], rel=SLACK)
    assert result.measures.centroid == pytest.approx(want["centroid"], abs=1e-9)
    assert flat(result.measures.bounds) == pytest.approx(flat(want["bounds"]), abs=BOUNDS_ABS)


@pytest.mark.parametrize("d", DIRECTORIES, ids=lambda d: d.name)
def test_every_pair_agrees(d: pathlib.Path) -> None:
    result = run(d)
    oracle = recorded(d).measures
    assert result.measures is not None
    assert oracle is not None
    deltas = measure_deltas(result.measures, oracle)
    assert within_tolerance(deltas), deltas


def test_the_face_counts_differ_where_conventions_do_and_are_not_judged() -> None:
    # arris keeps the coplanar faces of a fuse split; Open CASCADE's clean
    # merges them. The L's closed form is 8 faces.
    d = ROOT / "agree-l-prism-fuse"
    result = run(d)
    oracle = recorded(d).measures
    assert result.measures is not None
    assert oracle is not None
    assert oracle.faces == expected(d)["faces"] == 8
    assert result.measures.faces == 11
    deltas = measure_deltas(result.measures, oracle)
    assert deltas.faces == 3
    assert within_tolerance(deltas)


# --- The tolerance bites: a gap past each constant is a disagreement. -------

CUBE = Measures(
    volume=1000.0,
    area=600.0,
    centroid=(5.0, 5.0, 5.0),
    bounds=((0.0, 0.0, 0.0), (10.0, 10.0, 10.0)),
    faces=6,
    shells=1,
    genus=0,
    face_kinds=(("plane", 6),),
)
CUBE_ORACLE = OracleMeasures(
    volume=1000.0,
    area=600.0,
    centroid=(5.0, 5.0, 5.0),
    bounds=((0.0, 0.0, 0.0), (10.0, 10.0, 10.0)),
    faces=6,
    solids=1,
)
DIAGONAL = 300.0**0.5


def test_a_gap_past_each_constant_disagrees_and_one_inside_agrees() -> None:
    cases: dict[str, dict[str, Any]] = {
        "volume": {"volume": 1000.0 * (1 + 2 * VOLUME_REL)},
        "area": {"area": 600.0 * (1 + 2 * AREA_REL)},
        "centroid": {"centroid": (5.0 + 2 * CENTROID_DIAG * DIAGONAL, 5.0, 5.0)},
        "bounds": {"bounds": ((0.0, 0.0, 0.0), (10.0 + 2 * BOUNDS_ABS, 10.0, 10.0))},
    }
    for name, update in cases.items():
        deltas = measure_deltas(CUBE.model_copy(update=update), CUBE_ORACLE)
        assert not within_tolerance(deltas), name
        assert getattr(deltas, name) > 0.0
    padded = CUBE.model_copy(update={"bounds": ((-2e-7, -2e-7, -2e-7), (10.0 + 2e-7,) * 3)})
    assert within_tolerance(measure_deltas(padded, CUBE_ORACLE))


@given(
    st.floats(min_value=1e-3, max_value=1e6),
    st.floats(min_value=1e-3, max_value=1e6),
    st.floats(min_value=-1e3, max_value=1e3),
)
def test_deltas_are_symmetric_in_volume_and_area_and_zero_on_equals(
    v: float, a: float, c: float
) -> None:
    here = CUBE.model_copy(update={"volume": v, "area": a, "centroid": (c, c, c)})
    there = CUBE_ORACLE.model_copy(update={"volume": v, "area": a, "centroid": (c, c, c)})
    assert measure_deltas(here, there) == MeasureDeltas(
        volume=0.0, area=0.0, centroid=0.0, bounds=0.0, faces=0
    )
    swapped = measure_deltas(
        CUBE.model_copy(update={"volume": there.area}),
        CUBE_ORACLE.model_copy(update={"volume": v}),
    )
    other = measure_deltas(
        CUBE.model_copy(update={"volume": v}),
        CUBE_ORACLE.model_copy(update={"volume": there.area}),
    )
    assert swapped.volume == other.volume

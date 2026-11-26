"""Reduced measurement gaps from the BenchCAD shell replay."""

from __future__ import annotations

import hashlib

import pytest

import arris_gym as ag
import fixture_cases
from arris_gym.fidelity import ClosedForm, OracleReport, OracleStatus
from arris_gym.fidelity._agreement import figures_agree

_CASES = ("oracle-shell-floor-fillet", "oracle-shell-tray-through-cut")


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

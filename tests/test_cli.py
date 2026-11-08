"""`arris-gym census` writes the census and the slice, and names the extra when it is missing."""

from __future__ import annotations

from pathlib import Path

import pytest

from arris_gym import _cli
from arris_gym.census import CensusReport, CorpusProgram

CODE = "import cadquery as cq\nr = cq.Workplane('XY').box(1, 1, 1)\n"


def corpus() -> list[CorpusProgram]:
    return [
        CorpusProgram(stem=f"{family}-{i:03d}", family=family, text=CODE if i % 2 else "(")
        for family in ("washer", "gear", "bolt")
        for i in range(120)
    ]


def test_the_two_files_and_the_digest(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert _cli.main(["census", "--corpus", "benchcad", "--out", str(tmp_path)], reader=corpus) == 0
    report = CensusReport.from_json((tmp_path / "census.json").read_text(encoding="utf-8"))
    assert report.programs == 360
    assert report.unparsable == 180
    assert f"digest {report.digest}" in capsys.readouterr().out
    lines = (tmp_path / "slice.txt").read_text(encoding="utf-8").splitlines()
    header = [line for line in lines if line.startswith("#")]
    stems = [line for line in lines if not line.startswith("#")]
    assert len(stems) == 300
    assert any("CC-BY-4.0" in line for line in header)
    assert any(line.startswith("# families: ") for line in header)


def test_the_missing_extra_exits_2_with_one_line(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(_cli, "_extra_present", lambda: False)
    assert _cli.main(["census", "--corpus", "benchcad", "--out", str(tmp_path)]) == 2
    err = capsys.readouterr().err
    assert err.count("\n") == 1
    assert "arris-gym[corpus]" in err
    assert not list(tmp_path.iterdir())

"""`arris-gym census` writes the census and the slice, and names the extra when it is missing."""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

import arris.build as b
import pytest

from arris_gym import _cli
from arris_gym.census import CensusReport, CorpusProgram, ReachCurve, slice_families
from arris_gym.rescore import RescoreTable

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


def test_per_program_rows_and_curve_repeat_without_source_text(tmp_path: Path) -> None:
    ps = corpus()
    _cli.run_census(lambda: ps, tmp_path)
    first = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    _cli.run_census(lambda: list(reversed(ps)), tmp_path)
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == first
    records = [
        json.loads(line) for line in gzip.decompress(first["programs.jsonl.gz"]).splitlines()
    ]
    assert len(records) == len(ps)
    assert all(r["licence"] == "CC-BY-4.0" and "text" not in r for r in records)
    assert {r["census"]["stem"]: r["program_sha256"] for r in records} == {
        p.stem: hashlib.sha256(p.text.encode()).hexdigest() for p in ps
    }
    curve = ReachCurve.from_json(first["reach.json"].decode())
    assert curve.initial.programs == 360
    assert curve.initial.in_subset == 180  # every parsed r assignment is admitted


def test_the_missing_extra_exits_2_with_one_line(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(_cli, "_extra_present", lambda: False)
    assert _cli.main(["census", "--corpus", "benchcad", "--out", str(tmp_path)]) == 2
    err = capsys.readouterr().err
    assert err.count("\n") == 1
    assert "arris-gym[corpus]" in err
    assert not list(tmp_path.iterdir())


def test_the_header_names_the_families_the_slice_rule_chooses(tmp_path: Path) -> None:
    programs = corpus()
    report = _cli.run_census(lambda: programs, tmp_path)
    chosen = slice_families(report, _cli.SLICE_FAMILIES, _cli.PER_FAMILY)
    assert f"# families: {', '.join(chosen)}" in (tmp_path / "slice.txt").read_text("utf-8")


_BOX = b.Solid.box((-0.5, -1.0, -1.5), (0.5, 1.0, 1.5))
BOX_STEP = _BOX.model.write_step([_BOX.body])
BOX_CQ = "import cadquery as cq\nresult = cq.Workplane('XY').box(1, 2, 3)\n"


def rescore_files(tmp_path: Path, stems: list[str]) -> tuple[Path, Path]:
    slice_path = tmp_path / "slice.txt"
    slice_path.write_text("# header\n" + "\n".join(stems) + "\n", encoding="utf-8")
    rows = [{"stem": s, "step_sha256": "0" * 64, "step": BOX_STEP} for s in sorted(stems)]
    targets = tmp_path / "targets.jsonl.gz"
    targets.write_bytes(gzip.compress("\n".join(map(json.dumps, rows)).encode(), mtime=0))
    return slice_path, targets


def test_rescore_writes_the_table_and_prints_the_digest(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    slice_path, targets = rescore_files(tmp_path, ["good", "bad"])
    programs = [
        CorpusProgram(stem="good", family="f", text=BOX_CQ),
        CorpusProgram(stem="bad", family="f", text="("),
    ]
    out = tmp_path / "out"
    argv = [
        "rescore", "benchcad", "--slice", str(slice_path), "--targets", str(targets),
        "--out", str(out), "--workers", "2",
    ]  # fmt: skip
    assert _cli.main(argv, reader=lambda: programs) == 0
    table = RescoreTable.from_json((out / "rescore.json").read_text(encoding="utf-8"))
    assert table.programs == 2
    assert (table.statuses["ok"], table.statuses["syntax"]) == (1, 1)
    assert (table.stages["none"], table.stages["program"]) == (1, 1)
    assert [r.name for r in table.rows] == ["bad", "good"]
    assert {r.licence for r in table.rows} == {"CC-BY-4.0"}
    printed = capsys.readouterr().out
    assert f"digest {table.digest}" in printed
    assert "survivors" in printed
    markdown = (out / "rescore.md").read_text(encoding="utf-8")
    assert table.digest in markdown
    assert "survivors" in markdown


def test_rescore_names_a_stem_the_corpus_lacks(tmp_path: Path) -> None:
    slice_path, targets = rescore_files(tmp_path, ["only"])
    argv = ["rescore", "benchcad", "--slice", str(slice_path), "--targets", str(targets)]
    with pytest.raises(ValueError, match="not in the pinned corpus"):
        _cli.main([*argv, "--out", str(tmp_path / "o")], reader=list)


def test_rescore_without_the_extra_exits_2(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(_cli, "_extra_present", lambda: False)
    assert _cli.main(["rescore", "benchcad", "--out", str(tmp_path / "o")]) == 2
    assert "arris-gym[corpus]" in capsys.readouterr().err
    assert not (tmp_path / "o").exists()

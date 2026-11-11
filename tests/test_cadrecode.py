"""CAD-Recode's validation adapter reads only text at an exact revision and count."""

import gzip
import hashlib
import json
from pathlib import Path

import pytest

from arris_gym import _cli, cq
from arris_gym.census import (
    CensusReport,
    CorpusProgram,
    ProgramCensus,
    ReachCurve,
    cadrecode,
    reach_curve,
)


def test_files_preserve_order_bytes_and_validation_family(tmp_path: Path) -> None:
    first, second = tmp_path / "b.py", tmp_path / "a.py"
    first.write_bytes(b"# utf-8: \xc3\xa9\r\nresult = 1\r\n")
    second.write_text("(", encoding="utf-8")
    got = cadrecode.read_files([first, second], expected=2)
    assert got == [
        CorpusProgram(stem="b", family="validation", text="# utf-8: é\r\nresult = 1\r\n"),
        CorpusProgram(stem="a", family="validation", text="("),
    ]
    assert (
        hashlib.sha256(got[0].text.encode()).digest() == hashlib.sha256(first.read_bytes()).digest()
    )


def test_wrong_count_and_duplicate_stems_are_refused(tmp_path: Path) -> None:
    path = tmp_path / "a.py"
    path.write_text("result = 1", encoding="utf-8")
    with pytest.raises(ValueError, match="1 programs read, 968 expected"):
        cadrecode.read_files([path])
    with pytest.raises(ValueError, match="stem"):
        cadrecode.read_files([path, path], expected=2)


def test_the_original_release_and_validation_count_are_pinned() -> None:
    assert cadrecode.INFO.source == "filapro/cad-recode"
    assert cadrecode.INFO.revision == "17d554bbc50a23de6cf6a742a3e0ed867f000153"
    assert cadrecode.INFO.config == "val"
    assert cadrecode.INFO.licence == "CC-BY-NC-4.0"
    assert cadrecode.PROGRAMS == 968


def test_cli_uses_cadrecode_metadata_and_does_not_select_a_benchcad_slice(tmp_path: Path) -> None:
    ps = [CorpusProgram(stem="0", family="validation", text="r = 1")]
    assert (
        _cli.main(["census", "--corpus", "cadrecode", "--out", str(tmp_path)], reader=lambda: ps)
        == 0
    )
    report = CensusReport.from_json((tmp_path / "census.json").read_text())
    assert report.corpus == cadrecode.INFO
    assert not (tmp_path / "slice.txt").exists()
    records = [
        json.loads(line)
        for line in gzip.decompress((tmp_path / "programs.jsonl.gz").read_bytes()).splitlines()
    ]
    assert records[0]["licence"] == "CC-BY-NC-4.0"
    assert records[0]["revision"] == cadrecode.REVISION
    assert ReachCurve.from_json((tmp_path / "reach.json").read_text()).initial.in_subset == 0


def test_committed_cadrecode_census_and_curve_recheck_offline() -> None:
    root = Path(__file__).parent / "fixtures/c2/cadrecode"
    data = gzip.decompress((root / "programs.jsonl.gz").read_bytes())
    manifest = json.loads((root / "manifest.json").read_text())
    assert hashlib.sha256(data).hexdigest() == manifest["programs_sha256"]
    records = [json.loads(line) for line in data.splitlines()]
    assert len(records) == cadrecode.PROGRAMS
    for record in records:
        assert all(record[key] == value for key, value in cadrecode.INFO.model_dump().items())
        assert "text" not in record
    rows = [ProgramCensus.model_validate(record["census"]) for record in records]
    assert all(row.end_form == "r = …" for row in rows)
    report = CensusReport.from_json((root / "census.json").read_text())
    assert report.digest == manifest["census_digest"]
    assert report.programs == report.parsed == 968
    assert report.families[0].end_forms == (("r = …", 968),)
    curve = ReachCurve.from_json((root / "reach.json").read_text())
    assert curve.digest == manifest["reach_digest"]
    assert reach_curve(rows, cq.subset()) == curve
    assert curve.initial.programs == 968
    assert curve.initial.in_subset == 0
    assert all(step.in_subset == 0 for step in curve.steps)


def test_download_lists_only_validation_and_preserves_sorted_paths(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from types import SimpleNamespace

    import huggingface_hub

    class FakeApi:
        def list_repo_tree(
            self, repo: str, *, path_in_repo: str, repo_type: str, revision: str, recursive: bool
        ) -> list[SimpleNamespace]:
            assert (repo, path_in_repo, repo_type, revision, recursive) == (
                cadrecode.REPO,
                "val",
                "dataset",
                cadrecode.REVISION,
                True,
            )
            return [
                SimpleNamespace(path="val/b.py"),
                SimpleNamespace(path="val/a.py"),
                SimpleNamespace(path="val/README.md"),
            ]

    def fetch(repo: str, name: str, *, repo_type: str, revision: str) -> str:
        assert (repo, repo_type, revision) == (cadrecode.REPO, "dataset", cadrecode.REVISION)
        return str(tmp_path / name)

    monkeypatch.setattr(huggingface_hub, "HfApi", FakeApi)
    monkeypatch.setattr(huggingface_hub, "hf_hub_download", fetch)
    monkeypatch.setattr(cadrecode, "PROGRAMS", 2)
    assert cadrecode.download() == [tmp_path / "val/a.py", tmp_path / "val/b.py"]
    monkeypatch.setattr(cadrecode, "PROGRAMS", 3)
    with pytest.raises(ValueError, match="2 validation paths listed, 3 expected"):
        cadrecode.download()


def test_examples_run() -> None:
    import doctest

    assert doctest.testmod(cadrecode).failed == 0

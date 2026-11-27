"""`tools/cq_corpus.py`'s resume (plans/fidelity-target step 5): a saved chunk is kept
except for its timed-out rows, which are run again (a timeout is never cached). With
`--oracle-rows`, the oracle runs only the programs no saved row of its versions answers."""

from __future__ import annotations

import gzip
import json
import pathlib
from collections.abc import Sequence
from typing import Any

import pytest

import cq_corpus
import oracle_run
from arris_gym.census import CorpusProgram
from arris_gym.fidelity import (
    FidelityTable,
    OracleMeasures,
    OracleReport,
    OracleStatus,
    OracleVersions,
    program_sha256,
)
from arris_gym.sandbox._zygote import BACKSTOP
from test_fidelity_table import entries


def test_a_resume_reruns_only_the_timed_out_rows() -> None:
    chosen = [e for e in entries() if e.name in ("agree-box", "class-cq-bug")]
    good = [e.model_dump(mode="json") for e in chosen]
    stale = dict(good[1])
    stale["row"] = {**good[1]["row"], "oracle_status": "timeout", "oracle_versions": None}
    oracle: list[dict[str, Any]] = [{"stem": "a"}, {"stem": "stale"}]
    data = {"entries": [good[0], stale], "oracle": oracle}
    part = [CorpusProgram(stem=e.name, family="f", text="") for e in chosen]
    seen: list[str] = []

    def rerun(ps: Sequence[CorpusProgram]) -> dict[str, Any]:
        seen.extend(p.stem for p in ps)
        return {"entries": [good[1]], "oracle": [{"stem": "fresh"}]}

    body, again = cq_corpus.retry_timeouts(part, data, rerun)
    assert again
    assert seen == [chosen[1].name]
    assert body["entries"] == good
    assert body["oracle"] == [{"stem": "a"}, {"stem": "fresh"}]
    # No timeout, no rerun: the saved body is returned as it is.
    body, again = cq_corpus.retry_timeouts(part, {"entries": good, "oracle": oracle}, rerun)
    assert not again
    assert body["entries"] == good


V1 = OracleVersions(cadquery="2.3.0", ocp="7.9.3.0", python="3.12.3")
V2 = OracleVersions(cadquery="2.4.0", ocp="7.9.3.0", python="3.12.3")


def _report(sha: str, versions: OracleVersions | None, message: str = "") -> OracleReport:
    status = OracleStatus.RUNTIME if versions is not None else OracleStatus.TIMEOUT
    return OracleReport(
        status=status,
        message=message,
        measures=None,
        step_sha256=None,
        program_sha256=sha * 64,
        versions=versions,
    )


def test_the_oracle_runs_only_the_programs_no_saved_row_answers() -> None:
    known = {"a" * 64: _report("a", V1, "saved a"), "c" * 64: _report("c", V1, "saved c")}
    asked: list[list[str]] = []

    def run(texts: Sequence[str]) -> list[OracleReport]:
        asked.append(list(texts))
        return [_report(t, V1, f"fresh {t}") for t in texts]

    shas = [s * 64 for s in "abcd"]
    reports = cq_corpus.merge_reports(list("abcd"), shas, known, run)
    assert asked == [["b", "d"]]
    assert [r.message for r in reports] == ["saved a", "fresh b", "saved c", "fresh d"]
    # Every program answered by a saved row: the oracle is not started.
    asked.clear()
    reports = cq_corpus.merge_reports(["a", "c"], [shas[0], shas[2]], known, run)
    assert asked == []
    assert [r.message for r in reports] == ["saved a", "saved c"]


def test_a_saved_row_is_reused_only_from_this_oracle_and_never_a_timeout(
    tmp_path: pathlib.Path,
) -> None:
    saved = [_report("a", V1), _report("b", V2), _report("c", None)]
    part = [CorpusProgram(stem=s, family="f", text="") for s in "abc"]
    path = tmp_path / "oracle.jsonl.gz"
    path.write_bytes(cq_corpus.gz(oracle_run.rows_text(cq_corpus.rows(part, saved, "L", "R"))))
    read = cq_corpus.read_oracle(path)
    assert read == {r.program_sha256: r for r in saved}
    assert list(cq_corpus.reusable(read, V1)) == ["a" * 64]


@pytest.fixture
def replay_input(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[list[dict[str, object]], list[str], pathlib.Path]:
    programs = [CorpusProgram(stem=s, family="validation", text="x =") for s in "abc"]
    sha = program_sha256(programs[0].text)
    reports = [
        OracleReport(
            status=OracleStatus.SYNTAX,
            message=f"pinned {p.stem}",
            measures=None,
            step_sha256=None,
            program_sha256=sha,
            versions=V2 if p.stem == "b" else V1,
        )
        for p in programs
    ]
    monkeypatch.setattr(cq_corpus, "load", lambda _: (programs, "source", "L", "R"))
    monkeypatch.setattr(oracle_run, "PYTHON", tmp_path / "missing-oracle-python")
    path = tmp_path / "oracle.jsonl.gz"
    argv = [
        "--corpus",
        "cadrecode",
        "--replay-oracle-rows",
        str(path),
        "--out-dir",
        str(tmp_path / "out"),
        "--workers",
        "1",
    ]
    return cq_corpus.rows(programs, reports, "L", "R"), argv, path


def test_replay_preserves_reports_by_stem_without_an_oracle_environment(
    replay_input: tuple[list[dict[str, object]], list[str], pathlib.Path],
) -> None:
    rows, argv, path = replay_input
    path.write_bytes(cq_corpus.gz(oracle_run.rows_text(rows)))
    assert cq_corpus.main(argv) == 0
    out = path.parent / "out"
    assert (out / "oracle.jsonl.gz").read_bytes() == path.read_bytes()
    table_path = out / "fidelity.json.gz"
    table = FidelityTable.from_json(gzip.decompress(table_path.read_bytes()).decode("utf-8"))
    assert table.programs == 3
    assert [entry.row.oracle_versions for entry in table.entries] == [V1, V2, V1]

    selection = path.parent / "slice.txt"
    selection.write_text("a\nc\n", encoding="utf-8")
    work = path.parent / "slice-work"
    assert cq_corpus.main([*argv, "--slice", str(selection), "--work-dir", str(work)]) == 0
    assert (out / "oracle.jsonl.gz").read_bytes() == cq_corpus.gz(
        oracle_run.rows_text([rows[0], rows[2]])
    )

    report = OracleReport.model_validate(rows[1]["report"])
    rows[1]["report"] = report.model_copy(update={"versions": V1}).model_dump(
        mode="json", exclude={"step", "seconds"}
    )
    path.write_bytes(cq_corpus.gz(oracle_run.rows_text(rows)))
    with pytest.raises(ValueError, match="does not match the pinned oracle rows"):
        cq_corpus.main(argv)


def test_replay_slice_uses_the_corpus_verdicts(
    replay_input: tuple[list[dict[str, object]], list[str], pathlib.Path],
) -> None:
    rows, argv, path = replay_input
    report = OracleReport.model_validate(rows[0]["report"])
    rows[0]["report"] = report.model_copy(
        update={
            "status": OracleStatus.INVALID,
            "measures": OracleMeasures(
                volume=1,
                area=6,
                centroid=(0, 0, 0),
                bounds=((0, 0, 0), (1, 1, 1)),
                faces=6,
                solids=1,
            ),
        },
    ).model_dump(mode="json", exclude={"step", "seconds"})
    path.write_bytes(cq_corpus.gz(oracle_run.rows_text(rows)))
    selection = path.parent / "slice.txt"
    selection.write_text("a\n", encoding="utf-8")
    verdicts = path.parent / "verdicts.json"
    verdict = {
        "disagreement": "by_design",
        "evidence": {"kind": "doc", "anchor": "docs/ARCHITECTURE.md#outcomes"},
    }
    verdicts.write_text(json.dumps({"a": verdict, "b": verdict}), encoding="utf-8")
    command = [*argv, "--slice", str(selection), "--verdicts", str(verdicts)]
    assert cq_corpus.main(command) == 0
    table_path = path.parent / "out" / "fidelity.json.gz"
    table = FidelityTable.from_json(gzip.decompress(table_path.read_bytes()).decode("utf-8"))
    (entry,) = table.entries
    assert entry.name == "a"
    assert entry.row.verdict is not None
    assert entry.row.verdict.model_dump(mode="json") == verdict

    verdicts.write_text(json.dumps({"a": verdict, "unknown": verdict}), encoding="utf-8")
    with pytest.raises(ValueError, match=r"verdicts for stems outside the run: .*unknown"):
        cq_corpus.main(command)


@pytest.mark.parametrize(
    ("issue", "error"),
    [
        ("missing", "1 missing replay reports, starting with b"),
        ("duplicate", "b: duplicate replay report"),
        ("timeout", "b: unanswered replay report"),
        ("crash", "b: unanswered replay report"),
        ("family", "b: replay family does not match"),
        ("licence", "b: replay licence does not match"),
        ("revision", "b: replay revision does not match"),
        ("sha", "b: replay program SHA-256 does not match"),
    ],
)
def test_replay_rejects_bad_reports_before_running(
    replay_input: tuple[list[dict[str, object]], list[str], pathlib.Path],
    issue: str,
    error: str,
) -> None:
    rows, argv, path = replay_input
    if issue == "missing":
        del rows[1]
    elif issue == "duplicate":
        rows.append(rows[1])
    elif issue in ("timeout", "crash", "sha"):
        report = OracleReport.model_validate(rows[1]["report"]).model_dump(mode="json")
        if issue == "sha":
            report["program_sha256"] = "0" * 64
        else:
            report.update(status=issue, versions=None)
        rows[1]["report"] = report
    else:
        rows[1][issue] = "wrong"
    path.write_bytes(cq_corpus.gz(oracle_run.rows_text(rows)))
    with pytest.raises(ValueError, match=error):
        cq_corpus.main(argv)
    assert not (path.parent / "out").exists()


def test_replay_cannot_be_combined_with_live_reuse(tmp_path: pathlib.Path) -> None:
    path = str(tmp_path / "oracle.jsonl.gz")
    with pytest.raises(SystemExit) as stopped:
        cq_corpus.main(
            ["--corpus", "benchcad", "--oracle-rows", path, "--replay-oracle-rows", path]
        )
    assert stopped.value.code == 2


def test_the_oracle_deadline_is_a_measured_multiple_and_inside_a_zygotes_lifetime() -> None:
    """ADR-0013's amendment: 240 s is the next multiple of 30 s above 4 x the slowest
    BenchCAD program (57.3 s), and a program of it still fits a zygote."""
    slowest = 57.3
    assert cq_corpus.ORACLE_TIMEOUT == 240.0
    assert (int(4 * slowest // 30) + 1) * 30 == cq_corpus.ORACLE_TIMEOUT
    assert cq_corpus.ORACLE_TIMEOUT + BACKSTOP < oracle_run.ZYGOTE_LIFETIME

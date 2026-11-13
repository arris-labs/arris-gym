"""`tools/cq_corpus.py`'s resume (plans/fidelity-target step 5): a saved chunk is kept
except for its timed-out rows, which are run again (a timeout is never cached). With
`--oracle-rows`, the oracle runs only the programs no saved row of its versions answers."""

from __future__ import annotations

import pathlib
from collections.abc import Sequence
from typing import Any

import cq_corpus
import oracle_run
from arris_gym.census import CorpusProgram
from arris_gym.fidelity import OracleReport, OracleStatus, OracleVersions
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

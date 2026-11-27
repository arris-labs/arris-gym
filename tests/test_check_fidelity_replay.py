"""Independent C2 acceptance checks, using one program and no corpus fetch."""

import gzip
from pathlib import Path

import pytest

import check_fidelity_replay
from arris_gym import Status
from arris_gym.census import CorpusProgram
from arris_gym.cq import subset
from arris_gym.fidelity import (
    DisagreementClass,
    OracleStatus,
    RegressionFixture,
    TableEntry,
    Verdict,
    arris_rows,
    compare,
    fidelity_table,
    reach_report,
)
from test_fidelity_compare import report, result


@pytest.mark.parametrize("status", [Status.OK, Status.TIMEOUT])
def test_matching_reports_still_have_to_meet_acceptance(
    status: Status,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setitem(check_fidelity_replay.ACCEPTANCE, "benchcad", (1, 1, 0))
    oracle = report(OracleStatus.OK)
    verdict = None
    if status is Status.TIMEOUT:
        verdict = Verdict(
            disagreement=DisagreementClass.ARRIS_BUG,
            evidence=RegressionFixture(path="tests/fixtures/regression/fork-bomb-status"),
        )
    row = compare(result(status), oracle, verdict)
    table = fidelity_table([TableEntry(name="box", source="test", licence="MIT", row=row)])
    program = CorpusProgram(stem="box", family="box", text="result = 1")
    reach = reach_report(table, [program], subset())
    arris = arris_rows(table)
    assert table.outcomes["unclassified"] == 0
    assert reach.in_subset == 1

    reference = tmp_path / "reference"
    replay = tmp_path / "replay"
    for path in (reference, replay):
        path.mkdir()
        (path / "fidelity.json.gz").write_bytes(gzip.compress(table.to_json().encode()))
        (path / "oracle.jsonl.gz").write_bytes(gzip.compress(oracle.model_dump_json().encode()))
        (path / "reach-report.json").write_text(reach.to_json(), encoding="utf-8")
        (path / "arris-report.json").write_text(arris.to_json(), encoding="utf-8")
        (path / "arris-report.md").write_text(arris.to_markdown(), encoding="utf-8")

    expected = 1 if status is Status.TIMEOUT else 0
    assert (
        check_fidelity_replay.main(
            ["--corpus", "benchcad", "--reference-dir", str(reference), "--replay-dir", str(replay)]
        )
        == expected
    )
    output = capsys.readouterr()
    assert f"timeouts={expected}" in output.out
    assert output.err == ("Replay does not meet C2 acceptance for benchcad\n" if expected else "")

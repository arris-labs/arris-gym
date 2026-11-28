"""The pinned Vision2Code join, frozen inputs, upstream parity and isolation."""

from __future__ import annotations

import gzip
import hashlib
import json
import math
import os
import re
import socket
import struct
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import arris.build
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from arris_gym import Sandbox, Status
from arris_gym.census import CorpusProgram, benchcad
from arris_gym.rescore import RescoreEntry, RescoreTable, Stage, rescore
from arris_gym.sandbox import Dialect
from benchcad._bundle import _Prediction
from benchcad._generation import _capture_predictions
from benchcad.vision2code import Upstream, _slice_programs, open_upstream

_FIXTURE = Path(__file__).parent / "fixtures" / "benchcad-vision2code" / "smoke"
_BOX = b"import cadquery as cq\nresult = cq.Workplane('XY').box(1, 1, 1)"


def test_join_checks_every_stem_and_reference_hash(tmp_path: Path) -> None:
    stem, family = "box_1", "box"
    program = CorpusProgram(stem=stem, family=family, text=_BOX.decode())
    row = {
        "stem": stem,
        "family": family,
        "revision": benchcad.REVISION,
        "report": {"program_sha256": hashlib.sha256(_BOX).hexdigest()},
    }
    oracle = tmp_path / "oracle.jsonl"
    oracle.write_text(json.dumps(row) + "\n")
    assert _slice_programs([stem], [program], oracle) == [program]
    with pytest.raises(ValueError, match="IDs differ"):
        _slice_programs([stem, "box_2"], [program], oracle)
    with pytest.raises(ValueError, match="duplicate corpus row"):
        _slice_programs([stem], [program, program], oracle)
    with pytest.raises(ValueError, match="program hash differs"):
        _slice_programs([stem], [CorpusProgram(stem=stem, family=family, text="pass")], oracle)


def test_frozen_smoke_artifacts() -> None:
    evidence = json.loads((_FIXTURE / "smoke.json").read_bytes())
    assert evidence["verified_ids"] == 300
    assert [row["family"] for row in evidence["rows"]] == [
        "lobed_knob",
        "phone_stand",
        "venturi_tube",
    ]
    with Sandbox() as sandbox:
        for row in evidence["rows"]:
            stem = row["record_id"]
            target = gzip.decompress((_FIXTURE / f"{stem}.step.gz").read_bytes())
            candidate = gzip.decompress((_FIXTURE / f"{stem}.candidate.step.gz").read_bytes())
            program = (_FIXTURE / f"{stem}.py").read_bytes()
            render = (_FIXTURE / f"{stem}.png").read_bytes()
            assert hashlib.sha256(target).hexdigest() == row["target_sha256"]
            assert hashlib.sha256(candidate).hexdigest() == row["candidate_sha256"]
            assert hashlib.sha256(program).hexdigest() == row["extracted_sha256"]
            assert hashlib.sha256(render).hexdigest() == row["render_sha256"]
            assert render.startswith(b"\x89PNG\r\n\x1a\n")
            assert struct.unpack(">II", render[16:24]) == (524, 524)
            imported = sandbox.read_target(target.decode())
            assert imported.status is Status.OK, imported.message
            assert imported.step_sha256 == row["step_sha256"]


@pytest.fixture(scope="module")
def checkout() -> Path:
    path = os.environ.get("BENCHCAD_CHECKOUT")
    if path is None:
        pytest.skip("set BENCHCAD_CHECKOUT to the pinned upstream checkout")
    return Path(path)


@pytest.fixture(scope="module")
def upstream(checkout: Path) -> Iterator[Upstream]:
    with open_upstream(checkout) as helper:
        yield helper


@pytest.fixture(scope="module")
def box(upstream: Upstream) -> bytes:
    return upstream.export(_BOX)


@pytest.mark.oracle
def test_regrader_parity(upstream: Upstream, box: bytes) -> None:
    def compare(raw: str | None, outcome: str) -> float:
        code = None if raw is None else upstream.extract(raw)
        grade, candidate = upstream._grade_capture(box, code)
        assert grade.outcome == outcome, grade.message
        assert grade.iou == upstream._regrade(box, raw or "", code, candidate)
        return grade.iou

    assert compare(None, "missing") == 0.0
    assert compare("no program here", "blank") == 0.0
    assert compare("```python\nresult = (\n```", "export_error") == 0.0
    assert compare(_BOX.decode(), "scored") == 1.0
    assert compare(_BOX.decode().replace("1, 1, 1", "2, 2, 2"), "scored") == 1.0
    rectangular = compare(_BOX.decode().replace("1, 1, 1", "1, 2, 3"), "scored")
    assert 0.0 < rectangular < 1.0
    assert rectangular == round(rectangular, 4)
    captured = _replay_box_step().encode()
    frozen_grade, candidate = upstream._grade_capture(captured, _BOX)
    assert candidate is not None
    assert frozen_grade.outcome == "scored"
    assert frozen_grade.iou == upstream._regrade(captured, _BOX.decode(), _BOX, candidate) == 1.0
    # The upstream scorer catches a bad STEP internally and reports zero.
    grade = upstream.grade(b"bad STEP", _BOX)
    assert grade.outcome == "scored"
    assert grade.iou == 0.0


@pytest.mark.oracle
def test_upstream_box_round_trip_retains_the_surface_term(box: bytes) -> None:
    entry = RescoreEntry(
        name="upstream box",
        source="test",
        licence="CC0-1.0",
        program=_BOX.decode(),
        dialect=Dialect.CQ,
        step=box.decode(),
    )
    (row,) = rescore([entry]).rows
    assert row.score.status is Status.OK
    assert row.score.iou == 1.0
    assert row.score.field is not None
    assert row.score.field.voxel_iou_64 == 1.0
    assert row.score.surface is not None
    assert 0.0 < row.score.surface < 1.0
    assert row.score.reward < 1.0


@pytest.mark.oracle
def test_regrader_parity_on_frozen_slice_parts(upstream: Upstream) -> None:
    rows = json.loads((_FIXTURE / "smoke.json").read_bytes())["rows"]
    for row in rows:
        stem = row["record_id"]
        target = gzip.decompress((_FIXTURE / f"{stem}.step.gz").read_bytes())
        candidate = gzip.decompress((_FIXTURE / f"{stem}.candidate.step.gz").read_bytes())
        program = (_FIXTURE / f"{stem}.py").read_bytes()
        raw = f"```python\n{program.decode()}\n```"
        assert upstream.extract(raw) == program
        assert upstream._regrade(target, raw, program, candidate) == row["upstream_iou"] == 1.0


@pytest.mark.oracle
def test_export_jobs_isolate_scratch_inputs_credentials_and_network(
    upstream: Upstream, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    private = tmp_path / "outside.txt"
    private.write_text("keep this")
    monkeypatch.setenv("BENCHCAD_TEST_CREDENTIAL", "test-only")
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        program = f"""
import mmap
import os
import re
import resource
import socket
from pathlib import Path
from typing import Any

assert "BENCHCAD_TEST_CREDENTIAL" not in os.environ
assert os.getuid() != 0
assert not Path({str(private)!r}).exists()
try:
    Path("/inputs/program.py").write_text("changed")
except OSError:
    pass
else:
    raise AssertionError("input was writable")
with socket.socket() as conn:
    conn.settimeout(0.1)
    assert conn.connect_ex({listener.getsockname()!r}) != 0
_, hard = resource.getrlimit(resource.RLIMIT_AS)
assert 0 < hard < 4 * 2**30
try:
    mmap.mmap(-1, hard + mmap.PAGESIZE)
except (MemoryError, OSError):
    pass
else:
    raise AssertionError("allocation exceeded the address space limit")
Path("/tmp/test-marker").write_text("only in this job")
"""
        assert upstream.export(program.encode() + _BOX).startswith(b"ISO-10303-21;")
    clean = b'from pathlib import Path\nassert not Path("/tmp/test-marker").exists()\n'
    export_call = b"\nresult.val().exportStep('rewritten.step')"
    assert upstream.export(clean + _BOX + export_call).startswith(b"ISO-10303-21;")
    assert private.read_text() == "keep this"


@pytest.mark.oracle
def test_deadline_bounds_export_and_next_job_runs(checkout: Path, box: bytes) -> None:
    with open_upstream(checkout, timeout=3.0) as helper:
        # A bounded wait in a fresh session also holds the export child's pipe open.
        blocked = b"""
import subprocess
import sys
subprocess.Popen([sys.executable, "-c", "import time; time.sleep(12)"], start_new_session=True)
"""
        grade = helper.grade(box, blocked + _BOX)
        assert grade.outcome == "timeout", grade.message
        assert grade.iou == 0.0
        assert grade.stage == "export"
        assert helper.export(_BOX).startswith(b"ISO-10303-21;")


@pytest.mark.oracle
@settings(max_examples=20, deadline=None)
@given(st.text(max_size=120))
def test_every_utf8_program_has_an_upstream_grade(
    upstream: Upstream, box: bytes, program: str
) -> None:
    grade = upstream.grade(box, program.encode("utf-8"))
    assert 0.0 <= grade.iou <= 1.0
    if not program.strip():
        assert grade.outcome == "blank"
    if grade.outcome != "scored":
        assert grade.iou == 0.0


_DRIVER = Path(__file__).resolve().parents[1] / "tools/benchcad/vision2code.py"


def _replay_box_step() -> str:
    box = arris.build.Workplane.XY().offset(-0.5).rect(1, 1).extrude(1)
    step = box.to_step()
    # Start the base's four-edge loop at the same geometric corner as the
    # CQ extrusion's mesh. A cyclic shift preserves the boundary and its
    # orientation. The pinned STEP import then gives the same ordered mesh
    # and the seeded surface samples agree exactly (ADR-0009).
    loop = re.search(r"EDGE_LOOP\('',\(([^)]+)\)\);", step)
    assert loop is not None
    a, b, c, d = loop[1].split(",")
    return step[: loop.start(1)] + ",".join((d, a, b, c)) + step[loop.end(1) :]


def _hash(text: str | None) -> str | None:
    return hashlib.sha256(text.encode()).hexdigest() if text is not None else None


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


@pytest.fixture
def bundle(tmp_path: Path) -> Path:
    """Freeze a complete comparison bundle from a unit box and independent failures."""
    root = tmp_path / "bundle"
    targets = root / "targets"
    targets.mkdir(parents=True)
    target_box = _replay_box_step()
    prediction_box = _BOX.decode()
    prediction_cases = [
        ("box", prediction_box, None, "scored", 1.0),
        ("blank", " \n\t", None, "blank", 0.0),
        ("missing", None, None, "missing", 0.0),
        ("broken", "result = (", None, "export_error", 0.0),
        ("corrupt", prediction_box, None, "scored", 0.0),
        ("generation-failed", None, "generation_failed", "missing", 0.0),
        ("extraction-failed", None, "extraction_failed", "missing", 0.0),
        ("upstream-timeout", prediction_box, None, "timeout", 0.0),
    ]
    tasks, predictions, grades = [], [], []
    for name, program, failure, outcome, iou in prediction_cases:
        step = "corrupt STEP" if name == "corrupt" else target_box
        target_hash = _hash(step)
        start = step.find("DATA;")
        (targets / f"{name}.step").write_bytes(step.encode())
        tasks.append(
            {
                "record_id": name,
                "stem": name,
                "family": "box",
                "source": "test",
                "licence": "CC0-1.0",
                "reference_sha256": _hash(prediction_box),
                "target_sha256": target_hash,
                "step_sha256": None if start < 0 else _hash(step[start:]),
                "render_sha256": _hash(f"render of {name}"),
            }
        )
        if name != "missing":
            raw = None if failure == "generation_failed" else f"raw: {program}"
            prompt = "Build a unit box"
            predictions.append(
                {
                    "record_id": name,
                    "model": "fixture",
                    "model_revision": "fixture-v1",
                    "licence": "CC0-1.0",
                    "prompt": prompt,
                    "prompt_sha256": _hash(prompt),
                    "render_sha256": _hash(f"render of {name}"),
                    "decoding": {"temperature": 0},
                    "raw_response": raw,
                    "raw_response_sha256": _hash(raw),
                    "program": program,
                    "program_sha256": _hash(program),
                    "failure": failure,
                }
            )
        grade: dict[str, Any] = {"outcome": outcome, "iou": iou}
        if outcome == "timeout":
            grade["stage"] = "scoring"
        grades.append(
            {
                "record_id": name,
                "target_sha256": target_hash,
                "program_sha256": _hash(program),
                "grade": grade,
            }
        )
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "version": 1,
                "pins": {
                    "code_gen_revision": benchcad.REVISION,
                    "upstream_commit": "77fd16a80a4e5fc39964ee23b6cc3225beefac8f",
                    "oracle_lock_sha256": hashlib.sha256(
                        (_DRIVER.parent.parent / "oracle/uv.lock").read_bytes()
                    ).hexdigest(),
                },
                "tasks": tasks,
            }
        ),
        encoding="utf-8",
    )
    _write_jsonl(root / "predictions.jsonl", predictions)
    _write_jsonl(root / "upstream.jsonl", grades)
    return root


@pytest.mark.oracle
def test_pinned_prompt_uses_the_frozen_canonical_render(
    upstream: Upstream, monkeypatch: pytest.MonkeyPatch
) -> None:
    stem = "lobed_knob_000072_s20260505"
    target = gzip.decompress((_FIXTURE / f"{stem}.step.gz").read_bytes())
    render = (_FIXTURE / f"{stem}.png").read_bytes()
    # The isolated builder uses the upstream full hint regardless of the host.
    monkeypatch.setenv("BENCH_VIEW_HINT", "anchor")
    system, user = upstream._prompt(target, render)
    assert _hash(system) == "357ab68907383eb86456255e4934a81e2fa32e5139407c97eeb43abbfdd849f0"
    assert _hash(user) == "bc68c2b8ad55007567c033ad125cb6eb19be06db8e7ed1cf6bfb4d5b0bec9150"


def test_generation_sees_only_prompt_and_render_and_captures_each_outcome(
    bundle: Path, tmp_path: Path
) -> None:
    renders = bundle / "renders"
    renders.mkdir()
    for task in json.loads((bundle / "manifest.json").read_bytes())["tasks"]:
        record_id = task["record_id"]
        (renders / f"{record_id}.png").write_bytes(f"render of {record_id}".encode())
    system_text, user_text = "Describe the shape — as code", "Recreate this part"
    responses = {"blank": "", "box": "```python\nprogram\n```", "extraction-failed": "☃"}
    calls = []

    def prompt(target: bytes, render: bytes) -> tuple[str, str]:
        assert target == (bundle / "targets/blank.step").read_bytes()
        assert render == b"render of blank"
        return system_text, user_text

    def generate(system: str, user: str, render: bytes) -> str | None:
        assert (system, user) == (system_text, user_text)
        calls.append(render)
        return responses.get(render.decode().removeprefix("render of "))

    def extract(raw: str) -> bytes:
        if raw == "☃":
            raise RuntimeError("extractor failed")
        return b"program" if raw else b""

    out = tmp_path / "captured.jsonl"
    selected = ["generation-failed", "extraction-failed", "box", "blank"]
    _capture_predictions(
        bundle, out, prompt=prompt, generate=generate, extract=extract, record_ids=selected
    )
    assert calls == [f"render of {record_id}".encode() for record_id in sorted(selected)]
    rows = [_Prediction.model_validate_json(line) for line in out.read_bytes().splitlines()]
    assert [row.record_id for row in rows] == sorted(selected)
    assert [row._outcome() for row in rows] == [
        "blank",
        "program",
        "extraction_failed",
        "generation_failed",
    ]
    assert [row.raw_response for row in rows] == ["", responses["box"], "☃", None]
    assert [row.program for row in rows] == ["", "program", None, None]
    assert all(json.loads(row.prompt) == {"system": system_text, "user": user_text} for row in rows)

    # Even an unselected record belongs to the frozen manifest.
    (renders / "missing.png").write_bytes(b"changed after freeze")
    calls.clear()
    with pytest.raises(ValueError, match="render file hash differs at missing"):
        _capture_predictions(
            bundle,
            tmp_path / "bad.jsonl",
            prompt=prompt,
            generate=generate,
            extract=extract,
            record_ids=selected,
        )
    assert calls == []


def _run_replay(bundle: Path, out: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_DRIVER), "replay", "--bundle", str(bundle), "--out", str(out), *args],
        text=True,
        capture_output=True,
        check=False,
    )


def _report(out: Path) -> dict[str, Any]:
    report: dict[str, Any] = json.loads((out / "comparison.json").read_bytes())
    claimed = report.pop("digest")
    canonical = json.dumps(report, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    assert claimed == _hash(canonical)
    report["digest"] = claimed
    return report


@given(st.text(max_size=120))
def test_prediction_program_round_trips_as_utf8(program: str) -> None:
    text_hash = _hash(program)
    prediction = _Prediction.model_validate_json(
        json.dumps(
            {
                "record_id": "box",
                "model": "fixture",
                "model_revision": "fixture-v1",
                "licence": "CC0-1.0",
                "prompt": "box",
                "prompt_sha256": _hash("box"),
                "render_sha256": _hash("render"),
                "decoding": {"temperature": 0},
                "raw_response": program,
                "raw_response_sha256": text_hash,
                "program": program,
                "program_sha256": text_hash,
            }
        )
    )
    assert prediction.program is not None
    assert prediction.program.encode("utf-8") == program.encode("utf-8")
    assert _Prediction.model_validate_json(prediction.model_dump_json()) == prediction


def test_replay_counts_all_failures_and_ignores_bundle_order(bundle: Path, tmp_path: Path) -> None:
    out = tmp_path / "replay"
    result = _run_replay(bundle, out, "--workers", "1")
    assert result.returncode == 0, result.stderr
    report = _report(out)
    rows = {row["task"]["record_id"]: row for row in report["rows"]}
    assert list(rows) == sorted(rows)
    box = rows["box"]
    assert box["prediction_outcome"] == "program"
    assert box["upstream"]["iou"] == box["gym"]["score"]["iou"] == 1.0
    assert box["gym"]["score"]["field"]["voxel_iou_64"] == 1.0
    assert box["gym"]["score"]["reward"] == 1.0
    want = (
        ("blank", "blank", "blank", "program", "runtime"),
        ("missing", "missing", "missing", "program", "runtime"),
        ("broken", "program", "export_error", "program", "syntax"),
        ("corrupt", "program", "scored", "target", "runtime"),
        ("generation-failed", "generation_failed", "missing", "program", "runtime"),
        ("extraction-failed", "extraction_failed", "missing", "program", "runtime"),
    )
    for name, prediction, upstream, stage, status in want:
        row = rows[name]
        assert row["prediction_outcome"] == prediction
        assert (row["upstream"]["outcome"], row["upstream"]["iou"]) == (upstream, 0.0)
        assert row["gym"]["stage"] == stage
        assert (row["gym"]["score"]["status"], row["gym"]["score"]["reward"]) == (status, -1.0)
    for name in ("missing", "blank", "generation-failed", "extraction-failed"):
        assert rows[name]["gym"]["program_sha256"] == _hash("")
    assert rows["broken"]["gym"]["program_sha256"] == _hash("result = (")
    totals = report["aggregates"]
    assert totals["records"] == len(rows) == 8
    assert totals["gym_invalid"] == 6
    assert totals["gym_invalidity_rate"] == 6 / 8
    assert totals["gym_program_statuses"]["ok"] == 3
    assert totals["gym_score_statuses"]["ok"] == 2
    assert totals["upstream_mean_voxel_iou_all"] == 1 / 8
    assert totals["upstream_scored_zero_iou"] == 1
    assert totals["upstream_timeouts"] == [{"record_id": "upstream-timeout", "stage": "scoring"}]
    assert totals["gym_iou_routes"] == {"exact": 2, "sampled": 0}
    assert totals["gym_survivors"]["records"] == 2
    assert totals["paired_scored"]["records"] == 1
    table = RescoreTable.from_json((out / "rescore.json").read_text())
    assert report["gym_digest"] == table.digest
    manifest = bundle / "manifest.json"
    fields = json.loads(manifest.read_bytes())
    fields["tasks"].reverse()
    manifest.write_text(json.dumps(fields), encoding="utf-8")
    for path in (bundle / "predictions.jsonl", bundle / "upstream.jsonl"):
        path.write_bytes(b"\n".join(reversed(path.read_bytes().splitlines())) + b"\n")
    rerun = tmp_path / "reordered"
    result = _run_replay(bundle, rerun, "--workers", "4")
    assert result.returncode == 0, result.stderr
    for name in ("rescore.json", "rescore.md", "comparison.json", "comparison.md"):
        assert (rerun / name).read_bytes() == (out / name).read_bytes()


def test_record_id_selects_one_row_and_records_a_real_scoring_timeout(
    bundle: Path, tmp_path: Path
) -> None:
    out = tmp_path / "selected"
    # Adding the smallest positive float to the worker's monotonic clock
    # gives an immediately expired deadline, independent of CPU speed.
    result = _run_replay(
        bundle, out, "--record-id", "box", "--score-timeout", str(math.nextafter(0.0, 1.0))
    )
    assert result.returncode == 0, result.stderr
    report = _report(out)
    table = RescoreTable.from_json((out / "rescore.json").read_text())
    (row,) = table.rows
    assert row.name == report["rows"][0]["task"]["record_id"] == "box"
    assert row.stage is Stage.SCORING
    assert row.score.status is Status.TIMEOUT
    assert row.score.reward == -1.0
    assert report["aggregates"]["records"] == 1
    assert report["aggregates"]["gym_timeouts"] == [{"name": "box", "stage": "scoring"}]
    assert "Gym scoring" in (out / "comparison.md").read_text()
    rejected = _run_replay(bundle, tmp_path / "unknown", "--record-id", "unknown")
    assert rejected.returncode == 2
    assert "unknown manifest ID unknown" in rejected.stderr
    (bundle / "targets" / "corrupt.step").write_bytes(b"changed unselected target")
    rejected = _run_replay(bundle, tmp_path / "rejected", "--record-id", "box")
    assert rejected.returncode == 2
    assert "target file hash differs at corrupt" in rejected.stderr


@pytest.mark.parametrize(
    ("filename", "edit", "reason"),
    [
        ("manifest.json", "duplicate", "duplicate manifest ID"),
        ("manifest.json", "step_sha256", "STEP data-section hash differs"),
        ("manifest.json", "upstream_commit", "differs from the pilot pin"),
        ("manifest.json", "oracle_lock_sha256", "differs from the pilot lock"),
        ("predictions.jsonl", "duplicate", "duplicate prediction ID"),
        ("predictions.jsonl", "record_id", "foreign prediction IDs"),
        ("predictions.jsonl", "render_sha256", "prediction render hash differs"),
        ("predictions.jsonl", "prompt_sha256", "prediction text hash differs"),
        ("predictions.jsonl", "raw_response_sha256", "prediction text hash differs"),
        ("predictions.jsonl", "program_sha256", "prediction text hash differs"),
        ("upstream.jsonl", "duplicate", "duplicate upstream ID"),
        ("upstream.jsonl", "record_id", "upstream IDs differ from manifest"),
        ("upstream.jsonl", "target_sha256", "target file hash differs"),
        ("upstream.jsonl", "program_sha256", "upstream program hash differs"),
        ("upstream.jsonl", "grade", "upstream outcome disagrees with prediction"),
    ],
)
def test_replay_rejects_bad_joins_and_hashes(
    bundle: Path, tmp_path: Path, filename: str, edit: str, reason: str
) -> None:
    path = bundle / filename
    if filename == "manifest.json":
        manifest = json.loads(path.read_bytes())
        if edit == "duplicate":
            manifest["tasks"].append(manifest["tasks"][0])
        elif edit == "step_sha256":
            manifest["tasks"][0][edit] = "0" * 64
        else:
            manifest["pins"][edit] = "0" * 64
        path.write_text(json.dumps(manifest), encoding="utf-8")
    else:
        records = [json.loads(line) for line in path.read_bytes().splitlines()]
        if edit == "duplicate":
            records.append(records[0])
        elif edit == "record_id":
            records[0][edit] = "foreign"
        elif edit == "grade":
            records[0][edit] = {"outcome": "missing", "iou": 0}
        else:
            records[0][edit] = "0" * 64
        _write_jsonl(path, records)
    out = tmp_path / "invalid"
    result = _run_replay(bundle, out)
    assert result.returncode == 2, result.stderr
    assert reason in result.stderr
    assert not out.exists()

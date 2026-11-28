"""The pinned Vision2Code join, frozen inputs, upstream parity and isolation."""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import socket
import struct
from collections.abc import Iterator
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from arris_gym import Sandbox, Status
from arris_gym.census import CorpusProgram, benchcad
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
    # The upstream scorer catches a bad STEP internally and reports zero.
    grade = upstream.grade(b"bad STEP", _BOX)
    assert grade.outcome == "scored"
    assert grade.iou == 0.0


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
import resource
import socket
from pathlib import Path

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

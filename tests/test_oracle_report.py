"""The oracle report's frame parser (fidelity/_oracle.py): trusts no frame."""

from __future__ import annotations

import hashlib
import json
from typing import Any

import pydantic
import pytest
from hypothesis import given
from hypothesis import strategies as st

from arris_gym.fidelity import OracleReport, OracleStatus, parse_outcome, program_sha256
from arris_gym.sandbox._isolate import Ending, EndKind
from arris_gym.sandbox._zygote import MAX_RESULT_BYTES, Outcome

PROGRAM = "import cadquery as cq\nresult = cq.Workplane().box(2, 3, 4)\n"
TIMEOUT = 5.0
CLEAN = Ending(EndKind.EXITED, 0, True)
VERSIONS = {"cadquery": "2.3.0", "ocp": "7.9.3.0", "python": "3.12.3"}
MEASURES = {
    "volume": 24.0,
    "area": 52.0,
    "centroid": [0.0, 0.0, 0.0],
    "bounds": [[-1.0, -1.5, -2.0], [1.0, 1.5, 2.0]],
    "faces": 6,
    "solids": 1,
}
# A STEP text as the worker sends it, header blanked; its hash is of the data
# section alone, by construction.
STEP_HEADER = "ISO-10303-21;\nHEADER;\nFILE_NAME('Open CASCADE Shape Model','',());\nENDSEC;\n"
STEP_DATA = "DATA;\n#1 = CARTESIAN_POINT('',(0.,0.,0.));\nENDSEC;\nEND-ISO-10303-21;\n"
STEP = STEP_HEADER + STEP_DATA
SHA = hashlib.sha256(STEP_DATA.encode("ascii")).hexdigest()


def frame(**changes: Any) -> dict[str, Any]:
    """A whole `ok` frame for PROGRAM, with `changes` applied."""
    base: dict[str, Any] = {
        "status": "ok",
        "message": "",
        "measures": MEASURES,
        "step_sha256": SHA,
        "step_text": STEP,
        "program_sha256": program_sha256(PROGRAM),
        "versions": VERSIONS,
    }
    return {**base, **changes}


def outcome(data: bytes, ending: Ending | None = CLEAN, *, overflow: bool = False) -> Outcome:
    return Outcome(ending=ending, data=data, overflow=overflow, stderr=b"warned\n")


def parse(data: bytes, **kw: Any) -> OracleReport:
    return parse_outcome(outcome(data, **kw), PROGRAM, timeout=TIMEOUT, seconds=1.25)


def test_a_whole_frame_is_the_report() -> None:
    report = parse(json.dumps(frame()).encode())
    assert report.status is OracleStatus.OK
    assert report.measures is not None
    assert report.measures.volume == 24.0
    assert report.seconds == 1.25
    assert report.versions is not None
    assert report.versions.ocp == "7.9.3.0"
    assert report.step == STEP
    assert report.step_sha256 == SHA


@pytest.mark.parametrize(
    ("status", "measures", "step"),
    [
        ("syntax", None, None),
        ("runtime", None, None),
        ("no_result", None, None),
        ("invalid", MEASURES, None),
    ],
)
def test_each_status_a_worker_decides_parses(
    status: str, measures: dict[str, Any] | None, step: str | None
) -> None:
    data = json.dumps(
        frame(status=status, message="m", measures=measures, step_sha256=step, step_text=step)
    )
    report = parse(data.encode())
    assert report.status is OracleStatus(status)
    assert report.step is None


@pytest.mark.parametrize(
    "bad",
    [
        {"status": "ok", "measures": None},  # ok without measures
        {"status": "ok", "step_sha256": None, "step_text": None},  # ok without a STEP hash
        {"step_text": None},  # ok without its STEP
        {"step_text": STEP_HEADER},  # a STEP with no data section
        {"status": "invalid", "step_sha256": None},  # invalid with a STEP
        {"status": "runtime", "measures": None, "step_sha256": None},  # runtime with a STEP
        {"step_text": 3},
        {"status": "syntax"},  # syntax with measures and a hash
        {"status": "invalid", "step_sha256": SHA},  # invalid with a hash
        {"status": "runtime", "measures": None},  # a hash without ok
        {"status": "timeout", "measures": None, "step_sha256": None, "step_text": None},
        {"status": "crash", "measures": None, "step_sha256": None, "step_text": None},
        {"program_sha256": "b" * 64},  # another program's
        {"program_sha256": "A" * 64},  # not lower case
        {"step_sha256": "short"},
        {"versions": None},
        {"measures": {**MEASURES, "volume": float("nan")}},
        {"measures": {**MEASURES, "faces": -1}},
        {"surprise": 1},  # an unknown field
        {"status": "no such status"},
    ],
)
def test_a_frame_contradicting_its_status_or_job_is_a_crash(bad: dict[str, Any]) -> None:
    report = parse(json.dumps(frame(**bad)).encode())
    assert report.status is OracleStatus.CRASH
    assert report.measures is None
    assert report.versions is None
    assert report.program_sha256 == program_sha256(PROGRAM)


def test_a_frame_without_its_step_text_field_is_a_crash() -> None:
    # The worker always writes the field; a frame without it is not whole.
    old = {key: value for key, value in frame().items() if key != "step_text"}
    assert parse(json.dumps(old).encode()).status is OracleStatus.CRASH


@pytest.mark.parametrize(
    "step",
    [
        STEP_HEADER + STEP_DATA.replace("0.,0.,0.", "0.,0.,1."),  # a coordinate moved
        STEP_HEADER + STEP_DATA + "\n",  # one byte more
        STEP_HEADER + STEP_DATA.replace("DATA;", "DATA; "),  # the mark's own line
    ],
)
def test_a_step_that_contradicts_its_hash_is_a_crash(step: str) -> None:
    report = parse(json.dumps(frame(step_text=step)).encode())
    assert report.status is OracleStatus.CRASH
    assert report.message == "the oracle worker delivered a STEP that contradicts its hash"
    assert report.step is None
    assert report.step_sha256 is None


def test_the_hash_is_of_the_data_section_alone() -> None:
    # The header is what the worker blanks (timestamp, counter); a header the
    # hash does not cover changes nothing it pins.
    header = STEP_HEADER.replace("''", "'2026-11-09T22:43:23'")
    report = parse(json.dumps(frame(step_text=header + STEP_DATA)).encode())
    assert report.status is OracleStatus.OK
    assert report.step == header + STEP_DATA


def test_a_report_refuses_a_step_its_hash_or_status_contradicts() -> None:
    ok = parse(json.dumps(frame()).encode())
    with pytest.raises(pydantic.ValidationError, match="step_sha256 is its hash"):
        OracleReport(**{**dict(ok), "step": STEP + "x"})
    syntax = parse(
        json.dumps(frame(status="syntax", measures=None, step_sha256=None, step_text=None)).encode()
    )
    with pytest.raises(pydantic.ValidationError, match="only when status is OK"):
        OracleReport(**{**dict(syntax), "step": STEP_DATA})
    with pytest.raises(pydantic.ValidationError, match="only when status is OK"):
        OracleReport(**{**dict(syntax), "step": STEP_HEADER})  # no data section, no hash


def test_a_recorded_report_reads_back_without_its_step() -> None:
    ok = parse(json.dumps(frame()).encode())
    recorded = OracleReport.model_validate_json(ok.model_dump_json(exclude={"step", "seconds"}))
    assert recorded.step is None
    assert recorded.digest() == ok.digest()


def test_a_timeout_is_named_with_the_deadline() -> None:
    report = parse(b"", ending=Ending(EndKind.TIMED_OUT, 0, True))
    assert report.status is OracleStatus.TIMEOUT
    assert report.message == "the oracle worker ran past the 5.0 s deadline"


@pytest.mark.parametrize(
    ("ending", "overflow", "words"),
    [
        (None, False, "left no record"),
        (Ending(EndKind.SIGNALLED, 11, True), False, "killed by SIGSEGV"),
        (Ending(EndKind.EXITED, 0, False), False, "could not isolate itself"),
        (Ending(EndKind.EXITED, 3, True), False, "exited with code 3"),
        (CLEAN, True, f"more than {MAX_RESULT_BYTES} bytes"),
        (CLEAN, False, "delivered no result"),
    ],
)
def test_a_job_that_delivered_no_frame_is_a_crash_with_its_stderr(
    ending: Ending | None, overflow: bool, words: str
) -> None:
    data = b"" if overflow or words == "delivered no result" else b"{}"
    report = parse(data, ending=ending, overflow=overflow)
    assert report.status is OracleStatus.CRASH
    assert words in report.message
    assert report.message.endswith("its stderr ends:\nwarned\n")


def test_a_frame_from_a_worker_that_did_not_exit_cleanly_is_not_believed() -> None:
    report = parse(json.dumps(frame()).encode(), ending=Ending(EndKind.EXITED, 1, True))
    assert report.status is OracleStatus.CRASH


def test_the_digest_leaves_out_step_and_seconds_and_nothing_else() -> None:
    a = parse(json.dumps(frame()).encode())
    b = a.model_copy(update={"seconds": 99.0})
    c = a.model_copy(update={"message": "x"})
    d = a.model_copy(update={"step": None})
    assert a.digest() == b.digest() == d.digest() != c.digest()


@given(st.binary(max_size=2000))
def test_arbitrary_bytes_on_the_result_pipe_give_a_report_or_a_crash(data: bytes) -> None:
    report = parse(data)
    assert report.status is OracleStatus.CRASH


JSON = st.recursive(
    st.none() | st.booleans() | st.integers() | st.floats() | st.text(max_size=20),
    lambda kids: (
        st.lists(kids, max_size=4) | st.dictionaries(st.text(max_size=12), kids, max_size=6)
    ),
    max_leaves=20,
)
FIELDS = st.sampled_from(
    ["status", "message", "measures", "step_sha256", "step_text", "program_sha256", "versions"]
)


@given(st.dictionaries(FIELDS, JSON, max_size=6))
def test_a_forged_object_gives_a_report_that_holds_its_own_guarantees(
    obj: dict[str, Any],
) -> None:
    # Whatever parses is a report whose fields agree with its status; the
    # rest is a crash. Never an exception.
    report = parse(json.dumps(obj, allow_nan=True).encode())
    again = OracleReport.model_validate_json(report.model_dump_json())
    assert again == report
    if report.status is not OracleStatus.CRASH:
        assert report.program_sha256 == program_sha256(PROGRAM)


@given(st.integers(min_value=1, max_value=3000))
def test_deeply_nested_json_is_a_crash_not_a_recursion_error(depth: int) -> None:
    assert parse(b"[" * depth + b"]" * depth).status is OracleStatus.CRASH

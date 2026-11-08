"""The oracle report's frame parser (fidelity/_oracle.py): trusts no frame."""

from __future__ import annotations

import json
from typing import Any

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
SHA = "a" * 64


def frame(**changes: Any) -> dict[str, Any]:
    """A whole `ok` frame for PROGRAM, with `changes` applied."""
    base: dict[str, Any] = {
        "status": "ok",
        "message": "",
        "measures": MEASURES,
        "step_sha256": SHA,
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
    data = json.dumps(frame(status=status, message="m", measures=measures, step_sha256=step))
    assert parse(data.encode()).status is OracleStatus(status)


@pytest.mark.parametrize(
    "bad",
    [
        {"status": "ok", "measures": None},  # ok without measures
        {"status": "ok", "step_sha256": None},  # ok without a STEP hash
        {"status": "syntax"},  # syntax with measures and a hash
        {"status": "invalid", "step_sha256": SHA},  # invalid with a hash
        {"status": "runtime", "measures": None},  # a hash without ok
        {"status": "timeout", "measures": None, "step_sha256": None},  # the caller's status
        {"status": "crash", "measures": None, "step_sha256": None},
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


def test_the_digest_leaves_out_seconds_and_nothing_else() -> None:
    a = parse(json.dumps(frame()).encode())
    b = a.model_copy(update={"seconds": 99.0})
    c = a.model_copy(update={"message": "x"})
    assert a.digest() == b.digest() != c.digest()


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
    ["status", "message", "measures", "step_sha256", "program_sha256", "versions"]
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

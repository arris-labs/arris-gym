"""`run` classifies a program by type and returns a result for every one.

Fixtures under `tests/fixtures/sandbox/` hold one program per status with
expectations by construction (tests/fixture_cases.py).
"""

from __future__ import annotations

import base64
import doctest
import hashlib
import json

import pytest

import arris_gym as ag
import fixture_cases
from arris_gym.sandbox import _isolate, _run, _sandbox, _zygote
from arris_gym.sandbox._zygote import Outcome

CASES = fixture_cases.load("sandbox")


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.slug)
def test_a_fixture_program_gives_its_expected_result(case: fixture_cases.Case) -> None:
    result = fixture_cases.run(case)
    assert fixture_cases.check(result, case.expected) == []
    assert result.program_sha256 == hashlib.sha256(case.program.encode()).hexdigest()
    assert result.versions == _run.current_versions()


def test_the_fixtures_cover_every_status() -> None:
    reached = {c.expected["status"] for c in CASES}
    assert reached == {s.value for s in ag.Status}


def test_an_ok_result_carries_the_bytes_of_its_digest() -> None:
    program = next(c.program for c in CASES if c.slug == "ok-box")
    result = ag.run(program)
    assert result.body is not None
    assert result.body == ag.BodyRef.of(result.body.data)
    assert ag.run(program).body == result.body


@pytest.mark.parametrize(
    "text",
    ["x = \x00", 'x = "\ud800"\nresult = 1', "", "﻿", "(" * 5000, "x = 1\r" * 3],
    ids=["nul", "surrogate", "empty", "bom", "deep-nesting", "cr"],
)
def test_odd_text_gets_a_status(text: str) -> None:
    result = ag.run(text)
    assert result.status in (ag.Status.SYNTAX, ag.Status.RUNTIME)
    assert result.message


def test_a_program_that_never_ends_times_out() -> None:
    result = ag.run("while True:\n    pass\n", timeout=0.5)
    assert result.status is ag.Status.TIMEOUT
    assert result.seconds < 2.5


def test_a_program_that_exits_the_process_is_a_crash() -> None:
    result = ag.run("import os\nos._exit(3)\n")
    assert result.status is ag.Status.CRASH
    assert result.message == "the program worker exited with code 3"


def test_a_crash_keeps_only_the_tail_of_a_flooded_stderr() -> None:
    last = "the last words\n"
    program = (
        "import ctypes, sys\n"
        "for _ in range(256):\n"
        "    sys.stderr.write('x' * 4096)\n"
        f"sys.stderr.write({last!r})\n"
        "sys.stderr.flush()\n"
        "ctypes.string_at(0)\n"
    )
    result = ag.run(program)
    assert result.status is ag.Status.CRASH
    head, tail = result.message.split("; its stderr ends:\n")
    # A null read faults as SIGSEGV on both machines; an `abort` would not
    # (fixtures/sandbox/crash-abort).
    assert head == "the program worker was killed by SIGSEGV"
    assert tail == ("x" * (_zygote.STDERR_TAIL_BYTES - len(last))) + last


def test_a_program_cannot_reach_stdout_into_a_message() -> None:
    result = ag.run("print('to stdout')\nimport os\nos._exit(4)\n")
    assert result.message == "the program worker exited with code 4"


# A program that writes a frame of its own to its result pipe, then exits
# before the worker can write the real one.
FORGING = """
import os
def is_open(fd):
    try:
        os.fstat(fd)
    except OSError:
        return False
    return True
os.write(max(fd for fd in range(3, 1024) if is_open(fd)), {frame!r}.encode())
os._exit(0)
"""


def box_bytes() -> bytes:
    import arris
    import arris.build

    model = arris.Model()
    box = arris.build.Solid.box((0, 0, 0), (4, 5, 6), model=model)
    return model.write_body(box.body)


def test_a_forged_ok_frame_is_judged_by_its_body_not_its_claim() -> None:
    body = base64.b64encode(box_bytes()).decode()
    frame = {"status": "ok", "message": "", "refusal": None, "body": body}
    result = ag.run(FORGING.format(frame=json.dumps(frame)))
    ok_box = next(c for c in CASES if c.slug == "ok-box")
    assert fixture_cases.check(result, ok_box.expected) == []
    # Measures are the body worker's: a frame carrying its own is refused.
    forged = dict(frame, measures={"volume": 1.0})
    assert ag.run(FORGING.format(frame=json.dumps(forged))).status is ag.Status.CRASH


def test_a_forged_failure_costs_only_the_program() -> None:
    frame = {"status": "runtime", "message": "forged", "refusal": None, "body": None}
    result = ag.run(FORGING.format(frame=json.dumps(frame)))
    assert (result.status, result.message) == (ag.Status.RUNTIME, "forged")


def _outcome(kind: _isolate.EndKind, value: int, stderr: bytes = b"") -> Outcome:
    return Outcome(_isolate.Ending(kind, value, True), b"", overflow=False, stderr=stderr)


@pytest.mark.parametrize(
    ("outcome", "status", "message"),
    [
        (
            _outcome(_isolate.EndKind.SIGNALLED, 6, b"thread panicked\n"),
            ag.Status.CRASH,
            "the body worker was killed by SIGABRT; its stderr ends:\nthread panicked\n",
        ),
        (
            _outcome(_isolate.EndKind.EXITED, 1),
            ag.Status.CRASH,
            "the body worker exited with code 1",
        ),
        (
            _outcome(_isolate.EndKind.TIMED_OUT, 0),
            ag.Status.TIMEOUT,
            "the body worker ran past the 5.0 s deadline",
        ),
        (
            Outcome(None, b"", overflow=False),
            ag.Status.CRASH,
            "the body worker left no record: the zygote died or stopped answering",
        ),
    ],
    ids=["abort", "exit", "timeout", "no-record"],
)
def test_a_body_worker_that_delivers_nothing_costs_the_program(
    outcome: Outcome, status: ag.Status, message: str
) -> None:
    # No program is known to crash the kernel's reading of a body, so the
    # body worker's endings are built here.
    verdict = _run.body_verdict(outcome, b"body", 5.0)
    assert (verdict.status, verdict.message, verdict.body) == (status, message, None)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"dialect": "nope"},
        {"dialect": "cadquery"},
        {"timeout": 0.0},
        {"timeout": -1.0},
        {"timeout": float("nan")},
        {"timeout": float("inf")},
        {"memory": 0},
        {"memory": -5},
    ],
)
def test_a_callers_mistake_raises(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValueError, match=r"dialect|timeout|memory"):
        ag.run("result = 1", **kwargs)  # type: ignore[arg-type]


def test_the_docstring_example_runs() -> None:
    assert doctest.testmod(_sandbox).failed == 0

"""`run` classifies a program by type and returns a result for every one.

Fixtures under `tests/fixtures/sandbox/` hold one program per status with
expectations by construction (tests/fixture_cases.py).
"""

from __future__ import annotations

import doctest
import hashlib

import pytest

import arris_gym as ag
import fixture_cases
from arris_gym.sandbox import _run

CASES = fixture_cases.load("sandbox")


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.slug)
def test_a_fixture_program_gives_its_expected_result(case: fixture_cases.Case) -> None:
    result = ag.run(case.program)
    assert fixture_cases.check(result, case.expected) == []
    assert result.program_sha256 == hashlib.sha256(case.program.encode()).hexdigest()
    assert result.versions == _run.current_versions()


def test_the_fixtures_cover_the_statuses_the_program_path_reaches() -> None:
    reached = {c.expected["status"] for c in CASES}
    assert reached == {"ok", "syntax", "runtime", "unsupported_api", "arris_refusal"}


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
    assert result.message == "the worker exited with code 3"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"dialect": "cq"},
        {"dialect": "nope"},
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
    assert doctest.testmod(_run).failed == 0

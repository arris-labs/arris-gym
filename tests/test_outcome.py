"""The outcome types hold their invariants (docs/ARCHITECTURE.md §Outcomes)."""

from __future__ import annotations

import doctest
import hashlib
from typing import assert_never

import pytest
from pydantic import ValidationError

from arris_gym import (
    ArrisRefusal,
    BodyRef,
    Dialect,
    ExecResult,
    Measures,
    SandboxUnavailable,
    Status,
    Versions,
)
from arris_gym.cq import UnsupportedApi
from arris_gym.sandbox import outcome

VERSIONS = Versions(arris="0.10.0", numpy="2.3.4", arris_gym="0.1.0")
BOX = Measures(
    volume=6.0,
    area=22.0,
    centroid=(0.5, 1.0, 1.5),
    bounds=((0.0, 0.0, 0.0), (1.0, 2.0, 3.0)),
    faces=6,
    shells=1,
    genus=0,
    face_kinds=(("plane", 6),),
)
REFUSAL = ArrisRefusal(kind="OpDegenerateError", message="degenerate", entities=("f3",))


def make(status: Status, **over: object) -> ExecResult:
    """A result of `status` with the fields that status requires, then `over`."""
    fields: dict[str, object] = {
        "status": status,
        "message": "m",
        "refusal": REFUSAL if status is Status.ARRIS_REFUSAL else None,
        "body": BodyRef.of(b"body") if status in (Status.OK, Status.CHECKER_FAIL) else None,
        "measures": BOX if status is Status.OK else None,
        "violations": (),
        "program_sha256": hashlib.sha256(b"p").hexdigest(),
        "dialect": Dialect.ARRIS,
        "versions": VERSIONS,
        "seconds": 0.1,
    }
    return ExecResult.model_validate(fields | over)


def describe(status: Status) -> str:
    """A dispatch over every status, closed by `assert_never` (gym.md)."""
    match status:
        case Status.OK:
            return "valid body"
        case Status.SYNTAX | Status.RUNTIME | Status.UNSUPPORTED_API | Status.TIMEOUT:
            return "no body, no refusal"
        case Status.ARRIS_REFUSAL:
            return "refusal"
        case Status.CHECKER_FAIL:
            return "invalid body"
        case Status.CRASH:
            return "died"
        case _ as unreachable:
            assert_never(unreachable)


@pytest.mark.parametrize("status", list(Status))
def test_every_status_builds_and_is_dispatched(status: Status) -> None:
    assert make(status).status is status
    assert describe(status)


def test_there_are_eight_statuses_and_two_dialects() -> None:
    assert [s.value for s in Status] == [
        "ok", "syntax", "runtime", "unsupported_api",
        "arris_refusal", "checker_fail", "timeout", "crash",
    ]  # fmt: skip
    assert [d.value for d in Dialect] == ["arris", "cq"]


@pytest.mark.parametrize(
    "bad",
    [
        {"status": Status.OK, "body": None, "measures": None},
        {"status": Status.OK, "measures": None},
        {"status": Status.CHECKER_FAIL, "measures": BOX},
        {"status": Status.SYNTAX, "body": BodyRef.of(b"x")},
        {"status": Status.RUNTIME, "refusal": REFUSAL},
        {"status": Status.ARRIS_REFUSAL, "refusal": None},
        {"status": Status.OK, "violations": ("v",)},
    ],
)
def test_a_result_that_contradicts_its_status_is_refused(bad: dict[str, object]) -> None:
    over = dict(bad)
    status = over.pop("status")
    assert isinstance(status, Status)
    with pytest.raises(ValidationError):
        make(status, **over)


def test_a_checker_fail_carries_its_violations_and_a_result_is_frozen() -> None:
    failed = make(Status.CHECKER_FAIL, violations=("open shell",))
    assert failed.violations == ("open shell",)
    with pytest.raises(ValidationError):
        failed.message = "other"


def test_a_body_ref_refuses_a_digest_that_is_not_its_bytes() -> None:
    assert BodyRef.of(b"abc").sha256 == hashlib.sha256(b"abc").hexdigest()
    with pytest.raises(ValidationError):
        BodyRef(data=b"abc", sha256="0" * 64)


def test_a_result_round_trips_through_json() -> None:
    result = make(Status.OK)
    assert ExecResult.model_validate_json(result.model_dump_json()) == result


def test_the_docstring_example_runs() -> None:
    assert doctest.testmod(outcome, extraglobs={"hashlib": hashlib}).failed == 0


def test_the_exceptions_are_exported() -> None:
    assert issubclass(SandboxUnavailable, RuntimeError)
    assert str(UnsupportedApi("Workplane.loft")) == "Workplane.loft"

"""The oracle worker under the warden (ADR-0004): M0's hostile corpus, contained.

Needs the oracle environment (`uv sync --project tools/oracle`), so it is
marked `oracle` and left out of the gate: `uv run pytest -m oracle`. Each
program goes through the zygote as an exec job, as `tools/oracle_run.py`
sends it, and the test reads the raw outcome: the warden's `Ending` and the
worker's one JSON frame.
"""

from __future__ import annotations

import json
import signal
import time
from collections.abc import Iterator
from typing import Any

import pytest

import fixture_cases
import oracle_run
from arris_gym.sandbox import _exec
from arris_gym.sandbox._isolate import EndKind
from arris_gym.sandbox._zygote import Outcome, Zygote

pytestmark = pytest.mark.oracle

HOSTILE = {c.slug: c for c in fixture_cases.load("sandbox")}
# Room for the oracle's start-up, about 1.5 s, and a boolean.
TIMEOUT = 30.0
# The deadline the infinite loop runs to, and the most its run may take.
LOOP_DEADLINE = 1.0
LOOP_BOUND = 2.0
# A deadline the oracle's start-up (about 1.5 s: Python, cadquery, OCP)
# leaves the program well inside.
REACHED_DEADLINE = 5.0
# A box with a through hole and filleted vertical edges, then a boolean on a
# sphere: cadquery runs each boolean on Open CASCADE's thread pool.
BOOLEAN = (
    "import cadquery as cq\n"
    "part = cq.Workplane().box(10, 10, 10).faces('>Z').workplane().hole(3)\n"
    "part = part.edges('|Z').fillet(1).cut(cq.Workplane().sphere(6))\n"
    "show_object(part)\n"
)


@pytest.fixture(scope="module")
def zygote() -> Iterator[Zygote]:
    with Zygote() as z:
        yield z


@pytest.fixture(scope="module")
def oracle() -> _exec.ExecSpec:
    return oracle_run.spec()


def run(zygote: Zygote, oracle: _exec.ExecSpec, program: str) -> Outcome:
    return oracle_run.run_one(zygote, oracle, program, timeout=TIMEOUT)


def report(outcome: Outcome) -> dict[str, Any]:
    """The frame of a worker that ran armed to a clean exit, as JSON."""
    assert outcome.ending is not None
    assert (outcome.ending.kind, outcome.ending.value, outcome.ending.armed) == (
        EndKind.EXITED,
        0,
        True,
    ), outcome.stderr
    frame: dict[str, Any] = json.loads(outcome.data)
    return frame


def test_a_boolean_runs_on_one_thread_under_the_limits(
    zygote: Zygote, oracle: _exec.ExecSpec
) -> None:
    frame = report(run(zygote, oracle, BOOLEAN))
    assert frame["status"] == "ok", frame["message"]
    assert frame["measures"]["solids"] == 1


@pytest.mark.parametrize(
    "slug", ["hostile-fork-bomb", "hostile-memory-1gib", "hostile-connect", "hostile-read-outside"]
)
def test_a_hostile_program_costs_one_runtime_status(
    zygote: Zygote, oracle: _exec.ExecSpec, slug: str
) -> None:
    case = HOSTILE[slug]
    frame = report(run(zygote, oracle, case.program))
    assert (frame["status"], frame["message"]) == ("runtime", case.expected["message"])


def test_a_file_of_the_repository_cannot_be_read(zygote: Zygote, oracle: _exec.ExecSpec) -> None:
    frame = report(run(zygote, oracle, f"open({__file__!r}).read()\n"))
    assert frame["status"] == "runtime"
    assert frame["message"].startswith("PermissionError: [Errno 13]")


def test_nothing_is_written_not_even_beside_the_worker(
    zygote: Zygote, oracle: _exec.ExecSpec
) -> None:
    planted = oracle_run.ORACLE / "planted"
    frame = report(run(zygote, oracle, f"open({str(planted)!r}, 'w')\n"))
    # The read-only mount answers before Landlock does (ADR-0002).
    assert (frame["status"], frame["message"]) == (
        "runtime",
        f"OSError: [Errno 30] Read-only file system: {str(planted)!r}",
    )
    assert not (oracle_run.ORACLE / "planted").exists()


def test_no_other_executable_runs(zygote: Zygote, oracle: _exec.ExecSpec) -> None:
    frame = report(run(zygote, oracle, "import os\nos.execv('/usr/bin/true', ['true'])\n"))
    assert frame["status"] == "runtime"
    assert frame["message"] == "PermissionError: [Errno 13] Permission denied"


def test_an_exit_without_a_report_leaves_no_frame(zygote: Zygote, oracle: _exec.ExecSpec) -> None:
    outcome = run(zygote, oracle, HOSTILE["crash-exit-zero"].program)
    assert outcome.ending is not None
    assert (outcome.ending.kind, outcome.ending.value, outcome.ending.armed) == (
        EndKind.EXITED,
        0,
        True,
    )
    assert outcome.data == b""


def test_a_segfault_ends_the_worker_by_its_signal(zygote: Zygote, oracle: _exec.ExecSpec) -> None:
    outcome = run(zygote, oracle, HOSTILE["crash-segfault"].program)
    assert outcome.ending is not None
    assert (outcome.ending.kind, outcome.ending.value, outcome.ending.armed) == (
        EndKind.SIGNALLED,
        signal.SIGSEGV,
        True,
    )
    assert outcome.data == b""


def test_an_infinite_loop_times_out_within_two_seconds(
    zygote: Zygote, oracle: _exec.ExecSpec
) -> None:
    start = time.monotonic()
    outcome = oracle_run.run_one(
        zygote, oracle, HOSTILE["timeout-infinite-loop"].program, timeout=LOOP_DEADLINE
    )
    assert time.monotonic() - start < LOOP_BOUND
    assert outcome.ending is not None
    assert outcome.ending.kind is EndKind.TIMED_OUT
    assert outcome.data == b""


def test_the_loop_itself_is_killed_at_its_deadline(zygote: Zygote, oracle: _exec.ExecSpec) -> None:
    # Past the oracle's start-up, so that the program reaches its loop and
    # says so on stderr before the warden ends it.
    program = (
        "import sys\nsys.stderr.write('looping\\n')\nsys.stderr.flush()\nwhile True:\n    pass\n"
    )
    start = time.monotonic()
    outcome = oracle_run.run_one(zygote, oracle, program, timeout=REACHED_DEADLINE)
    assert time.monotonic() - start < REACHED_DEADLINE + LOOP_BOUND - LOOP_DEADLINE
    assert outcome.ending is not None
    assert outcome.ending.kind is EndKind.TIMED_OUT
    assert outcome.stderr.endswith(b"looping\n")

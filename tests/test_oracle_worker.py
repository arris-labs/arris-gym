"""The oracle worker under the warden (ADR-0004): M0's hostile corpus, contained.

Needs the oracle environment (`uv sync --project tools/oracle`), so it is
marked `oracle` and left out of the gate: `uv run pytest -m oracle`. Each
program goes through the zygote as an exec job, as `tools/oracle_run.py`
sends it, and the test reads the raw outcome: the warden's `Ending` and the
worker's one JSON frame. The oracle zygote (ADR-0013) is held to the same:
each hostile program costs one report, the next program on the same zygote
sees none of it, and a report is the same bytes as a fresh worker's.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import signal
import time
from collections.abc import Iterator
from typing import Any

import pytest

import fixture_cases
import oracle_run
from arris_gym.fidelity import parse_outcome
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
# The most a trivial program may take on an oracle zygote, start to report: a
# tenth of the fresh worker's import (ADR-0013 measured about 20 ms).
ZYGOTE_START_BOUND = 0.15
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


@pytest.fixture(scope="module")
def oracle_zygote(zygote: Zygote, oracle: _exec.ExecSpec) -> Iterator[oracle_run.OracleZygote]:
    with oracle_run.OracleZygote(zygote, oracle) as z:
        yield z


def test_run_report_parses_the_real_frame(oracle_zygote: oracle_run.OracleZygote) -> None:
    from arris_gym.fidelity import OracleStatus, program_sha256

    program = "import cadquery as cq\nresult = cq.Workplane().box(2, 3, 4)\n"
    report = oracle_run.run_report(oracle_zygote, program, timeout=TIMEOUT)
    assert report.status is OracleStatus.OK, report.message
    assert report.measures is not None
    assert report.measures.faces == 6
    assert report.measures.solids == 1
    assert report.program_sha256 == program_sha256(program)
    assert report.versions is not None
    assert report.versions.cadquery == "2.3.0"


def test_the_step_text_is_the_same_bytes_on_every_run_and_holds_its_hash(
    zygote: Zygote, oracle: _exec.ExecSpec, oracle_zygote: oracle_run.OracleZygote
) -> None:
    # A fresh worker and a zygote's child, so two processes' translator
    # counters and two clocks: the blanked text is equal, and its data
    # section hashes to `step_sha256`.
    program = "import cadquery as cq\nresult = cq.Workplane().box(2, 3, 4)\n"
    a = parse_outcome(run(zygote, oracle, program), program, timeout=TIMEOUT, seconds=0.0)
    b = oracle_run.run_report(oracle_zygote, program, timeout=TIMEOUT)
    assert a.step is not None
    assert a.step == b.step
    assert "FILE_NAME('Open CASCADE Shape Model','',(" in a.step
    assert "'Open CASCADE STEP translator 7.9 N'" in a.step
    data = a.step[a.step.index("DATA;") :].encode("ascii")
    assert a.step_sha256 == hashlib.sha256(data).hexdigest()
    assert a.step.startswith("ISO-10303-21;")
    assert a.step.rstrip().endswith("END-ISO-10303-21;")


def test_run_many_keeps_submission_order() -> None:
    from arris_gym.fidelity import OracleStatus

    texts = ["def (:\n", "raise ValueError('boom')\n", "x = 1\n"]
    reports = oracle_run.run_many(texts, timeout=TIMEOUT, workers=3)
    assert [r.status for r in reports] == [
        OracleStatus.SYNTAX,
        OracleStatus.RUNTIME,
        OracleStatus.NO_RESULT,
    ]
    assert reports[1].message == "ValueError: boom"


def test_the_command_writes_one_row_per_program_in_order(tmp_path: Any) -> None:
    files = []
    for name, text in [("b.py", "def (:\n"), ("a.py", "x = 1\n")]:
        (tmp_path / name).write_text(text)
        files.append(str(tmp_path / name))
    out = tmp_path / "oracle.jsonl"
    assert oracle_run.main([*files, "--out", str(out), "--timeout", str(TIMEOUT)]) == 0
    rows = [json.loads(line) for line in out.read_text().splitlines()]
    assert [(r["path"], r["report"]["status"]) for r in rows] == [
        (files[0], "syntax"),
        (files[1], "no_result"),
    ]


# --- The oracle zygote (ADR-0013) ----------------------------------------------

# Run after each hostile program on the same zygote: it fails with what it
# saw of an earlier program. A module's state, a planted module, the file a
# program tried to write, and a task still held (RLIMIT_NPROC 4: warden,
# zygote and this child leave it one fork, which a leftover would take).
PLANTED = "/tmp/arris-gym-oracle-planted"
PROBE = (
    "import os, sys\n"
    "import cadquery as cq\n"
    "seen = []\n"
    "if hasattr(cq, 'planted') or 'planted' in sys.modules or cq.Workplane.box is None:\n"
    "    seen.append('state')\n"
    f"if os.path.exists({PLANTED!r}):\n"
    "    seen.append('file')\n"
    "try:\n"
    "    pid = os.fork()\n"
    "except BlockingIOError:\n"
    "    seen.append('tasks')\n"
    "else:\n"
    "    if pid == 0:\n"
    "        os._exit(0)\n"
    "    os.waitpid(pid, 0)\n"
    "raise ValueError(f'seen {seen}')\n"
)
CLEAN = ("runtime", "ValueError: seen []")
# A program that leaves a child behind, in its own session, and reports.
LEAVES_A_CHILD = (
    "import os, time\n"
    "if os.fork() == 0:\n"
    "    os.setsid()\n"
    "    time.sleep(1000)\n"
    "raise ValueError('left a child')\n"
)
STATE = (
    "import sys\n"
    "import cadquery as cq\n"
    "cq.planted = 1\n"
    "cq.Workplane.box = None\n"
    "sys.modules['planted'] = cq\n"
    "raise ValueError('planted')\n"
)
WRITE_OUTSIDE = f"open({PLANTED!r}, 'w').write('x')\n"


def zygote_report(outcome: Outcome) -> tuple[str, str]:
    frame = report(outcome)
    return frame["status"], frame["message"]


def test_the_probe_is_clean_on_a_fresh_zygote(oracle_zygote: oracle_run.OracleZygote) -> None:
    assert zygote_report(oracle_zygote.run(PROBE, timeout=TIMEOUT)) == CLEAN


@pytest.mark.parametrize(
    ("program", "expected"),
    [
        (
            HOSTILE["hostile-fork-bomb"].program,
            ("runtime", HOSTILE["hostile-fork-bomb"].expected["message"]),
        ),
        (LEAVES_A_CHILD, ("runtime", "ValueError: left a child")),
        (STATE, ("runtime", "ValueError: planted")),
        (
            WRITE_OUTSIDE,
            ("runtime", f"OSError: [Errno 30] Read-only file system: {PLANTED!r}"),
        ),
        (
            HOSTILE["hostile-memory-1gib"].program,
            ("runtime", HOSTILE["hostile-memory-1gib"].expected["message"]),
        ),
    ],
    ids=["fork-bomb", "leaves-a-child", "state-in-a-module", "write-outside", "memory-1gib"],
)
def test_a_hostile_program_costs_one_report_and_the_next_sees_none_of_it(
    oracle_zygote: oracle_run.OracleZygote, program: str, expected: tuple[str, str]
) -> None:
    starts = oracle_zygote.starts
    assert zygote_report(oracle_zygote.run(program, timeout=TIMEOUT)) == expected
    assert zygote_report(oracle_zygote.run(PROBE, timeout=TIMEOUT)) == CLEAN
    assert oracle_zygote.starts == starts, "the zygote was replaced"


@pytest.mark.parametrize(
    ("slug", "kind", "value"),
    [
        ("crash-exit-zero", EndKind.EXITED, 0),
        ("crash-segfault", EndKind.SIGNALLED, signal.SIGSEGV),
        ("timeout-infinite-loop", EndKind.TIMED_OUT, 0),
    ],
)
def test_a_child_that_ends_without_a_report_costs_that_report_alone(
    oracle_zygote: oracle_run.OracleZygote, slug: str, kind: EndKind, value: int
) -> None:
    starts = oracle_zygote.starts
    timeout = LOOP_DEADLINE if kind is EndKind.TIMED_OUT else TIMEOUT
    start = time.monotonic()
    outcome = oracle_zygote.run(HOSTILE[slug].program, timeout=timeout)
    assert time.monotonic() - start < timeout + LOOP_BOUND
    assert outcome.ending is not None
    assert (outcome.ending.kind, outcome.ending.value, outcome.ending.armed) == (kind, value, True)
    assert outcome.data == b""
    assert zygote_report(oracle_zygote.run(PROBE, timeout=TIMEOUT)) == CLEAN
    assert oracle_zygote.starts == starts, "the zygote was replaced"


@pytest.mark.parametrize("slug", ["hostile-connect", "hostile-read-outside"])
def test_a_zygotes_child_keeps_the_workers_limits(
    oracle_zygote: oracle_run.OracleZygote, slug: str
) -> None:
    case = HOSTILE[slug]
    assert zygote_report(oracle_zygote.run(case.program, timeout=TIMEOUT)) == (
        "runtime",
        case.expected["message"],
    )


def test_a_zygotes_child_cannot_run_another_executable(
    oracle_zygote: oracle_run.OracleZygote,
) -> None:
    program = "import os\nos.execv('/usr/bin/true', ['true'])\n"
    assert zygote_report(oracle_zygote.run(program, timeout=TIMEOUT)) == (
        "runtime",
        "PermissionError: [Errno 13] Permission denied",
    )


def test_a_zygotes_report_is_a_fresh_workers_bytes(
    zygote: Zygote, oracle: _exec.ExecSpec, oracle_zygote: oracle_run.OracleZygote
) -> None:
    for program in (BOOLEAN, "def (:\n", "raise ValueError('boom')\n", "x = 1\n"):
        fresh = run(zygote, oracle, program)
        forked = oracle_zygote.run(program, timeout=TIMEOUT)
        assert forked.data == fresh.data


def test_a_zygote_that_died_is_replaced_for_the_next_program(
    zygote: Zygote, oracle: _exec.ExecSpec
) -> None:
    with oracle_run.OracleZygote(zygote, oracle) as z:
        assert zygote_report(z.run(PROBE, timeout=TIMEOUT)) == CLEAN
        z._stop()  # as when its record never came: the channel closed, the zygote gone
        assert zygote_report(z.run(PROBE, timeout=TIMEOUT)) == CLEAN
        assert z.starts == 2


def test_a_program_in_a_zygotes_child_starts_in_well_under_the_import(
    oracle_zygote: oracle_run.OracleZygote,
) -> None:
    # ADR-0013's measure: a fresh worker spends about 1.5 s importing before
    # a program's first line; a zygote's child starts in milliseconds. The
    # bound is a tenth of the import, far above what was measured.
    oracle_zygote.run("x = 1\n", timeout=TIMEOUT)
    start = time.monotonic()
    oracle_zygote.run("x = 1\n", timeout=TIMEOUT)
    assert time.monotonic() - start < ZYGOTE_START_BOUND


def test_the_slices_rows_through_oracle_zygotes_are_c1s_bytes() -> None:
    # ADR-0013's acceptance: `oracle.jsonl` was written by fresh workers
    # (ADR-0004); through oracle zygotes it is the same bytes. Reads the
    # pinned corpus: the `[corpus]` extra and the Hugging Face cache or network.
    pytest.importorskip("pyarrow")
    pytest.importorskip("huggingface_hub")
    c1 = pathlib.Path(__file__).parent / "fixtures" / "c1"
    stems = oracle_run.read_slice(c1 / "slice.txt")
    programs, reports = oracle_run.slice_reports(stems)
    text = oracle_run.rows_text(oracle_run.slice_rows(programs, reports))
    assert text == (c1 / "oracle.jsonl").read_text(encoding="utf-8")

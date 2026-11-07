"""The zygote forks a clean worker per job and outlives none of its failures.

`sandbox/_zygote.py` (ADR-0001, ADR-0002): a clean start, the job socket and
its descriptors, reaping, replacement, and `SandboxUnavailable`.
"""

from __future__ import annotations

import contextlib
import json
import os
import pathlib
import signal
import subprocess
import sys
import textwrap
import threading
import time
from collections.abc import Iterator

import arris
import arris.build
import pytest

from arris_gym.sandbox import _isolate, _zygote
from arris_gym.sandbox._frame import ProgramFrame
from arris_gym.sandbox._zygote import JobKind, Outcome, Zygote

MEMORY = 512 * 2**20  # the roadmap's default memory limit
TIMEOUT = 10.0  # far past every program below: a hang fails, never a slow machine
CLEAN_EXIT = _isolate.Ending(_isolate.EndKind.EXITED, 0, True)

BOX_LESS_CYLINDER = """
import arris.build as b
result = b.Solid.box((0, 0, 0), (10, 10, 10)).cut(b.Solid.cylinder((5, 5, -1), (0, 0, 1), 2, 12))
"""
OTHER_BOX = """
import arris.build as b
result = b.Solid.box((0, 0, 0), (3, 4, 5))
"""
# A program that writes `report` as JSON to its result pipe: the one
# descriptor above stdio the worker holds.
REPORTING = """
import json, os
def report(value):
    fd = max(fd for fd in range(3, 1024) if _open(fd))
    os.write(fd, json.dumps(value).encode())
def _open(fd):
    try:
        os.fstat(fd)
    except OSError:
        return False
    return True
"""


def boxes_in_order(names: str) -> str:
    """A program fusing one box per name, in the order `names` gives them."""
    return f"""
import arris.build as b
offsets = {{"a": 0, "b": 1, "c": 2, "d": 3}}
parts = [b.Solid.box((10 * offsets[n], 0, 0), (10 * offsets[n] + 12, 10, 10)) for n in {names}]
result = parts[0].fuse(*parts[1:])
"""


def run(zygote: Zygote, program: str, timeout: float = TIMEOUT) -> Outcome:
    deadline = time.monotonic() + timeout
    return zygote.execute(JobKind.PROGRAM, program.encode(), deadline=deadline, memory=MEMORY)


def body(zygote: Zygote, program: str) -> bytes:
    """The body bytes of a program that ran to a clean exit, from its frame."""
    outcome = run(zygote, program)
    assert outcome.ending == CLEAN_EXIT, outcome
    frame = ProgramFrame.model_validate_json(outcome.data)
    assert frame.body is not None, frame
    return frame.body


def threads(pid: int) -> int:
    status = pathlib.Path(f"/proc/{pid}/status").read_text()
    return int(status.split("Threads:")[1].split()[0])


def children(pid: int) -> list[int]:
    return [int(c) for c in pathlib.Path(f"/proc/{pid}/task/{pid}/children").read_text().split()]


def first_warden(pid: int) -> int:
    """The first warden the zygote `pid` forks, once it has forked its worker.

    Waited for at most TIMEOUT. A warden with a worker has closed every
    descriptor it was not given.
    """
    give_up = time.monotonic() + TIMEOUT
    while time.monotonic() < give_up:
        for warden in children(pid):
            with contextlib.suppress(FileNotFoundError):
                if children(warden):
                    return warden
    raise AssertionError("the zygote forked no warden")


def dead(pid: int) -> None:
    """Wait, at most TIMEOUT, until the killed child `pid` is a zombie.

    A job sent between the kill and the death is in flight, and lost.
    """
    give_up = time.monotonic() + TIMEOUT
    while time.monotonic() < give_up:
        if pathlib.Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0] == "Z":
            return
    raise AssertionError(f"{pid} did not die")


@pytest.fixture(scope="module")
def zygote() -> Iterator[Zygote]:
    with Zygote() as z:
        yield z


def test_the_zygote_starts_clean_and_stays_on_one_thread(zygote: Zygote) -> None:
    environ = pathlib.Path(f"/proc/{zygote.pid}/environ").read_bytes()
    entries = sorted(e.decode() for e in environ.split(b"\0") if e)
    assert entries == sorted(f"{k}={v}" for k, v in _zygote.ENVIRONMENT.items())
    assert threads(zygote.pid) == 1
    body(zygote, BOX_LESS_CYLINDER)
    assert threads(zygote.pid) == 1


def test_programs_through_one_zygote_give_a_fresh_models_bytes(zygote: Zygote) -> None:
    first = body(zygote, BOX_LESS_CYLINDER)
    body(zygote, OTHER_BOX)
    assert body(zygote, BOX_LESS_CYLINDER) == first
    # The zygote built nothing: each worker's bytes are a fresh model's.
    model = arris.Model()
    fresh = arris.build.Solid.box((0, 0, 0), (10, 10, 10), model=model).cut(
        arris.build.Solid.cylinder((5, 5, -1), (0, 0, 1), 2, 12, model=model)
    )
    assert first == fresh.model.write_body(fresh.body)


def test_a_set_order_program_gives_equal_bytes_across_zygotes(zygote: Zygote) -> None:
    program = boxes_in_order('{"a", "b", "c", "d"}')
    with Zygote() as other:
        assert body(zygote, program) == body(other, program)
    # The test has teeth: the order moves the bytes, and the hash seed the order.
    assert body(zygote, boxes_in_order('"abcd"')) != body(zygote, boxes_in_order('"dcab"'))
    orders = {
        subprocess.run(
            [sys.executable, "-c", "print(list({'a', 'b', 'c', 'd'}))"],
            env={"PYTHONHASHSEED": seed},
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        for seed in ("1", "2", "3")
    }
    assert len(orders) > 1


def test_a_worker_cannot_reach_the_job_socket(zygote: Zygote) -> None:
    program = REPORTING + textwrap.dedent(f"""
        import stat, threading
        def sockets():
            return [fd for fd in range(1024) if _open(fd) and stat.S_ISSOCK(os.fstat(fd).st_mode)]
        def zygote_fds():
            try:
                return os.listdir("/proc/{zygote.pid}/fd")
            except OSError as e:
                return [type(e).__name__]
        report({{"sockets": sockets(), "zygote_fds": zygote_fds()}})
        """)
    outcome = run(zygote, program)
    assert outcome.ending == CLEAN_EXIT, outcome
    # The program's report, then the worker's own frame (no `result` bound).
    report, _ = json.JSONDecoder().raw_decode(outcome.data.decode())
    assert report == {"sockets": [], "zygote_fds": ["PermissionError"]}


def test_a_warden_holds_no_descriptor_of_the_zygotes(zygote: Zygote) -> None:
    thread = threading.Thread(target=lambda: run(zygote, "import time\ntime.sleep(2)\n"))
    thread.start()
    warden = first_warden(zygote.pid)
    held = []
    for fd in os.listdir(f"/proc/{warden}/fd"):
        with contextlib.suppress(FileNotFoundError):  # closed since the listing
            held.append(os.readlink(f"/proc/{warden}/fd/{fd}").split(":")[0])
    thread.join()
    assert "socket" not in held, held


def test_a_result_past_the_cap_is_dropped_whole_and_ends_the_writer(zygote: Zygote) -> None:
    program = REPORTING + textwrap.dedent("""
        fd = max(fd for fd in range(3, 1024) if _open(fd))
        chunk = bytes(2**20)
        while True:
            os.write(fd, chunk)
        """)
    start = time.monotonic()
    outcome = run(zygote, program)
    assert time.monotonic() - start < TIMEOUT / 2  # ended by the closed pipe, not the deadline
    assert outcome.overflow is True
    assert outcome.data == b""
    assert outcome.ending == _isolate.Ending(_isolate.EndKind.EXITED, 1, True)  # BrokenPipeError


def test_a_zygote_killed_mid_run_costs_its_in_flight_jobs_only() -> None:
    with Zygote() as zygote:
        expected = body(zygote, OTHER_BOX)
        first = zygote.pid
        outcomes: list[Outcome] = []
        thread = threading.Thread(
            target=lambda: outcomes.append(run(zygote, "import time\ntime.sleep(1)\n" + OTHER_BOX))
        )
        start = time.monotonic()
        thread.start()
        first_warden(first)
        os.kill(first, signal.SIGKILL)
        dead(first)
        assert body(zygote, OTHER_BOX) == expected
        assert zygote.pid != first
        thread.join()
        assert time.monotonic() - start < TIMEOUT + _zygote.BACKSTOP
        # Its warden outlived the zygote and kept the deadline: lost at worst.
        (in_flight,) = outcomes
        assert in_flight.ending in (None, CLEAN_EXIT), in_flight
        # A zygote dead between jobs costs nothing.
        os.kill(zygote.pid, signal.SIGKILL)
        dead(zygote.pid)
        assert body(zygote, OTHER_BOX) == expected


def test_a_zygote_that_stops_answering_is_given_up_at_the_backstop() -> None:
    with Zygote() as zygote:
        stopped = zygote.pid
        os.kill(stopped, signal.SIGSTOP)
        start = time.monotonic()
        outcome = run(zygote, OTHER_BOX, timeout=0.5)
        waited = time.monotonic() - start
        assert outcome == Outcome(None, b"", overflow=False)
        assert 0.5 + _zygote.BACKSTOP <= waited < 0.5 + 2 * _zygote.BACKSTOP
        assert body(zygote, OTHER_BOX)
        assert zygote.pid != stopped


# A caller in a user namespace that may create no more of them: the warden's
# `unshare` fails as it would under a container's seccomp profile.
NO_NAMESPACES = """
import os
uid, gid = os.getuid(), os.getgid()
os.unshare(os.CLONE_NEWUSER)
for name, line in (("setgroups", "deny"), ("uid_map", f"0 {uid} 1"), ("gid_map", f"0 {gid} 1")):
    with open(f"/proc/self/{name}", "w") as f:
        f.write(line)
with open("/proc/sys/user/max_user_namespaces", "w") as f:
    f.write("0")
from arris_gym.sandbox._zygote import SandboxUnavailable, Zygote
try:
    Zygote()
except SandboxUnavailable as e:
    print(e)
"""


def test_the_sandbox_is_unavailable_when_its_probe_fails() -> None:
    done = subprocess.run(
        [sys.executable, "-c", NO_NAMESPACES], capture_output=True, text=True, timeout=60
    )
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == (
        "the warden could not enter its namespaces: No space left on device"
    )


def test_a_status_record_is_whole_or_absent() -> None:
    record = _isolate._STATUS.pack(_isolate.EndKind.TIMED_OUT, 0, 1)
    assert _isolate.parse_ending(record) == _isolate.Ending(_isolate.EndKind.TIMED_OUT, 0, True)
    assert _isolate.parse_ending(record[:-1]) is None
    assert _isolate.parse_ending(_isolate._STATUS.pack(99, 0, 1)) is None

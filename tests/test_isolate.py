"""A function under `sandbox._isolate` costs its own end and nothing else (ADR-0002).

Each case runs in a clean interpreter (`tests/isolate_cases.py`), which forks
the warden as the zygote will.
"""

from __future__ import annotations

import errno
import json
import os
import pathlib
import platform
import socket
import subprocess
import sys
from typing import Any

import pytest

from arris_gym.sandbox import _isolate

CASES = pathlib.Path(__file__).resolve().parent / "isolate_cases.py"
# The zygote's environment (ADR-0002), and nothing else from the caller's.
CLEAN = {"OPENBLAS_NUM_THREADS": "1", "PYTHONHASHSEED": "0"}
# How long a case may take before the test gives up on it: far past every
# expectation below, so that a hang fails the test instead of stalling it.
CASE_TIMEOUT = 30.0


def case(name: str, *args: str, **env: str) -> dict[str, Any]:
    """Run one case; its ending, report and timings."""
    done = subprocess.run(
        [sys.executable, str(CASES), name, *args],
        env={**CLEAN, **env},
        capture_output=True,
        text=True,
        timeout=CASE_TIMEOUT,
        check=True,
    )
    result: dict[str, Any] = json.loads(done.stdout)
    return result


def ok(result: dict[str, Any]) -> Any:
    """The report of a case that ran armed to a clean exit."""
    assert (result["kind"], result["value"], result["armed"]) == ("EXITED", 0, True), result
    return result["report"]


def test_a_build_and_a_lazy_import_work_under_isolation() -> None:
    report = ok(case("build"))
    assert report["ok"] is True
    assert report["bytes"] > 0
    assert report["xml"] == "xml.dom.minidom"


def test_a_connect_to_a_public_address_is_unreachable() -> None:
    assert ok(case("connect_inet")) == ["OSError", errno.ENETUNREACH]


def test_a_unix_socket_outside_cannot_be_reached(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "listener.sock"
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
        listener.bind(str(path))
        listener.listen()
        listener.setblocking(False)
        report = ok(case("connect_unix", str(path)))
        with pytest.raises(BlockingIOError):
            listener.accept()
    refused = ["PermissionError", errno.EACCES]
    assert report == {"connect": refused, "socketpair": refused, "netlink": refused}


def test_nothing_outside_the_reach_is_read(tmp_path: pathlib.Path) -> None:
    secret = tmp_path / "target.json"
    secret.write_text("{}", encoding="utf-8")
    report = ok(case("read_outside", str(secret)))
    refused = ["PermissionError", errno.EACCES]
    assert report["outside"] == refused
    assert report["listdir"] == refused
    assert report["passwd"] == refused
    assert report["inside"][0] == "ok"
    # The repository beside the package is outside too.
    assert ok(case("read_outside", str(CASES)))["outside"] == refused


def test_nothing_is_written_and_no_limit_is_lifted(tmp_path: pathlib.Path) -> None:
    victim = tmp_path / "victim"
    victim.write_bytes(b"kept")
    before = victim.stat()
    report = ok(case("write_outside", str(tmp_path)))
    after = victim.stat()
    assert victim.read_bytes() == b"kept"
    assert (after.st_mode, after.st_mtime_ns) == (before.st_mode, before.st_mtime_ns)
    assert os.listxattr(victim) == []
    assert sorted(p.name for p in tmp_path.iterdir()) == ["victim"]
    for action in ("create", "append", "chmod", "utime", "setxattr", "truncate", "unlink"):
        assert report[action][0] in ("OSError", "PermissionError"), (action, report[action])
    for action in ("memfd", "keyctl"):
        assert report[action] == ["PermissionError", errno.EACCES], action
    for action in ("remount", "nested"):
        assert report[action] == ["PermissionError", errno.EPERM], action
    for limit in ("rlimit_as", "rlimit_nproc", "rlimit_core"):
        assert report[limit] == ["ValueError", None], limit
    assert report["core"] == [0, 0]


def test_a_fork_bomb_is_bounded() -> None:
    result = case("fork_bomb")
    # The warden and the worker count against the limit; the rest are forks.
    assert ok(result) == {"forks": _isolate.NPROC_LIMIT - 2, "error": ["BlockingIOError", 11]}
    assert result["released"] < 1.0  # every fork died with the worker


def test_a_setsid_descendant_holding_a_pipe_dies_with_pid_1() -> None:
    result = case("setsid_descendant")
    assert ok(result) == {"forked": True}
    # The descendant sleeps a minute holding the report pipe: the pipe's end
    # within a second of the worker's is the descendant's death.
    assert result["seconds"] < 1.0
    assert result["released"] < 1.0
    assert result["held"] is False


def test_a_worker_ignoring_signals_dies_at_its_deadline() -> None:
    result = case("stubborn", ISOLATE_TIMEOUT="1.0")
    assert (result["kind"], result["armed"]) == ("TIMED_OUT", True)
    assert 1.0 <= result["seconds"] < 2.0


def test_1_gib_is_refused_under_512_mib() -> None:
    report = ok(case("allocate"))
    assert report["gib"] == ["MemoryError", None]
    assert report["mib_100"] == ["ok", 100 * 2**20]


def test_descriptors_are_closed_and_stdio_detached() -> None:
    report = ok(case("descriptors"))
    assert report["extra"] not in report["open"]
    assert report["open"][:3] == [0, 1, 2]
    assert len(report["open"]) == 4  # stdio and the report pipe, nothing else
    assert report["stdin"] == ""
    assert report["tty"] is False
    assert report["session_leader"] is True
    assert report["pid"] == 1


def test_an_exception_and_an_exit_code_are_relayed() -> None:
    raised, exited = case("raises"), case("exits", "7")
    assert (raised["kind"], raised["value"], raised["report"]) == ("EXITED", 1, None)
    assert (exited["kind"], exited["value"], exited["armed"]) == ("EXITED", 7, True)


def test_a_worker_that_cannot_isolate_itself_runs_nothing() -> None:
    result = case("build", ISOLATE_MISSING_ROOT="/nonexistent/arris-gym")
    assert result["armed"] is False
    assert result["report"] is None


@pytest.mark.parametrize("machine", sorted(_isolate._ARCHES))
def test_every_seccomp_path_ends_in_a_verdict(machine: str) -> None:
    program = _isolate.seccomp_program(_isolate._ARCHES[machine])
    ret = 0x06
    assert program[-1][0] == ret
    for i, (code, jt, jf, _) in enumerate(program):
        if code != ret and code & 0x07 == 0x05:  # a jump: both targets inside
            assert i + 1 + max(jt, jf) < len(program)


def test_this_machine_is_supported() -> None:
    assert platform.machine() in _isolate._ARCHES
    assert _isolate.landlock_abi() >= 1

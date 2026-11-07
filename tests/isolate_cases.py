"""Hostile functions run under `sandbox._isolate`, one per invocation.

Run by `tests/test_isolate.py` as `python tests/isolate_cases.py CASE [ARG]`
in a clean interpreter, as the zygote will be: forking pytest itself would
fork whatever threads its plugins hold. Each case's function writes one JSON
report to a pipe the worker keeps; this script prints one JSON line: the
`Ending`, the report, the seconds the run took, and the seconds from the
ending until every holder of the report pipe was gone.
"""

from __future__ import annotations

import contextlib
import ctypes
import errno
import json
import os
import resource
import select
import signal
import socket
import sys
import time
from collections.abc import Callable

import arris.build

from arris_gym.sandbox import _isolate

MEMORY = 512 * 2**20  # the roadmap's default memory limit
REPORT_FD = 0  # set in main: the write end of the report pipe


def report(value: object) -> None:
    """Write the case's finding to the report pipe, whole."""
    data = json.dumps(value).encode()
    while data:
        data = data[os.write(REPORT_FD, data) :]


def failure(action: Callable[[], object]) -> object:
    """What `action` raised, as [class name, errno]; or ["ok", its value]."""
    try:
        value = action()
    except OSError as e:
        return [type(e).__name__, e.errno]
    except (MemoryError, ValueError) as e:
        return [type(e).__name__, None]
    return ["ok", value if isinstance(value, int | str | bool | None) else repr(value)]


def build() -> None:
    import xml.dom.minidom  # not imported before the fork: a lazy stdlib import

    part = arris.build.Solid.box((0, 0, 0), (10, 10, 10)).cut(
        arris.build.Solid.cylinder((5, 5, -1), (0, 0, 1), 2, 12)
    )
    data = part.model.write_body(part.body)
    report({"bytes": len(data), "ok": part.check("full").ok, "xml": xml.dom.minidom.__name__})


def connect_inet() -> None:
    def attempt() -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect(("1.1.1.1", 53))

    report(failure(attempt))


def connect_unix(path: str) -> None:
    def attempt() -> None:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.connect(path)

    def pair() -> None:
        socket.socketpair()

    def netlink() -> None:
        socket.socket(socket.AF_NETLINK, socket.SOCK_RAW)

    report({"connect": failure(attempt), "socketpair": failure(pair), "netlink": failure(netlink)})


def read_outside(path: str) -> None:
    def read(p: str) -> Callable[[], object]:
        return lambda: len(open(p, "rb").read())

    report(
        {
            "outside": failure(read(path)),
            "listdir": failure(lambda: os.listdir(os.path.dirname(path))),
            "passwd": failure(read("/etc/passwd")),
            "inside": failure(read(arris.build.__file__)),
        }
    )


def write_outside(directory: str) -> None:
    victim = os.path.join(directory, "victim")
    libc = ctypes.CDLL(None, use_errno=True)

    def clear_read_only() -> object:
        # mount_setattr(AT_FDCWD, "/", AT_RECURSIVE, {clr: RDONLY}): lift the mounts.
        attr = (ctypes.c_uint64 * 4)(0, 1, 0, 0)
        if libc.syscall(442, -100, b"/", 0x8000, attr, 32) < 0:
            code = ctypes.get_errno()
            raise OSError(code, os.strerror(code))
        return "lifted"

    def nested() -> object:
        os.unshare(os.CLONE_NEWUSER | os.CLONE_NEWNS)
        return clear_read_only()

    def raise_limit(which: int) -> Callable[[], object]:
        return lambda: resource.setrlimit(which, (resource.RLIM_INFINITY,) * 2)

    def session_keyring() -> object:
        # keyctl(KEYCTL_GET_KEYRING_ID, KEY_SPEC_SESSION_KEYRING): the caller's keys.
        key = libc.syscall(250 if os.uname().machine == "x86_64" else 219, 0, -3)
        if key < 0:
            code = ctypes.get_errno()
            raise OSError(code, os.strerror(code))
        return int(key)

    def create() -> None:
        with open(os.path.join(directory, "created"), "wb") as f:
            f.write(b"x")

    def append() -> None:
        with open(victim, "ab") as f:
            f.write(b"x")

    report(
        {
            "create": failure(create),
            "append": failure(append),
            "chmod": failure(lambda: os.chmod(victim, 0o777)),
            "utime": failure(lambda: os.utime(victim, (0, 0))),
            "setxattr": failure(lambda: os.setxattr(victim, "user.arris_gym", b"1")),
            "truncate": failure(lambda: os.truncate(victim, 0)),
            "unlink": failure(lambda: os.unlink(victim)),
            "memfd": failure(lambda: os.memfd_create("x")),
            "keyctl": failure(session_keyring),
            "remount": failure(clear_read_only),
            "rlimit_as": failure(raise_limit(resource.RLIMIT_AS)),
            "rlimit_nproc": failure(raise_limit(resource.RLIMIT_NPROC)),
            "rlimit_core": failure(raise_limit(resource.RLIMIT_CORE)),
            "core": list(resource.getrlimit(resource.RLIMIT_CORE)),
            "nested": failure(nested),
        }
    )


def fork_bomb() -> None:
    forks = 0
    try:
        while True:
            if os.fork() == 0:
                time.sleep(60)
                os._exit(0)
            forks += 1
    except OSError as e:
        report({"forks": forks, "error": [type(e).__name__, e.errno]})


def setsid_descendant() -> None:
    if os.fork() == 0:
        os.setsid()
        time.sleep(60)  # holds the report pipe, in a session of its own
        os._exit(0)
    report({"forked": True})


def stubborn() -> None:
    for sig in range(1, signal.NSIG):
        with contextlib.suppress(OSError, ValueError):  # SIGKILL, SIGSTOP and the like
            signal.signal(sig, signal.SIG_IGN)
    libc = ctypes.CDLL(None, use_errno=True)
    libc.prctl(1, 0, 0, 0, 0)  # PR_SET_PDEATHSIG: none
    while True:
        pass


def allocate() -> None:
    def bytes_of(size: int) -> Callable[[], object]:
        return lambda: len(bytearray(size))

    report({"gib": failure(bytes_of(2**30)), "mib_100": failure(bytes_of(100 * 2**20))})


def descriptors(extra: str) -> None:
    def fstat(fd: int) -> bool:
        try:
            os.fstat(fd)
        except OSError as e:
            if e.errno != errno.EBADF:
                raise
            return False
        return True

    report(
        {
            "open": [fd for fd in range(256) if fstat(fd)],
            "extra": int(extra),
            "stdin": os.read(0, 16).decode(),
            "tty": os.isatty(0) or os.isatty(1) or os.isatty(2),
            "session_leader": os.getsid(0) == os.getpid(),
            "pid": os.getpid(),
        }
    )


def raises() -> None:
    raise RuntimeError("a program's own failure")


def exits(code: str) -> None:
    os._exit(int(code))


CASES: dict[str, Callable[..., None]] = {
    "build": build,
    "connect_inet": connect_inet,
    "connect_unix": connect_unix,
    "read_outside": read_outside,
    "write_outside": write_outside,
    "fork_bomb": fork_bomb,
    "setsid_descendant": setsid_descendant,
    "stubborn": stubborn,
    "allocate": allocate,
    "descriptors": descriptors,
    "raises": raises,
    "exits": exits,
}


def main() -> None:
    global REPORT_FD
    case, *args = sys.argv[1:]
    timeout = float(os.environ.get("ISOLATE_TIMEOUT", "10"))
    memory = int(os.environ.get("ISOLATE_MEMORY", str(MEMORY)))
    extra_r, extra_w = os.pipe()  # a descriptor the worker is not given
    report_r, REPORT_FD = os.pipe()
    # A root that cannot be opened: the worker cannot build its ruleset.
    missing = tuple(filter(None, [os.environ.get("ISOLATE_MISSING_ROOT")]))
    limits = _isolate.Limits(memory=memory, readable=_isolate.readable_roots() + missing)
    target = CASES[case]
    if case == "descriptors":
        args = [str(extra_w)]
    start = time.monotonic()
    ending = _isolate.run(
        lambda: target(*args), timeout=timeout, limits=limits, keep_fds=(REPORT_FD,)
    )
    seconds = time.monotonic() - start
    os.close(REPORT_FD)
    chunks = []
    held = False  # whether some process still held the pipe 5 s after the ending
    while select.select([report_r], [], [], 5.0)[0]:
        chunk = os.read(report_r, 65536)
        if not chunk:
            break
        chunks.append(chunk)
    else:
        held = True
    released = time.monotonic() - start - seconds
    data = b"".join(chunks).decode()
    sys.stdout.write(
        json.dumps(
            {
                "kind": ending.kind.name,
                "value": ending.value,
                "armed": ending.armed,
                "report": json.loads(data) if data else None,
                "held": held,
                "seconds": seconds,
                "released": released,
            }
        )
        + "\n"
    )
    os.close(extra_r)


if __name__ == "__main__":
    main()

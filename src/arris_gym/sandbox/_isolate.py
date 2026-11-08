"""Run one function in a program worker under its warden (ADR-0002).

The chain is forking process -> **warden** -> **program worker**. The warden
closes every descriptor it was not given, enters fresh user, network, PID,
mount and IPC namespaces, makes every mount read-only, and forks the
program worker, which is PID 1 of the new PID namespace: when it ends, the
kernel kills every process it left behind, `setsid` or not. The warden owns
the deadline (a pidfd, then `SIGKILL`) and writes how the worker ended to a
status pipe the worker never holds.

The program worker, before the function runs: leaves the session, detaches
stdin and stdout (stderr goes where the caller says), closes every
descriptor it was not given, sets its rlimits, forbids new privileges,
enters a Landlock domain that reads only the interpreter's prefixes and
site-packages (an exec job's: those of the interpreter it execs, which alone
it may execute), drops its capabilities and installs a seccomp filter. Then
it writes one byte to the armed pipe; an ending without that byte is a
worker whose isolation was never complete, and the function did not run.
Nothing here trusts the function: every limit is one it cannot lift.

Linux only, x86-64 and AArch64. Private: `sandbox/_zygote.py` is its caller.
"""

from __future__ import annotations

import contextlib
import ctypes
import enum
import errno
import os
import platform
import resource
import select
import signal
import site
import socket
import struct
import sys
import time
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from typing import NoReturn

# --- Limits -------------------------------------------------------------------

# RLIMIT_NPROC, counted per user namespace (the plan's measurement): the
# warden and the worker count, so 4 leaves a program two more tasks (threads
# or forks). arris and numpy (OPENBLAS_NUM_THREADS=1) build on one thread, so
# a program needs none; each extra task may hold another `memory`, so the
# limit is also the bound on a program's memory: (NPROC_LIMIT - 1) * memory.
NPROC_LIMIT = 4


@dataclass(frozen=True)
class Limits:
    """What one program worker may use.

    `memory` is the worker's `RLIMIT_AS` in bytes; `nproc` its
    `RLIMIT_NPROC`; `readable` the directories (or single files) its Landlock
    domain may read beneath; `executable` the files it may also execute,
    which is none but an exec job's interpreter and its ELF loader
    (ADR-0004). Nothing else is readable, executable or writable. Each limit
    is hard: the worker cannot raise it.
    """

    memory: int
    readable: tuple[str, ...]
    nproc: int = NPROC_LIMIT
    executable: tuple[str, ...] = ()


def readable_roots() -> tuple[str, ...]:
    """The directories a program worker reads: interpreter and packages.

    The interpreter's prefixes (the standard library, lazily imported),
    every site-packages directory, and the directory `arris_gym` itself is
    imported from, which for an editable install is the repository's
    `src/arris_gym` and nothing beside it. Sorted, so the ruleset does not
    depend on a `set`'s order.
    """
    import arris_gym  # the package directory, wherever it is installed

    roots: set[str] = {
        sys.prefix,
        sys.exec_prefix,
        sys.base_prefix,
        sys.base_exec_prefix,
        *site.getsitepackages(),
        *arris_gym.__path__,
    }
    return tuple(sorted(os.path.realpath(r) for r in roots if os.path.isdir(r)))


# --- How a worker ended -------------------------------------------------------


class EndKind(enum.IntEnum):
    """How a program worker ended, as its warden saw it."""

    EXITED = 0  # value: the exit code
    SIGNALLED = 1  # value: the signal number
    TIMED_OUT = 2  # the deadline passed; the warden killed it
    UNAVAILABLE = 3  # value: the errno of the isolation step the warden could not take


@dataclass(frozen=True)
class Ending:
    """One worker's end: its kind, the code or signal, and whether it was armed.

    `armed` is true exactly when the worker completed its isolation and so
    ran the function. A worker that is not armed ran nothing of the caller's.
    """

    kind: EndKind
    value: int
    armed: bool


# Status record, warden to caller: kind, value, armed.
_STATUS = struct.Struct("<iii")
# The exit code of a worker that could not isolate itself; it never ran the
# function, and its ending says so by `armed` being false, not by this code.
_SETUP_FAILED = 120
# The exit code of a worker whose function raised.
_RAISED = 1
# The exit code of a warden that failed in its own code (a bug here).
_WARDEN_FAILED = 121


def parse_ending(record: bytes) -> Ending | None:
    """The `Ending` a warden's status record holds, or None if it is not one whole."""
    if len(record) != _STATUS.size:
        return None
    kind, value, armed = _STATUS.unpack(record)
    try:
        return Ending(EndKind(kind), value, bool(armed))
    except ValueError:  # not a kind a warden writes
        return None


def read_ending(fd: int) -> Ending | None:
    """The record a warden wrote to `fd`, or None if it wrote none whole."""
    data = b""
    while len(data) < _STATUS.size:
        chunk = os.read(fd, _STATUS.size - len(data))
        if not chunk:
            return None
        data += chunk
    return parse_ending(data)


# --- The kernel interfaces ----------------------------------------------------

_libc = ctypes.CDLL(None, use_errno=True)
_syscall = _libc.syscall
_syscall.restype = ctypes.c_long
_prctl = _libc.prctl
_prctl.restype = ctypes.c_int

_PR_SET_NO_NEW_PRIVS = 38
_PR_SET_SECCOMP = 22
_SECCOMP_MODE_FILTER = 2

# Syscall numbers shared by both architectures (the generic table's).
_SYS_LANDLOCK_CREATE_RULESET = 444
_SYS_LANDLOCK_ADD_RULE = 445
_SYS_LANDLOCK_RESTRICT_SELF = 446
_SYS_MOUNT_SETATTR = 442


@dataclass(frozen=True)
class _Arch:
    audit: int  # AUDIT_ARCH_*: the filter kills a syscall made under any other
    capset: int
    denied: tuple[int, ...]  # refused outright with EACCES
    families: tuple[int, ...]  # socket, socketpair: refused but for AF_INET/AF_INET6
    x32: bool  # x86-64's x32 ABI shares the arch value; it is killed


# What the seccomp filter refuses, and why each (ADR-0002): io_uring creates
# sockets past the filter; keyrings reach the caller's session keyring;
# memfd_create and shmget hold memory that RLIMIT_AS does not count.
_ARCHES = {
    "x86_64": _Arch(
        audit=0xC000003E,
        capset=126,
        denied=(425, 426, 427, 248, 249, 250, 319, 29),
        families=(41, 53),
        x32=True,
    ),
    "aarch64": _Arch(
        audit=0xC00000B7,
        capset=91,
        denied=(425, 426, 427, 217, 218, 219, 279, 194),
        families=(198, 199),
        x32=False,
    ),
}


def _check(result: int, what: str) -> int:
    if result < 0:
        code = ctypes.get_errno()
        raise OSError(code, f"{what}: {os.strerror(code)}")
    return result


# Landlock (include/uapi/linux/landlock.h).
class _RulesetAttr(ctypes.Structure):
    _fields_ = (("handled_access_fs", ctypes.c_uint64),)


class _PathBeneathAttr(ctypes.Structure):
    _pack_ = 1
    _fields_ = (("allowed_access", ctypes.c_uint64), ("parent_fd", ctypes.c_int32))


_LANDLOCK_CREATE_RULESET_VERSION = 1
_LANDLOCK_RULE_PATH_BENEATH = 1
_FS_EXECUTE = 1 << 0
_FS_READ_FILE = 1 << 2
_FS_READ = _FS_READ_FILE | (1 << 3)  # READ_FILE | READ_DIR
# The filesystem rights each ABI version knows: 13 in ABI 1, REFER in 2,
# TRUNCATE in 3, IOCTL_DEV in 5. Every one is handled, so all but reading
# beneath `readable` is refused.
_FS_RIGHTS_BY_ABI = {1: 13, 2: 14, 3: 15, 4: 15, 5: 16}


def landlock_abi() -> int:
    """The kernel's Landlock ABI version; 0 where Landlock is absent."""
    version = _syscall(
        ctypes.c_long(_SYS_LANDLOCK_CREATE_RULESET),
        None,
        ctypes.c_size_t(0),
        ctypes.c_uint32(_LANDLOCK_CREATE_RULESET_VERSION),
    )
    return max(int(version), 0)


def _landlock(readable: Iterable[str], executable: Iterable[str] = ()) -> None:
    abi = landlock_abi()
    if abi < 1:
        raise OSError(errno.ENOSYS, "Landlock is unavailable")
    handled = (1 << _FS_RIGHTS_BY_ABI.get(abi, 16)) - 1
    attr = _RulesetAttr(handled)
    ruleset = _check(
        _syscall(
            ctypes.c_long(_SYS_LANDLOCK_CREATE_RULESET),
            ctypes.byref(attr),
            ctypes.c_size_t(ctypes.sizeof(attr)),
            ctypes.c_uint32(0),
        ),
        "landlock_create_ruleset",
    )
    # A rule on a file may grant only a file's rights, READ_DIR not among them.
    rules = [(p, _FS_READ if os.path.isdir(p) else _FS_READ_FILE) for p in readable]
    rules += [(p, _FS_EXECUTE | _FS_READ_FILE) for p in executable]
    for path, allowed in rules:
        fd = os.open(path, os.O_PATH | os.O_CLOEXEC)
        rule = _PathBeneathAttr(allowed, fd)
        _check(
            _syscall(
                ctypes.c_long(_SYS_LANDLOCK_ADD_RULE),
                ctypes.c_int(ruleset),
                ctypes.c_int(_LANDLOCK_RULE_PATH_BENEATH),
                ctypes.byref(rule),
                ctypes.c_uint32(0),
            ),
            f"landlock_add_rule {path}",
        )
        os.close(fd)
    _check(
        _syscall(
            ctypes.c_long(_SYS_LANDLOCK_RESTRICT_SELF), ctypes.c_int(ruleset), ctypes.c_uint32(0)
        ),
        "landlock_restrict_self",
    )
    os.close(ruleset)


# mount_setattr (include/uapi/linux/mount.h).
class _MountAttr(ctypes.Structure):
    _fields_ = (
        ("attr_set", ctypes.c_uint64),
        ("attr_clr", ctypes.c_uint64),
        ("propagation", ctypes.c_uint64),
        ("userns_fd", ctypes.c_uint64),
    )


_AT_FDCWD = -100
_AT_RECURSIVE = 0x8000
_MOUNT_ATTR_RDONLY = 0x1


def _read_only_mounts() -> None:
    attr = _MountAttr(_MOUNT_ATTR_RDONLY, 0, 0, 0)
    _check(
        _syscall(
            ctypes.c_long(_SYS_MOUNT_SETATTR),
            ctypes.c_int(_AT_FDCWD),
            b"/",
            ctypes.c_uint(_AT_RECURSIVE),
            ctypes.byref(attr),
            ctypes.c_size_t(ctypes.sizeof(attr)),
        ),
        "mount_setattr",
    )


# capset (include/uapi/linux/capability.h), version 3: two data words.
class _CapHeader(ctypes.Structure):
    _fields_ = (("version", ctypes.c_uint32), ("pid", ctypes.c_int))


class _CapData(ctypes.Structure):
    _fields_ = (
        ("effective", ctypes.c_uint32),
        ("permitted", ctypes.c_uint32),
        ("inheritable", ctypes.c_uint32),
    )


_LINUX_CAPABILITY_VERSION_3 = 0x20080522


def _drop_capabilities(arch: _Arch) -> None:
    header = _CapHeader(_LINUX_CAPABILITY_VERSION_3, 0)
    data = (_CapData * 2)()
    _check(_syscall(ctypes.c_long(arch.capset), ctypes.byref(header), ctypes.byref(data)), "capset")


# seccomp-bpf (include/uapi/linux/filter.h, seccomp.h).
class _SockFilter(ctypes.Structure):
    _fields_ = (
        ("code", ctypes.c_uint16),
        ("jt", ctypes.c_uint8),
        ("jf", ctypes.c_uint8),
        ("k", ctypes.c_uint32),
    )


class _SockFprog(ctypes.Structure):
    _fields_ = (("len", ctypes.c_ushort), ("filter", ctypes.POINTER(_SockFilter)))


_LD_ABS = 0x20  # BPF_LD | BPF_W | BPF_ABS
_JEQ = 0x15  # BPF_JMP | BPF_JEQ | BPF_K
_JGE = 0x35  # BPF_JMP | BPF_JGE | BPF_K
_RET = 0x06  # BPF_RET | BPF_K
_RET_ALLOW = 0x7FFF0000
_RET_KILL_PROCESS = 0x80000000
_RET_EACCES = 0x00050000 | errno.EACCES
_X32_SYSCALL_BIT = 0x40000000
# struct seccomp_data: nr at 0, arch at 4, args at 16; args[0]'s low word
# first on these little-endian machines.
_OFF_NR, _OFF_ARCH, _OFF_ARG0 = 0, 4, 16
_ALLOWED_FAMILIES = (int(socket.AF_INET), int(socket.AF_INET6))


def seccomp_program(arch: _Arch) -> list[tuple[int, int, int, int]]:
    """The filter as (code, jt, jf, k) instructions; a jump counts from the next."""
    program = [
        (_LD_ABS, 0, 0, _OFF_ARCH),
        (_JEQ, 1, 0, arch.audit),
        (_RET, 0, 0, _RET_KILL_PROCESS),
    ]
    program.append((_LD_ABS, 0, 0, _OFF_NR))
    if arch.x32:
        program += [(_JGE, 0, 1, _X32_SYSCALL_BIT), (_RET, 0, 0, _RET_KILL_PROCESS)]
    for nr in arch.denied:
        program += [(_JEQ, 0, 1, nr), (_RET, 0, 0, _RET_EACCES)]
    inet, inet6 = _ALLOWED_FAMILIES
    for nr in arch.families:
        # Not this call: skip the five instructions of its own verdict.
        program += [
            (_JEQ, 0, 5, nr),
            (_LD_ABS, 0, 0, _OFF_ARG0),
            (_JEQ, 2, 0, inet),
            (_JEQ, 1, 0, inet6),
            (_RET, 0, 0, _RET_EACCES),
            (_RET, 0, 0, _RET_ALLOW),
        ]
    program.append((_RET, 0, 0, _RET_ALLOW))
    return program


def _seccomp(arch: _Arch) -> None:
    program = seccomp_program(arch)
    filters = (_SockFilter * len(program))(*(_SockFilter(*i) for i in program))
    fprog = _SockFprog(len(program), filters)
    _check(
        _prctl(
            ctypes.c_int(_PR_SET_SECCOMP),
            ctypes.c_ulong(_SECCOMP_MODE_FILTER),
            ctypes.byref(fprog),
            ctypes.c_ulong(0),
            ctypes.c_ulong(0),
        ),
        "seccomp",
    )


# --- The warden and the worker ------------------------------------------------

_NAMESPACES = (
    os.CLONE_NEWUSER | os.CLONE_NEWNET | os.CLONE_NEWPID | os.CLONE_NEWNS | os.CLONE_NEWIPC
)
# Signals a terminal or a session sends to a whole group; the warden outlives
# them, since a warden gone is a deadline gone.
_WARDEN_IGNORES = (signal.SIGINT, signal.SIGHUP, signal.SIGQUIT, signal.SIGTERM)


def spawn(
    target: Callable[[], object],
    *,
    deadline: float,
    limits: Limits,
    status_fd: int,
    keep_fds: Sequence[int] = (),
    stderr_fd: int | None = None,
) -> int:
    """Fork a warden that runs `target` in a program worker; return its pid.

    `deadline` is a `time.monotonic()` instant: the worker is killed when it
    passes. The worker keeps `keep_fds` (at their numbers) and nothing else
    but stdio: stdin and stdout are `/dev/null`, stderr goes to `stderr_fd`
    or `/dev/null`. The warden writes one `Ending` record to `status_fd`
    (`read_ending`), then exits; the caller reaps it. The caller's copies of
    the descriptors are its own to close.

    Refuses (ValueError) an unsupported machine or a descriptor list that
    includes stdio. Never returns in the child processes.
    """
    arch = _ARCHES.get(platform.machine())
    if arch is None:
        raise ValueError(f"the sandbox runs on x86_64 and aarch64, not {platform.machine()}")
    if any(fd <= 2 for fd in keep_fds):
        raise ValueError("stdio is the worker's own; keep_fds names descriptors above 2")
    pid = os.fork()
    if pid:
        return pid
    try:
        _warden(target, deadline, limits, status_fd, tuple(keep_fds), stderr_fd, arch)
    finally:
        os._exit(_WARDEN_FAILED)


def _warden(
    target: Callable[[], object],
    deadline: float,
    limits: Limits,
    status_fd: int,
    keep_fds: tuple[int, ...],
    stderr_fd: int | None,
    arch: _Arch,
) -> None:
    for sig in _WARDEN_IGNORES:
        signal.signal(sig, signal.SIG_IGN)
    # The forking process's own descriptors (a zygote's job socket among
    # them) are not the warden's: holding one would keep it open past its
    # owner's death.
    out = () if stderr_fd is None else (stderr_fd,)
    _close_all_but((0, 1, 2, status_fd, *keep_fds, *out))

    def report(kind: EndKind, value: int, armed: bool) -> NoReturn:
        # A caller gone is no reason for the warden to linger.
        with contextlib.suppress(OSError):
            os.write(status_fd, _STATUS.pack(kind, value, int(armed)))
        os._exit(0)

    try:
        os.unshare(_NAMESPACES)
        _read_only_mounts()
        armed_r, armed_w = os.pipe()
        pid = os.fork()
    except OSError as e:
        report(EndKind.UNAVAILABLE, e.errno or 0, False)
    if pid == 0:
        try:
            os.close(armed_r)
            os.close(status_fd)
            _worker(target, limits, keep_fds, stderr_fd, armed_w, arch)
        finally:
            os._exit(_SETUP_FAILED)
    os.close(armed_w)
    for fd in sorted({*keep_fds, *out}):
        os.close(fd)
    pidfd = os.pidfd_open(pid)
    poller = select.poll()
    poller.register(pidfd, select.POLLIN)
    remaining_ms = max(0, int((deadline - time.monotonic()) * 1000) + 1)
    timed_out = not poller.poll(remaining_ms)
    if timed_out:
        signal.pidfd_send_signal(pidfd, signal.SIGKILL)
    _, status = os.waitpid(pid, 0)
    os.set_blocking(armed_r, False)
    try:
        armed = os.read(armed_r, 1) == b"\x01"
    except BlockingIOError:
        armed = False
    if timed_out:
        report(EndKind.TIMED_OUT, 0, armed)
    if os.WIFSIGNALED(status):
        report(EndKind.SIGNALLED, os.WTERMSIG(status), armed)
    report(EndKind.EXITED, os.waitstatus_to_exitcode(status), armed)


def _close_all_but(keep: Iterable[int]) -> None:
    kept = sorted(set(keep))
    ceiling = resource.getrlimit(resource.RLIMIT_NOFILE)[1]
    for low, high in zip(kept, [*kept[1:], ceiling], strict=True):
        os.closerange(low + 1, high)


def _worker(
    target: Callable[[], object],
    limits: Limits,
    keep_fds: tuple[int, ...],
    stderr_fd: int | None,
    armed_w: int,
    arch: _Arch,
) -> None:
    for sig in _WARDEN_IGNORES:
        signal.signal(sig, signal.SIG_DFL)
    os.setsid()
    null = os.open(os.devnull, os.O_RDWR)
    os.dup2(null, 0)
    os.dup2(null, 1)
    os.dup2(null if stderr_fd is None else stderr_fd, 2)
    _close_all_but((0, 1, 2, armed_w, *keep_fds))
    resource.setrlimit(resource.RLIMIT_AS, (limits.memory, limits.memory))
    resource.setrlimit(resource.RLIMIT_NPROC, (limits.nproc, limits.nproc))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    _check(_prctl(ctypes.c_int(_PR_SET_NO_NEW_PRIVS), ctypes.c_ulong(1), 0, 0, 0), "no_new_privs")
    _landlock(limits.readable, limits.executable)
    _drop_capabilities(arch)
    _seccomp(arch)
    os.write(armed_w, b"\x01")
    os.close(armed_w)
    try:
        target()
    except BaseException:  # noqa: BLE001  # the function's failure is its exit code
        os._exit(_RAISED)
    os._exit(0)


def run(
    target: Callable[[], object],
    *,
    timeout: float,
    limits: Limits,
    keep_fds: Sequence[int] = (),
    stderr_fd: int | None = None,
) -> Ending:
    """Run `target` isolated for at most `timeout` seconds; how it ended.

    `spawn`, then the status read and the warden reaped. Blocks until the
    worker ends. A warden that wrote no record is a bug in this module and
    raises RuntimeError.
    """
    status_r, status_w = os.pipe()
    try:
        warden = spawn(
            target,
            deadline=time.monotonic() + timeout,
            limits=limits,
            status_fd=status_w,
            keep_fds=keep_fds,
            stderr_fd=stderr_fd,
        )
    finally:
        os.close(status_w)
    try:
        ending = read_ending(status_r)
    finally:
        os.close(status_r)
        os.waitpid(warden, 0)
    if ending is None:
        raise RuntimeError("the warden ended without a status record")
    return ending

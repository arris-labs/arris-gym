"""The oracle worker: run one CadQuery program on Open CASCADE, report JSON.

Runs in the oracle environment only and imports nothing of ``arris_gym``. A
program is hostile input: it runs only as an oracle worker, this script
exec'd inside a program worker the sandbox's warden isolated (ADR-0004).

Usage, as the oracle worker: ``worker.py PAYLOAD_FD RESULT_FD`` reads the
program's text from ``PAYLOAD_FD`` to its end and writes one JSON report to
``RESULT_FD``, only from the process that started (a child the program
forked writes nothing). For a trusted program by hand, ``worker.py
PROGRAM.py`` prints the report on stdout.

As the oracle zygote (ADR-0013): ``worker.py --zygote PAYLOAD_FD RESULT_FD
CHANNEL_FD``. It has imported CadQuery and built nothing, says ``ready`` on
the channel, then serves one program at a time: a job message (its
deadline) with the status, result and stderr pipes' write ends and the
program's text, as the sandbox's zygote receives a job. It forks a child that
runs the program as the oracle worker would, and is that child's warden: it
kills it at the deadline, then kills everything else in its PID namespace,
of which it is PID 1, reaps it all, and writes the child's ending to the
status pipe in the warden's record. The child keeps every limit it
inherits; the zygote's own state it can only copy.

The result is taken as ``docs/ARCHITECTURE.md`` §Outcomes says: the argument
of the last ``show_object`` call, else the module-level ``result``, else
module-level ``r`` (ADR-0015), by presence even when the value is invalid.
"""

from __future__ import annotations

import contextlib
import ctypes
import errno
import hashlib
import io
import json
import os
import re
import resource
import select
import signal
import socket
import struct
import sys
import time
import traceback
from typing import Any

import cadquery as cq
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.Interface import Interface_Static
from OCP.OSD import OSD_ThreadPool
from OCP.STEPControl import STEPControl_AsIs, STEPControl_Writer
from OCP.TopAbs import TopAbs_FACE, TopAbs_SOLID
from OCP.TopExp import TopExp_Explorer

_FILENAME = "program.py"


def _shape_hash_code(self: cq.Shape) -> int:
    # cadquery 2.3.0 calls TopoDS_Shape.HashCode(), which OCP 7.9 removed; it
    # keys every selector (`faces`, `edges`, ...) on it. TopoDS_Shape's own
    # hash agrees with IsSame, the identity cadquery means. Nothing else of
    # cadquery is patched.
    return hash(self.wrapped)


cq.Shape.hashCode = _shape_hash_code  # type: ignore[method-assign]
# Open CASCADE's default thread pool has a thread per logical processor, and
# cadquery runs every boolean in parallel on it. Under the worker's
# RLIMIT_NPROC the pool cannot start them and the boolean hangs (ADR-0004),
# and its size would make a report depend on the machine. The pool is created
# here, before any program, with one thread: the calling one.
OSD_ThreadPool.DefaultPool_s(1)
# STEP's header carries a timestamp, FILE_NAME's second argument, and the
# product name a per-process counter ("translator 7.9 2"). The text sent back
# has both blanked, so it is the same bytes on every run; its hash is of the
# data section alone, which `fidelity/_oracle.py` recomputes the same way.
_STEP_DATA_MARK = "DATA;"
_STEP_COUNTER = re.compile(r"(translator \d+\.\d+ )\d+")
_STEP_TIMESTAMP = re.compile(r"(FILE_NAME\('(?:[^']|'')*',)'[^']*'")


def _count(shape: cq.Shape, kind: Any) -> int:
    n = 0
    explorer = TopExp_Explorer(shape.wrapped, kind)
    while explorer.More():
        n += 1
        explorer.Next()
    return n


def _as_shape(result: Any) -> cq.Shape | None:
    """The shape a result stands for, or None when it is not geometry."""
    if isinstance(result, cq.Workplane):
        shapes = [v for v in result.vals() if isinstance(v, cq.Shape)]
        if not shapes:
            return None
        return shapes[0] if len(shapes) == 1 else cq.Compound.makeCompound(shapes)
    if isinstance(result, cq.Shape):
        return result
    return None


def _measures(shape: cq.Shape) -> dict[str, Any]:
    vol = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape.wrapped, vol)
    surf = GProp_GProps()
    BRepGProp.SurfaceProperties_s(shape.wrapped, surf)
    c = vol.CentreOfMass()
    box = Bnd_Box()
    # Tight, from the geometry: the plain Add_s boxes a torus by its control
    # net (0.33 too wide on a 8 x 8 x 2 one). Neither triangulation nor the
    # shapes' tolerances, so it is the part's own extent.
    BRepBndLib.AddOptimal_s(shape.wrapped, box, False, False)
    lo_x, lo_y, lo_z, hi_x, hi_y, hi_z = box.Get()
    return {
        "volume": vol.Mass(),
        "area": surf.Mass(),
        "centroid": [c.X(), c.Y(), c.Z()],
        "bounds": [[lo_x, lo_y, lo_z], [hi_x, hi_y, hi_z]],
        "faces": _count(shape, TopAbs_FACE),
        "solids": _count(shape, TopAbs_SOLID),
    }


def _step_text(shape: cq.Shape) -> str:
    """The STEP of ``shape``, its timestamp and translator counter blanked.

    As ``cq.exporters.export`` writes STEP (a compound, ``Shape.exportStep``'s
    defaults), but to memory: an oracle worker can write no file. Open
    CASCADE writes ISO 10303-21's ASCII.
    """
    writer = STEPControl_Writer()
    Interface_Static.SetIVal_s("write.surfacecurve.mode", 1)
    Interface_Static.SetIVal_s("write.precision.mode", 0)
    writer.Transfer(cq.Compound.makeCompound([shape]).wrapped, STEPControl_AsIs)
    stream = io.BytesIO()
    writer.WriteStream(stream)
    text = stream.getvalue().decode("ascii")
    text = _STEP_TIMESTAMP.sub(r"\1''", text, count=1)
    return _STEP_COUNTER.sub(r"\1N", text)


def _step_sha256(text: str) -> str:
    """The hash of a blanked STEP text: its data section's UTF-8 bytes."""
    data = text[text.index(_STEP_DATA_MARK) :]
    return hashlib.sha256(data.encode("utf-8", "surrogatepass")).hexdigest()


def run_program(text: str) -> dict[str, Any]:
    """Run ``text`` and return its report: status, message, measures, hashes.

    ``step_text`` is the result's STEP, blanked as ``_step_text`` says, and
    ``step_sha256`` its hash: both set exactly when the status is ``ok``.

    Statuses: ``ok``, ``syntax``, ``runtime``, ``no_result`` and ``invalid``
    (``BRepCheck_Analyzer`` fails). Messages are the exception's own words.
    """
    report: dict[str, Any] = {
        "status": "ok",
        "message": "",
        "measures": None,
        "step_sha256": None,
        "step_text": None,
        "program_sha256": hashlib.sha256(text.encode("utf-8", "surrogatepass")).hexdigest(),
        "versions": {
            "cadquery": cq.__version__,
            "ocp": _ocp_version(),
            "python": sys.version.split()[0],
        },
    }
    try:
        code = compile(text, _FILENAME, "exec")
    except (SyntaxError, ValueError) as exc:  # ValueError: a NUL byte
        report.update(status="syntax", message=f"{type(exc).__name__}: {exc}")
        return report

    shown: list[Any] = []
    ns: dict[str, Any] = {"__name__": "__main__", "show_object": shown.append}
    try:
        exec(code, ns)
    except BaseException as exc:  # noqa: BLE001 - SystemExit included: the program's own end
        tb = traceback.format_exception_only(type(exc), exc)
        report.update(status="runtime", message="".join(tb).rstrip("\n"))
        return report

    result = shown[-1] if shown else ns.get("result", ns.get("r"))
    shape = _as_shape(result) if result is not None else None
    if shape is None:
        what = "nothing" if result is None else type(result).__name__
        report.update(status="no_result", message=f"no shape result: {what}")
        return report
    report["measures"] = _measures(shape)
    if not BRepCheck_Analyzer(shape.wrapped).IsValid():
        report.update(status="invalid", message="BRepCheck_Analyzer: shape is not valid")
        return report
    step = _step_text(shape)
    report.update(step_text=step, step_sha256=_step_sha256(step))
    return report


def _ocp_version() -> str:
    from importlib.metadata import version

    return version("cadquery-ocp")


def _read_all(fd: int) -> bytes:
    chunks = []
    while chunk := os.read(fd, 1 << 20):
        chunks.append(chunk)
    os.close(fd)
    return b"".join(chunks)


def _write_all(fd: int, data: bytes) -> None:
    view = memoryview(data)
    while view:
        view = view[os.write(fd, view) :]


# The oracle zygote's protocol (ADR-0013). Its first message on the channel.
ZYGOTE_FLAG = "--zygote"
_READY = b"ready"
# A job: its deadline, a `time.monotonic()` instant (CLOCK_MONOTONIC, which
# the caller shares: no time namespace is entered). Its four descriptors are
# the status, result and stderr pipes' write ends and the program's text.
_JOB = struct.Struct("<d")
_JOB_FDS = 4
# The warden's status record (`arris_gym.sandbox._isolate`): kind, value,
# armed. Kinds: exited (the code), signalled (the signal), timed out, and
# unavailable (the errno of a fork refused). A child is armed from birth: it
# inherits a complete isolation, so its ending always has it set.
_STATUS = struct.Struct("<iii")
_EXITED, _SIGNALLED, _TIMED_OUT, _UNAVAILABLE = 0, 1, 2, 3
# A child whose own code failed outside the program: Python's exit code for
# an uncaught exception, as the exec'd worker ended with one.
_RAISED = 1
# prctl(2): the zygote is not dumpable, so a child of the same uid can neither
# ptrace it nor open its memory; the child is made dumpable again, as an
# exec'd worker is.
_PR_SET_DUMPABLE = 4


def _set_dumpable(value: int) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(_PR_SET_DUMPABLE, ctypes.c_ulong(value), 0, 0, 0) != 0:
        code = ctypes.get_errno()
        raise OSError(code, f"prctl(PR_SET_DUMPABLE): {os.strerror(code)}")


def _close_all_but(keep: tuple[int, ...]) -> None:
    kept = sorted(set(keep))
    ceiling = resource.getrlimit(resource.RLIMIT_NOFILE)[1]
    for low, high in zip(kept, [*kept[1:], ceiling], strict=True):
        os.closerange(low + 1, high)


def _child(result_w: int, stderr_w: int, payload: int) -> None:
    """Run the program in ``payload`` as an exec'd oracle worker would; never returns."""
    code = _RAISED
    try:
        # As the exec'd worker started: its own session, Python's handler for
        # SIGINT, dumpable, stderr the job's, nothing but its descriptors.
        os.setsid()
        signal.signal(signal.SIGINT, signal.default_int_handler)
        _set_dumpable(1)
        os.dup2(stderr_w, 2)
        _close_all_but((0, 1, 2, result_w, payload))
        child = os.getpid()
        text = _read_all(payload).decode("utf-8", "surrogatepass")
        report = json.dumps(run_program(text), sort_keys=True) + "\n"
        # A child the program forked returns here too; only the child reports.
        if os.getpid() == child:
            _write_all(result_w, report.encode("utf-8", "surrogatepass"))
        code = 0
    except BaseException:  # noqa: BLE001 - reported as an uncaught exception would be
        traceback.print_exc()
    finally:
        sys.stderr.flush()
        os._exit(code)


def _sweep() -> None:
    """Kill and reap every process in this PID namespace but this one.

    ``kill(-1)`` from PID 1 reaches every process of its namespace except
    itself; what a program left behind is reparented here, so it is reaped
    here. Repeated until no child is left, so a process forked between a kill
    and a wait meets the next kill.
    """
    while True:
        with contextlib.suppress(ProcessLookupError):  # none left to kill
            os.kill(-1, signal.SIGKILL)
        try:
            os.waitpid(-1, 0)
        except ChildProcessError:
            return


def _serve_one(deadline: float, result_w: int, stderr_w: int, payload: int) -> bytes:
    """Run one program in a child under this zygote's warding; its status record."""
    sys.stdout.flush()
    sys.stderr.flush()
    try:
        pid = os.fork()
    except OSError as e:
        return _STATUS.pack(_UNAVAILABLE, e.errno or errno.EAGAIN, 0)
    if pid == 0:
        _child(result_w, stderr_w, payload)
    for fd in (result_w, stderr_w, payload):
        os.close(fd)
    pidfd = os.pidfd_open(pid)
    try:
        poller = select.poll()
        poller.register(pidfd, select.POLLIN)
        remaining_ms = max(0, int((deadline - time.monotonic()) * 1000) + 1)
        timed_out = not poller.poll(remaining_ms)
        if timed_out:
            signal.pidfd_send_signal(pidfd, signal.SIGKILL)
        _, status = os.waitpid(pid, 0)
    finally:
        os.close(pidfd)
    _sweep()
    if timed_out:
        return _STATUS.pack(_TIMED_OUT, 0, 1)
    if os.WIFSIGNALED(status):
        return _STATUS.pack(_SIGNALLED, os.WTERMSIG(status), 1)
    return _STATUS.pack(_EXITED, os.waitstatus_to_exitcode(status), 1)


def serve(channel_fd: int) -> None:
    """The oracle zygote: say ready on the channel, then serve jobs to its end."""
    # PID 1 of its namespace receives from inside it only the signals it
    # handles; Python handles SIGINT, which a child could send, so it is
    # ignored here and restored in the child.
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    _set_dumpable(0)
    sock = socket.socket(fileno=channel_fd)
    sock.send(_READY)
    while True:
        message, fds, flags, _ = socket.recv_fds(sock, _JOB.size, _JOB_FDS)
        if not message and not fds:
            return  # the caller is gone
        if len(message) != _JOB.size or len(fds) != _JOB_FDS or flags & socket.MSG_CTRUNC:
            for fd in fds:  # a caller's bug: no record, and the caller's backstop
                os.close(fd)
            continue
        (deadline,) = _JOB.unpack(message)
        status_w, result_w, stderr_w, payload = fds
        try:
            record = _serve_one(deadline, result_w, stderr_w, payload)
            with contextlib.suppress(OSError):  # a caller that gave the job up
                os.write(status_w, record)
        finally:
            os.close(status_w)


def main() -> None:
    worker = os.getpid()
    if len(sys.argv) == 5 and sys.argv[1] == ZYGOTE_FLAG:
        # The payload holds no program and the result carries nothing: the
        # zygote answers on its channel, its children on their own pipes.
        os.close(int(sys.argv[2]))
        os.close(int(sys.argv[3]))
        serve(int(sys.argv[4]))
        return
    if len(sys.argv) == 3:  # the oracle worker: payload and result descriptors
        text = _read_all(int(sys.argv[1])).decode("utf-8", "surrogatepass")
        out = int(sys.argv[2])
    else:
        with open(sys.argv[1], encoding="utf-8", errors="surrogateescape") as fh:
            text = fh.read()
        # Open CASCADE's STEP writer prints to C stdout; keep fd 1 for the JSON.
        out = os.dup(1)
        os.dup2(2, 1)
    report = json.dumps(run_program(text), sort_keys=True) + "\n"
    # A child the program forked returns here too; only the worker reports.
    if os.getpid() == worker:
        _write_all(out, report.encode("utf-8", "surrogatepass"))


if __name__ == "__main__":
    main()

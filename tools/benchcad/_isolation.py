"""Disposable Linux jobs for the pinned BenchCAD helpers (ADR-0032)."""

from __future__ import annotations

import os
import platform
import shutil
import struct
import subprocess
import tempfile
from collections.abc import Mapping
from pathlib import Path

from arris_gym.sandbox._isolate import _ARCHES, seccomp_program

_ORACLE = Path(__file__).resolve().parents[1] / "oracle"
_PYTHON = Path("/usr/bin/python3.12")
_VENV = _ORACLE / ".venv"
_WORKER = _ORACLE / "vision2code_worker.py"
# Bound STEP, image and diagnostics written to the stdout/stderr spools.
_OUTPUT_BYTES = 32 * 2**20
_SCRATCH_BYTES = 64 * 2**20
_ADDRESS_BYTES = 2560 * 2**20
# Upstream has one parent and one export child. OCP and Mesa may start threads.
_TASKS = 16

_ENV = {
    "HOME": "/tmp",
    "TMPDIR": "/tmp",
    "LC_ALL": "C.UTF-8",
    "OPENBLAS_NUM_THREADS": "1",
    "PYTHONHASHSEED": "0",
    "PYTHONDONTWRITEBYTECODE": "1",
    "VTK_DEFAULT_OPENGL_WINDOW": "vtkEGLRenderWindow",
    "VTK_SMP_MAX_THREADS": "1",
    "LP_NUM_THREADS": "1",
    "LIBGL_ALWAYS_SOFTWARE": "1",
}


def _command(bwrap: str, sources: Path, inputs: Path, filter_fd: int) -> list[str]:
    # The oracle wheel environment uses the host's system CPython 3.12. Mount
    # just that runtime and its libraries at their expected paths.
    return [
        bwrap,
        "--unshare-all",
        "--unshare-user",
        "--disable-userns",
        "--uid",
        "1000",
        "--gid",
        "1000",
        "--cap-drop",
        "ALL",
        "--new-session",
        "--die-with-parent",
        "--ro-bind",
        "/usr/lib",
        "/usr/lib",
        "--ro-bind-try",
        "/usr/lib64",
        "/usr/lib64",
        "--symlink",
        "usr/lib",
        "/lib",
        "--symlink",
        "usr/lib64",
        "/lib64",
        "--ro-bind",
        str(_PYTHON),
        str(_PYTHON),
        "--symlink",
        "python3.12",
        "/usr/bin/python3",
        "--ro-bind",
        "/usr/bin/prlimit",
        "/usr/bin/prlimit",
        "--ro-bind",
        str(_VENV),
        "/venv",
        "--ro-bind",
        str(_WORKER),
        "/worker.py",
        "--ro-bind",
        str(sources),
        "/upstream",
        "--ro-bind",
        str(inputs),
        "/inputs",
        "--ro-bind-try",
        "/usr/share/glvnd/egl_vendor.d/50_mesa.json",
        "/usr/share/glvnd/egl_vendor.d/50_mesa.json",
        "--dev",
        "/dev",
        "--remount-ro",
        "/dev",
        "--size",
        str(_SCRATCH_BYTES),
        "--perms",
        "1777",
        "--tmpfs",
        "/tmp",
        "--remount-ro",
        "/",
        "--chdir",
        "/tmp",
        "--clearenv",
        *(arg for key, value in _ENV.items() for arg in ("--setenv", key, value)),
        "--seccomp",
        str(filter_fd),
        "--",
        "/usr/bin/prlimit",
        f"--nproc={_TASKS}:{_TASKS}",
        "--",
        "/venv/bin/python",
        "/worker.py",
    ]


def _job(
    sources: Path,
    operation: str,
    inputs: Mapping[str, bytes],
    *,
    timeout: float,
) -> tuple[int, bytes, bytes] | None:
    """One job's exit code and bounded streams, or None at the host deadline."""
    bwrap = shutil.which("bwrap", path="/usr/bin")
    if bwrap is None or not _PYTHON.is_file() or (_VENV / "bin/python").resolve() != _PYTHON:
        raise RuntimeError("BenchCAD jobs need bubblewrap and the system Python 3.12 oracle venv")
    arch = _ARCHES[platform.machine()]
    with (
        tempfile.TemporaryDirectory(prefix="benchcad-inputs-") as directory,
        tempfile.TemporaryFile() as seccomp,
        tempfile.TemporaryFile() as stdout,
        tempfile.TemporaryFile() as stderr,
    ):
        root = Path(directory)
        for name, data in inputs.items():
            (root / name).write_bytes(data)
        for insn in seccomp_program(arch):
            seccomp.write(struct.pack("=HBBI", *insn))
        seccomp.seek(0)
        command = [
            # Upstream strips BLAS settings from the export child's environment.
            # Its affinity gives BLAS one CPU even after that filtering.
            "/usr/bin/taskset",
            "--cpu-list",
            str(min(os.sched_getaffinity(0))),
            "/usr/bin/prlimit",
            f"--as={_ADDRESS_BYTES}:{_ADDRESS_BYTES}",
            f"--fsize={_OUTPUT_BYTES}:{_OUTPUT_BYTES}",
            "--core=0:0",
            "--",
            *_command(bwrap, sources, root, seccomp.fileno()),
            operation,
        ]
        try:
            result = subprocess.run(
                command,
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=stderr,
                cwd="/",
                env={},
                pass_fds=(seccomp.fileno(),),
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return None
        stdout.seek(0)
        stderr.seek(0, os.SEEK_END)
        stderr.seek(max(0, stderr.tell() - 4096))
        return result.returncode, stdout.read(), stderr.read()

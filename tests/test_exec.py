"""The exec job (ADR-0004): a program worker that execs another interpreter.

Runs in the gate on the main interpreter, which stands in for the oracle's:
the spec's round trip, a payload that is not one refused, and an exec'd
script that keeps every limit of the worker it replaced.
"""

from __future__ import annotations

import json
import os
import pathlib
import sys
import time
from collections.abc import Iterator

import pytest
from hypothesis import given
from hypothesis import strategies as st

from arris_gym.sandbox import _exec
from arris_gym.sandbox._isolate import EndKind
from arris_gym.sandbox._zygote import ENVIRONMENT, JobKind, Zygote

ECHO = pathlib.Path(__file__).resolve().parent / "exec_echo.py"
TIMEOUT = 30.0
MEMORY = 512 * 2**20

paths = st.lists(st.text(min_size=1).map(lambda s: "/" + s), max_size=4).map(tuple)


@pytest.fixture(scope="module")
def zygote() -> Iterator[Zygote]:
    with Zygote() as z:
        yield z


@given(
    argv=paths.filter(bool),
    env=st.lists(st.tuples(st.text(), st.text()), max_size=4).map(tuple),
    readable=paths,
    executable=paths,
    text=st.binary(),
)
def test_a_spec_round_trips_and_leaves_the_text(
    argv: tuple[str, ...],
    env: tuple[tuple[str, str], ...],
    readable: tuple[str, ...],
    executable: tuple[str, ...],
    text: bytes,
) -> None:
    spec = _exec.ExecSpec(argv=argv, env=env, readable=readable, executable=executable)
    fd = os.memfd_create("spec", os.MFD_CLOEXEC)
    try:
        os.write(fd, _exec.payload(spec, text))
        os.lseek(fd, 0, os.SEEK_SET)
        assert _exec.read_spec(fd) == spec
        assert os.read(fd, len(text) + 1) == text
    finally:
        os.close(fd)


@given(st.binary(max_size=256))
def test_a_payload_that_is_no_spec_is_refused_never_raised(data: bytes) -> None:
    fd = os.memfd_create("spec", os.MFD_CLOEXEC)
    try:
        os.write(fd, data)
        os.lseek(fd, 0, os.SEEK_SET)
        spec = _exec.read_spec(fd)
    finally:
        os.close(fd)
    assert spec is None or isinstance(spec, _exec.ExecSpec)


def test_a_relative_path_is_refused() -> None:
    with pytest.raises(ValueError, match="absolute"):
        _exec.ExecSpec(argv=("python",), env=(), readable=(), executable=())


def test_the_loader_is_the_interpreters_own() -> None:
    loader = _exec.elf_loader(os.path.realpath(sys.executable))
    assert loader is not None
    assert os.path.isabs(loader)
    assert os.path.isfile(loader)


def test_the_script_runs_as_pid_1_and_reaches_only_its_spec(zygote: Zygote) -> None:
    spec = _exec.interpreter_spec(sys.executable, str(ECHO), ENVIRONMENT)
    assert spec.executable[0] == os.path.realpath(sys.executable)
    text = "result = 1\n\udc80"
    outcome = zygote.execute(
        JobKind.EXEC,
        _exec.payload(spec, text.encode("utf-8", "surrogatepass")),
        deadline=time.monotonic() + TIMEOUT,
        memory=MEMORY,
    )
    assert outcome.ending is not None
    assert (outcome.ending.kind, outcome.ending.value, outcome.ending.armed) == (
        EndKind.EXITED,
        0,
        True,
    ), outcome.stderr
    report = json.loads(outcome.data)
    assert report["text"] == text
    assert report["pid"] == 1
    assert report["argv0"] == str(ECHO)
    assert report["sibling"] == ["PermissionError", 13]
    assert report["exec"] == ["PermissionError", 13]


def test_a_payload_that_is_no_spec_runs_nothing(zygote: Zygote) -> None:
    outcome = zygote.execute(
        JobKind.EXEC, b"\xff\xff\xff\xff", deadline=time.monotonic() + TIMEOUT, memory=MEMORY
    )
    assert outcome.ending is None
    assert outcome.data == b""


LOADER_PROBE = pathlib.Path(__file__).resolve().parent / "exec_loader.py"


def test_the_loader_runs_any_readable_program_inside_the_same_boundary(zygote: Zygote) -> None:
    # ADR-0004: Landlock cannot refuse the loader mapping a file it reads, so a
    # program can run anything readable through it. What it runs is still
    # nobody, in the empty network namespace, on read-only mounts.
    loader = _exec.elf_loader(os.path.realpath(sys.executable))
    assert loader is not None
    spec = _exec.interpreter_spec(
        sys.executable, str(LOADER_PROBE), ENVIRONMENT | {"LOADER": loader}
    )
    assert "/usr/bin/bash" not in spec.executable
    assert "/usr/bin/id" not in spec.executable
    outcome = zygote.execute(
        JobKind.EXEC,
        _exec.payload(spec, b""),
        deadline=time.monotonic() + TIMEOUT,
        memory=MEMORY,
    )
    assert outcome.ending is not None
    assert (outcome.ending.kind, outcome.ending.value) == (EndKind.EXITED, 0), outcome.stderr
    report = json.loads(outcome.data)
    assert report["direct"] == ["PermissionError", 13]
    assert report["id"] == {"code": 0, "stdout": "65534\n", "stderr": ""}
    bash = report["bash"]
    assert bash["code"] == 0, bash
    assert bash["stdout"].splitlines() == ["uid=65534", "connect=1", "write=1"], bash
    assert "Network is unreachable" in bash["stderr"], bash
    assert "Read-only file system" in bash["stderr"] or "Permission denied" in bash["stderr"]

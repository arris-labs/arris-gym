#!/usr/bin/env python3
"""Run programs on the oracle: CadQuery on Open CASCADE in an oracle worker.

An oracle worker is a program worker under the sandbox's warden that execs
the oracle environment's interpreter on `tools/oracle/worker.py` (ADR-0004):
the same namespaces, rlimits, Landlock domain and seccomp filter as an arris
program, with the oracle environment's prefixes as its whole reach. Runs in
the main environment; needs `uv sync --project tools/oracle` first.
"""

from __future__ import annotations

import pathlib
import time

from arris_gym.sandbox import _exec
from arris_gym.sandbox._zygote import ENVIRONMENT, JobKind, Outcome, Zygote

ORACLE = pathlib.Path(__file__).resolve().parent / "oracle"
# The environment's interpreter as it is called: the path tells it its venv.
PYTHON = ORACLE / ".venv" / "bin" / "python"
WORKER = ORACLE / "worker.py"

# The oracle worker's RLIMIT_AS. Measured (ADR-0004): importing cadquery and
# OCP maps 875 MiB of address space, and a filleted box with a hole and five
# booleans on spheres and cylinders left it there; its resident set was
# 507 MiB. 1.5 GiB is that import plus about what an arris worker's 512 MiB
# leaves a program beyond its own import, and refuses a 1 GiB allocation.
MEMORY = 1536 * 2**20

# The zygote's environment, and a `HOME` that does not exist: ezdxf, which
# cadquery imports, asks the password database for one without it, and the
# worker cannot read that. Nothing is written there; the read-only mounts
# refuse it.
ORACLE_ENVIRONMENT = {**ENVIRONMENT, "HOME": "/nonexistent"}


def spec() -> _exec.ExecSpec:
    """The exec spec of an oracle worker on this checkout's oracle environment."""
    return _exec.interpreter_spec(str(PYTHON), str(WORKER), ORACLE_ENVIRONMENT)


def run_one(zygote: Zygote, oracle: _exec.ExecSpec, program: str, *, timeout: float) -> Outcome:
    """Run `program` in one oracle worker for at most `timeout` seconds.

    What came back, unread: the warden's `Ending`, the frame bytes on the
    result pipe (trusted no more than any worker's) and the stderr tail.
    """
    text = program.encode("utf-8", "surrogatepass")
    return zygote.execute(
        JobKind.EXEC,
        _exec.payload(oracle, text),
        deadline=time.monotonic() + timeout,
        memory=MEMORY,
    )

"""Run, score and train CAD-code models on the arris kernel.

`docs/ROADMAP.md` says what lands when.
"""

from importlib.metadata import version

from arris_gym.sandbox import (
    ArrisRefusal,
    BodyRef,
    Dialect,
    ExecResult,
    Measures,
    Sandbox,
    SandboxUnavailable,
    Status,
    Versions,
    digest,
    dump_text,
    run,
    run_many,
)

__version__ = version("arris-gym")

__all__ = [
    "ArrisRefusal",
    "BodyRef",
    "Dialect",
    "ExecResult",
    "Measures",
    "Sandbox",
    "SandboxUnavailable",
    "Status",
    "Versions",
    "__version__",
    "digest",
    "dump_text",
    "run",
    "run_many",
]

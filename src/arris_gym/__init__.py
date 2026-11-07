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
    SandboxUnavailable,
    Status,
    Versions,
    run,
)

__version__ = version("arris-gym")

__all__ = [
    "ArrisRefusal",
    "BodyRef",
    "Dialect",
    "ExecResult",
    "Measures",
    "SandboxUnavailable",
    "Status",
    "Versions",
    "__version__",
    "run",
]

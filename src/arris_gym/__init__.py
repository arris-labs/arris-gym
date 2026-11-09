"""Run, score and train CAD-code models on the arris kernel.

`docs/ROADMAP.md` says what lands when.
"""

from importlib.metadata import version

from arris_gym.reward import (
    DEFAULT_REWARD,
    FieldMetrics,
    IouRoute,
    RewardConfig,
    RewardWeights,
    Score,
    invalidity_rate,
    score,
)
from arris_gym.sandbox import (
    ArrisRefusal,
    BodyRef,
    Dialect,
    ExecResult,
    Measures,
    Sandbox,
    SandboxUnavailable,
    Status,
    TargetResult,
    Versions,
    digest,
    dump_png,
    dump_text,
    read_target,
    run,
    run_many,
)

__version__ = version("arris-gym")

__all__ = [
    "DEFAULT_REWARD",
    "ArrisRefusal",
    "BodyRef",
    "Dialect",
    "ExecResult",
    "FieldMetrics",
    "IouRoute",
    "Measures",
    "RewardConfig",
    "RewardWeights",
    "Sandbox",
    "SandboxUnavailable",
    "Score",
    "Status",
    "TargetResult",
    "Versions",
    "__version__",
    "digest",
    "dump_png",
    "dump_text",
    "invalidity_rate",
    "read_target",
    "run",
    "run_many",
    "score",
]

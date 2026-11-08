"""Oracle comparison and the disagreement classes."""

from arris_gym.fidelity._agreement import (
    AREA_REL,
    BOUNDS_ABS,
    CENTROID_DIAG,
    VOLUME_REL,
    MeasureDeltas,
    measure_deltas,
    within_tolerance,
)
from arris_gym.fidelity._compare import (
    ClosedForm,
    DisagreementClass,
    DocAnchor,
    Evidence,
    FidelityOutcome,
    FidelityRow,
    RegressionFixture,
    SecondOracle,
    Verdict,
    compare,
)
from arris_gym.fidelity._oracle import (
    OracleMeasures,
    OracleReport,
    OracleStatus,
    OracleVersions,
    parse_outcome,
    program_sha256,
)

__all__ = [
    "AREA_REL",
    "BOUNDS_ABS",
    "CENTROID_DIAG",
    "VOLUME_REL",
    "ClosedForm",
    "DisagreementClass",
    "DocAnchor",
    "Evidence",
    "FidelityOutcome",
    "FidelityRow",
    "MeasureDeltas",
    "OracleMeasures",
    "OracleReport",
    "OracleStatus",
    "OracleVersions",
    "RegressionFixture",
    "SecondOracle",
    "Verdict",
    "compare",
    "measure_deltas",
    "parse_outcome",
    "program_sha256",
    "within_tolerance",
]

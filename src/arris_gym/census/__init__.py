"""CadQuery corpus parsing and API counts (ADR-0003)."""

from arris_gym.census._curve import ReachCurve, ReachStep, reach_curve
from arris_gym.census._program import (
    BUILTIN,
    CQ,
    NON_LITERAL,
    SELECTOR_METHODS,
    UNKNOWN,
    CorpusProgram,
    Counts,
    ProgramCensus,
    Unparsable,
    census_program,
)
from arris_gym.census._reach import Reach, reach
from arris_gym.census._report import (
    CensusReport,
    CorpusInfo,
    FamilyCensus,
    census,
    select_slice,
    slice_families,
)

__all__ = [
    "BUILTIN",
    "CQ",
    "NON_LITERAL",
    "SELECTOR_METHODS",
    "UNKNOWN",
    "CensusReport",
    "CorpusInfo",
    "CorpusProgram",
    "Counts",
    "FamilyCensus",
    "ProgramCensus",
    "Reach",
    "ReachCurve",
    "ReachStep",
    "Unparsable",
    "census",
    "census_program",
    "reach",
    "reach_curve",
    "select_slice",
    "slice_families",
]

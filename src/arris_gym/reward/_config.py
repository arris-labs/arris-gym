"""`RewardConfig`: the reward's weights, τ, N, seed and routes' constants, versioned.

SEED.md §7.1, docs/ARCHITECTURE.md §The reward. The defaults are what
ADR-0008 (IoU budget, chord, N) and ADR-0009 (τ, the topology split)
measured, with SEED.md's weights. A change that can move any reward bumps
`version` (`.agents/rules/gym.md`); nothing else in `reward/` holds a weight,
τ or N.
"""

from __future__ import annotations

import math
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Weights sum to 1 within this: the sum of four decimal literals such as 0.6
# and 0.15 is exact to a few ulps, and a config that is off by more than
# this is a typo, not rounding.
WEIGHT_SUM_TOLERANCE = 1e-12


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class RewardWeights(_Frozen):
    """The weights of S = iou·IoU + surface·surface + measures·measures + topology·topology.

    Each is in [0, 1] and together they sum to 1 (within `WEIGHT_SUM_TOLERANCE`),
    which keeps S, and so the reward, in range. Refuses any other set.
    """

    iou: float = Field(default=0.6, ge=0.0, le=1.0)
    surface: float = Field(default=0.15, ge=0.0, le=1.0)
    measures: float = Field(default=0.15, ge=0.0, le=1.0)
    topology: float = Field(default=0.10, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _sum_to_one(self) -> Self:
        total = math.fsum((self.iou, self.surface, self.measures, self.topology))
        if abs(total - 1.0) > WEIGHT_SUM_TOLERANCE:
            raise ValueError(f"the weights must sum to 1, they sum to {total!r}")
        return self


class RewardConfig(_Frozen):
    """Everything a reward depends on besides the two bodies; frozen.

    `version` is written into every `Score`. `tau` is the surface term's
    scale as a share of the target's diagonal (ADR-0009); `points` is N, the
    sampled IoU's points (ADR-0008), of which the surface term draws half per
    body; `seed` seeds every draw; `iou_budget` is the exact route's step
    cap and `chord_fraction` the mesh chord as a share of a body's diagonal;
    `kind_weight` splits the topology term between the face-kind overlap and
    the genus gap. Refuses weights that do not sum to 1, a non-positive
    `tau`, `points`, `iou_budget` or `chord_fraction`, a `points` below 2, a
    `kind_weight` outside [0, 1] and a negative `seed`.

    >>> RewardConfig().version
    1
    """

    version: int = Field(default=1, ge=1)
    weights: RewardWeights = RewardWeights()
    tau: float = Field(default=0.05, gt=0.0)
    points: int = Field(default=10_648, ge=2)
    seed: int = Field(default=0, ge=0)
    iou_budget: int = Field(default=10**7, ge=1)
    chord_fraction: float = Field(default=1 / 200, gt=0.0)
    kind_weight: float = Field(default=0.5, ge=0.0, le=1.0)

    @property
    def surface_points(self) -> int:
        """Surface samples per body: N/2, as ADR-0009 measured (5,324 of 10,648)."""
        return self.points // 2


DEFAULT_REWARD = RewardConfig()
"""Reward version 1: SEED.md's weights with ADR-0008 and ADR-0009's constants."""

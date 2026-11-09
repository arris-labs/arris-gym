"""`Score` and the reward formula: the table of failures and 0.1 + 0.9·S.

SEED.md §7.1 and docs/ARCHITECTURE.md §The reward. A failure status gets a
fixed reward with no kernel call; a valid body gets `0.1 + 0.9·S`, S the
weighted sum of the four terms under a `RewardConfig`. The `match` over
`Status` ends in `assert_never`, so a new status stops `mypy --strict` here.
"""

from __future__ import annotations

import hashlib
import math
from typing import Self, assert_never

from pydantic import BaseModel, ConfigDict, Field, model_validator

from arris_gym.reward._config import RewardConfig
from arris_gym.reward._iou import IouRoute
from arris_gym.sandbox.outcome import Status, Versions

# The reward table of SEED.md §7.1.
REWARD_UNRUNNABLE = -1.0
REWARD_REFUSED = -0.5
REWARD_CHECK_FAILED = -0.3
# A valid body earns the floor plus a share of the span: 0.1 + 0.9·S.
REWARD_FLOOR = 0.1
REWARD_SPAN = 0.9


class FieldMetrics(BaseModel):
    """BenchCAD's own metrics beside ours, computed as its scorer does.

    `voxel_iou_64` is the IoU of two 64³ occupancy grids, each body
    normalised to its own box (scale-blind, so a cube and its double give 1);
    `chamfer_x1000` is the mean squared nearest distance both ways between
    2,048 seeded surface samples of each normalised body, times 1000. Both in
    the field's units; neither shares a name with our IoU or surface term,
    and neither moves the reward. Guarantees: `voxel_iou_64` is a finite
    number in [0, 1] and `chamfer_x1000` a finite number at least 0. Refuses
    anything else, a number written as a string included.
    """

    # Strict: a score worker's frame carries these, and a number written as
    # a string is a forgery there, not a coercion.
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    voxel_iou_64: float = Field(ge=0.0, le=1.0, allow_inf_nan=False)
    chamfer_x1000: float = Field(ge=0.0, allow_inf_nan=False)


def failure_reward(status: Status) -> float | None:
    """The fixed reward of a failure `status`, or `None` for `OK`, which is scored.

    -1.0 for `syntax`, `runtime`, `unsupported_api`, `timeout` and `crash`,
    -0.5 for `arris_refusal`, -0.3 for `checker_fail`.

    >>> failure_reward(Status.CHECKER_FAIL)
    -0.3
    """
    match status:
        case Status.OK:
            return None
        case (
            Status.SYNTAX | Status.RUNTIME | Status.UNSUPPORTED_API | Status.TIMEOUT | Status.CRASH
        ):
            return REWARD_UNRUNNABLE
        case Status.ARRIS_REFUSAL:
            return REWARD_REFUSED
        case Status.CHECKER_FAIL:
            return REWARD_CHECK_FAILED
        case _ as unreachable:
            assert_never(unreachable)


def combine(
    config: RewardConfig, *, iou: float, surface: float, measures: float, topology: float
) -> float:
    """The reward of a valid body, `0.1 + 0.9·S`, in [0.1, 1].

    S is the weights' `math.fsum` of the four terms, clamped to [0, 1]
    against rounding; four terms of exactly 1 give exactly 1.0. Raises
    `ValueError` for a term that is not a finite number in [0, 1].
    """
    weights = config.weights
    terms = (iou, surface, measures, topology)
    if not all(math.isfinite(t) and 0.0 <= t <= 1.0 for t in terms):
        raise ValueError(f"every term must be a finite number in [0, 1], got {terms!r}")
    total = math.fsum(
        (
            weights.iou * iou,
            weights.surface * surface,
            weights.measures * measures,
            weights.topology * topology,
        )
    )
    return min(1.0, REWARD_FLOOR + REWARD_SPAN * min(1.0, max(0.0, total)))


class Score(BaseModel):
    """What `score` returns for one result: the reward, its terms and the field's metrics.

    `status` is the result's, or `crash`, `timeout` or `runtime` when scoring
    a valid body failed; `message` is the kernel's or the result's words,
    verbatim. Guarantees, enforced on construction: for a failure status the
    four terms, `iou_route` and `field` are `None` and `reward` is exactly the
    table's; for `ok` all four terms, `iou_route` and `field` are set, each term in
    [0, 1], and `reward` is in [0.1, 1]. `reward_version` is the config's.
    Refuses any other combination.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: Status
    message: str
    reward: float
    iou: float | None
    iou_route: IouRoute | None
    surface: float | None
    measures: float | None
    topology: float | None
    field: FieldMetrics | None
    reward_version: int
    versions: Versions

    @model_validator(mode="after")
    def _fields_agree_with_status(self) -> Self:
        terms = (self.iou, self.surface, self.measures, self.topology)
        want = failure_reward(self.status)
        if want is not None:
            if self.reward != want:
                raise ValueError(f"a {self.status.value} reward is exactly {want}")
            if any(t is not None for t in terms) or self.iou_route or self.field:
                raise ValueError("a failure has no terms, route or field metrics")
            return self
        if any(t is None for t in terms) or self.iou_route is None or self.field is None:
            raise ValueError("an ok score has all four terms, a route and the field metrics")
        if not all(t is not None and math.isfinite(t) and 0.0 <= t <= 1.0 for t in terms):
            raise ValueError("every term must be a finite number in [0, 1]")
        if not (math.isfinite(self.reward) and REWARD_FLOOR <= self.reward <= 1.0):
            raise ValueError("an ok reward is in [0.1, 1]")
        return self

    def digest(self) -> str:
        """The SHA-256 (hex) of the score's numbers and names, floats in hex.

        Status, reward, terms, route, field metrics and versions; `message`
        is left out, since a timeout's words may carry a duration. The same
        score always digests the same.

        >>> from arris_gym.reward import DEFAULT_REWARD
        >>> s = Score(status=Status.SYNTAX, message="x", reward=-1.0, iou=None,
        ...     iou_route=None, surface=None, measures=None, topology=None,
        ...     field=None, reward_version=DEFAULT_REWARD.version,
        ...     versions=Versions(arris="0.10.0", numpy="2.3.4", arris_gym="0.1.0"))
        >>> s.digest() == s.digest()
        True
        """

        def hexed(value: float | None) -> str:
            return "none" if value is None else value.hex()

        field = self.field
        lines = [
            f"status: {self.status.value}",
            f"reward: {self.reward.hex()}",
            f"iou: {hexed(self.iou)}",
            f"iou_route: {'none' if self.iou_route is None else self.iou_route.value}",
            f"surface: {hexed(self.surface)}",
            f"measures: {hexed(self.measures)}",
            f"topology: {hexed(self.topology)}",
            f"voxel_iou_64: {hexed(None if field is None else field.voxel_iou_64)}",
            f"chamfer_x1000: {hexed(None if field is None else field.chamfer_x1000)}",
            f"reward_version: {self.reward_version}",
            f"versions: arris={self.versions.arris!r} numpy={self.versions.numpy!r}"
            f" arris_gym={self.versions.arris_gym!r}",
        ]
        return hashlib.sha256(("\n".join(lines) + "\n").encode("utf-8")).hexdigest()

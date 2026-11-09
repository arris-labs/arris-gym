"""The measures term: the mean of four min/max ratios of mass properties.

SEED.md §7.1 and docs/ARCHITECTURE.md §The reward; ADR-0009 fixes the
formula. The four ratios are the volume, the surface area, the centroid's gap
(1 minus its share of the target's bounding-box diagonal, floored at 0) and
the mean ratio of the sorted principal moments of inertia. The moments are
the eigenvalues of the inertia tensor about the centroid, by fixed cyclic
Jacobi sweeps in plain floats: only addition, subtraction, multiplication,
division and `sqrt`, which IEEE 754 rounds exactly, never `np.linalg` (§Determinism). The mean is a
`math.fsum`.
Private: called in-process on bodies already read into a fresh model, which
only a worker does.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import arris

from arris_gym.reward._iou import _corners

# Cyclic Jacobi sweeps over the three off-diagonal pairs. Convergence is
# quadratic: a 3 by 3 matrix is diagonal to rounding within 6 sweeps, so 10 is
# a fixed count with room to spare, and a fixed count (not a tolerance) keeps
# the operation sequence the same on every input.
JACOBI_SWEEPS = 10
_PAIRS = ((0, 1), (0, 2), (1, 2))

_Matrix = Sequence[Sequence[float]]


def principal_moments(inertia: _Matrix) -> tuple[float, float, float]:
    """The eigenvalues of a symmetric 3 by 3 `inertia`, ascending, by Jacobi sweeps.

    The matrix is symmetrised first (the mean of each off-diagonal pair).
    Each rotation zeroes one off-diagonal pair with the classical stable
    tangent; `JACOBI_SWEEPS` sweeps always run, and a pair already exactly
    zero is skipped. Exactly rounded operations only, so the bits are the
    same on every machine. Raises `ValueError` for a non-finite entry.
    """
    a = [[float(inertia[i][j]) for j in range(3)] for i in range(3)]
    if not all(math.isfinite(x) for row in a for x in row):
        raise ValueError("the inertia tensor has a non-finite entry")
    for i, j in _PAIRS:
        a[i][j] = a[j][i] = (a[i][j] + a[j][i]) / 2.0
    for _ in range(JACOBI_SWEEPS):
        for p, q in _PAIRS:
            apq = a[p][q]
            if apq == 0.0:
                continue
            theta = (a[q][q] - a[p][p]) / (2.0 * apq)
            t = math.copysign(1.0, theta) / (abs(theta) + math.sqrt(theta * theta + 1.0))
            c = 1.0 / math.sqrt(t * t + 1.0)
            s = t * c
            for k in range(3):
                akp, akq = a[k][p], a[k][q]
                a[k][p], a[k][q] = c * akp - s * akq, s * akp + c * akq
            for k in range(3):
                apk, aqk = a[p][k], a[q][k]
                a[p][k], a[q][k] = c * apk - s * aqk, s * apk + c * aqk
    low, mid, high = sorted((a[0][0], a[1][1], a[2][2]))
    return low, mid, high


def ratio(a: float, b: float) -> float:
    """min/max of two non-negative numbers, in [0, 1]; two zeros are 1 (alike).

    A negative input (rounding on a vanishing moment) counts as 0.
    """
    a, b = max(a, 0.0), max(b, 0.0)
    high = max(a, b)
    if high == 0.0:
        return 1.0
    return min(a, b) / high


def measures(model: arris.Model, candidate: arris.Body, target: arris.Body) -> float:
    """The measures term in [0, 1]; exactly 1.0 for a body against its own bytes.

    The mean of: volume ratio, area ratio, 1 - min(1, centroid gap / target
    diagonal) and the mean ratio of the sorted principal moments. Raises the
    kernel's `ArrisError` where it cannot measure a body, and `ValueError`
    for a target of no extent or a non-finite inertia.
    """
    ours, theirs = model.mass_properties(candidate), model.mass_properties(target)
    low, high = _corners(model, target)
    extent = high - low
    diagonal = math.sqrt(math.fsum((extent * extent).tolist()))
    if not diagonal > 0.0:
        raise ValueError("the target has no extent")
    gap = math.sqrt(
        math.fsum((x - y) * (x - y) for x, y in zip(ours.centroid, theirs.centroid, strict=True))
    )
    mine = principal_moments(ours.inertia_about(ours.centroid))
    want = principal_moments(theirs.inertia_about(theirs.centroid))
    moments = math.fsum(ratio(x, y) for x, y in zip(mine, want, strict=True)) / 3.0
    return (
        math.fsum(
            (
                ratio(ours.volume, theirs.volume),
                ratio(ours.area, theirs.area),
                1.0 - min(1.0, gap / diagonal),
                moments,
            )
        )
        / 4.0
    )

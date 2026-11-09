"""The surface term: exp(-d/τ), d a symmetric mean nearest-sample distance.

SEED.md §7.1 and docs/ARCHITECTURE.md §The reward; ADR-0009 measured τ and
the sample count. Each body is meshed at a chord of `chord_fraction` of its
own diagonal (as the IoU's sampled route meshes it) and sampled by area
from a fresh `PCG64(seed)`, so identical meshes give identical samples and
d = 0 exactly. d is the mean of the two one-way mean distances from a
sample to its nearest sample on the other body, over the target's
bounding-box diagonal. The path keeps to the operations IEEE 754 rounds
exactly (§Determinism): elementwise arithmetic, `sqrt`, `min`, `math.fsum`,
and `exp` as a fixed polynomial with `ldexp`, never a platform's `exp`.
Private: called in-process on bodies already read into a fresh model, which
only a worker does.
"""

from __future__ import annotations

import itertools
import math

import arris
import numpy as np
import numpy.typing as npt

from arris_gym.reward._iou import CHUNK_ELEMENTS, _corners, _mesh

_Floats = npt.NDArray[np.float64]
_Mesh = tuple[_Floats, _Floats, _Floats]

# ln 2 split for Cody and Waite's range reduction: LN2_HI has its low 11 bits
# zero, so n · LN2_HI is exact for every |n| < 2¹¹ the reduction meets, and
# LN2_HI + LN2_LO is ln 2 to about 2⁻¹⁰⁶ (fdlibm's e_exp.c constants).
LN2_HI = 6.93147180369123816490e-01
LN2_LO = 1.90821492927058770002e-10
# The Taylor coefficients 1/k! of exp on the reduced range |r| ≤ ln 2 / 2,
# up to the degree whose next term, (ln 2 / 2)¹⁴ / 14! ≈ 4·10⁻¹⁸, is below
# half an ulp of 1: each coefficient is one correctly rounded division.
EXP_DEGREE = 13
EXP_COEFFICIENTS = tuple(1.0 / math.factorial(k) for k in range(EXP_DEGREE + 1))
# Past this argument e^(-x) is below the smallest subnormal double (about
# 4.9·10⁻³²⁴, ln of which is -744.4): the polynomial path returns exactly 0.
EXP_UNDERFLOW = 745.2


def exp_neg(x: float) -> float:
    """e^(-x) for a finite `x` ≥ 0, from a fixed polynomial and `ldexp` alone.

    x = n·ln 2 + r with n the nearest integer and |r| ≤ ln 2 / 2 (Cody and
    Waite, with ln 2 split in two), e^(-r) by Horner's rule on its Taylor
    series to degree 13, then scaled by 2⁻ⁿ with `math.ldexp`, which is
    exact. Every step is a correctly rounded IEEE 754 operation in a fixed
    order, so the bits are the same on every machine; `math.exp` follows the
    platform's libm and `np.exp` the CPU's dispatch, so neither is used.
    Within a few ulps of e^(-x); exactly 1.0 at 0 and 0.0 from
    `EXP_UNDERFLOW`. Raises `ValueError` for a negative or non-finite `x`.
    """
    if not (math.isfinite(x) and x >= 0.0):
        raise ValueError(f"exp_neg takes a finite x >= 0, got {x!r}")
    if x >= EXP_UNDERFLOW:
        return 0.0
    n = round(x / (LN2_HI + LN2_LO))
    r = (n * LN2_HI - x) + n * LN2_LO
    total = EXP_COEFFICIENTS[EXP_DEGREE]
    for coefficient in reversed(EXP_COEFFICIENTS[:EXP_DEGREE]):
        total = total * r + coefficient
    return math.ldexp(total, -n)


def surface_samples(triangles: _Mesh, count: int, seed: int) -> _Floats:
    """`count` points (count by 3) uniform by area on the mesh of `triangles`' corners.

    From a fresh `PCG64(seed)`: `count` draws pick triangles by their share
    of the area (a cumulative sum in the mesh's order, one float at a time),
    then `count` pairs place a point uniformly in each, a pair past the
    diagonal reflected back. The same mesh and seed give the same bits.
    Raises `ValueError` for a mesh of no area or a `count` below 1.
    """
    if count < 1:
        raise ValueError(f"count must be positive, got {count}")
    a, b, c = triangles
    e1, e2 = b - a, c - a
    nx = e1[:, 1] * e2[:, 2] - e1[:, 2] * e2[:, 1]
    ny = e1[:, 2] * e2[:, 0] - e1[:, 0] * e2[:, 2]
    nz = e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0]
    # Twice each area; a common factor leaves the shares unchanged.
    areas = np.sqrt(nx * nx + ny * ny + nz * nz)
    cumulative = np.array(list(itertools.accumulate(areas.tolist())), dtype=np.float64)
    if len(cumulative) == 0 or not cumulative[-1] > 0.0:
        raise ValueError("the mesh has no area to sample")
    rng = np.random.Generator(np.random.PCG64(seed))
    # A draw below the total lands in the first triangle whose running sum
    # passes it, so a triangle of no area is never picked.
    picks = np.searchsorted(cumulative, rng.random(count) * cumulative[-1], side="right")
    picks = np.minimum(picks, len(cumulative) - 1)
    u, v = rng.random(count), rng.random(count)
    over = u + v > 1.0
    u, v = np.where(over, 1.0 - u, u), np.where(over, 1.0 - v, v)
    return np.asarray(a[picks] + u[:, None] * e1[picks] + v[:, None] * e2[picks])


def nearest_distances(points: _Floats, others: _Floats) -> _Floats:
    """Each of `points`' distance to its nearest point of `others` (both n by 3).

    By brute force in chunks of `CHUNK_ELEMENTS` pairs: squared distances
    elementwise, their minimum, then one `sqrt` per point, all exactly
    rounded, so the bits do not depend on the chunk or the machine.
    """
    out = np.empty(len(points), dtype=np.float64)
    rows = max(1, CHUNK_ELEMENTS // len(others))
    ox, oy, oz = others[None, :, 0], others[None, :, 1], others[None, :, 2]
    for start in range(0, len(points), rows):
        p = points[start : start + rows]
        dx = p[:, 0, None] - ox
        dy = p[:, 1, None] - oy
        dz = p[:, 2, None] - oz
        out[start : start + rows] = np.sqrt((dx * dx + dy * dy + dz * dz).min(axis=1))
    return out


def surface_distance(
    model: arris.Model,
    candidate: arris.Body,
    target: arris.Body,
    *,
    chord_fraction: float,
    points: int,
    seed: int,
) -> float:
    """d: the mean of both one-way mean nearest-sample distances, over the target's diagonal.

    Each body is meshed at `chord_fraction` of its own diagonal and sampled
    with `surface_samples(mesh, points, seed)`, the same seed for both, so
    bodies that mesh alike give d = 0 exactly. Each mean is `math.fsum` over
    the samples. Raises the kernel's `ArrisError` where it cannot mesh a
    body, and `ValueError` for a target of no extent.
    """
    low, high = _corners(model, target)
    extent = high - low
    diagonal = math.sqrt(math.fsum((extent * extent).tolist()))
    if not diagonal > 0.0:
        raise ValueError("the target has no extent")
    ours = surface_samples(_mesh(model, candidate, chord_fraction), points, seed)
    theirs = surface_samples(_mesh(model, target, chord_fraction), points, seed)
    forward = math.fsum(nearest_distances(ours, theirs).tolist()) / len(ours)
    backward = math.fsum(nearest_distances(theirs, ours).tolist()) / len(theirs)
    return (forward + backward) / (2.0 * diagonal)


def surface(
    model: arris.Model,
    candidate: arris.Body,
    target: arris.Body,
    *,
    tau: float,
    chord_fraction: float,
    points: int,
    seed: int,
) -> float:
    """The surface term, exp(-d/τ) in [0, 1], d from `surface_distance`.

    Exactly 1.0 when both bodies mesh alike; falls with d, to e⁻¹ at d = τ.
    `tau` is the reward config's (ADR-0009). Raises what `surface_distance`
    raises, and `ValueError` for a `tau` that is not positive.
    """
    if not tau > 0.0:
        raise ValueError(f"tau must be positive, got {tau}")
    d = surface_distance(
        model, candidate, target, chord_fraction=chord_fraction, points=points, seed=seed
    )
    return exp_neg(d / tau)

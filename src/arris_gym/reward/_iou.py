"""The IoU of two bodies in one model, by the exact route or the sampled route.

SEED.md §7.1 and docs/ARCHITECTURE.md §The reward. The **exact route** asks
the kernel's `interference` under a step budget, so whether it answers is the
same on every machine; any `ArrisError` from it, `Interrupted` included,
sends the pair to the **sampled route**, a winding number on each body's
`tessellate` mesh over jittered PCG64 points. The routes' constants are the
caller's (the reward's config), and ADR-0008 measured their defaults.
Private: called in-process on bodies already read into a fresh model, which
only a worker does.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

import arris
import numpy as np
import numpy.typing as npt

# Points times triangles held at once by the winding number: its temporaries
# are about fifteen float64 arrays of this many elements (some 2 MiB), so a
# chunk stays in cache. Measured in plans/m4-reward step 2 on 20,000 points
# against 400 triangles: 1 << 18 took 0.41 s alone and 4.5 s with sixteen
# processes at once, 1 << 14 took 0.31 s and 0.36 s. Not a tolerance: it
# moves no result.
CHUNK_ELEMENTS = 1 << 14
# A point is inside a closed mesh when the magnitude of its winding number,
# 1 inside and 0 outside, passes the midpoint. Only points within rounding of
# the surface come near it.
INSIDE_WINDING = 0.5

_Floats = npt.NDArray[np.float64]
_Flags = npt.NDArray[np.bool_]


class IouRoute(StrEnum):
    """Which route answered an IoU."""

    EXACT = "exact"
    """The kernel's `interference`: exact up to the kernel's rounding."""
    SAMPLED = "sampled"
    """A winding number over seeded points: an estimate within its sampling error."""


@dataclass(frozen=True)
class IouEstimate:
    """An IoU in [0, 1] and the route that answered it."""

    value: float
    route: IouRoute


def exact_iou(model: arris.Model, a: arris.Body, b: arris.Body, *, budget: int) -> float:
    """The IoU of `a` and `b` from the kernel's `interference` under `budget` steps.

    `apart` and `touching` are 0; both containment flags are exactly 1; one
    flag is the smaller volume over the larger; otherwise
    `v∩ / (vA + vB - v∩)`, clamped to [0, 1]. Raises the kernel's
    `ArrisError` where it refuses or the budget is spent (`Interrupted`), and
    `ValueError` for an overlap the kernel reports without its flags or volume.
    """
    found = model.interference(a, b, budget=budget)
    if found.kind != "overlapping":
        return 0.0
    if found.a_in_b is None or found.b_in_a is None:
        raise ValueError("interference reports an overlap without its containment flags")
    if found.a_in_b and found.b_in_a:
        return 1.0
    volume_a = model.mass_properties(a).volume
    volume_b = model.mass_properties(b).volume
    if found.a_in_b or found.b_in_a:
        return min(volume_a, volume_b) / max(volume_a, volume_b)
    common = found.volume
    if common is None:
        raise ValueError("interference reports an overlap without its volume")
    return min(1.0, max(0.0, common / (volume_a + volume_b - common)))


def _corners(model: arris.Model, body: arris.Body) -> tuple[_Floats, _Floats]:
    bounds = model.bounds(body)
    if bounds is None:
        raise ValueError("the kernel reports no bounds for the body")
    low, high = bounds
    return np.array(low, dtype=np.float64), np.array(high, dtype=np.float64)


def _mesh(
    model: arris.Model, body: arris.Body, chord_fraction: float
) -> tuple[_Floats, _Floats, _Floats]:
    """Each triangle's corners of the body's mesh at `chord_fraction` of its diagonal."""
    low, high = _corners(model, body)
    diagonal = math.dist(low.tolist(), high.tolist())
    positions, triangles = model.tessellate(body, diagonal * chord_fraction).to_numpy()
    corners = np.asarray(positions, dtype=np.float64)[np.asarray(triangles, dtype=np.intp)]
    return corners[:, 0, :], corners[:, 1, :], corners[:, 2, :]


def inside(points: _Floats, triangles: tuple[_Floats, _Floats, _Floats]) -> _Flags:
    """Which of `points` (n by 3) lie inside the closed mesh of `triangles`' corners.

    The generalised winding number: the solid angle each triangle subtends
    (Van Oosterom and Strackee, 1983), summed over the mesh and divided by 4π,
    is ±1 inside a closed mesh and 0 outside, whatever its orientation. Its
    `arctan2` and sum only feed the threshold, so their last bits never reach
    a result except for a point within rounding of the surface.
    """
    a, b, c = triangles
    flags = np.zeros(len(points), dtype=np.bool_)
    if len(a) == 0:
        return flags
    rows = max(1, CHUNK_ELEMENTS // len(a))
    for start in range(0, len(points), rows):
        p = points[start : start + rows, None, :]
        ra, rb, rc = a[None, :, :] - p, b[None, :, :] - p, c[None, :, :] - p
        ax, ay, az = ra[..., 0], ra[..., 1], ra[..., 2]
        bx, by, bz = rb[..., 0], rb[..., 1], rb[..., 2]
        cx, cy, cz = rc[..., 0], rc[..., 1], rc[..., 2]
        la = np.sqrt(ax * ax + ay * ay + az * az)
        lb = np.sqrt(bx * bx + by * by + bz * bz)
        lc = np.sqrt(cx * cx + cy * cy + cz * cz)
        det = ax * (by * cz - bz * cy) - ay * (bx * cz - bz * cx) + az * (bx * cy - by * cx)
        ab = ax * bx + ay * by + az * bz
        ac = ax * cx + ay * cy + az * cz
        bc = bx * cx + by * cy + bz * cz
        den = la * lb * lc + ab * lc + ac * lb + bc * la
        winding = (2.0 * np.arctan2(det, den)).sum(axis=1) / (4.0 * math.pi)
        flags[start : start + rows] = np.abs(winding) > INSIDE_WINDING
    return flags


def grid_side(points: int) -> int:
    """The largest k with k³ at most `points` (at least 1): the sampled route's cells per side.

    Integer arithmetic only, so the count of points drawn never depends on a
    platform's cube root.
    """
    if points < 1:
        raise ValueError(f"points must be positive, got {points}")
    k = 1
    while (k + 1) ** 3 <= points:
        k += 1
    return k


def jittered_points(points: int, seed: int) -> _Floats:
    """One uniform point in each of the k³ equal cells of the unit cube, k = `grid_side(points)`.

    Drawn from `PCG64(seed)`, cell by cell in a fixed order (x slowest), so
    the same seed gives the same bits. Each point is uniform over the cube,
    as an independent draw is, and the cells spread them: ADR-0008 measured
    the stratified draw's error below the independent draw's at every point
    count tried.
    """
    k = grid_side(points)
    index = np.arange(k, dtype=np.float64)
    gx, gy, gz = np.meshgrid(index, index, index, indexing="ij")
    cells = np.stack([gx.ravel(), gy.ravel(), gz.ravel()], axis=1)
    jitter = np.random.Generator(np.random.PCG64(seed)).random((k**3, 3))
    return np.asarray((cells + jitter) / k, dtype=np.float64)


def sampled_iou(
    model: arris.Model,
    a: arris.Body,
    b: arris.Body,
    *,
    chord_fraction: float,
    points: int,
    seed: int,
) -> float:
    """The IoU of `a` and `b` estimated from at most `points` seeded points (ADR-0008).

    The points are `jittered_points(points, seed)` scaled to the box that
    holds both bodies' bounds; each is classed inside or outside each body's
    mesh at a chord of `chord_fraction` of that body's own diagonal, and the
    estimate is the count inside both over the count inside either. Its
    standard error is at most the binomial one over the points inside
    either, and its bias the meshes' chord error; identical bodies give
    exactly 1 and bodies with no common point exactly 0. Bits equal on
    repeat calls with the same seed. No point inside either body gives 0.
    Raises the kernel's `ArrisError` where it cannot tessellate a body.
    """
    low_a, high_a = _corners(model, a)
    low_b, high_b = _corners(model, b)
    low, high = np.minimum(low_a, low_b), np.maximum(high_a, high_b)
    samples = low + jittered_points(points, seed) * (high - low)
    in_a = inside(samples, _mesh(model, a, chord_fraction))
    in_b = inside(samples, _mesh(model, b, chord_fraction))
    either = int(np.count_nonzero(in_a | in_b))
    if either == 0:
        return 0.0
    return int(np.count_nonzero(in_a & in_b)) / either


def iou(
    model: arris.Model,
    a: arris.Body,
    b: arris.Body,
    *,
    budget: int,
    chord_fraction: float,
    points: int,
    seed: int,
) -> IouEstimate:
    """The IoU of `a` and `b`: the exact route under `budget`, else the sampled route.

    Any `ArrisError` from the exact route, the budget spent included, sends
    the pair to the sampled route, and `route` says which answered. Raises
    what the sampled route raises.
    """
    try:
        return IouEstimate(exact_iou(model, a, b, budget=budget), IouRoute.EXACT)
    except arris.ArrisError:
        value = sampled_iou(model, a, b, chord_fraction=chord_fraction, points=points, seed=seed)
        return IouEstimate(value, IouRoute.SAMPLED)

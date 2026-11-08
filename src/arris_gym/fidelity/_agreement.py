"""The agreement tolerance (ADR-0005): when arris and the oracle measure one part.

`measure_deltas` is how far a result's measures lie from the oracle's, one
number per measure; `within_tolerance` is whether they agree. The constants
are set from the calibration set (`tests/fixtures/fidelity/agree-*`), where
both kernels were held to a closed form, and are justified in ADR-0005.
"""

from __future__ import annotations

import math
from typing import Protocol

from pydantic import BaseModel, ConfigDict

from arris_gym.fidelity._oracle import OracleMeasures
from arris_gym.sandbox import Measures

# Volume and area: the larger of the two figures is the scale. On the 19
# calibration parts both kernels were within 7e-16 of the closed form and so
# of each other; Open CASCADE's `GProp` is exact on analytic surfaces. 1e-9 is
# six orders above that and the figure the oracle's own selftest holds it to.
VOLUME_REL = 1e-9
AREA_REL = 1e-9
# The centroid's distance, in the bounding-box diagonal. Measured: 2e-15
# absolute on parts 4 to 20 across; the same 1e-9 as volume.
CENTROID_DIAG = 1e-9
# The bounds, in absolute length: arris pads a body's box by its tolerance
# (2e-7 on every calibration part) where the oracle's tight box (the worker
# uses `AddOptimal`) is the part's own extent, to within 1e-7. A gap of
# 2e-7 is the padding, not a modelling difference; 1e-6 is five times it.
BOUNDS_ABS = 1e-6


class MeasureDeltas(BaseModel):
    """How far arris's measures lie from the oracle's, one figure per measure.

    `volume` and `area` are relative to the larger of the two; `centroid` is
    the distance between the centroids over the bounding-box diagonal;
    `bounds` is the largest coordinate difference, absolute; `faces` is
    arris's face count minus the oracle's. Face counts differ by convention
    (arris keeps the coplanar faces of a fuse split, Open CASCADE's `clean`
    merges them), so `faces` is carried and never judged (ADR-0005).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    volume: float
    area: float
    centroid: float
    bounds: float
    faces: int


def _relative(a: float, b: float) -> float:
    scale = max(abs(a), abs(b))
    return 0.0 if scale == 0.0 else abs(a - b) / scale


def _dist(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    # A fixed summation order, one thread: the sum reaches a verdict.
    total = 0.0
    for x, y in zip(a, b, strict=True):
        total += (x - y) * (x - y)
    return math.sqrt(total)


class Figures(Protocol):
    """The judged measures of a shape, whoever measured it: arris, the
    oracle, or a closed form."""

    @property
    def volume(self) -> float: ...
    @property
    def area(self) -> float: ...
    @property
    def centroid(self) -> tuple[float, float, float]: ...
    @property
    def bounds(self) -> tuple[tuple[float, float, float], tuple[float, float, float]]: ...


def figures_agree(a: Figures, b: Figures) -> bool:
    """Whether two shapes' judged measures lie inside the agreement tolerance,
    `b`'s bounding box giving the diagonal. Face counts are not part of it."""
    volume, area, centroid, bounds = _judged(a, b)
    return within_tolerance(
        MeasureDeltas(volume=volume, area=area, centroid=centroid, bounds=bounds, faces=0)
    )


def _judged(a: Figures, b: Figures) -> tuple[float, float, float, float]:
    lo, hi = b.bounds
    diagonal = _dist(lo, hi)
    centroid = _dist(a.centroid, b.centroid)
    corners = (*a.bounds[0], *a.bounds[1]), (*lo, *hi)
    return (
        _relative(a.volume, b.volume),
        _relative(a.area, b.area),
        centroid if diagonal == 0.0 else centroid / diagonal,
        max(abs(x - y) for x, y in zip(*corners, strict=True)),
    )


def measure_deltas(arris: Measures, oracle: OracleMeasures) -> MeasureDeltas:
    """The deltas between a result's measures and the oracle's.

    >>> from arris_gym.sandbox import Measures
    >>> a = Measures(volume=1.0, area=6.0, centroid=(0.5, 0.5, 0.5),
    ...     bounds=((0.0, 0.0, 0.0), (1.0, 1.0, 1.0)), faces=6, shells=1, genus=0,
    ...     face_kinds=(("plane", 6),))
    >>> o = OracleMeasures(volume=1.0, area=6.0, centroid=(0.5, 0.5, 0.5),
    ...     bounds=((0.0, 0.0, 0.0), (1.0, 1.0, 1.0)), faces=6, solids=1)
    >>> measure_deltas(a, o).volume
    0.0
    """
    volume, area, centroid, bounds = _judged(arris, oracle)
    return MeasureDeltas(
        volume=volume, area=area, centroid=centroid, bounds=bounds, faces=arris.faces - oracle.faces
    )


def within_tolerance(deltas: MeasureDeltas) -> bool:
    """Whether the deltas agree: every judged measure inside its constant.

    >>> within_tolerance(MeasureDeltas(volume=0.0, area=0.0, centroid=0.0, bounds=2e-7, faces=3))
    True
    """
    return (
        deltas.volume <= VOLUME_REL
        and deltas.area <= AREA_REL
        and deltas.centroid <= CENTROID_DIAG
        and deltas.bounds <= BOUNDS_ABS
    )

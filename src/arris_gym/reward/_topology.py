"""The topology term: a face-kind histogram overlap blended with the genus gap.

SEED.md §7.1 and docs/ARCHITECTURE.md §The reward; ADR-0009 fixes the
formula. `w · Σmin/Σmax` over the counts of faces of each of the kernel's
seven surface kinds, plus `(1 - w) / (1 + |Δgenus|)`, `w` the reward config's
`kind_weight`. A round hole and a faceted one differ in the histogram (one
cylinder against many planes), and a through hole and none in the genus.
Private: called in-process on bodies already read into a fresh model, which
only a worker does.
"""

from __future__ import annotations

import arris

# The kernel's seven surface kinds (docs/ARRIS_API.md, `SurfaceInfo.kind`),
# in a fixed order so the histogram never takes its order from a set.
SURFACE_KINDS = ("plane", "cylinder", "elliptic_cylinder", "cone", "sphere", "torus", "nurbs")


def kind_histogram(model: arris.Model, body: arris.Body) -> tuple[int, ...]:
    """The number of the body's faces of each of `SURFACE_KINDS`, in that order.

    Raises `ValueError` for a face of a kind the list lacks, so a kernel
    that grows an eighth kind fails loudly instead of dropping faces.
    """
    counts = dict.fromkeys(SURFACE_KINDS, 0)
    for face in model.faces(body):
        kind = model.surface(face).kind
        if kind not in counts:
            raise ValueError(f"unknown surface kind {kind!r}")
        counts[kind] += 1
    return tuple(counts[k] for k in SURFACE_KINDS)


def overlap(a: tuple[int, ...], b: tuple[int, ...]) -> float:
    """Σmin/Σmax of two histograms, in [0, 1]; two empty ones are 1."""
    high = sum(max(x, y) for x, y in zip(a, b, strict=True))
    if high == 0:
        return 1.0
    return sum(min(x, y) for x, y in zip(a, b, strict=True)) / high


def genus(model: arris.Model, body: arris.Body) -> int:
    """The body's genus from the kernel's Euler line.

    Raises `ValueError` where the checker reports no Euler line.
    """
    line = model.check(body).euler
    if line is None:
        raise ValueError("the kernel reports no Euler line for the body")
    return line.genus


def topology(
    model: arris.Model, candidate: arris.Body, target: arris.Body, *, kind_weight: float
) -> float:
    """The topology term in [0, 1]; exactly 1.0 for a body against its own bytes.

    Raises `ValueError` for a `kind_weight` outside [0, 1] and what
    `kind_histogram` and `genus` raise, and the kernel's `ArrisError`.
    """
    if not 0.0 <= kind_weight <= 1.0:
        raise ValueError(f"kind_weight must be in [0, 1], got {kind_weight}")
    shape = overlap(kind_histogram(model, candidate), kind_histogram(model, target))
    gap = abs(genus(model, candidate) - genus(model, target))
    # Written as a blend from the genus term, so two ones give exactly 1.0
    # whatever the weight (w + (1 - w) need not round to 1).
    by_genus = 1.0 / (1 + gap)
    return by_genus + kind_weight * (shape - by_genus)

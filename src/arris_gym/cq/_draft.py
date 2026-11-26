"""Analytic solids for a single circle or rectangle with tapered sides (ADR-0027)."""

from __future__ import annotations

import math

from arris.build import Sketch, Solid, Workplane

_FULL_TURN = 2 * math.pi
_QUARTER_TURN = math.pi / 2


def _opposite(vector: tuple[float, float, float]) -> tuple[float, float, float]:
    return (-vector[0], -vector[1], -vector[2])


def disc_draft(plane: Workplane, radius: float, height: float, inset: float) -> Solid:
    """Revolve a circular draft's meridian, ending at the apex if the cap collapses."""
    section = Workplane.of(plane.origin, _opposite(plane.y), plane.x)
    cap = radius - inset
    if cap <= 0:
        points = [(0.0, 0.0), (radius, 0.0), (0.0, height * (radius / inset))]
    else:
        points = [(0.0, 0.0), (radius, 0.0), (cap, height), (0.0, height)]
    return section.polygon(points).revolve("y", _FULL_TURN)


def rect_draft(
    sketch: Sketch, plane: Workplane, width: float, depth: float, height: float, inset: float
) -> Solid:
    """Build the planar inward offset or the rounded outward offset of a rectangle."""
    if inset < 0:
        return _outward_rect(sketch, plane, width / 2, depth / 2, height, -inset)
    half_short = min(width, depth) / 2
    if inset >= half_short:
        if width < depth:
            plane = Workplane.of(plane.origin, plane.z, plane.y)
        return _collapsed_rect(
            plane, max(width, depth) / 2, half_short, height * (half_short / inset)
        )
    cap = plane.offset(height).rect(width - 2 * inset, depth - 2 * inset)
    return Sketch.loft((sketch, cap), kind="ruled")


def _outward_rect(
    sketch: Sketch,
    plane: Workplane,
    half_width: float,
    half_depth: float,
    height: float,
    spread: float,
) -> Solid:
    """Fuse a prism, four wedges and four quarter cones along their shared sides."""
    sides: list[Solid] = []
    corners: list[Solid] = []
    for x, y in ((1, 0), (0, 1), (-1, 0), (0, -1)):
        radial = plane.direction(x, y)
        tangent = plane.direction(-y, x)
        side_midpoint = plane.point(x * half_width, y * half_depth)
        half_length = half_depth if x else half_width
        side = Workplane.of(side_midpoint, tangent, radial).offset(-half_length)
        sides.append(
            side.polygon([(0, 0), (0, -height), (spread, -height)]).extrude(2 * half_length)
        )
        vertex = plane.point((x - y) * half_width, (y + x) * half_depth)
        corner = Workplane.of(vertex, _opposite(tangent), radial)
        corners.append(
            corner.polygon([(0, 0), (spread, height), (0, height)]).revolve("y", _QUARTER_TURN)
        )
    return sketch.extrude(height).fuse(*sides, *corners)


def _collapsed_rect(plane: Workplane, long: float, short: float, height: float) -> Solid:
    """Cut the two ends of a triangular prism to leave a ridge or a pyramid."""
    side = Workplane.of(plane.point(-long, 0), plane.x, plane.y)
    prism = side.polygon([(-short, 0), (short, 0), (0, height)]).extrude(2 * long)
    ends = Workplane.of(plane.point(0, short), _opposite(plane.y), plane.x)
    left = ends.polygon([(-long, 0), (-long + short, height), (-long, height)])
    right = ends.polygon([(long, 0), (long, height), (long - short, height)])
    return prism.cut(left.extrude(2 * short), right.extrude(2 * short))

"""Recognize the deferred literal polygon loft contexts without building a model."""

from __future__ import annotations

import ast
import math
from collections.abc import Callable, Sequence

from arris_gym.cq._profile_limits import CLOSE_GAP, MAX_CURVED_SIDES

_Point = tuple[float, float]
# Conservative lower bound on the sine of the angle between nonparallel
# edges. This is larger than the pinned wheel's 1e-12 angular tolerance.
_NONPARALLEL = 1e-9


def _number(node: ast.expr) -> float | None:
    sign = 1
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.UAdd | ast.USub):
        sign = -1 if isinstance(node.op, ast.USub) else 1
        node = node.operand
    if (
        isinstance(node, ast.Constant)
        and isinstance(node.value, int | float)
        and not isinstance(node.value, bool)
    ):
        try:
            value = float(node.value) * sign
        except OverflowError:
            return None
        return value if math.isfinite(value) else None
    return None


def _polygon(node: ast.expr) -> tuple[_Point, ...] | None:
    if not isinstance(node, ast.Tuple | ast.List):
        return None
    points = []
    for point in node.elts:
        if not isinstance(point, ast.Tuple | ast.List) or len(point.elts) != 2:
            return None
        x, y = map(_number, point.elts)
        if x is None or y is None:
            return None
        points.append((x, y))
    if len(points) > 1:
        (u0, v0), (u1, v1) = points[0], points[-1]
        if math.hypot(u1 - u0, v1 - v0) <= CLOSE_GAP:
            points.pop()
    return tuple(points) if len(points) >= 3 else None


def _directions(points: Sequence[_Point]) -> tuple[_Point, ...]:
    directions = []
    for i, (x, y) in enumerate(points):
        u, v = points[i - 1]
        dx, dy = x - u, y - v
        length = math.hypot(dx, dy)
        if not length or not math.isfinite(length):
            return ()
        directions.append((dx / length, dy / length))
    return tuple(directions)


def _too_many_curved_sides(first: tuple[_Point, ...], second: tuple[_Point, ...]) -> bool:
    n = len(first)
    if n != len(second) or n <= MAX_CURVED_SIDES:
        return False
    a, b = _directions(first), _directions(second)
    if not a or not b:
        return False
    # Any cyclic pairing the runtime can choose has to exceed the limit.
    # For parallel cap planes, nonparallel paired edges imply a nonplanar side.
    for directions in (b, b[::-1]):
        for start in range(n):
            curved = 0
            for i, (x, y) in enumerate(a):
                u, v = directions[(start + i) % n]
                if abs(x * v - y * u) > _NONPARALLEL:
                    curved += 1
                    if curved > MAX_CURVED_SIDES:
                        break
            else:
                return False
    return True


def _receiver(node: ast.expr, name: str) -> ast.expr | None:
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == name
        and not node.args
        and not node.keywords
    ):
        return node.func.value
    return None


def deferred_polygon_loft(operand: ast.expr, dotted: Callable[[ast.expr], str | None]) -> bool:
    """Prove a direct literal polygon chain exceeds the pinned loft's supported context."""
    sections = []
    while (profile := _receiver(operand, "close")) is not None:
        if (
            not isinstance(profile, ast.Call)
            or not isinstance(profile.func, ast.Attribute)
            or profile.func.attr != "polyline"
            or len(profile.args) != 1
            or profile.keywords
        ):
            return False
        polygon = _polygon(profile.args[0])
        if polygon is None:
            return False
        sections.append(polygon)
        previous = profile.func.value
        if isinstance(previous, ast.Call) and dotted(previous.func) == "cadquery.Workplane":
            return len(sections) > 2 or (len(sections) == 2 and _too_many_curved_sides(*sections))
        if (
            not isinstance(previous, ast.Call)
            or not isinstance(previous.func, ast.Attribute)
            or previous.func.attr != "workplane"
            or previous.args
            or len(previous.keywords) != 1
            or previous.keywords[0].arg != "offset"
            or not _number(previous.keywords[0].value)
        ):
            return False
        operand = previous.func.value
    return False

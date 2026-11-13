"""`Workplane`: a plane, a stack of objects and the workplane it came from.

ADR-0007. Every call returns a new `Workplane`; none changes one in place.
Private: `arris_gym.cq` exports `Workplane`.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import NoReturn

import arris
import arris.build

from arris_gym.cq._forms import census_form, numbers_of, shape_of
from arris_gym.cq._unsupported import UnsupportedApi, is_python_name
from arris_gym.cq._vector import Vector

__all__ = ["Workplane", "is_python_name"]

# The default named plane; the constructor admits the measured corpus planes.
_XY = "XY"


def _zx() -> arris.build.Workplane:
    """CadQuery's `ZX` plane: local x along world +z, y along +x, normal +y."""
    return arris.build.Workplane((0.0, 0.0, 0.0), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0))


# CadQuery 2.3.0's named planes the subset admits, each an `arris.build`
# workplane with the same frame (`Plane.named`, PROVENANCE.md).
_NAMED_PLANES: dict[str, Callable[[], arris.build.Workplane]] = {
    _XY: arris.build.Workplane.XY,
    "YZ": arris.build.Workplane.YZ,
    "XZ": arris.build.Workplane.XZ,
    "ZX": _zx,
}
# CadQuery's degrees-to-radians factor, applied as it applies it (one
# multiplication by pi / 180): not a tolerance.
_RADIANS_PER_DEGREE = math.pi / 180.0
# The factor CadQuery's `Solid.revolve` turns degrees into radians by,
# `2 * pi / 360.0` (`occ_impl/shapes.py`), kept apart from `transformed`'s
# so each call rounds as CadQuery's does: not a tolerance.
_REVOLVE_RADIANS_PER_DEGREE = 2 * math.pi / 360.0
# CadQuery's `close` adds a segment back to the path's first point only when
# the gap is wider than this, its numerical-error threshold (`cq.py`); a
# narrower gap is no segment. In plane units.
_CLOSE_GAP = 1e-6
_ZERO = Vector(0, 0, 0)


@dataclass(frozen=True)
class _Segment:
    """One drawn segment of a pending path, in plane coordinates.

    A straight line to `to` when `via` is `None`, else a circular arc to
    `to` through `via` (`threePointArc`'s middle point).
    """

    to: tuple[float, float]
    via: tuple[float, float] | None = None

    def ending_at(self, to: tuple[float, float]) -> _Segment:
        """This segment of the same kind, ending at `to` instead."""
        return _Segment(to, self.via)

    def built(self) -> arris.Segment:
        """The kernel's segment: `Segment.arc` takes the end first, then the middle point."""
        if self.via is None:
            return arris.Segment.line(self.to)
        return arris.Segment.arc(self.to, self.via)


@dataclass(frozen=True)
class _Path:
    """A pending path in plane coordinates: its start and the segments drawn from it.

    A path with no segment is a `moveTo` point with nothing drawn yet
    (`polyline` refuses a list of one, so only `moveTo` makes it). `close`
    turns it into an `arris.build.Sketch`.
    """

    start: tuple[float, float]
    segments: tuple[_Segment, ...] = ()

    @property
    def end(self) -> tuple[float, float]:
        """Where the next segment starts: the last segment's end, else the start."""
        return self.segments[-1].to if self.segments else self.start

    def to(self, x: float, y: float) -> _Path:
        """This path with a straight segment on to `(x, y)`."""
        return _Path(self.start, (*self.segments, _Segment((float(x), float(y)))))

    def arc(self, via: tuple[float, float], to: tuple[float, float]) -> _Path:
        """This path with a circular arc on to `to` through `via`."""
        return _Path(self.start, (*self.segments, _Segment(to, via)))


def _uv(point: object, refusal: str) -> tuple[float, float]:
    """A drawn point as plane coordinates: two numbers, else outside the subset.

    CadQuery also takes three (the third along the normal) and a `Vector`;
    a path that leaves its plane is not one the subset draws. `refusal` is
    the `UnsupportedApi` message, `{}` standing for what the point is.
    """
    pair = numbers_of(point, (2,))
    if pair is None:
        raise UnsupportedApi(refusal.format(shape_of(point)))
    return (pair[0], pair[1])


def _axis_point(point: object) -> tuple[float, ...]:
    """A `revolve` axis point as numbers: two or three, else outside the subset."""
    numbers = numbers_of(point, (2, 3))
    if numbers is None:
        shape = shape_of(point)
        of = f"tuple of {shape}" if shape.endswith(" numbers") else shape
        raise UnsupportedApi(f"Workplane.revolve(num, {of})")
    return numbers


class Workplane:
    """CadQuery's `Workplane` over `arris.build`: a frozen value.

    It holds its plane (an `arris.build.Workplane`), its **stack** (the
    objects its call made, newest last) and its parent (the workplane it was
    called on, `None` for one made by `cq.Workplane(...)`). Guarantees: no
    call changes a `Workplane`; a name the subset lacks raises
    `UnsupportedApi` naming it (`Workplane.sphere`), never `AttributeError`;
    setting an attribute raises `UnsupportedApi` too, and a copy is the
    workplane itself. Admits `"XY"` (x +x, y +y, normal +z), `"YZ"`
    (x +y, y +z, normal +x), `"XZ"` (x +x, y +z, normal -y) and `"ZX"`
    (x +z, y +x, normal +y); refuses other named planes. `origin`, three
    numbers in world coordinates, moves the plane's origin there and keeps
    its axes, as CadQuery's `Plane.named` does; any other `origin` is
    outside the subset.

    >>> import arris_gym.cq as cq
    >>> wp = cq.Workplane("XY")
    >>> try:
    ...     wp.sphere(1.0)
    ... except cq.UnsupportedApi as error:
    ...     print(error)
    Workplane.sphere
    """

    __slots__ = ("_parent", "_plane", "_stack")

    _plane: arris.build.Workplane
    _stack: tuple[object, ...]
    _parent: Workplane | None

    @census_form("cq.Workplane", [("str",)], keywords={"origin": ("tuple",)})
    def __init__(self, inPlane: str = _XY, origin: tuple[float, float, float] = (0, 0, 0)) -> None:
        if type(inPlane) is not str or inPlane not in _NAMED_PLANES:
            raise UnsupportedApi(f"cq.Workplane({inPlane!r})")
        at = numbers_of(origin, (3,))
        if at is None:
            # CadQuery also takes two numbers (z = 0); the corpora write three.
            shape = shape_of(origin)
            of = f"tuple of {shape}" if shape.endswith(" numbers") else shape
            raise UnsupportedApi(f"cq.Workplane(str; origin={of})")
        named = _NAMED_PLANES[inPlane]()
        plane = arris.build.Workplane((at[0], at[1], at[2]), named.x, named.y, named.z)
        object.__setattr__(self, "_plane", plane)
        object.__setattr__(self, "_stack", ())
        object.__setattr__(self, "_parent", None)

    def _derive(self, *objects: object) -> Workplane:
        """A new workplane on this one's plane, `objects` its stack, this one its parent."""
        child = object.__new__(Workplane)
        object.__setattr__(child, "_plane", self._plane)
        object.__setattr__(child, "_stack", objects)
        object.__setattr__(child, "_parent", self)
        return child

    def _derive_on(self, plane: arris.build.Workplane, *objects: object) -> Workplane:
        """A new workplane on `plane`, `objects` its stack, this one its parent."""
        child = self._derive(*objects)
        object.__setattr__(child, "_plane", plane)
        return child

    def _solids(self) -> tuple[arris.build.Solid, ...]:
        """The solids on the stack, in stack order: no call puts more than one there.

        A CadQuery compound, several solids that do not meet, is one solid
        whose body holds a shell per piece (ADR-0016): `fuse` and `cut`
        return it so.
        """
        return tuple(o for o in self._stack if isinstance(o, arris.build.Solid))

    def _base_solid(self) -> arris.build.Solid | None:
        """The solid a combining call acts on: the nearest in this chain, else `None`.

        CadQuery looks at this workplane's stack, then its parent's, and so
        on, and fuses with a compound as with a solid.
        """
        node: Workplane | None = self
        while node is not None:
            solids = node._solids()
            if solids:
                return solids[0]
            node = node._parent
        return None

    def _combined(self, new: arris.build.Solid) -> Workplane:
        """A workplane on this plane with `new` fused into the chain's solid, if any.

        Where the two are disjoint, `fuse` returns one solid with the shells
        of both: CadQuery's compound of two solids (ADR-0016).
        """
        base = self._base_solid()
        if base is None:
            return self._derive(new)
        return self._derive(base.fuse(new))

    def _pending_sketch(self) -> arris.build.Sketch:
        """The one sketch the stack holds, which `extrude` and `revolve` consume.

        Raises `ValueError` (CadQuery's words, `runtime`) for any other stack.
        """
        sketches = [o for o in self._stack if isinstance(o, arris.build.Sketch)]
        if len(sketches) != 1 or len(self._stack) != 1:
            raise ValueError("No pending wires present")
        return sketches[0]

    def _pen(self) -> _Path:
        """The path a `lineTo` or a `threePointArc` goes on from: the last object, or the origin.

        CadQuery reads the last object only: a drawn path goes on from its
        end, a `moveTo` point starts one, an empty stack starts at the
        origin. Anything else is CadQuery's `RuntimeError` (`runtime`).
        """
        if not self._stack:
            return _Path((0.0, 0.0))
        last = self._stack[-1]
        if isinstance(last, _Path):
            return last
        raise RuntimeError(f"Cannot convert object type '{type(last).__name__}' to vector")

    def _refuse_pending(self, form: str) -> None:
        """Raise `UnsupportedApi` naming `form` when the stack holds a pending wire.

        CadQuery keeps every pending wire in a context the whole chain
        shares and builds them together; the subset holds one on the stack,
        so a call that would start a second beside it is outside it.
        """
        if any(isinstance(o, (_Path, arris.build.Sketch)) for o in self._stack):
            raise UnsupportedApi(f"{form} on a pending wire")

    def _operand(self, other: object, form: str) -> tuple[arris.build.Solid, ...]:
        """The solids of the workplane given to `union` or `cut`; `form` names the call."""
        if not isinstance(other, Workplane):
            raise UnsupportedApi(f"{form} with {type(other).__name__}")
        solids = other._solids()
        if not solids:
            raise ValueError(f"{form} was given a Workplane holding no solid")
        return solids

    @census_form("Workplane.transformed", keywords={"rotate": ("call",), "offset": ("call",)})
    def transformed(self, rotate: Vector = _ZERO, offset: Vector = _ZERO) -> Workplane:
        """A workplane moved to `offset` and turned by `rotate`, its stack empty.

        `offset` is a point in this workplane's coordinates. `rotate` is three
        angles in degrees, right-handed about this workplane's own x, y and z
        axes; the turn is CadQuery's matrix product Rx·Ry·Rz, so the z angle
        acts first and every axis is this workplane's, not the turned one's.
        A zero rotation leaves the axes exactly as they were.

        >>> import arris_gym.cq as cq
        >>> wp = cq.Workplane("XY").transformed(
        ...     offset=cq.Vector(1, 2, 3), rotate=cq.Vector(0, 0, 0)
        ... )
        >>> [round(c, 9) for c in wp.box(2, 2, 2)._solids()[0].measure().centroid]
        [1.0, 2.0, 3.0]
        """
        self._refuse_pending("Workplane.transformed")
        plane = self._plane
        turned = plane
        # Each `rotated` turns about a fixed world direction through the
        # origin, so applying z, then y, then x about the parent's axes gives
        # Rx·Ry·Rz (CadQuery's `Plane.rotated`, `occ_impl/geom.py`).
        for degrees, axis in ((rotate.z, plane.z), (rotate.y, plane.y), (rotate.x, plane.x)):
            turned = turned.rotated(degrees * _RADIANS_PER_DEGREE, axis)
        origin = plane.point(offset.x, offset.y, offset.z)
        return self._derive_on(arris.build.Workplane(origin, turned.x, turned.y, turned.z))

    @census_form("Workplane.workplane", keywords={"offset": ("num",)})
    def workplane(self, offset: float = 0.0) -> Workplane:
        """A new workplane `offset` along this one's normal, its axes kept, its stack empty.

        On an empty stack it starts from this workplane's origin. On a stack
        holding one solid it starts from the plane through that solid's
        centroid: this origin moved along the normal to the centroid's height,
        not to the centroid itself (CadQuery's `centerOption="ProjectedOrigin"`,
        read on the oracle: `ok-workplane-*`). The solid stays in the chain
        for the next call to fuse with. A compound counts as one solid, its
        centroid that of all its pieces (CadQuery's `Shape.Center`, read on the
        oracle: `ok-workplane-on-compound`). Refuses, as `UnsupportedApi`, a
        pending wire on the stack.

        >>> import arris_gym.cq as cq
        >>> wp = cq.Workplane("XY").box(2, 2, 2).workplane(offset=3)
        >>> wp._plane.origin
        (0.0, 0.0, 3.0)
        """
        self._refuse_pending("Workplane.workplane")
        plane = self._plane
        o, n = plane.origin, plane.z
        if not self._stack:
            center = o
        else:
            # Past `_refuse_pending`, a stack that is not empty holds one solid.
            (solid,) = self._stack
            assert isinstance(solid, arris.build.Solid)
            center = solid.measure().centroid
        # As CadQuery does it: the origin projected onto the plane through
        # `center` (`Vector.projectToPlane`), then moved by `offset` along the
        # unit normal (`Workplane.workplane`, `cq.py`).
        height = (o[0] - center[0]) * n[0] + (o[1] - center[1]) * n[1] + (o[2] - center[2]) * n[2]
        projected = (o[0] - n[0] * height, o[1] - n[1] * height, o[2] - n[2] * height)
        at = (
            projected[0] + n[0] * offset,
            projected[1] + n[1] * offset,
            projected[2] + n[2] * offset,
        )
        return self._derive_on(arris.build.Workplane(at, plane.x, plane.y, plane.z))

    @census_form("Workplane.box", [("num",)] * 3)
    def box(self, length: float, width: float, height: float) -> Workplane:
        """A `length` by `width` by `height` box centred on the origin or a `moveTo` point.

        `length` runs along the workplane's x, `width` along its y and
        `height` along its normal; the box is the one solid on the new stack.
        On an empty stack it is centred on the workplane's origin; on a stack
        holding only a `moveTo` point, on that point, in the plane's own axes
        (CadQuery's `eachpoint` over one point, `centered=True`). A box on a
        workplane whose chain holds a solid further up is fused with it, as
        CadQuery's `combine=True` does. Refuses, as `UnsupportedApi`, a stack
        holding a drawn path or a sketch, and one holding a solid: there
        CadQuery centres the box on the solid's centre of mass (read on the
        oracle: `unsupported-box-on-solid`), which the subset does not model.

        >>> import arris_gym.cq as cq
        >>> round(cq.Workplane("XY").box(2, 3, 4)._solids()[0].measure().volume, 9)
        24.0
        >>> wp = cq.Workplane("XY").moveTo(3, 1).box(2, 4, 6)
        >>> [round(c, 9) + 0.0 for c in wp._solids()[0].measure().centroid]
        [3.0, 1.0, 0.0]
        """
        point = self._stack[0] if len(self._stack) == 1 else None
        if isinstance(point, _Path) and not point.segments:
            center = point.start
        else:
            self._refuse_pending("Workplane.box")
            if self._solids():
                # CadQuery centres the box on the solid's `Center()` (its
                # centre of mass, `eachpoint`), which the subset does not model.
                raise UnsupportedApi("Workplane.box on a stack holding a solid")
            center = (0.0, 0.0)
        if min(length, width, height) < 0:
            raise ValueError(
                f"Workplane.box({length}, {width}, {height}): a negative dimension "
                "(CadQuery's Standard_DomainError)"
            )
        sketch = self._plane.offset(-height / 2).rect(length, width, center=center)
        return self._combined(sketch.extrude(height))

    @census_form("Workplane.cylinder", [("num",)] * 2)
    def cylinder(self, height: float, radius: float) -> Workplane:
        """A cylinder of `height` and `radius` centred on the origin or a `moveTo` point.

        Its axis runs along the workplane's normal, and it is centred on the
        point in all three axes: `height / 2` either side of the plane, as
        CadQuery's `centered=True` places it (read on the oracle:
        `test_cq_cylinder.py`). On an empty stack it is centred on the
        workplane's origin; on a stack holding only a `moveTo` point, on that
        point, in the plane's own axes (CadQuery's `eachpoint` over one
        point). A cylinder on a workplane whose chain holds a solid further
        up is fused with it, as CadQuery's `combine=True` does. Refuses, as
        `UnsupportedApi`, a stack holding a drawn path or a sketch, and one
        holding a solid or a compound: there CadQuery centres the cylinder on
        the object's `Center()`, as it does a box, which the subset does not
        model (read on the oracle: `unsupported-cylinder-*`). Raises
        `ValueError` (`runtime`) for a height not positive or a negative
        radius, where CadQuery raises `Standard_ConstructionError`, and for a
        zero radius, where CadQuery builds a shape its checker rejects
        (`runtime-cylinder-zero-radius`, a `by_design` row).

        >>> import math
        >>> import arris_gym.cq as cq
        >>> (solid,) = cq.Workplane("XY").cylinder(4, 1)._solids()
        >>> round(solid.measure().volume / math.pi, 9)
        4.0
        >>> wp = cq.Workplane("XY").moveTo(3, 1).cylinder(2, 1)
        >>> [round(c, 9) + 0.0 for c in wp._solids()[0].measure().centroid]
        [3.0, 1.0, 0.0]
        """
        point = self._stack[0] if len(self._stack) == 1 else None
        if isinstance(point, _Path) and not point.segments:
            center = point.start
        else:
            self._refuse_pending("Workplane.cylinder")
            if self._solids():
                # As with `box`: CadQuery centres it on the solid's `Center()`.
                raise UnsupportedApi("Workplane.cylinder on a stack holding a solid")
            center = (0.0, 0.0)
        named = f"Workplane.cylinder({height}, {radius})"
        if height <= 0:
            raise ValueError(
                f"{named}: a height not positive (CadQuery's Standard_ConstructionError)"
            )
        if radius < 0:
            raise ValueError(f"{named}: a negative radius (CadQuery's Standard_ConstructionError)")
        if radius == 0:
            raise ValueError(f"{named}: a zero radius (CadQuery builds an invalid shape)")
        sketch = self._plane.offset(-height / 2).circle(radius, center=center)
        return self._combined(sketch.extrude(height))

    @census_form("Workplane.circle", [("num",)])
    def circle(self, radius: float) -> Workplane:
        """A pending circle of `radius`, centred on the workplane's origin or a `moveTo` point.

        The circle is the one sketch on the new stack, waiting for `extrude`
        or `revolve`. On an empty stack it is centred on the origin; on a
        stack holding only a `moveTo` point, on that point, in the plane's
        own axes (CadQuery's `eachpoint` over one point). Refuses, as
        `UnsupportedApi`, any other stack: CadQuery centres a circle on each
        object there, which the subset does not model (`transformed` leaves
        a stack empty).

        >>> import arris_gym.cq as cq
        >>> round(cq.Workplane("XY").circle(1).extrude(2)._solids()[0].measure().volume, 9)
        6.283185307
        >>> wp = cq.Workplane("XY").moveTo(2, 0).circle(1).extrude(1)
        >>> [round(c, 9) + 0.0 for c in wp._solids()[0].measure().centroid]
        [2.0, 0.0, 0.5]
        """
        if not self._stack:
            return self._derive(self._plane.circle(radius))
        point = self._stack[0] if len(self._stack) == 1 else None
        if not isinstance(point, _Path) or point.segments:
            raise UnsupportedApi("Workplane.circle on a non-empty stack")
        return self._derive(self._plane.circle(radius, center=point.start))

    @census_form("Workplane.extrude", [("num",)])
    def extrude(self, distance: float) -> Workplane:
        """The pending sketch extruded `distance` along the plane's normal.

        The solid grows from the plane, not about it, and is fused with the
        chain's solid if there is one (CadQuery's `combine=True`). Raises
        `ValueError` (`runtime`) when the stack holds no pending sketch.

        >>> import arris_gym.cq as cq
        >>> wp = cq.Workplane("XY").circle(1).extrude(2)
        >>> round(wp._solids()[0].measure().centroid[2], 9)
        1.0
        """
        return self._combined(self._pending_sketch().extrude(distance))

    @census_form("Workplane.moveTo", [("num",)] * 2)
    def moveTo(self, x: float = 0, y: float = 0) -> Workplane:
        """A pending path starting at `(x, y)` in the workplane's coordinates.

        Nothing is drawn: the next `lineTo` starts there. A solid in the
        chain stays there for `revolve` or `extrude` to fuse with. Refuses,
        as `UnsupportedApi`, a stack that holds a pending wire already.

        >>> import arris_gym.cq as cq
        >>> wp = cq.Workplane("XY").moveTo(1, 0).lineTo(2, 0).lineTo(2, 1).close()
        >>> round(wp.extrude(1)._solids()[0].measure().volume, 9)
        0.5
        """
        self._refuse_pending("Workplane.moveTo")
        return self._derive(_Path((float(x), float(y))))

    @census_form("Workplane.lineTo", [("num",)] * 2)
    def lineTo(self, x: float, y: float) -> Workplane:
        """The pending path with a straight segment on to `(x, y)`.

        The segment starts where the last object leaves off: the end of the
        path drawn so far, a `moveTo` point, or the plane's origin on an
        empty stack. Raises `RuntimeError` (CadQuery's, `runtime`) when the
        last object is a solid or a closed sketch.

        >>> import arris_gym.cq as cq
        >>> wp = cq.Workplane("XY").lineTo(3, 0).lineTo(0, 4).close()
        >>> round(wp.extrude(1)._solids()[0].measure().volume, 9)
        6.0
        """
        return self._derive(self._pen().to(x, y))

    @census_form("Workplane.threePointArc", [("tuple",)] * 2)
    def threePointArc(self, point1: object, point2: object) -> Workplane:
        """The pending path with a circular arc through `point1` on to `point2`.

        The arc starts where `lineTo` would: the end of the path drawn so
        far, a `moveTo` point, or the plane's origin on an empty stack
        (CadQuery's `_findFromPoint`). Both points are two numbers in the
        workplane's coordinates; one of three numbers or a `Vector` is
        outside the subset. Raises `RuntimeError` (CadQuery's, `runtime`)
        when the last object is a solid, a compound, a closed sketch or a
        pending circle (read on the oracle: `runtime-three-point-arc-*`).
        Three points on one line, two that coincide included, are no arc:
        CadQuery raises here, while the kernel refuses the profile when it
        is built (`arris_refusal`, `arris-refusal-three-point-arc-*`).

        >>> import math
        >>> import arris_gym.cq as cq
        >>> half = cq.Workplane("XY").moveTo(-2, 0).threePointArc((0, 2), (2, 0)).close()
        >>> round(half.extrude(1)._solids()[0].measure().volume / math.pi, 9)
        2.0
        """
        path = self._pen()
        refusal = "Workplane.threePointArc(tuple, tuple) with a point of {}"
        return self._derive(path.arc(_uv(point1, refusal), _uv(point2, refusal)))

    @census_form("Workplane.polyline", [("list",)])
    def polyline(self, listOfXYTuple: Sequence[object]) -> Workplane:
        """A pending path through the points of `listOfXYTuple`, in order.

        It starts at the first point, not at the current one, as CadQuery's
        `includeCurrent=False` does. Refuses, as `UnsupportedApi`, a stack
        that holds a pending wire already and a list of fewer than two
        points: CadQuery's one-point polyline is no `moveTo` point (read on
        the oracle: `unsupported-polyline-one-point-*`).

        >>> import arris_gym.cq as cq
        >>> wp = cq.Workplane("XY").polyline([(0, 0), (3, 0), (0, 4)]).close()
        >>> round(wp.extrude(1)._solids()[0].measure().volume, 9)
        6.0
        """
        self._refuse_pending("Workplane.polyline")
        points = tuple(_uv(p, "Workplane.polyline(list with a point of {})") for p in listOfXYTuple)
        if len(points) < 2:
            # CadQuery leaves no `moveTo` point here: a box or a circle after
            # it is centred on the origin and a `lineTo` starts there (read on
            # the oracle). A one-point `_Path` stays a `moveTo` point only.
            count = f"{len(points)} point" + ("" if len(points) == 1 else "s")
            raise UnsupportedApi(f"Workplane.polyline(list of {count})")
        return self._derive(_Path(points[0], tuple(_Segment(p) for p in points[1:])))

    @census_form("Workplane.close")
    def close(self) -> Workplane:
        """The pending path closed back to its start: a sketch on the stack.

        A straight segment back to the first point is added unless the path
        ends within CadQuery's `_CLOSE_GAP` of it, in which case its last
        segment, a line or an arc, ends exactly at the first point. Raises
        `ValueError` (CadQuery's words, `runtime`) when nothing has been
        drawn; a path the kernel cannot close (a single segment) ends in the
        kernel's own words.

        >>> import arris_gym.cq as cq
        >>> closed = cq.Workplane("XY").polyline([(0, 0), (1, 0), (1, 1)]).close()
        >>> closed._solids()
        ()
        """
        last = self._stack[-1] if self._stack else None
        if not isinstance(last, _Path) or not last.segments:
            raise ValueError("No start point specified - cannot close")
        segments = last.segments
        (u0, v0), (u1, v1) = last.start, last.end
        if math.hypot(u1 - u0, v1 - v0) <= _CLOSE_GAP:
            # The last segment, a line or an arc, ends exactly at the start.
            segments = (*segments[:-1], segments[-1].ending_at(last.start))
        else:
            segments = (*segments, _Segment(last.start))
        loop = arris.Loop.path(last.start, [segment.built() for segment in segments])
        return self._derive(arris.build.Sketch(self._plane, loop))

    @census_form("Workplane.revolve", [("num",), ("tuple",), ("tuple",)])
    def revolve(
        self,
        angleDegrees: float,
        axisStart: object,
        axisEnd: object,
    ) -> Workplane:
        """The pending sketch turned `angleDegrees` about the axis from `axisStart` to `axisEnd`.

        The axis points are in the workplane's coordinates (two or three of
        them, the third along its normal); the turn is right-handed about
        the direction from start to end. The angle is taken modulo 360 and a
        multiple of 360 is a full turn, as in CadQuery. The solid is fused
        with the chain's solid if there is one (`combine=True`). Raises
        `ValueError` (`runtime`) when the stack holds no pending sketch.

        >>> import math
        >>> import arris_gym.cq as cq
        >>> ring = cq.Workplane("XY").polyline([(1, 0), (2, 0), (2, 1), (1, 1)]).close()
        >>> (solid,) = ring.revolve(360, (0, 0, 0), (0, 1, 0))._solids()
        >>> round(solid.measure().volume / math.pi, 9)
        3.0
        """
        sketch = self._pending_sketch()
        start_at, end_at = _axis_point(axisStart), _axis_point(axisEnd)
        degrees = angleDegrees % 360.0
        if degrees == 0:
            degrees = 360.0
        start = self._plane.point(*start_at)
        end = self._plane.point(*end_at)
        direction = (end[0] - start[0], end[1] - start[1], end[2] - start[2])
        made = arris.build.default_model().revolve(
            sketch.profile(), start, direction, degrees * _REVOLVE_RADIANS_PER_DEGREE
        )
        return self._combined(arris.build.Solid.of(made))

    @census_form("Workplane.union", [None])
    def union(self, toUnion: Workplane) -> Workplane:
        """The chain's solid fused with the solid of `toUnion`, on this plane.

        On a chain that holds no solid, the result is `toUnion`'s solid
        itself, where it stands, on this plane (CadQuery's `union` with no
        solid to fuse with, read on the oracle: `ok-union-on-empty-chain-*`).
        Raises `ValueError` (a CadQuery error, `runtime`) when `toUnion`
        holds no solid. Disjoint solids make a compound: one solid whose body
        holds a shell per piece (ADR-0016).

        >>> import arris_gym.cq as cq
        >>> a = cq.Workplane("XY").box(2, 2, 2)
        >>> b = cq.Workplane("XY").transformed(offset=cq.Vector(1, 1, 1)).box(2, 2, 2)
        >>> round(a.union(b)._solids()[0].measure().volume, 9)
        15.0
        """
        self._refuse_pending("Workplane.union")
        others = self._operand(toUnion, "Workplane.union(Workplane)")
        # With no solid in the chain, the first `_combined` puts the operand's
        # solid on the stack as it is.
        result = self
        for other in others:
            result = result._combined(other)
        return result

    @census_form("Workplane.cut", [None])
    def cut(self, toCut: Workplane) -> Workplane:
        """The chain's solid less the solid of `toCut`, on this plane.

        Raises `ValueError` (`runtime`) when the chain holds no solid, in
        CadQuery's words (read on the oracle: `runtime-cut-on-empty-chain`),
        or `toCut` holds none. A cut that splits its base leaves a compound, one
        solid with a shell per piece (ADR-0016).

        >>> import arris_gym.cq as cq
        >>> a = cq.Workplane("XY").box(4, 4, 4)
        >>> b = cq.Workplane("XY").box(1, 1, 6)
        >>> round(a.cut(b)._solids()[0].measure().volume, 9)
        60.0
        """
        self._refuse_pending("Workplane.cut")
        tools = self._operand(toCut, "Workplane.cut(Workplane)")
        base = self._base_solid()
        if base is None:
            raise ValueError("Cannot find a solid on the stack or in the parent chain")
        # A cut that splits its base is CadQuery's compound: one solid with a
        # shell per piece (ADR-0016).
        return self._derive(base.cut(*tools))

    def __copy__(self) -> Workplane:
        return self

    def __deepcopy__(self, memo: object) -> Workplane:
        return self

    def __getattr__(self, name: str) -> NoReturn:
        if is_python_name(name):
            raise AttributeError(name)
        raise UnsupportedApi(f"Workplane.{name}")

    def __setattr__(self, name: str, value: object) -> NoReturn:
        raise UnsupportedApi(f"setting Workplane.{name}")

    def __delattr__(self, name: str) -> NoReturn:
        raise UnsupportedApi(f"deleting Workplane.{name}")

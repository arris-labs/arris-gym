"""`Workplane`: a plane, a stack of objects and the workplane it came from.

ADR-0007. Every call returns a new `Workplane`; none changes one in place.
Private: `arris_gym.cq` exports `Workplane`.
"""

from __future__ import annotations

import functools
import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Concatenate, NoReturn

import arris
import arris.build

from arris_gym.cq._forms import census_form, numbers_of, shape_of
from arris_gym.cq._selector import (
    AXIS_SELECTORS,
    NO_FACES,
    NO_SUITABLE_EDGES,
    SELECTORS,
    Edges,
    Faces,
    Seam,
    edges_of_faces,
    edges_of_solid,
    plane_on_faces,
    seams_of,
    select_edges,
    select_faces,
)
from arris_gym.cq._sketch import Sketch
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
# One whole turn in radians, the angle `sphere`'s half disc and `cskHole`'s
# cone's triangle are revolved by: not a tolerance.
_FULL_TURN = 2 * math.pi
# `cskHole`'s angle, in degrees, both ends included. Its half runs from -90 to
# 180, across the pole of CadQuery's `tan(angle / 2)` at a half of 90: the cone
# has a positive height only from 0 to `_CSK_NO_HEIGHT`, and a negative one at
# both ends, as the oracle reads them (`runtime-csk-angle-minus-180` and
# `runtime-csk-angle-360`).
# Outside the range the tangent repeats and the oracle builds the cone of the
# angle 360 degrees nearer, which no program asks for (`unsupported-csk-*`;
# ADR-0018 rule 4 and its amendment).
_CSK_ANGLES = (-180.0, 360.0)
# From this angle up, to the top of `_CSK_ANGLES`, the cone's height is
# negative, as it is below zero (the oracle's "negative or null height").
_CSK_NO_HEIGHT = 180.0
# CadQuery's `close` adds a segment back to the path's first point only when
# the gap is wider than this, its numerical-error threshold (`cq.py`); a
# narrower gap is no segment. In plane units.
_CLOSE_GAP = 1e-6
# `arris`'s `bounds` is a conservative box, wider than the body by this much on
# every side (measured on boxes of 1 to 40,000 and a cylinder: 2e-7, absolute).
# CadQuery's `largestDimension` is the diagonal of the tight box, so `hole`
# takes the padding off before it measures one: a bore that ends inside the
# part is as long as CadQuery's (`ok-push-points-3-tuple-above`).
_BOUNDS_PAD = 2e-7
# CadQuery's `polarArray` takes the angle for a full turn when it is within this
# many degrees of a multiple of 360 (its `TOL`, `cq.py`, read in ADR-0019).
_FULL_TURN_TOLERANCE = 1e-6
_ZERO = Vector(0, 0, 0)
_SKETCH_TO_VECTOR = "Cannot convert object type '<class 'cadquery.sketch.Sketch'>' to vector"

_NO_SOLID = "Cannot find a solid on the stack or in the parent chain"
_NO_WIRES = "No pending wires present"
_Bounds = tuple[tuple[float, float, float], tuple[float, float, float]]


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
class _Disc(arris.build.Sketch):
    """The sketch of one `circle`: a `Sketch` that also knows its centre and radius.

    A second `circle` on a stack holding one is CadQuery's `eachpoint` over
    the first wire, whose `Center()` is this centre: a concentric circle, and
    `extrude` builds both pending wires as a ring.
    """

    center: tuple[float, float] = (0.0, 0.0)
    radius: float = 0.0


@dataclass(frozen=True)
class _Points:
    """A stack of points `pushPoints`, `rarray` or `polarArray` put on the plane.

    The points are in its local coordinates.

    Each is `(u, v, w)`: x and y in the plane's own axes, `w` the offset along
    its normal (0 when the program gave two numbers). Never empty: CadQuery's
    `pushPoints([])` is an empty stack, which `eachpoint` treats as the plane's
    origin, so `pushPoints` leaves a stack with no object for it.
    """

    points: tuple[tuple[float, float, float], ...]


@dataclass(frozen=True)
class _Discs:
    """The circles `circle` drew on a stack of points, one at each, all of one radius.

    They wait for `extrude`, which builds each and fuses it with the chain's
    solid (ADR-0018 rule 5), or for `cutBlind`, which cuts them all from it in
    one call (ADR-0019 rule 3). No two overlap or touch: `circle` refuses a stack
    where they would, as CadQuery's wires then nest or merge.
    """

    sketches: tuple[_Disc, ...]


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


def _what(selected: Faces | Edges) -> str:
    """`faces` or `edges`: what a stack of selected objects holds, for a message."""
    return "faces" if isinstance(selected, Faces) else "edges"


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


def _one_sided_sketch_extrusion[**P](
    method: Callable[Concatenate[Workplane, P], Workplane],
) -> Callable[Concatenate[Workplane, P], Workplane]:
    """Keep the existing `both` keyword on pending wires only."""

    @functools.wraps(method)
    def checked(self: Workplane, /, *args: P.args, **kwargs: P.kwargs) -> Workplane:
        if "both" in kwargs:
            self._refuse_sketch("Workplane.extrude(both=bool)")
        return method(self, *args, **kwargs)

    return checked


class Workplane:
    """CadQuery's `Workplane` over `arris.build`: a frozen value.

    It holds its plane (an `arris.build.Workplane`), its **stack** (the
    objects its call made, newest last) and its parent (the workplane it was
    called on, `None` for one made by `cq.Workplane(...)`). Guarantees: no
    call changes a `Workplane`; a name the subset lacks raises
    `UnsupportedApi` naming it (`Workplane.text`), never `AttributeError`;
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
    ...     wp.text("arris", 5, 1)
    ... except cq.UnsupportedApi as error:
    ...     print(error)
    Workplane.text
    """

    __slots__ = ("_parent", "_plane", "_seams", "_stack")

    _plane: arris.build.Workplane
    _stack: tuple[object, ...]
    _parent: Workplane | None
    # Where Open CASCADE puts the seam of each cylinder this chain built, or
    # one of its operands did; `None` once a call made a seam no record places
    # (ADR-0020 rule 2, amended). `edges` reads it.
    _seams: tuple[Seam, ...] | None

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
        object.__setattr__(self, "_seams", ())

    def _derive(self, *objects: object) -> Workplane:
        """A new workplane on this one's plane, `objects` its stack, this one its parent."""
        child = object.__new__(Workplane)
        object.__setattr__(child, "_plane", self._plane)
        object.__setattr__(child, "_stack", objects)
        object.__setattr__(child, "_parent", self)
        object.__setattr__(child, "_seams", self._seams)
        return child

    def _with_seams(self, seams: tuple[Seam, ...] | None) -> Workplane:
        """This workplane, just derived, with `seams` added to its chain's; `None` forgets all.

        Called only on a workplane a call has just made and not yet returned.
        """
        known = None if self._seams is None or seams is None else self._seams + seams
        object.__setattr__(self, "_seams", known)
        return self

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
            # A `faces` or `edges` stack keeps the solid they were selected from.
            kept = [o for o in node._stack if isinstance(o, Faces | Edges)]
            if kept:
                return kept[0].solid
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

    def _pending_sketch(self, form: str) -> arris.build.Sketch:
        """The one sketch the stack holds, which `extrude` and `revolve` consume.

        Raises `UnsupportedApi` naming `form`, the call that consumes it, for
        selected faces, a stack of points and circles at points, and
        `ValueError` (CadQuery's words, `runtime`) for any other stack.
        """
        self._refuse_sketch(form)
        self._refuse_selected(form)
        if any(isinstance(o, _Points) for o in self._stack):
            raise UnsupportedApi(f"{form} on a stack of points")
        if any(isinstance(o, _Discs) for o in self._stack):
            raise UnsupportedApi(f"{form} on circles at points")
        sketches = [o for o in self._stack if isinstance(o, arris.build.Sketch)]
        if len(sketches) != 1 or len(self._stack) != 1:
            raise ValueError(_NO_WIRES)
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
        if isinstance(last, Faces | Edges):
            raise UnsupportedApi(f"Workplane.lineTo on selected {_what(last)}")
        if isinstance(last, _Points):
            raise UnsupportedApi("Workplane.lineTo on a stack of points")
        if isinstance(last, _Discs):
            raise UnsupportedApi("Workplane.lineTo on circles at points")
        if isinstance(last, _Path):
            return last
        if isinstance(last, Sketch):
            raise RuntimeError(_SKETCH_TO_VECTOR)
        kind = "Sketch" if isinstance(last, arris.build.Sketch) else type(last).__name__
        raise RuntimeError(f"Cannot convert object type '{kind}' to vector")

    def _has_sketch(self) -> bool:
        return len(self._stack) == 1 and isinstance(self._stack[0], Sketch)

    def _refuse_sketch(self, form: str) -> None:
        if self._has_sketch():
            raise UnsupportedApi(f"{form} on a sketch")

    def _refuse_selected(self, form: str) -> None:
        """Raise `UnsupportedApi` naming `form` when the stack holds selected faces or edges."""
        for o in self._stack:
            if isinstance(o, Faces | Edges):
                raise UnsupportedApi(f"{form} on selected {_what(o)}")

    def _refuse_pending(self, form: str) -> None:
        """Raise `UnsupportedApi` naming `form` when the stack holds a pending wire.

        CadQuery keeps every pending wire in a context the whole chain
        shares and builds them together; the subset holds one on the stack,
        so a call that would start a second beside it is outside it. Faces a
        selector kept are refused the same way: what a call does on them is
        CadQuery's `eachpoint` or `_getFaces`, which the subset does not model.
        """
        self._refuse_selected(form)
        if any(isinstance(o, _Points) for o in self._stack):
            raise UnsupportedApi(f"{form} on a stack of points")
        if any(isinstance(o, (_Path, _Discs, arris.build.Sketch)) for o in self._stack):
            raise UnsupportedApi(f"{form} on a pending wire")

    def _operand(self, other: object, form: str) -> tuple[arris.build.Solid, ...]:
        """The solids of the workplane given to `union` or `cut`; `form` names the call."""
        if not isinstance(other, Workplane):
            raise UnsupportedApi(f"{form} with {type(other).__name__}")
        for o in other._stack:
            if isinstance(o, Faces | Edges):
                raise UnsupportedApi(f"{form} with selected {_what(o)}")
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
        if isinstance(rotate, Sketch) or isinstance(offset, Sketch):
            # A Sketch has the census kind "call" (`unsupported-sketch-transformed-vector`).
            raise UnsupportedApi("Workplane.transformed requires Vector arguments")
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

        On a stack `faces` made, one planar face gives the plane of that
        face (ADR-0017 rule 3): its normal the face's outward normal, its x
        `(0, 0, 1)` crossed with it (+x for a normal along z), its origin
        this workplane's origin projected onto the face's plane. The solid
        stays in the chain. Several planar faces with a common outward normal
        that pass CadQuery's co-planar test in every order place the plane at
        their area-weighted offset (ADR-0022). One unified cylinder, cone,
        sphere or torus face places the plane through its centre of mass,
        normal to the surface at the centre's foot. The origin again projects
        from this workplane. A missing foot raises `RuntimeError`. An unstable
        foot or an unsupported surface raises `UnsupportedApi`.
        Mixed planar and curved or distinct curved faces raise CadQuery's
        `ValueError` (`runtime`), as do planar faces that fail its co-planar
        test whichever face comes first.
        An order-dependent or uncertain planar selection raises
        `UnsupportedApi`. An `offset`
        on faces moves the plane that far along its normal, as it does on a
        solid (read on the oracle: `ok-faces-workplane-offset-*`).

        >>> import arris_gym.cq as cq
        >>> wp = cq.Workplane("XY").box(2, 2, 2).workplane(offset=3)
        >>> wp._plane.origin
        (0.0, 0.0, 3.0)
        >>> wp = cq.Workplane("XY").box(2, 2, 2).faces(">Z").workplane()
        >>> wp._plane.origin
        (0.0, 0.0, 1.0)
        >>> wp = cq.Workplane("XY").box(2, 2, 2).faces(">Z").workplane(offset=2)
        >>> wp._plane.origin
        (0.0, 0.0, 3.0)
        """
        if self._has_sketch():
            raise ValueError("Needs a face or a vertex or point on a work plane")
        kept = [o for o in self._stack if isinstance(o, Faces)]
        if kept:
            (selected,) = kept
            plane = plane_on_faces(selected.groups, self._plane, selected.solid.model)
            # As on a solid below: moved along the unit normal, axes kept.
            n = plane.z
            at = (
                plane.origin[0] + n[0] * offset,
                plane.origin[1] + n[1] * offset,
                plane.origin[2] + n[2] * offset,
            )
            return self._derive_on(arris.build.Workplane(at, plane.x, plane.y, plane.z))
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

    @census_form("Workplane.faces", [("str",)])
    def faces(self, selector: str) -> Workplane:
        """The faces of the solid on the stack that CadQuery's `selector` keeps.

        `selector` is one of `>X <X >Y <Y >Z <Z`: the faces whose centre of
        mass lies furthest along (`>`) or least along (`<`) the axis, every one
        within CadQuery's `1e-4` of the first of its cluster. Faces of the same
        surface and sense joined by an edge rank as one by their area-weighted
        centre (ADR-0022). The kept groups form the one object on the new
        stack, in CadQuery's order. The solid stays in the
        chain, and `workplane()` places a plane on them (ADR-0017). On a stack
        of selected faces a selector ranks those faces only, as CadQuery's does
        (ADR-0018 rule 5; `ok-ctx-faces-on-faces-*`): a single face stays
        whatever the second selector. Raises `UnsupportedApi` for any other
        selector or if the error bound on a face's centre of mass can change
        the ranking (ADR-0022 rule 1). A stack with no solid (empty, a
        `moveTo` point, a drawn path or a sketch, whose
        objects have no faces) raises CadQuery's `ValueError` (`runtime`),
        read on the oracle: `runtime-faces-on-*`. Where the solid is a compound
        the faces of every piece are candidates (`ok-faces-compound-*`).

        >>> import arris_gym.cq as cq
        >>> wp = cq.Workplane("XY").box(2, 4, 6).faces("<X")
        >>> len(wp._stack[0].groups)
        1
        """
        if selector not in AXIS_SELECTORS:
            raise UnsupportedApi(f"Workplane.faces({selector!r})")
        if any(isinstance(o, Edges) for o in self._stack):
            raise UnsupportedApi("Workplane.faces on selected edges")
        kept = [o for o in self._stack if isinstance(o, Faces)]
        if kept:
            # CadQuery ranks the stacked faces only (ADR-0018 rule 5).
            (prior,) = kept
            return self._derive(
                Faces(prior.solid, select_faces(prior.solid, selector, prior.groups))
            )
        solids = self._solids()
        if not solids:
            # No object on the stack has a face: CadQuery's selector is handed
            # an empty list, even where the chain holds a solid further up.
            raise ValueError(NO_FACES)
        (solid,) = solids
        return self._derive(Faces(solid, select_faces(solid, selector)))

    @census_form("Workplane.edges", [], alternatives=[[("str",)]])
    def edges(self, selector: str | None = None) -> Workplane:
        """The edges of the stack's solid or faces that CadQuery's `selector` keeps (ADR-0020).

        With no `selector` every edge is kept. `selector` is one of `>X <X >Y
        <Y >Z <Z`: the edges whose centre of mass lies furthest along (`>`) or
        least along (`<`) the axis, every one within CadQuery's `1e-4` of the
        first of its cluster, in ascending key; `|X`, `|Y` or `|Z`: the line
        edges parallel to the axis (a circle or arc never, a seam line when it
        is parallel); or `>Z or <Z`: both ends' edges, each once. Candidates are
        the solid's edges, the boundary edges of the unified faces `faces` kept
        (each edge once, in first-encounter order), or the edges a selector kept
        before. A compound's edges are those of every piece.
        The selection is the one object on the new
        stack, which `fillet` and `chamfer` take; the solid stays in the chain.
        A degenerate edge is no candidate. A seam of a cylinder this chain built
        is ranked where Open CASCADE puts it, which the chain records (ADR-0020's
        amendment). Raises `UnsupportedApi` for any other selector and where the
        selection depends on an edge's place arris does not decide as CadQuery's
        kernel does (a seam no record places on a face about another axis, an
        ellipse arc or B-spline edge able to reach the kept cluster), or where
        the selection depends on joining split boundary edges of a unified face.
        A selector on an empty stack raises CadQuery's `ValueError`
        (`runtime`), as `faces` does.

        >>> import arris_gym.cq as cq
        >>> wp = cq.Workplane("XY").box(2, 4, 6).edges(">Z")
        >>> len(wp._stack[0].edges)
        4
        """
        if selector is not None and selector not in SELECTORS:
            raise UnsupportedApi(f"Workplane.edges({selector!r})")
        for o in self._stack:
            if isinstance(o, Edges):
                kept = select_edges(o.solid, o.edges, selector, self._seams)
                return self._derive(Edges(o.solid, kept))
            if isinstance(o, Faces):
                candidates, fragments = edges_of_faces(o.solid, o.groups)
                kept = select_edges(o.solid, candidates, selector, self._seams, fragments=fragments)
                return self._derive(Edges(o.solid, kept))
        solids = self._solids()
        if solids:
            (solid,) = solids
            kept = select_edges(solid, edges_of_solid(solid), selector, self._seams)
            return self._derive(Edges(solid, kept))
        if selector is not None and (not self._stack or self._has_sketch()):
            # No object on the stack has an edge: CadQuery's selector is handed
            # an empty list, even where the chain holds a solid further up.
            raise ValueError(NO_FACES)
        self._refuse_sketch("Workplane.edges")
        raise UnsupportedApi(
            "Workplane.edges on "
            + ("an empty stack" if not self._stack else "a stack that holds no solid")
        )

    def _blended(
        self,
        form: str,
        value: float,
        none_selected: str,
        blend: Callable[[arris.build.Solid, list[arris.Edge], float], arris.build.Solid],
    ) -> Workplane:
        """The chain's solid blended at the stack's edges in one call (ADR-0020 rule 5).

        The edges are the stack's, or every edge of the stacked faces or solid.
        Raises, in CadQuery's order, `ValueError` (`runtime`) for a chain with
        no solid, then for no edges (`none_selected`, CadQuery's words), then for
        a list of seams alone. Seams are dropped otherwise. `value` goes to
        `blend` as written, so a value arris refuses is `arris_refusal`.
        """
        base = self._base_solid()
        if base is None:
            raise ValueError(_NO_SOLID)
        candidates: tuple[arris.Edge, ...] = ()
        for o in self._stack:
            if isinstance(o, Edges):
                candidates = o.edges
            elif isinstance(o, Faces):
                candidates, fragments = edges_of_faces(o.solid, o.groups)
                if fragments:
                    raise UnsupportedApi(f"{form} on a split unified face boundary")
            elif isinstance(o, arris.build.Solid):
                candidates = edges_of_solid(o)
            else:
                self._refuse_pending(form)
        if not candidates:
            raise ValueError(none_selected)
        model = base.model
        # A seam has one face on both sides: arris refuses it, Open CASCADE passes over it.
        blendable = [e for e in candidates if len(model.faces_of(base.body, e)) != 1]
        if not blendable:
            raise ValueError(NO_SUITABLE_EDGES)
        return self._derive(blend(base, blendable, value))

    @census_form("Workplane.fillet", [("num",)])
    def fillet(self, radius: float) -> Workplane:
        """The chain's solid with the stack's edges rounded to `radius`, in one call (ADR-0020).

        The edges are those on the stack (`edges`), or every edge of the stacked
        faces or of the stacked solid, a compound's pieces included, which come
        out as one body. A seam, an edge with one face on both sides, is passed
        over, as Open CASCADE does; a stack of seams alone is CadQuery's
        `ValueError` (`runtime`), as is a chain with no solid or a stack with no
        edge. `radius` goes to arris as written: zero, a negative and one past
        what the edge's faces allow are `arris_refusal`, where CadQuery raises
        `StdFail_NotDone`; both fail. No `clean()` follows, which on the oracle
        moves no measure (`ok-fillet-*`).

        >>> import arris_gym.cq as cq
        >>> wp = cq.Workplane("XY").box(10, 8, 4).edges("|Z").fillet(1)
        >>> round(wp._solids()[0].measure().volume, 6)
        316.566371
        """
        return self._blended(
            "Workplane.fillet",
            radius,
            "Fillets requires that edges be selected",
            lambda solid, edges, value: solid.fillet(edges, value),
        )

    @census_form("Workplane.chamfer", [("num",)])
    def chamfer(self, length: float) -> Workplane:
        """The chain's solid with the stack's edges bevelled by `length`, in one call (ADR-0020).

        The edges, the seams passed over and the refusals are `fillet`'s (ADR-0020
        rule 5): a chain with no solid, a stack with no edge and a stack of seams
        alone are CadQuery's `ValueError` (`runtime`); `length` goes to arris as
        written, so zero, a negative and one past what the edge's faces allow are
        `arris_refusal`, where CadQuery raises `StdFail_NotDone`; both fail.

        >>> import arris_gym.cq as cq
        >>> wp = cq.Workplane("XY").box(10, 8, 4).edges("|Z").chamfer(1)
        >>> round(wp._solids()[0].measure().volume, 6)
        312.0
        """
        return self._blended(
            "Workplane.chamfer",
            length,
            "Chamfer requires that edges be selected",
            lambda solid, edges, value: solid.chamfer(edges, value),
        )

    @census_form("Workplane.pushPoints", [("list",)])
    def pushPoints(self, pntList: Sequence[object]) -> Workplane:
        """A stack of the points of `pntList`, in this workplane's local coordinates.

        Each point is a tuple or list of two numbers (x and y in the plane's
        own axes, as `moveTo` takes them) or three (the third its offset along
        the normal). The solid stays in the chain for the next call, `hole`
        for one, to act on: it bores at every point (ADR-0018 rules 1 and 2).
        An empty list leaves an empty stack, which bores at the plane's
        origin, as CadQuery's does (read on the oracle:
        `ok-push-points-empty`). A point that is not two or three numbers
        (one number, a `Vector`) ends `UnsupportedApi`: CadQuery's error
        there comes from inside its `Vector`, not from a check of the value.
        A stack that holds selected faces, a pending wire or a drawn path is
        outside the subset, as for `moveTo`; a stack of points is replaced.

        >>> import arris_gym.cq as cq
        >>> wp = cq.Workplane("XY").box(2, 2, 2).faces(">Z").workplane()
        >>> wp.pushPoints([(0.5, 0.5), [-0.5, -0.5]])._stack[0].points
        ((0.5, 0.5, 0.0), (-0.5, -0.5, 0.0))
        """
        if not any(isinstance(o, _Points) for o in self._stack):
            self._refuse_pending("Workplane.pushPoints")
        points: list[tuple[float, float, float]] = []
        for point in pntList:
            numbers = numbers_of(point, (2, 3))
            if numbers is None:
                raise UnsupportedApi(
                    f"Workplane.pushPoints(list with a point of {shape_of(point)})"
                )
            points.append((numbers[0], numbers[1], numbers[2] if len(numbers) == 3 else 0.0))
        if not points:
            return self._derive()
        return self._derive(_Points(tuple(points)))

    @census_form("Workplane.rarray", [("num",)] * 4)
    def rarray(self, xSpacing: float, ySpacing: float, xCount: int, yCount: int) -> Workplane:
        """A stack of the points of a grid, centred on this workplane's origin.

        CadQuery's points in its order, by its expressions: `xSpacing * i`
        plus `-xSpacing * (xCount - 1) * 0.5` for `i` in `range(xCount)`
        (the outer loop) and the same in y for `j` in `range(yCount)`, in the
        plane's own axes. The solid stays in the chain for the next call to
        act on, as after `pushPoints` (ADR-0019 rule 1): a bore at every
        point, `circle` at every point. A spacing of zero or less or a count
        under 1 raises `ValueError` (`runtime`) in CadQuery's words; a count
        that is not an `int` passes that check and raises `TypeError` from
        `range`, as CadQuery's does (`runtime-rarray-*`). A stack that holds
        selected faces, a pending wire or a drawn path is outside the subset,
        as for `pushPoints`; a stack of points is replaced.

        >>> import arris_gym.cq as cq
        >>> wp = cq.Workplane("XY").box(2, 2, 2).faces(">Z").workplane()
        >>> wp.rarray(1, 2, 2, 2)._stack[0].points
        ((-0.5, -1.0, 0.0), (-0.5, 1.0, 0.0), (0.5, -1.0, 0.0), (0.5, 1.0, 0.0))
        """
        if xSpacing <= 0 or ySpacing <= 0 or xCount < 1 or yCount < 1:
            raise ValueError("Spacing and count must be > 0 ")
        if not any(isinstance(o, _Points) for o in self._stack):
            self._refuse_pending("Workplane.rarray")
        x_offset = -xSpacing * (xCount - 1) * 0.5
        y_offset = -ySpacing * (yCount - 1) * 0.5
        points = tuple(
            (float(xSpacing * i + x_offset), float(ySpacing * j + y_offset), 0.0)
            for i in range(xCount)
            for j in range(yCount)
        )
        return self._derive(_Points(points))

    @census_form("Workplane.polarArray", [("num",)] * 4)
    def polarArray(self, radius: float, startAngle: float, angle: float, count: int) -> Workplane:
        """A stack of the points of a polar array on a circle about this workplane's origin.

        CadQuery's points by its expressions (ADR-0019 rule 2): the step is
        `angle / count` on a full turn (`angle` within `_FULL_TURN_TOLERANCE`
        degrees of a multiple of 360, of either sign), else `angle / (count -
        1)`; point `i` is at `phi = math.radians(startAngle + step * i)`,
        `(radius * cos(phi), radius * sin(phi))`, in the plane's own axes. So
        a partial turn has both its ends, one point sits at `startAngle`, and
        a negative radius puts each point across the centre. CadQuery's turn
        of each point is dropped: a bore and a circle are round. The stack
        acts as `pushPoints`' (`hole` at each point, `circle` at each, and
        the contexts `rarray` refuses). A `count` under 1 raises `ValueError`
        (`runtime`) with the count verbatim, as in CadQuery; one that is not an
        `int` raises `TypeError` from `range`, as there
        (`runtime-polar-array-*`). `fill=` and `rotate=` end `unsupported_api`.

        >>> import arris_gym.cq as cq
        >>> wp = cq.Workplane("XY").box(2, 2, 2).faces(">Z").workplane()
        >>> [round(u, 9) + 0.0 for u, _, _ in wp.polarArray(1, 0, 360, 4)._stack[0].points]
        [1.0, 0.0, -1.0, 0.0]
        """
        if count < 1:
            raise ValueError(f"At least 1 element required, requested {count}")
        if not any(isinstance(o, _Points) for o in self._stack):
            self._refuse_pending("Workplane.polarArray")
        if abs(math.remainder(angle, 360.0)) < _FULL_TURN_TOLERANCE:
            step = angle / count
        else:
            step = angle / (count - 1) if count > 1 else 0.0
        points = []
        for i in range(count):
            phi = math.radians(startAngle + step * i)
            points.append((float(radius * math.cos(phi)), float(radius * math.sin(phi)), 0.0))
        # CadQuery turns each point's axes by its angle, and with them where a bore's or
        # a circle's seam lies; `cq` drops the turn, so no seam of the chain is placed.
        return self._derive(_Points(tuple(points)))._with_seams(None)

    @census_form("Workplane.hole", [("num",)], keywords={"depth": ("num",)})
    def hole(self, diameter: float, depth: float | None = None) -> Workplane:
        """The chain's solid with a hole of `diameter` bored from the plane, as CadQuery bores it.

        The hole is a cylinder that starts at one point and runs against the
        plane's normal for `depth`, or with none for the diagonal of the
        solid's box, so it reaches through any material below the plane and
        leaves what lies above it (CadQuery's `hole`: `cutEach` of a cylinder
        of `depth` or `largestDimension()`, read on the oracle: `ok-hole-*`).
        A `depth` short of the part's thickness bores a blind hole, and one at
        or past it a through one (`ok-hole-depth-*`); `depth` is the keyword
        only, as the census writes it. The point is
        the plane's origin on an empty stack (after `workplane()`), the point
        of a lone `moveTo` on that plane, or the centre of mass of a solid on
        the stack, in all three coordinates (read on the oracle: `ok-hole-on-*`).
        On a stack of points (`pushPoints`) it is bored at every one, all in
        one cut, as CadQuery's `cutEach` does (ADR-0018 rule 2; read on the
        oracle: `ok-push-points-*`). The result is the one solid on the new
        stack, a compound where the hole splits the part (ADR-0016). A zero
        `diameter` cuts nothing, as in CadQuery. Raises `ValueError`
        (`runtime`) in CadQuery's words for a chain without a solid and for a
        negative diameter, for a `depth` of zero or less (CadQuery's
        `Standard_ConstructionError`, which it raises before a zero diameter
        cuts nothing: `runtime-hole-depth-*`), and `UnsupportedApi` for
        selected faces or a drawn path or sketch on the stack: CadQuery bores
        at their centres.

        >>> import arris_gym.cq as cq
        >>> wp = cq.Workplane("XY").box(2, 2, 2).faces(">Z").workplane().hole(1)
        >>> round(wp._solids()[0].measure().volume, 6)
        6.429204
        >>> wp = cq.Workplane("XY").box(2, 2, 2).faces(">Z").workplane().hole(1, depth=1)
        >>> round(wp._solids()[0].measure().volume, 6)
        7.214602
        """
        base, centres = self._bore_sites("Workplane.hole")
        named = (
            f"Workplane.hole({diameter})"
            if depth is None
            else (f"Workplane.hole({diameter}, depth={depth})")
        )
        if depth is not None and depth <= 0:
            raise ValueError(
                f"{named}: a depth not positive (CadQuery's Standard_ConstructionError)"
            )
        if diameter < 0:
            raise ValueError(
                f"{named}: a negative diameter (CadQuery's Standard_ConstructionError)"
            )
        if diameter == 0:
            return self._derive(base)
        if depth is None:
            depth = self._bore_length(self._bore_bounds(base))
        return self._cut_bores(base, centres, [(diameter / 2.0, depth)])

    @census_form("Workplane.cboreHole", [("num",)] * 3)
    def cboreHole(self, diameter: float, cboreDiameter: float, cboreDepth: float) -> Workplane:
        """The chain's solid with a counterbored hole bored from the plane, as CadQuery bores it.

        The hole is a cylinder of `diameter` as long as the solid's box
        diagonal, under a counterbore, a cylinder of `cboreDiameter` and
        `cboreDepth`, both starting at the same point and running against the
        plane's normal, at the points `hole` uses (ADR-0018 rules 2 and 3;
        read on the oracle: `ok-cbore-*`). CadQuery fuses the two cylinders;
        `cq` cuts them as separate tools of one call, which is the cut by
        their union. Whichever is wider or deeper, the union is what is cut: a
        counterbore no wider than the bore leaves the bore alone, and one
        deeper than the part makes a through hole of its own diameter. A zero
        `diameter` leaves the counterbore alone and a zero `cboreDiameter` the
        bore. Raises `ValueError` (`runtime`) for a negative diameter or
        counterbore diameter and a `cboreDepth` of zero or less (CadQuery's
        `Standard_ConstructionError`, and for a negative depth its
        `Null TopoDS_Shape object`) and for both diameters zero, which leaves
        no tool (`runtime-cbore-*`), and otherwise as `hole` does.

        >>> import arris_gym.cq as cq
        >>> wp = cq.Workplane("XY").box(4, 4, 2).faces(">Z").workplane()
        >>> cut = wp.cboreHole(1, 2, 0.5)
        >>> round(4 * 4 * 2 - cut._solids()[0].measure().volume, 6)
        2.748894
        """
        base, centres = self._bore_sites("Workplane.cboreHole")
        named = f"Workplane.cboreHole({diameter}, {cboreDiameter}, {cboreDepth})"
        if diameter < 0:
            raise ValueError(
                f"{named}: a negative diameter (CadQuery's Standard_ConstructionError)"
            )
        if cboreDiameter < 0:
            raise ValueError(
                f"{named}: a negative counterbore diameter (CadQuery's Standard_ConstructionError)"
            )
        if cboreDepth == 0:
            raise ValueError(
                f"{named}: a counterbore depth of zero (CadQuery's Standard_ConstructionError)"
            )
        if cboreDepth < 0:
            raise ValueError(
                f"{named}: a negative counterbore depth (CadQuery's Null TopoDS_Shape object)"
            )
        pieces = [
            (diameter / 2.0, self._bore_length(self._bore_bounds(base))),
            (cboreDiameter / 2.0, cboreDepth),
        ]
        if all(radius == 0 for radius, _ in pieces):
            raise ValueError(f"{named}: no bore and no counterbore (CadQuery's Null TopoDS_Shape)")
        return self._cut_bores(base, centres, pieces)

    @census_form("Workplane.cskHole", [("num",)] * 3)
    def cskHole(self, diameter: float, cskDiameter: float, cskAngle: float) -> Workplane:
        """The chain's solid with a countersunk hole bored from the plane, as CadQuery bores it.

        The hole is a cylinder of `diameter` as long as the solid's box
        diagonal, under a cone whose base, of `cskDiameter`, is at the
        starting point and whose tip is `cskDiameter / 2 / tan(cskAngle / 2)`
        below it, at the points `hole` uses (ADR-0018 rules 2 and 3; read on
        the oracle: `ok-csk-*`). CadQuery fuses the two; `cq` cuts them as
        separate tools of one call, the cone a right triangle revolved a
        full turn (arris has no cone), which is the cut by their union. A
        cone no wider than the bore leaves the bore, and a zero `diameter`
        leaves the cone alone. Raises `ValueError` (`runtime`) for what
        CadQuery refuses, in its order: a negative diameter, an angle of zero,
        a zero or negative `cskDiameter`, and an angle that gives the cone no
        height (from -180 to 0 and from 180 to 360, both ends included);
        `UnsupportedApi` for an angle outside them, where CadQuery's tangent repeats
        (`runtime-csk-*`, `unsupported-csk-*`), and otherwise as `hole` does.

        >>> import arris_gym.cq as cq
        >>> wp = cq.Workplane("XY").box(4, 4, 2).faces(">Z").workplane()
        >>> cut = wp.cskHole(1, 2, 90)
        >>> round(4 * 4 * 2 - cut._solids()[0].measure().volume, 6)
        2.094395
        """
        base, centres = self._bore_sites("Workplane.cskHole")
        named = f"Workplane.cskHole({diameter}, {cskDiameter}, {cskAngle})"
        if diameter < 0:
            raise ValueError(
                f"{named}: a negative diameter (CadQuery's Standard_ConstructionError)"
            )
        if cskAngle == 0:
            raise ValueError(f"{named}: an angle of zero (CadQuery's ZeroDivisionError)")
        if cskDiameter == 0:
            raise ValueError(
                f"{named}: a zero countersink diameter (CadQuery's Standard_DomainError)"
            )
        if cskDiameter < 0:
            raise ValueError(
                f"{named}: a negative countersink diameter (CadQuery's Standard_DomainError)"
            )
        if not _CSK_ANGLES[0] <= cskAngle <= _CSK_ANGLES[1]:
            raise UnsupportedApi(
                f"Workplane.cskHole with an angle outside [{_CSK_ANGLES[0]}, {_CSK_ANGLES[1]}]"
            )
        if cskAngle < 0 or cskAngle >= _CSK_NO_HEIGHT:
            raise ValueError(
                f"{named}: an angle that gives the cone no height (CadQuery's Standard_DomainError)"
            )
        radius = cskDiameter / 2.0
        height = radius / math.tan((cskAngle / 2.0) * _RADIANS_PER_DEGREE)
        return self._cut_bores(
            base,
            centres,
            [(diameter / 2.0, self._bore_length(self._bore_bounds(base)))],
            [(radius, height)],
        )

    def _bore_sites(self, form: str) -> tuple[arris.build.Solid, list[tuple[float, float, float]]]:
        """The solid a bore cuts and the points it is bored at, in world coordinates.

        CadQuery's `eachpoint` bores at each object's centre: a point is itself,
        a solid its centre of mass, and an empty stack the plane's origin. Faces
        and drawn paths have centres the subset does not model. Raises
        `ValueError` (`runtime`, CadQuery's words) for a chain with no solid and
        `UnsupportedApi` naming `form` for a stack the subset does not bore on.
        """
        self._refuse_sketch(form)
        base = self._base_solid()
        if base is None:
            raise ValueError(_NO_SOLID)
        plane = self._plane
        if not self._stack:
            return base, [plane.origin]
        (last,) = self._stack
        if isinstance(last, _Points):
            return base, [plane.point(*point) for point in last.points]
        if isinstance(last, _Path) and not last.segments:
            return base, [plane.point(last.start[0], last.start[1], 0.0)]
        if isinstance(last, arris.build.Solid):
            return base, [last.measure().centroid]
        self._refuse_pending(form)
        raise UnsupportedApi(f"{form} on a stack holding objects")

    @staticmethod
    def _bore_bounds(base: arris.build.Solid) -> _Bounds:
        """The kernel's conservative box of the stock."""
        box = base.model.bounds(base.body)
        if box is None:
            raise UnsupportedApi("a bore on a solid without a box")
        return box

    @staticmethod
    def _bore_length(box: _Bounds) -> float:
        """CadQuery's `largestDimension()`: the diagonal with the kernel's padding removed."""
        return math.sqrt(sum((box[1][k] - box[0][k] - 2 * _BOUNDS_PAD) ** 2 for k in range(3)))

    def _cut_bores(
        self,
        base: arris.build.Solid,
        centres: Sequence[tuple[float, float, float]],
        cylinders: Sequence[tuple[float, float]],
        cones: Sequence[tuple[float, float]] = (),
    ) -> Workplane:
        """`base` less a tool per piece at every centre, all cut in one call.

        A cylinder is `(radius, length)`, a cone `(radius at the top, height)`
        with its tip below; each runs from its centre against the plane's
        normal (ADR-0018 rules 2 and 3). A cylinder of zero radius is left
        out, as the oracle leaves it. A cone is a right triangle on a plane
        through its axis (the plane's x and its normal), revolved a full turn.
        """
        plane = self._plane
        down = (-plane.z[0], -plane.z[1], -plane.z[2])
        # The triangle's plane: its y is the workplane's normal, so the axis is y.
        meridian_normal = (-plane.y[0], -plane.y[1], -plane.y[2])
        tools = [
            arris.build.Solid.cylinder(at, down, radius, length, model=base.model)
            for at in centres
            for radius, length in cylinders
            if radius > 0
        ]
        for at in centres:
            meridian = arris.build.Workplane.of(at, meridian_normal, plane.x)
            for radius, height in cones:
                triangle = arris.Loop.polygon([(0.0, 0.0), (radius, 0.0), (0.0, -height)])
                tools.append(
                    arris.build.Sketch(meridian, triangle).revolve(
                        "y", _FULL_TURN, model=base.model
                    )
                )
        # CadQuery bores along its plane's -z, so Open CASCADE puts each bore's seam on -x.
        away = (-plane.x[0], -plane.x[1], -plane.x[2])
        seams: tuple[Seam, ...] | None = ()
        for tool in tools:
            placed = seams_of(tool, away)
            seams = None if seams is None or placed is None else seams + placed
        return self._derive(base.cut(*tools))._with_seams(seams)

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
        tool = sketch.extrude(height)
        return self._combined(tool)._with_seams(seams_of(tool, sketch.plane.x))

    @census_form("Workplane.sphere", [("num",)])
    def sphere(self, radius: float) -> Workplane:
        """A sphere of `radius` centred on the origin or a `moveTo` point.

        Its poles lie on the workplane's normal through the centre, as
        CadQuery's `direct=(0, 0, 1)` in the plane's own axes places them.
        On an empty stack it is centred on the workplane's origin; on a stack
        holding only a `moveTo` point, on that point, in the plane's own axes
        (CadQuery's `eachpoint` over one point). A sphere on a workplane whose
        chain holds a solid further up is fused with it, as CadQuery's
        `combine=True` does. arris has no sphere primitive: the sphere is a
        half disc, an arc from pole to pole closed by the diameter, revolved
        a full turn about the normal, one spherical face (read on the
        oracle: `ok-sphere-*`). Refuses, as `UnsupportedApi`, a stack
        holding a drawn path or a sketch, and one holding a solid or a
        compound: there CadQuery centres the sphere on the object's
        `Center()`, as it does a box, which the subset does not model (read
        on the oracle: `unsupported-sphere-*`). Raises `ValueError`
        (`runtime`) for a negative radius, where CadQuery raises
        `Standard_ConstructionError`, and for a zero radius, where CadQuery
        builds a shape its checker rejects (`runtime-sphere-zero-radius`, a
        `by_design` row).

        >>> import math
        >>> import arris_gym.cq as cq
        >>> (solid,) = cq.Workplane("XY").sphere(3)._solids()
        >>> round(solid.measure().volume / math.pi, 9)
        36.0
        >>> wp = cq.Workplane("XZ").moveTo(3, 1).sphere(2)
        >>> [round(c, 9) + 0.0 for c in wp._solids()[0].measure().centroid]
        [3.0, 0.0, 1.0]
        """
        point = self._stack[0] if len(self._stack) == 1 else None
        if isinstance(point, _Path) and not point.segments:
            center = point.start
        else:
            self._refuse_pending("Workplane.sphere")
            if self._solids():
                # As with `box`: CadQuery centres it on the solid's `Center()`.
                raise UnsupportedApi("Workplane.sphere on a stack holding a solid")
            center = (0.0, 0.0)
        named = f"Workplane.sphere({radius})"
        if radius < 0:
            raise ValueError(f"{named}: a negative radius (CadQuery's Standard_ConstructionError)")
        if radius == 0:
            raise ValueError(f"{named}: a zero radius (CadQuery builds an invalid shape)")
        plane = self._plane
        # The half disc's plane: through the centre, its x the workplane's x
        # and its y the workplane's normal, so `revolve("y", …)` turns it
        # about the axis through the poles.
        down = (-plane.y[0], -plane.y[1], -plane.y[2])
        meridian = arris.build.Workplane.of(plane.point(*center), down, plane.x)
        r = float(radius)
        loop = arris.Loop.path(
            (0.0, -r), [arris.Segment.arc((0.0, r), (r, 0.0)), arris.Segment.line((0.0, -r))]
        )
        return self._combined(arris.build.Sketch(meridian, loop).revolve("y", _FULL_TURN))

    @census_form("Workplane.circle", [("num",)])
    def circle(self, radius: float) -> Workplane:
        """A pending circle of `radius`, centred on the workplane's origin or a `moveTo` point.

        The circle is the one sketch on the new stack, waiting for `extrude`
        or `revolve`. On an empty stack it is centred on the origin; on a
        stack holding only a `moveTo` point, on that point, in the plane's
        own axes (CadQuery's `eachpoint` over one point). On a stack holding
        one circle, a second `circle` is concentric with it and the two make
        a ring for `extrude` or `revolve` (the larger circle outside). On a
        stack of points (`pushPoints`) it draws one circle at each, and
        `extrude` builds a post on each and fuses them with the chain's solid
        (ADR-0018 rule 5, read on the oracle: `ok-ctx-circle-points-*`); the circles
        are not drawn where two would overlap or touch, a duplicate point
        included, nor on a point with an offset along the normal, nor a ring
        of them: `UnsupportedApi`, where CadQuery nests or merges the wires
        or draws on another plane (`unsupported-circle-points-*`). Refuses, as
        `UnsupportedApi`, any other stack: CadQuery centres a circle on each
        object there, which the subset does not model (`transformed` leaves
        a stack empty).

        >>> import math
        >>> import arris_gym.cq as cq
        >>> round(cq.Workplane("XY").circle(1).extrude(2)._solids()[0].measure().volume, 9)
        6.283185307
        >>> wp = cq.Workplane("XY").moveTo(2, 0).circle(1).extrude(1)
        >>> [round(c, 9) + 0.0 for c in wp._solids()[0].measure().centroid]
        [2.0, 0.0, 0.5]
        >>> ring = cq.Workplane("XY").circle(3).circle(1).extrude(2)
        >>> round(ring._solids()[0].measure().volume / math.pi, 9)
        16.0
        """
        if len(self._stack) == 1 and isinstance(self._stack[0], _Disc):
            return self._derive(self._ring(self._stack[0], radius))
        if len(self._stack) == 1 and isinstance(self._stack[0], _Points):
            return self._derive(self._discs(self._stack[0], radius))
        centre = (0.0, 0.0)
        if self._stack:
            point = self._stack[0] if len(self._stack) == 1 else None
            if not isinstance(point, _Path) or point.segments:
                raise UnsupportedApi("Workplane.circle on a non-empty stack")
            centre = point.start
        return self._derive(self._disc(radius, centre))

    def _discs(self, stacked: _Points, radius: float) -> _Discs:
        """One circle of `radius` at each point of `stacked`, as CadQuery's `eachpoint` draws them.

        Refuses, as `UnsupportedApi`, a point with an offset along the normal
        (its circle is on another plane) and a stack where two circles overlap
        or touch, a pair of points no further apart than two radii and a
        point twice among them: CadQuery nests or merges the wires there.
        """
        if any(w != 0.0 for _, _, w in stacked.points):
            raise UnsupportedApi("Workplane.circle on a point with an offset")
        for i, (u, v, _) in enumerate(stacked.points):
            for u2, v2, _ in stacked.points[i + 1 :]:
                if math.hypot(u - u2, v - v2) <= 2 * abs(radius):
                    raise UnsupportedApi("Workplane.circle on points no further apart than 2 radii")
        return _Discs(tuple(self._disc(radius, (u, v)) for u, v, _ in stacked.points))

    def _disc(self, radius: float, centre: tuple[float, float]) -> _Disc:
        """The pending circle of `radius` about `centre`, in the plane's own axes."""
        sketch = self._plane.circle(radius, center=centre)
        return _Disc(sketch.plane, sketch.outer, sketch.holes, centre, radius)

    def _ring(self, first: _Disc, radius: float) -> arris.build.Sketch:
        """The two concentric circles as one ring sketch: the larger outside, the smaller its hole.

        CadQuery sorts the pending wires into outer and inner by size
        (read on the oracle: `ok-circle-circle-*`). Two radii of one size
        make a shape the oracle calls invalid; a radius of zero is not a
        circle. Both are refused, `UnsupportedApi`, where the radii meet
        there.
        """
        if radius == first.radius or radius <= 0 or first.radius <= 0:
            raise UnsupportedApi("Workplane.circle on a circle of the same size or no size")
        second = self._disc(radius, first.center)
        outer, inner = (first, second) if radius < first.radius else (second, first)
        # `Sketch.cut` of a `_Disc` is a `_Disc` still: a plain sketch ends the chain of circles.
        return arris.build.Sketch(outer.plane, outer.outer, (inner.outer,))

    @census_form("Workplane.polygon", [("num",)] * 2)
    def polygon(self, nSides: int, diameter: float) -> Workplane:
        """A pending regular polygon of `nSides` inscribed in a circle of `diameter`.

        The polygon is the one sketch on the new stack, waiting for `extrude`
        or `revolve`, centred as `circle` is: on the workplane's origin for
        an empty stack, on a `moveTo` point for a stack holding only one, in
        the plane's own axes (CadQuery's `eachpoint` over one point). Its
        first vertex lies on the plane's local +x from the centre, the others
        follow counterclockwise. The vertices are CadQuery's expression in
        its order (`Workplane.polygon`, `cq.py`): `radius = diameter / 2.0`,
        the angle `2.0 * math.pi / nSides` times `i`, and the point
        `(radius * cos, radius * sin)`; CadQuery's closing point repeating
        the first is left out, since the kernel closes the loop. A negative
        `diameter` turns the polygon by π, as CadQuery's does. Refuses, as
        `UnsupportedApi`, any other stack, as `circle` does: CadQuery centres
        a polygon on each object's `Center()` there (read on the oracle:
        `unsupported-polygon-*`).

        Fails as CadQuery does (read on the oracle: `runtime-polygon-*`):
        `nSides` of 0 raises `ZeroDivisionError` and a float `TypeError`,
        CadQuery's own, from the same expression. Raises `ValueError`
        (`runtime`) for fewer than three sides and for a zero `diameter`:
        CadQuery raises `StdFail_NotDone` on each but two sides, which it
        extrudes into a zero-volume solid: a `cq_bug` row, held by the strict
        `xfail` `regression/cq-polygon-two-sides`.

        >>> import math
        >>> import arris_gym.cq as cq
        >>> (solid,) = cq.Workplane("XY").polygon(6, 2).extrude(1)._solids()
        >>> round(solid.measure().volume / (3 * math.sqrt(3) / 2), 9)
        1.0
        >>> wp = cq.Workplane("XY").moveTo(3, 1).polygon(4, 2).extrude(1)
        >>> [round(c, 9) + 0.0 for c in wp._solids()[0].measure().centroid]
        [3.0, 1.0, 0.5]
        """
        if not self._stack:
            cx, cy = 0.0, 0.0
        else:
            point = self._stack[0] if len(self._stack) == 1 else None
            if not isinstance(point, _Path) or point.segments:
                raise UnsupportedApi("Workplane.polygon on a non-empty stack")
            cx, cy = point.start
        angle = 2.0 * math.pi / nSides
        radius = diameter / 2.0
        vertices: list[tuple[float, float]] = []
        for i in range(nSides):
            o = angle * i
            vertices.append((cx + radius * math.cos(o), cy + radius * math.sin(o)))
        # These checks come after the vertex loop on purpose: CadQuery's own
        # ZeroDivisionError (nSides 0) and TypeError (a float nSides) raise
        # first, from the same expressions, so those rows agree.
        named = f"Workplane.polygon({nSides}, {diameter})"
        if nSides < 3:
            # CadQuery raises StdFail_NotDone below two sides. Two sides make
            # the oracle's zero-volume solid, which cq does not build: a
            # cq_bug row (regression/cq-polygon-two-sides), not by design.
            raise ValueError(f"{named}: fewer than three sides enclose no area")
        if diameter == 0:
            raise ValueError(f"{named}: a zero diameter (CadQuery's StdFail_NotDone)")
        return self._derive(self._plane.polygon(vertices))

    @census_form("Workplane.sketch")
    def sketch(self) -> Sketch:
        """Start a mutable sketch on this plane. A nonempty stack is outside the subset.

        The original workplane stays empty. The sketch's `finalize()`
        returns the workplane holding the sketch for extrusion.

        >>> import arris_gym.cq as cq
        >>> s = cq.Workplane("XY").sketch().circle(1)
        >>> round(s.finalize().extrude(2)._solids()[0].measure().volume, 6)
        6.283185
        """
        if self._stack:
            raise UnsupportedApi("Workplane.sketch on a non-empty stack")
        return Sketch(self)

    @census_form("Workplane.extrude", [("num",)], keywords={"both": ("bool",)})
    @_one_sided_sketch_extrusion
    def extrude(self, distance: float, both: bool = False) -> Workplane:
        """The pending sketch extruded `distance` along the plane's normal.

        The solid grows from the plane, not about it, and is fused with the
        chain's solid if there is one (CadQuery's `combine=True`); on circles
        drawn at a stack of points (`circle`) it builds a post at each. With
        `both`, it grows `distance` to each side of the plane: CadQuery fuses
        the two sweeps and cleans away the seam, which is the one prism of
        height `2|distance|` that arris sweeps in one go: the same volume,
        centroid and bounds, and the same faces for a polygon profile, while
        a full circle's glued halves leave the oracle one face more (face
        counts are carried, never judged). Raises `ValueError`
        (`runtime`) when the stack holds no pending sketch, and for a zero
        `distance` with or without `both` (CadQuery's
        `Standard_ConstructionError` from the zero-length sweep).
        A finalized `sketch()` is extruded as one section (ADR-0023).
        The `both` keyword on that stack raises `UnsupportedApi`.

        >>> import arris_gym.cq as cq
        >>> wp = cq.Workplane("XY").circle(1).extrude(2)
        >>> round(wp._solids()[0].measure().centroid[2], 9)
        1.0
        >>> wp = cq.Workplane("XY").circle(1).extrude(2, both=True)
        >>> round(wp._solids()[0].measure().centroid[2], 9)
        0.0
        """
        if len(self._stack) == 1 and isinstance(self._stack[0], Sketch):
            return self._combined(self._stack[0]._extrusion(distance))._with_seams(None)
        discs = [o for o in self._stack if isinstance(o, _Discs)]
        sketches: Sequence[arris.build.Sketch]
        if discs and len(self._stack) == 1:
            sketches = discs[0].sketches
        else:
            sketches = (self._pending_sketch("Workplane.extrude"),)
        if distance == 0:
            raise ValueError(
                f"Workplane.extrude({distance}, both={both}): a zero distance "
                "(CadQuery's Standard_ConstructionError)"
            )
        result = self
        for sketch in sketches:
            tool = sketch.extrude(distance, both=both)
            result = result._combined(tool)._with_seams(seams_of(tool, sketch.plane.x))
        return result

    @census_form("Workplane.cutBlind", [("num",)])
    def cutBlind(self, until: float) -> Workplane:
        """The pending circle, ring or circles at points extruded `until` and cut from the solid.

        Each pending sketch is swept `until` along the plane's normal, against
        it when negative, and all the sweeps are cut from the chain's solid in
        one call (ADR-0019 rule 3). A negative `until` cuts into the part from
        a face, a depth past the part leaves a hole through, and a positive
        one runs out of the face's plane and leaves the part as it is. In
        CadQuery's order it raises `ValueError` (`runtime`): with no pending
        sketch, "No pending wires present"; then for `until == 0`, naming
        CadQuery's `Standard_ConstructionError` (the sweep comes first, so a
        chain with no solid ends there too); then with no solid in the chain,
        "Cannot find a solid on the stack or in the parent chain"
        (`runtime-cut-blind-*`). The keywords no corpus program writes
        (`clean=`, `both=`, `taper=`) and an `until` that is not a number
        end `unsupported_api`. A stack of selected faces or of points, and a
        drawn path, are outside the subset, as for `extrude`.

        >>> import arris_gym.cq as cq
        >>> wp = cq.Workplane("XY").box(2, 2, 2).faces(">Z").workplane()
        >>> round(wp.circle(0.5).cutBlind(-1)._solids()[0].measure().volume, 9)
        7.214601837
        """
        discs = [o for o in self._stack if isinstance(o, _Discs)]
        sketches: Sequence[arris.build.Sketch]
        if discs and len(self._stack) == 1:
            sketches = discs[0].sketches
        else:
            sketches = (self._pending_sketch("Workplane.cutBlind"),)
        if until == 0:
            raise ValueError(
                f"Workplane.cutBlind({until}): a zero depth (CadQuery's Standard_ConstructionError)"
            )
        base = self._base_solid()
        if base is None:
            raise ValueError(_NO_SOLID)
        return self._cut_sketches(base, [(s, until) for s in sketches])

    @census_form("Workplane.cutThruAll")
    def cutThruAll(self) -> Workplane:
        """Cut the chain's solid with the pending profiles through its full thickness.

        Each profile cuts along its plane's normal in both directions,
        including from outside the stock or through a compound. A miss
        leaves the stock intact. Circles, circles at points, polygons and
        closed paths are supported. Raises `ValueError` for a missing solid
        before checking for pending wires, and for missing wires or a ring
        (CadQuery's Standard_OutOfRange). A finalized sketch and keyword
        forms raise `UnsupportedApi` (ADR-0024 §A).

        See `ok-cut-thru-all-far`, `runtime-cut-thru-all-no-solid`,
        `runtime-cut-thru-all-no-wires`, `runtime-cut-thru-all-ring`,
        `unsupported-cut-thru-all-finalized-sketch`,
        `unsupported-cut-thru-all-clean` and `unsupported-cut-thru-all-taper`.

        >>> import arris_gym.cq as cq
        >>> wp = cq.Workplane("XY").box(2, 2, 2).faces(">Z").workplane(offset=10)
        >>> round(wp.circle(0.5).cutThruAll()._solids()[0].measure().volume, 9)
        6.429203673
        """
        base = self._base_solid()
        if base is None:
            raise ValueError(_NO_SOLID)
        self._refuse_sketch("Workplane.cutThruAll")
        profile = self._stack[0] if len(self._stack) == 1 else None
        sketches: Sequence[arris.build.Sketch]
        if isinstance(profile, _Discs):
            sketches = profile.sketches
        elif isinstance(profile, arris.build.Sketch):
            if profile.holes:
                raise ValueError("CadQuery's Standard_OutOfRange: NCollection_Sequence::Value")
            sketches = (profile,)
        else:
            raise ValueError(_NO_WIRES)
        box = self._bore_bounds(base)
        clearance = self._bore_length(box)
        return self._cut_sketches(
            base, [self._through_sweep(sketch, box, clearance) for sketch in sketches]
        )

    @staticmethod
    def _through_sweep(
        sketch: arris.build.Sketch, box: _Bounds, clearance: float
    ) -> tuple[arris.build.Sketch, float]:
        """A sweep from before the projected stock bounds to past their far end."""
        plane = sketch.plane
        lo, hi = box
        # Each axis contributes its own interval to the projection.
        projected = [
            sorted(((a - origin) * normal, (b - origin) * normal))
            for a, b, origin, normal in zip(lo, hi, plane.origin, plane.z, strict=True)
        ]
        start = sum(near for near, _ in projected) - clearance
        end = sum(far for _, far in projected) + clearance
        return sketch.moved_to(plane.offset(start)), end - start

    def _cut_sketches(
        self, base: arris.build.Solid, sweeps: Sequence[tuple[arris.build.Sketch, float]]
    ) -> Workplane:
        """Cut all swept profiles in order in one call and retain their seam directions."""
        tools = [sketch.extrude(distance, model=base.model) for sketch, distance in sweeps]
        seams: tuple[Seam, ...] | None = ()
        for (sketch, _), tool in zip(sweeps, tools, strict=True):
            placed = seams_of(tool, sketch.plane.x)
            seams = None if seams is None or placed is None else seams + placed
        return self._derive(base.cut(*tools))._with_seams(seams)

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
        `includeCurrent=False` does, so a lone `moveTo` point on the stack is
        dropped and `polyline` after it is `polyline` alone (read on the
        oracle: `ok-polyline-after-moveto-*`). Refuses, as `UnsupportedApi`, a
        stack that holds any other pending wire (a drawn path, which
        CadQuery joins to the polyline's edges, or a sketch) and a list of
        fewer than two points: CadQuery's one-point polyline is no `moveTo`
        point (read on the oracle: `unsupported-polyline-one-point-*`,
        `unsupported-polyline-after-drawn-path`).

        >>> import arris_gym.cq as cq
        >>> wp = cq.Workplane("XY").polyline([(0, 0), (3, 0), (0, 4)]).close()
        >>> round(wp.extrude(1)._solids()[0].measure().volume, 9)
        6.0
        >>> wp = cq.Workplane("XY").moveTo(5, 5).polyline([(0, 0), (3, 0), (0, 4)]).close()
        >>> round(wp.extrude(1)._solids()[0].measure().volume, 9)
        6.0
        """
        lone_point = (
            len(self._stack) == 1
            and isinstance(self._stack[0], _Path)
            and not self._stack[0].segments
        )
        if not lone_point:
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
        if isinstance(last, Sketch):
            raise RuntimeError(_SKETCH_TO_VECTOR)
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
        sketch = self._pending_sketch("Workplane.revolve")
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
        # Where Open CASCADE starts a turned face is not modelled: no seam is placed.
        return self._combined(arris.build.Solid.of(made))._with_seams(None)

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
        return result._with_seams(toUnion._seams)

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
            raise ValueError(_NO_SOLID)
        # A cut that splits its base is CadQuery's compound: one solid with a
        # shell per piece (ADR-0016).
        return self._derive(base.cut(*tools))._with_seams(toCut._seams)

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

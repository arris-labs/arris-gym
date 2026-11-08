"""`Workplane`: a plane, a stack of objects and the workplane it came from.

ADR-0007. Every call returns a new `Workplane`; none changes one in place.
Private: `arris_gym.cq` exports `Workplane`.
"""

from __future__ import annotations

import math
from typing import NoReturn

import arris.build

from arris_gym.cq._unsupported import UnsupportedApi, is_python_name
from arris_gym.cq._vector import Vector

__all__ = ["Workplane", "is_python_name"]

# The one named plane the subset has: CadQuery's "XY", origin at 0, x along
# +x and the normal along +z, which is `arris.build.Workplane.XY()`.
_XY = "XY"
# CadQuery's degrees-to-radians factor, applied as it applies it (one
# multiplication by pi / 180): not a tolerance.
_RADIANS_PER_DEGREE = math.pi / 180.0
_ZERO = Vector(0, 0, 0)


def _shell_count(solid: arris.build.Solid) -> int:
    """The shells of `solid`'s body, cavities included."""
    return len(solid.model.shells(solid.body))


class Workplane:
    """CadQuery's `Workplane` over `arris.build`: a frozen value.

    It holds its plane (an `arris.build.Workplane`), its **stack** (the
    objects its call made, newest last) and its parent (the workplane it was
    called on, `None` for one made by `cq.Workplane(...)`). Guarantees: no
    call changes a `Workplane`; a name the subset lacks raises
    `UnsupportedApi` naming it (`Workplane.sphere`), never `AttributeError`;
    setting an attribute raises `UnsupportedApi` too, and a copy is the
    workplane itself. Refuses every named plane but `"XY"`.

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

    def __init__(self, inPlane: str = _XY) -> None:
        if type(inPlane) is not str or inPlane != _XY:
            raise UnsupportedApi(f"cq.Workplane({inPlane!r})")
        object.__setattr__(self, "_plane", arris.build.Workplane.XY())
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
        """The solids on the stack, in stack order."""
        return tuple(o for o in self._stack if isinstance(o, arris.build.Solid))

    def _base_solid(self) -> arris.build.Solid | None:
        """The solid a combining call acts on: the nearest in this chain, else `None`.

        CadQuery looks at this workplane's stack, then its parent's, and so
        on. A stack holding several solids is a compound, outside the subset.
        """
        node: Workplane | None = self
        while node is not None:
            solids = node._solids()
            if len(solids) > 1:
                raise UnsupportedApi(f"a Workplane holding {len(solids)} solids")
            if solids:
                return solids[0]
            node = node._parent
        return None

    def _combined(self, new: arris.build.Solid) -> Workplane:
        """A workplane on this plane with `new` fused into the chain's solid, if any.

        Where the two are disjoint, `fuse` returns one solid with the shells
        of both; CadQuery's compound of two solids is modelled as both on the
        stack, so the result resolves to `unsupported_api` (ADR-0007).
        """
        base = self._base_solid()
        if base is None:
            return self._derive(new)
        fused = base.fuse(new)
        if _shell_count(fused) >= _shell_count(base) + _shell_count(new):
            return self._derive(base, new)
        return self._derive(fused)

    def _operand(self, other: object, form: str) -> tuple[arris.build.Solid, ...]:
        """The solids of the workplane given to `union` or `cut`; `form` names the call."""
        if not isinstance(other, Workplane):
            raise UnsupportedApi(f"{form} with {type(other).__name__}")
        solids = other._solids()
        if not solids:
            raise ValueError(f"{form} was given a Workplane holding no solid")
        return solids

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
        plane = self._plane
        turned = plane
        # Each `rotated` turns about a fixed world direction through the
        # origin, so applying z, then y, then x about the parent's axes gives
        # Rx·Ry·Rz (CadQuery's `Plane.rotated`, `occ_impl/geom.py`).
        for degrees, axis in ((rotate.z, plane.z), (rotate.y, plane.y), (rotate.x, plane.x)):
            turned = turned.rotated(degrees * _RADIANS_PER_DEGREE, axis)
        origin = plane.point(offset.x, offset.y, offset.z)
        return self._derive_on(arris.build.Workplane(origin, turned.x, turned.y, turned.z))

    def box(self, length: float, width: float, height: float) -> Workplane:
        """A `length` by `width` by `height` box centred on the workplane's origin.

        `length` runs along the workplane's x, `width` along its y and
        `height` along its normal; the box is the one solid on the new stack.
        A box on a workplane whose chain holds a solid is fused with it, as
        CadQuery's `combine=True` does.

        >>> import arris_gym.cq as cq
        >>> round(cq.Workplane("XY").box(2, 3, 4)._solids()[0].measure().volume, 9)
        24.0
        """
        sketch = self._plane.offset(-height / 2).rect(length, width)
        return self._combined(sketch.extrude(height))

    def union(self, toUnion: Workplane) -> Workplane:
        """The chain's solid fused with the solid of `toUnion`, on this plane.

        Raises `ValueError` (a CadQuery error, `runtime`) when the chain holds
        no solid or `toUnion` holds none. Disjoint solids make a compound,
        which the subset lacks: the result then holds both and ends
        `unsupported_api` when it resolves (ADR-0007).

        >>> import arris_gym.cq as cq
        >>> a = cq.Workplane("XY").box(2, 2, 2)
        >>> b = cq.Workplane("XY").transformed(offset=cq.Vector(1, 1, 1)).box(2, 2, 2)
        >>> round(a.union(b)._solids()[0].measure().volume, 9)
        15.0
        """
        others = self._operand(toUnion, "Workplane.union(Workplane)")
        base = self._base_solid()
        if base is None:
            raise ValueError("Cannot find a solid on the stack or in the parent chain")
        result = self
        for other in others:
            result = result._combined(other)
        return result

    def cut(self, toCut: Workplane) -> Workplane:
        """The chain's solid less the solid of `toCut`, on this plane.

        Raises `ValueError` (`runtime`) when the chain holds no solid or
        `toCut` holds none.

        >>> import arris_gym.cq as cq
        >>> a = cq.Workplane("XY").box(4, 4, 4)
        >>> b = cq.Workplane("XY").box(1, 1, 6)
        >>> round(a.cut(b)._solids()[0].measure().volume, 9)
        60.0
        """
        tools = self._operand(toCut, "Workplane.cut(Workplane)")
        base = self._base_solid()
        if base is None:
            raise ValueError("Cannot find a solid on the stack or in the parent chain")
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

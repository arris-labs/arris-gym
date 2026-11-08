"""`Workplane`: a plane, a stack of objects and the workplane it came from.

ADR-0007. Every call returns a new `Workplane`; none changes one in place.
Private: `arris_gym.cq` exports `Workplane`.
"""

from __future__ import annotations

from typing import NoReturn

import arris.build

from arris_gym.cq._unsupported import UnsupportedApi

# The one named plane the subset has: CadQuery's "XY", origin at 0, x along
# +x and the normal along +z, which is `arris.build.Workplane.XY()`.
_XY = "XY"


def is_python_name(name: str) -> bool:
    """Whether `name` belongs to Python or to arris-gym, never to CadQuery's API.

    A name with a leading underscore (a dunder protocol lookup such as
    `__deepcopy__`, or one of this package's private modules) answers
    `AttributeError` as Python expects, never `UnsupportedApi`.
    """
    return name.startswith("_")


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

    def _solids(self) -> tuple[arris.build.Solid, ...]:
        """The solids on the stack, in stack order."""
        return tuple(o for o in self._stack if isinstance(o, arris.build.Solid))

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

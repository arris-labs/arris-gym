"""`Vector`: CadQuery's three numbers, as a frozen value. Private: `arris_gym.cq`
exports it."""

from __future__ import annotations

from typing import NoReturn

from arris_gym.cq._unsupported import UnsupportedApi, is_python_name


class Vector:
    """CadQuery's `Vector(x, y, z)`: three floats, read as `x`, `y` and `z`.

    In the subset a `Vector` is what `Workplane.transformed` takes as its
    `offset` (a point in the workplane's coordinates) and its `rotate` (three
    angles in degrees). Guarantees: no operation changes a `Vector`; a name
    the subset lacks raises `UnsupportedApi` naming it (`Vector.Length`), and
    so does setting an attribute.

    >>> import arris_gym.cq as cq
    >>> v = cq.Vector(1, 2, 3)
    >>> (v.x, v.y, v.z)
    (1.0, 2.0, 3.0)
    >>> try:
    ...     v.Length
    ... except cq.UnsupportedApi as error:
    ...     print(error)
    Vector.Length
    """

    __slots__ = ("_xyz",)

    _xyz: tuple[float, float, float]

    def __init__(self, x: float, y: float, z: float) -> None:
        object.__setattr__(self, "_xyz", (float(x), float(y), float(z)))

    @property
    def x(self) -> float:
        """The first number."""
        return self._xyz[0]

    @property
    def y(self) -> float:
        """The second number."""
        return self._xyz[1]

    @property
    def z(self) -> float:
        """The third number."""
        return self._xyz[2]

    def __repr__(self) -> str:
        return f"Vector: {self._xyz!r}"

    def __copy__(self) -> Vector:
        return self

    def __deepcopy__(self, memo: object) -> Vector:
        return self

    def __getattr__(self, name: str) -> NoReturn:
        if is_python_name(name):
            raise AttributeError(name)
        raise UnsupportedApi(f"Vector.{name}")

    def __setattr__(self, name: str, value: object) -> NoReturn:
        raise UnsupportedApi(f"setting Vector.{name}")

    def __delattr__(self, name: str) -> NoReturn:
        raise UnsupportedApi(f"deleting Vector.{name}")

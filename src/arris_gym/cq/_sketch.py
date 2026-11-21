"""The mutable sketch attached to a Workplane by `sketch()` (ADR-0023)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, NoReturn

import arris.build

from arris_gym.cq._forms import census_form, numbers_of, shape_of
from arris_gym.cq._unsupported import UnsupportedApi, is_python_name

if TYPE_CHECKING:
    from arris_gym.cq._workplane import Workplane

_Mode = Literal["a", "s", "i"]
_Point = tuple[float, float]
_ORIGIN: _Point = (0.0, 0.0)
_LOCAL = arris.build.Workplane.XY()
# Extrusion commutes with the section's operations at any nonzero depth.
# Use a unit prism to test for an empty section before another cut or common.
_SECTION_DEPTH = 1.0


@dataclass(frozen=True)
class _Call:
    mode: _Mode
    regions: tuple[arris.build.Sketch, ...]


class Sketch:
    """Plane-local regions and a selection shared by successive drawing calls.

    Construct it through `Workplane.sketch()`. Drawing calls return the same
    sketch, and a finalized workplane sees edits made before its extrusion.
    """

    __slots__ = ("_calls", "_selection", "_workplane")

    def __init__(self, parent: Workplane) -> None:
        self._calls: list[_Call] = []
        self._selection: tuple[_Point, ...] = ()
        self._workplane = parent._derive(self)

    @census_form("Sketch.finalize")
    def finalize(self) -> Workplane:
        """Return the workplane holding this sketch, ready for `extrude(distance)`.

        >>> from arris_gym.cq import Workplane
        >>> sketch = Workplane("XY").sketch().rect(2, 3)
        >>> round(sketch.finalize().extrude(2)._solids()[0].measure().volume, 6)
        12.0
        """
        return self._workplane

    @census_form("Sketch.push", [("list",)])
    def push(self, pts: Sequence[object]) -> Sketch:
        """Replace the selection with the given pairs of plane-local coordinates.

        An empty list selects the origin for the next drawing call. A point
        other than a pair of numbers raises `UnsupportedApi`.

        >>> from arris_gym.cq import Workplane
        >>> s = Workplane("XY").sketch().push([(3, 5)]).rect(2, 2)
        >>> s.finalize().extrude(2)._solids()[0].measure().centroid
        (3.0, 5.0, 1.0)
        """
        points = []
        for point in pts:
            pair = numbers_of(point, (2,))
            if pair is None:
                raise UnsupportedApi(f"Sketch.push(list with a point of {shape_of(point)})")
            points.append((pair[0], pair[1]))
        self._selection = tuple(points)
        return self

    @census_form("Sketch.reset")
    def reset(self) -> Sketch:
        """Clear the selection. Future drawing calls use the origin.

        >>> from arris_gym.cq import Workplane
        >>> s = Workplane("XY").sketch().push([(4, 5)]).reset().rect(2, 2)
        >>> s.finalize().extrude(2)._solids()[0].measure().centroid
        (0.0, 0.0, 1.0)
        """
        self._selection = ()
        return self

    @census_form("Sketch.circle", [("num",)], keywords={"mode": ("str",)})
    def circle(self, r: float, *, mode: str = "a") -> Sketch:
        """Add, subtract or intersect discs at the selected points with mode a, s or i.

        A nonpositive radius or an invalid mode raises `ValueError`.

        >>> from arris_gym.cq import Workplane
        >>> s = Workplane("XY").sketch().circle(2).circle(1, mode="s")
        >>> round(s.finalize().extrude(2)._solids()[0].measure().volume, 6)
        18.849556
        """
        if r < 0:
            raise ValueError("gp_Circ() - radius should be positive number")
        if r == 0:
            raise ValueError("Cannot build face(s): wires not planar")
        return self._append(
            mode, tuple(_LOCAL.circle(r, center=p) for p in self._selection or (_ORIGIN,))
        )

    @census_form("Sketch.rect", [("num",)] * 2, keywords={"mode": ("str",)})
    def rect(self, w: float, h: float, *, mode: str = "a") -> Sketch:
        """Place centred rectangles at the selected points with mode a, s or i.

        Width and height are magnitudes along local x and y. A zero
        dimension or an invalid mode raises `ValueError`.

        >>> from arris_gym.cq import Workplane
        >>> s = Workplane("XY").sketch().rect(-2, 4)
        >>> round(s.finalize().extrude(2)._solids()[0].measure().volume, 6)
        16.0
        """
        if w == 0 or h == 0:
            raise ValueError("Sketch.rect() dimensions must be nonzero")
        return self._append(
            mode,
            tuple(_LOCAL.rect(abs(w), abs(h), center=p) for p in self._selection or (_ORIGIN,)),
        )

    def _append(self, mode: str, regions: tuple[arris.build.Sketch, ...]) -> Sketch:
        match mode:
            case "a" | "s" | "i" as valid_mode:
                if valid_mode != "a" and not self._has_section():
                    raise ValueError("Null TopoDS_Shape object")
                self._calls.append(_Call(valid_mode, regions))
                return self
            case "c":
                raise ValueError("No tag specified - the geometry will be unreachable")
            case _:
                raise ValueError(f"Invalid mode: {mode}")

    def _has_section(self) -> bool:
        if not self._calls:
            return False
        # An add always supplies material. A preceding cut or common can
        # leave nothing. Resolve that before accepting another drawing call,
        # so a program can catch its ValueError at that call.
        return self._calls[-1].mode == "a" or (
            self._fold(_LOCAL, _SECTION_DEPTH, arris.Model()) is not None
        )

    def _extrusion(self, distance: float) -> arris.build.Solid:
        """The section swept by a signed distance, or ValueError for an empty section."""
        if distance == 0:
            if not self._has_section():
                raise ValueError("No pending wires present")
            raise ValueError("Workplane.extrude: a zero distance")
        section = self._fold(self._workplane._plane, distance, arris.build.default_model())
        if section is None:
            raise ValueError("No pending wires present")
        return section

    def _fold(
        self, plane: arris.build.Workplane, distance: float, model: arris.Model
    ) -> arris.build.Solid | None:
        """Evaluate the grouped prism fold in call and selection order."""
        extended = plane.offset(-distance)
        current: arris.build.Solid | None = None
        for call in self._calls:
            if call.mode == "a":
                for region in call.regions:
                    tool = region.moved_to(plane).extrude(distance, model=model)
                    current = tool if current is None else current.fuse(tool)
                continue
            if current is None:
                raise ValueError("Null TopoDS_Shape object")
            # Extend the tools across both caps of the section, in either
            # extrusion direction. The section inside that interval is unchanged.
            section = current
            if call.mode == "i":
                current = None
            for region in call.regions:
                target = section if call.mode == "i" else current
                if target is None:
                    break
                tool = region.moved_to(extended).extrude(3 * distance, model=model)
                found = model.interference(target.body, tool.body)
                if call.mode == "s":
                    if found.a_in_b:
                        current = None
                    elif found.kind == "overlapping":
                        current = target.cut(tool)
                elif found.a_in_b:
                    current = section
                    break
                elif found.kind == "overlapping":
                    piece = section.common(tool)
                    current = piece if current is None else current.fuse(piece)
        return current

    def __getattr__(self, name: str) -> NoReturn:
        if is_python_name(name):
            raise AttributeError(name)
        raise UnsupportedApi(f"Sketch.{name}")

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
class _Edge:
    start: _Point
    end: _Point
    via: _Point | None = None

    def reversed(self) -> _Edge:
        return _Edge(self.end, self.start, self.via)

    def placed(self, offset: _Point) -> arris.Segment:
        end = _translated(self.end, offset)
        if self.via is None:
            return arris.Segment.line(end)
        return arris.Segment.arc(end, _translated(self.via, offset))


def _translated(point: _Point, offset: _Point) -> _Point:
    return (point[0] + offset[0], point[1] + offset[1])


def _edge_point(point: object, method: str) -> _Point:
    pair = numbers_of(point, (2,))
    if pair is None:
        raise UnsupportedApi(f"Sketch.{method}(tuple with a point of {shape_of(point)})")
    return (pair[0], pair[1])


@dataclass(frozen=True)
class _Call:
    mode: _Mode
    regions: tuple[arris.build.Sketch | _PlacedFold, ...]


@dataclass(frozen=True)
class _PlacedFold:
    calls: tuple[_Call, ...]
    point: _Point


def _prism(
    region: arris.build.Sketch | _PlacedFold,
    plane: arris.build.Workplane,
    distance: float,
    model: arris.Model,
) -> arris.build.Solid | None:
    if isinstance(region, _PlacedFold):
        (placed,) = plane.at((region.point,))
        return _fold(region.calls, placed, distance, model)
    return region.moved_to(plane).extrude(distance, model=model)


def _fold(
    calls: Sequence[_Call],
    plane: arris.build.Workplane,
    distance: float,
    model: arris.Model,
) -> arris.build.Solid | None:
    """Evaluate the grouped prism fold in call and selection order."""
    extended = plane.offset(-distance)
    current: arris.build.Solid | None = None
    for call in calls:
        if call.mode == "a":
            for region in call.regions:
                tool = _prism(region, plane, distance, model)
                if tool is not None:
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
            tool = _prism(region, extended, 3 * distance, model)
            if tool is None:
                continue
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


class Sketch:
    """Plane-local regions, free edges and a selection shared by drawing calls.

    Construct it through `Workplane.sketch()`. Drawing calls return the same
    sketch, and a finalized workplane sees edits made before its extrusion.
    """

    __slots__ = ("_calls", "_edges", "_selection", "_workplane")

    def __init__(self, parent: Workplane) -> None:
        self._calls: list[_Call] = []
        self._edges: list[_Edge] = []
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

    @census_form("Sketch.face", [("call",)], keywords={"mode": ("str",)})
    def face(self, sketch: Sketch, *, mode: str = "a") -> Sketch:
        """Place a snapshot of a sketch's local section at each selected point.

        Use the origin with an empty selection. Modes a, s and i add,
        subtract and intersect the placed sections, respectively. The tool's
        workplane and later edits have no effect. An empty tool raises
        `ValueError`, or `IndexError` for an add to an empty section.
        An invalid mode raises `ValueError`. Other argument types raise
        `UnsupportedApi`.

        >>> from arris_gym.cq import Workplane
        >>> tool = Workplane("XY").sketch().rect(2, 2)
        >>> s = Workplane("XY").sketch().rect(4, 4).face(tool, mode="s")
        >>> round(s.finalize().extrude(2)._solids()[0].measure().volume, 6)
        24.0
        """
        if not isinstance(sketch, Sketch):
            # A Vector also has the census kind "call" (`unsupported-sketch-face-non-sketch`).
            raise UnsupportedApi("Sketch.face requires a Sketch")
        calls = tuple(sketch._calls)
        regions = (
            tuple(_PlacedFold(calls, p) for p in self._selection or (_ORIGIN,))
            if sketch._has_section()
            else ()
        )
        return self._append(mode, regions)

    @census_form("Sketch.segment", [("tuple",)], alternatives=[[("tuple",)] * 2])
    def segment(self, p1: tuple[float, float], p2: tuple[float, float] | None = None) -> Sketch:
        """Draw a line from `p1` to `p2`, or from the last end to `p1`.

        Points are pairs of plane coordinates. An implicit start without a
        free edge or a zero-length line raises `ValueError`.

        >>> from arris_gym.cq import Workplane
        >>> s = Workplane("XY").sketch()
        >>> s.segment((0, 0), (4, 0)).segment((0, 2)) is s
        True
        """
        first = _edge_point(p1, "segment")
        start, end = (
            (self._last_end(), first) if p2 is None else (first, _edge_point(p2, "segment"))
        )
        if start == end:
            # The same degenerate line is drawn by `runtime-sketch-close-already-closed`.
            raise ValueError("BRep_API: command not done")
        self._edges.append(_Edge(start, end))
        return self

    @census_form("Sketch.arc", [("tuple",)] * 2, alternatives=[[("tuple",)] * 3])
    def arc(
        self,
        p1: tuple[float, float],
        p2: tuple[float, float],
        p3: tuple[float, float] | None = None,
    ) -> Sketch:
        """Draw a circular arc through the given plane-local points.

        With two points, use the last free edge's end as the start. An
        implicit start without a preceding edge or a collinear triple
        raises `ValueError`.

        >>> from arris_gym.cq import Workplane
        >>> s = Workplane("XY").sketch()
        >>> s.arc((1, 0), (0, 1), (-1, 0)) is s
        True
        """
        first, second = _edge_point(p1, "arc"), _edge_point(p2, "arc")
        if p3 is None:
            start, via, end = self._last_end(), first, second
        else:
            start, via, end = first, second, _edge_point(p3, "arc")
        via_x, via_y = via[0] - start[0], via[1] - start[1]
        end_x, end_y = end[0] - start[0], end[1] - start[1]
        if via_x * end_y == via_y * end_x:
            raise ValueError("GC_MakeArcOfCircle::Value() - no result")
        self._edges.append(_Edge(start, end, via))
        return self

    @census_form("Sketch.close")
    def close(self) -> Sketch:
        """Draw a line from the last free edge's end to the first edge's start.

        An empty edge list or a zero-length closing line raises `ValueError`.

        >>> from arris_gym.cq import Workplane
        >>> s = Workplane("XY").sketch().segment((0, 0), (4, 0)).segment((0, 2))
        >>> s.close() is s
        True
        """
        end = self._last_end()
        return self.segment(end, self._edges[0].start)

    @census_form("Sketch.assemble")
    def assemble(self) -> Sketch:
        """Add a region at each selected point, or at the origin.

        The free edges must make one closed loop, else `ValueError`.
        Assembly orders and reverses edges as needed and retains them for
        later calls.

        >>> from arris_gym.cq import Workplane
        >>> s = Workplane("XY").sketch().segment((0, 0), (4, 0)).segment((0, 2))
        >>> round(s.close().assemble().finalize().extrude(2)._solids()[0].measure().volume, 6)
        8.0
        """
        edges = self._closed_loop()
        return self._append(
            "a",
            tuple(
                arris.build.Sketch(
                    _LOCAL,
                    arris.Loop.path(
                        _translated(edges[0].start, offset),
                        [edge.placed(offset) for edge in edges],
                    ),
                )
                for offset in self._selection or (_ORIGIN,)
            ),
        )

    def _last_end(self) -> _Point:
        if not self._edges:
            raise ValueError("No free edges available")
        return self._edges[-1].end

    def _closed_loop(self) -> list[_Edge]:
        message = "Sketch.assemble() free edges do not form one closed loop"
        if not self._edges:
            raise ValueError(message)
        first, *remaining = self._edges
        ordered = [first]
        while remaining and ordered[-1].end != first.start:
            end = ordered[-1].end
            for index, edge in enumerate(remaining):
                if edge.start == end or edge.end == end:
                    remaining.pop(index)
                    ordered.append(edge if edge.start == end else edge.reversed())
                    break
            else:
                raise ValueError(message)
        if remaining or ordered[-1].end != first.start:
            raise ValueError(message)
        return ordered

    def _append(self, mode: str, regions: tuple[arris.build.Sketch | _PlacedFold, ...]) -> Sketch:
        match mode:
            case "a" | "s" | "i" as valid_mode:
                if not regions:
                    # CadQuery's two empty-tool failures are held by
                    # `runtime-sketch-face-empty-add` and `runtime-sketch-face-empty-tool`.
                    if valid_mode == "a" and not self._has_section():
                        raise IndexError("tuple index out of range")
                    raise ValueError("Null TopoDS_Shape object")
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
            _fold(self._calls, _LOCAL, _SECTION_DEPTH, arris.Model()) is not None
        )

    def _extrusion(self, distance: float) -> arris.build.Solid:
        """The section swept by a signed distance, or ValueError for an empty section."""
        if distance == 0:
            if not self._has_section():
                raise ValueError("No pending wires present")
            raise ValueError("Workplane.extrude: a zero distance")
        section = _fold(self._calls, self._workplane._plane, distance, arris.build.default_model())
        if section is None:
            raise ValueError("No pending wires present")
        return section

    def __getattr__(self, name: str) -> NoReturn:
        if is_python_name(name):
            raise AttributeError(name)
        raise UnsupportedApi(f"Sketch.{name}")

"""ADR-0019's evidence: what CadQuery's `rarray`, `polarArray` and `cutBlind` build, and the cut.

The oracle's reports come from `tools/cq_array_probe.py` (outside the gate)
and are committed in `tests/fixtures/arrays/constructed.json`; these tests
read that file offline and hold each report to the closed form of how its
part is built. The last test builds ADR-0019's blind cut in arris, the pending
circle, ring or circles extruded against the face's normal and cut from the
part in one call, flush with a box's face and with a revolved part's end
faces, and holds it to the same closed forms: the kernel risk of `cutBlind`,
read before `cq` lifts it.
"""

from __future__ import annotations

import json
import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import arris
import arris.build
import pytest

import cq_array_probe as probe
import fixture_cases
from arris_gym.fidelity import OracleReport, OracleStatus

ARRAYS = Path(__file__).parent / "fixtures" / "arrays" / "constructed.json"
Point = tuple[float, float, float]
DOWN = (0.0, 0.0, -1.0)
UP = (0.0, 0.0, 1.0)
TURN = 2 * math.pi


@dataclass(frozen=True)
class Prism:
    """A straight prism of one section cut into (or added onto) a part.

    `at` is the section's centroid where the prism starts, `axis` the unit
    direction it runs in for `length`; `section` is its `(area, perimeter)`.
    A cut `opens` when its start lies on the part's face (that disc is an
    opening, not a cap) and goes `through` when its end lies on the opposite
    face.
    """

    at: Point
    axis: Point
    section: tuple[float, float]
    length: float
    opens: bool = True
    through: bool = False

    def volume(self) -> float:
        return self.section[0] * self.length

    def moment(self) -> Point:
        """The prism's volume times its centroid."""
        v = self.volume()
        h = self.length / 2
        return (
            v * (self.at[0] + h * self.axis[0]),
            v * (self.at[1] + h * self.axis[1]),
            v * (self.at[2] + h * self.axis[2]),
        )

    def cut_area(self) -> float:
        """What the prism, cut, adds to the part's area: its walls, and its ends
        taken off the faces they open on or added as caps."""
        a, p = self.section
        return p * self.length + (-a if self.opens else a) + (-a if self.through else a)


def disc(r: float) -> tuple[float, float]:
    return (math.pi * r * r, TURN * r)


def ring(outer: float, inner: float) -> tuple[float, float]:
    return (math.pi * (outer * outer - inner * inner), TURN * (outer + inner))


@dataclass(frozen=True)
class Part:
    """A closed form: a base solid's volume, area and moment, less its cuts,
    plus its posts (prisms standing on its face, their foot on it)."""

    base: tuple[float, float, Point]
    cuts: Sequence[Prism] = ()
    posts: Sequence[Prism] = ()

    def measures(self) -> tuple[float, float, Point]:
        v0, a0, m0 = self.base
        v = v0 - sum(c.volume() for c in self.cuts) + sum(p.volume() for p in self.posts)
        a = a0 + sum(c.cut_area() for c in self.cuts)
        a += sum(p.section[1] * p.length for p in self.posts)
        m = [
            m0[k] - sum(c.moment()[k] for c in self.cuts) + sum(p.moment()[k] for p in self.posts)
            for k in range(3)
        ]
        return v, a, (m[0] / v, m[1] / v, m[2] / v)


# The box, 10 by 8 by 4 about the origin.
BOX = (320.0, 304.0, (0.0, 0.0, 0.0))
# The revolved cylinder, radius 5 from y = 0 to 4, and the flange, the same
# with a bore of radius 2.
_CYLINDER = 100 * math.pi
REV = (_CYLINDER, 90 * math.pi, (0.0, 2 * _CYLINDER, 0.0))
_FLANGE = 84 * math.pi
TUBE = (_FLANGE, 98 * math.pi, (0.0, 2 * _FLANGE, 0.0))


def polar(radius: float, degrees: Sequence[float]) -> list[tuple[float, float]]:
    """CadQuery's points of a polar array, by its expression: the angle in radians, then x and y."""
    out = []
    for d in degrees:
        phi = math.radians(d)
        out.append((radius * math.cos(phi), radius * math.sin(phi)))
    return out


def grid(dx: float, dy: float, nx: int, ny: int) -> list[tuple[float, float]]:
    """CadQuery's points of a centred rectangular array, x outer and y inner."""
    return [
        (dx * i - dx * (nx - 1) / 2, dy * j - dy * (ny - 1) / 2)
        for i in range(nx)
        for j in range(ny)
    ]


def top(
    points: Sequence[tuple[float, float]],
    section: tuple[float, float],
    length: float,
    through: bool = False,
) -> list[Prism]:
    """Cuts from the box's top face, down, at plane points (x, y)."""
    return [Prism((x, y, 2.0), DOWN, section, length, through=through) for x, y in points]


def bores(points: Sequence[tuple[float, float]]) -> list[Prism]:
    """`hole(1)` at plane points of the box's top face: through, radius 1/2."""
    return top(points, disc(0.5), 4.0, through=True)


def on_y_end(
    y: float,
    inward: float,
    points: Sequence[tuple[float, float]],
    section: tuple[float, float],
    length: float,
    through: bool = False,
) -> list[Prism]:
    """Cuts into a revolved part's end face at height `y`, running along `inward` (±1 in y).

    The points' frame on the face is any square one: every array on these
    faces is a full turn about the axis, or a single centred point, so the
    moment does not depend on which.
    """
    return [
        Prism((u, y, v), (0.0, inward, 0.0), section, length, through=through) for u, v in points
    ]


PARTS: dict[str, Part] = {
    "rarray-1x1": Part(BOX, bores([(0.0, 0.0)])),
    "rarray-3x2": Part(BOX, bores(grid(3, 4, 3, 2))),
    # Local (u, v) on `>X` is world (5, u, v), the bore along -x (ADR-0017's frame).
    "rarray-side>X": Part(
        BOX,
        [
            Prism((5.0, u, v), (-1.0, 0.0, 0.0), disc(0.5), 10.0, through=True)
            for u, v in grid(2, 1.5, 2, 2)
        ],
    ),
    # On `<Y`, local (u, v) is world (u, -4, v), the bore along +y.
    "rarray-side<Y": Part(
        BOX,
        [
            Prism((u, -4.0, v), (0.0, 1.0, 0.0), disc(0.5), 8.0, through=True)
            for u, v in grid(3, 1.5, 3, 2)
        ],
    ),
    "rarray-circle-extrude": Part(
        BOX, posts=[Prism((x, y, 2.0), UP, disc(1.0), 1.0) for x, y in grid(4, 3, 2, 2)]
    ),
    # A full turn is split in `count`.
    "polar-full": Part(BOX, bores(polar(3, [60.0 * i for i in range(6)]))),
    "polar-full-start": Part(BOX, bores(polar(3, [30.0 + 90.0 * i for i in range(4)]))),
    "polar-full-negative": Part(BOX, bores(polar(3, [-90.0 * i for i in range(4)]))),
    # A partial turn in `count - 1`, both ends included.
    "polar-partial": Part(BOX, bores(polar(3, [0.0, 45.0, 90.0]))),
    "polar-partial-start": Part(BOX, bores(polar(3, [30.0, 90.0, 150.0]))),
    "polar-partial-negative": Part(BOX, bores(polar(3, [0.0, -90.0]))),
    # One point is at the start angle, whatever the turn.
    "polar-count-1-full": Part(BOX, bores(polar(3, [0.0]))),
    "polar-count-1-partial": Part(BOX, bores(polar(3, [45.0]))),
    # A negative radius puts each point across the centre.
    "polar-radius-negative": Part(BOX, bores(polar(-3, [0.0, 90.0]))),
    # Radius zero: three bores at the centre, one hole.
    "polar-radius-zero": Part(BOX, bores([(0.0, 0.0)])),
    "polar-side>X": Part(
        BOX,
        [
            Prism((5.0, u, v), (-1.0, 0.0, 0.0), disc(0.4), 10.0, through=True)
            for u, v in polar(1.5, [0.0, 90.0])
        ],
    ),
    "polar-circle-extrude": Part(
        BOX,
        posts=[Prism((x, y, 2.0), UP, disc(0.5), 1.0) for x, y in polar(3, [0, 90, 180, 270])],
    ),
    # `cutBlind(depth)`: the pending circle extruded `depth` along the plane's
    # normal, cut from the part.
    "blind-disc": Part(BOX, top([(0.0, 0.0)], disc(1.0), 1.5)),
    "blind-disc-off-centre": Part(BOX, top([(2.0, 1.0)], disc(1.0), 1.5)),
    "blind-to-the-bottom": Part(BOX, top([(0.0, 0.0)], disc(1.0), 4.0, through=True)),
    "blind-past-the-part": Part(BOX, top([(0.0, 0.0)], disc(1.0), 4.0, through=True)),
    # Positive is along the normal: out of the top face, the box unchanged.
    "blind-positive": Part(BOX),
    # From a plane 1 below the top, down 1: a closed void inside the part.
    "blind-inside-the-part": Part(BOX, [Prism((0.0, 0.0, 1.0), DOWN, disc(1.0), 1.0, opens=False)]),
    # From that plane, up 2: through the top, a pocket 1 deep.
    "blind-positive-from-inside": Part(BOX, top([(0.0, 0.0)], disc(1.0), 1.0)),
    "blind-side>X": Part(BOX, [Prism((5.0, 1.0, 0.5), (-1.0, 0.0, 0.0), disc(0.5), 2.0)]),
    # Two circles are a ring, whichever comes first.
    "blind-ring": Part(BOX, top([(0.0, 0.0)], ring(2.0, 1.0), 1.0)),
    "blind-ring-inner-first": Part(BOX, top([(0.0, 0.0)], ring(2.0, 1.0), 1.0)),
    # Circles at points: a pocket at each.
    "blind-points": Part(BOX, top([(-3.0, -2.0), (3.0, 2.0)], disc(0.5), 1.0)),
    "blind-polar": Part(BOX, top(polar(3, [60.0 * i for i in range(6)]), disc(0.5), 1.0)),
    "blind-polar-through": Part(
        BOX, top(polar(3, [60.0 * i for i in range(6)]), disc(0.5), 4.0, through=True)
    ),
    "blind-rarray": Part(BOX, top(grid(4, 3, 2, 2), disc(1.0), 1.0)),
    # On the revolved part's end faces: `>Y` at y = 4, `<Y` at y = 0.
    "rev-blind-disc": Part(REV, on_y_end(4.0, -1.0, [(0.0, 0.0)], disc(1.0), 1.0)),
    "rev-blind-disc<Y": Part(REV, on_y_end(0.0, 1.0, [(0.0, 0.0)], disc(1.0), 1.0)),
    "rev-blind-ring": Part(REV, on_y_end(4.0, -1.0, [(0.0, 0.0)], ring(2.0, 1.0), 1.0)),
    "rev-blind-polar": Part(
        REV, on_y_end(4.0, -1.0, polar(3, [60.0 * i for i in range(6)]), disc(0.5), 1.0)
    ),
    "rev-polar-hole": Part(
        REV,
        on_y_end(0.0, 1.0, polar(3, [90.0 * i for i in range(4)]), disc(0.5), 4.0, through=True),
    ),
    # The flange cut through at six points: the tool's both ends on its faces.
    "tube-blind-polar-through": Part(
        TUBE,
        on_y_end(4.0, -1.0, polar(3.5, [60.0 * i for i in range(6)]), disc(0.5), 4.0, through=True),
    ),
}

# Built otherwise: (volume, area, centroid).
OTHER: dict[str, tuple[float, float, Point]] = {
    # A circle of the end face's own radius takes a slab off: a cylinder 3 long.
    "rev-blind-whole-face": (75 * math.pi, 80 * math.pi, (0.0, 1.5, 0.0)),
}

# What CadQuery raises, its last line verbatim.
_SPACING = "ValueError: Spacing and count must be > 0 "
_FLOAT_COUNT = "TypeError: 'float' object cannot be interpreted as an integer"
_ZERO_SWEEP = "OCP.OCP.Standard.Standard_ConstructionError: BRepSweep_Translation::Constructor"
RAISES: dict[str, str] = {
    "rarray-spacing-zero": _SPACING,
    "rarray-spacing-negative": _SPACING,
    "rarray-count-zero": _SPACING,
    "rarray-count-float": _FLOAT_COUNT,
    "polar-count-zero": "ValueError: At least 1 element required, requested 0",
    "polar-count-negative": "ValueError: At least 1 element required, requested -1",
    "polar-count-float": _FLOAT_COUNT,
    "blind-zero": _ZERO_SWEEP,
    # The sweep is built before the solid is looked for.
    "blind-zero-no-solid": _ZERO_SWEEP,
    "blind-nothing-pending": "ValueError: No pending wires present",
    "blind-no-solid": "ValueError: Cannot find a solid on the stack or in the parent chain",
}


def constructed() -> dict[str, dict[str, Any]]:
    data = json.loads(ARRAYS.read_text(encoding="utf-8"))
    return {c["name"]: c for c in data}


def report(name: str) -> OracleReport:
    return OracleReport.model_validate(constructed()[name]["report"])


def test_every_construction_is_recorded_and_held() -> None:
    records = constructed()
    assert list(records) == sorted(probe.CONSTRUCTED)
    assert {n: c["program"] for n, c in records.items()} == probe.constructed_programs()
    assert sorted([*PARTS, *OTHER, *RAISES]) == sorted(records)


def _held(got: tuple[float, float, Point], want: tuple[float, float, Point]) -> None:
    pairs = [(got[0], want[0]), (got[1], want[1]), *zip(got[2], want[2], strict=True)]
    assert all(fixture_cases.close(g, w) for g, w in pairs), pairs


def _oracle(name: str) -> tuple[float, float, Point]:
    got = report(name)
    assert got.status is OracleStatus.OK, got.message
    assert got.measures is not None
    assert got.measures.solids == 1
    c = got.measures.centroid
    return got.measures.volume, got.measures.area, (c[0], c[1], c[2])


@pytest.mark.parametrize("name", sorted(PARTS))
def test_the_oracle_builds_the_closed_form(name: str) -> None:
    _held(_oracle(name), PARTS[name].measures())


@pytest.mark.parametrize("name", sorted(OTHER))
def test_the_oracle_builds_the_other_closed_form(name: str) -> None:
    _held(_oracle(name), OTHER[name])


@pytest.mark.parametrize("name", sorted(RAISES))
def test_the_oracle_raises_in_its_own_words(name: str) -> None:
    got = report(name)
    assert got.status is OracleStatus.RUNTIME
    assert got.message.splitlines()[-1] == RAISES[name]


# ADR-0019's blind cut in arris: each pending sketch extruded `depth` along
# its plane's normal (against it when negative), all cut from the part in one
# call. The bases are built as `cq` builds them: a box, and a profile on XY
# revolved a full turn about its y axis.
Base = Callable[[arris.Model], arris.build.Solid]


def _box(model: arris.Model) -> arris.build.Solid:
    return arris.build.Solid.box((-5, -4, -2), (5, 4, 2), model=model)


def _revolved(inner: float) -> Base:
    def build(model: arris.Model) -> arris.build.Solid:
        profile = arris.build.Workplane.XY().polygon([(inner, 0), (5, 0), (5, 4), (inner, 4)])
        made = model.revolve(profile.profile(), (0, 0, 0), (0, 1, 0), TURN)
        return arris.build.Solid.of(made)

    return build


_TOP = arris.build.Workplane.of((0, 0, 2), (0, 0, 1), (1, 0, 0))
_SIDE_X = arris.build.Workplane.of((5, 0, 0), (1, 0, 0), (0, 1, 0))
# The revolved part's end faces, normal out of the part, x along +z; any
# square frame gives the same part (`on_y_end`).
_Y_TOP = arris.build.Workplane.of((0, 4, 0), (0, 1, 0), (0, 0, 1))
_Y_BOTTOM = arris.build.Workplane.of((0, 0, 0), (0, -1, 0), (0, 0, 1))


def _discs(
    plane: arris.build.Workplane, points: Sequence[tuple[float, float]], r: float
) -> list[arris.build.Sketch]:
    return [plane.circle(r, center=p) for p in points]


def _ring(plane: arris.build.Workplane, outer: float, inner: float) -> list[arris.build.Sketch]:
    return [arris.build.Sketch(plane, plane.circle(outer).outer, (plane.circle(inner).outer,))]


def _y_points(points: Sequence[tuple[float, float]]) -> list[tuple[float, float]]:
    """Plane points of `_Y_TOP` (x along +z, y along +x) for `on_y_end`'s world (u, ., v)."""
    return [(v, u) for u, v in points]


_SIX = polar(3, [60.0 * i for i in range(6)])

# Keyed by the construction whose closed form the cut must give.
SPIKES: dict[str, tuple[Base, list[arris.build.Sketch], float]] = {
    "blind-disc": (_box, _discs(_TOP, [(0, 0)], 1.0), -1.5),
    "blind-disc-off-centre": (_box, _discs(_TOP, [(2, 1)], 1.0), -1.5),
    # The tool's far end on the box's bottom face.
    "blind-to-the-bottom": (_box, _discs(_TOP, [(0, 0)], 1.0), -4.0),
    "blind-past-the-part": (_box, _discs(_TOP, [(0, 0)], 1.0), -10.0),
    # The tool stands on the top face, touching it only.
    "blind-positive": (_box, _discs(_TOP, [(0, 0)], 1.0), 1.0),
    "blind-inside-the-part": (_box, _discs(_TOP.offset(-1), [(0, 0)], 1.0), -1.0),
    "blind-positive-from-inside": (_box, _discs(_TOP.offset(-1), [(0, 0)], 1.0), 2.0),
    "blind-side>X": (_box, _discs(_SIDE_X, [(1, 0.5)], 0.5), -2.0),
    "blind-ring": (_box, _ring(_TOP, 2.0, 1.0), -1.0),
    "blind-points": (_box, _discs(_TOP, [(-3, -2), (3, 2)], 0.5), -1.0),
    "blind-polar": (_box, _discs(_TOP, _SIX, 0.5), -1.0),
    "blind-polar-through": (_box, _discs(_TOP, _SIX, 0.5), -4.0),
    "blind-rarray": (_box, _discs(_TOP, grid(4, 3, 2, 2), 1.0), -1.0),
    "rev-blind-disc": (_revolved(0.0), _discs(_Y_TOP, [(0, 0)], 1.0), -1.0),
    "rev-blind-disc<Y": (_revolved(0.0), _discs(_Y_BOTTOM, [(0, 0)], 1.0), -1.0),
    # The tool's wall on the part's: a slab off its end.
    "rev-blind-whole-face": (_revolved(0.0), _discs(_Y_TOP, [(0, 0)], 5.0), -1.0),
    "rev-blind-ring": (_revolved(0.0), _ring(_Y_TOP, 2.0, 1.0), -1.0),
    "rev-blind-polar": (_revolved(0.0), _discs(_Y_TOP, _y_points(_SIX), 0.5), -1.0),
    # Six tools through the flange, both ends flush with its faces.
    "tube-blind-polar-through": (
        _revolved(2.0),
        _discs(_Y_TOP, _y_points(polar(3.5, [60.0 * i for i in range(6)])), 0.5),
        -4.0,
    ),
}


def _closed_form(name: str) -> tuple[float, float, Point]:
    return OTHER[name] if name in OTHER else PARTS[name].measures()


@pytest.mark.parametrize("name", sorted(SPIKES))
def test_arris_cuts_the_blind_tools_to_the_closed_form(name: str) -> None:
    base, sketches, depth = SPIKES[name]
    model = arris.Model()
    cut = base(model).cut(*(s.extrude(depth, model=model) for s in sketches))
    assert cut.check().ok
    got = cut.measure()
    c = got.centroid
    _held((got.volume, got.area, (c[0], c[1], c[2])), _closed_form(name))

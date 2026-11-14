"""ADR-0018's evidence: what CadQuery's stacks of points and bore tools build, and arris's tool.

The oracle's reports come from `tools/cq_hole_probe.py` (outside the gate) and
are committed in `tests/fixtures/holes/constructed.json`; these tests read
that file offline and hold each report to the closed form of how its part is
built. The last tests build ADR-0018's tools in arris, CadQuery's pieces
(a cylinder, a counterbore cylinder, a cone revolved from a triangle) cut
from the box in one call, and hold the cut to the same closed forms: the
kernel risk of countersinks and counterbores, read before `cq` lifts them.
"""

from __future__ import annotations

import json
import math
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import arris
import arris.build
import pytest

import cq_hole_probe as probe
import fixture_cases
from arris_gym.fidelity import OracleReport, OracleStatus

HOLES = Path(__file__).parent / "fixtures" / "holes" / "constructed.json"
Point = tuple[float, float, float]
# Every construction's box: 10 by 8 by 4 about the origin.
BOX_VOLUME = 320.0
BOX_AREA = 304.0
# Its diagonal, CadQuery's `largestDimension()`: the depth of a bore with none.
DIAGONAL = math.sqrt(180.0)
TOP = (0.0, 0.0, 2.0)
DOWN = (0.0, 0.0, -1.0)
TURN = 2 * math.pi


@dataclass(frozen=True)
class Bore:
    """A cavity of revolution bored into the box from `at` along the unit `axis`.

    `sections` are its frusta from the entry down, `(radius at top, radius at
    bottom, length)`, already cut to where the part ends. `opens` says the
    entry is on the part's face (its disc is an opening, not a cap), and
    `through` that the last section leaves by the opposite face.
    """

    at: Point
    axis: Point
    sections: tuple[tuple[float, float, float], ...]
    opens: bool = True
    through: bool = True

    def volume(self) -> float:
        return sum(math.pi * h / 3 * (a * a + a * b + b * b) for a, b, h in self.sections)

    def moment(self) -> Point:
        """The cavity's volume times its centroid."""
        depth = 0.0
        total = [0.0, 0.0, 0.0]
        for a, b, h in self.sections:
            v = math.pi * h / 3 * (a * a + a * b + b * b)
            if v > 0:
                s = depth + h * (a * a + 2 * a * b + 3 * b * b) / (4 * (a * a + a * b + b * b))
                for k in range(3):
                    total[k] += v * (self.at[k] + s * self.axis[k])
            depth += h
        return (total[0], total[1], total[2])

    def area(self) -> float:
        """What the cavity adds to the part's area: its walls and steps, its
        entry and exit discs taken off the faces they open or added as caps."""
        a0 = self.sections[0][0]
        out = (-1.0 if self.opens else 1.0) * math.pi * a0 * a0
        for i, (a, b, h) in enumerate(self.sections):
            out += math.pi * (a + b) * math.hypot(h, b - a)
            if i + 1 < len(self.sections):
                out += math.pi * abs(b * b - self.sections[i + 1][0] ** 2)
        b = self.sections[-1][1]
        out += (-1.0 if self.through else 1.0) * math.pi * b * b
        return out


def through(x: float, y: float, r: float) -> Bore:
    return Bore((x, y, 2.0), DOWN, ((r, r, 4.0),))


def blind(x: float, y: float, r: float, depth: float) -> Bore:
    return Bore((x, y, 2.0), DOWN, ((r, r, depth),), through=False)


def cbore(x: float, y: float) -> Bore:
    """`cboreHole(1, 2, 0.5)` at (x, y): the counterbore, then the bore."""
    return Bore((x, y, 2.0), DOWN, ((1.0, 1.0, 0.5), (0.5, 0.5, 3.5)))


def csk(x: float, y: float, angle: float) -> Bore:
    """`cskHole(1, 2, angle)` at (x, y): the cone's frustum to the bore's radius, then the bore."""
    meet = 0.5 / math.tan(math.radians(angle / 2))
    return Bore((x, y, 2.0), DOWN, ((1.0, 0.5, meet), (0.5, 0.5, 4.0 - meet)))


@dataclass(frozen=True)
class Part:
    """A closed form: a base solid's volume, area and moment, less its bores."""

    bores: Sequence[Bore]
    volume0: float = BOX_VOLUME
    area0: float = BOX_AREA
    moment0: Point = (0.0, 0.0, 0.0)

    def measures(self) -> tuple[float, float, Point]:
        v = self.volume0 - sum(b.volume() for b in self.bores)
        a = self.area0 + sum(b.area() for b in self.bores)
        m = [self.moment0[k] - sum(b.moment()[k] for b in self.bores) for k in range(3)]
        return v, a, (m[0] / v, m[1] / v, m[2] / v)


# The union of two radius-1/2 discs whose centres are 1/2 apart: two discs
# less their lens, 2 r^2 acos(d / 2r) - (d / 2) sqrt(4 r^2 - d^2).
_LENS = 2 * 0.25 * math.acos(0.5) - 0.25 * math.sqrt(0.75)
_TWO_DISCS = 2 * math.pi * 0.25 - _LENS
# Two discs' perimeter less the arcs inside the other: each keeps 2 pi - 2 pi/3.
_TWO_DISCS_PERIMETER = 2 * (2 * math.pi - 2 * math.pi / 3) * 0.5
# `.union(box(2, 2, 4) at z = 4)` on the box: 16 more, its centroid at z = 4;
# its four sides add 32, its top and bottom cancel on the box's top.
_TOWER = (BOX_VOLUME + 16.0, BOX_AREA + 32.0, (0.0, 0.0, 64.0))
_T60 = math.tan(math.radians(30))

PARTS: dict[str, Part] = {
    "points-tuple": Part([through(2, 1, 0.5)]),
    "points-list": Part([through(2, 1, 0.5), through(-3, -2, 0.5)]),
    "points-several": Part([through(-3, -2, 0.5), through(3, 2, 0.5), through(3, -2, 0.5)]),
    # A third number is the point's offset along the plane's normal: from
    # z = 1 the bore starts inside the part, capped by a disc; from z = 5 it
    # reaches the face and goes through.
    "points-3-tuple-below": Part([Bore((2.0, 1.0, 1.0), DOWN, ((0.5, 0.5, 3.0),), opens=False)]),
    "points-3-tuple-above": Part([through(2, 1, 0.5)]),
    # An empty stack bores at the plane's origin, as `eachpoint` does.
    "points-empty": Part([through(0, 0, 0.5)]),
    "points-off-the-part": Part([]),
    # Local (1, 0.5) on `>X` is world (5, 1, 0.5): x along +y (`_computeXdir`), y along +z.
    "points-side>X": Part([Bore((5.0, 1.0, 0.5), (-1.0, 0.0, 0.0), ((0.5, 0.5, 10.0),))]),
    # On `<Y`, x is +x and y +z.
    "points-side<Y": Part([Bore((1.0, -4.0, 0.5), (0.0, 1.0, 0.0), ((0.5, 0.5, 8.0),))]),
    "points-duplicate": Part([through(2, 1, 0.5)]),
    "hole-depth-blind": Part([blind(2, 1, 0.5, 1.5)]),
    "hole-depth-blind-several": Part([blind(2, 1, 0.5, 1.5), blind(-3, -2, 0.5, 1.5)]),
    "hole-depth-to-the-bottom": Part([through(2, 1, 0.5)]),
    "hole-depth-past-the-part": Part([through(2, 1, 0.5)]),
    "hole-depth-no-points": Part([blind(0, 0, 0.5, 1.5)]),
    "cbore-one": Part([cbore(2, 1)]),
    "cbore-several": Part([cbore(-3, -2), cbore(3, 2)]),
    "cbore-no-points": Part([cbore(0, 0)]),
    # The counterbore deeper than the part swallows the bore.
    "cbore-past-the-part": Part([through(2, 1, 1.0)]),
    # A counterbore no wider than the bore is inside it: the bore alone.
    "cbore-narrower": Part([through(2, 1, 1.0)]),
    "cbore-equal": Part([through(2, 1, 0.5)]),
    "cbore-diameter-zero": Part([through(2, 1, 0.5)]),
    # A zero bore diameter leaves the counterbore alone.
    "cbore-hole-diameter-zero": Part([blind(2, 1, 1.0, 0.5)]),
    "csk-82-one": Part([csk(2, 1, 82)]),
    "csk-90-one": Part([csk(2, 1, 90)]),
    "csk-82-several": Part([csk(-3, -2, 82), csk(3, 2, 82), csk(0, 0, 82)]),
    "csk-no-points": Part([csk(0, 0, 90)]),
    # `cskHole(1, 6, 60)`: the cone (R = 3, h = 3 / tan 30) is still 3 - 4 tan 30
    # = 0.69 wide at the bottom, wider than the bore, which it holds whole.
    "csk-cone-past-the-part": Part([Bore(TOP, DOWN, ((3.0, 3.0 - 4 * _T60, 4.0),))]),
    # A countersink no wider than the bore is inside it.
    "csk-narrower": Part([through(2, 1, 1.0)]),
    "csk-equal": Part([through(2, 1, 0.5)]),
    # A zero bore diameter leaves the cone: R = 1, h = 1 at 90 degrees.
    "csk-hole-diameter-zero": Part(
        [Bore((2.0, 1.0, 2.0), DOWN, ((1.0, 0.0, 1.0),), through=False)]
    ),
    # `faces(sel)` on a stack of one face keeps that face, whatever the selector.
    "faces-faces-same": Part([through(0, 0, 0.5)]),
    "faces-faces-other": Part([through(0, 0, 0.5)]),
    # `faces(">X or <X")` keeps the box's two x faces (the tower's are inside);
    # `faces(">X")` on them keeps x = 5, the plane's origin (5, 0, 0).
    "faces-faces-of-two": Part(
        [Bore((5.0, 0.0, 0.0), (-1.0, 0.0, 0.0), ((0.5, 0.5, 10.0),))],
        volume0=_TOWER[0],
        area0=_TOWER[1],
        moment0=_TOWER[2],
    ),
}

# Built otherwise than by bores: (volume, area, centroid).
OTHER: dict[str, tuple[float, float, Point]] = {
    # Two holes whose discs overlap: their union through the part.
    "points-overlapping": (
        BOX_VOLUME - 4 * _TWO_DISCS,
        BOX_AREA - 2 * _TWO_DISCS + 4 * _TWO_DISCS_PERIMETER,
        (-4 * _TWO_DISCS * 0.25 / (BOX_VOLUME - 4 * _TWO_DISCS), 0.0, 0.0),
    ),
    # `circle` on each point, extruded 1 up and fused: two posts on the top.
    "points-circle-extrude": (
        BOX_VOLUME + 2 * math.pi * 0.25,
        BOX_AREA + 2 * math.pi * 1.0,
        (
            math.pi * 0.25 * (2 - 3) / (BOX_VOLUME + math.pi / 2),
            math.pi * 0.25 * (1 - 2) / (BOX_VOLUME + math.pi / 2),
            math.pi * 0.25 * 5 / (BOX_VOLUME + math.pi / 2),
        ),
    ),
}

# What CadQuery raises, its last line verbatim.
RAISES: dict[str, str] = {
    "points-one-number": (
        "UnboundLocalError: cannot access local variable 'fV'"
        " where it is not associated with a value"
    ),
    "points-bare-number": "TypeError: object of type 'int' has no len()",
    "hole-depth-zero": (
        "OCP.OCP.Standard.Standard_ConstructionError: gp_Vec::Normalize() - vector has zero norm"
    ),
    "hole-depth-negative": "OCP.OCP.Standard.Standard_ConstructionError",
    "cbore-depth-zero": (
        "OCP.OCP.Standard.Standard_ConstructionError: gp_Vec::Normalize() - vector has zero norm"
    ),
    "cbore-depth-negative": "ValueError: Null TopoDS_Shape object",
    "cbore-diameter-negative": "OCP.OCP.Standard.Standard_ConstructionError",
    "csk-angle-zero": "ZeroDivisionError: float division by zero",
    "csk-angle-180": "OCP.OCP.Standard.Standard_DomainError: cone with negative or null height",
    "csk-angle-negative": (
        "OCP.OCP.Standard.Standard_DomainError: cone with negative or null height"
    ),
    "csk-angle-minus-180": (
        "OCP.OCP.Standard.Standard_DomainError: cone with negative or null height"
    ),
    "csk-angle-360": "OCP.OCP.Standard.Standard_DomainError: cone with negative or null height",
    "csk-diameter-negative": (
        "OCP.OCP.Standard.Standard_DomainError: cone with negative or too small radius"
    ),
    "csk-diameter-zero": "OCP.OCP.Standard.Standard_DomainError: cone with two identic radii",
}


def constructed() -> dict[str, dict[str, Any]]:
    data = json.loads(HOLES.read_text(encoding="utf-8"))
    return {c["name"]: c for c in data}


def report(name: str) -> OracleReport:
    return OracleReport.model_validate(constructed()[name]["report"])


def test_every_construction_is_recorded_and_held() -> None:
    records = constructed()
    assert list(records) == sorted(probe.CONSTRUCTED)
    assert {n: c["program"] for n, c in records.items()} == probe.constructed_programs()
    assert sorted([*PARTS, *OTHER, *RAISES]) == sorted(records)


def _held(got: OracleReport, want: tuple[float, float, Point]) -> None:
    assert got.status is OracleStatus.OK, got.message
    assert got.measures is not None
    assert got.measures.solids == 1
    pairs = [(got.measures.volume, want[0]), (got.measures.area, want[1])]
    pairs += list(zip(got.measures.centroid, want[2], strict=True))
    assert all(fixture_cases.close(g, w) for g, w in pairs), pairs


@pytest.mark.parametrize("name", sorted(PARTS))
def test_the_oracle_bores_the_closed_form(name: str) -> None:
    _held(report(name), PARTS[name].measures())


@pytest.mark.parametrize("name", sorted(OTHER))
def test_the_oracle_builds_the_closed_form(name: str) -> None:
    _held(report(name), OTHER[name])


@pytest.mark.parametrize("name", sorted(RAISES))
def test_the_oracle_raises_in_its_own_words(name: str) -> None:
    got = report(name)
    assert got.status is OracleStatus.RUNTIME
    assert got.message.splitlines()[-1] == RAISES[name]


# ADR-0018's tools in arris: each piece of CadQuery's union its own tool, all
# cut in one call. A cylinder is `Solid.cylinder`; arris has no cone, so a cone
# is a right triangle on a plane through its axis, (radius, height above the
# top), revolved a full turn.
Piece = tuple[str, Point, float, float]  # kind, top, radius at the top, length


def _piece(piece: Piece, axis: Point, model: arris.Model) -> arris.build.Solid:
    kind, at, r, h = piece
    if kind == "cylinder":
        return arris.build.Solid.cylinder(at, axis, r, h, model=model)
    up = (-axis[0], -axis[1], -axis[2])
    # Any x across the axis: the solid of revolution does not depend on it.
    x = (1.0, 0.0, 0.0) if abs(axis[0]) < 0.5 else (0.0, 1.0, 0.0)
    normal = (
        x[1] * up[2] - x[2] * up[1],
        x[2] * up[0] - x[0] * up[2],
        x[0] * up[1] - x[1] * up[0],
    )
    meridian = arris.build.Workplane.of(at, normal, x)
    loop = arris.Loop.polygon([(0.0, 0.0), (r, 0.0), (0.0, -h)])
    return arris.build.Sketch(meridian, loop).revolve("y", TURN, model=model)


def _cbore(x: float, y: float) -> list[Piece]:
    """`cboreHole(1, 2, 0.5)`'s pieces at (x, y)."""
    return [("cylinder", (x, y, 2), 0.5, DIAGONAL), ("cylinder", (x, y, 2), 1.0, 0.5)]


def _csk(x: float, y: float, cd: float, angle: float) -> list[Piece]:
    """`cskHole(1, cd, angle)`'s pieces at (x, y): the bore and the cone."""
    h = cd / 2 / math.tan(math.radians(angle / 2))
    return [("cylinder", (x, y, 2), 0.5, DIAGONAL), ("cone", (x, y, 2), cd / 2, h)]


# Each construction's pieces as `cq` builds them, with the axis they run along;
# keyed by the construction whose closed form the cut must give.
SPIKES: dict[str, tuple[Point, list[Piece]]] = {
    "cbore-one": (DOWN, _cbore(2, 1)),
    "cbore-several": (DOWN, _cbore(-3, -2) + _cbore(3, 2)),
    # Equal radii: the two cylinders' walls coincide.
    "cbore-equal": (
        DOWN,
        [("cylinder", (2, 1, 2), 0.5, DIAGONAL), ("cylinder", (2, 1, 2), 0.5, 0.5)],
    ),
    "cbore-narrower": (
        DOWN,
        [("cylinder", (2, 1, 2), 1.0, DIAGONAL), ("cylinder", (2, 1, 2), 0.5, 0.5)],
    ),
    "cbore-past-the-part": (
        DOWN,
        [("cylinder", (2, 1, 2), 0.5, DIAGONAL), ("cylinder", (2, 1, 2), 1.0, 5.0)],
    ),
    "csk-82-one": (DOWN, _csk(2, 1, 2, 82)),
    "csk-90-one": (DOWN, _csk(2, 1, 2, 90)),
    "csk-82-several": (DOWN, _csk(-3, -2, 2, 82) + _csk(3, 2, 2, 82) + _csk(0, 0, 2, 82)),
    # The cone's edge meets the bore's at the top.
    "csk-equal": (DOWN, _csk(2, 1, 1, 90)),
    # The cone's tip past the part's far face.
    "csk-cone-past-the-part": (DOWN, _csk(0, 0, 6, 60)),
    # A zero bore diameter: the cone alone.
    "csk-hole-diameter-zero": (DOWN, [("cone", (2, 1, 2), 1.0, 1.0)]),
    # From a side face, the axis along -x.
    "points-side>X": ((-1.0, 0.0, 0.0), [("cylinder", (5, 1, 0.5), 0.5, DIAGONAL)]),
}


@pytest.mark.parametrize("name", sorted(SPIKES))
def test_arris_cuts_cadquerys_pieces_to_the_closed_form(name: str) -> None:
    axis, pieces = SPIKES[name]
    model = arris.Model()
    box = arris.build.Solid.box((-5, -4, -2), (5, 4, 2), model=model)
    cut = box.cut(*(_piece(p, axis, model) for p in pieces))
    assert cut.check().ok
    got = cut.measure()
    v, a, c = PARTS[name].measures()
    pairs = [(got.volume, v), (got.area, a), *zip(got.centroid, c, strict=True)]
    assert all(fixture_cases.close(g, w) for g, w in pairs), pairs

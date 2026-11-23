"""ADR-0020's evidence: what CadQuery's `edges`, `fillet` and `chamfer` select and build, and arris.

The oracle's records come from `tools/cq_edge_probe.py` (outside the gate) and
are committed in `tests/fixtures/edges/constructed.json`; these tests read that
file offline and hold each record to the closed form of how its part is built.
The rest build the same parts in arris: the blends (the kernel risk of
`fillet` and `chamfer`, read before `cq` lifts them), held to the same closed
forms, the values arris refuses, and ADR-0020's edge key, held to the
oracle's selections, to a quadrature and to the edges' own tessellation.
"""

from __future__ import annotations

import itertools
import json
import math
import struct
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import arris
import arris.build
import pytest

import cq_edge_probe as probe
import fixture_cases
from arris_gym.cq._selector import CQ_TOLERANCE
from arris_gym.fidelity import OracleReport, OracleStatus

EDGES = Path(__file__).parent / "fixtures" / "edges" / "constructed.json"
Point = tuple[float, float, float]
Measures = tuple[float, float, Point]
# Open CASCADE's centre of mass of an edge is a Gauss sum: on a line, circle
# or arc it sits within 1e-15 of the closed form. On the tilted cut's ellipse
# it is 1e-6 off in x (read below), so that edge is held to this wider bound,
# which is still a hundredth of CadQuery's selector tolerance.
ROUNDING = 1e-12
ELLIPSE_ROUNDING = 1e-5
# Open CASCADE's crossing curves are B-splines fitted to the true
# intersection: their centres sit up to 1.1e-9 off the quadrature's.
SPLINE_ROUNDING = 1e-8
# ADR-0017's chord and margin, as fractions of the solid's box diagonal.
CHORD = 1e-5
MARGIN = 1e-4
# What arris's B-spline polylines miss the quadrature's centre by, at most,
# as a fraction of the diagonal: measured 4e-9 on the crossing cylinders.
ESTIMATE_ERROR = 1e-8


def constructed() -> dict[str, dict[str, Any]]:
    data = json.loads(EDGES.read_text(encoding="utf-8"))
    return {c["name"]: c for c in data}


def record(name: str) -> dict[str, Any]:
    entry = constructed()[name]
    assert entry["status"] == "record", entry["message"]
    out: dict[str, Any] = entry["record"]
    return out


def report(name: str) -> OracleReport:
    return OracleReport.model_validate(constructed()[name]["report"])


# --- The selections -------------------------------------------------------

# The box's twelve edges by their midpoints: 10 by 8 by 4 about the origin.
_BOX_EDGES = [
    *((x, y, 0.0) for x in (-5.0, 5.0) for y in (-4.0, 4.0)),
    *((x, 0.0, z) for x in (-5.0, 5.0) for z in (-2.0, 2.0)),
    *((0.0, y, z) for y in (-4.0, 4.0) for z in (-2.0, 2.0)),
]
_AXIS = {"X": 0, "Y": 1, "Z": 2}


def _box_extreme(sel: str) -> list[Point]:
    k = _AXIS[sel[1]]
    end = max(p[k] for p in _BOX_EDGES) if sel[0] == ">" else min(p[k] for p in _BOX_EDGES)
    return [p for p in _BOX_EDGES if p[k] == end]


def _box_parallel(sel: str) -> list[Point]:
    # An edge along k has its midpoint at 0 in k, and only it does.
    k = _AXIS[sel[1]]
    return [p for p in _BOX_EDGES if p[k] == 0.0]


def lines(points: Sequence[Point]) -> list[tuple[str, Point]]:
    return [("LINE", p) for p in points]


def arc_centre(radius: float, start: float, sweep: float) -> tuple[float, float]:
    """The centre of mass of an arc about the origin, from angle `start` through `sweep`:
    `r sin(θ/2) / (θ/2)` along the bisector."""
    d = radius * math.sin(sweep / 2) / (sweep / 2)
    mid = start + sweep / 2
    return (d * math.cos(mid), d * math.sin(mid))


_D_ARC = arc_centre(1.0, 0.0, math.pi)
_PAC_ARC = arc_centre(1.0, 0.0, 1.5 * math.pi)
# The rounded box's corner at (3, 2): a quarter arc of radius 2 from 0 to 90 degrees.
_CORNER = arc_centre(2.0, 0.0, math.pi / 2)
_ROUNDED_ARCS = [
    ("CIRCLE", (sx * (3.0 + _CORNER[0]), sy * (2.0 + _CORNER[1]), 2.0))
    for sx in (-1.0, 1.0)
    for sy in (-1.0, 1.0)
]
# The tilted plane meets the axis 1/cos 30 below (0, 0, 2): the ellipse's centre.
_TILT_Z = 2.0 - 1.0 / math.cos(math.radians(30.0))

# Each selection: the number of candidate edges and the kept edges' types and
# centres of mass, by construction.
SELECTED: dict[str, tuple[int, list[tuple[str, Point]]]] = {
    "box-edges": (12, lines(_BOX_EDGES)),
    **{f"box-edges{s}": (12, lines(_box_extreme(s))) for s in (">X", "<X", ">Y", "<Y")},
    **{f"box-edges{s}": (12, lines(_box_extreme(s))) for s in (">Z", "<Z")},
    **{f"box-edges{s}": (12, lines(_box_parallel(s))) for s in ("|X", "|Y", "|Z")},
    "box-edges>Z or <Z": (12, lines(_box_extreme(">Z") + _box_extreme("<Z"))),
    # A face's own edges are the candidates.
    "box-faces>Z-edges": (4, lines(_box_extreme(">Z"))),
    "box-faces>Z-edges>X": (4, lines([(5.0, 0.0, 2.0)])),
    "box-faces>X-edges|Z": (4, lines([(5.0, -4.0, 0.0), (5.0, 4.0, 0.0)])),
    # The cylinder: two rims and a seam line at +x.
    "cylinder-edges": (
        3,
        [("CIRCLE", (0.0, 0.0, 2.0)), ("CIRCLE", (0.0, 0.0, -2.0)), ("LINE", (1.0, 0.0, 0.0))],
    ),
    "cylinder-edges>Z": (3, [("CIRCLE", (0.0, 0.0, 2.0))]),
    "cylinder-edges<Z": (3, [("CIRCLE", (0.0, 0.0, -2.0))]),
    # The seam is the edge furthest along x.
    "cylinder-edges>X": (3, [("LINE", (1.0, 0.0, 0.0))]),
    # All three lie at y = 0, one cluster.
    "cylinder-edges>Y": (
        3,
        [("CIRCLE", (0.0, 0.0, 2.0)), ("CIRCLE", (0.0, 0.0, -2.0)), ("LINE", (1.0, 0.0, 0.0))],
    ),
    "cylinder-edges|Z": (3, [("LINE", (1.0, 0.0, 0.0))]),
    # No line along x: nothing kept.
    "cylinder-edges|X": (3, []),
    "cylinder-edges>Z or <Z": (3, [("CIRCLE", (0.0, 0.0, 2.0)), ("CIRCLE", (0.0, 0.0, -2.0))]),
    "cylinder-faces>Z-edges": (1, [("CIRCLE", (0.0, 0.0, 2.0))]),
    # The D's half circles, 2/π from the chord.
    "d-edges>Y": (6, [("CIRCLE", (*_D_ARC, 0.0)), ("CIRCLE", (*_D_ARC, 1.0))]),
    "d-edges<Y": (
        6,
        lines([(0.0, 0.0, 0.0), (0.0, 0.0, 1.0), (-1.0, 0.0, 0.5), (1.0, 0.0, 0.5)]),
    ),
    # Three quarters of a circle: its centre of mass at 135 degrees, inside
    # every other edge's key along -x and +y.
    "pac-edges<X": (9, [("CIRCLE", (*_PAC_ARC, 0.0)), ("CIRCLE", (*_PAC_ARC, 1.0))]),
    "pac-edges>Y": (9, [("CIRCLE", (*_PAC_ARC, 0.0)), ("CIRCLE", (*_PAC_ARC, 1.0))]),
    "tilt-edges>Z": (3, [("ELLIPSE", (0.0, 0.0, _TILT_Z))]),
    "cross-edges>X": (12, [("CIRCLE", (5.0, 0.0, 0.0))]),
    # Open CASCADE puts the hole's seam at -x (arris puts it at +x, below).
    "plate-edges|Z": (
        15,
        lines([(x, y, 0.0) for x in (-5.0, 5.0) for y in (-4.0, 4.0)] + [(-1.5, 0.0, 0.0)]),
    ),
    "plate-faces>Z-edges": (
        5,
        [
            *lines([(-5.0, 0.0, 1.0), (5.0, 0.0, 1.0), (0.0, -4.0, 1.0), (0.0, 4.0, 1.0)]),
            ("CIRCLE", (0.0, 0.0, 1.0)),
        ],
    ),
    # The rounded box's top: four lines and four quarter arcs, one cluster.
    "rounded-edges>Z": (
        24,
        lines([(-5.0, 0.0, 2.0), (5.0, 0.0, 2.0), (0.0, -4.0, 2.0), (0.0, 4.0, 2.0)])
        + _ROUNDED_ARCS,
    ),
    # CadQuery's seams (ADR-0020 rule 2, amended): a cylinder's, and a circle's
    # swept by `extrude` or `cutBlind`, lies on its workplane's +x; a bore's on
    # its -x. "YZ" has x along +y, "XZ" along +x, "ZX" along +z; `workplane()` on
    # a face of normal n takes x along z x n (+y on ">X", +x on "<Y").
    "seam-yz-cylinder": (3, lines([(0.0, 2.0, 0.0)])),
    "seam-xz-cylinder": (3, lines([(2.0, 0.0, 0.0)])),
    "seam-zx-cylinder": (3, lines([(0.0, 0.0, 2.0)])),
    # The plane turned 30 degrees about z: its x, and the seam, turn with it.
    "seam-turned-cylinder": (
        3,
        lines([(math.cos(math.radians(30.0)), math.sin(math.radians(30.0)), 0.0)]),
    ),
    # Four rims and two seams: the wall's on the plane's +x, the bore's on -x of
    # the face's plane.
    "seam-yz-washer": (6, lines([(0.0, 5.0, 0.0), (0.0, -1.5, 0.0)])),
    "seam-xz-washer": (6, lines([(5.0, 0.0, 0.0), (-1.5, 0.0, 0.0)])),
    # The disc swept from y = 0 to -1 along "XZ"'s normal.
    "seam-xz-ring": (6, lines([(5.0, -0.5, 0.0), (-1.5, -0.5, 0.0)])),
    # Six rims and three seams: the wall's, the bore's (radius 1, from x = -1 to
    # 0.5) and the counterbore's (radius 2, from x = 0.5 to 1).
    "seam-yz-cbore": (9, lines([(0.0, 5.0, 0.0), (-0.25, -1.0, 0.0), (0.75, -2.0, 0.0)])),
    # A pocket of radius 1.5 from x = 0 to 1: a circle swept, its seam on +x (+y).
    "seam-yz-cut-blind": (6, lines([(0.0, 5.0, 0.0), (0.5, 1.5, 0.0)])),
    # Bores of radius 0.5 at the plane's (2, 0) and (-2, 1): world (2, ., 0) and
    # (-2, ., 1), its y being +z; each seam 0.5 towards -x.
    "seam-xz-points": (9, lines([(5.0, 0.0, 0.0), (1.5, 0.0, 0.0), (-2.5, 0.0, 1.0)])),
}


def _same_edges(
    got: Sequence[tuple[str, Sequence[float]]],
    want: Sequence[tuple[str, Point]],
    bound: float = ROUNDING,
) -> bool:
    """Whether two lists hold the same (type, centre) pairs, each matched once."""
    left = list(want)
    for kind, centre in got:
        for i, (k, c) in enumerate(left):
            if k == kind and all(abs(a - b) <= bound for a, b in zip(centre, c, strict=True)):
                del left[i]
                break
        else:
            return False
    return not left


def test_every_construction_is_recorded_and_held() -> None:
    records = constructed()
    programs = probe.constructed_programs()
    assert list(records) == list(programs)
    assert {n: (c["kind"], c["program"]) for n, c in records.items()} == programs
    held = sorted([*SELECTED, *PARTS, *RAISES, *UNCLEAN])
    assert held == sorted(records)


@pytest.mark.parametrize("name", sorted(SELECTED))
def test_the_oracle_keeps_the_edges_of_the_closed_form(name: str) -> None:
    got = record(name)
    count, want = SELECTED[name]
    assert len(got["candidates"]) == count
    kept = [(got["candidates"][i]["type"], got["candidates"][i]["centre"]) for i in got["kept"]]
    bound = ELLIPSE_ROUNDING if name == "tilt-edges>Z" else ROUNDING
    assert _same_edges(kept, want, bound), kept


def test_a_line_edges_key_is_its_midpoint() -> None:
    """CadQuery's centre of mass of every line candidate is its midpoint."""
    for name in sorted(SELECTED):
        for c in record(name)["candidates"]:
            if c["type"] == "LINE":
                mid = [(a + b) / 2 for a, b in zip(c["start"], c["end"], strict=True)]
                assert all(abs(a - b) <= ROUNDING for a, b in zip(c["centre"], mid, strict=True))


def test_open_cascade_centres_the_ellipse_a_millionth_off() -> None:
    """The full ellipse's centre of mass is its centre by symmetry; Open CASCADE's
    Gauss sum puts it about 1e-6 off along x, within `ELLIPSE_ROUNDING`."""
    (ellipse,) = [c for c in record("tilt-edges>Z")["candidates"] if c["type"] == "ELLIPSE"]
    off = abs(ellipse["centre"][0])
    assert ROUNDING < off < ELLIPSE_ROUNDING
    assert abs(ellipse["centre"][2] - _TILT_Z) < ELLIPSE_ROUNDING


def _cross_centre_x() -> float:
    """The centre of mass along x of a curve where x² + y² = 4 meets y² + z² = 1.

    On (x, y, z) = (√(4 - sin² t), sin t, cos t) the curve is smooth and
    periodic in t, so the trapezoid rule converges geometrically: 4,000 steps
    are exact to the last bits that matter here. Every half or quarter of it
    cut at y = 0 or z = 0 has the same centre along x, by symmetry.
    """
    steps = 4000
    num = den = 0.0
    for i in range(steps):
        t = 2 * math.pi * i / steps
        s = math.sin(t)
        x = math.sqrt(4 - s * s)
        ds = math.sqrt((s * math.cos(t) / x) ** 2 + 1.0)
        num += x * ds
        den += ds
    return num / den


def test_open_cascade_cuts_the_crossing_curves_in_its_own_pieces() -> None:
    """The cylinders meet in two closed B-spline curves: Open CASCADE cuts the one
    at +x in three (a half and two quarters) and keeps the one at -x whole."""
    got = record("cross-edges>X")["candidates"]
    splines = [c for c in got if c["type"] == "BSPLINE"]
    xbar = _cross_centre_x()
    assert all(abs(abs(c["centre"][0]) - xbar) < SPLINE_ROUNDING for c in splines)
    halves = sorted(c["length"] for c in splines if c["centre"][0] > 0)
    assert len(halves) == 3
    assert abs(halves[0] + halves[1] - halves[2]) < SPLINE_ROUNDING
    assert len([c for c in splines if c["centre"][0] < 0]) == 1


# --- The blends -----------------------------------------------------------


@dataclass(frozen=True)
class Section:
    """What a blend takes off along an edge, in the edge's own section.

    `u` is the inset from the wall, `w` the depth from the face the edge
    bounds, both inside the material: `area`, `su` = ∫u, `sw` = ∫w and
    `suw` = ∫uw over the section; `curve` and `curve_u` are the length of the
    blend's profile and ∫u along it; `width` is how far the blend reaches on
    each face.
    """

    area: float
    su: float
    sw: float
    suw: float
    curve: float
    curve_u: float
    width: float


def spandrel(r: float) -> Section:
    """A fillet of radius `r` at a right-angled edge: the square less the quarter disc."""
    a = r * r * (1 - math.pi / 4)
    s = r**3 * (5 / 6 - math.pi / 4)
    return Section(
        a, s, s, r**4 * (19 / 24 - math.pi / 4), math.pi * r / 2, r * r * (math.pi / 2 - 1), r
    )


def triangle(d: float) -> Section:
    """A chamfer of length `d` at a right-angled edge."""
    root2 = math.sqrt(2.0)
    return Section(d * d / 2, d**3 / 6, d**3 / 6, d**4 / 24, root2 * d, root2 * d * d / 2, d)


@dataclass(frozen=True)
class Rim:
    """A closed run of edges where a horizontal face at height `z` meets a vertical wall.

    The run's length at inset `u` into the face is `length - shrink * u`:
    a box's rectangle with mitred corners (`2(a + b)`, 8), a rounded
    rectangle (its perimeter, 2π), a disc's rim (2πR, 2π) or a hole's
    (2πr, -2π). `side` is -1 where the material lies below the face, +1 above.
    """

    length: float
    shrink: float
    z: float
    side: float


@dataclass(frozen=True)
class Part:
    """A closed form: a base solid's volume, area and moment, less its blends.

    `rims` blend runs of edges; `vertical` blends `count` straight edges of
    length `height` between two walls, each section's centroid symmetric
    about the part's.
    """

    volume: float
    area: float
    centroid: Point
    section: Section | None = None
    rims: Sequence[Rim] = ()
    vertical: tuple[int, float] = (0, 0.0)

    def measures(self) -> Measures:
        v, a = self.volume, self.area
        mz = v * self.centroid[2]
        s = self.section
        if s is not None:
            for rim in self.rims:
                removed = rim.length * s.area - rim.shrink * s.su
                v -= removed
                mz -= rim.z * removed + rim.side * (rim.length * s.sw - rim.shrink * s.suw)
                a += rim.length * s.curve - rim.shrink * s.curve_u
                a -= rim.length * s.width - rim.shrink * s.width**2 / 2
                a -= rim.length * s.width
            count, height = self.vertical
            v -= count * height * s.area
            mz -= count * height * s.area * self.centroid[2]
            a += count * height * (s.curve - 2 * s.width) - 2 * count * s.area
        return v, a, (self.centroid[0], self.centroid[1], mz / v)


def rounded_box(a: float, b: float, c: float, r: float) -> Measures:
    """A box with all its edges filleted at `r`: the inner box grown by a ball (Steiner)."""
    x, y, z = a - 2 * r, b - 2 * r, c - 2 * r
    v = x * y * z + 2 * r * (x * y + y * z + x * z) + math.pi * r * r * (x + y + z)
    v += 4 / 3 * math.pi * r**3
    area = 2 * (x * y + y * z + x * z) + 2 * math.pi * r * (x + y + z) + 4 * math.pi * r * r
    return v, area, (0.0, 0.0, 0.0)


ORIGIN = (0.0, 0.0, 0.0)
# The box, 10 by 8 by 4 about the origin; its top and bottom rims.
BOX = (320.0, 304.0, ORIGIN)
BOX_TOP = Rim(36.0, 8.0, 2.0, -1.0)
BOX_BOTTOM = Rim(36.0, 8.0, -2.0, 1.0)
# The cylinder of radius 2 from z = -2 to 2, and its rims.
CYL = (16 * math.pi, 24 * math.pi, ORIGIN)
CYL_TOP = Rim(4 * math.pi, 2 * math.pi, 2.0, -1.0)
CYL_BOTTOM = Rim(4 * math.pi, 2 * math.pi, -2.0, 1.0)
# The tube, radii 3 and 1.5, from z = 0 to 2; its top rims, outer and inner.
TUBE = (13.5 * math.pi, 31.5 * math.pi, (0.0, 0.0, 1.0))
TUBE_TOP = (Rim(6 * math.pi, 2 * math.pi, 2.0, -1.0), Rim(3 * math.pi, -2 * math.pi, 2.0, -1.0))
# The plate, 10 by 8 by 2 with a hole of radius 1.5; its top rims.
PLATE = (160 - 4.5 * math.pi, 232 + 1.5 * math.pi, ORIGIN)
PLATE_TOP = (Rim(36.0, 8.0, 1.0, -1.0), Rim(3 * math.pi, -2 * math.pi, 1.0, -1.0))
# The box with its four vertical edges filleted at 2, and its top rim, a
# rectangle with corners of radius 2.
ROUNDED = Part(*BOX, section=spandrel(2.0), vertical=(4, 4.0)).measures()
ROUNDED_TOP = Rim(2 * 6.0 + 2 * 4.0 + 4 * math.pi, 2 * math.pi, 2.0, -1.0)
# One 2 by 2 by 2 box of the pair, about its own centre.
CUBE = (8.0, 24.0, ORIGIN)


def pair(section: Section) -> Measures:
    """The two cubes 5 apart, each with its four vertical edges blended."""
    v, a, _ = Part(*CUBE, section=section, vertical=(4, 2.0)).measures()
    return 2 * v, 2 * a, (2.5, 0.0, 0.0)


PARTS: dict[str, Measures] = {
    "fillet-box>Z": Part(*BOX, section=spandrel(1.0), rims=(BOX_TOP,)).measures(),
    "fillet-box-faces>Z": Part(*BOX, section=spandrel(1.0), rims=(BOX_TOP,)).measures(),
    "fillet-box>Z or <Z": Part(*BOX, section=spandrel(1.0), rims=(BOX_TOP, BOX_BOTTOM)).measures(),
    "fillet-box|Z": Part(*BOX, section=spandrel(1.0), vertical=(4, 4.0)).measures(),
    "fillet-box-edges": rounded_box(10, 8, 4, 1),
    "fillet-box-solid": rounded_box(10, 8, 4, 1),
    "fillet-cylinder>Z": Part(*CYL, section=spandrel(0.5), rims=(CYL_TOP,)).measures(),
    # The seam is passed over: both rims.
    "fillet-cylinder-edges": Part(
        *CYL, section=spandrel(0.5), rims=(CYL_TOP, CYL_BOTTOM)
    ).measures(),
    "fillet-tube>Z": Part(*TUBE, section=spandrel(0.5), rims=TUBE_TOP).measures(),
    "fillet-plate-faces>Z": Part(*PLATE, section=spandrel(0.5), rims=PLATE_TOP).measures(),
    "fillet-rounded>Z": Part(*ROUNDED, section=spandrel(0.5), rims=(ROUNDED_TOP,)).measures(),
    "fillet-compound|Z": pair(spandrel(0.5)),
    "chamfer-box>Z": Part(*BOX, section=triangle(1.0), rims=(BOX_TOP,)).measures(),
    "chamfer-box|Z": Part(*BOX, section=triangle(1.0), vertical=(4, 4.0)).measures(),
    "chamfer-cylinder>Z": Part(*CYL, section=triangle(0.5), rims=(CYL_TOP,)).measures(),
    "chamfer-cylinder>Z or <Z": Part(
        *CYL, section=triangle(0.5), rims=(CYL_TOP, CYL_BOTTOM)
    ).measures(),
    "chamfer-cylinder-edges": Part(
        *CYL, section=triangle(0.5), rims=(CYL_TOP, CYL_BOTTOM)
    ).measures(),
    "chamfer-tube>Z": Part(*TUBE, section=triangle(0.5), rims=TUBE_TOP).measures(),
    "chamfer-plate-faces>Z": Part(*PLATE, section=triangle(0.5), rims=PLATE_TOP).measures(),
    "chamfer-rounded>Z": Part(*ROUNDED, section=triangle(0.5), rims=(ROUNDED_TOP,)).measures(),
    "chamfer-compound|Z": pair(triangle(0.5)),
}

# What CadQuery raises, its last line verbatim.
_NOT_DONE = "OCP.OCP.StdFail.StdFail_NotDone: BRep_API: command not done"
_NO_SUITABLE = (
    "OCP.OCP.Standard.Standard_Failure: There are no suitable edges for chamfer or fillet"
)
_NO_SOLID = "ValueError: Cannot find a solid on the stack or in the parent chain"
RAISES: dict[str, str] = {
    "fillet-box|Z-zero": _NOT_DONE,
    "fillet-box|Z-negative": _NOT_DONE,
    # Past half the box's width of 8, and past its height of 4.
    "fillet-box|Z-past": _NOT_DONE,
    "fillet-box>Z-past": _NOT_DONE,
    "chamfer-box|Z-zero": _NOT_DONE,
    "chamfer-box|Z-negative": _NOT_DONE,
    "chamfer-box|Z-past": _NOT_DONE,
    # The seam alone.
    "fillet-cylinder|Z": _NO_SUITABLE,
    "chamfer-cylinder|Z": _NO_SUITABLE,
    "fillet-cylinder-empty": "ValueError: Fillets requires that edges be selected",
    "chamfer-cylinder-empty": "ValueError: Chamfer requires that edges be selected",
    "fillet-no-solid": _NO_SOLID,
    "chamfer-no-solid": _NO_SOLID,
}

# `Solid.fillet` with no `clean()`, beside the `Workplane.fillet` it is.
UNCLEAN: dict[str, str] = {
    "unclean-fillet-box|Z": "fillet-box|Z",
    "unclean-fillet-box-edges": "fillet-box-edges",
    "unclean-fillet-cylinder-edges": "fillet-cylinder-edges",
    "unclean-fillet-rounded>Z": "fillet-rounded>Z",
}


def _held(got: Measures, want: Measures) -> None:
    pairs = [(got[0], want[0]), (got[1], want[1]), *zip(got[2], want[2], strict=True)]
    assert all(fixture_cases.close(g, w) for g, w in pairs), pairs


def _oracle(name: str) -> Measures:
    got = report(name)
    assert got.status is OracleStatus.OK, got.message
    assert got.measures is not None
    c = got.measures.centroid
    return got.measures.volume, got.measures.area, (c[0], c[1], c[2])


@pytest.mark.parametrize("name", sorted(PARTS))
def test_the_oracle_blends_to_the_closed_form(name: str) -> None:
    _held(_oracle(name), PARTS[name])


def test_the_compounds_stay_two_solids() -> None:
    for name in ("fillet-compound|Z", "chamfer-compound|Z"):
        measures = report(name).measures
        assert measures is not None
        assert measures.solids == 2


@pytest.mark.parametrize("name", sorted(RAISES))
def test_the_oracle_raises_in_its_own_words(name: str) -> None:
    got = report(name)
    assert got.status is OracleStatus.RUNTIME
    assert got.message.splitlines()[-1] == RAISES[name]


@pytest.mark.parametrize("name", sorted(UNCLEAN))
def test_cleaning_a_fillet_moves_no_measure(name: str) -> None:
    """CadQuery's `clean()` after `fillet` leaves the volume, area, centroid and
    face count bit for bit as `Solid.fillet` built them, here."""
    bare, cleaned = report(name).measures, report(UNCLEAN[name]).measures
    assert bare is not None
    assert cleaned is not None
    assert (bare.volume, bare.area, bare.centroid, bare.faces) == (
        cleaned.volume,
        cleaned.area,
        cleaned.centroid,
        cleaned.faces,
    )


# --- The same parts in arris ----------------------------------------------

Build = Callable[[arris.Model], arris.build.Solid]
Pick = Callable[[arris.Model, arris.build.Solid], list[arris.Edge]]


def _box(model: arris.Model) -> arris.build.Solid:
    return arris.build.Solid.box((-5, -4, -2), (5, 4, 2), model=model)


def _cylinder(radius: float) -> Build:
    def build(model: arris.Model) -> arris.build.Solid:
        return arris.build.Solid.cylinder((0, 0, -2), (0, 0, 1), radius, 4, model=model)

    return build


def _tube(model: arris.Model) -> arris.build.Solid:
    plane = arris.build.Workplane.XY()
    ring = arris.build.Sketch(plane, plane.circle(3).outer, (plane.circle(1.5).outer,))
    return ring.extrude(2, model=model)


def _plate(model: arris.Model) -> arris.build.Solid:
    plate = arris.build.Solid.box((-5, -4, -1), (5, 4, 1), model=model)
    return plate.cut(arris.build.Solid.cylinder((0, 0, -1), (0, 0, 1), 1.5, 2, model=model))


def _rounded(model: arris.Model) -> arris.build.Solid:
    box = _box(model)
    return box.fillet(_vertical(model, box), 2.0)


def _pair(model: arris.Model) -> arris.build.Solid:
    one = arris.build.Solid.box((-1, -1, -1), (1, 1, 1), model=model)
    return one.fuse(arris.build.Solid.box((4, -1, -1), (6, 1, 1), model=model))


def _at(z: float) -> Pick:
    """The edges lying wholly at height `z`."""

    def pick(model: arris.Model, solid: arris.build.Solid) -> list[arris.Edge]:
        out = []
        for e in model.edges(solid.body):
            c = model.curve(e)
            if abs(c.start[2] - z) < ROUNDING and abs(c.end[2] - z) < ROUNDING:
                out.append(e)
        return out

    return pick


def _vertical(model: arris.Model, solid: arris.build.Solid) -> list[arris.Edge]:
    """The line edges along z that are not a seam."""
    out = []
    for e in model.edges(solid.body):
        c = model.curve(e)
        along = abs(c.start[0] - c.end[0]) < ROUNDING and abs(c.start[1] - c.end[1]) < ROUNDING
        if c.kind == "line" and along and not _seam(model, solid, e):
            out.append(e)
    return out


def _seam(model: arris.Model, solid: arris.build.Solid, edge: arris.Edge) -> bool:
    """An edge with one face on both sides."""
    return len(model.faces_of(solid.body, edge)) == 1


def _all_but_seams(model: arris.Model, solid: arris.build.Solid) -> list[arris.Edge]:
    return [e for e in model.edges(solid.body) if not _seam(model, solid, e)]


def _both(*picks: Pick) -> Pick:
    def pick(model: arris.Model, solid: arris.build.Solid) -> list[arris.Edge]:
        return [e for p in picks for e in p(model, solid)]

    return pick


# Keyed by the construction whose closed form the blend must give: the base,
# the edges (a seam dropped, ADR-0020 rule 4), fillet or chamfer, and its value.
SPIKES: dict[str, tuple[Build, Pick, str, float]] = {
    "fillet-box>Z": (_box, _at(2.0), "fillet", 1.0),
    "fillet-box>Z or <Z": (_box, _both(_at(2.0), _at(-2.0)), "fillet", 1.0),
    "fillet-box|Z": (_box, _vertical, "fillet", 1.0),
    "fillet-box-edges": (_box, _all_but_seams, "fillet", 1.0),
    "fillet-cylinder>Z": (_cylinder(2.0), _at(2.0), "fillet", 0.5),
    "fillet-cylinder-edges": (_cylinder(2.0), _all_but_seams, "fillet", 0.5),
    "fillet-tube>Z": (_tube, _at(2.0), "fillet", 0.5),
    "fillet-plate-faces>Z": (_plate, _at(1.0), "fillet", 0.5),
    "fillet-rounded>Z": (_rounded, _at(2.0), "fillet", 0.5),
    "fillet-compound|Z": (_pair, _vertical, "fillet", 0.5),
    "chamfer-box>Z": (_box, _at(2.0), "chamfer", 1.0),
    "chamfer-box|Z": (_box, _vertical, "chamfer", 1.0),
    "chamfer-cylinder>Z": (_cylinder(2.0), _at(2.0), "chamfer", 0.5),
    "chamfer-cylinder-edges": (_cylinder(2.0), _all_but_seams, "chamfer", 0.5),
    "chamfer-tube>Z": (_tube, _at(2.0), "chamfer", 0.5),
    "chamfer-plate-faces>Z": (_plate, _at(1.0), "chamfer", 0.5),
    "chamfer-rounded>Z": (_rounded, _at(2.0), "chamfer", 0.5),
    "chamfer-compound|Z": (_pair, _vertical, "chamfer", 0.5),
}


def _blend(name: str) -> arris.build.Solid:
    build, pick, op, value = SPIKES[name]
    model = arris.Model()
    solid = build(model)
    edges = pick(model, solid)
    assert edges
    return solid.fillet(edges, value) if op == "fillet" else solid.chamfer(edges, value)


@pytest.mark.parametrize("name", sorted(SPIKES))
def test_arris_blends_to_the_closed_form(name: str) -> None:
    got = _blend(name)
    assert got.check().ok
    m = got.measure()
    c = m.centroid
    _held((m.volume, m.area, (c[0], c[1], c[2])), PARTS[name])


# The values arris refuses, in its own words: (base, edges, op, value, reason).
REFUSED: dict[str, tuple[Build, Pick, str, float, str]] = {
    "fillet-box|Z-zero": (_box, _vertical, "fillet", 0.0, "radius must be positive, not 0"),
    "fillet-box|Z-negative": (_box, _vertical, "fillet", -1.0, "radius must be positive, not -1"),
    "fillet-box|Z-past": (
        _box,
        _vertical,
        "fillet",
        4.5,
        "the blend does not fit its faces: it leaves its face through an edge that is not the "
        "corner's own, or two blends' contacts on one face cross or swap order",
    ),
    "fillet-box>Z-past": (
        _box,
        _at(2.0),
        "fillet",
        4.5,
        "the blend does not fit its faces: it leaves its face through an edge that is not the "
        "corner's own, or two blends' contacts on one face cross or swap order",
    ),
    "chamfer-box|Z-zero": (_box, _vertical, "chamfer", 0.0, "distance must be positive, not 0"),
    "chamfer-box|Z-negative": (
        _box,
        _vertical,
        "chamfer",
        -1.0,
        "distance must be positive, not -1",
    ),
    "chamfer-box|Z-past": (
        _box,
        _vertical,
        "chamfer",
        4.5,
        "the blend does not fit its faces: it leaves its face through an edge that is not the "
        "corner's own, or two blends' contacts on one face cross or swap order",
    ),
}


@pytest.mark.parametrize("name", sorted(REFUSED))
def test_arris_refuses_what_open_cascade_does_not_build(name: str) -> None:
    """Where CadQuery raises `StdFail_NotDone`, arris refuses with its own reason."""
    assert RAISES[name] == _NOT_DONE
    build, pick, op, value, reason = REFUSED[name]
    model = arris.Model()
    solid = build(model)
    edges = pick(model, solid)
    with pytest.raises(arris.OpDegenerateError) as raised:
        solid.fillet(edges, value) if op == "fillet" else solid.chamfer(edges, value)
    assert raised.value.reason == reason


@pytest.mark.parametrize("op", ["fillet", "chamfer"])
def test_arris_refuses_a_seam_open_cascade_passes_over(op: str) -> None:
    """A cylinder's seam has its one face on both sides: arris refuses to blend
    it, where Open CASCADE passes over it (`fillet-cylinder-edges`)."""
    model = arris.Model()
    solid = _cylinder(2.0)(model)
    edges = model.edges(solid.body)
    seams = [e for e in edges if _seam(model, solid, e)]
    assert len(seams) == 1
    assert model.curve(seams[0]).kind == "line"
    with pytest.raises(arris.OpDegenerateError) as raised:
        solid.fillet(edges, 0.5) if op == "fillet" else solid.chamfer(edges, 0.5)
    assert "tangent dihedral" in raised.value.reason


# --- ADR-0020's edge key in arris -----------------------------------------


def _sub(a: Sequence[float], b: Sequence[float]) -> Point:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a: Sequence[float], b: Sequence[float]) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Sequence[float], b: Sequence[float]) -> Point:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def exact_centre(model: arris.Model, edge: arris.Edge) -> Point | None:
    """ADR-0020 rule 2's exact centre of mass of an edge, or None where it is estimated.

    A line's midpoint; a full circle's or full ellipse's centre; an arc's
    centre moved `r sin(θ/2)/(θ/2)` along its bisector, the arc running
    counter-clockwise about the curve's axis from its start to its end, or
    from its end to its start on a reversed edge.
    """
    c = model.curve(edge)
    if c.kind == "line":
        return (
            (c.start[0] + c.end[0]) / 2,
            (c.start[1] + c.end[1]) / 2,
            (c.start[2] + c.end[2]) / 2,
        )
    if c.kind in ("circle", "ellipse") and c.start == c.end:
        assert c.origin is not None
        return c.origin
    if c.kind != "circle":
        return None
    assert c.origin is not None
    assert c.axis is not None
    first, last = (c.end, c.start) if edge.reversed else (c.start, c.end)
    u, v = _sub(first, c.origin), _sub(last, c.origin)
    sweep = math.atan2(_dot(_cross(u, v), c.axis), _dot(u, v))
    if sweep <= 0:
        sweep += 2 * math.pi
    # The bisector: u turned by sweep/2 about the axis (Rodrigues; u ⟂ axis).
    half = sweep / 2
    w = _cross(c.axis, u)
    bis = tuple(u[k] * math.cos(half) + w[k] * math.sin(half) for k in range(3))
    d = math.sin(half) / half
    return (c.origin[0] + d * bis[0], c.origin[1] + d * bis[1], c.origin[2] + d * bis[2])


def polyline_centres(model: arris.Model, solid: arris.build.Solid) -> dict[int, Point]:
    """Each edge's tessellated polyline's centre of mass, at ADR-0017's chord, by edge index."""
    lo, hi = model.bounds(solid.body) or ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0))
    mesh = model.tessellate(solid.body, CHORD * math.dist(lo, hi))
    pos = struct.unpack(f"<{mesh.n_positions * 3}d", mesh.positions)
    idx = struct.unpack(f"<{len(mesh.edge_indices) // 4}I", mesh.edge_indices)
    out = {}
    for edge, start, stop in mesh.edges:
        pts = [pos[3 * idx[k] : 3 * idx[k] + 3] for k in range(start, stop)]
        total = 0.0
        acc = [0.0, 0.0, 0.0]
        for p, q in itertools.pairwise(pts):
            ell = math.dist(p, q)
            total += ell
            for k in range(3):
                acc[k] += ell * (p[k] + q[k]) / 2
        out[edge.index] = (acc[0] / total, acc[1] / total, acc[2] / total)
    return out


def _d(
    model: arris.Model, plane: arris.build.Workplane, via: tuple[float, float]
) -> arris.build.Solid:
    loop = arris.Loop.path((-1, 0), [arris.Segment.line((1, 0)), arris.Segment.arc((-1, 0), via)])
    return arris.build.Sketch(plane, loop).extrude(1, model=model)


def _pac(model: arris.Model) -> arris.build.Solid:
    loop = arris.Loop.path(
        (0, 0),
        [
            arris.Segment.line((1, 0)),
            arris.Segment.arc((0, -1), (-1, 0)),
            arris.Segment.line((0, 0)),
        ],
    )
    return arris.build.Sketch(arris.build.Workplane.XY(), loop).extrude(1, model=model)


def _tilt(model: arris.Model) -> arris.build.Solid:
    cut = arris.build.Solid.box((-5, -5, -1), (5, 5, 1), model=model)
    cut = cut.moved(axis=(1, 0, 0), angle=math.radians(30)).moved((0, 0, 2))
    return _cylinder(1.0)(model).cut(cut)


def _cross_part(model: arris.Model) -> arris.build.Solid:
    up = arris.build.Solid.cylinder((0, 0, -5), (0, 0, 1), 2, 10, model=model)
    return up.fuse(arris.build.Solid.cylinder((-5, 0, 0), (1, 0, 0), 1, 10, model=model))


_FLIPPED = arris.build.Workplane.of((0, 0, 0), (0, 0, -1), (1, 0, 0))
ARCS: dict[str, Build] = {
    "d": lambda m: _d(m, arris.build.Workplane.XY(), (0, 1)),
    "d-other-side": lambda m: _d(m, arris.build.Workplane.XY(), (0, -1)),
    "d-flipped-plane": lambda m: _d(m, _FLIPPED, (0, 1)),
    "pac": _pac,
    "rounded": _rounded,
    "plate": _plate,
    "tube": _tube,
}


@pytest.mark.parametrize("name", sorted(ARCS))
def test_the_exact_centre_is_the_tessellations(name: str) -> None:
    """Every arc's and circle's exact centre is its own polyline's within the chord's
    reach: the sweep's direction is read right on either orientation."""
    model = arris.Model()
    solid = ARCS[name](model)
    lo, hi = model.bounds(solid.body) or ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0))
    diagonal = math.dist(lo, hi)
    polys = polyline_centres(model, solid)
    curved = 0
    for edge in model.edges(solid.body):
        exact = exact_centre(model, edge)
        assert exact is not None
        if model.curve(edge).kind == "circle":
            curved += 1
            assert math.dist(exact, polys[edge.index]) < CHORD * diagonal
    assert curved >= 2


def test_the_estimate_of_a_spline_is_well_inside_the_margin() -> None:
    """arris's crossing curves are B-splines (two halves at +x, one whole at -x, where
    Open CASCADE has three pieces and one); their polylines' centres sit within
    1e-8 of the diagonal of the quadrature's, ten thousand times inside the margin."""
    model = arris.Model()
    solid = _cross_part(model)
    lo, hi = model.bounds(solid.body) or ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0))
    diagonal = math.dist(lo, hi)
    polys = polyline_centres(model, solid)
    splines = [e for e in model.edges(solid.body) if model.curve(e).kind == "nurbs"]
    assert len(splines) == 3
    xbar = _cross_centre_x()
    for e in splines:
        assert exact_centre(model, e) is None
        assert abs(abs(polys[e.index][0]) - xbar) < ESTIMATE_ERROR * diagonal < MARGIN * diagonal


def _cluster(keys: Sequence[float], biggest: bool) -> list[int]:
    """CadQuery's clusters (ADR-0017 rule 1): the indices kept by `>` or `<`."""
    order = sorted(range(len(keys)), key=lambda i: keys[i])
    clusters: list[list[int]] = []
    start = 0.0
    for i in order:
        if clusters and keys[i] - start <= CQ_TOLERANCE:
            clusters[-1].append(i)
        else:
            clusters.append([i])
            start = keys[i]
    return clusters[-1] if biggest else clusters[0]


def select(model: arris.Model, edges: Sequence[arris.Edge], selector: str | None) -> list[int]:
    """ADR-0020's selection on exact keys: an axis cluster, the parallel lines, or both
    sides of an `or`."""
    if selector is None:
        return list(range(len(edges)))
    if " or " in selector:
        left, right = selector.split(" or ")
        return sorted(set(select(model, edges, left)) | set(select(model, edges, right)))
    axis = [0.0, 0.0, 0.0]
    axis[_AXIS[selector[1]]] = 1.0
    if selector[0] == "|":
        kept = []
        for i, e in enumerate(edges):
            c = model.curve(e)
            if c.kind == "line":
                along = _sub(c.end, c.start)
                length = math.sqrt(_dot(along, along))
                unit = tuple(a / length for a in along)
                cr = _cross(axis, unit)
                if math.sqrt(_dot(cr, cr)) < CQ_TOLERANCE:
                    kept.append(i)
        return kept
    centres = [exact_centre(model, e) for e in edges]
    assert all(c is not None for c in centres)
    keys = [_dot(c, axis) for c in centres if c is not None]
    return sorted(_cluster(keys, selector[0] == ">"))


_KIND = {"line": "LINE", "circle": "CIRCLE", "ellipse": "ELLIPSE", "nurbs": "BSPLINE"}


def _top_face(model: arris.Model, solid: arris.build.Solid, k: int) -> arris.Face:
    planar = [f for f in model.faces(solid.body) if model.surface(f).kind == "plane"]
    return max(planar, key=lambda f: (model.surface(f).origin or (0.0, 0.0, 0.0))[k])


# The selections arris can build, with their candidates (the solid's edges, or
# a face's) and selector, and how many candidates arris has where it differs.
ARRIS_SELECTIONS: dict[str, tuple[Build, str | None, str | None]] = {
    "box-edges": (_box, None, None),
    **{f"box-edges{s}": (_box, None, s) for s in (">X", "<X", ">Y", "<Y", ">Z", "<Z")},
    **{f"box-edges{s}": (_box, None, s) for s in ("|X", "|Y", "|Z")},
    "box-edges>Z or <Z": (_box, None, ">Z or <Z"),
    "box-faces>Z-edges": (_box, "Z", None),
    "box-faces>Z-edges>X": (_box, "Z", ">X"),
    "box-faces>X-edges|Z": (_box, "X", "|Z"),
    **{
        f"cylinder-edges{s}": (_cylinder(1.0), None, s)
        for s in (">Z", "<Z", ">X", ">Y", "|Z", "|X", ">Z or <Z")
    },
    "cylinder-edges": (_cylinder(1.0), None, None),
    "cylinder-faces>Z-edges": (_cylinder(1.0), "Z", None),
    "d-edges>Y": (ARCS["d"], None, ">Y"),
    "d-edges<Y": (ARCS["d"], None, "<Y"),
    "pac-edges<X": (_pac, None, "<X"),
    "pac-edges>Y": (_pac, None, ">Y"),
    "tilt-edges>Z": (_tilt, None, ">Z"),
    "plate-faces>Z-edges": (_plate, "Z", None),
    "rounded-edges>Z": (_rounded, None, ">Z"),
}


@pytest.mark.parametrize("name", sorted(ARRIS_SELECTIONS))
def test_the_exact_key_keeps_the_oracles_edges(name: str) -> None:
    """On lines, circles, arcs and a full ellipse, ADR-0020's key and CadQuery's
    clusters keep in arris the edges the oracle keeps, from as many candidates."""
    build, face, selector = ARRIS_SELECTIONS[name]
    model = arris.Model()
    solid = build(model)
    if face is None:
        edges = model.edges(solid.body)
    else:
        edges = model.edges_of(_top_face(model, solid, _AXIS[face]))
    count, want = SELECTED[name]
    assert len(edges) == count
    kept = []
    for i in select(model, edges, selector):
        centre = exact_centre(model, edges[i])
        assert centre is not None
        kept.append((_KIND[model.curve(edges[i]).kind], centre))
    assert _same_edges(kept, want), kept


def test_arris_and_open_cascade_put_a_holes_seam_on_opposite_sides() -> None:
    """The plate's hole: Open CASCADE's seam lies at -x, arris's at +x; both keep it
    under `|Z`, and its key along x differs by the hole's diameter."""
    oracle = record("plate-edges|Z")
    (seam,) = [
        oracle["candidates"][i]
        for i in oracle["kept"]
        if abs(oracle["candidates"][i]["centre"][0]) < 2
    ]
    model = arris.Model()
    solid = _plate(model)
    edges = model.edges(solid.body)
    seams = [e for e in edges if _seam(model, solid, e)]
    assert len(seams) == 1
    mine = exact_centre(model, seams[0])
    assert mine is not None
    assert abs(seam["centre"][0] + 1.5) < ROUNDING
    assert abs(mine[0] - 1.5) < ROUNDING
    assert seams[0] in [edges[i] for i in select(model, edges, "|Z")]

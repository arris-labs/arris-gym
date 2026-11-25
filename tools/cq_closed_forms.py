#!/usr/bin/env python3
"""Closed forms of the BenchCAD parts the oracle gets wrong (ADR-0006's `ClosedForm`).

Outside the gate. In its default mode it reads the pinned BenchCAD corpus
(the `[corpus]` extra) and the committed oracle rows, works out each listed
family's measures from how the part is built (never from either kernel's output),
and writes one `Verdict` per stem that the row's measures can test:

    uv run --extra corpus tools/cq_closed_forms.py --table T --oracle-rows O --out V.json \
        [--refusal FAMILY=FIXTURE ...] [--arris-bug FAMILY=FIXTURE ...] \
        [--blended-boundary STEM ...] [--signed-solids STEM ...] [--by-design STEM=ANCHOR ...]

or with its arguments in a file, one per line: `tools/cq_closed_forms.py @FILE` (BenchCAD's
are `tests/fixtures/c2/benchcad/verdicts.args`; a later `--table` or `--out` wins).

A row no rule classes is one the table left unclassified or classed only by a verdict, so
the tool reads a table run with or without `--verdicts` alike; a row arris ended
`unsupported_api` is outside the subset and gets no verdict. A family given by
`--refusal` or `--arris-bug` (or one row's stem, which wins) is classed by that regression
fixture rather than a closed form. A stem given by `--boundary` or `--blended-boundary` is
`occt_wrong` by the oracle's boundary integral (ADR-0006, amended 2026-11-23), by
`--signed-solids` by its oracle shape's signed solids, and by `--by-design` `by_design` on its
anchor where `check_by_design_cause` holds (ADR-0025); each wins over its family's.

The part shapes, each read from its program's text (a program that is not exactly
one of them raises, never guessed):

- **t_pipe_fitting**: a main cylinder M (axis = the plane's normal, radius R,
  height h), a branch B on the plane's local +y from y = 0 (radius r, to y = h2),
  a bore D through B (radius s, from y = 0), and a through bore C of M (radius q),
  as ((M united with B) less D) less C. Volume, moment and area are one-dimensional integrals
  over the part's cross-sections and surface patches (each patch's formula is in
  `_tee`). The flanged tee (`_flanged_tee`) adds a flange on each end of M, a
  `polarArray` of bolt holes through both by CadQuery's face frames, and a flange
  flush with B's end that may start inside M's wall (D then may end inside it too):
  the same integrals over each (x, z) column's y-extent (`flanged_tee_measures`).
- **u_bolt / j_hook**: one or two vertical cylinders (radius r) joined to a half
  torus (major radius R = the cylinder's offset, minor radius r) at its end disc
  z0, with an optional box under the cylinders. Pappus gives the torus; the only
  overlap, a cylinder with the torus's first r/2 of height, is
  an integral over a height h of the intersection's cross-section
  `2 min(wC, wT)`, and its boundary patches are one-dimensional integrals (`_hook`).
  Under the box, a nut under each cylinder: a convex polygon prism, `extrude(e,
  both=True)` of `polygon(n, d)` or of `moveTo(p).polyline([...]).close()` (whose lone
  `moveTo` point CadQuery drops, so the corpus's nut is a pentagon), its top inside the
  box. It adds `A·depth` below the box and `P·depth` of wall (its bottom takes the place
  of the box-bottom patch it covers), `A` and `P` by the shoelace formula; a cylinder
  foot just below the box adds only its disc's circular segments beyond the nut's edges.

- **manifold_block / connecting_rod / locator_block / pillow_block / mounting_angle /
  hollow_tube / l_bracket**: boxes and cylinders whose axes and faces all lie
  along x, y or z, united and cut in the program's order (`part_ops` reads the program
  by CadQuery's rules; bores crossing bores, a counterbore on a box's edge, a cross hole
  into a ring's wall), the first box's top edges optionally chamfered (`edges(">A").chamfer(c)`,
  the box less four mitred wedges, a convex solid whose slanted faces each hold a line along
  an axis). Volume and moments are fluxes through the boundary (the divergence theorem), and
  along a line on any face each solid is one exact interval, so what is left is one integral
  across the lines per face, split where its formula changes (`part_measures`). A fillet of
  straight edges along an axis (`edges("|A").fillet(r)`, or the four edges of the first box's
  +A face) is a `Round` per edge: the r-by-r square at the edge less its quarter disc, cut from
  a convex edge and added to a concave one, run on through the chamfer above a corner; where
  two rounds of a face cross at a sharp corner, the part is what lies under both (a mitre).
  A stadium cut (`slot2D` extruded both ways) is a box and two cylinders.

- **rect_frame / hex_nut**: a prism (a rectangle with a window and edge notches, or a polygon)
  bored through, the rims of its faces filleted: each section is the region offset inward
  with mitred corners, the holes grown by the offset (`_rim_prism`).

- **spur_gear**: a chamfered tooth plate, bored, lightened by holes, recessed on both faces
  and keyed (`gear_measures`: the recess's disc less the lens it shares with a hole), or with
  flanges and a relief groove on one end (`flanged_gear_closed_form`).

- **bellows**: a closed profile turned about y (Pappus), an optional `hole` from the top
  widening its inner wall, and a `polarArray` of circles `cutBlind` from each end face:
  through the bottom flange, and from the top face down to the cone under it (a sliver).
  A hole may run past the rim; what it takes is integrated by radius over its disc's
  part inside the rim (`bellows_measures`).

- **spacer_ring**: a ring on the `YZ` plane, bored and filleted at its four rim circles, cut
  across its wall by a box through the strip `|z| < w` (through the ring, or from its bottom
  face up to a height inside the outer cylinder's straight part): every measure is a
  one-dimensional integral over the radius (`slotted_ring_measures`).

- **sprocket**: one chamfered tooth plate bored along its axis, on `YZ`, `XY` or `XZ`
  (toward -y), and on `XY` a hub annulus under it: the double sprocket's mitred chamfer
  formulas without the hub above (`plate_measures`).

- **pan_head_screw**: a shank and a head turned about z, the head's top rim filleted, less
  the strip of a slot across the head: a disc cut by a strip is elementary, the fillet's
  torus a quadrature over its angle (`screw_closed_form`).

- **rivet**: a shank and a head swept from a circular arc, with three chamfered
  or filleted rims. The blended meridian gives each measure (`rivet_closed_form`).

- **crossing cylinders**: the one CAD-Recode program whose row nothing classes (`CROSSING`).
- **CAD-Recode sketch solids** (`--sketch-boundary`): integrate the planar
  and cylindrical boundary in an oracle worker, independently of GProp's
  volume and surface quadrature. Compare the two resolutions before using
  the finer integral. The bounds come from Open CASCADE's tight box.

The integrals are tanh-sinh quadrature (endpoint square-root singularities are
what it is for) over intervals split where an integrand's formula changes or turns
nearly singular. `tests/test_cq_closed_forms.py` holds each form to arris's own
measures on constructed programs, inside ADR-0005's tolerance; and the tool checks
every verdict it writes with `compare`, which holds the exonerated kernel to the
closed form and the blamed one away from it.
"""

from __future__ import annotations

import argparse
import ast
import functools
import gzip
import itertools
import json
import math
import multiprocessing
import re
import sys
from collections.abc import Callable, Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from arris_gym import ExecResult
    from arris_gym.fidelity import OracleReport
    from arris_gym.sandbox.outcome import ArrisRefusal

_BOUNDARY_MARK = "SketchBoundaryRecord: "
# Gauss-Legendre order on each slice of a smooth pcurve interval. The two
# subdivision counts are in tools/oracle/sketch_boundary.py.
_BOUNDARY_ORDER = 24
# Keep the evidence well inside ADR-0005 and discard the quadrature's last
# digits before serializing. Coordinates in this corpus are in [-100, 100].
_BOUNDARY_SIGNIFICANT_DIGITS = 10
# A signed volume's digits: twelve, so the sum of a part's solids keeps its 1e-9 (VOLUME_REL)
# against the measured volume with three orders to spare.
_SIGNED_SIGNIFICANT_DIGITS = 12
# Each trim interval split 32 and 64 times: on BenchCAD's waffle plates the two agree to the
# last digit kept; the sketch boundary's 128 and 256 take past a minute on a 100-face part.
_SIGNED_SUBDIVISIONS = (32, 64)
# The oracle's deadline for the probe, the corpus's (`cq_corpus.ORACLE_TIMEOUT`).
_SIGNED_TIMEOUT = 240.0
_BOUNDARY_COORDINATE_PLACES = 8

# Quadrature: the step of the tanh-sinh sum and its half-width. At 1/32 and 3.5 a
# square-root endpoint is integrated to full double precision (the weights past 3.5
# are below 1e-30). Not a tolerance of any comparison: those are ADR-0005's.
SINH_STEP = 1 / 32
SINH_SPAN = 3.5
# Outer Gauss-Legendre nodes over a height, where the integrand is analytic.
GAUSS_NODES = 48

# A cylinder's foot and the box's bottom face are one plane when they differ by less than
# this: the programs' decimal literals do not add up exactly (a cylinder's `h / 2` below
# its centre), and the kernels' own tolerance, 1e-7, is far above it.
FOOT_TOL = 1e-9

# A part's placements (a tee's branch start, a hook cylinder's x offset and top height) are
# the shape a closed form assumes when they match to this: the programs' decimal literals
# (`h / 2`, sums of them) are not exact, and the kernels' own tolerance, 1e-7, is far above.
PLACEMENT_TOL = 1e-9

# Newton's iteration for a Gauss-Legendre node stops when its step is under this: a node
# lies in [-1, 1], so a step this small is below the last bits a double keeps there.
NEWTON_STEP_TOL = 1e-16

_BLEND_DOES_NOT_FIT = (
    "degenerate result: the blend does not fit its faces: it leaves its face through an "
    "edge that is not the corner's own, or two blends' contacts on one face cross or swap order"
)

# What a `--refusal` fixture stands for: the kernel's refusal that a row must show on its
# re-run, (exception class, message prefix, number of entities), so a row refused for another
# reason is never classed by that fixture's name.
REFUSAL_CAUSES: dict[str, tuple[str, str, int]] = {
    "cq-locator-block-intersecting-bores-fillet": ("OpUnsupportedError", "no closed form for ", 0),
    "cq-rim-chamfer-after-crosswise-fillet": (
        "OpDegenerateError",
        "degenerate result: the corner at the edge's end is one the blend's "
        "closed forms do not cover",
        4,
    ),
    "cq-rim-chamfer-after-parallel-fillet": (
        "OpDegenerateError",
        _BLEND_DOES_NOT_FIT,
        2,
    ),
    "cq-short-slot-flat-link": ("SketchError", "slot: length ", 0),
    "cq-slotted-plate-chamfer-after-fillet": (
        "OpDegenerateError",
        "degenerate result: the corner at the edge's end is one the blend's "
        "closed forms do not cover",
        3,
    ),
    "cq-tangent-cylinders": (
        "OpDegenerateError",
        "degenerate result: the faces touch along a curve interior to both result faces",
        2,
    ),
    "cq-vertical-fillet-after-rim-chamfer": (
        "OpDegenerateError",
        _BLEND_DOES_NOT_FIT,
        2,
    ),
    "cq-waffle-plate-tangent-fillet": (
        "OpDegenerateError",
        "degenerate result: the edge's faces meet at a tangent dihedral, "
        "which has no corner to blend",
        3,
    ),
}

# What an `--arris-bug` bounds fixture stands for: arris's box loose past what ADR-0005's
# `BOUNDS_ABS` accepts, on a row `ok` on both sides, the other figures inside the
# fixture's own: (volume and area, relative, the most the oracle's may lie off arris's;
# the most arris's face count may differ from the oracle's). The cross hole's cylinders are
# measured 3.1e-5 and 1.1e-5 off the closed form by Open CASCADE (the fixture's README), so
# 1e-4 is three times that; the chamfered slot is exact on both sides, so ADR-0005's own.
# A row outside these has another fault than the fixture's, and stays unclassified.
CROSS_HOLE_REL = 1e-4
BOUNDS_CAUSES: dict[str, tuple[float, int]] = {
    "cq-cross-hole-bounds": (CROSS_HOLE_REL, 2),
    "cq-through-side-bore-cylinder-bounds": (CROSS_HOLE_REL, 1),
    "cq-chamfer-slot-bounds": (1e-9, 2),  # VOLUME_REL and AREA_REL
}

# Programs run at once when the verdicts are checked.
WORKERS = 16

Vec = tuple[float, float, float]
Box = tuple[Vec, Vec]


def tanh_sinh(f: Callable[[float], float], a: float, b: float) -> float:
    """The integral of `f` over `[a, b]`; 0 when the interval is empty."""
    if b <= a:
        return 0.0
    half = (b - a) / 2
    total = 0.0
    steps = int(SINH_SPAN / SINH_STEP)
    for k in range(-steps, steps + 1):
        t = k * SINH_STEP
        u = math.pi / 2 * math.sinh(t)
        # 1 - tanh(u) = 2 / (e^{2u} + 1): the distance to an end without cancellation.
        weight = math.pi / 2 * math.cosh(t) / math.cosh(u) ** 2
        if u >= 0:
            x = b - half * 2 / (math.exp(2 * u) + 1)
        else:
            x = a + half * 2 / (math.exp(-2 * u) + 1)
        if x <= a or x >= b:
            continue
        total += weight * f(x)
    return total * half * SINH_STEP


def _legendre(n: int) -> tuple[list[float], list[float]]:
    """Gauss-Legendre nodes and weights on [-1, 1], by Newton on P_n."""
    nodes: list[float] = []
    weights: list[float] = []
    for i in range(1, n + 1):
        x = math.cos(math.pi * (i - 0.25) / (n + 0.5))
        for _ in range(100):
            p0, p1 = 1.0, x
            for k in range(2, n + 1):
                p0, p1 = p1, ((2 * k - 1) * x * p1 - (k - 1) * p0) / k
            dp = n * (x * p1 - p0) / (x * x - 1)
            step = p1 / dp
            x -= step
            if abs(step) < NEWTON_STEP_TOL:
                break
        p0, p1 = 1.0, x
        for k in range(2, n + 1):
            p0, p1 = p1, ((2 * k - 1) * x * p1 - (k - 1) * p0) / k
        dp = n * (x * p1 - p0) / (x * x - 1)
        nodes.append(x)
        weights.append(2 / ((1 - x * x) * dp * dp))
    return nodes, weights


_GL = _legendre(GAUSS_NODES)


def _component(f: Callable[[float, int], float], k: int, x: float) -> float:
    """`f`'s component k at `x`: an integrand of one variable for `gauss`."""
    return f(x, k)


def gauss(f: Callable[[float], float], a: float, b: float) -> float:
    """The integral of an analytic `f` over `[a, b]`."""
    half = (b - a) / 2
    mid = (a + b) / 2
    return half * sum(w * f(mid + half * x) for x, w in zip(*_GL, strict=True))


def _num(text: str) -> float:
    return float(text)


_NUMBER = r"(-?\d+(?:\.\d+)?)"


def _cylinders(text: str) -> list[tuple[Vec, float, float]]:
    """Each `.cylinder(h, r)` of a program: its offset (0 when none) and `(h, r)`."""
    found: list[tuple[Vec, float, float]] = []
    pattern = re.compile(
        rf"(?:offset=cq\.Vector\({_NUMBER}, {_NUMBER}, {_NUMBER}\)[^\n]*\n\s*)?"
        rf"\.cylinder\({_NUMBER}, {_NUMBER}\)"
    )
    for m in pattern.finditer(text):
        g = m.groups()
        offset = (_num(g[0]), _num(g[1]), _num(g[2])) if g[0] is not None else (0.0, 0.0, 0.0)
        found.append((offset, _num(g[3]), _num(g[4])))
    return found


def _tee(text: str) -> dict[str, float]:
    """The tee's parameters, refusing a program that is not the one shape this reads."""
    plane = re.search(r'cq\.Workplane\("(XY|XZ|YZ)"\)', text)
    cyl = _cylinders(text)
    if plane is None or len(cyl) != 4 or "-90.0, 0.0, 0.0" not in text:
        raise ValueError("not the tee this tool reads")
    (_, h, big_r) = cyl[0]
    (ob, hb, r) = cyl[1]
    (od, hd, s) = cyl[2]
    (_, hc, q) = cyl[3]
    if (
        ob[0]
        or ob[2]
        or od[0]
        or od[2]
        or cyl[0][0] != (0.0, 0.0, 0.0)
        or cyl[3][0] != (0.0, 0.0, 0.0)
    ):
        raise ValueError("tee offsets are not along the plane's y alone")
    if abs(ob[1] - hb / 2) > PLACEMENT_TOL or abs(od[1] - hd / 2) > PLACEMENT_TOL:
        raise ValueError("a tee's branch or bore does not start at y = 0")
    if not (s < q < big_r and s < r < big_r and hc >= h and hd >= hb > big_r and r < h / 2):
        raise ValueError("a tee outside the ordering the closed form assumes")
    return {"R": big_r, "h": h, "r": r, "hb": hb, "s": s, "q": q}


def tee_measures(p: dict[str, float]) -> tuple[float, float, Vec, Box]:
    """Volume, area, centroid and bounds of the tee in the plane's local frame."""
    big_r, h, r, hb, s, q = p["R"], p["h"], p["r"], p["hb"], p["s"], p["q"]
    pi = math.pi

    def chord(radius: float) -> Callable[[float], float]:
        return lambda x: 2 * math.sqrt(max(radius * radius - x * x, 0.0))

    def wall(x: float) -> float:
        return math.sqrt(big_r * big_r - x * x)

    def bore(x: float) -> float:
        return math.sqrt(max(q * q - x * x, 0.0))

    ch_s, ch_r = chord(s), chord(r)
    # D inside the wall M \ C: its y-extent at (x, z) is wall(x) - bore(x).
    d_wall = tanh_sinh(lambda x: ch_s(x) * (wall(x) - bore(x)), -s, s)
    d_wall_y = pi * s * s * (big_r**2 - q**2) / 2
    # B outside M: y from wall(x) to hb; D inside it likewise.
    b_out = tanh_sinh(lambda x: ch_r(x) * (hb - wall(x)), -r, r)
    d_out = tanh_sinh(lambda x: ch_s(x) * (hb - wall(x)), -s, s)
    b_out_y = tanh_sinh(lambda x: ch_r(x) * (hb**2 - wall(x) ** 2) / 2, -r, r)
    d_out_y = tanh_sinh(lambda x: ch_s(x) * (hb**2 - wall(x) ** 2) / 2, -s, s)
    volume = pi * (big_r**2 - q**2) * h - d_wall + b_out - d_out
    moment_y = -d_wall_y + b_out_y - d_out_y
    # Patches of the boundary, by the cylinder they lie on.
    # M's side inside B and C's side inside D: not boundary. The integrand's square root
    # ends where |cos a| = r / R (s / q), so the angles are cut there.
    lo1, lo2 = math.acos(r / big_r), math.acos(s / q)
    p1 = tanh_sinh(
        lambda a: 2 * big_r * math.sqrt(max(r * r - (big_r * math.cos(a)) ** 2, 0.0)), lo1, pi - lo1
    )
    p2 = tanh_sinh(
        lambda a: 2 * q * math.sqrt(max(s * s - (q * math.cos(a)) ** 2, 0.0)), lo2, pi - lo2
    )
    # Over a quarter circle, where the integrand's near-singular point (R close to r) is an end.
    p3 = 4 * tanh_sinh(lambda a: r * (hb - math.sqrt(big_r**2 - (r * math.cos(a)) ** 2)), 0, pi / 2)
    p4 = 4 * tanh_sinh(lambda a: s * (hb - math.sqrt(q**2 - (s * math.cos(a)) ** 2)), 0, pi / 2)
    area = (
        (2 * pi * big_r * h - p1)  # M's side
        + (2 * pi * q * h - p2)  # C's side
        + p3  # B's side outside M
        + p4  # D's side, from C to B's end
        + 2 * pi * (big_r**2 - q**2)  # M's two ends
        + pi * (r * r - s * s)  # B's end
    )
    centroid = (0.0, moment_y / volume, 0.0)
    bounds = ((-big_r, -big_r, -h / 2), (big_r, hb, h / 2))
    return volume, area, centroid, bounds


_FRAMES = {  # a plane's local (x, y, z) in global coordinates, as (xdir, ydir, normal)
    "XY": ((1, 0, 0), (0, 1, 0), (0, 0, 1)),
    "XZ": ((1, 0, 0), (0, 0, 1), (0, -1, 0)),
    "YZ": ((0, 1, 0), (0, 0, 1), (1, 0, 0)),
}


def to_global(plane: str, v: Vec) -> Vec:
    """A point of the plane's local frame in global coordinates."""
    xd, yd, nd = _FRAMES[plane]
    return (
        v[0] * xd[0] + v[1] * yd[0] + v[2] * nd[0],
        v[0] * xd[1] + v[1] * yd[1] + v[2] * nd[1],
        v[0] * xd[2] + v[1] * yd[2] + v[2] * nd[2],
    )


def box_to_global(plane: str, box: Box) -> Box:
    """A local box in global coordinates, its corners sorted per axis."""
    lo, hi = to_global(plane, box[0]), to_global(plane, box[1])
    return (
        (min(lo[0], hi[0]), min(lo[1], hi[1]), min(lo[2], hi[2])),
        (max(lo[0], hi[0]), max(lo[1], hi[1]), max(lo[2], hi[2])),
    )


def _dot(u: Vec, v: Vec) -> float:
    return u[0] * v[0] + u[1] * v[1] + u[2] * v[2]


_BOLTS = re.compile(
    rf'\.faces\("([<>])([XYZ])"\)\.workplane\(\)\s*'
    rf"\.polarArray\({_NUMBER}, 0, 360, (\d+)\)\s*\.hole\({_NUMBER}\)"
)


def _bolt_centres(plane: str, text: str) -> tuple[float, list[tuple[float, float]]]:
    """The bolt holes' diameter and their centres in the plane's local (x, y), each once.

    Each `faces(">A" | "<A").workplane().polarArray(rp, 0, 360, n).hole(d)` puts `n`
    points `rp (cos θ, sin θ)`, θ = 360° k / n, in the face's frame by CadQuery's rules
    (ADR-0017, ADR-0019): its origin the parent's projected onto the face, so on the
    main axis; its x `Z cross normal`, or global X when the normal is ±Z; its y `normal cross x`.
    The two faces' frames are mirrored on XZ and YZ, so an odd `n` puts its second set
    between the first's holes. Each hole is a through bore of both flanges
    (`depth=None` is the part's diagonal). A centre met twice is one hole; two holes
    that overlap are not a part this tool reads.
    """
    xd, yd, _ = _FRAMES[plane]
    sets = _BOLTS.findall(text)
    if len(sets) != 2 or {s[0] for s in sets} != {"<", ">"}:
        raise ValueError("a flanged tee's bolt holes are not one polar array on each end")
    if len({(s[2], s[3], s[4]) for s in sets}) != 1:
        raise ValueError("a flanged tee's two bolt circles differ")
    centres: list[tuple[float, float]] = []
    for sign, axis, rp, n, _ in sets:
        out = 1.0 if sign == ">" else -1.0
        normal: Vec = (out * (axis == "X"), out * (axis == "Y"), out * (axis == "Z"))
        x_dir = _cross((0.0, 0.0, 1.0), normal)
        if math.hypot(*x_dir) == 0.0:
            x_dir = (1.0, 0.0, 0.0)
        y_dir = _cross(normal, x_dir)
        for k in range(int(n)):
            a = math.radians(360 / int(n) * k)
            c, s = _num(rp) * math.cos(a), _num(rp) * math.sin(a)
            g = (
                c * x_dir[0] + s * y_dir[0],
                c * x_dir[1] + s * y_dir[1],
                c * x_dir[2] + s * y_dir[2],
            )
            local = (_dot(g, xd), _dot(g, yd))
            if all(math.dist(local, old) > PLACEMENT_TOL for old in centres):
                centres.append(local)
    d = _num(sets[0][4])
    for one, two in itertools.combinations(centres, 2):
        if math.dist(one, two) <= d:
            raise ValueError("a flanged tee's bolt holes overlap")
    return d, centres


@dataclass(frozen=True)
class FlangedTee:
    """A flanged tee: the bare tee `tee` (`_tee`'s parameters) with a flange (t, Rf) on
    each end of M, bolt holes of diameter `d` at `centres` (the plane's local x, y)
    through both, and a flange (t2, rf2) flush with the branch's end."""

    tee: dict[str, float]
    t: float
    rf: float
    t2: float
    rf2: float
    d: float
    centres: tuple[tuple[float, float], ...]


def _flanged_tee(text: str) -> FlangedTee:
    """The flanged tee's parameters, refusing a program that is not the one shape this reads.

    Seven cylinders in the program's order: the main M (h, R), a flange (t, Rf) on each
    end centred on M's end discs, the bolt holes through both flanges, then the branch B
    (hb, r) on y from 0, its flange (t2, rf2) flush with B's end, the branch bore D and
    the through bore C (as `_tee`'s).
    """
    plane = re.search(r'cq\.Workplane\("(XY|XZ|YZ)"\)', text)
    cyl = _cylinders(text)
    if plane is None or len(cyl) != 7 or text.count("-90.0, 0.0, 0.0") != 3:
        raise ValueError("not the flanged tee this tool reads")
    (om, h, big_r), (of1, t, rf), (of2, t_, rf_), (ob, hb, r) = cyl[:4]
    (obf, t2, rf2), (od, hd, s), (oc, hc, q) = cyl[4:]
    if (om, oc) != ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0)) or (t, rf) != (t_, rf_):
        raise ValueError("a flanged tee's main cylinder, bore or flanges are not centred")
    if any(o[0] or o[1] for o in (of1, of2)) or any(o[0] or o[2] for o in (ob, obf, od)):
        raise ValueError("a flanged tee's offsets are not along the expected axes")
    if (
        abs(of1[2] + h / 2) > PLACEMENT_TOL
        or abs(of2[2] - h / 2) > PLACEMENT_TOL
        or abs(ob[1] - hb / 2) > PLACEMENT_TOL
        or abs(obf[1] - (hb - t2 / 2)) > PLACEMENT_TOL
        or abs(od[1] - hd / 2) > PLACEMENT_TOL
    ):
        raise ValueError("a flanged tee's flange, branch or bore is not where it is assumed")
    d, centres = _bolt_centres(plane.group(1), text)
    rp = math.hypot(*centres[0])
    if not (
        s < q < big_r < rf
        and s < r < min(rf2, big_r)
        and big_r < rp - d / 2
        and rp + d / 2 < rf
        and rf2 < h / 2 - t / 2
        and 0 < t2 < hb <= hd
        and hc >= h + t
    ):
        raise ValueError("a flanged tee outside the ordering the closed form assumes")
    tee = {"R": big_r, "h": h, "r": r, "hb": hb, "s": s, "q": q, "hd": hd}
    return FlangedTee(tee, t, rf, t2, rf2, d, tuple(centres))


def _pieces(f: Callable[[float], float], a: float, b: float, cuts: Sequence[float]) -> float:
    """The integral of `f` over `[a, b]`, split at each cut inside it (where `f` jumps,
    kinks or has a square-root end), each piece by tanh-sinh."""
    ends = [a, *sorted(c for c in cuts if a < c < b), b]
    return sum(tanh_sinh(f, lo, hi) for lo, hi in itertools.pairwise(ends))


def flanged_tee_measures(f: FlangedTee) -> tuple[float, float, Vec, Box]:
    """Volume, area, centroid and bounds of the flanged tee in the plane's local frame.

    The part is ((M with its flanges, less the bolt holes) united with the branch B and
    its flange BF) less D less C. Everything off the y = 0 side of the branch is
    elementary: M less C over h, each flange an annulus Rf - R over t plus the half t/2
    past M's end, its faces, rim and bolt-hole walls. The branch side is integrated over
    x with each (x, z) column's y-extent, where M's wall is at y = w(x) = sqrt(R^2 - x^2)
    and C's at b(x) = sqrt(q^2 - x^2): B and BF outside M less D add
    (hb - w)+ over s < rho < r and (hb - max(w, hb - t2))+ over r < rho < rf2 (w = 0 past
    |x| = R, where M ends), and D takes
    (min(w, hd) - b)+ of M's wall over rho < s (rho^2 = x^2 + z^2; BF may start inside M,
    D may end inside M's wall). Each surface patch is a one-dimensional integral of the
    same column lengths, on its cylinder by angle or on its plane by x, split where a
    level (hb, hb - t2, hd) meets M's wall or a radius (s, r, rf2) is reached.
    """
    big_r, h, r, hb, s, q = (f.tee[k] for k in ("R", "h", "r", "hb", "s", "q"))
    hd = f.tee["hd"]
    t, rf, t2, rf2, d = f.t, f.rf, f.t2, f.rf2, f.d
    low = hb - t2  # BF's inner face
    pi = math.pi

    def wall(x: float) -> float:
        return math.sqrt(max(big_r * big_r - x * x, 0.0))

    def bore(x: float) -> float:
        return math.sqrt(max(q * q - x * x, 0.0))

    def ch(radius: float, x: float) -> float:
        return 2 * math.sqrt(max(radius * radius - x * x, 0.0))

    # The |x| beyond which M's wall is under each level (at y = 0, where M ends: R itself).
    crossings = [math.sqrt(big_r**2 - lv**2) for lv in (0.0, hb, low, hd) if 0 <= lv < big_r]
    x_cuts = [s, r, rf2, *crossings]

    def over_x(g: Callable[[float], float], upto: float) -> float:
        return 2 * _pieces(g, 0.0, upto, x_cuts)  # every integrand is even in x

    def around(radius: float, g: Callable[[float], float]) -> float:
        """A patch of a branch-axis cylinder: radius times the y-length g(x) over its turn."""
        cuts = [math.acos(c / radius) for c in crossings if c < radius]
        return 4 * radius * _pieces(lambda u: g(radius * math.cos(u)), 0.0, pi / 2, cuts)

    def b_col(x: float) -> tuple[float, float, float, float]:
        """B and BF outside M less D at x: (s..r column, r..rf2 column) as (bottom, top)."""
        w = wall(x)
        return w, max(w, hb), max(w, low), max(w, low, hb)

    def vb(x: float) -> float:
        lo1, hi1, lo2, hi2 = b_col(x)
        return (ch(r, x) - ch(s, x)) * (hi1 - lo1) + (ch(rf2, x) - ch(r, x)) * (hi2 - lo2)

    def mb(x: float) -> float:
        lo1, hi1, lo2, hi2 = b_col(x)
        return (ch(r, x) - ch(s, x)) * (hi1**2 - lo1**2) / 2 + (ch(rf2, x) - ch(r, x)) * (
            hi2**2 - lo2**2
        ) / 2

    def vd(x: float) -> float:
        return ch(s, x) * max(min(wall(x), hd) - bore(x), 0.0)

    def md(x: float) -> float:
        top = max(min(wall(x), hd), bore(x))
        return ch(s, x) * (top**2 - bore(x) ** 2) / 2

    disc = pi * d * d / 4
    n = len(f.centres)
    main = pi * (big_r**2 - q**2) * h
    flanges = 2 * (pi * (rf**2 - big_r**2) * t + pi * (big_r**2 - q**2) * t / 2 - n * disc * t)
    volume = main + flanges + over_x(vb, rf2) - over_x(vd, s)
    moment_x = -2 * t * disc * sum(c[0] for c in f.centres)
    moment_y = over_x(mb, rf2) - over_x(md, s) - 2 * t * disc * sum(c[1] for c in f.centres)

    # M's side under the branch, by angle a (x = R cos a, y = R sin a): what B, BF and D
    # cover there is not boundary.
    def m_cover(a: float) -> float:
        x, y = big_r * math.cos(a), big_r * math.sin(a)
        if y < low:
            return ch(r, x)
        if y < hb:
            return ch(rf2, x)
        return ch(s, x) if y < hd else 0.0

    a_cuts = [math.acos(c / big_r) for c in (s, r, rf2) if c < big_r]
    a_cuts += [math.asin(lv / big_r) for lv in (hb, low, hd) if 0 <= lv < big_r]
    m_side = 2 * pi * big_r * (h - t) - 2 * big_r * _pieces(
        m_cover, math.acos(min(rf2 / big_r, 1.0)), pi / 2, a_cuts
    )
    c_cuts = [math.asin(hd / q)] if hd < q else []
    c_side = 2 * pi * q * (h + t) - 2 * q * _pieces(
        lambda a: ch(s, q * math.cos(a)) if q * math.sin(a) < hd else 0.0,
        math.acos(s / q),
        pi / 2,
        c_cuts,
    )
    area = (
        m_side
        + c_side
        + 2 * (pi * (rf**2 - q**2) - n * disc)  # the flanges' outer faces
        + 2 * (pi * (rf**2 - big_r**2) - n * disc)  # their inner faces
        + 2 * (2 * pi * rf * t + n * pi * d * t)  # their rims and bolt-hole walls
        + around(r, lambda x: max(low - wall(x), 0.0))  # B's side outside M, below BF
        + around(rf2, lambda x: max(hb - max(wall(x), low), 0.0))  # BF's rim outside M
        + around(s, lambda x: max(min(max(wall(x), hb), hd) - bore(x), 0.0))  # D's side
        + over_x(lambda x: ch(s, x) if wall(x) > hd else 0.0, s)  # D's end inside M's wall
        + over_x(lambda x: ch(rf2, x) - ch(r, x) if wall(x) < low else 0.0, rf2)  # BF's inner
        + over_x(lambda x: ch(rf2, x) - ch(s, x) if wall(x) < hb else 0.0, rf2)  # the end
    )
    centroid = (moment_x / volume, moment_y / volume, 0.0)
    wide = max(rf, rf2)
    bounds = ((-wide, -rf, -(h + t) / 2), (wide, max(hb, rf), (h + t) / 2))
    return volume, area, centroid, bounds


def tee_closed_form(text: str) -> dict[str, object]:
    """The `ClosedForm` JSON of a tee program, flanged or bare, in global coordinates."""
    plane = re.search(r'cq\.Workplane\("(XY|XZ|YZ)"\)', text)
    assert plane is not None
    if "polarArray" in text:
        f = _flanged_tee(text)
        p = f.tee
        volume, area, centroid, bounds = flanged_tee_measures(f)
        shape = (
            f"a flanged tee: a flange Rf, t centred on each end of M, {len(f.centres)} bolt "
            "holes d through both, a flange rf2, t2 flush with the branch's end, each adding "
            f"elementary terms (Rf={f.rf}, t={f.t}, rf2={f.rf2}, t2={f.t2}, d={f.d}) to "
        )
    else:
        p = _tee(text)
        volume, area, centroid, bounds = tee_measures(p)
        shape = ""
    lo, hi = box_to_global(plane.group(1), bounds)
    return {
        "kind": "closed_form",
        "volume": volume,
        "area": area,
        "centroid": list(to_global(plane.group(1), centroid)),
        "bounds": [list(lo), list(hi)],
        "note": (
            shape
            + "a tee on the "
            + plane.group(1)
            + " plane, ((main cylinder R, h) united with a branch r on y from 0 to hb) "
            "cut by a branch bore s and a through bore q; volume, y moment and area "
            "are one-dimensional integrals over the cross-section and each cylinder's "
            f"surface patch (tools/cq_closed_forms.py): R={p['R']}, h={p['h']}, "
            f"r={p['r']}, hb={p['hb']}, s={p['s']}, q={p['q']}"
        ),
    }


_BELLOWS = re.compile(
    r'cq\.Workplane\("XY"\)\s*\.polyline\((\[[^\]]*\])\)\s*\.close\(\)\s*'
    r"\.revolve\(360, \(0, 0, 0\), \(0, 1, 0\)\)\s*"
    rf'(?:\.faces\(">Y"\)\.workplane\(\)\s*\.hole\({_NUMBER}\)\s*)?'
    rf'\.faces\(">Y"\)\.workplane\(\)\s*\.polarArray\({_NUMBER}, 0, 360, (\d+)\)\s*'
    rf"\.circle\({_NUMBER}\)\s*\.cutBlind\({_NUMBER}\)\s*"
    rf'\.faces\("<Y"\)\.workplane\(\)\s*\.polarArray\({_NUMBER}, 0, 360, (\d+)\)\s*'
    rf"\.circle\({_NUMBER}\)\s*\.cutBlind\({_NUMBER}\)\s*\)"
)
_PAIR = re.compile(rf"\({_NUMBER}, {_NUMBER}\)")


@dataclass(frozen=True)
class Bellows:
    """A bellows: the closed profile `pts` (x the radius, y the height, a bore D/2 already
    in place of the inner wall) turned about y, and `n` holes of radius `r` on a circle of
    radius `rp` cut from each end face: through the bottom flange (thickness `d`), and from
    the top face down to the cone `cone` = ((x_k, y_k), (R, H)) under it."""

    pts: tuple[tuple[float, float], ...]
    n: int
    rp: float
    r: float
    d: float
    cone: tuple[tuple[float, float], tuple[float, float]]


def _bellows(text: str) -> Bellows:
    """The bellows's parameters, refusing a program that is not the one shape this reads.

    The profile, counter-clockwise from the inner bottom corner: (x_in, 0), (a, 0), (R, 0),
    (R, d), (a', d), the convolutions with every y strictly between d and y_k, (x_k, y_k),
    (R, H), (a'', H), (x_in, H), closed. An optional `hole(D)` from the top widens the inner
    wall to D/2, below every other radius. The two `polarArray(rp, 0, 360, n).circle(r)
    .cutBlind(-depth)` are alike: the bottom one `d` deep, through the flange (a hole
    clear of a and a', inside R, the edge after (a', d) going inward); the top one `H -
    y_k` deep, its floor on the cone's lower end, the holes clear of a'' and x_k (so under
    the top face, over the band, is only the cone). The holes do not overlap.
    """
    m = _BELLOWS.search(text)
    if m is None:
        raise ValueError("not the bellows this tool reads")
    pts = [(_num(x), _num(y)) for x, y in _PAIR.findall(m.group(1))]
    hole, rp, n, r, top, rp2, n2, r2, bottom = m.groups()[1:]
    if (rp, n, r) != (rp2, n2, r2):
        raise ValueError("a bellows's two hole circles differ")
    if len(pts) < 10 or pts[0] != pts[-1]:
        raise ValueError("a bellows's profile is not closed")
    x_in, big_r = pts[0][0], pts[2][0]
    d, (x_k, y_k), big_h = pts[3][1], pts[-5], pts[-4][1]
    if not (
        pts[0][1] == pts[1][1] == pts[2][1] == 0.0
        and pts[3] == (big_r, d)
        and pts[4][1] == d
        and pts[-4] == (big_r, big_h)
        and pts[-3][1] == pts[-2][1] == big_h
        and pts[-2][0] == x_in
        and all(d < p[1] < y_k for p in pts[5:-5])
        and y_k < big_h
        and pts[5][0] < pts[4][0]
        and max(p[0] for p in pts) == big_r
    ):
        raise ValueError("a bellows's profile is not the shape the closed form assumes")
    if hole is not None:
        bore = _num(hole) / 2
        if not x_in < bore < min(p[0] for p in pts[1:-2]):
            raise ValueError("a bellows's bore does not only widen its inner wall")
        x_in = bore
        pts = [(x_in, 0.0), *pts[1:-2], (x_in, big_h), (x_in, 0.0)]
    elif min(p[0] for p in pts[1:-2]) <= x_in:
        raise ValueError("a bellows's inner wall is not its least radius")
    rp_, r_, count = _num(rp), _num(r), int(n)
    lo, hi = rp_ - r_, rp_ + r_
    if not (
        max(pts[1][0], pts[4][0], pts[-3][0], x_k) < lo
        and lo < big_r
        and abs(hi - big_r) > PLACEMENT_TOL
        and abs(-_num(bottom) - d) <= PLACEMENT_TOL
        and abs(big_h + _num(top) - y_k) <= PLACEMENT_TOL
    ):
        raise ValueError("a bellows's holes are not where the closed form assumes")
    if count < 2 or 2 * rp_ * math.sin(math.pi / count) <= 2 * r_:
        raise ValueError("a bellows's holes overlap or do not balance about the axis")
    area2 = sum(a[0] * b[1] - b[0] * a[1] for a, b in itertools.pairwise(pts))
    if area2 <= 0:
        raise ValueError("a bellows's profile is not counter-clockwise")
    return Bellows(tuple(pts), count, rp_, r_, d, ((x_k, y_k), (big_r, big_h)))


def bellows_measures(b: Bellows) -> tuple[float, float, Vec, Box]:
    """Volume, area, centroid and bounds of the bellows, in global coordinates.

    The revolved profile by Pappus: V0 = 2 pi sum (x_i + x_j)(x_i y_j - x_j y_i) / 6, the y
    moment 2 pi times the profile's integral of x y, A0 = pi sum (x_i + x_j) |edge| (each
    edge a cone, a cylinder or a disc). A hole may run past the rim R: what it takes is its
    disc's part inside rho < R, integrated by rho with the disc's angular width 2 phi(rho)
    at that radius, cos phi = (rho^2 + rp^2 - r^2) / (2 rho rp) (tanh-sinh, for the square
    roots at rp - r and rp + r). Each bottom hole goes through the flange: that area Ac
    times d off, its wall (the hole's circle inside rho < R) times d on, Ac taken twice
    from the end faces and the rim's arc inside the disc, 2 phi(R) R, times d from the rim.
    Each top hole is the sliver over the cone c(rho) = y_k + k (rho - x_k): depth h(rho) =
    H - c(rho) = B - k rho (0 at R, so the rim loses nothing), its volume B Ac - k I1 and
    its y moment H V - (integral of h^2) / 2, I1 and I2 the integrals of rho and rho^2
    over the part of the disc; its wall the integral of h along the hole's circle inside
    rho < R, and it takes Ac from the top face and sqrt(1 + k^2) Ac from the cone. The n
    holes balance about the axis (n >= 2).
    """
    pts, n, rp, r, d = b.pts, b.n, b.rp, b.r, b.d
    (x_k, y_k), (big_r, big_h) = b.cone
    pi = math.pi
    edges = list(itertools.pairwise(pts))
    cross = [a[0] * c[1] - c[0] * a[1] for a, c in edges]
    v0 = 2 * pi * sum((a[0] + c[0]) * w for (a, c), w in zip(edges, cross, strict=True)) / 6
    a0 = pi * sum((a[0] + c[0]) * math.dist(a, c) for a, c in edges)
    xy = sum(
        w * (a[0] * c[1] + 2 * a[0] * a[1] + 2 * c[0] * c[1] + c[0] * a[1])
        for (a, c), w in zip(edges, cross, strict=True)
    )
    m0 = 2 * pi * xy / 24

    def phi(rho: float) -> float:
        """Half the angle the hole's disc spans at radius rho about the axis."""
        return math.acos(max(-1.0, min(1.0, (rho * rho + rp * rp - r * r) / (2 * rho * rp))))

    def over_disc(power: int) -> float:
        """The integral of rho^power over the hole's disc inside rho < R."""
        return tanh_sinh(lambda rho: 2 * phi(rho) * rho ** (power + 1), rp - r, min(rp + r, big_r))

    k = (big_h - y_k) / (big_r - x_k)
    big_b = big_h - y_k + k * x_k
    # The hole's circle (rp + r cos t, r sin t) lies inside rho < R for t from t0 to pi.
    t0 = math.acos(max(-1.0, min(1.0, (big_r**2 - rp * rp - r * r) / (2 * rp * r))))

    def h_on_circle(t: float) -> float:
        return big_b - k * math.sqrt(rp * rp + r * r + 2 * rp * r * math.cos(t))

    a_c, i1, i2 = over_disc(0), over_disc(1), over_disc(2)
    wall = 2 * r * (pi - t0)
    sliver_wall = 2 * r * tanh_sinh(h_on_circle, t0, pi)
    rim = 2 * phi(big_r) * big_r if big_r < rp + r else 0.0
    sliver = big_b * a_c - k * i1
    squares = big_b * big_b * a_c - 2 * big_b * k * i1 + k * k * i2
    volume = v0 - n * (a_c * d + sliver)
    moment = m0 - n * (a_c * d * d / 2 + big_h * sliver - squares / 2)
    area = (
        a0
        + n * (wall * d - 2 * a_c - rim * d)
        + n * (sliver_wall - a_c * (1 + math.sqrt(1 + k * k)))
    )
    bounds = ((-big_r, 0.0, -big_r), (big_r, big_h, big_r))
    return volume, area, (0.0, moment / volume, 0.0), bounds


def bellows_closed_form(text: str) -> dict[str, object]:
    """The `ClosedForm` JSON of a bellows program (on XY, turned about y: global already)."""
    b = _bellows(text)
    volume, area, centroid, (lo, hi) = bellows_measures(b)
    return {
        "kind": "closed_form",
        "volume": volume,
        "area": area,
        "centroid": list(centroid),
        "bounds": [list(lo), list(hi)],
        "note": (
            "a bellows: a closed profile turned about y (Pappus), n holes r on a circle rp "
            "cut from each end, through the bottom flange d and from the top face down to "
            "the cone (x_k, y_k) to (R, H) under it, the sliver's volume, moment and wall "
            "integrals of its depth over the disc and around it (tools/cq_closed_forms.py, "
            f"bellows_measures): n={b.n}, rp={b.rp}, r={b.r}, d={b.d}, cone={b.cone}, "
            f"profile={b.pts}"
        ),
    }


_DOME = re.compile(
    rf'cq\.Workplane\("XY"\)\s*\.moveTo\(0\.0, 0\.0\)\s*'
    rf"\.lineTo\({_NUMBER}, 0\.0\)\s*\.lineTo\({_NUMBER}, {_NUMBER}\)\s*"
    rf"\.threePointArc\(\({_NUMBER}, {_NUMBER}\), \(0\.0, {_NUMBER}\)\)\s*"
    r"\.close\(\)\s*\.revolve\(360, \(0, 0, 0\), \(0, 1, 0\)\)\s*"
    rf'(?:\.faces\("<Y"\)\.workplane\(\)\s*\.circle\({_NUMBER}\)\s*'
    rf"\.cutBlind\(-{_NUMBER}\)\s*)?"
    rf'\.faces\("<Y"\)\.workplane\(\)\s*\.polarArray\({_NUMBER}, 0, 360, (\d+)\)\s*'
    rf"\.hole\({_NUMBER}\)\s*"
    rf'(?:\.faces\("<Y"\)\s*\.edges\(\)\s*\.(chamfer|fillet)\({_NUMBER}\)\s*)?\)'
)


def dome_closed_form(text: str) -> dict[str, object]:
    """Measure a drilled circular-arc dome from its meridian and cutter discs."""
    match = _DOME.search(text)
    if match is None:
        raise ValueError("not the dome this tool reads")
    r, start_r, spring, mx, my, top = map(float, match.groups()[:6])
    pocket, depth, pitch, holes, diameter, blend, size = match.groups()[6:]
    b, d, p, a, c = (float(value or 0) for value in (pocket, depth, pitch, diameter, size))
    a /= 2
    n = int(holes)
    if not (
        r == start_r
        and 0 <= c < spring < top
        and 0 <= d < spring
        and n >= 2
        and 0 < a < p * math.sin(math.pi / n)
        and p + a < r
        and 0 <= b < r
    ):
        raise ValueError("dome dimensions outside the closed form")
    if c and (
        r - b <= 2 * c
        or (b and d <= c)
        or (b and p + a + c >= b)
        or (not b and (p + a + 2 * c >= r or a + c >= p * math.sin(math.pi / n)))
    ):
        raise ValueError("dome blends meet another boundary")

    # Circumcentre relative to the arc start.
    u, v = mx - r, my - spring
    w, z = -r, top - spring
    determinant = 2 * (u * z - v * w)
    if determinant <= 0:
        raise ValueError("dome arc does not turn toward the axis")
    cx = r + ((u * u + v * v) * z - (w * w + z * z) * v) / determinant
    cy = spring + (u * (w * w + z * z) - w * (u * u + v * v)) / determinant
    radius = math.hypot(r - cx, spring - cy)
    begin = math.atan2(spring - cy, r - cx)
    end = math.atan2(top - cy, -cx)
    if not (-math.pi / 4 < begin < math.pi / 4 and math.pi / 4 < end < 3 * math.pi / 4):
        raise ValueError("dome arc does not run from the rim to the axis")

    def arc_r(t: float) -> float:
        return cx + radius * math.cos(t)

    def roof(rho: float) -> float:
        return cy + math.sqrt(radius**2 - (rho - cx) ** 2)

    def half_angle(rho: float) -> float:
        cosine = (rho**2 + p * p - a * a) / (2 * rho * p)
        return math.acos(min(1.0, max(-1.0, cosine)))

    def over_hole(fn: Callable[[float], float], upper: float) -> float:
        return tanh_sinh(lambda rho: 2 * rho * half_angle(rho) * fn(rho), p - a, upper)

    def section(t: float) -> float:
        return math.pi * arc_r(t) ** 2 * radius * math.cos(t)

    disk = math.pi * a * a
    pocket_disk = math.pi * b * b
    shared = over_hole(lambda _: 1, min(b, p + a))
    volume = math.pi * r * r * spring + tanh_sinh(section, begin, end)
    moment = math.pi * r * r * spring**2 / 2 + tanh_sinh(
        lambda t: section(t) * (cy + radius * math.sin(t)), begin, end
    )
    area = (
        math.pi * r * r
        + 2 * math.pi * r * spring
        + tanh_sinh(lambda t: 2 * math.pi * arc_r(t) * radius, begin, end)
    )
    volume -= pocket_disk * d + n * (over_hole(roof, p + a) - d * shared)
    moment -= (
        pocket_disk * d * d / 2
        + n * (over_hole(lambda rho: roof(rho) ** 2, p + a) - d * d * shared) / 2
    )
    pocket_wall = 2 * math.pi * b * d
    if p - a < b < p + a:
        pocket_wall -= n * 2 * b * half_angle(b) * d
    wall = (
        2
        * a
        * tanh_sinh(lambda t: roof(math.hypot(p + a * math.cos(t), a * math.sin(t))), 0, math.pi)
    )
    if b > p - a:
        angle = math.acos(max(-1.0, min(1.0, (p * p + a * a - b * b) / (2 * p * a))))
        wall -= 2 * a * d * angle
    roof_patch = over_hole(lambda rho: radius / (roof(rho) - cy), p + a)
    # The base and pocket floor together lose one disc per through hole.
    area += pocket_wall + n * (wall - roof_patch - disk)

    def cutback(y: float) -> float:
        return c - y if blend == "chamfer" else c - math.sqrt(y * (2 * c - y))

    for rim, sign, count in ((r, -1, 1), (b or a, 1, 1 if b else n)):

        def removed(y: float, rim: float = rim, sign: int = sign) -> float:
            e = cutback(y)
            return math.pi * e * (2 * rim + sign * e)

        volume -= count * tanh_sinh(removed, 0, c)
        moment -= count * tanh_sinh(lambda y: y * removed(y), 0, c)
        if blend == "chamfer":
            patch = 2 * math.pi * (rim + sign * c / 2) * c * math.sqrt(2)
        else:
            patch = 2 * math.pi * c * (rim * math.pi / 2 + sign * c * (math.pi / 2 - 1))
        area += count * (patch - removed(0) - 2 * math.pi * rim * c)

    extent = cx + radius if begin < 0 else r
    return {
        "kind": "closed_form",
        "volume": volume,
        "area": area,
        "centroid": [0, moment / volume, 0],
        "bounds": [[-extent, 0, -extent], [extent, top, extent]],
        "note": "Circular meridian from the three programmed points. Integrate the pocket and "
        "drill discs against the roof height, subtract their shared volume, and integrate the "
        "rim blends by revolving a line or quarter circle "
        "(tools/cq_closed_forms.py, dome_closed_form).",
    }


def _hook(text: str) -> dict[str, object]:
    """The u_bolt / j_hook parameters, refusing a program that is not that shape."""
    cyl = _cylinders(text)
    torus = re.search(
        rf"offset=cq\.Vector\(0, 0, {_NUMBER}\)[^\n]*\n\s*\.moveTo\({_NUMBER}, 0\.0\)\n\s*"
        rf"\.circle\({_NUMBER}\)\n\s*\.revolve\(180, \(0, 0, 0\), \(0, -1, 0\)\)",
        text,
    )
    box = re.search(
        rf"offset=cq\.Vector\({_NUMBER}, 0(?:\.0)?, {_NUMBER}\)[^\n]*\n\s*"
        rf"\.box\({_NUMBER}, {_NUMBER}, {_NUMBER}\)",
        text,
    )
    prisms_found = list(_PRISM.finditer(text))
    solids = len(cyl) + 1 + (box is not None) + len(prisms_found)
    if torus is None or not 1 <= len(cyl) <= 2 or 'Workplane("XY")' not in text:
        raise ValueError("not the half-torus hook this tool reads")
    if (
        text.count(".union(") != solids - 1
        or ".cut(" in text
        or text.count(".extrude(") != len(prisms_found)
    ):
        raise ValueError("a hook with a solid this tool does not read")
    z0, big_r, r = (_num(g) for g in torus.groups())
    if not big_r > r > 0:
        raise ValueError("a hook whose minor radius is not under its major")
    cylinders: list[tuple[float, float, float]] = []  # x, bottom z, top z
    for offset, height, radius in cyl:
        if radius != r or abs(abs(offset[0]) - big_r) > PLACEMENT_TOL or offset[1] != 0:
            raise ValueError("a hook cylinder off the torus's end")
        cylinders.append((offset[0], offset[2] - height / 2, offset[2] + height / 2))
    if len(cylinders) == 2 and cylinders[0][0] != -cylinders[1][0]:
        raise ValueError("two hook cylinders on one side")
    for _, low, top in cylinders:
        if not low < z0 < top:
            raise ValueError("a hook cylinder that does not run through the torus's end disc")
        if not 0 < top - z0 < 2 * math.sqrt(big_r * r):
            raise ValueError("a cylinder end outside the overlap the closed form handles")
    out: dict[str, object] = {"z0": z0, "R": big_r, "r": r, "cylinders": cylinders, "box": None}
    if box is not None:
        cx, cz, bx, by, bz = (_num(g) for g in box.groups())
        for x, low, _ in cylinders:
            if abs(x - cx) + r > bx / 2 or r > by / 2 or not low < cz + bz / 2:
                raise ValueError("a hook box that does not cover the cylinders' footprints")
        out["box"] = (cx, cz, bx, by, bz)
    out["prisms"] = [_prism(m) for m in prisms_found]
    _check_prisms(out)
    return out


# A nut under a hook's box: `extrude(e, both=True)` of a closed polygon on a plane offset
# (x, y, z), written as `polygon(n, d)` or as `moveTo(p).polyline([...]).close()`, whose lone
# `moveTo` point CadQuery drops (plans/lift-extrude-both Q2a).
_PRISM = re.compile(
    rf"offset=cq\.Vector\({_NUMBER}, {_NUMBER}, {_NUMBER}\), rotate=cq\.Vector\(0, 0, 0\)\)"
    rf"\n\s*(?:\.moveTo\({_NUMBER}, {_NUMBER}\)\n\s*\.polyline\((\[[^\n]*\])\)\n\s*\.close\(\)"
    rf"|\.polygon\((\d+), {_NUMBER}\))\n\s*\.extrude\({_NUMBER}, both=True\)"
)

Prism = tuple[list[tuple[float, float]], float, float]  # CCW vertices (global x, y), bottom, top


def _prism(m: re.Match[str]) -> Prism:
    """A nut's vertices in global x, y (counter-clockwise) and its bottom and top heights."""
    x, y, z, _, _, polyline, sides, diameter, e = m.groups()
    ox, oy, oz, depth = _num(x), _num(y), _num(z), abs(_num(e))
    local: list[tuple[float, float]]
    if polyline is not None:
        local = [(float(a), float(b)) for a, b in json.loads(polyline)]
    else:
        n, radius = int(sides), _num(diameter) / 2
        step = 2.0 * math.pi / n  # CadQuery's `Workplane.polygon`: the angle i * 2 pi / n
        local = [(radius * math.cos(step * i), radius * math.sin(step * i)) for i in range(n)]
    vertices = [(ox + a, oy + b) for a, b in local]
    if len(vertices) < 3 or depth == 0:
        raise ValueError("a hook nut that is not a prism")
    if _shoelace(vertices)[0] < 0:
        vertices.reverse()
    return vertices, oz - depth, oz + depth


def _shoelace(vertices: Sequence[tuple[float, float]]) -> tuple[float, float, float, float]:
    """A polygon's signed area, its x and y moments, and its perimeter (the shoelace formula)."""
    area = m_x = m_y = perimeter = 0.0
    for (x0, y0), (x1, y1) in zip(vertices, [*vertices[1:], vertices[0]], strict=True):
        cross = x0 * y1 - x1 * y0
        area += cross / 2
        m_x += (x0 + x1) * cross / 6
        m_y += (y0 + y1) * cross / 6
        perimeter += math.hypot(x1 - x0, y1 - y0)
    return area, m_x, m_y, perimeter


def _check_prisms(hook: dict[str, object]) -> None:
    """Refuse nuts outside the shape `hook_measures` handles.

    Each nut is a convex polygon inside the box's footprint, its top between the box's faces
    and its bottom below them, and no two nuts' footprints meet. A cylinder whose foot is below
    the box's bottom stands on a nut whose polygon holds the cylinder's axis and no vertex
    inside its disc, and which runs below the foot; its disc is then the polygon plus the
    circular segments beyond each edge, which `_segments` reads.
    """
    prisms: list[Prism] = hook["prisms"]  # type: ignore[assignment]
    if not prisms:
        return
    box: tuple[float, float, float, float, float] | None = hook["box"]  # type: ignore[assignment]
    if box is None:
        raise ValueError("a hook nut with no box above it")
    cx, cz, bx, by, bz = box
    bottom, top = cz - bz / 2, cz + bz / 2
    for vertices, low, high in prisms:
        n = len(vertices)
        for i in range(n):
            (x0, y0), (x1, y1), (x2, y2) = vertices[i], vertices[(i + 1) % n], vertices[(i + 2) % n]
            if (x1 - x0) * (y2 - y1) - (y1 - y0) * (x2 - x1) <= 0:
                raise ValueError("a hook nut that is not a convex polygon")
        if any(abs(x - cx) >= bx / 2 or abs(y) >= by / 2 for x, y in vertices):
            raise ValueError("a hook nut outside the box's footprint")
        if not (low < bottom < high < top):
            raise ValueError("a hook nut whose top is not inside the box")
    spans = sorted((min(x for x, _ in v), max(x for x, _ in v)) for v, _, _ in prisms)
    if any(a[1] >= b[0] for a, b in itertools.pairwise(spans)):
        raise ValueError("two hook nuts that may meet")
    r = float(hook["r"])  # type: ignore[arg-type]
    cylinders: list[tuple[float, float, float]] = hook["cylinders"]  # type: ignore[assignment]
    for x, low, _ in cylinders:
        under = [p for p in prisms if _inside(p[0], (x, 0.0))]
        near = [
            p for p in prisms if min(v[0] for v in p[0]) < x + r and max(v[0] for v in p[0]) > x - r
        ]
        if bottom - low <= FOOT_TOL:
            continue
        if len(under) != 1 or len(near) != 1 or not under[0][1] < low:
            raise ValueError("a hook cylinder below the box that does not stand on one nut")
        if any(math.hypot(vx - x, vy) < r for vx, vy in under[0][0]):
            raise ValueError("a nut vertex inside a hook cylinder's disc")
        _segments(under[0][0], (x, 0.0), r)


def _inside(vertices: Sequence[tuple[float, float]], point: tuple[float, float]) -> bool:
    """Whether `point` is strictly inside a counter-clockwise convex polygon."""
    n = len(vertices)
    for i in range(n):
        (x0, y0), (x1, y1) = vertices[i], vertices[(i + 1) % n]
        if (x1 - x0) * (point[1] - y0) - (y1 - y0) * (point[0] - x0) <= 0:
            return False
    return True


def _segments(
    vertices: Sequence[tuple[float, float]], centre: tuple[float, float], r: float
) -> tuple[float, float, float, float, float]:
    """What a disc (centre, r) has beyond a convex polygon holding its centre.

    Returns the area, x and y moments of the circular segments beyond the edges, the length of
    their arcs and of their chords. Each edge closer than r cuts one segment of half-angle
    `a = acos(h / r)`: area `r^2 (a - sin a cos a)`, moment `2/3 r^3 sin^3 a` along the edge's
    outward normal. The segments are disjoint when no vertex is inside the disc; a chord that
    runs past its edge's ends raises.
    """
    area = m_x = m_y = arcs = chords = 0.0
    n = len(vertices)
    for i in range(n):
        (x0, y0), (x1, y1) = vertices[i], vertices[(i + 1) % n]
        length = math.hypot(x1 - x0, y1 - y0)
        tx, ty = (x1 - x0) / length, (y1 - y0) / length
        nx, ny = ty, -tx  # outward, the polygon being counter-clockwise
        h = (x0 - centre[0]) * nx + (y0 - centre[1]) * ny
        if h >= r:
            continue
        a = math.acos(h / r)
        foot = (centre[0] - x0) * tx + (centre[1] - y0) * ty
        half = r * math.sin(a)
        if foot - half < 0 or foot + half > length:
            raise ValueError("a hook cylinder's disc crosses a nut's corner")
        seg = r * r * (a - math.sin(a) * math.cos(a))
        moment = 2 / 3 * r**3 * math.sin(a) ** 3
        area += seg
        m_x += seg * centre[0] + moment * nx
        m_y += seg * centre[1] + moment * ny
        arcs += 2 * r * a
        chords += 2 * half
    return area, m_x, m_y, arcs, chords


def _overlap_slice(big_r: float, r: float, h: float) -> tuple[float, float]:
    """Area and x moment of the cylinder (axis x = R) meeting the half torus at height h.

    The torus's section at height h is `(sqrt(x^2 + h^2) - R)^2 + y^2 < r^2`, the
    cylinder's `(x - R)^2 + y^2 < r^2`; both are centred on y = 0, so the overlap's
    half-width at x is the smaller of the two. They swap at x = R - h^2 / 4R.
    """

    def w_cyl(x: float) -> float:
        return math.sqrt(max(r * r - (x - big_r) ** 2, 0.0))

    def w_tor(x: float) -> float:
        return math.sqrt(max(r * r - (math.hypot(x, h) - big_r) ** 2, 0.0))

    x_lo = big_r - r
    x_end = math.sqrt((big_r + r) ** 2 - h * h)
    x_swap = max(big_r - h * h / (4 * big_r), x_lo)
    area = tanh_sinh(lambda x: 2 * w_cyl(x), x_lo, x_swap) + tanh_sinh(
        lambda x: 2 * w_tor(x), x_swap, x_end
    )
    moment = tanh_sinh(lambda x: 2 * x * w_cyl(x), x_lo, x_swap) + tanh_sinh(
        lambda x: 2 * x * w_tor(x), x_swap, x_end
    )
    return area, moment


def _bisect(f: Callable[[float], float], lo: float, hi: float) -> float:
    """The root of a monotone `f` on `[lo, hi]` where its signs differ, to double precision."""
    f_lo = f(lo)
    for _ in range(200):
        mid = (lo + hi) / 2
        if (f(mid) > 0) == (f_lo > 0):
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def hook_measures(p: dict[str, object]) -> tuple[float, float, Vec, Box]:
    """Volume, area, centroid and bounds of the hook in global coordinates."""
    pi = math.pi
    z0 = float(p["z0"])  # type: ignore[arg-type]
    big_r = float(p["R"])  # type: ignore[arg-type]
    r = float(p["r"])  # type: ignore[arg-type]
    cylinders: list[tuple[float, float, float]] = p["cylinders"]  # type: ignore[assignment]
    box: tuple[float, float, float, float, float] | None = p["box"]  # type: ignore[assignment]
    prisms: list[Prism] = p.get("prisms", [])  # type: ignore[assignment]
    ht = cylinders[0][2] - z0
    if any(abs(top - z0 - ht) > PLACEMENT_TOL for _, _, top in cylinders):
        raise ValueError("cylinders of different height above the torus")
    nc = len(cylinders)
    # The overlap of one cylinder with the torus: volume and moments over h in [0, ht].
    over_v = gauss(lambda h: _overlap_slice(big_r, r, h)[0], 0.0, ht)
    over_mx = gauss(lambda h: _overlap_slice(big_r, r, h)[1], 0.0, ht)
    over_mz = gauss(lambda h: (z0 + h) * _overlap_slice(big_r, r, h)[0], 0.0, ht)
    cap = _overlap_slice(big_r, r, ht)[0]

    # Surface: the torus inside a cylinder, over the minor angle phi (cos > 0 only), where
    # the torus's angle runs to the smaller of the cylinder's wall and its end height.
    def theta_wall(c: float) -> float:
        return math.acos((big_r - r * c) / (big_r + r * c))

    def theta_end(c: float) -> float:
        return math.asin(min(1.0, ht / (big_r + r * c)))

    c_swap = _bisect(lambda c: theta_wall(c) - theta_end(c), 0.0, 1.0)
    phi_swap = math.acos(c_swap)
    torus_in = 2 * (
        tanh_sinh(lambda f: r * (big_r + r * math.cos(f)) * theta_end(math.cos(f)), 0, phi_swap)
        + tanh_sinh(
            lambda f: r * (big_r + r * math.cos(f)) * theta_wall(math.cos(f)), phi_swap, pi / 2
        )
    )
    # The cylinder's wall inside the torus: on its inner side, up to 2 sqrt(R r |cos|) or ht.
    a_swap = math.acos(min(1.0, ht * ht / (4 * big_r * r)))
    wall_in = 2 * (
        tanh_sinh(lambda a: r * ht, 0, a_swap)
        + tanh_sinh(lambda a: r * 2 * math.sqrt(big_r * r * math.cos(a)), a_swap, pi / 2)
    )
    v_torus = pi * r * r * pi * big_r
    m_torus_z = z0 * v_torus + 2 * pi * r * r * (big_r**2 + r * r / 4)  # x moment is 0
    # The torus's lateral area, its free end discs (a cylinder covers the others), and, per
    # cylinder, the part of its end cap outside the torus.
    area = 2 * pi * pi * r * big_r + (2 - nc) * pi * r * r
    volume = v_torus
    m_x = m_y = 0.0
    m_z = m_torus_z
    box_top = 0.0
    if box is not None:
        cx, cz, bx, by, bz = box
        box_top = cz + bz / 2
        volume += bx * by * bz
        m_x += bx * by * bz * cx
        m_z += bx * by * bz * cz
        area += 2 * (bx * by + bx * bz + by * bz)
        # A nut adds its prism below the box: its walls, and its bottom in place of the patch
        # of the box's bottom face it covers.
        for vertices, low, _ in prisms:
            a, ax, ay, perimeter = _shoelace(vertices)
            depth = cz - bz / 2 - low
            volume += a * depth
            m_x += ax * depth
            m_y += ay * depth
            m_z += a * depth * (cz - bz / 2 + low) / 2
            area += perimeter * depth
    for x, low, top in cylinders:
        sign = 1.0 if x > 0 else -1.0
        v_cyl = pi * r * r * (top - low)
        volume += v_cyl - over_v
        m_x += v_cyl * x - sign * over_mx
        m_z += v_cyl * (top + low) / 2 - over_mz
        area += (
            2 * pi * r * (top - (low if box is None else box_top))
            - wall_in
            - torus_in
            + (pi * r * r - cap)
        )
        if box is None:
            area += pi * r * r  # the free foot
        else:
            bottom = box[1] - box[4] / 2
            # A foot level with the box's bottom face (to FOOT_TOL) leaves no cylinder wall or
            # disc outside the box; one below it leaves a band of wall, its disc taking the
            # place of the footprint it cuts from the box's bottom face.
            below = bottom - low if bottom - low > FOOT_TOL else 0.0
            nut = [v for v, _, _ in prisms if _inside(v, (x, 0.0))]
            kept = max(low, bottom) if below and not nut else low
            volume -= pi * r * r * (box_top - kept)
            m_x -= pi * r * r * (box_top - kept) * x
            m_z -= pi * r * r * (box_top - kept) * (box_top + kept) / 2
            area -= pi * r * r  # the footprint on the box's top face
            if below and nut:
                # Standing on a nut, the band below the box is the nut's prism plus the disc's
                # segments beyond its edges: their arcs of wall less the nut's chords of wall.
                seg, sx, sy, arcs, chords = _segments(nut[0], (x, 0.0), r)
                volume += seg * below
                m_x += sx * below
                m_y += sy * below
                m_z += seg * below * (low + bottom) / 2
                area += (arcs - chords) * below
            elif below:
                area += 2 * pi * r * below
    centroid = (m_x / volume, m_y / volume, m_z / volume)
    low_all = [low for _, low, _ in cylinders] + [low for _, low, _ in prisms]
    top_all = [top for _, _, top in cylinders]
    xs = [(-(big_r + r), big_r + r)]
    ys = [(-r, r)]
    zs = [(z0, z0 + big_r + r), (min(low_all), max(top_all))]
    if box is not None:
        cx, cz, bx, by, bz = box
        xs.append((cx - bx / 2, cx + bx / 2))
        ys.append((-by / 2, by / 2))
        zs.append((cz - bz / 2, cz + bz / 2))
    bounds = (
        (min(a for a, _ in xs), min(a for a, _ in ys), min(a for a, _ in zs)),
        (max(b for _, b in xs), max(b for _, b in ys), max(b for _, b in zs)),
    )
    return volume, area, centroid, bounds


def hook_closed_form(text: str) -> dict[str, object]:
    """The `ClosedForm` JSON of a u_bolt or j_hook program."""
    p = _hook(text)
    volume, area, centroid, bounds = hook_measures(p)
    return {
        "kind": "closed_form",
        "volume": volume,
        "area": area,
        "centroid": list(centroid),
        "bounds": [list(bounds[0]), list(bounds[1])],
        "note": (
            "vertical cylinders joined to a half torus (Pappus: V = pi r^2 pi R) at its end "
            "disc, with an optional box under them; the overlap of a cylinder with the torus "
            "and the surface patches either side of it are integrals "
            f"(tools/cq_closed_forms.py): z0={p['z0']}, R={p['R']}, r={p['r']}, "
            f"cylinders={p['cylinders']}, box={p['box']}"
            + (
                ", and a polygon nut's prism under the box (shoelace area A and perimeter P: "
                f"V = A d, S = P d): {p['prisms']}"
                if p["prisms"]
                else ""
            )
        ),
    }


# The one CAD-Recode program whose row nothing classes: two cylinders crossing, read by hand
# from its text (`r = w0.workplane(offset=75/2).moveTo(0,-42).cylinder(75,8).union(
# w1.workplane(offset=85/2).moveTo(-31,0).cylinder(85,5))` on `ZX` and `YZ` planes with
# origins (0,-37,0) and (-35,0,0)) and keyed by its SHA-256, so no other text takes its form.
CROSSING = {
    "ed05e8ba373debeff45d68143bea25216f0bc9aff0523aba814e6a0a8598f0c2": {
        "a": 8.0,  # A: axis along y through (x = xa, z = 0), radius a, from ya0 to ya1
        "xa": -42.0,
        "ya0": -37.0,
        "ya1": 38.0,
        "b": 5.0,  # B: axis along x through (y = yb, z = 0), radius b, from xb0 to xb1
        "yb": -31.0,
        "xb0": -35.0,
        "xb1": 50.0,
    }
}


def crossing_measures(p: dict[str, float]) -> tuple[float, float, Vec, Box]:
    """Volume, area, centroid and bounds of a cylinder A crossed by a cylinder B.

    B starts inside A's width (at `u0 = xb0 - xa` from A's axis, `0 < u0 < a`), leaves A's
    far side, and keeps within A's length; the strip `|z| < c(u)`, `c = sqrt(a^2 - u^2)`,
    that A leaves of B's disc has area `2 (c sqrt(b^2 - c^2) + b^2 asin(c / b))`.
    """
    a, xa, ya0, ya1 = p["a"], p["xa"], p["ya0"], p["ya1"]
    b, yb, xb0, xb1 = p["b"], p["yb"], p["xb0"], p["xb1"]
    pi = math.pi
    u0 = xb0 - xa
    c0 = math.sqrt(a * a - u0 * u0)
    if not (0 < u0 < a and c0 < b and xb1 > xa + a and ya0 < yb - b and yb + b < ya1):
        raise ValueError("crossing cylinders outside the arrangement the closed form handles")

    def strip(c: float) -> float:
        return 2 * (c * math.sqrt(max(b * b - c * c, 0.0)) + b * b * math.asin(c / b))

    def cut(u: float) -> float:
        return strip(math.sqrt(max(a * a - u * u, 0.0)))

    over = tanh_sinh(cut, u0, a)
    over_x = tanh_sinh(lambda u: (xa + u) * cut(u), u0, a)
    v_a, v_b = pi * a * a * (ya1 - ya0), pi * b * b * (xb1 - xb0)
    volume = v_a + v_b - over
    m_x = v_a * xa + v_b * (xb0 + xb1) / 2 - over_x
    m_y = v_a * (ya0 + ya1) / 2 + v_b * yb - over * yb
    phi0 = math.acos(u0 / a)
    a_in_b = tanh_sinh(
        lambda f: 2 * a * math.sqrt(max(b * b - (a * math.sin(f)) ** 2, 0.0)), -phi0, phi0
    )
    psi0 = math.asin(c0 / b)
    b_in_a = 2 * tanh_sinh(
        lambda s: b * (math.sqrt(max(a * a - (b * math.sin(s)) ** 2, 0.0)) - u0), -psi0, psi0
    )
    area = (
        2 * pi * a * (ya1 - ya0)
        - a_in_b
        + 2 * pi * a * a
        + 2 * pi * b * (xb1 - xb0)
        - b_in_a
        + 2 * pi * b * b
        - strip(c0)
    )
    bounds = (
        (min(xa - a, xb0), min(ya0, yb - b), -max(a, b)),
        (max(xa + a, xb1), max(ya1, yb + b), max(a, b)),
    )
    return volume, area, (m_x / volume, m_y / volume, 0.0), bounds


def crossing_closed_form(sha256: str) -> dict[str, object]:
    """The `ClosedForm` JSON of the CAD-Recode program `sha256` names."""
    p = CROSSING[sha256]
    volume, area, centroid, bounds = crossing_measures(p)
    return {
        "kind": "closed_form",
        "volume": volume,
        "area": area,
        "centroid": list(centroid),
        "bounds": [list(bounds[0]), list(bounds[1])],
        "note": (
            "two cylinders crossing: A (r 8, along y from -37 to 38 at x = -42) and B (r 5, "
            "along x from -35 to 50 at y = -31) overlap only where B's first end sits inside "
            "A's width; volume, moments and the surface patches inside the other cylinder are "
            f"one-dimensional integrals (tools/cq_closed_forms.py, crossing_measures): {p}"
        ),
    }


# The one BenchCAD `shaft_collar` program a closed form clears: a cylinder bored through, both
# top rims chamfered (`edges(">Z")` takes the outer and the bore circle), then cut three times
# by one and the same cylinder: CadQuery's `transformed(rotate=Vector(90, 0, 120))` turns the
# plane about its own, already turned, z, which is the cylinder's axis, so the 120 and 240
# cuts repeat the first. Keyed by SHA-256, so no other text takes its form. The collar's
# axis is z, centred on the origin; the cut is a cylinder of radius `a` along y through
# (x = 0, z = `h / 2`), the top plane, so its half under the top removes a tunnel from each wall.
COLLARS = {
    "eb1b3b2ba69e9d1f5000933ee659038b7faba3e5dbd1ef01fac0ff10925f6119": {
        "h": 16.55,  # height, z from -h / 2 to h / 2
        "r": 18.915,  # outer radius
        "bore": 23.64,  # bore diameter
        "c": 2.13,  # chamfer of the outer and the bore rim at the top
        "a": 1.18,  # radius of the cross cylinder, under c so it cuts the cones only
    }
}


def collar_measures(p: dict[str, float]) -> tuple[float, float, Vec, Box]:
    """Volume, area, centroid and bounds of a chamfered collar crossed by a tunnel.

    With `d` the depth under the top face, the ring at `d` is `[ri(d), ro(d)]` in radius, the
    chamfers' cones making `ro = r - (c - d)` and `ri = bore / 2 + (c - d)` for `d < c`. The
    tunnel is `t^2 + d^2 <= a^2` (`t` across, along y), cut through both walls: in each, its
    length at `(t, d)` is `sqrt(ro^2 - t^2) - sqrt(ri^2 - t^2)`. The volume and the z moment
    are integrals over `d` of the ring less the tunnel; the area is the ring's six faces
    (two planes, two cylinders, two cones) less the tunnel's opening in the top plane and in
    each cone (`dA = sqrt(1 + (t^2 + r^2 r'^2) / y^2) dt dd` on a cone `y = sqrt(r^2 - t^2)`),
    plus the tunnel's wall (`a` times its length, around the half circle).
    """
    h, r, ri0, c, a = p["h"], p["r"], p["bore"] / 2, p["c"], p["a"]
    top = h / 2
    pi = math.pi
    if not (0 < a < c < min(h, r - ri0) / 2 and ri0 > a):
        raise ValueError("a collar outside the arrangement the closed form handles")

    def radii(d: float) -> tuple[float, float]:
        k = max(c - d, 0.0)
        return r - k, ri0 + k

    def ring(d: float) -> float:
        out, inn = radii(d)
        return pi * (out * out - inn * inn)

    def length(t: float, d: float) -> float:
        out, inn = radii(d)
        return math.sqrt(out * out - t * t) - math.sqrt(inn * inn - t * t)

    def across(f: Callable[[float, float], float]) -> Callable[[float], float]:
        def at(d: float) -> float:
            w = math.sqrt(max(a * a - d * d, 0.0))
            return tanh_sinh(lambda t: f(t, d), -w, w)

        return at

    tunnel = across(length)
    v_ring = tanh_sinh(ring, 0, c) + ring(c) * (h - c)
    m_ring = tanh_sinh(lambda d: (top - d) * ring(d), 0, c) + tanh_sinh(
        lambda d: (top - d) * ring(d), c, h
    )
    v_tunnel = tanh_sinh(tunnel, 0, a)
    m_tunnel = tanh_sinh(lambda d: (top - d) * tunnel(d), 0, a)
    volume = v_ring - 2 * v_tunnel
    z_moment = m_ring - 2 * m_tunnel
    out0, in0 = radii(0.0)

    def cone(outer: bool) -> Callable[[float, float], float]:
        def element(t: float, d: float) -> float:
            rad = r - c + d if outer else ri0 + c - d
            y2 = rad * rad - t * t
            return math.sqrt(1 + (t * t + rad * rad) / y2)

        return element

    s_ring = (
        pi * (out0 * out0 - in0 * in0)  # the top annulus
        + pi * (r * r - ri0 * ri0)  # the bottom
        + 2 * pi * (r + ri0) * (h - c)  # the two cylinders
        + pi * (2 * r - c) * c * math.sqrt(2)  # the outer cone
        + pi * (2 * ri0 + c) * c * math.sqrt(2)  # the bore's
    )
    opening = tanh_sinh(
        lambda t: math.sqrt(out0 * out0 - t * t) - math.sqrt(in0 * in0 - t * t), -a, a
    )
    cones = tanh_sinh(across(cone(True)), 0, a) + tanh_sinh(across(cone(False)), 0, a)
    wall = tanh_sinh(lambda q: a * length(a * math.cos(q), a * math.sin(q)), 0, pi)
    area = s_ring - 2 * (opening + cones) + 2 * wall
    bounds = ((-r, -r, -top), (r, r, top))
    return volume, area, (0.0, 0.0, z_moment / volume), bounds


def collar_closed_form(sha256: str) -> dict[str, object]:
    """The `ClosedForm` JSON of the `shaft_collar` program `sha256` names."""
    p = COLLARS[sha256]
    volume, area, centroid, bounds = collar_measures(p)
    return {
        "kind": "closed_form",
        "volume": volume,
        "area": area,
        "centroid": list(centroid),
        "bounds": [list(bounds[0]), list(bounds[1])],
        "note": (
            "a collar bored through, both top rims chamfered, a cross cylinder along y through "
            "the top plane cutting a tunnel in each wall (the program's three cuts are one: "
            "the plane's z turn leaves the cylinder's axis where it was); volume, z moment and "
            "areas are one- and two-dimensional integrals over the tunnel's cross-section "
            f"(tools/cq_closed_forms.py, collar_measures): {p}"
        ),
    }


# --- A spacer ring slotted after its blend ------------------------------------------------
#
# A ring on the `YZ` plane (a cylinder or a circle extruded, bored through by `hole`), its four
# rim circles filleted, then cut by a box across its wall: the strip `|z| < w` of the +y side,
# from inside the bore to past the rim, and axially from the bottom face up to `hi` (the box's
# top, through the whole ring or inside the outer cylinder's straight part). With `a` the
# axial distance from the bottom face, `rho` the radius and `c(rho)` how far a fillet takes the
# profile in from the flat face (0 on the straight part), the ring's column at `rho` is
# `[c, h - c]`, the strip's polar element is `rho d(rho) d(phi)` over `|phi| < asin(w / rho)`,
# and every measure is a one-dimensional integral over `rho`.

_RING = re.compile(
    rf'^import cadquery as cq\n\nresult = \(\n    cq\.Workplane\("YZ"\)\n'
    rf"    (?:\.cylinder\({_NUMBER}, {_NUMBER}\)"
    rf"|\.circle\({_NUMBER}\)\n    \.extrude\({_NUMBER}\))\n"
    rf'    \.faces\(">X"\)\.workplane\(\)\n'
    rf"    (?:\.hole\({_NUMBER}\)|\.circle\({_NUMBER}\)\n    \.cutThruAll\(\))\n"
    rf'    \.edges\(">Z or <Z"\)\n    \.fillet\({_NUMBER}\)\n'
    rf"    \.cut\(\n        cq\.Workplane\(\"YZ\"\)\n"
    rf"            \.transformed\(offset=cq\.Vector\({_NUMBER}, 0\.0, 0\.0\), "
    rf"rotate=cq\.Vector\(0, 0, 0\)\)\n"
    rf"            \.box\({_NUMBER}, {_NUMBER}, {_NUMBER}\)\n    \)\n\)\n\n"
    rf"# Export\nshow_object\(result\)\n?$"
)


@dataclass(frozen=True)
class SlottedRing:
    """A filleted ring (outer radius `big`, bore radius `small`, height `h`, fillet `f`) whose
    bottom face is at `bottom` along x, slotted by a strip of half-width `w` that reaches
    axially from the bottom face to `hi` above it and across from `y0` to `y1` along y."""

    big: float
    small: float
    h: float
    f: float
    bottom: float
    w: float
    hi: float
    y0: float
    y1: float


def _slotted_ring(text: str) -> SlottedRing:
    m = _RING.match(text)
    if m is None:
        raise ValueError("not a filleted ring slotted across its wall")
    g = m.groups()
    if g[0] is not None:  # `.cylinder(h, r)`: centred on the plane
        h, big, bottom = _num(g[0]), _num(g[1]), -_num(g[0]) / 2
    else:  # `.circle(r).extrude(h)`: from the plane along +x
        h, big, bottom = _num(g[3]), _num(g[2]), 0.0
    bore = _num(g[4]) / 2 if g[4] is not None else _num(g[5])
    f, y_centre, y_len, z_len, x_len = (_num(v) for v in g[6:11])
    ring = SlottedRing(
        big=big,
        small=bore,
        h=h,
        f=f,
        bottom=bottom,
        w=z_len / 2,
        hi=x_len / 2 - bottom,
        y0=y_centre - y_len / 2,
        y1=y_centre + y_len / 2,
    )
    lo = -x_len / 2 - bottom
    clear = math.sqrt(ring.small**2 - ring.w**2) if ring.w < ring.small else 0.0
    if not (
        0 < f < h / 2
        and f < big - bore - f
        and ring.w < ring.small
        and 0 < ring.y0 < clear
        and ring.y1 > big
        and lo <= 0
        and ring.hi >= f
    ):
        raise ValueError("a slotted ring outside the arrangement the closed form handles")
    return ring


def slotted_ring_measures(p: SlottedRing) -> tuple[float, float, Vec, Box]:
    """Volume, area, centroid and bounds of a `SlottedRing`, each a one-dimensional integral
    over the radius (the strip's `phi` range is `2 asin(w / rho)` and its moment along y
    `2 w` per unit of `rho`, whatever `rho`); the walls of the cut are `g rho / sqrt(rho^2 -
    w^2)` integrals and its floor, where the cut stops inside the ring, an annulus's strip."""
    big, r, h, f, w, hi = p.big, p.small, p.h, p.f, p.w, p.hi
    pi = math.pi
    through = hi >= h
    top_angle = pi / 2 if through else math.asin(max(0.0, (hi - (h - f)) / f))
    floor_inset = f * (1 - math.cos(top_angle)) if not through else 0.0
    cuts = [r, r + f, big - f, big]
    if floor_inset:
        cuts.extend((r + floor_inset, big - floor_inset))

    def over(g: Callable[[float], float], lo: float = r, up: float = big) -> float:
        edges = sorted({lo, up, *(c for c in cuts if lo < c < up)})
        return sum(tanh_sinh(g, a, b) for a, b in itertools.pairwise(edges))

    def turn(rho: float) -> float:  # how far the fillet takes the profile in from a flat face
        s = min(rho - r, big - rho)
        return f - math.sqrt(f * f - (f - s) ** 2) if s < f else 0.0

    def top(rho: float) -> float:  # the cut's upper end in a column
        return h - turn(rho) if through else min(h - turn(rho), hi)

    def column(rho: float) -> float:  # what the cut takes of a column
        return top(rho) - turn(rho)

    def arc(rho: float) -> float:  # the strip's arc at radius rho
        return 2 * rho * math.asin(w / rho)

    ring_v = over(lambda rho: 2 * pi * rho * (h - 2 * turn(rho)))
    cut_v = over(lambda rho: column(rho) * arc(rho))
    cut_x = over(lambda rho: column(rho) * rho * 2 * w)
    cut_a = over(lambda rho: arc(rho) * (top(rho) ** 2 - turn(rho) ** 2) / 2)
    volume = ring_v - cut_v

    ring_a = (
        2 * pi * (big * (h - 2 * f) + r * (h - 2 * f))
        + 2 * pi * ((big - f) ** 2 - (r + f) ** 2)
        + 4 * pi * f * ((r + f) * pi / 2 - f + (big - f) * pi / 2 + f)
    )

    def wedge(angle: float) -> float:
        return tanh_sinh(lambda t: arc(r + f - f * math.cos(t)) * f, 0.0, angle) + tanh_sinh(
            lambda t: arc(big - f + f * math.cos(t)) * f, 0.0, angle
        )

    lower_wedge = wedge(pi / 2)
    flat = over(arc, r + f, big - f)
    reach = min(hi, h - f) - f
    taken = (
        flat
        + (2 * big * math.asin(w / big) + 2 * r * math.asin(w / r)) * reach
        + lower_wedge
        + ((flat + lower_wedge) if through else wedge(top_angle))
    )
    walls = 2 * over(lambda rho: column(rho) * rho / math.sqrt(rho * rho - w * w))
    floor = 0.0 if through else over(arc, r + floor_inset, big - floor_inset)
    area = ring_a - taken + walls + floor

    centroid = (
        p.bottom + (ring_v * h / 2 - cut_a) / volume,
        -cut_x / volume,
        0.0,
    )
    side = math.sqrt(big * big - w * w)
    y_hi = side if through else max(side, big - floor_inset)
    bounds = ((p.bottom, -big, -big), (p.bottom + h, y_hi, big))
    return volume, area, centroid, bounds


def slotted_ring_closed_form(text: str) -> dict[str, object]:
    """The `ClosedForm` JSON of a spacer_ring program of the form `_RING` reads."""
    ring = _slotted_ring(text)
    volume, area, centroid, bounds = slotted_ring_measures(ring)
    return {
        "kind": "closed_form",
        "volume": volume,
        "area": area,
        "centroid": list(centroid),
        "bounds": [list(bounds[0]), list(bounds[1])],
        "note": (
            "a ring, bored and filleted at its four rim circles, cut across its wall by a box "
            "(the strip |z| < w, radially through, axially from the bottom face to the box's "
            "top): each measure is a one-dimensional integral over the radius of the column "
            "the cut takes (g(rho) over the strip's arc 2 rho asin(w / rho)), its walls and its "
            f"floor (tools/cq_closed_forms.py, slotted_ring_measures): {ring}"
        ),
    }


# --- A double sprocket: a hub between two chamfered tooth plates ---------------------------
#
# A hub (a circle of radius `hub` extruded `length` along the plane's normal from the plane), two
# plates (one polygon, `polyline(...).close().extrude(w)`, at the plane and `offset` above it,
# each chamfered by `c` at both ends), united, and a `hole` of diameter `d` along the axis through
# all. A plate's
# chamfer along a polygon of perimeter `P` and area `A`, whose vertex `v` turns by `alpha_v`
# (positive where convex), is mitred (the planes of two chamfers meet in a line): it takes
# `c^2 P / 2 - c^3 / 3 sum tan(alpha_v / 2)` of volume, leaves a flat face of area
# `A - c P + c^2 sum tan(alpha_v / 2)` (the polygon offset in by `c`, a mitre) and, on the side of
# each edge, a slanted face `sqrt(2) c (L - c (t_v + t_w) / 2)`; the hub meets the plates inside
# the flat faces, so it only adds its own side, its top annulus and the bore.

_SPROCKET = re.compile(
    r'^import cadquery as cq\n\nresult = \(\n    cq\.Workplane\("(YZ|XY|XZ)"\)\n'
    rf"    \.circle\({_NUMBER}\)\n    \.extrude\({_NUMBER}\)\n"
    r"    \.union\(\n        cq\.Workplane\(\"\1\"\)\n"
    r"            \.polyline\((\[.*?\])\)\n            \.close\(\)\n"
    rf"            \.extrude\({_NUMBER}\)\n"
    rf'            \.edges\("(>[XYZ])"\)\n            \.chamfer\({_NUMBER}\)\n'
    rf'            \.edges\("(<[XYZ])"\)\n            \.chamfer\({_NUMBER}\)\n    \)\n'
    r"    \.union\(\n        cq\.Workplane\(\"\1\"\)\n"
    rf"            \.workplane\(offset={_NUMBER}\)\n"
    r"            \.polyline\((\[.*?\])\)\n            \.close\(\)\n"
    rf"            \.extrude\({_NUMBER}\)\n"
    rf'            \.edges\("(>[XYZ])"\)\n            \.chamfer\({_NUMBER}\)\n'
    rf'            \.edges\("(<[XYZ])"\)\n            \.chamfer\({_NUMBER}\)\n    \)\n'
    rf'    \.faces\("(?P<bore_face>>[XYZ])"\)\.workplane\(\)\n    \.hole\({_NUMBER}\)\n'
    rf'(?:    \.faces\("(?P=bore_face)"\)\.workplane\(\)\n'
    rf"    \.center\({_NUMBER}, {_NUMBER}\)\n    \.rect\({_NUMBER}, {_NUMBER}\)\n"
    r"    \.cutThruAll\(\)\n)?\)\n\n"
    r"# Export\nshow_object\(result\)\n?$",
    re.S,
)
_POINT = re.compile(rf"\({_NUMBER}, {_NUMBER}\)")


@dataclass(frozen=True)
class Sprocket:
    """A double sprocket along `axis` (0 for `YZ`, 2 for `XY`, 1 for `XZ`, whose normal is -y so
    the part lies below y = 0): hub radius `hub` and length
    `length`, two plates of outline `outline` (the plane's two other axes in order), thickness
    `w` and chamfer `c`, the second at `offset`, and a bore of radius `bore`.
    `keyway` gives the half-width and reach of a rectangular through cut in the bore."""

    axis: int
    hub: float
    length: float
    outline: tuple[tuple[float, float], ...]
    w: float
    c: float
    offset: float
    bore: float
    keyway: tuple[float, float] | None = None


def _sprocket(text: str) -> Sprocket:
    m = _SPROCKET.match(text)
    if m is None:
        raise ValueError("not a double sprocket")
    g = m.groups()
    plane = g[0]
    outline = tuple((_num(a), _num(b)) for a, b in _POINT.findall(g[3]))
    if g[3] != g[10] or len(outline) < 3:
        raise ValueError("a sprocket whose two plates are not one outline")
    axis_name = {"YZ": "X", "XY": "Z", "XZ": "Y"}[plane]
    axis_up, axis_low = f">{axis_name}", f"<{axis_name}"
    if {g[5], g[12], g[16]} != {axis_up} or {g[7], g[14]} != {axis_low}:
        raise ValueError("a sprocket whose selectors are not along its axis")
    values = [_num(g[i]) for i in (1, 2, 4, 6, 8, 9, 11, 13, 15, 17)]
    hub, length, w, c1, c2, offset, w2, c3, c4, bore = values
    if not (w == w2 and c1 == c2 == c3 == c4):
        raise ValueError("a sprocket whose two plates differ")
    keyway = None
    if g[18] is not None:
        u, v, width, reach = (_num(value) for value in g[18:22])
        if u != 0.0 or v != reach / 2:
            raise ValueError("a sprocket keyway whose rectangle starts off the bore axis")
        keyway = (width / 2, reach)
    return Sprocket(
        {"YZ": 0, "XZ": 1, "XY": 2}[plane], hub, length, outline, w, c1, offset, bore / 2, keyway
    )


def _turns(
    outline: Sequence[tuple[float, float]],
) -> tuple[float, float, list[float], list[float]]:
    """The polygon's area and perimeter, each vertex's turning angle (convex positive) and each
    edge's length."""
    n = len(outline)
    twice = sum(
        outline[i][0] * outline[(i + 1) % n][1] - outline[(i + 1) % n][0] * outline[i][1]
        for i in range(n)
    )
    sign = 1.0 if twice > 0 else -1.0
    lengths = [math.dist(outline[i], outline[(i + 1) % n]) for i in range(n)]
    turns = []
    for i in range(n):
        a, b, c = outline[i - 1], outline[i], outline[(i + 1) % n]
        u = (b[0] - a[0], b[1] - a[1])
        v = (c[0] - b[0], c[1] - b[1])
        turns.append(sign * math.atan2(u[0] * v[1] - u[1] * v[0], u[0] * v[0] + u[1] * v[1]))
    return abs(twice) / 2, sum(lengths), turns, lengths


def _keyway_cut(
    bore: float, keyway: tuple[float, float], clearance: float
) -> tuple[float, float, float]:
    """The area and first moment removed beyond the bore, and the perimeter added."""
    a, reach = keyway
    if not (0 < a < bore < reach and math.hypot(a, reach) < clearance):
        raise ValueError("a sprocket keyway outside the arrangement the closed form handles")
    # Integrate the rectangle above the circle from -a to +a.
    edge = math.sqrt(bore * bore - a * a)
    angle = math.asin(a / bore)
    area = 2 * a * reach - a * edge - bore * bore * angle
    moment = a * (reach * reach - bore * bore) + a**3 / 3
    perimeter = 2 * (a + reach - edge - bore * angle)
    return area, moment, perimeter


def sprocket_measures(s: Sprocket) -> tuple[float, float, Vec, Box]:
    """Volume, area, centroid and bounds of a `Sprocket` by the plate polygon's mitred chamfer
    (the header's formulas) and the hub's cylinders; a part outside what they hold raises
    `ValueError`: a plate not wholly above its chamfers, the hub touching a chamfer, a bore
    wider than the hub, plates that meet or reach past the hub, a chamfer that overruns an edge.
    A hub ending inside the second plate (`length` between `offset` and `offset + w`) is the
    same solid as one ending flush with it, as the flat face of the plate covers the hub's end
    disc: it is worked out as the flush one."""
    n = len(s.outline)
    area, perimeter, turns, lengths = _turns(s.outline)
    tans = [math.tan(a / 2) for a in turns]
    c, w, hub, bore = s.c, s.w, s.hub, s.bore
    length = max(s.length, s.offset + w)  # a hub ending inside the second plate is buried in it
    near = min(
        _segment_distance(s.outline[i], s.outline[(i + 1) % n]) for i in range(n)
    )  # the outline's distance from the axis
    if not (
        c > 0
        and w > 2 * c
        and 0 < bore < hub < near - c
        and s.offset > w
        and s.offset < s.length
        and all(lengths[i] > c * (abs(tans[i]) + abs(tans[(i + 1) % n])) for i in range(n))
    ):
        raise ValueError("a sprocket outside the arrangement the closed form handles")
    pi = math.pi
    sum_tan = sum(tans)
    cut = c * c * perimeter / 2 - c**3 / 3 * sum_tan  # the volume a chamfer takes at one end
    plate = area * w - 2 * cut
    outside = plate - pi * hub * hub * w
    volume = pi * hub * hub * length + 2 * outside - pi * bore * bore * length
    moment = (
        pi * hub * hub * length * length / 2
        + outside * (w / 2)
        + outside * (s.offset + w / 2)
        - pi * bore * bore * length * length / 2
    )
    flat = area - c * perimeter + c * c * sum_tan
    slant = math.sqrt(2) * c * (perimeter - c * sum_tan)
    one = 2 * flat + perimeter * (w - 2 * c) + 2 * slant
    total = (
        2 * one
        - 3 * pi * hub * hub
        + pi * (hub * hub - bore * bore)
        + 2 * pi * hub * (length - 2 * w)
        + 2 * pi * bore * length
        - pi * bore * bore
    )
    # The plate's transverse moment: its layers are the outline offset inward by the chamfer's
    # remaining leg, a mitred polygon whose first moment is a cubic in the offset; the hub, its
    # overlap with the plates and the bore are centred on the axis and add none.
    m0 = _offset_moment(s.outline, 0.0)

    def lost(k: int) -> Callable[[float], float]:
        return lambda d: m0[k] - _offset_moment(s.outline, d)[k]

    taken = [gauss(lost(k), 0.0, c) for k in range(2)]
    across_moment = [2 * (m0[k] * w - 2 * taken[k]) for k in range(2)]
    if s.keyway is not None:
        extra, v_moment, wall = _keyway_cut(bore, s.keyway, hub)
        volume -= extra * length
        moment -= extra * length * length / 2
        total += wall * length - 2 * extra
        across_moment[1] -= v_moment * length
    across = [value / volume for value in across_moment]
    xs = [p[0] for p in s.outline]
    ys = [p[1] for p in s.outline]
    low = [min(xs), min(ys)]
    high = [max(xs), max(ys)]
    if s.axis == 0:
        lo: Vec = (0.0, low[0], low[1])
        hi: Vec = (length, high[0], high[1])
        centroid: Vec = (moment / volume, across[0], across[1])
    elif s.axis == 1:
        lo = (low[0], -length, low[1])
        hi = (high[0], 0.0, high[1])
        centroid = (across[0], -moment / volume, across[1])
    else:
        lo = (low[0], low[1], 0.0)
        hi = (high[0], high[1], length)
        centroid = (across[0], across[1], moment / volume)
    return volume, total, centroid, (lo, hi)


def _offset_outline(
    outline: Sequence[tuple[float, float]], delta: float
) -> list[tuple[float, float]]:
    """The outline offset inward by `delta` with mitred corners, as `_offset_moment` moves it."""
    n = len(outline)
    twice = sum(
        outline[i][0] * outline[(i + 1) % n][1] - outline[(i + 1) % n][0] * outline[i][1]
        for i in range(n)
    )
    side = 1.0 if twice > 0 else -1.0
    normals = []
    for i in range(n):
        dx = outline[(i + 1) % n][0] - outline[i][0]
        dy = outline[(i + 1) % n][1] - outline[i][1]
        length = math.hypot(dx, dy)
        normals.append((-side * dy / length, side * dx / length))
    moved = []
    for i in range(n):
        a, b = normals[i - 1], normals[i]
        scale = delta / (1 + a[0] * b[0] + a[1] * b[1])
        moved.append((outline[i][0] + scale * (a[0] + b[0]), outline[i][1] + scale * (a[1] + b[1])))
    return moved


def _simple(polygon: Sequence[tuple[float, float]]) -> bool:
    """Whether no two non-adjacent edges of a closed polygon meet."""
    n = len(polygon)

    def cross(o: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    for i in range(n):
        a, b = polygon[i], polygon[(i + 1) % n]
        for j in range(i + 2, n):
            if i == 0 and j == n - 1:
                continue
            p, q = polygon[j], polygon[(j + 1) % n]
            if (
                cross(a, b, p) * cross(a, b, q) <= 0
                and cross(p, q, a) * cross(p, q, b) <= 0
                and min(a[0], b[0]) <= max(p[0], q[0])
                and min(p[0], q[0]) <= max(a[0], b[0])
                and min(a[1], b[1]) <= max(p[1], q[1])
                and min(p[1], q[1]) <= max(a[1], b[1])
            ):
                return False
    return True


def _offset_moment(outline: Sequence[tuple[float, float]], delta: float) -> tuple[float, float]:
    """The first moment (of x, of y) of the outline offset inward by `delta` with mitred corners:
    each vertex moves `delta (n + n') / (1 + n . n')` along the sum of its two edges' inward
    normals, and the shoelace formula gives the moment of the result."""
    n = len(outline)
    twice = sum(
        outline[i][0] * outline[(i + 1) % n][1] - outline[(i + 1) % n][0] * outline[i][1]
        for i in range(n)
    )
    side = 1.0 if twice > 0 else -1.0
    normals = []
    for i in range(n):
        dx = outline[(i + 1) % n][0] - outline[i][0]
        dy = outline[(i + 1) % n][1] - outline[i][1]
        length = math.hypot(dx, dy)
        normals.append((-side * dy / length, side * dx / length))
    moved = []
    for i in range(n):
        a, b = normals[i - 1], normals[i]
        scale = delta / (1 + a[0] * b[0] + a[1] * b[1])
        moved.append((outline[i][0] + scale * (a[0] + b[0]), outline[i][1] + scale * (a[1] + b[1])))
    mx = my = 0.0
    for i in range(n):
        (x0, y0), (x1, y1) = moved[i], moved[(i + 1) % n]
        cross = x0 * y1 - x1 * y0
        mx += cross * (x0 + x1) / 6
        my += cross * (y0 + y1) / 6
    return side * mx, side * my


def _segment_distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    """The distance from the origin to the segment `a b`."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    t = max(0.0, min(1.0, -(a[0] * dx + a[1] * dy) / (dx * dx + dy * dy)))
    return math.hypot(a[0] + t * dx, a[1] + t * dy)


def sprocket_closed_form(text: str) -> dict[str, object]:
    """The `ClosedForm` JSON of a double_simplex_sprocket program of the form `_SPROCKET` reads."""
    s = _sprocket(text)
    volume, area, centroid, bounds = sprocket_measures(s)
    keyway_note = (
        f"; through keyway {s.keyway} (half-width and reach), only the rectangle outside the bore"
        if s.keyway is not None
        else ""
    )
    return {
        "kind": "closed_form",
        "volume": volume,
        "area": area,
        "centroid": list(centroid),
        "bounds": [list(bounds[0]), list(bounds[1])],
        "note": (
            "a hub and two tooth plates (one polygon, a mitred chamfer c at both ends of each), "
            "united, bored through along the axis: the plate's volume, flat faces and slanted "
            "faces from the polygon's area, perimeter and the sum of tan(turn / 2) over its "
            "vertices, the hub's cylinders and bore by Pappus-free elementary formulas "
            f"(tools/cq_closed_forms.py, sprocket_measures): hub {s.hub} x {s.length}, "
            f"plates {len(s.outline)} vertices, thickness {s.w}, chamfer {s.c}, "
            f"second at {s.offset}, bore radius {s.bore}{keyway_note}"
        ),
    }


# --- A sprocket plate: one chamfered tooth plate, bored, with an optional hub below ---------
#
# The `sprocket_*` programs: the double sprocket's plate alone (`polyline(...).close().extrude(w)`
# chamfered by `c` at both ends, a `hole` through it along the axis) and an optional hub below it
# (`faces("<A").workplane().circle(R).extrude(h)`, then a blind `hole` of the bore's diameter from
# the hub's end, which leaves a hub annulus under the plate). The plate's formulas are the double
# sprocket's (its header); the hub's disc lies inside the plate's flat bottom face.

_PLATE = re.compile(
    r'^import cadquery as cq\n\nresult = \(\n    cq\.Workplane\("(YZ|XY|XZ)"\)\n'
    r"    \.polyline\((\[.*?\])\)\n    \.close\(\)\n"
    rf"    \.extrude\({_NUMBER}\)\n"
    rf'    \.edges\("(>[XYZ])"\)\n    \.chamfer\({_NUMBER}\)\n'
    rf'    \.edges\("(<[XYZ])"\)\n    \.chamfer\({_NUMBER}\)\n'
    rf'    \.faces\("(?P<bore_face>>[XYZ])"\)\.workplane\(\)\n    \.hole\({_NUMBER}\)\n'
    rf'(?:    \.faces\("(<[XYZ])"\)\.workplane\(\)\n    \.circle\({_NUMBER}\)\n'
    rf'    \.extrude\({_NUMBER}\)\n    \.faces\("(<[XYZ])"\)\.workplane\(\)\n'
    rf"    \.hole\({_NUMBER}, depth={_NUMBER}\)\n)?"
    rf'(?:    \.faces\("(?P=bore_face)"\)\.workplane\(\)\n'
    rf"    \.center\({_NUMBER}, {_NUMBER}\)\n    \.rect\({_NUMBER}, {_NUMBER}\)\n"
    r"    \.cutThruAll\(\)\n)?"
    r"\)\n\n# Export\nshow_object\(result\)\n?$",
    re.S,
)


def plate_measures(text: str) -> tuple[float, float, Vec, Box, str]:
    """Volume, area, centroid, bounds and a note of a `sprocket_*` plate program `_PLATE` reads.

    Raises `ValueError` for another program, or one outside the arrangement the formulas hold:
    selectors not along the axis, a bore not inside the flat faces, a chamfer that overruns an
    edge, a hub narrower than the bore or outside the flat bottom face, or
    a blind hole that is not the bore's diameter or does not reach the plate.
    """
    m = _PLATE.match(text)
    if m is None:
        raise ValueError("not a sprocket plate")
    g = m.groups()
    plane = g[0]
    name = {"YZ": "X", "XY": "Z", "XZ": "Y"}[plane]
    outline = tuple((_num(a), _num(b)) for a, b in _POINT.findall(g[1]))
    ends = (f">{name}", f"<{name}")
    if len(outline) < 3 or (g[3], g[5], g[7]) != (ends[0], ends[1], ends[0]):
        raise ValueError("a plate whose selectors are not along its axis")
    w, c1, c2, bore = _num(g[2]), _num(g[4]), _num(g[6]), _num(g[8]) / 2
    if c1 != c2:
        raise ValueError("a plate whose two chamfers differ")
    c = c1
    hub, height = 0.0, 0.0
    if g[9] is not None:
        hub, height = _num(g[10]), _num(g[11])
        if (g[9], g[12]) != (ends[1], ends[1]):
            raise ValueError("a hub this tool does not read")
        if _num(g[13]) != bore * 2 or _num(g[14]) < height:
            raise ValueError("a blind hole that is not the bore or stops short of the plate")
    n = len(outline)
    area, perimeter, turns, lengths = _turns(outline)
    tans = [math.tan(a / 2) for a in turns]
    near = min(_segment_distance(outline[i], outline[(i + 1) % n]) for i in range(n))
    if not (
        c > 0
        and w > 2 * c
        and 0 < bore < near - c
        and (g[9] is None or bore < hub < near - c)
        and all(lengths[i] > c * (abs(tans[i]) + abs(tans[(i + 1) % n])) for i in range(n))
    ):
        raise ValueError("a plate outside the arrangement the closed form handles")
    pi = math.pi
    sum_tan = sum(tans)
    cut = c * c * perimeter / 2 - c**3 / 3 * sum_tan
    plate = area * w - 2 * cut - pi * bore * bore * w
    annulus = pi * (hub * hub - bore * bore) * height if g[9] is not None else 0.0
    volume = plate + annulus
    flat = area - c * perimeter + c * c * sum_tan
    slant = math.sqrt(2) * c * (perimeter - c * sum_tan)
    total = 2 * flat + perimeter * (w - 2 * c) + 2 * slant - 2 * pi * bore * bore
    total += 2 * pi * bore * w
    total += 2 * pi * (hub + bore) * height  # zero without a hub
    m0 = _offset_moment(outline, 0.0)

    def lost(k: int) -> Callable[[float], float]:
        return lambda d: m0[k] - _offset_moment(outline, d)[k]

    taken = [gauss(lost(k), 0.0, c) for k in range(2)]
    across_moment = [m0[k] * w - 2 * taken[k] for k in range(2)]
    along_moment = plate * (w / 2) - annulus * (height / 2)
    keyway_note = ""
    if g[15] is not None:
        u, v, width, reach = (_num(value) for value in g[15:19])
        if u != 0.0 or v != reach / 2:
            raise ValueError("a sprocket plate keyway whose rectangle starts off the bore axis")
        extra, v_moment, wall = _keyway_cut(bore, (width / 2, reach), hub or near - c)
        length = w + height
        volume -= extra * length
        along_moment -= extra * length * (w - height) / 2
        total += wall * length - 2 * extra
        across_moment[1] -= v_moment * length
        keyway_note = f"; through keyway {width} wide to {reach} from the axis"
    across = [value / volume for value in across_moment]
    along = along_moment / volume
    xs = [p[0] for p in outline]
    ys = [p[1] for p in outline]
    low = [min(xs), min(ys)]
    high = [max(xs), max(ys)]
    below = height
    if plane == "YZ":
        bounds: Box = ((-below, low[0], low[1]), (w, high[0], high[1]))
        centroid: Vec = (along, across[0], across[1])
    elif plane == "XZ":
        # The plate's normal is -Y. A hub extends its more negative end.
        bounds = ((low[0], -w - below, low[1]), (high[0], 0.0, high[1]))
        centroid = (across[0], along - w if below else -along, across[1])
    else:
        bounds = ((low[0], low[1], -below), (high[0], high[1], w))
        centroid = (across[0], across[1], along)
    note = (
        "one tooth plate (a polygon, a mitred chamfer c at both ends), bored through along the "
        "axis, with a hub annulus under it where the program has one: the plate's volume, flat "
        "faces and slanted faces from the polygon's area, perimeter and the sum of tan(turn / 2) "
        f"(tools/cq_closed_forms.py, plate_measures): {n} vertices, thickness {w}, chamfer {c}, "
        f"bore radius {bore}, hub radius {hub} x {height}{keyway_note}"
    )
    return volume, total, centroid, bounds, note


def plate_closed_form(text: str) -> dict[str, object]:
    """The `ClosedForm` JSON of a `sprocket_*` plate program `_PLATE` reads."""
    volume, area, centroid, bounds, note = plate_measures(text)
    return {
        "kind": "closed_form",
        "volume": volume,
        "area": area,
        "centroid": list(centroid),
        "bounds": [list(bounds[0]), list(bounds[1])],
        "note": note,
    }


# --- A spur gear: a chamfered toothed plate, bored, lightened, recessed and keyed ---------------
#
# `spur_gear_*` programs of one shape: a tooth outline extruded w along the plane's normal, a
# through bore of radius b, through holes of radius l at points around the axis, the edges of
# the +A face chamfered by c (the outline mitred as the sprocket's plate, each hole's rim a 45
# degree cone, the bore's rim taken later by the recess), an annulus from b to R cut d deep
# into each face, and a keyway rectangle through the hub. Every section across the axis is the
# outline inset by the chamfer at that height, less discs and the keyway: its area, moment and
# perimeter are elementary (a disc that the recess's disc overlaps loses the lens they share,
# two circular segments), and the measures are one integral over the height, smooth between the
# chamfer's and the recesses' ends.

_GEAR = re.compile(
    r'^import cadquery as cq\n\nresult = \(\n    cq\.Workplane\("(?P<plane>XY|YZ|XZ)"\)\n'
    r"    \.polyline\((?P<outline>\[.*?\])\)\n    \.close\(\)\n"
    rf"    \.extrude\((?P<w>{_NUMBER})\)\n"
    rf'    \.faces\("(?P<top>>[XYZ])"\)\.workplane\(\)\n    \.hole\((?P<bore>{_NUMBER})\)\n'
    r"(?P<holes>(?:    \.cut\(\n        cq\.Workplane\(\"(?P=plane)\"\)\n"
    rf"            \.transformed\(offset=cq\.Vector\({_NUMBER}, {_NUMBER}, {_NUMBER}\), "
    r"rotate=cq\.Vector\(0, 0, 0\)\)\n"
    rf"            \.cylinder\({_NUMBER}, {_NUMBER}\)\n    \)\n)+)"
    rf'    \.edges\("(?P=top)"\)\n    \.chamfer\((?P<c>{_NUMBER})\)\n'
    r'    \.faces\("(?P<low><[XYZ])"\)\.workplane\(\)\n'
    rf"    \.circle\((?P<r1>{_NUMBER})\)\n    \.circle\((?P<i1>{_NUMBER})\)\n"
    rf"    \.cutBlind\(-(?P<d1>{_NUMBER})\)\n"
    r'    \.faces\("(?P=top)"\)\.workplane\(\)\n'
    rf"    \.circle\((?P<r2>{_NUMBER})\)\n    \.circle\((?P<i2>{_NUMBER})\)\n"
    rf"    \.cutBlind\(-(?P<d2>{_NUMBER})\)\n"
    r'    \.faces\("(?P=top)"\)\.workplane\(\)\n'
    rf"    \.center\((?P<u>{_NUMBER}), (?P<v>{_NUMBER})\)\n"
    rf"    \.rect\((?P<kw>{_NUMBER}), (?P<ks>{_NUMBER})\)\n    \.cutThruAll\(\)\n\)\n\n"
    r"# Export\nshow_object\(result\)\n?$",
    re.S,
)
_GEAR_HOLE = re.compile(
    rf"offset=cq\.Vector\({_NUMBER}, {_NUMBER}, {_NUMBER}\), rotate=cq\.Vector\(0, 0, 0\)\)\n"
    rf"            \.cylinder\({_NUMBER}, {_NUMBER}\)"
)


def _lens(big: float, r: float, dist: float) -> tuple[float, float, float, float]:
    """The overlap of the disc of radius `big` about the origin with a disc of radius `r` at
    `dist` from it: its area, its moment along the line to the second centre, and the arcs of
    each circle that lie inside the other disc (by the common chord's two circular segments, a
    segment of half-angle a of radius s having area s^2 (a - sin a cos a) and moment
    2/3 s^3 sin^3 a about its circle's centre)."""
    if dist - r >= big:
        return 0.0, 0.0, 0.0, 0.0
    if dist + r <= big:
        return math.pi * r * r, math.pi * r * r * dist, 0.0, 2 * math.pi * r
    chord = (dist * dist + big * big - r * r) / (2 * dist)  # from the origin along the line
    a1 = math.acos(chord / big)
    a2 = math.acos((dist - chord) / r)
    area1 = big * big * (a1 - math.sin(a1) * math.cos(a1))
    area2 = r * r * (a2 - math.sin(a2) * math.cos(a2))
    moment = 2 / 3 * big**3 * math.sin(a1) ** 3 + area2 * dist - 2 / 3 * r**3 * math.sin(a2) ** 3
    return area1 + area2, moment, 2 * big * a1, 2 * r * a2


def gear_measures(text: str) -> tuple[float, float, Vec, Box, str]:
    """Volume, area, centroid, bounds and a note of a `spur_gear_*` program `_GEAR` reads.

    Raises `ValueError` for another program, or one outside the arrangement: selectors not
    along the plane's normal, a hole not through the plate, holes that meet each other, the
    bore, the keyway or the chamfered outline, a recess that is not the bore's annulus or that
    meets the outline, a chamfer that overruns an edge or reaches the recess floor, or a keyway
    that does not start inside the bore or leaves the recess.
    """
    m = _GEAR.match(text)
    if m is None:
        raise ValueError("not a spur gear this tool reads")
    plane = m["plane"]
    name = {"YZ": "X", "XY": "Z", "XZ": "Y"}[plane]
    if (m["top"], m["low"]) != (f">{name}", f"<{name}"):
        raise ValueError("a gear whose selectors are not along its axis")
    outline = tuple((_num(a), _num(b)) for a, b in _POINT.findall(m["outline"]))
    w, b, c = _num(m["w"]), _num(m["bore"]) / 2, _num(m["c"])
    big, d = _num(m["r1"]), _num(m["d1"])
    if (_num(m["r2"]), _num(m["d2"]), _num(m["i1"]), _num(m["i2"])) != (big, d, b, b):
        raise ValueError("recesses that are not one annulus about the bore")
    holes = []
    for x, y, z, height, radius in _GEAR_HOLE.findall(m["holes"]):
        if not (_num(z) - _num(height) / 2 <= 0.0 and _num(z) + _num(height) / 2 >= w):
            raise ValueError("a hole that does not pass through the plate")
        holes.append((_num(x), _num(y), _num(radius)))
    u0, v0, kw, ks = _num(m["u"]), _num(m["v"]), _num(m["kw"]), _num(m["ks"])
    half, reach = kw / 2, v0 + ks / 2
    n = len(outline)
    area, perimeter, turns, lengths = _turns(outline)
    tans = [math.tan(t / 2) for t in turns]
    near = min(_segment_distance(outline[i], outline[(i + 1) % n]) for i in range(n))

    def clear(x: float, y: float) -> float:  # from a point to the outline
        return min(
            _segment_distance(
                (outline[i][0] - x, outline[i][1] - y),
                (outline[(i + 1) % n][0] - x, outline[(i + 1) % n][1] - y),
            )
            for i in range(n)
        )

    if not (
        0 < c < d < w / 2
        and b + c < big < near - c
        and u0 == 0.0
        and 0 < half < b < reach
        and v0 - ks / 2 < math.sqrt(b * b - half * half)
        and math.hypot(half, reach) < big
        and all(lengths[i] > c * (tans[i] + tans[(i + 1) % n]) for i in range(n))
        and _simple(_offset_outline(outline, c))
        and all(clear(x, y) > r + 2 * c for x, y, r in holes)
        and all(math.hypot(x, y) - r > math.hypot(half, reach) for x, y, r in holes)
        and all(
            math.hypot(p[0] - q[0], p[1] - q[1]) > p[2] + q[2] + 2 * c
            for p, q in itertools.combinations(holes, 2)
        )
    ):
        raise ValueError("a spur gear outside the arrangement the closed form handles")
    sum_tan = sum(tans)
    key_area, key_moment, key_wall = _keyway_cut(b, (half, reach), big)
    pi = math.pi
    # The chamfered face's height along the local normal: >A is the extrusion's end on XY and
    # YZ, its start on XZ (whose normal is -Y).
    face = 0.0 if plane == "XZ" else w

    def section(h: float, zone: bool) -> tuple[float, float, float, float]:
        """Area, moments (of u, of v) and boundary length per unit height (slant included) of
        the section at height h, in a recess (`zone`) or between them."""
        t = max(0.0, c - abs(face - h))
        slant = math.sqrt(2) if t > 0 else 1.0
        stock = area - perimeter * t + sum_tan * t * t
        mu, mv = _offset_moment(outline, t)
        edge = (perimeter - 2 * sum_tan * t) * slant
        if zone:
            stock -= pi * big * big
            edge += 2 * pi * big
        else:
            stock -= pi * b * b + key_area
            mv -= key_moment
            edge += 2 * pi * b + key_wall
        for x, y, r in holes:
            radius = r + t
            dist = math.hypot(x, y)
            lens, along, arc_big, arc_hole = _lens(big, radius, dist) if zone else (0, 0, 0, 0)
            stock -= pi * radius * radius - lens
            shift = pi * radius * radius - (along / dist if dist else 0.0)
            mu -= x * shift
            mv -= y * shift
            edge += (2 * pi * radius - arc_hole) * slant - arc_big
        return stock, mu, mv, edge

    near_face = (0.0, c) if face == 0.0 else (w - c, w)
    cuts = sorted({0.0, d, w - d, w, *near_face})
    totals = [0.0] * 5  # volume, moment along h, moment of u, of v, lateral area
    for lo, hi in itertools.pairwise(cuts):
        zone = hi <= d or lo >= w - d

        def values(h: float, k: int, zone: bool = zone) -> float:
            s = section(h, zone)
            return (s[0], s[0] * h, s[1], s[2], s[3])[k]

        for k in range(5):
            totals[k] += gauss(functools.partial(_component, values, k), lo, hi)
    volume, along, mu, mv, lateral = totals
    floor = pi * (big * big - b * b) - key_area
    for x, y, r in holes:
        floor -= _lens(big, r, math.hypot(x, y))[0]
    total = lateral + section(0.0, True)[0] + section(w, True)[0] + 2 * floor
    xs = [p[0] for p in outline]
    ys = [p[1] for p in outline]
    lo_uv, hi_uv = (min(xs), min(ys)), (max(xs), max(ys))
    cu, cv, ch = mu / volume, mv / volume, along / volume
    if plane == "XY":
        centroid: Vec = (cu, cv, ch)
        bounds: Box = ((lo_uv[0], lo_uv[1], 0.0), (hi_uv[0], hi_uv[1], w))
    elif plane == "YZ":
        centroid = (ch, cu, cv)
        bounds = ((0.0, lo_uv[0], lo_uv[1]), (w, hi_uv[0], hi_uv[1]))
    else:
        centroid = (cu, -ch, cv)
        bounds = ((lo_uv[0], -w, lo_uv[1]), (hi_uv[0], 0.0, hi_uv[1]))
    note = (
        "a toothed plate (one polygon) bored, its +A edges chamfered c (the outline mitred, each "
        "hole's rim a 45 degree cone), lightened by through holes, an annulus from the bore to R "
        "cut d into each face and a keyway through the hub: the integral over the height of each "
        "section's area, moments and boundary, the outline's inset by the shoelace formula and "
        "sum of tan(turn / 2), a hole the recess overlaps less the lens they share "
        f"(tools/cq_closed_forms.py, gear_measures): {n} vertices, thickness {w}, chamfer {c}, "
        f"bore radius {b}, {len(holes)} holes, recess {big} x {d}, keyway {kw} to {reach}"
    )
    return volume, total, centroid, bounds, note


def gear_closed_form(text: str) -> dict[str, object]:
    """The `ClosedForm` JSON of a `spur_gear_*` program `_GEAR` reads."""
    volume, area, centroid, bounds, note = gear_measures(text)
    return {
        "kind": "closed_form",
        "volume": volume,
        "area": area,
        "centroid": list(centroid),
        "bounds": [list(bounds[0]), list(bounds[1])],
        "note": note,
    }


# --- A rectangular frame: a plate with a window, holes and edge notches, its faces' rims rounded
#
# `rect_frame_*` programs: a rectangle extruded t, a centred window cut through, optional
# holes through it and two notch boxes on its plane cut into an outer edge from the face at
# h = 0 (to a depth e, or through), then every edge of one or both faces filleted. A fillet of
# a face's edges with the third edge at each corner sharp is, at each height, the face's region
# offset inward with mitred corners (the cylinders cross on the corner's mitre plane, a reflex
# corner's as a convex one's, and a hole's rim is a torus whose section is the circle grown by
# the offset): its area A - P d + T d^2, its boundary P - 2 T d and its moment by the shoelace
# formula of the moved vertices, T the sum of tan(turn / 2) over the outline's corners less the
# window's and pi per hole. The measures are one integral over the height in four pieces.

_FRAME = re.compile(
    r'^import cadquery as cq\n\nresult = \(\n    cq\.Workplane\("(?P<plane>XY|YZ|XZ)"\)\n'
    rf"    \.rect\((?P<L>{_NUMBER}), (?P<H>{_NUMBER})\)\n    \.extrude\((?P<t>{_NUMBER})\)\n"
    r'    \.faces\("(?P<top>>[XYZ])"\)\.workplane\(\)\n'
    rf"    \.rect\((?P<l>{_NUMBER}), (?P<h>{_NUMBER})\)\n    \.cutThruAll\(\)\n"
    r'(?:    \.faces\("(?P=top)"\)\.workplane\(\)\n    \.pushPoints\((?P<points>\[[^\]]*\])\)\n'
    rf"    (?:\.circle\((?P<r>{_NUMBER})\)\n    \.cutThruAll\(\)|\.hole\((?P<d>{_NUMBER})\))\n)?"
    r"(?P<notches>(?:    \.cut\(\n        cq\.Workplane\(\"(?P=plane)\"\)\n"
    rf"            \.transformed\(offset=cq\.Vector\({_NUMBER}, {_NUMBER}, {_NUMBER}\), "
    r"rotate=cq\.Vector\(0, 0, 0\)\)\n"
    rf"            \.box\({_NUMBER}, {_NUMBER}, {_NUMBER}\)\n    \)\n)*)"
    r'(?P<fillets>(?:    \.faces\("[<>][XYZ]"\)\n    \.edges\(\)\n'
    rf"    \.fillet\({_NUMBER}\)\n)+)"
    r"\)\n\n# Export\nshow_object\(result\)\n?$",
    re.S,
)
_FRAME_NOTCH = re.compile(
    rf"offset=cq\.Vector\({_NUMBER}, {_NUMBER}, {_NUMBER}\), rotate=cq\.Vector\(0, 0, 0\)\)\n"
    rf"            \.box\({_NUMBER}, {_NUMBER}, {_NUMBER}\)"
)
_FRAME_FILLET = re.compile(
    rf'\.faces\("([<>])([XYZ])"\)\n    \.edges\(\)\n    \.fillet\({_NUMBER}\)'
)


def _notched(width: float, height: float, notches: Sequence[Box]) -> list[tuple[float, float]]:
    """The rectangle `width` x `height` about the origin, counter-clockwise, with each notch (a
    box on the plane, (u, v) ranges) cut into the edge it straddles."""
    hu, hv = width / 2, height / 2
    sides: dict[int, list[tuple[float, float, float]]] = {0: [], 1: [], 2: [], 3: []}
    for (u0, v0, _), (u1, v1, _) in notches:
        if v0 < -hv < v1 < hv and -hu < u0 < u1 < hu:
            sides[0].append((u0, u1, v1))  # into the bottom edge, to v1
        elif -hv < v0 < hv < v1 and -hu < u0 < u1 < hu:
            sides[2].append((u1, u0, v0))  # into the top edge, to v0
        elif u0 < -hu < u1 < hu and -hv < v0 < v1 < hv:
            sides[3].append((v1, v0, u1))
        elif -hu < u0 < hu < u1 and -hv < v0 < v1 < hv:
            sides[1].append((v0, v1, u0))
        else:
            raise ValueError("a notch that does not cut into one edge of the frame")
    out: list[tuple[float, float]] = [(-hu, -hv)]
    for a, b, depth in sorted(sides[0]):
        out += [(a, -hv), (a, depth), (b, depth), (b, -hv)]
    out.append((hu, -hv))
    for a, b, depth in sorted(sides[1]):
        out += [(hu, a), (depth, a), (depth, b), (hu, b)]
    out.append((hu, hv))
    for a, b, depth in sorted(sides[2], reverse=True):
        out += [(a, hv), (a, depth), (b, depth), (b, hv)]
    out.append((-hu, hv))
    for a, b, depth in sorted(sides[3], reverse=True):
        out += [(-hu, a), (depth, a), (depth, b), (-hu, b)]
    return out


def _rim_prism(
    plane: str,
    full: Sequence[tuple[float, float]],
    low: Sequence[tuple[float, float]],
    depth: float,
    window: Sequence[tuple[float, float]],
    holes: Sequence[tuple[float, float]],
    radius: float,
    t: float,
    fillets: tuple[float, float],
) -> tuple[float, float, Vec, Box]:
    """Volume, area, centroid and bounds of a prism of height t on `plane` whose section is
    `low` (to `depth` from h = 0, notched) then `full`, less a `window` (empty for none) and
    holes of `radius`, the rims of its faces at h = 0 and h = t filleted by `fillets`: at each
    height the region offset inward with mitred corners (see the frame's header).
    """
    f0, f1 = fillets
    notched = list(low) != list(full)
    upper = low if depth >= t else full  # the outline at the h = t face
    lo_u, lo_v = min(u for u, _ in full), min(v for _, v in full)
    hi_u, hi_v = max(u for u, _ in full), max(v for _, v in full)

    def measures(outline: Sequence[tuple[float, float]]) -> tuple[float, float, float]:
        area, perimeter, turns, _ = _turns(outline)
        w_area, w_perimeter, w_turns, _ = _turns(window) if window else (0.0, 0.0, [], [])
        tan = sum(math.tan(a / 2) for a in turns) - sum(math.tan(a / 2) for a in w_turns)
        return (
            area - w_area - len(holes) * math.pi * radius**2,
            perimeter + w_perimeter + len(holes) * 2 * math.pi * radius,
            tan - len(holes) * math.pi,
        )

    def check(outline: Sequence[tuple[float, float]], f: float) -> bool:
        n = len(outline)
        _, _, turns, lengths = _turns(outline)
        tans = [math.tan(a / 2) for a in turns]
        inner = _offset_outline(outline, f)
        grown = _offset_outline(window, -f) if window else []
        return (
            all(lengths[i] > f * (tans[i] + tans[(i + 1) % n]) for i in range(n))
            and _simple(inner)
            and all(min(abs(c) for c in p) > 0.0 for p in grown)
            and all(  # the grown window inside the inset outline
                _segment_distance(
                    (inner[i][0] - p[0], inner[i][1] - p[1]),
                    (inner[(i + 1) % n][0] - p[0], inner[(i + 1) % n][1] - p[1]),
                )
                > 0.0
                and lo_u + f < p[0] < hi_u - f
                and lo_v + f < p[1] < hi_v - f
                for p in grown
                for i in range(n)
            )
            and all(
                min(
                    _segment_distance((q[0][0] - x, q[0][1] - y), (q[1][0] - x, q[1][1] - y))
                    for loop in (outline, window)
                    if loop
                    for q in itertools.pairwise([*loop, loop[0]])
                )
                > radius + 2 * f
                for x, y in holes
            )
            and all(
                math.hypot(p[0] - q[0], p[1] - q[1]) > 2 * (radius + f)
                for p, q in itertools.combinations(holes, 2)
            )
        )

    if (
        not (f0 >= 0 and f1 >= 0 and f0 + f1 < t)
        or (notched and depth < t and not f0 < depth < t - f1)
        or not check(low, f0)
        or not check(upper, f1)
    ):
        raise ValueError("a rimmed prism outside the arrangement the closed form handles")

    def section(outline: Sequence[tuple[float, float]], d: float) -> tuple[float, ...]:
        area, perimeter, tan = measures(outline)
        mu, mv = _offset_moment(outline, d)
        wu, wv = _offset_moment(window, -d) if window else (0.0, 0.0)
        hu = sum(x for x, _ in holes) * math.pi * (radius + d) ** 2
        hv = sum(y for _, y in holes) * math.pi * (radius + d) ** 2
        return (
            area - perimeter * d + tan * d * d,
            mu - wu - hu,
            mv - wv - hv,
            perimeter - 2 * tan * d,
        )

    totals = [0.0] * 5  # volume, moments along h, u, v; lateral area
    straight = [(low, f0, depth if notched and depth < t else t - f1)]
    if notched and depth < t:
        straight.append((upper, depth, t - f1))
    for outline, a, b in straight:
        s = section(outline, 0.0)
        for k, value in enumerate((s[0], s[0] * (a + b) / 2, s[1], s[2], s[3])):
            totals[k] += value * (b - a)
    for outline, f, base, way in ((low, f0, f0, -1), (upper, f1, t - f1, 1)):
        if not f:
            continue

        def rim(
            angle: float,
            k: int,
            outline: Sequence[tuple[float, float]] = outline,
            f: float = f,
            base: float = base,
            way: int = way,
        ) -> float:
            d = f * (1 - math.cos(angle))
            h = base + way * f * math.sin(angle)
            s = section(outline, d)
            dh = f * math.cos(angle)
            return (s[0] * dh, s[0] * h * dh, s[1] * dh, s[2] * dh, s[3] * f)[k]

        for k in range(5):
            totals[k] += gauss(functools.partial(_component, rim, k), 0.0, math.pi / 2)
    volume, along, mu, mv, lateral = totals
    faces = section(low, f0)[0] + section(upper, f1)[0]
    if notched and depth < t:
        faces += section(full, 0.0)[0] - section(low, 0.0)[0]  # the notches' floors
    cu, cv, ch = mu / volume, mv / volume, along / volume
    if plane == "XY":
        centroid: Vec = (cu, cv, ch)
        bounds: Box = ((lo_u, lo_v, 0.0), (hi_u, hi_v, t))
    elif plane == "YZ":
        centroid = (ch, cu, cv)
        bounds = ((0.0, lo_u, lo_v), (t, hi_u, hi_v))
    else:
        centroid = (cu, -ch, cv)
        bounds = ((lo_u, -t, lo_v), (hi_u, 0.0, hi_v))
    return volume, lateral + faces, centroid, bounds


def frame_measures(text: str) -> tuple[float, float, Vec, Box, str]:
    """Volume, area, centroid, bounds and a note of a `rect_frame_*` program `_FRAME` reads.

    Raises `ValueError` for another program or one outside the arrangement: selectors off the
    plane's normal, a notch that does not start on the face at h = 0 or cut into one outer
    edge, unequal notch depths, a notch floor inside a fillet, or a fillet that meets another
    feature or overruns an edge.
    """
    m = _FRAME.match(text)
    if m is None:
        raise ValueError("not a rectangular frame this tool reads")
    plane = m["plane"]
    name = {"YZ": "X", "XY": "Z", "XZ": "Y"}[plane]
    if m["top"] != f">{name}":
        raise ValueError("a frame whose selectors are not along its axis")
    width, height, t = _num(m["L"]), _num(m["H"]), _num(m["t"])
    window = [(-_num(m["l"]) / 2, -_num(m["h"]) / 2), (_num(m["l"]) / 2, -_num(m["h"]) / 2)]
    window += [(-u, -v) for u, v in window]  # counter-clockwise from the lower left
    mirror = -1.0 if plane == "XZ" else 1.0  # the >Y workplane's x is -X
    radius = 0.0
    holes: list[tuple[float, float]] = []
    if m["points"] is not None:
        radius = _num(m["r"]) if m["r"] is not None else _num(m["d"]) / 2
        holes = [(mirror * _num(u), _num(v)) for u, v in _POINT.findall(m["points"])]
        if len(holes) != m["points"].count("("):
            raise ValueError("points this tool does not read")
    boxes: list[Box] = []
    depths = set()
    for x, y, z, bx, by, bz in _FRAME_NOTCH.findall(m["notches"]):
        lo, hi = _num(z) - _num(bz) / 2, _num(z) + _num(bz) / 2
        if lo > 0.0:
            raise ValueError("a notch that does not start on the frame's face at h = 0")
        depths.add(min(hi, t))
        u, v, du, dv = _num(x), _num(y), _num(bx) / 2, _num(by) / 2
        boxes.append(((u - du, v - dv, lo), (u + du, v + dv, hi)))
    if len(depths) > 1:
        raise ValueError("notches of different depths")
    depth = depths.pop() if depths else 0.0
    fillets = {0.0: 0.0, t: 0.0}
    for sign, axis, size in _FRAME_FILLET.findall(m["fillets"]):
        if axis != name:
            raise ValueError("a fillet on a face off the frame's axis")
        at = t if (sign == ">") != (plane == "XZ") else 0.0
        fillets[at] = _num(size)
    f0, f1 = fillets[0.0], fillets[t]
    full = [(-width / 2, -height / 2), (width / 2, -height / 2)]
    full += [(-u, -v) for u, v in full]
    low = _notched(width, height, boxes) if boxes else full

    inner_notch = boxes and not all(
        min(abs(b[0][1]), abs(b[1][1])) > _num(m["h"]) / 2 + 2 * max(f0, f1)
        or min(abs(b[0][0]), abs(b[1][0])) > _num(m["l"]) / 2 + 2 * max(f0, f1)
        for b in boxes
    )
    if inner_notch:
        raise ValueError("a notch that meets the window's fillets")
    volume, area, centroid, bounds = _rim_prism(
        plane, full, low, depth, window, holes, radius, t, (f0, f1)
    )
    note = (
        "a plate with a window, holes and notches, its faces' rims filleted: at each height the "
        "region offset inward with mitred corners (area A - P d + T d^2, boundary P - 2 T d, the "
        "moment by the shoelace formula), integrated over the height through each fillet's angle "
        f"(tools/cq_closed_forms.py, frame_measures): {width} x {height} x {t}, window "
        f"{_num(m['l'])} x {_num(m['h'])}, {len(holes)} holes of radius {radius}, "
        f"{len(boxes)} notches {depth} deep, fillets {f0} and {f1}"
    )
    return volume, area, centroid, bounds, note


def frame_closed_form(text: str) -> dict[str, object]:
    """The `ClosedForm` JSON of a `rect_frame_*` program `_FRAME` reads."""
    volume, area, centroid, bounds, note = frame_measures(text)
    return {
        "kind": "closed_form",
        "volume": volume,
        "area": area,
        "centroid": list(centroid),
        "bounds": [list(bounds[0]), list(bounds[1])],
        "note": note,
    }


# --- A hex nut: a polygon prism bored through, its faces' rims filleted (the frame's core) ------

_NUT = re.compile(
    r'^import cadquery as cq\n\nresult = \(\n    cq\.Workplane\("(?P<plane>XY|YZ|XZ)"\)\n'
    rf"(?:    \.moveTo\((?P<u>{_NUMBER}), (?P<v>{_NUMBER})\)\n"
    rf"(?P<lines>(?:    \.lineTo\({_NUMBER}, {_NUMBER}\)\n)+)"
    r"    \.close\(\)\n"
    rf"|    \.polygon\((?P<n>\d+), (?P<d>{_NUMBER})\)\n)"
    rf"    \.extrude\((?P<t>{_NUMBER})\)\n"
    r'    \.faces\("(?P<top>>[XYZ])"\)\.workplane\(\)\n'
    rf"    (?:\.circle\((?P<r>{_NUMBER})\)\n    \.cutThruAll\(\)|\.hole\((?P<bore>{_NUMBER})\))\n"
    r'(?P<fillets>(?:    \.faces\("[<>][XYZ]"\)\n    \.edges\(\)\n'
    rf"    \.fillet\({_NUMBER}\)\n)+)"
    r"\)\n\n# Export\nshow_object\(result\)\n?$",
    re.S,
)


def nut_closed_form(text: str) -> dict[str, object]:
    """The `ClosedForm` JSON of a `hex_nut_*` program `_NUT` reads: a polygon (`moveTo` then
    `lineTo`s, or `polygon(n, d)`) extruded, bored through at the origin, the rims of one or
    both faces filleted, by `_rim_prism`."""
    m = _NUT.match(text)
    if m is None:
        raise ValueError("not a nut this tool reads")
    plane = m["plane"]
    name = {"YZ": "X", "XY": "Z", "XZ": "Y"}[plane]
    if m["top"] != f">{name}":
        raise ValueError("a nut whose selectors are not along its axis")
    if m["n"] is not None:
        n, d = int(m["n"]), _num(m["d"])
        outline = [
            (d / 2 * math.cos(2 * math.pi * j / n), d / 2 * math.sin(2 * math.pi * j / n))
            for j in range(n)
        ]
    else:
        outline = [(_num(m["u"]), _num(m["v"]))]
        outline += [(_num(u), _num(v)) for u, v in _POINT.findall(m["lines"])]
    if _turns(outline)[0] <= 0 or not _simple(outline):
        raise ValueError("a nut outline that is not a simple polygon")
    t = _num(m["t"])
    radius = _num(m["r"]) if m["r"] is not None else _num(m["bore"]) / 2
    fillets = {0.0: 0.0, t: 0.0}
    for sign, axis, size in _FRAME_FILLET.findall(m["fillets"]):
        if axis != name:
            raise ValueError("a fillet on a face off the nut's axis")
        fillets[t if (sign == ">") != (plane == "XZ") else 0.0] = _num(size)
    f0, f1 = fillets[0.0], fillets[t]
    volume, area, centroid, bounds = _rim_prism(
        plane, outline, outline, 0.0, [], [(0.0, 0.0)], radius, t, (f0, f1)
    )
    return {
        "kind": "closed_form",
        "volume": volume,
        "area": area,
        "centroid": list(centroid),
        "bounds": [list(bounds[0]), list(bounds[1])],
        "note": (
            "a polygon prism bored through, its faces' rims filleted: at each height the region "
            "offset inward with mitred corners, the bore grown by the offset (a torus's section), "
            "integrated over the height through each fillet's angle (tools/cq_closed_forms.py, "
            f"_rim_prism): {len(outline)} vertices, height {t}, bore radius {radius}, "
            f"fillets {f0} and {f1}"
        ),
    }


# --- A flanged spur gear: the toothed plate, a hub flange and a relief groove on one end --------
#
# `spur_gear_*` programs of a second shape: the tooth outline extruded w, bored, the +A face's
# edges chamfered c (the outline mitred, the bore's rim a cone), a keyway through, then on the
# far end a flange ring (outer radius over the teeth) and a hub, with a relief groove cut into the
# plate's end: each section across the axis is the mitred outline less the bore and keyway (or,
# inside the groove's depth, less the relief disc, clipped by the outline where the disc reaches
# it), and the flange's rings are elementary.


def _chain(text: str) -> list[tuple[str, ast.Call]]:
    """The calls of `result = (...)`, first to last."""
    node = ast.parse(text).body[1]
    if not isinstance(node, ast.Assign):
        raise ValueError("not a chain this tool reads")
    value = node.value
    out: list[tuple[str, ast.Call]] = []
    while isinstance(value, ast.Call) and isinstance(value.func, ast.Attribute):
        out.append((value.func.attr, value))
        value = value.func.value
    return list(reversed(out))


def _literals(node: ast.Call) -> tuple[object, ...]:
    return tuple(ast.literal_eval(a) for a in node.args)


def _rivet_point(values: object) -> tuple[float, float]:
    if (
        not isinstance(values, tuple)
        or len(values) != 2
        or not all(type(v) in (int, float) for v in values)
    ):
        raise ValueError("a rivet profile point needs two numbers")
    return float(values[0]), float(values[1])


def rivet_closed_form(text: str) -> dict[str, object]:
    """The blended rivet's measures from its meridian. Refuse other arrangements."""
    chain = _chain(text)
    names = [name for name, _ in chain]
    forward = ["moveTo", "lineTo", "lineTo", "lineTo", "threePointArc"]
    reverse = ["moveTo", "threePointArc", "lineTo", "lineTo", "lineTo"]
    if (
        len(names) != 10
        or names[0] != "Workplane"
        or names[1:6] not in (forward, reverse)
        or names[6:9] != ["close", "revolve", "edges"]
        or names[9] not in ("chamfer", "fillet")
        or any(call.keywords for _, call in chain)
    ):
        raise ValueError("not the rivet this tool reads")
    frame, *profile, close, turn, select, blend = [_literals(call) for _, call in chain]
    frames = {("XY",): (1, "<Z"), ("XZ",): (2, "<Y"), ("YZ",): (2, "<X")}
    if frame not in tuple(frames) or close or turn != (360, (0, 0, 0), (0, 1, 0)):
        raise ValueError("a rivet must be a full turn about the plane's y axis")
    axis, selector = frames[frame]
    if select != (selector,) or len(blend) != 1 or not isinstance(blend[0], int | float):
        raise ValueError("a rivet must blend all three rims")
    distance = float(blend[0])
    if names[1:6] == forward:
        foot, base, shank_top, shoulder = map(_rivet_point, profile[:4])
        mid, pole = map(_rivet_point, profile[4])
    else:
        pole = _rivet_point(profile[0])
        mid, shoulder = map(_rivet_point, profile[1])
        shank_top, base, foot = map(_rivet_point, profile[2:])
    shank, height = shank_top
    head, shoulder_height = shoulder
    if not (
        foot == (0, 0)
        and base == (shank, 0)
        and shoulder_height == height
        and 0 < distance < shank < mid[0] < head
        and 2 * distance < height
        and pole[0] == 0
        and height < mid[1] < pole[1]
    ):
        raise ValueError("not a shank with a rounded rivet head and room for a blend")

    # Circumcentre of the head's arc, in radius and height coordinates.
    x, y = mid[0] - head, mid[1] - height
    u, v = -head, pole[1] - height
    determinant = 2 * (x * v - y * u)
    if determinant <= 0:
        raise ValueError("a rivet head must follow a counterclockwise arc toward the pole")
    p, q = x * x + y * y, u * u + v * v
    rc = head + (p * v - q * y) / determinant
    zc = height + (x * q - u * p) / determinant
    radius = math.hypot(head - rc, height - zc)
    if distance >= radius:
        raise ValueError("a rivet blend consumes the head arc")
    start = math.atan2(height - zc, head - rc)
    end = math.atan2(pole[1] - zc, -rc)

    lines = [((0.0, 0.0), (shank - distance, 0.0)), ((shank, distance), (shank, height - distance))]
    arcs: list[tuple[float, float, float, float, float]] = []
    if names[-1] == "chamfer":
        # A chamfer trims each side by a straight-line distance from the rim.
        angle = start + 2 * math.asin(distance / (2 * radius))
        rim = head - distance
        lines.extend(
            [
                ((shank - distance, 0.0), (shank, distance)),
                ((shank, height - distance), (shank + distance, height)),
                ((rim, height), (rc + radius * math.cos(angle), zc + radius * math.sin(angle))),
            ]
        )
    else:
        # The third fillet is tangent to the shoulder and the circular head.
        fillet_height = height + distance
        rim = rc + math.sqrt((radius - distance) ** 2 - (fillet_height - zc) ** 2)
        angle = math.atan2(fillet_height - zc, rim - rc)
        arcs.extend(
            [
                (shank - distance, distance, distance, -math.pi / 2, 0.0),
                (shank + distance, height - distance, distance, math.pi, math.pi / 2),
                (rim, fillet_height, distance, -math.pi / 2, angle),
            ]
        )
    if not (shank + distance < rim and start < angle < end):
        raise ValueError("a rivet's blends overlap or consume its head")
    lines.append(((shank + distance, height), (rim, height)))
    arcs.append((rc, zc, radius, angle, end))

    # A meridian ordinate (r, z) contributes pi r² dz to volume, z times
    # that to moment, and 2 pi r ds to area. dz stays signed over an arc
    # that passes the top of the head before it reaches the rotation axis.
    volume = moment = area = 0.0
    reach, top = shank, height
    for (r0, z0), (r1, z1) in lines:
        dr, dz = r1 - r0, z1 - z0
        volume += math.pi * dz * (r0 * r0 + r0 * r1 + r1 * r1) / 3
        # Integral of the cubic (r0 + dr t)^2 (z0 + dz t) for t in [0, 1].
        moment += (
            math.pi
            * dz
            * (r0 * r0 * (z0 + dz / 2) + r0 * dr * (z0 + 2 * dz / 3) + dr * dr * (z0 / 3 + dz / 4))
        )
        area += math.pi * (r0 + r1) * math.hypot(dr, dz)
    for r_center, z_center, r_arc, t0, t1 in arcs:
        dv, dm, da, r_max, z_max = _rivet_arc(r_center, z_center, r_arc, t0, t1)
        volume += dv
        moment += dm
        area += da
        reach, top = max(reach, r_max), max(top, z_max)
    return {
        "kind": "closed_form",
        "volume": volume,
        "area": area,
        "centroid": [moment / volume if k == axis else 0.0 for k in range(3)],
        "bounds": [
            [0.0 if k == axis else -reach for k in range(3)],
            [top if k == axis else reach for k in range(3)],
        ],
        "note": f"{names[-1]} of the three rivet rims, by the meridian in rivet_closed_form",
    }


def _rivet_arc(
    rc: float, zc: float, radius: float, start: float, end: float
) -> tuple[float, float, float, float, float]:
    def r(t: float) -> float:
        return rc + radius * math.cos(t)

    def z(t: float) -> float:
        return zc + radius * math.sin(t)

    volume = math.pi * radius * gauss(lambda t: r(t) ** 2 * math.cos(t), start, end)
    moment = math.pi * radius * gauss(lambda t: z(t) * r(t) ** 2 * math.cos(t), start, end)
    sweep = rc * (end - start) + radius * (math.sin(end) - math.sin(start))
    area = 2 * math.pi * radius * abs(sweep)
    lo, hi = sorted((start, end))
    reach = rc + radius if lo <= 0 <= hi else max(r(start), r(end))
    top = zc + radius if lo <= math.pi / 2 <= hi else max(z(start), z(end))
    return volume, moment, area, reach, top


def flanged_gear_closed_form(text: str) -> dict[str, object]:
    """The `ClosedForm` JSON of a flanged `spur_gear_*` program (two `union`s, two `cut`s).

    Raises `ValueError` for another program or one outside the arrangement: selectors off the
    axis, flanges not coaxial, a groove that does not open into the plate's end, or a keyway
    that does not start inside the bore.
    """
    fields: dict[str, list[ast.Call]] = {}
    for name, call in _chain(text):
        fields.setdefault(name, []).append(call)
    if len(fields.get("union", ())) != 2 or len(fields.get("cut", ())) != 2:
        raise ValueError("not a flanged gear")
    (plane,) = _literals(fields["Workplane"][0])
    (profile,) = _literals(fields["polyline"][0])
    (w,) = _literals(fields["extrude"][0])
    (diameter,) = _literals(fields["hole"][0])
    (c,) = _literals(fields["chamfer"][0])
    k0, k = _literals(fields["center"][0])
    width, span = _literals(fields["rect"][0])
    if not (
        isinstance(plane, str)
        and plane in _PLANES
        and isinstance(profile, list)
        and all(isinstance(v, float) for v in (w, diameter, c, k0, k, width, span))
    ):
        raise ValueError("a flanged gear this tool does not read")
    assert isinstance(w, float)
    assert isinstance(diameter, float)
    assert isinstance(c, float)
    assert isinstance(k, float)
    assert isinstance(width, float)
    assert isinstance(span, float)
    outline = [(float(u), float(v)) for u, v in profile]
    r = diameter / 2
    reach = k + span / 2
    a = width / 2
    at_low = plane == "XZ"
    axis = {"XY": "Z", "YZ": "X", "XZ": "Y"}[plane]
    if not (
        k0 == 0
        and 0 < a < r
        and abs(k - span / 2) < math.sqrt(r * r - a * a)
        and all(_literals(n) == (f">{axis}",) for n in fields["faces"] + fields["edges"])
    ):
        raise ValueError("a flanged gear's keyway or selectors this tool does not read")
    area, per, turns, _ = _turns(outline)
    tan = sum(math.tan(t / 2) for t in turns)
    sides = list(itertools.pairwise([*outline, outline[0]]))
    near = min(_segment_distance(p, q) for p, q in sides)
    far = max(math.hypot(*p) for p in outline)

    def cylinder(call: ast.Call) -> tuple[float, float, float]:
        node = call.args[0]
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "cylinder"
            and isinstance(node.func.value, ast.Call)
        ):
            raise ValueError("a flange that is not a cylinder")
        height, radius = (float(v) for v in _literals(node))  # type: ignore[arg-type]
        x, y, z = (float(v) for v in _literals(node.func.value.keywords[0].value))  # type: ignore[arg-type]
        if x != 0 or y != 0:
            raise ValueError("a flange off the gear's axis")
        return z - height / 2, z + height / 2, radius

    start, end, outer = cylinder(fields["union"][0])
    cut_start, cut_end, relief = cylinder(fields["cut"][0])
    foot, head, hub = cylinder(fields["union"][1])
    bolt_start, bolt_end, bore = cylinder(fields["cut"][1])
    if not (
        (start, end) == (foot, head)
        and (cut_start, cut_end) == (bolt_start, bolt_end)
        and bore == r
        and c < w
        and 0 < cut_start < start < w < end < cut_end
        and outer > far
        and r < hub < relief
        and max(hub, r + c, math.hypot(reach, a)) < relief
    ):
        raise ValueError("a flanged gear outside the arrangement the closed form handles")

    def trim(z: float) -> float:
        return max(0.0, c - z) if at_low else max(0.0, c - w + z)

    intersected = relief >= near - max(trim(start), trim(cut_start))
    clip_area = clip_x = clip_y = outer_len = arc_len = 0.0
    if intersected:
        if not (at_low and cut_start > c):
            raise ValueError("a relief that meets the chamfered outline")
        oriented = (
            sides
            if sum(x * v - y * u for (x, y), (u, v) in sides) > 0
            else [(q, p) for p, q in reversed(sides)]
        )

        def cos_primitive(t: float) -> float:
            return math.sin(t) - math.sin(t) ** 3 / 3

        def sin_primitive(t: float) -> float:
            return -math.cos(t) + math.cos(t) ** 3 / 3

        for (x, y), (u, v) in oriented:
            dx, dy = u - x, v - y
            if not x * v - y * u > 0:
                raise ValueError("an outline not star-shaped about the axis")
            qa = dx * dx + dy * dy
            qb = 2 * (x * dx + y * dy)
            qc = x * x + y * y - relief * relief
            events = [0.0, 1.0]
            disc = qb * qb - 4 * qa * qc
            if disc > 0:
                roots = ((-qb - math.sqrt(disc)) / (2 * qa), (-qb + math.sqrt(disc)) / (2 * qa))
                events.extend(t for t in roots if 0 < t < 1)
            for lo, hi in itertools.pairwise(sorted(events)):
                x0, y0 = x + dx * lo, y + dy * lo
                x1, y1 = x + dx * hi, y + dy * hi
                mid = (lo + hi) / 2
                if math.hypot(x + dx * mid, y + dy * mid) < relief:
                    clip_area += (x0 * y1 - y0 * x1) / 2
                    clip_x += (y1 - y0) * (x0 * x0 + x0 * x1 + x1 * x1) / 6
                    clip_y -= (x1 - x0) * (y0 * y0 + y0 * y1 + y1 * y1) / 6
                else:
                    angle = math.atan2(x0 * y1 - y0 * x1, x0 * x1 + y0 * y1)
                    t0 = math.atan2(y0, x0)
                    clip_area += relief * relief * angle / 2
                    clip_x += relief**3 * (cos_primitive(t0 + angle) - cos_primitive(t0)) / 2
                    clip_y += relief**3 * (sin_primitive(t0 + angle) - sin_primitive(t0)) / 2
                    outer_len += math.hypot(dx, dy) * (hi - lo)
                    arc_len += relief * angle

    def cutout(radius: float) -> tuple[float, float, float, float]:
        first = min(a, math.sqrt(max(0.0, radius * radius - reach * reach)))

        def antiderivative(x: float) -> float:
            return x * math.sqrt(radius * radius - x * x) + radius * radius * math.asin(x / radius)

        def moment(x: float) -> float:
            return (reach * reach - radius * radius) * x + x**3 / 3

        arc = 2 * radius * (math.pi - math.asin(a / radius) + math.asin(first / radius))
        wall = 2 * (max(0.0, reach - math.sqrt(radius * radius - a * a)) + a - first)
        hole = (
            math.pi * radius * radius
            + 2 * (a - first) * reach
            - antiderivative(a)
            + antiderivative(first)
        )
        return hole, moment(a) - moment(first), arc, wall

    def actual(z: float) -> tuple[float, float, float, float, float]:
        t = trim(z)
        stock = area - per * t + tan * t * t
        perimeter = per - 2 * tan * t
        mx, my = _offset_moment(outline, t)
        factor = math.sqrt(2) if t > 0 else 1.0
        if z < cut_start:
            hole, shift, curve, wall = cutout(r + t)
            return (
                stock - hole,
                (stock - hole) * z,
                mx,
                my - shift,
                (perimeter + curve) * factor + wall,
            )
        if intersected:
            return (
                stock - clip_area,
                (stock - clip_area) * z,
                mx - clip_x,
                my - clip_y,
                outer_len + arc_len,
            )
        hole = math.pi * relief * relief
        return stock - hole, (stock - hole) * z, mx, my, perimeter * factor + 2 * math.pi * relief

    cuts = {0.0, cut_start, start}
    for h in (c, w - c, reach - r, math.hypot(reach, a) - r):
        if 0 < h < start:
            cuts.add(h)
        if 0 < w - h < start:
            cuts.add(w - h)
    figures = [
        sum(
            tanh_sinh(functools.partial(_component, lambda z, i: actual(z)[i], i), lo, hi)
            for lo, hi in itertools.pairwise(sorted(cuts))
        )
        for i in range(5)
    ]
    volume, axial, mx, my, wall = figures
    flange_area = math.pi * (outer**2 - relief**2 + hub**2 - bore**2)
    volume += flange_area * (end - start)
    axial += flange_area * (end - start) * (end + start) / 2
    wall += (end - start) * 2 * math.pi * (outer + relief + hub + bore)
    start_face = area - per * trim(0.0) + tan * trim(0.0) ** 2 - cutout(r + trim(0.0))[0]
    groove_step = (clip_area if intersected else math.pi * relief**2) - cutout(r + trim(cut_start))[
        0
    ]
    neck_area = actual(start)[0]
    flange_step = flange_area - neck_area
    surface = wall + flange_area + start_face + groove_step + flange_step
    centroid = {
        "XY": (mx / volume, my / volume, axial / volume),
        "YZ": (axial / volume, mx / volume, my / volume),
        "XZ": (mx / volume, -axial / volume, my / volume),
    }[plane]
    box = {
        "XY": ((-outer, -outer, 0.0), (outer, outer, end)),
        "YZ": ((0.0, -outer, -outer), (end, outer, outer)),
        "XZ": ((-outer, -end, -outer), (outer, 0.0, outer)),
    }[plane]
    return {
        "kind": "closed_form",
        "volume": volume,
        "area": surface,
        "centroid": list(centroid),
        "bounds": [list(box[0]), list(box[1])],
        "note": (
            "Analytic axial sections of a mitred gear, its keyway, relieved annulus and "
            "concentric paired flanges."
        ),
    }


_CAM = re.compile(
    r'^import cadquery as cq\n\nresult = \(\n    cq\.Workplane\("(?P<plane>XY|YZ|XZ)"\)\n'
    r"    \.polyline\((?P<outline>\[.*?\])\)\n    \.close\(\)\n"
    rf"    \.extrude\({_NUMBER}\)\n"
    r'    \.union\(\n        cq\.Workplane\("(?P=plane)"\)\n'
    rf"            \.transformed\(offset=cq\.Vector\(0, 0, {_NUMBER}\), "
    r"rotate=cq\.Vector\(0, 0, 0\)\)\n"
    rf"            \.cylinder\({_NUMBER}, {_NUMBER}\)\n    \)\n"
    r'    \.faces\("(?P<workface>>[XYZ])"\)\.workplane\(\)\n'
    rf"    (?:\.hole\({_NUMBER}\)|\.circle\({_NUMBER}\)\n    \.cutThruAll\(\))\n"
    r"(?P<blends>(?:    \.faces\(\"[<>][XYZ]\"\)\n    \.edges\(\)\n"
    r"    \.(?:chamfer|fillet)\([^\n]+\)\n){1,2})"
    r'    \.faces\("(?P=workface)"\)\.workplane\(\)\n'
    rf"    \.pushPoints\(\[\(0\.0, {_NUMBER}\)\]\)\n"
    rf"    \.rect\({_NUMBER}, {_NUMBER}\)\n    \.cutThruAll\(\)\n"
    r'(?:    \.cut\(\n        cq\.Workplane\("(?P=plane)"\)\n'
    rf"            \.transformed\(offset=cq\.Vector\({_NUMBER}, 0\.0, {_NUMBER}\), "
    r"rotate=cq\.Vector\(0, 0, 0\)\)\n"
    rf"            \.cylinder\({_NUMBER}, {_NUMBER}\)\n    \)\n)?"
    r"\)\n\n# Export\nshow_object\(result\)\n?$",
    re.S,
)
_CAM_BLEND = re.compile(
    rf'    \.faces\("([<>][XYZ])"\)\n    \.edges\(\)\n    \.(chamfer|fillet)\({_NUMBER}\)\n'
)


def cam_closed_form(text: str) -> dict[str, object]:
    """Measures of a cam with a blended polygon base and annular boss, bored through.

    A rectangular keyway opens into the bore. An optional off-axis hole has to
    clear the boss, bore, keyway and rim blend. Raises ValueError outside this
    arrangement.
    """
    match = _CAM.fullmatch(text)
    if match is None:
        raise ValueError("not a cam with axis-aligned blends and through cuts")
    (
        plane,
        polygon,
        depth,
        boss_center,
        height,
        outer_radius,
        workface,
        diameter,
        radius,
        blend_calls,
        offset,
        width,
        length,
        drill_x,
        drill_z,
        drill_depth,
        drill_radius,
    ) = match.groups()
    axis = {"XY": "Z", "YZ": "X", "XZ": "Y"}[plane]
    if workface != f">{axis}":
        raise ValueError("the cam's bores must run along its axis")
    w, h, hub = _num(depth), _num(height), _num(outer_radius)
    if abs(_num(boss_center) - h / 2 - w) > PLACEMENT_TOL:
        raise ValueError("the cam's boss does not start on the top of the plate")
    bore = _num(diameter) / 2 if diameter is not None else _num(radius)
    half_width, half_length = _num(width) / 2, _num(length) / 2
    start, reach = _num(offset) - half_length, _num(offset) + half_length
    if not (0 < half_width < bore and 0 <= start < math.sqrt(bore**2 - half_width**2) < reach):
        raise ValueError("the cam's keyway does not straddle the bore")

    blends: dict[bool, tuple[str, float]] = {}
    parsed_blends = _CAM_BLEND.findall(blend_calls)
    if len(parsed_blends) != blend_calls.count(".edges()"):
        raise ValueError("the cam's blend size must be a literal")
    for selector, mode, size in parsed_blends:
        on_boss = (selector[0] == ">") != (plane == "XZ")
        if selector[1] != axis or on_boss in blends:
            raise ValueError("the cam's rim blends must each select a separate axial end")
        blends[on_boss] = mode, _num(size)
    lower = blends.get(False, ("none", 0.0))
    upper = blends.get(True, ("none", 0.0))
    outline = [(_num(x), _num(y)) for x, y in _POINT.findall(polygon)]
    if len(outline) < 3 or len(outline) != polygon.count("("):
        raise ValueError("the cam's outline must contain literal point pairs")
    edges = list(zip(outline, [*outline[1:], outline[0]], strict=True))
    area, perimeter, turns, edges_length = _turns(outline)
    tangents = [math.tan(turn / 2) for turn in turns]
    total_turn = sum(tangents)
    near = min(_segment_distance(a, b) for a, b in edges)
    key_corner = math.hypot(half_width, reach)
    if not (
        0 <= lower[1] < w
        and 0 <= upper[1] < h
        and max(bore + upper[1], key_corner) < hub - upper[1]
        and hub < near
        and max(bore + lower[1], key_corner) < near - lower[1]
        and all(
            size > lower[1] * (abs(tangents[i]) + abs(tangents[(i + 1) % len(outline)]))
            for i, size in enumerate(edges_length)
        )
    ):
        raise ValueError("the cam's blend exceeds its section")

    extra_x = extra_r = 0.0
    drill_top = -math.inf  # where an off-axis bore that cuts into the boss ends in it
    if drill_x is not None:
        extra_x, extra_r = _num(drill_x), _num(drill_radius)
        clearance = min(
            _segment_distance((a[0] - extra_x, a[1]), (b[0] - extra_x, b[1])) for a, b in edges
        )
        if not (
            abs(_num(drill_z) - w / 2) <= PLACEMENT_TOL
            and _num(drill_depth) > w
            and 0 < extra_r < clearance - lower[1]
            and abs(extra_x) - extra_r > max(bore + max(lower[1], upper[1]), key_corner)
        ):
            raise ValueError("the cam's off-axis bore touches another feature")
        if abs(extra_x) - extra_r <= hub:
            drill_top = _num(drill_z) + _num(drill_depth) / 2
            if not w < drill_top < w + h:
                raise ValueError("the cam's off-axis bore leaves its boss through the top")

    def section(
        on_boss: bool, setback: float, drilled: bool = False
    ) -> tuple[float, float, float, float, float]:
        # The keyway walls are vertical. The bore is exposed everywhere except
        # the arc inside the keyway's rectangular cross-section. Below its end, an
        # off-axis bore takes the lens it shares with the boss's section (`_lens`).
        a = half_width
        r = bore + setback
        x0 = min(a, math.sqrt(max(0.0, r * r - reach * reach)))

        def arc_integral(x: float) -> float:
            return x * math.sqrt(r * r - x * x) + r * r * math.asin(x / r)

        def key_moment(x: float) -> float:
            return (reach * reach - r * r) * x + x**3 / 3

        aperture = math.pi * r * r + 2 * (a - x0) * reach - arc_integral(a) + arc_integral(x0)
        arc = 2 * r * (math.pi - math.asin(a / r) + math.asin(x0 / r))
        wall = 2 * (max(0.0, reach - math.sqrt(r * r - a * a)) + a - x0)
        my = key_moment(x0) - key_moment(a)
        if on_boss:
            lens = (0.0, 0.0, 0.0, 0.0)
            if drilled:
                lens = _lens(hub - setback, extra_r, abs(extra_x))
            return (
                math.pi * (hub - setback) ** 2 - aperture - lens[0],
                -math.copysign(lens[1], extra_x),
                my,
                arc + 2 * math.pi * (hub - setback) - lens[2],
                wall + lens[3],
            )
        base = area - setback * perimeter + setback**2 * total_turn
        mx, polygon_my = _offset_moment(outline, setback)
        drill = math.pi * extra_r * extra_r
        return (
            base - aperture - drill,
            mx - drill * extra_x,
            polygon_my + my,
            arc + perimeter - 2 * setback * total_turn,
            wall + 2 * math.pi * extra_r,
        )

    def segment(
        on_boss: bool, start_z: float, height_z: float, blend: tuple[str, float]
    ) -> list[float]:
        mode, size = blend
        thickness = height_z - size
        low = start_z + (0.0 if on_boss else size)
        middle = low + thickness / 2
        split = on_boss and low < drill_top < low + thickness
        pieces = [(low, drill_top, True), (drill_top, low + thickness, False)] if split else []
        drilled = on_boss and low + thickness <= drill_top
        base, mx, my, slope, straight = section(on_boss, 0.0, drilled)
        bulk = [
            base * thickness,
            base * thickness * middle,
            mx * thickness,
            my * thickness,
            (slope + straight) * thickness,
        ]
        if pieces:  # an off-axis bore ends in the boss's straight part
            bulk = [0.0] * 5
            for a, b, under in pieces:
                base, mx, my, slope, straight = section(on_boss, 0.0, under)
                piece = [base, base * (a + b) / 2, mx, my, slope + straight]
                bulk = [x + y * (b - a) for x, y in zip(bulk, piece, strict=True)]
        if not size:
            return bulk

        def rim(t: float) -> tuple[float, float, float, float, float]:
            if mode == "chamfer":
                setback, advance, dz, ds = size * t, size * t, size, math.sqrt(2) * size
            else:
                angle = math.pi / 2 * t
                ds = size * math.pi / 2
                setback, advance, dz = (
                    size * (1 - math.cos(angle)),
                    size * math.sin(angle),
                    ds * math.cos(angle),
                )
            z = start_z + (thickness + advance if on_boss else size - advance)
            base, mx, my, slanted, straight = section(on_boss, setback, on_boss and z < drill_top)
            return base * dz, base * z * dz, mx * dz, my * dz, slanted * ds + straight * dz

        cuts = [0.0, 1.0]
        if on_boss and start_z + thickness < drill_top < start_z + height_z:
            rise = (drill_top - start_z - thickness) / size
            cuts.append(rise if mode == "chamfer" else 2 / math.pi * math.asin(rise))
        for change in (reach - bore, key_corner - bore):
            if 0 < change < size:
                cuts.append(
                    change / size
                    if mode == "chamfer"
                    else 2 / math.pi * math.acos(1 - change / size)
                )
        intervals = tuple(itertools.pairwise(sorted(cuts)))

        def integrate_component(component: int) -> float:
            return sum(tanh_sinh(lambda t: rim(t)[component], lo, hi) for lo, hi in intervals)

        return [value + integrate_component(i) for i, value in enumerate(bulk)]

    volume, axial, mx, my, lateral = map(
        sum, zip(segment(False, 0.0, w, lower), segment(True, w, h, upper), strict=True)
    )
    flat = (
        section(False, lower[1])[0]
        + section(True, upper[1])[0]
        + section(False, 0.0)[0]
        - section(True, 0.0, drill_top > w)[0]
    )
    if drill_top > w:  # the off-axis bore's end, inside the boss
        rise = max(0.0, drill_top - (w + h - upper[1]))
        setback = 0.0
        if rise and upper[0] == "chamfer":
            setback = rise
        elif rise:
            setback = upper[1] - math.sqrt(upper[1] ** 2 - rise**2)
        flat += _lens(hub - setback, extra_r, abs(extra_x))[0]
    xs, ys = zip(*outline, strict=True)
    centroid = {"XY": (mx, my, axial), "YZ": (axial, mx, my), "XZ": (mx, -axial, my)}[plane]
    bounds = {
        "XY": ((min(xs), min(ys), 0.0), (max(xs), max(ys), w + h)),
        "YZ": ((0.0, min(xs), min(ys)), (w + h, max(xs), max(ys))),
        "XZ": ((min(xs), -w - h, min(ys)), (max(xs), 0.0, max(ys))),
    }[plane]
    return {
        "kind": "closed_form",
        "volume": volume,
        "area": flat + lateral,
        "centroid": [moment / volume for moment in centroid],
        "bounds": bounds,
        "note": (
            "Cross sections of the mitred polygon base and annular boss, less the bore "
            "and keyway; integration through each rim blend (tools/cq_closed_forms.py)."
        ),
    }


# --- A pan head screw: a shank, a filleted head and a slot across it ---------------------------
#
# A shank (a cylinder of radius `s` from z = 0 to `z1`), a head (radius `R`, from `z1` to
# `z1 + h`) whose top rim is filleted by `f`, and a box slot `lx x 2a x lz` across the head
# (through its whole width, `lx / 2 >= R`, its floor `zb` inside the head). Body of revolution
# less the strip `|y| < a` above `zb`. At the fillet's angle `t` (0 at the side, pi / 2 at the top)
# the head's radius is `rho = R - f + f cos t` at `z = z1 + h - f + f sin t`. A disc of radius
# `rho` cut by the strip has area `2 (a sqrt(rho^2 - a^2) + rho^2 asin(a / rho))`, the strip's
# rim patch on the torus `4 asin(a / rho) rho f dt` and each slot wall `2 sqrt(rho^2 - a^2)`
# per unit height; the floor is the strip's section at `zb`.

_SCREW = re.compile(
    r'^import cadquery as cq\n\nresult = \(\n    cq\.Workplane\("XY"\)\n'
    rf"(?:    \.circle\({_NUMBER}\)\n    \.extrude\({_NUMBER}\)\n"
    rf"|    \.transformed\(offset=cq\.Vector\({_NUMBER}, {_NUMBER}, {_NUMBER}\), "
    rf"rotate=cq\.Vector\(0, 0, 0\)\)\n    \.cylinder\({_NUMBER}, {_NUMBER}\)\n)"
    rf'    \.faces\(">Z"\)\.workplane\(\)\n    \.circle\({_NUMBER}\)\n    \.extrude\({_NUMBER}\)\n'
    rf'    \.edges\(">Z"\)\n    \.fillet\({_NUMBER}\)\n'
    r"    \.cut\(\n        cq\.Workplane\(\"XY\"\)\n"
    rf"            \.transformed\(offset=cq\.Vector\({_NUMBER}, {_NUMBER}, {_NUMBER}\), "
    r"rotate=cq\.Vector\(0, 0, 0\)\)\n"
    rf"            \.box\({_NUMBER}, {_NUMBER}, {_NUMBER}\)\n    \)\n\)\n\n"
    r"# Export\nshow_object\(result\)\n?$",
    re.S,
)


def screw_closed_form(text: str) -> dict[str, object]:
    """The `ClosedForm` JSON of a `pan_head_screw` program `_SCREW` reads.

    Raises `ValueError` for another program, or one outside what the formulas hold: a cylinder
    or slot off the axis, a fillet that is not inside the head, a slot narrower than the head or
    a floor below the head or above its top rim.
    """
    m = _SCREW.match(text)
    if m is None:
        raise ValueError("not a pan head screw")
    g = m.groups()
    if g[0] is not None:
        s, z1 = _num(g[0]), _num(g[1])
    else:
        ox, oy, oz = _num(g[2]), _num(g[3]), _num(g[4])
        height, s = _num(g[5]), _num(g[6])
        if ox != 0 or oy != 0:
            raise ValueError("a shank off the axis")
        z1 = oz + height / 2
        if oz - height / 2 != 0:
            raise ValueError("a shank that does not start at the origin")
    radius, h, f = _num(g[7]), _num(g[8]), _num(g[9])
    bx, by, bz, lx, ly, lz = (_num(g[i]) for i in range(10, 16))
    a = ly / 2
    zb = bz - lz / 2
    top = z1 + h
    if bx != 0 or by != 0:
        raise ValueError("a slot off the axis")
    if not (0 < s < radius and 0 < f < min(h, radius - a) and a > 0 and lx / 2 >= radius):
        raise ValueError("a screw outside the arrangement the closed form handles")
    if not (z1 <= zb < top and bz + lz / 2 >= top):
        raise ValueError("a slot that does not open the head's top")
    pi = math.pi
    zc = top - f

    def rho(t: float) -> float:
        return radius - f + f * math.cos(t)

    def strip(r: float) -> float:
        return 2 * (a * math.sqrt(r * r - a * a) + r * r * math.asin(a / r))

    half = pi / 2

    def over_fillet(g_of_t: Callable[[float], float]) -> float:
        return gauss(g_of_t, 0.0, half)

    # Body of revolution: the shank, the head and the fillet's removed ring.
    ring = over_fillet(lambda t: pi * (radius**2 - rho(t) ** 2) * f * math.cos(t))
    ring_moment = over_fillet(
        lambda t: (zc + f * math.sin(t)) * pi * (radius**2 - rho(t) ** 2) * f * math.cos(t)
    )
    v_shank = pi * s * s * z1
    v_head = pi * radius * radius * h
    revolved = v_shank + v_head - ring
    m_revolved = v_shank * z1 / 2 + v_head * (z1 + h / 2) - ring_moment
    # The strip above the floor.
    side = strip(radius) * (zc - zb)
    side_moment = strip(radius) * (zc * zc - zb * zb) / 2
    rim = over_fillet(lambda t: strip(rho(t)) * f * math.cos(t))
    rim_moment = over_fillet(lambda t: (zc + f * math.sin(t)) * strip(rho(t)) * f * math.cos(t))
    volume = revolved - side - rim
    moment = m_revolved - side_moment - rim_moment
    # Area: the revolved surface less its part in the strip, plus the slot's floor and walls.
    torus = over_fillet(lambda t: 2 * pi * rho(t) * f)
    torus_strip = over_fillet(lambda t: 4 * math.asin(a / rho(t)) * rho(t) * f)
    area = (
        pi * s * s  # the shank's end
        + 2 * pi * s * z1
        + pi * (radius**2 - s * s)
        + 2 * pi * radius * (h - f)
        + torus
        + pi * (radius - f) ** 2
    )
    area -= 4 * math.asin(a / radius) * radius * (zc - zb) + torus_strip
    area -= strip(radius - f)  # the top disc's part in the strip
    area += strip(radius)  # the floor
    wall = 2 * gauss(lambda z: 2 * math.sqrt(radius**2 - a * a), zb, zc)
    area += wall + 2 * over_fillet(lambda t: 2 * math.sqrt(rho(t) ** 2 - a * a) * f * math.cos(t))
    return {
        "kind": "closed_form",
        "volume": volume,
        "area": area,
        "centroid": [0.0, 0.0, moment / volume],
        "bounds": [[-radius, -radius, 0.0], [radius, radius, top]],
        "note": (
            "a shank and a head turned about z (the head's top rim filleted: Pappus-free "
            "quadrature over the fillet's angle) less the strip |y| < a of a slot across the head "
            "from its floor up: the section of a disc cut by the strip is 2 (a sqrt(r^2 - a^2) + "
            "r^2 asin(a / r)) (tools/cq_closed_forms.py, screw_closed_form): "
            f"shank radius {s} to z {z1}, head radius {radius} x {h}, fillet {f}, "
            f"slot half width {a} from z {zb}"
        ),
    }


# --- Boxes and cylinders on the axes: manifold_block and connecting_rod -------------------
#
# A part built of boxes and cylinders whose axes and faces are all along x, y or z, united
# and cut in the program's order, a box's top edges optionally chamfered (`Bevel`: each
# chamfer a plane holding the axis along its edge, so read along lines on it like the rest).
# Its measures are integrals over its boundary (the divergence theorem: V = 1/3 of the flux
# of x, the moment along j the flux of x_j^2/2 e_j), and every boundary patch lies on one of
# the solids' faces. Along a line on such a face
# (a cylinder's side along its axis, a flat face along one of its axes) each solid is one
# interval, found exactly, so the solid on either side of the face, and with it the boundary
# and its orientation, is exact interval arithmetic. What is left is one integral across the
# lines, smooth between the points where an interval appears or two ends cross: those points
# are found (`_piecewise`) and the integral is tanh-sinh quadrature between them.

# Two planes this close are one: the programs' decimal literals (a top at `h / 2`) do not add
# up exactly, and the kernels' own tolerance, 1e-7, is far above it.
COPLANAR_TOL = 1e-9
# Two interval ends this close, relative to the larger, are one point to `_piecewise`: the
# same point reached by two formulas rounds either way, and its order must not flicker.
TIE_REL = 1e-12
# `_piecewise` samples a range at this many points to find where the integrand's formula
# changes, and halves a bracket this many times to place a change (to the last bit).
SCAN_POINTS = 512
BISECT_STEPS = 64
# A change closer than this to a piece's end (relative to the range) is not split off: where
# an interval opens at a square root's zero, its argument rounds to either side of zero over
# ~1e-8 of the range, and the interval there is ~1e-8 long, so it moves the sum by < 1e-15.
FUZZ_REL = 1e-7
# More splits than this in one range is a formula that never settles: an error, not a result.
MAX_SPLITS = 10_000


@dataclass(frozen=True)
class Cuboid:
    """A box from `lo` to `hi`."""

    lo: Vec
    hi: Vec


@dataclass(frozen=True)
class Rod:
    """A cylinder along `axis` (0, 1, 2), radius `r`, from `lo` to `hi` along it; `centre`'s
    coordinate along the axis is not read."""

    axis: int
    centre: Vec
    r: float
    lo: float
    hi: float


@dataclass(frozen=True)
class Bevel:
    """A box from `lo` to `hi` whose four edges around its face toward +`axis` are chamfered
    by `c` (CadQuery's `edges(">A").chamfer(c)` on a box): the box less, along each of those
    edges, the wedge beyond the plane through the two lines `c` from it on its two faces. Two
    such planes meet at a corner along the mitre a box's chamfer makes, so the solid is the
    box's half-spaces and the four planes' (`_bevel_planes`), convex."""

    lo: Vec
    hi: Vec
    axis: int
    c: float


@dataclass(frozen=True)
class Round:
    """What a fillet of radius `r` along a straight edge on `axis` takes away (op "-", a convex
    edge) or adds (op "+", a concave one), from `lo` to `hi` along the axis: the r-by-r square
    at the edge (at `edge` on the two other axes, `_others(axis)` in order) on the side
    `toward` (+1 or -1 per axis), less the disc of radius r about the square's far corner.

    Read along a line on any axis it is one interval: a line along the axis is in or out, and
    a line across it, at u from the edge on one axis, runs from the edge to where it meets the
    disc, r - sqrt(r^2 - (r - u)^2) along the other. Its boundary is two flat faces in the
    planes of the edge's faces, two ends across the axis and a quarter of the cylinder."""

    axis: int
    edge: tuple[float, float]
    toward: tuple[int, int]
    r: float
    lo: float
    hi: float


Solid = Cuboid | Rod | Bevel | Round
Op = tuple[str, Solid]  # "+" unites, "-" cuts, in the program's order
Interval = tuple[float, float]
Signature = tuple[object, ...]
Integrand = Callable[[float], tuple[tuple[float, ...], Signature]]


def _others(a: int) -> tuple[int, int]:
    return ((1, 2), (0, 2), (0, 1))[a]


def _within(x: float, lo: float, hi: float, nudge: int) -> bool:
    """Whether `x`, moved by an infinitesimal `nudge` (-1, 0 or +1), is inside (lo, hi)."""
    if nudge and abs(x - lo) <= COPLANAR_TOL:
        return nudge > 0
    if nudge and abs(x - hi) <= COPLANAR_TOL:
        return nudge < 0
    return lo < x < hi


def _chord(r: float, off: float) -> float | None:
    """Half the chord of a circle of radius `r` at `off` from its centre, or None."""
    gap = (r - off) * (r + off)
    return math.sqrt(gap) if gap > 0 else None


def _sign(x: float) -> int:
    return (x > 0) - (x < 0)


def _toward(a: int, step: int) -> Vec:
    """An infinitesimal step along axis `a` (-1 for none), `step` = ±1, as a nudge."""
    v = [0.0, 0.0, 0.0]
    if a >= 0:
        v[a] = float(step)
    return v[0], v[1], v[2]


Plane = tuple[Vec, float]  # the half-space n . p <= k


def _bevel_planes(solid: Bevel) -> list[Plane]:
    """The half-spaces whose intersection is `solid`: the box's six, then the four chamfers'.

    A chamfer along the edge of the +a face and the face toward s along b cuts its two faces
    `c` from the edge, so its plane is s x_b + x_a = (s hi_b or -lo_b) + hi_a - c.
    """
    a = solid.axis
    planes: list[Plane] = []
    for j in range(3):
        planes.append((_toward(j, 1), solid.hi[j]))
        planes.append((_toward(j, -1), -solid.lo[j]))
    for b in _others(a):
        for s, edge in ((1, solid.hi[b]), (-1, -solid.lo[b])):
            n = [0.0, 0.0, 0.0]
            n[b], n[a] = float(s), 1.0
            planes.append(((n[0], n[1], n[2]), edge + solid.hi[a] - solid.c))
    return planes


def _clip(
    planes: Sequence[Plane], d: int, at: Vec, nudge: Vec, skip: Callable[[Vec], bool]
) -> tuple[Interval | None, object]:
    """Where the line along axis `d` through `at` lies inside the half-spaces but those `skip`
    names, and which planes bound it (its formula: where that changes, the integrand's does).

    A plane the line lies on (to `COPLANAR_TOL`) keeps it when `nudge` moves it inside, as
    `_within` does; a plane the nudge runs along keeps it only strictly inside.
    """
    lo, hi = -math.inf, math.inf
    lo_by, hi_by = -1, -1
    for m, (n, k) in enumerate(planes):
        if skip(n):
            continue
        rest = 0.0
        for j in _others(d):
            rest += n[j] * at[j]
        if n[d] == 0.0:
            gap = k - rest
            step = 0.0
            for j in range(3):
                step += n[j] * nudge[j]
            if step and abs(gap) <= COPLANAR_TOL:
                if step > 0:
                    return None, None
            elif not gap > 0:
                return None, None
            continue
        bound = (k - rest) / n[d]
        if n[d] > 0 and bound < hi:
            hi, hi_by = bound, m
        elif n[d] < 0 and bound > lo:
            lo, lo_by = bound, m
    if not hi > lo:
        return None, None
    return (lo, hi), (lo_by, hi_by)


def _on_line(solid: Solid, d: int, at: Vec, nudge: Vec) -> tuple[Interval | None, object]:
    """Where the line along axis `d` through `at` lies inside `solid` (its d coordinate is not
    read), and what that interval's formula depends on (None when there is none); `nudge`
    moves the line by an infinitesimal step in its direction."""
    if isinstance(solid, Bevel):
        return _clip(_bevel_planes(solid), d, at, nudge, lambda n: False)
    if isinstance(solid, Round):
        return _round_on_line(solid, d, at, nudge)
    if isinstance(solid, Cuboid):
        for j in _others(d):
            if not _within(at[j], solid.lo[j], solid.hi[j], _sign(nudge[j])):
                return None, None
        return (solid.lo[d], solid.hi[d]), True
    c = solid.centre
    if solid.axis == d:
        b, k = _others(d)
        if (at[b] - c[b]) ** 2 + (at[k] - c[k]) ** 2 < solid.r * solid.r:
            return (solid.lo, solid.hi), True
        return None, None
    a = solid.axis
    if not _within(at[a], solid.lo, solid.hi, _sign(nudge[a])):
        return None, None
    o = 3 - a - d
    w = _chord(solid.r, at[o] - c[o])
    return (None, None) if w is None else ((c[d] - w, c[d] + w), True)


def _round_reach(r: float, s: float) -> float:
    """How far a round of radius r reaches from its edge's face at s from the other face:
    r - sqrt(r^2 - (r - s)^2), written without the cancellation near s = r, where the disc
    is tangent to the face (subtracted as written, the reach there is lost for |r - s| below
    ~1e-8 r, a strip that moves an area by 1e-9)."""
    d = r - s
    return d * d / (r + math.sqrt(max(0.0, r * r - d * d)))


def _round_across(solid: Round, j: int, v: float, nudge: int) -> Interval | None:
    """Where a line across `solid` along its other axis `1 - j` (of `_others`) lies inside it,
    the line at `v` on axis j (nudged by `nudge`), or None."""
    s = solid.toward[j] * (v - solid.edge[j])
    if not _within(s, 0.0, solid.r, nudge * solid.toward[j]):
        return None
    reach = _round_reach(solid.r, s)
    if not reach > 0.0:
        return None
    o = 1 - j
    ends = sorted((solid.edge[o], solid.edge[o] + solid.toward[o] * reach))
    return ends[0], ends[1]


def _round_on_line(solid: Round, d: int, at: Vec, nudge: Vec) -> tuple[Interval | None, object]:
    a = solid.axis
    p, q = _others(a)
    if d == a:
        u = solid.toward[0] * (at[p] - solid.edge[0])
        v = solid.toward[1] * (at[q] - solid.edge[1])
        inside = (
            _within(u, 0.0, solid.r, _sign(nudge[p]) * solid.toward[0])
            and _within(v, 0.0, solid.r, _sign(nudge[q]) * solid.toward[1])
            and max(u, 0.0) < _round_reach(solid.r, v)
        )
        return ((solid.lo, solid.hi), True) if inside else (None, None)
    if not _within(at[a], solid.lo, solid.hi, _sign(nudge[a])):
        return None, None
    j = 1 if d == p else 0  # the axis the line is fixed on
    k = (p, q)[j]
    interval = _round_across(solid, j, at[k], _sign(nudge[k]))
    return (interval, True) if interval is not None else (None, None)


def _union(intervals: Sequence[Interval]) -> list[Interval]:
    out: list[Interval] = []
    for lo, hi in sorted(intervals):
        if hi <= lo:
            continue
        if out and lo <= out[-1][1]:
            out[-1] = (out[-1][0], max(hi, out[-1][1]))
        else:
            out.append((lo, hi))
    return out


def _minus(keep: Sequence[Interval], drop: Sequence[Interval]) -> list[Interval]:
    out: list[Interval] = []
    for interval in keep:
        pieces = [interval]
        for dlo, dhi in drop:
            cut: list[Interval] = []
            for lo, hi in pieces:
                if dhi <= lo or dlo >= hi:
                    cut.append((lo, hi))
                    continue
                if dlo > lo:
                    cut.append((lo, dlo))
                if dhi < hi:
                    cut.append((dhi, hi))
            pieces = cut
        out.extend(pieces)
    return out


def _both(one: Sequence[Interval], two: Sequence[Interval]) -> list[Interval]:
    out = [
        (max(alo, blo), min(ahi, bhi))
        for alo, ahi in one
        for blo, bhi in two
        if min(ahi, bhi) > max(alo, blo)
    ]
    return sorted(out)


def _length(intervals: Sequence[Interval]) -> float:
    total = 0.0
    for lo, hi in intervals:
        total += hi - lo
    return total


def _order(ends: Sequence[tuple[float, int]]) -> tuple[int, ...]:
    """The labels of `ends` in order of their values, tied ends in order of their labels."""
    out: list[int] = []
    group: list[int] = []
    last: float | None = None
    for value, label in sorted(ends):
        if last is not None and abs(value - last) > TIE_REL * max(abs(value), abs(last), 1.0):
            out.extend(sorted(group))
            group = []
        group.append(label)
        last = value
    out.extend(sorted(group))
    return tuple(out)


def _part_on_line(
    ops: Sequence[Op],
    d: int,
    at: Vec,
    nudge: Vec,
    own: tuple[int, bool] | None,
    seen: list[object],
    ends: list[tuple[float, int]],
) -> list[Interval]:
    """The part's intervals on a line, `ops` applied in order. `own` = (i, inside) puts the
    line just inside or just outside solid i (whose side it lies on); `seen` and `ends`
    collect what the integrand's formula depends on."""
    part: list[Interval] = []
    for i, (kind, solid) in enumerate(ops):
        if own is not None and own[0] == i:
            assert isinstance(solid, Rod | Round)
            interval = (solid.lo, solid.hi) if own[1] else None
            seen.append(interval is not None)
        else:
            interval, formula = _on_line(solid, d, at, nudge)
            seen.append(formula)
        if interval is None:
            continue
        ends.extend(((interval[0], 2 * i), (interval[1], 2 * i + 1)))
        part = _union([*part, interval]) if kind == "+" else _minus(part, [interval])
    return part


def _nodes(a: float, b: float) -> list[tuple[float, float]]:
    """`tanh_sinh`'s nodes and weights on [a, b], its points strictly inside."""
    half = (b - a) / 2
    steps = int(SINH_SPAN / SINH_STEP)
    out: list[tuple[float, float]] = []
    for k in range(-steps, steps + 1):
        t = k * SINH_STEP
        u = math.pi / 2 * math.sinh(t)
        weight = math.pi / 2 * math.cosh(t) / math.cosh(u) ** 2
        if u >= 0:
            x = b - half * 2 / (math.exp(2 * u) + 1)
        else:
            x = a + half * 2 / (math.exp(-2 * u) + 1)
        if a < x < b:
            out.append((x, weight * half * SINH_STEP))
    return out


def _change(f: Integrand, lo: float, hi: float) -> float:
    """Where `f`'s signature stops being the one it has at `lo`, between `lo` and `hi`."""
    first = f(lo)[1]
    for _ in range(BISECT_STEPS):
        mid = (lo + hi) / 2
        if not lo < mid < hi:
            break
        if f(mid)[1] == first:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def _piecewise(f: Integrand, a: float, b: float, seeds: Sequence[float] = ()) -> list[float]:
    """The integral over [a, b] of `f`'s values, split wherever its signature changes.

    `f` returns its values and a signature: what its formula depends on (which intervals
    exist, the order of their ends). Between two changes the values are smooth but for a
    square root at an end, which tanh-sinh integrates exactly. A scan finds the changes and
    bisection places them; a piece whose own nodes show a change the scan missed is split.
    `seeds` are points where a change may lie (a plane another solid ends at): each one and
    the midpoints between them are sampled too, so a window narrower than the scan's step
    between two of them is found.
    """
    mids = [a + (b - a) * (i + 0.5) / SCAN_POINTS for i in range(SCAN_POINTS)]
    inner = sorted(x for x in seeds if a < x < b)
    if inner:
        extra = [*inner, *((x + y) / 2 for x, y in itertools.pairwise([a, *inner, b]))]
        mids = sorted({*mids, *extra})
    sigs = [f(x)[1] for x in mids]
    cuts = [a]
    for i in range(SCAN_POINTS - 1):
        if sigs[i] != sigs[i + 1]:
            cuts.append(_change(f, mids[i], mids[i + 1]))
    cuts.append(b)
    total: list[float] = []
    pending = list(itertools.pairwise(cuts))
    splits = 0
    fuzz = FUZZ_REL * (b - a)
    while pending:
        lo, hi = pending.pop()
        if hi <= lo:
            continue
        sig = f((lo + hi) / 2)[1]
        evals = [(x, w, f(x)) for x, w in _nodes(lo, hi)]
        missed = [
            i
            for i, (x, _, (_, s)) in enumerate(evals)
            if s != sig and x - lo > fuzz and hi - x > fuzz
        ]
        if missed:
            splits += 1
            if splits > MAX_SPLITS:
                raise ValueError("an integrand whose formula never settles")
            i = max(missed, key=lambda m: min(evals[m][0] - lo, hi - evals[m][0]))
            j = i + 1 if evals[i][0] < (lo + hi) / 2 else i - 1
            x0, x1 = sorted((evals[i][0], evals[j][0]))
            cut = _change(f, x0, x1)
            pending.extend(((lo, cut), (cut, hi)))
            continue
        for _, w, (values, _) in evals:
            if not total:
                total = [0.0] * len(values)
            for m, value in enumerate(values):
                total[m] += w * value
    return total


def _flat_extent(
    solid: Solid, a: int, c: float, b: int, k: int, v: float
) -> tuple[Interval | None, object]:
    """A flat face of `solid` in the plane a = c (a box's, a cylinder's end) on the line along
    b at k = v, and what its formula depends on."""
    if isinstance(solid, Bevel):
        at = [0.0, 0.0, 0.0]
        at[a], at[k] = c, v
        still = (0.0, 0.0, 0.0)
        up, down = _toward(a, 1), _toward(a, -1)
        point = (at[0], at[1], at[2])
        return _clip(_bevel_planes(solid), b, point, still, lambda n: n in (up, down))
    if isinstance(solid, Round):
        extent = _round_face(solid, a, c, b, k, v)
        return extent, extent is not None
    extent = _axis_extent(solid, b, k, v)
    return extent, extent is not None


def _round_face(solid: Round, a: int, c: float, b: int, k: int, v: float) -> Interval | None:
    """`solid`'s flat face in the plane a = c (an end, or a face of its edge's) on the line
    along b at k = v."""
    axis = solid.axis
    p, q = _others(axis)
    if a == axis:  # an end: the square less the disc
        return _round_across(solid, (p, q).index(k), v, 0)
    j = (p, q).index(a)  # the face on the plane of the edge's face across axis `a`
    o = 1 - j
    span = sorted((solid.edge[o], solid.edge[o] + solid.toward[o] * solid.r))
    if b == axis:
        return (solid.lo, solid.hi) if span[0] < v < span[1] else None
    return (span[0], span[1]) if solid.lo < v < solid.hi else None


def _axis_extent(solid: Cuboid | Rod, b: int, k: int, v: float) -> Interval | None:
    if isinstance(solid, Cuboid):
        return (solid.lo[b], solid.hi[b]) if solid.lo[k] < v < solid.hi[k] else None
    w = _chord(solid.r, v - solid.centre[k])
    return None if w is None else (solid.centre[b] - w, solid.centre[b] + w)


# What `_flat`, `_slant` and `_side` return: area, three times the volume, and the three moments.
_ZERO = (0.0, 0.0, 0.0, 0.0, 0.0)


def _flat(
    ops: Sequence[Op], solid: Solid, a: int, side: int, c: float, before: Sequence[Solid]
) -> list[float]:
    """The part's boundary on a flat face of `solid` at `a = c`, its outward normal `side`.

    `before` holds the solids whose flat face in this plane was read already: what lies on
    them is not read twice.
    """
    b, k = _others(a)
    if isinstance(solid, Cuboid | Bevel):
        v0, v1 = solid.lo[k], solid.hi[k]
    elif isinstance(solid, Round):
        lo, hi = _solid_box(solid)
        v0, v1 = lo[k], hi[k]
    else:
        v0, v1 = solid.centre[k] - solid.r, solid.centre[k] + solid.r

    def f(v: float) -> tuple[tuple[float, ...], Signature]:
        at = [0.0, 0.0, 0.0]
        at[a], at[k] = c, v
        point = (at[0], at[1], at[2])
        extent, formula = _flat_extent(solid, a, c, b, k, v)
        if extent is None:
            return _ZERO, ("none",)
        seen: list[object] = [formula]
        ends: list[tuple[float, int]] = [(extent[0], -1), (extent[1], -2)]
        inside = _part_on_line(ops, b, point, _toward(a, -side), None, seen, ends)
        outside = _part_on_line(ops, b, point, _toward(a, side), None, seen, ends)
        face = [extent]
        for j, other in enumerate(before):
            known, formula = _flat_extent(other, a, c, b, k, v)
            seen.append(formula)
            if known is not None:
                face = _minus(face, [known])
                ends.extend(((known[0], -3 - 2 * j), (known[1], -4 - 2 * j)))
        out = _length(_both(_minus(inside, outside), face))  # the part's normal is +side
        into = _length(_both(_minus(outside, inside), face))  # its normal is -side
        net = (out - into) * side
        values = [out + into, c * net, 0.0, 0.0, 0.0]
        values[2 + a] = c * c / 2 * net
        return tuple(values), (tuple(seen), _order(ends))

    return _piecewise(f, v0, v1)


def _turn_seeds(
    ops: Sequence[Op], i: int, a: int, centre: tuple[float, float], r: float
) -> list[float]:
    """The angles on a circle of radius r about `centre` (on `_others(a)`) where a line along
    a may enter or leave another solid of `ops`: where the circle crosses a plane that solid's
    box ends at, or the circle of a cylinder along a, in [0, 2 pi)."""
    b, k = _others(a)
    out: list[float] = []

    def add(t: float) -> None:
        out.append(t % (2 * math.pi))

    for j, (_, solid) in enumerate(ops):
        if j == i:
            continue
        lo, hi = _solid_box(solid)
        for value in (lo[b], hi[b]):
            ratio = (value - centre[0]) / r
            if -1 < ratio < 1:
                add(math.acos(ratio))
                add(-math.acos(ratio))
        for value in (lo[k], hi[k]):
            ratio = (value - centre[1]) / r
            if -1 < ratio < 1:
                add(math.asin(ratio))
                add(math.pi - math.asin(ratio))
        if isinstance(solid, Rod) and solid.axis == a:
            dx, dy = solid.centre[b] - centre[0], solid.centre[k] - centre[1]
            dist = math.hypot(dx, dy)
            if dist and abs(r - solid.r) < dist < r + solid.r:
                spread = math.acos((r * r + dist * dist - solid.r**2) / (2 * r * dist))
                add(math.atan2(dy, dx) + spread)
                add(math.atan2(dy, dx) - spread)
    return out


def _side(ops: Sequence[Op], i: int, rod: Rod) -> list[float]:
    """The part's boundary on the side of cylinder i, over its angle by quarter turns."""
    a, r = rod.axis, rod.r
    b, k = _others(a)

    def f(t: float) -> tuple[tuple[float, ...], Signature]:
        cos, sin = math.cos(t), math.sin(t)
        at = [0.0, 0.0, 0.0]
        at[b] = rod.centre[b] + r * cos
        at[k] = rod.centre[k] + r * sin
        point = (at[0], at[1], at[2])
        seen: list[object] = []
        ends: list[tuple[float, int]] = []
        inside = _part_on_line(ops, a, point, _toward(-1, 0), (i, True), seen, ends)
        outside = _part_on_line(ops, a, point, _toward(-1, 0), (i, False), seen, ends)
        own = [(rod.lo, rod.hi)]
        out = _length(_both(_minus(inside, outside), own))
        into = _length(_both(_minus(outside, inside), own))
        net = out - into
        values = [r * (out + into), r * (at[b] * cos + at[k] * sin) * net, 0.0, 0.0, 0.0]
        values[2 + b] = r * at[b] ** 2 / 2 * cos * net
        values[2 + k] = r * at[k] ** 2 / 2 * sin * net
        return tuple(values), (tuple(seen), _order(ends))

    seeds = _turn_seeds(ops, i, a, (rod.centre[b], rod.centre[k]), r)
    total = [0.0] * 5
    for q in range(4):  # a quarter turn's ends are where a chord across it can touch zero
        part = _piecewise(f, q * math.pi / 2, (q + 1) * math.pi / 2, seeds)
        total = [x + y for x, y in zip(total, part or _ZERO, strict=True)]
    return total


def _round_side(ops: Sequence[Op], i: int, solid: Round) -> list[float]:
    """The part's boundary on the quarter cylinder of round i: `_side` over the quarter turn
    that faces the edge, the round lying outside the disc (its own side, just inside, is the
    disc's outside)."""
    a, r = solid.axis, solid.r
    b, k = _others(a)
    centre = (solid.edge[0] + solid.toward[0] * r, solid.edge[1] + solid.toward[1] * r)
    start = {(-1, -1): 0.0, (1, -1): 0.5, (1, 1): 1.0, (-1, 1): 1.5}[solid.toward] * math.pi
    # The arc lies strictly inside the square, off the edge's two faces toward `toward`; near
    # its tangent ends it is within an ulp of their planes, so it is nudged off them that way.
    shift = [0.0, 0.0, 0.0]
    shift[b], shift[k] = float(solid.toward[0]), float(solid.toward[1])
    nudge = (shift[0], shift[1], shift[2])

    def f(t: float) -> tuple[tuple[float, ...], Signature]:
        cos, sin = math.cos(t), math.sin(t)
        at = [0.0, 0.0, 0.0]
        at[b] = centre[0] + r * cos
        at[k] = centre[1] + r * sin
        point = (at[0], at[1], at[2])
        seen: list[object] = []
        ends: list[tuple[float, int]] = []
        inside = _part_on_line(ops, a, point, nudge, (i, False), seen, ends)
        outside = _part_on_line(ops, a, point, nudge, (i, True), seen, ends)
        own = [(solid.lo, solid.hi)]
        out = _length(_both(_minus(inside, outside), own))
        into = _length(_both(_minus(outside, inside), own))
        net = out - into
        values = [r * (out + into), r * (at[b] * cos + at[k] * sin) * net, 0.0, 0.0, 0.0]
        values[2 + b] = r * at[b] ** 2 / 2 * cos * net
        values[2 + k] = r * at[k] ** 2 / 2 * sin * net
        return tuple(values), (tuple(seen), _order(ends))

    seeds = _turn_seeds(ops, i, a, centre, r)
    return _piecewise(f, start, start + math.pi / 2, seeds) or list(_ZERO)


def _slant(ops: Sequence[Op], solid: Bevel, b: int, s: int) -> list[float]:
    """The part's boundary on `solid`'s chamfer along the edge of its +a face and the face
    toward s along b: the plane s x_b + x_a = K, read along lines on it along the third axis
    k, across them by w = x_a from hi_a - c to hi_a (x_b = s (K - w)).

    Its outward normal is n / sqrt(2) with n = s e_b + e_a and the area element sqrt(2) dw dk,
    so the flux of p through it is K per unit of w and k, and that of x_j^2/2 e_j is
    x_j^2/2 n_j; the area is sqrt(2) per unit.
    """
    a = solid.axis
    (k,) = [j for j in range(3) if j not in (a, b)]
    n = [0.0, 0.0, 0.0]
    n[b], n[a] = float(s), 1.0
    normal = (n[0], n[1], n[2])
    big = solid.hi[b] if s > 0 else -solid.lo[b]
    plane = big + solid.hi[a] - solid.c
    inward = (-normal[0], -normal[1], -normal[2])

    def f(w: float) -> tuple[tuple[float, ...], Signature]:
        at = [0.0, 0.0, 0.0]
        at[a], at[b] = w, s * (plane - w)
        point = (at[0], at[1], at[2])
        extent, formula = _clip(
            _bevel_planes(solid), k, point, (0.0, 0.0, 0.0), lambda m: m == normal
        )
        if extent is None:
            return _ZERO, ("none",)
        seen: list[object] = [formula]
        ends: list[tuple[float, int]] = [(extent[0], -1), (extent[1], -2)]
        inside = _part_on_line(ops, k, point, inward, None, seen, ends)
        outside = _part_on_line(ops, k, point, normal, None, seen, ends)
        face = [extent]
        out = _length(_both(_minus(inside, outside), face))  # the part's normal is +n
        into = _length(_both(_minus(outside, inside), face))  # its normal is -n
        net = out - into
        values = [math.sqrt(2) * (out + into), plane * net, 0.0, 0.0, 0.0]
        values[2 + b] = at[b] ** 2 / 2 * s * net
        values[2 + a] = w * w / 2 * net
        return tuple(values), (tuple(seen), _order(ends))

    return _piecewise(f, solid.hi[a] - solid.c, solid.hi[a])


def _solid_box(solid: Solid) -> Box:
    if isinstance(solid, Cuboid | Bevel):
        return solid.lo, solid.hi
    if isinstance(solid, Round):
        lo, hi = [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]
        lo[solid.axis], hi[solid.axis] = solid.lo, solid.hi
        for j, m in enumerate(_others(solid.axis)):
            lo[m], hi[m] = sorted((solid.edge[j], solid.edge[j] + solid.toward[j] * solid.r))
        return (lo[0], lo[1], lo[2]), (hi[0], hi[1], hi[2])
    lo = [solid.centre[i] - solid.r for i in range(3)]
    hi = [solid.centre[i] + solid.r for i in range(3)]
    lo[solid.axis], hi[solid.axis] = solid.lo, solid.hi
    return (lo[0], lo[1], lo[2]), (hi[0], hi[1], hi[2])


def _united_box(ops: Sequence[Op]) -> Box:
    boxes = [_solid_box(s) for kind, s in ops if kind == "+"]
    lo = tuple(min(box[0][i] for box in boxes) for i in range(3))
    hi = tuple(max(box[1][i] for box in boxes) for i in range(3))
    return (lo[0], lo[1], lo[2]), (hi[0], hi[1], hi[2])


def _check_bounds(ops: Sequence[Op], box: Box) -> None:
    """Refuse a part whose cuts take away the extreme of its united solids on some side.

    On each side some united solid reaches the box, and the part keeps material there: along
    a line on that solid's extreme face (a box's, scanned across it) or its side's extreme
    line, the part is not empty just inside.
    """
    for a in range(3):
        for end in (0, 1):
            extreme = box[end][a]
            step = 1 if end == 0 else -1
            found = False
            lines: list[tuple[int, Vec, Vec, tuple[int, bool] | None]]
            for i, (kind, solid) in enumerate(ops):
                if kind != "+" or _solid_box(solid)[end][a] != extreme:
                    continue
                if isinstance(solid, Rod) and solid.axis != a:
                    at = [solid.centre[0], solid.centre[1], solid.centre[2]]
                    at[a] = extreme
                    lines = [(solid.axis, (at[0], at[1], at[2]), _toward(a, step), (i, True))]
                else:
                    b, k = _others(a)
                    lo, hi = _solid_box(solid)
                    lines = []
                    for n in range(SCAN_POINTS):
                        at = [0.0, 0.0, 0.0]
                        at[a] = extreme
                        at[k] = lo[k] + (hi[k] - lo[k]) * (n + 0.5) / SCAN_POINTS
                        lines.append((b, (at[0], at[1], at[2]), _toward(a, step), None))
                for d, point, nudge, own in lines:
                    if _part_on_line(ops, d, point, nudge, own, [], []):
                        found = True
                        break
                if found:
                    break
            if not found:
                raise ValueError("a part whose cuts take away the extreme of its box")


def part_measures(ops: Sequence[Op]) -> tuple[float, float, Vec, Box]:
    """Volume, area, centroid and bounds of a part of boxes and cylinders on the axes."""
    totals = [0.0] * 5
    planes: list[tuple[int, float, Solid]] = []  # flat faces read so far
    for i, (_, solid) in enumerate(ops):
        faces: list[tuple[int, int, float]] = []  # axis, outward side, plane
        if isinstance(solid, Bevel):
            for b in _others(solid.axis):
                for s in (-1, 1):
                    part = _slant(ops, solid, b, s) or list(_ZERO)
                    totals = [x + y for x, y in zip(totals, part, strict=True)]
        if isinstance(solid, Cuboid | Bevel):
            faces = [
                (a, s, solid.hi[a] if s > 0 else solid.lo[a]) for a in range(3) for s in (-1, 1)
            ]
        elif isinstance(solid, Round):
            part = _round_side(ops, i, solid)
            totals = [x + y for x, y in zip(totals, part, strict=True)]
            p, q = _others(solid.axis)
            faces = [
                (solid.axis, -1, solid.lo),
                (solid.axis, 1, solid.hi),
                (p, -solid.toward[0], solid.edge[0]),
                (q, -solid.toward[1], solid.edge[1]),
            ]
        else:
            part = _side(ops, i, solid)
            totals = [x + y for x, y in zip(totals, part, strict=True)]
            faces = [(solid.axis, s, solid.hi if s > 0 else solid.lo) for s in (-1, 1)]
        for a, s, c in faces:
            before = [o for (pa, pc, o) in planes if pa == a and abs(pc - c) <= COPLANAR_TOL]
            part = _flat(ops, solid, a, s, c, before) or list(_ZERO)
            totals = [x + y for x, y in zip(totals, part, strict=True)]
            planes.append((a, c, solid))
    area, volume3, m_x, m_y, m_z = totals
    volume = volume3 / 3
    box = _united_box(ops)
    _check_bounds(ops, box)
    return volume, area, (m_x / volume, m_y / volume, m_z / volume), box


# CadQuery's planes: each one's local x, y and normal in global coordinates.
_PLANES: dict[str, tuple[Vec, Vec, Vec]] = {
    "XY": ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
    "XZ": ((1.0, 0.0, 0.0), (0.0, 0.0, 1.0), (0.0, -1.0, 0.0)),
    "YZ": ((0.0, 1.0, 0.0), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0)),
}
Frame = tuple[Vec, Vec, Vec, Vec]  # origin, x, y, normal


def _at(frame: Frame, u: float, v: float, w: float) -> Vec:
    o, x, y, n = frame
    p = [o[i] + u * x[i] + v * y[i] + w * n[i] for i in range(3)]
    return p[0], p[1], p[2]


def _axis(n: Vec) -> int:
    (axis,) = [i for i in range(3) if abs(n[i]) == 1.0]
    return axis


def _cross(u: Vec, v: Vec) -> Vec:
    return (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])


def _top(ops: Sequence[Op], a: int, sign: int = 1) -> float:
    """The plane of `faces(">A")` (`sign` +1) or `faces("<A")` (-1): CadQuery keeps the faces
    whose centre lies furthest along +A or -A.

    That is the outermost flat face of a united solid facing that way (a box's, or a
    cylinder's end on that axis). A cut leaves faces inside the part, behind it. A cylinder
    across the axis has its side's centre on its own mid-plane only when the whole part is
    symmetric about that plane, which is checked; that plane must lie behind the face.
    """
    top = -math.inf
    for kind, solid in ops:
        if kind == "+" and isinstance(solid, Cuboid | Bevel):
            top = max(top, sign * (solid.hi[a] if sign > 0 else solid.lo[a]))
        elif kind == "+" and isinstance(solid, Rod) and solid.axis == a:
            top = max(top, sign * (solid.hi if sign > 0 else solid.lo))
    for kind, solid in ops:
        if kind == "+" and isinstance(solid, Rod) and solid.axis != a:
            mid = solid.centre[a]
            for _, other in ops:
                lo, hi = _solid_box(other)
                if abs((lo[a] - mid) + (hi[a] - mid)) > PLACEMENT_TOL:
                    raise ValueError("a cylinder's side whose centre this tool cannot place")
            if not sign * mid < top:
                raise ValueError("a cylinder's side beyond the selected face")
    return sign * top


def _made(plane: str, offset: Vec, call: str, args: str, turned: bool = False) -> Solid:
    """`Workplane(plane).transformed(offset=offset).box(...)` or `.cylinder(h, r)`; `turned`,
    `rotate=(90, 0, 0)`, turns the plane about its x so that its normal is its old -y, which
    only a cylinder's axis reads (along the plane's y)."""
    x, y, n = _PLANES[plane]
    o = _at(((0.0, 0.0, 0.0), x, y, n), *offset)
    values = [_num(v) for v in args.split(",")]
    if turned:
        if call != "cylinder" or len(values) != 2:
            raise ValueError(f"a turned solid this tool does not read: {call}({args})")
        h, r = values
        a = _axis(y)
        return Rod(a, o, r, o[a] - h / 2, o[a] + h / 2)
    if call == "box" and len(values) == 3:
        half = [sum(abs(values[j] * (x, y, n)[j][i]) / 2 for j in range(3)) for i in range(3)]
        return Cuboid(
            (o[0] - half[0], o[1] - half[1], o[2] - half[2]),
            (o[0] + half[0], o[1] + half[1], o[2] + half[2]),
        )
    if call == "cylinder" and len(values) == 2:
        h, r = values
        a = _axis(n)
        return Rod(a, o, r, o[a] - h / 2, o[a] + h / 2)
    raise ValueError(f"a solid this tool does not read: {call}({args})")


_CALL = re.compile(r"\.(\w+)\(((?:[^()]|\((?:[^()]|\([^()]*\))*\))*)\)")
_MADE = re.compile(
    rf'^\s*cq\.Workplane\("(XY|XZ|YZ)"\)\s*'
    rf"(?:\.transformed\(offset=cq\.Vector\({_NUMBER}, {_NUMBER}, {_NUMBER}\), "
    rf"rotate=cq\.Vector\((0|90), 0, 0\)\)\s*)?"
    rf"\.(box|cylinder)\(([^()]*)\)\s*$"
)
# A stadium prism: `slot2D(length, diameter, angle)` (0 or 90 degrees) extruded both ways.
_MADE_SLOT = re.compile(
    rf'^\s*cq\.Workplane\("(XY|XZ|YZ)"\)\s*'
    rf"\.transformed\(offset=cq\.Vector\({_NUMBER}, {_NUMBER}, {_NUMBER}\), "
    rf"rotate=cq\.Vector\(0, 0, 0\)\)\s*"
    rf"\.slot2D\({_NUMBER}, {_NUMBER}, (0|90)\)\s*\.extrude\({_NUMBER}, both=True\)\s*$"
)


def _stadium(plane: str, made: re.Match[str]) -> list[Solid]:
    """The box and two cylinders a `_MADE_SLOT` stadium prism unites: the slot's straight part
    and its two round ends, from -h to h along the plane's normal."""
    x, y, n = _PLANES[plane]
    offset = (_num(made[2]), _num(made[3]), _num(made[4]))
    o = _at(((0.0, 0.0, 0.0), x, y, n), *offset)
    length, diameter, h = _num(made[5]), _num(made[6]), _num(made[8])
    if not length > diameter > 0 or not h > 0:
        raise ValueError("a slot this tool does not read")
    along, across = (x, y) if made[7] == "0" else (y, x)
    r, d = diameter / 2, (length - diameter) / 2
    half = [abs(along[i]) * d + abs(across[i]) * r + abs(n[i]) * h for i in range(3)]
    box = Cuboid(
        (o[0] - half[0], o[1] - half[1], o[2] - half[2]),
        (o[0] + half[0], o[1] + half[1], o[2] + half[2]),
    )
    a = _axis(n)
    ends = [_at((o, along, across, n), s * d, 0.0, 0.0) for s in (-1, 1)]
    return [box, *(Rod(a, c, r, o[a] - h, o[a] + h) for c in ends)]


def _axial_rounds(ops: Sequence[Op], a: int, r: float) -> list[Op]:
    """The rounds of `edges("|A").fillet(r)` on the part `ops` builds (`Round`).

    Its straight edges along A lie where a flat face along A of one box meets one of another
    (or the same) box: on each such line, the part just off it in each of the four quadrants
    around it is read along A, exactly. Where one quadrant holds material the edge is convex
    and its round is cut ("-"); where three do, concave and its round is united ("+"); two
    opposite quadrants are refused. A convex round runs on through a stretch of the line
    outside the part (a chamfer above a corner): its square still meets the chamfer, and
    nothing else is there. A cylinder along A that a flat face along A crosses would give
    straight edges this does not read, and a solid that meets a round's square but neither
    holds the whole square nor lies on the edge's faces is a fillet this does not model:
    both raise `ValueError`. A cylinder's seam is not an edge (ADR-0020).
    """
    p, q = _others(a)
    boxes = [s for _, s in ops if isinstance(s, Cuboid | Bevel)]

    def planes(j: int) -> list[float]:
        out: list[float] = []
        for value in sorted(c for s in boxes for c in (s.lo[j], s.hi[j])):
            if not out or value - out[-1] > COPLANAR_TOL:
                out.append(value)
        return out

    for _, rod in ops:
        if not isinstance(rod, Rod) or rod.axis != a:
            continue
        for s in boxes:
            for j, o in ((p, q), (q, p)):
                for c in (s.lo[j], s.hi[j]):
                    if (
                        abs(c - rod.centre[j]) < rod.r + COPLANAR_TOL
                        and s.lo[o] < rod.centre[o] + rod.r
                        and s.hi[o] > rod.centre[o] - rod.r
                        and s.lo[a] < rod.hi
                        and s.hi[a] > rod.lo
                    ):
                        raise ValueError("a cylinder along the fillet's axis crossed by a face")
    lo_box, hi_box = _united_box(ops)
    found: list[Op] = []
    for big_p in planes(p):
        for big_q in planes(q):
            at = [0.0, 0.0, 0.0]
            at[p], at[q] = big_p, big_q
            point = (at[0], at[1], at[2])
            quads: dict[tuple[int, int], list[Interval]] = {}
            cuts = {lo_box[a], hi_box[a]}
            for sp in (-1, 1):
                for sq in (-1, 1):
                    shift = [0.0, 0.0, 0.0]
                    shift[p], shift[q] = float(sp), float(sq)
                    nudge = (shift[0], shift[1], shift[2])
                    quads[(sp, sq)] = _part_on_line(ops, a, point, nudge, None, [], [])
                    cuts.update(x for interval in quads[(sp, sq)] for x in interval)
            ends = sorted(cuts)
            runs: list[tuple[float, float, frozenset[tuple[int, int]]]] = []
            for s0, s1 in itertools.pairwise(ends):
                mid = (s0 + s1) / 2
                filled = frozenset(k for k, iv in quads.items() if any(x < mid < y for x, y in iv))
                if runs and runs[-1][2] == filled:
                    runs[-1] = (runs[-1][0], s1, filled)
                else:
                    runs.append((s0, s1, filled))
            for n, (s0, s1, filled) in enumerate(runs):
                if (
                    len(filled) == 2
                    and len({sp for sp, _ in filled}) == 2
                    and len({sq for _, sq in filled}) == 2
                ):
                    raise ValueError("an edge between two opposite quadrants")
                if len(filled) == 1:
                    (toward,) = filled
                    if n > 0 and not runs[n - 1][2]:
                        s0 = runs[n - 1][0]
                    if n + 1 < len(runs) and not runs[n + 1][2]:
                        s1 = runs[n + 1][1]
                    found.append(("-", Round(a, (big_p, big_q), toward, r, s0, s1)))
                elif len(filled) == 3:
                    (toward,) = {(sp, sq) for sp in (-1, 1) for sq in (-1, 1)} - filled
                    found.append(("+", Round(a, (big_p, big_q), toward, r, s0, s1)))
    for n, (_, made) in enumerate(found):
        assert isinstance(made, Round)
        lo, hi = _solid_box(made)
        for _, other in [*ops, *found[:n], *found[n + 1 :]]:
            olo, ohi = _solid_box(other)
            if not all(olo[j] < hi[j] and ohi[j] > lo[j] for j in range(3)):
                continue
            holds = all(
                olo[j] <= lo[j] + COPLANAR_TOL and ohi[j] >= hi[j] - COPLANAR_TOL for j in range(3)
            )
            on_faces = isinstance(other, Cuboid | Bevel) and any(
                abs(c - made.edge[i]) <= COPLANAR_TOL
                for i, j in enumerate((p, q))
                for c in (other.lo[j], other.hi[j])
            )
            if not (holds or on_faces) or isinstance(other, Round):
                raise ValueError("a fillet whose round meets another feature")
    if not found:
        raise ValueError("a fillet on no straight edge")
    return [op for op in found if op[0] == "-"] + [op for op in found if op[0] == "+"]


def _face_rounds(ops: Sequence[Op], selected: tuple[int, int], args: str) -> list[Op]:
    """The rounds of `faces(">A").fillet(r)` right after the first box: its +A face's four
    edges, each round along the whole edge. Two meet at a corner, whose edge along A stays
    sharp, where the two cylinders cross on the corner's mitre plane: the part there is what
    lies under both, so the rounds are cut one after the other (`Round`)."""
    a, sign = selected
    box = ops[0][1] if len(ops) == 1 else None
    if sign < 0 or not isinstance(box, Cuboid) or "," in args:
        raise ValueError("a face fillet this tool does not read")
    r = _num(args)
    span = [box.hi[j] - box.lo[j] for j in range(3)]
    if not 0 < r < min(span[a], *(span[j] / 2 for j in _others(a))):
        raise ValueError("a face fillet that meets another face")
    out: list[Op] = []
    for b in _others(a):
        (k,) = [j for j in range(3) if j not in (a, b)]
        p, q = _others(k)
        for side in (-1, 1):
            edge = [0.0, 0.0, 0.0]
            toward = [0, 0, 0]
            edge[a], toward[a] = box.hi[a], -1
            edge[b] = box.hi[b] if side > 0 else box.lo[b]
            toward[b] = -side
            out.append(
                ("-", Round(k, (edge[p], edge[q]), (toward[p], toward[q]), r, box.lo[k], box.hi[k]))
            )
    return out


def part_ops(text: str) -> list[Op]:
    """The axis-aligned boxes and cylinders a program unites and cuts.

    Read by CadQuery 2.3.0's rules, which `arris_gym.cq` follows (ADR-0017, ADR-0018): a
    box or a cylinder is centred on its workplane, a cylinder along the plane's normal;
    `faces(">A").workplane()` or `faces("<A").workplane()` (once or twice, ADR-0018 rule 5)
    is the plane of the outermost face along +A or -A (`_top`), its x `(0, 0, 1)` crossed
    with its normal (+x for a normal along z), its origin the previous origin projected onto
    it; `pushPoints` are points in that plane; `hole(d)` and `cboreHole(d, D, h)` bore from
    each point (the origin when none) against the normal for `largestDimension()`, the
    diagonal of the part's box (so through it), the counterbore a second cylinder of D to h
    deep, and `hole(d, depth=h)` to h deep. `edges(">A").chamfer(c)` or
    `faces(">A").chamfer(c)` right after the first box is the four edges of its +A face (the
    edges whose centre lies furthest along A, the face's own) chamfered by c (`Bevel`), c
    short of half each side across A and of the box's depth along it. A rectangle at the
    workplane's origin, or circles at its points, cut along the whole normal
    (`cutThruAll`) or `cutBlind(-h)` h deep against it; `center` moves the origin in that
    plane. `edges("|A").fillet(r)` rounds every straight edge along A (`_axial_rounds`).
    Raises `ValueError` for any other call.
    """
    m = re.search(r'result = \(\n\s*cq\.Workplane\("(XY|XZ|YZ)"\)', text)
    if m is None:
        raise ValueError("not a part this tool reads")
    plane = m.group(1)
    x, y, n = _PLANES[plane]
    body = text[m.end() : text.index("\n)\n", m.end())]
    ops: list[Op] = []
    frame: Frame = ((0.0, 0.0, 0.0), x, y, n)
    points: list[Vec] | None = None
    rectangle: tuple[float, float] | None = None
    circles: float | None = None
    selected: tuple[int, int] | None = None
    edged: int | None = None
    filleted: int | None = None
    origin_offset: Vec | None = None  # a `transformed` before the stock, which centres it

    def through() -> tuple[int, int, float, float]:
        """The workplane's normal axis and sign, its plane along it, and the part's diagonal."""
        a = _axis(frame[3])
        lo, hi = _united_box(ops)
        return a, int(frame[3][a]), frame[0][a], math.dist(lo, hi)

    for call in _CALL.finditer(body):
        name, args = call.group(1), call.group(2)
        if edged is not None and name != "chamfer":
            raise ValueError("edges this tool does not blend")
        if filleted is not None and name != "fillet":
            raise ValueError("edges this tool does not round")
        if rectangle is not None and name not in ("cutThruAll", "cutBlind"):
            raise ValueError("a rectangle this tool does not consume")
        if circles is not None and name != "cutBlind":
            raise ValueError("circles this tool does not consume")
        if selected is not None and name not in ("faces", "workplane", "chamfer", "fillet"):
            raise ValueError("faces this tool does not read")
        if name in ("box", "cylinder"):
            if ops:
                raise ValueError("a second solid on the chain")
            ops.append(("+", _made(plane, origin_offset or (0.0, 0.0, 0.0), name, args)))
        elif name in ("union", "cut"):
            kind = "+" if name == "union" else "-"
            slot = _MADE_SLOT.match(args)
            made = _MADE.match(args)
            if slot is not None and slot.group(1) == plane:
                ops.extend((kind, piece) for piece in _stadium(plane, slot))
            elif made is not None and made.group(1) == plane:
                offset = (
                    _num(made.group(2) or "0"),
                    _num(made.group(3) or "0"),
                    _num(made.group(4) or "0"),
                )
                turned = made.group(5) == "90"
                ops.append((kind, _made(plane, offset, made.group(6), made.group(7), turned)))
            else:
                raise ValueError(f"a {name} this tool does not read")
            points = None
        elif name == "transformed" and not ops and origin_offset is None:
            moved = re.fullmatch(
                rf"offset=cq\.Vector\({_NUMBER}, {_NUMBER}, {_NUMBER}\), "
                r"rotate=cq\.Vector\(0, 0, 0\)",
                args,
            )
            if moved is None:
                raise ValueError("a transformed stock this tool does not read")
            origin_offset = (_num(moved[1]), _num(moved[2]), _num(moved[3]))
            frame = (_at(frame, *origin_offset), frame[1], frame[2], frame[3])
        elif name == "edges" and re.fullmatch(r'"\|([XYZ])"', args):
            filleted = "XYZ".index(args[2])
        elif name == "fillet" and selected is not None:
            ops.extend(_face_rounds(ops, selected, args))
            selected = None
        elif name == "fillet":
            if filleted is None or "," in args or not _num(args) > 0:
                raise ValueError("a fillet this tool does not read")
            ops.extend(_axial_rounds(ops, filleted, _num(args)))
            filleted = None
            points = None
        elif name == "edges":
            chosen = re.fullmatch(r'">([XYZ])"', args)
            if chosen is None or len(ops) != 1 or not isinstance(ops[0][1], Cuboid):
                raise ValueError(f"edges this tool does not read: {args}")
            edged = "XYZ".index(chosen.group(1))
        elif name == "chamfer":
            if edged is None and selected is not None and selected[1] > 0:
                edged, selected = selected[0], None
            box = ops[0][1] if edged is not None and len(ops) == 1 else None
            if not isinstance(box, Cuboid) or edged is None or "," in args:
                raise ValueError("a chamfer this tool does not read")
            c = _num(args)
            span = [box.hi[j] - box.lo[j] for j in range(3)]
            if not 0 < c < min(span[edged], *(span[j] / 2 for j in _others(edged))):
                raise ValueError("a chamfer that meets another face")
            ops[0] = ("+", Bevel(box.lo, box.hi, edged, c))
            edged = None
        elif name == "faces":
            chosen = re.fullmatch(r'"([<>])([XYZ])"', args)
            if chosen is None:
                raise ValueError(f"a selector this tool does not read: {args}")
            a = "XYZ".index(chosen.group(2))
            chosen_face = (a, 1 if chosen.group(1) == ">" else -1)
            if selected is not None and selected != chosen_face:
                raise ValueError("faces on faces of another direction")
            selected = chosen_face
        elif name == "workplane" and args == "":
            if selected is None:
                raise ValueError("a workplane on no faces")
            a, sign = selected
            normal = [0.0, 0.0, 0.0]
            normal[a] = float(sign)
            nv = (normal[0], normal[1], normal[2])
            xd = _cross((0.0, 0.0, 1.0), nv)
            if math.hypot(*xd) == 0.0:
                xd = (1.0, 0.0, 0.0)
            origin = list(frame[0])
            origin[a] = _top(ops, a, sign)
            frame = ((origin[0], origin[1], origin[2]), xd, _cross(nv, xd), nv)
            points = [frame[0]]
            selected = None
        elif name == "pushPoints":
            pairs = re.findall(rf"\({_NUMBER}, {_NUMBER}\)", args)
            if not pairs or len(pairs) != args.count("(") or points is None:
                raise ValueError("points this tool does not read")
            points = [_at(frame, _num(u), _num(v), 0.0) for u, v in pairs]
        elif name == "center":
            if points != [frame[0]]:
                raise ValueError("a center on no workplane")
            u, v = (_num(value) for value in args.split(","))
            frame = (_at(frame, u, v, 0.0), frame[1], frame[2], frame[3])
            points = [frame[0]]
        elif name == "rect":
            if points != [frame[0]]:
                raise ValueError("a rectangle on no workplane origin")
            width, height = (_num(value) for value in args.split(","))
            if min(width, height) <= 0.0:
                raise ValueError("a non-positive rectangle dimension")
            rectangle = (width, height)
        elif name == "circle":
            if points is None or "," in args or not _num(args) > 0:
                raise ValueError("a circle this tool does not read")
            circles = _num(args)
        elif name in ("cutThruAll", "cutBlind") and (rectangle or circles) is not None:
            a, sign, at, depth = through()
            if name == "cutThruAll" and args == "":
                box_lo, box_hi = _united_box(ops)
                near, far = box_lo[a] - depth, box_hi[a] + depth
            elif name == "cutBlind" and re.fullmatch(_NUMBER, args) and _num(args) < 0:
                near, far = at, at + sign * _num(args)
            else:
                raise ValueError(f"a {name} this tool does not read")
            extent = (min(near, far), max(near, far))
            if rectangle is not None:
                width, height = rectangle
                corner1 = list(_at(frame, -width / 2, -height / 2, 0.0))
                corner2 = list(_at(frame, width / 2, height / 2, 0.0))
                corner1[a], corner2[a] = extent
                xs, ys, zs = [sorted(pair) for pair in zip(corner1, corner2, strict=True)]
                ops.append(("-", Cuboid((xs[0], ys[0], zs[0]), (xs[1], ys[1], zs[1]))))
            else:
                assert circles is not None
                assert points is not None
                if name == "cutThruAll":
                    raise ValueError("circles cut through: this tool reads them as holes")
                ops.extend(("-", Rod(a, p, circles, extent[0], extent[1])) for p in points)
            rectangle = circles = None
            points = None
        elif name in ("hole", "cboreHole"):
            if points is None:
                raise ValueError("a hole on no workplane")
            a, sign, top, depth = through()
            lo, hi = _united_box(ops)
            if top - sign * depth >= lo[a] if sign > 0 else top - sign * depth <= hi[a]:
                raise ValueError("a hole this tool does not read")
            parts = [v.strip() for v in args.split(",")]
            if name == "hole" and len(parts) == 2 and parts[1].startswith("depth="):
                depth = _num(parts[1].removeprefix("depth="))
                values = [_num(parts[0])]
            else:
                values = [_num(v) for v in parts]
            if len(values) != (1 if name == "hole" else 3) or not depth > 0:
                raise ValueError("a hole this tool does not read")
            # Each bore from `start` to `end` behind the plane, along the normal's axis.
            bores = (
                [(values[0] / 2, 0.0, depth)]
                if name == "hole"
                else [(values[0] / 2, values[2], depth), (values[1] / 2, 0.0, values[2])]
            )
            for p in points:
                for radius, start, end in bores:
                    span = sorted((top - sign * start, top - sign * end))
                    ops.append(("-", Rod(a, p, radius, span[0], span[1])))
            points = None
        else:
            raise ValueError(f"a call this tool does not read: {name}")
    if edged is not None or filleted is not None:
        raise ValueError("edges this tool does not blend")
    if rectangle is not None or circles is not None:
        raise ValueError("an unconsumed profile")
    return ops


def part_closed_form(text: str) -> dict[str, object]:
    """The `ClosedForm` JSON of an axis-aligned part that `part_ops` reads."""
    ops = part_ops(text)
    volume, area, centroid, bounds = part_measures(ops)
    solids = "; ".join(
        f"{kind} {'cylinder' if isinstance(s, Rod) else 'box'} {s}" for kind, s in ops
    )
    return {
        "kind": "closed_form",
        "volume": volume,
        "area": area,
        "centroid": list(centroid),
        "bounds": [list(bounds[0]), list(bounds[1])],
        "note": (
            "boxes and cylinders on the axes, united (+) and cut (-) in order; volume and "
            "moments are the flux of x/3 and x_j^2/2 through the boundary (divergence theorem), "
            "each face's boundary patch exact interval arithmetic along lines on it and one "
            f"integral across them (tools/cq_closed_forms.py, part_measures): {solids}"
        ),
    }


_ANGLE_FILLET = re.compile(rf'    \.edges\("\|([XYZ])"\)\n    \.fillet\({_NUMBER}\)\n')


def _rounded_angle_form(text: str, fillet: re.Match[str]) -> dict[str, object]:
    """A rectangular L, with six rounded axial edges and disjoint bores."""
    ops = part_ops(text[: fillet.start()] + text[fillet.end() :])
    axis = "XYZ".index(fillet[1])
    radius = _num(fillet[2])
    if len(ops) < 2:
        raise ValueError("rounded angle without a through rectangle")
    (add, stock), (subtract, tool), *bores = ops
    if (
        add != "+"
        or subtract != "-"
        or not isinstance(stock, Cuboid)
        or not isinstance(tool, Cuboid)
    ):
        raise ValueError("rounded angle without a rectangular stock and cut")
    if tool.lo[axis] > stock.lo[axis] or tool.hi[axis] < stock.hi[axis]:
        raise ValueError("rounded angle cut does not reach both ends")
    depth = stock.hi[axis] - stock.lo[axis]
    axes = _others(axis)
    starts, signs, spans, walls = [], [], [], []
    for k in axes:
        lo, hi, cut_lo, cut_hi = stock.lo[k], stock.hi[k], tool.lo[k], tool.hi[k]
        if abs(cut_hi - hi) <= PLACEMENT_TOL and lo < cut_lo < hi:
            start, sign, wall = lo, 1, cut_lo - lo
        elif abs(cut_lo - lo) <= PLACEMENT_TOL and lo < cut_hi < hi:
            start, sign, wall = hi, -1, hi - cut_hi
        else:
            raise ValueError("rounded angle cut does not touch one outside edge per axis")
        starts.append(start)
        signs.append(sign)
        spans.append(hi - lo)
        walls.append(wall)
    u, v = spans
    a, b = walls
    if not 0 < 2 * radius < min(a, b, u - a, v - b):
        raise ValueError("rounded angle fillets meet another corner")
    vertices = ((0.0, 0.0), (u, 0.0), (u, b), (a, b), (a, v), (0.0, v))
    for kind, bore in bores:
        if kind != "-" or not isinstance(bore, Rod) or bore.axis != axis:
            raise ValueError("rounded angle with a non-axial bore")
        x, y = [
            (bore.centre[k] - start) * sign
            for k, start, sign in zip(axes, starts, signs, strict=True)
        ]
        # The fillet changes material only in the radius-by-radius square at each tip.
        if any(
            math.hypot(max(abs(x - p) - radius, 0), max(abs(y - q) - radius, 0)) <= bore.r
            for p, q in vertices
        ):
            raise ValueError("rounded angle bore touches a fillet")
    volume, area, centroid, bounds = part_measures(ops)
    removed = radius**2 * (1 - math.pi / 4)
    corner_moment = radius**3 * (5 / 6 - math.pi / 4)
    moment = [coordinate * volume for coordinate in centroid]
    removed_volume = 0.0
    removed_area = 0.0
    for i, vertex in enumerate(vertices):
        previous = vertices[i - 1]
        following = vertices[(i + 1) % len(vertices)]
        sign = -1 if i == 3 else 1
        removed_volume += sign * removed * depth
        removed_area += sign * 2 * removed
        for j, k in enumerate(axes):
            sides = (previous[j] - vertex[j], following[j] - vertex[j])
            inward = math.copysign(1, sum(sides))
            tip = starts[j] + signs[j] * vertex[j]
            moment[k] -= sign * depth * (tip * removed + signs[j] * inward * corner_moment)
    moment[axis] -= removed_volume * (stock.lo[axis] + stock.hi[axis]) / 2
    volume -= removed_volume
    area -= removed_area + len(vertices) * depth * radius * (2 - math.pi / 2)
    return {
        "kind": "closed_form",
        "volume": volume,
        "area": area,
        "centroid": [m / volume for m in moment],
        "bounds": bounds,
        "note": (
            "A rectangular cut leaves an L-shaped prism. Each axial fillet replaces two "
            "straight segments with a quarter circle, removing a square less a quadrant "
            "at five corners and adding it at the re-entrant corner. "
            f"Fillet radius {radius}, unrounded construction {ops}."
        ),
    }


_PART_FAMILIES = (
    "manifold_block_",
    "connecting_rod_",
    "hollow_tube_",
    "l_bracket_",
    "mounting_angle_",
    "rect_frame_",
    "locator_block_",
    "pillow_block_",
)


FORM_FAMILIES = (
    "t_pipe_fitting_",
    "u_bolt_",
    "j_hook_",
    *_PART_FAMILIES,
    "bellows_",
    "cam_",
    "spacer_ring_",
    "double_simplex_sprocket_",
    "sprocket_",
    "pan_head_screw_",
    "rivet_",
    "spur_gear_",
    "hex_nut_",
)


def closed_form_for(stem: str, text: str, sha256: str) -> dict[str, object] | None:
    """The closed form of a program of a family (or a SHA-256) this tool knows, else None."""
    if sha256 in CROSSING:
        return crossing_closed_form(sha256)
    if sha256 in COLLARS:
        return collar_closed_form(sha256)
    if stem.startswith("t_pipe_fitting_"):
        return tee_closed_form(text)
    if stem.startswith(("u_bolt_", "j_hook_")):
        return hook_closed_form(text)
    if stem.startswith(_PART_FAMILIES):
        if stem.startswith("rect_frame_") and ".fillet(" in text:
            return frame_closed_form(text)
        fillet = _ANGLE_FILLET.search(text) if stem.startswith("mounting_angle_") else None
        if fillet is not None:
            try:
                return _rounded_angle_form(text, fillet)
            except ValueError:  # bores into a fillet: the rounds as solids, below
                pass
        return part_closed_form(text)
    if stem.startswith("bellows_"):
        return bellows_closed_form(text)
    if stem.startswith("cam_"):
        return cam_closed_form(text)
    if stem.startswith("spacer_ring_"):
        return slotted_ring_closed_form(text)
    if stem.startswith("double_simplex_sprocket_"):
        return sprocket_closed_form(text)
    if stem.startswith("sprocket_"):
        return plate_closed_form(text)
    if stem.startswith("pan_head_screw_"):
        return screw_closed_form(text)
    if stem.startswith("rivet_"):
        return rivet_closed_form(text)
    if stem.startswith("spur_gear_"):
        return flanged_gear_closed_form(text) if ".union(" in text else gear_closed_form(text)
    if stem.startswith("hex_nut_"):
        return nut_closed_form(text)
    return None


def _closed_form_job(job: tuple[str, str, str]) -> dict[str, object] | None:
    """The closed form of one row, or None where the form's reader refuses its program (a
    `ValueError`: another arrangement than it handles), which leaves the row unclassified."""
    try:
        return closed_form_for(*job)
    except ValueError:
        return None


def verdicts_for(
    table: Path,
    corpus_texts: dict[str, str],
    refusals: dict[str, str],
    arris_bugs: dict[str, str] | None = None,
    explicit: frozenset[str] = frozenset(),
) -> dict[str, dict[str, object]]:
    """A verdict for each row of `table` no rule classes, of a family this tool knows.

    A row no rule classes is `unclassified`, or classed only by a verdict (a table run
    with `--verdicts`), so the same table gives the same verdicts either way; a row
    arris ended `unsupported_api` is outside the subset and gets none. A family
    with a closed form is `occt_wrong` by it; a family named in `refusals`
    (`family=regression fixture`, or a single row's stem in place of the family, which wins) is
    `arris_refusal` by that fixture, and one named in `arris_bugs` is `arris_bug` by its
    fixture. A key in both raises `ValueError`. A row whose closed form refuses its program is left
    unclassified and named on stderr. A stem in `explicit` is skipped: its verdict is named
    by stem elsewhere (`--boundary`, `--signed-solids`, `--by-design`), winning over its family.
    Each verdict is built as a `Verdict`, so ADR-0006's checks of the evidence run here.
    """
    from arris_gym import Status
    from arris_gym.fidelity import FidelityTable

    bugs = arris_bugs or {}
    both = sorted(set(refusals) & set(bugs))
    if both:
        raise ValueError(f"a family classed both arris_refusal and arris_bug: {both}")
    rows = FidelityTable.model_validate_json(gzip.decompress(table.read_bytes())).entries
    out: dict[str, dict[str, object]] = {}
    jobs: list[tuple[str, str, str]] = []  # rows a closed form may class: stem, text, SHA-256
    for entry in rows:
        if (
            entry.row.outcome.value != "unclassified"
            and entry.row.verdict is None
            and not (entry.name in bugs and entry.row.status is Status.CHECKER_FAIL)
        ):
            continue
        if entry.row.status is Status.UNSUPPORTED_API or entry.name in explicit:
            continue  # outside the subset (the kernel never saw it), or classed by stem below
        family = re.sub(r"_\d+_s\d+$", "", entry.name)
        if entry.row.program_sha256 in COLLARS:  # its own closed form wins over a family's flag
            jobs.append((entry.name, corpus_texts[entry.name], entry.row.program_sha256))
        elif entry.name in refusals or (entry.name not in bugs and family in refusals):
            fixture = refusals[entry.name if entry.name in refusals else family]
            out[entry.name] = {
                "disagreement": "arris_refusal",
                "evidence": {"kind": "fixture", "path": fixture},
            }
        elif entry.name in bugs or family in bugs:
            fixture = bugs[entry.name if entry.name in bugs else family]
            out[entry.name] = {
                "disagreement": "arris_bug",
                "evidence": {"kind": "fixture", "path": fixture},
            }
        elif (
            entry.name.startswith(FORM_FAMILIES)
            or entry.row.program_sha256 in CROSSING
            or entry.row.program_sha256 in COLLARS
        ):
            jobs.append((entry.name, corpus_texts[entry.name], entry.row.program_sha256))
    # Each closed form is a pure function of its program, worked out one per process, each
    # process started afresh (a fork of a process with threads may deadlock).
    forms: list[dict[str, object] | None] = []
    if jobs:
        spawn = multiprocessing.get_context("spawn")
        with ProcessPoolExecutor(max_workers=WORKERS, mp_context=spawn) as pool:
            forms = list(pool.map(_closed_form_job, jobs))
    left = []
    for (stem, _, _), closed in zip(jobs, forms, strict=True):
        if closed is None:
            left.append(stem)
        else:
            out[stem] = {"disagreement": "occt_wrong", "evidence": closed}
    if left:  # counted, never dropped: the table still holds them unclassified
        print(f"{len(left)} rows no closed form reads, left unclassified: {left}", file=sys.stderr)
    return dict(sorted(out.items()))


def check_refusal_cause(refusal: ArrisRefusal | None, fixture: str) -> None:
    """Raise `ValueError` unless `refusal` is the kernel's refusal that `fixture` names.

    `fixture` is a `--refusal` path; its last component keys `REFUSAL_CAUSES`. The kind, the
    message's start and the number of entities must all match, and a fixture with no
    registered cause is itself an error.
    """
    name = Path(fixture).name
    if name not in REFUSAL_CAUSES:
        raise ValueError(f"no refusal cause is registered for fixture {name!r}")
    kind, prefix, entities = REFUSAL_CAUSES[name]
    if refusal is None:
        raise ValueError(f"arris did not refuse, but fixture {name!r} stands for a refusal")
    if (
        refusal.kind != kind
        or not refusal.message.startswith(prefix)
        or len(refusal.entities) != entities
        or (
            name == "cq-locator-block-intersecting-bores-fillet"
            and not re.fullmatch(
                r"no closed form for \+f\d+ \(cylinder surface\) "
                r"against \+f\d+ \(cylinder surface\)",
                refusal.message,
            )
        )
    ):
        raise ValueError(
            f"refused for another reason than fixture {name!r}: {refusal.kind}: {refusal.message}"
        )


def check_bounds_cause(result: ExecResult, report: OracleReport, fixture: str) -> None:
    """Raise `ValueError` unless the row shows the cause `fixture` names (a loose arris box).

    `fixture` is an `--arris-bug` path; its last component keys `BOUNDS_CAUSES`. Both sides end
    `ok` with measures, arris's box lies past the oracle's by more than `BOUNDS_ABS` (a box
    within it is the kernel's padding, ADR-0005), and the volume, the area and the face count
    differ by no more than the fixture allows.
    """
    from arris_gym import Status
    from arris_gym.fidelity import BOUNDS_ABS, OracleStatus, measure_deltas

    name = Path(fixture).name
    if name not in BOUNDS_CAUSES:
        raise ValueError(f"no bounds cause is registered for fixture {name!r}")
    if (
        result.status is not Status.OK
        or report.status is not OracleStatus.OK
        or result.measures is None
        or report.measures is None
    ):
        raise ValueError(f"a side did not end ok, so fixture {name!r} is not its evidence")
    figures, faces = BOUNDS_CAUSES[name]
    deltas = measure_deltas(result.measures, report.measures)
    if deltas.bounds <= BOUNDS_ABS:
        raise ValueError(f"arris's box is not loose ({deltas.bounds:.1e}), fixture {name!r}")
    if name == "cq-through-side-bore-cylinder-bounds":
        (lo, hi), (oracle_lo, oracle_hi) = result.measures.bounds, report.measures.bounds
        # The transverse bore leaves the cylinder's extreme on both sides of Z.
        # A loose hull there extends past both extrema, in opposite directions.
        if oracle_lo[2] - lo[2] <= BOUNDS_ABS or hi[2] - oracle_hi[2] <= BOUNDS_ABS:
            raise ValueError("the box lacks both loose Z bounds of the side-bore fixture")
    if deltas.volume > figures or deltas.area > figures:
        raise ValueError(
            f"volume {deltas.volume:.1e} or area {deltas.area:.1e} off beyond fixture {name!r}"
        )
    if abs(deltas.faces) > faces:
        raise ValueError(f"faces differ by {deltas.faces}, beyond fixture {name!r}")


# What `cq-chamfers-overlap-on-a-face` stands for: arris's own `OpInternalError` of a face
# arrangement that is no subdivision, on a program Open CASCADE builds `invalid`.
OVERLAP_KIND = "OpInternalError"
OVERLAP_PREFIX = "kernel bug: the face arrangement is not a subdivision"


def check_overlap_cause(result: ExecResult, report: OracleReport, fixture: str) -> None:
    """Raise `ValueError` unless the row shows the cause `fixture` names: arris refusing
    with the kernel's own `OpInternalError` (a face arrangement that is no subdivision) where
    the oracle's shape is `invalid`. Which edges the program chamfers is the fixture's own."""
    from arris_gym.fidelity import OracleStatus

    name = Path(fixture).name
    refusal = result.refusal
    if report.status is not OracleStatus.INVALID:
        raise ValueError(f"the oracle's shape is not invalid, fixture {name!r} is not its evidence")
    if (
        refusal is None
        or refusal.kind != OVERLAP_KIND
        or not refusal.message.startswith(OVERLAP_PREFIX)
    ):
        raise ValueError(f"arris did not end with the internal error of fixture {name!r}")


# A vertex blend's corner patch is the kernel's own (ADR-0025): the two kernels' figures differ
# by what the patch holds, 8.8e-7 and 7.5e-8 of the area on the BenchCAD rows it classes. A
# figure further apart than 1e-5, eleven times the larger, is another difference than the patch.
CORNER_PATCH_REL = 1e-5


def check_by_design_cause(result: ExecResult, report: OracleReport) -> None:
    """Raise `ValueError` unless both sides built one solid whose measures differ only as two
    corner patches can (`CORNER_PATCH_REL`), the bounds inside ADR-0005's `BOUNDS_ABS`."""
    from arris_gym import Status
    from arris_gym.fidelity import BOUNDS_ABS, OracleStatus
    from arris_gym.fidelity._agreement import _judged

    if result.status is not Status.OK or report.status is not OracleStatus.OK:
        raise ValueError("a corner patch on a row that is not ok on both sides")
    assert result.measures is not None
    assert report.measures is not None
    if report.measures.solids != 1 or result.measures.shells != 1:
        raise ValueError("a corner patch on a part of several solids")
    volume, area, centroid, bounds = _judged(result.measures, report.measures)
    if max(volume, area, centroid) > CORNER_PATCH_REL or bounds > BOUNDS_ABS:
        raise ValueError("measures further apart than a corner patch moves them")


def signed_solid_forms(texts: Sequence[str], *, workers: int = WORKERS) -> list[dict[str, object]]:
    """The `SignedSolids` JSON of each program's oracle shape (ADR-0006, amended 2026-11-22).

    In oracle workers, each solid's signed volume is the flux of x / 3 through its faces by
    Green's theorem along their trims (`report_signed_solids`, the blended boundary's
    integrands), at both resolutions; they must agree inside `VOLUME_REL`, and the finer is kept
    to `_SIGNED_SIGNIFICANT_DIGITS`. No kernel's mass properties are read.
    """
    from numpy.polynomial.legendre import leggauss

    import oracle_run
    from arris_gym.fidelity import VOLUME_REL, OracleStatus, SignedSolids

    points, weights = leggauss(_BOUNDARY_ORDER)
    nodes = tuple(zip(points.tolist(), weights.tolist(), strict=True))
    probe = (oracle_run.ORACLE / "sketch_boundary.py").read_text(encoding="utf-8")
    suffix = f"\n{probe}\nreport_signed_solids(r, {nodes!r}, {_SIGNED_SUBDIVISIONS!r})\n"
    reports = oracle_run.run_many(
        [text + suffix for text in texts], workers=workers, timeout=_SIGNED_TIMEOUT
    )
    forms = []
    for report in reports:
        if report.status is not OracleStatus.RUNTIME or not report.message.startswith(
            _BOUNDARY_MARK
        ):
            raise ValueError(f"signed solid probe ended {report.status.value}: {report.message}")
        volumes = []
        for coarse, fine in json.loads(report.message.removeprefix(_BOUNDARY_MARK)):
            if abs(coarse - fine) > VOLUME_REL * max(abs(coarse), abs(fine)):
                raise ValueError(f"signed volumes disagree: {coarse} and {fine}")
            volumes.append(float(f"{fine:.{_SIGNED_SIGNIFICANT_DIGITS}g}"))
        forms.append(
            SignedSolids(
                volumes=tuple(volumes),
                note=(
                    "Each solid's signed volume, the flux of x / 3 through its faces by Green's "
                    "theorem along planar, cylindrical, conical and toroidal trims at two "
                    "resolutions that agree (tools/cq_closed_forms.py, signed_solid_forms)."
                ),
            ).model_dump(mode="json")
        )
    return forms


def _clipped_bellows_bounds(text: str) -> Box:
    """Bound the union of the two rims left by the polar arrays."""
    match = _BELLOWS.search(text)
    if match is None:
        raise ValueError("not the bellows this tool reads")
    pts = [(_num(x), _num(y)) for x, y in _PAIR.findall(match[1])]
    _, pitch, count, radius, top, pitch2, count2, radius2, bottom = match.groups()[1:]
    if len(pts) < 10 or (pitch, count, radius) != (pitch2, count2, radius2):
        raise ValueError("clipped bellows requires matching arrays on both rims")
    r, height = pts[-4]
    p, a, n = _num(pitch), _num(radius), int(count)
    if not (
        n >= 2
        and 0 < p - a < r < p + a
        and a < p * math.sin(math.pi / n)
        and pts[2] == (r, 0)
        and pts[3][0] == r
        and abs(pts[3][1] + _num(bottom)) <= PLACEMENT_TOL
        and abs(height + _num(top) - pts[-5][1]) <= PLACEMENT_TOL
        and all(0 <= y <= height for _, y in pts)
    ):
        raise ValueError("bellows cuts do not remove the two outer rims")
    half_angle = math.acos((r * r + p * p - a * a) / (2 * r * p))
    period = math.tau / n

    def extent(angle: float) -> float:
        # The bottom plane mirrors the top's X axis. Take the larger surviving
        # support of the two rims. A disc minus these disjoint cutters attains
        # its directional maximum at a surviving rim point or circle intersection.
        separation = max(abs(math.remainder(q, period)) for q in (angle, math.pi - angle))
        return r * math.cos(max(0, half_angle - separation))

    lo = (-extent(math.pi), 0.0, -extent(-math.pi / 2))
    hi = (extent(0), height, extent(math.pi / 2))
    other_radii = [x for i, (x, _) in enumerate(pts) if i not in (2, 3, len(pts) - 4)]
    if max(other_radii) >= min(-lo[0], -lo[2], hi[0], hi[2]):
        raise ValueError("a bellows profile segment can extend past the clipped rims")
    return lo, hi


_COLLAR_STOCK = re.compile(
    rf'cq\.Workplane\("(XY|XZ|YZ)"\)\s*'
    rf"(?:\.circle\({_NUMBER}\)\s*\.extrude\({_NUMBER}\)|\.cylinder\({_NUMBER}, {_NUMBER}\))"
)
_COLLAR_CUT = re.compile(
    rf'\.cut\(\s*cq\.Workplane\("(XY|XZ|YZ)"\)\s*'
    rf"\.transformed\(offset=cq\.Vector\(0\.0, 0\.0, {_NUMBER}\), "
    rf"rotate=cq\.Vector\(90\.0, 0\.0, (0|120|240)\.0\)\)\s*"
    rf"\.cylinder\({_NUMBER}, {_NUMBER}\)\s*\)"
)


def _check_clipped_rim(result: ExecResult, report: OracleReport, text: str) -> None:
    from arris_gym.fidelity import BOUNDS_ABS

    expected_lo, expected_hi = _clipped_bellows_bounds(text)
    assert result.measures is not None
    assert report.measures is not None
    lo, hi = result.measures.bounds
    oracle_lo, oracle_hi = report.measures.bounds
    for expected, oracle in zip(expected_lo + expected_hi, oracle_lo + oracle_hi, strict=True):
        if abs(expected - oracle) > BOUNDS_ABS:
            raise ValueError("oracle bounds differ from the clipped rims")
    if max(abs(lo[1] - expected_lo[1]), abs(hi[1] - expected_hi[1])) > BOUNDS_ABS:
        raise ValueError("the bellows bounds disagree along the revolve axis")
    overshoots = False
    for axis in (0, 2):
        lower, upper = expected_lo[axis] - lo[axis], hi[axis] - expected_hi[axis]
        if min(lower, upper) < -BOUNDS_ABS:
            raise ValueError("bellows bounds exclude part of the clipped rims")
        overshoots |= max(lower, upper) > BOUNDS_ABS
    if not overshoots:
        raise ValueError("the bellows bounds do not extend past the clipped rims")


def _check_mid_collar(result: ExecResult, report: OracleReport, text: str) -> None:
    from arris_gym.fidelity import BOUNDS_ABS

    stock = _COLLAR_STOCK.search(text)
    cuts = list(_COLLAR_CUT.finditer(text))
    if stock is None or len(cuts) != 3 or text.count(".cut(") != len(cuts):
        raise ValueError("not the repeated cross-hole collar")
    plane, disk_radius, extrusion, cylinder_height, cylinder_radius = stock.groups()
    r, h = float(disk_radius or cylinder_radius), float(extrusion or cylinder_height)
    _, first_offset, _, first_length, first_radius = cuts[0].groups()
    blend = max(
        map(float, re.findall(rf"\.(?:chamfer|fillet)\({_NUMBER}\)", text[: cuts[0].start()])),
        default=0.0,
    )
    for rotation, cut in zip(("0", "120", "240"), cuts, strict=True):
        cut_plane, offset, turn, length, radius = cut.groups()
        a = float(radius)
        if (
            cut_plane != plane
            or turn != rotation
            or (offset, length, radius) != (first_offset, first_length, first_radius)
            or abs(float(offset) - h / 2) > PLACEMENT_TOL
            or not (0 < a < h / 2 - blend and float(length) > 2 * r)
        ):
            raise ValueError("the cutter is not a repeated through bore at mid-height")
    # The radius survives along the drill direction above or below the hole.
    # The turned workplane's normal lies along its original local y axis.
    axis = 1 if plane == "XY" else 2
    assert result.measures is not None
    assert report.measures is not None
    lo, hi = result.measures.bounds
    oracle_lo, oracle_hi = report.measures.bounds
    if abs(oracle_lo[axis] + r) > BOUNDS_ABS or abs(oracle_hi[axis] - r) > BOUNDS_ABS:
        raise ValueError("oracle bounds differ from the stock radius along the bore")
    if min(-r - lo[axis], hi[axis] - r) <= BOUNDS_ABS or any(
        max(abs(lo[k] - oracle_lo[k]), abs(hi[k] - oracle_hi[k])) > BOUNDS_ABS
        for k in range(3)
        if k != axis
    ):
        raise ValueError("the box lacks the cross hole's two loose bounds")


def check_bug_cause(
    result: ExecResult, report: OracleReport, fixture: str, *, measure_program: str | None = None
) -> None:
    """Raise `ValueError` unless the row shows the cause of its `--arris-bug` `fixture`."""
    name = Path(fixture).name
    if measure_program is not None:
        from arris_gym import Status
        from arris_gym.fidelity import OracleStatus

        if result.status is not Status.OK or report.status is not OracleStatus.OK:
            raise ValueError("the bounds evidence requires two measured results")
        if name == "cq-revolved-cone-notches-bounds":
            _check_clipped_rim(result, report, measure_program)
        elif name == "cq-cross-hole-bounds":
            _check_mid_collar(result, report, measure_program)
        else:
            raise ValueError(f"no measure replay check for fixture {name!r}")
    elif name in ("cq-chamfers-overlap-on-a-face", "cq-through-keyway-after-overlapping-chamfers"):
        check_overlap_cause(result, report, fixture)
    elif name in ("cq-keyway-through-filleted-rim-bounds", "cq-slot-into-rounded-rim-bounds"):
        from arris_gym.fidelity import BOUNDS_ABS, OracleStatus

        if (
            result.measures is None
            or report.measures is None
            or report.status is not OracleStatus.OK
        ):
            raise ValueError("the blend trim bounds require two measured solids")
        expected = report.measures.bounds[1][1]
        if name == "cq-keyway-through-filleted-rim-bounds" and abs(expected) > BOUNDS_ABS:
            raise ValueError("the oracle's keyway bound is outside the original end plane")
        if result.measures.bounds[1][1] - expected <= BOUNDS_ABS:
            raise ValueError("the result lacks the blend trim's loose upper Y bound")
    elif name == "cq-sketch-post-tangent-to-cap":
        from arris_gym import Status
        from arris_gym.fidelity import OracleStatus

        if (
            result.status is not Status.CHECKER_FAIL
            or report.status is not OracleStatus.OK
            or len(result.violations) != 1
            or not re.fullmatch(r"L5 f\d+: loops 0 and 1 intersect", result.violations[0])
        ):
            raise ValueError("the row lacks the tangent cap's intersecting-loop violation")
    else:
        check_bounds_cause(result, report, fixture)


def sketch_boundary_forms(
    texts: Sequence[str],
    *,
    blends: bool = False,
    subdivisions: tuple[int, int] | None = None,
    workers: int = WORKERS,
) -> list[dict[str, object]]:
    """Integrate the planar and cylindrical faces of a part's boundary.

    Run in oracle workers and raise if the two quadratures do not converge
    within the fidelity tolerance. With `blends`, also integrate conical and
    toroidal faces. The integral uses the B-Rep's trim curves and no kernel mass
    properties.
    """
    from numpy.polynomial.legendre import leggauss

    import oracle_run
    from arris_gym.fidelity import ClosedForm, OracleStatus
    from arris_gym.fidelity._agreement import figures_agree

    points, weights = leggauss(_BOUNDARY_ORDER)
    nodes = tuple(zip(points.tolist(), weights.tolist(), strict=True))
    probe = (oracle_run.ORACLE / "sketch_boundary.py").read_text(encoding="utf-8")
    optional = f", subdivisions={subdivisions!r}" if subdivisions is not None else ""
    suffix = f"\n{probe}\nreport_sketch_boundary(r, {nodes!r}, blends={blends!r}{optional})\n"
    reports = oracle_run.run_many([text + suffix for text in texts], workers=workers)
    forms = []
    for report in reports:
        if report.status is not OracleStatus.RUNTIME or not report.message.startswith(
            _BOUNDARY_MARK
        ):
            raise ValueError(f"boundary probe ended {report.status.value}: {report.message}")
        bbox, coarse, fine = json.loads(report.message.removeprefix(_BOUNDARY_MARK))
        bounds = (tuple(bbox[:3]), tuple(bbox[3:]))
        note = (
            "Exact v antiderivatives of the area and flux on planar and cylindrical faces, "
            "integrated along the trims (Green's theorem); both quadratures agree. Tight "
            "bounds from AddOptimal. tools/cq_closed_forms.py --sketch-boundary"
        )
        if blends:
            note = (
                "Green's theorem along planar, cylindrical, conical and toroidal trim curves. "
                "The flux primitives on cones and tori use Gauss-Legendre quadrature. "
                "Both trim resolutions agree. Tight bounds from AddOptimal. "
                "tools/cq_closed_forms.py"
            )
        a = ClosedForm(
            volume=coarse[0], area=coarse[1], centroid=coarse[2:], bounds=bounds, note=note
        )
        b = ClosedForm(volume=fine[0], area=fine[1], centroid=fine[2:], bounds=bounds, note=note)
        if not figures_agree(a, b):
            raise ValueError(f"boundary integrals disagree: {coarse} and {fine}")
        volume, area = (float(f"{v:.{_BOUNDARY_SIGNIFICANT_DIGITS}g}") for v in fine[:2])
        forms.append(
            ClosedForm(
                volume=volume,
                area=area,
                centroid=_boundary_coordinates(b.centroid),
                bounds=(
                    _boundary_coordinates(b.bounds[0]),
                    _boundary_coordinates(b.bounds[1]),
                ),
                note=note,
            ).model_dump(mode="json")
        )
    return forms


def _boundary_coordinates(point: Vec) -> Vec:
    x, y, z = point
    return (
        round(x, _BOUNDARY_COORDINATE_PLACES),
        round(y, _BOUNDARY_COORDINATE_PLACES),
        round(z, _BOUNDARY_COORDINATE_PLACES),
    )


_MEASURE_FIXTURES = {
    "bellows": "tests/fixtures/regression/cq-revolved-cone-notches-bounds",
    "shaft_collar": "tests/fixtures/regression/cq-cross-hole-bounds",
}


def _measure_replay_verdicts(
    stems: Sequence[str], texts: dict[str, str]
) -> dict[str, dict[str, object]]:
    """Derive evidence for each explicitly named 0.12.0 measure disagreement."""
    verdicts: dict[str, dict[str, object]] = {}
    torus = []
    for stem in stems:
        family = re.sub(r"_\d+_s\d+$", "", stem)
        if family in _MEASURE_FIXTURES:
            verdicts[stem] = {
                "disagreement": "arris_bug",
                "evidence": {"kind": "fixture", "path": _MEASURE_FIXTURES[family]},
            }
        elif family == "dome_cap":
            verdicts[stem] = {
                "disagreement": "occt_wrong",
                "evidence": dome_closed_form(texts[stem]),
            }
        elif family == "torus_link":
            torus.append(stem)
        else:
            raise ValueError(f"no measure replay evidence for {stem}")
    if torus:
        forms = sketch_boundary_forms(
            [texts[stem] + "\nr = result\n" for stem in torus], blends=True
        )
        for stem, form in zip(torus, forms, strict=True):
            verdicts[stem] = {"disagreement": "occt_wrong", "evidence": form}
    return verdicts


def main(argv: Sequence[str] | None = None) -> int:
    """Write the verdicts of a corpus table's unclassified rows, checked against both sides."""
    import arris_gym as ag
    from arris_gym.census import benchcad, cadrecode
    from arris_gym.fidelity import (
        FidelityOutcome,
        FidelityTable,
        OracleReport,
        OracleStatus,
        Verdict,
        compare,
    )

    parser = argparse.ArgumentParser(description=__doc__, fromfile_prefix_chars="@")
    parser.add_argument("--corpus", choices=("benchcad", "cadrecode"), default="benchcad")
    parser.add_argument("--table", type=Path, help="a fidelity.json.gz")
    parser.add_argument(
        "--measure-replay",
        type=Path,
        help="recheck the listed BenchCAD measure disagreements, one stem per line",
    )
    parser.add_argument("--oracle-rows", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--sketch-boundary",
        action="store_true",
        help="check CAD-Recode sketch measures with independent boundary quadrature",
    )
    parser.add_argument(
        "--refusal",
        action="append",
        default=[],
        metavar="FAMILY=FIXTURE",
        help="class a family's rows (or a stem's) arris_refusal by this fixture directory",
    )
    parser.add_argument(
        "--arris-bug",
        action="append",
        default=[],
        metavar="FAMILY=FIXTURE",
        help="class a family's rows (or a stem's) arris_bug by this regression fixture directory",
    )
    parser.add_argument(
        "--boundary",
        action="append",
        default=[],
        metavar="STEM",
        help="class a stem occt_wrong by the planar and cylindrical boundary integral",
    )
    parser.add_argument(
        "--blended-boundary",
        action="append",
        default=[],
        metavar="STEM",
        help="class a stem occt_wrong by the boundary integral with conical and toroidal faces",
    )
    parser.add_argument(
        "--signed-solids",
        action="append",
        default=[],
        metavar="STEM",
        help="class a stem occt_wrong by its oracle shape's signed solids",
    )
    parser.add_argument(
        "--by-design",
        action="append",
        default=[],
        metavar="STEM=ANCHOR",
        help="class a stem by_design by this doc anchor (a vertex blend's corner patch)",
    )
    args = parser.parse_args(argv)
    if args.sketch_boundary and args.corpus != "cadrecode":
        parser.error("--sketch-boundary requires --corpus cadrecode")
    measure_stems: frozenset[str] = frozenset()
    if args.measure_replay is not None:
        if args.corpus != "benchcad":
            parser.error("--measure-replay requires --corpus benchcad")
        lines = args.measure_replay.read_text(encoding="utf-8").splitlines()
        measure_stems = frozenset(lines)
        if not lines or "" in measure_stems or len(lines) != len(measure_stems):
            parser.error("--measure-replay requires distinct, nonempty stems")
    if args.table is None and (
        not measure_stems or args.refusal or args.arris_bug or args.sketch_boundary
    ):
        parser.error("--table is required for table-based verdict selection")
    refusals = dict(item.split("=", 1) for item in args.refusal)
    arris_bugs = dict(item.split("=", 1) for item in args.arris_bug)
    designs = dict(item.split("=", 1) for item in args.by_design)
    explicit = frozenset([*args.boundary, *args.blended_boundary, *args.signed_solids, *designs])
    if measure_stems & explicit:
        parser.error("a measure replay stem is also specified by another option")
    programs = benchcad.read() if args.corpus == "benchcad" else cadrecode.read()
    texts = {p.stem: p.text for p in programs}
    verdicts = (
        verdicts_for(args.table, texts, refusals, arris_bugs, explicit | measure_stems)
        if args.table is not None
        else {}
    )
    if not measure_stems <= texts.keys():
        parser.error(f"unknown measure replay stems: {sorted(measure_stems - texts.keys())}")
    try:
        verdicts.update(_measure_replay_verdicts(sorted(measure_stems), texts))
    except ValueError as error:
        print(error, file=sys.stderr)
        return 1
    # The probes read the result as `r`, CAD-Recode's name; BenchCAD's is `result`.
    alias = "\nr = result\n" if args.corpus == "benchcad" else ""
    for stems, blends in ((args.boundary, False), (args.blended_boundary, True)):
        if stems:
            forms = sketch_boundary_forms([texts[stem] + alias for stem in stems], blends=blends)
            for stem, boundary_form in zip(stems, forms, strict=True):
                verdicts[stem] = {"disagreement": "occt_wrong", "evidence": boundary_form}
    if args.signed_solids:
        signed = signed_solid_forms([texts[stem] + alias for stem in args.signed_solids])
        for stem, signed_form in zip(args.signed_solids, signed, strict=True):
            verdicts[stem] = {"disagreement": "occt_wrong", "evidence": signed_form}
    for stem, anchor in designs.items():
        verdicts[stem] = {
            "disagreement": "by_design",
            "evidence": {"kind": "doc", "anchor": anchor},
        }
    if args.sketch_boundary:
        table = FidelityTable.model_validate_json(gzip.decompress(args.table.read_bytes()))
        sketch_stems = [
            entry.name
            for entry in table.entries
            if entry.name not in verdicts
            and entry.row.status is ag.Status.OK
            and (entry.row.outcome is FidelityOutcome.UNCLASSIFIED or entry.row.verdict is not None)
        ]
        forms = sketch_boundary_forms([texts[stem] for stem in sketch_stems])
        for stem, boundary_form in zip(sketch_stems, forms, strict=True):
            verdicts[stem] = {"disagreement": "occt_wrong", "evidence": boundary_form}
    reports = {}
    for line in gzip.decompress(args.oracle_rows.read_bytes()).decode("utf-8").splitlines():
        row = json.loads(line)
        reports[row["stem"]] = OracleReport.model_validate(row["report"])
    stems = list(verdicts)
    with ag.Sandbox() as sandbox:
        results = sandbox.run_many([texts[s] for s in stems], dialect="cq", workers=WORKERS)
    refused = []
    not_its_cause = []
    for stem, result in zip(stems, results, strict=True):
        try:
            evidence = verdicts[stem]["evidence"]
            if verdicts[stem]["disagreement"] == "arris_refusal" and isinstance(evidence, dict):
                check_refusal_cause(result.refusal, str(evidence["path"]))
            if verdicts[stem]["disagreement"] == "by_design":
                check_by_design_cause(result, reports[stem])
            if stem in measure_stems:
                if result.program_sha256 != reports[stem].program_sha256:
                    raise ValueError("the pinned oracle report is for a different program")
                report = reports[stem]
                if (
                    result.status is not ag.Status.OK
                    or report.status is not OracleStatus.OK
                    or result.measures is None
                    or report.measures is None
                    or result.measures.solids != report.measures.solids
                    or compare(result, report).outcome is not FidelityOutcome.UNCLASSIFIED
                ):
                    raise ValueError(
                        "the row lacks an unclassified measure gap with matching solids"
                    )
                if verdicts[stem]["disagreement"] == "arris_bug" and isinstance(evidence, dict):
                    check_bug_cause(
                        result, reports[stem], str(evidence["path"]), measure_program=texts[stem]
                    )
            elif verdicts[stem]["disagreement"] == "arris_bug" and isinstance(evidence, dict):
                try:
                    check_bug_cause(result, reports[stem], str(evidence["path"]))
                except ValueError as error:  # counted, never labelled: the row stays as it is
                    not_its_cause.append(f"{stem}: {error}")
                    del verdicts[stem]
                    continue
            compare(result, reports[stem], Verdict.model_validate(verdicts[stem]))
        except ValueError as error:
            refused.append(f"{stem}: {error}")
    if not_its_cause:
        print(
            f"{len(not_its_cause)} rows show no cause of their --arris-bug fixture, "
            "left unclassified:\n" + "\n".join(not_its_cause),
            file=sys.stderr,
        )
    if refused:
        print("\n".join(refused), file=sys.stderr)
        return 1
    verdicts = dict(sorted(verdicts.items()))
    args.out.write_text(json.dumps(verdicts, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"{len(verdicts)} verdicts, each checked by `compare`", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

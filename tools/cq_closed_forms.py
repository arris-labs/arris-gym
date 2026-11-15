#!/usr/bin/env python3
"""Closed forms of the BenchCAD parts the oracle gets wrong (ADR-0006's `ClosedForm`).

Outside the gate, no oracle imported or run. Reads the pinned BenchCAD corpus
(the `[corpus]` extra) and the committed oracle rows, works out each listed
family's measures from how the part is built (never from either kernel's output),
and writes one `Verdict` per stem that the row's measures can test:

    uv run --extra corpus tools/cq_closed_forms.py --table T --oracle-rows O --out V.json \
        [--refusal FAMILY=FIXTURE ...] [--arris-bug FAMILY=FIXTURE ...]

A row no rule classes is one the table left unclassified or classed only by a verdict, so
the tool reads a table run with or without `--verdicts` alike; a row arris ended
`unsupported_api` is outside the subset and gets no verdict. A family given by
`--refusal` or `--arris-bug` (or one row's stem, which wins) is classed by that regression
fixture rather than a closed form.

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

- **manifold_block / connecting_rod**: boxes and cylinders whose axes and faces all lie
  along x, y or z, united and cut in the program's order (`part_ops` reads the program
  by CadQuery's rules; bores crossing bores, a counterbore on a box's edge, a cross hole
  into a ring's wall). Volume and moments are fluxes through the boundary (the divergence
  theorem), and along a line on any face each solid is one exact interval, so what is
  left is one integral across the lines per face, split where its formula changes
  (`part_measures`).

- **bellows**: a closed profile turned about y (Pappus), an optional `hole` from the top
  widening its inner wall, and a `polarArray` of circles `cutBlind` from each end face:
  through the bottom flange, and from the top face down to the cone under it (a sliver).
  A hole may run past the rim; what it takes is integrated by radius over its disc's
  part inside the rim (`bellows_measures`).

- **spacer_ring**: a ring on the `YZ` plane, bored and filleted at its four rim circles, cut
  across its wall by a box through the strip `|z| < w` (through the ring, or from its bottom
  face up to a height inside the outer cylinder's straight part): every measure is a
  one-dimensional integral over the radius (`slotted_ring_measures`).

- **crossing cylinders**: the one CAD-Recode program whose row nothing classes (`CROSSING`).

The integrals are tanh-sinh quadrature (endpoint square-root singularities are
what it is for) over intervals split where an integrand's formula changes or turns
nearly singular. `tests/test_cq_closed_forms.py` holds each form to arris's own
measures on constructed programs, inside ADR-0005's tolerance; and the tool checks
every verdict it writes with `compare`, which holds the exonerated kernel to the
closed form and the blamed one away from it.
"""

from __future__ import annotations

import argparse
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
    from arris_gym.sandbox.outcome import ArrisRefusal

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

# What a `--refusal` fixture stands for: the kernel's refusal that a row must show on its
# re-run, (exception class, message prefix, number of entities), so a row refused for another
# reason is never classed by that fixture's name.
REFUSAL_CAUSES: dict[str, tuple[str, str, int]] = {
    "cq-tangent-cylinders": (
        "OpDegenerateError",
        "degenerate result: the faces touch along a curve interior to both result faces",
        2,
    ),
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
    rf'    \.faces\(">X"\)\.workplane\(\)\n    \.hole\({_NUMBER}\)\n'
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
    bore, f, y_centre, y_len, z_len, x_len = (_num(v) for v in g[4:10])
    ring = SlottedRing(
        big=big,
        small=bore / 2,
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
        and f < big - bore / 2 - f
        and ring.w < ring.small
        and 0 < ring.y0 < clear
        and ring.y1 > big
        and lo <= 0
        and (ring.hi >= h or f <= ring.hi <= h - f)
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
    cuts = [r, r + f, big - f, big]

    def over(g: Callable[[float], float], lo: float = r, up: float = big) -> float:
        edges = sorted({lo, up, *(c for c in cuts if lo < c < up)})
        return sum(tanh_sinh(g, a, b) for a, b in itertools.pairwise(edges))

    def turn(rho: float) -> float:  # how far the fillet takes the profile in from a flat face
        s = min(rho - r, big - rho)
        return f - math.sqrt(f * f - (f - s) ** 2) if s < f else 0.0

    def top(rho: float) -> float:  # the cut's upper end in a column
        return h - turn(rho) if through else hi

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
    wedge = (  # the fillet patches' strips: bottom pair always, top pair when the cut passes them
        tanh_sinh(lambda t: arc(r + f - f * math.cos(t)) * f, 0.0, pi / 2)
        + tanh_sinh(lambda t: arc(big - f + f * math.cos(t)) * f, 0.0, pi / 2)
    )
    flat = over(arc, r + f, big - f)
    reach = min(hi, h - f) - f
    taken = (
        flat
        + (2 * big * math.asin(w / big) + 2 * r * math.asin(w / r)) * reach
        + wedge
        + ((flat + wedge) if through else 0.0)
    )
    walls = 2 * over(lambda rho: column(rho) * rho / math.sqrt(rho * rho - w * w))
    floor = 0.0 if through else over(arc)
    area = ring_a - taken + walls + floor

    centroid = (
        p.bottom + (ring_v * h / 2 - cut_a) / volume,
        -cut_x / volume,
        0.0,
    )
    y_hi = math.sqrt(big * big - w * w) if through else big
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


# --- Boxes and cylinders on the axes: manifold_block and connecting_rod -------------------
#
# A part built of boxes and cylinders whose axes and faces are all along x, y or z, united
# and cut in the program's order. Its measures are integrals over its boundary (the
# divergence theorem: V = 1/3 of the flux of x, the moment along j the flux of x_j^2/2 e_j),
# and every boundary patch lies on one of the solids' faces. Along a line on such a face
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


Solid = Cuboid | Rod
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


def _on_line(solid: Solid, d: int, at: Vec, nudge: tuple[int, int]) -> Interval | None:
    """Where the line along axis `d` through `at` lies inside `solid` (its d coordinate is not
    read); `nudge` moves the coordinate on one axis by an infinitesimal step, (axis, ±1)."""
    axis, step = nudge
    if isinstance(solid, Cuboid):
        for j in _others(d):
            if not _within(at[j], solid.lo[j], solid.hi[j], step if j == axis else 0):
                return None
        return solid.lo[d], solid.hi[d]
    c = solid.centre
    if solid.axis == d:
        b, k = _others(d)
        if (at[b] - c[b]) ** 2 + (at[k] - c[k]) ** 2 < solid.r * solid.r:
            return solid.lo, solid.hi
        return None
    a = solid.axis
    if not _within(at[a], solid.lo, solid.hi, step if a == axis else 0):
        return None
    o = 3 - a - d
    w = _chord(solid.r, at[o] - c[o])
    return None if w is None else (c[d] - w, c[d] + w)


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
    nudge: tuple[int, int],
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
            assert isinstance(solid, Rod)
            interval = (solid.lo, solid.hi) if own[1] else None
        else:
            interval = _on_line(solid, d, at, nudge)
        seen.append(interval is not None)
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


def _piecewise(f: Integrand, a: float, b: float) -> list[float]:
    """The integral over [a, b] of `f`'s values, split wherever its signature changes.

    `f` returns its values and a signature: what its formula depends on (which intervals
    exist, the order of their ends). Between two changes the values are smooth but for a
    square root at an end, which tanh-sinh integrates exactly. A scan finds the changes and
    bisection places them; a piece whose own nodes show a change the scan missed is split.
    """
    mids = [a + (b - a) * (i + 0.5) / SCAN_POINTS for i in range(SCAN_POINTS)]
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


def _flat_extent(solid: Solid, b: int, k: int, v: float) -> Interval | None:
    """A flat face of `solid` (a box's, a cylinder's end) on the line along b at k = v."""
    if isinstance(solid, Cuboid):
        return (solid.lo[b], solid.hi[b]) if solid.lo[k] < v < solid.hi[k] else None
    w = _chord(solid.r, v - solid.centre[k])
    return None if w is None else (solid.centre[b] - w, solid.centre[b] + w)


# What `_flat` and `_side` return: area, three times the volume, and the three moments.
_ZERO = (0.0, 0.0, 0.0, 0.0, 0.0)


def _flat(
    ops: Sequence[Op], solid: Solid, a: int, side: int, c: float, before: Sequence[Solid]
) -> list[float]:
    """The part's boundary on a flat face of `solid` at `a = c`, its outward normal `side`.

    `before` holds the solids whose flat face in this plane was read already: what lies on
    them is not read twice.
    """
    b, k = _others(a)
    if isinstance(solid, Cuboid):
        v0, v1 = solid.lo[k], solid.hi[k]
    else:
        v0, v1 = solid.centre[k] - solid.r, solid.centre[k] + solid.r

    def f(v: float) -> tuple[tuple[float, ...], Signature]:
        at = [0.0, 0.0, 0.0]
        at[a], at[k] = c, v
        point = (at[0], at[1], at[2])
        extent = _flat_extent(solid, b, k, v)
        if extent is None:
            return _ZERO, ("none",)
        seen: list[object] = []
        ends: list[tuple[float, int]] = [(extent[0], -1), (extent[1], -2)]
        inside = _part_on_line(ops, b, point, (a, -side), None, seen, ends)
        outside = _part_on_line(ops, b, point, (a, side), None, seen, ends)
        face = [extent]
        for j, other in enumerate(before):
            known = _flat_extent(other, b, k, v)
            seen.append(known is not None)
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
        inside = _part_on_line(ops, a, point, (-1, 0), (i, True), seen, ends)
        outside = _part_on_line(ops, a, point, (-1, 0), (i, False), seen, ends)
        own = [(rod.lo, rod.hi)]
        out = _length(_both(_minus(inside, outside), own))
        into = _length(_both(_minus(outside, inside), own))
        net = out - into
        values = [r * (out + into), r * (at[b] * cos + at[k] * sin) * net, 0.0, 0.0, 0.0]
        values[2 + b] = r * at[b] ** 2 / 2 * cos * net
        values[2 + k] = r * at[k] ** 2 / 2 * sin * net
        return tuple(values), (tuple(seen), _order(ends))

    total = [0.0] * 5
    for q in range(4):  # a quarter turn's ends are where a chord across it can touch zero
        part = _piecewise(f, q * math.pi / 2, (q + 1) * math.pi / 2)
        total = [x + y for x, y in zip(total, part or _ZERO, strict=True)]
    return total


def _solid_box(solid: Solid) -> Box:
    if isinstance(solid, Cuboid):
        return solid.lo, solid.hi
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
            lines: list[tuple[int, Vec, tuple[int, int], tuple[int, bool] | None]]
            for i, (kind, solid) in enumerate(ops):
                if kind != "+" or _solid_box(solid)[end][a] != extreme:
                    continue
                if isinstance(solid, Rod) and solid.axis != a:
                    at = [solid.centre[0], solid.centre[1], solid.centre[2]]
                    at[a] = extreme
                    lines = [(solid.axis, (at[0], at[1], at[2]), (a, step), (i, True))]
                else:
                    b, k = _others(a)
                    lo, hi = _solid_box(solid)
                    lines = []
                    for n in range(SCAN_POINTS):
                        at = [0.0, 0.0, 0.0]
                        at[a] = extreme
                        at[k] = lo[k] + (hi[k] - lo[k]) * (n + 0.5) / SCAN_POINTS
                        lines.append((b, (at[0], at[1], at[2]), (a, step), None))
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
        if isinstance(solid, Cuboid):
            faces = [
                (a, s, solid.hi[a] if s > 0 else solid.lo[a]) for a in range(3) for s in (-1, 1)
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


def _top(ops: Sequence[Op], a: int) -> float:
    """The plane of `faces(">A")`: CadQuery keeps the faces whose centre lies furthest along A.

    That is the highest flat face of a united solid facing +A (a box's, or a cylinder's end
    on that axis). A cut leaves faces inside the part, below it. A cylinder across the axis
    has its side's centre on its own mid-plane only when the whole part is symmetric about
    that plane, which is checked; that plane must lie below the top.
    """
    top = -math.inf
    for kind, solid in ops:
        if kind == "+" and isinstance(solid, Cuboid):
            top = max(top, solid.hi[a])
        elif kind == "+" and isinstance(solid, Rod) and solid.axis == a:
            top = max(top, solid.hi)
    for kind, solid in ops:
        if kind == "+" and isinstance(solid, Rod) and solid.axis != a:
            mid = solid.centre[a]
            for _, other in ops:
                lo, hi = _solid_box(other)
                if abs((lo[a] - mid) + (hi[a] - mid)) > PLACEMENT_TOL:
                    raise ValueError("a cylinder's side whose centre this tool cannot place")
            if not mid < top:
                raise ValueError("a cylinder's side above the top face")
    return top


def _made(plane: str, offset: Vec, call: str, args: str) -> Solid:
    """`Workplane(plane).transformed(offset=offset).box(...)` or `.cylinder(h, r)`."""
    x, y, n = _PLANES[plane]
    o = _at(((0.0, 0.0, 0.0), x, y, n), *offset)
    values = [_num(v) for v in args.split(",")]
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
    rf"rotate=cq\.Vector\(0, 0, 0\)\)\s*)?"
    rf"\.(box|cylinder)\(([^()]*)\)\s*$"
)


def part_ops(text: str) -> list[Op]:
    """The boxes and cylinders a manifold_block or connecting_rod program unites and cuts.

    Read by CadQuery 2.3.0's rules, which `arris_gym.cq` follows (ADR-0017, ADR-0018): a
    box or a cylinder is centred on its workplane, a cylinder along the plane's normal;
    `faces(">A").workplane()` (once or twice, ADR-0018 rule 5) is the plane of the top face
    along +A (`_top`), its x `(0, 0, 1)` crossed with its normal (+x for a normal along z),
    its origin the previous origin projected onto it; `pushPoints` are points in that plane;
    `hole(d)` and `cboreHole(d, D, h)` bore from each point (the origin when none) against
    the normal for `largestDimension()`, the diagonal of the part's box (so through it), the
    counterbore a second cylinder of D to h deep. Raises `ValueError` for any other call.
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
    selected: int | None = None
    for call in _CALL.finditer(body):
        name, args = call.group(1), call.group(2)
        if name in ("box", "cylinder"):
            if ops:
                raise ValueError("a second solid on the chain")
            ops.append(("+", _made(plane, (0.0, 0.0, 0.0), name, args)))
        elif name in ("union", "cut"):
            made = _MADE.match(args)
            if made is None or made.group(1) != plane:
                raise ValueError(f"a {name} this tool does not read")
            offset = (
                _num(made.group(2) or "0"),
                _num(made.group(3) or "0"),
                _num(made.group(4) or "0"),
            )
            solid = _made(plane, offset, made.group(5), made.group(6))
            ops.append(("+" if name == "union" else "-", solid))
            points = None
        elif name == "faces":
            chosen = re.fullmatch(r'">([XYZ])"', args)
            if chosen is None:
                raise ValueError(f"a selector this tool does not read: {args}")
            a = "XYZ".index(chosen.group(1))
            if selected is not None and selected != a:
                raise ValueError("faces on faces of another direction")
            selected = a
        elif name == "workplane" and args == "":
            if selected is None:
                raise ValueError("a workplane on no faces")
            normal = [0.0, 0.0, 0.0]
            normal[selected] = 1.0
            nv = (normal[0], normal[1], normal[2])
            xd = _cross((0.0, 0.0, 1.0), nv)
            if math.hypot(*xd) == 0.0:
                xd = (1.0, 0.0, 0.0)
            origin = list(frame[0])
            origin[selected] = _top(ops, selected)
            frame = ((origin[0], origin[1], origin[2]), xd, _cross(nv, xd), nv)
            points = [frame[0]]
            selected = None
        elif name == "pushPoints":
            pairs = re.findall(rf"\({_NUMBER}, {_NUMBER}\)", args)
            if not pairs or len(pairs) != args.count("(") or points is None:
                raise ValueError("points this tool does not read")
            points = [_at(frame, _num(u), _num(v), 0.0) for u, v in pairs]
        elif name in ("hole", "cboreHole"):
            if points is None:
                raise ValueError("a hole on no workplane")
            values = [_num(v) for v in args.split(",")]
            a = _axis(frame[3])
            top = frame[0][a]
            lo, hi = _united_box(ops)
            depth = math.dist(lo, hi)
            if top - depth >= lo[a] or len(values) != (1 if name == "hole" else 3):
                raise ValueError("a hole this tool does not read")
            for p in points:
                if name == "hole":
                    ops.append(("-", Rod(a, p, values[0] / 2, top - depth, top)))
                else:
                    d, big, deep = values
                    ops.append(("-", Rod(a, p, d / 2, top - depth, top - deep)))
                    ops.append(("-", Rod(a, p, big / 2, top - deep, top)))
            points = None
        else:
            raise ValueError(f"a call this tool does not read: {name}")
    return ops


def part_closed_form(text: str) -> dict[str, object]:
    """The `ClosedForm` JSON of a manifold_block or connecting_rod program."""
    ops = part_ops(text)
    volume, area, centroid, bounds = part_measures(ops)
    solids = "; ".join(
        f"{kind} {'box' if isinstance(s, Cuboid) else 'cylinder'} {s}" for kind, s in ops
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


FORM_FAMILIES = (
    "t_pipe_fitting_",
    "u_bolt_",
    "j_hook_",
    "manifold_block_",
    "connecting_rod_",
    "bellows_",
    "spacer_ring_",
)


def closed_form_for(stem: str, text: str, sha256: str) -> dict[str, object] | None:
    """The closed form of a program of a family (or a SHA-256) this tool knows, else None."""
    if sha256 in CROSSING:
        return crossing_closed_form(sha256)
    if stem.startswith("t_pipe_fitting_"):
        return tee_closed_form(text)
    if stem.startswith(("u_bolt_", "j_hook_")):
        return hook_closed_form(text)
    if stem.startswith(("manifold_block_", "connecting_rod_")):
        return part_closed_form(text)
    if stem.startswith("bellows_"):
        return bellows_closed_form(text)
    if stem.startswith("spacer_ring_"):
        return slotted_ring_closed_form(text)
    return None


def _closed_form_job(job: tuple[str, str, str]) -> dict[str, object] | None:
    return closed_form_for(*job)


def verdicts_for(
    table: Path,
    corpus_texts: dict[str, str],
    refusals: dict[str, str],
    arris_bugs: dict[str, str] | None = None,
) -> dict[str, dict[str, object]]:
    """A verdict for each row of `table` no rule classes, of a family this tool knows.

    A row no rule classes is `unclassified`, or classed only by a verdict (a table run
    with `--verdicts`), so the same table gives the same verdicts either way; a row
    arris ended `unsupported_api` is outside the subset and gets none. A family
    with a closed form is `occt_wrong` by it; a family named in `refusals`
    (`family=regression fixture`, or a single row's stem in place of the family, which wins) is
    `arris_refusal` by that fixture, and one named in `arris_bugs` is `arris_bug` by its
    fixture. A key in both raises `ValueError`.
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
        if entry.row.outcome.value != "unclassified" and entry.row.verdict is None:
            continue
        if entry.row.status is Status.UNSUPPORTED_API:
            continue  # outside the subset: the kernel never saw it, so no finding classes it
        family = re.sub(r"_\d+_s\d+$", "", entry.name)
        if entry.name in refusals or (entry.name not in bugs and family in refusals):
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
        elif entry.name.startswith(FORM_FAMILIES) or entry.row.program_sha256 in CROSSING:
            jobs.append((entry.name, corpus_texts[entry.name], entry.row.program_sha256))
    # Each closed form is a pure function of its program, worked out one per process, each
    # process started afresh (a fork of a process with threads may deadlock).
    forms: list[dict[str, object] | None] = []
    if jobs:
        spawn = multiprocessing.get_context("spawn")
        with ProcessPoolExecutor(max_workers=WORKERS, mp_context=spawn) as pool:
            forms = list(pool.map(_closed_form_job, jobs))
    for (stem, _, _), closed in zip(jobs, forms, strict=True):
        if closed is not None:
            out[stem] = {"disagreement": "occt_wrong", "evidence": closed}
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
    ):
        raise ValueError(
            f"refused for another reason than fixture {name!r}: {refusal.kind}: {refusal.message}"
        )


def main(argv: Sequence[str] | None = None) -> int:
    """Write the verdicts of a corpus table's unclassified rows, checked against both sides."""
    import arris_gym as ag
    from arris_gym.census import benchcad, cadrecode
    from arris_gym.fidelity import OracleReport, Verdict, compare

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", choices=("benchcad", "cadrecode"), default="benchcad")
    parser.add_argument("--table", type=Path, required=True, help="a fidelity.json.gz")
    parser.add_argument("--oracle-rows", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
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
    args = parser.parse_args(argv)
    refusals = dict(item.split("=", 1) for item in args.refusal)
    arris_bugs = dict(item.split("=", 1) for item in args.arris_bug)
    programs = benchcad.read() if args.corpus == "benchcad" else cadrecode.read()
    texts = {p.stem: p.text for p in programs}
    verdicts = verdicts_for(args.table, texts, refusals, arris_bugs)
    reports = {}
    for line in gzip.decompress(args.oracle_rows.read_bytes()).decode("utf-8").splitlines():
        row = json.loads(line)
        reports[row["stem"]] = OracleReport.model_validate(row["report"])
    stems = list(verdicts)
    with ag.Sandbox() as sandbox:
        results = sandbox.run_many([texts[s] for s in stems], dialect="cq", workers=WORKERS)
    refused = []
    for stem, result in zip(stems, results, strict=True):
        try:
            evidence = verdicts[stem]["evidence"]
            if verdicts[stem]["disagreement"] == "arris_refusal" and isinstance(evidence, dict):
                check_refusal_cause(result.refusal, str(evidence["path"]))
            compare(result, reports[stem], Verdict.model_validate(verdicts[stem]))
        except ValueError as error:
            refused.append(f"{stem}: {error}")
    if refused:
        print("\n".join(refused), file=sys.stderr)
        return 1
    args.out.write_text(json.dumps(verdicts, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"{len(verdicts)} verdicts, each checked by `compare`", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

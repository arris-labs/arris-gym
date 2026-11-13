#!/usr/bin/env python3
"""Closed forms of the BenchCAD parts the oracle gets wrong (ADR-0006's `ClosedForm`).

Outside the gate, no oracle imported or run. Reads the pinned BenchCAD corpus
(the `[corpus]` extra) and the committed oracle rows, works out each listed
family's measures from how the part is built (never from either kernel's output),
and writes one `Verdict` per stem that the row's measures can test:

    uv run --extra corpus tools/cq_closed_forms.py --table T --oracle-rows O --out V.json

Two part shapes, each read from its program's text (a program that is not exactly
one of them raises, never guessed):

- **t_pipe_fitting**: a main cylinder M (axis = the plane's normal, radius R,
  height h), a branch B on the plane's local +y from y = 0 (radius r, to y = h2),
  a bore D through B (radius s, from y = 0), and a through bore C of M (radius q),
  as ((M united with B) less D) less C. Volume, moment and area are one-dimensional integrals
  over the part's cross-sections and surface patches (each patch's formula is in
  `_tee`).
- **u_bolt / j_hook**: one or two vertical cylinders (radius r) joined to a half
  torus (major radius R = the cylinder's offset, minor radius r) at its end disc
  z0, with an optional box under the cylinders. Pappus gives the torus; the only
  overlap, a cylinder with the torus's first r/2 of height, is
  an integral over a height h of the intersection's cross-section
  `2 min(wC, wT)`, and its boundary patches are one-dimensional integrals (`_hook`).

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
import json
import math
import re
import sys
from collections.abc import Callable, Sequence
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


def tee_closed_form(text: str) -> dict[str, object]:
    """The `ClosedForm` JSON of a tee program, in global coordinates."""
    plane = re.search(r'cq\.Workplane\("(XY|XZ|YZ)"\)', text)
    assert plane is not None
    p = _tee(text)
    volume, area, centroid, bounds = tee_measures(p)
    lo, hi = box_to_global(plane.group(1), bounds)
    return {
        "kind": "closed_form",
        "volume": volume,
        "area": area,
        "centroid": list(to_global(plane.group(1), centroid)),
        "bounds": [list(lo), list(hi)],
        "note": (
            "a tee on the "
            + plane.group(1)
            + " plane, ((main cylinder R, h) united with a branch r on y from 0 to hb) "
            "cut by a branch bore s and a through bore q; volume, y moment and area "
            "are one-dimensional integrals over the cross-section and each cylinder's "
            f"surface patch (tools/cq_closed_forms.py): R={p['R']}, h={p['h']}, "
            f"r={p['r']}, hb={p['hb']}, s={p['s']}, q={p['q']}"
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
    if torus is None or not 1 <= len(cyl) <= 2 or 'Workplane("XY")' not in text:
        raise ValueError("not the half-torus hook this tool reads")
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
    return out


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
    m_x = 0.0
    m_z = m_torus_z
    box_top = 0.0
    if box is not None:
        cx, cz, bx, by, bz = box
        box_top = cz + bz / 2
        volume += bx * by * bz
        m_x += bx * by * bz * cx
        m_z += bx * by * bz * cz
        area += 2 * (bx * by + bx * bz + by * bz)
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
            kept = max(low, bottom) if below else low
            volume -= pi * r * r * (box_top - kept)
            m_x -= pi * r * r * (box_top - kept) * x
            m_z -= pi * r * r * (box_top - kept) * (box_top + kept) / 2
            area -= pi * r * r  # the footprint on the box's top face
            if below:
                area += 2 * pi * r * below
    centroid = (m_x / volume, 0.0, m_z / volume)
    low_all = [low for _, low, _ in cylinders]
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


def closed_form_for(stem: str, text: str, sha256: str) -> dict[str, object] | None:
    """The closed form of a program of a family (or a SHA-256) this tool knows, else None."""
    if sha256 in CROSSING:
        return crossing_closed_form(sha256)
    if stem.startswith("t_pipe_fitting_"):
        return tee_closed_form(text)
    if stem.startswith(("u_bolt_", "j_hook_")):
        return hook_closed_form(text)
    return None


def verdicts_for(
    table: Path, corpus_texts: dict[str, str], refusals: dict[str, str]
) -> dict[str, dict[str, object]]:
    """A verdict for each unclassified row of `table` of a family this tool knows.

    A family with a closed form is `occt_wrong` by it; a family named in `refusals`
    (`family=regression fixture`) is `arris_refusal` by that fixture. Each verdict is
    built as a `Verdict`, so ADR-0006's checks of the evidence run here.
    """
    from arris_gym.fidelity import FidelityTable

    rows = FidelityTable.model_validate_json(gzip.decompress(table.read_bytes())).entries
    out: dict[str, dict[str, object]] = {}
    for entry in rows:
        if entry.row.outcome.value != "unclassified":
            continue
        family = re.sub(r"_\d+_s\d+$", "", entry.name)
        text = corpus_texts[entry.name]
        verdict: dict[str, object]
        if family in refusals:
            verdict = {
                "disagreement": "arris_refusal",
                "evidence": {"kind": "fixture", "path": refusals[family]},
            }
        else:
            closed = closed_form_for(entry.name, text, entry.row.program_sha256)
            if closed is None:
                continue
            verdict = {"disagreement": "occt_wrong", "evidence": closed}
        out[entry.name] = verdict
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
        help="class a family's rows arris_refusal by this regression fixture directory",
    )
    args = parser.parse_args(argv)
    refusals = dict(item.split("=", 1) for item in args.refusal)
    programs = benchcad.read() if args.corpus == "benchcad" else cadrecode.read()
    texts = {p.stem: p.text for p in programs}
    verdicts = verdicts_for(args.table, texts, refusals)
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

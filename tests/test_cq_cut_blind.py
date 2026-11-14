"""`cutBlind(depth)` extrudes the pending sketch and cuts it in one call (ADR-0019 rule 3).

The pending circle, ring or circles at points are swept `depth` along the
plane's normal (against it when negative) and cut from the chain's solid. The
closed forms are worked out by hand from how each part is built
(`test_array_probe.PARTS` and `OTHER` for the probe's own programs, the
functions below for the corpus's gear); nothing is read from `cq`. Each
`ok-cut-blind-*` fixture also has the oracle's recorded report, and each
`runtime-cut-blind-*` one CadQuery's own refusal.
"""

from __future__ import annotations

import gzip
import hashlib
import itertools
import json
import math
import re

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import arris_gym as ag
import arris_gym.cq as cq
import cq_array_probe as probe
import fixture_cases
from arris_gym.fidelity import (
    ClosedForm,
    DisagreementClass,
    FidelityOutcome,
    Verdict,
    compare,
)
from test_array_probe import OTHER, PARTS
from test_cq_hole import measures
from test_cq_rarray import cases, recorded

BOX_BOUNDS: Bounds = ((-5.0, -4.0, -2.0), (5.0, 4.0, 2.0))
REV_BOUNDS: Bounds = ((-5.0, 0.0, -5.0), (5.0, 4.0, 5.0))
SLAB_BOUNDS: Bounds = ((-5.0, 0.0, -5.0), (5.0, 3.0, 5.0))
Kinds = list[list[object]]
Bounds = tuple[tuple[float, float, float], tuple[float, float, float]]
# slug -> (probe construction, bounds, faces, kinds, genus, what it is). The faces are counted
# from how each part is cut: a box has 6 planes, the revolved cylinder 2 planes and its wall; a
# pocket adds its wall and its floor, a hole through its wall alone, a groove two walls, a floor
# and the island's top.
SLUGS: dict[str, tuple[str, Bounds, int, Kinds, int, str]] = {
    "ok-cut-blind-disc": (
        "blind-disc",
        BOX_BOUNDS,
        8,
        [["cylinder", 1], ["plane", 7]],
        0,
        "`circle(1).cutBlind(-1.5)` from the top face: a pocket 1.5 deep",
    ),
    "ok-cut-blind-disc-off-centre": (
        "blind-disc-off-centre",
        BOX_BOUNDS,
        8,
        [["cylinder", 1], ["plane", 7]],
        0,
        "`moveTo(2, 1).circle(1).cutBlind(-1.5)`: the pocket at the point",
    ),
    "ok-cut-blind-to-the-bottom": (
        "blind-to-the-bottom",
        BOX_BOUNDS,
        7,
        [["cylinder", 1], ["plane", 6]],
        1,
        "`cutBlind(-4)` on the 4-thick box: the tool's far end on the bottom face, a hole through",
    ),
    "ok-cut-blind-past-the-part": (
        "blind-past-the-part",
        BOX_BOUNDS,
        7,
        [["cylinder", 1], ["plane", 6]],
        1,
        "`cutBlind(-10)` on the 4-thick box: a hole through",
    ),
    "ok-cut-blind-positive": (
        "blind-positive",
        BOX_BOUNDS,
        7,
        [["plane", 7]],
        0,
        "`cutBlind(1)` from the top face: the sweep runs out of the part, the box is unchanged "
        "(volume, area, centroid and bounds are the box's). The tool touches the top face "
        "along its circle, which arris keeps as an edge: the top is two planes, a disc and "
        "the rest, a face more than CadQuery's 6 (face counts are carried, never judged)",
    ),
    "ok-cut-blind-inside-the-part": (
        "blind-inside-the-part",
        BOX_BOUNDS,
        9,
        [["cylinder", 1], ["plane", 8]],
        0,
        "`workplane(offset=-1).circle(1).cutBlind(-1)`: the tool lies wholly inside the part, "
        "a closed void: one solid of two shells, the box's and the void's",
    ),
    "ok-cut-blind-positive-from-inside": (
        "blind-positive-from-inside",
        BOX_BOUNDS,
        8,
        [["cylinder", 1], ["plane", 7]],
        0,
        "`workplane(offset=-1).circle(1).cutBlind(2)`: from 1 below the top, up through it: "
        "a pocket 1 deep",
    ),
    "ok-cut-blind-box-max-x": (
        "blind-side>X",
        BOX_BOUNDS,
        8,
        [["cylinder", 1], ["plane", 7]],
        0,
        '`faces(">X").workplane().moveTo(1, 0.5).circle(0.5).cutBlind(-2)`: a pocket from the side',
    ),
    "ok-cut-blind-ring": (
        "blind-ring",
        BOX_BOUNDS,
        10,
        [["cylinder", 2], ["plane", 8]],
        0,
        "`circle(2).circle(1).cutBlind(-1)`: an annular groove, the island's top a face of its own",
    ),
    "ok-cut-blind-ring-inner-first": (
        "blind-ring-inner-first",
        BOX_BOUNDS,
        10,
        [["cylinder", 2], ["plane", 8]],
        0,
        "`circle(1).circle(2).cutBlind(-1)`: the same groove, whichever circle came first",
    ),
    "ok-cut-blind-points": (
        "blind-points",
        BOX_BOUNDS,
        10,
        [["cylinder", 2], ["plane", 8]],
        0,
        "`pushPoints([(-3, -2), (3, 2)]).circle(0.5).cutBlind(-1)`: a pocket at each point",
    ),
    "ok-cut-blind-polar": (
        "blind-polar",
        BOX_BOUNDS,
        18,
        [["cylinder", 6], ["plane", 12]],
        0,
        "`polarArray(3, 0, 360, 6).circle(0.5).cutBlind(-1)`: six pockets",
    ),
    "ok-cut-blind-polar-through": (
        "blind-polar-through",
        BOX_BOUNDS,
        12,
        [["cylinder", 6], ["plane", 6]],
        6,
        "`polarArray(3, 0, 360, 6).circle(0.5).cutBlind(-4)`: six holes through",
    ),
    "ok-cut-blind-rarray": (
        "blind-rarray",
        BOX_BOUNDS,
        14,
        [["cylinder", 4], ["plane", 10]],
        0,
        "`rarray(4, 3, 2, 2).circle(1).cutBlind(-1)`: four pockets",
    ),
    "ok-cut-blind-revolved-max-y": (
        "rev-blind-disc",
        REV_BOUNDS,
        5,
        [["cylinder", 2], ["plane", 3]],
        0,
        "a disc of 1 cut 1 deep from a revolved cylinder's `>Y` end face",
    ),
    "ok-cut-blind-revolved-min-y": (
        "rev-blind-disc<Y",
        REV_BOUNDS,
        5,
        [["cylinder", 2], ["plane", 3]],
        0,
        "a disc of 1 cut 1 deep from a revolved cylinder's `<Y` end face",
    ),
    "ok-cut-blind-revolved-whole-face": (
        "rev-blind-whole-face",
        SLAB_BOUNDS,
        3,
        [["cylinder", 1], ["plane", 2]],
        0,
        "a disc of the end face's own radius, 1 deep: the tool's wall on the part's, a slab "
        "off the end, a cylinder 3 long",
    ),
    "ok-cut-blind-revolved-ring": (
        "rev-blind-ring",
        REV_BOUNDS,
        7,
        [["cylinder", 3], ["plane", 4]],
        0,
        "a ring of 2 and 1 cut 1 deep from a revolved cylinder's end face: a groove",
    ),
    "ok-cut-blind-revolved-polar": (
        "rev-blind-polar",
        REV_BOUNDS,
        15,
        [["cylinder", 7], ["plane", 8]],
        0,
        "six pockets of 0.5, 1 deep, on a circle of 3 in a revolved cylinder's end face",
    ),
    "ok-cut-blind-flange-through": (
        "tube-blind-polar-through",
        REV_BOUNDS,
        10,
        [["cylinder", 8], ["plane", 2]],
        7,
        "six tools through a revolved flange (radii 2 to 5, 4 thick): both ends flush with its "
        "faces, six holes through",
    ),
}
# The constructions that leave a void: one solid of two shells.
VOIDS = {"blind-inside-the-part"}
RUNTIME = {
    "runtime-cut-blind-zero": (
        "blind-zero",
        "ValueError: Workplane.cutBlind(0): a zero depth (CadQuery's Standard_ConstructionError)",
    ),
    "runtime-cut-blind-zero-no-solid": (
        "blind-zero-no-solid",
        "ValueError: Workplane.cutBlind(0): a zero depth (CadQuery's Standard_ConstructionError)",
    ),
    "runtime-cut-blind-nothing-pending": (
        "blind-nothing-pending",
        "ValueError: No pending wires present",
    ),
    "runtime-cut-blind-no-solid": (
        "blind-no-solid",
        "ValueError: Cannot find a solid on the stack or in the parent chain",
    ),
}
# What CadQuery raises for each, its last line.
RAISES = {
    "runtime-cut-blind-zero": "OCP.OCP.Standard.Standard_ConstructionError: "
    "BRepSweep_Translation::Constructor",
    "runtime-cut-blind-zero-no-solid": "OCP.OCP.Standard.Standard_ConstructionError: "
    "BRepSweep_Translation::Constructor",
    "runtime-cut-blind-nothing-pending": "ValueError: No pending wires present",
    "runtime-cut-blind-no-solid": "ValueError: Cannot find a solid on the stack or in the parent "
    "chain",
}
# The keywords no corpus program writes stay outside the subset.
UNSUPPORTED = {
    "unsupported-cut-blind-clean": (
        'import cadquery as cq\n\nresult = cq.Workplane("XY").box(10, 8, 4).faces(">Z").workplane()'
        ".circle(1).cutBlind(-1, clean=False)\nshow_object(result)\n",
        "Workplane.cutBlind(num; clean=bool)",
    ),
    "unsupported-cut-blind-next": (
        'import cadquery as cq\n\nresult = cq.Workplane("XY").box(10, 8, 4).faces(">Z").workplane()'
        '.circle(1).cutBlind("next")\nshow_object(result)\n',
        "Workplane.cutBlind(str)",
    ),
}


def corpus_program(slug: str) -> str:
    """A corpus program as the fixture holds it: `program.py`, the text BenchCAD wrote."""
    return (fixture_cases.ROOT / "cq" / slug / "program.py").read_text(encoding="utf-8")


def polyline(program: str) -> list[tuple[float, float]]:
    """The vertices of the program's one `polyline([...])` call."""
    body = re.search(r"polyline\(\[(.*?)\]\)", program, re.DOTALL)
    assert body is not None
    return [(float(a), float(b)) for a, b in re.findall(r"\(([-\d.]+), ([-\d.]+)\)", body.group(1))]


def gear() -> dict[str, object]:
    """BenchCAD's `spur_gear_000738_s20260505`: a gear outline extruded 11.4, a groove, a hole.

    The outline is a polygon of N vertices on `YZ` (local x world y, local y world
    z) extruded 11.4 along +x: with its shoelace area A, perimeter P and
    centroid c, V0 = 11.4 A, A0 = 2 A + 11.4 P, centre (5.7, c). The `<X` face
    carries a ring of 8.47 and 4.34 cut 6.52 deep from x = 0: it lies inside the
    outline (checked below), so V = pi (8.47^2 - 4.34^2) 6.52 comes off, the
    ring's walls 2 pi (8.47 + 4.34) 6.52 are added (its mouth and floor cancel),
    centre (3.26, 0, 0). The `>X` bore of 3.26 (r = 1.63) goes through the
    core, x from 0 to 11.4, inside the island of 4.34: V = pi r^2 11.4 off, its
    wall 2 pi r 11.4 added and its two ends 2 pi r^2 taken, centre (5.7, 0, 0).
    Faces: the N sides, `>X`, the `<X` outline face, the island's top and the
    groove's floor are planes (N + 4); the groove's two walls and the bore's wall
    are cylinders: N + 7, genus 1.
    """
    pts = polyline(corpus_program("ok-cut-blind-corpus-spur-gear"))
    # The outline is one closed polygon: its last vertex is not its first.
    assert pts[0] != pts[-1]
    n = len(pts)
    edges = [(pts[i], pts[(i + 1) % n]) for i in range(n)]
    cross = [a[0] * b[1] - b[0] * a[1] for a, b in edges]
    area = abs(sum(cross)) / 2
    sign = 1.0 if sum(cross) > 0 else -1.0
    cy = sign * sum((a[0] + b[0]) * c for (a, b), c in zip(edges, cross, strict=True)) / (6 * area)
    cz = sign * sum((a[1] + b[1]) * c for (a, b), c in zip(edges, cross, strict=True)) / (6 * area)
    perimeter = sum(math.dist(a, b) for a, b in edges)
    # The ring must lie inside the outline: its outer circle is nearer the origin than any edge.
    nearest = min(distance_to_segment(a, b) for a, b in edges)
    assert nearest > 8.47
    # No two consecutive sides are collinear, so none are one face.
    assert all(abs(c) > 1e-6 for c in turns(pts))
    r_out, r_in, depth, r_hole, thick = 8.47, 4.34, 6.52, 1.63, 11.4
    groove = math.pi * (r_out**2 - r_in**2) * depth
    bore = math.pi * r_hole**2 * thick
    volume = area * thick - groove - bore
    moment = (
        area * thick * 5.7 - groove * 3.26 - bore * 5.7,
        area * thick * cy,
        area * thick * cz,
    )
    surface = (
        2 * area
        + thick * perimeter
        + 2 * math.pi * (r_out + r_in) * depth
        + 2 * math.pi * r_hole * thick
        - 2 * math.pi * r_hole**2
    )
    ys = [p[0] for p in pts]
    zs = [p[1] for p in pts]
    return measures(
        volume,
        surface,
        (moment[0] / volume, moment[1] / volume, moment[2] / volume),
        ((0, min(ys), min(zs)), (thick, max(ys), max(zs))),
        n + 7,
        [["cylinder", 3], ["plane", n + 4]],
        genus=1,
    )


def distance_to_segment(a: tuple[float, float], b: tuple[float, float]) -> float:
    """The distance from the origin to the segment `a` to `b`."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    t = max(0.0, min(1.0, -(a[0] * dx + a[1] * dy) / (dx * dx + dy * dy)))
    return math.hypot(a[0] + t * dx, a[1] + t * dy)


def turns(pts: list[tuple[float, float]]) -> list[float]:
    """The cross product of each pair of consecutive sides (zero where they are collinear)."""
    n = len(pts)
    out = []
    for i in range(n):
        a, b, c = pts[i - 1], pts[i], pts[(i + 1) % n]
        out.append((b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0]))
    return out


def disc_integral(f: object, centre: float, radius: float) -> float:
    """The integral of `f(x, z)` over the disc of `radius` about `(centre, 0)`.

    Gauss-Legendre in the radius and the trapezoid rule in the angle, which
    converges geometrically on a periodic integrand: for the smooth functions
    here the sum is exact to rounding.
    """
    assert callable(f)
    nodes, weights = np.polynomial.legendre.leggauss(24)
    u = radius * (nodes + 1) / 2
    w = radius / 2 * weights
    theta = np.arange(96) * (2 * math.pi / 96)
    total = 0.0
    for ui, wi in zip(u, w, strict=True):
        for t in theta:
            total += wi * ui * (2 * math.pi / 96) * f(centre + ui * math.cos(t), ui * math.sin(t))
    return float(total)


def bellows() -> dict[str, object]:
    """BenchCAD's `bellows_011187_s20260505`: a revolved bellows with six holes at each end.

    The 16-edge profile (x the radius, y the height) turns about the y axis:
    V0 = 2 pi sum (x_i + x_j)(x_i y_j - x_j y_i) / 6 (Pappus), A0 = pi sum (x_i +
    x_j) |edge| (each edge a cone, a cylinder or a disc), the centroid's height
    2 pi (int x y dA) / V0. Six circles of 1.52 on a circle of 48.896 are cut
    10.99 deep from each end face.
    The `<Y` end: they lie inside the flange (radii 46.52 to 50.84, y 0 to 10.99), the
    tool as thick as it: six holes through, V = pi r^2 10.99 each, centre y = 5.495,
    its wall added and its two discs taken. The `>Y` end: the outer cone from
    (43.08, 171.79) to (50.84, 182.78) leaves a sliver above it under the
    top face, the tool's floor (171.79) below the cone everywhere in the
    circle: the pocket is the sliver, h(rho) = 182.78 - 171.79 - k (rho -
    43.08) deep, k = 10.99 / 7.76, over the circle: V = integral of h dA, its
    wall added (the integral of h around the circle) and the top disc and the cone's
    patch (sqrt(1 + k^2) pi r^2) taken; the sliver goes through to the cone, a
    hole through the rim. The six about the axis cancel in x and z.
    Faces: the 16 edges (5 planes, 9 cones, 2 cylinders) and a wall for each of the
    twelve holes (cylinders): 28 faces, genus 1 + 12.
    """
    pts = polyline(corpus_program("ok-cut-blind-corpus-bellows"))
    assert pts[0] == pts[-1]
    edges = list(itertools.pairwise(pts))
    cross = [a[0] * b[1] - b[0] * a[1] for a, b in edges]
    sign = 1.0 if sum(cross) > 0 else -1.0
    v0 = (
        2
        * math.pi
        * sign
        * sum((a[0] + b[0]) * c for (a, b), c in zip(edges, cross, strict=True))
        / 6
    )
    a0 = math.pi * sum((a[0] + b[0]) * math.dist(a, b) for a, b in edges)
    # int x y dA over the polygon, then the volume's moment in y is 2 pi times it.
    xy = (
        sign
        * sum(
            c * (a[0] * b[1] + 2 * a[0] * a[1] + 2 * b[0] * b[1] + b[0] * a[1])
            for (a, b), c in zip(edges, cross, strict=True)
        )
        / 24
    )
    m0 = 2 * math.pi * xy
    r, big, d, count = 1.52, 48.896, 10.99, 6
    # The bottom flange: six holes through, centre y = d / 2.
    hole = math.pi * r * r * d
    # The top sliver, above the cone (x1, y1) to (x2, y2), under y = y_top.
    (x1, y1), (x2, y2), y_top = pts[12], pts[13], max(p[1] for p in pts)
    k = (y2 - y1) / (x2 - x1)
    assert abs(y_top - y2) < 1e-12
    assert x1 < big - r
    assert big + r < x2

    def depth(x: float, z: float) -> float:
        return y_top - y1 - k * (math.hypot(x, z) - x1)

    def middle(x: float, z: float) -> float:
        return depth(x, z) * (y_top + y_top - depth(x, z)) / 2

    sliver = disc_integral(depth, big, r)
    ring = 0.0
    for t in np.arange(96) * (2 * math.pi / 96):
        ring += depth(big + r * math.cos(t), r * math.sin(t)) * r * (2 * math.pi / 96)
    patch = math.pi * r * r * (1 + math.sqrt(1 + k * k))
    volume = v0 - count * (hole + sliver)
    moment = m0 - count * (hole * d / 2 + disc_integral(middle, big, r))
    surface = a0 + count * (2 * math.pi * r * d - 2 * math.pi * r * r) + count * (ring - patch)
    top = max(p[0] for p in pts)
    return measures(
        volume,
        surface,
        (0, moment / volume, 0),
        ((-top, 0, -top), (top, y_top, top)),
        28,
        [["cone", 9], ["cylinder", 14], ["plane", 5]],
        genus=13,
    )


def fixture_programs() -> dict[str, tuple[str, dict[str, object], str]]:
    """Every generated `ok-cut-blind-*` fixture: slug -> (program, expected measures, note)."""
    programs = probe.constructed_programs()
    found = {}
    for slug, (name, bounds, faces, kinds, genus, note) in SLUGS.items():
        volume, area, centroid = OTHER[name] if name in OTHER else PARTS[name].measures()
        got = measures(
            volume,
            area,
            centroid,
            bounds,
            faces,
            kinds,
            shells=2 if name in VOIDS else 1,
            genus=genus,
        )
        if name in VOIDS:
            got["cavities"] = 1
        found[slug] = (programs[name], got, note)
    for slug, expected in (
        ("ok-cut-blind-corpus-spur-gear", gear),
        ("ok-cut-blind-corpus-bellows", bellows),
    ):
        found[slug] = (corpus_program(slug), expected(), expected.__doc__ or "")
    return found


def runtime_programs() -> dict[str, tuple[str, str]]:
    """Every `runtime-cut-blind-*` fixture: slug -> (program text, `cq`'s message)."""
    programs = probe.constructed_programs()
    return {slug: (programs[name], message) for slug, (name, message) in RUNTIME.items()}


def test_every_ok_cut_blind_fixture_is_the_closed_form() -> None:
    committed = cases("ok-cut-blind-")
    assert sorted(committed) == sorted(fixture_programs())
    for slug, (program, expected, _) in fixture_programs().items():
        assert committed[slug].program == program, slug
        got = committed[slug].expected["measures"]
        assert json.loads(json.dumps(got)) == json.loads(json.dumps(expected)), slug


# Where the closed form and arris agree and Open CASCADE does not (see
# `test_the_oracle_is_off_the_bellows_closed_form`).
OCCT_WRONG = {"ok-cut-blind-corpus-bellows"}


@pytest.mark.parametrize("slug", sorted(set(fixture_programs()) - OCCT_WRONG))
def test_ok_cut_blind_fixtures_agree_with_the_recorded_oracle(slug: str) -> None:
    case = cases("ok-cut-blind-")[slug]
    assert compare(fixture_cases.run(case), recorded(slug)).outcome is FidelityOutcome.AGREE


def test_the_corpus_programs_are_the_corpuss() -> None:
    """Each corpus fixture's `program.py` is a program of the committed BenchCAD rows."""
    data = gzip.decompress(
        (fixture_cases.ROOT / "c2" / "benchcad" / "programs.jsonl.gz").read_bytes()
    )
    shas = {json.loads(line)["program_sha256"] for line in data.splitlines()}
    for slug in ("ok-cut-blind-corpus-spur-gear", "ok-cut-blind-corpus-bellows"):
        assert hashlib.sha256(corpus_program(slug).encode()).hexdigest() in shas, slug


def test_the_oracles_reports_hold_the_closed_forms() -> None:
    """Open CASCADE builds the closed form's part: one solid, the same volume and area."""
    for slug, (_, expected, _) in fixture_programs().items():
        if slug in OCCT_WRONG:
            continue
        report = recorded(slug)
        assert report.measures is not None
        assert report.measures.solids == 1, slug
        assert fixture_cases.close(report.measures.volume, float(str(expected["volume"]))), slug
        assert fixture_cases.close(report.measures.area, float(str(expected["area"]))), slug


def test_the_oracle_is_off_the_bellows_closed_form() -> None:
    """Open CASCADE's volume of the bellows is off the closed form, arris's is on it.

    The closed form is Pappus's for the revolved profile and a quadrature of the
    sliver over each circle (`bellows`); arris is within 1e-9 of it. The recorded
    oracle report is 1.3e-7 high in volume and 2.3e-7 low in area, with a centroid
    off the axis by 4e-6 (the part is symmetric about it), and its 26 faces are
    the 28 less the two coplanar pairs `clean` merges. The disagreement is
    `occt_wrong` by this closed form, and the fixture holds arris to it: nothing is
    widened.
    """
    slug = "ok-cut-blind-corpus-bellows"
    expected = fixture_programs()[slug][1]
    volume = float(str(expected["volume"]))
    area = float(str(expected["area"]))
    got = fixture_cases.run(cases("ok-cut-blind-")[slug]).measures
    assert got is not None
    assert abs(got.volume - volume) <= 1e-9 * volume
    assert abs(got.area - area) <= 1e-9 * area
    report = recorded(slug)
    assert report.measures is not None
    assert abs(report.measures.volume - volume) > 1e-8 * volume
    assert abs(report.measures.area - area) > 1e-8 * area
    assert report.measures.faces == 26
    assert fixture_cases.close(report.measures.volume, volume)  # within the fixtures' 1e-6
    row = compare(fixture_cases.run(cases("ok-cut-blind-")[slug]), report)
    assert row.outcome is FidelityOutcome.UNCLASSIFIED


def test_the_bellows_verdict_is_its_closed_form() -> None:
    """`verdict.json` classes the bellows `occt_wrong` by the closed form `bellows` computes."""
    slug = "ok-cut-blind-corpus-bellows"
    path = fixture_cases.ROOT / "cq" / slug / "verdict.json"
    verdict = Verdict.model_validate_json(path.read_text(encoding="utf-8"))
    assert verdict == bellows_verdict()
    result = fixture_cases.run(cases("ok-cut-blind-")[slug])
    row = compare(result, recorded(slug), verdict)
    assert (row.outcome, row.disagreement) == (
        FidelityOutcome.DISAGREE,
        DisagreementClass.OCCT_WRONG,
    )


def bellows_verdict() -> Verdict:
    """The verdict on the bellows: the closed form of `bellows`, the oracle's figures off it."""
    want = bellows()
    centroid = want["centroid"]
    bounds = want["bounds"]
    assert isinstance(centroid, list)
    assert isinstance(bounds, list)
    return Verdict(
        disagreement=DisagreementClass.OCCT_WRONG,
        evidence=ClosedForm(
            volume=float(str(want["volume"])),
            area=float(str(want["area"])),
            centroid=(centroid[0], centroid[1], centroid[2]),
            bounds=((*bounds[0],), (*bounds[1],)),
            note=bellows.__doc__ or "",
        ),
    )


def test_every_runtime_cut_blind_fixture_is_cadquerys_refusal() -> None:
    committed = cases("runtime-cut-blind-")
    assert sorted(committed) == sorted(runtime_programs())
    for slug, (program, message) in runtime_programs().items():
        assert committed[slug].program == program, slug
        assert committed[slug].expected == {
            "dialect": "cq",
            "status": "runtime",
            "message": message,
        }


@pytest.mark.parametrize("slug", sorted(RUNTIME))
def test_a_cut_cadquery_refuses_is_a_runtime_status_that_agrees_with_the_oracle(slug: str) -> None:
    report = recorded(slug)
    assert report.status.value == "runtime"
    assert (report.message or "").splitlines()[-1] == RAISES[slug]
    case = cases("runtime-cut-blind-")[slug]
    assert compare(fixture_cases.run(case), report).outcome is FidelityOutcome.AGREE


@pytest.mark.parametrize("slug", sorted(UNSUPPORTED))
def test_a_form_outside_the_subset_is_unsupported(slug: str) -> None:
    program, message = UNSUPPORTED[slug]
    case = cases("unsupported-cut-blind-")[slug]
    assert case.program == program
    assert case.expected == {"dialect": "cq", "status": "unsupported_api", "message": message}


@pytest.mark.parametrize(
    ("chain", "message"),
    [
        ('.faces(">Z").cutBlind(-1)', "Workplane.cutBlind on selected faces"),
        (".pushPoints([(1, 1)]).cutBlind(-1)", "Workplane.cutBlind on a stack of points"),
    ],
)
def test_a_cut_in_a_context_outside_the_subset_is_unsupported(chain: str, message: str) -> None:
    program = f'import cadquery as cq\n\nresult = cq.Workplane("XY").box(4, 6, 8){chain}\n'
    result = ag.run(program + "show_object(result)\n", dialect="cq")
    assert result.status is ag.Status.UNSUPPORTED_API
    assert message in result.message


def test_a_cut_leaves_the_workplane_it_came_from() -> None:
    wp = cq.Workplane("XY").box(2, 2, 2).faces(">Z").workplane().circle(0.5)
    cut = wp.cutBlind(-1)
    assert wp._solids() == ()
    assert len(cut._solids()) == 1


@settings(max_examples=40, deadline=None)
@given(
    centre=st.tuples(st.integers(-4, 4), st.integers(-4, 4)),
    radius=st.sampled_from([0.5, 1.0, 1.5]),
    depth=st.sampled_from([0.5, 1.0, 2.0, 3.5, 4.0, 6.0]),
)
def test_a_pocket_in_a_box_is_the_closed_form(
    centre: tuple[int, int], radius: float, depth: float
) -> None:
    """Volume V - pi r^2 min(depth, 4) for a 12 x 12 x 4 box, the pocket from the top face.

    A circle of up to 1.5 at a point within 4 of the centre is inside the
    top face (half sizes 6); a depth of 4 or more goes through the box.
    """
    program = (
        "import cadquery as cq\n\nresult = (\n"
        f'    cq.Workplane("XY").box(12, 12, 4).faces(">Z").workplane()\n'
        f"    .moveTo({centre[0]}, {centre[1]}).circle({radius}).cutBlind(-{depth})\n)\n"
        "show_object(result)\n"
    )
    result = ag.run(program, dialect="cq")
    assert result.status is ag.Status.OK, result.message
    assert result.measures is not None
    removed = math.pi * radius * radius * min(depth, 4.0)
    assert fixture_cases.close(result.measures.volume, 576.0 - removed)
    assert result.measures.genus == (1 if depth >= 4.0 else 0)
    # The cut's centroid is the point, half the depth below the face.
    mid = 2.0 - min(depth, 4.0) / 2
    moment = (-removed * centre[0], -removed * centre[1], -removed * mid)
    for k in range(3):
        assert fixture_cases.close(result.measures.centroid[k], moment[k] / (576.0 - removed))

"""The contexts plans/lift-arrays-and-blind-cuts step 5 reads on the oracle (ADR-0019).

An array of points on a compound (`rarray`, `polarArray` then `hole`); a hole
after a blind cut on the same face (BenchCAD's `dome_cap`, whose own revolved
dome is the known spindle-torus refusal, so a box and a revolved cylinder carry
it); a blind cut from a face above a lower part (`impeller`); `union` after
`cutBlind` (`spur_gear`, as written). Each fixture's expectation is a closed
form worked out by hand from how the part is built (the `note` says how), each
beside the oracle's recorded report. Nothing is read from `cq`.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import math

import pytest

import arris_gym as ag
import fixture_cases
from arris_gym.fidelity import FidelityOutcome, OracleReport, compare
from test_cq_cut_blind import distance_to_segment, polyline, turns
from test_cq_hole import measures, wrap
from test_cq_point_contexts import BOX_AREA, BOX_VOLUME, PAIR

CORPUS = "ok-ctx-union-after-a-cut-blind-corpus-spur-gear"
Vec = tuple[float, float, float]


def in_a_compound() -> dict[str, object]:
    """Four bores of r = 1/2 on a circle or a grid about the pair's first box, through it.

    The pair is two 10 x 8 x 4 boxes 10 apart (V = 640, A = 608, one solid each),
    and `faces(">Z").workplane()` is z = 2 with its origin at (0, 0), over the first.
    Four points, (+-3, 0) and (0, +-3) of `polarArray(3, 0, 360, 4)` or (+-2, +-1.5) of
    `rarray(4, 3, 2, 2)`, each a bore through the first box (z -2 to 2) clear of its sides:
    V = 640 - 4 pi r^2 4 = 640 - 4 pi, each wall adds 2 pi r 4 and its two ends take
    2 pi r^2: A = 608 + 4 (4 pi - pi / 2). The points are symmetric about the box's
    centre, so the x moment is the second box's, 320 * 20, and y, z are 0.
    Faces: 12 planes and 4 cylinders; two shells, genus 4.
    """
    volume = 2 * BOX_VOLUME - 4 * math.pi
    return measures(
        volume,
        2 * BOX_AREA + 4 * (4 * math.pi - math.pi / 2),
        (BOX_VOLUME * 20 / volume, 0, 0),
        ((-5, -4, -2), (25, 4, 2)),
        16,
        [["cylinder", 4], ["plane", 12]],
        shells=2,
        genus=4,
    )


def lens(centre: float, big: float, small: float) -> tuple[float, float, float]:
    """The overlap of two discs `centre` apart: its area and each circle's arc inside the other.

    Standard circle-circle intersection: with half-angles `a` at the big disc's centre and
    `b` at the small one's, the area is `big^2 a + small^2 b - centre big sin(a)` and the
    arcs `2 a big` (of the big circle) and `2 b small` (of the small one).
    """
    a = math.acos((centre**2 + big**2 - small**2) / (2 * centre * big))
    b = math.acos((centre**2 + small**2 - big**2) / (2 * centre * small))
    return (
        big * big * a + small * small * b - centre * big * math.sin(a),
        2 * a * big,
        2 * b * small,
    )


def pocket_then_bores() -> dict[str, object]:
    """The 10 x 8 x 4 box, a pocket of r = 2 and 1 deep, then four bores of r = 1 that bite into it.

    `circle(2).cutBlind(-1)` on `>Z` takes z 1 to 2 inside r = 2. `faces(">Z")` is then the
    one top face, the box's top less the pocket, centred on the origin, and
    `polarArray(2.5, 0, 360, 4).hole(2)` bores r = 1 at (+-2.5, 0), (0, +-2.5), through
    (z -2 to 2). Each bore's disc overlaps the pocket's in a lens L (circles 2.5 apart, the
    standard formula in `lens`), so the pocket's slab (V_P = pi 4 1) and the bores
    (V_B = pi 4 each) overlap in L * 1 four times: V = 320 - 4 pi - 4 pi 4 + 4 L.
    Faces: the top has the pocket and the four bites cut out; the floor (z = 1) is the pocket
    less the bites, the pocket's wall splits into the four arcs between them (each of
    arc A_P = 2 a R); each bore's wall is one cylinder with a notch where it meets the pocket
    (length 4 less the arc A_B = 2 b r of the pocket's depth 1). Area = the four sides 144,
    the bottom less four discs (80 - 4 pi), the top less the pocket and the bites
    (80 - 4 pi - 4 (pi - L)), the floor (4 pi - 4 L), the four arcs of pocket wall
    (2 pi 2 - 4 A_P) and the bores' walls (4 (8 pi - A_B)).
    The part is symmetric under a quarter turn, so x and y are 0; z is minus the two removed
    moments about 0: the pocket's slab at z = 1.5, less the lens re-added at 1.5.
    Planes: four sides, top, floor, bottom (7); cylinders: four arcs, four bores (8); genus 4.
    """
    area_l, arc_p, arc_b = lens(2.5, 2.0, 1.0)
    pocket = math.pi * 4
    volume = BOX_VOLUME - pocket - 4 * math.pi * 4 + 4 * area_l
    surface = (
        144
        + (80 - 4 * math.pi)
        + (80 - pocket - 4 * (math.pi - area_l))
        + (pocket - 4 * area_l)
        + (2 * math.pi * 2 - 4 * arc_p)
        + 4 * (2 * math.pi * 4 - arc_b)
    )
    moment = -pocket * 1.5 + 4 * area_l * 1.5
    return measures(
        volume,
        surface,
        (0, 0, moment / volume),
        ((-5, -4, -2), (5, 4, 2)),
        15,
        [["cylinder", 8], ["plane", 7]],
        genus=4,
    )


def pocket_then_bores_revolved() -> dict[str, object]:
    """A cylinder revolved from a rectangle (r = 5, y 0 to 4), a pocket and four bores clear of it.

    `faces("<Y").workplane()` is the y = 0 end, its normal -y; `circle(2).cutBlind(-1)` takes
    y 0 to 1 inside r = 2 (V_P = pi 4 1); `faces("<Y")` is then the annulus at y = 0 (the floor
    is at y = 1), and `polarArray(3, 0, 360, 4).hole(1.4)` bores r = 0.7 at 3 from the axis,
    (2.3 to 3.7: clear of the pocket's wall at 2 and the rim at 5), four through, y 0 to 4:
    V = 100 pi - 4 pi - 4 pi 0.49 4. Area: the cylinder's 90 pi, the pocket's wall 4 pi and
    floor less its mouth (net +4 pi), each bore's wall 2 pi 0.7 4 less its two ends 2 pi 0.49.
    The y moment is 100 pi 2 less the pocket's pi 4 * 0.5 and the bores' 4 pi 0.49 4 * 2.
    Planes: the end at y = 4, the annulus and the floor (3); cylinders: the rim, the pocket's
    wall and four bores (6); genus 4.
    """
    r = 0.7
    pocket = math.pi * 4
    bores = 4 * math.pi * r * r * 4
    volume = 100 * math.pi - pocket - bores
    surface = 90 * math.pi + 4 * math.pi + 4 * (2 * math.pi * r * 4 - 2 * math.pi * r * r)
    moment = 100 * math.pi * 2 - pocket * 0.5 - bores * 2
    return measures(
        volume,
        surface,
        (0, moment / volume, 0),
        ((-5, 0, -5), (5, 4, 5)),
        9,
        [["cylinder", 6], ["plane", 3]],
        genus=4,
    )


def cut_from_a_higher_face() -> dict[str, object]:
    """`impeller`'s shape: a disc, a hub, a ring clear of it, a bore, a pocket from the ring's top.

    A disc of r = 6 on `XY` from z -1 to 1; a hub of r = 2 from z -1 to 3 (its top
    2 above the disc's); a ring of r 5 to 6 from z = 3 to 3.5, which touches
    neither, a second shell. `faces(">Z")` is the ring's top at z = 3.5 and `workplane()`
    its plane with the origin on the axis: `hole(1)` bores r = 1/2 from there down through
    hub and disc (z -1 to 3), and a second `faces(">Z").workplane().circle(3).cutBlind(-1)`
    cuts r < 3 from z = 3.5 to 2.5. That clears the hub's top 0.5 (the circle is wider than
    the hub and the ring is outside it) and nothing else. V = 72 pi + 8 pi + 5.5 pi - pi
    (bore) - 1.875 pi (the slab, pi (4 - 1/4) 0.5), at z 0, 2, 3.25, 1 and 2.75.
    A: the disc's bottom less the bore, lateral and top less the hub's foot; the hub's wall
    from z = 1 to 2.5 and its floor at 2.5; the bore's wall from -1 to 2.5; the ring's
    2 planes and 2 walls.
    Faces, as arris builds them: arris keeps the hub's foot (z = -1, r 0.5 to 2) and the
    disc's bottom as two planes, where Open CASCADE's `clean` merges them. Planes: bottom,
    foot, top, floor, ring top and bottom (6); cylinders: disc, hub, bore, ring outer and
    inner (5); two shells, genus 2.
    """
    pieces = [
        (72 * math.pi, 0.0),
        (8 * math.pi, 2.0),
        (5.5 * math.pi, 3.25),
        (-math.pi, 1.0),
        (-1.875 * math.pi, 2.75),
    ]
    volume = sum(v for v, _ in pieces)
    surface = math.pi * (35.75 + 24 + 32 + 6 + 3.75 + 3.5 + 33)
    return measures(
        volume,
        surface,
        (0, 0, sum(v * z for v, z in pieces) / volume),
        ((-6, -6, -1), (6, 6, 3.5)),
        11,
        [["cylinder", 5], ["plane", 6]],
        shells=2,
        genus=2,
    )


def corpus_program() -> str:
    """The committed fixture's `program.py`: the text BenchCAD wrote."""
    return (fixture_cases.ROOT / "cq" / CORPUS / "program.py").read_text(encoding="utf-8")


def gear_with_hubs() -> dict[str, object]:
    """BenchCAD's `spur_gear_017922_s20260505` as written: a pocket filled, a groove, a bore.

    The outline is a polygon of N vertices on `YZ` (local x world y, local y world z)
    extruded 12.53 along +x, shoelace area A, perimeter P, centroid c. A pocket of r = 7.35
    and 9.77 deep from `>X`, then a united cylinder of r = 9.35 and the whole 12.53 (x 0 to
    12.53) fills it again: that cylinder lies inside the outline (checked below: the nearest
    edge is farther from the axis than 9.35) and holds the pocket, so the part is the prism
    again. The second pocket, r = 6.43 and 9.19 deep (x 3.34 to 12.53), is only partly filled by its
    cylinder of r = 5.43: a groove of r 5.43 to 6.43 is left, V_G = pi (6.43^2 - 5.43^2) 9.19.
    The bore of r = 3.09 (`hole(6.18)` from `>X` through, inside the island of 5.43) takes
    V_B = pi 3.09^2 12.53. V = 12.53 A - V_G - V_B; the groove adds its walls
    2 pi (6.43 + 5.43) 9.19 (its mouth and floor cancel) and the bore its wall 2 pi r 12.53 less
    its two ends 2 pi r^2: A_total = 2 A + 12.53 P + those. The moments in x are the prism's
    12.53 / 2 less the groove's at 12.53 - 9.19 / 2 and the bore's at 12.53 / 2; y and z are the
    prism's, the groove and the bore being on the axis.
    Faces, as arris builds them: the N sides, the groove's two walls and the bore's wall (three
    cylinders), the groove's floor, and the end faces: arris keeps the unions' coplanar
    splits, so x = 0 is three planes (the circles of 9.35 and 5.43 cut it) and x = 12.53 four
    (the circle of 9.35, and the island's top), where Open CASCADE's `clean` merges them:
    N + 8 planes and 3 cylinders; genus 1 (the bore).
    """
    pts = polyline(corpus_program())
    assert pts[0] != pts[-1]
    n = len(pts)
    edges = [(pts[i], pts[(i + 1) % n]) for i in range(n)]
    cross = [a[0] * b[1] - b[0] * a[1] for a, b in edges]
    area = abs(sum(cross)) / 2
    sign = 1.0 if sum(cross) > 0 else -1.0
    cy = sign * sum((a[0] + b[0]) * c for (a, b), c in zip(edges, cross, strict=True)) / (6 * area)
    cz = sign * sum((a[1] + b[1]) * c for (a, b), c in zip(edges, cross, strict=True)) / (6 * area)
    perimeter = sum(math.dist(a, b) for a, b in edges)
    # Each united cylinder, and the pockets, lie inside the outline.
    assert min(distance_to_segment(a, b) for a, b in edges) > 9.35
    assert all(abs(c) > 1e-6 for c in turns(pts))
    thick, r_bore = 12.53, 6.18 / 2
    r_out, r_in, depth = 6.43, 5.43, 9.19
    groove = math.pi * (r_out**2 - r_in**2) * depth
    bore = math.pi * r_bore**2 * thick
    volume = area * thick - groove - bore
    surface = (
        2 * area
        + thick * perimeter
        + 2 * math.pi * (r_out + r_in) * depth
        + 2 * math.pi * r_bore * thick
        - 2 * math.pi * r_bore**2
    )
    moment_x = area * thick * thick / 2 - groove * (thick - depth / 2) - bore * thick / 2
    ys = [p[0] for p in pts]
    zs = [p[1] for p in pts]
    return measures(
        volume,
        surface,
        (moment_x / volume, area * thick * cy / volume, area * thick * cz / volume),
        ((0, min(ys), min(zs)), (thick, max(ys), max(zs))),
        n + 11,
        [["cylinder", 3], ["plane", n + 8]],
        genus=1,
    )


TOP = '.faces(">Z").workplane()'
PROGRAMS: dict[str, tuple[str, dict[str, object], str]] = {}


def add(slug: str, program: str, expected: dict[str, object], doc: str | None) -> None:
    PROGRAMS[slug] = (program, expected, doc or "")


add(
    "ok-ctx-polar-array-in-a-compound",
    wrap(f"{PAIR}{TOP}.polarArray(3, 0, 360, 4).hole(1)"),
    in_a_compound(),
    '`faces(">Z").workplane().polarArray(3, 0, 360, 4).hole(1)` on the pair of boxes. '
    + (in_a_compound.__doc__ or ""),
)
add(
    "ok-ctx-rarray-in-a-compound",
    wrap(f"{PAIR}{TOP}.rarray(4, 3, 2, 2).hole(1)"),
    in_a_compound(),
    '`faces(">Z").workplane().rarray(4, 3, 2, 2).hole(1)` on the pair of boxes. '
    + (in_a_compound.__doc__ or ""),
)
add(
    "ok-ctx-hole-after-a-blind-cut-biting",
    wrap(
        'cq.Workplane("XY").box(10, 8, 4)'
        '.faces(">Z").workplane().circle(2).cutBlind(-1)'
        '.faces(">Z").workplane().polarArray(2.5, 0, 360, 4).hole(2)'
    ),
    pocket_then_bores(),
    pocket_then_bores.__doc__,
)
add(
    "ok-ctx-hole-after-a-blind-cut-revolved",
    wrap(
        'cq.Workplane("XY").moveTo(0, 0).lineTo(5, 0).lineTo(5, 4).lineTo(0, 4).close()'
        ".revolve(360, (0, 0, 0), (0, 1, 0))"
        '.faces("<Y").workplane().circle(2).cutBlind(-1)'
        '.faces("<Y").workplane().polarArray(3, 0, 360, 4).hole(1.4)'
    ),
    pocket_then_bores_revolved(),
    pocket_then_bores_revolved.__doc__,
)
add(
    "ok-ctx-cut-blind-from-a-higher-face",
    wrap(
        'cq.Workplane("XY").cylinder(2, 6)'
        '.union(cq.Workplane("XY").transformed(offset=cq.Vector(0, 0, 1)).cylinder(4, 2))'
        '.union(cq.Workplane("XY").transformed(offset=cq.Vector(0, 0, 3))'
        ".circle(6).circle(5).extrude(0.5))"
        '.faces(">Z").workplane().hole(1)'
        '.faces(">Z").workplane().circle(3).cutBlind(-1)'
    ),
    cut_from_a_higher_face(),
    cut_from_a_higher_face.__doc__,
)


def committed() -> dict[str, fixture_cases.Case]:
    return {case.slug: case for case in fixture_cases.load("cq") if case.slug in PROGRAMS}


def recorded(slug: str) -> OracleReport:
    path = fixture_cases.ROOT / "cq" / slug / "oracle.json"
    return OracleReport.model_validate_json(path.read_text())


def all_programs() -> dict[str, tuple[str, dict[str, object], str]]:
    """`PROGRAMS` and the corpus gear, which needs its committed text to be computed."""
    found = dict(PROGRAMS)
    found[CORPUS] = (corpus_program(), gear_with_hubs(), gear_with_hubs.__doc__ or "")
    return found


def test_every_context_fixture_is_the_closed_form() -> None:
    """The committed files are exactly what `all_programs` computes."""
    found = {c.slug: c for c in fixture_cases.load("cq") if c.slug in all_programs()}
    assert sorted(found) == sorted(all_programs())
    for slug, (program, expected, _) in all_programs().items():
        assert found[slug].program == program, slug
        got = found[slug].expected["measures"]
        assert json.loads(json.dumps(got)) == json.loads(json.dumps(expected)), slug


@pytest.mark.parametrize("slug", [*sorted(PROGRAMS), CORPUS])
def test_context_fixtures_agree_with_the_recorded_oracle(slug: str) -> None:
    case = {c.slug: c for c in fixture_cases.load("cq")}[slug]
    assert compare(fixture_cases.run(case), recorded(slug)).outcome is FidelityOutcome.AGREE


def test_the_oracles_reports_hold_the_closed_forms() -> None:
    """Open CASCADE builds the closed form's part: its volume, area and solid count."""
    for slug, (_, expected, _) in all_programs().items():
        report = recorded(slug)
        assert report.measures is not None
        assert report.measures.solids == expected["shells"], slug
        assert fixture_cases.close(report.measures.volume, float(str(expected["volume"]))), slug
        assert fixture_cases.close(report.measures.area, float(str(expected["area"]))), slug


def test_the_corpus_program_is_the_corpuss() -> None:
    """The fixture's `program.py` is a program of the committed BenchCAD rows."""
    data = gzip.decompress(
        (fixture_cases.ROOT / "c2" / "benchcad" / "programs.jsonl.gz").read_bytes()
    )
    shas = {json.loads(line)["program_sha256"] for line in data.splitlines()}
    assert hashlib.sha256(corpus_program().encode()).hexdigest() in shas
    assert (
        "spur_gear_017922_s20260505"
        in (fixture_cases.ROOT / "cq" / CORPUS / "expected.json").read_text()
    )


def test_a_bore_clear_of_a_pocket_takes_only_its_cylinder() -> None:
    """A bore clear of the pocket takes exactly its cylinder from the box."""
    clear = ag.run(
        wrap(
            'cq.Workplane("XY").box(10, 8, 4).faces(">Z").workplane().circle(1).cutBlind(-1)'
            '.faces(">Z").workplane().polarArray(3, 0, 360, 4).hole(1)'
        ),
        dialect="cq",
    )
    assert clear.measures is not None
    assert fixture_cases.close(clear.measures.volume, BOX_VOLUME - math.pi - 4 * math.pi * 0.25 * 4)

"""`tools/cq_closed_forms.py`: the closed forms behind the C2 `occt_wrong` verdicts
(plans/lift-cylinder step 5).

The tool's formulas are integrals over the part's cross-sections and surface patches; arris
builds the same parts with its own boolean. Two computations that share nothing agree
inside ADR-0005's tolerance on constructed programs (so a wrong formula, or an arris error,
shows), and the committed verdicts are each a verdict `compare` accepts: their evidence is a
closed form, or a regression fixture that exists.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

import arris_gym as ag
import cq_closed_forms as cf
import cq_corpus
from arris_gym.fidelity import (
    AREA_REL,
    BOUNDS_ABS,
    CENTROID_DIAG,
    VOLUME_REL,
    ClosedForm,
    DisagreementClass,
    RegressionFixture,
    Verdict,
)
from arris_gym.sandbox.outcome import ArrisRefusal

C2 = Path(__file__).parent / "fixtures" / "c2"
REGRESSION = Path(__file__).parent / "fixtures" / "regression"


def _agrees(result: ag.ExecResult, closed: dict[str, object]) -> list[str]:
    """What differs, in ADR-0005's constants, between arris's measures and a closed form."""
    assert result.measures is not None, result.message
    m = result.measures
    form = ClosedForm.model_validate(closed)
    problems = []
    if abs(m.volume - form.volume) > VOLUME_REL * max(m.volume, form.volume):
        problems.append(f"volume {m.volume} against {form.volume}")
    if abs(m.area - form.area) > AREA_REL * max(m.area, form.area):
        problems.append(f"area {m.area} against {form.area}")
    diag = math.dist(m.bounds[0], m.bounds[1])
    if math.dist(m.centroid, form.centroid) > CENTROID_DIAG * diag:
        problems.append(f"centroid {m.centroid} against {form.centroid}")
    gap = max(
        abs(a - b)
        for lo, hi in zip(m.bounds, form.bounds, strict=True)
        for a, b in zip(lo, hi, strict=True)
    )
    if gap > BOUNDS_ABS:
        problems.append(f"bounds {m.bounds} against {form.bounds}")
    return problems


def test_the_quadrature_is_exact_on_endpoint_roots() -> None:
    # A disc's area as the integral of its chord, and a hemisphere's volume: square-root ends.
    disc = cf.tanh_sinh(lambda x: 2 * math.sqrt(max(1.0 - x * x, 0.0)), -1.0, 1.0)
    assert disc == pytest.approx(math.pi, rel=1e-13)
    ball = cf.tanh_sinh(lambda x: math.pi * (1.0 - x * x), -1.0, 1.0)
    assert ball == pytest.approx(4 * math.pi / 3, rel=1e-13)
    # An empty interval is zero, never an error; a Gauss rule is exact on a polynomial.
    assert cf.tanh_sinh(lambda x: 1.0, 2.0, 2.0) == 0.0
    assert cf.gauss(lambda x: x**5 - x + 1, 0.0, 2.0) == pytest.approx(64 / 6 - 2 + 2, rel=1e-14)


TEE = """import cadquery as cq

result = (
    cq.Workplane("{plane}")
    .union(
        cq.Workplane("{plane}")
            .cylinder({h}, {R})
    )
    .union(
        cq.Workplane("{plane}")
            .transformed(offset=cq.Vector(0.0, {hb2}, 0.0), rotate=cq.Vector(-90.0, 0.0, 0.0))
            .cylinder({hb}, {r})
    )
    .cut(
        cq.Workplane("{plane}")
            .transformed(offset=cq.Vector(0.0, {hd2}, 0.0), rotate=cq.Vector(-90.0, 0.0, 0.0))
            .cylinder({hd}, {s})
    )
    .cut(
        cq.Workplane("{plane}")
            .cylinder({hc}, {q})
    )
)
show_object(result)
"""


@pytest.mark.parametrize("plane", ["XY", "XZ", "YZ"])
@pytest.mark.parametrize(
    ("R", "r", "s", "q"),
    [
        (26.75, 13.35, 9.27, 22.67),
        (16.915, 16.7, 13.85, 14.065),
    ],  # the second: branch near the main
)
def test_a_tee_is_what_arris_builds(plane: str, R: float, r: float, s: float, q: float) -> None:
    hb, hd = 46.63, 47.63
    text = TEE.format(
        plane=plane, h=100.0, R=R, hb=hb, hb2=hb / 2, r=r, hd=hd, hd2=hd / 2, s=s, hc=102.0, q=q
    )
    closed = cf.tee_closed_form(text)
    assert _agrees(ag.run(text, dialect="cq"), closed) == []


def test_a_tee_whose_ordering_the_closed_form_does_not_hold_is_refused() -> None:
    text = TEE.format(
        plane="XY", h=100.0, R=10.0, hb=46.63, hb2=23.315, r=12.0, hd=47.63, hd2=23.815,
        s=9.0, hc=102.0, q=8.0,
    )  # fmt: skip
    with pytest.raises(ValueError, match="ordering"):
        cf.tee_closed_form(text)


FLANGED_TEE = """import cadquery as cq

result = (
    cq.Workplane("{plane}")
    .union(
        cq.Workplane("{plane}")
            .cylinder({h}, {R})
    )
    .union(
        cq.Workplane("{plane}")
            .transformed(offset=cq.Vector(0.0, 0.0, -{h2}), rotate=cq.Vector(0.0, 0.0, 0.0))
            .cylinder({t}, {Rf})
    )
    .union(
        cq.Workplane("{plane}")
            .transformed(offset=cq.Vector(0.0, 0.0, {h2}), rotate=cq.Vector(0.0, 0.0, 0.0))
            .cylinder({t}, {Rf})
    )
    .faces(">{axis}").workplane()
    .polarArray({rp}, 0, 360, {n})
    .hole({d})
    .faces("<{axis}").workplane()
    .polarArray({rp}, 0, 360, {n})
    .hole({d})
    .union(
        cq.Workplane("{plane}")
            .transformed(offset=cq.Vector(0.0, {hb2}, 0.0), rotate=cq.Vector(-90.0, 0.0, 0.0))
            .cylinder({hb}, {r})
    )
    .union(
        cq.Workplane("{plane}")
            .transformed(offset=cq.Vector(0.0, {bf}, 0.0), rotate=cq.Vector(-90.0, 0.0, 0.0))
            .cylinder({t2}, {rf2})
    )
    .cut(
        cq.Workplane("{plane}")
            .transformed(offset=cq.Vector(0.0, {hd2}, 0.0), rotate=cq.Vector(-90.0, 0.0, 0.0))
            .cylinder({hd}, {s})
    )
    .cut(
        cq.Workplane("{plane}")
            .cylinder({hc}, {q})
    )
)

# Export
show_object(result)"""

# BenchCAD's flanged tees as written, by the corpus's literals: t_pipe_fitting_000436 (the
# branch flange clear of M), _017687 (the branch inside M's wall, its flange half in it, the
# branch bore ending in the wall) and _001101 (a branch flange wider than M, three bolts).
FLANGED_TEES = {
    "000436": dict(
        plane="XZ", axis="Y", h="336.07", R="62.91", h2="168.035", t="9.91", Rf="102.85",
        rp="75.3", n="6", d="8.81", hb2="42.325", hb="84.65", r="13.35", bf="78.705",
        t2="11.89", rf2="21.35", hd2="42.825", hd="85.65", s="6.72", hc="356.89", q="56.28",
    ),
    "017687": dict(
        plane="XZ", axis="Y", h="210.41", R="33.92", h2="105.205", t="7.16", Rf="65.7",
        rp="49.15", n="4", d="7.43", hb2="15.565", hb="31.13", r="10.65", bf="26.81",
        t2="8.64", rf2="17.05", hd2="16.065", hd="32.13", s="5.85", hc="225.73", q="29.12",
    ),
    "001101": dict(
        plane="XY", axis="Z", h="171.63", R="27.05", h2="85.815", t="5.29", Rf="54.25",
        rp="41.15", n="3", d="7.18", hb2="40.685", hb="81.37", r="21.1", bf="78.23",
        t2="6.28", rf2="33.75", hd2="41.185", hd="82.37", s="17.59", hc="183.21", q="23.54",
    ),
}  # fmt: skip


@pytest.mark.parametrize(
    ("stem", "plane", "holes"),
    [
        ("000436", "XZ", 6),
        ("017687", "XZ", 4),
        ("001101", "XY", 3),  # XY's two end frames give one set of three
        ("001101", "YZ", 6),  # YZ's are mirrored: an odd count's second set falls between
        ("000436", "YZ", 6),
    ],
)
def test_a_flanged_tee_is_what_arris_builds(stem: str, plane: str, holes: int) -> None:
    axis = {"XY": "Z", "XZ": "Y", "YZ": "X"}[plane]
    text = FLANGED_TEE.format(**{**FLANGED_TEES[stem], "plane": plane, "axis": axis})
    assert len(cf._flanged_tee(text).centres) == holes
    closed = cf.tee_closed_form(text)
    assert _agrees(ag.run(text, dialect="cq"), closed) == []


def test_a_corpus_flanged_tee_is_occt_wrong_by_its_closed_form() -> None:
    """t_pipe_fitting_000436 as written: arris is within ADR-0005's constants of the closed
    form, the recorded oracle report is not, and the rule alone leaves the row unclassified."""
    import gzip
    import hashlib

    from arris_gym.fidelity import FidelityOutcome, OracleReport, compare

    stem = "t_pipe_fitting_000436_s20260505"
    text = FLANGED_TEE.format(**FLANGED_TEES["000436"])
    rows = gzip.decompress((C2 / "benchcad" / "oracle.jsonl.gz").read_bytes()).splitlines()
    row = next(json.loads(line) for line in rows if json.loads(line)["stem"] == stem)
    report = OracleReport.model_validate(row["report"])
    assert hashlib.sha256(text.encode()).hexdigest() == report.program_sha256
    result = ag.run(text, dialect="cq")
    assert compare(result, report).outcome is FidelityOutcome.UNCLASSIFIED
    verdict = Verdict.model_validate(
        {"disagreement": "occt_wrong", "evidence": cf.tee_closed_form(text)}
    )
    row_classed = compare(result, report, verdict)
    assert row_classed.disagreement is DisagreementClass.OCCT_WRONG


def test_a_flanged_tee_this_tool_does_not_read_is_refused() -> None:
    overlap = FLANGED_TEE.format(**{**FLANGED_TEES["000436"], "n": "60"})
    with pytest.raises(ValueError, match="overlap"):
        cf.tee_closed_form(overlap)
    into_main = FLANGED_TEE.format(**{**FLANGED_TEES["000436"], "rp": "64.0"})
    with pytest.raises(ValueError, match="ordering"):
        cf.tee_closed_form(into_main)


# BenchCAD's bellows_011847_s20260505 as written: a bore widening the inner wall, and holes
# whose circle runs past the rim (19.925 + 1.18 > 21.09), so each takes a notch out of it.
BELLOWS = """import cadquery as cq

result = (
    cq.Workplane("XY")
    .polyline([(5.135, 0.0), (18.5, 0.0), (21.09, 0.0), (21.09, 3.18), (18.5, 3.18), (8.6, 10.25), (18.5, 17.32), (8.6, 24.39), (18.5, 31.46), (8.6, 38.53), (18.5, 45.6), (8.6, 52.67), (18.5, 59.74), (21.09, 62.92), (18.5, 62.92), (5.135, 62.92), (5.135, 0.0)])
    .close()
    .revolve(360, (0, 0, 0), (0, 1, 0))
    .faces(">Y").workplane()
    .hole({bore})
    .faces(">Y").workplane()
    .polarArray({rp}, 0, 360, 6)
    .circle(1.18)
    .cutBlind(-3.18)
    .faces("<Y").workplane()
    .polarArray({rp}, 0, 360, 6)
    .circle(1.18)
    .cutBlind(-3.18)
)

# Export
show_object(result)"""  # noqa: E501


def test_the_bellows_closed_form_is_the_cut_blind_fixtures() -> None:
    """The tool's bellows is `ok-cut-blind-corpus-bellows`'s closed form, worked out apart
    (`test_cq_cut_blind.bellows`: the sliver by columns of a disc, not by radius)."""
    from test_cq_cut_blind import bellows, corpus_program

    want = bellows()
    got = cf.bellows_closed_form(corpus_program("ok-cut-blind-corpus-bellows"))
    for key in ("volume", "area"):
        assert float(str(got[key])) == pytest.approx(float(str(want[key])), rel=1e-13), key
    assert got["centroid"] == pytest.approx(want["centroid"], rel=1e-13)
    bounds = want["bounds"]
    assert isinstance(bounds, (list, tuple))
    assert got["bounds"] == [list(corner) for corner in bounds]


@pytest.mark.parametrize(("bore", "rp"), [("14.14", "19.925"), ("10.5", "19.8")])
def test_a_bellows_is_what_arris_builds(bore: str, rp: str) -> None:
    """As written (holes past the rim) and with the holes inside it, a narrower bore."""
    text = BELLOWS.format(bore=bore, rp=rp)
    assert _agrees(ag.run(text, dialect="cq"), cf.bellows_closed_form(text)) == []


def test_a_corpus_bellows_is_occt_wrong_by_its_closed_form() -> None:
    """bellows_011847 as written: arris is within ADR-0005's constants of the closed form, the
    recorded oracle report is not, and the rule alone leaves the row unclassified."""
    import gzip
    import hashlib

    from arris_gym.fidelity import FidelityOutcome, OracleReport, compare

    stem = "bellows_011847_s20260505"
    text = BELLOWS.format(bore="14.14", rp="19.925")
    rows = gzip.decompress((C2 / "benchcad" / "oracle.jsonl.gz").read_bytes()).splitlines()
    row = next(json.loads(line) for line in rows if json.loads(line)["stem"] == stem)
    report = OracleReport.model_validate(row["report"])
    assert hashlib.sha256(text.encode()).hexdigest() == report.program_sha256
    result = ag.run(text, dialect="cq")
    assert compare(result, report).outcome is FidelityOutcome.UNCLASSIFIED
    verdict = Verdict.model_validate(
        {"disagreement": "occt_wrong", "evidence": cf.bellows_closed_form(text)}
    )
    assert compare(result, report, verdict).disagreement is DisagreementClass.OCCT_WRONG


@pytest.mark.parametrize(
    ("bore", "rp", "match"),
    [
        ("14.14", "19.5", "holes are not where"),  # across the end faces' split at 18.5
        ("18.0", "19.925", "bore"),  # wider than the convolutions' 8.6
        ("14.14", "19.91", "holes are not where"),  # tangent to the rim
    ],
)
def test_a_bellows_this_tool_does_not_read_is_refused(bore: str, rp: str, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        cf.bellows_closed_form(BELLOWS.format(bore=bore, rp=rp))


HOOK = """import cadquery as cq

result = (
    cq.Workplane("XY")
    .transformed(offset=cq.Vector({R}, 0.0, {zc}), rotate=cq.Vector(0, 0, 0))
    .cylinder({h}, {r})
    .union(
        cq.Workplane("XY")
            .transformed(offset=cq.Vector(0, 0, {z0}), rotate=cq.Vector(0, 0, 0))
            .moveTo({R}, 0.0)
            .circle({r})
            .revolve(180, (0, 0, 0), (0, -1, 0))
    ){more}
)
show_object(result)
"""
SECOND = """
    .union(
        cq.Workplane("XY")
            .transformed(offset=cq.Vector({mR}, 0.0, {zc}), rotate=cq.Vector(0, 0, 0))
            .cylinder({h}, {r})
    )"""
BOX = """
    .union(
        cq.Workplane("XY")
            .transformed(offset=cq.Vector(0, 0, {bz2}), rotate=cq.Vector(0, 0, 0))
            .box({bx}, {by}, {bz})
    )"""


@pytest.mark.parametrize(
    "shape", ["hook", "hook-and-box", "bolt", "bolt-and-box", "bolt-box-proud"]
)
def test_a_hook_is_what_arris_builds(shape: str) -> None:
    big_r, r, z0 = 27.32, 4.97, 59.62
    top = z0 + r / 2  # the cylinders run r/2 past the torus's end disc
    bottom = -3.97
    if shape.endswith("proud"):
        bottom = -3.97 - 0.00025  # a cylinder's rounded height: its foot just under the box's
    height = top - bottom
    parts = {"R": big_r, "r": r, "z0": z0, "zc": (top + bottom) / 2, "h": height}
    more = ""
    if shape.startswith("bolt"):
        more += SECOND.format(mR=-big_r, **{k: parts[k] for k in ("zc", "h", "r")})
    if shape.endswith(("box", "proud")):
        more += BOX.format(bx=84.46, by=21.86, bz=3.97, bz2=-1.985)
    text = HOOK.format(more=more, **parts)
    closed = cf.hook_closed_form(text)
    assert _agrees(ag.run(text, dialect="cq"), closed) == []


NUT_POLYGON = """
    .union(
        cq.Workplane("XY")
            .transformed(offset=cq.Vector({x}, 0.0, {z}), rotate=cq.Vector(0, 0, 0))
            .polygon(6, 18.0)
            .extrude({e}, both=True)
    )"""
# The corpus's nut as written: the lone `moveTo` point is dropped, so a pentagon (one edge
# 4.5 from the axis, inside a cylinder of radius 4.97: a proud foot meets its segment).
NUT_POLYLINE = """
    .union(
        cq.Workplane("XY")
            .transformed(offset=cq.Vector({x}, 0.0, {z}), rotate=cq.Vector(0, 0, 0))
            .moveTo(7.7942, 4.5)
            .polyline([[0.0, 9.0], [-7.7942, 4.5], [-7.7942, -4.5], [-0.0, -9.0], [7.7942, -4.5]])
            .close()
            .extrude({e}, both=True)
    )"""


def _hook_with_nuts(cylinders: int, nut: str, proud: bool, z: float = -5.97) -> str:
    """A hook (one or two cylinders) on a box, a nut under each cylinder."""
    big_r, r, z0 = 27.32, 4.97, 59.62
    top = z0 + r / 2
    bottom = -3.97 - (0.00025 if proud else 0.0)
    parts = {"R": big_r, "r": r, "z0": z0, "zc": (top + bottom) / 2, "h": top - bottom}
    more = ""
    if cylinders == 2:
        more += SECOND.format(mR=-big_r, **{k: parts[k] for k in ("zc", "h", "r")})
    more += BOX.format(bx=84.46, by=21.86, bz=3.97, bz2=-1.985)
    template = NUT_POLYGON if nut == "polygon" else NUT_POLYLINE
    for x in [big_r, -big_r][:cylinders]:
        more += template.format(x=x, z=z, e=2.4)
    return HOOK.format(more=more, **parts)


@pytest.mark.parametrize("cylinders", [1, 2])
@pytest.mark.parametrize("nut", ["polygon", "polyline"])
@pytest.mark.parametrize("proud", [False, True])
def test_a_hook_on_nuts_is_what_arris_builds(cylinders: int, nut: str, proud: bool) -> None:
    text = _hook_with_nuts(cylinders, nut, proud)
    closed = cf.hook_closed_form(text)
    assert _agrees(ag.run(text, dialect="cq"), closed) == []


def test_the_pentagon_nut_moves_the_centroid_off_the_hook_plane() -> None:
    # The pentagon is not symmetric in y, so the closed form's y moment is not zero.
    closed = cf.hook_closed_form(_hook_with_nuts(1, "polyline", proud=False))
    assert isinstance(closed["centroid"], list)
    assert closed["centroid"][1] < 0


@pytest.mark.parametrize(
    ("text", "match"),
    [
        (_hook_with_nuts(1, "polygon", False, z=-1.0), "top is not inside the box"),
        (_hook_with_nuts(1, "polygon", False).replace("0.0, -5.97", "6.0, -5.97"),
         "outside the box's footprint"),
        (_hook_with_nuts(1, "polygon", False).replace("show_object", "x = cq.Workplane().union(\n"
         ")\nshow_object"), "a solid this tool does not read"),
    ],
)  # fmt: skip
def test_a_hook_nut_outside_the_shape_is_refused(text: str, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        cf.hook_closed_form(text)


def test_the_crossing_cylinders_are_what_arris_builds() -> None:
    # CAD-Recode's 550 on its own: the program's text is not committed (licence), so the same
    # two cylinders are written on the XY plane's axes. A along y at x = -42, B along x.
    text = (
        'import cadquery as cq\nw0 = cq.Workplane("ZX", origin=(0, -37, 0))\n'
        'w1 = cq.Workplane("YZ", origin=(-35, 0, 0))\n'
        "r = w0.workplane(offset=75/2).moveTo(0, -42).cylinder(75, 8).union("
        "w1.workplane(offset=85/2).moveTo(-31, 0).cylinder(85, 5))\n"
    )
    sha = next(iter(cf.CROSSING))
    assert ag.run(text, dialect="cq").program_sha256 != sha  # a rewrite, not the corpus's text
    assert _agrees(ag.run(text, dialect="cq"), cf.crossing_closed_form(sha)) == []


def test_a_part_of_boxes_and_cylinders_meets_its_textbook_figures() -> None:
    # A 4 x 6 x 8 box less a through bore of radius 1 off its axis: V = 192 - 8 pi, the
    # bore's side added and its two discs taken from the faces, the centroid opposite it.
    box = cf.Cuboid((-2.0, -3.0, -4.0), (2.0, 3.0, 4.0))
    bore = cf.Rod(2, (0.5, 0.0, 0.0), 1.0, -10.0, 10.0)
    volume, area, centroid, bounds = cf.part_measures([("+", box), ("-", bore)])
    assert volume == pytest.approx(192 - 8 * math.pi, rel=1e-14)
    assert area == pytest.approx(208 - 2 * math.pi + 16 * math.pi, rel=1e-14)
    assert centroid[0] == pytest.approx(-0.5 * 8 * math.pi / (192 - 8 * math.pi), rel=1e-13)
    assert bounds == ((-2.0, -3.0, -4.0), (2.0, 3.0, 4.0))
    # Two crossing cylinders of one radius r and length L: their union is twice a cylinder
    # less the Steinmetz solid (16 r^3 / 3), each side losing 8 r^2 inside the other.
    r, half = 1.5, 4.0
    x = cf.Rod(0, (0.0, 0.0, 0.0), r, -half, half)
    y = cf.Rod(1, (0.0, 0.0, 0.0), r, -half, half)
    volume, area, _, _ = cf.part_measures([("+", x), ("+", y)])
    assert volume == pytest.approx(2 * math.pi * r * r * 2 * half - 16 * r**3 / 3, rel=1e-14)
    assert area == pytest.approx(
        2 * (2 * math.pi * r * 2 * half + 2 * math.pi * r * r) - 16 * r * r
    )
    # The CAD-Recode crossing, worked out apart (`crossing_measures`), is the same figures.
    p = next(iter(cf.CROSSING.values()))
    a = cf.Rod(1, (p["xa"], 0.0, 0.0), p["a"], p["ya0"], p["ya1"])
    b = cf.Rod(0, (0.0, p["yb"], 0.0), p["b"], p["xb0"], p["xb1"])
    got = cf.part_measures([("+", a), ("+", b)])
    want = cf.crossing_measures(p)
    assert got[0] == pytest.approx(want[0], rel=1e-14)
    assert got[1] == pytest.approx(want[1], rel=1e-14)
    assert math.dist(got[2], want[2]) < 1e-12
    assert got[3] == want[3]


MANIFOLD = """import cadquery as cq

result = (
    cq.Workplane("{plane}")
    .box(83.17, 41.3, 31.06)
    .faces(">{f1}").workplane()
    .pushPoints([(-24.95, 0.0), (0.0, 0.0), (24.95, 0.0)])
    .hole(9.4)
    .faces(">{f2}")
    .faces(">{f2}").workplane()
    .pushPoints([(-6.7, 0.0), (0.002, 0.0), (6.71, 0.0)])
    .cboreHole(4.1, 7.6, 3.85)
    .faces(">{f3}")
    .faces(">{f3}").workplane()
    .pushPoints([(0.0, 0.0)])
    .hole(9.4)
)
"""

ROD = """import cadquery as cq

result = (
    cq.Workplane("{plane}")
    .cylinder(10.4, 16.2)
    .union(
        cq.Workplane("{plane}")
            .transformed(offset=cq.Vector(41.3, 0, 0), rotate=cq.Vector(0, 0, 0))
            .box(52.9, 10.4, 9.7)
    )
    .union(
        cq.Workplane("{plane}")
            .transformed(offset=cq.Vector(74.6, 0, {lift}), rotate=cq.Vector(0, 0, 0))
            .cylinder(10.4, 9.1)
    )
    .faces(">{f1}").workplane()
    .hole(19.6)
    .cut(
        cq.Workplane("{plane}")
            .transformed(offset=cq.Vector(74.6, 0, {lift}), rotate=cq.Vector(0, 0, 0))
            .cylinder(15.6, 4.9)
    )
    .union(
        cq.Workplane("{plane}")
            .transformed(offset=cq.Vector(41.3, 0, 6.1), rotate=cq.Vector(0, 0, 0))
            .box(42.32, 10.4, 3.3)
    )
    .union(
        cq.Workplane("{plane}")
            .transformed(offset=cq.Vector(41.3, 0, -6.1), rotate=cq.Vector(0, 0, 0))
            .box(42.32, 10.4, 3.3)
    )
    .faces(">{f2}")
    .faces(">{f2}").workplane()
    .pushPoints([(3.7, 0.0)])
    .hole(2.4)
)
"""


@pytest.mark.parametrize(("plane", "faces"), [("XY", "ZYX"), ("XZ", "YZX"), ("YZ", "XZY")])
def test_a_manifold_block_is_what_arris_builds(plane: str, faces: str) -> None:
    # The corpus's three bore directions on each plane: a row of holes, counterbores across
    # them from a face whose origin is the first face's projected (so on its edge), and a
    # hole of the first holes' size along the third axis, through the counterbores.
    text = MANIFOLD.format(plane=plane, f1=faces[0], f2=faces[1], f3=faces[2])
    assert _agrees(ag.run(text, dialect="cq"), cf.part_closed_form(text)) == []


@pytest.mark.parametrize(("plane", "faces"), [("XY", "ZY"), ("XZ", "YZ")])
@pytest.mark.parametrize("lift", ["0.0", "2.7"])
def test_a_connecting_rod_is_what_arris_builds(plane: str, faces: str, lift: str) -> None:
    # Two rings joined by a web and two rails, the small ring lifted along its axis or not,
    # and the cross hole on the rails' top face at the first hole's projected origin.
    text = ROD.format(plane=plane, f1=faces[0], f2=faces[1], lift=lift)
    assert _agrees(ag.run(text, dialect="cq"), cf.part_closed_form(text)) == []


@pytest.mark.parametrize(
    ("change", "match"),
    [
        ((".hole(9.4)\n)", ".hole(9.4)\n    .fillet(1.0)\n)"), "does not read: fillet"),
        (('.faces(">Y")\n', '.faces("<Y")\n'), "selector this tool does not read"),
        ((".box(83.17, 41.3, 31.06)\n", ".box(83.17, 41.3, 31.06)\n    .box(1, 1, 1)\n"), "second"),
    ],
)
def test_a_part_this_tool_does_not_read_is_refused(change: tuple[str, str], match: str) -> None:
    text = MANIFOLD.format(plane="XY", f1="Z", f2="Y", f3="X").replace(*change)
    with pytest.raises(ValueError, match=match):
        cf.part_closed_form(text)


def test_a_cut_that_takes_away_an_extreme_is_refused() -> None:
    # A bore wider than the box's x extent removes its +x and -x faces: the box no longer
    # gives the bounds, and the tool refuses rather than report them.
    box = cf.Cuboid((-1.0, -5.0, -5.0), (1.0, 5.0, 5.0))
    bore = cf.Rod(1, (0.0, 0.0, 0.0), 9.0, -6.0, 6.0)
    with pytest.raises(ValueError, match="extreme"):
        cf.part_measures([("+", box), ("-", bore)])


@pytest.mark.parametrize("corpus", ["benchcad", "cadrecode"])
def test_each_committed_verdict_rests_on_evidence_that_exists(corpus: str) -> None:
    raw = json.loads((C2 / corpus / "verdicts.json").read_text(encoding="utf-8"))
    assert raw, corpus
    for stem, value in raw.items():
        verdict = Verdict.model_validate(value)
        if verdict.disagreement is DisagreementClass.OCCT_WRONG:
            assert isinstance(verdict.evidence, ClosedForm), stem
        else:
            assert verdict.disagreement in (
                DisagreementClass.ARRIS_REFUSAL,
                DisagreementClass.ARRIS_BUG,
            ), stem
            assert isinstance(verdict.evidence, RegressionFixture), stem
            fixture = REGRESSION / Path(verdict.evidence.path).name
            expected = json.loads((fixture / "expected.json").read_text(encoding="utf-8"))
            assert "xfail" in expected, stem  # a regression fixture still failing, strict xfail


def test_a_stem_two_verdict_files_class_is_an_error(tmp_path: Path) -> None:
    one = {
        "s": {
            "disagreement": "arris_bug",
            "evidence": {"kind": "fixture", "path": "tests/fixtures/regression/x"},
        }
    }
    (tmp_path / "a.json").write_text(json.dumps(one), encoding="utf-8")
    (tmp_path / "b.json").write_text(json.dumps(one), encoding="utf-8")
    both = [tmp_path / "a.json", tmp_path / "b.json"]
    assert list(cq_corpus.read_verdict_files(both[:1], ["s"])) == ["s"]
    with pytest.raises(ValueError, match="two files"):
        cq_corpus.read_verdict_files(both, ["s"])


def test_a_row_refused_for_another_reason_is_not_classed_by_the_tangent_fixture() -> None:
    fixture = "tests/fixtures/regression/cq-tangent-cylinders"
    kind, message, _ = cf.REFUSAL_CAUSES["cq-tangent-cylinders"]
    same = ArrisRefusal(kind=kind, message=f"{message} (+f2, +f5)", entities=("+f2", "+f5"))
    cf.check_refusal_cause(same, fixture)
    other_kind = ArrisRefusal(kind="OpInvalidError", message=same.message, entities=same.entities)
    other_message = ArrisRefusal(kind=kind, message="no such face", entities=same.entities)
    other_shape = ArrisRefusal(kind=kind, message=same.message, entities=("+f2",))
    for refusal in (other_kind, other_message, other_shape, None):
        with pytest.raises(ValueError, match=r"another reason|did not refuse"):
            cf.check_refusal_cause(refusal, fixture)
    with pytest.raises(ValueError, match="no refusal cause"):
        cf.check_refusal_cause(same, "tests/fixtures/regression/other")


def test_a_family_fixture_classes_only_its_in_subset_rows(tmp_path: Path) -> None:
    """`--refusal` and `--arris-bug` rebuild the committed fixture verdicts from the committed
    table (run with `--verdicts`), and leave a row arris ended `unsupported_api` unclassed."""
    import gzip

    from arris_gym.fidelity import FidelityTable, fidelity_table

    table = FidelityTable.model_validate_json(
        gzip.decompress((C2 / "benchcad" / "fidelity.json.gz").read_bytes())
    )
    committed = json.loads((C2 / "benchcad" / "verdicts.json").read_text(encoding="utf-8"))
    collars = [e for e in table.entries if e.name.startswith("shaft_collar_")]
    outside = [e for e in collars if e.row.status is ag.Status.UNSUPPORTED_API]
    pins = [e for e in table.entries if e.name.startswith("cotter_pin_") and e.row.verdict][:3]
    knob = next(e for e in table.entries if e.name.startswith("lobed_knob_") and e.row.verdict)
    assert outside
    assert any(e.row.outcome.value == "agree" for e in collars)  # rows no verdict touches
    picked = [*collars, *pins, knob]
    path = tmp_path / "fidelity.json.gz"
    path.write_bytes(gzip.compress(fidelity_table(picked).to_json().encode()))
    texts = {e.name: "" for e in picked}
    refusals = {"cotter_pin": "tests/fixtures/regression/cq-tangent-cylinders"}
    bugs = {"shaft_collar": "tests/fixtures/regression/cq-cross-hole-bounds"}
    got = cf.verdicts_for(path, texts, refusals, bugs)
    want = {k: v for k, v in committed.items() if k.startswith(("shaft_collar_", "cotter_pin_"))}
    want = {k: v for k, v in want.items() if k in texts}
    assert got == want
    assert len([k for k in got if k.startswith("shaft_collar_")]) == 5
    assert not {e.name for e in outside} & set(got)
    assert set(cf.verdicts_for(path, texts, refusals)) == {e.name for e in pins}
    with pytest.raises(ValueError, match="both"):
        cf.verdicts_for(path, texts, refusals, {"cotter_pin": bugs["shaft_collar"]})

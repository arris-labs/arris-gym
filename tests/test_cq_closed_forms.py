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
import re
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
    DocAnchor,
    FidelityOutcome,
    OracleReport,
    RegressionFixture,
    SignedSolids,
    Verdict,
    compare,
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


RIVET = REGRESSION / "cq-rivet-edges-across-revolve-axis"


@pytest.mark.parametrize("blend", ["chamfer", "fillet"])
@pytest.mark.parametrize(("plane", "normal"), [("XY", "Z"), ("XZ", "Y"), ("YZ", "X")])
def test_the_rivet_meridian_gives_the_blended_parts_measures(
    blend: str, plane: str, normal: str
) -> None:
    source = (RIVET / "program.py").read_text()
    program = source.replace('"XZ"', f'"{plane}"').replace('"<Y"', f'"<{normal}"')
    program = program.replace(".chamfer(", f".{blend}(")
    form = cf.rivet_closed_form(program)
    result = ag.run(program, dialect="cq")
    assert result.status is ag.Status.OK
    assert _agrees(result, form) == []


def test_the_rivet_form_refuses_a_selector_that_does_not_keep_all_rims() -> None:
    program = (RIVET / "program.py").read_text().replace('"<Y"', '">X"')
    with pytest.raises(ValueError, match="must blend all three rims"):
        cf.rivet_closed_form(program)


def test_the_recorded_rivet_measurements_disagree_with_the_meridian() -> None:
    program = (RIVET / "program.py").read_text()
    report = OracleReport.model_validate_json((RIVET / "oracle.json").read_text())
    result = ag.run(program, dialect="cq")
    assert result.program_sha256 == report.program_sha256
    assert result.status is ag.Status.OK
    verdict = Verdict(
        disagreement=DisagreementClass.OCCT_WRONG,
        evidence=ClosedForm.model_validate(cf.rivet_closed_form(program)),
    )
    row = compare(result, report, verdict)
    assert row.outcome is FidelityOutcome.DISAGREE
    assert row.disagreement is DisagreementClass.OCCT_WRONG


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


RING = """import cadquery as cq

result = (
    cq.Workplane("YZ")
    {start}
    .faces(">X").workplane()
    .hole({bore})
    .edges(">Z or <Z")
    .fillet({f})
    .cut(
        cq.Workplane("YZ")
            .transformed(offset=cq.Vector({y}, 0.0, 0.0), rotate=cq.Vector(0, 0, 0))
            .box({length}, {width}, {thick})
    )
)

# Export
show_object(result)"""

# The corpus's two slotted rings that Open CASCADE gets wrong: a cylinder slotted through (a
# fillet of 0.14 on a ring 0.47 thick) and a circle extruded and slotted to 1.68 of its 2.36.
CORPUS_RINGS = {
    "spacer_ring_012675_s20260505": {
        "start": ".cylinder(0.47, 12.13)",
        "bore": "15.86",
        "f": "0.14",
        "y": "10.03",
        "length": "9.4",
        "width": "2.1",
        "thick": "1.47",
    },
    "spacer_ring_016757_s20260505": {
        "start": ".circle(70.73)\n    .extrude(2.36)",
        "bore": "117.88",
        "f": "0.47",
        "y": "64.835",
        "length": "24.58",
        "width": "2.5",
        "thick": "3.36",
    },
}


@pytest.mark.parametrize("stem", sorted(CORPUS_RINGS))
def test_a_corpus_slotted_ring_is_occt_wrong_by_its_closed_form(stem: str) -> None:
    """The two rows as written: arris is within ADR-0005's constants of the closed form, the
    recorded oracle report is not (1.3e-6 and 2.9e-9 off in volume), and the rule alone leaves
    each unclassified."""
    import gzip
    import hashlib

    from arris_gym.fidelity import FidelityOutcome, OracleReport, compare

    text = RING.format(**CORPUS_RINGS[stem])
    rows = gzip.decompress((C2 / "benchcad" / "oracle.jsonl.gz").read_bytes()).splitlines()
    row = next(json.loads(line) for line in rows if json.loads(line)["stem"] == stem)
    report = OracleReport.model_validate(row["report"])
    assert hashlib.sha256(text.encode()).hexdigest() == report.program_sha256
    result = ag.run(text, dialect="cq")
    assert compare(result, report).outcome is FidelityOutcome.UNCLASSIFIED
    verdict = Verdict.model_validate(
        {"disagreement": "occt_wrong", "evidence": cf.slotted_ring_closed_form(text)}
    )
    assert compare(result, report, verdict).disagreement is DisagreementClass.OCCT_WRONG


@pytest.mark.parametrize(
    ("start", "thick"),
    [
        (".cylinder(2.0, 6.0)", "3.0"),  # centred: the box reaches past both faces (through)
        (".circle(6.0)\n    .extrude(2.0)", "5.0"),  # from the plane: through the ring
        (".circle(6.0)\n    .extrude(2.0)", "3.0"),  # a floor 1.5 up, inside the straight part
    ],
)
@pytest.mark.parametrize(
    ("y", "length", "width", "f"),
    [("4.0", "6.0", "1.6", "0.2"), ("4.5", "7.5", "2.4", "0.3")],  # a wider slot, a bigger fillet
)
def test_a_slotted_ring_is_what_arris_builds(
    start: str, thick: str, y: str, length: str, width: str, f: str
) -> None:
    text = RING.format(start=start, bore="9.0", f=f, y=y, length=length, width=width, thick=thick)
    assert _agrees(ag.run(text, dialect="cq"), cf.slotted_ring_closed_form(text)) == []


@pytest.mark.oracle
@pytest.mark.parametrize(
    ("expression", "volume", "area", "centroid", "bounds"),
    [
        ("makeTorus(5, 1)", 10 * math.pi**2, 20 * math.pi**2, (0, 0, 0), ((-6, -6, -1), (6, 6, 1))),
        (
            "makeCone(3, 1, 2)",
            26 * math.pi / 3,
            math.pi * (10 + 4 * math.sqrt(8)),
            (0, 0, 9 / 13),
            ((-3, -3, 0), (3, 3, 2)),
        ),
    ],
)
def test_boundary_integrates_analytic_blend_surfaces(
    expression: str,
    volume: float,
    area: float,
    centroid: tuple[float, float, float],
    bounds: tuple[tuple[float, float, float], tuple[float, float, float]],
) -> None:
    from arris_gym.fidelity._agreement import figures_agree

    text = f'import cadquery as cq\nr = cq.Workplane("XY").newObject([cq.Solid.{expression}])\n'
    expected = ClosedForm(
        volume=volume, area=area, centroid=centroid, bounds=bounds, note="Analytic solid."
    )
    (measured,) = cf.sketch_boundary_forms([text], blends=True, subdivisions=(24, 48), workers=1)
    assert figures_agree(expected, ClosedForm.model_validate(measured))


@pytest.mark.oracle
@pytest.mark.xfail(
    reason="The converged oracle trim integral still differs from the annular closed form",
    raises=AssertionError,
    strict=True,
)
def test_boundary_integral_with_toroidal_rim_fillets() -> None:
    from arris_gym.fidelity._agreement import figures_agree

    fixture = REGRESSION / "oracle-slotted-ring-boundary"
    text = (fixture / "oracle.py").read_text()
    expected = ClosedForm.model_validate_json((fixture / "expected.json").read_text())
    (measured,) = cf.sketch_boundary_forms(
        [text + "\nr = result\n"], blends=True, subdivisions=(24, 48), workers=1
    )
    assert figures_agree(expected, ClosedForm.model_validate(measured))


@pytest.mark.parametrize(
    ("change", "match"),
    [
        (("YZ", "XZ"), "not a filleted ring"),
        ((".fillet(0.14)", ".chamfer(0.14)"), "not a filleted ring"),
        (("9.4, 2.1", "4.0, 2.1"), "outside the arrangement"),  # the slot stops inside the wall
    ],
)
def test_a_ring_this_tool_does_not_read_is_refused(change: tuple[str, str], match: str) -> None:
    text = RING.format(**CORPUS_RINGS["spacer_ring_012675_s20260505"]).replace(*change)
    with pytest.raises(ValueError, match=match):
        cf.slotted_ring_closed_form(text)


def test_a_slot_that_stops_in_the_lower_rim_fillet_is_refused() -> None:
    text = RING.format(**{**CORPUS_RINGS["spacer_ring_016757_s20260505"], "thick": "0.3"})
    with pytest.raises(ValueError, match="outside the arrangement"):
        cf.slotted_ring_closed_form(text)


def test_a_slot_that_stops_in_the_upper_rim_fillet_changes_the_box() -> None:
    from arris_gym.fidelity import OracleReport

    fixture = REGRESSION / "cq-slot-into-rounded-rim-bounds"
    text = (fixture / "program.py").read_text()
    report = OracleReport.model_validate_json((fixture / "oracle.json").read_text())
    result = ag.run(text, dialect="cq")
    expected = cf.slotted_ring_closed_form(text)
    closed = ClosedForm.model_validate(expected)
    assert result.program_sha256 == report.program_sha256
    assert closed.bounds[1][1] == math.sqrt(52.41**2 - 1.25**2)
    differences = _agrees(result, expected)
    assert len(differences) == 1
    assert differences[0].startswith("bounds ")
    cf.check_bug_cause(result, report, str(fixture))


SPROCKET = """import cadquery as cq

result = (
    cq.Workplane("{plane}")
    .circle({hub})
    .extrude({length})
    .union(
        cq.Workplane("{plane}")
            .polyline({outline})
            .close()
            .extrude({w})
            .edges(">{axis}")
            .chamfer({c})
            .edges("<{axis}")
            .chamfer({c})
    )
    .union(
        cq.Workplane("{plane}")
            .workplane(offset={offset})
            .polyline({outline})
            .close()
            .extrude({w})
            .edges(">{axis}")
            .chamfer({c})
            .edges("<{axis}")
            .chamfer({c})
    )
    .faces(">{axis}").workplane()
    .hole({bore})
)

# Export
show_object(result)"""


def sprocket_text(plane: str, c: str = "0.6", teeth: int = 7, length: str = "20.04") -> str:
    """A sprocket of the corpus's shape on a constructed outline: `teeth` lobes, so not
    centrally symmetric, a reflex vertex at every root, a plate 4 thick."""
    points = []
    for k in range(4 * teeth):
        angle = 2 * math.pi * k / (4 * teeth)
        radius = (14.0, 11.0, 10.0, 11.0)[k % 4] + 0.5 * (k % 3)
        points.append((round(radius * math.cos(angle), 4), round(radius * math.sin(angle), 4)))
    return SPROCKET.format(
        plane=plane,
        axis={"YZ": "X", "XY": "Z", "XZ": "Y"}[plane],
        hub="6.0",
        length=length,
        outline=points,
        w="4.0",
        c=c,
        offset="12.0",
        bore="4.4",
    )


@pytest.mark.parametrize("plane", ["YZ", "XY", "XZ"])
@pytest.mark.parametrize("c", ["0.3", "0.6"])
@pytest.mark.parametrize("length", ["20.04", "19.99"])  # the hub past the plate, and inside it
def test_a_sprocket_is_what_arris_builds(plane: str, c: str, length: str) -> None:
    # An outline with convex and reflex corners and no symmetry (7 lobes), along each axis:
    # the mitred chamfer's volume, area and centre, the hub's and the bore's, and a centroid off
    # the axis, against arris's own boolean and chamfer.
    # `XZ` extrudes toward -y; a hub ending 0.01 inside the second plate is that plate's solid.
    text = sprocket_text(plane, c, length=length)
    assert _agrees(ag.run(text, dialect="cq"), cf.sprocket_closed_form(text)) == []


@pytest.mark.parametrize(("plane", "axis"), [("YZ", "X"), ("XY", "Z"), ("XZ", "Y")])
def test_a_sprocket_keyway_removes_only_the_rectangle_outside_the_bore(
    plane: str, axis: str
) -> None:
    text = sprocket_text(plane).replace(
        "    .hole(4.4)\n",
        f'    .hole(4.4)\n    .faces(">{axis}").workplane()\n'
        "    .center(0, 2)\n    .rect(2, 4)\n    .cutThruAll()\n",
    )
    assert _agrees(ag.run(text, dialect="cq"), cf.sprocket_closed_form(text)) == []


@pytest.mark.parametrize(
    ("change", "match"),
    [
        (("hole(4.4)", "hole(14.0)"), "outside the arrangement"),  # a bore wider than the hub
        (("offset=12.0", "offset=3.0"), "outside the arrangement"),  # the plates meet
        (("circle(6.0)", "circle(19.0)"), "outside the arrangement"),  # the hub reaches the outline
        (("chamfer(0.6)", "chamfer(2.1)"), "outside the arrangement"),  # more than half a plate
        (('edges(">X")', 'edges(">Z")'), "not along its axis"),
    ],
)
def test_a_sprocket_this_tool_does_not_read_is_refused(change: tuple[str, str], match: str) -> None:
    text = sprocket_text("YZ").replace(*change)
    with pytest.raises(ValueError, match=match):
        cf.sprocket_closed_form(text)


@pytest.mark.parametrize("slug", ["ok-sprocket-corpus-along-x", "ok-sprocket-corpus-along-z"])
def test_a_corpus_sprocket_is_occt_wrong_by_its_closed_form(slug: str) -> None:
    """The two sprockets as committed: arris is within ADR-0005's constants of the closed form,
    the recorded oracle report is not (its chamfer takes less than the mitre does), and the
    rule alone leaves each row unclassified."""
    from arris_gym.fidelity import FidelityOutcome, OracleReport, compare

    directory = Path(__file__).parent / "fixtures" / "cq" / slug
    text = (directory / "program.py").read_text(encoding="utf-8")
    verdict = Verdict.model_validate_json((directory / "verdict.json").read_text(encoding="utf-8"))
    assert verdict.evidence == ClosedForm.model_validate(cf.sprocket_closed_form(text))
    report = OracleReport.model_validate_json((directory / "oracle.json").read_text("utf-8"))
    result = ag.run(text, dialect="cq", timeout=60)
    assert _agrees(result, cf.sprocket_closed_form(text)) == []
    assert compare(result, report).outcome is FidelityOutcome.UNCLASSIFIED
    assert compare(result, report, verdict).disagreement is DisagreementClass.OCCT_WRONG


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


@pytest.mark.oracle
def test_boundary_integrals_match_closed_forms_on_sketches_and_crossing_cylinders() -> None:
    from arris_gym.fidelity._agreement import figures_agree

    sketch = C2.parent / "sketch"
    texts = []
    expected = []
    for name in ("ok-sketch-ring", "ok-sketch-disjoint-adds", "ok-sketch-yz-negative"):
        directory = sketch / name
        text = (directory / "program.py").read_text("utf-8")
        texts.append(text + ("\nr = result\n" if "result =" in text else ""))
        measures = json.loads((directory / "expected.json").read_text("utf-8"))["measures"]
        expected.append(
            ClosedForm.model_validate(
                {
                    **{key: measures[key] for key in ("volume", "area", "centroid", "bounds")},
                    "note": name,
                }
            )
        )
    # Perpendicular equal cylinders with an entire Steinmetz intersection.
    texts.append(
        "import cadquery as cq\n"
        'r = cq.Workplane("XY").cylinder(8, 2).union(cq.Workplane("YZ").cylinder(8, 2))\n'
    )
    expected.append(
        ClosedForm(
            volume=64 * math.pi - 128 / 3,
            area=80 * math.pi - 64,
            centroid=(0, 0, 0),
            bounds=((-4, -2, -4), (4, 2, 4)),
            note="equal cylinders crossing",
        )
    )
    for got, want in zip(cf.sketch_boundary_forms(texts), expected, strict=True):
        assert figures_agree(ClosedForm.model_validate(got), want), (got, want)


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


def test_part_closed_form_for_an_edge_touching_through_rectangle() -> None:
    text = """import cadquery as cq

result = (
    cq.Workplane("YZ")
    .box(8, 6, 10)
    .faces(">X").workplane()
    .center(1, 1)
    .rect(6, 4)
    .cutThruAll()
)
"""
    # Removing the upper-right 6 x 4 corner leaves an L of area 24,
    # perimeter 28 and centroid opposite the removed rectangle's centre.
    closed = cf.part_closed_form(text)
    assert closed["volume"] == pytest.approx(240)
    assert closed["area"] == pytest.approx(328)
    assert closed["centroid"] == pytest.approx([0, -1, -1])
    assert closed["bounds"] == [[-5, -4, -3], [5, 4, 3]]
    assert _agrees(ag.run(text, dialect="cq"), closed) == []


def test_a_rounded_l_section_matches_the_closed_form_with_a_bore() -> None:
    text = """import cadquery as cq

result = (
    cq.Workplane("XY")
    .box(12, 12, 8)
    .faces(">Z").workplane()
    .center(2, 2)
    .rect(8, 8)
    .cutThruAll()
    .edges("|Z")
    .fillet(0.5)
    .faces(">Z").workplane()
    .pushPoints([(-5.0, 2.0)])
    .hole(1.0)
)
"""
    result = ag.run(text, dialect="cq")
    closed = cf.closed_form_for("mounting_angle_example", text, result.program_sha256)
    assert closed is not None
    assert _agrees(result, closed) == []


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


def test_a_chamfered_box_meets_its_textbook_figures() -> None:
    # A box L x W x H with the four edges of its top chamfered by c: the top layer's section at
    # t above its foot is (L - 2t)(W - 2t), so V = LW(H - c) + LWc - (L + W)c^2 + 4c^3/3, and
    # each chamfer is a trapezoid of slant c sqrt 2.
    L, W, H, c = 7.0, 5.0, 3.0, 0.8
    for a in range(3):
        lo, hi = [-L / 2, -W / 2, -H / 2], [L / 2, W / 2, H / 2]
        lo[a], lo[2], hi[a], hi[2] = lo[2], lo[a], hi[2], hi[a]  # the top toward +a
        bevel = cf.Bevel((lo[0], lo[1], lo[2]), (hi[0], hi[1], hi[2]), a, c)
        volume, area, centroid, bounds = cf.part_measures([("+", bevel)])
        assert volume == pytest.approx(L * W * H - (L + W) * c * c + 4 * c**3 / 3, rel=1e-14)
        sides = (L - 2 * c) * (W - 2 * c) + 2 * (L + W) * (H - c)
        slants = 2 * math.sqrt(2) * ((L + W) * c - 2 * c * c)
        assert area == pytest.approx(L * W + sides + slants, rel=1e-14)
        foot = H / 2 - c  # the moment along a: the block under the layer, then the layer
        moment = L * W * (H - c) * (foot - H / 2) / 2
        moment += L * W * (foot * c + c * c / 2) - 2 * (L + W) * (foot * c * c / 2 + c**3 / 3)
        moment += 4 * (foot * c**3 / 3 + c**4 / 4)
        assert centroid[a] == pytest.approx(moment / volume, rel=1e-13)
        assert bounds == ((lo[0], lo[1], lo[2]), (hi[0], hi[1], hi[2]))


CHAMFERED = MANIFOLD.replace(
    ".box(83.17, 41.3, 31.06)\n",
    '.box(83.17, 41.3, 31.06)\n    .edges(">{f1}")\n    .chamfer(1.3)\n',
).replace(
    ".hole(9.4)\n)",
    """.hole(9.4)
    .union(
        cq.Workplane("{plane}")
            .transformed(offset=cq.Vector(-24.95, 0.0, {lift}), rotate=cq.Vector(0, 0, 0))
            .cylinder(3.0, 7.5)
    )
)""",
)


@pytest.mark.parametrize(
    ("plane", "faces", "lift"),
    [("XY", "ZYX", "16.53"), ("XZ", "YZX", "-16.53"), ("YZ", "XZY", "16.53")],
)
def test_a_chamfered_manifold_block_is_what_arris_builds(plane: str, faces: str, lift: str) -> None:
    """The corpus's chamfered block: the top's edges chamfered, the counterbores and the third
    hole centred on the chamfered edges (their workplanes' origins keep the top's height), so
    the chamfers meet the bores' sides, and a boss sunk into the top over a hole."""
    text = CHAMFERED.format(plane=plane, f1=faces[0], f2=faces[1], f3=faces[2], lift=lift)
    assert any(isinstance(s, cf.Bevel) for _, s in cf.part_ops(text))
    assert _agrees(ag.run(text, dialect="cq"), cf.part_closed_form(text)) == []


@pytest.mark.parametrize(
    ("change", "match"),
    [
        (
            (".chamfer(1.3)\n", ".chamfer(1.3)\n    .fillet(1.0)\n"),
            "fillet this tool does not read",
        ),
        (('.faces(">Y")\n', '.faces("%PLANE")\n'), "selector this tool does not read"),
        (('.faces(">Y")\n', '.faces("<Y")\n'), "faces of another direction"),
        ((".box(83.17, 41.3, 31.06)\n", ".box(83.17, 41.3, 31.06)\n    .box(1, 1, 1)\n"), "second"),
        (("chamfer(1.3)", "chamfer(21.0)"), "meets another face"),  # past half the width
        (("chamfer(1.3)", "chamfer(1.3, 0.5)"), "chamfer this tool does not read"),
        (("chamfer(1.3)", "fillet(1.3)"), "does not blend"),
        (('edges(">Z")', 'edges("|Z")'), "edges this tool does not round"),
    ],
)
def test_a_part_this_tool_does_not_read_is_refused(change: tuple[str, str], match: str) -> None:
    text = CHAMFERED.format(plane="XY", f1="Z", f2="Y", f3="X", lift="16.53").replace(*change)
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
    report = json.loads((C2 / corpus / "arris-report.json").read_text(encoding="utf-8"))
    assert raw, corpus
    for stem, value in raw.items():
        verdict = Verdict.model_validate(value)
        if verdict.disagreement is DisagreementClass.OCCT_WRONG:
            assert isinstance(verdict.evidence, ClosedForm | SignedSolids), stem
        elif verdict.disagreement is DisagreementClass.BY_DESIGN:
            assert isinstance(verdict.evidence, DocAnchor), stem
            path, slug = verdict.evidence.anchor.split("#")
            text = (Path(__file__).parent.parent / path).read_text(encoding="utf-8")
            assert f"## {slug.capitalize()}" in text, stem  # an ADR's own heading
        else:
            assert verdict.disagreement in (
                DisagreementClass.ARRIS_REFUSAL,
                DisagreementClass.ARRIS_BUG,
            ), stem
            assert isinstance(verdict.evidence, RegressionFixture), stem
            fixture = REGRESSION / Path(verdict.evidence.path).name
            expected = json.loads((fixture / "expected.json").read_text(encoding="utf-8"))
            # An arris bug's fixture still fails (strict xfail); a refusal's may instead pin
            # the kernel's typed refusal, the capability arris is asked for.
            pinned = verdict.disagreement is DisagreementClass.ARRIS_REFUSAL and (
                expected["status"] == "arris_refusal"
            )
            historical = expected.get("historical_xfail", {})
            recorded_versions = report["arris_versions"]
            was_failing = bool(recorded_versions) and all(
                historical.get(version) for version in recorded_versions
            )
            assert pinned or "xfail" in expected or was_failing, stem


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


@pytest.mark.parametrize(
    "slug",
    [
        "cq-locator-block-intersecting-bores-fillet",
        "cq-chamfers-overlap-on-a-face",
        "cq-cotter-pin-self-contact",
        "cq-cotter-pin-tangent-faces",
        "cq-fillets-overlap-on-a-face",
        "cq-short-slot-flat-link",
        "cq-rim-chamfer-after-crosswise-fillet",
        "cq-rim-chamfer-after-parallel-fillet",
        "cq-slotted-plate-chamfer-after-fillet",
        "cq-vertical-fillet-after-rim-chamfer",
        "cq-waffle-plate-tangent-fillet",
    ],
)
def test_a_refusal_fixture_identifies_the_corpus_failure(slug: str) -> None:
    from arris_gym.fidelity import OracleReport, OracleStatus

    fixture = REGRESSION / slug
    result = ag.run((fixture / "program.py").read_text(), dialect="cq")
    report = OracleReport.model_validate_json((fixture / "oracle.json").read_text())
    assert result.program_sha256 == report.program_sha256
    assert report.status is OracleStatus.INVALID
    assert result.status is ag.Status.ARRIS_REFUSAL
    assert result.refusal is not None
    path = f"tests/fixtures/regression/{slug}"
    cf.check_refusal_cause(result.refusal, path)
    other = result.refusal.message.replace("cylinder surface", "cone surface")
    if other == result.refusal.message:
        other = "another cause"
    with pytest.raises(ValueError, match="another reason"):
        cf.check_refusal_cause(result.refusal.model_copy(update={"message": other}), path)


@pytest.mark.parametrize(
    ("slug", "disagreement"),
    [
        ("cq-cotter-pin-self-contact", "arris_refusal"),
        ("cq-retainer-plate-arc-loop-intersection", "arris_bug"),
    ],
)
def test_failure_replay_requires_the_fixtures_failure_signature(
    slug: str, disagreement: str
) -> None:
    """Check the evidence against live fixtures and reject unrelated failures."""
    from arris_gym.fidelity import OracleReport, OracleStatus, Verdict, compare

    fixture = REGRESSION / slug
    result = ag.run((fixture / "program.py").read_text(), dialect="cq")
    report = OracleReport.model_validate_json((fixture / "oracle.json").read_text())
    verdict = Verdict.model_validate(cf._failure_replay_verdict(result, report, slug))
    assert verdict.disagreement.value == disagreement
    assert compare(result, report, verdict).verdict == verdict

    with pytest.raises(ValueError, match="different program"):
        cf._failure_replay_verdict(
            result, report.model_copy(update={"program_sha256": "0" * 64}), slug
        )
    with pytest.raises(ValueError, match=r"invalid oracle shape|self-intersecting loops"):
        cf._failure_replay_verdict(
            result, report.model_copy(update={"status": OracleStatus.RUNTIME}), slug
        )
    if result.refusal is not None:
        refusal = result.refusal.model_copy(update={"entities": ("+f2", "+f5")})
        with pytest.raises(ValueError, match="refusal entities"):
            cf._failure_replay_verdict(result.model_copy(update={"refusal": refusal}), report, slug)
    else:
        with pytest.raises(ValueError, match="self-intersecting loops"):
            cf._failure_replay_verdict(
                result.model_copy(update={"violations": ("L5 f1: loops 0 and 1 intersect",)}),
                report,
                slug,
            )


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
    # Rows outside the subset, of a family flagged below: no fixture classes them.
    outside = [e for e in table.entries if e.row.status is ag.Status.UNSUPPORTED_API][:3]
    pins = [e for e in table.entries if e.name.startswith("cotter_pin_") and e.row.verdict][:3]
    knob = next(e for e in table.entries if e.name.startswith("lobed_knob_") and e.row.verdict)
    assert outside
    assert any(e.row.outcome.value == "agree" for e in collars)  # rows no verdict touches
    picked = [*collars, *pins, knob, *outside]
    path = tmp_path / "fidelity.json.gz"
    path.write_bytes(gzip.compress(fidelity_table(picked).to_json().encode()))
    texts = {e.name: "" for e in picked}
    tangent = "tests/fixtures/regression/cq-tangent-cylinders"
    refusals = {
        "cotter_pin": tangent,
        **{re.sub(r"_\d+_s\d+$", "", e.name): tangent for e in outside},
    }
    overlap = "tests/fixtures/regression/cq-chamfers-overlap-on-a-face"
    bugs = {
        "shaft_collar": "tests/fixtures/regression/cq-cross-hole-bounds",
        "shaft_collar_016155_s20260505": overlap,
        "shaft_collar_017314_s20260505": overlap,
    }
    # The collars classed by their boundary integral (`--blended-boundary`), each by its stem.
    integrated = frozenset(
        k
        for k, v in committed.items()
        if k.startswith("shaft_collar_") and "Green's theorem" in str(v["evidence"])
    )
    assert len(integrated) == 3
    got = cf.verdicts_for(path, texts, refusals, bugs, integrated)
    want = {k: v for k, v in committed.items() if k.startswith(("shaft_collar_", "cotter_pin_"))}
    want = {k: v for k, v in want.items() if k in texts and k not in integrated}
    assert got == want
    assert len([k for k in got if k.startswith("shaft_collar_")]) == 64
    assert not {e.name for e in outside} & set(got)
    own = {e.name for e in collars if e.row.program_sha256 in cf.COLLARS}  # its closed form
    assert len(own) == 1
    assert set(cf.verdicts_for(path, texts, refusals)) == {e.name for e in pins} | own
    with pytest.raises(ValueError, match="both"):
        cf.verdicts_for(path, texts, refusals, {"cotter_pin": bugs["shaft_collar"]})


def test_a_row_stem_classes_that_row_alone(tmp_path: Path) -> None:
    """`--arris-bug` and `--refusal` take a stem as well as a family; the stem wins over its
    family's key, and its siblings keep the family's."""
    import gzip

    from arris_gym.fidelity import FidelityTable, fidelity_table

    table = FidelityTable.model_validate_json(
        gzip.decompress((C2 / "benchcad" / "fidelity.json.gz").read_bytes())
    )
    collars = [
        e
        for e in table.entries
        if e.name.startswith("shaft_collar_")
        and e.row.verdict
        and e.row.program_sha256 not in cf.COLLARS  # its own closed form, not a fixture's row
    ]
    assert len(collars) == 66
    path = tmp_path / "fidelity.json.gz"
    path.write_bytes(gzip.compress(fidelity_table(collars).to_json().encode()))
    texts = {e.name: "" for e in collars}
    family = "tests/fixtures/regression/cq-cross-hole-bounds"
    one = "tests/fixtures/regression/cq-chamfer-slot-bounds"
    got = cf.verdicts_for(path, texts, {}, {"shaft_collar": family, collars[0].name: one})
    paths = {name: v["evidence"]["path"] for name, v in got.items()}  # type: ignore[index]
    assert paths.pop(collars[0].name) == one
    assert set(paths.values()) == {family}
    assert len(paths) == 65


def test_a_row_whose_program_no_closed_form_reads_stays_unclassified(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A program the family's reader refuses (here an empty text) does not stop the tool: the
    row is left out of the verdicts and named on stderr, never dropped from the count."""
    import gzip

    from arris_gym.fidelity import FidelityTable, fidelity_table

    table = FidelityTable.model_validate_json(
        gzip.decompress((C2 / "benchcad" / "fidelity.json.gz").read_bytes())
    )
    rows = [e for e in table.entries if e.name.startswith(cf.FORM_FAMILIES) and e.row.verdict][:2]
    assert len(rows) == 2
    path = tmp_path / "fidelity.json.gz"
    path.write_bytes(gzip.compress(fidelity_table(rows).to_json().encode()))
    assert cf.verdicts_for(path, {e.name: "" for e in rows}, {}) == {}
    assert "2 rows no closed form reads" in capsys.readouterr().err


def plate_text(plane: str, hub: bool = False, c: str = "0.6") -> str:
    """A `sprocket_*` program of the corpus's shape on the constructed 7-lobe outline: a plate
    4 thick bored 8.8 across, with an optional hub of radius 9 and height 5 below it."""
    points = []
    for k in range(28):
        angle = 2 * math.pi * k / 28
        radius = (14.0, 11.0, 10.0, 11.0)[k % 4] + 0.5 * (k % 3)
        points.append((round(radius * math.cos(angle), 4), round(radius * math.sin(angle), 4)))
    top = {"YZ": "X", "XY": "Z", "XZ": "Y"}[plane]
    text = (
        f'import cadquery as cq\n\nresult = (\n    cq.Workplane("{plane}")\n'
        f"    .polyline({points})\n    .close()\n    .extrude(4.0)\n"
        f'    .edges(">{top}")\n    .chamfer({c})\n    .edges("<{top}")\n    .chamfer({c})\n'
        f'    .faces(">{top}").workplane()\n    .hole(8.8)\n'
    )
    if hub:
        text += (
            f'    .faces("<{top}").workplane()\n    .circle(9.0)\n    .extrude(5.0)\n'
            f'    .faces("<{top}").workplane()\n    .hole(8.8, depth=6.0)\n'
        )
    return text + ")\n\n# Export\nshow_object(result)\n"


@pytest.mark.parametrize("plane", ["YZ", "XY", "XZ"])
@pytest.mark.parametrize("c", ["0.3", "0.6"])
def test_a_sprocket_plate_is_what_arris_builds(plane: str, c: str) -> None:
    # A plate with convex and reflex corners and no symmetry, along each axis (`XZ` toward -y).
    text = plate_text(plane, c=c)
    assert _agrees(ag.run(text, dialect="cq"), cf.plate_closed_form(text)) == []


def test_a_sprocket_plate_with_a_hub_is_what_arris_builds() -> None:
    text = plate_text("XY", hub=True)
    assert _agrees(ag.run(text, dialect="cq"), cf.plate_closed_form(text)) == []


@pytest.mark.parametrize(("plane", "axis"), [("XY", "Z"), ("YZ", "X"), ("XZ", "Y")])
@pytest.mark.parametrize("hub", [False, True])
def test_a_keyway_through_a_sprocket_plate(plane: str, axis: str, hub: bool) -> None:
    text = plate_text(plane, hub=hub).replace(
        "\n)\n\n# Export",
        f'\n    .faces(">{axis}").workplane()\n    .center(0, 3)\n    .rect(2, 6)\n'
        "    .cutThruAll()\n)\n\n# Export",
    )
    assert _agrees(ag.run(text, dialect="cq"), cf.plate_closed_form(text)) == []


@pytest.mark.parametrize(("plane", "axis"), [("XY", "Z"), ("YZ", "X"), ("XZ", "Y")])
def test_a_cam_closed_form_includes_both_rims_and_the_keyway(plane: str, axis: str) -> None:
    text = f"""import cadquery as cq

result = (
    cq.Workplane("{plane}")
    .polyline([(-10, -10), (10, -10), (10, 10), (-10, 10)])
    .close()
    .extrude(5)
    .union(
        cq.Workplane("{plane}")
            .transformed(offset=cq.Vector(0, 0, 7), rotate=cq.Vector(0, 0, 0))
            .cylinder(4, 5)
    )
    .faces(">{axis}").workplane()
    .hole(4)
    .faces("<{axis}")
    .edges()
    .fillet(0.4)
    .faces(">{axis}")
    .edges()
    .chamfer(0.6)
    .faces(">{axis}").workplane()
    .pushPoints([(0.0, 2.0)])
    .rect(1, 2)
    .cutThruAll()
    .cut(
        cq.Workplane("{plane}")
            .transformed(offset=cq.Vector(7, 0.0, 2.5), rotate=cq.Vector(0, 0, 0))
            .cylinder(10, 0.75)
    )
)

# Export
show_object(result)
"""
    assert _agrees(ag.run(text, dialect="cq"), cf.cam_closed_form(text)) == []
    with pytest.raises(ValueError, match="exceeds its section"):
        cf.cam_closed_form(
            text.replace(".rect(1, 2)", ".rect(1, 8)").replace("(0.0, 2.0)", "(0.0, 5.0)")
        )


@pytest.mark.parametrize(
    ("change", "match"),
    [
        (
            ("hole(8.8)\n", "hole(24.0)\n"),
            "stops short|outside the arr",
        ),  # a bore past the flat face
        (("chamfer(0.6)", "chamfer(2.1)"), "outside the arrangement"),  # more than half the plate
        (('edges(">Z")', 'edges(">X")'), "not along its axis"),
        (("hole(8.8, depth=6.0)", "hole(8.8, depth=3.0)"), "stops short"),
        (("circle(9.0)", "circle(3.0)"), "outside the arrangement"),  # a hub inside the bore
    ],
)
def test_a_sprocket_plate_this_tool_does_not_read_is_refused(
    change: tuple[str, str], match: str
) -> None:
    with pytest.raises(ValueError, match=match):
        cf.plate_closed_form(plate_text("XY", hub=True).replace(*change))


SCREW_TURNED = """import cadquery as cq

result = (
    cq.Workplane("XY")
    .circle(1.25)
    .extrude(20.0)
    .faces(">Z").workplane()
    .circle(2.5)
    .extrude(1.5)
    .edges(">Z")
    .fillet(0.3)
    .cut(
        cq.Workplane("XY")
            .transformed(offset=cq.Vector(0, 0, 21.2), rotate=cq.Vector(0, 0, 0))
            .box(5.4, 0.6, 1.4)
    )
)

# Export
show_object(result)
"""
SCREW_CYLINDER = SCREW_TURNED.replace(
    ".circle(1.25)\n    .extrude(20.0)",
    ".transformed(offset=cq.Vector(0, 0, 10.0), rotate=cq.Vector(0, 0, 0))\n"
    "    .cylinder(20.0, 1.25)",
).replace("fillet(0.3)", "fillet(0.45)")


@pytest.mark.parametrize("text", [SCREW_TURNED, SCREW_CYLINDER], ids=["turned", "cylinder"])
def test_a_pan_head_screw_is_what_arris_builds(text: str) -> None:
    """A filleted head with a slot across it, the shank by either of the corpus's two ways."""
    assert _agrees(ag.run(text, dialect="cq"), cf.screw_closed_form(text)) == []


@pytest.mark.parametrize(
    ("change", "match"),
    [
        (("box(5.4, 0.6, 1.4)", "box(4.0, 0.6, 1.4)"), "outside the arrangement"),  # narrower
        (("fillet(0.3)", "fillet(1.6)"), "outside the arrangement"),  # more than the head
        (("21.2", "20.3"), "does not open"),  # a floor under the head's bottom
        (("(0, 0, 21.2)", "(1, 0, 21.2)"), "off the axis"),
    ],
)
def test_a_pan_head_screw_this_tool_does_not_read_is_refused(
    change: tuple[str, str], match: str
) -> None:
    with pytest.raises(ValueError, match=match):
        cf.screw_closed_form(SCREW_TURNED.replace(*change))


def _bounds_pair(
    *,
    box_gap: float = 1e-3,
    volume_rel: float = 1e-5,
    arris_ok: bool = True,
    oracle_ok: bool = True,
    faces: int = 0,
) -> tuple[ag.ExecResult, object]:
    """An arris result and an oracle report of one body, the arris box `box_gap` wider in x."""
    from arris_gym.fidelity import OracleMeasures, OracleReport, OracleStatus
    from arris_gym.sandbox import Dialect, Measures, Versions

    sha = "0" * 64
    box = ((-1.0, -1.0, 0.0), (1.0, 1.0, 2.0))
    wide = ((-1.0 - box_gap, -1.0, 0.0), (1.0 + box_gap, 1.0, 2.0))
    measures = Measures(
        volume=10.0 * (1 + volume_rel),
        area=30.0,
        centroid=(0.0, 0.0, 1.0),
        bounds=wide,
        faces=6 + faces,
        shells=1,
        genus=0,
        face_kinds=(("plane", 6 + faces),),
    )
    result = ag.ExecResult.model_construct(  # no body: only the measures are read
        status=ag.Status.OK if arris_ok else ag.Status.ARRIS_REFUSAL,
        message="",
        refusal=None,
        body=None,
        measures=measures if arris_ok else None,
        violations=(),
        program_sha256=sha,
        dialect=Dialect.CQ,
        versions=Versions(arris="0", numpy="0", arris_gym="0"),
        seconds=0.0,
    )
    report = OracleReport.model_construct(
        status=OracleStatus.OK if oracle_ok else OracleStatus.INVALID,
        message="",
        measures=OracleMeasures(
            volume=10.0, area=30.0, centroid=(0.0, 0.0, 1.0), bounds=box, faces=6, solids=1
        )
        if oracle_ok
        else None,
        step_sha256=sha if oracle_ok else None,
        program_sha256=sha,
        versions=None,
    )
    return result, report


def test_a_family_arris_bug_row_is_classed_only_when_the_bounds_fixture_is_its_cause() -> None:
    """`--arris-bug` keyed by a family classes a row only if its figures show the fixture's
    cause: both sides `ok`, arris's box loose against the oracle's, and the other figures what
    the fixture allows. Any other row stays unclassified (the tool names it)."""
    fixture = "tests/fixtures/regression/cq-cross-hole-bounds"
    result, report = _bounds_pair()
    cf.check_bounds_cause(result, report, fixture)  # type: ignore[arg-type]
    cases = {
        "box is not loose": _bounds_pair(box_gap=BOUNDS_ABS / 10),
        "did not end ok": _bounds_pair(arris_ok=False),
        "did not end ok ": _bounds_pair(oracle_ok=False),
        "volume": _bounds_pair(volume_rel=1e-2),
        "faces": _bounds_pair(faces=9),
    }
    for why, (bad, other) in cases.items():
        with pytest.raises(ValueError, match=why.strip()):
            cf.check_bounds_cause(bad, other, fixture)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="no bounds cause"):
        cf.check_bounds_cause(result, report, "tests/fixtures/regression/other")  # type: ignore[arg-type]


def test_side_bore_evidence_requires_both_z_bounds_to_be_loose() -> None:
    from arris_gym.fidelity import OracleReport

    fixture = Path("tests/fixtures/regression/cq-through-side-bore-cylinder-bounds")
    result = ag.run((fixture / "program.py").read_text(), dialect="cq")
    report = OracleReport.model_validate_json((fixture / "oracle.json").read_text())
    cf.check_bounds_cause(result, report, str(fixture))

    assert result.measures is not None
    assert report.measures is not None
    lo, hi = result.measures.bounds
    tightened = result.measures.model_copy(
        update={"bounds": (lo, (hi[0], hi[1], report.measures.bounds[1][2]))}
    )
    with pytest.raises(ValueError, match="both loose Z bounds"):
        cf.check_bounds_cause(
            result.model_copy(update={"measures": tightened}), report, str(fixture)
        )


def test_keyway_bound_evidence_requires_material_above_the_original_end_plane() -> None:
    from arris_gym.fidelity import OracleReport

    fixture = REGRESSION / "cq-keyway-through-filleted-rim-bounds"
    result = ag.run((fixture / "program.py").read_text(), dialect="cq")
    report = OracleReport.model_validate_json((fixture / "oracle.json").read_text())
    path = "tests/fixtures/regression/cq-keyway-through-filleted-rim-bounds"
    assert result.program_sha256 == report.program_sha256
    cf.check_bug_cause(result, report, path)
    assert result.measures is not None
    lo, hi = result.measures.bounds
    tightened = result.measures.model_copy(update={"bounds": (lo, (hi[0], 0.0, hi[2]))})
    with pytest.raises(ValueError, match="loose upper Y bound"):
        cf.check_bug_cause(result.model_copy(update={"measures": tightened}), report, path)


def test_the_chamfered_collar_is_what_arris_builds_and_what_the_family_flag_never_takes(
    tmp_path: Path,
) -> None:
    """`shaft_collar_004924`'s closed form: its parameters, in one cut (CadQuery's three are
    the same cylinder), meet arris's figures to ADR-0005's constants, and a row with that
    program's SHA-256 is `occt_wrong` by it whatever a `--arris-bug` family flag says."""
    import gzip

    from arris_gym.fidelity import FidelityTable, fidelity_table

    sha = next(iter(cf.COLLARS))
    p = cf.COLLARS[sha]
    text = (
        'import cadquery as cq\n\nresult = (\n    cq.Workplane("XY")\n'
        f"    .cylinder({p['h']}, {p['r']})\n"
        f'    .faces(">Z").workplane()\n    .hole({p["bore"]})\n'
        f'    .edges(">Z")\n    .chamfer({p["c"]})\n'
        '    .cut(\n        cq.Workplane("XY")\n'
        f"            .transformed(offset=cq.Vector(0.0, 0.0, {p['h'] / 2}), "
        "rotate=cq.Vector(90.0, 0.0, 0.0))\n"
        f"            .cylinder(41.83, {p['a']})\n    )\n)\n"
    )
    result = ag.run(text, dialect="cq")
    assert result.program_sha256 != sha  # one cut where the corpus writes three
    assert _agrees(result, cf.collar_closed_form(sha)) == []
    table = FidelityTable.model_validate_json(
        gzip.decompress((C2 / "benchcad" / "fidelity.json.gz").read_bytes())
    )
    row = next(e for e in table.entries if e.row.program_sha256 == sha)
    assert row.name.startswith("shaft_collar_")
    path = tmp_path / "fidelity.json.gz"
    path.write_bytes(gzip.compress(fidelity_table([row]).to_json().encode()))
    flag = {"shaft_collar": "tests/fixtures/regression/cq-cross-hole-bounds"}
    got = cf.verdicts_for(path, {row.name: ""}, {}, flag)
    assert {k: v["disagreement"] for k, v in got.items()} == {row.name: "occt_wrong"}


def test_an_arris_bug_row_is_classed_by_the_overlap_fixture_only_on_its_internal_error() -> None:
    from arris_gym.fidelity import OracleReport, OracleStatus
    from arris_gym.sandbox import Dialect, Versions

    fixture = "tests/fixtures/regression/cq-chamfers-overlap-on-a-face"
    refusal = ArrisRefusal(
        kind="OpInternalError",
        message="kernel bug: the face arrangement is not a subdivision: a hole of f14 lies",
        entities=(),
    )

    def result(refusal: ArrisRefusal | None, status: ag.Status) -> ag.ExecResult:
        return ag.ExecResult.model_construct(
            status=status,
            message="",
            refusal=refusal,
            body=None,
            measures=None,
            violations=(),
            program_sha256="0" * 64,
            dialect=Dialect.CQ,
            versions=Versions(arris="0", numpy="0", arris_gym="0"),
            seconds=0.0,
        )

    def oracle(status: OracleStatus) -> OracleReport:
        return OracleReport.model_construct(status=status, message="", measures=None)

    cf.check_bug_cause(
        result(refusal, ag.Status.ARRIS_REFUSAL), oracle(OracleStatus.INVALID), fixture
    )
    other = ArrisRefusal(kind="OpDegenerateError", message=refusal.message, entities=())
    for bad, report in (
        (result(refusal, ag.Status.ARRIS_REFUSAL), oracle(OracleStatus.OK)),
        (result(other, ag.Status.ARRIS_REFUSAL), oracle(OracleStatus.INVALID)),
        (result(None, ag.Status.OK), oracle(OracleStatus.INVALID)),
    ):
        with pytest.raises(ValueError, match=r"not invalid|internal error"):
            cf.check_bug_cause(bad, report, fixture)


# --- Rounds: `edges("|A").fillet(r)` and `faces(">A").fillet(r)` as solids (step 7) ---------

LOCATOR = """import cadquery as cq

result = (
    cq.Workplane("{plane}")
    .box(40.0, 60.0, 30.0)
    .faces(">{axis}")
{top}    .faces(">{axis}").workplane()
    .center(0.0, 0.0)
    .rect(50.0, 30.0)
    .cutBlind(-12.0)
    .faces("<{axis}").workplane()
    .pushPoints([(12.0, 24.0), (-12.0, 24.0), (12.0, -24.0), (-12.0, -24.0)])
    .hole(3.0)
    .faces("<{axis}").workplane()
    .circle(5.0)
    .cutBlind(-4.0)
{edges})

# Export
show_object(result)
"""
NORMALS = [("XY", "Z"), ("XZ", "Y"), ("YZ", "X")]


def test_a_round_takes_the_square_less_its_quarter_disc() -> None:
    r, h = 1.0, 10.0
    ops: list[cf.Op] = [
        ("+", cf.Cuboid((0.0, 0.0, 0.0), (4.0, 5.0, h))),
        ("-", cf.Round(2, (4.0, 5.0), (-1, -1), r, 0.0, h)),
        ("-", cf.Round(2, (0.0, 0.0), (1, 1), r, 0.0, h)),
    ]
    volume, area, _, _ = cf.part_measures(ops)
    taken = r * r * (1 - math.pi / 4)
    assert volume == pytest.approx(4 * 5 * h - 2 * taken * h, rel=1e-14)
    want = 2 * (20 - 2 * taken) + (18 - 4 * r) * h + 2 * (math.pi / 2) * r * h
    assert area == pytest.approx(want, rel=1e-14)


@pytest.mark.parametrize(("plane", "axis"), NORMALS)
@pytest.mark.parametrize(
    ("top", "edges"),
    [
        ("    .chamfer(1.5)\n", '    .edges("|{axis}")\n    .fillet(1.1)\n'),
        ("    .fillet(1.2)\n", ""),
    ],
    ids=["chamfered-top-filleted-edges", "filleted-top"],
)
def test_a_locator_block_is_what_arris_builds(plane: str, axis: str, top: str, edges: str) -> None:
    text = LOCATOR.format(plane=plane, axis=axis, top=top, edges=edges.format(axis=axis))
    assert _agrees(ag.run(text, dialect="cq"), cf.part_closed_form(text)) == []


def test_a_bore_into_a_concave_round_is_what_arris_builds() -> None:
    text = """import cadquery as cq

result = (
    cq.Workplane("XY")
    .box(60.0, 60.0, 40.0)
    .faces(">Z").workplane()
    .center(3.0, 3.0)
    .rect(54.0, 54.0)
    .cutThruAll()
    .edges("|Z")
    .fillet(2.0)
    .faces(">Z").workplane()
    .pushPoints([(-24.5, -27.0), (21.0, -27.0)])
    .hole(5.0)
)

# Export
show_object(result)
"""
    ops = cf.part_ops(text)
    assert [kind for kind, solid in ops if isinstance(solid, cf.Round)] == ["-"] * 5 + ["+"]
    assert _agrees(ag.run(text, dialect="cq"), cf.part_closed_form(text)) == []


def test_a_stadium_cut_and_a_turned_cylinder_are_what_arris_builds() -> None:
    text = """import cadquery as cq

result = (
    cq.Workplane("XY")
    .transformed(offset=cq.Vector(0, 0, 10.0), rotate=cq.Vector(0, 0, 0))
    .box(120.0, 40.0, 20.0)
    .union(
        cq.Workplane("XY")
            .transformed(offset=cq.Vector(0, 0, 30.0), rotate=cq.Vector(90, 0, 0))
            .cylinder(40.0, 18.0)
    )
    .cut(
        cq.Workplane("XY")
            .transformed(offset=cq.Vector(0, 0, 30.0), rotate=cq.Vector(90, 0, 0))
            .cylinder(44.0, 12.0)
    )
    .cut(
        cq.Workplane("XY")
            .transformed(offset=cq.Vector(-45.0, 0, 10.0), rotate=cq.Vector(0, 0, 0))
            .slot2D(16.0, 8.0, 0)
            .extrude(30.0, both=True)
    )
    .cut(
        cq.Workplane("XY")
            .transformed(offset=cq.Vector(0, 0, 20.0), rotate=cq.Vector(0, 0, 0))
            .cylinder(30.0, 2.5)
    )
)

# Export
show_object(result)
"""
    assert _agrees(ag.run(text, dialect="cq"), cf.part_closed_form(text)) == []


@pytest.mark.parametrize(
    ("change", "match"),
    [
        # a bore inside a round's square: a fillet this tool does not model
        (
            ("(12.0, 24.0), (-12.0, 24.0)", "(19.3, 29.3), (-12.0, 24.0)"),
            "meets another feature",
        ),
        # a bore through the faces the edge joins: straight edges this tool does not read
        (("(12.0, 24.0), (-12.0, 24.0)", "(19.0, 29.0), (-12.0, 24.0)"), "crossed by a face"),
        # two rounds of the top face's edges are only read on the stock
        (("    .circle(5.0)\n    .cutBlind(-4.0)\n", ""), None),
    ],
)
def test_a_round_this_tool_does_not_model_is_refused(
    change: tuple[str, str], match: str | None
) -> None:
    text = LOCATOR.format(
        plane="XY",
        axis="Z",
        top="    .chamfer(1.5)\n",
        edges='    .edges("|Z")\n    .fillet(1.1)\n',
    ).replace(*change)
    if "19.3" in change[1]:
        text = text.replace(".hole(3.0)", ".hole(0.6)")
    if match is None:
        cf.part_closed_form(text)
        return
    with pytest.raises(ValueError, match=match):
        cf.part_closed_form(text)


def _teeth(n: int, root: float, tip: float) -> str:
    """A toothed outline of n trapezoid teeth, as `polyline` points."""
    points = []
    for i in range(n):
        centre = 2 * math.pi * i / n
        for radius, half in ((root, 0.42), (tip, 0.22), (tip, -0.22), (root, -0.42)):
            angle = centre - half * 2 * math.pi / n
            points.append(f"({radius * math.cos(angle):.6f}, {radius * math.sin(angle):.6f})")
    return "[" + ", ".join(points) + "]"


def gear_text(plane: str, axis: str, ring: float, big: float) -> str:
    """A spur gear `gear_closed_form` reads: four holes on a circle of `ring`, a recess to `big`."""
    holes = "".join(
        f"""    .cut(
        cq.Workplane("{plane}")
            .transformed(offset=cq.Vector({x}, {y}, 4.0), rotate=cq.Vector(0, 0, 0))
            .cylinder(16.0, 1.8)
    )
"""
        for x, y in ((ring, 0.0), (0.0, ring), (-ring, 0.0), (-0.0, -ring))
    )
    return f"""import cadquery as cq

result = (
    cq.Workplane("{plane}")
    .polyline({_teeth(16, 19.0, 21.5)})
    .close()
    .extrude(8.0)
    .faces(">{axis}").workplane()
    .hole(6.0)
{holes}    .edges(">{axis}")
    .chamfer(0.4)
    .faces("<{axis}").workplane()
    .circle({big})
    .circle(3.0)
    .cutBlind(-1.5)
    .faces(">{axis}").workplane()
    .circle({big})
    .circle(3.0)
    .cutBlind(-1.5)
    .faces(">{axis}").workplane()
    .center(0.0, 2.0)
    .rect(1.6, 4.0)
    .cutThruAll()
)

# Export
show_object(result)
"""


@pytest.mark.parametrize(("plane", "axis"), NORMALS)
@pytest.mark.parametrize(("ring", "big"), [(12.0, 9.0), (11.0, 11.5)], ids=["apart", "recessed"])
def test_a_spur_gear_is_what_arris_builds(plane: str, axis: str, ring: float, big: float) -> None:
    text = gear_text(plane, axis, ring, big)
    assert _agrees(ag.run(text, dialect="cq"), cf.gear_closed_form(text)) == []


def test_a_recess_lens_is_two_circular_segments() -> None:
    area, moment, arc_big, arc_hole = cf._lens(1.0, 1.0, 1.0)
    assert area == pytest.approx(2 * math.pi / 3 - math.sqrt(3) / 2, rel=1e-15)
    assert moment == pytest.approx(area / 2, rel=1e-14)  # symmetric about the chord's midpoint
    assert arc_big == pytest.approx(2 * math.pi / 3, rel=1e-15)
    assert arc_hole == pytest.approx(2 * math.pi / 3, rel=1e-15)
    assert cf._lens(1.0, 0.25, 0.5)[0] == pytest.approx(math.pi / 16, rel=1e-15)
    assert cf._lens(1.0, 0.25, 2.0) == (0.0, 0.0, 0.0, 0.0)


def test_a_gear_whose_holes_meet_the_keyway_is_refused() -> None:
    text = gear_text("XY", "Z", 12.0, 9.0).replace(".rect(1.6, 4.0)", ".rect(1.6, 20.0)")
    with pytest.raises(ValueError, match="outside the arrangement"):
        cf.gear_closed_form(text)


@pytest.mark.parametrize(("plane", "axis"), NORMALS)
def test_a_cam_bore_into_its_boss_is_what_arris_builds(plane: str, axis: str) -> None:
    text = f"""import cadquery as cq

result = (
    cq.Workplane("{plane}")
    .polyline([(-10, -10), (10, -10), (10, 10), (-10, 10)])
    .close()
    .extrude(5)
    .union(
        cq.Workplane("{plane}")
            .transformed(offset=cq.Vector(0, 0, 7), rotate=cq.Vector(0, 0, 0))
            .cylinder(4, 5)
    )
    .faces(">{axis}").workplane()
    .hole(4)
    .faces(">{axis}")
    .edges()
    .chamfer(0.8)
    .faces("<{axis}")
    .edges()
    .chamfer(0.6)
    .faces(">{axis}").workplane()
    .pushPoints([(0.0, 2.0)])
    .rect(1, 2)
    .cutThruAll()
    .cut(
        cq.Workplane("{plane}")
            .transformed(offset=cq.Vector(5.2, 0.0, 2.5), rotate=cq.Vector(0, 0, 0))
            .cylinder({{depth}}, 0.75)
    )
)

# Export
show_object(result)
"""
    for depth in ("10", "12"):  # ends in the boss's straight side, and in its top chamfer
        program = text.replace("{depth}", depth)
        assert _agrees(ag.run(program, dialect="cq"), cf.cam_closed_form(program)) == []


FRAME = """import cadquery as cq

result = (
    cq.Workplane("{plane}")
    .rect(80.0, 30.0)
    .extrude(3.0)
    .faces(">{axis}").workplane()
    .rect(60.0, 14.0)
    .cutThruAll()
    .faces(">{axis}").workplane()
    .pushPoints([(34.0, 11.0), (-34.0, 11.0), (34.0, -11.0), (-34.0, -11.0)])
    .circle(1.5)
    .cutThruAll()
{notches}    .faces(">{axis}")
    .edges()
    .fillet(0.7)
    .faces("<{axis}")
    .edges()
    .fillet(0.6)
)

# Export
show_object(result)
"""
NOTCH = """    .cut(
        cq.Workplane("{plane}")
            .transformed(offset=cq.Vector(0.0, {v}, 0.0), rotate=cq.Vector(0, 0, 0))
            .box(20.0, 2.0, {depth})
    )
"""


@pytest.mark.parametrize(("plane", "axis"), NORMALS)
@pytest.mark.parametrize("depth", [None, "4.0", "7.0"], ids=["plain", "notched", "through"])
def test_a_rect_frame_is_what_arris_builds(plane: str, axis: str, depth: str | None) -> None:
    notches = (
        ""
        if depth is None
        else "".join(NOTCH.format(plane=plane, v=v, depth=depth) for v in ("15.0", "-15.0"))
    )
    text = FRAME.format(plane=plane, axis=axis, notches=notches)
    assert _agrees(ag.run(text, dialect="cq"), cf.frame_closed_form(text)) == []


@pytest.mark.parametrize("outline", ["moveTo", "polygon"])
def test_a_hex_nut_is_what_arris_builds(outline: str) -> None:
    shape = (
        "    .polygon(6, 12.0)\n"
        if outline == "polygon"
        else "    .moveTo(6.0, 0.0)\n"
        + "".join(
            f"    .lineTo({6 * math.cos(k * math.pi / 3):.4f}, "
            f"{6 * math.sin(k * math.pi / 3):.4f})\n"
            for k in range(1, 6)
        )
        + "    .close()\n"
    )
    text = f"""import cadquery as cq

result = (
    cq.Workplane("XY")
{shape}    .extrude(5.0)
    .faces(">Z").workplane()
    .circle(3.0)
    .cutThruAll()
    .faces("<Z")
    .edges()
    .fillet(0.6)
)

# Export
show_object(result)
"""
    assert _agrees(ag.run(text, dialect="cq"), cf.nut_closed_form(text)) == []


@pytest.mark.parametrize(("plane", "axis"), NORMALS)
def test_a_flanged_spur_gear_is_what_arris_builds(plane: str, axis: str) -> None:
    def ring(kind: str, height: float, radius: float) -> str:
        return f"""    .{kind}(
        cq.Workplane("{plane}")
            .transformed(offset=cq.Vector(0, 0, 10.6), rotate=cq.Vector(0, 0, 0))
            .cylinder({height}, {radius})
    )
"""

    text = f"""import cadquery as cq

result = (
    cq.Workplane("{plane}")
    .polyline({_teeth(16, 19.0, 21.5)})
    .close()
    .extrude(10.0)
    .faces(">{axis}").workplane()
    .hole(4.0)
    .edges(">{axis}")
    .chamfer(0.5)
    .faces(">{axis}").workplane()
    .center(0.0, 1.5)
    .rect(1.0, 3.0)
    .cutThruAll()
{ring("union", 1.9, 23.0)}{ring("cut", 3.8, 15.0)}{ring("union", 1.9, 4.0)}{ring("cut", 3.8, 2.0)})

# Export
show_object(result)
"""
    assert _agrees(ag.run(text, dialect="cq"), cf.flanged_gear_closed_form(text)) == []


def test_a_corner_patch_is_by_design_only_where_both_kernels_built_one_part() -> None:
    from arris_gym.fidelity import OracleMeasures, OracleReport, OracleStatus, OracleVersions
    from arris_gym.sandbox import BodyRef, Dialect, Measures, Status, Versions

    measures = Measures(
        volume=1000.0,
        area=600.0,
        centroid=(0.0, 0.0, 5.0),
        bounds=((-5.0, -5.0, 0.0), (5.0, 5.0, 10.0)),
        faces=30,
        shells=1,
        genus=0,
        face_kinds=(("plane", 30),),
    )

    def oracle(area: float, solids: int = 1) -> OracleReport:
        return OracleReport(
            status=OracleStatus.OK,
            message="",
            measures=OracleMeasures(
                volume=1000.0,
                area=area,
                centroid=(0.0, 0.0, 5.0),
                bounds=((-5.0, -5.0, 0.0), (5.0, 5.0, 10.0)),
                faces=29,
                solids=solids,
            ),
            step_sha256="5" * 64,
            program_sha256="0" * 64,
            versions=OracleVersions(cadquery="2.3.0", ocp="7.9.3.0", python="3.12.3"),
        )

    result = ag.ExecResult(
        status=Status.OK,
        message="",
        refusal=None,
        body=BodyRef.of(b"body"),
        measures=measures,
        violations=(),
        program_sha256="0" * 64,
        dialect=Dialect.CQ,
        versions=Versions(arris="0", numpy="0", arris_gym="0"),
        seconds=0.0,
    )
    cf.check_by_design_cause(result, oracle(600.0005))  # 8.3e-7 apart, as a patch moves it
    with pytest.raises(ValueError, match="further apart"):
        cf.check_by_design_cause(result, oracle(601.0))
    with pytest.raises(ValueError, match="several solids"):
        cf.check_by_design_cause(result, oracle(600.0005, solids=2))


_DOME_PROGRAM = """import cadquery as cq

result = (
    cq.Workplane("XY")
    .moveTo(0.0, 0.0)
    .lineTo(10.0, 0.0)
    .lineTo(10.0, 10.0)
    .threePointArc((6.0, 18.0), (0.0, 20.0))
    .close()
    .revolve(360, (0, 0, 0), (0, 1, 0))
    {pocket}
    .faces("<Y").workplane()
    .polarArray(5, 0, 360, 4)
    .hole(2)
    {blend}
)
"""


@pytest.mark.parametrize(
    ("pocket_radius", "blend"),
    [(0, ""), (5, ""), (8, ".chamfer(0.5)"), (0, ".fillet(0.5)")],
)
def test_dome_closed_form_covers_pocket_overlap_and_rim_blends(
    pocket_radius: int, blend: str
) -> None:
    pocket = (
        f'.faces("<Y").workplane().circle({pocket_radius}).cutBlind(-2)' if pocket_radius else ""
    )
    finishing = f'.faces("<Y").edges(){blend}' if blend else ""
    program = _DOME_PROGRAM.format(pocket=pocket, blend=finishing)
    result = ag.run(program, dialect="cq")
    assert result.status is ag.Status.OK, result.message
    assert _agrees(result, cf.dome_closed_form(program)) == []


def test_clipped_bellows_bound_uses_circle_intersections_at_both_rims() -> None:
    program = """import cadquery as cq

result = (
    cq.Workplane("XY")
    .polyline([(1, 0), (6, 0), (10, 0), (10, 2), (6, 2), (3, 3), (6, 4),
               (10, 6), (6, 6), (1, 6), (1, 0)])
    .close()
    .revolve(360, (0, 0, 0), (0, 1, 0))
    .faces(">Y").workplane().polarArray(10, 0, 360, 2).circle(2).cutBlind(-2)
    .faces("<Y").workplane().polarArray(10, 0, 360, 2).circle(2).cutBlind(-2)
)
"""
    lo, hi = cf._clipped_bellows_bounds(program)
    assert lo == pytest.approx((-9.8, 0, -10))
    assert hi == pytest.approx((9.8, 6, 10))
    with pytest.raises(ValueError, match="do not remove the two outer rims"):
        cf._clipped_bellows_bounds(program.replace(".cutBlind(-2)", ".cutBlind(-1)", 1))


def test_measure_replay_covers_every_listed_stem_with_the_expected_evidence() -> None:
    root = C2 / "benchcad"
    stems = (root / "measure-replay.txt").read_text().splitlines()
    verdicts = json.loads((root / "measure-verdicts.json").read_text())
    expected = {
        "bellows": (40, "arris_bug", "fixture"),
        "shaft_collar": (11, "arris_bug", "fixture"),
        "dome_cap": (25, "occt_wrong", "closed_form"),
        "torus_link": (3, "occt_wrong", "closed_form"),
    }
    assert stems == sorted(verdicts)
    for family, (count, disagreement, kind) in expected.items():
        entries = [
            Verdict.model_validate(v)
            for stem, v in verdicts.items()
            if re.fullmatch(rf"{family}_\d+_s\d+", stem)
        ]
        assert len(entries) == count
        assert all(
            v.disagreement.value == disagreement and v.evidence.kind == kind for v in entries
        )
    assert len(stems) == sum(count for count, _, _ in expected.values())

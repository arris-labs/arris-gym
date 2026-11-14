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


@pytest.mark.parametrize("corpus", ["benchcad", "cadrecode"])
def test_each_committed_verdict_rests_on_evidence_that_exists(corpus: str) -> None:
    raw = json.loads((C2 / corpus / "verdicts.json").read_text(encoding="utf-8"))
    assert raw, corpus
    for stem, value in raw.items():
        verdict = Verdict.model_validate(value)
        if verdict.disagreement is DisagreementClass.OCCT_WRONG:
            assert isinstance(verdict.evidence, ClosedForm), stem
        else:
            assert verdict.disagreement is DisagreementClass.ARRIS_REFUSAL, stem
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

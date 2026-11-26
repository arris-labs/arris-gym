"""Closed forms and pinned oracle evidence for ADR-0029's shell probes."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

import arris_gym as ag
import fixture_cases
from arris_gym.cq._selector import Edges, Faces
from arris_gym.fidelity import (
    ClosedForm,
    DisagreementClass,
    FidelityOutcome,
    OracleMeasures,
    OracleReport,
    OracleStatus,
    Verdict,
    compare,
)
from arris_gym.fidelity._agreement import figures_agree
from oracle_run import run_many

ROOT = fixture_cases.ROOT / "shells"
CASES = fixture_cases.load("shells")
ORACLE_FAILURES = {
    "compound": (OracleStatus.RUNTIME, "BRep_API: command not done"),
    "compound-one": (OracleStatus.RUNTIME, "BRep_API: command not done"),
    "compound-sealed": (OracleStatus.RUNTIME, "BRep_API: command not done"),
    "sealed-again": (OracleStatus.RUNTIME, "BRep_API: command not done"),
    "zero": (OracleStatus.RUNTIME, "BRep_API: command not done"),
    "infinite": (OracleStatus.RUNTIME, "gce_MakePln::Value() - no result"),
    "nan": (OracleStatus.TIMEOUT, "the oracle worker ran past the 30.0 s deadline"),
    "missing": (
        OracleStatus.RUNTIME,
        "ValueError: Cannot find a solid on the stack or in the parent chain",
    ),
}
RIMS = tuple(case for case in CASES if case.slug.startswith("rim-"))


def _oracle(directory: Path) -> OracleReport:
    report = OracleReport.model_validate_json((directory / "oracle.json").read_text())
    assert (
        report.program_sha256 == hashlib.sha256((directory / "oracle.py").read_bytes()).hexdigest()
    )
    assert report.versions is None or report.versions.cadquery == "2.3.0"
    assert report.versions is None or report.versions.ocp == "7.9.3.0"
    return report


def _check_oracle_measures(report: OracleReport, expected: object) -> None:
    assert report.status is OracleStatus.OK
    got = report.measures
    assert got is not None
    want = OracleMeasures.model_validate(expected)
    assert (got.faces, got.solids) == (want.faces, want.solids)
    for measured, analytic in zip(
        (got.volume, got.area, *got.centroid, *got.bounds[0], *got.bounds[1]),
        (want.volume, want.area, *want.centroid, *want.bounds[0], *want.bounds[1]),
        strict=True,
    ):
        assert fixture_cases.close(measured, analytic)


def _oracle_fields(expected: object) -> dict[str, object]:
    assert isinstance(expected, dict)
    return {name: expected[name] for name in OracleMeasures.model_fields}


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.slug)
def test_shell_in_arris_dialect(case: fixture_cases.Case) -> None:
    result = fixture_cases.run(case)
    assert fixture_cases.check(result, case.expected) == []
    if result.measures is not None:
        want = _oracle_fields(case.expected["measures"])
        assert result.measures.solids == want["solids"]
        if case.slug not in ORACLE_FAILURES:
            report = _oracle(ROOT / case.slug)
            _check_oracle_measures(report, want)
            if case.slug.startswith("rim-"):
                reference = OracleMeasures.model_validate(want)
                verdict = Verdict(
                    disagreement=DisagreementClass.OCCT_WRONG,
                    evidence=ClosedForm(
                        **reference.model_dump(exclude={"faces", "solids"}),
                        note="Integral of the rectangular slices, tests/fixtures/shells/README.md.",
                    ),
                )
                assert compare(result, report, verdict).disagreement is DisagreementClass.OCCT_WRONG
            else:
                assert compare(result, report).outcome is FidelityOutcome.AGREE


@pytest.mark.parametrize("name", ORACLE_FAILURES)
def test_oracle_shell_failure(name: str) -> None:
    report = _oracle(ROOT / name)
    status, message = ORACLE_FAILURES[name]
    assert report.status is status
    assert report.message.endswith(message)


def test_oracle_excessive_thickness_returns_the_original_box() -> None:
    report = _oracle(ROOT / "too-thick")
    _check_oracle_measures(
        report,
        dict(
            volume=480,
            area=376,
            centroid=(0, 0, 0),
            bounds=((-5, -4, -3), (5, 4, 3)),
            faces=6,
            solids=1,
        ),
    )


@pytest.mark.parametrize(
    "name", ["shell-outward-arc", "shell-inward-reentrant-arc", "shell-pending-wire"]
)
def test_regression_geometry_on_the_oracle(name: str) -> None:
    directory = fixture_cases.ROOT / "regression" / name
    expected = json.loads((directory / "expected.json").read_text())
    _check_oracle_measures(_oracle(directory), _oracle_fields(expected["measures"]))


def test_oracle_measures_the_chamfered_rim_by_construction(request: pytest.FixtureRequest) -> None:
    directory = fixture_cases.ROOT / "regression" / "oracle-shell-chamfered-rim-volume"
    report = _oracle(directory)
    assert report.status is OracleStatus.OK
    assert report.measures is not None
    expected = ClosedForm.model_validate_json((directory / "closed-form.json").read_text())
    request.node.add_marker(
        pytest.mark.xfail(
            reason="The oracle's shelled chamfer volume differs from the section integral.",
            raises=AssertionError,
            strict=True,
        )
    )
    assert figures_agree(report.measures, expected)


@pytest.mark.oracle
def test_oracle_step_encodes_the_constructed_tray_rims() -> None:
    programs = [(ROOT / case.slug / "oracle.py").read_text() for case in RIMS]
    for report, case in zip(run_many(programs, workers=3), RIMS, strict=True):
        assert report.status is OracleStatus.OK
        assert report.step is not None
        target = ag.read_target(report.step)
        assert target.status is ag.Status.OK
        assert target.measures is not None
        expected = OracleMeasures.model_validate(_oracle_fields(case.expected["measures"]))
        assert figures_agree(target.measures, expected)
        assert (target.measures.faces, target.measures.solids) == (expected.faces, expected.solids)


def _cq_program(path: Path) -> str:
    return path.read_text().replace("import cadquery as cq", "import arris_gym.cq as cq")


def _shell_expected(result: ag.ExecResult, expected: dict[str, object]) -> None:
    assert fixture_cases.check(result, {**expected, "dialect": "cq"}) == []
    measures = expected.get("measures")
    if isinstance(measures, dict):
        assert result.measures is not None
        assert result.measures.solids == measures["solids"]


@pytest.mark.parametrize(
    "name",
    ["inward", "sealed", "edge-stack", "bore", "cylinder", "zero", "infinite", "nan", "too-thick"],
)
def test_shell_form_reuses_the_verified_construction(name: str) -> None:
    directory = ROOT / name
    result = ag.run(_cq_program(directory / "oracle.py"), dialect="cq")
    _shell_expected(result, json.loads((directory / "expected.json").read_text()))
    if result.status is ag.Status.OK:
        assert compare(result, _oracle(directory)).outcome is FidelityOutcome.AGREE


@pytest.mark.parametrize(
    ("call", "status", "message"),
    [
        (
            "shell(-1)",
            ag.Status.RUNTIME,
            "ValueError: Cannot find a solid on the stack or in the parent chain",
        ),
        ("shell()", ag.Status.UNSUPPORTED_API, "Workplane.shell()"),
        ("shell(True)", ag.Status.UNSUPPORTED_API, "Workplane.shell(bool)"),
        ("shell('-1')", ag.Status.UNSUPPORTED_API, "Workplane.shell(str)"),
        ("shell(-1, 'arc')", ag.Status.UNSUPPORTED_API, "Workplane.shell(num, str)"),
        (
            "shell(-1, kind='intersection')",
            ag.Status.UNSUPPORTED_API,
            "Workplane.shell(num; kind=str)",
        ),
        ("shell(thickness=-1)", ag.Status.UNSUPPORTED_API, "Workplane.shell(thickness=num)"),
    ],
)
def test_shell_wrong_forms_and_missing_stock(call: str, status: ag.Status, message: str) -> None:
    result = ag.run(f'import arris_gym.cq as cq\nresult = cq.Workplane("XY").{call}', dialect="cq")
    assert result.status is status
    assert result.message == message
    assert result.measures is None


def test_shell_does_not_inherit_an_opening_from_its_parent() -> None:
    directory = ROOT / "parent-selection"
    result = ag.run(_cq_program(directory / "oracle.py"), dialect="cq")
    _shell_expected(result, json.loads((ROOT / "sealed" / "expected.json").read_text()))
    assert compare(result, _oracle(directory)).outcome is FidelityOutcome.AGREE


def test_shell_opens_both_faces_of_a_tied_selection() -> None:
    directory = ROOT / "adjacent-selected"
    result = ag.run(_cq_program(directory / "oracle.py"), dialect="cq")
    assert result.status is ag.Status.OK
    assert result.measures is not None
    # Opening the two adjacent sides of the 8 by 8 by 6 stock removes a
    # 7 by 7 by 4 cavity centred at (0.5, -0.5, 0) before the 45-degree turn.
    cavity = 7 * 7 * 4
    volume = 8 * 8 * 6 - cavity
    span = 4 * math.sqrt(2)
    # The cavity's side walls replace the openings with equal area.
    area = 2 * (8 * 8 + 2 * 8 * 6) + 2 * 7 * 7
    _shell_expected(
        result,
        {
            "status": "ok",
            "measures": {
                "volume": volume,
                "area": area,
                "centroid": [-cavity / (math.sqrt(2) * volume), 0, 0],
                "bounds": [[-span, -span, -3], [span, span, 3]],
                "faces": 10,
                "shells": 1,
                "solids": 1,
                "genus": 0,
                "face_kinds": [["plane", 10]],
            },
        },
    )
    assert compare(result, _oracle(directory)).outcome is FidelityOutcome.AGREE


@pytest.mark.parametrize(
    "chain", ['.faces(">Z").shell(-1)', ".shell(-1)", '.shell(-1).faces(">Z").shell(-0.25)']
)
def test_shell_refuses_multiple_boundary_shells(chain: str) -> None:
    program = 'import arris_gym.cq as cq\nstock = cq.Workplane("XY").box(10, 8, 6)\n'
    if not chain.startswith(".shell(-1)."):
        program += 'stock = stock.union(cq.Workplane("XY", origin=(14, 0, 0)).box(10, 8, 6))\n'
    result = ag.run(program + f"result = stock{chain}\n", dialect="cq")
    assert result.status is ag.Status.RUNTIME
    assert result.message == "RuntimeError: BRep_API: command not done"


ARC_GAPS = {
    "shell-outward-arc": "Workplane.shell with outward arc joins",
    "shell-inward-reentrant-arc": "Workplane.shell on stock without verified inward joins",
}


@pytest.mark.parametrize("name", ARC_GAPS)
def test_shell_refuses_where_arc_and_sharp_joins_differ(name: str) -> None:
    directory = fixture_cases.ROOT / "regression" / name
    result = ag.run(_cq_program(directory / "oracle.py"), dialect="cq")
    assert result.status is ag.Status.UNSUPPORTED_API
    assert result.message == ARC_GAPS[name]


@pytest.mark.parametrize("pending", ["circle(1)", "moveTo(0, 0).lineTo(1, 0)"])
def test_shell_refuses_to_discard_a_pending_wire_or_drawn_path(pending: str) -> None:
    result = ag.run(
        'import arris_gym.cq as cq\nstock = cq.Workplane("XY").box(10, 8, 6)\n'
        f'result = stock.faces(">Z").workplane().{pending}.shell(-1)\n',
        dialect="cq",
    )
    assert result.status is ag.Status.UNSUPPORTED_API
    assert result.message == "Workplane.shell on a pending wire or drawn path"


@pytest.mark.parametrize(
    ("case", "plane", "axis", "length", "width", "height", "chamfer", "thickness"),
    [
        (RIMS[0], "XY", 2, 56.16, 47.01, 32.82, 0.42, 1.93),
        (RIMS[1], "XZ", 1, 235.97, 41.54, 39.03, 0.96, 3.83),
        (RIMS[2], "YZ", 0, 202.1, 152.09, 48.39, 0.69, 1.85),
    ],
    ids=["rim-xy", "rim-xz", "rim-yz"],
)
def test_shell_keeps_the_chamfered_opening(
    case: fixture_cases.Case,
    plane: str,
    axis: int,
    length: float,
    width: float,
    height: float,
    chamfer: float,
    thickness: float,
) -> None:
    selector = ">" + "XYZ"[axis]
    stock = f'cq.Workplane("{plane}").box({length}, {width}, {height})'
    program = f'import arris_gym.cq as cq\nstock = {stock}.edges("{selector}").chamfer({chamfer})\n'
    program += f'selected = stock.faces("{selector}")\nresult = selected.shell(-{thickness})\n'
    result = ag.run(program, dialect="cq")
    _shell_expected(result, case.expected)

    # Use the public selectors to inspect the original face, then both rim loops.
    stock_face = ag.cq.Workplane(plane).box(length, width, height).edges(selector).chamfer(chamfer)
    selected = stock_face.faces(selector)
    rim = selected.shell(-thickness).faces(selector)
    outer = (length - 2 * chamfer, width - 2 * chamfer)
    inner = tuple(span - 2 * math.sqrt(2) * thickness for span in outer)
    for workplane, spans, area in (
        (selected, outer, math.prod(outer)),
        (rim, (*outer, *inner), math.prod(outer) - math.prod(inner)),
    ):
        (faces,) = workplane._stack
        assert isinstance(faces, Faces)
        ((face,),) = faces.groups
        model = faces.solid.model
        assert fixture_cases.close(model.surface_properties(face).area, area)
        assert fixture_cases.close(workplane.workplane()._plane.origin[axis], height / 2)
        (edges,) = workplane.edges()._stack
        assert isinstance(edges, Edges)
        curves = [model.curve(edge) for edge in edges.edges]
        want = sorted(2 * list(spans))
        assert len(curves) == len(want)
        assert all(curve.kind == "line" for curve in curves)
        for got, expected in zip(
            sorted(math.dist(curve.start, curve.end) for curve in curves), want, strict=True
        ):
            assert fixture_cases.close(got, expected)


@given(
    length=st.integers(5, 40),
    width=st.integers(5, 40),
    height=st.integers(5, 40),
    quarter_units=st.integers(1, 8),
    named_plane=st.sampled_from([("XY", 2), ("XZ", 1), ("YZ", 0), ("ZX", 1)]),
    sign=st.sampled_from([-1, 1]),
)
def test_inward_box_shell_preserves_the_plane_and_original_branch(
    length: int,
    width: int,
    height: int,
    quarter_units: int,
    named_plane: tuple[str, int],
    sign: int,
) -> None:
    plane, axis = named_plane
    thickness = quarter_units / 4
    selector = ("<" if sign < 0 else ">") + "XYZ"[axis]
    stock = ag.cq.Workplane(plane).box(length, width, height)
    selected = stock.faces(selector)
    cup = selected.shell(-thickness)

    assert cup._parent is selected
    assert cup._plane == selected._plane
    program = (
        "import arris_gym.cq as cq\n"
        f"stock = cq.Workplane({plane!r}).box({length}, {width}, {height})\n"
        f"result = stock.faces({selector!r}).shell(-{thickness})\n"
    )
    result = ag.run(program, dialect="cq")
    assert result.status is ag.Status.OK
    got = result.measures
    assert got is not None
    assert (got.faces, got.shells, got.solids) == (11, 1, 1)
    inside_length, inside_width = length - 2 * thickness, width - 2 * thickness
    inside_height = height - thickness
    cavity = inside_length * inside_width * inside_height
    volume = length * width * height - cavity
    outside_area = 2 * (length * width + height * (length + width))
    area = outside_area + 2 * inside_height * (inside_length + inside_width)
    assert fixture_cases.close(got.volume, volume)
    assert fixture_cases.close(got.area, area)
    for i, part in enumerate(got.centroid):
        expected = -sign * cavity * thickness / (2 * volume) if i == axis else 0
        assert fixture_cases.close(part, expected)

    # The original selection still supplies the opening on a sibling branch.
    (sibling,) = selected.shell(-thickness / 2)._solids()
    assert len(sibling.model.faces(sibling.body)) == 11
    assert sibling.measure().volume < got.volume
    assert fixture_cases.close(stock._solids()[0].measure().volume, length * width * height)
    for workplane, count in ((selected, 4), (cup.faces(selector), 8), (cup, 24)):
        (edges,) = workplane.edges()._stack
        assert isinstance(edges, Edges)
        assert len(edges.edges) == count

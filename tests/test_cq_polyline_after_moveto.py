# ruff: noqa: E501  (the corpus programs below are quoted as written)
"""`polyline` after a lone `moveTo` point is `polyline` alone.

Read on the oracle (CadQuery 2.3.0, `ok-polyline-after-moveto-*` beside their
`oracle.json`): `polyline` starts at its first point (`includeCurrent=False`)
and leaves no trace of the `moveTo` point, which is no pending wire. After a
drawn path or another polyline it is another matter: CadQuery joins the edges,
and the oracle's answer is `invalid` (`unsupported-polyline-after-drawn-path`),
so those stay refused. Every other call after the polyline meets the stack
`polyline` alone leaves, which the subset already runs or refuses.
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import arris_gym as ag
import fixture_cases
from arris_gym.fidelity import FidelityOutcome, OracleReport, OracleStatus, compare

AGREEING = [
    "ok-polyline-after-moveto-triangle",
    "ok-polyline-after-moveto-fused",
    "ok-polyline-after-moveto-pentagon-both",
    "ok-polyline-after-moveto-u-bolt-base",
]


def _case(slug: str) -> fixture_cases.Case:
    return next(c for c in fixture_cases.load("cq") if c.slug == slug)


def _report(slug: str) -> OracleReport:
    path = fixture_cases.ROOT / "cq" / slug / "oracle.json"
    return OracleReport.model_validate_json(path.read_text())


@pytest.mark.parametrize("slug", AGREEING)
def test_each_fixture_agrees_with_the_recorded_oracle(slug: str) -> None:
    case = _case(slug)
    assert ".moveTo(" in case.program
    assert compare(fixture_cases.run(case), _report(slug)).outcome is FidelityOutcome.AGREE


def test_the_oracle_joins_a_polyline_to_a_drawn_path() -> None:
    # The oracle answers `invalid` and a part that is not the polyline's, so
    # `cq` refuses the call rather than builds either.
    report = _report("unsupported-polyline-after-drawn-path")
    assert report.status is OracleStatus.INVALID
    result = fixture_cases.run(_case("unsupported-polyline-after-drawn-path"))
    assert result.status is ag.Status.UNSUPPORTED_API


U_BOLT = """\
import cadquery as cq

result = (
    cq.Workplane("XY")
    .transformed(offset=cq.Vector(42.59, 0.0, 39.183749999999996), rotate=cq.Vector(0, 0, 0))
    .cylinder(87.987, 6.015)
    .union(
        cq.Workplane("XY")
            .transformed(offset=cq.Vector(-42.59, 0.0, 39.183749999999996), rotate=cq.Vector(0, 0, 0))
            .cylinder(87.987, 6.015)
    )
    .union(
        cq.Workplane("XY")
            .transformed(offset=cq.Vector(0, 0, 80.17), rotate=cq.Vector(0, 0, 0))
            .moveTo(42.59, 0.0)
            .circle(6.015)
            .revolve(180, (0, 0, 0), (0, -1, 0))
    )
    .union(
        cq.Workplane("XY")
            .transformed(offset=cq.Vector(0, 0, -2.405), rotate=cq.Vector(0, 0, 0))
            .box(121.25, 26.46, 4.81)
    )
    .union(
        cq.Workplane("XY")
            .transformed(offset=cq.Vector(-42.59, 0.0, -9.11), rotate=cq.Vector(0, 0, 0))
            .moveTo(7.7942, 4.5)
            .polyline([[0.0, 9.0], [-7.7942, 4.5], [-7.7942, -4.5], [-0.0, -9.0], [7.7942, -4.5]])
            .close()
            .extrude(4.8, both=True)
    )
    .union(
        cq.Workplane("XY")
            .transformed(offset=cq.Vector(42.59, 0.0, -9.11), rotate=cq.Vector(0, 0, 0))
            .moveTo(7.7942, 4.5)
            .polyline([[0.0, 9.0], [-7.7942, 4.5], [-7.7942, -4.5], [-0.0, -9.0], [7.7942, -4.5]])
            .close()
            .extrude(4.8, both=True)
    )
)

# Export
show_object(result)
"""

J_HOOK = """\
import cadquery as cq

result = (
    cq.Workplane("XY")
    .transformed(offset=cq.Vector(38.5, 0.0, 59.120000000000005), rotate=cq.Vector(0, 0, 0))
    .cylinder(127.84, 6.0)
    .union(
        cq.Workplane("XY")
            .transformed(offset=cq.Vector(0, 0, 120.04), rotate=cq.Vector(0, 0, 0))
            .moveTo(38.5, 0.0)
            .circle(6.0)
            .revolve(180, (0, 0, 0), (0, -1, 0))
    )
    .union(
        cq.Workplane("XY")
            .transformed(offset=cq.Vector(38.5, 0, -2.4), rotate=cq.Vector(0, 0, 0))
            .box(42.0, 42.0, 4.8)
    )
    .union(
        cq.Workplane("XY")
            .transformed(offset=cq.Vector(38.5, 0.0, -9.1), rotate=cq.Vector(0, 0, 0))
            .moveTo(7.7942, 4.5)
            .polyline([[0.0, 9.0], [-7.7942, 4.5], [-7.7942, -4.5], [-0.0, -9.0], [7.7942, -4.5]])
            .close()
            .extrude(4.8, both=True)
    )
)

# Export
show_object(result)
"""


@pytest.mark.parametrize(
    ("program", "x", "z"),
    [(U_BOLT, (-60.625, 60.625), (-13.91, 128.775)), (J_HOOK, (-44.5, 59.5), (-13.9, 164.54))],
    ids=["u_bolt", "j_hook"],
)
def test_the_corpus_programs_as_written_are_one_solid_with_the_nuts_underneath(
    program: str, x: tuple[float, float], z: tuple[float, float]
) -> None:
    # BenchCAD's u_bolt and j_hook write the nut as moveTo(...).polyline(...).
    # Their volumes wait for the closed form of the hook rows (the oracle's
    # half torus is off); the bounds follow from how the parts are built.
    result = ag.run(program, dialect="cq")
    assert result.status is ag.Status.OK, result.message
    assert result.measures is not None
    assert result.measures.shells == 1
    assert fixture_cases.close(result.measures.bounds[0][0], x[0])
    assert fixture_cases.close(result.measures.bounds[1][0], x[1])
    assert fixture_cases.close(result.measures.bounds[0][2], z[0])
    assert fixture_cases.close(result.measures.bounds[1][2], z[1])


@settings(max_examples=30, deadline=None)
@given(
    start=st.tuples(st.integers(-9, 9), st.integers(-9, 9)),
    a=st.integers(1, 9),
    b=st.integers(1, 9),
    height=st.integers(1, 9),
    both=st.booleans(),
)
def test_the_move_to_point_leaves_no_trace(
    start: tuple[int, int], a: int, b: int, height: int, both: bool
) -> None:
    tail = f".polyline([(0, 0), ({a}, 0), (0, {b})]).close().extrude({height}, both={both})"

    def body(point: str) -> str:
        text = f"import cadquery as cq\nshow_object(cq.Workplane('XY'){point}{tail})\n"
        result = ag.run(text, dialect="cq")
        assert result.body is not None, result.message
        return result.body.sha256

    assert body(f".moveTo({start[0]}, {start[1]})") == body("")

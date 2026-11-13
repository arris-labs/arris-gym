"""`sphere` is centred on its point, its poles on the plane's normal.

Read on the oracle (CadQuery 2.3.0, `ok-sphere-*` beside their `oracle.json`):
`Workplane.sphere(radius)` places one sphere at each point of the stack with
`centered=True`, on the origin of an empty stack or on a `moveTo` point;
after `transformed` or `workplane(offset=…)` the point is on the moved plane,
and a solid in the chain is fused with it (`combine=True`). `cq` builds it as
a half disc revolved a full turn about the normal: one spherical face, as
Open CASCADE's `makeSphere` has.
"""

import math
import pathlib
import re

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import arris_gym as ag
import arris_gym.cq as cq
import fixture_cases
from arris_gym.census import CorpusProgram, reach
from arris_gym.fidelity import (
    DisagreementClass,
    DocAnchor,
    FidelityOutcome,
    OracleReport,
    OracleStatus,
    Verdict,
    compare,
    program_sha256,
)

PLANES = ["XY", "YZ", "XZ", "ZX"]
FIXTURES = [
    "ok-sphere-centred-xy",
    "ok-sphere-at-point-xz",
    "ok-sphere-at-point-origin-yz",
    "ok-sphere-transformed-zx",
    "ok-sphere-fused-at-point-xy",
    "ok-sphere-capsule",
]
# The other last objects the subset puts on a stack, read on the oracle
# (2026-11-13): CadQuery builds a sphere on each, centred on the object's
# `Center()`, which the subset does not model; `cq` refuses each.
CONTEXTS = {
    "unsupported-sphere-on-solid": "Workplane.sphere on a stack holding a solid",
    "unsupported-sphere-on-compound": "Workplane.sphere on a stack holding a solid",
    "unsupported-sphere-on-closed-wire": "Workplane.sphere on a pending wire",
    "unsupported-sphere-on-pending-wire": "Workplane.sphere on a pending wire",
    "unsupported-sphere-on-pending-circle": "Workplane.sphere on a pending wire",
}


@pytest.mark.parametrize("slug", FIXTURES)
def test_sphere_fixtures_agree_with_the_recorded_oracle(slug: str) -> None:
    case = next(c for c in fixture_cases.load("cq") if c.slug == slug)
    assert "sphere(" in case.program
    path = fixture_cases.ROOT / "cq" / slug / "oracle.json"
    report = OracleReport.model_validate_json(path.read_text())
    assert compare(fixture_cases.run(case), report).outcome is FidelityOutcome.AGREE


@pytest.mark.parametrize("slug", FIXTURES)
def test_the_oracle_holds_each_spheres_closed_form(slug: str) -> None:
    # The semantics are CadQuery's, not only `cq`'s reading of them: the
    # oracle's own measures meet the closed form in `expected.json`.
    case = next(c for c in fixture_cases.load("cq") if c.slug == slug)
    expected = case.expected["measures"]
    assert isinstance(expected, dict)
    path = fixture_cases.ROOT / "cq" / slug / "oracle.json"
    measures = OracleReport.model_validate_json(path.read_text()).measures
    assert measures is not None
    assert fixture_cases.close(measures.volume, expected["volume"])
    assert fixture_cases.close(measures.area, expected["area"])
    assert measures.faces == expected["faces"]
    for got, want in zip(measures.centroid, expected["centroid"], strict=True):
        assert fixture_cases.close(got, want)
    for got_corner, want_corner in zip(measures.bounds, expected["bounds"], strict=True):
        for got, want in zip(got_corner, want_corner, strict=True):
            assert fixture_cases.close(got, want)


def _world(plane: str, u: float, v: float, w: float) -> list[float]:
    """Local (u, v, w) on a named plane at the world origin, in world coordinates."""
    if plane == "XY":
        return [u, v, w]
    if plane == "YZ":
        return [w, u, v]
    if plane == "XZ":
        return [u, -w, v]
    assert plane == "ZX"
    return [v, w, u]


@settings(max_examples=30, deadline=None)
@given(
    plane=st.sampled_from(PLANES),
    origin=st.tuples(*(st.integers(-9, 9) for _ in range(3))),
    offset=st.integers(-8, 8),
    point=st.none() | st.tuples(st.integers(-6, 6), st.integers(-6, 6)),
    radius=st.integers(1, 40).map(lambda n: n / 4),
)
def test_a_sphere_is_centred_on_its_point(
    plane: str,
    origin: tuple[int, int, int],
    offset: int,
    point: tuple[int, int] | None,
    radius: float,
) -> None:
    (x, y) = point if point is not None else (0, 0)
    at_point = "" if point is None else f".moveTo({x}, {y})"
    program = (
        "import cadquery as cq\n"
        f"r = cq.Workplane('{plane}', origin={origin}).workplane(offset={offset})"
        f"{at_point}.sphere({radius})\n"
    )
    result = ag.run(program, dialect="cq")
    centre = [o + c for o, c in zip(origin, _world(plane, x, y, offset), strict=True)]
    expected: dict[str, object] = {
        "dialect": "cq",
        "status": "ok",
        "measures": {
            "volume": 4 / 3 * math.pi * radius**3,
            "area": 4 * math.pi * radius**2,
            "centroid": centre,
            "bounds": [[c - radius for c in centre], [c + radius for c in centre]],
            "faces": 1,
            "face_kinds": [["sphere", 1]],
            "shells": 1,
            "genus": 0,
        },
    }
    assert fixture_cases.check(result, expected) == [], result.message


def test_reach_reads_the_declared_form_only() -> None:
    def written(call: str) -> CorpusProgram:
        text = f"import cadquery as cq\nresult = cq.Workplane('XY').{call}"
        return CorpusProgram(stem=call, family="f", text=text)

    assert cq.subset().admits("Workplane.sphere(num)")
    report = reach([written("sphere(4)"), written("sphere(4, angle1=0)")], cq.subset())
    assert report.stems == ("sphere(4)",)
    refused = ag.run(
        "import cadquery as cq\nresult = cq.Workplane('XY').sphere(4, centered=False)",
        dialect="cq",
    )
    assert refused.status is ag.Status.UNSUPPORTED_API
    assert refused.message == "Workplane.sphere(num; centered=bool)"


@pytest.mark.parametrize("slug", sorted(CONTEXTS))
def test_a_sphere_on_any_other_last_object_is_refused(slug: str) -> None:
    case = next(c for c in fixture_cases.load("cq") if c.slug == slug)
    result = fixture_cases.run(case)
    assert result.status is ag.Status.UNSUPPORTED_API
    assert result.message == CONTEXTS[slug]


def _recorded(slug: str) -> tuple[fixture_cases.Case, OracleReport]:
    case = next(c for c in fixture_cases.load("cq") if c.slug == slug)
    path = fixture_cases.ROOT / "cq" / slug / "oracle.json"
    report = OracleReport.model_validate_json(path.read_text())
    assert report.program_sha256 == program_sha256(case.program)
    return case, report


def test_a_negative_radius_fails_on_both_sides() -> None:
    # Q1 of plans/lift-sphere: CadQuery raises Standard_ConstructionError.
    case, report = _recorded("runtime-sphere-negative-radius")
    assert report.status is OracleStatus.RUNTIME
    result = fixture_cases.run(case)
    assert fixture_cases.check(result, case.expected) == []
    assert compare(result, report).outcome is FidelityOutcome.AGREE


def test_a_zero_radius_is_a_by_design_row_against_the_oracles_invalid_shape() -> None:
    # Q1 of plans/lift-sphere: CadQuery builds a zero-volume shape its own
    # checker rejects; `cq` builds nothing and ends `runtime`, by design.
    slug = "runtime-sphere-zero-radius"
    case, report = _recorded(slug)
    directory = fixture_cases.ROOT / "cq" / slug
    verdict = Verdict.model_validate_json((directory / "verdict.json").read_text())
    assert report.status is OracleStatus.INVALID
    assert report.measures is not None
    assert report.measures.volume == 0.0
    result = fixture_cases.run(case)
    assert compare(result, report).outcome is FidelityOutcome.UNCLASSIFIED
    row = compare(result, report, verdict)
    assert (row.outcome, row.disagreement) == (
        FidelityOutcome.DISAGREE,
        DisagreementClass.BY_DESIGN,
    )
    assert isinstance(verdict.evidence, DocAnchor)
    path, anchor = verdict.evidence.anchor.split("#")
    text = (pathlib.Path(__file__).resolve().parent.parent / path).read_text()
    headings = re.findall(r"^#+ (.+)$", text, re.MULTILINE)
    assert anchor in [h.lower().replace(" ", "-") for h in headings]
    assert "sphere(0)" in text


@settings(max_examples=30, deadline=None)
@given(
    plane=st.sampled_from(PLANES),
    point=st.none() | st.tuples(st.integers(-6, 6), st.integers(-6, 6)),
    on_slab=st.booleans(),
    radius=st.integers(-20, 0).map(lambda n: n / 4),
)
def test_a_degenerate_sphere_ends_runtime_in_every_admitted_context(
    plane: str, point: tuple[int, int] | None, on_slab: bool, radius: float
) -> None:
    # Read on the oracle (`runtime-sphere-*`): a negative radius raises
    # Standard_ConstructionError and a zero radius builds an invalid shape;
    # `cq` ends each `runtime`, never a body.
    chain = (".box(4, 4, 2).workplane(offset=1)" if on_slab else "") + (
        "" if point is None else f".moveTo{point}"
    )
    program = f"import cadquery as cq\nr = cq.Workplane('{plane}'){chain}.sphere({radius})\n"
    result = ag.run(program, dialect="cq")
    assert result.status is ag.Status.RUNTIME, result.message
    assert result.message.startswith(f"ValueError: Workplane.sphere({radius}): ")

"""A compound result under `cq`: one solid whose body holds a shell per piece.

ADR-0016. Read on the oracle (CadQuery 2.3.0, `ok-compound-*`,
`ok-cut-into-pieces`, `ok-workplane-on-compound`): a `union` of solids that
do not meet, or a `cut` that splits its base, is a compound; Open CASCADE
reports its volume, area and faces as the sums over its solids, its bounds as
their union and one solid per piece. `cq` builds the same part as one arris
body of several shells, measured and scored as any body; a fidelity row
agrees when the oracle's solids are one or as many as the body's shells.
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import arris_gym as ag
import fixture_cases
from arris_gym.fidelity import (
    ClosedForm,
    DisagreementClass,
    FidelityOutcome,
    OracleReport,
    Verdict,
    compare,
)
from arris_gym.fidelity._agreement import figures_agree

AGREEING = [
    "ok-compound-two-boxes",
    "ok-compound-three-boxes",
    "ok-compound-bridged",
    "ok-cut-into-pieces",
    "ok-workplane-on-compound",
]
OCCT_CENTROID = "ok-compound-occt-centroid"


def _case(slug: str) -> fixture_cases.Case:
    return next(c for c in fixture_cases.load("cq") if c.slug == slug)


def _report(slug: str) -> OracleReport:
    path = fixture_cases.ROOT / "cq" / slug / "oracle.json"
    return OracleReport.model_validate_json(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("slug", AGREEING)
def test_a_compound_fixture_agrees_with_the_recorded_oracle(slug: str) -> None:
    result = fixture_cases.run(_case(slug))
    report = _report(slug)
    assert result.measures is not None
    assert report.measures is not None
    assert report.measures.solids == result.measures.shells
    assert compare(result, report).outcome is FidelityOutcome.AGREE


def test_the_oracle_gets_one_compounds_centroid_wrong_and_the_closed_form_settles_it() -> None:
    # Open CASCADE's `VolumeProperties` of this compound puts the centroid at
    # (4.725, 0, 0.975); the closed form, and arris, at (4, 0, 0.8). Volume,
    # area and bounds hold on both sides, so only the centroid is off.
    case = _case(OCCT_CENTROID)
    result = fixture_cases.run(case)
    report = _report(OCCT_CENTROID)
    assert fixture_cases.check(result, case.expected) == []
    assert report.measures is not None
    want = case.expected["measures"]
    assert isinstance(want, dict)
    assert fixture_cases.close(report.measures.volume, float(want["volume"]))
    assert fixture_cases.close(report.measures.area, float(want["area"]))
    assert not fixture_cases.close(report.measures.centroid[0], float(want["centroid"][0]))
    assert compare(result, report).outcome is FidelityOutcome.UNCLASSIFIED
    path = fixture_cases.ROOT / "cq" / OCCT_CENTROID / "verdict.json"
    verdict = Verdict.model_validate_json(path.read_text(encoding="utf-8"))
    assert result.measures is not None
    assert isinstance(verdict.evidence, ClosedForm)
    assert figures_agree(result.measures, verdict.evidence)
    assert not figures_agree(report.measures, verdict.evidence)
    row = compare(result, report, verdict)
    assert (row.outcome, row.disagreement) == (
        FidelityOutcome.DISAGREE,
        DisagreementClass.OCCT_WRONG,
    )


def test_a_compound_of_another_piece_count_than_the_body_does_not_agree() -> None:
    slug = "ok-compound-two-boxes"
    result = fixture_cases.run(_case(slug))
    report = _report(slug)
    assert result.measures is not None
    assert report.measures is not None
    for solids in (3, 4):
        other = report.model_copy(
            update={"measures": report.measures.model_copy(update={"solids": solids})}
        )
        assert compare(result, other).outcome is FidelityOutcome.UNCLASSIFIED


def test_one_oracle_solid_is_judged_by_its_measures_whatever_the_shells() -> None:
    # A solid with a cavity has two shells and is one solid on both sides; the
    # rule for one oracle solid is the measures alone, as before ADR-0016.
    result = ag.run(
        "import cadquery as cq\n"
        "r = cq.Workplane('XY').box(3, 3, 3).cut(cq.Workplane('XY').box(1, 1, 1))\n",
        dialect="cq",
    )
    assert result.measures is not None
    assert result.measures.shells == 2
    report = OracleReport.model_validate(
        {
            "status": "ok",
            "message": "",
            "measures": {
                "volume": 26.0,
                "area": 60.0,
                "centroid": [0.0, 0.0, 0.0],
                "bounds": [[-1.5, -1.5, -1.5], [1.5, 1.5, 1.5]],
                "faces": 12,
                "solids": 1,
            },
            "step_sha256": "0" * 64,
            "program_sha256": result.program_sha256,
            "versions": {"cadquery": "2.3.0", "ocp": "7.9.3.0", "python": "3.12.3"},
        }
    )
    assert compare(result, report).outcome is FidelityOutcome.AGREE


def test_a_compound_scores_against_itself_exactly_one() -> None:
    result = fixture_cases.run(_case("ok-compound-three-boxes"))
    assert result.body is not None
    score = ag.score(result, result.body)
    assert (score.status, score.reward) == (ag.Status.OK, 1.0)


@settings(max_examples=25, deadline=None)
@given(
    sizes=st.lists(st.tuples(*(st.integers(1, 4) for _ in range(3))), min_size=2, max_size=4),
    gaps=st.lists(st.integers(1, 3), min_size=3, max_size=3),
    lift=st.integers(-3, 3),
)
def test_disjoint_boxes_unioned_are_a_compound_of_their_closed_form(
    sizes: list[tuple[int, int, int]], gaps: list[int], lift: int
) -> None:
    # Boxes in a row along x, each `gap` past the last, every other one
    # lifted by `lift`: no two meet, so the union is a compound.
    centres: list[tuple[float, float, float]] = []
    x = 0.0
    for i, (length, _, _) in enumerate(sizes):
        x += length / 2
        centres.append((x, 0.0, float(lift * (i % 2))))
        x += length / 2 + gaps[i % len(gaps)]
    boxes = [
        f"cq.Workplane('XY').transformed(offset=cq.Vector{c}).box({s[0]}, {s[1]}, {s[2]})"
        for c, s in zip(centres, sizes, strict=True)
    ]
    program = "import cadquery as cq\nr = " + "".join(
        [boxes[0], *(f".union({b})" for b in boxes[1:])]
    )
    result = ag.run(program + "\n", dialect="cq")

    volumes = [float(a * b * c) for a, b, c in sizes]
    total = sum(volumes)
    lows = [[c[k] - s[k] / 2 for k in range(3)] for c, s in zip(centres, sizes, strict=True)]
    highs = [[c[k] + s[k] / 2 for k in range(3)] for c, s in zip(centres, sizes, strict=True)]
    expected: dict[str, object] = {
        "dialect": "cq",
        "status": "ok",
        "measures": {
            "volume": total,
            "area": sum(2 * (a * b + a * c + b * c) for a, b, c in sizes),
            "centroid": [
                sum(v * c[k] for v, c in zip(volumes, centres, strict=True)) / total
                for k in range(3)
            ],
            "bounds": [
                [min(lo[k] for lo in lows) for k in range(3)],
                [max(hi[k] for hi in highs) for k in range(3)],
            ],
            "faces": 6 * len(sizes),
            "face_kinds": [["plane", 6 * len(sizes)]],
            "shells": len(sizes),
            "genus": 0,
        },
    }
    assert fixture_cases.check(result, expected) == [], result.message

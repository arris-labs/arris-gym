"""What `faces`, `workplane(offset=)` and `hole` do in the contexts step 6 reads on the oracle.

Each fixture's expectation is a closed form worked out by hand from how the part is
built (the `note` in its `expected.json` says how), and each carries CadQuery's recorded
report of the same program. Nothing is read from `cq`.
"""

from __future__ import annotations

import json
import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import arris_gym.cq as cq
import fixture_cases
from arris_gym.fidelity import FidelityOutcome, OracleReport, compare
from test_cq_faces import AXES
from test_cq_hole import BASE, measures, wrap

PIECES = (
    'cq.Workplane("XY").box(2, 2, 2).union(\n'
    '        cq.Workplane("XY").transformed(offset=cq.Vector({x}, 0, {z})).box(2, 2, {h})\n    )'
)


def compound_tops() -> dict[str, object]:
    """A 2 x 2 x 2 box A on the origin (z -1..1) and a 2 x 2 x 4 box B at (5, 0, 1) (z -1..3).

    `faces(">Z")` is B's top alone, the plane z = 3, so a circle of radius 1/2
    at the plane's origin, extruded 1, stands in the air over nothing: a
    third piece. V = 8 + 16 + pi/4; A = 24 + 40 + pi + 2 (pi/4); the pieces'
    centroids are (0, 0, 0), (5, 0, 1) and (0, 0, 3.5).
    """
    disc = math.pi / 4
    volume = 24 + disc
    return measures(
        volume,
        64 + 1.5 * math.pi,
        (80 / volume, 0, (16 + disc * 3.5) / volume),
        ((-1, -1, -1), (6, 1, 4)),
        15,
        [["cylinder", 1], ["plane", 14]],
        shells=3,
    )


def compound_bottoms() -> dict[str, object]:
    """The same A and B, `faces("<Z")`: both bottoms are at z = -1, one coplanar set.

    The plane is z = -1 with its normal -z, and the circle of radius 1/2 at
    its origin extruded 1 goes down to z = -2, fused with A's bottom where it
    touches it: V = 24 + pi/4, A = 64 + pi (the wall; its cap replaces the disc
    it covers), centroid z = (16 - 1.5 pi/4) / V.
    """
    disc = math.pi / 4
    volume = 24 + disc
    return measures(
        volume,
        64 + math.pi,
        (80 / volume, 0, (16 - disc * 1.5) / volume),
        ((-1, -1, -2), (6, 1, 3)),
        14,
        [["cylinder", 1], ["plane", 13]],
        shells=2,
    )


def compound_coplanar_tops() -> dict[str, object]:
    """Two 2 x 2 x 2 boxes, on the origin and at (5, 0, 0): both tops are at z = 1.

    `faces(">Z")` keeps both faces, one on each piece, and the plane is z = 1
    through the origin: a circle of radius 1/2, extruded 1, fuses with the
    first box's top. V = 16 + pi/4, A = 48 + pi, centroid x = 40 / V.
    """
    disc = math.pi / 4
    volume = 16 + disc
    return measures(
        volume,
        48 + math.pi,
        (40 / volume, 0, disc * 1.5 / volume),
        ((-1, -1, -1), (6, 1, 2)),
        14,
        [["cylinder", 1], ["plane", 13]],
        shells=2,
    )


def offset_above() -> dict[str, object]:
    """`box(4, 6, 8)` `.faces(">Z").workplane(offset=1).circle(1).extrude(1)`: a disc over the top.

    The plane is z = 5, so the cylinder (r = 1, z 5..6) is a second piece in
    the air: V = 192 + pi, A = 208 + 4 pi, centroid z = 5.5 pi / V.
    """
    volume = 192 + math.pi
    return measures(
        volume,
        208 + 4 * math.pi,
        (0, 0, 5.5 * math.pi / volume),
        ((-2, -3, -4), (2, 3, 6)),
        9,
        [["cylinder", 1], ["plane", 8]],
        shells=2,
    )


def offset_into() -> dict[str, object]:
    """`offset=-1` puts the plane at z = 3: a cylinder (r = 1, z 3..4) inside the box.

    It lies wholly in the box and its top is flush with the box's: the union is
    the box, V = 192, A = 208. arris keeps the flush disc as a face of its own on
    the top, 7 faces where CadQuery's `clean` merges it back into 6.
    """
    return measures(192, 208, (0, 0, 0), ((-2, -3, -4), (2, 3, 4)), 7, [["plane", 7]])


def offset_side() -> dict[str, object]:
    """`.faces("<X").workplane(offset=2.5).moveTo(1, 1).circle(1).extrude(1)`.

    `<X` is the plane x = -2 with normal -x, x axis -y, y axis +z, so the
    offset puts it at x = -4.5 and (1, 1) at (y, z) = (-1, 1); the cylinder
    (r = 1) goes on along -x to x = -5.5: a second piece, V = 192 + pi,
    A = 208 + 4 pi, centroid (-5 pi, -pi, pi) / V.
    """
    volume = 192 + math.pi
    return measures(
        volume,
        208 + 4 * math.pi,
        (-5 * math.pi / volume, -math.pi / volume, math.pi / volume),
        ((-5.5, -3, -4), (2, 3, 4)),
        9,
        [["cylinder", 1], ["plane", 8]],
        shells=2,
    )


def offset_hole() -> dict[str, object]:
    """`.faces(">Z").workplane(offset=-2).hole(1)`: the plane is z = 2.

    The cylinder (r = 1/2) runs from z = 2 against the normal, out of the
    bottom, so it bores z -4..2, 6 deep: V = 192 - 1.5 pi, A = 208 + 6 pi (the cap at z = 2
    replaces the disc the bore takes from the bottom), centroid z = 1.5 pi / V
    (the bore's is -1).
    """
    cut = math.pi * 0.25 * 6
    volume = 192 - cut
    return measures(
        volume,
        208 + math.pi * 6,
        (0, 0, cut / volume),
        ((-2, -3, -4), (2, 3, 4)),
        8,
        [["cylinder", 1], ["plane", 7]],
    )


def fixture_programs() -> dict[str, tuple[str, dict[str, object], str]]:
    """Every generated fixture of this file: slug -> (program text, expected measures, note)."""
    tops = PIECES.format(x=5, z=1, h=4)
    flat = PIECES.format(x=5, z=0, h=2)
    circle = ".workplane().circle(0.5).extrude(1)"
    return {
        "ok-faces-compound-tops": (
            wrap(f'{tops}.faces(">Z"){circle}'),
            compound_tops(),
            compound_tops.__doc__ or "",
        ),
        "ok-faces-compound-bottoms": (
            wrap(f'{tops}.faces("<Z"){circle}'),
            compound_bottoms(),
            compound_bottoms.__doc__ or "",
        ),
        "ok-faces-compound-coplanar-tops": (
            wrap(f'{flat}.faces(">Z"){circle}'),
            compound_coplanar_tops(),
            compound_coplanar_tops.__doc__ or "",
        ),
        "ok-faces-workplane-offset-above": (
            wrap(f'{BASE}.faces(">Z").workplane(offset=1).circle(1).extrude(1)'),
            offset_above(),
            offset_above.__doc__ or "",
        ),
        "ok-faces-workplane-offset-into": (
            wrap(f'{BASE}.faces(">Z").workplane(offset=-1).circle(1).extrude(1)'),
            offset_into(),
            offset_into.__doc__ or "",
        ),
        "ok-faces-workplane-offset-side": (
            wrap(f'{BASE}.faces("<X").workplane(offset=2.5).moveTo(1, 1).circle(1).extrude(1)'),
            offset_side(),
            offset_side.__doc__ or "",
        ),
        "ok-faces-workplane-offset-hole": (
            wrap(f'{BASE}.faces(">Z").workplane(offset=-2).hole(1)'),
            offset_hole(),
            offset_hole.__doc__ or "",
        ),
    }


# The programs CadQuery runs into an error, or the subset refuses, with the message each ends in.
EMPTY_LIST = "ValueError: Can not return the Nth element of an empty list"
RUNTIME = {
    "runtime-faces-on-empty-stack": (f'{BASE}.workplane().faces(">Z")', EMPTY_LIST),
    "runtime-faces-on-a-move-point": ('cq.Workplane("XY").moveTo(1, 1).faces(">Z")', EMPTY_LIST),
    "runtime-faces-on-a-pending-circle": (
        'cq.Workplane("XY").circle(1).faces(">Z")',
        EMPTY_LIST,
    ),
    "runtime-faces-on-an-open-path": (
        'cq.Workplane("XY").moveTo(0, 0).lineTo(1, 0).faces(">Z")',
        EMPTY_LIST,
    ),
}
UNSUPPORTED = {
    "unsupported-hole-on-selected-faces": (
        f'{BASE}.faces(">Z").hole(1)',
        "Workplane.hole on selected faces",
    ),
    "unsupported-hole-on-a-drawn-path": (
        f'{BASE}.faces(">Z").workplane().moveTo(1, 1).lineTo(2, 2).hole(1)',
        "Workplane.hole on a pending wire",
    ),
    "unsupported-hole-on-a-pending-circle": (
        f'{BASE}.faces(">Z").workplane().circle(1).hole(1)',
        "Workplane.hole on a pending wire",
    ),
}


def cases() -> dict[str, fixture_cases.Case]:
    mine = [*fixture_programs(), *RUNTIME, *UNSUPPORTED]
    return {case.slug: case for case in fixture_cases.load("cq") if case.slug in mine}


def recorded(slug: str) -> OracleReport:
    path = fixture_cases.ROOT / "cq" / slug / "oracle.json"
    return OracleReport.model_validate_json(path.read_text())


def test_every_generated_fixture_is_the_closed_form() -> None:
    """The committed files are exactly what `fixture_programs` computes."""
    committed = cases()
    for slug, (program, expected, _) in fixture_programs().items():
        assert committed[slug].program == program, slug
        got = committed[slug].expected["measures"]
        assert json.loads(json.dumps(got)) == json.loads(json.dumps(expected)), slug


def test_every_runtime_and_unsupported_fixture_is_the_table() -> None:
    committed = cases()
    for slug, (chain, message) in {**RUNTIME, **UNSUPPORTED}.items():
        assert committed[slug].program == wrap(chain), slug
        assert committed[slug].expected["message"] == message, slug


@pytest.mark.parametrize("slug", sorted(fixture_programs()))
def test_a_generated_fixture_agrees_with_the_recorded_oracle(slug: str) -> None:
    report = recorded(slug)
    assert compare(fixture_cases.run(cases()[slug]), report).outcome is FidelityOutcome.AGREE
    _, expected, _ = fixture_programs()[slug]
    assert report.measures is not None
    assert report.measures.solids == expected["shells"], slug
    assert fixture_cases.close(report.measures.volume, float(str(expected["volume"]))), slug
    assert fixture_cases.close(report.measures.area, float(str(expected["area"]))), slug


@pytest.mark.parametrize("slug", sorted(RUNTIME))
def test_cadquery_raises_where_a_stack_has_no_faces(slug: str) -> None:
    report = recorded(slug)
    assert report.status.value == "runtime"
    assert report.message == RUNTIME[slug][1]
    assert compare(fixture_cases.run(cases()[slug]), report).outcome is FidelityOutcome.AGREE


@pytest.mark.parametrize("slug", sorted(UNSUPPORTED))
def test_cadquery_bores_where_the_subset_refuses(slug: str) -> None:
    """CadQuery builds each part, boring at a centre the subset lacks: ours is `unsupported_api`."""
    assert recorded(slug).status.value == "ok"


@settings(max_examples=60, deadline=None)
@given(
    size=st.tuples(*(st.integers(2, 9) for _ in range(3))),
    selector=st.sampled_from(sorted(AXES)),
    offset=st.integers(-3, 5),
)
def test_an_offset_moves_the_faces_plane_along_its_normal(
    size: tuple[int, int, int], selector: str, offset: int
) -> None:
    """The plane keeps its axes and its origin moves `offset` along the outward normal."""
    plain = cq.Workplane("XY").box(*size).faces(selector).workplane()._plane
    moved = cq.Workplane("XY").box(*size).faces(selector).workplane(offset=offset)._plane
    normal = AXES[selector][0]
    assert (moved.x, moved.y, moved.z) == (plain.x, plain.y, plain.z)
    want = tuple(o + offset * n for o, n in zip(plain.origin, normal, strict=True))
    assert moved.origin == pytest.approx(want, abs=1e-9)

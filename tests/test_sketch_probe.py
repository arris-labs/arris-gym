"""Hold the recorded sketch traces and extrusions to their constructions, offline."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import pytest

import cq_sketch_probe as probe
import fixture_cases
from arris_gym.fidelity import OracleReport, OracleStatus, program_sha256

Point = tuple[float, float, float]
# Count, total area and area-weighted centroid of the faces on the sketch plane.
Section = tuple[int, float | None, Point | None]
EMPTY: Section = (0, 0.0, None)
ORIGIN = (0.0, 0.0, 0.0)
SQUARE: Section = (1, 4.0, ORIGIN)
RECTANGLE: Section = (1, 24.0, ORIGIN)
TRIANGLE: Section = (1, 4.0, (4 / 3, 2 / 3, 0.0))
HALF_DISC: Section = (1, math.pi / 2, (0.0, 4 / (3 * math.pi), 0.0))
TOOL: Section = (1, 4.0, (1.0, -1.0, 0.0))
TOOL_MOVED: Section = (1, 4.0, (6.0, 2.0, 0.0))
SHIFTED_TRIANGLE: Section = (1, 4.0, (5 + 4 / 3, 3 + 2 / 3, 0.0))
INTERSECTION_BASE: Section = (1, 40.0, ORIGIN)
# A zero dimension asks OCCT for an unbounded plane. It has no finite
# closed-form area or centroid. The final oracle status checks the extrusion.
UNBOUNDED: Section = (1, None, None)

# One section per successful call after sketch() and before finalize().
SECTIONS: dict[str, tuple[Section, ...]] = {
    "arc-three-coordinates": (),
    "arc-without-edges": (),
    "assemble-at-selection": (
        EMPTY,
        EMPTY,
        EMPTY,
        EMPTY,
        SHIFTED_TRIANGLE,
        SHIFTED_TRIANGLE,
        (2, 8.0, (5 / 2 + 4 / 3, 3 / 2 + 2 / 3, 0.0)),
    ),
    "assemble-half-disc": (EMPTY, EMPTY, HALF_DISC),
    "assemble-half-disc-three-point-arc": (EMPTY, EMPTY, HALF_DISC),
    "assemble-open-chain": (EMPTY, EMPTY, TRIANGLE),
    "assemble-ordered-chain": (EMPTY, EMPTY, EMPTY, TRIANGLE),
    "assemble-reversed-arc-at-selection": (
        EMPTY,
        EMPTY,
        EMPTY,
        (1, math.pi / 2, (3, 5 + 4 / (3 * math.pi), 0)),
    ),
    "assemble-unordered-chain": (EMPTY, EMPTY, EMPTY, TRIANGLE),
    "assemble-without-edges": (),
    "circle-negative": (),
    "circle-zero": (),
    "close-already-closed": (EMPTY, EMPTY, EMPTY),
    "close-without-edges": (),
    "cut-to-empty": (SQUARE, EMPTY),
    "disjoint-adds": (SQUARE, SQUARE, (2, 12.0, (10 / 3, 2 / 3, 0.0))),
    "empty-add": (SQUARE,),
    "empty-construction": (),
    "empty-intersect": (),
    "empty-subtract": (),
    "empty-unknown": (),
    "face-at-selection": (
        EMPTY,
        EMPTY,
        TOOL,
        EMPTY,
        TOOL_MOVED,
        TOOL_MOVED,
        (2, 8.0, (3.5, 0.5, 0.0)),
    ),
    "intersect-at-disjoint-points": (INTERSECTION_BASE, INTERSECTION_BASE, (2, 8.0, ORIGIN)),
    "intersect-at-overlapping-points": (INTERSECTION_BASE, INTERSECTION_BASE, (3, 12.0, ORIGIN)),
    "nonempty-add": (RECTANGLE, (2, 24.0, ORIGIN)),
    "nonempty-construction": (RECTANGLE,),
    "nonempty-intersect": (RECTANGLE, SQUARE),
    "nonempty-subtract": (RECTANGLE, (1, 20.0, ORIGIN)),
    "nonempty-unknown": (RECTANGLE,),
    "push-rect-rect-s": (EMPTY, (2, 32.0, (-0.5, 1.0, 0.0)), (2, 24.0, (-0.5, 1.0, 0.0))),
    "rect-negative-height": ((1, 8.0, ORIGIN),),
    "rect-negative-width": ((1, 8.0, ORIGIN),),
    "rect-zero-height": (UNBOUNDED,),
    "rect-zero-width": (UNBOUNDED,),
    "ring": ((1, 4 * math.pi, ORIGIN), (1, 3 * math.pi, ORIGIN)),
    "segment-three-coordinates": (),
    "segment-without-edges": (),
}

# The section's outer and inner boundaries after adjoining faces are joined.
# Each extrusion is 2 high. The pair is (total perimeter, number of solids).
_TRIANGLE_PERIMETER = 4 + 2 + math.hypot(4, 2)
PRISMS: dict[str, tuple[float, int]] = {
    "assemble-at-selection": (2 * _TRIANGLE_PERIMETER, 2),
    "assemble-half-disc": (2 + math.pi, 1),
    "assemble-half-disc-three-point-arc": (2 + math.pi, 1),
    "assemble-ordered-chain": (_TRIANGLE_PERIMETER, 1),
    "assemble-reversed-arc-at-selection": (2 + math.pi, 1),
    "assemble-unordered-chain": (_TRIANGLE_PERIMETER, 1),
    "disjoint-adds": (8 + 12, 2),
    "empty-add": (8, 1),
    "face-at-selection": (2 * 8, 2),
    "intersect-at-disjoint-points": (2 * 8, 2),
    "intersect-at-overlapping-points": (2 * (6 + 2), 1),
    "nonempty-add": (20, 1),
    "nonempty-intersect": (8, 1),
    "nonempty-subtract": (20 + 8, 1),
    "push-rect-rect-s": (2 * (16 + 8), 2),
    "rect-negative-height": (12, 1),
    "rect-negative-width": (12, 1),
    "ring": (2 * math.pi * (2 + 1), 1),
}

_INVALID = {"assemble-open-chain", "rect-zero-height", "rect-zero-width"}
_NO_TAG = "ValueError: No tag specified - the geometry will be unreachable"
_NO_EDGES = "ValueError: No free edges available"
_SKETCH_TYPE = "<class 'cadquery.sketch.Sketch'>"
_TUPLE_TYPE = "<class 'tuple'>"
_RUNTIME = {
    "arc-three-coordinates": (
        f"multimethod.DispatchError: ('arc: 0 methods found', "
        f"({_SKETCH_TYPE}, {_TUPLE_TYPE}, {_TUPLE_TYPE}, {_TUPLE_TYPE}), set())"
    ),
    "arc-without-edges": _NO_EDGES,
    "assemble-without-edges": "IndexError: list index out of range",
    "circle-negative": (
        "OCP.OCP.Standard.Standard_ConstructionError: gp_Circ() - radius should be positive number"
    ),
    "circle-zero": "ValueError: Cannot build face(s): wires not planar",
    "close-already-closed": "OCP.OCP.StdFail.StdFail_NotDone: BRep_API: command not done",
    "close-without-edges": _NO_EDGES,
    "cut-to-empty": "ValueError: No pending wires present",
    "empty-intersect": "ValueError: Null TopoDS_Shape object",
    "empty-subtract": "ValueError: Null TopoDS_Shape object",
    "empty-construction": _NO_TAG,
    "nonempty-construction": _NO_TAG,
    "empty-unknown": "ValueError: Invalid mode: other",
    "nonempty-unknown": "ValueError: Invalid mode: other",
    "segment-three-coordinates": (
        f"multimethod.DispatchError: ('segment: 0 methods found', "
        f"({_SKETCH_TYPE}, {_TUPLE_TYPE}, {_TUPLE_TYPE}), set())"
    ),
    "segment-without-edges": _NO_EDGES,
}

_PATH = Path(__file__).parent / "fixtures" / "sketch" / "constructed.json"
_ROWS: list[dict[str, Any]] = json.loads(_PATH.read_text(encoding="utf-8"))


def test_every_construction_is_recorded_and_held() -> None:
    names = [row["name"] for row in _ROWS]
    programs = probe.constructed_programs()
    assert names == list(programs) == sorted(SECTIONS)
    assert {row["name"]: row["program"] for row in _ROWS} == programs
    assert names == sorted([*PRISMS, *_INVALID, *_RUNTIME])


def _hold_point(got: list[float] | Point, want: Point) -> None:
    for actual, expected in zip(got, want, strict=True):
        assert fixture_cases.close(actual, expected), (got, want)


@pytest.mark.parametrize("row", _ROWS, ids=[row["name"] for row in _ROWS])
def test_sketch_faces_and_extrusion(row: dict[str, Any]) -> None:
    name = row["name"]
    report = OracleReport.model_validate(row["report"])
    assert report.program_sha256 == program_sha256(row["program"])

    sections = (EMPTY, *SECTIONS[name])
    # A failure at extrude still has a snapshot of finalize.
    if name in PRISMS or name in _INVALID or name == "cut-to-empty":
        sections += (sections[-1],)
    calls = [line for line in row["program"].splitlines()[2:-1]]
    assert [snapshot["call"] for snapshot in row["snapshots"]] == calls[: len(sections)]
    for snapshot, (faces, area, centroid) in zip(row["snapshots"], sections, strict=True):
        assert snapshot["faces"] == faces
        if area is not None:
            assert fixture_cases.close(snapshot["area"], area)
            if centroid is None:
                assert snapshot["centroid"] is None
            else:
                _hold_point(snapshot["centroid"], centroid)

    if name in _RUNTIME:
        assert report.status is OracleStatus.RUNTIME
        assert report.message == _RUNTIME[name]
    elif name in _INVALID:
        assert report.status is OracleStatus.INVALID
        assert report.message == "BRepCheck_Analyzer: shape is not valid"
    else:
        assert report.status is OracleStatus.OK, report.message
        assert report.measures is not None
        _, section_area, centre = sections[-1]
        assert section_area is not None
        assert centre is not None
        perimeter, solids = PRISMS[name]
        assert report.measures.solids == solids
        assert fixture_cases.close(report.measures.volume, 2 * section_area)
        assert fixture_cases.close(report.measures.area, 2 * section_area + 2 * perimeter)
        _hold_point(report.measures.centroid, (centre[0], centre[1], 1.0))

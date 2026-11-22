"""Check the pinned oracle's profile constructions offline against closed forms."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TypedDict

import pytest

import cq_profile_probe as probe
from arris_gym.fidelity import OracleMeasures, OracleStatus, OracleVersions, program_sha256
from arris_gym.fidelity._agreement import figures_agree

_RECORDS = Path(__file__).parent / "fixtures" / "profiles" / "constructed.json"
_SIDE_EXPECTED = (
    _RECORDS.parent.parent / "regression" / "oracle-cut-thru-all-side" / "expected.json"
)
_Point = tuple[float, float, float]
_Section = tuple[float, float]  # area, perimeter
_Origin = (0.0, 0.0, 0.0)


@dataclass(frozen=True)
class _Measures:
    volume: float
    area: float
    centroid: _Point
    bounds: tuple[_Point, _Point]
    solids: int = 1


def _rect(w: float, h: float) -> _Section:
    return w * h, 2 * (w + h)


def _disc(r: float) -> _Section:
    return math.pi * r**2, math.tau * r


def _prism(section: _Section, center: _Point, size: _Point, axis: int = 2) -> _Measures:
    area, perimeter = section
    x, y, z = center
    dx, dy, dz = (span / 2 for span in size)
    length = size[axis]
    return _Measures(
        area * length,
        2 * area + perimeter * length,
        center,
        ((x - dx, y - dy, z - dz), (x + dx, y + dy, z + dz)),
    )


def _rectangle(w: float, h: float, x: float = 0, y: float = 0) -> _Measures:
    return _prism(_rect(w, h), (x, y, 1), (w, h, 2))


def _cylinder(r: float, x: float, y: float) -> _Measures:
    return _prism(_disc(r), (x, y, 1), (2 * r, 2 * r, 2))


def _centroid(volume: float, *parts: tuple[float, _Point]) -> _Point:
    x, y, z = (sum(v * c[axis] for v, c in parts) / volume for axis in range(3))
    return x, y, z


def _disjoint(*parts: _Measures) -> _Measures:
    volume = sum(p.volume for p in parts)
    x0, y0, z0 = (min(p.bounds[0][axis] for p in parts) for axis in range(3))
    x1, y1, z1 = (max(p.bounds[1][axis] for p in parts) for axis in range(3))
    return _Measures(
        volume,
        sum(p.area for p in parts),
        _centroid(volume, *((p.volume, p.centroid) for p in parts)),
        ((x0, y0, z0), (x1, y1, z1)),
        sum(p.solids for p in parts),
    )


def _cut(stock: _Measures, *removed: _Measures, openings: float) -> _Measures:
    # An opening is part of both the tool and the old outside of the stock.
    # The cut removes it from the stock and leaves only the tool's inner walls.
    volume = stock.volume - sum(p.volume for p in removed)
    return _Measures(
        volume,
        stock.area + sum(p.area for p in removed) - 2 * openings,
        _centroid(
            volume, (stock.volume, stock.centroid), *((-p.volume, p.centroid) for p in removed)
        ),
        stock.bounds,
        stock.solids,
    )


_BOX = _prism(_rect(10, 8), _Origin, (10, 8, 4))
_UPPER_BOX = _prism(_rect(10, 8), (0, 0, 8), (10, 8, 4))


def _through(section: _Section, *points: tuple[float, float]) -> _Measures:
    # Tool bounds are immaterial here. Its length and material centroid
    # come from the stock, including when the workplane is outside it.
    removed = [_prism(section, (x, y, 0), (0, 0, 4)) for x, y in points]
    return _cut(_BOX, *removed, openings=2 * section[0] * len(points))


def _nested(outer: _Section, inner: _Section, outer_size: tuple[float, float]) -> _Measures:
    return _prism((outer[0] - inner[0], outer[1] + inner[1]), (1, -2, 1), (*outer_size, 2))


def _slot(dx: float, dy: float, x: float = 0, y: float = 0) -> _Measures:
    # A 4 by 2 rectangle plus two semicircles of radius 1.
    return _prism((8 + math.pi, 8 + math.tau), (x, y, 1), (dx, dy, 2))


_FACE_POST = _prism(_disc(1), (6, 1, -0.5), (2, 2, 2), axis=0)
_CIRCLE_THROUGH = _through(_disc(1), (1, -2))
_RECT_IN_RECT = _nested(_rect(6, 4), _rect(2, 1), (6, 4))
_DISC_IN_RECT = _nested(_rect(6, 4), _disc(1), (6, 4))
_RECT_IN_DISC = _nested(_disc(3), _rect(2, 1), (6, 6))
_DIAGONAL_SLOT_SPAN = 2 + 2 * math.sqrt(2)
_SHIFTED_CIRCLE = _cylinder(1, 2, -1)
_PENDING_CIRCLE = _cylinder(0.5, -2, 1)

_PARTS: dict[str, _Measures] = {
    **dict.fromkeys(
        ("through-on-face", "through-inside", "through-above", "through-below"), _CIRCLE_THROUGH
    ),
    "blind-ring-through-depth": replace(_through((3 * math.pi, 3 * math.tau), (1, -1)), solids=2),
    "through-miss": _BOX,
    # The intersection is x=3..5, y=-1..1, z=-2..2. The notch opens
    # on both caps and on the +X side of the box.
    "through-overhang": _cut(
        _BOX, _prism(_rect(2, 2), (4, 0, 0), (2, 2, 4)), openings=2 * 4 + 2 * 4
    ),
    "through-compound": _cut(
        _disjoint(_BOX, _UPPER_BOX),
        _prism(_disc(1), (0, 0, 0), (2, 2, 4)),
        _prism(_disc(1), (0, 0, 8), (2, 2, 4)),
        openings=4 * math.pi,
    ),
    "through-polygon": _through((8, 8 * math.sqrt(2)), (0, 0)),
    "through-path": _through((3, 5 + math.sqrt(13)), (0, -1 / 3)),
    "through-circles-at-points": _through(_disc(0.5), (-3, -1), (2, 2)),
    "through-rects-at-points": _through(_rect(2, 1), (-2, -1.5), (-2, 1.5), (2, -1.5), (2, 1.5)),
    "rect-on-rect": _RECT_IN_RECT,
    "rect-on-rect-outer-last": _RECT_IN_RECT,
    "rect-on-circle": _RECT_IN_DISC,
    "rect-on-circle-outer-last": _DISC_IN_RECT,
    "circle-on-rect": _DISC_IN_RECT,
    "circle-on-rect-outer-last": _RECT_IN_DISC,
    "rects-edge-touch": _rectangle(4, 2, 1, 0),
    "rects-corner-touch": _disjoint(_rectangle(2, 2), _rectangle(2, 2, 2, 2)),
    "rects-overlap": _rectangle(3, 2, 0.5, 0),
    "through-rects-edge-touch": _through(_rect(4, 2), (1, 0)),
    "through-rects-overlap": _through(_rect(3, 2), (0.5, 0)),
    "center-circle": _SHIFTED_CIRCLE,
    "center-twice": _cylinder(1, 1, 2),
    "center-after-move": _SHIFTED_CIRCLE,
    "center-after-points": _SHIFTED_CIRCLE,
    "center-before-move": _cylinder(1, -1, 3),
    "center-before-array": _through(_disc(0.5), (-1, -2), (-1, 0), (3, -2), (3, 0)),
    "center-on-face": replace(
        _disjoint(_BOX, _FACE_POST), area=_BOX.area + _FACE_POST.area - 2 * math.pi, solids=1
    ),
    "center-on-pending": _PENDING_CIRCLE,
    "center-between-profiles": _disjoint(_PENDING_CIRCLE, _SHIFTED_CIRCLE),
    "rect-origin": _rectangle(4, 2),
    "rect-at-point": _rectangle(4, 2, 1, -2),
    "rect-at-center": _rectangle(4, 2, 1, -2),
    "rects-at-points": _disjoint(_rectangle(2, 1, -3, -1), _rectangle(2, 1, 2, 2)),
    "rects-at-polar-points": _disjoint(
        _rectangle(2, 1, 3, 0),
        _rectangle(1, 2, 0, 3),
        _rectangle(2, 1, -3, 0),
        _rectangle(1, 2, 0, -3),
    ),
    "rect-blind": _cut(_BOX, _prism(_rect(4, 2), (1, -2, 1.5), (4, 2, 1)), openings=8),
    **dict.fromkeys(("rect-negative-x", "rect-negative-y", "rect-negative-both"), _rectangle(4, 2)),
    # A doubled line extrudes to two coincident walls. With zero mass,
    # Open CASCADE leaves the volume centroid at the origin.
    "rect-zero-x": replace(_rectangle(0, 2), centroid=_Origin),
    "rect-zero-y": replace(_rectangle(4, 0), centroid=_Origin),
    "slot-0": _slot(6, 2),
    "slot-45": _slot(_DIAGONAL_SLOT_SPAN, _DIAGONAL_SLOT_SPAN),
    "slot-90": _slot(2, 6),
    "slot-at-point": _slot(2, 6, 1, -2),
    "slots-at-points": _disjoint(_slot(2, 6, -3, -2), _slot(2, 6, 2, 1)),
    "slot-through": _through((8 + math.pi, 8 + math.tau), (1, -1)),
    # The short slot's two semicircles cross. Each cap integral counts the
    # semicircles positively and the 2 by 4 rectangle between them negatively.
    "slot-short": _prism((4 * math.pi - 8, 4 * math.pi + 4), (0, 0, 1), (2, 4, 2)),
}

_NO_SOLID = "ValueError: Cannot find a solid on the stack or in the parent chain"
_RAISES = {
    "through-no-solid": _NO_SOLID,
    "through-no-solid-or-wires": _NO_SOLID,
    "through-no-wires": "ValueError: No pending wires present",
    "through-ring": "OCP.OCP.Standard.Standard_OutOfRange: NCollection_Sequence::Value",
    "slot-equal": "OCP.OCP.StdFail.StdFail_NotDone: BRep_API: command not done",
}
_INVALID = {"slot-short": "BRepCheck_Analyzer: shape is not valid"}


class _Record(TypedDict):
    name: str
    program: str
    report: dict[str, object]


def _read_records() -> dict[str, _Record]:
    rows: list[_Record] = json.loads(_RECORDS.read_text(encoding="utf-8"))
    assert [row["name"] for row in rows] == sorted(probe.constructed_programs())
    return {row["name"]: row for row in rows}


_REPORTS = _read_records()


def test_each_probe_is_recorded_and_checked() -> None:
    """Every report belongs to the exact probe program and has an expectation."""
    assert {name: row["program"] for name, row in _REPORTS.items()} == probe.constructed_programs()
    assert sorted([*_PARTS, *_RAISES, "through-side"]) == sorted(_REPORTS)
    for row in _REPORTS.values():
        assert row["report"]["program_sha256"] == program_sha256(row["program"])
        OracleVersions.model_validate(row["report"]["versions"])


@pytest.mark.parametrize("name", sorted(_PARTS))
def test_measured_profiles_match_the_closed_form(name: str) -> None:
    """Hold volume, area, centroid, bounds and solid count even on an invalid shape."""
    report = _REPORTS[name]["report"]
    status = OracleStatus.INVALID if name in _INVALID else OracleStatus.OK
    assert report["status"] == status.value
    assert report["message"] == _INVALID.get(name, "")
    got = OracleMeasures.model_validate(report["measures"])
    want = _PARTS[name]
    assert got.solids == want.solids
    assert figures_agree(got, want), (got, want)


@pytest.mark.parametrize("name", sorted(_RAISES))
def test_exception_is_reported_verbatim(name: str) -> None:
    """Distinguish failure to find the solid, the wires and to build the tool."""
    report = _REPORTS[name]["report"]
    assert report["status"] == OracleStatus.RUNTIME.value
    assert report["message"] == _RAISES[name]
    assert report["measures"] is None


def test_side_cut_is_one_solid() -> None:
    """The side bore completes and reports one solid despite the measure error."""
    report = _REPORTS["through-side"]["report"]
    assert report["status"] == OracleStatus.OK.value
    assert OracleMeasures.model_validate(report["measures"]).solids == 1


@pytest.mark.xfail(
    reason="oracle-cut-thru-all-side: the side bore exceeds ADR-0005's measure tolerance",
    raises=AssertionError,
    strict=True,
)
def test_side_cut_matches_the_closed_form() -> None:
    """Hold the recorded side bore to its closed form with ADR-0005's constants."""
    got = OracleMeasures.model_validate(_REPORTS["through-side"]["report"]["measures"])
    want = OracleMeasures.model_validate_json(_SIDE_EXPECTED.read_text(encoding="utf-8"))
    assert figures_agree(got, want), (got, want)

#!/usr/bin/env python3
"""Record CadQuery through cuts, profile placement and size limits on the oracle.

    uv run tools/cq_profile_probe.py [--out-dir tests/fixtures/profiles]

Writes one entry per construction in name order to `constructed.json`, with
the program, oracle status, exception text, measures and versions. The
programs run on oracle zygotes (ADR-0013). The fixture README gives the
geometry, which `tests/test_profile_probe.py` checks offline.
"""

from __future__ import annotations

import argparse
import json
import pathlib
from collections import Counter
from collections.abc import Sequence

import oracle_run
from arris_gym.fidelity import OracleReport

_FIXTURES = pathlib.Path(__file__).resolve().parent.parent / "tests" / "fixtures"
OUT = _FIXTURES / "profiles"
_SIDE_CUT = _FIXTURES / "regression" / "oracle-cut-thru-all-side" / "oracle.py"
TIMEOUT = 30.0
WORKERS = 4
# The 10-unit constructions have variation in the last digits of GProp
# measures across zygotes. Record 12 decimal places, finer than ADR-0005's
# agreement tolerance, and leave the variable STEP hash out of this record.
MEASURE_DECIMALS = 12

_XY = 'cq.Workplane("XY")'
_BOX = f"{_XY}.box(10, 8, 4)"
_TOP = f'{_BOX}.faces(">Z").workplane()'
# Two 10 by 8 by 4 boxes with disjoint height intervals.
_STACKED = f'{_BOX}.union(cq.Workplane("XY", origin=(0, 0, 8)).box(10, 8, 4))'

CONSTRUCTED: dict[str, str] = {
    # Through the same stock from different planes, and the errors' order.
    "through-on-face": f"result = {_TOP}.moveTo(1, -2).circle(1).cutThruAll()",
    "through-inside": f"result = {_TOP}.workplane(offset=-1).moveTo(1, -2).circle(1).cutThruAll()",
    "through-above": f"result = {_TOP}.workplane(offset=3).moveTo(1, -2).circle(1).cutThruAll()",
    "through-below": f"result = {_TOP}.workplane(offset=-7).moveTo(1, -2).circle(1).cutThruAll()",
    "through-miss": f"result = {_TOP}.moveTo(8, 0).circle(1).cutThruAll()",
    "through-overhang": f"result = {_TOP}.moveTo(5, 0).rect(4, 2).cutThruAll()",
    "through-compound": f"result = {_STACKED}.workplane(offset=3).circle(1).cutThruAll()",
    "through-no-solid": f"result = {_XY}.circle(1).cutThruAll()",
    "through-no-wires": f"result = {_TOP}.cutThruAll()",
    "through-no-solid-or-wires": f"result = {_XY}.cutThruAll()",
    "through-ring": f"result = {_TOP}.moveTo(1, -1).circle(2).circle(1).cutThruAll()",
    "blind-ring-through-depth": f"result = {_TOP}.moveTo(1, -1).circle(2).circle(1).cutBlind(-5)",
    "through-polygon": f"result = {_TOP}.polygon(4, 4).cutThruAll()",
    "through-path": (
        f"result = {_TOP}.moveTo(-1, -1).lineTo(2, -1).lineTo(-1, 1).close().cutThruAll()"
    ),
    "through-circles-at-points": (
        f"result = {_TOP}.pushPoints([(-3, -1), (2, 2)]).circle(0.5).cutThruAll()"
    ),
    "through-rects-at-points": f"result = {_TOP}.rarray(4, 3, 2, 2).rect(2, 1).cutThruAll()",
    # A second wire centred on the first, in both containment orders.
    "rect-on-rect": f"result = {_XY}.moveTo(1, -2).rect(6, 4).rect(2, 1).extrude(2)",
    "rect-on-rect-outer-last": f"result = {_XY}.moveTo(1, -2).rect(2, 1).rect(6, 4).extrude(2)",
    "rect-on-circle": f"result = {_XY}.moveTo(1, -2).circle(3).rect(2, 1).extrude(2)",
    "rect-on-circle-outer-last": f"result = {_XY}.moveTo(1, -2).circle(1).rect(6, 4).extrude(2)",
    "circle-on-rect": f"result = {_XY}.moveTo(1, -2).rect(6, 4).circle(1).extrude(2)",
    "circle-on-rect-outer-last": f"result = {_XY}.moveTo(1, -2).rect(2, 1).circle(3).extrude(2)",
    "rects-edge-touch": f"result = {_XY}.pushPoints([(0, 0), (2, 0)]).rect(2, 2).extrude(2)",
    "rects-corner-touch": f"result = {_XY}.pushPoints([(0, 0), (2, 2)]).rect(2, 2).extrude(2)",
    "rects-overlap": f"result = {_XY}.pushPoints([(0, 0), (1, 0)]).rect(2, 2).extrude(2)",
    "through-rects-edge-touch": (
        f"result = {_TOP}.pushPoints([(0, 0), (2, 0)]).rect(2, 2).cutThruAll()"
    ),
    "through-rects-overlap": (
        f"result = {_TOP}.pushPoints([(0, 0), (1, 0)]).rect(2, 2).cutThruAll()"
    ),
    # Origin changes, replacing the points while retaining pending wires.
    "center-circle": f"result = {_XY}.center(2, -1).circle(1).extrude(2)",
    "center-twice": f"result = {_XY}.center(2, -1).center(-1, 3).circle(1).extrude(2)",
    "center-after-move": f"result = {_XY}.moveTo(-3, 4).center(2, -1).circle(1).extrude(2)",
    "center-before-move": f"result = {_XY}.center(2, -1).moveTo(-3, 4).circle(1).extrude(2)",
    "center-after-points": (
        f"result = {_XY}.pushPoints([(-3, 4), (3, 4)]).center(2, -1).circle(1).extrude(2)"
    ),
    "center-before-array": f"result = {_TOP}.center(1, -1).rarray(4, 2, 2, 2).hole(1)",
    "center-on-face": (
        f'result = {_BOX}.faces(">X").workplane().center(1, -0.5).circle(1).extrude(2)'
    ),
    "center-on-pending": f"result = {_XY}.moveTo(-2, 1).circle(0.5).center(2, -1).extrude(2)",
    "center-between-profiles": (
        f"result = {_XY}.moveTo(-2, 1).circle(0.5).center(2, -1).circle(1).extrude(2)"
    ),
    # Rectangles at the origin, one point, and several points.
    "rect-origin": f"result = {_XY}.rect(4, 2).extrude(2)",
    "rect-at-point": f"result = {_XY}.moveTo(1, -2).rect(4, 2).extrude(2)",
    "rect-at-center": f"result = {_XY}.center(1, -2).rect(4, 2).extrude(2)",
    "rects-at-points": f"result = {_XY}.pushPoints([(-3, -1), (2, 2)]).rect(2, 1).extrude(2)",
    "rects-at-polar-points": f"result = {_XY}.polarArray(3, 0, 360, 4).rect(2, 1).extrude(2)",
    "rect-blind": f"result = {_TOP}.moveTo(1, -2).rect(4, 2).cutBlind(-1)",
    "rect-negative-x": f"result = {_XY}.rect(-4, 2).extrude(2)",
    "rect-negative-y": f"result = {_XY}.rect(4, -2).extrude(2)",
    "rect-negative-both": f"result = {_XY}.rect(-4, -2).extrude(2)",
    "rect-zero-x": f"result = {_XY}.rect(0, 2).extrude(2)",
    "rect-zero-y": f"result = {_XY}.rect(4, 0).extrude(2)",
    # A 6 by 2 slot has a straight segment of length 4 between its arc centres.
    "slot-0": f"result = {_XY}.slot2D(6, 2, 0).extrude(2)",
    "slot-45": f"result = {_XY}.slot2D(6, 2, 45).extrude(2)",
    "slot-90": f"result = {_XY}.slot2D(6, 2, 90).extrude(2)",
    "slot-at-point": f"result = {_XY}.moveTo(1, -2).slot2D(6, 2, 90).extrude(2)",
    "slots-at-points": f"result = {_XY}.pushPoints([(-3, -2), (2, 1)]).slot2D(6, 2, 90).extrude(2)",
    "slot-through": f"result = {_TOP}.center(1, -1).slot2D(6, 2, 45).cutThruAll()",
    "slot-equal": f"result = {_XY}.slot2D(4, 4, 0).extrude(2)",
    "slot-short": f"result = {_XY}.slot2D(2, 4, 0).extrude(2)",
}

_HEAD = "import cadquery as cq\n\n"
_SHOW = "\nshow_object(result)\n"


def constructed_programs() -> dict[str, str]:
    """The constructions as whole programs, by name."""
    programs = {name: _HEAD + body + _SHOW for name, body in CONSTRUCTED.items()}
    programs["through-side"] = _SIDE_CUT.read_text(encoding="utf-8")
    return dict(sorted(programs.items()))


def _rounded(value: float) -> float:
    return round(value, MEASURE_DECIMALS) or 0.0


def _record(report: OracleReport) -> dict[str, object]:
    record = report.model_dump(mode="json", exclude={"step", "step_sha256", "seconds"})
    got = report.measures
    if got is not None:
        record["measures"] = {
            "volume": _rounded(got.volume),
            "area": _rounded(got.area),
            "centroid": [_rounded(x) for x in got.centroid],
            "bounds": [[_rounded(x) for x in point] for point in got.bounds],
            "faces": got.faces,
            "solids": got.solids,
        }
    return record


def main(argv: Sequence[str] | None = None) -> int:
    """Run the constructions and write their recorded oracle measurements."""
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n", 1)[0])
    parser.add_argument("--out-dir", type=pathlib.Path, default=OUT)
    parser.add_argument("--workers", type=int, default=WORKERS)
    args = parser.parse_args(argv)
    constructions = constructed_programs()
    reports = oracle_run.run_many(
        list(constructions.values()), timeout=TIMEOUT, workers=args.workers
    )
    out = [
        {"name": name, "program": text, "report": _record(report)}
        for (name, text), report in zip(constructions.items(), reports, strict=True)
    ]
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "constructed.json").write_text(
        json.dumps(out, sort_keys=True, indent=1) + "\n", encoding="utf-8"
    )
    counts = Counter(report.status.value for report in reports)
    print(f"{len(out)} constructions: {dict(sorted(counts.items()))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""What CadQuery's `rarray`, `polarArray` and `cutBlind` build, read on the oracle (ADR-0019).

The evidence of ADR-0019. Each construction in `CONSTRUCTED` is an own program
whose answer has a closed form: a box or a revolved part bored at the points
an array stacks, or cut by `cutBlind` from a circle, a ring or circles at
points. They run as they are on oracle zygotes (ADR-0013), with no prelude:
the oracle's own report (status, its message verbatim, the measures) is the
record.

    uv run tools/cq_array_probe.py [--out-dir tests/fixtures/arrays]

writes `constructed.json`, one entry per construction sorted by name: its name,
program text and the oracle's report less `step` and `seconds`. Two runs give
the same bytes. `tests/test_array_probe.py` holds each report to its closed
form. Outside the gate: the oracle environment is needed.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from collections.abc import Sequence

import oracle_run

OUT = pathlib.Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "arrays"
TIMEOUT = 30.0
WORKERS = 4

_HEAD = "import cadquery as cq\n\n"
_SHOW = "\nshow_object(result)\n"
# The box, 10 by 8 by 4 about the origin, and its top face's plane: the origin
# (0, 0, 2), x along +x.
_BOX = 'cq.Workplane("XY").box(10, 8, 4)'
_TOP = f'{_BOX}.faces(">Z").workplane()'
# A solid cylinder of radius 5 from y = 0 to y = 4, revolved as the corpus's
# `bellows` and `dome_cap` are: a profile on XY turned about its y axis.
_REV = (
    'cq.Workplane("XY").polyline([(0, 0), (5, 0), (5, 4), (0, 4)]).close()'
    ".revolve(360, (0, 0, 0), (0, 1, 0))"
)
# The same with a bore of radius 2 through it: a flange.
_TUBE = (
    'cq.Workplane("XY").polyline([(2, 0), (5, 0), (5, 4), (2, 4)]).close()'
    ".revolve(360, (0, 0, 0), (0, 1, 0))"
)

# Own programs, each a construction with a closed form
# (`tests/fixtures/arrays/README.md` gives them).
CONSTRUCTED: dict[str, str] = {
    # `rarray(xSpacing, ySpacing, xCount, yCount)`.
    "rarray-1x1": f"result = {_TOP}.rarray(2, 3, 1, 1).hole(1)",
    "rarray-3x2": f"result = {_TOP}.rarray(3, 4, 3, 2).hole(1)",
    "rarray-side>X": f'result = {_BOX}.faces(">X").workplane().rarray(2, 1.5, 2, 2).hole(1)',
    "rarray-side<Y": f'result = {_BOX}.faces("<Y").workplane().rarray(3, 1.5, 3, 2).hole(1)',
    "rarray-circle-extrude": f"result = {_TOP}.rarray(4, 3, 2, 2).circle(1).extrude(1)",
    "rarray-spacing-zero": f"result = {_TOP}.rarray(0, 1, 2, 2).hole(1)",
    "rarray-spacing-negative": f"result = {_TOP}.rarray(2, -1, 2, 2).hole(1)",
    "rarray-count-zero": f"result = {_TOP}.rarray(2, 2, 0, 2).hole(1)",
    "rarray-count-float": f"result = {_TOP}.rarray(2, 2, 2.0, 2).hole(1)",
    # `polarArray(radius, startAngle, angle, count)`.
    "polar-full": f"result = {_TOP}.polarArray(3, 0, 360, 6).hole(1)",
    "polar-full-start": f"result = {_TOP}.polarArray(3, 30, 360, 4).hole(1)",
    "polar-full-negative": f"result = {_TOP}.polarArray(3, 0, -360, 4).hole(1)",
    "polar-partial": f"result = {_TOP}.polarArray(3, 0, 90, 3).hole(1)",
    "polar-partial-start": f"result = {_TOP}.polarArray(3, 30, 120, 3).hole(1)",
    "polar-partial-negative": f"result = {_TOP}.polarArray(3, 0, -90, 2).hole(1)",
    "polar-count-1-full": f"result = {_TOP}.polarArray(3, 0, 360, 1).hole(1)",
    "polar-count-1-partial": f"result = {_TOP}.polarArray(3, 45, 90, 1).hole(1)",
    "polar-radius-negative": f"result = {_TOP}.polarArray(-3, 0, 90, 2).hole(1)",
    "polar-radius-zero": f"result = {_TOP}.polarArray(0, 0, 360, 3).hole(1)",
    "polar-side>X": f'result = {_BOX}.faces(">X").workplane().polarArray(1.5, 0, 90, 2).hole(0.8)',
    "polar-circle-extrude": f"result = {_TOP}.polarArray(3, 0, 360, 4).circle(0.5).extrude(1)",
    "polar-count-zero": f"result = {_TOP}.polarArray(3, 0, 360, 0).hole(1)",
    "polar-count-negative": f"result = {_TOP}.polarArray(3, 0, 360, -1).hole(1)",
    "polar-count-float": f"result = {_TOP}.polarArray(3, 0, 360, 2.0).hole(1)",
    # `cutBlind(depth)` on the box.
    "blind-disc": f"result = {_TOP}.circle(1).cutBlind(-1.5)",
    "blind-disc-off-centre": f"result = {_TOP}.moveTo(2, 1).circle(1).cutBlind(-1.5)",
    "blind-to-the-bottom": f"result = {_TOP}.circle(1).cutBlind(-4)",
    "blind-past-the-part": f"result = {_TOP}.circle(1).cutBlind(-10)",
    "blind-positive": f"result = {_TOP}.circle(1).cutBlind(1)",
    "blind-inside-the-part": f"result = {_TOP}.workplane(offset=-1).circle(1).cutBlind(-1)",
    "blind-positive-from-inside": f"result = {_TOP}.workplane(offset=-1).circle(1).cutBlind(2)",
    "blind-side>X": (
        f'result = {_BOX}.faces(">X").workplane().moveTo(1, 0.5).circle(0.5).cutBlind(-2)'
    ),
    "blind-ring": f"result = {_TOP}.circle(2).circle(1).cutBlind(-1)",
    "blind-ring-inner-first": f"result = {_TOP}.circle(1).circle(2).cutBlind(-1)",
    "blind-points": f"result = {_TOP}.pushPoints([(-3, -2), (3, 2)]).circle(0.5).cutBlind(-1)",
    "blind-polar": f"result = {_TOP}.polarArray(3, 0, 360, 6).circle(0.5).cutBlind(-1)",
    "blind-polar-through": f"result = {_TOP}.polarArray(3, 0, 360, 6).circle(0.5).cutBlind(-4)",
    "blind-rarray": f"result = {_TOP}.rarray(4, 3, 2, 2).circle(1).cutBlind(-1)",
    "blind-zero": f"result = {_TOP}.circle(1).cutBlind(0)",
    "blind-nothing-pending": f"result = {_TOP}.cutBlind(-1)",
    "blind-no-solid": 'result = cq.Workplane("XY").circle(1).cutBlind(-1)',
    "blind-zero-no-solid": 'result = cq.Workplane("XY").circle(1).cutBlind(0)',
    # `cutBlind` and a bore on a revolved part's end faces.
    "rev-blind-disc": f'result = {_REV}.faces(">Y").workplane().circle(1).cutBlind(-1)',
    "rev-blind-disc<Y": f'result = {_REV}.faces("<Y").workplane().circle(1).cutBlind(-1)',
    "rev-blind-whole-face": f'result = {_REV}.faces(">Y").workplane().circle(5).cutBlind(-1)',
    "rev-blind-ring": f'result = {_REV}.faces(">Y").workplane().circle(2).circle(1).cutBlind(-1)',
    "rev-blind-polar": (
        f'result = {_REV}.faces(">Y").workplane().polarArray(3, 0, 360, 6).circle(0.5).cutBlind(-1)'
    ),
    "rev-polar-hole": f'result = {_REV}.faces("<Y").workplane().polarArray(3, 0, 360, 4).hole(1)',
    "tube-blind-polar-through": (
        f'result = {_TUBE}.faces(">Y").workplane().polarArray(3.5, 0, 360, 6).circle(0.5)'
        ".cutBlind(-4)"
    ),
}


def constructed_programs() -> dict[str, str]:
    """The constructions as whole programs, by name."""
    return {name: _HEAD + body + _SHOW for name, body in sorted(CONSTRUCTED.items())}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n", 1)[0])
    parser.add_argument("--out-dir", type=pathlib.Path, default=OUT)
    parser.add_argument("--workers", type=int, default=WORKERS)
    args = parser.parse_args(argv)
    constructions = constructed_programs()
    reports = oracle_run.run_many(
        list(constructions.values()), timeout=TIMEOUT, workers=args.workers
    )
    out = [
        {
            "name": name,
            "program": text,
            "report": json.loads(report.model_dump_json(exclude={"step", "seconds"})),
        }
        for (name, text), report in zip(constructions.items(), reports, strict=True)
    ]
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "constructed.json").write_text(
        json.dumps(out, sort_keys=True, indent=1) + "\n", encoding="utf-8"
    )
    counts: dict[str, int] = {}
    for report in reports:
        counts[report.status.value] = counts.get(report.status.value, 0) + 1
    print(f"{len(out)} constructions: {dict(sorted(counts.items()))}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

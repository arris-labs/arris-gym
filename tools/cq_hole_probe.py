#!/usr/bin/env python3
"""What CadQuery's stacks of points and bore tools build, read on the oracle (ADR-0018).

The evidence of ADR-0018. Each construction in `CONSTRUCTED` is an own program
whose answer has a closed form: a box with holes, counterbores or countersinks
bored at points `pushPoints` stacks, and `faces(sel)` on a stack of faces. They
run as they are on oracle zygotes (ADR-0013), with no prelude: the oracle's own
report (status, its message verbatim, the measures) is the record.

    uv run tools/cq_hole_probe.py [--out-dir tests/fixtures/holes]

writes `constructed.json`, one entry per construction sorted by name: its name,
program text and the oracle's report less `step` and `seconds`. Two runs give
the same bytes. `tests/test_hole_probe.py` holds each report to its closed form.
Outside the gate: the oracle environment is needed.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from collections.abc import Sequence

import oracle_run

OUT = pathlib.Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "holes"
TIMEOUT = 30.0
WORKERS = 4

_HEAD = "import cadquery as cq\n\n"
_SHOW = "\nshow_object(result)\n"
# Every construction starts from one box, 10 by 8 by 4 about the origin, and
# its top face's plane: the origin (0, 0, 2), x along +x.
_TOP = 'cq.Workplane("XY").box(10, 8, 4).faces(">Z").workplane()'
_BOX = 'cq.Workplane("XY").box(10, 8, 4)'

# Own programs, each a construction with a closed form
# (`tests/fixtures/holes/README.md` gives them).
CONSTRUCTED: dict[str, str] = {
    # The stack of points.
    "points-tuple": f"result = {_TOP}.pushPoints([(2, 1)]).hole(1)",
    "points-list": f"result = {_TOP}.pushPoints([[2, 1], [-3, -2]]).hole(1)",
    "points-several": f"result = {_TOP}.pushPoints([(-3, -2), (3, 2), (3, -2)]).hole(1)",
    "points-3-tuple-below": f"result = {_TOP}.pushPoints([(2, 1, -1)]).hole(1)",
    "points-3-tuple-above": f"result = {_TOP}.pushPoints([(2, 1, 3)]).hole(1)",
    "points-empty": f"result = {_TOP}.pushPoints([]).hole(1)",
    "points-off-the-part": f"result = {_TOP}.pushPoints([(20, 0)]).hole(1)",
    "points-overlapping": f"result = {_TOP}.pushPoints([(0, 0), (0.5, 0)]).hole(1)",
    "points-duplicate": f"result = {_TOP}.pushPoints([(2, 1), (2, 1)]).hole(1)",
    "points-one-number": f"result = {_TOP}.pushPoints([(2,)]).hole(1)",
    "points-bare-number": f"result = {_TOP}.pushPoints([2]).hole(1)",
    "points-side>X": f'result = {_BOX}.faces(">X").workplane().pushPoints([(1, 0.5)]).hole(1)',
    "points-side<Y": f'result = {_BOX}.faces("<Y").workplane().pushPoints([(1, 0.5)]).hole(1)',
    "points-circle-extrude": (
        f"result = {_TOP}.pushPoints([(2, 1), (-3, -2)]).circle(0.5).extrude(1)"
    ),
    # `hole` with a depth.
    "hole-depth-blind": f"result = {_TOP}.pushPoints([(2, 1)]).hole(1, depth=1.5)",
    "hole-depth-blind-several": (
        f"result = {_TOP}.pushPoints([(2, 1), (-3, -2)]).hole(1, depth=1.5)"
    ),
    "hole-depth-to-the-bottom": f"result = {_TOP}.pushPoints([(2, 1)]).hole(1, depth=4)",
    "hole-depth-past-the-part": f"result = {_TOP}.pushPoints([(2, 1)]).hole(1, depth=10)",
    "hole-depth-no-points": f"result = {_TOP}.hole(1, depth=1.5)",
    "hole-depth-zero": f"result = {_TOP}.pushPoints([(2, 1)]).hole(1, depth=0)",
    "hole-depth-negative": f"result = {_TOP}.pushPoints([(2, 1)]).hole(1, depth=-1)",
    # `cboreHole(diameter, cboreDiameter, cboreDepth)`.
    "cbore-one": f"result = {_TOP}.pushPoints([(2, 1)]).cboreHole(1, 2, 0.5)",
    "cbore-several": (f"result = {_TOP}.pushPoints([(-3, -2), (3, 2)]).cboreHole(1, 2, 0.5)"),
    "cbore-no-points": f"result = {_TOP}.cboreHole(1, 2, 0.5)",
    "cbore-past-the-part": f"result = {_TOP}.pushPoints([(2, 1)]).cboreHole(1, 2, 5)",
    "cbore-narrower": f"result = {_TOP}.pushPoints([(2, 1)]).cboreHole(2, 1, 0.5)",
    "cbore-equal": f"result = {_TOP}.pushPoints([(2, 1)]).cboreHole(1, 1, 0.5)",
    "cbore-depth-zero": f"result = {_TOP}.pushPoints([(2, 1)]).cboreHole(1, 2, 0)",
    "cbore-depth-negative": f"result = {_TOP}.pushPoints([(2, 1)]).cboreHole(1, 2, -0.5)",
    "cbore-diameter-negative": f"result = {_TOP}.pushPoints([(2, 1)]).cboreHole(1, -2, 0.5)",
    "cbore-diameter-zero": f"result = {_TOP}.pushPoints([(2, 1)]).cboreHole(1, 0, 0.5)",
    "cbore-hole-diameter-zero": f"result = {_TOP}.pushPoints([(2, 1)]).cboreHole(0, 2, 0.5)",
    # `cskHole(diameter, cskDiameter, cskAngle)`.
    "csk-82-one": f"result = {_TOP}.pushPoints([(2, 1)]).cskHole(1, 2, 82)",
    "csk-90-one": f"result = {_TOP}.pushPoints([(2, 1)]).cskHole(1, 2, 90)",
    "csk-82-several": (f"result = {_TOP}.pushPoints([(-3, -2), (3, 2), (0, 0)]).cskHole(1, 2, 82)"),
    "csk-no-points": f"result = {_TOP}.cskHole(1, 2, 90)",
    "csk-cone-past-the-part": f"result = {_TOP}.cskHole(1, 6, 60)",
    "csk-narrower": f"result = {_TOP}.pushPoints([(2, 1)]).cskHole(2, 1, 90)",
    "csk-equal": f"result = {_TOP}.pushPoints([(2, 1)]).cskHole(1, 1, 90)",
    "csk-angle-zero": f"result = {_TOP}.pushPoints([(2, 1)]).cskHole(1, 2, 0)",
    "csk-angle-180": f"result = {_TOP}.pushPoints([(2, 1)]).cskHole(1, 2, 180)",
    "csk-angle-negative": f"result = {_TOP}.pushPoints([(2, 1)]).cskHole(1, 2, -90)",
    # The ends of ADR-0018 rule 4's range, where `tan(angle / 2)` crosses the pole
    # (-180) or comes back through zero (360): each a cone of no height.
    "csk-angle-minus-180": f"result = {_TOP}.pushPoints([(2, 1)]).cskHole(1, 2, -180)",
    "csk-angle-360": f"result = {_TOP}.pushPoints([(2, 1)]).cskHole(1, 2, 360)",
    "csk-diameter-negative": f"result = {_TOP}.pushPoints([(2, 1)]).cskHole(1, -2, 90)",
    "csk-diameter-zero": f"result = {_TOP}.pushPoints([(2, 1)]).cskHole(1, 0, 90)",
    "csk-hole-diameter-zero": f"result = {_TOP}.pushPoints([(2, 1)]).cskHole(0, 2, 90)",
    # `faces(sel)` on a stack of faces.
    "faces-faces-same": f'result = {_BOX}.faces(">Z").faces(">Z").workplane().hole(1)',
    "faces-faces-other": f'result = {_BOX}.faces(">Z").faces("<Z").workplane().hole(1)',
    "faces-faces-of-two": (
        f'result = ({_BOX}.union(cq.Workplane("XY").transformed(offset=cq.Vector(0, 0, 4))'
        '.box(2, 2, 4)).faces(">X or <X").faces(">X").workplane().hole(1))'
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

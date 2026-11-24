#!/usr/bin/env python3
"""What CadQuery's `edges`, `fillet` and `chamfer` select and build, read on the oracle (ADR-0020).

The evidence of ADR-0020. Two sets of own programs, each with a closed form:

- `SELECTIONS` end in `edges(…)`. They run with a prelude that wraps CadQuery's
  `Workplane.edges` and the worker's `show_object`: each `edges` call records
  every candidate edge (its `geomType`, centre of mass, length and ends, in
  CadQuery's collection order) and the indices of the edges it kept, sorted;
  `show_object(result)` then stops the program by raising `ProbeRecord` with
  the record of the call that made `result` as its JSON message. The worker reports
  it as a `runtime` status in the exception's own words (`tools/oracle/worker.py`),
  so nothing of the oracle changes. The kept indices are sorted because the
  `or` selector returns a `set`, whose order follows Open CASCADE's hash of a
  shape and is not the same from one run to the next.
- `BLENDS` run as they are, with no prelude: the oracle's own report (status,
  its message verbatim, the measures) is the record.

    uv run tools/cq_edge_probe.py [--out-dir tests/fixtures/edges] [--revolves]

writes `constructed.json`, one entry per construction sorted by name: its name,
kind (`selection` or `blend`), program text, and the record or the report less
`step` and `seconds`. Two runs give the same bytes. `tests/test_edge_probe.py`
holds each to its closed form. Outside the gate: the oracle environment is
needed. `--revolves` writes `revolve.json` for the full revolve selections
and neighboring cases.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from collections.abc import Sequence
from typing import Any

import oracle_run
from arris_gym.fidelity import OracleReport, OracleStatus

OUT = pathlib.Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "edges"
TIMEOUT = 30.0
WORKERS = 4
# The prefix of a record in the worker's runtime message (`format_exception_only`).
MARK = "ProbeRecord: "

# Run before a selection, in its namespace. CadQuery's own `Workplane.edges`
# is wrapped; nothing else of CadQuery is touched.
PRELUDE = r"""
import json as _pj
import cadquery as _pcq


class ProbeRecord(BaseException):
    pass


_p_edges = _pcq.Workplane.edges
_p_made = []


def _p_v(v):
    return [v.x, v.y, v.z]


def _p_edges_wrap(self, selector=None, tag=None):
    out = _p_edges(self, selector, tag)
    candidates = self._collectProperty("Edges")
    record = {
        "selector": selector,
        "stack": [type(o).__name__ for o in self.objects],
        "candidates": [
            {
                "type": e.geomType(),
                "centre": _p_v(e.Center()),
                "length": e.Length(),
                "start": _p_v(e.startPoint()),
                "end": _p_v(e.endPoint()),
            }
            for e in candidates
        ],
        "kept": sorted(
            next(i for i, e in enumerate(candidates) if e.isSame(o)) for o in out.objects
        ),
    }
    _p_made.append((out, record))
    return out


def show_object(shown):
    for made, record in _p_made:
        if made is shown:
            raise ProbeRecord(_pj.dumps(record, sort_keys=True))


_pcq.Workplane.edges = _p_edges_wrap
"""

_HEAD = "import cadquery as cq\n\n"
_SHOW = "\nshow_object(result)\n"

# The head arc is from regression/cq-rivet-edges-across-revolve-axis.
_RIVET_PATH = (
    ".moveTo(0, 0).lineTo(2.5, 0).lineTo(2.5, 3).lineTo(4, 3)"
    ".threePointArc((3.464, 4.625), (0, 6.25)).close()"
)
_REVERSE_RIVET_PATH = (
    ".moveTo(0, 6.25).threePointArc((3.464, 4.625), (4, 3))"
    ".lineTo(2.5, 3).lineTo(2.5, 0).lineTo(0, 0).close()"
)
_REVOLVE_CYLINDER = 'cq.Workplane("XY").polyline([(0, -2), (2, -2), (2, 2), (0, 2)]).close()'
REVOLVES: dict[str, str] = {
    **{
        f"rivet-{plane}": f'cq.Workplane("{plane}"){path}'
        f'.revolve(360, (0, 0, 0), (0, 1, 0)).edges("<{normal}")'
        for plane, normal, path in (
            ("XY", "Z", _RIVET_PATH),
            ("XZ", "Y", _REVERSE_RIVET_PATH),
            ("YZ", "X", _RIVET_PATH),
        )
    },
    "rivet-side": f'cq.Workplane("YZ"){_RIVET_PATH}.revolve(360, (0, 0), (0, -1)).edges(">Y")',
    "rivet-spherical": 'cq.Workplane("XY").moveTo(0, 0).lineTo(2.5, 0).lineTo(2.5, 3)'
    ".lineTo(4, 3).threePointArc((3, 4), (0, 5)).close()"
    '.revolve(360, (0, 0), (0, 1)).edges("<Z")',
    "rivet-parallel": f'cq.Workplane("XZ"){_RIVET_PATH}.revolve(360, (0, 0), (0, 1)).edges("|Z")',
    "rivet-reselect": f'cq.Workplane("XY"){_RIVET_PATH}'
    '.revolve(360, (0, 0), (0, 1)).edges("<Z").edges(">X")',
    "cylinder-side": f'{_REVOLVE_CYLINDER}.revolve(360, (0, -2, 0), (0, 2, 0)).edges(">X")',
    "cylinder-wall": f'{_REVOLVE_CYLINDER}.revolve(360, (0, -2), (0, 2)).faces(">Z").edges(">X")',
    "cylinder-reversed": 'cq.Workplane("XY", origin=(3, 1, -2))'
    ".polyline([(1, -2), (-1, -2), (-1, 2), (1, 2)]).close()"
    '.revolve(360, (1, 0), (1, -1)).edges("<X")',
    "partial": f'{_REVOLVE_CYLINDER}.revolve(180, (0, -2), (0, 2)).edges("<X")',
    "cone": 'cq.Workplane("XY").polyline([(0, -2), (2, -2), (1, 2), (0, 2)]).close()'
    '.revolve(360, (0, 0), (0, 1)).edges(">X")',
    "turned": 'cq.Workplane("XY").transformed(rotate=(0, 0, 30))'
    f'{_RIVET_PATH}.revolve(360, (0, 0), (0, 1)).edges("<Z")',
    "after-union": f"{_REVOLVE_CYLINDER}.revolve(360, (0, -2), (0, 2))"
    '.union(cq.Workplane("XY", origin=(0, 8, 0)).box(1, 1, 1)).edges(">X")',
}
# The box, 10 by 8 by 4 about the origin.
_BOX = 'cq.Workplane("XY").box(10, 8, 4)'
# A cylinder of radius 1 and height 4 along z about the origin, and one of
# radius 2.
_CYL = 'cq.Workplane("XY").cylinder(4, 1)'
_CYL2 = 'cq.Workplane("XY").cylinder(4, 2)'
# A D: the chord from (-1, 0) to (1, 0) and a half circle through (0, 1),
# extruded 1 along z.
_D = (
    'cq.Workplane("XY").moveTo(-1, 0).lineTo(1, 0).threePointArc((0, 1), (-1, 0)).close()'
    ".extrude(1)"
)
# Three quarters of the unit disc, from angle 0 to 270 degrees, extruded 1.
_PAC = (
    'cq.Workplane("XY").moveTo(0, 0).lineTo(1, 0).threePointArc((-1, 0), (0, -1)).close()'
    ".extrude(1)"
)
# The cylinder of radius 1 with its top cut off by a plane tilted 30 degrees
# about x through the axis at z = 2 - 1/cos 30: a full ellipse.
_TILT = (
    f'{_CYL}.cut(cq.Workplane("XY").transformed(offset=cq.Vector(0, 0, 2), '
    "rotate=cq.Vector(30, 0, 0)).box(10, 10, 2))"
)
# A cylinder of radius 2 along z and one of radius 1 along x, both 10 long,
# united: the two curves where they meet are B-splines.
_CROSS = 'cq.Workplane("XY").cylinder(10, 2).union(cq.Workplane("YZ").cylinder(10, 1))'
# A 10 by 8 by 2 plate with a hole of diameter 3 through it at its centre.
_PLATE = 'cq.Workplane("XY").box(10, 8, 2).faces(">Z").workplane().hole(3)'
# A tube: radius 3 outside, 1.5 inside, from z = 0 to 2.
_TUBE = 'cq.Workplane("XY").circle(3).circle(1.5).extrude(2)'
# The box with its vertical edges rounded at radius 2.
_ROUNDED = f'{_BOX}.edges("|Z").fillet(2)'
# Two 2 by 2 by 2 boxes 5 apart along x that do not meet: a compound.
_PAIR = (
    'cq.Workplane("XY").box(2, 2, 2)'
    '.union(cq.Workplane("XY").transformed(offset=cq.Vector(5, 0, 0)).box(2, 2, 2))'
)

# Cylinders CadQuery builds off the XY plane, each with the parallel selector
# along its axis, which keeps its seams (and the lines of a box along it): where
# Open CASCADE puts each seam (ADR-0020 rule 2, amended). A washer is a
# cylinder of radius 5 and height 1 or 2 about the origin with a bore of
# radius 1.5 through it from the face the selector names.
SEAMS: dict[str, str] = {
    "seam-yz-cylinder": 'cq.Workplane("YZ").cylinder(10, 2).edges("|X")',
    "seam-xz-cylinder": 'cq.Workplane("XZ").cylinder(10, 2).edges("|Y")',
    "seam-zx-cylinder": 'cq.Workplane("ZX").cylinder(10, 2).edges("|Y")',
    "seam-turned-cylinder": (
        'cq.Workplane("XY").transformed(rotate=cq.Vector(0, 0, 30)).cylinder(4, 1).edges("|Z")'
    ),
    "seam-yz-washer": (
        'cq.Workplane("YZ").cylinder(1, 5).faces(">X").workplane().hole(3).edges("|X")'
    ),
    "seam-xz-washer": (
        'cq.Workplane("XZ").cylinder(1, 5).faces("<Y").workplane().hole(3).edges("|Y")'
    ),
    "seam-xz-ring": (
        'cq.Workplane("XZ").circle(5).extrude(1).faces("<Y").workplane().hole(3).edges("|Y")'
    ),
    "seam-yz-cbore": (
        'cq.Workplane("YZ").cylinder(2, 5).faces(">X").workplane().cboreHole(2, 4, 0.5).edges("|X")'
    ),
    "seam-yz-cut-blind": (
        'cq.Workplane("YZ").cylinder(2, 5).faces(">X").workplane().circle(1.5).cutBlind(-1)'
        '.edges("|X")'
    ),
    "seam-xz-points": (
        'cq.Workplane("XZ").cylinder(2, 5).faces("<Y").workplane()'
        '.pushPoints([(2, 0), (-2, 1)]).hole(1).edges("|Y")'
    ),
}

_AXES = (">X", "<X", ">Y", "<Y", ">Z", "<Z")
_PARALLEL = ("|X", "|Y", "|Z")

# Each ends in `edges(…)`; the record is that call's.
SELECTIONS: dict[str, str] = {
    "box-edges": f"result = {_BOX}.edges()",
    **{f"box-edges{sel}": f'result = {_BOX}.edges("{sel}")' for sel in _AXES + _PARALLEL},
    "box-edges>Z or <Z": f'result = {_BOX}.edges(">Z or <Z")',
    "box-faces>Z-edges": f'result = {_BOX}.faces(">Z").edges()',
    "box-faces>Z-edges>X": f'result = {_BOX}.faces(">Z").edges(">X")',
    "box-faces>X-edges|Z": f'result = {_BOX}.faces(">X").edges("|Z")',
    "cylinder-edges": f"result = {_CYL}.edges()",
    **{
        f"cylinder-edges{sel}": f'result = {_CYL}.edges("{sel}")'
        for sel in (">Z", "<Z", ">X", ">Y", "|Z", "|X", ">Z or <Z")
    },
    "cylinder-faces>Z-edges": f'result = {_CYL}.faces(">Z").edges()',
    "d-edges>Y": f'result = {_D}.edges(">Y")',
    "d-edges<Y": f'result = {_D}.edges("<Y")',
    "pac-edges<X": f'result = {_PAC}.edges("<X")',
    "pac-edges>Y": f'result = {_PAC}.edges(">Y")',
    "tilt-edges>Z": f'result = {_TILT}.edges(">Z")',
    "cross-edges>X": f'result = {_CROSS}.edges(">X")',
    "plate-edges|Z": f'result = {_PLATE}.edges("|Z")',
    "plate-faces>Z-edges": f'result = {_PLATE}.faces(">Z").edges()',
    "rounded-edges>Z": f'result = {_ROUNDED}.edges(">Z")',
    **{name: f"result = {chain}" for name, chain in SEAMS.items()},
}

# Each is measured as it is.
BLENDS: dict[str, str] = {
    # `fillet(radius)` on the box.
    "fillet-box>Z": f'result = {_BOX}.edges(">Z").fillet(1)',
    "fillet-box|Z": f'result = {_BOX}.edges("|Z").fillet(1)',
    "fillet-box-edges": f"result = {_BOX}.edges().fillet(1)",
    "fillet-box-solid": f"result = {_BOX}.fillet(1)",
    "fillet-box-faces>Z": f'result = {_BOX}.faces(">Z").fillet(1)',
    "fillet-box>Z or <Z": f'result = {_BOX}.edges(">Z or <Z").fillet(1)',
    "fillet-box|Z-zero": f'result = {_BOX}.edges("|Z").fillet(0)',
    "fillet-box|Z-negative": f'result = {_BOX}.edges("|Z").fillet(-1)',
    "fillet-box|Z-past": f'result = {_BOX}.edges("|Z").fillet(4.5)',
    "fillet-box>Z-past": f'result = {_BOX}.edges(">Z").fillet(4.5)',
    # On a cylinder, its rims and its seam.
    "fillet-cylinder>Z": f'result = {_CYL2}.edges(">Z").fillet(0.5)',
    "fillet-cylinder-edges": f"result = {_CYL2}.edges().fillet(0.5)",
    "fillet-cylinder|Z": f'result = {_CYL2}.edges("|Z").fillet(0.5)',
    "fillet-cylinder-empty": f'result = {_CYL2}.edges("|X").fillet(0.5)',
    # Rims of a hole and of a tube.
    "fillet-tube>Z": f'result = {_TUBE}.edges(">Z").fillet(0.5)',
    "fillet-plate-faces>Z": f'result = {_PLATE}.faces(">Z").edges().fillet(0.5)',
    # A blend along edges an earlier fillet made: the rounded box's top.
    "fillet-rounded>Z": f'result = {_ROUNDED}.faces(">Z").edges().fillet(0.5)',
    "fillet-compound|Z": f'result = {_PAIR}.edges("|Z").fillet(0.5)',
    "fillet-no-solid": 'result = cq.Workplane("XY").fillet(1)',
    # `chamfer(length)`.
    "chamfer-box>Z": f'result = {_BOX}.edges(">Z").chamfer(1)',
    "chamfer-box|Z": f'result = {_BOX}.edges("|Z").chamfer(1)',
    "chamfer-box|Z-zero": f'result = {_BOX}.edges("|Z").chamfer(0)',
    "chamfer-box|Z-negative": f'result = {_BOX}.edges("|Z").chamfer(-1)',
    "chamfer-box|Z-past": f'result = {_BOX}.edges("|Z").chamfer(4.5)',
    "chamfer-cylinder>Z": f'result = {_CYL2}.edges(">Z").chamfer(0.5)',
    "chamfer-cylinder>Z or <Z": f'result = {_CYL2}.edges(">Z or <Z").chamfer(0.5)',
    "chamfer-cylinder-edges": f"result = {_CYL2}.edges().chamfer(0.5)",
    "chamfer-cylinder|Z": f'result = {_CYL2}.edges("|Z").chamfer(0.5)',
    "chamfer-cylinder-empty": f'result = {_CYL2}.edges("|X").chamfer(0.5)',
    "chamfer-tube>Z": f'result = {_TUBE}.edges(">Z").chamfer(0.5)',
    "chamfer-plate-faces>Z": f'result = {_PLATE}.faces(">Z").edges().chamfer(0.5)',
    # A chamfer along a fillet's edges: two blends meeting at the rounded
    # corners' vertices.
    "chamfer-rounded>Z": f'result = {_ROUNDED}.edges(">Z").chamfer(0.5)',
    "chamfer-compound|Z": f'result = {_PAIR}.edges("|Z").chamfer(0.5)',
    "chamfer-no-solid": 'result = cq.Workplane("XY").chamfer(1)',
    # CadQuery's fillet less its `clean()`: `Solid.fillet` on the same edges.
    "unclean-fillet-box|Z": (f'b = {_BOX}\nresult = b.val().fillet(1, b.edges("|Z").vals())'),
    "unclean-fillet-box-edges": f"b = {_BOX}\nresult = b.val().fillet(1, b.edges().vals())",
    "unclean-fillet-cylinder-edges": (
        f"b = {_CYL2}\nresult = b.val().fillet(0.5, b.edges().vals())"
    ),
    "unclean-fillet-rounded>Z": (
        f'b = {_ROUNDED}\nresult = b.val().fillet(0.5, b.faces(">Z").edges().vals())'
    ),
}


def constructed_programs() -> dict[str, tuple[str, str]]:
    """The constructions as whole programs, by name: (kind, text)."""
    out: dict[str, tuple[str, str]] = {}
    for name, body in SELECTIONS.items():
        out[name] = ("selection", _HEAD + body + _SHOW)
    for name, body in BLENDS.items():
        out[name] = ("blend", _HEAD + body + _SHOW)
    return dict(sorted(out.items()))


def record_of(report: OracleReport) -> dict[str, Any] | None:
    """The probe's record carried in a runtime report's message, or None."""
    if report.status is not OracleStatus.RUNTIME:
        return None
    last = report.message.splitlines()[-1] if report.message else ""
    if not last.startswith(MARK):
        return None
    record: dict[str, Any] = json.loads(last[len(MARK) :])
    return record


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n", 1)[0])
    parser.add_argument("--out-dir", type=pathlib.Path, default=OUT)
    parser.add_argument("--workers", type=int, default=WORKERS)
    parser.add_argument("--revolves", action="store_true")
    args = parser.parse_args(argv)
    constructions = (
        {
            name: ("selection", _HEAD + f"result = {chain}" + _SHOW)
            for name, chain in sorted(REVOLVES.items())
        }
        if args.revolves
        else constructed_programs()
    )
    texts = [
        (PRELUDE + text) if kind == "selection" else text for kind, text in constructions.values()
    ]
    reports = oracle_run.run_many(texts, timeout=TIMEOUT, workers=args.workers)
    out: list[dict[str, Any]] = []
    for (name, (kind, text)), report in zip(constructions.items(), reports, strict=True):
        entry: dict[str, Any] = {"name": name, "kind": kind, "program": text}
        if kind == "selection":
            record = record_of(report)
            entry["record"] = record
            entry["status"] = "record" if record is not None else report.status.value
            entry["message"] = "" if record is not None else report.message
        else:
            entry["report"] = json.loads(report.model_dump_json(exclude={"step", "seconds"}))
        out.append(entry)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / ("revolve.json" if args.revolves else "constructed.json")).write_text(
        json.dumps(out, sort_keys=True, indent=1) + "\n", encoding="utf-8"
    )
    counts: dict[str, int] = {}
    for entry in out:
        status = entry["status"] if entry["kind"] == "selection" else entry["report"]["status"]
        counts[status] = counts.get(status, 0) + 1
    print(f"{len(out)} constructions: {dict(sorted(counts.items()))}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

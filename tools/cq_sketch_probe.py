#!/usr/bin/env python3
"""Record CadQuery's sketch faces after each call and its final extrusion.

Run with the synced oracle environment: uv run tools/cq_sketch_probe.py.
The traced and untraced programs run in separate children of oracle zygotes.
"""

from __future__ import annotations

import argparse
import json
import pathlib
from collections import Counter
from collections.abc import Sequence
from textwrap import indent

import oracle_run
from arris_gym.fidelity import OracleReport, OracleStatus

OUT = pathlib.Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "sketch"
# The worker's exception-only formatter carries the trace back to this tool.
MARK = "SketchTrace: "

_PRELUDE = """
import json as _json
import math as _math
import traceback as _traceback


class SketchTrace(Exception):
    pass


_trace = []


def _snapshot(call, sketch):
    faces = sketch._faces.Faces()
    areas = [f.Area() for f in faces]
    centres = [f.Center().toTuple() for f in faces]
    area = _math.fsum(areas)
    centroid = [
        _math.fsum(a * c[axis] for a, c in zip(areas, centres)) / area
        for axis in range(3)
    ] if area else None
    _trace.append(dict(call=call, faces=len(faces), area=area, centroid=centroid))
"""

# Each case starts with s on XY. The optional tool has its own origin so
# face(tool) can distinguish its local faces from its workplane placement.
_INIT = 's = cq.Workplane("XY").sketch()'
_TOOL_INIT = 'tool = cq.Workplane("XY", origin=(17, 19, 0)).sketch()'
_FINALIZE = "w = s.finalize()"
_EXTRUDE = "result = w.extrude(2)"
_TRIANGLE = ("segment((0, 0), (4, 0))", "segment((0, 2))")
_MODES = {"add": "a", "subtract": "s", "intersect": "i", "construction": "c", "unknown": "other"}

_CALLS: dict[str, tuple[str, ...]] = {
    **{
        f"{kind}-{mode_name}": (*base, f"rect(2, 2, mode={mode!r})")
        for mode_name, mode in _MODES.items()
        for kind, base in (("empty", ()), ("nonempty", ("rect(6, 4)",)))
    },
    "push-rect-rect-s": ("push([(-4, 1), (3, 1)])", "rect(4, 4)", "rect(2, 2, mode='s')"),
    "assemble-at-selection": (
        "push([(5, 3)])",
        *_TRIANGLE,
        "close()",
        "assemble()",
        "reset()",
        "assemble()",
    ),
    "face-at-selection": ("push([(5, 3)])", "face(tool)", "reset()", "face(tool)"),
    "intersect-at-disjoint-points": (
        "rect(10, 4)",
        "push([(-3, 0), (3, 0)])",
        "rect(2, 2, mode='i')",
    ),
    "intersect-at-overlapping-points": (
        "rect(10, 4)",
        "push([(-1, 0), (1, 0)])",
        "rect(4, 2, mode='i')",
    ),
    "cut-to-empty": ("rect(2, 2)", "rect(4, 4, mode='s')"),
    "disjoint-adds": ("rect(2, 2)", "push([(5, 1)])", "rect(4, 2)"),
    "ring": ("circle(2)", "circle(1, mode='s')"),
    "circle-zero": ("circle(0)",),
    "circle-negative": ("circle(-2)",),
    "rect-zero-width": ("rect(0, 2)",),
    "rect-zero-height": ("rect(4, 0)",),
    "rect-negative-width": ("rect(-4, 2)",),
    "rect-negative-height": ("rect(4, -2)",),
    "close-already-closed": (*_TRIANGLE, "segment((0, 0))", "close()"),
    "close-without-edges": ("close()",),
    "assemble-without-edges": ("assemble()",),
    "assemble-open-chain": (*_TRIANGLE, "assemble()"),
    "assemble-ordered-chain": (*_TRIANGLE, "close()", "assemble()"),
    "assemble-unordered-chain": (
        "segment((4, 0), (0, 2))",
        "segment((0, 0), (4, 0))",
        "segment((0, 0), (0, 2))",
        "assemble()",
    ),
    "assemble-half-disc": ("segment((-1, 0), (1, 0))", "arc((0, 1), (-1, 0))", "assemble()"),
    "assemble-half-disc-three-point-arc": (
        "arc((1, 0), (0, 1), (-1, 0))",
        "close()",
        "assemble()",
    ),
    "assemble-reversed-arc-at-selection": (
        "push([(3, 5)])",
        "segment((-1, 0), (1, 0))",
        "arc((-1, 0), (0, 1), (1, 0))",
        "assemble()",
    ),
    "segment-three-coordinates": (
        "segment((0, 0, 0), (4, 0))",
        "segment((0, 2))",
        "close()",
        "assemble()",
    ),
    "arc-three-coordinates": (
        "arc((1, 0), (0, 1, 0), (-1, 0))",
        "close()",
        "assemble()",
    ),
    "segment-without-edges": ("segment((4, 0))",),
    "arc-without-edges": ("arc((0, 1), (-1, 0))",),
}


def _program(name: str, *, traced: bool = False) -> str:
    steps = [(_INIT, "s")]
    if name == "face-at-selection":
        steps += [
            (_TOOL_INIT, "tool"),
            ("tool.push([(1, -1)])", "tool"),
            ("tool.rect(2, 2)", "tool"),
        ]
    steps += [(f"s.{call}", "s") for call in _CALLS[name]]
    steps.append((_FINALIZE, "s"))

    head = "import cadquery as cq\n\n"
    if not traced:
        return head + "\n".join(line for line, _ in steps) + f"\n{_EXTRUDE}\n"
    body = "".join(f"{line}\n_snapshot({line!r}, {sketch})\n" for line, sketch in steps)
    return (
        head
        + _PRELUDE
        + "\n_error = ''\ntry:\n"
        + indent(body + f"{_EXTRUDE}\n", "    ")
        + "except Exception as _exc:\n"
        + "    _error = ''.join(_traceback.format_exception_only(type(_exc), _exc)).rstrip('\\n')\n"
        + "raise SketchTrace(_json.dumps(dict(snapshots=_trace, error=_error)))\n"
    )


def constructed_programs() -> dict[str, str]:
    """Return the untraced programs in name order."""
    return {name: _program(name) for name in sorted(_CALLS)}


def _read_trace(name: str, traced: OracleReport, untraced: OracleReport) -> list[dict[str, object]]:
    if traced.status is not OracleStatus.RUNTIME or not traced.message.startswith(MARK):
        raise RuntimeError(
            f"{name}: missing sketch trace ({traced.status.value}: {traced.message})"
        )
    trace = json.loads(traced.message[len(MARK) :])
    expected_error = untraced.message if untraced.status is OracleStatus.RUNTIME else ""
    if trace["error"] != expected_error or untraced.status not in (
        OracleStatus.OK,
        OracleStatus.INVALID,
        OracleStatus.RUNTIME,
    ):
        raise RuntimeError(
            f"{name}: sketch trace and oracle report disagree: {trace['error']!r}, "
            f"{untraced.status.value}: {untraced.message}"
        )
    snapshots: list[dict[str, object]] = trace["snapshots"]
    return snapshots


def main(argv: Sequence[str] | None = None) -> int:
    """Write constructed.json with one row per sketch, in name order."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=pathlib.Path, default=OUT)
    parser.add_argument("--workers", type=int, default=oracle_run.DEFAULT_WORKERS)
    args = parser.parse_args(argv)

    programs = constructed_programs()
    n = len(programs)
    reports = oracle_run.run_many(
        [*programs.values(), *(_program(name, traced=True) for name in programs)],
        workers=args.workers,
    )
    rows = [
        {
            "name": name,
            "program": program,
            "snapshots": _read_trace(name, traced, report),
            "report": report.model_dump(mode="json", exclude={"step", "seconds"}),
        }
        for (name, program), report, traced in zip(
            programs.items(), reports[:n], reports[n:], strict=True
        )
    ]
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "constructed.json").write_text(
        json.dumps(rows, sort_keys=True, indent=1, allow_nan=False) + "\n", encoding="utf-8"
    )
    counts = Counter(report.status.value for report in reports[:n])
    print(f"{n} constructions: {dict(sorted(counts.items()))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# CadQuery sketch traces

`tools/cq_sketch_probe.py` writes `constructed.json` from 37 constructed
programs on CadQuery 2.3.0 and `cadquery-ocp` 7.9.3.0. The probe runs outside
the gate in the synced oracle environment.

```sh
uv sync --locked --project tools/oracle
uv run --locked tools/cq_sketch_probe.py
```

Each record contains the program, a snapshot after each successful sketch
call, and the standard oracle report for the untraced program, with STEP text
and elapsed time omitted. A snapshot names the call and records the number
of faces in the sketch's `_faces`, their total area, and their area-weighted
centroid in sketch coordinates. The centroid is null when the total area is
zero. A failed call ends the trace at the preceding snapshot. The report
preserves the oracle's status and message and includes the measured extrusion
when the oracle built a shape.

| Constructions | Observation |
|---|---|
| `push-rect-rect-s` | Both rectangle calls use the same two points. The result is two rectangular rings of area 12 each. |
| `assemble-at-selection`, `face-at-selection` | The pushed point translates the new faces. After `reset()`, the next call uses the origin as its placement. The second `assemble()` can still use the original edges. `face(tool)` uses the tool's local face coordinates, including its own push, and ignores the tool's workplane origin. |
| `empty-*`, `nonempty-*`, `cut-to-empty` | Subtraction and intersection on a fresh sketch raise `Null TopoDS_Shape object`. Subtracting a larger rectangle from an existing one leaves an empty sketch that fails at extrusion with `No pending wires present`. Mode `c` without a tag and an unknown mode both raise on a fresh or populated sketch. |
| `intersect-at-*-points` | The intersection retains both regions of disjoint tools. Overlapping tools leave three sketch faces of total area 12, which extrude to one solid with a 6 × 2 section. |
| `disjoint-adds`, `ring` | Separate adds can extrude to two solids. Subtracting a concentric disc leaves a ring. |
| `circle-*`, `rect-*` | Zero and negative circle radii raise different exceptions. A negative rectangle dimension builds the same part as its positive magnitude. A zero dimension makes an unbounded plane and the extrusion is invalid. The recorded measures for those invalid extrusions are kernel diagnostics. |
| `close-already-closed`, `assemble-*-chain` | Closing creates a zero-length segment and raises when the chain is already closed. An open chain yields a face, then an invalid extrusion. The unordered closed chain assembles and extrudes as the triangle. |
| `assemble-half-disc*`, `*-without-edges` | Both arc forms make the half-disc with its chord. An implicit start for a segment or arc requires a preceding edge. |
| `close-without-edges`, `assemble-without-edges` | Closing with no edges raises `ValueError`. Assembly raises `IndexError` on the oracle and `ValueError` in `cq`. |
| `assemble-ordered-chain`, `assemble-reversed-arc-at-selection` | The triangle in drawing order has the same measures as the shuffled triangle. Reversing an arc keeps its middle point and the selection translates the assembled half-disc. |
| `*-three-coordinates` | The oracle's tuple dispatch refuses the third coordinate. The dialect returns `unsupported_api`. |

A run with four zygotes and a run with one produced identical bytes.
`tests/test_sketch_probe.py` checks the recorded call order, closed forms
for the bounded sections and valid prisms, and the exact statuses and
messages on failures. The test reads the records offline.

## Sketch extrusion fixtures

The fixture directories hold sketch programs and closed-form measures or
expected statuses. `tests/test_cq_sketch.py` checks each program against
either the matching trace above or the fixture's own `oracle.json`. It
checks negative extrusion on a shifted YZ plane, placement selection,
grouped intersections, mutation after `finalize()` and fusion with a
solid earlier in the chain. It also checks triangle and half-disc assembly,
including a reversed arc and two assemblies of the same edges with
different selections. The cases that use sketch forms outside the
subset record how CadQuery handles those programs. `Sketch.clean` has a
refusal fixture for the unsupported method.

The prism fold's known kernel limits have strict fixtures under
`regression/`. `cq-sketch-corner-contact` expects two solids that touch
along a vertical edge. `cq-sketch-common-after-contact` expects an empty
intersection after a fuse. `cq-sketch-fuse-nested-prisms` expects the
outermost of three nested prisms.

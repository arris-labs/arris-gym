# ADR-0023: A `cq` sketch extrudes as an ordered fold of prisms

- Status: accepted
- Date: 2026-11-21
- Plan: `lift-sketches` step 2

## Context

CAD-Recode draws planar regions with `Workplane.sketch()`, combines them
on the sketch plane and extrudes the final section. arris can extrude closed
profiles and combine solids through `fuse`, `cut` and `common`
([wheel API](../ARRIS_API.md)). ADR-0014 sets CAD-Recode's fidelity target.

The [sketch probe](../../tests/fixtures/sketch/README.md) records the faces
after each call and the extrusion on CadQuery 2.3.0. `tests/test_sketch_probe.py`
checks the bounded sections and valid prisms against closed forms and holds
the failure statuses and messages. These records settle the grouping and
edge rules.

| Construction | Oracle observation |
|---|---|
| `intersect-at-disjoint-points` | One `i` call retains two disjoint 2 × 2 regions. Extrusion by 2 has volume 16 in two solids. |
| `intersect-at-overlapping-points` | One `i` call leaves three sketch faces of total area 12. Extrusion by 2 has volume 24 in one solid. |
| `assemble-unordered-chain`, `assemble-open-chain` | The shuffled triangle includes an edge drawn in reverse and extrudes to volume 8. The open chain produces a sketch face whose extrusion is `invalid`. |

Additional oracle probes distinguished two kinds of aliasing. When a 2 × 2
rectangle grows to 4 × 4 after `finalize()`, extruding that workplane by 2
gives volume 32. Adding the 2 × 2 tool via `face` before growing the tool to
4 × 4 leaves the receiving sketch's extrusion at volume 8.

## Decision

**1. A mutable sketch sits on a frozen Workplane.** `sketch()` accepts an
empty stack and keeps the workplane's directed frame. CadQuery places a
sketch at each object's centre on a nonempty stack. That form ends
`unsupported_api` in `cq`. The sketch keeps a selection of plane-local points,
free edges in drawing order, and an ordered fold of calls, each with a mode
and its placed regions. Each sketch call changes and returns that sketch,
except `finalize()`, which returns the derived workplane whose stack holds
the same sketch. `extrude` reads the fold when called. `cq.Sketch()` remains
outside the subset (ADR-0007).

**2. One call places a group of regions.** `push` replaces the selection,
`reset` clears it, and the selection stays in effect across other calls.
`circle` places a disc and `rect` places a centred rectangle with its width
along local x. `assemble` places the loop made from the free edges. `face`
places a snapshot of the other sketch's fold in its plane-local coordinates,
including the other sketch's own selections as applied to its regions.
The other workplane's frame is ignored. Each call places its region or fold
at every selected point, using the origin when the selection is empty
(`push-rect-rect-s`, `assemble-at-selection`, `face-at-selection`). A nested
fold is evaluated on its own before its prisms are combined with the parent,
so a hole in an added region only removes material from that region.

**3. The free edges must assemble into one closed loop.** Both `segment`
and `arc` can take an explicit start. With an implicit start they continue
from the last edge's end. `close()` adds a line from the last end to the
first start. These operations require a preceding edge and raise
`ValueError("No free edges available")` without one (`segment-without-edges`,
`arc-without-edges`, and a separate `close()` probe). `close()` raises
`ValueError` if the line would have zero length (`close-already-closed`,
where CadQuery reports `StdFail_NotDone`).
`assemble()` follows matching endpoints from the first edge, reversing
edges as needed and consuming all free edges in a single loop. It keeps the
free edges for a later `assemble()`. For an open chain it raises
`ValueError("Sketch.assemble() free edges do not form one closed loop")` at
assembly (`runtime`). The `assemble-open-chain` record holds CadQuery's
`invalid` extrusion separately. The closed loop rule also admits a loop
whose last arc already ends at its start (`assemble-half-disc`).

**4. Extrusion evaluates the fold left to right.** For the current section
`S`, let `T` be the union of all placements from one call. Mode `a` replaces
`S` with `S ∪ T`, `s` with `S ∖ T`, and `i` with `S ∩ T`. Visit placements
in selection order. Apply adds and subtracts in sequence with `fuse` and
`cut`. For intersection, intersect each placement with the original `S`
and fuse the surviving pieces in selection order. This distributes the
intersection over the union and avoids fusing the extended tools.

A direct arris 0.11.1 probe used a 4 × 4 base with two 4 × 4 tools centred
at (−1, 0) and (1, 0). Fusing the extended tools raised `OpDegenerateError`.
Intersecting each tool with the base and fusing those results gave the
closed-form volume of 32 for an extrusion by 2. CadQuery gave the same
volume for the corresponding two-point `i` call.

An `s` or `i` on an empty section raises `ValueError("Null TopoDS_Shape object")`
(`empty-subtract`, `empty-intersect`). Mode `c` without a tag and unknown
modes raise CadQuery's `ValueError` with its message (`*-construction`,
`*-unknown`). Negative rectangle dimensions use their magnitudes
(`rect-negative-width`, `rect-negative-height`). Zero rectangle dimensions
raise `ValueError` (`rect-zero-width`, `rect-zero-height`, where CadQuery
makes an unbounded plane and its extrusion is `invalid`). Nonpositive
circle radii also raise `ValueError` (`circle-zero`, `circle-negative`).

For a distance `d`, take the prism from 0 to `|d|` on the axis of extrusion,
the plane normal for positive `d` and its reverse for negative `d`.
Extrusion by the same interval commutes with union, difference and
intersection. `cq` extrudes the added regions over that interval and folds
with arris's solid operations. The cut and common tools instead extend from
`−|d|` to `2|d|` on that axis so their caps lie beyond the target's caps.
The portion of each tool inside the target's interval is unchanged.

An empty section has no solid. arris 0.11.1 raises `OpDegenerateError` for
both a cut of a fully covered target and the common of disjoint solids.
Before cutting or intersecting, `Model.interference` determines whether
the operation would leave no material. A cut is empty when `a_in_b` is
true for the target against the tool. A common is empty when `kind` is
`apart` or `touching`, and equals the target when `a_in_b` is true. A cut
that empties the section and a common that retains the whole target each
settle the current call. A later add can start a new section. In the oracle
probe, adding a 1 × 1 rectangle after `cut-to-empty` produces volume 2
when extruded by 2. If the fold finishes empty, `extrude` raises
`ValueError("No pending wires present")` (`cut-to-empty`). When it finishes
with material, `extrude` combines it with the nearest solid in the chain
if present (ADR-0007, ADR-0016).

## Consequences

- `disjoint-adds` extrudes to a compound (ADR-0016). A single solid can have
  a different decomposition into faces across the kernels. ADR-0005 carries
  the face counts and judges the measured geometry.
- Open chains and rectangles with a zero dimension end `runtime` in `cq`.
  The recorded oracle extrusions have status `invalid` (ADR-0006). All
  968 committed [CAD-Recode oracle rows](../../tests/fixtures/c2/cadrecode/oracle.jsonl.gz)
  are `ok`.
- Kernel refusals keep their typed outcome and verbatim details. Step 7 of
  `lift-sketches` measures how often the prism fold reaches one.

## Alternatives considered

- **Apply each intersection to the previous placement's result.** Two
  disjoint placements would leave nothing. The probe gives both solids.
- **Make an extrusion from the open chain.** The oracle can form a face
  from it, then its checker rejects the extrusion. Requiring one closed
  loop surfaces the error at the sketch call.
- **Evaluate planar booleans before extruding.** That would need planar
  operations on lines, arcs and circles with holes. The prism fold uses the
  pinned wheel's solid operations and preserves the section's point set.

## Amendment (2026-11-21): keep the prism fold for interior cuts

CAD-Recode reaches 968/968. The table has 873 agreements, 75 arris
refusals (51 `OpDegenerateError`, 17 `OpInternalError`, seven
`OpProfileError`), one arris bug, and 19 `occt_wrong` rows. It has zero
`cq_bug`, `by_design`, unclassified and timed-out rows. The
[CAD-Recode table](../../tests/fixtures/c2/cadrecode/README.md) records
the digests and verdicts. With the analytic area and flux integrated
along the planar and cylindrical trim curves, 18 new measure gaps fall
within ADR-0005's tolerances for arris. The oracle's default GProp
integration lies outside them.

The fold still cuts even when the tool lies strictly inside the section.
Two reduced section cuts touch the outer boundary at one point
(`regression/cq-sketch-tangent-cut-from-left` and
`regression/cq-sketch-tangent-cut-from-bottom`). A profile with a strictly
interior hole would exclude that contact. The checker failure is a fuse
of a post to a cap with its footprint tangent to an edge
(`regression/cq-sketch-post-tangent-to-cap`). The direct prism fold
keeps the same operation order for both ordinary and contact cases.

## Amendment (2026-11-21): free-edge validation

`arc` rejects collinear points with `ValueError` at the drawing call, for
both explicit and implicit starts. CadQuery rejects those constructions
even if the program never assembles the edge. The collinear-arc regression
fixtures hold both forms.

`assemble` uses exact endpoint equality. CadQuery joins the 1e-8 gap in
`regression/cq-sketch-assemble-near-endpoints`. That construction remains
a strict expected failure pending a decision on join tolerance.

# ADR-0028. A `cq` mirror joins a half outline in its drawing plane

- Status: accepted
- Date: 2026-11-26

## Context

BenchCAD writes `mirrorY()` after a sequence of lines in all 92
`gusseted_bracket` and 173 `i_beam` programs. The start and end of each
outline lie on the workplane's y axis. The form takes static reach to
15,718 of 17,900 on BenchCAD and 968 of 968 on CAD-Recode.

CadQuery assembles its free edges, reflects the resulting wires about
the local y axis and attempts to consolidate all the wires. The pinned
oracle closes the line-wire probes when the separation of each pair is
at most 1e-7 drawing units, including when both pairs have that gap
(`mirror-y-join-limit`). Just above that limit, two unjoined pairs leave
two open wires. Extrusion raises `ValueError("Cannot build face(s): outer
wire is not closed")`. One joined pair leaves one open wire, which
extrusion returns as an invalid shape. The fixture probes are
`both-above-join-limit` and `one-above-join-limit`.

## Decision

The subset accepts one drawn open path. It reflects each original
segment by negating the local x coordinate and traverses the reflection
in reverse drawing order. An arc keeps its reflected middle point. The
result holds one closed profile in the same frame. The earlier branch
keeps the half outline.

Both ends meet their corresponding reflections on the axis. For
horizontal end segments, the subset joins gaps of at most 1e-7 by
placing the common vertices on the axis. A nonzero gap at a curved or
sloped end raises `UnsupportedApi`, since moving such an endpoint can
change the supporting curve. `arc-gap` and `sloped-gap` show volume
differences of 2.7e-8 and 5.0e-9 relative when the endpoints are moved
in x alone. Extending the sloped line to the axis along its original
direction also exceeds the fidelity tolerance.

Exactly coincident straight runs along the axis at either end are
omitted from the boundary. The two halves of a straight edge across the
axis form one edge, as on the cleaned oracle prism. This keeps an edge
selector from passing a tangent seam to a later blend. The rectangular,
gusset and I-section fixtures check the cleaned face counts as well as
the geometry.

A call with no drawn edges on an empty or point-only pen raises
`ValueError("No pending wires present")`. Two separate open wires raise
the oracle's extrusion error at the mirror call. One joined pair,
coincident or cross-matched ends, a path confined to the axis, already
closed profiles, other stack objects and carried wires raise
`UnsupportedApi`. The context records give the oracle outcomes.

## Consequences

The mirrored profile uses the existing straight extrusion, cut and
revolution routes. The tested plane changes carry it at the drawing
placement. With stock, the existing consumer fuses or cuts the solid
and consumes the wire on its result.

A loft through a mirrored section raises `UnsupportedApi`. The oracle
loft retains the axis vertices of the joined wire. The adapter merges
the straight axis seams for the sweep operations it supports. In the
rectangle loft probe, the merged profile yields volume 15⅓ and the oracle
yields 15¼. `loft-after-mirror` records that case.

The strict regressions retain the geometry of a profile that touches the
axis between its ends and the exact bounds of in-plane rotated arcs.
The `mirrors` fixtures record the two half outlines used by the corpus,
a reflected lens on a translated YZ plane, open endpoints, and
follow-on operations. The property checks trapezoids drawn from either
side and in either order, in every named frame, with signed heights.

## Alternatives considered

Keeping every original and reflected edge would retain tangent seams
on the extruded solids. Implementing general wire consolidation would
also require deciding how to represent open, disjoint and touching
wires on the stack. The corpus paths use one joined profile.

## Sources

CadQuery 2.3.0's `Workplane.mirrorY`, `consolidateWires`, `Plane.mirrorInPlane`
and `Wire.combine` are listed in [PROVENANCE.md](../../PROVENANCE.md).
The last passes 1e-9 to Open CASCADE's edge connector. The join limit above
comes from measured outcomes on OCCT 7.9.3.0.

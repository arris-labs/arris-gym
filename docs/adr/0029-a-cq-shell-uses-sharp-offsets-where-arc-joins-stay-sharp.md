# ADR-0029. A `cq` shell uses sharp offsets where arc joins stay sharp

- Status: accepted
- Date: 2026-11-26

## Context

The BenchCAD census adds 330 programs with `Workplane.shell(num)`. Every
prefix is a box with a single axis end selected. In 101 prefixes, all in
the tray family, a chamfer precedes the face selection. Each thickness
is negative. CadQuery uses its arc join by default. The arris 0.12.0
`Solid.shell` takes a positive magnitude, an offset side and a list of
openings. It intersects offset faces with sharp joins.

## Decision

`Workplane.shell(thickness)` looks for the nearest solid on the current stack
and then up the parent chain. Only face groups on the current stack supply
openings. Flatten the selected groups in order to their constituent
arris faces under ADR-0022. A solid stack or an edge stack supplies an
empty list, which makes a sealed cavity. Return one solid on the caller's
plane with the caller as parent. Selectors on it start from the new
solid. The caller's branch keeps its original selection (ADR-0007).

Use the inward sharp offset where the retained surfaces can meet without
a new round join. A single convex planar stock meets this condition for
the measured box and chamfered tray cases. The open-ended circular
cylinder probe also agrees, with coaxial cylindrical walls and a planar
floor. The box probes cover one opening, adjacent openings, and no
opening. The sealed box has one solid and two boundary shells.

A positive finite thickness needs an outward arc join at the convex
edges in the box probe. An inward offset can need a new rounded join
where two retained surfaces meet at a reentrant edge. An L-shaped prism
with one end open shows that difference even with negative thickness.
Refuse outward arc joins and inward geometry without established join
equivalence as `unsupported_api`. Explicit join arguments are outside
the subset. Static reach still follows ADR-0012 and keeps all 330 stems.

Missing stock raises `ValueError` with CadQuery's message. The measured
compound and already sealed stock probes are `runtime` in CadQuery.
Refuse multiple boundary shells as `runtime` at the call. This covers
both tested stock configurations. Zero and non-finite thickness on the
box go to the kernel's validation, where they yield `arris_refusal`
with the kernel's kind and message. An infeasible finite inward offset
also keeps the kernel's refusal. CadQuery returned the original stock
in the oversized box probe.

## Evidence

The [shell fixtures](../../tests/fixtures/shells/README.md) give the
offset planes and closed-form measures for the tray prefixes in XY, XZ
and YZ. The stock end face, the rim plane and both rim loops are checked.
The three arris bodies meet the ADR-0005 tolerance against the construction.
CadQuery's STEP exports, measured after import, also meet it. The
oracle's own integration reports volumes outside the tolerance on all
three. The reduced oracle regression preserves this discrepancy for
ADR-0006 verdicts when replay evidence supports them.

The strict regressions for outward convex joins and inward reentrant
joins retain the default arc geometry. Their intersection-join controls
agree with the pinned wheel and show where the sharp offsets diverge.

## Sources

See [PROVENANCE.md](../../PROVENANCE.md) for the CadQuery 2.3.0 source
consulted and [ARRIS_API.md](../ARRIS_API.md) for the pinned wheel API.

# ADR-0027: A `cq` draft uses slant length and offset sections

- Status: accepted
- Date: 2026-11-26

## Context

BenchCAD bundle 5 writes `Workplane.extrude(distance, taper=angle)`.
The pinned programs make 367 circular drafts in `knob` and 455
rectangular drafts in `tee_nut`. The tee-nut tools have negative distances
and positive angles. Of the knob programs, 57 make one inward draft and
155 follow it with an outward draft on its cap. All of these drafts have
room for a cap. The form adds 311 stems to static reach, from 15,142 to
15,453 of 17,900. CAD-Recode stays at 968 of 968.

CadQuery 2.3.0 sends the nonzero taper to Open CASCADE 7.9.3.0's
`LocOpe_DPrism`. Its sweep uses the length of the slanted side.
The recorded oracle programs under `tests/fixtures/tapers/` and
`tests/fixtures/regression/cq-draft-*` check the construction.

## Decision

For signed slant length `d` and angle `a` in radians, the cap is at
`d cos(a)` along the drawing normal. Every edge moves towards the interior
by `|d| sin(a)` at the cap. The same positive angle shrinks the profile
on either side of the drawing plane. At distance zero the oracle ends
`runtime` from a null direction. When a profile has an inner wire,
CadQuery raises `ValueError("Inner wires not allowed with tapered extrusion")`
before considering the distance. Explicit `taper=0` uses the existing
straight sweep and retains its contexts, including rings and finalized
sketches.

The nonzero form supports one circle or rectangle in the drawing frame,
including a section carried across a plane change with the same normal
(ADR-0026). It uses the stock lookup, default fusion and wire consumption
of `extrude`. Earlier branches keep their pending wires. The two keyword
sets for `both` and `taper` have separate subset declarations. A call
giving both, even `both=False` or `taper=0`, raises `UnsupportedApi`
before reading the stack. Taper on cuts stays outside this lift.

Angles must be strictly between −90° and 90°. At 89° and −89° the
oracle builds a solid about 0.01745 units tall for a unit slant length.
At 90° the measured circle is invalid. At −90° the oracle reports a
solid about 6e-16 in volume and flat in its axial bounds. At 91° the
cap passes to the opposite side. The nonzero form refuses these angles
and nonfinite inputs. Pending arrays, polygon and slot profiles, paths,
and finalized sketches with nonzero taper are outside the measured
corpus contexts. The fixtures record their oracle outcomes and the
subset's refusals. A tilted carried circle follows its drawing normal in
the oracle and the subset keeps the plane-change restriction of ADR-0026.
A circle of radius zero or below ends `runtime` on both sides, and thus
can never reach the meridian construction. A rectangle with a zero
dimension is outside the admitted profiles. The oracle's collapsed base
yields an invalid shape in the inward case and a solid in the outward case.

## Constructions

- A circular draft uses the full revolution of a straight-sided meridian.
  When the requested inset reaches the radius, the meridian ends at the
  apex. The oracle matches the cone at collapse and past it.
- An inward rectangular draft with two nonempty caps is a ruled loft of
  rectangles with corresponding vertices. Its side faces are planar.
  At collapse the limit is a ridge along the longer direction, or a
  point on a square. A triangular prism with two wedge cuts produces
  these limits. The square and 4 × 3 oracle probes continue about
  1.414e-6 beyond the limit at 45°. Their volume differences from the
  independent closed forms are about 1.1e-6 and 2.2e-6 relative.
  The strict expected failures retain ADR-0005's tolerances.
- An outward rectangular draft has a rectangular core, a wedge for
  each side, and a quarter cone for each corner. Their faces meet at
  the section's straight-to-round transitions. This gives the rounded
  offset boundary and four analytic conical sides. The cap faces remain
  split on arris. For edge selection and blending on the draft, use the
  boundaries of the unified faces (ADR-0022). The rounded cap, its
  workplane, a hole and either spelling of the upper-rim chamfer have
  recorded comparisons. A chamfer of all edges fails on both sides in
  `rounded-all-edges`.

The two constructive acceptance fixtures use slant lengths √10 and √5
to obtain axial heights 3 and 2 respectively. Their volumes are 7π for
the circular frustum and 56/3 for the square draft. Both kernels agree
with their closed forms and with each other. The properties check volume,
area, centroid, bounds and solid count for signed drafts on all admitted
named planes.

## Consequences

The bounds of tilted circular and rectangular drafts and in-plane
rotated rounded drafts can be wider than the extreme points of their
sections. The regressions retain their exact boxes. An outward
rectangular draft with an offset shorter than the kernel's tolerance
can receive its typed refusal. Circular and square drafts with cap edges
just short of collapse can also hit that limit. These cases are outside
the BenchCAD taper stems.

The replay still needs to classify full-program surface and boolean
measurement gaps. The recorded `knob_000063_s20260506` prefix agrees before
its first cut. With the first cut alone, the independent volume integral
differs from arris by about 2e-11 relative and from the oracle by about
1.8e-7. The calculation is in `regression/oracle-draft-knob-first-cut`.

## Sources

The CadQuery entry points and oracle version are listed in
`PROVENANCE.md`. The lengths and offsets also follow from
[Open CASCADE 7.9.3's draft prism constructor](https://github.com/Open-Cascade-SAS/OCCT/blob/V7_9_3/src/LocOpe/LocOpe_DPrism.cxx#L336-L360).

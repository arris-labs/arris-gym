# ADR-0025: A vertex blend's corner patch is each kernel's own

- Status: accepted
- Date: 2026-11-23
- Amends: ADR-0014's "none `by_design`" for this anchor alone

## Context

Two BenchCAD rows of plans/lift-rects-and-through-cuts step 7,
`locator_block_001595_s20260505` and `locator_block_008469_s20260505`,
fillet a box's top face first (`faces(">Y").fillet(r1)`) and its edges along
the top face's normal last (`edges("|Y").fillet(r2)`, r2 < r1). Three blends
meet at each of the top's four corners: the two top fillets, already mitred
where they cross, and the vertical fillet, which ends against both.

Both kernels build both parts, one solid each. Every face but the ones at
the corners agrees to 1e-12. At each corner arris ends the vertical
fillet's cylinder higher and closes the corner with a four-sided NURBS patch
with one degenerate edge; Open CASCADE sets the cylinder back further and
closes it with a three-sided B-spline patch. The tables' area differs by
8.8e-7 (`001595`) and 7.5e-8 (`008469`) of the part's, volume by less.

A rolling ball defines a fillet along an edge. Where three blends meet at a
vertex, it does not: the patch that fills the corner is a kernel's choice
(a setback, a fitted surface), and there is no closed form, so no
construction can show either kernel wrong. ADR-0006 classes such a
difference `by_design` when a doc makes it intended. ADR-0014's target
forbids an in-subset `by_design` row, because the only `by_design` it had in
view was a behaviour `cq` declines, which must leave the subset (ADR-0012).

## Decision

**A vertex blend's corner patch is each kernel's own.** Where a blend ends
against other blends at a vertex, so that three or more meet there, a
difference confined to the patch that closes the corner is a semantic
difference between the kernels, by design. Such a row is `by_design` on
this anchor.

`tools/cq_closed_forms.py --by-design STEM=ANCHOR` classes a row on it only
where `check_by_design_cause` holds: both sides end `ok` with one solid,
their volume, area and centroid differ by no more than `CORNER_PATCH_REL`
(1e-5, eleven times the larger of the two rows' area differences) and their
boxes by no more than `BOUNDS_ABS`.

**ADR-0014's "none `by_design`" is amended for this anchor alone.** A
corpus meets the target with in-subset `by_design` rows on this anchor;
each is named in the corpus's README, and `in_subset_by_design` counts
them. Any other in-subset `by_design` row still fails the target: a
behaviour `cq` declines leaves the subset.

## Consequences

- BenchCAD's two rows are `by_design`; `in_subset_by_design` is 2.
- The anchor does not class a measure gap a closed form can settle: a
  corner of two blends with its third edge sharp is a mitre, and
  `part_measures` (its `Round`s) holds both kernels to it.
- arris is asked nothing: the patch is its choice. A program whose corner
  patches arris refuses is an arris refusal, as before.

## Alternatives considered

- **Leaving the rows unclassified.** The cycle stays red on two rows no
  evidence can ever settle.
- **An arris refusal of every vertex blend, or a patch matched to Open
  CASCADE's.** That puts CadQuery's shape into arris (gym.md).

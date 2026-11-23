# arris-cut-fused-bore-tool-flush

Found by plans/lift-holes-and-points step 1, building CadQuery's
`cboreHole` tool as CadQuery 2.3.0 builds it (`cq.py`, `cboreHole`): a bore
cylinder fused with a counterbore cylinder, both starting on the workplane,
then cut from the part. arris 0.10.0 fuses the two cylinders (6 faces: the
tool's end stays split by the bore's circle) and refuses the cut,
`OpDegenerateError` "degenerate result: the faces touch along a curve
interior to both result faces", wherever the tool's end lies on the part's
face, which is every `cboreHole` and `cskHole` (a cylinder fused with a cone
is refused the same way). The same fused tool started 0.5 above the face cuts
to the closed form, and so do the two cylinders as two tools of one cut,
which ADR-0018 builds instead (`tests/test_hole_probe.py`). The refusal looks
like the one of `cq-union-three-coplanar-cylinders`: a coplanar contact with
a face split by an edge.

The oracle builds this part: `tests/fixtures/holes/constructed.json`,
`cbore-one`, holds the same closed form.

Desired: `ok`, the measures of the closed form in `expected.json`'s `note`. Not on `cq`'s path
(ADR-0018 cuts the pieces), so not yet reported to arris; a candidate for
`../arris/docs/ideas/union-coplanar-third-operand.md`.

Still failing as above on arris 0.11.1, the same words and numbers (plans/bump-arris-0-11 step 3, 2026-11-16).

arris 0.12.0 builds the expected geometry.

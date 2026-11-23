# cq-hole-tangent-column

Found by plans/lift-face-selectors step 6's battery of what a `hole` leaves on
the stack (a `union` or a `cut` after it; both fail the same way). A box with a
bore of diameter 1 from its top, cut by a 1 x 1 column along the bore's axis:
the cylinder's surface is tangent to the column's four sides. arris 0.10.0
refuses it, `OpInternalError` "kernel bug: the face arrangement is not a
subdivision: a section edge of f9 ends at a node nothing else reaches"
(`arris_refusal`); CadQuery 2.3.0 builds the box less the column (V = 184, one
solid), as its recorded run of the same program shows. With a bore of diameter
0.9 or 1.1 the cut builds. Not a corpus shape: no BenchCAD program does this.

Desired: `ok`, the closed form of `expected.json`'s `note`. Reported to arris in `../arris/docs/ideas/hole-tangent-column.md`.

Still failing as above on arris 0.11.1, the same words and numbers (plans/bump-arris-0-11 step 3, 2026-11-16).

arris 0.12.0 builds the expected geometry.

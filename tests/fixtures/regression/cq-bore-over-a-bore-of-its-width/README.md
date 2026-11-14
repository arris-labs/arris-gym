# cq-bore-over-a-bore-of-its-width

Found by plans/lift-holes-and-points step 6, running `cboreHole` and `cskHole` after a `hole` (the stack then holds the solid, so the second call bores at its centroid, not at the face). Not a corpus program's text: no BenchCAD program writes a second bore on the same axis.

A through hole of r = 1/2 at the origin, then `cboreHole(1, 2, 0.5)` (the same call with `cskHole(1, 2, 90)` ends the same, and so does a counterbore of 1.5 or a depth of 5): the second call's tools start at the plane z = 0, a bore cylinder of r = 1/2 whose wall is the wall of the existing hole, and a cylinder of r = 1 over it. arris 0.10.0 refuses the cut, `OpDegenerateError` "degenerate result: the faces touch along a curve interior to both result faces"; CadQuery 2.3.0 builds the through hole with an annular chamber (its record is `oracle.json`, which agrees with the closed form of `expected.json`'s `note`). The same cut with a bore of another width (`cboreHole(0.5, 2, 0.5)`, `cboreHole(2, 3, 0.5)`) or with no bore (`cboreHole(0, 2, 0.5)`) builds, and so does `hole(1).hole(2)`: the refusal is a coincident wall with a wider tool from the same plane.

Desired: `ok`, the closed form. Marked strict `xfail` until an arris release cuts it. Reported to arris as item 8 of `../arris/docs/ideas/fuse-contact-refusals.md` (a coplanar contact whose face is split by an edge).

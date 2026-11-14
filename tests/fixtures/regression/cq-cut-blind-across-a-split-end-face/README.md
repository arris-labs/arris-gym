# cq-cut-blind-across-a-split-end-face

Shrunk from the 42 `bellows` programs of
[BenchCAD](https://huggingface.co/datasets/BenchCAD/BenchCAD) `code_gen` at revision
`5919f578ab09ec283603a082fab07c7639ab56eb`,
[CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/), whose holes (`polarArray(...)`, `circle(r)`,
`cutBlind(-t)` from each end) all end `arris_refusal`, "degenerate result: the faces touch along a curve
interior to both result faces" (e.g. `bellows_000367_s20260505`); the shape of the programs, not
their text. Their revolved profile has a vertex on the bottom edge (`(32.12, 0.0)` between `(12.167, 0.0)` and
`(35.1, 0.0)`), which splits the end face into a disc and an annulus, and each hole's circle crosses
that edge: of the 67 in-subset `bellows` programs that write `cutBlind`, the 42 whose holes cross it are
refused and the 25 whose holes lie clear of it are built (and unclassified, the Open CASCADE error of
`ok-cut-blind-corpus-bellows`). Here a cylinder of radius 10 and height 3 with a vertex at (6, 0) takes
a pocket of radius 7, 1 deep, across that circle. The same cut without the vertex, or inside the disc
(radius 5), builds; a `hole(14)` and a `circle(7).extrude(-1)` across the circle are refused the same, so
it is not `cutBlind`'s: a tool flush with a face split by an edge it crosses.

The oracle builds this part (volume 788.5398, area 860.7964, one solid), the closed form of
`expected.json`'s `note`. It looks like `cq-cut-blind-after-a-filled-pocket` (a face split by a
union's circles), `cq-union-three-coplanar-cylinders` and `arris-cut-fused-bore-tool-flush`.

Desired: `ok`, the measures of the closed form. Marked strict `xfail` until an arris release cuts it.
Not yet reported to arris; a candidate for `../arris/docs/ideas/union-coplanar-third-operand.md`.

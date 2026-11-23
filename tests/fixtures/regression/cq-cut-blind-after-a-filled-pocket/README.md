# cq-cut-blind-after-a-filled-pocket

Shrunk from two BenchCAD `spur_gear` programs of
[BenchCAD](https://huggingface.co/datasets/BenchCAD/BenchCAD) `code_gen` at revision
`5919f578ab09ec283603a082fab07c7639ab56eb`,
[CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/), `spur_gear_006039_s20260505` and
`spur_gear_018321_s20260505` (the 36 other in-subset `spur_gear` programs agree with the oracle): the shape of the programs, not their text. Each cuts a pocket from the gear's end
face, unites a cylinder that fills it, and cuts a second pocket from the same face; arris 0.10.0
refuses that second cut, `OpDegenerateError` "degenerate result: the faces touch along a curve
interior to both result faces" (`arris_refusal`), and the same two programs build under
CadQuery 2.3.0. Here a disc of radius 8 and height 4 takes a pocket of radius 1.5 and 2 deep, a united
cylinder of radius 2.5 that fills it, and a second pocket of radius 2.2 and 2.5 deep.

The cut is the refused step, not the union: the union alone builds, so does the second pocket
without the first, so does one whose circle lies inside the first pocket's (radius 1.0), and a second
pocket only 1 deep is refused the same, so the contact is the circle the
union leaves on the end face. It looks like `cq-union-three-coplanar-cylinders` and
`arris-cut-fused-bore-tool-flush`: a flush tool against a face split by an edge.

The oracle builds this part (volume 766.2344, area 637.7433, one solid) and holds the closed form of
`expected.json`'s `note`.

Desired: `ok`, the measures of the closed form.
Not yet reported to arris; a candidate for `../arris/docs/ideas/union-coplanar-third-operand.md`.

Still failing as above on arris 0.11.1, the same words and numbers (plans/bump-arris-0-11 step 3, 2026-11-16).

arris 0.12.0 builds the expected geometry.

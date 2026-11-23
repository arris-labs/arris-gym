# cq-tangent-cylinder-and-box

Shrunk from the 61 in-subset `hinge` programs of [BenchCAD](https://huggingface.co/datasets/BenchCAD/BenchCAD) `code_gen` at revision `5919f578ab09ec283603a082fab07c7639ab56eb`, [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/); the shape of the programs, not their text: a box
whose side face is tangent to a cylinder of the knuckle (centre 15.375 from the
axis, radius 2.975, the box's half-width 12.4). arris 0.10.0 refuses the first
union, `OpDegenerateError` "degenerate result: the faces touch along a curve
interior to both result faces"; CadQuery 2.3.0 builds a compound of two solids
(2 solids, V = box + cylinder).

Desired: `ok`, the closed form of `expected.json`'s `note`. Reported to arris
in `../arris/docs/ideas/fuse-contact-refusals.md`.

Still failing as above on arris 0.11.1, the same words and numbers (plans/bump-arris-0-11 step 3, 2026-11-16).

arris 0.12.0 builds the expected geometry.

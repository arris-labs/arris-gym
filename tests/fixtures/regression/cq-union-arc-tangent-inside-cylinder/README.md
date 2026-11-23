# cq-union-arc-tangent-inside-cylinder

Shrunk from the 25 `bearing_retainer_cap` programs of [BenchCAD](https://huggingface.co/datasets/BenchCAD/BenchCAD) `code_gen` at revision `5919f578ab09ec283603a082fab07c7639ab56eb`, [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/), that end `arris_refusal` `OpInternalError` "a section edge of f0 ends at a node nothing else reaches" (e.g. `bearing_retainer_cap_000542_s20260505`); the shape of the programs, not their text. They are `cq-union-cylinder-tangent-inside`'s slotted plates with the rounding the other way: the middle arcs' ends fall just inside the cylinder, so the arc lies inside the cylinder's circle and touches it along one line. Their `faces(...).workplane().hole(d)` is not at fault: every one of them ends the same without it. Here a unit cylinder of height 2 and a plate (a rectangle under a half disc of radius 0.5 on (0, 0.5)) inside its circle, tangent along x = 0, y = 1, standing 0.25 out of its bottom.

arris 0.10.0 refuses the union, `OpInternalError` "kernel bug: the face arrangement is not a subdivision: a section edge of f0 ends at a node nothing else reaches" (`arris_refusal`); `arris.build`'s `fuse` of the same cylinder and extruded sketch fails the same way. CadQuery 2.3.0 builds the closed form (V = 2 pi + (0.5 + pi / 8) / 4, one solid).

Desired: `ok`, the closed form of `expected.json`'s `note`. Reported to arris in `../arris/docs/ideas/union-tangent-inside.md`.

Still failing as above on arris 0.11.1, the same words and numbers (plans/bump-arris-0-11 step 3, 2026-11-16).

arris 0.12.0 builds the expected geometry.

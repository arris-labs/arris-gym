# cq-union-end-cylinders-tangent

Shrunk from the 15 `bearing_retainer_cap` programs of [BenchCAD](https://huggingface.co/datasets/BenchCAD/BenchCAD) `code_gen` at revision `5919f578ab09ec283603a082fab07c7639ab56eb`, [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/), that end `checker_fail` "loop 0 intersects itself" (e.g. `bearing_retainer_cap_000434_s20260507`); the shape of the programs, not their text. Each unites a bar with a cylinder at each end that reaches exactly the bar's end face (tangent to it along a line) and stands out of its sides. Their `faces(...).workplane().hole(d)` is not at fault: every one of them ends the same without it. Here a 30 x 5 x 1 box with cylinders of radius 3 on x = 12 and x = -12. One end cylinder builds; the second gives the invalid body. At a tenth of the size (`box(3, 0.5, 0.1)`) it builds.

arris 0.10.0 unites them into a body its checker refuses, "L5 f16: loop 0 intersects itself" and "L5 f19: loop 0 intersects itself" (`checker_fail`, `arris_bug`); `arris.build`'s two `fuse` calls give the same report. CadQuery 2.3.0 builds the closed form (V = 154.5016, one solid). The same shape at other sizes is the family's other kernel words: 3 programs `OpInternalError` (a section edge of f38), 2 `OpUnsupportedError`, 21 `ok`.

Desired: `ok`, the closed form of `expected.json`'s `note`. Reported to arris in `../arris/docs/ideas/union-tangent-inside.md`.

Still failing as above on arris 0.11.1, the same words and numbers (plans/bump-arris-0-11 step 3, 2026-11-16).

arris 0.12.0 builds the expected geometry.

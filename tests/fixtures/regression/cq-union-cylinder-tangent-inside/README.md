# cq-union-cylinder-tangent-inside

Shrunk from the 22 `bearing_retainer_cap` programs of [BenchCAD](https://huggingface.co/datasets/BenchCAD/BenchCAD) `code_gen` at revision `5919f578ab09ec283603a082fab07c7639ab56eb`, [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/), that end `checker_fail` "loops 1 and 2 intersect" (e.g. `bearing_retainer_cap_000183_s20260505`); the shape of the programs, not their text. Each unites a central cylinder with a slotted plate whose middle arcs, meant to lie on the cylinder, are rounded to three decimals so that their ends fall just outside it: the arc's circle holds the cylinder's and touches it along one line. Their `faces(...).workplane().hole(d)` is not at fault: every one of them ends the same without it, and `_000183` the same again with the hole's cylinder built by hand (`circle(5.34).extrude(-40)` from its top face). Here a unit cylinder of height 2 is united with a cylinder of radius 2 and height 1 that holds it, tangent along x = 0, y = 1.

arris 0.10.0 unites them into a body its checker refuses, "L5 f5: loops 0 and 1 intersect" and "L5 f6: loops 0 and 1 intersect" (`checker_fail`, `arris_bug`); `arris.build`'s `fuse` of the same two cylinders gives the same report. CadQuery 2.3.0 builds the closed form (V = 5 pi, A = 14 pi, one solid).

Desired: `ok`, the closed form of `expected.json`'s `note`. Marked strict `xfail` until an arris release unites a solid tangent from inside to another's face along a line. Reported to arris in `../arris/docs/ideas/union-tangent-inside.md`.

Still failing as above on arris 0.11.1, the same words and numbers (plans/bump-arris-0-11 step 3, 2026-11-16).

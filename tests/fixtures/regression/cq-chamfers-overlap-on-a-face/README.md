# cq-chamfers-overlap-on-a-face

Shrunk from the `shaft_collar` program `shaft_collar_016155_s20260505` of [BenchCAD](https://huggingface.co/datasets/BenchCAD/BenchCAD) `code_gen` at revision `5919f578ab09ec283603a082fab07c7639ab56eb`, [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/); the shape of the program, not its text. The corpus row is a collar with a stem (radius 9.75) whose top face, 3.14 wide between the bore (radius 6.61) and the rim, takes `edges(">Z").chamfer(2.2)`: both rims, 4.4 of bevel on a face 3.14 wide. Here a ring of outer radius 10 and bore radius 6, 8 high, takes `chamfer(2.5)` on its top face (4 wide, 5 of bevel), then a cross cylinder of radius 1 along y at z = 2.

The program has no solid: the two bevels meet before the face is used up.

- Open CASCADE 2.3.0 (CadQuery) builds a shape its own checker rejects: `oracle.json`, status `invalid` (`BRepCheck_Analyzer: shape is not valid`), the report of `uv run tools/oracle_run.py tests/fixtures/regression/cq-chamfers-overlap-on-a-face/program.py` (2026-11-15, `seconds` left out).
- arris 0.10.0 refuses with `OpInternalError`, "kernel bug: the face arrangement is not a subdivision: a hole of f9 lies inside no region"; without the cross cut it builds a body its checker rejects (`checker_fail`, "hole loop 0 lies outside every outer loop"). Neither says what is wrong: one chamfer past its faces is already `OpDegenerateError` ("the blend leaves its face through an edge that is not the corner's own", `tests/fixtures/cq/arris-refusal-chamfer-past-the-faces`).

So the corpus row is `arris_bug` by this fixture (`tests/fixtures/c2/benchcad/verdicts.json`): the kernel's own words call it a bug, and a blend that cannot be built is to be refused as degenerate. Desired: `arris_refusal` of kind `OpDegenerateError`, the words the kernel's (the fixture gives the kind alone; `fixture_cases.check` compares the keys a refusal expectation names). Marked strict `xfail` until an arris release refuses it. Reported to arris in `../arris/docs/ideas/overlapping-blends-refusal.md`.

Still failing as above on arris 0.11.1, the same words and numbers (plans/bump-arris-0-11 step 3, 2026-11-16).

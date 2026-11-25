# cq-revolved-cone-notches-bounds

A reduced construction for the loose bounds on the newly building
`bellows` parts of [BenchCAD](https://huggingface.co/datasets/BenchCAD/BenchCAD)
`code_gen`, revision `5919f578ab09ec283603a082fab07c7639ab56eb`,
[CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/).

A conical frustum about Y has radius 6 at y = 0 and 10 at y = 2. Two
through notches of radius 2 remove the points at x = ±10 on its top rim.
The measured X bounds on arris 0.12.0 still extend to ±10. The desired
bounds are x = ±9.8 by the circle intersections in `expected.json`.
CadQuery 2.3.0 reports those X bounds with 1e-7 of padding in `oracle.json`,
recorded with `uv run tools/oracle_run.py` on this program.

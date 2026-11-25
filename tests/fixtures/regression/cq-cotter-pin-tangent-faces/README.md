# cq-cotter-pin-tangent-faces

Reduced from `cotter_pin_000370_s20260507` in
[BenchCAD](https://huggingface.co/datasets/BenchCAD/BenchCAD) `code_gen`,
revision `5919f578ab09ec283603a082fab07c7639ab56eb`,
[CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/).

Two tangent unit-radius cylinders end at the two end discs of a half horn torus. The cylinders have equal lengths. After the head joins the cylinders, their line of tangency is inside one connected lump and its boundary pinches along that line. The desired result is a typed refusal.

CadQuery 2.3.0 builds a shape its checker rejects. The report in
`oracle.json` comes from `uv run tools/oracle_run.py` on this program.

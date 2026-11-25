# cq-cotter-pin-self-contact

Reduced from `cotter_pin_000042_s20260507` in
[BenchCAD](https://huggingface.co/datasets/BenchCAD/BenchCAD) `code_gen`,
revision `5919f578ab09ec283603a082fab07c7639ab56eb`,
[CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/).

Two tangent unit-radius cylinders of heights 1 and 2 end at the two end discs of a half horn torus. After the head joins the cylinders, their line of tangency is inside one connected lump and its boundary pinches along that line. The unequal arms exercise the self-contact refusal.

CadQuery 2.3.0 builds a shape its checker rejects. The report in
`oracle.json` comes from `uv run tools/oracle_run.py` on this program.

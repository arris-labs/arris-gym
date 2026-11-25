# cq-fillets-overlap-on-a-face

Reduced from `shaft_collar_000653_s20260505` in
[BenchCAD](https://huggingface.co/datasets/BenchCAD/BenchCAD) `code_gen`,
revision `5919f578ab09ec283603a082fab07c7639ab56eb`,
[CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/).

A ring of radii 1 and 4 and height 5 has a top face of radial width 3. Its two radius-2 fillets each need 2 units of that face, so their contact circles cross. The desired result is a typed refusal.

CadQuery 2.3.0 builds a shape its checker rejects. The report in
`oracle.json` comes from `uv run tools/oracle_run.py` on this program.

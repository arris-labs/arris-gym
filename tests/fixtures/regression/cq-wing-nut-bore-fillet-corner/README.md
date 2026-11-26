# Wing-nut bore and fillet corner

Reduced from `wing_nut_000008_s20260505` in [BenchCAD](https://huggingface.co/datasets/BenchCAD/BenchCAD)
`code_gen` at revision `5919f578ab09ec283603a082fab07c7639ab56eb`
([CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/)).
One wing on the tapered hub suffices to reproduce the refusal after the bore.
Both kernels build the unfilleted solid. arris 0.12.0 raises
`OpDegenerateError` on the fillet and identifies two edges and a vertex.
The recorded CadQuery 2.3.0 and Open CASCADE 7.9.3.0 run for this program
passes the validity check with one solid.

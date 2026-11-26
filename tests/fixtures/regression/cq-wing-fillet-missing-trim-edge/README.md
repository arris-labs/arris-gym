# Wing fillet with a missing corner edge

Reduced from `wing_nut_016440_s20260505` in [BenchCAD](https://huggingface.co/datasets/BenchCAD/BenchCAD)
`code_gen` at revision `5919f578ab09ec283603a082fab07c7639ab56eb`
([CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/)).
One wing, the tapered hub and the bore reproduce arris's
`OpInternalError` at the fillet. The recorded CadQuery 2.3.0 and Open
CASCADE 7.9.3.0 run raises `Standard_ConstructionError` on this reduction.
The original two-wing shape is invalid on the pinned oracle.
The strict regression requires the candidate to build or return a typed
geometric refusal. The desired corner geometry still needs evidence.

# Tangency between a flute and a through bore

Reduced from `knob_005588_s20260505` in [BenchCAD](https://huggingface.co/datasets/BenchCAD/BenchCAD)
`code_gen` at revision `5919f578ab09ec283603a082fab07c7639ab56eb`
([CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/)).
One flute suffices. Its radius is 0.66 and the bore radius is 1.23.
Their parallel axes are 1.89 units apart, so the voids touch along a
line inside the stock. arris 0.12.0 refuses the resulting self-contact.
The recorded CadQuery 2.3.0 and Open CASCADE 7.9.3.0 run calls the
solid valid. The strict regression requires the oracle to reject it.

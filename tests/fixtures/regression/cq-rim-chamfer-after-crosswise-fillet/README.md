# Rim chamfer after crosswise fillet

The box retains the order of the blends in u_channel_000515_s20260505, from [BenchCAD](https://huggingface.co/datasets/BenchCAD/BenchCAD) `code_gen` revision `5919f578ab09ec283603a082fab07c7639ab56eb` ([CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/)). It removes the other cuts and simplifies the dimensions.

The horizontal edge fillets leave radius-0.5 quarter cylinders where the upper rim ends. The 1.0 chamfer consumes more than that rounded corner. Arris refuses this corner arrangement. The pinned oracle builds an invalid shape for the same fixture, recorded in `oracle.json`.

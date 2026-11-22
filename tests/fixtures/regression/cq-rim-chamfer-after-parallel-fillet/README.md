# Rim chamfer after parallel fillet

The box retains the order of the blends in mounting_plate_003622_s20260505 and slotted_plate_000070_s20260507, from [BenchCAD](https://huggingface.co/datasets/BenchCAD/BenchCAD) `code_gen` revision `5919f578ab09ec283603a082fab07c7639ab56eb` ([CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/)). It removes the other cuts and simplifies the dimensions.

The vertical edge fillets leave quarter cylinders of radius 0.5 on the upper rim. The 1.0 chamfer extends beyond those fillets. Arris refuses when the chamfer crosses a neighbouring edge. The pinned oracle builds an invalid shape for the same fixture, recorded in `oracle.json`.

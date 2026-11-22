# Slotted plate chamfer after fillet

From `slotted_plate_010849_s20260505` in [BenchCAD](https://huggingface.co/datasets/BenchCAD/BenchCAD), `code_gen` revision `5919f578ab09ec283603a082fab07c7639ab56eb` ([CC-BY-4.0](https://creativecommons.org/licenses/by/4.0)). The fixture retains the operations that reproduce the blend refusal and the oracle's invalid result.

The rim has existing radius-1.31 blends, with three rectangular through cuts and four bores in the plate. The 1.42 chamfer asks arris to blend into those existing rounded corners. Arris refuses the corner arrangement. The pinned oracle builds an invalid shape for this fixture, recorded in `oracle.json`.

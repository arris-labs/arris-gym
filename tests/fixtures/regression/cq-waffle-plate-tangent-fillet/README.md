# Waffle plate tangent fillet

From `waffle_plate_014130_s20260505` in [BenchCAD](https://huggingface.co/datasets/BenchCAD/BenchCAD), `code_gen` revision `5919f578ab09ec283603a082fab07c7639ab56eb` ([CC-BY-4.0](https://creativecommons.org/licenses/by/4.0)). The fixture retains the operations that reproduce the blend refusal and the oracle's invalid result.

Opposite pockets and the central bore leave the last selector with a tangent dihedral. Its two faces meet without a corner, so arris refuses to fillet it. The pinned oracle builds an invalid shape for this fixture, recorded in `oracle.json`.

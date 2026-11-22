# Vertical fillet after rim chamfer

From `locator_block_019017_s20260505` in [BenchCAD](https://huggingface.co/datasets/BenchCAD/BenchCAD), `code_gen` revision `5919f578ab09ec283603a082fab07c7639ab56eb` ([CC-BY-4.0](https://creativecommons.org/licenses/by/4.0)). The fixture retains the operations that reproduce the blend refusal and the oracle's invalid result.

The top chamfer cuts across the ends of the vertical edges. Rounding an edge by 1.71 reaches across the 0.43 chamfer. Arris refuses when the blend crosses a neighbouring edge. The pinned oracle builds an invalid shape for this fixture, recorded in `oracle.json`.

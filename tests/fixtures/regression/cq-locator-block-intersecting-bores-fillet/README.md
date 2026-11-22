# Locator block intersecting bores fillet

From `locator_block_006933_s20260505` in [BenchCAD](https://huggingface.co/datasets/BenchCAD/BenchCAD), `code_gen` revision `5919f578ab09ec283603a082fab07c7639ab56eb` ([CC-BY-4.0](https://creativecommons.org/licenses/by/4.0)). The fixture retains the operations that reproduce the blend refusal and the oracle's invalid result.

The pocket, corner bores and side bore leave cylinder surfaces that meet the final vertical fillet. Arris refuses that cylinder-cylinder arrangement. The pinned oracle builds an invalid shape for this fixture, recorded in `oracle.json`.

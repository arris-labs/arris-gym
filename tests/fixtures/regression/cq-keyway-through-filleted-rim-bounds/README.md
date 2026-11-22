# Bounds of a keyway through a filleted rim

This reduces `cam_001007_s20260505` from [BenchCAD](https://huggingface.co/datasets/BenchCAD/BenchCAD), `code_gen` revision `5919f578ab09ec283603a082fab07c7639ab56eb` ([CC-BY-4.0](https://creativecommons.org/licenses/by/4.0)). The cylinder replaces the polygon and boss. The bore, end fillet and through keyway keep their sizes.

The cylinder begins at Y = 0 and extends along −Y. The fillet and the keyway remove material, leaving part of that end face. The exact upper bound along Y is 0. Arris 0.11.1 reports +0.0004628821772632914, also the excess in the full program. The pinned oracle's reduced report is in `oracle.json`.

The figures integrate the annular sections along Y. In the rounded section the outside radius decreases and the bore radius increases by `f (1 − cos θ)`. From each section subtract the part of the keyway rectangle outside the bore. The curved wall area uses the remaining bore arc and the straight walls use the rectangle's sides outside that arc.

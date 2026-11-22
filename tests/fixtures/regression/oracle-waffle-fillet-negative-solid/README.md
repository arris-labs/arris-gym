# Oracle waffle plate with a negatively oriented solid

This reduces `waffle_plate_000211_s20260507` from [BenchCAD](https://huggingface.co/datasets/BenchCAD/BenchCAD) `code_gen` revision `5919f578ab09ec283603a082fab07c7639ab56eb` ([CC-BY-4.0](https://creativecommons.org/licenses/by/4.0)). It removes the rim chamfer and the four corner holes.

The opposing blind cuts leave a 2 mm web wherever the central through bore does not pass. The outside margins and the web keep one connected piece after the 0.83 fillet. Arris returns a valid one-shell result. The pinned oracle reports an invalid shape with two solids after the fillet. The second solid has negative signed volume. The exact fixture's report is in `oracle.json`. Signed aggregate measures can be close despite the oracle's subshape orientation error.

`verdict.json` classes the row `occt_wrong` by signed solids (ADR-0006, amended 2026-11-23): `tools/cq_closed_forms.py`'s `signed_solid_forms` integrates each oracle solid's boundary flux at two resolutions, giving 205,928.446963 and -3,219.30888194. Their sum is the oracle's GProp volume and arris's, 202,709.138081, within `VOLUME_REL`. `tests/test_fidelity_compare.py` runs the program under `cq` and holds the verdict with `compare`. The oracle's invalid shape keeps the strict `xfail` above.

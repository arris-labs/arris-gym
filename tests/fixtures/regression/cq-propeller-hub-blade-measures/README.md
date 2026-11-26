# Measurements of four blades joined to a lofted hub

From `propeller_012902_s20260505` in [BenchCAD](https://huggingface.co/datasets/BenchCAD/BenchCAD)
`code_gen` at revision `5919f578ab09ec283603a082fab07c7639ab56eb`
([CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/)).
The hub agrees in isolation. One, two or three blades stay within
ADR-0005. The fourth exposes a relative volume gap of about 1.07e-9.

The reference integrates the oracle's trimmed boundary under ADR-0006.
Run `sketch_boundary_forms` in `tools/cq_closed_forms.py` with the
contents of `oracle.py` followed by `r = result`, `blends=True` and
subdivisions `(128, 256)`. Both resolutions agree with the recorded
CadQuery 2.3.0 and Open CASCADE 7.9.3.0 run. The candidate volume
differs. The two builds' geometric equivalence remains a Step 7 check.

# Filleted beam bore measurements

Reduced from `i_beam_000007_s20260505` in [BenchCAD](https://huggingface.co/datasets/BenchCAD/BenchCAD)
`code_gen` at revision `5919f578ab09ec283603a082fab07c7639ab56eb`
([CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/)).
Removing the chamfer preserves the gap. Removing the fillet or the
three through bores makes the two sides agree under ADR-0005.

The reference follows the oracle's trims through Green's theorem and the
divergence theorem under ADR-0006. Run `sketch_boundary_forms` in
`tools/cq_closed_forms.py` with the contents of `oracle.py` followed by
`r = result`, `blends=True` and subdivisions `(8, 16)`. The two
resolutions agree. The candidate agrees with the integral and the
recorded CadQuery 2.3.0 and Open CASCADE 7.9.3.0 volume differs.

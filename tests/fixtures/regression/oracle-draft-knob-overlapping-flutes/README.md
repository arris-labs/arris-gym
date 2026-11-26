# Measurements of two intersecting flutes in drafted stock

Reduced from `knob_000989_s20260506` in [BenchCAD](https://huggingface.co/datasets/BenchCAD/BenchCAD)
`code_gen` at revision `5919f578ab09ec283603a082fab07c7639ab56eb`
([CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/)).
The stock and the first flute agree under ADR-0005. The second flute
overlaps the first and reproduces the gap after the remaining flutes
and the axial bore are removed.

The reference integrates the trimmed planar, conical and cylindrical
boundary under ADR-0006. Run `sketch_boundary_forms` in
`tools/cq_closed_forms.py` on the contents of `oracle.py` followed
by `r = result`, with `blends=True` and subdivisions `(128, 256)`.
Both resolutions agree, and the candidate agrees with the integral.
The recorded CadQuery 2.3.0 and Open CASCADE 7.9.3.0 measures differ.

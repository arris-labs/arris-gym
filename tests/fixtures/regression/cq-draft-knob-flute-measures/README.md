# Measures of two overlapping flutes in a bored draft

Reduced from `knob_002035_s20260506` in [BenchCAD](https://huggingface.co/datasets/BenchCAD/BenchCAD)
`code_gen` at revision `5919f578ab09ec283603a082fab07c7639ab56eb`
([CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/)).
The stock, through bore and two neighboring flutes are enough for
the candidate's volume gap. Removing either flute brings its volume
within ADR-0005. The pinned full program's oracle report agrees with the
construction, while the recorded CadQuery 2.3.0 and Open CASCADE 7.9.3.0
report for this reduction differs.

The section integral in `tools/cq_closed_forms.py` uses the exposed arcs
of the stock, flute and bore circles. Each arc contributes to Green's
theorem for area and moments, and the circumference contributes to
the lateral area with the appropriate slant factor. The candidate
volume differs from the integral by 1.24e-9 relative and the oracle
volume by 1.30e-8. The strict regressions hold both kernels to the
same construction.

# Measurements of four blades joined to a lofted hub

From `propeller_012902_s20260505` in [BenchCAD](https://huggingface.co/datasets/BenchCAD/BenchCAD)
`code_gen` at revision `5919f578ab09ec283603a082fab07c7639ab56eb`
([CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/)).
The hub agrees in isolation. One, two or three blades stay within
ADR-0005. The fourth exposes a relative volume gap of about 1.08e-9.

The expected geometry comes from the union of the bored or unbored
coaxial hub and the placed blade prisms. Run `propeller_closed_form` in
`tools/cq_closed_forms.py` on the contents of `oracle.py` followed by
`\n# Export\nshow_object(result)\n`. In this fixture the hub is unbored.
Both construction quadratures converge. The candidate agrees with the
construction and the recorded CadQuery 2.3.0 and Open CASCADE 7.9.3.0
volume differs. The regression holds both kernels to the construction.

`oracle-trims.json` preserves the earlier diagnostic integral, made
with `sketch_boundary_forms`, `blends=True` and subdivisions
`(128, 256)` after appending `r = result`. That integral uses the
oracle's own trims. Its volume also differs from the construction,
so it establishes a discrepancy in the oracle's boundary.

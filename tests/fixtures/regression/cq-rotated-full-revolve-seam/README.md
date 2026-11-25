# cq-rotated-full-revolve-seam

A half-turn about Z places the cylinder's drawing side at −X. CadQuery
selects both rims with `edges(">X")` and chamfers them. The report in
`oracle.json` is from `tools/oracle_run.py` on this exact program using
CadQuery 2.3.0 and Open CASCADE 7.9.3.0.

The resulting solid is a radius-2 cylinder of length 3.5 with one conical
frustum at each end. Each frustum is 0.25 high with radii 2 and 1.75. Its
volume is π·0.25·(2² + 2·1.75 + 1.75²)/3. The area is the cylinder's
mantle, two frustum mantles of slant length 0.25·√2 and the two end discs
of radius 1.75. The centroid is the origin by symmetry.

The frame's rotation leaves inexact x and y components. The full-revolve
seam placement is limited to exact world axis directions (ADR-0020).
The bounded rule returns `unsupported_api` on this selector.

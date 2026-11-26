# Turned blade prism bounds

Reduced from `propeller_000111_s20260505` in [BenchCAD](https://huggingface.co/datasets/BenchCAD/BenchCAD)
`code_gen` at revision `5919f578ab09ec283603a082fab07c7639ab56eb`
([CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/)).
The fixture keeps one turned blade and replaces its section with a triangle.

The base triangle has vertices (0, −3), (0, 3) and (8, 0), so its area
is 24, its perimeter is 6 + 2√73 and its centroid is (8/3, 0).
Extruding by 2 gives volume 48, area 60 + 4√73 and local centroid
(8/3, 0, 1). Rotate the centroid and the six vertices by 24° about the
local X axis, then 120° about the original XZ workplane's normal. The
vertices give the six world bounds.

arris 0.12.0 agrees on the volume, area and centroid. It reports X min
near −6.373461 and Z max near 8.705258. The six vertices give −4 and
7.334940. `oracle.json` records this program under CadQuery 2.3.0 and
Open CASCADE 7.9.3.0, with all measures matching the construction.

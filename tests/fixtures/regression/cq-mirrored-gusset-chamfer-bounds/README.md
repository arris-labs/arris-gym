# Chamfered mirrored gusset bounds

Reduced from `gusseted_bracket_000041_s20260507` in [BenchCAD](https://huggingface.co/datasets/BenchCAD/BenchCAD)
`code_gen` at revision `5919f578ab09ec283603a082fab07c7639ab56eb`
([CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/)).
The fixture drops the bores and uses smaller dimensions.

The mirrored section and its prism reach Y = ±6 and Z = 0 and 6.
The +X chamfer removes material from the prism. Its X = 0 section keeps
each original Y and Z extremum. The inset retains a face at X = 8.
These points give the exact box of the one solid.

From X = 0 to X = 7.5 the section is constant. Over the chamfer it
is the same polygon inset by X − 7.5. Its vertices are the intersections
of successive offset edge lines. The shoelace area is quadratic and its
first moments are cubic in X, so Simpson's rule over the chamfer gives
the exact volume and moments there. The surface area sums the two caps,
the prism's side rectangles and the chamfer's side trapezoids.

arris 0.12.0 gives Y bounds near ±6.158114. The unchamfered prism has
the expected bounds. The report in `oracle.json` is for this program
through CadQuery 2.3.0 and Open CASCADE 7.9.3.0, which give Y = ±6 up
to rounding.

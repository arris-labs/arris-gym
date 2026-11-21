# Workplane on a nearly horizontal curved face

A box cuts a radius-3 sphere through its centre, leaving a hemisphere with
axis `n = (sin θ, 0, cos θ)` for `θ = 0.0055°`. The spherical face's centre
of mass is `1.5 n`. Its normal is close enough to +z for CadQuery to choose
global +x as the reference direction. The resulting local x axis is
`u = (cos θ, 0, −sin θ)`.

The bore of radius 0.6 and depth 1.2 is fully enclosed. Its centre is
`0.9 n + 1.75 u`. Subtract its volume and first moment from the hemisphere's
volume `18π` and first moment `18π · 1.125 n`. The bore adds its side and
both cap areas to the hemisphere's `27π`. It preserves the outer bounds.
Using global +x directly moves the bore off its workplane and shifts the
part's centroid from z ≈ 1.130536913 to z ≈ 1.130532782.

`oracle.json` is the CadQuery 2.3.0 report for `program.py`, recorded with
`uv run tools/oracle_run.py` and the elapsed time omitted.

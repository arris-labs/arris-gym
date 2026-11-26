# Bounds of an in-plane rotated rounded draft

A 4 × 3 rectangle turns 30° in XY and drafts outward 1 unit per side
at axial height 2. Its sections have areas `12 + 14t + πt²` and
perimeters `14 + 2πt` in the height fraction `t`. The caps and the
mean perimeter times slant length √5 give the surface area. The
extremes in XY are the rotated rectangular support plus the outward
offset, giving half spans `2 cos(30°) + 1.5 sin(30°) + 1` and
`2 sin(30°) + 1.5 cos(30°) + 1` on the wide cap.

`oracle.json` records `program.py` through CadQuery 2.3.0 and Open
CASCADE 7.9.3.0. The largest excess in arris 0.12.0 is about 0.36603
units at a corner's conservative bound.

# Bounds of an oblique planar draft

A 4 × 3 rectangle tilts 1° about X and drafts 2 units at 20°.
Its cap is at axial height `h = 2 cos(20°)` with an inset per side
of `q = 2 sin(20°)`. Integrate `(4 − 2qt)(3 − 2qt)` in the
height fraction `t` for volume and the axial moment. The side area
is the slant length times the mean of the two cap perimeters. The
eight cap vertices give the tight bounds.

`oracle.json` records `program.py` through CadQuery 2.3.0 and Open
CASCADE 7.9.3.0. Arris 0.12.0 encloses the exact box with a largest
excess of about 0.03280 units.

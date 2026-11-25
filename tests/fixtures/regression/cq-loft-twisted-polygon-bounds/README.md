# Twisted polygon loft bounds

Two regular nine-sided sections at Z = 0 and Z = 8 have circumradii 10 and
8. The upper section turns by 19°. Between them the paired coordinates
interpolate linearly. The section area at fraction t of the height is
(9/2) sin(2π/9) times the squared length of the interpolated first
vertex. Integrating this quadratic and its first moment gives the volume
and axial centroid. The extrema of the bilinear sides occur among their
corners, so the cap vertices give the exact bounds.

`oracle.json` records `program.py` through CadQuery 2.3.0 and Open CASCADE
7.9.3.0. The area comes from that report. Arris 0.12.0 agrees on the
volume, area and centroid. The largest bound gap is about 0.27602.

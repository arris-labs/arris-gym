# Bounds of an oblique circular draft

Radii 1 and 2, axial height 1 and a normal tilted 1° about X give a
volume of 7π/3, area π(5 + 3√2) and a centroid 17/28 of the way up
the axis. The circle of radius `r` spans `r sqrt(1 − nᵢ²)` on
either side of its centre in coordinate `i`. The extrema of the two
caps give the exact box. The reported maximum Y exceeds the upper cap's
exact projection by about 0.01745.

`oracle.json` records `program.py` through CadQuery 2.3.0 and Open
CASCADE 7.9.3.0. The program uses a revolved meridian in the subset.
The equivalent loft is `regression/cq-loft-tilted-cone-bounds`.

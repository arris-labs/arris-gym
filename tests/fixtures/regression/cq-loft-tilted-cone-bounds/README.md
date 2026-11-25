# Tilted conical loft bounds

The radii are 1 and 2, the axial length is 1 and the axis is
(0, −sin(1°), cos(1°)). The volume is 7π/3, the area is π(5 + 3√2)
and the centroid is 17/28 of the way along the axis. The projection of
each cap onto each coordinate axis extends by its radius times the
length of that coordinate axis's projection onto the cap plane.
The extremes across both projected caps give the exact box.

`oracle.json` records `program.py` through CadQuery 2.3.0 and Open CASCADE
7.9.3.0. Arris 0.12.0 reports Y max near 1.99969549. The desired value is
2 cos(1°) − sin(1°), near 1.98224298.

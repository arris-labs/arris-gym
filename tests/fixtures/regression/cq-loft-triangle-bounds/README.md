# Triangular loft bounds

The two equilateral sections have circumradii 2 and 1 and lie at Z = 0
and Z = 3. Paired vertices make a planar triangular frustum. Its volume
is 21√3/4, with centroid at Z = 33/28. The caps have total area 15√3/4.
The perimeters are 6√3 and 3√3 and the slant height is √37/2, giving
total area (15√3 + 9√111)/4. The six cap vertices bound the whole loft.

`oracle.json` records `program.py` through CadQuery 2.3.0 and Open CASCADE
7.9.3.0. The kernel reports X min near −1.25 on arris 0.12.0. The desired
value is −1, the leftmost cap vertex.

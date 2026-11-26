# Outward draft shorter than the kernel's tolerance

The rectangle is 4 × 3 and its slant length is 2. Its outward offset
is `s = 2 sin(10⁻¹⁰°)`. The sections have areas `12 + 14st + πs²t²`
and perimeters `14 + 2πst` in the height fraction `t`. The side area
uses the mean perimeter and the length 2. To double precision the axial
height is also 2.

`oracle.json` records `program.py` through CadQuery 2.3.0 and Open
CASCADE 7.9.3.0. It agrees with the construction at ADR-0005's
tolerances. Arris 0.12.0 refuses a wedge segment shorter than its
tolerance.

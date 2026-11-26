# Inward draft to a point

A side-4 square tapers inward at 45°. It reaches a point at Z = 2.
The pyramid has volume 32/3, area 16 + 8√8, centroid Z = 1/2 and
four triangular sides with a square base.

`oracle.json` records the same program with CadQuery 2.3.0 and Open
CASCADE 7.9.3.0. The oracle goes to Z = 2.000001414213563 and reports a
volume about 1.13e-5 larger than the pyramid's. The strict oracle
comparison is in `tests/test_cq_taper.py`.

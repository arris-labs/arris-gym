# Inward draft to a ridge

A 4 × 3 rectangle tapers in the negative Z direction at 45°. The shorter
side vanishes at Z = −1.5, leaving a length-1 ridge. Integrating the
section area `(4 − 2h)(3 − 2h)` from h = 0 to 1.5 gives volume 27/4.
Its first moment gives centroid Z = −5/12. Two triangular and two
trapezoidal sides give area 12 + 8√(1.5² + 1.5²), including the base.

`oracle.json` records the same program with CadQuery 2.3.0 and Open
CASCADE 7.9.3.0. The oracle goes to Z = −1.5000014142135636 and reports
volume 6.750015071069. The strict oracle comparison is in
`tests/test_cq_taper.py`.

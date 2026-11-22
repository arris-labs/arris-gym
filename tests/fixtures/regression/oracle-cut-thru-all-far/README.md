# Through cut from a distant workplane

CadQuery 2.3.0 reports the uncut 10 × 8 × 4 box when the workplane
is 40 units above its top face. The same profile cuts the box from a
workplane 3 units above that face.

The full sweep of a radius-1 circle at (1, −2) along Z removes 4π
from the box. The two openings remove 2π of area and the bore adds
8π. The stock's bounds stay fixed. The desired measures are in
`cq/ok-cut-thru-all-far/expected.json` for the identical program.
`tests/test_cq_cut_thru_all.py` checks them on arris and holds the
recorded oracle report to them as a strict `xfail`.

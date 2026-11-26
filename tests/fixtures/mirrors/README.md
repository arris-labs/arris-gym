# Reflected workplane paths

ADR-0028 records the `mirrorY()` decision from CadQuery 2.3.0 and Open
CASCADE 7.9.3.0. Each `oracle.json` records the report for its sibling
`program.py`. The contexts file records a program and report per case,
including the refusal and follow-on cases. The tests check each program's
digest against its report.

- `mirror-y-rectangle` doubles a 2 × 3 half outline and extrudes it by 4.
  The six-faced prism has volume 48 and centroid (0, 1.5, 2).
- `mirror-y-join-limit` starts and ends 5e-8 from the axis, so the
  separation of each pair is 1e-7. The two horizontal segments still
  give the 4 × 3 closed section. In the context probes at 1.000001e-7,
  two unjoined pairs cause the oracle's open-wire error, and one
  unjoined pair leaves an invalid extrusion.
- `mirror-y-lens` reflects an arc through (1, 0) from (0, −2) to
  (0, 2). The lens consists of two circular segments of radius 5/2
  cut at distance 3/2 from their centres. For θ = acos(3/5), its area
  is 2((25/4)θ − 3) and its perimeter is 10θ. It extrudes in the
  negative normal direction from a translated YZ workplane.
- `mirror-y-axis-run` drops the line along y from (0, 0) to (0, 1).
  The remaining reflected profile is a 4 × 2 rectangle.
- `mirror-y-i-section` has two 6 × 1 flanges and a 2 × 4 web. The
  mirrored boundary has 12 sides.
- `mirror-y-gusset-section` combines a 2 × 4 rectangle and a
  trapezoid of width 2 with depths 1 and 2 in each half. Reflecting
  doubles the area to 22. Its local y centroid is 5/3.

The gusset and I-section are constructions in the shapes used by
BenchCAD's `gusseted_bracket` and `i_beam`. The full programs belong to
the replay. The strict regressions under `../regression/*mirror-y*/`
hold the exact bounds of in-plane rotated arcs and the geometry of a
wire that touches the axis between its ends.

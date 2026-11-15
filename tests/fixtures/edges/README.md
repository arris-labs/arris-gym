# What CadQuery's edge selections and blends select and build, read on the oracle

ADR-0020's evidence (plans/lift-edges-and-blends step 1). Written by
`tools/cq_edge_probe.py` (CadQuery 2.3.0 on `cadquery-ocp` 7.9.3.0, oracle
zygotes, outside the gate):

```sh
cd tools && uv run python cq_edge_probe.py
```

`constructed.json` holds the constructions in `SELECTIONS` and `BLENDS`, own
programs on a 10 × 8 × 4 box about the origin, cylinders of radius 1 and 2,
a D (a half circle on a chord), three quarters of a disc, a cylinder cut by a
tilted plane (a full ellipse), two crossing cylinders (B-spline edges), a
plate with a hole, a tube, the box with its vertical edges rounded, and two
boxes that do not meet. A selection's entry holds the record of the `edges`
call that made `result`: every candidate edge (type, centre of mass, length,
ends, in CadQuery's collection order) and the kept indices, sorted. A blend's
entry holds the oracle's report less `step` and `seconds`: `fillet` and
`chamfer` of top edges, vertical edges, rims, all edges, a seam alone and in a
list, a compound, the values CadQuery refuses, and `Solid.fillet` with no
`clean()` beside four `fillet`s.

Two runs give the same records except in the last bits of four: the `or`
blend, whose edge order is a `set`'s, and three selections on a profile with
an arc. `tests/test_edge_probe.py` holds every value to the closed form of how
its part is built (kept edges by type and centre; volume, area, centroid) or
to CadQuery's last line, verbatim, so any run passes. It also builds the
blends in arris and holds them to the same closed forms, reads the values
arris refuses, and holds ADR-0020's edge key in arris to the oracle's
selections, to the edges' own polylines and to a quadrature. No corpus program
is recorded here.

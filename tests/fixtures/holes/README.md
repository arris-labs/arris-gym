# What CadQuery's point stacks and bore tools build, read on the oracle

ADR-0018's evidence (plans/lift-holes-and-points step 1). Written by
`tools/cq_hole_probe.py` (CadQuery 2.3.0 on `cadquery-ocp` 7.9.3.0, oracle
zygotes, outside the gate):

```sh
cd tools && uv run python cq_hole_probe.py
```

`constructed.json` holds the constructions in `CONSTRUCTED`, own programs on
one 10 × 8 × 4 box about the origin: `pushPoints` of tuples, lists, 3-tuples,
an empty list, points off the part and on side faces, overlapping and
duplicated; `hole(d, depth=)` blind, to the bottom and past it;
`cboreHole` and `cskHole` (82° and 90°) at one and several points, narrower,
equal, deeper and zero pieces; `faces(sel).faces(sel)`; `circle` on points
then `extrude`; and the arguments CadQuery refuses. Each entry is the name,
the program text and the oracle's report less `step` and `seconds`. Two runs
give the same bytes.

`tests/test_hole_probe.py` holds every `ok` report to the closed form of how
its part is built (volume, area, centroid) and every `runtime` report to
CadQuery's last line, verbatim. It also cuts ADR-0018's tools in arris (the
pieces of each bore, one call) and holds the cut to the same closed forms.
No corpus program is recorded here.

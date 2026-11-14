# What CadQuery's arrays and blind cuts build, read on the oracle

ADR-0019's evidence (plans/lift-arrays-and-blind-cuts step 1). Written by
`tools/cq_array_probe.py` (CadQuery 2.3.0 on `cadquery-ocp` 7.9.3.0, oracle
zygotes, outside the gate):

```sh
cd tools && uv run python cq_array_probe.py
```

`constructed.json` holds the constructions in `CONSTRUCTED`, own programs on
one 10 × 8 × 4 box about the origin and on a part revolved from a profile on
XY about its y axis (a cylinder of radius 5 from y = 0 to 4, and a flange
with a bore of radius 2): `rarray` 1 × 1, 3 × 2 and on `>X` and `<Y`, then
`hole` or `circle` and `extrude`; `polarArray` on full and partial turns of
either sign, from a start angle, with count 1, a negative and a zero radius,
on `>X` and on the revolved part's `<Y`; `cutBlind` of a circle, a ring
(either circle first) and circles at `pushPoints`, `polarArray` and `rarray`
points, blind, to the far face, past it, positive, from a plane inside the
part, on `>X` and on the revolved part's end faces; and the arguments
CadQuery refuses (a spacing or count out of range, a float count, a zero
depth, no pending wire, no solid). Each entry is the name, the program text
and the oracle's report less `step` and `seconds`. Two runs give the same
bytes.

`tests/test_array_probe.py` holds every `ok` report to the closed form of how
its part is built (volume, area, centroid) and every `runtime` report to
CadQuery's last line, verbatim. It also cuts ADR-0019's blind tools in arris
(each pending sketch extruded, all in one cut) and holds the cut to the same
closed forms. No corpus program is recorded here.

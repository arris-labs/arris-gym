# Provenance

arris-gym is written from scratch under MIT OR Apache-2.0.

- **CadQuery** (Apache-2.0) is read for its API surface and documented
  semantics, and `src/arris_gym/cq/` reimplements them over `arris.build`: no
  code, comments or identifiers beyond the public API's own names carried over,
  no line-by-line translation. A behaviour taken from its source is named here,
  with the file read.
- **CadQuery and Open CASCADE** (`cadquery-ocp`) are **run** as the oracle, out
  of process under `tools/oracle/` in their own environment. They are never a
  build, runtime or dev dependency of the library.
- **Benchmark scorers** are read to reproduce their metrics, and cited in the
  module that does: BenchCAD's evaluation code is MIT.
- **Data** keeps its licence on every row. BenchCAD is CC-BY-4.0; CAD-Recode is
  CC BY-NC 4.0, for research only, and weights inherit the most restrictive
  licence of their data.
- **arris** is a dependency, its pinned wheel the only interface. `../arrix` is
  not read for any of this.

## CadQuery behaviours taken from its source

Read in cadquery 2.3.0 (the oracle's pin); none of its code is carried over.

- `Workplane.transformed` (`cadquery/cq.py`) and `Plane.rotated`
  (`cadquery/occ_impl/geom.py`): the new origin is `offset` in the old
  plane's coordinates; the axes turn by the product Rx·Ry·Rz of rotations in
  degrees about the old plane's own x, y and z axes, so the z angle acts first.
- `Workplane.box` (`cadquery/cq.py`, with `eachpoint` and
  `_combineWithBase`): `length`, `width` and `height` along the plane's x, y
  and normal, centred on its origin by default, and fused with a solid
  already in the chain.
- `Workplane.union`, `Workplane.cut` and `_combineWithBase` (`cadquery/cq.py`):
  the solid acted on is the nearest one up the chain (this stack, then the
  parent's); the other is the solid of the Workplane given; the result sits on
  the same plane. Disjoint solids make a compound in CadQuery.
- `Workplane.circle` and `Workplane.extrude` (`cadquery/cq.py`, with
  `eachpoint` and `_getFaces`): a circle is centred on the plane's origin
  where the stack is empty; `extrude` grows the pending wire from the plane
  along its normal by `distance` (not about it) and fuses the result with
  the solid in the chain (`combine=True`).
- `Workplane.moveTo`, `lineTo`, `polyline`, `close`, `_findFromPoint` and
  `_addPendingEdge` (`cadquery/cq.py`): `moveTo` puts a point in plane
  coordinates on the stack; `lineTo` goes on from the last object only (an
  edge's end, a point, or the plane's origin on an empty stack, any other
  object an error); `polyline` starts at its first point, not the current
  one; `close` adds a segment back to the first point only when the gap is
  over 1e-6, and with nothing drawn is an error.
- `Workplane.revolve` and `Solid.revolve` (`cadquery/cq.py`,
  `cadquery/occ_impl/shapes.py`): the angle in degrees taken modulo 360, 0
  meaning a full turn, turned into radians by `2 * pi / 360`; the axis
  points in plane coordinates (a third coordinate along the normal); a
  right-handed turn about the direction from start to end; the result fused
  with the solid in the chain (`combine=True`).
- `Workplane.box` with a negative dimension: CadQuery 2.3.0 ends in Open
  CASCADE's `Standard_DomainError` (observed by running it, not read in its
  source); the subset raises `ValueError`, so the program ends `runtime` as
  the oracle's does.

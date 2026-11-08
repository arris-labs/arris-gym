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

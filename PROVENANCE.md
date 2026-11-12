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

- `Plane.named` (`cadquery/occ_impl/geom.py`): the `YZ` plane has its local
  x along world +y, local y along world +z and normal along world +x.
  `arris.build.Workplane.YZ()` provides that same frame.
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

## Benchmark scorers read

Read to reproduce the field's metrics in `src/arris_gym/reward/_field.py`;
none of their code is carried over, and the module cites each step.

- **BenchCAD** (MIT), `BenchCAD/BenchCAD-main` at commit
  `77fd16a80a4e5fc39964ee23b6cc3225beefac8f`:
  `benchcad_core/scoring/iou.py` (`_load_normalized_mesh`, `_vox_dense`,
  `iou_step_vs_step`) and `Vision2Code/scoring/composite_metrics.py`
  (`compute_iou`, `compute_chamfer`). Taken: the tessellation at 0.05, each
  mesh normalised to its own box (centre 0.5, longest side 1, refused below
  1e-9), the 64³ grid centred by shape in 68³ and cut where it overflows, an
  empty union scored 0, and Chamfer as the mean squared nearest distance both
  ways between 2,048 area-weighted samples per body. Their samples are
  unseeded; ours are seeded.
- **trimesh** 4.12.2 (MIT), the sdist from PyPI: `trimesh/base.py`
  (`Trimesh.voxelized`), `trimesh/voxel/creation.py` (`voxelize`,
  `voxelize_subdivide`), `trimesh/remesh.py` (`subdivide`,
  `subdivide_to_size`), `trimesh/voxel/base.py` (`VoxelGrid.fill`,
  `VoxelGrid.matrix`), `trimesh/voxel/encoding.py` (a sparse encoding's
  shape), `trimesh/voxel/morphology.py` (`fill`, `fill_holes`) and
  `trimesh/sample.py` (`sample_surface`). Taken: a triangle with an edge over
  pitch / 2 cut into four at its edges' midpoints, at most 10 rounds; every
  corner of the triangles left rounded half to even to its voxel; the grid
  spanning the hit voxels' box; holes filled by
  `scipy.ndimage.binary_fill_holes` at its documented default structure
  (faces-only connectivity), here a flood from the border.

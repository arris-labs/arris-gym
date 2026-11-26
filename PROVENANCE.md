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
  `arris.build.Workplane.YZ()` provides that same frame. The `XZ` plane has
  its local x along world +x, local y along world +z and normal along world
  -y; `arris.build.Workplane.XZ()` provides that same frame. The `ZX` plane
  has its local x along world +z, local y along world +x and normal along
  world +y, built as an `arris.build.Workplane` with those axes. `origin` is
  a point in world coordinates: the plane's origin moves there and its axes
  stay (`Plane(origin, xDir, normal)`), confirmed on the oracle by
  `tests/fixtures/cq/ok-origin-*`.
- `Workplane.transformed` (`cadquery/cq.py`) and `Plane.rotated`
  (`cadquery/occ_impl/geom.py`): the new origin is `offset` in the old
  plane's coordinates; the axes turn by the product Rx·Ry·Rz of rotations in
  degrees about the old plane's own x, y and z axes, so the z angle acts first.
  `newObject` preserves the pending wires in CadQuery's shared context
  through a plane change. The subset carries each admitted section in its
  original world frame and keeps them in drawing order on each branch
  (ADR-0026).
- `Workplane.workplane` (`cadquery/cq.py`, with `Vector.projectToPlane` in
  `cadquery/occ_impl/geom.py`): the new plane keeps the old axes; its
  centre is the old origin on an empty stack and the one object's `Center()`
  (a solid's centre of mass) otherwise; with the default
  `centerOption="ProjectedOrigin"` the old origin is projected onto the
  plane through that centre, then moved `offset` along the unit normal, and
  the new stack is empty. Confirmed on the oracle on `XY`, `YZ`, `XZ` and
  `ZX` with `origin=` by `tests/fixtures/cq/ok-workplane-*`.
  For a single wire drawn on its plane, projecting the old origin onto the
  plane through the wire's centre leaves that origin in place before the
  offset. The face-based cases in
  `tests/fixtures/lofts/plane-change-contexts.json` exercise this placement.
- `Workplane.box` (`cadquery/cq.py`, with `eachpoint` and
  `_combineWithBase`): `length`, `width` and `height` along the plane's x, y
  and normal, centred on its origin by default, and on each point of the
  stack otherwise, in the plane's own axes (the subset admits one `moveTo`
  point), and fused with a solid already in the chain. Confirmed on the
  oracle by `tests/fixtures/cq/ok-box-at-point-*`, after `workplane(offset=…)`
  and with a solid in the chain.
- `Workplane.cylinder` (`cadquery/cq.py`, with `eachpoint` and
  `_combineWithBase`, its default `centered=True`): a cylinder of `height`
  along the plane's normal and `radius`, centred on the origin or on each
  point of the stack in all three axes, `height / 2` either side of the
  plane, and fused with a solid already in the chain. Confirmed on the oracle
  by `tests/fixtures/cq/ok-cylinder-*` whose programs call `cylinder`: on each
  named plane, with `origin=`, after `transformed` and `workplane(offset=…)`,
  on a `moveTo` point and with a solid in the chain.
- `Workplane.faces`, `_selectObjects`, `StringSyntaxSelector` and
  `DirectionMinMaxSelector` (`cadquery/cq.py`, `cadquery/selectors.py`),
  `Workplane.workplane` with `centerOption="ProjectedOrigin"`, `_computeXdir`
  and `_isCoPlanar` (`cadquery/cq.py`), `Shape.clean`, `Shape.CombinedCenter`,
  `Face.Center` and `Face.normalAt` (`cadquery/occ_impl/shapes.py`), and
  `Plane._calcTransforms` (`cadquery/occ_impl/geom.py`):
  `>X <X >Y <Y >Z <Z` rank a solid's faces by
  centre of mass along the axis, cluster keys within 1e-4 of the cluster's first
  and keep the last (`>`) or first (`<`). `Shape.clean` uses Open CASCADE's
  same-domain unification. `workplane()` on one face uses its centre of mass
  and the outward normal at the centre's projection onto the surface.
  For multiple planar faces, CadQuery tests the normals and signed centre
  separations against the first face and uses their area-weighted centre.
  The plane's x follows `(0, 0, 1)` crossed with the normal, with global +x
  as the reference direction when the cross product is shorter than 1e-4.
  The frame squares x to the normal. The origin is the parent's origin
  projected onto the plane.
  Read in CadQuery 2.3.0 and confirmed on the oracle in ADR-0017 and ADR-0022,
  `tests/fixtures/selectors/` for the 950 BenchCAD programs and the
  constructions, `tests/fixtures/cq/ok-faces-*` for the planes.
- `Workplane.hole`, `cutEach` and `eachpoint` (`cadquery/cq.py`): `hole(d)` bores
  a cylinder of diameter `d` and length `largestDimension()` (the solid's
  bounding-box diagonal) from each stack point, against the plane's normal, and
  cuts it from the chain's solid. Read in cadquery 2.3.0 and confirmed on the
  oracle: `tests/fixtures/cq/ok-hole-*`.
- `Workplane.pushPoints`, `cboreHole`, `cskHole`, `hole(depth=)` and
  `largestDimension` (`cadquery/cq.py`, `cadquery/occ_impl/shapes.py`):
  `pushPoints` replaces the stack by the points in the plane's local
  coordinates (a third number is an offset along the normal); `hole` with a
  depth bores that length, else the solid's box diagonal; `cboreHole` and
  `cskHole` fuse a cylinder with a second cylinder or a cone of height
  `(cskDiameter - diameter) / 2 / tan(cskAngle / 2)` and cut it at every
  point through `cutEach`; the arguments CadQuery refuses and its order of
  checks were read on the oracle. `arris-gym` cuts the pieces separately, not
  fused (ADR-0018). Confirmed on the oracle: `tests/fixtures/holes/`,
  `tests/fixtures/cq/ok-push-points-*`, `ok-hole-depth-*`, `ok-cbore-*`,
  `ok-csk-*`, `ok-ctx-*`.
- A second `faces(sel)` on the stack of faces a first kept, and `circle` and
  `extrude` on a stack of points (`cadquery/cq.py`, `_selectObjects`,
  `eachpoint`): the selector ranks only the stacked faces; a circle at each
  point, extruded and fused. Confirmed by `tests/fixtures/cq/ok-ctx-*` and
  `unsupported-circle-points-*`.
- `Workplane.sphere` and `Solid.makeSphere` (`cadquery/cq.py`,
  `cadquery/occ_impl/shapes.py`): one sphere at each point of the stack
  (`eachpoint`, in the plane's own axes, the origin on an empty stack),
  `direct=(0, 0, 1)` local so its poles lie on the plane's normal,
  `centered=True` placing its centre on the point, and fused with the
  solid in the chain (`combine=True`). Confirmed on the oracle by
  `tests/fixtures/cq/ok-sphere-*`: on an empty stack, on a `moveTo`
  point, after `transformed` and an `origin=`, on each named plane, fused
  with a slab and three times into BenchCAD's capsule.
- `Workplane.polygon` (`cadquery/cq.py`): `nSides` points on the circle of
  `diameter`, `radius = diameter / 2.0` and the angle
  `2.0 * math.pi / nSides` times `i`, the first at angle 0 on the plane's
  local x, made into one closed wire at each point of the stack
  (`eachpoint`, the origin on an empty stack). Confirmed on the oracle by
  `tests/fixtures/cq/ok-polygon-*`: on an empty stack, on a `moveTo` point,
  after `transformed` and `workplane(offset=…)`, on each named plane, fused
  with a slab and in BenchCAD's grease nipple.
- `Workplane.extrude` and `Workplane._extrude`, the `both` branch
  (`cadquery/cq.py`): the face is swept `distance` along the normal and,
  with `both=True`, fused (`glue=True`) with the sweep of `-distance`, and
  `clean()` merges the halves' coplanar side faces, so the solid is one
  prism of height `2|distance|` centred on the plane. Confirmed on the
  oracle by `tests/fixtures/cq/ok-extrude-both-*`: a circle and polygons on
  several planes, a negative distance, `both=False`, fused with and cut
  from a slab, and BenchCAD's hex key organizer. A circle's cylinder stays
  two faces there (four in all) where `cq` builds one; face counts are
  carried, never judged.
- `Workplane.union`, `Workplane.cut` and `_combineWithBase` (`cadquery/cq.py`):
  the solid acted on is the nearest one up the chain (this stack, then the
  parent's); the other is the solid of the Workplane given; the result sits on
  the same plane. Disjoint solids make a compound in CadQuery: one
  `Compound` on the stack, which `_findType((Solid, Compound))` finds for the
  next `union`, `cut` or combining call, and on which `workplane()` takes
  `Shape.Center()`, the centre of mass of all its pieces. A `cut` that splits
  its base returns a compound too. Confirmed on the oracle by
  `tests/fixtures/cq/ok-compound-*`, `ok-cut-into-pieces` and
  `ok-workplane-on-compound` (ADR-0016).
  With no solid up the chain, `union` returns the given Workplane's solid
  as it stands (its `solidRef is None` branch) and `cut` raises `findSolid`'s
  `ValueError`. Confirmed on the oracle by `ok-union-on-empty-chain-*` and
  `runtime-cut-on-empty-chain`.
- `Workplane.circle` and `Workplane.extrude` (`cadquery/cq.py`, with
  `eachpoint` and `_getFaces`): a circle is centred on the plane's origin
  where the stack is empty, and on each point of the stack otherwise, in the
  plane's own axes (the subset admits one `moveTo` point); `extrude` grows the pending wire from the plane
  along its normal by `distance` (not about it) and fuses the result with
  the solid in the chain (`combine=True`).
- `Workplane.cutThruAll`, `_getFaces`, `center`, `rect`, `slot2D` and
  `eachpoint` (`cadquery/cq.py`), with `dprism`
  (`cadquery/occ_impl/shapes.py`): a through cut finds the solid before
  reading the pending profiles, then runs a local through cut for each
  face. `center` moves the plane origin, replaces the stack with that
  point and retains pending wires. `rect` and `slot2D` place wires at the
  stack's points with their local rotations. ADR-0024 cites the oracle
  constructions in `tests/fixtures/profiles/`.
- `Workplane.moveTo`, `lineTo`, `polyline`, `close`, `_findFromPoint` and
  `_addPendingEdge` (`cadquery/cq.py`): `moveTo` puts a point in plane
  coordinates on the stack; `lineTo` goes on from the last object only (an
  edge's end, a point, or the plane's origin on an empty stack, any other
  object an error); `polyline` starts at its first point, not the current
  one (so a lone `moveTo` point before it is dropped: `includeCurrent=False`); `close` adds a segment back to the first point only when the gap is
  over 1e-6, and with nothing drawn is an error.
- `Workplane.threePointArc` and `Edge.makeThreePointArc` (`cadquery/cq.py`,
  `cadquery/occ_impl/shapes.py`): an arc from `_findFromPoint`'s pen (as
  `lineTo`'s) through `point1` to `point2`, both in plane coordinates; the
  arc's end is the pen of the next call and what `close` measures its gap
  from. Confirmed on the oracle by `tests/fixtures/cq/ok-three-point-arc-*`:
  on a `moveTo` point, on an empty stack, after `lineTo` and after an arc,
  on each named plane, closed by a line and by an arc ending on the start,
  extruded both ways and revolved.
- `Workplane.mirrorY`, `wire` and `consolidateWires` (`cadquery/cq.py`),
  `Plane.mirrorInPlane` (`cadquery/occ_impl/geom.py`) and `Wire.combine`
  (`cadquery/occ_impl/shapes.py`) define the free-edge assembly, local
  reflection and wire joining. The effective endpoint limit on the
  pinned oracle is recorded in ADR-0028 and `tests/fixtures/mirrors/`.
- `Sketch.segment`, `arc`, `close` and `assemble` (`cadquery/sketch.py`):
  implicit starts use the last free edge's end, closing draws a line to
  the first start, and assembly retains the free edges. Confirmed in
  `tests/fixtures/sketch/constructed.json` (ADR-0023).
- `Workplane.revolve` and `Solid.revolve` (`cadquery/cq.py`,
  `cadquery/occ_impl/shapes.py`): the angle in degrees taken modulo 360, 0
  meaning a full turn, turned into radians by `2 * pi / 360`; the axis
  points in plane coordinates (a third coordinate along the normal); a
  right-handed turn about the direction from start to end; the result fused
  with the solid in the chain (`combine=True`).
- `Workplane.loft`, `_combineWithBase` and `Solid.makeLoft` (`cadquery/cq.py`,
  `cadquery/occ_impl/shapes.py`): pending wires in drawing order, the empty
  and one-wire errors, smooth solid construction and stock lookup when
  `combine` is true. Confirmed on the oracle by `tests/fixtures/lofts/`.
  ADR-0026 records the wire pairing read in Open CASCADE 7.9.3 and the
  constructed comparisons. `PlaneOfWire` and `ComputeOrigin` in
  `BRepFill/BRepFill_CompatibleWires.cxx` use each wire's length-weighted
  centre of mass and compare starts in both directions.
- `Workplane._extrude` and `Solid.extrudeLinear` (`cadquery/cq.py`,
  `cadquery/occ_impl/shapes.py`), and Open CASCADE 7.9.3
  `LocOpe/LocOpe_DPrism.cxx`: the inner-wire error, sign of the sweep along
  the face normal and sine and cosine projections of its slant length.
  The analytic constructions and the oracle runs are in ADR-0027 and
  `tests/fixtures/tapers/`.
- `Workplane.box` with a negative dimension: CadQuery 2.3.0 ends in Open
  CASCADE's `Standard_DomainError` (observed by running it, not read in its
  source); the subset raises `ValueError`, so the program ends `runtime` as
  the oracle's does.

- CadQuery 2.3.0's [`Workplane.shell`](https://github.com/CadQuery/cadquery/blob/2.3.0/cadquery/cq.py#L1201-L1234)
  and [solid shell](https://github.com/CadQuery/cadquery/blob/2.3.0/cadquery/occ_impl/shapes.py#L2697-L2753)
  establish which stock and openings are used, the sign of thickness,
  the default arc join and the sealed cavity for an empty face list.
  ADR-0029 and `tests/fixtures/shells/` record the pinned behaviour.

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
- `Workplane.rarray`, `Workplane.polarArray` and `Workplane.cutBlind`
  (`cadquery/cq.py`, with `_extrude` and `clean`): the grid's order (x outer,
  y inner) and centring, the circle's angles (a full turn split in `count`, a
  partial one in `count - 1`), each refusal's words and `cutBlind`'s order of
  refusals (no pending wire, zero depth, no solid). Confirmed on the oracle by
  `tests/fixtures/arrays/` and `tests/fixtures/cq/ok-rarray-*`,
  `ok-polar-array-*` and `ok-cut-blind-*`; ADR-0019.
- `Workplane.cutThruAll` (`cadquery/cq.py`, `occ_impl/shapes.py`): the
  solid lookup precedes wire lookup, and `dprism` cuts along the profile
  normal through the whole stock. The oracle's ring refusal is recorded in
  `tests/fixtures/profiles/` (ADR-0024 §A).
- `Workplane.edges`, `Workplane.fillet`, `Workplane.chamfer`, `ParallelDirSelector` and `SumSelector`
  (`cadquery/cq.py`, `selectors.py`, `occ_impl/shapes.py`: `_collectProperty`,
  `findSolid`, `DirectionMinMaxSelector`, `Mixin1D.Center`, `Mixin3D.fillet`,
  `Mixin3D.chamfer`):
  the candidates (each edge once, in the order first found, degenerate edges left
  out), an edge's centre of mass as its key, the parallel line test, the union
  of an `or`, the solid and edges a blend takes and each refusal's words.
  Confirmed on the oracle by `tests/fixtures/edges/` and `tests/fixtures/cq/ok-fillet-*`,
  `runtime-fillet-*`, `arris-refusal-fillet-*` and the `chamfer` fixtures
  (`ok-chamfer-*`, `runtime-chamfer-*`, `arris-refusal-chamfer-*`); ADR-0020.
- Where Open CASCADE puts a seam (`cadquery/cq.py`: `Workplane.cylinder`, `circle`,
  `hole`, `cboreHole`, `cskHole`, `polarArray`, `_computeXdir`; `occ_impl/shapes.py`:
  `Solid.makeCylinder`, `Edge.makeCircle`; Open CASCADE's `gp_Ax2` from a direction):
  each cylinder and circle made in the workplane's own axes, along +z for a cylinder
  or circle and -z for a bore, so its seam lies on the workplane's +x or -x; the
  turn `polarArray` gives each point. Confirmed on the oracle by the `seam-*`
  constructions of `tests/fixtures/edges/` and `tests/fixtures/cq/ok-chamfer-corpus-*`;
  ADR-0020's amendment.

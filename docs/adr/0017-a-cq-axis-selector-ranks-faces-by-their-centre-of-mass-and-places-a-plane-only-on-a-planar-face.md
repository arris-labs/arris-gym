# ADR-0017: A `cq` axis selector ranks faces by their centre of mass, and places a plane only on a planar face

- Status: accepted
- Date: 2026-11-14
- Closes: the ⚠ OPEN in `docs/ARCHITECTURE.md` §Dialects, how CadQuery's string
  selectors map onto arris's selection when they are ambiguous on curved faces

## Context

plans/lift-face-selectors lifts `faces(sel)` for `>X <X >Y <Y >Z <Z`,
`workplane()` on the faces it keeps, and `hole(diameter)`. That admits 950
BenchCAD programs. Each writes exactly one `.faces(sel).workplane()`.

**What CadQuery does.** Read in cadquery 2.3.0: `selectors.py`
(`DirectionMinMaxSelector`, `CenterNthSelector`, `_NthSelector`), `cq.py`
(`Workplane._selectObjects`, `Workplane.workplane`) and `occ_impl/shapes.py`
(`Face.Center`, `Face.normalAt`, `Shape.CombinedCenter`).

- `">Z"` is `DirectionMinMaxSelector((0, 0, 1), directionMax=True)` with its
  default tolerance of 1e-4. Its candidates are the faces of every object on the
  stack, each taken once, in the order they are first found.
- A face's key is `Center()·axis`. `Center()` is the face's centre of mass by
  `BRepGProp.SurfaceProperties`, the area-weighted mean of its points. The keys
  are sorted ascending, and a stable sort keeps tied faces in that order.
- The clusters are greedy. A cluster starts at a key and takes each next key
  within 1e-4 of that start, not of its neighbour. `>` keeps the last cluster
  and `<` the first.
- `workplane()` with the default `centerOption="ProjectedOrigin"` on one face:
  the centre is `Center()`. The normal is `normalAt(centre)`, taken where the
  centre projects onto the surface (`GeomAPI_ProjectPointOnSurf`). x is
  `(0, 0, 1) × normal`, or `(1, 0, 0)` when that is shorter than 1e-4
  (`_computeXdir`, `ctx.tolerance`). The origin is the parent plane's origin
  projected onto the plane through the centre.
- On several faces, each must be planar, or it raises `ValueError: If multiple
  objects selected, they all must be planar faces.` They must also pass
  `_isCoPlanar`, or it raises `ValueError: Selected faces must be co-planar.`
  That test passes two normals when any one component agrees within 1e-4, and
  passes an offset when `n0·(p0 − p1) < 1e-4`, which is signed. The centre is the
  area-weighted `CombinedCenter`. The normal is the first face's `normalAt()` at
  its mid-parameter.

**What the oracle shows.** `tools/cq_selector_probe.py` runs each program on
the oracle with CadQuery's `faces` and `workplane` wrapped. It records what was
kept and the plane built, then stops the program. The rows and constructions
are in `tests/fixtures/selectors/`, and `tests/test_selector_probe.py` holds
each figure below.

| The 950 programs | |
|---|---|
| selectors | `>Z` 351, `>Y` 295, `>X` 275, `<X` 10, `<Y` 10, `<Z` 9 |
| `workplane()` | a plane in all 950, no error |
| faces kept | one in 910, two in 40 (all `connecting_rod`, one offset, a spread ≤ 9e-16) |
| a kept face | planar, its normal along the selector's signed axis, in all 950 |
| the plane | the parent origin with its axis coordinate set to the face's offset (within 1.8e-15); x by `_computeXdir` |
| nearest key outside the kept cluster | 0.04 away (400 times the tolerance) |
| faces not normal to the axis (6,620 planar, 1,082 cylinder) whose box reaches the boundary | their centres more than 0.5% of the part's extent along the axis inside it (0.0399 at the least) |
| a box-centre ranking with CadQuery's clusters | keeps the same faces in all 950 |

The constructions, each with a closed form:

- **A box, an offset box and a turned box**, every selector: the plane is the
  face's plane, through the projected parent origin.
- **A half cylinder** (radius 1 along x, cut to z ≥ 0), `>Z`: Open CASCADE keeps
  one half-cylinder face. Its centre of mass is at z = 2r/π = 0.6366, off the
  surface. The plane passes through that centre with normal +z, and not through
  the surface at z = 1. A box-centre ranking keeps three faces. arris's own cut
  of the same solid leaves two quarter-cylinder faces, each with z = 2/π, so the
  same selector there keeps two curved faces.
- **A full cylinder along z**, `>X`: the side face's centre lies on the axis and
  ties with both discs, so CadQuery raises the several-faces `ValueError`. That
  centre has no unique foot on the surface, and Open CASCADE's projection raises
  `StdFail_NotDone`.
- **A triangular prism**, `>X`: a side face and the hypotenuse tie at x = 2 by
  centre of mass, and CadQuery raises the co-planar `ValueError`. A box-centre
  ranking ties four faces.
- **Near ties** (tops 1.5 and 1.50005, 1.5 and 1.50015, and 1.5, 1.50008 and
  1.50016): within 1e-4 CadQuery keeps both faces and places the plane at the
  area-weighted offset, 1.5000167. Outside 1e-4 it keeps the top face only. In
  the chain it keeps only the top face, though each step is within 1e-4.

**What arris 0.10.0 offers** (`docs/ARRIS_API.md`):

- `Selection.extreme(direction)` keeps the members whose centre is within the
  model's tolerance of the furthest. Its centre is the member's box centre moved
  onto its plane, which is not CadQuery's centre, and its rule is not CadQuery's
  clusters.
- arris has no centre of mass per face. `surface_properties` is per body.
- `surface(face)` gives a plane's origin and normal exactly. `bounds(face)` gives
  a box padded by the model's tolerance, and `tessellate_faces` gives a mesh per
  face.
- On the half cylinder, the area centroid of `tessellate_faces` is off by about
  0.4 times the chord: 4.0e-4 at a chord of 1e-3, and 4.2e-5 at 1e-4.

## Decision

**1. The ranking is CadQuery's.** `cq` does not call `Selection.extreme`.

- The candidates are every face of the chain's solid, all its pieces included
  (ADR-0016).
- A face's key is its centre of mass along the axis.
- The keys are sorted and clustered greedily within `CQ_TOLERANCE` = 1e-4 of each
  cluster's first key. `CQ_TOLERANCE` is one named constant, CadQuery's default
  for its selectors, `_computeXdir` and `_isCoPlanar`.
- `>` keeps the last cluster and `<` the first. The kept faces are in ascending
  key, and a tie keeps arris's face order.

**2. Where a key comes from.**

- **Exact** for a planar face whose normal is parallel to the axis within the
  model's angular tolerance. Its key is its plane's offset,
  `surface(face).origin·axis`, since every point of the face has it. This
  covers every face kept in the 950.
- **Bounded** for any other face whose box (`bounds`) lies wholly outside the
  boundary by more than `CQ_TOLERANCE`. Its centre lies inside its box, so it
  cannot join the cluster.
- **Estimated** for the rest. The estimate is the area centroid of the face's
  tessellation (`tessellate_faces` at a chord of 1e-5 of the solid's box
  diagonal). It is summed in triangle order in Python floats, so it has the same
  bits on every machine. The estimate is trusted only at a margin of 1e-4 of the
  diagonal, ten chords or 25 times the error measured above. If moving any
  estimated key by the margin could change which faces the cluster keeps,
  `faces` ends `unsupported_api`, naming the selector and saying that the
  selection depends on a face's centre arris does not give. No program of the
  950 comes near: its faces sit more than 0.5% of the extent inside.
- arris is asked for a face's exact area and centre of mass
  (`../arris/docs/ideas/face-surface-properties.md`). When an arris bump brings
  them, they replace the estimate and the margin, by an amendment here.

**3. `workplane()` on one planar face** follows CadQuery's rule. The plane is the
face's own, its normal the face's outward normal. x is `(0, 0, 1) × normal`,
normalised, or +x when its length is under `CQ_TOLERANCE`. The origin is the
parent plane's origin projected onto the face's plane. The face's centre is
never needed: `ProjectedOrigin` keeps only the plane through it, and every point
of a planar face lies on that plane.

**4. `workplane()` on several faces.**

- If any face is not planar, `cq` raises CadQuery's own `ValueError` (`runtime`).
  This applies when the cluster mixes a planar face with a curved one, or curved
  faces of different surfaces.
- If all are planar and normal to the axis with one outward normal and one offset
  (within the model's tolerance), the plane is that one, as in the 40
  `connecting_rod` programs.
- Offsets apart by more than the model's tolerance (a near tie) put CadQuery's
  plane at the area-weighted offset, which needs face areas arris does not give,
  so `cq` ends `unsupported_api`. So do opposite normals, where CadQuery takes
  the first face's normal by an order the two kernels do not share.
- Planar faces not normal to the axis: `cq` raises CadQuery's co-planar
  `ValueError` where their normals already fail `_isCoPlanar`. Otherwise
  `unsupported_api`, since the offset test needs their centres.

**5. A curved face (the ⚠ OPEN).** A cluster whose faces all lie on one curved
surface ends `unsupported_api`: one face, or one surface split into several.
CadQuery's plane on a curved face hangs on the face's centre of mass in all
three coordinates. That centre is off the surface (2r/π on the half cylinder),
and an estimate's error would land in the plane itself, not only in a ranking.
It also depends on how a kernel splits the surface into faces, and arris and
Open CASCADE split the half cylinder differently (two faces against one). None
of the 950 keeps a curved face.

## Consequences

- plans/lift-face-selectors step 3 builds 1 to 3. Step 4 builds 4 and 5, its
  refusals and errors as fixtures on the constructions above.
- `CQ_TOLERANCE`, the chord and the margin are named constants in `cq`, each
  with this ADR as its comment.
- A selection costs a tessellation only for faces the box test cannot settle. On
  the 950 that is the side faces next to the kept face, mostly planar, which
  tessellate to a few triangles.
- A program that keeps a curved face, or that ties within the margin, is an
  in-subset `cq_bug` row if the corpus has one (ADR-0012). The forecast is none,
  and step 7's measurement counts them.
- The face split arris and Open CASCADE disagree on also moves a ranking where
  several split faces compete for the cluster. That is visible only where a
  curved face would be kept, which rule 5 refuses.

## Alternatives considered

- **`Selection.extreme` as it is.** Its centre is a box centre and its tie rule
  is a threshold from the maximum. It differs from CadQuery on the half cylinder,
  the triangle and the chain.
- **A box-centre key with CadQuery's clusters.** It agrees on all 950 but keeps
  other faces on the half cylinder and the triangle. That is a different
  selection, not a rounding error, so it cannot be the rule.
- **A tessellation estimate everywhere, with no margin.** A selection would then
  hang on a chord and could be wrong with nothing to show it.
- **Closed forms per surface kind** (a cylinder band's centre). These fit a
  ranking but not rule 5, which also turns on how each kernel splits a face. The
  exact per-face centre asked of arris serves both, so they wait for it.

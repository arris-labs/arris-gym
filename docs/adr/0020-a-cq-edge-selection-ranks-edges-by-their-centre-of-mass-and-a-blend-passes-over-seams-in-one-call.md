# ADR-0020: A `cq` edge selection ranks edges by their centre of mass, and a blend passes over seams in one call

- Status: accepted
- Date: 2026-11-15
- Closes: the kernel risk of plans/lift-edges-and-blends (whether arris blends
  the edges the corpus selects as Open CASCADE does), and its two ⚠ OPEN of
  step 1 (a seam in a blend's list; `clean()` after a blend)

## Context

plans/lift-edges-and-blends lifts `edges()`, `edges(str)` with the six axis
selectors, `|X`, `|Y`, `|Z` and `'>Z or <Z'`, then `fillet(radius)` and
`chamfer(length)`. Read in the corpus text at planning time, the 3,433 BenchCAD
programs they admit write `edges(sel)` after a solid or after `faces(sel)`,
then `fillet(r)` or `chamfer(d)`, and usually nothing after it, or `faces(sel)`
or `union`.

**What CadQuery does.** Read in cadquery 2.3.0: `cq.py` (`Workplane.edges`,
`_selectObjects`, `_collectProperty`, `findSolid`, `fillet`, `chamfer`),
`selectors.py` (`DirectionMinMaxSelector`, `CenterNthSelector`,
`_NthSelector`, `BaseDirSelector`, `ParallelDirSelector`, `SumSelector`, the
string grammar's `or`) and `occ_impl/shapes.py` (`Shape.Edges`,
`Mixin1D.Center`, `Mixin3D.fillet`, `Mixin3D.chamfer`, `Shape.clean`).

- `edges(sel)` collects the edges of every object on the stack
  (`_collectProperty("Edges")`): a solid's, a face's own, an edge itself. A
  dict keyed by `hashCode()`, which ignores orientation, keeps each edge once
  in the order it is first found. `Shape.Edges()` leaves out degenerated
  edges (a sphere's poles).
- `>Z` keys an edge by `Center()·axis`; an edge's `Center()` is its centre of
  mass along its length (`BRepGProp.LinearProperties`). The keys are sorted
  and clustered as for faces (ADR-0017 rule 1, tolerance 1e-4).
- `|Z` is `ParallelDirSelector`: it keeps an edge only if its `geomType()` is
  `LINE` and `|axis × tangentAt()| < 1e-4`. A circle, an ellipse or a
  B-spline edge is never kept.
- `'>Z or <Z'` is `SumSelector`: `list(set(left + right))`. Its order is a
  `set`'s, which follows Open CASCADE's hash of a shape.
- `fillet(radius)` finds the chain's solid (`findSolid`: the stack's, else the
  nearest parent's, `ValueError: Cannot find a solid on the stack or in the
  parent chain`), then takes `self.edges()`: the stack's edges, or every edge
  of the stacked faces or solid. None raises `ValueError: Fillets requires
  that edges be selected`. It then adds every edge to one
  `BRepFilletAPI_MakeFillet` at `radius` and returns `clean()` of the result.
  `chamfer(length)` does the same with `BRepFilletAPI_MakeChamfer` (`Chamfer
  requires that edges be selected`) and no `clean()`. Neither checks the value.

**What the oracle shows.** `tools/cq_edge_probe.py` runs 70 constructions,
each with a closed form. `tests/fixtures/edges/constructed.json` holds the
records, and `tests/test_edge_probe.py` holds each one:

| Construction | What the oracle keeps or builds |
|---|---|
| a 10 × 8 × 4 box, `edges()`, each axis selector, `\|X \|Y \|Z`, `'>Z or <Z'` | 12, then 4 for each, then 8: the edges whose midpoints the closed form names |
| the box's `faces(">Z").edges()`, `.edges(">X")`; `faces(">X").edges("\|Z")` | the face's 4 edges are the candidates; 4, 1 and 2 kept |
| a cylinder, `edges()` | 3 candidates: two rims and a seam line at +x |
| the cylinder, `>Z`, `<Z`, `'>Z or <Z'`, `faces(">Z").edges()` | the rims, by their centres |
| the cylinder, `>X`; `\|Z` | the seam alone |
| the cylinder, `>Y`; `\|X` | all three, tied at y = 0; nothing |
| a D (a half circle on a chord), `>Y`; `<Y` | the two half circles, 2r/π off the chord; the four lines |
| three quarters of a disc, `<X` and `>Y` | the two arcs, their centre of mass `r sin(θ/2)/(θ/2)` along the bisector |
| the box with its vertical edges rounded, `>Z` | 8 of 24: four lines and four quarter arcs |
| a cylinder cut by a plane tilted 30°, `>Z` | the full ellipse, its centre at `2 − 1/cos 30°` (1e-6 off in x: Open CASCADE's sum) |
| two crossing cylinders, `>X` | the end circle; the B-spline curves where they meet are cut into a half and two quarters at +x and one whole at −x, each centre 1e-9 off a quadrature |
| a plate with a hole, `\|Z`; `faces(">Z").edges()` | the four corners and the hole's seam, at −x; the face's 4 lines and the hole's rim |
| `fillet` and `chamfer` of the box's top edges, its vertical edges, both rims, all twelve (by `edges()`, by the solid alone, by `faces(">Z")`) | the closed form: the section (a square less a quarter disc, or a right triangle) swept along each run of edges, mitred at the box's corners, by Pappus |
| the same on a cylinder's rims, a tube's two rims, a plate's top and its hole's rim | the closed form |
| a fillet and a chamfer along the edges an earlier fillet made (the rounded box's top) | the closed form, the two blends meeting at the arcs' ends |
| a blend of the cylinder's `edges()`, its seam in the list | both rims: the seam is passed over |
| a blend of two boxes that do not meet (a compound) | two blended solids |
| `Solid.fillet` with no `clean()`, beside four `fillet`s | the same volume, area, centroid and face count, bit for bit |

CadQuery raises for: a radius or length of 0, of −1, past half the box's
width or past its height (`StdFail_NotDone: BRep_API: command not done`); the
seam alone (`Standard_Failure: There are no suitable edges for chamfer or
fillet`); an empty selection (`Fillets requires that edges be selected`,
`Chamfer requires …`); and no solid in the chain. Two runs of the probe give
the same records but in four constructions' last bits: the `or` blend (its
edge order is a `set`'s) and the three selections on a profile with an arc.
The tests hold every value to its closed form, so any run passes.

**What arris 0.10.0 offers** (`docs/ARRIS_API.md`).
`Solid.fillet(edges, radius)` and `Solid.chamfer(edges, distance)` blend in
one call. Measured in the probe's spike (`test_arris_blends_to_the_closed_form`,
18 constructions): every blend the oracle builds, arris builds to the same
closed form with the checker passing, the compound included. Both kernels
meet the closed form within 1e-14 of it, except where two blends meet at a
box's mitred corner (within 1e-10, relative, for both). arris refuses with
`OpDegenerateError`: a value of 0 or less ("radius must be positive, not 0",
"distance must be positive, not -1"), a value past the edge's faces ("the
blend leaves its face through an edge that is not the corner's own") and a
seam in the list ("the edge's faces meet at a tangent dihedral, which has no
corner to blend").

`Model.curve(edge)` gives a line's ends, and a circle's or ellipse's centre,
axis, radius and ends. An arc runs counter-clockwise about the axis from its
start to its end, or from its end to its start on a reversed edge; that holds
on arcs of either orientation and on a plane facing −z
(`test_the_exact_centre_is_the_tessellations`). A B-spline edge has only its
ends. `Model.tessellate` gives each edge's polyline. On the crossing
cylinders arris cuts the curve at +x into two halves where Open CASCADE has
three pieces. The polylines' centres, at ADR-0017's chord, sit within 1e-8 of
the box diagonal of the quadrature's. arris puts a cylinder's seam at +x, as
Open CASCADE does for `cylinder()`, but a bored hole's seam at +x where Open
CASCADE puts it at −x.

## Decision

**1. The candidates are CadQuery's.** `edges(sel)` collects the edges of each
object on the stack: a solid's (every piece, ADR-0016), a face's own, and an
edge itself. Each edge is kept once, in the order it is first found. An arris
edge of kind `degenerate` is not a candidate, as CadQuery's `Edges()` leaves
out a degenerated edge. With no selector the candidates are the selection.

**2. The edge key is the centre of mass along the axis.** The clusters and
`CQ_TOLERANCE` are ADR-0017 rule 1's. `>` keeps the last cluster, `<` the first.

- **Exact**: a line's midpoint; a full circle's or full ellipse's centre; an
  arc's centre moved `r sin(θ/2)/(θ/2)` along its bisector, the sweep `θ`
  read as stated above.
- **Bounded**: a seam's key is the kernel's choice where its face's axis is
  not along the selector's. A seam is an edge with one face on both sides.
  Its key is exact where its face is a surface of revolution whose axis is
  parallel to the selector's: every generator then has the same key. Otherwise
  the seam lies anywhere on its face, so its key is bounded by the face's box.
- **Estimated**: an ellipse arc's or a B-spline edge's key is its polyline's
  centre of mass, from `tessellate` at ADR-0017's chord, summed in order in
  Python floats. It is trusted at ADR-0017's margin, as a face's estimate is.
- If moving any bounded or estimated key across its range could change the
  kept cluster, `edges` ends `unsupported_api`. The message names the
  selector and says the selection depends on an edge's place, which arris
  does not decide as CadQuery's kernel does.
- A kept cluster that holds an estimated edge also ends `unsupported_api`.
  The kernels cut such curves into different edges (the crossing cylinders:
  three pieces against two), so which edges are kept is the kernel's own.

**3. `|X`, `|Y`, `|Z` keep the line edges whose direction crosses the axis
within `CQ_TOLERANCE`.** The direction is the line's ends' difference,
normalised. Any other kind of edge is never kept. A seam line is kept where it
is parallel: a cylinder's seam is parallel to its axis wherever it lies.

**4. `'>Z or <Z'` keeps the union of both selections, each edge once, in the
order of rule 1's candidates.** CadQuery's order is a `set`'s and varies from
run to run. Only a blend reads it (rule 6), and `cq`'s order is the same on
every machine.

**5. `fillet(radius)` and `chamfer(length)` blend in one call, in CadQuery's
order.**

- No solid in the chain raises `ValueError` (`runtime`) in CadQuery's words.
  The solid is the stack's, else the nearest parent's, a compound included.
- The edges are the stack's, or every edge of the stacked faces or solid
  (rule 1). None raises `ValueError` (`runtime`) in CadQuery's words, one
  for each method.
- Seams are dropped: arris refuses them, and Open CASCADE passes over them.
  A list of seams alone raises `ValueError` (`runtime`) naming Open
  CASCADE's `Standard_Failure: There are no suitable edges for chamfer or
  fillet`.
- The rest go to one `Solid.fillet` or `Solid.chamfer` with the value as
  written. A value of 0 or less, or one past an edge's faces, is arris's
  refusal (`arris_refusal`, its words verbatim). There CadQuery raises
  `StdFail_NotDone`: both fail, a row that agrees (ADR-0006).
- No `clean()`: on the oracle it moves no measure, and `chamfer` has none.
  The face counts are carried, never judged (ADR-0005).
- The result goes on the stack as one solid, so `faces`, `edges`, `union`
  and the rest act on it as on any solid.

**6. A stack of edges is read only by `edges`, `fillet` and `chamfer`.** Every
other call of the subset on one ends `unsupported_api`, until a plan reads it
on the oracle. One example is `workplane()`, which CadQuery places through
one edge's centre with the parent's normal.

## Consequences

- plans/lift-edges-and-blends steps 2 and 3 build rules 1 to 4, step 4
  `fillet`'s rule 5, and step 5 `chamfer`'s. Each step's `ok-`, `runtime-`,
  `arris-refusal-` and `unsupported-` fixtures come from these constructions.
- The arc's sweep, the seam test and the estimate are `cq`'s, each with this
  ADR as its comment. The chord and the margin are ADR-0017's constants.
- A seam's key is bounded wherever the selector crosses its face's axis. So
  `edges(">X")` on a lone cylinder, or `>Y`, where the seam ties with the
  rims, ends `unsupported_api` though both kernels agree there. A seam on a
  bored hole at the part's edge would too. How often the corpus's selections
  cross a turned part's axis is not read here; step 7 counts any that do.
- A blend refused by arris where Open CASCADE builds is an `arris_refusal`
  row. It counts against agreement, not reach. None of the constructions here
  is one.
- The kernels may cut other curves (a circle, a seam) into different edges.
  That moves a selection only where the cut pieces compete for a cluster.
  Step 7's measurement finds any in the corpus.

## Alternatives considered

- **`Selection.extreme` and `Selection.parallel`.** Their centre is a box
  centre and their tie rule is a threshold from the maximum (ADR-0017). The
  box centre of an arc is not CadQuery's key: on the D it is 1/2 off the chord
  where CadQuery's is 2/π.
- **Passing seams to arris.** arris refuses a seam in the list, where Open
  CASCADE passes over it: every `edges().fillet(r)` on a part with a
  cylinder face would be an `arris_refusal`.
- **Checking the value in `cq`, as `cutBlind(0)` does (ADR-0019).** CadQuery
  raises from Open CASCADE here, not from Python, and arris refuses in its own
  words. A check in `cq` would replace the kernel's words with ours for no
  change of class.
- **Calling `clean()` after `fillet`.** It moves nothing the oracle measures,
  and arris has no counterpart.
- **An estimate for every edge, as a face's.** A line, a circle and an arc
  have exact centres, and an estimate would put a margin on every selection
  of them for no gain.

## Amendment (2026-11-15): `cq` places the seams of the cylinders it builds as Open CASCADE does

plans/lift-edges-and-blends step 7 ran BenchCAD's 9,998 in-subset programs and found 300
`cq_bug` rows, 275 of them `edges(">Z or <Z")` ended `unsupported_api` by rule 2's bound: a
pin, washer or spacer ring turned along x or y (`"YZ"`, `"XZ"`), whose seams lie on walls
about an axis square to z. The bound is right for a seam whose place nothing tells: a washer's
two seams, one above its rims and one below, would leave `'>Z or <Z'` the seams alone. But
CadQuery's source tells the place of every seam `cq` itself builds, and the oracle bears it out.

**What CadQuery does.** `Workplane.cylinder` makes `Solid.makeCylinder` in the workplane's own
axes along +z and moves it there; `circle` makes `Wire.makeCircle` the same way, and `extrude`
and `cutBlind` sweep it; `hole`, `cboreHole` and `cskHole` make their cylinders along -z.
Open CASCADE's `gp_Ax2` for a direction of +z takes x along +x, and for -z along -x; a circle,
and the face it sweeps, starts at its frame's x. So the seam of a cylinder, of a swept circle and
of a pocket lies on the workplane's +x, and a bore's on its -x, at every point of the stack.
`polarArray` turns each point's axes by its angle, and the seam with them. `workplane()` on a
face of normal n takes x along z × n (`_computeXdir`), so on any face of a turned part along x
or y, x is square to z.

**What the oracle shows.** Ten constructions of `tools/cq_edge_probe.py` (`seam-*`, held in
`tests/test_edge_probe.py`), each with the parallel selector along its axis, record every seam
on that line: cylinders on `"YZ"`, `"XZ"`, `"ZX"` and a plane turned 30° about z; washers on
`"YZ"` and `"XZ"` with a bore from `">X"` or `"<Y"`; a swept disc with a bore; a counterbore;
a pocket by `cutBlind`; and two bores at `pushPoints`. arris puts its own seams by its own rule:
the bore's on `"YZ"` at -z where Open CASCADE's is at -y.

**Rule 2, amended.** Each `cq` chain carries a record of where Open CASCADE puts the seam of
every cylinder it built, or an operand of its `union` or `cut` did: the cylinder's axis line
and radius, and the side, the workplane's +x for `cylinder`, `extrude` and `cutBlind`, its -x
for a bore. A seam whose face is a cylinder whose axis is square to the selector's (its
component along the selector's axis exactly 0) is exact, at the axis's key plus the radius's
share along the side, where the records of that cylinder, matched by radius and axis line
within the model's tolerance, name one side. Elsewhere it is bounded as before. The chain
forgets every record, and every seam is bounded again, after a call whose seams it does not
model: `revolve`, and `polarArray`, which `cq` places without CadQuery's turn. A tool swept from
a part of a circle (an arc), whose face Open CASCADE could later join into one with a seam
where neither kernel says, forgets them too.

**Consequences.** The 275 programs run, every one `ok` on both sides: 191 agree with the
oracle and 84 are unclassified for a cause after the blend (81 clevis pins with a cross hole cut
after it, 3 spacer rings with a box cut after it; plans/lift-edges-and-blends step 7c);
`tests/fixtures/cq/ok-chamfer-corpus-clevis-pin` (once `unsupported-chamfer-corpus-clevis-pin-seam`),
`-washer` and `-spacer-ring` hold three of them to their closed forms. `edges(">X")` on a
lone `cylinder` keeps the seam and `>Y` ties it with the rims, as the oracle does; the seam of a
revolved wall still ends `unsupported_api` (`unsupported-edges-revolved-side`). Rules 1 and 3
to 6 are unchanged.

## Amendment (2026-11-24): Seams on full cylinder and rivet revolves

`tools/cq_edge_probe.py --revolves` records CadQuery's selected edges in
`tests/fixtures/edges/revolve.json`. On `XY`, `XZ` and `YZ`, the normal
selectors `<Z`, `<Y` and `<X` respectively keep the three circular rims,
the shank's line seam and the head's arc seam. All five centres of mass
lie in the drawing plane. The selector toward the drawing side can keep a
seam alone. Reversing the direction of the axis or the drawing order keeps
the seam on the side on which the generator was drawn.

**Rule 2, amended.** Record the axis and drawing side after a full turn
of a closed path about its local y direction on a world-axis-aligned
plane. The axis lies in the profile plane at one extreme of its drawing
points. The solid has two plane faces and a cylinder with two rims and
one seam. An optional spherical or toroidal head adds one rim and one
seam. The seam's centre of mass has the same axial
coordinate and radial distance from the axis as the kernel's seam. Project
that centre from the original drawing side. Parallel selectors keep the
cylinder's axial line seam under rule 3.

The placement belongs to the original solid, including when the stack
holds its faces or a previous edge selection. A combine that changes the
solid calls for fresh evidence. A partial turn keeps its ordinary boundary
edges. Cones, turned planes with oblique axes, and changed solids use the
existing bounded rule when the placement is unknown, as does the polar
bore in the previous amendment. A bare edge selection still resolves to
no solid (`runtime-edges-revolved-side`).

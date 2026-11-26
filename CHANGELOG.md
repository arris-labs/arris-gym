# Changelog

What a consumer of arris-gym can now do, the statuses they will see, and each
break with its fix. Pre-1.0, `0.y.z` is `y` breaking.

## Unreleased

- Static CadQuery reach excludes literal polygon lofts with more than
  two sections or with more than 48 nonplanar sides in every possible
  section pairing. Fidelity continues to count every program.

- In the CadQuery dialect, `mirrorY()` reflects an open outline with
  joined endpoints on the workplane's y axis. The closed profile keeps
  its lines and circular arcs for extrusion and cutting. Newly supported
  builds receive geometry-based scores under reward version 1.

- In the CadQuery dialect, `extrude(distance, taper=angle)` drafts a
  circle or rectangle and joins it to stock. Positive angles shrink the
  profile and negative angles expand it, rounding rectangular corners.
  For nonzero taper, `distance` is the slant length. Use `taper=0` for
  the straight extrusion. Inner wires end `runtime`. Giving both
  `taper=` and `both=` ends `unsupported_api`. Newly supported programs
  receive geometry-based scores under reward version 1.

- In the CadQuery dialect, `loft()` builds a smooth solid through two
  coaxial circles or matching straight-sided sections. It joins the solid
  to stock by default. Use `loft(combine=False)` to keep the new solid separate.

- In the CadQuery dialect, `workplane(offset=…)` and `transformed(…)` keep
  a single pending disc, rectangle, polygon or closed path where it was
  drawn. You can change the workplane and then extrude or blind-cut the
  original profile along the same normal.

- Upgrade the geometry kernel to arris 0.12.0. Chained fuses of cylinders
  on a shared end plane now build, as do several point- and edge-touching
  unions and horn and spindle torus revolves. Some overlapping blends
  now return `arris_refusal` with `OpDegenerateError`. Outcomes and scores
  can change with the recorded kernel version.

- In the CadQuery dialect, axis edge selectors rank seams in the original
  drawing plane on supported full cylinder and rivet revolves. This lets
  selectors across the drawing plane reach the rivet's chamfers and fillets.
  Programs that now build receive geometry-based scores under reward version 1.

- `Measures.solids` counts the material pieces in a body with sealed
  cavities. `fidelity.compare` checks that count against the oracle's
  solid count.

- `fidelity.SignedSolids` is new verdict evidence for `occt_wrong`. It holds
  each solid's signed volume, from an independent boundary flux, of an
  `invalid` oracle shape where arris built the part. `compare` accepts it
  only on an arris `ok` against an oracle `invalid` row, with one volume per
  oracle solid, at least one negative, a finite sum within the agreement
  tolerance of both measured volumes, and matching counts of arris solids
  and positive oracle solids.

- In the CadQuery dialect, draw slots with `slot2D(length, diameter, angle)`
  at the workplane origin, a moved point or each point of an array. The angle
  is in degrees. Extrude the slots or cut them with `cutBlind` or
  `cutThruAll`. With nonnegative dimensions, equal dimensions or zero
  diameter return `runtime`.
  A nonnegative length shorter than a positive diameter returns
  `arris_refusal`. Touching or overlapping slots at array points
  return `unsupported_api`.

- In the CadQuery dialect, draw centred rectangles with `rect(xLen, yLen)`
  at the workplane origin, a moved point or each point of an array. Extrude
  them or cut them with `cutBlind` or `cutThruAll`. Nested rectangles and
  circles can form holes in extrusions and blind cuts.

- In the CadQuery dialect, use `center(x, y)` to shift the workplane origin
  before drawing or drilling. Pending closed wires keep their original positions.

- In the CadQuery dialect, use `cutThruAll()` to cut circles, rectangles,
  slots, polygons and closed paths through the entire stock. A distant
  workplane offset preserves the profile's alignment and the full span
  of the cut. Concentric circular rings and nested sections with a
  rectangle return `runtime`.

- In the CadQuery dialect, use `Sketch.face(tool)` to add a copy of another
  sketch's section at the selected points, or use `mode="s"` to subtract it
  and `mode="i"` to intersect it. Later edits to the tool leave that copy intact.

- The CadQuery dialect supports `Workplane.sketch()` on an empty stack.
  Draw circles and rectangles at selected points, add, subtract or intersect
  them, then use `finalize().extrude(distance)` to build the solid.
  A section with no material returns `runtime` at extrusion.

- In the CadQuery dialect, draw sketch outlines with `segment` and `arc`.
  Use `close` to draw a closing line and `assemble` to add the region
  at the sketch's selected points. Assembly returns `runtime` when
  the edges fail to form one closed loop. A collinear arc returns
  `runtime` at the drawing call.

- The census counts calls after `Workplane.sketch()` through `finalize()`
  under `Sketch.*`. Calls after `finalize()` return to the workplane
  receiver. CAD-Recode's census and reach curve digests change.

- A fidelity row that pairs the CadQuery dialect's `unsupported_api` with an
  oracle shape that fails CadQuery's validity check is now classed `cq_bug`,
  as an `unsupported_api` against a valid oracle shape already was; it was
  `unclassified`. No reward moves.

- In the CadQuery dialect, `workplane()` on a single unified cylinder, cone,
  sphere or torus face now places a plane through its centre of mass with the
  outward normal at its projection onto the surface. A singular projection
  returns `runtime`. A poorly conditioned projection returns `unsupported_api`.

- In the CadQuery dialect, `workplane()` on co-planar faces with a common
  outward normal uses their area-weighted offset. This includes selected
  faces at slightly different heights and selections on a slanted plane.

- CadQuery face selectors use the kernel's surface centre of mass and rank
  connected faces of the same surface by their combined centre. This fixes
  workplane placement on parts such as a connecting rod whose cylinder is
  split at its seam. Edges inside a unified face are skipped. Edge selection
  and blending that depend on joining split boundary edges return
  `unsupported_api`. Mixed planar and curved selections, multiple distinct
  curved faces, and planar selections that fail the co-planarity check in every
  order now reach CadQuery's `ValueError` as `runtime`.

- arris-gym now requires `arris` 0.11.1 (was 0.10.0). Every row records the
  kernel's version and every digest hashes it, so a digest from an earlier run
  no longer matches, and a cached result from 0.10.0 is not reused. The
  reward's version is unchanged: a kernel bump is named by `versions.arris`.
  On BenchCAD and CAD-Recode no status, measure, class or reward moves.

- `dialect="cq"` now runs `edges()` and `edges(selector)` with the axis
  selectors `>X <X >Y <Y >Z <Z`, the parallel selectors `|X |Y |Z` and
  `'>Z or <Z'`, `fillet(radius)` and `chamfer(length)`: the edges on the stack, or
  every edge of the stacked faces or solid, rounded or bevelled in one call. An edge is ranked by its
  centre of mass, as in CadQuery; a seam (a cylinder's, a hole's) is passed over
  by a blend. `fillet` and `chamfer` on a chain with no solid, a stack with no
  edge and a stack of seams alone end `runtime`, as in CadQuery; `edges(selector)`
  on an empty stack does too, but `edges()` with no selector on an empty stack
  or on a stack that holds no solid ends `unsupported_api` (CadQuery gives an
  empty workplane for the empty stack); a radius or length of zero, a negative one or one
  past what the edge's faces allow ends `arris_refusal` where CadQuery raises.
  A selection whose answer is the kernel's own choice (an edge's place on a
  face about another axis, a B-spline edge) ends `unsupported_api`. `faces`
  does not take the parallel or `or` selectors.

- `dialect="cq"` now runs `cutBlind(depth)`: the pending circle, ring (two
  concentric circles) or circles at points (`pushPoints`, `rarray`,
  `polarArray`) cut from the part, `depth` along the workplane's normal, so a
  negative depth cuts into the part from a face, one past the part makes a
  hole through, and a positive one cuts nothing. A depth of zero, a chain with
  no pending circle and a chain with no solid end `runtime`, as in CadQuery;
  `clean=` and an `until` that is not a number end `unsupported_api`.

- `dialect="cq"` now runs `polarArray(radius, startAngle, angle, count)`:
  points on a circle about the workplane's origin, at which `hole`,
  `cboreHole`, `cskHole` and `circle` act as at the points of a `pushPoints`.
  A full turn is split in `count` and a partial one in `count - 1` with both
  ends included; one point sits at `startAngle`; a negative radius puts each
  point across the centre. A count under 1 ends `runtime` with CadQuery's
  words, as does a count that is not an integer; `fill=` and `rotate=` end
  `unsupported_api`.

- `dialect="cq"` now runs `rarray(xSpacing, ySpacing, xCount, yCount)`: a grid
  of points centred on the workplane's origin, at which `hole`, `cboreHole`,
  `cskHole` and `circle` act as at the points of a `pushPoints`. A spacing of
  zero or less or a count under 1 ends `runtime`, as does a count that is not
  an integer, in CadQuery's words; `center=` ends `unsupported_api`.

- `dialect="cq"` now runs a second `faces(selector)` on the faces a first one
  kept (`faces(">Z").faces(">Z")`): as in CadQuery it ranks those faces only,
  so a single face stays whatever the second selector is. `circle(radius)` on
  the points of a `pushPoints` draws a circle at each, and `extrude` builds a
  post on each and fuses them with the part. Circles that would overlap or
  touch (a duplicate point included), a point with an offset along the normal,
  and a ring of circles at points end `unsupported_api`.

- `dialect="cq"` now runs `cskHole(diameter, cskDiameter, cskAngle)`: a
  countersunk hole at the plane's origin or at every point of a `pushPoints`,
  as CadQuery builds it (a bore through, under a cone of `cskDiameter` at the
  face and `cskAngle` degrees across). A cone no wider than the bore leaves
  the bore, and a zero `diameter` leaves the cone alone. A negative diameter,
  an angle of zero, a zero or negative `cskDiameter`, and an angle that gives
  the cone no height (from -180 to 0 and from 180 to 360) end `runtime`, as in
  CadQuery; an angle outside -180 to 360, `clean=` and a depth end
  `unsupported_api`.

- `dialect="cq"` now runs `cboreHole(diameter, cboreDiameter, cboreDepth)`: a
  counterbored hole at the plane's origin or at every point of a `pushPoints`,
  as CadQuery builds it (a bore through, a wider counterbore from the face).
  A counterbore no wider than the bore leaves the bore, one deeper than the
  part makes a through hole of its own width, and a zero diameter leaves the
  other piece alone. A negative diameter or counterbore diameter, a
  counterbore depth of zero or less, and both diameters zero end `runtime`, as
  in CadQuery; `clean=` and a depth still end `unsupported_api`.

- `dialect="cq"` now runs `hole(diameter, depth=depth)`: a bore `depth` long
  from the workplane, blind where it ends inside the part and through where it
  reaches the far face, at the plane's origin or at every point of a
  `pushPoints`. A `depth` of zero or less ends `runtime`, as in CadQuery, which
  raises for it even beside a zero diameter. `depth` is the keyword only: a
  second positional argument still ends `unsupported_api`.

- `dialect="cq"` now runs `pushPoints(list)`: a stack of points, each a tuple
  or list of two numbers (the plane's own x and y) or three (the third along
  the normal), and `hole(diameter)` after it bores at every one in a single cut,
  as CadQuery's does; an empty list bores once at the plane's origin. A point
  that is not two or three numbers, and `pushPoints` after a selected face, a
  `moveTo` or a drawn path, or any other call on the points, still end
  `unsupported_api`. A hole that ends inside the part (a point offset above the
  face) is now as long as CadQuery's.

- `dialect="cq"` now runs a second `circle` after a first one, as CadQuery
  does: it is drawn about the first circle's centre and the two make a ring
  that `extrude` (with or without `both=True`) or `revolve` builds, the larger
  circle outside whichever was drawn first. A second circle of the same radius
  or of radius 0, a third circle, and `polyline`, `box` or `union` on the ring
  still end `unsupported_api`.

- `dialect="cq"` now runs `hole(diameter)` as CadQuery does with no depth: a
  cylinder bored from the workplane's origin (after `workplane()` on a face or
  on a solid), against the plane's normal and as long as the solid's
  bounding-box diagonal. It cuts through material below the
  plane and leaves what lies above it. A hole that splits the part leaves a
  compound. A zero diameter changes nothing and a negative one ends `runtime`,
  as in CadQuery; a chain with no solid ends `runtime` too. A hole on a stack
  that holds a `moveTo` point starts there, and on one that holds a solid at its
  centre of mass, as CadQuery's does. A hole on selected faces or beside a
  drawn path ends `unsupported_api`, and a hole that leaves
  nothing ends `arris_refusal`, where CadQuery's own checker cannot measure its
  empty result.

- `dialect="cq"` now runs `faces(selector)` for `">X"`, `"<X"`, `">Y"`,
  `"<Y"`, `">Z"` and `"<Z"` on the solid a chain holds, and `workplane()` on
  the planar faces it keeps: the plane of that face, its normal the face's
  outward normal, or the one plane of several coplanar faces. A circle,
  polygon or `moveTo` drawn there and extruded fuses with the solid, as in
  CadQuery. Several selected faces not all planar, or whose normals CadQuery
  finds not co-planar, end `runtime` with CadQuery's `ValueError` on a small
  part only (a bounding-box diagonal under about 0.5 to 1 model units); the
  same shape larger ends `unsupported_api` in `faces`, where CadQuery still
  raises: `cylinder(0.2, 0.1).faces(">X").workplane()` ends `runtime`,
  `cylinder(2, 1)`'s `unsupported_api`.
  `workplane(offset=…)` on them moves the plane along its normal. `faces` on a
  stack with no faces (an empty stack, a point, a drawn path) ends `runtime` with
  CadQuery's `ValueError`; on a compound it selects across its pieces. Any other
  selector, a curved face, several faces at slightly different offsets,
  any other call on them, and a selection that
  depends on a face's centre of mass arris does not give (a cylinder's
  `">X"`) end `unsupported_api`.

- `dialect="cq"` now runs `polyline` after a lone `moveTo` point, as CadQuery
  does: the polyline starts at its own first point and the `moveTo` point is
  dropped. `polyline` after a drawn path or another polyline still ends
  `unsupported_api`.

- `dialect="cq"` now runs `extrude(distance, both=True)`: the pending sketch
  grows `distance` to each side of its plane, one prism of height
  `2 * |distance|`, fused with or cut from the chain's solid as `extrude`'s
  is. `both=False` is plain `extrude`; the other keywords (`combine`,
  `clean`, `until`) and `extrude(distance, True)`, whose second
  argument is CadQuery's `combine`, still end `unsupported_api`. A zero
  distance, with or without `both`, ends `runtime`, as CadQuery's does.

- `dialect="cq"` now runs `polygon(nSides, diameter)`: a regular polygon
  inscribed in the circle of `diameter`, centred on the workplane's origin
  or on a `moveTo` point, its first vertex on the plane's x axis, ready to
  extrude or revolve as a circle is. Its keywords (`forConstruction`,
  `circumscribed`) end `unsupported_api`, and so does a polygon on a stack
  holding anything but one `moveTo` point. A negative diameter turns the
  polygon by half a turn, as CadQuery's does; fewer than three sides or a
  zero diameter end `runtime`.

- `dialect="cq"` now runs `sphere(radius)`: a sphere centred on the
  workplane's origin or on a `moveTo` point, its poles on the plane's
  normal, fused with a solid further up the chain. Its other arguments
  (`direct`, `angle1` to `angle3`, `centered`, `combine`, `clean`) end
  `unsupported_api`, and so does a sphere on a stack holding a drawn
  outline, a circle or a solid. A radius not positive ends `runtime`.

- `dialect="cq"` now runs `threePointArc(point1, point2)`: a circular arc
  from where `lineTo` would start, through `point1`, ending at `point2`,
  each two numbers in the workplane's coordinates, so an outline of lines
  and arcs can be closed, extruded and revolved. A point of three numbers
  or a `Vector`, or a keyword, ends `unsupported_api`. After a closed
  outline, a circle or a solid it ends `runtime`, as CadQuery's does;
  three points on one line (two that coincide, or an arc ending where it
  starts) end `arris_refusal` in the kernel's words where CadQuery raises.

- `dialect="cq"` now runs `union` on a workplane whose chain holds no
  solid, as CadQuery does: the result is the given workplane's solid, so
  `cq.Workplane("XY").union(part)` starts a chain. A `cut` there still ends
  `runtime`.

- `dialect="cq"` now runs `cylinder(height, radius)`: its axis along the
  plane's normal, centred on the plane's origin or a `moveTo` point in all
  three axes, and fused with a solid already in the chain. Its other
  keywords, and a drawn path, a sketch, a solid or a compound on the
  stack, end `unsupported_api`; a height not above 0 or a radius not above
  0 ends `runtime`.

- `dialect="cq"` now runs `cq.Workplane("YZ")`, with sketch axes along
  world +y and +z and extrusion along +x.

- `dialect="cq"` now runs `cq.Workplane("XZ")`, with sketch axes along
  world +x and +z and extrusion along -y.

- `dialect="cq"` now runs `cq.Workplane("ZX")`, with sketch axes along
  world +z and +x and extrusion along +y, and `cq.Workplane(name,
  origin=(x, y, z))` on each plane it runs, the plane moved to that world
  point with its axes kept. Any other `origin` ends `unsupported_api`.

- `dialect="cq"` now runs `workplane()` and `workplane(offset=d)`: a new
  plane `d` along the normal, from the current origin on an empty stack and
  from the height of the solid's centroid when the stack holds one solid,
  its axes kept. Other keywords or a pending wire on the stack end
  `unsupported_api`.

- `dialect="cq"` now builds a compound: a `union` of solids that do not
  meet, or a `cut` that splits its base, ends `ok` with one body holding a
  shell per piece, where it ended `unsupported_api` "a Workplane holding
  `n` solids". Its measures are the sums over the pieces (the centroid
  volume-weighted, the bounds their union, `shells` one per piece), later
  calls act on every piece, and it scores as any body (reward version 1
  unchanged). A fidelity row agrees with an oracle compound of as many
  solids as the body has shells.

- `dialect="cq"` now runs `circle` after `moveTo`, centring the circle on
  that point; a circle on any other non-empty stack still ends
  `unsupported_api`.

- `dialect="cq"` now runs `box` after `moveTo`, centring the box on that
  point, and fuses it with a solid already in the chain; a box after a drawn
  path or a sketch still ends `unsupported_api`.

- `dialect="cq"` now ends `unsupported_api` "Workplane.box on a stack
  holding a solid" for a `box` called straight on a solid (after `extrude`,
  `revolve`, `box`, `union` or `cut`), where it ended `ok` with the box on
  the plane's origin: CadQuery centres it on the solid's centre of mass.

- `dialect="cq"` now ends `unsupported_api` "Workplane.polyline(list of 1
  point)" (or "0 points") for a polyline of fewer than two points, where a
  `box`, `circle` or `lineTo` after it went on from that point as after
  `moveTo`; CadQuery goes on from the plane's origin.

- `dialect="cq"` now accepts a module-level `r` as the result, after the
  last `show_object` argument and module-level `result`. A present but
  invalid value keeps that precedence. The oracle reads the same names,
  and `cq.Subset.end_forms` now admits `r = …`.

- `fidelity.reach_report(table, programs, subset)` returns a frozen
  `ReachReport` for a corpus: reach, agreement over all programs, timeouts, and
  the in-subset rows by outcome and class, with `in_subset_cq_bug` and
  `in_subset_by_design` named. It refuses programs and rows that do not match
  one to one.

- `census.cadrecode` reads the pinned original CAD-Recode validation split
  with the `[corpus]` extra; `arris-gym census --corpus cadrecode` writes its
  census and reach curve. All derived rows carry CC-BY-NC-4.0. The 968
  programs end in `r = …`.

- `census.reach_curve(programs, subset)` returns frozen `ReachCurve` /
  `ReachStep` records showing how many programs each additional census item
  (`kind` form, selector or end form; the exact `item`) admits, with a
  deterministic digest. `arris-gym census` also writes
  licensed per-program counts to `programs.jsonl.gz` and the curve to
  `reach.json`, without program text.

- `cq.subset()` returns frozen `Subset` / `CensusForm` declarations of the
  implemented forms, selectors and end forms; `Subset.admits(form)` checks
  a census API form without running it. `census.reach(programs, subset)`
  returns a frozen `Reach` with the in-subset count and stems over every
  program, unparsable programs included. It accepts source records or saved
  census outcomes. Static membership does not promise execution success.

### Breaking

- Census rows can carry `deferred_polygon_loft`, and `cq.subset()`
  exposes `defer_polygon_lofts`. Update strict census readers and
  regenerate saved subset and reach snapshots where these limits apply.

- `Workplane.extrude` adds the keyword-only `taper` parameter.
  Regenerate saved `cq.subset()` snapshots and handle execution results
  for the new form where a caller previously expected `unsupported_api`.
- Serialized `Measures` and `dump_text` include `solids`, which can be
  `None` when the count is unavailable. Accept the new field in readers
  and regenerate saved execution digests.
- `fidelity.Verdict.evidence` can now contain `fidelity.SignedSolids`.
  Add a `signed_solids` case to exhaustive evidence handlers.
- `cq.subset()` declares `Workplane.cutThruAll()`, `Workplane.center(x, y)`,
  `Workplane.rect(xLen, yLen)` and `Workplane.slot2D(length, diameter, angle)`.
  Regenerate saved subset snapshots and handle execution results for these
  forms where a caller previously expected `unsupported_api`.

## 0.1.0 — 2026-11-10

- `arris-gym rescore benchcad` (needs the `[corpus]` extra) runs the 300 slice
  programs under `cq` and scores each against the CadQuery oracle's STEP of the
  same program, writing `rescore.json` and `rescore.md`: a row per program with
  its status, stage, terms, digests, source, licence and versions, and
  aggregates over all 300. `mean_reward_valid` (valid programs only) is printed
  beside `mean_reward` and labelled as survivors. The table's digest is equal
  on x86-64 and aarch64. From Python: `arris_gym.rescore.rescore(entries)`
  returns a `RescoreTable` (`RescoreEntry`, `RescoreRow`, `Stage`, `TimedOut`).
  `Stage` says whether a failure was the program's (`program`), its target's
  (`target`) or the scorer's (`scoring`). `tools/rescore_diff.py A B` lists the
  rows two tables differ at.
- `read_target(step)` (also `Sandbox.read_target`) reads a STEP in a worker of
  its own and returns a frozen `TargetResult`: one valid solid gives its body,
  measures and `step_sha256`; text the kernel cannot read, no solid or several
  give `arris_refusal` or `runtime` with the kernel's words. It never raises on
  the text.
- `sandbox.check_workers` and `reward.failed_score` are public: the first
  checks a `workers=` count as `run_many` does (a positive integer, or
  `None` for the default) and raises `ValueError` otherwise; the second
  builds the `Score` of a failed scorer (status, message, reward -1.0).
- A program run on a standalone Python (such as one `uv` downloads) now starts
  inside the sandbox: an exec job may read the shared libraries its
  interpreter links.

- `score(result, target)` gives an `ExecResult` its reward against a target
  body, under reward version 1 (`DEFAULT_REWARD`), as a frozen `Score`:
  `syntax`, `runtime`, `unsupported_api`, `timeout` and `crash` get -1.0,
  `arris_refusal` -0.5, `checker_fail` -0.3, and a valid body
  `0.1 + 0.9·S` over its IoU, surface, measures and topology terms, each in
  [0, 1]; a body scored against itself gets exactly 1.0. `Score.iou_route`
  (`IouRoute`: `exact` or `sampled`) says whether the kernel answered the IoU
  exactly or it was estimated from seeded points. A valid body is scored in a
  worker of its own (`sandbox=`, `timeout=` 30 s, `memory=`): when scoring
  fails the score is `runtime` with the kernel's words, `timeout` or `crash`,
  and its reward -1.0. `RewardConfig` and `RewardWeights` set the weights, τ,
  sample counts and seed; a config's `version` is written into every `Score`,
  and `Score.digest()` hashes its numbers. A valid body's `Score.field`
  (`FieldMetrics`) holds BenchCAD's own metrics beside ours, computed as its
  scorer does: `voxel_iou_64`, in [0, 1], and `chamfer_x1000`, at least 0.
  Both normalise each body to its own box, so they ignore size and place (a
  cube against its double gives 1 and 0), and neither moves the reward. The
  Chamfer samples are seeded, so a body against itself gives exactly 0.
- `invalidity_rate(scores)` is the share of all given scores whose status is not
  `ok` (BenchCAD's invalidity rate): every failure counts, and no scores raise
  `ValueError`.
- `run(program, dialect="cq")` (also `run_many`, `Sandbox.run`) runs a
  CadQuery program: `import cadquery as cq` gives a subset over `arris.build`
  and `show_object` is available. The subset covers `Workplane("XY")`,
  `Vector`, `transformed`, `box`, `circle`, `extrude`, `union`, `cut`,
  `moveTo`, `lineTo`, `polyline`, `close` and `revolve`. A program's result
  is the last `show_object` argument, else `result`. Any other call, name,
  import or argument form ends `unsupported_api` naming it; a result that is
  not one solid is `runtime` (none) or `unsupported_api` (several).
  `Dialect.CQ` is new.
- `arris_gym.fidelity` compares an `ExecResult` with an oracle report of the
  same program run on CadQuery 2.3.0 and Open CASCADE 7.9.3.0.
  `compare(result, report, verdict=None)` returns a frozen `FidelityRow`:
  `agree` (volume, area, centroid and bounds within a named tolerance), a
  `disagree` with its `DisagreementClass` (`cq_bug`, `arris_refusal`,
  `arris_bug`, `occt_wrong`, `by_design`), or `unclassified` until a `Verdict`
  with its evidence (a closed form, a second oracle's record, a doc anchor or a
  regression fixture) classes it. Each row carries both sides' statuses,
  measure deltas and versions; a timeout on either side is `unclassified` and
  named. `compare` raises `ValueError` for a verdict it cannot accept (one on an
  agreement, or one that would clear an arris crash).
- `fidelity.parse_outcome` turns an oracle worker's outcome into an
  `OracleReport` (`OracleStatus`: `ok`, `syntax`, `runtime`, `no_result`,
  `invalid`, `timeout`, `crash`) and never raises: a report that contradicts
  itself is a `crash`. An `ok` report carries the oracle's STEP as `step`,
  the same text on every run (its timestamp and translator counter blanked),
  and `step_sha256` is its data section's hash; a STEP that contradicts its
  hash is a `crash`. `step` stays out of `OracleReport.digest()`.
- `fidelity.fidelity_table(entries)` gathers rows, each with its program's
  source and licence, into a `FidelityTable`: sorted by name, counts over every
  row, and a digest that input order does not move. `fidelity.arris_rows(table)`
  gives an `ArrisReport` for the arris kernel (`to_json`, `to_markdown`):
  refusals by kind then the kernel's message, arris bugs with their program's
  SHA-256 and fixture, and the licences and versions behind them.

- `arris-gym census --corpus benchcad` parses BenchCAD's `code_gen` programs
  without running any and writes `census.json` and `slice.txt` (the first 100
  programs of each of the 3 families, of at least 100, that call the least
  distinct API): every CadQuery call, selector string and argument form by
  family, each program counted or listed as
  unparsable with its exception verbatim, under a digest that a re-run
  reproduces. It needs the `arris-gym[corpus]` extra (without it the command
  prints one line and exits 2). `arris_gym.census` offers `census_program`,
  `census`, `select_slice`, `slice_families` and `CensusReport` for the same from Python.
- `arris_gym.run(program)` runs one `arris`-dialect program alone in an
  isolated process and returns a frozen `ExecResult` with a `Status`: `ok`
  (with the body and its measures), `syntax`, `runtime`, `unsupported_api`,
  `arris_refusal` (the kernel's class, message and entities verbatim),
  `checker_fail`, `timeout` or `crash`. It raises only for a caller's mistake
  (an unknown dialect, a non-positive timeout or memory limit) or
  `SandboxUnavailable` where the machine cannot isolate a program. Linux only,
  with user namespaces, Landlock, `mount_setattr` and seccomp (on Ubuntu
  24.04, `kernel.apparmor_restrict_unprivileged_userns` must be 0).
- `arris_gym.run_many(programs, workers=N)` runs many programs, at most `N`
  alive at once, and returns one result per program in submission order.
  `arris_gym.Sandbox` is the same as an object you can close, safe to call
  from several threads.
- `Sandbox(cache_dir=...)` caches results exactly: the same program under the
  same limits and versions is not run twice (`Sandbox.executions` counts the
  runs). A `timeout`, a `crash` or a `MemoryError` is never cached.
- `arris_gym.dump_text(result)` writes a result as text, a line per field, to
  read or `diff`; `arris_gym.digest(results)` hashes results in order, floats
  exact and wall-clock time left out, so two runs are equal when their
  digests are.
- `arris_gym.dump_png(result, path)` draws a result's body as a PNG, four
  fixed views of the part in one greyscale sheet, to look at.
- A program that forks no longer comes back as a `crash` on some runs and
  `ok` on others: only the program's own process reports, so a fork bomb is
  always a `runtime` error (`BlockingIOError`) and a program that forks and
  then builds a part is always `ok`.

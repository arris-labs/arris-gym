# `cq` fixtures

Programs run under `dialect="cq"` (or `"arris"`, where `expected.json` says
so), one per outcome of the subset (ADR-0007): a name outside it ends
`unsupported_api` naming it as the census writes it, a result that does not
resolve to one solid ends `runtime`. Expected messages follow from the
program's text and ADR-0007's rules; measures come from closed forms.

The `ok-*` fixtures build parts whose measures are worked out from how they
are built (`note` in `expected.json` says how). Where `oracle.json` sits
beside one, it is the oracle's recorded report of the same `program.py`
(`uv run tools/oracle_run.py --out ... tests/fixtures/cq/<slug>/program.py`,
the row's `report` less `seconds`), and `tests/test_cq.py` holds it to the
same closed form: the semantics are CadQuery's, not only arris-gym's reading
of them. `ok-box-rotated-xyz` is one: a turn about x, y and z at once, whose
bounds tell CadQuery's order (Rx·Ry·Rz) from the reverse one. `ok-revolved-quarter`
is another: a 90° revolve, whose bounds tell a right-handed turn from a
left-handed one. `ok-revolved-rectangle` and `ok-revolved-rectangle-lines`
draw one profile by `polyline` and by `moveTo`/`lineTo`; `tests/test_cq.py`
holds their body digests equal.

`ok-result-r` binds a centred 2 × 4 × 6 box to `r`; its volume is 48,
area 88 and centroid the origin. ADR-0015 admits this result after the
last `show_object` argument and `result`. The 300 C1 oracle programs were
rerun after that change: `tests/fixtures/c1/oracle.jsonl` stayed byte-equal,
SHA-256 `6bbfb7724508505b44e664d1b74d16c2ce70bf777d2c8e70e86de93cd3add68b`.

`ok-plane-yz-box` fixes the `YZ` axis order with unequal dimensions.
`ok-plane-yz-prism` fixes its axis signs and local offset: a 3 × 4 right
triangle extruded by +7 along world +x, volume 42, area 96, centroid
(8.5, 5, 4/3). Both have recorded oracle reports and agreeing fidelity rows
in `test_cq_planes.py`. Its property varies the triangle, local offset and
signed extrusion against the closed form. All 319 BenchCAD programs whose
diagnosed first failure was `cq.Workplane('YZ')` were rerun against their
baseline oracle reports on 2026-11-12: 319 `ok`, 319 agree, no other outcome.

`ok-plane-xz-box` and `ok-plane-xz-prism` do the same for `XZ`, whose normal
is world -y: the prism's local (u, v, w) maps to world (u, -w, v), so the
+7 extrusion spans y from -12 to -5, centroid (5, -8.5, 4/3). Both have
recorded oracle reports and agreeing rows in `test_cq_planes.py`, with a
property like `YZ`'s. `unsupported-named-plane` moved from `XZ` to `ZX`,
a CadQuery name the subset still refuses. All 285 BenchCAD programs whose
diagnosed first failure was `cq.Workplane('XZ')` were rerun against their
baseline oracle reports on 2026-11-12: 285 `ok`, 285 agree, no other outcome.

`ok-circle-at-point-prism` and `ok-circle-at-point-half-torus` fix where
`circle` goes after `moveTo`: on its point, in the plane's axes. The prism
draws a radius-2 circle at local (3, 1) on `XZ` and extrudes it 5 toward
world -y, centroid (3, -2.5, 1). The half torus turns a unit circle at
(3, 2) by 180° about +y, so it lies in z ≤ 0, centroid z -37/(6π). Both
have recorded oracle reports and agreeing rows in `test_cq_circle.py`, with
a property over the plane, point, radius and signed extrusion. All 113
BenchCAD programs whose diagnosed first failure was `circle` on a non-empty
stack were rerun against their baseline oracle reports on 2026-11-12: 70
`ok` and agree, 43 `arris_refusal` (a box touching the torus at its seam
vertex, BACKLOG `torus-box-point-contact`), no `cq_bug` or timeout.

`ok-origin-box-xy`, `-yz`, `-xz` and `-zx` put a 2 × 4 × 6 box on each
admitted plane with `origin=(3, -5, 7)`: the centroid is that world point
on every plane, and the bounds fix each plane's axis order (`ZX`: x +z,
y +x, normal +y). `ok-origin-prism-zx` adds a local `transformed` offset
on `ZX`: origin (1, 2, 3) plus local (3, -2, 5), world (-2, 5, 3), puts the
triangle's plane at (-1, 7, 6), centroid (7/3, 10.5, 8). All five have
recorded oracle reports and agreeing rows in `test_cq_origin.py`, with a
property over plane, origin, local offset, triangle and signed extrusion.
`unsupported-named-plane` moved from `ZX`, now admitted, to `YX`, a
CadQuery name the subset still refuses.

`ok-workplane-offset-xy`, `-yz`, `-xz` and `-zx` call `workplane(offset=4)`
on an empty stack of each admitted plane with `origin=(1, 2, 3)` and put a
2 × 4 × 6 box there: the centroid is the origin moved 4 along the normal.
`ok-workplane-on-solid-*` call `workplane(offset=1.5)` on a 6 × 2 × 2 slab
(local u from -1 to 5, origin `(1, 1, 0)`) and put a 1 × 1 × 2 box there:
its boss spans local w from 2 to 3.5, so the plane passed through the
slab's centroid height (w = 1), while u and v stayed the origin's, not the
centroid's (u = 2). `ok-workplane-on-solid-neg-xz` does it below a slab
extruded by -2 with a negative offset, `ok-workplane-bare-xy` with
`workplane()` (offset 0), a box crossing the slab both ways. All ten have
recorded oracle reports and agreeing rows in `test_cq_workplane.py`, with
properties over plane, origin, signed offset, slab and signed extrusion.
`unsupported-workplane-on-pending-wire` and `-invert` are the context and
keyword the subset refuses (read on the oracle, CadQuery keeps the origin
after a `moveTo` point, which the subset does not model).

`ok-box-at-point-*` fix where `box` goes after `moveTo`: centred on its
point, in the plane's axes (CadQuery's `centered=True`). `-xz` puts a
2 × 4 × 6 box at local (3, 1) on `XZ`, centroid (3, 0, 1), y from -3 to 3;
`-offset-yz` does it on `YZ` with `origin=(1, 2, 3)` after
`workplane(offset=5)`, centroid (6, 5, 4); `-fused-xy` fuses a 1 × 1 × 4 post
at (1, 0) through a 4 × 4 × 2 slab, centroid x 1/17. All three have recorded
oracle reports and agreeing rows in `test_cq_box.py`, with a property over
plane, origin, offset, point and dimensions. `unsupported-box-on-pending-wire`
now draws a segment after its `moveTo`: a box there is still refused.
`unsupported-box-on-solid` calls `box` on the stack an extrusion left: read
on the oracle, CadQuery centres the box on the solid's centre of mass
(`eachpoint` over the solid's `Center()`), so a unit box after
`moveTo(5, 0).circle(1).extrude(2)` lies inside the cylinder (V = 2π) and a
1 × 1 × 10 one spans z from -4 to 6; the subset refuses the context. No
BenchCAD or CAD-Recode row the C2 tables hold as `ok` or a refusal reaches it.
`unsupported-polyline-one-point-box`, `-circle` and `-line` follow
`polyline([(3, 1)])` with a box, a circle and two `lineTo`s: read on the
oracle, CadQuery centres the box and the circle on the plane's origin and
starts the first segment there, not at (3, 1) as after `moveTo(3, 1)`. The
subset refuses a polyline of fewer than two points; no C2 row reaches one.

`ok-compound-two-boxes`, `ok-compound-three-boxes`, `ok-cut-into-pieces` and
`ok-workplane-on-compound` are compounds (ADR-0016): solids that do not meet,
one arris body with a shell per piece, its measures the sums over the pieces,
the centroid volume-weighted. Two unequal boxes give centroid (4.2, 0, 0.8);
three, chained, (32/15, 2, 0); a bar cut across its middle two pieces of
volume 3 in all; `workplane(offset=1)` on two boxes at heights 0 and 2 puts
its plane through the compound's centroid height 1, so the box there is a
third piece. `ok-compound-bridged` unites a bar with a two-box compound into
one solid. They replace `unsupported-union-disjoint`,
`unsupported-cut-into-pieces` and `unsupported-workplane-on-two-solids`.
Each has a recorded oracle report of as many solids as the closed form has
shells, and an agreeing row in `test_cq_compound.py`, with a property over
two to four disjoint boxes. `ok-compound-occt-centroid` is the one recorded
report the oracle gets wrong: its centroid is (4.725, 0, 0.975) against the
closed form's (4, 0, 0.8), and `verdict.json` classes the row `occt_wrong`
by that closed form (BACKLOG Findings `occt-compound-centroid`);
`test_cq.py` leaves a fixture with a `verdict.json` out of the oracle's
closed-form check.

`ok-cylinder-centred-xy`, `-at-point-xz`, `-at-point-offset-yz`,
`-transformed-zx`, `-origin-zx` and `-fused-at-point-xy` call
`Workplane.cylinder(height, radius)` (`ok-cylinder` and
`ok-cylinder-transformed` extrude a circle instead). Each is centred on its
point in all three axes, its axis the plane's normal, `height / 2` either
side: on `XY` at the origin, z ±2; on `XZ` at `moveTo(3, 1)`, world
(3, 0, 1); on `YZ` with `origin=(1, 2, 3)` after `workplane(offset=5)`,
(6, 5, 4); on `ZX` after `transformed` with a 90° turn about local x, its
axis world -x (unturned, the bounds would differ); on `ZX` with
`origin=(3, -5, 7)`; and a radius-0.5 post fused into a 4 × 4 × 2 slab from
`workplane(offset=1)` on it, its lower half inside the slab, V = 32 + π/4.
All six have recorded oracle reports and agreeing rows in
`test_cq_cylinder.py`, with a property over plane, origin, offset, point,
height and radius.

`unsupported-cylinder-on-pending-wire`, `-on-closed-wire`,
`-on-pending-circle`, `-on-solid` and `-on-compound` call `cylinder` on
each stack context the subset does not model. Read on the oracle
(2026-11-13), CadQuery builds every one, centring the cylinder on the
object's `Center()`: the segment (1, 1)-(2, 1) puts it at (1.5, 1); the
closed triangle at its edges' centre (1.293, 0.707); the circle at (3, 1),
leaving the circle unused (V = 2π); the extruded post at its centre of
mass (5, 0, 1), so a 10 × 0.5 cylinder spans z from -4 to 6 (V = 4π); the
two-box compound at (2.5, 0, 0), a third piece. `runtime-cylinder-zero-height`,
`-negative-height` and `-negative-radius` raise `Standard_ConstructionError`
on the oracle and end `runtime` under `cq`: both fail, the row agrees.
`runtime-cylinder-zero-radius` is the one the oracle answers `invalid`: a
zero-volume shape its checker rejects (`oracle.json`, V = 0, bounds the
segment z ±1); `cq` ends it `runtime`, and `verdict.json` classes the row
`by_design` on `docs/ARCHITECTURE.md` §Dialects. `test_cq_cylinder.py`
holds that row, and a property over plane, point, slab and the degenerate
dimensions.

`ok-union-on-empty-chain`, `-tube` and `-yz` call `union` on a workplane
whose chain holds no solid, the first call of every BenchCAD
`t_pipe_fitting` program. Read on the oracle (2026-11-13), CadQuery puts the
given solid on the stack as it stands: a 6 × 2 cylinder (V = 24π); with a
coaxial radius-1 bore cut through it, a tube (V = 18π, A = 42π, genus 1);
an XY cube united on a `YZ` workplane keeps the caller's plane, so
`workplane(offset=1.25)` moves along +x and the unit box there spans x 0.75
to 1.75 (V = 8.75, centroid x 33/280). Each has a recorded oracle report and
an agreeing row in `test_cq.py`, with a property over both planes, offsets,
height and radius. `runtime-cut-on-empty-chain` is `cut` there: CadQuery's
`findSolid` raises, and `cq` ends it `runtime` in the same words.

`ok-three-point-arc-*` call `threePointArc(point1, point2)`, each closed
form in its `note`. `-half-disc-xy` starts on a `moveTo` point and closes
the radius-2 half disc by its diameter (V = 6π). `-from-origin-xz` starts
on an empty stack, at the origin: a radius-5 half disc on a 10 × 2
rectangle drawn by `lineTo` after the arc, extruded -2 toward world +y.
`-stadium-yz` is a stadium as BenchCAD's `dog_bone` draws it: lines, then a
major arc through a far point at each end, the second ending on the start.
`-lens-zx` is two arcs, the second after the first and ending on the start,
extruded -3. `-hemisphere-xy` revolves a quarter disc about +y (V = 2πr³/3).
`-on-slab-xy` draws a unit half disc on `workplane(offset=1)` over a
4 × 4 × 2 slab and fuses its extrusion on (V = 32 + π/2, A = 66 + π).
All six have recorded oracle reports and agreeing rows in
`test_cq_three_point_arc.py`, with a property over a circular segment's
plane, centre, radius, angles and signed height.

`runtime-three-point-arc-on-closed-wire`, `-on-pending-circle`, `-on-solid`
and `-on-compound` call `threePointArc` on each other last object the
subset puts on a stack. Read on the oracle (2026-11-13, `oracle.json`
beside each), CadQuery's `_findFromPoint` raises `RuntimeError` on a wire,
a solid and a compound; `cq` ends each `runtime` too, and the rows agree.
`arris-refusal-three-point-arc-collinear`, `-coincident` and `-full-circle`
draw an arc through three points on one line, through a point equal to its
end, and from a point back to itself: the oracle's `GC_MakeArcOfCircle`
fails (`runtime`), the kernel refuses the profile (`OpProfileError`), and
the rule classes both failing as agreeing. `-near-chord` passes 1e-8 off a
chord of 2: the oracle builds it, the kernel refuses its via point as on
the chord, and the row is `arris_refusal`. A `test_cq_three_point_arc.py`
property draws three points on one line in every admitted plane and gets
the kernel's refusal each time. `unsupported-three-point-arc-point-of-three-numbers`
writes `(1, 1, 0)`: the oracle builds it (the third number is 0, on the
plane), and the subset refuses a point of three numbers as `polyline`'s.

`ok-sphere-*` call `sphere(radius)`, each closed form in its `note`.
`-centred-xy` is a radius-2 sphere on an empty stack (V = 32π/3, A = 16π).
`-at-point-xz` and `-at-point-origin-yz` centre it on a `moveTo` point,
the second with `origin=(1, 2, 3)`: world (3, 0, 1) and (1, 0, 7).
`-transformed-zx` centres it on a `transformed` offset, world (2, 3, 1),
its turn moving only the poles. `-fused-at-point-xy` fuses a radius-1.5
sphere with a 6 × 6 × 2 slab, a cap of height 1 inside it
(V = 72 + 10π/3, A = 120 + 4π). `-capsule` is BenchCAD's
`capsule_000247_s20260505` (BenchCAD/BenchCAD, CC BY 4.0) less its
comments: a cylinder with a sphere of its radius on each end disc, tangent
along the rims, and a belt (V = πr²h + 4πr³/3 + π(R² − r²)t, 7 faces). All
six have recorded oracle reports that meet their closed forms and agreeing
rows in `test_cq_sphere.py`, with a property over plane, origin, offset,
point and radius. `unsupported-workplane-call` moved from `sphere`, now
admitted, to `text`, a CadQuery name the subset still refuses.

`unsupported-sphere-on-solid`, `-on-compound`, `-on-closed-wire`,
`-on-pending-wire` and `-on-pending-circle` call `sphere` on each other
last object the subset puts on a stack, as `unsupported-cylinder-*` do.
Read on the oracle (2026-11-13), CadQuery builds every one, centring the
sphere on the object's `Center()`: the radius-0.5 sphere at the post's
centre of mass (5, 0, 1) lies inside it and leaves the post (V = 2π); on
the two-box compound, a third piece at (2.5, 0, 0); the radius-1 sphere at
the triangle's edge centre (1.293, 0.707), at the segment's (1.5, 1) and at
the circle's centre (3, 1), the circle left unused (V = 4π/3 each).
`runtime-sphere-negative-radius` raises `Standard_ConstructionError` on the
oracle and ends `runtime` under `cq`: the row agrees.
`runtime-sphere-zero-radius` is answered `invalid` by the oracle, a
zero-volume shape at the origin (`oracle.json`); `cq` ends it `runtime`,
and `verdict.json` classes the row `by_design` on `docs/ARCHITECTURE.md`
§Dialects. `test_cq_sphere.py` holds every one, with a property over
plane, point, slab and a radius not positive.

`ok-polygon-*` call `polygon(nSides, diameter)`, each closed form in its
`note`: the n-gon of circumradius r has area (n/2) r² sin(2π/n),
(3√3/2) r² for the hexagon, its first vertex on the plane's +x.
`-centred-xy` is a hexagon on an empty stack; `-at-point-yz` (a pentagon)
and `-at-point-xz` centre it on a `moveTo` point; `-offset-zx` is a
triangle on `workplane(offset=2)` extruded back through the plane;
`-transformed-xy` a square after a 90° `transformed`; `-fused-xy` a hexagon
prism fused onto a slab. `-grease-nipple` is BenchCAD's
`grease_nipple_000156_s20260505` (BenchCAD/BenchCAD, CC BY 4.0) less its
comment: a revolved profile, a hexagon fused across its neck and a bore
(V and the z-moment by Pappus over the profile, 16 faces, genus 1). All
seven have recorded oracle reports that meet their closed forms and
agreeing rows in `test_cq_polygon.py`, with a property over n, diameter,
plane, offset, point and distance.
`-negative-diameter` (2026-11-14) is `polygon(5, -4)`: each vertex turned
by π, the first at (-2, 0), the area and side of `polygon(5, 4)`; x from
-2 to 2 cos 36°, y ±2 sin 72°. Its recorded oracle report meets that closed
form and the row agrees.

`unsupported-polygon-on-solid`, `-on-compound`, `-on-closed-wire`,
`-on-pending-wire` and `-on-pending-circle` call `polygon(6, 1).extrude(1)`
on each other last object the subset puts on a stack, as
`unsupported-sphere-*` do. Read on the oracle (2026-11-14, CadQuery 2.3.0,
OCP 7.9.3.0: `uv run python tools/oracle_run.py --out <scratch>.jsonl`
over these five `program.py`, reports not committed), CadQuery builds a
polygon on each, centred on the object's `Center()`: inside the post at
(5, 0, 1), which it leaves at V = 2π; between the two boxes at (2.5, 0, 0),
a third piece (V = 2 + 3√3/8); at the segment's centre (1.5, 1), the
segment dropped (V = 3√3/8); at the circle's centre, a hexagonal hole in
its disc (V = 9π − 3√3/8); and with the triangle, an `invalid` shape.
`runtime-polygon-float-sides` and `-zero-sides` raise CadQuery's own
`TypeError` and `ZeroDivisionError` on both sides; `-negative-sides`,
`-one-side` and `-zero-diameter` raise `StdFail_NotDone` on the oracle and
`ValueError` under `cq`. Each has its `oracle.json` and the rows agree.
`polygon(2, 4)`, which the oracle answers `ok` with a zero-volume solid and
`cq` ends `runtime`, is a `cq_bug` row, not a fixture here: it is the strict
`xfail` `regression/cq-polygon-two-sides`. `test_cq_polygon.py` holds every
one, with a property over plane, point, slab, sides and diameter.

`ok-extrude-both-*` call `extrude(distance, both=True)`, each closed form in
its `note`: a circle (`-circle-xy`, V = 4π) and a hexagon (`-hexagon-xy`) on
`XY`, a square on `YZ` after `transformed` (`-polygon-yz-transformed`), a
negative distance on `XZ` (`-negative-distance`, the same prism as the
positive one), `both=False` (`-false`, the plain extrusion), the hexagon
prism fused with (`-fused`) and cut through (`-cut`) a 6 × 6 × 2 slab, and
BenchCAD's `hex_key_organizer_000841_s20260506` as written
(`-hex-key-organizer`, CC BY 4.0, three blind hexagonal pockets). Each has
a recorded oracle report that meets its closed form and an agreeing row in
`test_cq_extrude_both.py`, with a property over plane, profile, point,
offset, signed distance and `both`. The oracle keeps a circle's cylinder
as two faces (4 in all, `-circle-xy`) where `cq` builds one: the fidelity
table carries face counts and never judges them (ADR-0005).

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

`ok-circle-circle-ring`, `-larger-second`, `-at-point` and `-revolve` fix a
second `circle` on a stack holding one circle (plans/lift-face-selectors
step 7a): CadQuery centres it on the first wire's centre and builds both
pending wires as a ring, the larger outside whichever was drawn first. V =
16π for radii 3 and 1 and height 2; the revolve (V = 80π², Pappus) is two
tori, two shells. `ok-circle-circle-corpus-impeller` is BenchCAD's
`impeller_006376_s20260505` as written (BenchCAD/BenchCAD, CC BY 4.0): a
disc, a hub, six blades and the ring the second `circle` makes, clear of the
blades, so a second shell; a bore from the hub's top (V and A summed over the
pieces, 40 faces, genus 2). Each has a recorded oracle report and an agreeing
row in `test_cq_circle.py`. The 105 BenchCAD `impeller` programs that ended
`circle` on a non-empty stack ran against the oracle's recorded reports on
2026-11-14: 105 `ok` and agree. `unsupported-circle-circle-same-radius`
(CadQuery's checker calls the shape invalid) and `-circle-circle-circle` (a
third wire inside the ring, invalid on the oracle) are refused, as are
`polyline`, `box` and `union` on the pending ring, which the oracle
accepts: they are refused on a single pending circle too. A radius-0 second
circle is the strict `xfail` `regression/cq-circle-circle-zero-radius`.

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

`ok-extrude-both-closed-path` is a lineTo-drawn right triangle extruded by 1
with `both` (V = 1). `runtime-extrude-zero` and `-zero-both` extrude a
circle by 0: read on the oracle (2026-11-14) the sweep fails with
`Standard_ConstructionError`, and `cq` ends `runtime` in its own words, as
`cylinder` does for a zero height. `runtime-extrude-both-on-empty-stack`,
`-on-solid`, `-on-open-path` and `-on-point` are `both` where no pending
wire is: CadQuery and `cq` both raise `No pending wires present`.
`ok-extrude-both-circle-circle` draws a second circle before the
extrusion: the oracle extrudes both (`ok`, `oracle.json`: an annulus, V = 6 pi),
and so does `cq`, the two circles a ring. `test_cq_extrude_both.py` holds
the failing rows as agreeing, with properties over stacks, planes and
distances.

`ok-polyline-after-moveto-triangle`, `-fused`, `-pentagon-both` and
`-u-bolt-base` read `polyline` after a lone `moveTo` point on the oracle
(2026-11-14): the point is dropped, the polyline starts at its own first
point. The triangle is the 3-4-5 prism (V = 12, A = 36); `-fused` shares a
corner block of 1/8 with a unit cube (V = 12.875, A = 40.5); `-pentagon-both`
is BenchCAD's nut as written, five points closed to the first, so a pentagon
and not the hexagon the `moveTo` point suggests; `-u-bolt-base` is its plate
and two such nuts. Each has a recorded oracle report holding its closed form
and an agreeing row in `test_cq_polyline_after_moveto.py`, with a property
that the `moveTo` point leaves no trace. The oracle answers `invalid` for a
polyline after a drawn path (`moveTo(...).lineTo(...).polyline(...)`) or
after another polyline, so `unsupported-polyline-after-drawn-path` keeps it
refused. The corpus `u_bolt` and `j_hook` programs run as written (bounds
tested in the same file); their volumes wait for step 4's hook closed form,
the oracle's half torus being off by 1e-8 there. The other calls after the
polyline meet the stack `polyline` alone leaves, so none changes.

`ok-faces-box-*`, `-turned-box-*` and `-cylinder-*` select a face with each of
`>X <X >Y <Y >Z <Z` (a cylinder only on its axis: its other selectors tie its
side face with its discs, ADR-0017), put a plane on it with `workplane()` and
stand a triangular prism of circumdiameter 1.5 and height 2 there, at
(0.5, 0.25) of that plane, so the volume-weighted centroid pins the plane's
x and y directions and its projected origin. The turned box is a 4 × 6 × 8 box
at (1, 2, 3) turned 90 degrees about z, so the parent origin is not the world
origin. The cylinders are 6 × radius 2 on `XY`, `YZ` and `XZ`. `ok-faces-bolt-head`
is BenchCAD's `bolt_000037_s20260505` as written (CC BY 4.0): a shaft and a
hexagonal head on its `>Z` face. Each has a recorded oracle report holding its
closed form (`tests/test_cq_faces.py` writes the expectations, with
properties over box and cylinder sizes, planes and origins for the plane
itself) and an agreeing row in the same file. The oracle's face counts equal
the closed form's here (10 for a box, 7 for a cylinder).

`ok-faces-coplanar-tops` is ADR-0017's `coplanar-tops>Z` construction
(`tests/fixtures/selectors/constructed.json`): two boxes fused on a slab, their
tops two faces at z = 1.5 that `faces(">Z")` keeps together, and `workplane()`
their one plane, as in the 40 `connecting_rod` programs; a triangular prism
stands at (-3, 0.25) of it. Its closed form is `coplanar_tops_expected` in
`tests/test_cq_faces.py` (22 faces: arris keeps apart the coplanar side faces
CadQuery's `clean` merges, 18), with a recorded oracle report and an agreeing
row. `runtime-faces-workplane-mixed-surfaces` (a 0.2 × radius 0.1 cylinder's
`>X`: its side and both discs tie) and `runtime-faces-workplane-not-coplanar`
(a small triangular prism turned 30° about x, `>X` keeping two faces whose
normals differ in every component) end in CadQuery's own `ValueError`, each
with a recorded oracle report saying the same. `runtime-faces-cylinder-side`
and `runtime-faces-triangular-prism` are the larger `cylinder>X` and
`box-centre-not-mass>X` constructions as recorded. The cylinder's side and
both discs tie. The prism's two selected side faces tie on x and fail
CadQuery's signed centre check in either order. Both reach the recorded
`ValueError` with the face keys from ADR-0022.
`unsupported-faces-near-tie` is `near-tie-inside>Z` (tops 5e-5 apart,
the oracle's plane at their area-weighted offset).
`unsupported-faces-half-cylinder` turns the recorded `half-cylinder>Z`
construction about x so the selected half cylinder spans the arris seam.
Its two quarter faces rank as one, as the oracle's half cylinder does.
Placing a plane on the curved face ends `unsupported_api`.
`tests/test_cq_faces.py` checks the half cylinder's ranking, centre and area.

`unsupported-edges-unified-face-boundary` selects the positive-y side of
the `slot-split-side>Y` construction, then its edges furthest along x.
The side ranks as one unified face, and its internal seam is excluded.
CadQuery's selected edge is a single cap arc (recorded in `oracle.json`).
arris retains two arcs at that cap, so the selection ends `unsupported_api`.
The face can still supply its two straight edges along the slot, as held by
`tests/test_cq_faces.py`.

`ok-hole-*` are `hole(diameter)` read on the oracle (`tests/test_cq_hole.py`
writes their expectations and holds each against its recorded report):
`ok-hole-box-*` bores a 4 x 6 x 8 box through from each of the six selectors;
`ok-hole-above-the-plane` is `box.workplane().hole(1)`, the plane through the
box's centroid, so the cylinder bores the lower half and the upper half stays;
`ok-hole-post-top-over-the-slab` starts a hole in the air above a slab (the
post's top plane); `ok-hole-in-a-compound` bores one of two disjoint boxes from
the other's top; `ok-hole-wider-than-the-face` is a hole whose cylinder cuts
the box in two pieces; `ok-hole-zero-diameter` leaves the box as it was; and
`ok-hole-corpus-hex-standoff` is BenchCAD's `hex_standoff_000011_s20260507` as
written (CC BY 4.0). `runtime-hole-negative-diameter` and `runtime-hole-no-solid`
end in CadQuery's own errors, each with a recorded report saying so. A hole
that leaves nothing (`hole(10)` on the same box) is an oracle `crash` row, not
a report: its empty result has no bounding box to measure, so no fixture holds
it against the oracle, and `tests/test_cq_hole.py` holds arris's refusal.

Step 6 reads the contexts the bundle admits, each beside its recorded oracle
report (`tests/test_cq_contexts.py` and `tests/test_cq_hole.py` write the
expectations). `ok-faces-compound-*` select across a compound's pieces: `-tops`
the taller piece's top alone (a circle stands in the air over it), `-bottoms`
both pieces' coplanar bottoms, `-coplanar-tops` both tops, which `workplane()`
reads as one plane. `ok-faces-workplane-offset-*` move a face's plane along its
normal: above the top, into the box (flush, so arris keeps one face more than
CadQuery's `clean`), off a `<X` face, and under a hole. `ok-hole-on-*` bore at a
`moveTo` point (through and blind) and, with no `workplane`, at a solid's centre
of mass on `XY` and on `XZ`, whose normal is -y. `runtime-faces-on-*`: `faces` on
a stack that holds no face (CadQuery hands its selector an empty list, even with
a solid higher in the chain). `unsupported-hole-on-*`: CadQuery bores at a
selected face's centre and at a drawn path's, which the subset does not model;
each has CadQuery's report of a part it builds.
`tests/fixtures/regression/cq-hole-tangent-column` is arris's refusal of a cut
tangent to a bore.

`ok-push-points-*` (plans/lift-holes-and-points step 2, `tests/test_cq_push_points.py`)
bore a 4 x 6 x 8 box through at the points `pushPoints` stacks, each beside its
recorded oracle report: one point, several, as lists, an empty list (one bore
at the plane's origin), two points on each of the six faces (in that face's own
x and y, ADR-0017), a third number below the face (a blind bore from there) and
above it (the bore starts in the air and ends inside, a diagonal long), a point
off the part (the box unchanged) and `dog_bone_000282_s20260505` as the corpus
writes it. `unsupported-*` programs for the points and stacks the subset
refuses are held in `tests/test_cq_push_points.py` as calls, not as fixtures.

`ok-hole-depth-*` (step 3, the same test file) bore `hole(1, depth=)`: blind from
the top at one point, at several, at the plane's origin and `0.25` deep; a depth
of the box's thickness and one past it, which leave it as `hole(1)` does; and
`hex_standoff_001194_s20260505` as the corpus writes it, a blind bore from a
hexagonal prism's bottom under a stud. `runtime-hole-depth-*`: a depth of 0 and
of -1 (CadQuery's `Standard_ConstructionError`, the zero one from
`gp_Vec::Normalize()`), raised before a zero diameter would cut nothing, and a
negative diameter with a depth; each has its recorded oracle report.

`ok-cbore-*` (step 4, `tests/test_cq_cbore.py`) counterbore a 10 x 8 x 4 box
from its top face, each beside its recorded oracle report: one point, several,
none (the plane's origin), a counterbore deeper than the part and one exactly
as deep (a through hole of the counterbore's width), a counterbore narrower than
the bore and one of its width (the bore alone), a zero bore (the counterbore
alone, blind) and a zero counterbore, and a manifold block's row of three
counterbores as `manifold_block_000049_s20260505` writes it less its other
holes: that program also writes `faces(">Z").faces(">Z")`, a context step 6
lifts, with its holes along y that cross these bores. `runtime-cbore-*`: the
arguments CadQuery refuses, its words recorded beside ours.

`ok-csk-*` (step 5, `tests/test_cq_csk.py`) countersink the same box from its top
face, each beside its recorded oracle report: one point at 82 and at 90 degrees,
several, none (the plane's origin), a wide angle (170), a cone no wider than the
bore and one of its width (the bore alone), a zero bore (the cone alone, blind,
ending in its tip), a cone whose frustum has not met the bore at the far face
(the cone alone, through), and the plate of `hinge_000040_s20260506` as the
corpus writes it up to its first `union`: that union touches a cylinder to the
plate's side, which arris refuses (`regression/cq-tangent-cylinder-and-box`).
`runtime-csk-*`: the arguments CadQuery refuses (a negative diameter, an angle of
zero, a zero or negative countersink diameter, an angle of 180 and one below
zero, and the range's ends, 360 and -180), its words recorded beside ours.
`unsupported-csk-*`: an angle past either end (400, -200), where the oracle
builds the countersink of the angle 360 degrees nearer (40, 160), its report
beside ours (ADR-0018's amendment).

`ok-ctx-faces-on-faces-*` (step 6, `tests/test_cq_point_contexts.py`) run a second
`faces` on the faces the first kept, each beside its recorded oracle report: the
same selector, the opposite one and one along another axis on a box (the one
face stays, so the hole is the one `ok-hole-box-*` bores), and on a pair of
boxes `>X` then `<Z` (B's end face alone, so a bore along x through both).
`ok-ctx-circle-points-*` draw a circle at each of a stack of points and `extrude`:
posts on a box's top face (one point, several, `both=True`) and posts of
`cq.Workplane("XY")` alone, two solids that do not meet. `ok-ctx-cbore-in-a-compound`
and `ok-ctx-csk-in-a-compound` bore the pair's first box from the top plane;
`ok-ctx-cbore-after-a-hole` and `ok-ctx-csk-after-a-hole` call them on the stack a
`hole` left, which bores at the solid's centroid in the middle plane (a cavity
that leaves by the bottom face). The calls the subset refuses in these
contexts (overlapping or touching circles, a duplicate point, a point with an
offset, a ring of circles at points, a hole or a revolve on the circles) are held
in the test file as calls; four are fixtures, each beside the oracle's report:
`unsupported-circle-points-overlapping` and `-duplicate` (a shape its checker
calls invalid), `-offset` (`runtime`, its wires not planar) and `-ring` (it
builds a ring at each point). `manifold_block_000049_s20260505`
as written ends `ok` on both sides with every measure equal but volume and area
(1.1e-8 and 2.9e-8 relative, over the 1e-9 tolerance): its volume by
quadrature over x (the cross-section is a rectangle less rectangles) is
80766.0861318698, arris's 80766.0861318263 and the oracle's 80766.0852197574,
Open CASCADE's cylinder-cylinder section again. It has no fixture here:
`compare` needs a closed form of all four figures to class it, which step 7's
diagnosis writes.

`ok-rarray-*` (plans/lift-arrays-and-blind-cuts step 2, `tests/test_cq_rarray.py`)
put a grid of bores or posts on a box's face with `rarray`: a 1 x 1 grid, 3 x 2 on
`>Z`, 2 x 2 on `>X`, 3 x 2 on `<Y` and posts of `circle(1).extrude(1)` at 2 x 2, and
a BenchCAD `vented_panel` as written (nine holes on an `XZ` box's `>Y`), each beside
the oracle's recorded report and held to the closed form of how it is built.
`runtime-rarray-*` are the values CadQuery refuses (a spacing of zero or less, a count
of zero, a float count), its words verbatim; `unsupported-rarray-center` is the
`center=` keyword no corpus program writes, which the oracle builds.

`ok-polar-array-*` (plans/lift-arrays-and-blind-cuts step 3, `tests/test_cq_polar_array.py`)
bore a box's `>Z` and `>X` faces, a revolved cylinder's `<Y` end and BenchCAD's
`motor_end_cap` (as written: a bore, then six holes) at the points of a `polarArray`:
a full turn of either sign, from a start angle, a partial turn of either sign, one point
(at the start angle), a negative radius and a zero one (three bores at the centre, one
hole); `circle(0.5).extrude(1)` at a full turn of four draws a post at each. Each is
beside the oracle's recorded report and held to the closed form of how it is built.
`runtime-polar-array-*` are the counts CadQuery refuses (zero, negative, a float), its
words verbatim; `unsupported-polar-array-*` are the `fill=` and `rotate=` keywords no
corpus program writes, which the oracle builds.

`ok-cut-blind-*` (plans/lift-arrays-and-blind-cuts step 4, `tests/test_cq_cut_blind.py`)
cut a circle, a ring or circles at points from a box and from a revolved cylinder
and flange: a pocket, a hole through, a depth past the part, a positive depth (the
box unchanged), a plane inside the part (a pocket from below the face, a closed
void of two shells), the tool's wall on the part's (a slab off the end) and six
tools through a flange flush at both ends, each beside the oracle's recorded report
and held to the closed form of how it is built. `ok-cut-blind-corpus-spur-gear`
(a groove and a bore in a 196-sided gear outline) and `ok-cut-blind-corpus-bellows`
(twelve holes in a revolved bellows) are BenchCAD's programs as written, their
`program.py` a row of the committed census, the closed forms the polygon's shoelace
sums and Pappus's rule (the bellows' top holes cut a sliver under the rim, a
quadrature). The oracle agrees with the gear. On the bellows arris is on the closed
form to 1e-9 and Open CASCADE's recorded report is not (volume 1.3e-7 high, area
2.3e-7 low, a centroid 4e-6 off the axis, 26 faces for 28): `occt_wrong` by that closed
form, held in `test_cq_cut_blind.py`, so the fixture is not asserted to agree.
`runtime-cut-blind-*` are the refusals, in CadQuery's order (no pending circle, a zero
depth, no solid), and `unsupported-cut-blind-*` the `clean=` keyword and a string depth.

`ok-ctx-*` of plans/lift-arrays-and-blind-cuts step 5 (`tests/test_cq_array_contexts.py`),
each beside the oracle's recorded report and held to the closed form of how it is built:
`ok-ctx-polar-array-in-a-compound` and `ok-ctx-rarray-in-a-compound` bore four holes in
the pair's first box from `faces(">Z").workplane()` (`t_pipe_fitting` writes both on a
compound); `ok-ctx-hole-after-a-blind-cut-biting` and `-revolved` call `faces(...).workplane()`
again after a pocket and bore a ring of holes, those of the first biting into the pocket (the
overlap is the circles' lens), as `dome_cap` does on a dome that is itself the known
spindle-torus refusal; `ok-ctx-cut-blind-from-a-higher-face` takes `impeller`'s shape (a ring
above a hub, a pocket from the ring's top that clears only the hub); and
`ok-ctx-union-after-a-cut-blind-corpus-spur-gear` is `spur_gear_017922_s20260505` as written,
a pocket filled by a united cylinder, a groove it leaves, a bore: a row of the committed
census, the oracle agreeing. Of the corpus's contexts, read on the committed oracle rows: all 161 in-subset `impeller` and
36 of 38 in-subset `spur_gear` programs agree; the two that do not are the refusal of
`regression/cq-cut-blind-after-a-filled-pocket`. Of the 202 in-subset `bellows`, 135 write no
`cutBlind` and agree, 42 end `arris_refusal` (`regression/cq-cut-blind-across-a-split-end-face`)
and 25 differ by Open CASCADE's error as `ok-cut-blind-corpus-bellows` does (volume up to 2e-6).
The 77 new `t_pipe_fitting` rows differ by the tee's own Open CASCADE error (volume up to 1e-4,
as its 64 older rows), which step 6 classes. All 87 in-subset `dome_cap` end in the known
spindle-torus refusal.

`runtime-edges-*` and `unsupported-edges-*` of plans/lift-edges-and-blends step 2
(`tests/test_cq_edges.py`, which also holds step 3's `|X |Y |Z` and `'>Z or <Z'` on a box, a
cylinder and a drilled plate), each beside the oracle's recorded report: `edges(">Z")` on an
empty stack is CadQuery's `ValueError` for an empty selection, and the oracle builds what
`cq` refuses: a revolved wall's `>X`, where its seam, which no record places, may tie the rims
(ADR-0020 rule 2 and its amendment), the
type selector `%LINE`, and a `box` on a stack of edges (rule 6). A program that ends in
edges has no `ok-` fixture: the oracle reports a bare edge as a shape of volume 0 and
`cq` a result holding no solid, so what `edges` keeps is held on the stack in
`tests/test_cq_edges.py` and by the part a blend makes of it (`ok-fillet-*`, step 4).

`ok-fillet-*` of plans/lift-edges-and-blends step 4 (`tests/test_cq_fillet.py`), each beside the
oracle's recorded report and held to the closed form of how it is built (a section swept
along each run of edges, mitred at a box's corners, by Pappus; `test_edge_probe.PARTS`): a box's
top edges, its vertical edges, one edge, the top face's edges, every edge of the solid, a
cylinder's rim and its `edges()` (the seam passed over), a plate's top with its hole, a tube's
two rims, two cubes that do not meet (a compound), and a second blend along the edges an earlier
one made. `ok-fillet-corpus-washer` is `washer_000042_s20260505` as written: a row of the
committed census, both rims of a ring rounded. `runtime-fillet-*` are CadQuery's refusals
(no solid, no edge, a stack of seams alone) and `arris-refusal-fillet-*` the values Open CASCADE
refuses with `StdFail_NotDone` (zero, negative, past the faces) and arris with its own words:
both fail, a row that agrees.

`ok-chamfer-*` of plans/lift-edges-and-blends step 5 (`tests/test_cq_chamfer.py`), each beside the
oracle's recorded report and held to the closed form of how it is built (a triangle swept
along each run of edges, mitred at a box's corners, by Pappus; `test_edge_probe.PARTS`): a box's
top and vertical edges, a cylinder's rim, both rims (`'>Z or <Z'`) and `edges()` (the seam
passed over), a plate's top with its hole, a tube's two rims, two cubes that do not meet (a
compound) and a chamfer along the edges a fillet made. `ok-chamfer-corpus-dowel-pin` is
`dowel_pin_000027_s20260505` as written, by closed form; `ok-chamfer-corpus-handwheel` is
`handwheel_000006_s20260506` as written, its volume, area, centroid and bounds the oracle's
recorded report (no closed form is at hand; its face kinds, shells and genus are `cq`'s, the face count held
to the report's), and `cq` agrees with that report. `ok-chamfer-corpus-clevis-pin` (a pin along y,
`unsupported-chamfer-corpus-clevis-pin-seam` until plans/lift-edges-and-blends step 7a),
`ok-chamfer-corpus-washer` and `ok-chamfer-corpus-spacer-ring` (a washer and a swept ring along x,
each with a bore) are `clevis_pin_000171_s20260505`, `washer_000024_s20260505` and
`spacer_ring_001337_s20260505` as written (BenchCAD/BenchCAD, CC BY 4.0), by closed form:
`'>Z or <Z'` ranks each seam, placed where Open CASCADE puts it, at the height of the axis, tied
with the rims (ADR-0020's amendment). `runtime-chamfer-*` are CadQuery's refusals
and `arris-refusal-chamfer-*` the lengths Open CASCADE refuses with `StdFail_NotDone` and arris
with its own words: both fail, a row that agrees.

`ok-blend-corpus-stepped-shaft` and `ok-blend-corpus-gridfinity-bin` of
plans/lift-edges-and-blends step 6 (`tests/test_cq_blend_contexts.py`): BenchCAD's
`stepped_shaft_000048_s20260505` as written (four stacked cylinders, `faces(">Z").chamfer`
bevelling a face's one rim, a hole along the axis) and `gridfinity_bin_000166_s20260505` as written
(a fillet before a cut and a union, the rib joined against a wall), each held to its closed form
and agreeing with the oracle's recorded report. The `ball_knob` blend (`faces("<Z").edges()`
after a sphere and a stem touching at a point) is `regression/cq-ball-knob-chamfer-after-point-contact`,
waiting on arris's union; the handwheel (blends after unions and cuts) is `ok-chamfer-corpus-handwheel`.

`ok-thin-band-top-face` and `ok-sprocket-corpus-along-x`, `-along-z` of plans/lift-edges-and-blends
step 7b (ADR-0017's 2026-11-15 amendment): `faces(">Z")` where a cylinder's side shows 0.005 above
a box, a thin band whose centre is 0.0025 under the kept disc (a box and a cylinder, closed form by
construction, agreeing with the oracle's recorded report), and BenchCAD's
`double_simplex_sprocket_016264_s20260505` and `double_simplex_sprocket_017919_s20260505` as written
(BenchCAD/BenchCAD, CC BY 4.0: a hub between two chamfered tooth plates, `faces(">X")` and
`faces(">Z")` on the hub's end, then a bore), held to the closed form of `tools/cq_closed_forms.py`
(`sprocket_measures`; the plate polygon's mitred chamfer, arris within 1e-10 of it). Each beside the
oracle's recorded report and a `verdict.json`: the oracle's chamfer on the tooth outline takes less
than the mitre does (its volume 0.1% over the closed form), so the row is `occt_wrong` by that
closed form. arris carries one face more than the oracle (the plate's bottom flat and the hub's
coplanar bottom disc stay two), ADR-0005's convention.


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

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

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

# fidelity fixtures

`agree-*/` is the calibration set of ADR-0005: one part built twice, as an
`arris` program (`program.py`) and as CadQuery text (`oracle.py`).
`expected.json` is the part's closed form, worked out from how it is built
(never from either kernel's output; `note` says how), `oracle.json` the oracle's recorded
report, made by `tools/oracle_run.py` on `oracle.py`
(`uv run tools/oracle_run.py --out ... tests/fixtures/fidelity/agree-*/oracle.py`,
each row's `report` less `seconds`). The gate runs arris and reads the record;
`tests/test_fidelity_calibration.py` holds both to the closed form and to each
other. A re-record that changes a figure is a change of the oracle and says so
in the commit.

| Fixture | Closed form |
|---|---|
| `agree-box-blind-hole` | V = 1000 - pi 4 6; A = 600 - 4 pi + 2 pi 2 6 + 4 pi; the hole's centroid is at z = 7 |
| `agree-box-minus-notch` | V = 1000 - 4*4*10; A = 600 - 2*16 - 2*40 + 2*40; centroid (5000 - 160*8)/840 |
| `agree-box-offset` | 5*3*6; 2(15+30+18) |
| `agree-box-through-hole` | V = 1000 - pi 4 10; A = 600 - 2 pi 4 + 2 pi 2 10 |
| `agree-box-two-holes` | V = 1000 - 2 pi 5; A = 700 - 4 pi + 2 (2 pi 5); symmetric about x = 10 |
| `agree-box` | V = 2*3*4; A = 2(2*3+2*4+3*4) |
| `agree-chamfer-one-edge` | box 6 x 4 x 3, d 1 on the top edge along y at x = 0: V = 72 - 1/2 * 4; A = 108 - 2*4 - 2 (1/2) + 4 sqrt2 (the two end faces lose the corner too); removed triangle of area 1/2 has its centroid 1/3 from the corner |
| `agree-chamfer-top-ring` | d 1 on the four top edges: removed volume int_0^1 (100 - (8 + 2t)^2) dt = 20 - 4/3; A = 64 + 4 (9 sqrt2) + 360 + 100; z from the moment 10 (20 - 4/3) - 19/3 removed |
| `agree-cylinder-offset` | V = pi 4 5; A = 2 pi 2 (2+5) |
| `agree-cylinder` | V = pi r^2 h; A = 2 pi r (r+h) |
| `agree-fillet-one-edge` | box 6 x 4 x 3, an r 1 fillet on the top edge along y at x = 0: V = 72 - 4 (1 - pi/4); A = 108 - 2*4 - 2 (1 - pi/4) + (pi/2) 4 (the two end faces lose the corner too); centroid from the removed corner, area 1 - pi/4 at ((5/6 - pi/4)/(1 - pi/4)) from the corner in x and in z |
| `agree-fillet-vertical-edges` | four r 2 fillets of length 10 each remove (4 - pi) 10; A = 2 (100 - 4 (4 - pi)) + 10 (4 (10 - 4) + 2 pi 2) |
| `agree-hexagon-prism` | regular hexagon of circumradius 2: area 6 sqrt3, perimeter 12; V = 3 * 6 sqrt3; A = 2 * 6 sqrt3 + 12 * 3 |
| `agree-l-prism-fuse` | an L of area 12 and perimeter 16, 2 thick: V = 24; A = 2*12 + 16*2; centroid from 8 at (2,1) and 4 at (1,3) |
| `agree-revolve-frustum` | frustum r1 2, r2 1, h 3: V = pi h/3 (r1^2 + r1 r2 + r2^2); A = pi (r1^2 + r2^2) + pi (r1 + r2) sqrt(h^2 + (r1-r2)^2); z = h (r1^2 + 2 r1 r2 + 3 r2^2) / (4 (r1^2 + r1 r2 + r2^2)) |
| `agree-revolve-sphere` | sphere r 2: V = 4/3 pi r^3; A = 4 pi r^2 |
| `agree-revolve-torus` | torus R 3, r 1: V = 2 pi^2 R r^2; A = 4 pi^2 R r |
| `agree-revolve-washer` | Pappus: V = pi (9-1) 2; A = 2 pi (1*2 + 3*2) + 2 pi (9-1) |
| `agree-tube` | V = pi (9-1) 4; A = 2 pi 3 4 + 2 pi 1 4 + 2 pi (9-1) |

`class-*/` are the planted fixtures of ADR-0006: an `arris` program
(`program.py`), a planted `oracle.json` written by hand (what the oracle would
report, its `program_sha256` that of `program.py`; never recorded), a
`verdict.json` where the rule needs one, and `expected.json`, the row ADR-0006's
table gives. `tests/test_fidelity_compare.py` runs the program and compares.

| Fixture | arris | Oracle (planted) | Row |
|---|---|---|---|
| `class-cq-bug` | `runtime` (`AttributeError`) | `ok` | `cq_bug` |
| `class-arris-refusal` | `arris_refusal` (`OpDegenerateError`, a fillet of 10 on a 3-high box) | `ok` | `arris_refusal` |
| `class-arris-bug` | `crash` (`os._exit(3)`) | `ok` | `arris_bug` |
| `class-occt-wrong` | `ok`, the 2 x 3 x 4 box | `ok`, volume 25 | `occt_wrong` by its closed form, 24 |
| `class-by-design` | `ok` | `no_result` | `by_design` by its anchor |
| `class-both-fail-agree` | `syntax` | `syntax` | agree |
| `class-unclassified-gap` | `ok`, the box | `ok`, volume 24.5, no verdict | unclassified |
| `class-timeout` | `ok` | `timeout` | unclassified, timed out |

`table-expected.json`, `arris-report-expected.json` and `arris-report-expected.md`
are the `FidelityTable` counts and the arris report that all of the above make
(the 19 `agree-*` pairs plus the 8 `class-*`), worked out by counting the two
tables here: 27 programs, 20 agree, 5 disagree (one per class), 2 unclassified.
`tests/test_fidelity_table.py` holds the table and `arris_rows` to them. The
refusal's words are the kernel's, as `class-arris-refusal` draws them.

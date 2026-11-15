# Plan: lift-edges-and-blends

- Started: 2026-11-15
- Milestone: C2, subset growth (docs/ROADMAP.md §C2), bundle 3 of the knee
  (ADR-0014's 2026-11-14 amendment)
- Idea: none; verbatim from the human: "bundle 3"

## Goal

`dialect="cq"` runs `edges()`, `edges(str)` with the six axis selectors, the
parallel selectors `|X`, `|Y`, `|Z` and `'>Z or <Z'`, and `fillet(num)` and
`chamfer(num)`, as CadQuery 2.3.0 builds them: an edge selection is a stack of
edges of the chain's solid, and a blend rounds or bevels the edges on the
stack (or every edge of the stacked faces or solid) in one call. `cq.subset()`
declares the four forms and four selectors. Measured at planning time against
today's subset (`programs.jsonl.gz`, `_eligible` and `_missing_forms`),
BenchCAD reach goes from 6,565 to 9,998 of 17,900 (+3,433: `chamfer` with
`edges(str)` 1,587, the same with `'>Z or <Z'` 391, `chamfer` alone 327,
`fillet` with `edges(str)` 233 …; 41 families, `handwheel` 201,
`clevis_pin` 178, `dowel_pin` 177, `gridfinity_bin` 164 leading). CAD-Recode
writes none of them and stays at 104 of 968. ADR-0020 decides the edge keys,
the parallel and `or` selectors and the blend over arris. Both tables are
re-run with the oracle's committed rows and committed, nothing unclassified
in the subset.

## Non-goals

- `faces("XY")`, `faces("YZ")`, `faces("XZ")` (332 programs, `circlip` 182 and
  `snap_clip` 150, all unlocked if added here): CadQuery's `DirectionSelector`
  on a diagonal, not one of the knee's 35 items; a backlog line.
- `faces` with `|X|Y|Z` or `'>Z or <Z'`: no corpus program writes them, so they
  stay `unsupported_api` (the four selectors are declared once for both
  methods, ADR-0012; step 7 counts the `cq_bug` rows, forecast none).
  `vertices`, `chamfer(num, num)`, blend keywords, `and`/`not`/`#` selectors.
- The 1,950 + 1,688 + 823 programs that also need `rect`, `cutThruAll` or
  `center` (bundle 5), `shell` and the tail. Bundle 4; arris code (a needed
  capability is asked of arris, `../arris/docs/ideas/`).

## Design deltas

- **What the 3,433 write** (corpus text read at planning time, not run):
  `edges(sel)` after a solid or after `faces(sel)`, then `fillet(r)` or
  `chamfer(d)` and usually nothing, `faces(sel)` or `union`. Edge selectors:
  `>Z` 1,474, `>X` 1,026, bare `edges()` 873, `>Y` 806, `|Y` 568, `<Z` 554,
  `|Z` 547, `|X` 509, `'>Z or <Z'` 468, `<Y` 344, `<X` 323.
- **`Workplane.edges(selector=None)`**, `census_form` `[]` and `[("str",)]`:
  a new stack object `Edges(solid, edges)` in `_selector.py`, beside `Faces`.
  The edges of the stack's solid or of its `Faces` (deduplicated in first-seen
  order, as CadQuery's `_collectProperty`), filtered by the selector.
- **Edge key** (ADR-0020, step 1): CadQuery's `DirectionMinMaxSelector` on an
  edge ranks its `Center()`, the centre of mass. Exact for a line (its
  midpoint), a circle (its centre) and an arc (centre plus `r·sin(θ/2)/(θ/2)`
  along the bisector); an ellipse or NURBS edge is estimated and held to
  ADR-0017 rule 2's margin, or settled by its box, else `unsupported_api`.
  Clusters and `CQ_TOLERANCE` as ADR-0017 rule 1. *Settled* (step 1,
  ADR-0020 rules 1 and 2): an arc runs counter-clockwise about its axis from
  start to end, end to start on a reversed edge; a seam's key is exact only
  where its face's axis is along the selector's, else bounded by its face's
  box (arris and Open CASCADE put a bored hole's seam on opposite sides); a
  kept cluster holding an estimated edge ends `unsupported_api` (the kernels
  cut a B-spline curve into different edges); a `degenerate` edge is no
  candidate.
- **`|X|Y|Z`**: CadQuery's `ParallelDirSelector` keeps the line edges whose
  direction crosses the axis within `CQ_TOLERANCE`; a circle, arc or NURBS
  edge is never kept. **`'>Z or <Z'`**: the union of both selections; its
  order (CadQuery takes a `set`) reaches only a blend, which is order-free, so
  `cq` keeps the kernel's edge order. *Settled* (step 1, ADR-0020 rule 6):
  only `edges`, `fillet` and `chamfer` read a stack of edges; every other
  call on one ends `unsupported_api`.
- **`Workplane.fillet(radius)`, `chamfer(length)`**, `[("num",)]`: the chain's
  solid (`findSolid`: the stack's, else the nearest parent's) blended at the
  stack's edges, or every edge of the stacked faces or solid, in one
  `Solid.fillet` / `Solid.chamfer`. What step 1 decides: a seam edge in the
  list (arris refuses it, `OpDegenerateError` "tangent dihedral"; Open
  CASCADE's handling read on the oracle), `clean()` after the blend (face
  counts only, or measures too), the values CadQuery refuses, and a blend on
  a compound (ADR-0016). *Settled* (step 1, ADR-0020 rule 5): no solid, then
  no edges, raise CadQuery's `ValueError`s (`runtime`); seams are dropped, and
  seams alone raise a `ValueError` naming Open CASCADE's `Standard_Failure`;
  the value goes to arris as written, so 0, a negative and a value past the
  edge's faces are `arris_refusal` (CadQuery raises `StdFail_NotDone`: both
  fail); no `clean()`; a compound is blended as one body.
- **ADR-0020** (step 1); `SELECTORS` gains the four strings; `subset()`'s
  doctest and ARCHITECTURE §Dialects' "26 API forms" move to 30.
- **Unsupported-example hits** (grep of `tests/`, `src/`, `docs/`):
  `tests/test_cq.py:143` (`edges` among the names outside the subset: replaced
  by `vertices` in step 2); `tests/test_cq.py:898` and
  `tests/test_cq_faces.py:296-297` (`faces("|Z")`, `faces(">Z or <Z")`: still
  `unsupported_api` by the non-goal, kept); ARCHITECTURE §Dialects ("`chamfer`
  … wait for their bundle"); `tests/test_cq_calibration.py`'s four blend
  calibration programs stay out by their bare `cq.Workplane()`.
- `GLOSSARY.md` **Stack**: `edges` puts a stack of edges, which `fillet` and
  `chamfer` take; **Edge key** is new (a selector's rank of an edge, ADR-0020).

## Steps

Grades are tiers (`.agents/tiers.md`): **[1]** routine; **[2]** careful
within a given design; **[3]** unproven semantics, established here.

- [x] Step 1 **[3]** — ADR-0020 from CadQuery's source and the oracle, the
  kernel risk first: a spike that blends the leading families' shapes in arris
  against closed forms (a box's top edges, its vertical edges, all twelve; a
  cylinder's rims; a hole's rim; a fillet next to a chamfer at one vertex; a
  radius past an edge's faces). A probe `tools/cq_edge_probe.py`, its reports
  under `tests/fixtures/edges/`, each held to a closed form or CadQuery's
  words: edge keys on lines, circles, arcs and a NURBS edge; `|Z` on a
  cylinder (its seam); `'>Z or <Z'`; `edges()` on faces; a blend with a seam,
  on a compound, of radius 0 and negative, with no solid, and `clean()`.
- [x] Step 2 **[2]** — `edges()` and `edges(str)` with the axis selectors
  (the edge key): `cq/ok-edges-*` with each kept edge's count and curve kind,
  `unsupported-` for an estimate inside the margin; `hypothesis`: a random box
  and selector keeps the four edges of the face the closed form names.
- [x] Step 3 **[2]** — `|X|Y|Z` and `'>Z or <Z'`: fixtures on a box, a
  cylinder and a drilled plate; `hypothesis`: on a random box, `|Z` keeps four
  lines and `'>Z or <Z'` eight.
- [x] Step 4 **[2]** — `fillet(num)` per ADR-0020: `cq/ok-fillet-*` (a box's
  edge, its vertical edges, a cylinder rim) with closed-form volume, area and
  centroid, `runtime-` and `arris-refusal-` for the refused values, one
  `handwheel` as written; `hypothesis`: a box with its four `|Z` edges filleted
  at a random radius, `V − (4 − π) r² h`.
- [x] Step 5 **[2]** — `chamfer(num)`: `cq/ok-chamfer-*` (a box's top edges, a
  cylinder rim, a hole's rim), refused values, one `clevis_pin` and one
  `dowel_pin` as written; `hypothesis`: a cylinder's rim chamfered by `d`,
  `V − π d²(r − d/3)`.
- [x] Step 6 **[2]** — the corpus contexts, read on the oracle: a blend after
  `faces(sel)` then `edges()` (`ball_knob`), after a `union` or `cut` (a
  compound), `'>Z or <Z'` on a turned part (`stepped_shaft`), `gridfinity_bin`
  and `handwheel`; lifted where they agree, else refused, each with its `ok-`,
  `runtime-` or `unsupported-` fixture; a new arris refusal is an xfail
  `regression/` fixture and an ask in `../arris/docs/ideas/`.
- [ ] Step 7 **[2, conductor-run]** — the measurement: `cq_corpus.py
  --oracle-rows` on both corpora into a scratch out-dir, then `cq_diagnose.py`;
  in-subset rows by class, `cq_bug` and unclassified by family, recorded
  here. Each cause becomes a step 7a, 7b … before step 8, largest first,
  shrunk to `regression/` fixtures and filed with arris where the kernel is at
  fault, or classed by a closed form (`tools/cq_closed_forms.py`).
- [x] Step 7a **[3]** — BenchCAD's measurement (2026-11-15, scratch out-dir): reach
  9,998/17,900 as forecast; 7,222 agree, 10,178 disagree, 500 unclassified; in-subset
  `cq_bug` **300**, not 7. 275 are `edges('>Z')` ended `unsupported_api` by ADR-0020 rule 2
  (the seam's key bound): `dowel_pin` 122, `clevis_pin` 112, `washer` 27, `spacer_ring` 14.
  Narrow rule 2 so these run (a cylinder's seam key from its axis and the face's box; the
  oracle and closed forms say which edge `>Z` keeps), or, where the key truly cannot be
  decided, refuse by a declared form so the program is out of the subset, never a `cq_bug`;
  each shrunk to a fixture, ADR-0020 amended.
- [x] Step 7c **[2]** — the 84 rows step 7a's lift makes unclassified, every one `ok` on both
  sides with the blend agreeing: 81 `clevis_pin` with a cross hole cut after the chamfer (volume
  up to 2.2e-5, bounds up to 0.005: the crossing cylinders, as `clevis_pin_000420_s20260505` of
  step 5) and 3 `spacer_ring` with a box cut after the blend (`008375`: bounds 0.037 and 2 faces;
  `012675`: volume 1.3e-6, 3 faces; `016757`: bounds 2e-7). Class each by a closed form
  (`tools/cq_closed_forms.py`) or shrink it to a `regression/` fixture.
- [x] Step 7b **[2]** — the other 25 in-subset `cq_bug`: 18 `double_simplex_sprocket`
  `faces('>X')`/`faces('>Z')` ("the centre of a face that arris does not give"), 7
  `connecting_rod` (ADR-0014's amendment, expected). Class the sprocket rows: new in the
  subset by this lift, so a fixture each and either a lift or a declared refusal.
- [x] Step 7d **[2]** — the full re-run on the final code (scratch, 2026-11-15) reaches
  9,998/17,900, in-subset `cq_bug` 6 (`connecting_rod`), 603 unclassified; `cq_closed_forms.py`
  then stops with `ValueError: a sprocket outside the arrangement the closed form handles`:
  a `double_simplex_sprocket` beyond the 18 of step 7b now runs `ok` (the finer `faces` pass).
  Find which, and class every such row: widen the closed form where it is exact, else an
  xfail `regression/` fixture, else (kernel at fault) an arris ask. No row dropped; the tool
  must not crash on one it cannot class (it leaves it unclassified, counted). Done when
  `cq_closed_forms.py` over the scratch table
  (`.../scratchpad/c2b2/fidelity.json.gz`, oracle rows `.../c2b/oracle.jsonl.gz`) with step
  7c's flags writes verdicts and no in-subset row is unclassified.
  *Done* (step 7d): the sprocket crash was a plate ending 0.01 inside the hub's length and the
  `XZ` plane (axis -y), both now in `sprocket_measures`; a row whose closed form refuses its
  program is left unclassified and named on stderr. The blend lifts newly ran 143 in-subset
  unclassified rows, each now `occt_wrong` by a closed form, arris within 1e-11 of it:
  `sprocket_*` (82, `plate_measures`), `pan_head_screw_*` (29, `screw_closed_form`) and
  `manifold_block_*` (16: the box's top edges chamfered, with counterbores and a hole centred
  on the chamfered edges). `part_measures` reads that box as a `Bevel` (its half-spaces and the
  four chamfer planes, each holding a line along an axis, so its faces are read like the rest
  and every feature on the rim is exact interval arithmetic); Open CASCADE is 1e-9 to 6e-8 off
  in volume or area. The run over the scratch table with step 7c's flags writes 1,152
  verdicts, each checked by `compare`, and leaves 0 in-subset rows unclassified.
- [ ] Step 8 **[1, conductor-run]** — the committed re-run of both tables
  (`tests/fixtures/c2/*`, the READMEs' figures and digests), the baseline
  subset helper step 2 adds deleted as in plans/lift-arrays-and-blind-cuts.

## Acceptance

- `uv run tools/gate.sh` green with steps 2 to 6's fixtures, the `hypothesis`
  properties of steps 2 to 5, and step 1's probe test.
- Committed tables: BenchCAD reach 9,998/17,900 (or the step-7 figure, with
  its reason, if a declaration had to narrow), CAD-Recode 104/968;
  `in_subset_cq_bug` 0 on CAD-Recode and 7 on BenchCAD (ADR-0014's
  amendment, the `connecting_rod` rows; none new), `in_subset_by_design` 0
  and no in-subset row unclassified on both; each new `arris_bug` row a
  `regression/` fixture.

## Docs to update on completion

- `docs/ARCHITECTURE.md` §Dialects (30 forms; the edges and blends paragraph)
  and §Fidelity (the C2 table and this lift's paragraph).
- `docs/ROADMAP.md` §C2 status and next bundle; `AGENTS.md` current state.
- `GLOSSARY.md` **Stack**, **Edge key** (above).
- `CHANGELOG.md` `Unreleased`: the forms, selectors and refusals a consumer sees.
- `PROVENANCE.md`: `edges`, `fillet`, `chamfer`, `ParallelDirSelector`,
  `OrSelector` read from CadQuery's source.
- `docs/BACKLOG.md`: `faces` with a plane name (332 programs, above).

## Open questions

- *Settled* (step 1): a seam edge in a blend's list. Open CASCADE passes over
  it (`fillet-cylinder-edges` blends both rims) and raises `Standard_Failure`
  for seams alone, so `cq` drops edges whose two sides are one face before
  the call (ADR-0020 rule 5).
- *Settled* (step 1): CadQuery's `clean()` after `fillet` moved no measure
  and no face count, bit for bit, on four constructions (`unclean-*`), so `cq`
  writes no `clean`.
- *Settled* (step 2): `cq/ok-edges-*` fixtures cannot exist: a program that
  ends in edges is `ok` with volume 0 on the oracle and `runtime` ("holding no
  solid") in `cq`, as for any non-solid result. What each selector keeps (count,
  curve kind, centre) is held on the stack in `tests/test_cq_edges.py`, each kept
  edge to its closed form, and by `ok-fillet-*` and `ok-chamfer-*` through the part
  a blend makes of it; step 2's fixtures are the `runtime-edges-*` and
  `unsupported-edges-*` refusals beside the oracle's reports. `census_form` gained
  `alternatives=` so `edges()` and `edges(str)` are two declared forms.
- *Settled* (step 3): the box, cylinder and drilled-plate selections are held
  on the stack in `tests/test_cq_edges.py` (counts, curve kinds, centres by
  closed form), not as `cq/` fixtures, for step 2's reason. `SELECTORS` splits
  into `AXIS_SELECTORS` (what `faces` reads) and the whole declared set.
- *Settled* (step 4): the `handwheel` is a step 5/6 program: all 201 write
  `chamfer` and none `fillet`. Step 4's corpus program is `washer_000042_s20260505`
  (`.edges(">X").fillet(0.25)` on a bored ring, a row of the committed census), and
  `handwheel` goes to step 5 with `chamfer`.
- *Settled* (step 5): `Workplane.chamfer` is `fillet`'s `_blended` with `Solid.chamfer` and
  CadQuery's "Chamfer requires that edges be selected". The corpus programs as written: the
  `clevis_pin` is `clevis_pin_000171_s20260505` (a pin along y), `unsupported-` at its seam
  (ADR-0020 rule 2: 234 of the 355 pin programs write a plane other than `XY` and meet it);
  the `dowel_pin` is `dowel_pin_000027_s20260505` (`XY`, closed form); the `handwheel` is
  `handwheel_000006_s20260506`, whose measures are the oracle's (no closed form is at hand).
  `clevis_pin_000420_s20260505` (a cross hole cut after the chamfer) is not a fixture: arris's
  volume equals the closed form (a quadrature of the two cylinders, 42415.8528408) and the
  oracle's is 1.3e-5 off, so `compare` leaves the row unclassified; step 6 or 7 classes it
  (Open CASCADE wrong, by closed form).
- *Settled* (step 6): no `stepped_shaft` writes `'>Z or <Z'` (115 write `faces(sel).chamfer`);
  the turned parts that do are the pins of step 5, so the shaft fixture is `stepped_shaft_000048_s20260505`
  and the pins cover the `or` selector on a turned part. All 78 blend-writing `ball_knob` programs end
  `arris_refusal` at their union (a sphere and a stem touching at the pole, already
  `fuse-contact-refusals`), before any blend: `regression/cq-ball-knob-chamfer-after-point-contact`
  holds the desired result by closed form (xfail, no new ask). `gridfinity_bin` (164) and the
  `stepped_shaft` (115) run `ok`, each fixture held to a closed form and agreeing with the oracle.
- *Settled* (step 7a, ADR-0020's amendment): the 275 are not undecidable. CadQuery builds every
  cylinder, swept circle and bore in its workplane's own axes, so Open CASCADE's seam lies on the
  workplane's +x (a bore's on -x); the oracle bears it out on ten `seam-*` constructions. Each
  `cq` chain records those seams (`Seam`, `Workplane._seams`), merged through `union` and `cut`
  and forgotten after `revolve`, `polarArray` (CadQuery turns each point) and a swept arc; a seam
  on a cylinder whose axis is square to the selector's is ranked there. The 275 run `ok`: 191
  agree, 84 unclassified after the blend (step 7c), 0 `cq_bug`. A narrower rule needing no
  record (a blend passes over seams, so only the other edges' membership matters) decides the
  234 pins but not a washer's two seams, which one above and one below the rims would leave
  `'>Z or <Z'` the seams alone; not taken. `unsupported-chamfer-corpus-clevis-pin-seam` became
  `ok-chamfer-corpus-clevis-pin`, `unsupported-edges-cylinder-side` (a lone cylinder's `>X`,
  now the seam, as the oracle keeps it) became `unsupported-edges-revolved-side`.
- *Settled* (step 7c): the 84 are three causes, none a `cq` fault. 81 `clevis_pin` (a chamfered
  cylinder, one or two cross holes): arris's box is 1e-3 to 5e-3 wide along the hole's axis (the NURBS hull,
  `cq-cross-hole-bounds`' cause) and the oracle's volume 4e-9 to 2.2e-5 off the crossing cylinders' closed
  form, so `arris_bug` by that fixture, family-keyed (`--arris-bug clevis_pin=...`), as the
  `shaft_collar` rows; no closed form can clear arris's box. `spacer_ring_008375`: volume, area and centroid
  equal to 1e-14 on both sides, arris's x max 0.037 past the part (the slot's walls cut the chamfer cone in
  two NURBS hyperbolas): new fixture `regression/cq-chamfer-slot-bounds` (a solid disc, closed form by
  quadrature, the oracle's measures equal it to 1e-15), `arris_bug` by stem (`--arris-bug`/`--refusal`
  now take a stem, which wins over its family). `spacer_ring_012675` and `_016757` (a fillet, then a slot
  through, or to a floor 1.68 up): `occt_wrong` by `slotted_ring_closed_form` (a one-dimensional integral over
  the radius; arris within 6e-12 of it, Open CASCADE 1.3e-6 and 2.9e-9 off in volume), the ring's
  parameters read by `_RING` (a program of another shape raises). Re-run on the 275 slice the three
  classes give 84 verdicts, each passing `compare`; step 8's command is `tools/cq_closed_forms.py` with
  `--arris-bug shaft_collar=...cq-cross-hole-bounds --arris-bug clevis_pin=...cq-cross-hole-bounds
  --arris-bug spacer_ring_008375_s20260505=...cq-chamfer-slot-bounds`.
- *Settled* (step 7b): the 7 `connecting_rod` rows stay as ADR-0014's amendment has them (not
  touched). The 18 sprockets are **lifted**, not refused: reach has no geometric declaration (ADR-0012
  is static) and a refusal in the subset would be a left-over `cq_bug`. Cause: `faces('>X')`/`('>Z')`
  on a hub whose cylinder side shows 0.01 above the top plate, a band whose centre (0.005 under the
  end disc) is inside ADR-0017 rule 2's margin (1e-4 of the diagonal, 0.008 on D about 80). A second
  estimate 100 times finer settles a gap, never a tie (`_REFINED_CHORD`, `_REFINED_MARGIN`; ADR-0017's
  2026-11-15 amendment: the refusals of the 2026-11-14 one are unchanged, `test_cq_faces` holds
  them). The 18 then end `ok` and disagree with the oracle: Open CASCADE's chamfer of the tooth
  outline (252 to 522 edges) takes less than the mitre (0.1% of the volume), shown on one plate
  alone (`chamfer(0.3)`: 1.2e-4 off) while convex, L-shaped, short-edge and arc polygons agree; the
  closed form (`sprocket_measures`: mitred chamfer by the polygon's area, perimeter and sum of
  tan(turn / 2), moments from the mitred offset) matches arris to 1e-11 and passes `compare` on all
  18 (`occt_wrong`), asymmetric outlines included. Fixtures: `ok-thin-band-top-face` (the selection,
  by construction, agreeing with the oracle), `ok-sprocket-corpus-along-x` (016264, asymmetric) and
  `-along-z` (017919), each with a `verdict.json` and the oracle's record. No wheel change.
- ⚠ OPEN (agent, by step 7): the share of the 3,433 arris refuses (a blend
  next to a boolean's edges, a radius at its limit). Refusals are
  `arris_refusal` rows and lower agreement, not reach; if they dominate a
  family, its asks go to arris before step 8, and the plan does not wait on them.

# Plan: lift-sketches

- Started: 2026-11-21
- Milestone: C2, bundle 4 (docs/ROADMAP.md §C2; ADR-0014's amendment of 2026-11-14)
- Idea: none; verbatim from the human: "/plan for bundle 4" (CAD-Recode's sketch API)

## Goal
`cq` runs CadQuery 2.3.0's `Workplane.sketch()` API as CAD-Recode writes it:
`push`, `circle` and `rect` with `mode=`, `segment`, `arc`, `close`,
`assemble`, `reset`, `face` and `finalize`, extruded. The census calls a
sketch's methods `Sketch.*`, so the lift admits CAD-Recode's programs and no
BenchCAD program. CAD-Recode's reach goes from 104/968 to 968/968 with zero
in-subset `cq_bug` and zero unclassified rows, which meets its fidelity target
(ADR-0014). BenchCAD's table stays byte-equal.

## Non-goals
- `Workplane.rect`, `center` and the rest of bundle 5 (BenchCAD's head).
- `cq.Sketch()`, `placeSketch`, `Sketch.clean` (BenchCAD's 156 programs: the tail).
- Sketch methods and keywords CAD-Recode never writes (`rarray`, `fillet`, `hull`, `tag=`, `angle=`, …).
- `sketch()` on a stack that is not empty; `extrude(both=)`, `cutBlind`, `revolve` or holes on a sketch.
- The table digest across architectures (C2's accept line), checked when C2 closes.

## Design deltas
**A. The census types a sketch chain** (step 3, ADR-0003 amended). Today a
call is counted on its chain's root constructor (`chain_root`), so
`w0.sketch().rect(1, 2)` counts as `Workplane.rect(num, num)`. Lifting the
sketch forms under those names would also admit 725 BenchCAD programs
(`rib_plate` 190, `heat_sink` 180, `waffle_plate` 163, `u_channel` 159, …)
that never write `sketch()`. They write the real `Workplane.rect`, which `cq`
refuses, so each would be an in-subset `cq_bug` (measured 2026-11-21 on the
committed census rows). Instead, a call's receiver is `Sketch` when the
nearest `sketch()` below it on the chain is above the nearest `finalize()`,
and the root otherwise. A name bound to such a chain carries the same type.
Under `Sketch.*` names the lift admits 0 BenchCAD programs. No BenchCAD
program writes `sketch()`, so BenchCAD's census digest (`043db6d9…`) does not
move. CAD-Recode's (`6ac45480…`) and its reach curve do.

**B. A `cq` sketch is the ordered fold of its regions' prisms**
([ADR-0023](../adr/0023-a-cq-sketch-extrudes-as-an-ordered-fold-of-prisms.md),
step 2). `sketch()` on an empty stack derives a frozen workplane holding a
mutable sketch, which `finalize()` returns. The sketch holds a fold of
calls, a selection in plane coordinates and the free edges. Each call
places its regions at every selected point or, for an empty selection, at
the origin. `face(s)` captures `s`'s local fold, and `assemble()` records
one closed loop in the fold while retaining the free edges.

`extrude(d)` folds left to right. Each call fuses, cuts or intersects with
the union of its placements. For `i`, intersect each tool with the original
section and fuse the surviving pieces. The extrusion interval is 0 to |d|
on the signed axis, and cut or common tools extend from −|d| to 2|d|.
`Model.interference` detects an empty cut or common from containment or
overlap. A fold that finishes empty ends `runtime` ("No pending wires
present"). A nonempty fold is fused with the chain's solid if it has one.
ADR-0023 gives the edge and mode errors and their oracle records.

**C. Public surface.** New private module `cq/_sketch.py`, and a
program-facing `Sketch` reached only through `sketch()`. `cq.Sketch` stays
`UnsupportedApi`; any other attribute raises `UnsupportedApi("Sketch.<name>")`.
`cq.subset()` gains 13 declarations covering 16 API forms:
- `Workplane.sketch()`
- `Sketch.finalize()`, `push(list)`, `reset()`, `close()`, `assemble()`
- `Sketch.circle(num)`, `rect(num, num)`, `face(call)`, each also with `mode=str`
- `Sketch.segment(tuple)`, `segment(tuple, tuple)`, `arc(tuple, tuple)`, `arc(tuple, tuple, tuple)`

`kind_of` reads a `Sketch` as `call`. No existing public type or method
changes. `cq` still imports only `arris`.

**Glossary.** Step 2 defines **Sketch** (delta B's fold, selection and free
edges). Step 3 sharpens **Receiver** at `sketch()` and `finalize()`.

## Steps
Grades are tiers (`.agents/tiers.md`):
- **[1]** routine: the design says what to write, the tests are mechanical.
- **[2]** careful: a numeric, geometric or semantic case inside this design.
- **[3]** unproven: a CadQuery semantic or algorithm established here.

- [x] Step 1 **[3]** — `tools/cq_sketch_probe.py` runs constructed sketches
  on oracle zygotes, in the pattern of `tools/cq_edge_probe.py`. After each
  sketch call it records the face count, area and centroid of CadQuery's
  `_faces`, and at the end the extruded solid's measures. Cases: the
  selection carried across calls (`push rect rect-s`); `assemble` and `face`
  at the selection; each mode on an empty and a non-empty sketch, `i` at two
  points; a sketch a cut empties; disjoint adds; zero and negative sizes; a
  `close` on a chain already closed; an open chain assembled. Writes
  `tests/fixtures/sketch/constructed.json` and its README.
- [x] Step 2 **[3]** — ADR-0023: delta B, settled from step 1's records,
  closing the first `⚠ OPEN`. Doc only.
- [x] Step 3 **[2]** — the census types sketch chains (delta A), with
  ADR-0003's amendment and unit cases: a chained sketch, a sketch bound to a
  name, `finalize().extrude`. The never-raises property still holds.
  Regenerates CAD-Recode's census, `programs.jsonl.gz`, `reach.json` and
  manifest. Checks BenchCAD's census is byte-equal (**[conductor-run]** past
  110 s). Amends ADR-0014 for the renamed CAD-Recode items and the 725.
  CHANGELOG bullet.
- [x] Step 4 **[3]** — `cq` core in `cq/_sketch.py`: `Workplane.sketch()`,
  `Sketch.finalize`, `push`, `reset`, `circle` and `rect` with and without
  `mode=`, and `extrude(num)` of a sketch (delta B). Keep the frozen C1
  subset in `tests/fixture_cases.py` free of the bundle's declarations.
  Fixtures by construction in
  `tests/fixtures/sketch/`: a plate minus a disc, a ring, `push rect rect-s`,
  disjoint adds (a compound, ADR-0016), disjoint and overlapping `i`
  placements including ADR-0023's 4 × 4 base, cuts and intersections that
  empty the section, and `YZ` with `origin=` and a negative distance. Hold
  the mode and size cases in ADR-0023. Check mutation after `finalize()`
  and an add after an empty section. Property (`hypothesis`): axis-aligned
  rects on an integer grid under modes `a s i`, with extruded volume equal
  to their rectilinear area by coordinate compression times |d|.
- [x] Step 5 **[2]** — `segment`, `arc`, `close`, `assemble()`. Fixtures: a
  triangle in drawing order and shuffled with a reversed edge, a D (a half
  disc on its chord), an arc ending on the start with no `close`,
  `assemble` after `push` and again after `reset`, implicit starts and
  `close` with no edges, `close` on a closed loop, and the open chain.
  A triangle property checks assembly under permutation, reversal and translation.
- [ ] Step 6 **[2]** — `Sketch.face(sketch)` with and without `mode=`, and `kind_of` for a
  `Sketch`. Fixtures: a disc minus an assembled triangle (closed form);
  `reset` against `push` before `face`; a tool mutated after `face`;
  a non-sketch argument (`unsupported_api`). An offline reach test over the
  committed census rows gives 968/968 on CAD-Recode and 9,998/17,900 on
  BenchCAD. CHANGELOG bullet.
- [ ] Step 7 **[3, conductor-run]** — re-run CAD-Recode under `cq` against
  the committed oracle rows (`tools/cq_corpus.py --corpus cadrecode`, fresh
  `--work-dir`). Class every new in-subset disagreement: a `cq` fault shrunk
  to a fixture and fixed (the commit carries its step's suffix), a
  closed-form verdict (`tools/cq_closed_forms.py`), or an arris refusal or bug
  filed in `../arris/docs/ideas/`. Commits the table, reports and README
  figures. Checks the committed reach report against the current subset again.
- [ ] Step 8 **[1, conductor-run]** — re-run BenchCAD. The table digest
  (`45ee27a1…`) and the reach report are byte-equal; the README names the
  re-run.

## Acceptance
- `tests/fixtures/sketch/*`, step 4's property and the census property pass
  under the gate.
- CAD-Recode, each figure over all 968 programs: reach 968/968; in-subset
  `cq_bug` 0, `by_design` 0, unclassified 0, timeouts 0; agreement reported,
  not targeted. That is its fidelity target met (ADR-0014).
- BenchCAD: reach 9,998/17,900, table digest `45ee27a1…` and census digest
  `043db6d9…`, all unchanged.

## Docs to update on completion
- `docs/ARCHITECTURE.md` §Dialects: the subset list and a sketch paragraph (delta B).
- `docs/ARCHITECTURE.md` §The census: receiver typing and CAD-Recode's curve.
- `docs/ARCHITECTURE.md` §Fidelity: CAD-Recode's figures.
- `docs/ROADMAP.md` §C2 status: bundle 4 done, CAD-Recode's target met, bundle 5 next.
- `AGENTS.md` current state.
- `GLOSSARY.md`: **Sketch** (step 2), **Receiver** (step 3).
- `CHANGELOG.md` bullets come from steps 3 through 6; no reward moves.

## Open questions
- *Settled* (step 3, ADR-0014 amendment). The receiver change exposes
  `Sketch.circle(num)` and `Sketch.close()` in the C1 reach curve because C1
  only admitted their workplane counterparts. The curve now takes 20
  items. The subset declarations name both the default and explicit modes
  used by the corpus for `circle`, `rect` and `face`; the reach target is
  still 968/968.
- *Settled* (step 2, ADR-0023). One `i` call intersects with the union of its
  placements, as the two-point records show. `assemble` orders and reverses
  edges to form one closed loop, as the shuffled triangle requires. An open
  chain ends `runtime` at `assemble` because it cannot bound a valid section.
  The oracle's invalid extrusion stays in the fixture.
- *Settled* (step 4). When a cut or common precedes another cut or common,
  evaluate the prefix as unit prisms in a separate model. This lets the
  program catch a null-section error at the drawing call. Final extrusion
  still folds at the requested signed depth in the program's model. The
  partial lift reaches 193 of 968 CAD-Recode programs. The committed table
  is checked against its pre-sketch subset until the step 7 re-run.
- *Settled* (step 5). An empty edge list fails the same single-loop rule
  as an open chain. The dialect raises `ValueError` at assembly, and
  the empty assembly trace records the oracle's `IndexError`.
- ⚠ OPEN: arris may refuse prism folds that Open CASCADE builds. Those rows
  are `arris_refusal` and do not block the target. At step 7 the agent decides
  whether to build a profile with holes for cuts that lie strictly inside, and
  records the choice in ADR-0023 by amendment. Step 4's strict regression
  fixtures also hold corner contact, common after a fused contact, and
  the second fuse of three nested prisms. The coordinate-compression
  property generates rectangle pairs with distinct sides and checks a
  mixed three-call fold explicitly.

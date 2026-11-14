# Plan: lift-arrays-and-blind-cuts

- Started: 2026-11-15
- Milestone: C2, subset growth (docs/ROADMAP.md §C2), bundle 2b of the knee
  (ADR-0014's 2026-11-14 amendment; split from bundle 2 by
  plans/lift-holes-and-points, git)
- Idea: none; verbatim from the human: "bundle 2b (rarray, polarArray,
  center, cutBlind, about +1,270 reach)"

## Goal

`dialect="cq"` runs `rarray(xSpacing, ySpacing, xCount, yCount)`,
`polarArray(radius, startAngle, angle, count)` and `cutBlind(depth)` as
CadQuery 2.3.0 builds them: each array a stack of points that a bore cuts at
and `circle` draws at, and `cutBlind` cutting the pending circles, ring or
circles at points into the part. `cq.subset()` declares the three forms.
Measured at planning time against today's subset (`programs.jsonl.gz`,
`_eligible` and `_missing_forms`), BenchCAD reach goes from 6,154 to 6,565
of 17,900 (+411: `polarArray` alone 160, `cutBlind` alone 109, both 82,
`rarray` 60); the human's +1,270 is bundles 2 and 2b together over 5,295.
CAD-Recode writes none of them and stays at 104 of 968. ADR-0019 decides the
arrays' points and the blind cut over arris. Both tables are re-run with the
oracle's committed rows and committed, nothing unclassified in the subset.

## Non-goals

- `center(num, num)`: it unlocks no program in this bundle. All 1,593
  BenchCAD programs that write it also need a form of a later bundle (`rect`
  and `cutThruAll` 425, with `chamfer`/`edges(str)` 249, with `loft` 248,
  `sweep`/`makeHelix` 57 …); it is lifted with bundle 5's `rect` (open
  question 1).
- The keywords no corpus program writes: `rarray(center=)`,
  `polarArray(fill=, rotate=)`, `cutBlind(clean=, both=, taper=)`, and
  `cutBlind` up to a face or `"next"`/`"last"`.
- The 1,000+ programs that write these forms and also `rect`, `cutThruAll`,
  `chamfer`, `fillet` or `edges`: bundles 3 and 5. Bundle 4 (CAD-Recode's
  sketch API); arris code (a needed capability is asked of arris).

## Design deltas

- **What the 411 write** (read from the corpus text at planning time, not
  run): `polarArray(r, 0, 360, n)` always, after `workplane()` on a face, then
  `hole` (`t_pipe_fitting` 154 calls, `motor_end_cap` 78, `dome_cap` 20) or
  `circle` then `cutBlind` (`bellows` 134); `rarray` with integer counts
  then `hole` (`vented_panel` 60); `cutBlind` always negative (into the
  part), after `circle` (`impeller`, `dome_cap`) or `circle(a).circle(b)` (a
  ring, `spur_gear`), followed by nothing, `faces(sel)` or `union`.
- **`Workplane.rarray(xSpacing, ySpacing, xCount, yCount)`**,
  `census_form(…, [("num",)] * 4)`: a `_Points` stack in CadQuery's order
  (x outer, y inner), the grid centred on the plane's origin; the values
  CadQuery refuses (spacing, counts) as step 1 reads them. Stack contexts as
  `pushPoints`.
- **`Workplane.polarArray(radius, startAngle, angle, count)`**, same
  declaration: points on the circle at CadQuery's angles (a full turn is
  split in `count`, a partial one in `count - 1`, as step 1 reads it), by
  `math.cos`/`math.sin` of `math.radians`: their bits follow libm as
  `transformed`'s turn does (ARCHITECTURE §Determinism). CadQuery's
  rotation of each `Location` is dropped: a bore and a circle are round, and
  nothing else the subset puts on points (ADR-0019).
- **`Workplane.cutBlind(depth)`**, `[("num",)]`: the pending sketch (what
  `extrude` takes: a circle, a ring, `_Discs`) extruded `depth` along the
  normal and cut from the chain's solid in one `Solid.cut(*tools)`;
  `depth = 0` and a chain with no solid end `runtime` with CadQuery's words
  (step 1). `_Discs`'s docstring gains `cutBlind`.
- **ADR-0019** (step 1): CadQuery 2.3.0's `rarray`, `polarArray`,
  `cutBlind`, `_extrude` and `clean` read, the oracle's constructions, and
  arris's cut of a tool flush with the face (a disc, a ring, six discs).
- **Unsupported-example hits** (grep of `tests/`, `src/`, `docs/` for the
  three names): none; `fixture_cases.c1_subset()` keeps the three forms
  out (it is C1's curve, frozen).
- `subset()`'s doctest and ARCHITECTURE §Dialects' "23 API forms" move to
  26; `GLOSSARY.md` **Stack**: `rarray` and `polarArray` also put a stack of
  points, and `cutBlind` takes `circle`'s circles.

## Steps

Grades are tiers (`.agents/tiers.md`): **[1]** routine; **[2]** careful
within a given design; **[3]** unproven semantics, established here.

- [x] Step 1 **[3]** — ADR-0019 from CadQuery's source and the oracle, the
  kernel risk first: a spike that cuts flush blind pockets (a disc, a ring,
  six discs on a circle) from a box and from a revolved part's end face in
  arris against their closed forms. A probe as `tools/cq_hole_probe.py`, its
  reports under `tests/fixtures/arrays/`, each held to a closed form or to
  CadQuery's words: `rarray` (1 × 1, 3 × 2, on `>X` and `<Y`), `polarArray`
  (full and partial turn, a start angle, count 1, a negative radius),
  `cutBlind` (disc, ring, circles at points; inside, past the part, positive,
  zero, with no solid). *Settled*: `tools/cq_array_probe.py`, 49
  constructions; arris cut every flush case to its closed form in one call;
  the refusals and their order (a float count `TypeError`; `cutBlind`: no
  pending wire, then zero depth, then no solid) are ADR-0019's.
- [x] Step 2 **[2]** — `rarray` and a bore on its points: `cq/ok-rarray-*`,
  `runtime-` fixtures for the refused values, one `vented_panel` as written;
  `hypothesis`: a random grid of non-overlapping holes through a box, volume
  `V − n·π d²/4·h`.
- [x] Step 3 **[2]** — `polarArray`: `cq/ok-polar-array-*` (holes, circles
  then `extrude`), `runtime-` fixtures, one `motor_end_cap` as written;
  `hypothesis`: each point at radius `r` within the tolerance, the volume of
  `n` holes on a disc's face.
- [x] Step 4 **[2]** — `cutBlind` per ADR-0019 on a circle, a ring and circles
  at points: `cq/ok-cut-blind-*` with closed-form volume and centroid,
  `runtime-` for zero depth and no solid, a `bellows` and a `spur_gear` as
  written; `hypothesis`: a random pocket in a box, volume `V − π r²·|d|`
  capped at the box.
- [x] Step 5 **[2]** — the corpus contexts, read on the oracle: a hole after a
  blind cut on the same face (`dome_cap`), arrays on a compound
  (`t_pipe_fitting`), `union` after `cutBlind` (`spur_gear`), `impeller`;
  lifted where they agree, else refused, each with its `ok-`, `runtime-` or
  `unsupported-` fixture. *Settled*: all four
  agree on the oracle where they run (161 `impeller`, 36 of 38 `spur_gear`;
  `t_pipe_fitting`'s 77 differ by the tee's own error, step 6). `dome_cap`'s
  87 in-subset programs all end in the known spindle-torus refusal, so its
  context (a hole after a blind cut on the same face) is read on a box and a
  revolved cylinder instead: `ok-ctx-*` in `tests/test_cq_array_contexts.py`.
  Two new arris refusals, both `OpDegenerateError` "the faces touch along a
  curve interior to both result faces", each a tool flush with a face split by
  an edge it crosses, each an xfail fixture and not yet filed with arris:
  `regression/cq-cut-blind-after-a-filled-pocket` (2 `spur_gear` programs; a
  union's circles split the face) and `regression/cq-cut-blind-across-a-split-end-face`
  (42 of 202 `bellows`; a profile vertex splits it; `hole` and a fused post
  across it are refused the same, so it is not `cutBlind`'s). Step 6 counts them
  as `arris_refusal` rows.
- [x] Step 6 **[2, conductor-run]** — the measurement: `cq_corpus.py
  --oracle-rows` on both corpora into a scratch out-dir, then `cq_diagnose.py`;
  in-subset rows by class, `cq_bug` and unclassified by family, recorded
  here. Each cause becomes a step 6a, 6b … before step 7, largest first,
  shrunk to `regression/` fixtures and filed with arris where the kernel is at
  fault, or classed by a closed form (`tools/cq_closed_forms.py`).
  *Measured* (2026-11-15, scratch out-dir, oracle rows reused): BenchCAD reach
  6,565/17,900, in-subset `arris_bug` 142 and `cq_bug` 7 (unchanged),
  `arris_refusal` 1,137 (+95: the 44 refusals of step 5's two fixtures and the
  51 `dome_cap` spindle-torus ones), `occt_wrong` 482, **102 unclassified**
  (77 `t_pipe_fitting`, 25 `bellows`: Open CASCADE's error, volume delta up
  to 9.5e-5 and 2.2e-6); CAD-Recode 104/968, `cq_bug` 0, 0 unclassified;
  31 timeouts as before. The two causes are steps 6a and 6b.
- [x] Step 6a **[3]** — `tools/cq_closed_forms.py` `_tee` reads `polarArray`
  and the flange holes: the 77 `t_pipe_fitting` rows classed `occt_wrong` by a
  closed form, arris within the ADR-0005 constants; a test on one.
  *Settled*: a flanged tee of its own (`_flanged_tee`, `flanged_tee_measures`):
  the end flanges, the bolt holes at CadQuery's face frames (mirrored on XZ and
  YZ, so an odd count's second set falls between; every corpus odd count is on
  XY, one set), and a branch flange that in 48 of the 77 is wider than M or
  starts inside M's wall (7, one with the branch bore ending in it), so the
  branch side is integrated by (x, z) column rather than added to `_tee`'s.
  On the step-6 table (scratch `--out`, the committed verdicts' invocation),
  723 verdicts each checked by `compare`: the 646 committed unchanged, 77
  `t_pipe_fitting` `occt_wrong`, arris within 5e-11 in volume and area of the
  closed form. Tests: three corpus tees on their planes and two on YZ, and
  t_pipe_fitting_000436 against its committed oracle row.
- [x] Step 6b **[3]** — the same tool reads the 25 `bellows` rows (Pappus for
  the revolved profile, the rim sliver by quadrature, as
  `ok-cut-blind-corpus-bellows`'s test does) and classes them `occt_wrong`.
  *Settled*: `_bellows`, `bellows_measures`. 16 of the 25 widen the inner wall
  with a `hole` from the top, and in 10 the holes' circle runs past the rim (a
  notch through it), so each hole's part inside the rim is integrated by radius
  (the disc's angular width at each radius), the rim losing its arc in the
  bottom flange; on `ok-cut-blind-corpus-bellows` the tool equals that test's
  closed form to 3e-16. The 42 refused `bellows` rows are already
  `arris_refusal` by the rule (`regression/cq-cut-blind-across-a-split-end-face`
  holds the cause), so no `--refusal` is given: it would class the family's 25
  ok rows too. On the step-6 table (the committed verdicts' invocation, scratch
  `--out`), 748 verdicts each checked by `compare`: step 6a's 723 unchanged and
  25 `bellows` `occt_wrong`, arris within 1.7e-10 in volume and 7.2e-11 in area
  of the closed form. Tests: the fixture's closed form, `bellows_011847` as
  written and with its holes inside the rim, and its committed oracle row.
- [ ] Step 7 **[1, conductor-run]** — the committed re-run of both tables
  (`tests/fixtures/c2/*`, the READMEs' figures and digests); it deletes
  `fixture_cases.c2_baseline_subset()` (step 2 added it, as step 2 of
  plans/lift-holes-and-points did) and the selector probe's `later` forms.

## Acceptance

- `uv run tools/gate.sh` green with steps 2 to 5's fixtures and the
  `hypothesis` properties of steps 2 to 4, and step 1's probe test.
- Committed tables: BenchCAD reach 6,565/17,900 (or the step-6 figure, with
  its reason, if a declaration had to narrow), CAD-Recode 104/968;
  `in_subset_cq_bug` 0 on CAD-Recode and 7 on BenchCAD (ADR-0014's
  amendment, the `connecting_rod` rows; none new), `in_subset_by_design` 0
  and no in-subset row unclassified on both; each new `arris_bug` row a
  `regression/` fixture.

## Docs to update on completion

- `docs/ARCHITECTURE.md` §Dialects (26 forms; the arrays and `cutBlind`
  paragraph) and §Fidelity (the C2 table and this lift's paragraph).
- `docs/ROADMAP.md` §C2 status and next bundle; `AGENTS.md` current state.
- `GLOSSARY.md` **Stack** (above).
- `CHANGELOG.md` `Unreleased`: the three forms and the refusals a consumer sees.
- `docs/BACKLOG.md`: the bundle 2b line, misfiled under *Rejected*, is
  removed; its tail (`pushPoints` of `Vector` or `Location`, bore keywords,
  `hole`'s positional depth) and `center` with bundle 5 become backlog lines.

## Open questions

- ⚠ OPEN: `center` trimmed (agent's pick, the reach curve decides): it
  unlocks 0 programs now and 673+ with `rect` and `cutThruAll`, so it rides
  with bundle 5. The human may put it back here at review; it costs one
  step of [1] (a moved origin, already how `transformed` offsets the plane).
- ⚠ OPEN (agent, by step 6): whether `tools/cq_closed_forms.py` classes the
  77 new `t_pipe_fitting` rows (the tee of the 64 `occt_wrong` verdicts, with
  bolt holes through its flanges) and the 51 `dome_cap` rows, some of which
  reach the known spindle-torus refusal (`arris_refusal`, not new).

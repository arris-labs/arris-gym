# Plan: lift-sphere

- Started: 2026-11-13
- Milestone: C2, subset growth in reach-curve order (docs/ROADMAP.md §C2)
- Idea: from the human, "the next BenchCAD reach-curve item, radiusArc
  (834 calls)". Measured at planning time against today's subset,
  `radiusArc` is item 41 on the curve and unlocks 0 programs by itself:
  its 417 programs (`pipe_elbow` 241, `duct_elbow` 176) also need
  `sweep(call; isFrenet=bool)`, and `duct_elbow` needs `rect` too. The
  human chose curve item 1, `sphere`, instead. The target is settled
  (ADR-0014); the order is the reach curve's.

## Goal

`dialect="cq"` runs `Workplane.sphere(radius)` as CadQuery 2.3.0 builds it,
and `cq.subset()` declares the form. It is item 1 on BenchCAD's reach curve,
measured at planning time: reach goes from 3,667 to 4,011 of 17,900 (+344:
`capsule` 191, `ball_knob` 153). CAD-Recode writes no `sphere`, so it stays at
104 of 968. All 613 corpus calls write one number, on a fresh workplane
(`ball_knob`'s base) or after a `transformed` (`capsule`'s two caps), and
then `union` it. Each newly reached program agrees with the oracle or has a
class other than `cq_bug`. Both corpora's tables are re-run with the oracle's
committed rows reused (`tools/cq_corpus.py --oracle-rows`) and committed.

## Non-goals

- `sphere`'s other arguments (`direct`, `angle1`–`angle3`, `centered`,
  `combine`, `clean`): the census writes none.
- `radiusArc` and `sweep(isFrenet=)`: one plan when `sweep` comes up in
  curve order, since neither unlocks anything alone. Recorded in
  `docs/BACKLOG.md`.
- BenchCAD's next items (`polygon`, `extrude(both=)`, `slot2D`, `rect`):
  the following plans.

## Design deltas

- **`Workplane.sphere(radius)`**, declared by
  `census_form("Workplane.sphere", [("num",)])`. arris has no sphere
  primitive. The sphere is a half-disc (an arc from pole to pole, closed by
  the diameter) revolved 360° about the workplane's normal through the
  centre, built with `arris.build` as `revolve` builds it. Probed at
  planning time, this gives one face, with volume and area equal to
  4πr³/3 and 4πr² to 1e-15. The poles lie on the normal, as CadQuery's
  `direct=(0, 0, 1)` in local coordinates places them. The centre is the one
  `cylinder` takes: the workplane's origin on an empty stack, or a lone
  `moveTo` point in the plane's own axes (CadQuery's `eachpoint`). A
  workplane whose chain holds a solid is fused with it (`_combined`, as for
  `combine=True`).
- **Refusals** follow `cylinder`'s, each read on the oracle in step 2. A
  stack holding a solid or a compound is `UnsupportedApi`, since CadQuery
  centres the sphere on the object's `Center()`. A drawn path or a sketch is
  refused as `_refuse_pending` does. A radius ≤ 0 is `ValueError`
  (`runtime`), or whatever the oracle shows (Q1).
- **No public type or API change.** `cq.subset().forms` gains one
  declaration. CHANGELOG gets a bullet, and `PROVENANCE.md` names CadQuery's
  `Workplane.sphere` and `Solid.makeSphere` (read, not copied).
- **Known risk, from a planning-time probe** (spheres from a revolved
  `threePointArc`): a `capsule` (a cylinder with a sphere of its radius on
  each end disc, so the surfaces are tangent along the rims) fuses and
  equals πr²h + 4πr³/3. In `ball_knob`, the stem's end disc touches the
  sphere at its pole, and arris refuses that fuse (`OpUnsupportedError`,
  "no closed form for … (plane surface) against … (point)"). This is the
  point-contact family of `fuse-tangent-and-point-contacts` and
  `torus-box-point-contact`. Expect up to 153 in-subset `arris_refusal` rows;
  step 4 shrinks them.

## Steps

Grades are tiers (`.agents/tiers.md`): **[1]** routine; **[2]** careful within
a given design; **[3]** unproven semantics, established here.

- [x] Step 1 **[3]** — the lift. Add `sphere` on an empty stack and on a
  `moveTo` point, on `XY`, `YZ`, `XZ` and `ZX` and after `transformed`, then
  fuse it with a chain solid. Fixtures `cq/ok-sphere-*` take their
  expectations from closed forms (4πr³/3, 4πr², the centre), each checked
  against the oracle. Add `ok-sphere-capsule`, `capsule`'s shape at a
  corpus program's numbers, πr²h + 4πr³/3. A `hypothesis` property ranges
  over centre, radius and plane against the closed form. Declare the form;
  `tables_subset()` holds the committed reports to today's subset less
  `sphere`.
- [x] Step 2 **[3]** — the contexts and refusals. Run `sphere` on each other
  last object, on both sides (the work skill's new-context rule): a solid, a
  compound, a closed sketch, a drawn path, a pending circle. Also run a zero
  and a negative radius. Each is lifted when it agrees and refused otherwise,
  with an `ok-`, `runtime-` or `unsupported-` fixture. Settle Q1.
- [x] Step 3 **[2]** — the measurement. Run `cq_corpus.py --oracle-rows` on
  both corpora into a scratch out-dir, then `cq_diagnose.py` over the new
  BenchCAD table, to get the in-subset rows by class and the `cq_bug` rows by
  message. Rewrite steps 4 and 5 to the causes, largest first, and record any
  cause left for a later plan as Q2, with the reach it costs.
- [ ] Step 4 **[2]** — classify what is left. Measured at step 3: the one
  cause is `ball_knob`'s stem touching the sphere at its pole (the end disc
  of a cylinder meeting the sphere at one point), 153 in-subset
  `arris_refusal` rows (231 `ball_knob` rows refuse, 78 of them outside the
  subset), in four messages by operand order and by how the floating-point
  pole falls ("plane surface against sphere surface" 53 and 66, "plane
  surface against point" 61 and 51). Shrink them to four strict-xfail
  `regression/cq-sphere-pole-on-disc*` fixtures, each with its closed form
  (ADR-0016's compound) checked against the oracle; add item 7 to the arris
  idea `fuse-contact-refusals` and a BACKLOG Finding.
- [ ] Step 5 **[2]** — commit the re-run. The step 3 run (BenchCAD and
  CAD-Recode, `--oracle-rows`, the C1 verdicts and BenchCAD's own) is the
  re-run: copy its outputs from the scratch out-dir into
  `tests/fixtures/c2/*` as `fixtures:` with the new figures (reach 4,011;
  BenchCAD table digest `651fe2c1…c1f5a`, oracle digest `e9925835…73157`
  unchanged; CAD-Recode's table digest unchanged), update both READMEs and
  `tests/test_c2_baseline.py`'s figures, and return `tables_subset()` to
  `cq.subset()`.

## Acceptance

- `uv run --extra corpus tools/cq_corpus.py --corpus benchcad --verdicts
  tests/fixtures/c1/verdicts.json tests/fixtures/c2/benchcad/verdicts.json
  --oracle-rows tests/fixtures/c2/benchcad/oracle.jsonl.gz` reports:
  - reach 4,011/17,900;
  - `in_subset_cq_bug` 0 and 0 unclassified in the subset;
  - the 100 `lobed_knob` rows still `arris_bug`;
  - the oracle digest unchanged, unless a timeout re-ran (named).
- `… --corpus cadrecode --oracle-rows …/cadrecode/oracle.jsonl.gz`: reach
  104/968, its table digest unchanged.
- The `cq/ok-sphere-*`, `runtime-sphere-*` and `unsupported-sphere-*`
  fixtures and the closed-form property pass. Every existing `cq/` fixture
  passes unchanged. Every `regression/` fixture step 4 adds is strict xfail.
  The gate is green.

## Docs to update on completion

- `docs/ARCHITECTURE.md` §Dialects: `sphere` in the call list, with its
  centre, contexts and refusals. §The oracle, "The C2 tables": the figures
  for both corpora and a `sphere` paragraph.
- `docs/ROADMAP.md` §C2 status line: the new reach.
- `AGENTS.md` current state: the reach line.
- `tests/fixtures/c2/{benchcad,cadrecode}/README.md`: the re-run's figures.
- `CHANGELOG.md` §Unreleased: `sphere` under `dialect="cq"`.
- `PROVENANCE.md`: CadQuery's `Workplane.sphere` and `Solid.makeSphere`.
- `docs/BACKLOG.md`: the `radiusArc` + `sweep` line (planning time), and
  §Findings, any arris finding step 4 files or extends.

## Open questions

- *Settled* (step 2): Q1 — `cylinder`'s rule. On the oracle a negative
  radius raises `Standard_ConstructionError` and `sphere(0)` builds a
  zero-volume shape its checker rejects (`invalid`). `cq` ends both
  `runtime` (`ValueError`), the second a `by_design` row
  (`runtime-sphere-zero-radius`). Before this, `cq` built a body from a
  negative radius and the kernel refused a zero one.
- *Settled* (step 3): Q2 — none. Both tables have 0 in-subset `cq_bug` and 0
  unclassified rows. All 153 new in-subset non-agreeing BenchCAD rows are
  `ball_knob` `arris_refusal`s (the pole contact of Known risk); `capsule`'s
  191 all agree. BenchCAD reach 4,011/17,900 (3,667 + 344); CAD-Recode
  104/968. The 100 `lobed_knob` rows are still `arris_bug`. The BenchCAD oracle
  digest is the committed one (the 31 `double_simplex_sprocket` timeouts
  timed out again).

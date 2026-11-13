# Plan: lift-three-point-arc

- Started: 2026-11-13
- Milestone: C2, subset growth in reach-curve order (docs/ROADMAP.md §C2)
- Idea: verbatim from the human: "next reach-curve item". The target is
  settled (ADR-0014); the order is the reach curve's.

## Goal

`dialect="cq"` runs `Workplane.threePointArc(point1, point2)` as CadQuery
2.3.0 builds it, and `cq.subset()` declares the form. Under today's subset
(cylinder lifted) it is item 1 on BenchCAD's reach curve, measured at
planning time: reach goes from 3,304 to 3,667 of 17,900 (+363:
`spline_hub` 177, `ratchet_sector` 61, `dog_bone` 57, `dome_cap` 36,
`rivet` 32). CAD-Recode writes no `threePointArc`, so it stays at 104 of
968. Every newly reached program writes the arc after a `moveTo`, a
`lineTo` or another arc, and closes the path with `close` before an
`extrude` or a `revolve`. Each newly reached program agrees with the oracle
or has a class other than `cq_bug`. Both corpora's tables are re-run with
the oracle's committed rows reused (`tools/cq_corpus.py --oracle-rows`) and
committed.

## Non-goals

- `radiusArc` (834 calls in BenchCAD), `sagittaArc`, `tangentArcPoint`,
  `spline`: each goes in a later plan, in curve order.
- `threePointArc` with a `Vector` or a three-number point: the census
  records only `(tuple, tuple)`, and `_uv` already refuses a point that
  leaves the plane.
- CAD-Recode's head of the curve (`finalize`, `sketch`, `push`,
  `circle(mode=)`, `rect`): a run of forms that unlocks nothing until
  `push` lands. It is its own plan, possibly after an idea.
- BenchCAD's next items (`sphere`, `polygon`, `extrude(both=)`, `slot2D`):
  the following plans.

## Design deltas

- **`_Path` holds segments, not just points.** It keeps its start point
  and a tuple of segments: a line to a point, or an arc to a point through
  a middle point. `lineTo` and `polyline` add lines as they do now. `close`
  builds the loop with `arris.build.Loop.path(start, [Segment.line(to) |
  Segment.arc(to, via)])` on the plane, in place of `PathSketch.line_to`.
  The `_CLOSE_GAP` rule is unchanged: a last segment that ends within the
  gap of the start ends exactly at the start, whether it is a line or an
  arc (`spline_hub`'s last arc ends on its start point).
- **`Workplane.threePointArc(point1, point2)`**, declared by
  `census_form("Workplane.threePointArc", [("tuple",)] * 2)`. CadQuery's
  arc goes from the pen through `point1` to `point2`. arris's
  `Segment.arc(to, via)` takes the end first, so the arguments swap. The
  pen is the same as `lineTo`'s (`_pen`): the end of the drawn path, a
  `moveTo` point, or the plane's origin on an empty stack. Each point
  goes through `_uv`, with the error naming `threePointArc`.
- **Refusals**, each read on the oracle in step 2:
  - a solid or a closed sketch as the last object raises `RuntimeError` as
    `lineTo` does (`runtime`);
  - three collinear or coincident points: CadQuery's exception, its words
    read on the oracle, ends `runtime` on both sides (Q1);
  - an arc whose end is the start of the path (a full circle drawn by one
    arc): read on the oracle, then lifted or refused (Q1).
- **No public type or API change.** `cq.subset().forms` gains one
  declaration. CHANGELOG gets a bullet. `PROVENANCE.md` names
  `threePointArc` and `_findFromPoint`'s pen, which are read, not copied.
- **Diagnosis by the committed oracle**, as in `lift-cylinder`: step 3
  re-runs both corpora under `cq` with `--oracle-rows`, and steps 4 and 5
  are rewritten to the measured causes. One risk is known now: `rivet`'s
  arc meets the revolve axis at a slant, so a cone-like apex is revolved,
  and `dome_cap`'s arc meets the axis square on. arris may refuse the first.

## Steps

Grades are tiers (`.agents/tiers.md`): **[1]** routine; **[2]** careful within
a given design; **[3]** unproven semantics, established here.

- [x] Step 1 **[3]** — the lift. Add `_Path`'s segments and
  `threePointArc` on a `moveTo` point, after `lineTo`, after an arc and on
  an empty stack, on `XY`, `YZ`, `XZ` and `ZX`, closed by a line and by an
  arc that ends on the start. Then `extrude` it (positive and negative) and
  `revolve` it. Fixtures `cq/ok-three-point-arc-*` take their expectations
  from closed forms (a circular segment's area × h, a stadium as
  `dog_bone` draws it, a quarter disc revolved into a hemisphere,
  2πr³/3), each checked against the oracle. A `hypothesis` property ranges
  over a circular segment (centre, radius, two angles, plane, height)
  against the closed form. The form is declared, and reach reads it.
- [ ] Step 2 **[3]** — the contexts and refusals. Run `threePointArc` on
  each other last object on both sides (the work skill's new-context rule):
  a closed sketch, a solid, a compound, a pending circle. Run it with
  collinear, coincident and full-circle points. Each one is lifted when it
  agrees and refused otherwise, with an `ok-`, `runtime-` or
  `unsupported-` fixture. Settle Q1.
- [ ] Step 3 **[2]** — the measurement. Run `cq_corpus.py --oracle-rows`
  on both corpora into a scratch out-dir, then `cq_diagnose.py` over the new
  BenchCAD table, to get the in-subset rows by class and the `cq_bug` rows
  by message. Rewrite steps 4 and 5 to the causes (largest first), and
  record any cause left for a later plan as Q2, with the reach it costs.
- [ ] Step 4 **[3]** — cause 1 from step 3 (placeholder).
- [ ] Step 5 **[3]** — cause 2 from step 3 (placeholder). If step 3 finds
  no `cq_bug`, steps 4 and 5 are deleted.
- [ ] Step 6 **[2]** — classify what is left. Shrink the cause of each
  in-subset `arris_bug` or `arris_refusal` row to a strict-xfail
  `regression/` fixture, listed in `arris-report`. A new kernel ask goes to
  `../arris/docs/ideas/`. A disagreement with the oracle that a closed form
  settles gets its verdict (`tools/cq_closed_forms.py`). No in-subset row
  may be unclassified.
- [ ] Step 7 **[2]** — commit the re-run. Run both corpora with
  `--oracle-rows`, and BenchCAD with the C1 verdicts and its own, in the
  background. Commit `tests/fixtures/c2/*` as `fixtures:` with the new
  figures. The oracle rows must be the committed bytes (none re-run but
  timeouts); state their digest beside the table digest. Return
  `tests/test_c2_baseline.py`'s `tables_subset()` to `cq.subset()`: step 1
  holds the committed reports to today's subset less `threePointArc`.

## Acceptance

- `uv run --extra corpus tools/cq_corpus.py --corpus benchcad --verdicts
  tests/fixtures/c1/verdicts.json tests/fixtures/c2/benchcad/verdicts.json
  --oracle-rows
  tests/fixtures/c2/benchcad/oracle.jsonl.gz` reports:
  - reach 3,667/17,900, less any form step 3 removes (named);
  - `in_subset_cq_bug` 0 and 0 unclassified in the subset;
  - the 100 `lobed_knob` rows still `arris_bug`;
  - the oracle digest unchanged, unless a timeout re-ran (named).
- `… --corpus cadrecode --oracle-rows …/cadrecode/oracle.jsonl.gz`: reach
  104/968 and its table digest unchanged.
- The `cq/ok-three-point-arc-*`, `runtime-three-point-arc-*` and
  `unsupported-three-point-arc-*` fixtures and the closed-form property
  pass. Every existing `cq/` fixture passes unchanged (the `_Path` rewrite).
  Every `regression/` fixture step 6 adds is strict xfail. The gate is
  green.

## Docs to update on completion

- `docs/ARCHITECTURE.md` §Dialects — `threePointArc`, `_Path`'s
  segments, the contexts and refusals; §The oracle, "The C2 tables" — the
  figures for both corpora.
- `docs/ROADMAP.md` §C2 status line — the new reach.
- `AGENTS.md` current state — the reach line.
- `tests/fixtures/c2/{benchcad,cadrecode}/README.md` — the re-run's figures.
- `CHANGELOG.md` §Unreleased — `threePointArc` under `dialect="cq"`.
- `PROVENANCE.md` — CadQuery's `threePointArc` and the pen it starts from.
- `docs/BACKLOG.md` §Findings — any arris finding step 6 files.

## Open questions

- ⚠ OPEN: Q1 — how `cq` ends a degenerate arc: collinear or coincident
  points, and one arc that closes on its own start. Ending them as `runtime`
  matches an oracle failure. A full circle the oracle builds is lifted or
  refused as `unsupported_api`. The agent decides at step 2 against
  ADR-0006's classes. No corpus program writes one, so reach does not move.
- ⚠ OPEN: Q2 — a `cq_bug` cause step 3 measures that steps 4 and 5 cannot
  lift. The agent decides at step 3, by its reach cost: lift it as a step
  here, or remove its form and name the reach it costs (ADR-0012). The
  acceptance's 0 `cq_bug` holds either way.

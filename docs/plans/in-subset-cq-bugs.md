# Plan: in-subset-cq-bugs

- Started: 2026-11-12
- Milestone: C2, the first subset-growth plan (docs/ROADMAP.md §C2)
- Idea: verbatim from the human: "for diagnosing the 717 in-subset cq_bug
  rows. They are the biggest block between reach and a trustworthy reach
  number, and lifting the r = … end form should come in the same plan, since
  it moves CAD-Recode off 0%." The target is settled (ADR-0014).

## Goal

BenchCAD's in-subset programs carry no `cq_bug` row: each of the 717 rows of
the baseline has a measured cause, and each cause is lifted (`cq` builds what
CadQuery builds, inside the agreement tolerance) or its whole form leaves the
subset and reach falls by the programs it held (ADR-0012, ADR-0014). A
CAD-Recode program ending in `r = …` is read as a result by both `cq` and the
oracle's worker, and with `cq.Workplane(str; origin=tuple)` and
`workplane(offset=…)` lifted, CAD-Recode's reach is 37 of 968 (its curve's
item 3), every one of them agreeing or classed outside `cq_bug`. Both
corpora's tables are re-run and committed; reach and the two target
comparisons are the published numbers.

## Non-goals

- The rest of BenchCAD's curve (items 1 to 35 beyond what a cause needs):
  `cylinder`, `threePointArc`, selectors, `hole`, `chamfer`, `fillet` are the
  next plans, in curve order.
- CAD-Recode's items 4 to 18 (`cylinder`, `sketch()` and its calls): a
  following plan, which takes CAD-Recode to 100%.
- The 174 in-subset `arris_refusal` rows and the oracle-side timeouts' effect
  on the digest (backlog); the 363 unclassified rows outside the subset.
- Changing `FidelityRow` to carry `cq`'s message: the diagnosis is a file of
  its own (step 1), not a public type change.

## Design deltas

- **The 717, measured in step 1.** 319 refuse `cq.Workplane('YZ')`, 285
  refuse `cq.Workplane('XZ')`, and 113 refuse `Workplane.circle on a
  non-empty stack` (all `torus_link`, a `moveTo` point before `circle`).
  The constructor's `str` form admits plane values `cq` refuses; `circle`
  has a stack-context gap. No pending-wire refusal is reached by these rows.
  Steps 3 to 5 lift these three causes, largest first; no form is removed,
  so BenchCAD's starting reach stays 1,871. Each named-plane lift uses
  CadQuery's axes and brings an asymmetric, directed construction checked
  against the oracle as well as its shrunk box regression.
- **The diagnosis** (`tools/cq_diagnose.py`, outside the gate, no oracle):
  reruns a table's in-subset `cq_bug` programs under `cq` and writes
  `tests/fixtures/c2/benchcad/cq-bugs.json`: per stem its status and message
  verbatim, a histogram by message, the families per message, no program
  text, CC-BY-4.0 attribution. Each message is a **cause**; the plan's steps 3
  to 5 are rewritten to the causes in descending count when step 1 lands.
- **A cause lifted** follows CadQuery 2.3.0's own behaviour (read, not copied;
  `PROVENANCE.md`): e.g. a `circle` on a stack of points or a solid places one
  circle at each object's centre (`eachpoint`), and a call on a pending wire
  keeps it in the chain's context. Each lift brings a fixture by construction
  under `tests/fixtures/cq/` and the shrunk corpus program under
  `regression/`, strict `xfail` until its commit.
- **A cause not lifted** in this plan removes its form's declaration, so its
  programs leave the subset; the commit names the reach it costs.
- **The result's name** (ADR-0015, step 2): under `cq` a program's result is
  the last `show_object` argument, else module-level `result`, else
  module-level `r`; the oracle's `tools/oracle/worker.py` reads the same
  three in the same order. `cq.subset().end_forms` gains `r = …`. The `arris`
  dialect still reads `result` only. ARCHITECTURE §Dialects and §The oracle
  change; ADR-0007's result rule is amended by ADR-0015. BenchCAD's and the
  slice's oracle rows stay the same bytes (they all end in `show_object`).
- **`cq.Workplane(str; origin=tuple)`**: the named plane moved to `origin`.
  **`Workplane.workplane(offset=num)`**: a new workplane along the current
  normal, on the stack CadQuery would use (no face selected, so the current
  plane); its rule with a solid on the stack is a CadQuery semantic step 7
  establishes against the oracle. Both are `census_form` declarations, so
  reach reads them; BenchCAD's curve item `workplane(offset=…)` moves too.

## Steps

Grades are tiers (`.agents/tiers.md`): **[1]** routine; **[2]** careful within
a given design; **[3]** unproven semantics or worker output, established here.

- [x] Step 1 **[2]** — `tools/cq_diagnose.py` and `cq-bugs.json` for the 717:
  every row has a message, the histogram's counts sum to 717. Rewrite steps 3
  to 5 to the measured causes (largest first) and record the pick for any
  cause left out (Q2).
- [x] Step 2 **[3]** — ADR-0015 and the result's name `r` in the `cq` worker,
  the oracle's worker and `Subset.end_forms`: fixtures `cq/ok-result-r` and an
  `r` program on the oracle; a `hypothesis` property that `result = X` and
  `r = X` give equal rows; the slice's `oracle.jsonl` unchanged.
- [x] Step 3 **[3]** — `cq.Workplane('YZ')` (319 rows): lift the named plane,
  its oracle fidelity fixtures and `regression/cq-plane-yz`; rerun its rows
  to expose any later cause: all 319 `ok` and agree with the baseline oracle,
  no further cause or timeout. Box and directed prism fixtures, plus a property
  over triangle dimensions, local offsets and signed extrusion, pass.
- [x] Step 4 **[3]** — `cq.Workplane('XZ')` (285 rows): lift the named plane,
  its oracle fidelity fixtures and `regression/cq-plane-xz`; rerun its rows
  to expose any later cause: all 285 `ok` and agree with the baseline oracle,
  no further cause or timeout. Box and directed prism fixtures (normal -y),
  plus a property over triangle dimensions, local offsets and signed
  extrusion, pass.
- [x] Step 5 **[3]** — `circle` on a `moveTo` point (113 `torus_link` rows):
  lift its placement, with oracle fidelity fixtures for extrusion and revolve,
  lift `regression/cq-circle-at-point`; its rows agree or have another class:
  70 `ok` and agree, 43 `arris_refusal` (a box touching the torus at its
  seam vertex, BACKLOG Findings `torus-box-point-contact`), no `cq_bug`.
- [x] Step 6 **[3]** — `cq.Workplane(str; origin=tuple)`: fixture by
  construction (a box on an offset plane, its centroid by construction), on
  each admitted plane, `ZX` lifted with it; oracle fixtures `ok-origin-*` and
  a property over plane, origin, local offset and signed extrusion pass.
  *Settled* (agent, step 6, 2026-11-12): CAD-Recode writes the form on `XY`,
  `YZ` and `ZX` (412, 408, 377 calls), and 7 of the 37 programs its curve's
  item 3 reaches name `ZX`; admitting `origin=` without `ZX` would leave them
  in-subset `cq_bug` against step 8's acceptance, so `ZX` (x +z, y +x,
  normal +y, read on the oracle) is lifted in this step.
- [ ] Step 7 **[3]** — `Workplane.workplane(offset=…)`: fixtures with an
  empty stack and with a solid on it, each agreeing with the oracle.
- [ ] Step 8 **[2]** — re-run both corpora with `tools/cq_corpus.py`
  (BenchCAD with the C1 verdicts, in the background), commit
  `tests/fixtures/c2/*` with `fixtures:` and the new figures; the plan's
  numbers in ARCHITECTURE §Fidelity follow.

## Acceptance

- `uv run --extra corpus tools/cq_corpus.py --corpus benchcad --verdicts …`:
  `in_subset_cq_bug` 0, `in_subset_by_design` 0; reach at least 1,871 less
  the programs of any form removed (named); the 100 `lobed_knob` rows
  `arris_bug`; oracle rows the same bytes as the baseline's for every program
  that does not time out.
- `… --corpus cadrecode`: reach 37 of 968, `in_subset_cq_bug` 0, and the 968
  vacuous agreements gone (no row agrees on two `no_result`s).
- `cq-bugs.json`'s 717 stems each accounted for: lifted (now agreeing or
  another class) or out of the subset.
- Each lifted cause's fixtures pass and its regression xfail is lifted; the
  `r`-equals-`result` property passes; the gate is green.

## Docs to update on completion

- `docs/ARCHITECTURE.md` §Dialects — the lifted forms and contexts, the
  result's name; §The oracle — the worker reads `r`; §Fidelity — the new
  table for both corpora, the 717's causes replacing "not established".
- `docs/ROADMAP.md` §C2 — status line: the in-subset `cq_bug` rows cleared,
  CAD-Recode's reach.
- `AGENTS.md` current state — the new reach figures.
- `docs/BACKLOG.md` — drop the "Diagnose the 717" line, the "no CadQuery
  context" line for what is lifted, and the "without C1 verdicts" line.
- `GLOSSARY.md` — no new term expected; **result name** if ADR-0015 needs one.
- `CHANGELOG.md` — `Unreleased`: `r = …` read as a result, `origin=`,
  `workplane(offset=)`, the stack contexts `cq` now runs.
- `PROVENANCE.md` — each CadQuery behaviour taken from its source.

## Open questions

- Q1, settled (agent, delegated by the human, 2026-11-12): `r = …` alone
  does not move CAD-Recode's reach — it is a bridge on the curve (item 1, 0
  programs); items 2 and 3 (`origin=`, `workplane(offset=…)`) reach 37. They
  stay in this plan (steps 6, 7): the plan's purpose is a reach off 0%, both
  are next on CAD-Recode's curve, and `workplane(offset=…)` is item 7 of
  BenchCAD's, so neither is work out of curve order.
- Q2, settled (agent, step 1, 2026-11-12): exactly three first-failure
  messages account for all 717 rows, so steps 3 to 5 lift all three. No form
  removal or reach cost. These are first failures, not proof that later calls
  succeed; each lift reruns its rows and absorbs any newly exposed cause
  needed to meet the unchanged acceptance. The three shrunk regressions are
  strict xfails until those lifts.
- Q3, settled (agent, step 2, 2026-11-12): the fixed list `show_object`,
  `result`, `r`, by presence even when invalid (ADR-0015). It preserves
  existing selection, admits the census's ranked end form and needs no
  runtime parse; the last statement's arbitrary bound name is not a result.

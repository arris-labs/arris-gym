# Plan: lift-cylinder

- Started: 2026-11-13
- Milestone: C2, subset growth in reach-curve order (docs/ROADMAP.md §C2)
- Idea: verbatim from the human: "for lifting Workplane.cylinder(num, num)".
  The target is settled (ADR-0014); the order is the reach curve's.

## Goal

`dialect="cq"` runs `Workplane.cylinder(height, radius)` as CadQuery 2.3.0
builds it, and `cq.subset()` declares the form. Under today's subset it is
item 1 on both reach curves, measured at planning time: BenchCAD reach goes
from 1,871 to 3,304 of 17,900 (+1,433, led by `turnbuckle` 186,
`pull_handle` 176, `cotter_pin` 159, `tee_nut` 152), and CAD-Recode from 37 to
104 of 968 (+67). Each newly reached program agrees with the oracle or has
a class outside `cq_bug`. Both corpora's tables are re-run with the oracle's
committed rows reused (`tools/cq_corpus.py --oracle-rows`) and committed.

## Non-goals

- The other `cylinder` forms (`direct=`, `angle=`, `centered=`, `combine=`):
  the census records none in either corpus.
- `cylinder` on a solid's stack or on a drawn path: CadQuery centres it on
  the object's `Center()` (read on the oracle at planning time), which the
  subset does not model, as with `box` (`unsupported-box-on-solid`).
- BenchCAD's next curve items (`threePointArc`, `sphere`, `polygon`,
  `extrude(both=)`) and CAD-Recode's (`finalize`, `sketch`, `push`): the
  following plans, in curve order.
- A new reward or a new fidelity rule: the cylinder is a body like a box.

## Design deltas

- **`Workplane.cylinder(height, radius)`** in `cq/_workplane.py`, declared
  by `census_form("Workplane.cylinder", [("num",)] * 2)`. Read on the
  oracle at planning time: the axis runs along the plane's normal, and the
  cylinder is centred on the point in all three axes (`centered=True`,
  bounds ±h/2 along the normal), with 3 faces. On an empty stack it sits at
  the plane's origin; on one `moveTo` point, at that point; a solid further
  up the chain is fused (`combine=True`). It is built as `box` is, a circle
  on the plane offset by −h/2 and extruded h. arris's circle extrude
  already gives the oracle's 3 faces.
- **Refusals**, each read on the oracle:
  - a pending path, wire or sketch, and a stack holding a solid, end
    `unsupported_api` "Workplane.cylinder on …";
  - height ≤ 0 or radius < 0 raise as CadQuery's `Standard_ConstructionError`
    does (`runtime` on both sides);
  - radius 0 is `invalid` on the oracle; its `cq` outcome is Q1.
- **No public type or API change.** `cq.subset().forms` gains one
  declaration. CHANGELOG gets a bullet; `PROVENANCE.md` names `cylinder`'s
  `eachpoint` placement, which is read, not copied.
- **Diagnosis by the committed oracle.** Step 3 re-runs both corpora under
  `cq` with `--oracle-rows`, so only `cq` runs. The in-subset rows that do
  not agree are grouped by `cq` message and class (`tools/cq_diagnose.py`
  over the new table), and steps 4 and 5 are rewritten to the measured
  causes, largest first.

## Steps

Grades are tiers (`.agents/tiers.md`): **[1]** routine; **[2]** careful within
a given design; **[3]** unproven semantics, established here.

- [ ] Step 1 **[3]** — the lift. `cylinder` on an empty stack and on a
  `moveTo` point, on `XY`, `YZ`, `XZ`, `ZX` and with `origin=`, after
  `transformed` and after `workplane(offset=)`, and fused with a chain
  solid. Fixtures `cq/ok-cylinder-*` have closed-form expectations
  (V = πr²h, the centroid on the point, bounds ±r and ±h/2 along the
  plane's axes), and each is checked against the oracle. A `hypothesis`
  property ranges over plane, origin, point, height and radius against the
  closed form. The form is declared, and reach reads it.
- [ ] Step 2 **[3]** — the refusals and the degenerate dimensions. Run
  `cylinder` on every other stack context on both sides (the work skill's
  new-context rule): a pending path, a pending circle, a sketch, a solid,
  a compound. Each one that disagrees is refused, with an `unsupported-*`
  fixture. Also add `runtime` fixtures for height ≤ 0 and radius < 0, and
  settle radius 0 (Q1).
- [ ] Step 3 **[2]** — the measurement. Run `cq_corpus.py --oracle-rows`
  on both corpora into a scratch out-dir, then `cq_diagnose.py` over the new
  BenchCAD table, to get the in-subset rows by class and the `cq_bug` rows
  by message. Rewrite steps 4 and 5 to the causes (largest first), and
  record any cause left for a later plan as Q2, with the reach it costs.
- [ ] Step 4 **[3]** — cause 1 from step 3 (placeholder).
- [ ] Step 5 **[3]** — cause 2 from step 3 (placeholder). If step 3 finds
  no `cq_bug`, steps 4 and 5 are deleted.
- [ ] Step 6 **[2]** — classify what is left. Each in-subset `arris_bug` or
  `arris_refusal` row's cause is shrunk to a strict-xfail `regression/`
  fixture and listed in `arris-report`. A new kernel ask goes to
  `../arris/docs/ideas/`, and a disagreement with the oracle that a closed
  form settles gets its verdict. No in-subset row may be unclassified.
- [ ] Step 7 **[2]** — the re-run committed. Run both corpora with
  `--oracle-rows` and BenchCAD with the C1 verdicts, in the background, and
  commit `tests/fixtures/c2/*` as `fixtures:` with the new figures. The
  oracle rows must be the committed bytes (none re-run but timeouts); state
  their digest beside the table digest.

## Acceptance

- `uv run --extra corpus tools/cq_corpus.py --corpus benchcad --verdicts
  tests/fixtures/c1/verdicts.json --oracle-rows
  tests/fixtures/c2/benchcad/oracle.jsonl.gz` reports:
  - reach 3,304/17,900, less any form step 3 removes (named);
  - `in_subset_cq_bug` 0 and 0 unclassified in the subset;
  - the 100 `lobed_knob` rows still `arris_bug`;
  - the oracle digest unchanged, unless a timeout re-ran (named).
- `… --corpus cadrecode --oracle-rows …/cadrecode/oracle.jsonl.gz`: reach
  104/968, `in_subset_cq_bug` 0, 0 unclassified in the subset.
- The `cq/ok-cylinder-*` and `unsupported-cylinder-*` fixtures and the
  closed-form property pass; every `regression/` fixture step 6 adds is
  strict xfail; the gate is green.

## Docs to update on completion

- `docs/ARCHITECTURE.md` §Dialects — `cylinder`, its contexts and refusals;
  §Fidelity — the C2 table figures for both corpora.
- `docs/ROADMAP.md` §C2 status line — the new reach.
- `AGENTS.md` current state — the reach line.
- `tests/fixtures/c2/{benchcad,cadrecode}/README.md` — the re-run's figures
  and its `--oracle-rows` command.
- `CHANGELOG.md` §Unreleased — `cylinder` under `dialect="cq"`.
- `PROVENANCE.md` — CadQuery's `cylinder` placement.
- `docs/BACKLOG.md` §Findings — any arris finding step 6 files.

## Open questions

- ⚠ OPEN: Q1 — how `cq` ends `cylinder(h, 0)`, where the oracle builds an
  `invalid` zero-volume shape. Refusing it as `runtime` leaves a disagreement
  whose class must be named; the alternative is to build nothing and match
  `invalid`. The agent decides at step 2 against ADR-0006's classes. No
  corpus program writes a literal 0, so reach does not move either way.
- ⚠ OPEN: Q2 — a `cq_bug` cause step 3 measures that steps 4 and 5 cannot
  lift. The agent decides at step 3, by its reach cost: lift it as a step
  here, or remove its form and name the reach it costs (ADR-0012). The
  acceptance's 0 `cq_bug` holds either way.

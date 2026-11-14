# Idea: next-lift

- Status: Accepted (C, bundles riskiest first); not yet planned
- Raised: 2026-11-14
- Prompt (verbatim from the human): "next-lift"

## Problem

C2 has lifted five items one plan each (`cylinder`, `threePointArc`,
`sphere`, `polygon`, `extrude(both=)`), BenchCAD reach 1,871 → 4,345
(24.3%), CAD-Recode 104/968. ADR-0014 asks for 15,215 and 968. Each plan
has taken 5 to 6 steps, most of them the fixed cost of one item: the
oracle's contexts, a corpus re-run, the causes it finds, a committed re-run.

The reach curve recomputed today against `cq.subset()` (not the committed
`reach.json`, which measures C1's subset):

| # | items (BenchCAD) | gain each | reach after |
|---|---|---|---|
| 1–6 | `slot2D`, `rect`, `loft(combine=)`, `mirrorY`, `extrude(taper=)`, `cutThruAll` | 22 to 272 | 5,030 |
| 7–28 | `faces(str)` (bridge), six axis selectors, `hole`, `pushPoints`, `rarray`, `center`, `cutBlind`, `chamfer`, `edges(str)`, `fillet`, `\|X/Y/Z`, `edges()`, `polarArray`, `>Z or <Z`, `hole(depth=)` | 0 to 1,630 | **15,485 (86.5%)** |
| 29– | `shell` and the tail | ≤ 417 | |

The **knee is now item 28**: the 28 items are exactly the set that clears
T = 85%, so all of them get lifted in C2 whatever the order. One item per
plan is 28 more plans at today's cadence. Order and batching are therefore
the only free choices, and they decide how fast reach rises and when the
risky semantics are met.

Measured bundles (BenchCAD, programs unlocked over 4,345, nothing else
admitted):

| bundle | reach | gain |
|---|---|---|
| head (items 1–6) | 5,030 | +685 |
| selectors: `faces(str)`, `workplane()`, `>Z <Z >X <X >Y <Y` | 4,507 | +162 |
| head + selectors | 5,658 | +1,313 |
| selectors + holes (`hole`, `hole(depth=)`, `pushPoints`, `rarray`, `center`, `cutBlind`, `polarArray`) | 6,444 | +2,099 |
| head + selectors + holes | 9,450 | +5,105 |
| all 28 | 15,485 | +11,140 |

The head and the selector programs are entangled: 466 of the 1,313 that
head + selectors unlock need items from both.

CAD-Recode's remaining curve is one API: `Workplane.sketch()` and
`finalize()` (bridges), `push`, `circle(mode=)`, `rect` with and without
`mode`, `assemble`, `arc` (2 and 3 points), `segment` (1 and 2 points),
`reset`, `face(call)` with and without `mode`: 14 items, 864 programs, no
selector, nothing shared with BenchCAD's knee but `rect`.

## Constraints it runs into

- **ADR-0014 and `docs/ROADMAP.md` §C2 say "census order"; `AGENTS.md`
  says "reach-curve order".** Any order but the greedy curve's bends that
  wording. Within the knee's 28 items the order moves no target, only the
  path; amending the wording is a dated section of ADR-0014 (as its
  2026-11-12 correction was), not a new decision on T.
- **ROADMAP's principle**: each milestone retires the riskiest remaining
  unknown first. The riskiest left in C2 are the selectors
  (`docs/ARCHITECTURE.md` §Dialects: ⚠ OPEN, CadQuery's string selectors on
  curved faces), `workplane()` on a selected face (its origin and x
  direction), and `fillet`/`chamfer` on arris (refusals there feed C2's
  decision point: "low fidelity from arris refusals ranks arris's next
  cycle", and arris has its own lead time).
- **ADR-0012**: an in-subset context limitation is a `cq_bug`. A batched
  plan admits several forms at once, so more new in-subset rows land in one
  re-run and must all be classed before its commit; the plan's measurement
  step grows with the batch.
- **The census keys `.sketch().rect(…)` as `Workplane.rect`** (the `mode=`
  keyword in CAD-Recode's items shows it). Lifting BenchCAD's `rect(num,
  num)` declares a key CAD-Recode's sketch programs also write. Harmless
  while `sketch()` is out (those programs stay outside), but when
  `sketch()` is lifted, `rect` on a pending sketch must run as `Sketch.rect`
  or be an in-subset `cq_bug`. No census change proposed: the plan that
  lifts `sketch()` dispatches on the stack.
- **The plan rule**: at most ~10 steps; a batch of N items is roughly
  2N steps (lift, contexts) plus 3 shared (measure, causes, committed
  re-run), so a plan holds 3 or 4 items.
- arris offers `Selection.extreme/normal/parallel/perpendicular`,
  `Solid.hole(at, diameter, depth)`, `fillet`, `chamfer`, `shell`, `loft`
  and `Sketch.slot`/`rect`; it has no tapered extrude (`ARRIS_API.md`), so
  `extrude(taper=)` is built from a loft or asked of arris.

## Options

### A — Greedy, one item per plan (today)
Next is `slot2D(num, num, num)`: +143, all `pillow_block`. Simple, each
plan small and reviewable; the curve needs no judgement. Costs ~28 plans
to the knee, the next six of them for +685 together, and meets the
selector and `fillet` risks last, around plan 7 and plan 14.

### B — Greedy order, batched by shared semantics
The same order in plans of 3–4 items that share code and fixtures: (1)
2D profiles `slot2D`, `rect`, `mirrorY`, `cutThruAll`; (2) `loft(combine=)`,
`extrude(taper=)`; (3) `faces(str)`, `workplane()`, the six axis
selectors; (4) holes and point stacks; (5) `edges`, `fillet`, `chamfer`,
the parallel selectors and `>Z or <Z`. About 7 plans to the knee, one
corpus re-run each. Order unchanged, so no wording to amend. Selectors
still come third.

### C — Batched, riskiest bundle first
B's bundles, ordered by risk: selectors and `workplane()` on a face first
(it closes the ⚠ OPEN with an ADR), then holes (+1,937 more with the
selectors), then `edges`/`fillet`/`chamfer` (the arris refusals arris needs
to hear about), then the head. The first plan unlocks only +162, the least
of any bundle; reach catches up from the second plan on (6,444 after it,
against B's 5,658 after three). Amends "census order" in ADR-0014,
ROADMAP and AGENTS.md to "the knee's items, riskiest bundle first".

### D — CAD-Recode's sketch API first
The 14 items in two or three plans: 864 programs, the corpus to its 100%.
One coherent API (`cq.Sketch` reached through `Workplane.sketch()`), a
whole corpus finished early. Its semantics (`mode` booleans, faces
assembled from edges) are new, but they are not what arris's next cycle
needs to hear, and BenchCAD waits.

### Do nothing
Stop lifting and revisit T. Nothing measured argues for it: the knee
moved earlier (item 28, not 35) as items were lifted, and every C2 lift so
far ended with 0 in-subset `cq_bug`.

## Recommendation

**C.** The knee's 28 items are fixed, so the greedy order buys nothing
lasting; it only front-loads +685 of easy reach and pushes the two real
unknowns (selector semantics, arris's `fillet`/`chamfer`) to the last
third of the cycle, where a bad answer costs the most. Batching (B and C
alike) cuts ~28 plans to ~7 and pays the corpus re-run once per bundle.
A loses on cost, B on risk order, D on arris's lead time (CAD-Recode
comes after the knee, or between bundles if a plan stalls on arris).

What would change my mind: if the first selector plan's measurement shows
`workplane()` on a face needs the head's `rect` or `center` to test
anything real, fold those two into it; if arris answers a `fillet` ask
slowly, move the `fillet` bundle ahead of holes.

## Decision for the human

Round 1:

❓ **Q1 — Cadence**: (A) one item per plan, as now; (B) a bundle of 3–4
items sharing semantics per plan, one corpus re-run each.
➡️ B: the knee's items are fixed, the re-run and its classing are the
fixed cost per plan, ~7 plans instead of ~28.

❓ **Q2 — Order**: (A) the greedy curve (head, then selectors); (B) riskiest
bundle first: selectors and `workplane()` on a face, holes,
`edges`/`fillet`/`chamfer`, then the head; (C) CAD-Recode's sketch API
first.
➡️ B: retires the ⚠ OPEN and the arris `fillet`/`chamfer` question while
there is time to act on them; costs one slow first plan (+162).

❓ **Q3 — The words**: add to `GLOSSARY.md` **Lift**: "admitting a census
item to the subset: `cq` runs it as CadQuery 2.3.0 does, its
`census_form` declares it, its fixtures come from closed forms, and both
corpora are re-run with every new in-subset row classed"; and **Knee**:
"the reach curve's item at which a corpus's reach first clears its T; the
items up to it are those C2 must lift (ADR-0014)".
➡️ Yes: both words are in every C2 plan and ADR-0014 without an entry.

An ADR: if Q2 is B, ADR-0014 gets a dated amendment ("census order" →
"the knee's items, riskiest bundle first"), and the first plan writes the
selector ADR that closes the ⚠ OPEN in `docs/ARCHITECTURE.md`.

Round 2, measured against `cq.subset()` (BenchCAD gains over 4,345):

❓ **Q4 — The first plan's bundle**: (A) `faces(str)`, `workplane()` on a
face, the six axis selectors `>Z <Z >X <X >Y <Y` (one parser) and
`hole(num)`: +950, reach 5,295; the unlocked programs write `>Z` 351,
`>Y` 295, `>X` 275 and each `<` about 10 times (`bearing_retainer_cap`
160, `impeller` 105, `connecting_rod` 94, …); (B) A and `cutThruAll()`:
+1,221; (C) the selectors and `workplane()` alone: +162, only `>Z`,
`>Y`, `>X` written.
➡️ A: `hole` on a selected face is what the selectors are for in this
corpus (+162 → +950), and it is the same machinery (a face, a workplane on
it, a cut); `cutThruAll` waits for the head bundle to keep the plan under
ten steps. `bearing_retainer_cap`'s 25 known `OpInternalError` rows
(BACKLOG) will land in its measurement as `arris_refusal`, to be shrunk.

❓ **Q5 — Where CAD-Recode's sketch bundle goes**: (A) after
`edges`/`fillet`/`chamfer` and before the head; (B) second, right after
the selector plan; (C) last, after BenchCAD's knee.
➡️ A: it is new semantics (`mode` booleans, faces from edges), riskier
than the head and less urgent for arris than `fillet`/`chamfer`; it also
settles the `.sketch().rect` key before the head lifts `rect`, so `rect`
is lifted once, knowing both receivers.

## Decision

Round 1 (2026-11-14), the human: "yes".
- Q1: B, a bundle of 3–4 items sharing semantics per plan, one corpus
  re-run each.
- Q2: B, riskiest bundle first: selectors and `workplane()` on a face,
  holes, `edges`/`fillet`/`chamfer`, then the head. ADR-0014 gets a dated
  amendment ("census order" → "the knee's items, riskiest bundle first"),
  written by the first plan with the selector ADR.
- Q3: yes; **Knee** and **Lift** added to `GLOSSARY.md`.

Round 2 (2026-11-14), the human: "yes".
- Q4: A, the first plan lifts `faces(str)`, `workplane()` on a face, the
  six axis selectors and `hole(num)` (+950, reach 5,295); `cutThruAll`
  waits for the head bundle.
- Q5: A, CAD-Recode's sketch bundle goes after `edges`/`fillet`/`chamfer`
  and before the head, so `rect` is lifted once for both receivers.

The bundles in order: (1) selectors, `workplane()` on a face, `hole(num)`;
(2) the other holes and point stacks (`hole(depth=)`, `pushPoints`,
`rarray`, `center`, `cutBlind`, `polarArray`); (3) `edges`, `fillet`,
`chamfer`, the parallel selectors and `>Z or <Z`; (4) CAD-Recode's sketch
API, in two or three plans; (5) the head (`slot2D`, `rect`, `mirrorY`,
`cutThruAll`, `loft(combine=)`, `extrude(taper=)`). Each bundle's exact
items are re-measured against the subset at its `/plan`.

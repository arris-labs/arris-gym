# ADR-0014: The fidelity target is a reach of 85% on BenchCAD and all of CAD-Recode

- Status: Accepted (T approved by the human, 2026-11-12)
- Date: 2026-11-12
- Corrected 2026-11-12: the reading of the curves (item shares and bridges) and the cause of the 717 in-subset `cq_bug` rows, against `reach.json`.

## Context

C2 needs a finish line before the subset grows (SEED.md §9.8, ROADMAP §C2).
ADR-0012 fixed what **reach** is (the share of a corpus's programs that are
in-subset, decided statically, every program in the denominator).
`plans/fidelity-target` measured the **reach curves** of both corpora (the
census's items admitted one at a time, greedy by programs unlocked, ties by
programs still missing the item, then kind and key) and a baseline fidelity
table over both full corpora with the C1 subset (arris 0.10.0).

The baseline, each figure over all programs
(`tests/fixtures/c2/<corpus>/`, `docs/ARCHITECTURE.md` §Fidelity):

| | BenchCAD `code_gen` | CAD-Recode validation |
|---|---|---|
| programs | 17,900 | 968 |
| reach | 1,871 (10.5%) | 0 |
| agree (all programs) | 980 (5.5%) | 968 (vacuous, below) |
| in-subset `cq_bug` | 717 | 0 |
| in-subset `by_design` | 0 | 0 |
| unclassified | 363 | 0 |

**C2's starting gap.** BenchCAD's 717 in-subset `cq_bug` rows are all
`unsupported_api` where the oracle builds the part: the static rule admits
programs `cq` still refuses. The cause is not established. What the rows show
points to a gap between the kinds the rule admits and the kinds `cq` runs
(`_subset.py` `_fits`), not to the chain's context: `Workplane.circle(num)`
appears in 113 of the 717 programs and in 0 agreeing ones, `extrude(num)` in
159 against 73. They are recorded here as where C2 starts; diagnosing and
fixing them is a later C2 plan, not the plan that wrote this ADR.

**CAD-Recode's 968 agreements are vacuous.** Every program ends in `r = …`,
which neither `cq` nor the oracle's worker reads as a result, so both sides
fail alike and ADR-0006 classes the pair `agree`. They say nothing about
fidelity, and reach there is 0.

## Decision

**A corpus meets the fidelity target when its reach is at least T and no
in-subset program is `cq_bug`** (and none `by_design`, by ADR-0012's
rule). Plain agreement over all programs is published beside it, never
targeted. T is per corpus, never pooled.

### BenchCAD `code_gen`: T = 85% (15,215 of 17,900 programs)

The curve (`tests/fixtures/c2/benchcad/reach.json`, 57 items to 100%) has
three parts:

- **Items 1 to 11**, forms only: 28.0% (5,008). `cylinder(num, num)` alone is
  1,433 programs (8.0%), 3,304 (18.5%) with the corpus's first item; then `threePointArc`, `sphere`, `loft`, `polygon`,
  `slot2D`, `rect`, `workplane(offset=…)`, `extrude(both=…)`,
  `extrude(taper=…)`, `mirrorY()`. Item 12 (`cutThruAll`) adds 22 programs; items 13 and 14
  (`faces(str)`, `workplane()`) are bridges that unlock nothing alone.
- **Items 15 to 35**, the steep part: from 29.5% to 86.5%. Selectors, `hole`,
  `pushPoints`, `rarray`, `center`, `cutBlind`, `chamfer`, `edges(str)`,
  `fillet`, `edges()`, `polarArray` and `hole(…; depth=…)`, the selectors `>Z`,
  `>X`, `>Y`, `<Z`, `<Y`, `<X`, `|X`, `|Y`, `|Z`, `>Z or <Z`. Almost every
  item here unlocks 300 to 1,600 programs; these are the forms and selectors
  ROADMAP §C2 already names.
- **Items 36 to 57**, the tail: `shell(num)` (+330) and then 21 items
  unlocking up to 417 programs each, among them `workplane(centerOption=…)`,
  `cboreHole`, `cskHole`, `radiusArc`, `makeHelix`, `spline`, `Sketch`, `sweep`
  and `twistExtrude`. The last 1,324 programs cost 14 items.

**The knee is item 35.** Item 34 reaches 84.2%, item 35 reaches 86.5%, and
every later item but `shell(num)` (+330), `radiusArc`, `makeHelix` and
`makeTorus` unlocks under 1% of the corpus (179 programs). T = 85% is the round figure the knee's 35 items clear:
35 items, 25 forms and 10 selectors.
T below 84.2% would leave a selector or `hole(depth)` out; T above 86.5% buys
single-form 1% gains, the tail. T moves by a later ADR if C2's measures say so.

### CAD-Recode validation split: T = 100% (968 of 968 programs)

The curve (`tests/fixtures/c2/cadrecode/reach.json`) has no tail: 18 items
reach every program; items 1, 2, 5, 6, 11 and 16 are bridges that unlock
nothing alone and the other 12 each unlock programs. 697 programs (72%) are
in-subset after item 15; item 16 adds 0, item 17 adds 133 and item 18 adds 138. No T between 85.7% (item 17,
830) and 100% costs less than all 18, so T is 100%. The 18 items are the end
form `r = …`, `cq.Workplane(str; origin=…)`, `workplane(offset=…)`,
`cylinder`, `finalize()`, `sketch()`, `push(list)`, `circle(…; mode=…)`,
`rect(…)` with and without `mode`, `assemble()`, `arc` with two and three
points, `segment` with one and two points, `reset()` and `face(call)` with
and without `mode`.

CAD-Recode's reach is 0 today and cannot rise until `r = …` is read as a
result: that is the first subset-growth candidate, and it is the item with
the baseline's only vacuous agreements behind it.

## Consequences

- C2's accept line becomes: both corpora meet the target, 0 unclassified, the
  table's digest equal across architectures. BenchCAD needs 1,871 to 15,215
  in-subset programs (13,344 more) with the 717 `cq_bug` rows fixed.
- Reach is raised only by lifting forms, selectors and end forms in census
  order; it is never raised by shrinking the denominator.
- A declined behaviour leaves the subset and lowers reach; it is never
  `by_design` inside it (plan Q5).
- ROADMAP §C2's "from that number" is amended to "from the reach curves over
  both corpora", and SEED.md §9.8's fidelity-target `⚠ OPEN` closes, both by
  this ADR's acceptance.

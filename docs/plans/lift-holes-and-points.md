# Plan: lift-holes-and-points

- Started: 2026-11-14
- Milestone: C2, subset growth (docs/ROADMAP.md §C2), bundle 2 of the knee
  (ADR-0014's 2026-11-14 amendment: "the other holes and point stacks")
- Idea: none; verbatim from the human: "for bundle 2, the other holes and point
  stacks (pushPoints, cboreHole, cskHole, hole(…, depth=)), which ROADMAP §C2
  now names as next."

## Goal

`dialect="cq"` runs `pushPoints(list)`, `hole(diameter, depth=)`,
`cboreHole(d, cboreD, cboreDepth)` and `cskHole(d, cskD, cskAngle)` as
CadQuery 2.3.0 builds them, each hole bored at every point on the stack, and
the contexts the newly admitted programs write: `faces(sel)` on a stack of
faces and `circle` on a stack of points. `cq.subset()` declares the four
forms. Measured at planning time against today's subset (`programs.jsonl.gz`,
`_missing_forms`), BenchCAD reach goes from 5,295 to 6,154 of 17,900 (+859:
`pushPoints` alone 684, `hole(…; depth=)` alone 54, `cskHole` 93 and
`cboreHole` 28 each with `pushPoints`); CAD-Recode writes none of them and
stays at 104 of 968. ADR-0018 decides how CadQuery's point stack and bore
tools map onto arris. Both tables are re-run with the oracle's committed rows
and committed, with 0 in-subset `cq_bug` and nothing unclassified in the
subset.

## Non-goals

- The idea's other point-stack items, `rarray`, `polarArray`, `center` and
  `cutBlind` (bundle 2b, next; with them this bundle would reach +1,270):
  split off because this one already holds four forms and two contexts.
- `cboreHole`/`cskHole` with `depth=` or `clean=`, `hole` with a positional
  depth, `pushPoints` of `Vector` or `Location`: no corpus program writes them.
- Bundles 3 to 5 (`edges`/`fillet`/`chamfer`, CAD-Recode's sketch API, the
  head); arris code (a needed capability is asked of arris).

## Design deltas

- **What the 859 write** (read from the corpus text at planning time, not
  run): `pushPoints` always follows `workplane()` on a face (1,112 calls),
  its points 2-tuples (843) or 2-lists (159), and is followed by `hole`,
  `cskHole` (all 93 `hinge`, angle 82), `cboreHole` (28 `manifold_block`)
  or `circle` (56 `pcb_standoff_plate`, then `extrude`). `hole(d, depth=)`
  is 54 `hex_standoff` from a `<Y` face. 138 programs write
  `faces(sel).faces(sel)` with one selector twice (`mounting_plate` 59,
  `connecting_rod` 45, `manifold_block` 34).
- **`Workplane.pushPoints(points)`**, `census_form("Workplane.pushPoints",
  [("list",)])`: a stack of points in the plane's local coordinates (as a
  `moveTo` point is today); an element that is not two or three numbers
  ends `unsupported_api`. The rest (an empty list, 3-tuples) as step 1 reads.
- **`Workplane.hole(diameter, depth=None)`**, declared `("num",)` with
  keyword `depth: ("num",)`: a cylinder of `depth` from each point against
  the normal, the box diagonal when `None` (today's rule). Several points cut
  in one `Solid.cut(*tools)`, as CadQuery's `cutEach`. `hole(1, 2)` stays
  out (`tests/test_cq.py:899` keeps it; the census writes depth only as a
  keyword).
- **`Workplane.cboreHole` / `Workplane.cskHole`**, `(num, num, num)`: the
  bore and its counterbore or cone as separate tools, every point's pieces in
  the one cut `hole` makes (ADR-0018 rule 3: CadQuery fuses them, and arris
  refuses the cut of that fused tool flush with the face; the cone is a
  revolved right triangle, arris having no cone primitive).
- **Contexts**: `faces(sel)` on a `Faces` stack ranks the stacked faces only
  (today `unsupported_api`, `cq/_workplane.py` `faces`); `circle` on a
  stack of points draws one circle per point, extruded and fused with the
  chain's solid. Each lifted where it agrees with the oracle, else refused.
- **ADR-0018** (step 1): CadQuery's point stacks and bore tools over arris,
  read in cadquery 2.3.0 (`pushPoints`, `hole`, `cboreHole`, `cskHole`,
  `cutEach`, `largestDimension`) and on the oracle.
- **Unsupported-example hits** (grep of `tests/`, `src/`, `docs/`):
  `tests/test_cq.py:899` stays (above); the calibration fixtures
  `fidelity/agree-box-*-hole*` write `pushPoints` but use the bare
  `cq.Workplane()` and stay refused. `fixture_cases.c1_subset()` drops the
  four forms until step 8.
- `Subset`'s doctest count and ARCHITECTURE's "20 API forms" move to 23: the
  three new forms (`pushPoints`, `cboreHole`, `cskHole`) are the additions;
  `hole` is one of the 20 already and gains a keyword.
- `fixture_cases.c2_baseline_subset()` (step 2): `cq.subset()` less the new
  forms and `hole`'s keyword, which `test_c2_baseline` compares the committed
  reach to until step 8 returns it to `cq.subset()`.
- `hole` measures its depth on arris's box less its 2e-7 padding
  (`_BOUNDS_PAD`), the diagonal CadQuery's tight box gives: a bore that ends
  inside the part (`ok-push-points-3-tuple-above`) was 5e-7 too long.

## Steps

Grades are tiers (`.agents/tiers.md`): **[1]** routine; **[2]** careful
within a given design; **[3]** unproven semantics, established here.

- [x] Step 1 **[3]** — ADR-0018 from CadQuery's source and the oracle, the
  kernel risk first: a spike that cuts a revolved countersink and
  counterbore tool from a box in arris against their closed forms (cone
  frustum, stepped cylinder). Constructions with closed forms, each run on
  the oracle and recorded under `tests/fixtures/holes/`: points (tuple,
  list, 3-tuple, empty), `hole` with depth inside and past the part,
  `cboreHole`, `cskHole` (82° and 90°) at one and several points, and
  `faces(sel).faces(sel)`.
- [x] Step 2 **[2]** — `pushPoints` and `hole(d)` on its points. Fixtures
  `cq/ok-push-points-*` (one point, several, lists, after each selector),
  one corpus program as written (`dog_bone`); `hypothesis`: a random box,
  face and non-overlapping points, volume `V − n·π d²/4·h`.
- [ ] Step 3 **[2]** — `hole(d, depth=)`: blind, past the part, on points;
  `runtime-` fixtures for the depths CadQuery refuses (step 1); the corpus
  `hex_standoff` as written; the property gains a depth.
- [ ] Step 4 **[2]** — `cboreHole` per ADR-0018: `ok-cbore-*` with closed-form
  volume and centroid, a `manifold_block` as written, `runtime-` for the
  arguments CadQuery refuses; a property over random bores.
- [ ] Step 5 **[2]** — `cskHole` per ADR-0018, as step 4 (`ok-csk-*`, a
  `hinge` as written, the cone's volume by closed form).
- [ ] Step 6 **[2]** — the contexts, read on the oracle: `faces` on faces,
  `circle` on points then `extrude`, each hole on a compound and after a
  hole; lifted where they agree, else refused, each with its `ok-`,
  `runtime-` or `unsupported-` fixture.
- [ ] Step 7 **[2]** — the measurement: `cq_corpus.py --oracle-rows` on both
  corpora into a scratch out-dir, then `cq_diagnose.py`; in-subset rows by
  class, `cq_bug` and unclassified by family, recorded here. Each cause
  becomes a step 7a, 7b … before step 8, largest first, shrunk to
  `regression/` fixtures and filed with arris where the kernel is at fault.
- [ ] Step 8 **[1]** — the committed re-run of both tables
  (`tests/fixtures/c2/*`, READMEs' figures and digests); `c1_subset()`
  takes the four forms back.

## Acceptance

- `uv run tools/gate.sh` green, with the step fixtures: `cq/ok-push-points-*`,
  `ok-hole-depth-*`, `ok-cbore-*`, `ok-csk-*`, the context fixtures, each
  `runtime-`/`unsupported-` fixture of steps 3 to 6, and the `hypothesis`
  properties of steps 2 to 4.
- Committed tables: BenchCAD reach 6,154/17,900 (or the step-7 figure, with
  its reason, if a declaration had to narrow), CAD-Recode 104/968;
  `in_subset_cq_bug` 0, `in_subset_by_design` 0 and no in-subset row
  unclassified on both; each new `arris_bug` row a `regression/` fixture.

## Docs to update on completion

- `docs/ARCHITECTURE.md` §Dialects (24 forms; `pushPoints`, the holes
  paragraph, `faces` on faces, `circle` on points) and §Fidelity (the C2
  table and this lift's paragraph).
- `docs/ROADMAP.md` §C2 status; `AGENTS.md` current state.
- `CHANGELOG.md` `Unreleased`: the four forms and the refusals a consumer sees.
- `docs/BACKLOG.md`: bundle 2b's line if not yet planned; the chain-context
  line loses `circle` on points.

## Open questions

- ⚠ OPEN: bundle 2 split. The idea's bundle 2 (`docs/ideas/next-lift.md`,
  git) listed `hole(depth=)`, `pushPoints`, `rarray`, `center`, `cutBlind`,
  `polarArray`; the human named `pushPoints`, `cboreHole`, `cskHole` and
  `hole(depth=)`. Agent's pick: the human's four now (a coherent hole family,
  +859; `cboreHole`/`cskHole` are past ADR-0014's knee but cost little once
  `pushPoints` lands), the other four as bundle 2b next. ADR-0014's
  amendment names bundle 2 only as "the other holes and point stacks", so no
  amendment. The human may reorder at review.
- *Settled* (step 1, ADR-0018): the bore tool's construction. Neither one
  revolve nor CadQuery's fuse: each piece its own tool, all in one cut. arris
  refuses the cut of CadQuery's fused tool wherever its end is flush with the
  face (`regression/arris-cut-fused-bore-tool-flush`, strict `xfail`), and
  cuts the pieces, the cone included, to every closed form of step 1
  (`tests/test_hole_probe.py`); a whole-union profile also cuts but needs
  the outline worked out case by case.

# Plan: lift-face-selectors

- Started: 2026-11-14
- Milestone: C2, subset growth (docs/ROADMAP.md §C2), bundle 1 of the knee
- Idea: docs/ideas/next-lift.md (absorbed): bundles of 3–4 items, riskiest
  first; this bundle is `faces(str)`, `workplane()` on a face, the six axis
  selectors and `hole(num)` (Q1 B, Q2 B, Q4 A).

## Goal

`dialect="cq"` runs `faces(sel)` for `>X <X >Y <Y >Z <Z`, `workplane()` on
the faces it selects and `hole(diameter)` as CadQuery 2.3.0 builds them;
`cq.subset()` declares `Workplane.faces(str)`, `Workplane.hole(num)` and
the six selectors. Measured at planning time against today's subset,
BenchCAD reach goes from 4,345 to 5,295 of 17,900 (+950); CAD-Recode
writes no selector and stays at 104 of 968. Every one of the 950 writes
exactly one `.faces(sel).workplane()`, followed by `hole` (788, 29 of
them after a `<` selector), `circle` (116) or `polygon` (46). An ADR settles how a
CadQuery selector maps onto arris (closing the ⚠ OPEN in
`docs/ARCHITECTURE.md` §Dialects), and ADR-0014 records the bundle order.
Both tables are re-run with the oracle's committed rows and committed, with
0 in-subset `cq_bug` and nothing unclassified in the subset.

## Non-goals

- Other selectors (`|X`, `>Z or <Z`, `XY`, indexed or named ones), `edges`,
  `faces()` without an argument, `workplane(centerOption=…, invert=…,
  origin=…)`, `hole(…; depth=…)`, `pushPoints`, `cboreHole`, `cskHole`:
  later bundles in the order of docs/ideas/next-lift.md's decision.
- The bundles after this one: (2) the other holes and point stacks, (3)
  `edges`/`fillet`/`chamfer`, (4) CAD-Recode's sketch API, (5) the head
  (`slot2D`, `rect`, `mirrorY`, `cutThruAll`, `loft`, `extrude(taper=)`).
- arris code; a kernel capability this plan needs is asked of arris.

## Design deltas

- **`Workplane.faces(selector)`**, `census_form("Workplane.faces",
  [("str",)])`: the faces of the chain's solid that CadQuery's
  `DirectionMinMaxSelector` keeps, as a new private stack object
  (`_Faces`: the solid and its selected faces, in CadQuery's order). The
  ranking (which centre, which tolerance) is ADR-0017's. arris's
  `Selection.extreme` ranks by a face's box centre, CadQuery by its centre
  of mass (`Shape.Center`), so `cq` does not take `extreme` as is.
- **`Subset.selectors`** gains `>X <X >Y <Y >Z <Z`, read by `subset()` from
  one constant beside the decorators (no new public type; the `subset()`
  doctest's `(18, ())` moves).
- **`Workplane.workplane()` on a `_Faces` stack**: CadQuery's rule for one
  face (its centre, `normalAt(centre)`, `_computeXdir`, then
  `ProjectedOrigin`: the parent plane's origin projected onto that plane)
  and for several (coplanar planar faces, else `ValueError`). On a planar
  face only the plane matters; on a curved face the centre places the
  plane, which is what the ⚠ OPEN is about. Decided by step 2's ADR-0017.
- **`Workplane.hole(diameter)`**, `census_form("Workplane.hole",
  [("num",)])`: CadQuery's `hole` bores a cylinder from each stack point
  (the plane's origin on an empty stack) against the plane's normal, as
  long as the solid's bounding-box diagonal, and cuts it from the chain's
  solid (`cutEach`). `cq` builds the same: `Solid.hole(at, d, depth)` with
  a depth past the solid, or the cylinder and `cut`, whichever step 5
  shows equal to the oracle where material lies above the plane.
- **ADR-0017** (step 2): CadQuery's face selectors over arris: the centre
  and tolerance a ranking uses, `workplane()` on one and on several faces,
  where a face's centre of mass comes from (arris has `surface_properties`
  per body, not per face). A named constant for CadQuery's selector
  tolerance (1e-4). If a curved face's centre needs a kernel capability,
  the ask goes to `../arris/docs/ideas/`.
- **ADR-0014**, a dated amendment (step 1): "census order" becomes "the
  knee's items, riskiest bundle first" (docs/ideas/next-lift.md).
- **Unsupported-example hits** (grep of `tests/`, `src/`, `docs/`), moved
  in the lift's step: `tests/test_cq.py:142` (`"faces"` among the unknown
  names) becomes another name; `tests/test_cq.py:897` and `:898`
  (`faces(">Z")`, `hole(1)` in `BAD_CALLS`) become `faces("|Z")` and
  `hole(1, 2)`. `test_reach.py:96–103`, `test_reach_curve.py` and
  `tests/fixtures/reach/out-selector` build their own subsets or measure
  C1's, so they stay. The calibration fixtures with `hole` use the bare
  `cq.Workplane()` and stay refused.
- **`test_c2_baseline`** holds the committed reports to `cq.subset()` less
  this plan's declarations from step 3 until step 8.

## Steps

Grades are tiers (`.agents/tiers.md`): **[1]** routine; **[2]** careful
within a given design; **[3]** unproven semantics, established here.

- [x] Step 1 **[1]** — ADR-0014's dated amendment, and the order's wording
  in ROADMAP §C2, AGENTS.md and ARCHITECTURE §Dialects.
- [x] Step 2 **[3]** — what the 950 select, on the oracle. A probe under
  `tools/` runs each program cut after its `.faces(sel)` in the oracle
  worker and records the selected faces (count, surface type, centre,
  normal at the centre) and the new plane (origin, x, normal). Commit its
  counts by family and write ADR-0017 from them and from constructed cases
  (a box, a cylinder's side, a partial cylinder, two coplanar faces, a
  near tie); its evidence is the probe's committed rows.
  Done: `tools/cq_selector_probe.py`, rows in `tests/fixtures/selectors/`; all
  950 keep planar faces normal to the axis (40 keep two), no near tie.
- [x] Step 3 **[2]** — `faces(sel)` and `workplane()` on one planar face.
  Declare `faces(str)` and the selectors; move the hits. Fixtures
  `cq/ok-faces-*`: each selector on a box, a transformed box and a
  cylinder, followed by `circle`/`polygon` and `extrude` (closed forms;
  `polygon` pins the x direction), one corpus program as written. A
  `hypothesis` property: a random box on a random named plane, every
  selector, the new plane's origin and axes against the closed form.
  *Settled* (step 3): the stack object is `Faces` in `cq/_selector.py`
  (private, not `_Faces`); the cylinder fixtures use the selectors along
  the cylinder's own axis (`XY`, `YZ`, `XZ` planes), since its others end
  `unsupported_api` (ADR-0017). The hits the plan said stay did not:
  `test_reach.py` (three tests), `test_reach_curve.py` and
  `reach/out-selector` read `cq.subset()`, so they moved to `|Z`/`edges`;
  `fixture_cases.c1_subset()` and the new `c2_baseline_subset()` drop
  `faces` and the selectors, and `tools/cq_selector_probe.py` reads its 950
  against `before_subset()`.
- [x] Step 4 **[3]** — `workplane()` on a curved face and on several faces,
  as ADR-0017 says, with step 2's shapes as fixtures (closed forms where
  the centre has one, the oracle's plane otherwise, ADR-0005).
  *Settled* (step 2): ADR-0017 rules 4 and 5 make this step coplanar faces
  at one offset (the 40 `connecting_rod` shape) as `ok-`, and as refusals or
  CadQuery's `ValueError` the half cylinder, the full cylinder's `>X`, the
  triangular prism and the near ties (`unsupported-` / `runtime-`
  fixtures, each beside its oracle record in `tests/fixtures/selectors/
  constructed.json`); no curved-face plane is built. None of the 950 is
  affected, so the acceptance stands.
  *Settled* (step 4): `cq/_selector.plane_on_faces`. At their recorded
  size the cylinder's `>X` and the triangular prism end at `faces` (the
  estimate's margin), so the two `runtime-faces-workplane-*` fixtures are
  small variants (0.2 × r 0.1 cylinder; 0.4 × 0.3 prism turned 30° about x)
  with their own oracle reports, CadQuery's words matched. The half
  cylinder is rewritten in the subset (`box(centered=)`, `mirror` outside
  it). `near-tie-outside` and `-chain` keep one face on both sides and are
  held as plane tests against their records. Curved faces of one kind and
  size are refused even where they are two faces in both kernels (CadQuery
  would raise): an arris split cannot be told from them.
- [x] Step 5 **[2]** — `hole(d)`. Fixtures `cq/ok-hole-*`: through a box
  from each selector, from a face with material above its plane, through a
  compound, a corpus program as written; `runtime-hole-*` for `d ≤ 0`. A
  property: random box, face and diameter, volume `V − π d²/4 · depth` and
  centroid by closed form. Declare the form; move `test_cq.py:898`.
  *Settled* (step 5): `Workplane.hole` cuts `Solid.cylinder(at, -normal, r,
  diagonal)` from the chain's solid rather than calling `Solid.hole`, whose
  numeric depth gave a volume 8e-5 off the closed form. `hole(0)` is a no-op
  (the oracle's result is the box) and `hole(-1)` is `runtime`. A cylinder that
  swallows the part is an oracle `crash` row (its empty shape has no box) and
  ours an `arris_refusal`, so no fixture holds that one against the oracle.
  A stack holding anything (a `moveTo` point, a solid) is refused until
  step 6 reads those contexts.

- [ ] Step 6 **[2]** — contexts, read on the oracle: `faces` on an empty
  stack, a pending wire, a compound; `workplane()` then `offset=` on a face;
  `hole` on a solid's stack (no `workplane`), on a `moveTo` point, wider
  than the face. Each lifted when it agrees, else refused, with its
  `ok-`, `runtime-` or `unsupported-` fixture.
- [ ] Step 7 **[2]** — the measurement. `cq_corpus.py --oracle-rows` on both
  corpora into a scratch out-dir, then `cq_diagnose.py`: in-subset rows by
  class, `cq_bug` and unclassified by family, recorded in *Open questions*.
  Each cause becomes a step 7a, 7b … before step 8, largest first, shrunk
  to `regression/` fixtures (the 25 known `bearing_retainer_cap`
  `OpInternalError` rows among them, filed with arris).
- [ ] Step 8 **[2]** — commit the re-run: `tests/fixtures/c2/*` as
  `fixtures:` with the new figures, both READMEs, `test_c2_baseline`'s
  figures, its subset back to `cq.subset()`.

## Acceptance

- `uv run --extra corpus tools/cq_corpus.py --corpus benchcad --verdicts
  tests/fixtures/c1/verdicts.json tests/fixtures/c2/benchcad/verdicts.json
  --oracle-rows tests/fixtures/c2/benchcad/oracle.jsonl.gz` reports reach
  5,295/17,900 (or step 7's figure, named); `in_subset_cq_bug` 0 and 0
  unclassified in the subset; the 100 `lobed_knob` rows still `arris_bug`;
  the oracle digest `e9925835…73157` unchanged unless a timeout re-ran
  (named).
- `… --corpus cadrecode …`: reach 104/968, table digest `24c2f92a…3448`
  unchanged.
- ADR-0017 accepted, the ⚠ OPEN on selectors gone from
  `docs/ARCHITECTURE.md`; ADR-0014 amended.
- The `cq/ok-faces-*`, `ok-hole-*` and step 6 fixtures, the two properties
  and the moved unsupported-example tests pass; the gate is green.

## Docs to update on completion

- `docs/ARCHITECTURE.md` §Dialects: `faces`, the six selectors,
  `workplane()` on a face, `hole`; the ⚠ OPEN replaced by ADR-0017; the C2
  tables (§Fidelity) with step 8's figures.
- `docs/ROADMAP.md` §C2 status line; `AGENTS.md` current state (reach).
- `docs/adr/README.md` index: ADR-0017.
- `CHANGELOG.md` (Unreleased): the calls and six selectors; `PROVENANCE.md`:
  `faces`, `DirectionMinMaxSelector`, `workplane`, `hole`.
- `GLOSSARY.md`: sharpen **Selector string** if ADR-0017 names a term (the
  face centre a ranking uses).

## Open questions

- *Settled* (step 2, ADR-0017): a curved face's centre of mass is not
  computed. A ranking takes exact plane offsets, box bounds or a tessellation
  estimate trusted at a margin; a plane on a curved face is `unsupported_api`.
  The exact per-face area and centre are asked of arris
  (`../arris/docs/ideas/face-surface-properties.md`, BACKLOG).
- ⚠ OPEN: step 7's figures and causes — the agent, step 7.

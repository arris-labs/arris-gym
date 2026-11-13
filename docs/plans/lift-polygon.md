# Plan: lift-polygon

- Started: 2026-11-14
- Milestone: C2, subset growth in reach-curve order (docs/ROADMAP.md §C2)
- Idea: from the human, "BenchCAD's next reach-curve item, polygon, to
  continue C2's growth". Measured at planning time against today's subset,
  `Workplane.polygon(num, num)` is item 1 on BenchCAD's reach curve. The
  target is settled (ADR-0014), and the reach curve sets the order.

## Goal

`dialect="cq"` runs `Workplane.polygon(nSides, diameter)` as CadQuery 2.3.0
builds it, and `cq.subset()` declares the form. Measured at planning time,
BenchCAD reach goes from 4,011 to 4,103 of 17,900 (+92, all `grease_nipple`).
CAD-Recode writes no `polygon`, so it stays at 104 of 968. The 1,662 corpus
calls all write `polygon(6, d)`, after a named plane, a
`workplane(offset=…)`, a `transformed` or a `faces(…).workplane()` (the last
is not in the subset), and then `extrude` the result. Each newly reached
program agrees with the oracle or has a class other than `cq_bug`. Both
corpora's tables are re-run with the oracle's committed rows reused
(`tools/cq_corpus.py --oracle-rows`) and committed.

## Non-goals

- `polygon`'s keywords `forConstruction` and `circumscribed`: the census
  writes neither, and the form check refuses both.
- The other 837 programs that call `polygon`, which still miss other items:
  `faces`/`edges` selectors, `chamfer`, `fillet`, `hole`,
  `extrude(both=)`, `cutThruAll`. Each comes up in curve order.
- BenchCAD's next items (`extrude(both=)` +242, `slot2D` +143, `rect` +127,
  `loft(combine=)` +272): the following plans.

## Design deltas

- **`Workplane.polygon(nSides, diameter)`**, declared by
  `census_form("Workplane.polygon", [("num",)] * 2)`. It is a pending closed
  sketch, like `circle`: `plane.polygon(points)` with CadQuery's vertices,
  `radius = diameter / 2.0`, `o = (2.0 * math.pi / nSides) * i`, and the point
  `(radius * math.cos(o), radius * math.sin(o))` for `i` in `0..nSides-1`. The
  first vertex lies on local +x. CadQuery's closing point `i = nSides` is
  dropped, since `Loop.polygon` closes the loop. The expression and its
  order are CadQuery's (`cadquery/cq.py`), so the vertices carry its bits on
  the same libm. This is libm on a body's path, as `transformed`'s
  `rotated` already is (ARCHITECTURE §Determinism, "Measured"). The C2
  digest check across architectures covers it.
- **Placement** follows `circle`'s stack rule (CadQuery's `eachpoint`): an
  empty stack centres it on the plane's origin. A stack holding only a
  `moveTo` point centres it on that point, in the plane's axes. Any other
  stack is `UnsupportedApi`, as `circle` refuses it. Step 2 reads each of
  these on the oracle.
- **Arguments.** Each corpus call writes `nSides` as the integer 6. CadQuery
  does not check `nSides` itself. `range` refuses a float, `2π/0` raises,
  and a count below 3 or a diameter ≤ 0 builds whatever `makePolygon` makes
  (a negative diameter turns the polygon by π). Step 2 reads each case on the
  oracle and decides it (Q1).
- **No public type or API change.** `cq.subset().forms` gains one
  declaration. CHANGELOG gets a bullet, and `PROVENANCE.md` names CadQuery's
  `Workplane.polygon` (read, not copied).
- **Unsupported-example hits** (grep of `tests/`, `src/`, `docs/` for
  `polygon` used as an unsupported name): none. The hits are all
  `arris.build`'s own `polygon(points)` or the census fixture
  `aliased-import`, which is not a refusal.
- **Planning-time probe.** The 92 `grease_nipple` programs, with each
  `polygon` rewritten as the `polyline(...).close()` of the vertices above,
  all end `ok` under `cq`. Volume and area are within 7e-16 relative of the
  committed oracle rows, with equal face counts. There is no known risk of an
  `arris_refusal`.

## Steps

Grades are tiers (`.agents/tiers.md`): **[1]** routine; **[2]** careful within
a given design; **[3]** unproven semantics, established here.

- [x] Step 1 **[3]** — the lift. Add `polygon` on an empty stack and on a
  `moveTo` point, on `XY`, `YZ`, `XZ` and `ZX`, and after `transformed` and
  `workplane(offset=)`, then extrude it and fuse it with a chain solid.
  Fixtures `cq/ok-polygon-*` take their expectations from closed forms (the
  n-gon's area `(n/2) r² sin(2π/n)`, `(3√3/2) r²` for the hexagon, times the
  height; the centroid; the bounds, with the first vertex on +x), each
  checked against the oracle. Add `ok-polygon-grease-nipple`, a corpus
  program as written. A `hypothesis` property ranges over n, diameter,
  plane and centre and checks against the closed form. Declare the form, and
  have `test_c2_baseline`'s `tables_subset()` hold the committed reports to
  today's subset less `polygon`.
- [x] Step 2 **[3]** — the contexts and arguments. Run `polygon` on each
  other last object, on both sides: a solid, a compound, a closed sketch, a
  drawn path, a pending circle. Also run `nSides` as 6.0, 2, 0 and -6, and a
  diameter of 0 and of -d. Each case is lifted when it agrees and refused
  otherwise, with an `ok-`, `runtime-` or `unsupported-` fixture. Settle Q1.
- [x] Step 3 **[2]** — the measurement. Run `cq_corpus.py --oracle-rows` on
  both corpora into a scratch out-dir, then `cq_diagnose.py` over the new
  BenchCAD table, to get the in-subset rows by class and the `cq_bug` rows by
  message. Any cause other than agreement becomes a step before step 4,
  largest first, shrunk to `regression/` fixtures, or becomes Q2 with the
  reach it costs.
- [x] Step 4 **[2]** — commit the re-run. The step 3 run (BenchCAD and
  CAD-Recode, `--oracle-rows`, the C1 verdicts and BenchCAD's own) is the
  re-run. Copy its outputs into `tests/fixtures/c2/*` as `fixtures:` with
  the new figures, update both READMEs and `tests/test_c2_baseline.py`'s
  figures, and return `tables_subset()` to `cq.subset()`.

## Acceptance

- `uv run --extra corpus tools/cq_corpus.py --corpus benchcad --verdicts
  tests/fixtures/c1/verdicts.json tests/fixtures/c2/benchcad/verdicts.json
  --oracle-rows tests/fixtures/c2/benchcad/oracle.jsonl.gz` reports:
  - reach 4,103/17,900, or step 3's measured figure if it differs (named);
  - the 92 new `grease_nipple` rows agree;
  - `in_subset_cq_bug` 0 and 0 unclassified in the subset;
  - the 100 `lobed_knob` rows still `arris_bug`;
  - the oracle digest `e9925835…73157` unchanged, unless a timeout re-ran
    (named).
- `… --corpus cadrecode --oracle-rows …/cadrecode/oracle.jsonl.gz`: reach
  104/968, with its table digest unchanged.
- The `cq/ok-polygon-*`, `runtime-polygon-*` and `unsupported-polygon-*`
  fixtures and the closed-form property pass. Every existing `cq/` fixture
  passes unchanged (no unsupported-example hits). The gate is green.

## Docs to update on completion

- `docs/ARCHITECTURE.md` §Dialects: `polygon` in the call list (18 forms),
  with its vertices, placement and refusals. §The oracle, "The C2 tables":
  the figures for both corpora and a `polygon` paragraph.
- `docs/ROADMAP.md` §C2 status line: the new reach.
- `AGENTS.md` current state: the reach line.
- `tests/fixtures/c2/{benchcad,cadrecode}/README.md`: the re-run's figures.
- `tests/fixtures/cq/README.md`: the `polygon` fixtures.
- `CHANGELOG.md` §Unreleased: `polygon` under `dialect="cq"`.
- `PROVENANCE.md`: CadQuery's `Workplane.polygon`.
- `docs/BACKLOG.md` §Findings: any arris finding step 3 turns up.

## Open questions

- *Settled* (step 2): Q1 — `cylinder`'s rule, read on the oracle. `nSides`
  of 0 and 6.0 raise CadQuery's own `ZeroDivisionError` and `TypeError`,
  which `cq` raises from the same expression. -6, 1 and a zero diameter
  raise `StdFail_NotDone`; `cq` ends each `runtime` (`ValueError`), where
  the kernel refused the profile before. `polygon(2, d)` builds a
  zero-volume solid the oracle's checker passes (`ok`); `cq` ends it
  `runtime` too, and the row is `cq_bug`, not `by_design`: the form is
  admitted, and ADR-0012 classes a declined behaviour of an admitted form
  `cq_bug` until fixed (`cylinder(h, 0)` and `sphere(0)` differ: there the
  oracle answers `invalid`). It is held by the strict `xfail`
  `regression/cq-polygon-two-sides` and a `docs/BACKLOG.md` line. A negative diameter builds the polygon turned by π
  on both sides and agrees (`ok-polygon-negative-diameter`). The five other
  contexts are built by CadQuery on the object's `Center()` and stay
  refused (`unsupported-polygon-*`).
- *Settled* (step 3): Q2 — none. The re-run (oracle rows reused) gives
  BenchCAD reach 4,103/17,900 (4,011 + 92), CAD-Recode 104/968. Against the
  committed table exactly 92 rows change, all `grease_nipple`, from `cq_bug`
  (`unsupported_api`) to agree: 2,826 agree, in-subset classes unchanged
  (`arris_bug` 100, `arris_refusal` 852, `occt_wrong` 325, `cq_bug` 0,
  `by_design` 0), in-subset unclassified 0. The 204 unclassified rows are the
  same ones, all outside the subset. `cq_diagnose.py` diagnoses 0 in-subset
  `cq_bug` programs. The 100 `lobed_knob` rows are still `arris_bug`. The
  BenchCAD oracle digest `e9925835…73157` is the committed one (the 31
  `double_simplex_sprocket` timeouts timed out again); the table digest is
  `db6adfc4…de2cee`. CAD-Recode's table digest `24c2f92a…3448` and oracle
  digest `8d28ce11…195f` are the committed ones. Step 4 needs no cause step.

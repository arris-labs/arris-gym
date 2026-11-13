# Plan: lift-extrude-both

- Started: 2026-11-14
- Milestone: C2, subset growth in reach-curve order (docs/ROADMAP.md §C2)
- Idea: from the human, `/plan lift-extrude-both`. Measured at planning time
  against today's subset, `Workplane.extrude(num; both=bool)` is item 1 on
  BenchCAD's reach curve (+242), before `slot2D` (+143), `rect` (+127) and
  `loft(combine=)` (+272). The target is settled (ADR-0014), and the reach
  curve sets the order.

## Goal

`dialect="cq"` runs `Workplane.extrude(distance, both=…)` as CadQuery 2.3.0
builds it, and `cq.subset()` declares the form. Measured at planning time,
BenchCAD reach goes from 4,103 to 4,345 of 17,900 (+242: `hex_key_organizer`
117, `u_bolt` 66, `j_hook` 59). CAD-Recode writes no `both=`, so it stays at
104 of 968. Every corpus call writes `extrude(<positive number>, both=True)`
on a pending `polygon(6, d)` or a closed hexagonal `polyline`, after a
`transformed`. Each newly reached program agrees with the oracle or has a
class other than `cq_bug`, and none is unclassified. Both corpora's tables
are re-run with the oracle's committed rows reused (`tools/cq_corpus.py
--oracle-rows`) and committed.

## Non-goals

- `extrude`'s other keywords (`combine`, `clean`, `taper`, `until`) and the
  positional `extrude(num, bool)`. CadQuery's second positional argument is
  `combine`, not `both`, so that form stays refused.
- The other 2,325 programs that write `both=`, which still miss other items
  (`handwheel`, `wing_nut`, `pillow_block`, …): each comes up in curve order.
- BenchCAD's next items (`slot2D` +143, `rect` +127, `loft(combine=)` +272,
  `mirrorY` +64, `extrude(taper=)` +57): the following plans.

## Design deltas

- **`Workplane.extrude(distance, both=False)`**, declared by
  `census_form("Workplane.extrude", [("num",)], keywords={"both": ("bool",)})`
  (any subset of the keywords, so `extrude(num)` keeps its form). CadQuery's
  `_extrude` makes `s1 = extrudeLinear(face, n·d)` and, with `both`, fuses it
  (`glue=True`) with `extrudeLinear(face, -n·d)`, and `clean()` merges the two
  halves' side faces. That is `distance` to each side of the plane, a prism
  of height `2|d|`. arris's `Sketch.extrude(distance, both=True)` is the same
  solid in one sweep ("with `both`, `distance` to each side of the plane"),
  so `cq` passes `both` through. Step 1 checks volume, centroid, bounds and
  **face count** against the oracle, so the one prism matches CadQuery's
  cleaned glue.
- **Arguments.** `both=False` is `extrude(d)`. A negative `d` with `both`
  builds the same prism. `d = 0` (with or without `both`) is read on the
  oracle in step 2 and decided by `cylinder`'s rule (Q1).
- **No public type or API change**; the `extrude` declaration gains one
  keyword (CHANGELOG bullet; `PROVENANCE.md` names `Workplane._extrude`).
- **Unsupported-example hits** (grep of `tests/`, `src/`, `docs/` for
  `both=` used as an unsupported name), each moved in step 1:
  `tests/test_reach.py:82` turns `True`, with `extrude(num; taper=num)`
  added as `False`; `tests/test_cq.py:728` and `:828` become
  `extrude(1, taper=5)`. `census/keyword-forms` and the GLOSSARY/ADR-0003
  examples do not call the form unsupported, so they stay.
- **`test_c2_baseline`'s `tables_subset()`** holds the committed reports to
  today's subset with `extrude`'s declaration less `both` until step 5.
- **`tools/cq_closed_forms.py`, the hook shape** (step 4, if step 3 finds
  the 125 new `u_bolt`/`j_hook` rows off like the 261 committed ones): it
  gains a hexagonal prism under the box (`polygon(6, d)` or a closed
  six-point `polyline`, `extrude(e, both=True)`). It is accepted only with
  the hexagon inside the box's footprint and its top between the box's
  faces; otherwise the tool raises. The union then adds the prism below the
  box: volume `A·depth`, area `P·depth` (its bottom replaces the box-bottom
  patch it covers), centroid and bounds elementary; `A` and `P` by the
  shoelace formula over the vertices.

## Steps

Grades are tiers (`.agents/tiers.md`): **[1]** routine; **[2]** careful within
a given design; **[3]** unproven semantics, established here.

- [x] Step 1 **[2]** — the lift. Pass `both` through to arris. Fixtures
  `cq/ok-extrude-both-*`: a circle and a hexagon on `XY`, a polygon on `YZ`
  after `transformed`, a negative distance, `both=False`, and a `both`
  prism fused with and cut from a chain's box. Each takes its expectations
  from closed forms (the volume `2|d|·A`, the centroid on the plane, the
  bounds `±|d|` along the normal) and its face count from the oracle. Add
  `ok-extrude-both-hex-key-organizer`, a corpus program as written. Add a
  `hypothesis` property over the profile, distance, sign and plane. Declare
  the form and move the three unsupported-example hits.
- [ ] Step 2 **[2]** — the arguments and contexts. Run `d = 0` with and
  without `both` on both sides, and `both` on each stack `extrude` refuses
  today (empty, a solid, a drawn path, two sketches). Each case is lifted
  when it agrees and refused otherwise, with an `ok-`, `runtime-` or
  `unsupported-` fixture. Settle Q1.
- [ ] Step 3 **[2]** — the measurement. Run `cq_corpus.py --oracle-rows` on
  both corpora into a scratch out-dir, then `cq_diagnose.py` over the new
  BenchCAD table, to get the in-subset rows by class and the `cq_bug` and
  unclassified rows by family. Record the figures in Q2. Any cause other
  than agreement or step 4's hook rows becomes a step before step 5,
  largest first, shrunk to `regression/` fixtures, or becomes Q2 with the
  reach it costs.
- [ ] Step 4 **[3]** — the hook rows. If step 3 leaves `u_bolt`/`j_hook`
  rows unclassified, extend the hook closed form with the hexagonal prism
  (Design deltas). `tests/test_cq_closed_forms.py` holds it to arris's
  measures on constructed programs (`polygon` and `polyline` hexagons, one
  and two cylinders) inside ADR-0005's tolerance. Run the tool and append
  its verdicts to `tests/fixtures/c2/benchcad/verdicts.json`, each checked
  by `compare` (arris on the closed form, Open CASCADE off it).
- [ ] Step 5 **[2]** — commit the re-run. Re-run step 3 with step 4's
  verdicts (BenchCAD and CAD-Recode, `--oracle-rows`, the C1 verdicts and
  BenchCAD's own). Copy its outputs into `tests/fixtures/c2/*` as
  `fixtures:` with the new figures, update both READMEs and
  `tests/test_c2_baseline.py`'s figures, and return `tables_subset()` to
  `cq.subset()`.

## Acceptance

- `uv run --extra corpus tools/cq_corpus.py --corpus benchcad --verdicts
  tests/fixtures/c1/verdicts.json tests/fixtures/c2/benchcad/verdicts.json
  --oracle-rows tests/fixtures/c2/benchcad/oracle.jsonl.gz` reports:
  - reach 4,345/17,900, or step 3's measured figure if it differs (named);
  - the 117 new `hex_key_organizer` rows agree, or each has a class other
    than `cq_bug` (named in Q2);
  - the 125 new `u_bolt`/`j_hook` rows agree or are `occt_wrong` by closed
    form;
  - `in_subset_cq_bug` 0 and 0 unclassified in the subset;
  - the 100 `lobed_knob` rows still `arris_bug`;
  - the oracle digest `e9925835…73157` unchanged, unless a timeout re-ran
    (named).
- `… --corpus cadrecode --oracle-rows …/cadrecode/oracle.jsonl.gz`: reach
  104/968, with its table digest `24c2f92a…3448` unchanged.
- The `cq/ok-extrude-both-*` fixtures (and step 2's `runtime-`/`unsupported-`
  ones), the closed-form property and step 4's closed-form tests pass. The
  three moved unsupported-example tests pass in their new form, and every
  other `cq/` fixture passes unchanged. The gate is green.

## Docs to update on completion

- `docs/ARCHITECTURE.md` §Dialects: `extrude`'s `both=` (each side of the
  plane, CadQuery's glue and clean as one prism) and its refusals. §The
  oracle, "The C2 tables": the figures for both corpora and an
  `extrude(both=)` paragraph.
- `docs/ROADMAP.md` §C2 status line: the new reach.
- `AGENTS.md` current state: the reach line.
- `tests/fixtures/c2/{benchcad,cadrecode}/README.md`: the re-run's figures,
  and BenchCAD's `occt_wrong` count by family.
- `tests/fixtures/cq/README.md`: the `extrude-both` fixtures.
- `tools/cq_closed_forms.py` module docstring: the hook's hexagonal prism.
- `CHANGELOG.md` §Unreleased: `extrude(…, both=True)` under `dialect="cq"`.
- `PROVENANCE.md`: CadQuery's `Workplane._extrude`, `both` branch.
- `docs/BACKLOG.md` §Findings: any arris finding step 3 turns up.

## Open questions

- ⚠ OPEN: Q1 — `extrude(0)` and `extrude(0, both=True)`. The agent decides
  by step 2, by `cylinder`'s rule: read on the oracle, and `cq` ends
  `runtime` where the oracle raises or answers `invalid`. If the oracle
  answers `ok`, the row is a counted `cq_bug` with a strict `xfail`
  regression fixture (ADR-0012), as `polygon(2, d)` is.
- ⚠ OPEN: Q2 — what the re-run finds. The agent records it by step 3: the
  in-subset rows by class, which rows step 4 must class, and any other
  cause with the reach it costs.
- ⚠ OPEN: Q3 — whether every new hook row fits step 4's shape. The agent
  decides by step 4. A program outside the shape (the hexagon not inside
  the box, or a third solid) is named here with its count, and gets its own
  closed form or a step before step 5. It is never left unclassified.

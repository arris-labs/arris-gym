# Plan: face-centre-of-mass

- Started: 2026-11-17
- Milestone: C2, the knee's selectors and "no in-subset `cq_bug`" (docs/ROADMAP.md, ADR-0014)
- Idea: the backlog line, verbatim: "arris 0.11.1 gives a face's exact area and
  centre of mass (`Model.surface_properties` takes a `Face`): replace ADR-0017's
  tessellation estimate and its margin with it, and lift `workplane()` on a
  curved face and on a near tie where the two kernels split faces alike
  (ADR-0017 rules 2, 4 and 5) … unblocks the 6 `connecting_rod` in-subset
  `cq_bug` rows only together with the cylinder side that arris splits …:
  ask arris or merge the halves in `cq` before ranking". Merged in `cq`
  (step 4): CadQuery's own `clean()` does the same merge.

## Goal

`faces(sel)` ranks every face by arris's per-face centre of mass
(`Model.surface_properties(face).centroid`), never by a tessellation, so
ADR-0017's estimate, its margin, the finer pass and the size-dependent
outcomes of its amendments are gone. Faces of one surface that share an edge
rank and stand on the stack as one **unified face**, as CadQuery's `clean()`
(`ShapeUpgrade_UnifySameDomain`) leaves them. `workplane()` lifts on a near
tie of parallel planes (the area-weighted offset), on planar faces whose
co-planarity needs their centres, and on one curved face of a cylinder, cone,
sphere or torus. The strict `xfail` on
`regression/cq-workplane-on-a-cylinder-face-split-at-its-seam` is lifted,
and the C2 tables, re-run, count 0 in-subset `cq_bug` on both corpora.

## Non-goals

- Edge keys: arris gives no per-edge centre of mass, so ADR-0020's estimate stays.
- `workplane()` on an elliptic cylinder or a NURBS face, and on opposite
  normals (CadQuery's face order): still `unsupported_api`.
- `workplane(centerOption=…)` other than the default; `clean=False`.
- Any arris ask: the merge is CadQuery's semantics, so it is absorbed in `cq`.

## Design deltas

- **ADR-0022 (step 2)**, "a `cq` face key is arris's centre of mass, and faces
  of one surface that share an edge are one face", amends ADR-0017 rules 2, 4
  and 5 and both amendments; ADR-0017 gains a one-line amendment pointing to it.
- **Face key.** A planar face normal to the axis keeps its exact plane offset.
  Every other face's key is `surface_properties(face).centroid·axis`, a
  quadrature, so it is an interval `_CENTRE_ERROR` wide, measured by step 1
  (relative to the face's √area, as arris's own tests hold it), through the
  existing `_pick_widths`. `_estimates`, `_ESTIMATE_*`, `_REFINED_*` and the
  second pass go. See the settled box pre-filter decision below.
- **Unified face.** Faces of one surface (same kind, frame and size within
  the model's tolerances, `_surely_apart` negated) joined through shared
  edges are one: key from the area-weighted centroid, kept or dropped
  together. `Faces.faces` becomes `Faces.groups: tuple[tuple[arris.Face, ...],
  ...]` (private type). A second `faces(sel)` ranks the groups;
  `edges_of_faces` leaves out an edge both of whose faces are in one group
  (Open CASCADE has no such edge after `clean()`).
- **Rule 4.** Parallel planes, one normal, offsets apart within the cluster:
  the plane at the area-weighted offset (`surface_properties(face).area`).
  Planar faces not normal to the axis: `_isCoPlanar` with their centres,
  decided only where it holds for every choice of first face, else
  `unsupported_api`.
- **Rule 5.** One unified curved face: CadQuery's plane through its centre,
  normal at the centre's foot on the untrimmed surface (closed form per kind,
  oriented outward by the face's sense), x by `_computeXdir`, origin the
  parent's projected. A centre with no unique foot (on a cylinder's axis, a
  sphere's centre) gives what the oracle gives (step 1 records the status
  and words).
- **Moved "unsupported" examples** (grep of `does not give`, `centre of a
  face`, `workplane on a cylinder`, `different offsets`, `their centres`):
  `tests/fixtures/cq/unsupported-faces-{cylinder-side,half-cylinder,near-tie,triangular-prism}`,
  `tests/test_cq_faces.py` (the size-dependent cases), the regression fixture;
  each is renamed to its new status in the commit that lifts it.
- **Foot band (step 2's ADR-0022, rule 4)**: a centre on a curved face's axis (or the
  sphere's centre, the torus's tube circle) has no foot: `runtime` with the oracle's
  words where d ≤ `_CENTRE_ERROR`·√area, `unsupported_api` up to `_FOOT_MIN`·√area
  (1e-3, step 6 measures it), the closed-form foot beyond. Private constants.
- **Glossary**: *Face key* and *Unified face*, new (written in step 2).

## Steps

Grades: **[1]** routine; **[2]** careful, a numeric, geometric or semantic
case within a given design; **[3]** unproven. The grade is the tier
(`.agents/tiers.md`). **[conductor-run]**: a run past 110 s.

- [x] Step 1 **[3]** — The evidence. `tools/cq_selector_probe.py --constructed`
  gains: the half cylinder, the seam-split ring (the regression's shape), a
  cylinder side cut by a through slot into two disjoint faces, the near ties
  of ADR-0017, two slanted planar faces, and `workplane()` on an outer
  cylinder, a bore, a cone, a sphere and a torus face, plus a centre on an
  axis. Oracle records into `tests/fixtures/selectors/constructed.json`;
  `tests/test_selector_probe.py` holds each against its closed form, and
  arris's per-face centroid against the same, which measures `_CENTRE_ERROR`.
  It must show Open CASCADE's one face where arris has two sharing an edge,
  and two where they share none; if not, stop and re-plan.
- [x] Step 2 **[2]** — ADR-0022 from step 1's figures; ADR-0017's pointer
  amendment; `GLOSSARY.md` *Face key*, *Unified face*.
- [x] Step 3 **[2]** — Exact keys in `select_faces`: the estimate gone,
  `_CENTRE_ERROR` in. The size-dependent cases end `runtime` at every size;
  `unsupported-faces-cylinder-side` and `-triangular-prism` move to
  `runtime-…` (CadQuery's `ValueError`). For the prism, this includes the
  signed centre check when it rejects every face order. Hypothesis: on random
  unions of boxes and cylinders, `faces(sel)` agrees with a ranking over
  closed-form centres.
- [x] Step 4 **[3]** — Unified faces: grouping, `Faces.groups`, the second
  `faces` over groups, `edges_of_faces` without inner edges. Lifts the
  regression fixture (strict `xfail` dropped, `fixtures:` in the message) and
  `unsupported-faces-half-cylinder`'s ranking. Fixture: the slot-split side
  ranks as two faces.
- [ ] Step 5 **[2]** — Rule 4 with areas and centres; `unsupported-faces-near-tie`
  becomes `ok-faces-near-tie` (origin z = 1.5000167 by closed form, held by a bore).
- [ ] Step 6 **[3]** — Rule 5 on cylinder, cone, sphere, torus: the foot and
  normal per kind; one `ok-…` fixture each, the plane fixed by a bore by
  construction; the no-foot case as step 1 recorded. Hypothesis: a cylinder
  of random r, h, sense, `>Z` on its half, plane at 2r/π.
- [ ] Step 7 **[2, conductor-run]** — Re-run C2's tables (`tools/cq_corpus.py
  --corpus benchcad|cadrecode --oracle-rows`). Every moved row has a cause;
  the 6 `connecting_rod` rows agree or are classed by closed form; in-subset
  `cq_bug` 0 on both. A row that is not becomes a regression fixture here.

## Acceptance

- The gate green: `tests/test_selector_probe.py` (step 1's constructions,
  closed forms against oracle records and arris), `tests/test_cq_faces.py`,
  the moved `tests/fixtures/cq/*-faces-*` fixtures and the new `ok-` ones,
  the step 3 and step 6 properties.
- `regression/cq-workplane-on-a-cylinder-face-split-at-its-seam` passes
  without `xfail`: `ok`, V = 623.5616, A = 571.8575 (its `expected.json`).
- `tests/fixtures/c2/benchcad` and `cadrecode`: 0 unclassified, in-subset
  `cq_bug` 0 on both; reach not lower than 9,998 and 104; new digests recorded.

## Docs to update on completion

- `docs/ARCHITECTURE.md` §Dialects (the selector paragraphs, ~l. 386 and
  494) and §Fidelity (the "Six in-subset `cq_bug` rows stay" paragraph, the
  tables and digests).
- `docs/ROADMAP.md` C2 status; `AGENTS.md` current state.
- `docs/adr/0014-…`: an amendment closing the 2026-11-14 one, if step 7 holds.
- `docs/BACKLOG.md`: the face-properties line removed.
- `GLOSSARY.md` (step 2); `CHANGELOG.md` `Unreleased`: the lifted
  `workplane()` forms and the statuses that move (`unsupported_api` → `ok`
  or `runtime`); no reward moves.
- `tests/fixtures/cq/README.md`, the regression fixture's README.

## Open questions

- *Settled (ADR-0022 rule 1):* use `_CENTRE_ERROR = 1e-12`. In step 1's
  constructions, both kernels' centre errors were at most 1.5e-16 times
  the square root of the face area.
- *Settled (ADR-0022 rule 2):* unify faces of the same surface and sense
  linked by shared edges. The ring and slot constructions show the merged
  and disjoint cases. The ADR applies the rule across the subset based on
  CadQuery's default cleaning and the topology of the other supported calls.
- *Settled (step 3):* drop the box pre-filter. A local selector timing on a
  box, cylinder and thin-band union put both tested axes under 2.5 ms per
  selection with quadrature. The box adds under 1 ms and the cylinder and
  union get faster. Step 7 checks the cost on both full corpora.
- *Settled (step 3):* the prism's two faces share a zero normal component.
  The signed test of their centres rejects both orders and belongs in step 3
  to reproduce its oracle row. Step 5 still owns placing the plane when
  co-planarity holds and lifting near ties.

- *Settled (step 4):* the slot-split side's two circular boundary arcs each
  remain two fragments in arris after the internal seam is removed. Edge
  selection and blending return `unsupported_api` where they require the
  joined arcs, as held by `unsupported-edges-unified-face-boundary`. A selector
  that can choose its edges independently of the fragments still runs.

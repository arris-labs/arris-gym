# Plan: fidelity-target

- Started: 2026-11-10
- Milestone: the fidelity target, C2's first (cycle C2, docs/ROADMAP.md)
- Idea: docs/ideas/fidelity-target.md (absorbed; its decision, rounds 1 and 2,
  is settled and lives in git at 06de909)

## Goal
C2 has its finish line. An ADR sets the **fidelity target** for each corpus,
BenchCAD `code_gen` and the CAD-Recode validation split, nothing pooled. A
corpus meets it with a **reach** of at least T and no `cq_bug` row among its
**in-subset programs**. Plain agreement over all programs is published beside
it, never targeted. Inside the subset no row is `by_design`: a declined
behaviour leaves the subset and lowers reach. T comes from the measured
**reach curves** of both corpora. A baseline fidelity table over both full
corpora, with the C1 subset, states where C2 starts. The oracle imports
CadQuery once per oracle zygote, not once per program.

## Non-goals
- Growing the subset: lifting a form, a selector or an end form is a later C2
  plan, in census order.
- Meeting the target, and 0 unclassified: C2's acceptance, not this plan's.
- An `arris` bump. Closing the selector `⚠ OPEN` (ARCHITECTURE §cq).
- Verdicts on the baseline's unclassified rows. They are counted, not worked.

## Design deltas
- **The in-subset rule** (step 1, [3]; ADR-0012). A program is in-subset when
  it is parsable, every census `forms` key matches a subset declaration, every
  `selectors` key is admitted (none are yet), its `end_form` is one `cq`
  decides a result from, and `unknown` is empty. A call on a receiver the
  census cannot place is never in-subset. `foreign` calls (stdlib, builtins)
  are admitted when the program worker's Python offers them. The ADR fixes
  that list. The rule is static: it never runs a program.
- **`cq` states its subset as data.** `arris_gym.cq.subset()` returns a frozen
  `Subset` holding the `census_form` declarations (name, positional kinds,
  allowed keywords), the end forms and the admitted selectors, plus
  `Subset.admits(form: str) -> bool`. These are read from the same
  declarations the decorators enforce, so the two cannot drift. `cq` still
  imports only `arris`. `census` and `fidelity` import `cq`, which the layer
  rule allows.
- **`census` keeps per-program rows and computes reach.**
  `census.reach(programs, subset) -> Reach` (frozen) holds the in-subset count
  and stems over all programs, unparsable programs included in the
  denominator. `census.reach_curve(programs, subset) -> ReachCurve` holds reach
  after admitting the next missing API form, one form at a time, in census
  order: the form whose admission makes the most programs in-subset first,
  ties broken by key, so the curve is deterministic. `arris-gym census`
  writes `programs.jsonl.gz` and `reach.json` beside `census.json`.
- **`census.cadrecode`**: the CAD-Recode validation split pinned to a
  revision, read lazily under `[corpus]`. Its row count is checked as
  BenchCAD's is. Its licence (CC BY-NC 4.0) goes on every row. It closes
  ARCHITECTURE §cq's `⚠ OPEN` on CAD-Recode's end forms by measuring them.
- **The oracle zygote** (step 4, [3]; ADR-0013, amending ADR-0004). One
  oracle worker per zygote is exec'd as today: isolated, then `execve`.
  It imports CadQuery once, then forks one child per program under its own
  warden. Each child keeps the namespaces, rlimits, Landlock domain and seccomp
  filter it inherits. A program still meets an interpreter in which nothing
  has been built. An oracle report's bytes do not move.
- **`fidelity.reach_report(table, programs, subset) -> ReachReport`** (frozen,
  public). It holds reach, agreement over all programs, and in-subset rows by
  outcome and class. `in_subset_cq_bug` and `in_subset_by_design` are named
  fields, so the target is two comparisons. Every corpus program has a row,
  and an unparsable program counts as not in-subset.
- **`tools/cq_corpus.py`** generalises `tools/cq_slice.py` and `oracle_run.py`
  to a whole corpus (`--corpus benchcad|cadrecode`). It writes the fidelity
  table, the arris report and the reach report. Committed runs live
  gzipped under `tests/fixtures/c2/<corpus>/`. They hold rows (names,
  SHA-256s, measures, licence), never programs.
- **T** is measured by steps 2, 3 and 6 and written by step 7's ADR-0014. It
  closes SEED.md §9.8's `⚠ OPEN` on the fidelity target and amends ROADMAP
  §C2's "from that number" to "from the reach curves over both corpora".

## Steps
Complexity grades: **[1]** routine, the design says exactly what to write
and the tests are mechanical; **[2]** careful, a numeric, geometric or
semantic case to get right within a given design; **[3]** unproven, an
algorithm, an isolation guarantee or a CadQuery semantic whose correctness
has to be established here. A step's grade is its tier (`.agents/tiers.md`).

- [ ] Step 1 **[3]** — ADR-0012, the in-subset rule. `cq.subset()` /
  `Subset`, read from the decorators' declarations, plus `census.reach`.
  Fixtures by construction under `tests/fixtures/reach/`: an in-subset program
  for each rule clause, and one just outside each. `hypothesis`: a program
  built only from `Subset`'s forms is in-subset. Removing one of its forms
  makes it not. Cross-check: all 300 slice programs are in-subset.
- [ ] Step 2 **[2]** — `census.reach_curve`. `arris-gym census` writes
  `programs.jsonl.gz` and `reach.json`. Committed BenchCAD run in
  `tests/fixtures/c2/benchcad/`, with an equal digest on re-run.
  **If the curve is flat** (no 20 forms reach 25%), stop and ask the human:
  the idea said that would reopen option A.
- [ ] Step 3 **[2]** — `census.cadrecode`: the pin, the adapter, its census
  and reach curve, committed in `tests/fixtures/c2/cadrecode/` with its
  licence beside it. ARCHITECTURE's end-form `⚠ OPEN` is answered by the
  census's `end_form` counts.
- [ ] Step 4 **[3]** — ADR-0013, the oracle zygote. The slice's `oracle.jsonl`
  is byte-equal with and without it. Hostile programs (fork bomb, `os._exit`,
  state left in a module, a write outside reach) each cost one report, and
  the next program on the same zygote sees none of it. Per-program start-up
  is measured and written in the ADR.
- [ ] Step 5 **[2]** — `fidelity.reach_report` / `ReachReport` and
  `tools/cq_corpus.py`. Fixtures by construction: a table of 4 programs with
  their reach, agreement and in-subset classes. On the slice, the report
  equals C1's figures (200 agree, 100 `arris_bug`, reach 300/300).
- [ ] Step 6 **[2]** — the baseline: `tools/cq_corpus.py` over both full corpora
  with the C1 subset, run in the background. Committed under
  `tests/fixtures/c2/`. A gate test re-reads each digest offline. Figures go
  into ARCHITECTURE: reach, agreement, unclassified, timeouts, and in-subset
  `cq_bug`, each over all programs.
- [ ] Step 7 **[2]** — ADR-0014, the fidelity target: T per corpus read from
  the reach curves, the knee and the forms it takes named. It closes SEED.md
  §9.8's `⚠ OPEN` and amends ROADMAP §C2 in the same commit. **The human
  approves T** before it is accepted.

## Acceptance
- `tests/fixtures/reach/` passes, including the `hypothesis` property. The 300
  slice programs are in-subset.
- `reach.json` for both corpora is committed, and re-running the census gives
  equal digests. Every program is counted, unparsable ones as not in-subset.
- The slice's `oracle.jsonl` is byte-equal through the oracle zygote, and each
  hostile oracle program costs one report.
- `ReachReport` over the slice: reach 300/300, 200 agree, `in_subset_cq_bug`
  0, `in_subset_by_design` 0. Over both baselines: one row per corpus
  program, each figure over all programs, timeouts named.
- ADR-0014 accepted with T per corpus. ROADMAP §C2 and SEED.md §9.8's
  `⚠ OPEN` are closed by it.

## Docs to update on completion
- `docs/ARCHITECTURE.md` §The census: per-program rows, reach and the reach
  curve. §cq: the subset as data, and the CAD-Recode end-form `⚠ OPEN`
  answered. §Fidelity: `ReachReport`, the baseline's figures and the oracle
  zygote.
- `docs/ROADMAP.md` §C2: the target's wording, by ADR-0014.
- `GLOSSARY.md`: *Reach curve*, *Oracle zygote*.
- `AGENTS.md` current state: the target set, C2's next is lifting forms.
- `CHANGELOG.md`: `cq.subset()`, `census.reach`, `census.reach_curve`,
  `census.cadrecode`, `fidelity.reach_report`, and `arris-gym census`'s new
  outputs.
- `docs/BACKLOG.md`: drop the oracle-zygote line.

## Open questions
- ⚠ OPEN: a behaviour declined on context, not by form (the backlog's
  "`cq` keeps no CadQuery context along a chain"). The static rule cannot
  exclude it, and Q5 forbids `by_design` inside the subset. So an in-subset
  program that fails on context is a `cq_bug` until it is fixed, or until its
  whole form leaves the subset. The agent records this consequence in
  ADR-0012 (step 1). The human hears it if the baseline shows many such rows
  (step 6).
- ⚠ OPEN: the census order the curve follows: greedy by programs unlocked
  (proposed), or by programs that write the form. The agent decides in step 2
  and records it in `census.reach_curve`'s docstring and ARCHITECTURE; ADR-0014
  cites it.
- ⚠ OPEN: committing derived rows of CC BY-NC data to a public repository.
  Rows carry the licence (gym.md), and no program is committed. The human
  confirms before step 3's commit, since it publishes.

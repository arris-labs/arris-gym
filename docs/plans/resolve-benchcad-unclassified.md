# Plan: resolve-benchcad-unclassified

- Started: 2026-11-21
- Milestone: C2, the fidelity gate (docs/ROADMAP.md): its "0 unclassified on
  both corpora"
- Idea: none; verbatim from the human: "resolve-benchcad-unclassified" (the
  roadmap's "C2 still owes classification of 199 out-of-subset BenchCAD rows")

## Goal

BenchCAD's fidelity table has 0 unclassified rows and 0 timeouts, and
CAD-Recode's stays at 0. The 168 rows that pair `cq`'s `unsupported_api` with
an oracle `invalid` shape are `cq_bug` by an amended ADR-0006 rule. The 31
`double_simplex_sprocket` programs that time out at the oracle's 30 s now run
to an oracle status under a corpus oracle deadline measured from them, and
the rule classes them. Reach (9,998), in-subset `cq_bug` (0) and the
in-subset class counts do not move.

## Non-goals

- Lifting any form. All 199 programs are outside the subset: 136 need bundle
  5's `rect`, `center`, `cutThruAll`, `slot2D` or `loft(combine=)`. 63
  (`worm_screw` 57, `bolt` 6) need `sweep` and `cq.Wire.makeHelix`, which are
  past the knee. Bundle 5's plan classes its 136 once it reaches them. An `ok`
  against `invalid` row is then unclassified until a verdict, as today.
- `unsupported_api` against an oracle `crash`, and `runtime` or
  `arris_refusal` against `invalid`: their ADR-0006 rows stay. Neither corpus
  holds one.
- Verdicts for the 168 (closed forms of 13 families, or a second oracle).
- The oracle's own `DEFAULT_TIMEOUT` (30 s, the slice and fixtures) and the
  sandbox's `cq` deadline.

## Design deltas

- **ADR-0006 amendment (step 2):** `unsupported_api` against `invalid` is
  `cq_bug`; it was unclassified. `unsupported_api` makes no claim about the
  program, since it is a declaration that `cq` does not run the form. So the
  oracle's checker failure cannot be what the two sides disagree on: the row
  is a program the subset does not reach, exactly as against `ok`. ADR-0006 left
  `invalid` unclassified because an arris side that *tried* may have answered
  rightly (a `runtime` on a degenerate input), and that holds only for the
  statuses that ran the program. In the subset the row counts against the
  target, as an `unsupported_api` against `ok` does. Only `_oracle_broke` in
  `fidelity/_compare.py` changes. No type or signature changes. `compare`'s
  docstring and the rule table say so.
- **ADR-0013 amendment (step 1):** a corpus run's oracle deadline,
  `tools/cq_corpus.py` `ORACLE_TIMEOUT` (the `--oracle-timeout` default), is a
  factor over the slowest program measured on the corpus. Measured by step 1.
  Wall-clock time still reaches only a status. With the slowest program
  well inside the deadline, load no longer moves BenchCAD's statuses, and so
  ADR-0014's "digest equal across architectures" holds for it. This absorbs the
  backlog line on that tension. The zygote's 600 s lifetime stays above
  deadline + backstop.
- **Fixture:** `tests/fixtures/fidelity/class-cq-bug-oracle-invalid/` (a
  program outside the subset; an `invalid` oracle record with measures;
  expected `disagree`/`cq_bug`). `table-expected.json` and
  `arris-report-expected.*` gain its row by count.
- **Tables:** BenchCAD's `fidelity.json.gz`, `oracle.jsonl.gz` (the 31 rows
  answered), `reach-report.json`, `arris-report.*`, README, and
  `tests/test_c2_baseline.py` `FIGURES` and `BENCHCAD_BASELINE_ORACLE_ROWS`.
  The C1 slice (no such pair) and CAD-Recode (oracle `ok` on all 968) are
  untouched by the rule.
- No new term. `GLOSSARY.md` "Disagreement class" is unchanged.

## Steps

Grades are tiers (`.agents/tiers.md`): **[1]** routine, the design says
exactly what to write and the tests are mechanical; **[2]** careful, a
numeric, geometric or semantic case to get right within a given design;
**[3]** unproven, something whose correctness has to be established here.

- [x] Step 1 **[2, conductor-run]**: run the 31 timed-out stems alone
  (`tools/cq_corpus.py --corpus benchcad --slice <31 stems> --oracle-timeout
  300`, a fresh `--work-dir`). Record each stem's oracle status and `seconds`
  in the ADR-0013 amendment. Set `ORACLE_TIMEOUT` to the next multiple of
  30 s above 4 × the slowest, and pin it in `tests/test_cq_corpus.py`. If
  any stem still times out or crashes at 300 s, stop: see Q1.
- [x] Step 2 **[2]**: write the ADR-0006 amendment and make the rule change.
  Add the `class-cq-bug-oracle-invalid` fixture. Change the `unsupported_api`
  row of the `RULE` table in `tests/test_fidelity_compare.py` to `(CQ, A, A,
  A, CQ, U, U)`. Re-count `table-expected.json` and the arris report.
  Write `CHANGELOG.md` under Unreleased and the rule's sentence in
  `docs/ARCHITECTURE.md` §The oracle.
- [x] Step 3 **[2, conductor-run]**: re-run BenchCAD (the README's command,
  `--oracle-rows`, a fresh `--work-dir`). Only `cq` and the 31 stems run.
  Commit the tables and the C2 README section, and update `FIGURES` and the
  pinned oracle-rows SHA-256 (`fixtures:` in the message).
  The figures must be: unclassified 0, `timed_out` 0, `cq_bug` 7,695 + 168 +
  the 31 that end `ok` or `invalid`, agree 7,415 + any that end `runtime`,
  every in-subset figure and the reach unchanged.

## Acceptance

- `uv run pytest tests/test_fidelity_compare.py tests/test_fidelity_table.py`:
  every status pair as the amended rule table says; the new class fixture
  `disagree`/`cq_bug`.
- `tests/test_c2_baseline.py` on the committed tables:
  - BenchCAD: `unclassified` 0 and `timed_out` 0, with reach 9,998,
    `in_subset_cq_bug` 0 and `in_subset_by_design` 0;
  - the in-subset classes as before (`arris_bug` 289, `arris_refusal`
    1,449, `occt_wrong` 845);
  - CAD-Recode's table digest `e2bf586c…7308` unchanged.
- The BenchCAD oracle rows differ from the committed file in the 31
  `double_simplex_sprocket` rows alone (a diff of the decompressed lines).
- The gate green.

## Docs to update on completion

- `docs/ARCHITECTURE.md` §The oracle: the C2 table's BenchCAD column
  (unclassified 0, timeouts 0, `cq_bug`); the paragraph on the 199 replaced by
  the rule's and the deadline's outcome; the oracle deadline for corpora.
- `docs/ROADMAP.md` §C2 status: zero unclassified on both corpora; what C2
  still owes is reach.
- `AGENTS.md` current state: the C2 line.
- `docs/BACKLOG.md`: remove the ADR-0014 digest/timeouts line (absorbed).
  Bundle 5's 136 rows go to its plan through the ADR-0006 amendment's
  Consequences.
- `CHANGELOG.md`: the step-2 bullet stands.

## Open questions

- ⚠ OPEN Q1 (the human, at step 1, only if it fails): if some of the 31 do not
  finish within 300 s and 1.5 GiB, they stay timeouts, and no rule may class a
  timeout (ADR-0006). The way out is to amend C2's accept line to "0
  unclassified apart from named oracle timeouts", which changes the cycle's
  scope.
- Agent's pick, recorded: the rule rather than verdicts or `agree`.
  Verdicts would need 13 closed forms for rows `cq` never builds. `agree`
  ("both failed") would add 168 rows to the agreement in which `cq` built
  nothing. `cq_bug` is what the out-of-subset rows already are, and the
  real class arrives when the subset reaches each program.

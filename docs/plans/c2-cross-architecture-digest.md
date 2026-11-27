# Plan: c2-cross-architecture-digest

- Started: 2026-11-27
- Milestone: C2, the fidelity gate (docs/ROADMAP.md)
- From the human “$plan c2-cross-architecture-digest”
- Branch for CI: `plan/c2-cross-architecture-digest`. The push requires authorization during `/work`.

## Goal

Fresh Linux x86-64 and aarch64 runs of the same commit reproduce the
BenchCAD and CAD-Recode fidelity table digests on the locked arris 0.12.0
environment. Each run executes every program under `cq` against the
corpus's committed oracle reports and passes C2's reach and classification
checks. The two corpus READMEs record the run and the complete digests.

## Non-goals

- New `cq` forms, changes to the fidelity target, and arris or NumPy bumps.
- Fresh oracle runs as an architecture comparison, the oracle's own
  repeatability, and the separate finding about hashing `versions.arris_gym`.
- C1 rescore changes, C2 closure, releases, and C3 work.

## Design deltas

- In Architecture §The oracle, define C2's comparison as a replay against
  the same committed oracle reports, including their versions, STEP hashes
  and full-precision measures. The reports record oracle Python 3.12.3.
  The existing `--oracle-rows` probes a live oracle and may run missing
  programs. Add a mutually exclusive `--replay-oracle-rows FILE` to
  `tools/cq_corpus.py` for replay without an oracle environment. Each selected
  stem must have a unique, answered report matching the program SHA-256,
  family, revision and licence. Distinct stems can share a program hash
  (12 groups in BenchCAD and one in CAD-Recode). An incomplete or mismatched
  input stops the replay. Allow existing `--slice` selection for diagnosis
  of either corpus with the full pinned file. Document the two tool options.
- In Architecture §Determinism, specify the evidence for fidelity
  separately from the C1 re-scored table. Validate the full canonical
  `FidelityTable` on both machines, including every measure delta and
  refusal. Compare uncompressed oracle rows with their pinned input and the
  reach and arris reports with their committed contents. Record the replay
  decision in an ADR linked from ADR-0014 and the oracle finding in BACKLOG.
- Add a fidelity workflow with one job per architecture and corpus, using
  C1's `ubuntu-latest` and `ubuntu-24.04-arm` labels. Trigger it on pushes
  to the plan branch and by manual dispatch. Start each job from
  fresh work and output directories, use the repository's locked Python
  3.12 environment and the full verdict sets in the corpus READMEs. Log the
  commit, CPU, Python and glibc versions, worker count, deadline and digests.
  Retain the reports on a comparison failure, with source licences and
  without source programs. Keep corpus fetches outside the offline gate.
- The changes belong to corpus tooling and CI. A reproduced architecture
  difference may require a narrow fix in its owning module. Record any
  resulting public API delta in this plan before implementing it.

## Steps

**[1]** routine, the design specifies the change and the checks are
mechanical. **[2]** careful, a numeric, geometric or semantic case within
the design. **[3]** unproven, correctness has to be established here.

- [x] Step 1 **[1]** — Add strict replay to `tools/cq_corpus.py`.
  Extend `tests/test_cq_corpus.py` with a report for every selected stem,
  shared program hashes under distinct stems, and rejected missing,
  duplicate, unanswered or mismatched reports. Exercise replay without
  an oracle environment and run the existing reuse and resume tests.
- [x] Step 2 **[3] [CI] [conductor-run]** — Run both full corpus replays
  on both machines with the committed inputs and the existing 30 s corpus
  deadline. Compare each validated table with its committed fixture. Upload
  the table and reports before declaring any comparison failure, and retain
  the evidence from all four jobs.
- [ ] Step 3 **[3]** — If a comparison differs, diff by stem and field,
  then use `--slice` and the inspect skill to isolate the earliest difference
  in execution, body measures or fidelity comparison. Record minimal strict
  xfail fixtures for newly reproduced failures. For timeouts, measure the
  named programs on both architectures, alone and at the replay's
  concurrency. If all four jobs match, record that evidence and skip step 4.
- [ ] Step 4 **[3] [conductor-run]** — If needed, fix the demonstrated
  cause and verify the reduced fixture on both architectures. A replay-only
  deadline or worker count is measured by step 3. For an arris defect that
  requires an upstream fix, file the reduced case under
  `../arris/docs/ideas/` and leave C2 open. After a local fix, compare the
  four fresh outputs, record any justified fixture changes in a `fixtures:`
  commit, and verify all four jobs against the resulting fixtures.
- [ ] Step 5 **[1]** — Record the tested commit, run links, digests and
  counts in both corpus READMEs. Add the ADR for pinned-oracle replay and
  update the BACKLOG finding with the evidence. Verify each README's
  commands and values against the green run.

## Step 2 evidence

The workflow tested `53f333b7a59dbff050d64c1106ad4ecb9d2cfecd` on 2026-11-27
with four workers and a 30 s deadline. All four replays uploaded their reports
before comparison. The x86-64 runner used Python 3.12.16 and glibc 2.43.
The aarch64 runner used Python 3.12.3 and glibc 2.39.
[Run 45957071207](https://github.com/arris-labs/arris-gym/actions/runs/45957071207)

| Corpus and architecture | Validated digest | Timeouts | Comparison |
| --- | --- | ---: | --- |
| [BenchCAD x86-64](https://github.com/arris-labs/arris-gym/actions/runs/45957071207/artifacts/15183345295) | `dbca3adbb134737eab0e6a839b47a1ecfc77569b580128a7f43dde4300dde4d9` | 55 | Fidelity and reach differ |
| [BenchCAD aarch64](https://github.com/arris-labs/arris-gym/actions/runs/45957071207/artifacts/15180034817) | `0cfcef7289eba916e89c58dcf7b259dfb59a1bbee316ddb381db19cfee678183` | 28 | Fidelity and reach differ |
| [CAD-Recode x86-64](https://github.com/arris-labs/arris-gym/actions/runs/45957071207/artifacts/15179432086) | `7cc30ad7c343342e6763224b231790dd9de5f2954d2b7bac3693522dc1246b92` | 0 | All reports match |
| [CAD-Recode aarch64](https://github.com/arris-labs/arris-gym/actions/runs/45957071207/artifacts/15179795475) | `7cc30ad7c343342e6763224b231790dd9de5f2954d2b7bac3693522dc1246b92` | 0 | All reports match |

The oracle rows and the two arris reports match the committed contents in
all four jobs. Every count in the acceptance table matches except the
BenchCAD timeout counts. The x86-64 timeouts span 51 `double_simplex_sprocket`
and four `sprocket` programs. All 28 aarch64 timeouts are
`double_simplex_sprocket` programs. The tables name each timed-out stem.

## Acceptance

The fidelity workflow replays both full corpora on the same commit using
`uv sync --locked --extra corpus` and `uv run --locked --extra corpus
python tools/cq_corpus.py --corpus … --verdicts … --replay-oracle-rows …`.
The corpus READMEs give the verdict files and pins. The comparison reads
the tables with `FidelityTable.from_json`, checks the validated digests
against the committed fixtures and checks that both architectures return
these counts.

| Corpus | Programs | In subset | Agree | Unclassified | Timeouts | In-subset `cq_bug` | In-subset `by_design` |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| BenchCAD | 17,900 | 15,656 | 12,791 | 0 | 0 | 0 | 2 (ADR-0025) |
| CAD-Recode | 968 | 968 | 893 | 0 | 0 | 0 | 0 |

Committed digests before diagnosis:

- BenchCAD `bde03cc9c0d13ee40a400db9d3b0ff6cf1773b89745fdf524359b77c295300ff`
- CAD-Recode `7cc30ad7c343342e6763224b231790dd9de5f2954d2b7bac3693522dc1246b92`

If a verified fix changes a digest, acceptance requires the full new
digest to match on both machines and a documented account of the changed
rows. Run `tools/gate.sh` for the offline checks.

## Docs to update on completion

- `docs/ARCHITECTURE.md` §Determinism and §The oracle document the replay
  command, inputs and the cross-architecture evidence.
- `docs/ROADMAP.md` §C2 and `AGENTS.md` Current state record that both
  fidelity digests match and leave cycle closure to `/close-cycle`.
- `tests/fixtures/c2/{benchcad,cadrecode}/README.md`, `docs/adr/README.md`,
  ADR-0014 and BACKLOG carry the evidence and ADR links from step 5.

## Open questions

- **Settled (step 2):** Commit the workflow before the authorized branch
  push so GitHub Actions can run it. Record the run and tick step 2 after
  collecting the results from all four jobs.
- **Settled (step 2):** CAD-Recode matches at the existing deadline.
  BenchCAD's 55 and 28 timeouts break digest equality. Step 3 checks
  whether any other rows or fields differ.
- ⚠ OPEN: If the replay hits timeouts, what deadline and worker count make
  both machines finish reliably? The agent measures in step 3 and records
  the choice in step 4. Any change to C2 acceptance is the human's decision.

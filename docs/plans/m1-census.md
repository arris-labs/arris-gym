# Plan: m1-census

- Started: 2026-11-08
- Milestone: M1 (cycle C1, docs/ROADMAP.md)
- Idea: none; verbatim from the human: "/plan M1"

## Goal
`arris-gym census --corpus benchcad` reads BenchCAD `code_gen` at revision
`5919f578ab09ec283603a082fab07c7639ab56eb`, parses every one of its 17,900
programs without running any, and writes a census: every API call, selector
string and argument form, by family, each program counted or listed as
unparsable with its exception verbatim. A re-run gives the same digest. The
families are ranked by how few API forms they need, and
`tests/fixtures/c1/slice.txt` lists the 300 stems of the C1 slice: the first
3 ranked families with ≥ 100 programs, the first 100 of each by `stem`.

## Non-goals
- Executing a corpus program, in the sandbox or anywhere (M2, M3).
- CAD-Recode or any other corpus (C2); `cq` itself (M3).
- Type inference past a call's chain root (design delta 1): the census
  counts what a program writes, not what CadQuery would dispatch.
- A census of `edit-bench` or `QA`.

## Design deltas
1. **What is counted** (ADR-0003, step 1). The census parses with
   `ast.parse` and never compiles or executes: the hostile-input rule
   ("runs only in a worker") governs running, and parsing runs nothing. Any
   exception out of parse or walk (`SyntaxError`, `RecursionError`,
   `MemoryError`; a NUL byte is a `SyntaxError` on 3.12) makes the program
   **unparsable**, with class and message verbatim; the census never
   raises on a program. Per call:
   - **receiver**: `cq` for `cq.<name>(…)` (the alias the program's
     `import cadquery as …` binds), the root constructor's name for a
     method on a chain rooted in one (`Workplane`, `Sketch`, `Vector`),
     `builtin` for `show_object`, and `?` for anything else, which is
     listed with its unparsed text, never dropped;
   - **call**: `receiver.name`, e.g. `Workplane.extrude`;
   - **argument form**: each positional argument's literal kind (`str`,
     `num`, `bool`, `tuple`, `list`, `call`, `name`, `expr`) and the sorted
     keyword names with theirs: `Workplane.extrude(num; both=bool)`;
   - **selector string**: the first positional argument of `faces`,
     `edges`, `vertices`, `wires`, `solids`, `shells`, `compounds`, as
     written (`'>Z or <Z'`), or `<non-literal>`;
   - **end form**: the program's last statement, normalised
     (`show_object(result)`, `result = …`, other), for ARCHITECTURE.md
     §Outcomes's ⚠ OPEN.

   *Settled* (step 1, ADR-0003 has the whole rule): a chain may pass through
   a name whose every binding is a chain on one root (flow-insensitive, no
   scopes); `builtin` also covers Python's builtins the program leaves
   unbound; a dotted path on another import has that module as receiver
   (`math.sqrt`); a method on a plain attribute is `?`. Kinds `none` and
   `*kind` join the list; `selector=` counts like the first positional.
   End forms also `show_object(…)` and `empty`. Warnings are silenced
   around the parse and every walk is iterative, so neither the caller's
   warning filters nor its stack depth can move an answer.
2. **The ranking** (ADR-0003). Per family: distinct calls, distinct
   selector strings, distinct argument forms. Families rank ascending by
   that triple, then by name; only families with ≥ 100 programs are
   eligible for the slice. A family's stems sort as strings. *Settled*
   (step 1, ADR-0003): calls on `builtin` and on another module are counted
   but not ranked (`cq` does not provide them); `?` calls are ranked.
3. **New public API** in `arris_gym.census`, frozen pydantic models:
   `CorpusProgram(stem, family, text)`; `CorpusInfo(source, config,
   revision, licence)`; `ProgramCensus(stem, calls, forms, selectors,
   unknown, end_form)` or `Unparsable(stem, kind, message)`, from
   `census_program(program: CorpusProgram)` (step 1: it takes the program,
   not bare text, so an `Unparsable` carries its stem); `Counts`, and the
   receiver constants `CQ`, `BUILTIN`, `UNKNOWN`, `NON_LITERAL`,
   `SELECTOR_METHODS`; `FamilyCensus`; `CensusReport`
   (corpus info, totals, families in rank order, unparsable list, `digest`);
   `census(programs, corpus) -> CensusReport`; `select_slice(report,
   programs, families=3, per_family=100, min_programs=100) -> tuple[str,
   ...]`. Every count is a `tuple` of `(key, count)` sorted by key: no
   dict or set order reaches the report.
4. **The digest**: SHA-256 of the report's canonical JSON (sorted keys, no
   whitespace) without the digest field. Input order does not move it:
   programs are sorted by stem first.
5. **The corpus reader**, `arris_gym.census.benchcad`: the revision, config
   and licence (`CC-BY-4.0`) as constants; `huggingface_hub.snapshot_download`
   of `code_gen/data/*.parquet` at that revision into the HF cache, and
   `pyarrow` reading only `stem`, `family`, `code`. A row count other than
   17,900 raises (not the pinned corpus: no program's fault). Both are an optional
   extra `[corpus]`, pinned exactly, and in the `dev` group so `mypy` sees
   them; imported lazily, so `import arris_gym` needs neither.
6. **CLI**: `[project.scripts] arris-gym = "arris_gym._cli:main"`;
   `arris-gym census --corpus benchcad [--out DIR]` writes `census.json`
   and `slice.txt` (a `#` header naming source, revision, licence and the
   three families; then one stem per line, families in rank order), prints
   totals, the top ranked rows and the digest. The extra missing: one line
   naming `arris-gym[corpus]`, exit 2.
7. **Committed**: `tests/fixtures/c1/{slice.txt,census.json,README.md}`,
   the README carrying BenchCAD's CC-BY-4.0 attribution. The census holds
   counts and no program text.
8. **ARCHITECTURE.md §Outcomes ⚠ OPEN** (what programs end in) is narrowed:
   BenchCAD's half answered by the end-form counts, CAD-Recode's and the
   multi-solid question left open for M3 / C2.

## Steps
Complexity grades; a step's grade is its tier (`.agents/tiers.md`):
**[1]** routine — the design says exactly what to write and the tests are
mechanical; **[2]** careful — a numeric, geometric or semantic case to get
right within a given design; **[3]** unproven — an algorithm, an isolation
guarantee or a CadQuery semantic whose correctness has to be established here.

- [x] Step 1 **[3]** — `census_program(text)` per delta 1, ADR-0003 (what is
  counted, the parse-not-run reading, the ranking). Fixtures
  `tests/fixtures/census/<slug>/` (`program.py`, `expected.json` written by
  hand from the program): a washer chain, a nested `union(cq.Workplane…)`,
  `cq.Vector`/`cq.Sketch` roots, keyword forms, a non-literal selector, an
  aliased import, a `?` receiver, a syntax error, nesting deep enough for
  `RecursionError`, a NUL byte. `hypothesis`: never raises on arbitrary
  text; a chain built from drawn calls counts exactly those calls. Also
  `deep-unary-memory` (`MemoryError`) and `syntax-warning-parsed`.
- [ ] Step 2 **[2]** — `census` and `select_slice` (deltas 2, 3): a corpus
  built in the test, four families with known form sets and one below 100
  programs, gives the expected rank order, ties broken by name, and the
  expected stems; every program in exactly one of parsed or unparsable.
- [ ] Step 3 **[2]** — `CensusReport` JSON and digest (delta 4): a
  round-trip is equal; `hypothesis`: a shuffled corpus gives the same
  digest; a changed count changes it.
- [ ] Step 4 **[2]** — the `[corpus]` extra and `benchcad` reader (delta 5);
  `uv.lock` changes here. Tested offline on a parquet the test writes with
  `pyarrow` (columns, order, the row-count refusal); the download itself is
  not in the gate.
- [ ] Step 5 **[1]** — `arris-gym census` (delta 6): run on the step-4
  parquet through an injected reader, it writes the two files and the
  digest; without the extra, exit 2 and the line.
- [ ] Step 6 **[2]** — the run: `arris-gym census --corpus benchcad` twice,
  digests equal; commit delta 7's files. Each `?` receiver and unparsable
  program is read: explained in the README, or shrunk to a step-1 fixture
  and the counting fixed. A gate test checks `slice.txt` against
  `census.json`: 300 unique stems, 3 × 100, the families the top 3
  eligible, sorted within each. Totals and families recorded here.

## Acceptance
- `arris-gym census --corpus benchcad`: parsed + unparsable = 17,900, every
  unparsable program listed with its kind and message; a second run's
  digest equal to the first and to the committed `census.json`'s.
- `tests/fixtures/c1/slice.txt` committed: 300 stems, the 3 families named.
- Gate: the step-1 fixtures, the never-raises and counting properties, the
  order-invariance property, the slice consistency test.

## Docs to update on completion
- `docs/ARCHITECTURE.md` §Modules — `census` as built; a new §The census
  (deltas 1–6, short); §Outcomes ⚠ OPEN narrowed (delta 8).
- `docs/ROADMAP.md` C1 — the slice's three families named; M1 landed.
- `docs/adr/README.md` — ADR-0003 in the index.
- `GLOSSARY.md` — **API form** (call plus argument form), **selector
  string**, **slice**, **unparsable** (a census outcome, not a status).
- `CHANGELOG.md` Unreleased — `arris-gym census`, the `[corpus]` extra.
- `README.md` — the census command, if it lists commands.
- `AGENTS.md` current state — M1 landed; next `/plan M2`.

## Open questions
- *Settled* (step 1, recorded in ADR-0003): `huggingface_hub` + `pyarrow`
  rather than `datasets` (SEED.md §7 says "HF `datasets`, Parquet"):
  `datasets` reads the same Parquet through `pyarrow` and adds `pandas`,
  `fsspec` and `multiprocess` for nothing the census needs. The human may
  still overrule before step 4, by a superseding ADR.
- *Settled* (step 1, ADR-0003): the ranking triple is calls, then selector
  strings, then API forms: a call is what `cq` has to implement; a selector
  string is grammar, cheaper per item.
- ⚠ OPEN: `census.json`'s size. If the run passes ~200 KB the committed
  copy keeps totals and the per-family rows, and the full report stays a
  command's output. Agent, at step 6.

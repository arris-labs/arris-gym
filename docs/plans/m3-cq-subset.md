# Plan: m3-cq-subset

- Started: 2026-11-08
- Milestone: M3 (cycle C1, docs/ROADMAP.md)
- Idea: none; verbatim from the human: "/plan M3"

## Goal
`run(program, dialect="cq")` runs a CadQuery program on `arris.build`: inside
the program worker `import cadquery as cq` gets `arris_gym.cq`, `show_object`
is a builtin, and a call or API form outside the subset ends `unsupported_api`
naming it. The subset is what the slice's census needs, the 13 API forms of
`tests/fixtures/c1/census.json`: `cq.Workplane(str)`, `cq.Vector(num, num,
num)`, `transformed(offset=, rotate=)`, `box`, `circle`, `extrude`, `union`,
`cut`, `moveTo`, `lineTo`, `polyline`, `close`, `revolve(num, tuple, tuple)`.
The 300 slice programs run in the sandbox under `cq`, each with a status;
each is compared with its oracle report in `tests/fixtures/c1/oracle.jsonl`,
and the fidelity table has **0 unclassified** rows. Agreement is reported.

## Non-goals
- Calls the slice does not write: selectors, `hole`, `chamfer`, `fillet`,
  named planes but `"XY"`, STEP export (Open questions): C2, census order.
- The C2 fidelity target: its ADR is written from this plan's agreement
  figure when C2 opens, not here.
- An oracle zygote, a public outcome type for `parse_outcome`: backlog lines.
- M4's reward and M5's re-scored table.

## Design deltas
- **ADR-0007, the `cq` stack over `arris.build`** (step 1): a `Workplane` is a
  frozen value holding its plane (an `arris.build.Workplane`), its stack of
  objects (solids, a pending sketch or path) and its parent; every call
  returns a new one. What resolves to a program's result: the last
  `show_object` argument, else module-level `result`; a `Workplane` resolves
  to the single solid on its stack. Zero solids is `runtime`; several is
  `unsupported_api` naming the count (a CadQuery compound is outside the
  subset; the slice makes none: every oracle report has one solid).
  "Several" counts stack entries and, after `union`, the fused body's outer
  shells (`ExecResult.shells`): what arris's `fuse` of disjoint solids
  returns is established by step 3's fixture, not assumed. A call
  the subset lacks raises `UnsupportedApi` from `__getattr__` on the module
  and on `Workplane`; an implemented call given an API form outside the
  census raises `UnsupportedApi` naming the form as the census writes it
  (`Workplane.box(num, num, num; centered=bool)`). Never `AttributeError` or
  `TypeError`.
- **`Dialect.CQ = "cq"`** in `sandbox/outcome.py`: a public enum member;
  `run`, `run_many`, `Sandbox.run` accept `"cq"`. The program job carries
  its dialect (one header byte in the payload memfd, `sandbox/_program.py`);
  the worker installs `arris_gym.cq` as `sys.modules["cadquery"]` and puts
  `show_object` in the namespace only for `cq`. Under `arris`, `import
  cadquery` stays `runtime` (`ModuleNotFoundError`). The cache key already
  holds the dialect. Closes `⚠ OPEN` "what a Workplane holding several
  solids scores as (M3)" in ARCHITECTURE.md §Outcomes.
- **Semantics taken from CadQuery's source**, each named in `PROVENANCE.md`
  with the file read: `transformed` (rotation about the plane's local x, y, z
  in CadQuery's order, offset in the parent plane's coordinates), `box`
  centred on the plane's origin, `polyline`/`moveTo`/`lineTo`/`close` as a
  pending wire, `revolve`'s axis points in plane coordinates, degrees,
  `union`/`cut` taking the other Workplane's solid. CadQuery's `clean=True`
  face merging is not reproduced: face counts are carried, never judged
  (ADR-0005).
- **`tools/cq_slice.py`** (step 7): reads the corpus (`[corpus]` extra,
  network, outside the gate), runs the 300 under `cq`, compares with
  `oracle.jsonl`, applies `tests/fixtures/c1/verdicts.json`, and writes
  `tests/fixtures/c1/fidelity.json` (the table) and `arris-report.{json,md}`.
  Decides the backlog line on `OracleReport.digest()`: used for the row's
  oracle side or dropped.
- **`arris_gym.cq.Vector(x, y, z)`** (step 2): a frozen value read as
  `x`, `y`, `z`; `Workplane.transformed(rotate=Vector, offset=Vector)` and
  `Workplane.box(length, width, height)`, the census's forms.
- **Glossary**: **Subset** (the calls and API forms `cq` implements, grown in
  census order) and **Stack** (a `cq` Workplane's objects, newest last).

## Steps
Complexity grades; a step's grade is its tier (`.agents/tiers.md`), and
`**[1, tier 3]**` overrides it: **[1]** routine — the design says exactly
what to write and the tests are mechanical; **[2]** careful — a numeric,
geometric or semantic case to get right within a given design; **[3]**
unproven — an algorithm, an isolation guarantee or a CadQuery semantic whose
correctness has to be established here.

- [x] Step 1 **[3]** — ADR-0007; `Dialect.CQ`, the job's dialect byte, the
  module install, `show_object`, result resolution, `UnsupportedApi` on an
  unknown name. Fixtures `tests/fixtures/cq/`: an unknown call, an unknown
  attribute of `cq`, no result, a non-Workplane `show_object`, `import
  cadquery` under `arris`, each its status; `hypothesis`: `run(text,
  dialect="cq")` never raises. *Settled:* `cq.Workplane("XY")` (other names
  `unsupported_api`) lands here, since the unknown-call and empty-stack
  fixtures need a Workplane; step 2 keeps the rest. `import
  cadquery.<name>` is `unsupported_api` too (a finder in the worker).
- [x] Step 2 **[3]** — `Vector`, `Workplane("XY")`, `transformed`, `box`.
  Fixtures by closed form: a box offset; a box rotated about x by −30°
  (bounds by trigonometry); two chained `transformed`; one rotation about
  x, y and z together, its bounds by the matrix product, oracle-recorded.
  *Settled:* a `box` on a workplane whose chain already holds a solid is
  `unsupported_api` (`Workplane.box combined with a solid in its chain`)
  until step 3, since CadQuery fuses the two and a fuse is step 3's.
- [x] Step 3 **[2]** — `union`, `cut` of Workplanes onto the stack's solid;
  `box` fused with a solid in its chain (step 2's *Settled*).
  Fixtures: overlapping boxes (V by inclusion–exclusion), a box less a
  through box, a disjoint union ending `unsupported_api` (ADR-0007; what
  arris's `fuse` returns for it is recorded here first).
  *Settled:* `fuse` of disjoint solids returns one Solid whose body holds both
  outer shells (a test records it). A cavity (`cut` of an inner box) also has
  two shells, so shells alone cannot tell it from a compound: `union` and a
  fusing `box` treat the result as disjoint when the fused body has at least
  as many shells as the two operands together, and then keep both solids on
  the stack; resolving that stack ends `unsupported_api` (`a Workplane
  holding 2 solids`), and a further `union`/`cut`/`box` on it likewise.
- [x] Step 4 **[2]** — `circle`, `extrude` along the plane's normal.
  Fixtures: a cylinder (πr²h, 2πr(r+h)), a transformed cylinder, a
  two-lobe union whose lens volume is the closed form.
  *Settled:* the pending circle is the stack's one sketch (not a context
  shared along the chain); `circle` on a non-empty stack, where CadQuery
  centres it on each object, is `unsupported_api` (`Workplane.circle on a
  non-empty stack`), and `extrude` needs exactly one sketch on the stack
  (`ValueError`, `runtime`). Step 6 still checks the call forms.
- [x] Step 5 **[3]** — `moveTo`, `lineTo`, `polyline`, `close`, `revolve`.
  Fixtures by Pappus: a revolved rectangle (tube), a revolved trapezoid
  (frustum shell), one profile drawn by `polyline` and by `moveTo`/`lineTo`
  giving the same body digest.
  *Settled:* as step 4's circle, the pending path is the stack's one
  object, not CadQuery's context shared along the chain: `moveTo` or
  `polyline` on a stack holding a pending wire (a path, a closed sketch, a
  circle) is `unsupported_api` (`Workplane.moveTo on a pending wire`), and
  `lineTo` after a solid or a closed sketch is CadQuery's `RuntimeError`
  (`runtime`). `revolve` takes the census's three arguments; its default
  axes wait for step 6. A 90° fixture (oracle-recorded) pins the turn as
  right-handed. ⚠ OPEN (step 6): `transformed`, `box`, `union` and `cut`
  on a stack holding a pending wire drop it, where CadQuery keeps it in
  its context; the slice writes none. *Settled in step 6:* see Open questions.
- [x] Step 6 **[2]** — API forms outside the census: every implemented call
  checks its form. `hypothesis`: chains drawn from implemented calls with
  census forms run `ok` or end in a kernel refusal; chains with one call or
  keyword outside them end `unsupported_api` naming it, never `runtime`.
  *Settled:* the check is a decorator (`cq/_forms.py`) on every implemented
  call, run before the method; a form is its positional kinds and its
  keywords, spelled as the census spells it. `union`/`cut` accept any one
  argument (their operand check keeps its own message); `transformed`
  accepts any subset of its two census keywords, `Vector` and `Workplane`
  values being `call`. The census-chains property is built in-process
  from recipes (box, cylinder, prism, ring, each maybe on a turned plane)
  joined by `union`/`cut`; a compound is the one `unsupported_api` it allows.
- [ ] Step 7 **[2]** — `tools/cq_slice.py` and its first run: 300 rows,
  the table and arris report committed with their digests (two runs equal);
  `tests/test_c1_slice.py` checks the committed table offline (300 rows,
  counts summing to 300, digest).
- [ ] Step 8 **[3]** — every disagreement of step 7 classed: each shrunk
  under the `inspect` skill to `tests/fixtures/regression/<slug>/` (strict
  `xfail`) or given a verdict in `verdicts.json`; a `cq` bug fixed in the
  commit carrying its step's suffix; the table rewritten, **0 unclassified**.
- [ ] Step 9 **[1]** — the calibration set's `oracle.py` programs that use
  only the subset run under `cq` and match their `expected.json` closed
  forms; the others end `unsupported_api` naming their first call outside it.

## Acceptance
- `tools/cq_slice.py` over the 300 slice programs: one status each, counted
  over all 300 in the table; the fidelity table's digest equal on two runs;
  **unclassified: 0**; agreement, each class and each status reported with
  zeros, timeouts named.
- `tests/fixtures/cq/` (steps 1–6) pass against closed forms; regression
  fixtures from step 8 committed with strict `xfail`.
- `hypothesis`: `run` never raises under `cq`; out-of-subset forms are
  `unsupported_api`, never `runtime`.
- The gate passes, `tools/check_layers.py` included (`cq` imports only
  `arris`).

## Docs to update on completion
- `docs/ARCHITECTURE.md` §Dialects — the subset as built, the stack, result
  resolution, out-of-subset forms; §Outcomes — the several-solids `⚠ OPEN`
  closed by ADR-0007; the selector `⚠ OPEN` stays (C2).
- `docs/ROADMAP.md` M3 — landed, its numbers; the "hole and chamfer"
  parenthetical replaced by what the census found; the C1 status line.
- `docs/adr/README.md` — ADR-0007 row.
- `AGENTS.md` current state — M3 landed, next `/plan M4`.
- `GLOSSARY.md` — **Subset**, **Stack**.
- `PROVENANCE.md` — each CadQuery behaviour taken, with the file read.
- `tests/fixtures/c1/README.md` — the cq run: command, digests, counts.
- `CHANGELOG.md` `Unreleased` — `dialect="cq"`, the calls it covers,
  `unsupported_api` naming the call or form.
- `docs/BACKLOG.md` — the `OracleReport.digest()` line removed (step 7).

## Open questions
- *Settled* (human, before step 1): selectors, `hole`, `chamfer` and STEP
  export are all left to C2's census order, as *Non-goals* says; no STEP
  step. The census shows the slice calls none of them, and STEP export
  inside the sandbox could not write a file (every mount is read-only).
- *Settled* (step 1, ADR-0007): several solids are `unsupported_api`, not
  `runtime`: a compound is a CadQuery value the subset lacks, not a program
  error; both give the same reward (−1.0).
- *Settled* (agent, step 6): `box` with a negative dimension is `runtime`
  (`ValueError`, naming CadQuery's `Standard_DomainError`), as CadQuery 2.3.0
  ends, though arris would build it from the magnitudes: the subset follows
  the oracle, so the table never counts it a disagreement. A zero dimension
  stays the kernel's refusal (`arris_refusal`). The slice has none.
- *Settled* (agent, step 6): `transformed`, `box`, `union` and `cut` on a stack
  holding a pending wire are `unsupported_api` (`Workplane.box on a pending
  wire`), as `moveTo` and `polyline` already are: dropping the wire silently
  would build a part CadQuery does not, where refusing names the gap.
- *Settled* (agent, step 6): `revolve` has the census's three arguments only;
  CadQuery's default axes and every other form are `unsupported_api` naming
  the form (`Workplane.revolve(num)`), since the census writes none.
- *Settled* (agent, step 6): a `polyline` point must be two numbers (a tuple or
  list); three coordinates, a `Vector` or anything else is `unsupported_api`
  (`Workplane.polyline(list with a point of 3 numbers)`): a path leaving its
  plane is not one the subset draws. `revolve`'s axis points keep two or three.
- ⚠ OPEN (agent, step 7): the slice run's timeout and memory — the sandbox's
  defaults unless a program needs more, measured by step 7.

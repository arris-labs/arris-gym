# Backlog

One line per raw idea. Picking one up means `/idea` (needs thinking) or
`/plan` (obvious); the line is removed then — as is a line a roadmap cycle
has committed to, which now lives in `docs/ROADMAP.md` instead. Rejected
ideas keep one line below with the reason, so the same idea is not
re-brainstormed. A *measured* defect is not a raw idea: it goes under
[Findings](#findings) below, in the fixed shape.

- The human's: the GitHub repository `arris-labs/arris-gym`, and reserving `arris-gym` on PyPI with a minimal 0.0.x release (free on PyPI as of 2026-11-07, SEED.md §2)
- `readable_roots` includes `sys.prefix`: for a system interpreter that is all of `/usr`, wider than the interpreter's own files; narrow it when a consumer runs a system Python
- Port `/release` and `release.yml` from laman when the first real release is planned; until then git.md says an agent never tags or uploads
- BenchCAD 2.0 (`BenchCAD/benchcad-2.0-public` and `-core`, drawing → STEP, gated, licence "other") is not in the survey: read its terms before C3 and decide if it belongs among the re-scored benchmarks
- Census: a chain on a receiver it cannot place (`x = a.b().b()…`) keys each `?` call by its whole source prefix, so a hostile program can make `unknown` quadratic in size (4,000 calls: 32 M characters); decide a truncation of the key
- File with arris once M4 measures it (SEED.md §10.6): the batch `classify_points` binding, and whether a public `Model` reset or id-stable `read_body` would help consumers
- `fidelity/_oracle.py` imports the private `sandbox._run.ended` and `sandbox._zygote.Outcome`, so the public `parse_outcome` takes a private type: give `sandbox` a public outcome type or move the parse
- An oracle zygote (import cadquery once, fork per program): each oracle program pays ~1.5 s of start-up, so the slice takes minutes
- A crash on both sides is `agree` under ADR-0006, so it never reaches the arris report; decide whether `arris_rows` lists every arris `crash` regardless of outcome (gym.md: an arris crash goes to arris as a fixture candidate)
- `tools/check_layers.py` sees `import`, `from` and literal `importlib.import_module`; a computed name evades it, as it would evade any static check

## Findings

A defect a run measured, one block each:

```
### <slug>
- What: …
- Where: module, file, function
- Seen: run / commit / corpus revision / program id / date
- Reproduce: the command that replays it
- Measured: the numbers
- State: raw | measured | regression/<slug> | fixed
```

### union-coplanar-third-operand
- What: arris refuses a chained `fuse` whose third operand shares an end plane with the first two's union (`OpDegenerateError`, "the faces touch along a curve interior to both result faces"); the n-ary `fuse` builds it
- Where: arris 0.10.0 `Solid.fuse`, reached by `cq`'s `Workplane.union`
- Seen: `tools/cq_slice.py`, plans/m3-cq-subset step 8, BenchCAD `5919f578ab09ec283603a082fab07c7639ab56eb`, all 100 `lobed_knob` slice programs, 2026-11-08
- Reproduce: `uv run pytest --runxfail tests/test_regression.py -k cq-union-three-coplanar-cylinders`
- Measured: 100 of 100 refused (98 at the second union, 2 at the fourth); rebuilt by n-ary fuse, all 100 within 8e-15 of the oracle's volume
- State: regression/cq-union-three-coplanar-cylinders; reported in `../arris/docs/ideas/union-coplanar-third-operand.md`; lift the xfail and drop the 100 verdicts when an arris bump builds it

## Rejected

- The working name `arris-zero`: it suggested R1-Zero, pure RL with no supervised fine-tuning, which is not the plan (SEED.md §2)

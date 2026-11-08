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
- `OracleReport.digest()` is called by nothing but its tests (`oracle.jsonl`'s digest is the file's SHA-256): use it in M3's rows or drop it
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

## Rejected

- The working name `arris-zero`: it suggested R1-Zero, pure RL with no supervised fine-tuning, which is not the plan (SEED.md §2)

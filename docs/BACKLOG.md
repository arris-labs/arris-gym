# Backlog

One line per raw idea. Picking one up means `/idea` (needs thinking) or
`/plan` (obvious); the line is removed then — as is a line a roadmap cycle
has committed to, which now lives in `docs/ROADMAP.md` instead. Rejected
ideas keep one line below with the reason, so the same idea is not
re-brainstormed. A *measured* defect is not a raw idea: it goes under
[Findings](#findings) below, in the fixed shape.

- Possible: an oracle zygote killed by its warden or a timeout may leave itself orphaned (its child or the exec'd interpreter outliving the kill); reproduce on a killed zygote and check `/proc` for survivors (ADR-0013)
- `readable_roots` includes `sys.prefix`: for a system interpreter that is all of `/usr`, wider than the interpreter's own files; narrow it when a consumer runs a system Python
- BenchCAD 2.0 (`BenchCAD/benchcad-2.0-public` and `-core`, drawing → STEP, gated, licence "other") is not in the survey: read its terms before C3 and decide if it belongs among the re-scored benchmarks
- Census: a chain on a receiver it cannot place (`x = a.b().b()…`) keys each `?` call by its whole source prefix, so a hostile program can make `unknown` quadratic in size (4,000 calls: 32 M characters); decide a truncation of the key
- `rescore`'s `SLICE` and `TARGETS` defaults are paths relative to the repository root: an installed `arris-gym rescore benchcad` fails without `--slice` and `--targets`; resolve them from the package or require the flags
- `_cli.py`'s docstring names only `census`; `.github/workflows/ci.yml` comments cite deleted plans (`m0-sandbox`, `m5-rescore` step 9); `tools/check_layers.py` does not hold `rescore` against importing `train` (harmless until `train` exists)
- BENCHMARK-SURVEY.md's numbers (BenchCAD 0.768/0.601, 52 ISO families, 748 edit pairs; Text2CAD-Bench, MUSE, cadbench, CADWorld, CAD-Recode ~1M) are unverified until read in each paper; verify before C3's report cites them
- File with arris (SEED.md §10.6) whether a public `Model` reset or id-stable `read_body` would help consumers; the batch `classify_points` and cone-against-cone asks are filed (`../arris/docs/ideas/`)
- Compare `step_sha256` across machines: regenerate the slice's STEPs on the second architecture (ADR-0011 does not claim OCCT is equal across machines)
- `Score` does not check that an `ok` score's `reward` equals `combine(terms, config)`; a validator would refuse a forged one
- `sandbox/_zygote_main.py` imports `reward._job` to register the score handler, an edge `tools/check_layers.py` does not hold: allow only that module or register through a plugin point
- `fidelity/_oracle.py` imports the private `sandbox._run.ended` and `sandbox._zygote.Outcome`, so the public `parse_outcome` takes a private type: give `sandbox` a public outcome type or move the parse
- A crash on both sides is `agree` under ADR-0006, so it never reaches the arris report; decide whether `arris_rows` lists every arris `crash` regardless of outcome (gym.md: an arris crash goes to arris as a fixture candidate)
- `tools/check_layers.py` sees `import`, `from` and literal `importlib.import_module`; a computed name evades it, as it would evade any static check
- Decide whether the `cq` subset admits the bare `cq.Workplane()` (CadQuery's default plane) and `box(...; centered=False)`: all 19 calibration programs in `tests/fixtures/fidelity/` use one, so none runs under `cq` and `tests/test_cq_calibration.py` holds them to `unsupported_api` (a product question, in census order for C2)
- `cq` keeps no CadQuery context along a chain: a `circle` on a stack other than one `moveTo` point, a `moveTo` on a pending wire, and `transformed`, `union`, `cut` on a pending wire and `box` on a drawn path or sketch or on a stack holding a solid (CadQuery centres it on the solid's centre), and a `polyline` of fewer than two points (CadQuery starts the next call from the origin), end `unsupported_api`; lift them in census order when a program writes them
- A target read from a STEP is exactly one solid (ADR-0011), so a re-scored corpus whose oracle builds a compound (827 BenchCAD oracle `ok` reports hold 2 to 9 solids) gets a `runtime` target; decide how a compound target is read before BenchCAD is re-scored beyond the slice (ADR-0016)
- `cq`'s `workplane()` on a compound puts the plane at arris's centroid, while CadQuery uses Open CASCADE's `Center()`, which can be wrong for a compound (`cq/ok-compound-occt-centroid`): the two planes differ in that construction; add a fixture with a closed form if a corpus program reaches it
- A compound whose pieces hold cavities has more shells than oracle solids, so its row is `unclassified` under ADR-0016; count outer shells (the sign of each shell's tessellated volume) if a corpus shows one
- `show_object(x, color=...)` ends `runtime` (a `TypeError` from the builtin's signature) where the goal says an out-of-subset form is `unsupported_api`: route the builtin's form through `cq/_forms.py`
- `cq/_forms.py` `kind_of` decides the "call" kind by class name, so a program's own `class Vector` passes the form check, and `transformed(rotate=cq.Workplane("XY"))` ends `unsupported_api` as `Workplane.z`: decide by type
- `test_regression.py`'s strict `xfail(raises=AssertionError)` also covers the `sandbox.executions == REPEATS` assert, so a cache-hit bug would pass as the expected failure; and `fixture_cases.load`'s faces guard has no test
- Face counts in `tests/fixtures/cq/ok-*` are what arris produces (carried, ADR-0005), while gym.md says expected values never come from arris-gym's output: settle with the rule's author whether `faces` may be recorded for a fixture whose other measures are closed-form
- `sandbox/_program.py` imports the private `arris_gym.cq._result`; `tests/test_cq_calibration.py` carries literal tolerances (`rel=1e-12`, `abs=1e-9`) and plan history in its docstring; the 2 `lobed_knob` rows refused at the fourth union have only the n-ary rebuild as evidence, not a shrunk fixture
- Canonical JSON is hand-rolled in `_cli.py` `run_census` and `fidelity/_reach.py` `ReachReport.to_json` though `census._report._canonical` exists: use one
- `run_census` picks the slice by `if info == benchcad.INFO` instead of a field on the `CORPORA` entry
- ADR-0014's accept line "table digest equal across architectures" is in tension with the oracle timeouts (31 `double_simplex_sprocket` programs, 4 to 30 s) making BenchCAD's table digest load-dependent: decide a timeout-stable digest or amend the line

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

### interference-split-planar-faces
- What: `interference` of an arris-built body against the same part read from Open Cascade's STEP refuses (`OpDegenerateError`, "the faces touch along a curve interior to both result faces") when both are all planes but the STEP's coplanar faces are merged (the candidate has more faces); the pair then takes the sampled IoU route, not the exact one
- Where: arris 0.10.0 `Model.interference`, reached by `reward`'s exact IoU route; ADR-0008 measured `phone_stand` pairs of one split, never an arris body against an Open Cascade one
- Seen: plans/m5-rescore step 7, `arris-gym rescore benchcad`, BenchCAD `5919f578ab09ec283603a082fab07c7639ab56eb`, all 100 `phone_stand` slice pairs, 2026-11-09
- Reproduce: `uv run --extra corpus arris-gym rescore benchcad`, then the `iou_route` of the `phone_stand` rows in `rescore.json`
- Measured: 100 of 100 refused; the sampled IoU is 1.0 on all 100; the same body against itself answers 1.0 exactly
- State: measured; reported in `../arris/docs/ideas/interference-split-planar-faces.md`; no regression fixture (a pair of two bodies, not one program)

### torus-box-point-contact
- What: arris refuses the fuse of a torus and a box whose face touches the torus at its seam vertex (`arris_refusal`, "no closed form for +f6 (plane surface) against +v0 (point)"); the oracle builds two solids meeting at that point
- Where: arris 0.10.0 `Solid.fuse`, reached by `cq`'s `Workplane.union` after a revolved `circle`
- Seen: plans/in-subset-cq-bugs step 5, rerun of the 113 `circle`-cause rows of `tests/fixtures/c2/benchcad/cq-bugs.json`, BenchCAD `5919f578ab09ec283603a082fab07c7639ab56eb`, 43 `torus_link` programs (e.g. `torus_link_000353_s20260507`), 2026-11-12
- Reproduce: `cq.Workplane("XY").moveTo(3, 0).circle(1).revolve(360, (0, 0, 0), (0, 1, 0)).union(cq.Workplane("XY").transformed(offset=cq.Vector(5, 0, 0)).box(2, 2, 2))` under `dialect="cq"`; the oracle gives 2 solids, volume 6π² + 8
- Measured: 43 of 113 refused with that message, the other 70 agree. With the box moved 0.5 into the torus, `cq` builds it (volume 66.13564505370971) but the row is `unclassified`: the oracle's volume is 66.13565097373274, and a quadrature of the overlap gives 66.135645049 and converging, so Open CASCADE is the one off (about 9e-8 relative); a classing case for the oracle, not seen in the corpus
- State: measured; ADR-0016 decides a result of two solids meeting is a compound, so the desired outcome is now known: arris's `fuse` should accept a point contact, or `cq` needs a regression fixture (strict `xfail`) for it; the arris ask is not yet filed in `../arris/docs/ideas/`

### occt-compound-centroid
- What: Open CASCADE's centroid of a compound of two disjoint boxes is wrong in one solid order: a 2 × 2 × 2 box at the origin united with a 2 × 4 × 4 box centred on (5, 0, 1) reports (4.725, 0, 0.975), where the closed form and arris give (4, 0, 0.8); volume, area and bounds are right
- Where: `tools/oracle/worker.py` `_measures`, `BRepGProp.VolumeProperties_s` with its default `OnlyClosed = false`, OCP 7.9.3.0; with the solids reversed, `OnlyClosed = true` or `GProp_GProps.Add` over the solids it is right
- Seen: plans/in-subset-cq-bugs step 9, probing compounds for ADR-0016, 2026-11-13
- Reproduce: `uv run pytest tests/test_cq_compound.py -k occt`; the recorded report is `tests/fixtures/cq/ok-compound-occt-centroid/oracle.json`
- Measured: 1 of 7 two-box compounds probed; the 5 CAD-Recode compound programs and the other compound fixtures give the closed form
- State: a recorded `occt_wrong` verdict by its closed form (`verdict.json`); the worker is unchanged, since re-measuring could change committed oracle bytes for compound rows: a change of the oracle for its own plan

### oracle-nondeterministic-step
- What: the oracle's report of one program is not the same bytes run to run: the STEP's SHA-256 and the last digits of centroid, volume and area move, status, solids and faces do not; the same program on the same code returns the baseline's bytes on some runs and not on others
- Where: `tools/oracle/worker.py` on an oracle zygote (ADR-0013), CadQuery 2.3.0 / OCP 7.9.3.0: Open CASCADE's boolean, chamfer and shell build order follows memory addresses (address-space layout, and a job's position on its zygote)
- Seen: plans/in-subset-cq-bugs step 10, `tools/cq_corpus.py --corpus benchcad` re-run against the committed baseline rows, BenchCAD `5919f578ab09ec283603a082fab07c7639ab56eb`, 2026-11-13
- Reproduce: rerun one stem (e.g. `hollow_tube_000907_s20260505`) N times with `oracle_run.run_many` and compare `step_sha256`; or re-run the corpus and diff `oracle.jsonl.gz` against `tests/fixtures/c2/benchcad/`
- Measured: 214 of 17,900 rows differ, all in 8 families (`sheet_metal_tray` 101, `washer` 49, `spacer_ring` 32, `snap_clip` 13, `ratchet_sector` 11, `hollow_tube` 3, `spline_hub` 3, `parallel_key` 2), measures at most 4e-13 relative; none of their fidelity rows moved, so the table digest does not depend on it; the committed rows are the baseline's. Turning address-space randomisation off and starting a fresh zygote per program would make one machine repeat its bytes, not two machines agree
- State: measured; no regression fixture: the oracle runs outside the gate (`-m oracle`), and a run-to-run difference that some runs do not show cannot be a strict xfail; decide whether the oracle's committed bytes keep the STEP hash and full-precision measures, or a fidelity-row digest is the claim (ADR-0014's cross-machine accept line)

## Rejected

- The working name `arris-zero`: it suggested R1-Zero, pure RL with no supervised fine-tuning, which is not the plan (SEED.md §2)

# Backlog

One line per raw idea. Picking one up means `/idea` (needs thinking) or
`/plan` (obvious); the line is removed then — as is a line a roadmap cycle
has committed to, which now lives in `docs/ROADMAP.md` instead. Rejected
ideas keep one line below with the reason, so the same idea is not
re-brainstormed. A *measured* defect is not a raw idea: it goes under
[Findings](#findings) below, in the fixed shape.

- `tools/cq_closed_forms.py`'s hook is an untyped `dict[str, object]` read back through `# type: ignore[assignment]` casts, and `_check_prisms` builds `_segments` only to raise while `hook_measures` builds it again; give the hook a frozen type and compute each once (found by the `lift-extrude-both` review)
- Possible: an oracle zygote killed by its warden or a timeout may leave itself orphaned (its child or the exec'd interpreter outliving the kill); reproduce on a killed zygote and check `/proc` for survivors (ADR-0013)
- `readable_roots` includes `sys.prefix`: for a system interpreter that is all of `/usr`, wider than the interpreter's own files; narrow it when a consumer runs a system Python
- BenchCAD 2.0 (`BenchCAD/benchcad-2.0-public` and `-core`, drawing → STEP, gated, licence "other") is not in the survey: read its terms before C3 and decide if it belongs among the re-scored benchmarks
- Census: a chain on a receiver it cannot place (`x = a.b().b()…`) keys each `?` call by its whole source prefix, so a hostile program can make `unknown` quadratic in size (4,000 calls: 32 M characters); decide a truncation of the key
- `rescore`'s `SLICE` and `TARGETS` defaults are paths relative to the repository root: an installed `arris-gym rescore benchcad` fails without `--slice` and `--targets`; resolve them from the package or require the flags
- `_cli.py`'s docstring names only `census`; `.github/workflows/ci.yml` comments cite deleted plans (`m0-sandbox`, `m5-rescore` step 9); `tools/check_layers.py` does not hold `rescore` against importing `train` (harmless until `train` exists)
- `radiusArc(tuple, num)` (834 BenchCAD calls) unlocks nothing alone: all 417 of its programs also need `sweep(call; isFrenet=bool)` (`pipe_elbow` 241), and `duct_elbow`'s 176 also need `rect`; lift `radiusArc` and `sweep` in one plan when `sweep` comes up on the reach curve (measured 2026-11-13, curve item 41; plans/lift-sphere)
- BENCHMARK-SURVEY.md's numbers (BenchCAD 0.768/0.601, 52 ISO families, 748 edit pairs; Text2CAD-Bench, MUSE, cadbench, CADWorld, CAD-Recode ~1M) are unverified until read in each paper; verify before C3's report cites them
- File with arris (SEED.md §10.6) whether a public `Model` reset or id-stable `read_body` would help consumers; the batch `classify_points` and cone-against-cone asks are filed (`../arris/docs/ideas/`)
- Compare `step_sha256` across machines: regenerate the slice's STEPs on the second architecture (ADR-0011 does not claim OCCT is equal across machines)
- `Score` does not check that an `ok` score's `reward` equals `combine(terms, config)`; a validator would refuse a forged one
- `sandbox/_zygote_main.py` imports `reward._job` to register the score handler, an edge `tools/check_layers.py` does not hold: allow only that module or register through a plugin point
- `fidelity/_oracle.py` imports the private `sandbox._run.ended` and `sandbox._zygote.Outcome`, so the public `parse_outcome` takes a private type: give `sandbox` a public outcome type or move the parse
- A crash on both sides is `agree` under ADR-0006, so it never reaches the arris report; decide whether `arris_rows` lists every arris `crash` regardless of outcome (gym.md: an arris crash goes to arris as a fixture candidate)
- `tools/check_layers.py` sees `import`, `from` and literal `importlib.import_module`; a computed name evades it, as it would evade any static check
- Decide whether the `cq` subset admits the bare `cq.Workplane()` (CadQuery's default plane) and `box(...; centered=False)`: all 19 calibration programs in `tests/fixtures/fidelity/` use one, so none runs under `cq` and `tests/test_cq_calibration.py` holds them to `unsupported_api` (a product question, in the knee's bundle order for C2)
- `tests/fixtures/cq/arris-refusal-three-point-arc-near-chord` keeps as expected a case the oracle builds and arris refuses (an arc 1e-8 off a chord of 2); gym.md wants such a case as an xfail `regression/` fixture with the desired `ok`: move it when the kernel's threshold is next read
- `cq/_workplane.py` `_uv` takes a `str.format` template for its refusal message; pass the call's name and build the message inside it
- arris 0.11.1 returns a top face with intersecting loops when two round posts sit on a box with footprints tangent to opposite edges. The same case predates sketches and is held by `regression/cq-rarray-posts-tangent-to-box`.
- Determine when CadQuery preserves a torus seam after a cut, then preserve those faces in `cq` (`regression/cq-workplane-on-a-cut-torus-crossing-its-seam`).
- `cq` keeps no CadQuery context along a chain: a `circle` on a stack other than one `moveTo` point, a stack of points or one pending circle, a `moveTo` on a pending wire, and `transformed`, `union`, `cut` on a pending wire and `box` on a drawn path or sketch or on a stack holding a solid (CadQuery centres it on the solid's centre), and a `polyline` of fewer than two points (CadQuery starts the next call from the origin), end `unsupported_api`; lift them in the knee's bundle order when a program writes them
- A target read from a STEP is exactly one solid (ADR-0011), so a re-scored corpus whose oracle builds a compound (827 BenchCAD oracle `ok` reports hold 2 to 9 solids) gets a `runtime` target; decide how a compound target is read before BenchCAD is re-scored beyond the slice (ADR-0016)
- `FIXTURE_DEADLINE` (60 s, `tests/fixture_cases.py`) hides a fixture's slowdown up to 12x past `run`'s 5 s default that users get: record each `ok` fixture's runtime or assert a bound so a speed regression shows; and `tests/test_regression.py` would run a future `timeout` regression fixture to 60 s five times, not to `TIMEOUT_DEADLINE`
- `cq`'s `workplane()` on a compound puts the plane at arris's centroid, while CadQuery uses Open CASCADE's `Center()`, which can be wrong for a compound (`cq/ok-compound-occt-centroid`): the two planes differ in that construction; add a fixture with a closed form if a corpus program reaches it
- A compound whose pieces hold cavities has more shells than oracle solids, so its row is `unclassified` under ADR-0016; count outer shells (the sign of each shell's tessellated volume) if a corpus shows one
- `show_object(x, color=...)` ends `runtime` (a `TypeError` from the builtin's signature) where the goal says an out-of-subset form is `unsupported_api`: route the builtin's form through `cq/_forms.py`
- `cq/_forms.py` `kind_of` decides the "call" kind by class name, so a program's own `class Vector` passes the form check, and `transformed(rotate=cq.Workplane("XY"))` ends `unsupported_api` as `Workplane.z`: decide by type
- `test_regression.py`'s strict `xfail(raises=AssertionError)` also covers the `sandbox.executions == REPEATS` assert, so a cache-hit bug would pass as the expected failure; and `fixture_cases.load`'s faces guard has no test
- Face counts in `tests/fixtures/cq/ok-*` are what arris produces (carried, ADR-0005), while gym.md says expected values never come from arris-gym's output: settle with the rule's author whether `faces` may be recorded for a fixture whose other measures are closed-form
- `sandbox/_program.py` imports the private `arris_gym.cq._result`; `tests/test_cq_calibration.py` carries literal tolerances (`rel=1e-12`, `abs=1e-9`) and plan history in its docstring; the 2 `lobed_knob` rows refused at the fourth union have only the n-ary rebuild as evidence, not a shrunk fixture
- Canonical JSON is hand-rolled in `_cli.py` `run_census` and `fidelity/_reach.py` `ReachReport.to_json` though `census._report._canonical` exists: use one
- `run_census` picks the slice by `if info == benchcad.INFO` instead of a field on the `CORPORA` entry
- `cylinder` on a solid, a path or a sketch ends `unsupported_api` before its height and radius are checked, so `box(1,1,1).cylinder(-1, 1)` is `unsupported_api` where CadQuery ends `runtime`; check the dimensions first if a corpus program reaches it
- The `occt_wrong` verdicts for the tee and hook families rest on a closed form checked only against arris and its quadrature; add a limiting case with an elementary answer (branch radius equal to the main radius, a hook with no cylinder overlap) so the check is independent of both kernels
- 176 `pull_handle` rows end `OpInternalError` ("kernel bug: the face arrangement is not a subdivision…") and are `arris_refusal` by ADR-0006's rule, though the kernel calls it a bug and C1's `lobed_knob` rows were raised to `arris_bug` by verdict; decide whether these get `arris_bug` verdicts
- Three BenchCAD programs outside the subset (`bearing_retainer_cap_014254`, `_015325`, `_016792`) end `OpInternalError` "a section edge of f38 ends at a node nothing else reaches"; shrink each to a `regression/` fixture and report it to arris
- `cq`'s `polygon(2, d)` ends `runtime` where CadQuery 2.3.0 builds a zero-volume solid its checker passes (`ok`): an in-subset `cq_bug` (ADR-0012), held by `regression/cq-polygon-two-sides` (strict `xfail`); the census cannot see a literal, so the form cannot leave the subset for it alone: build the out-and-back prism in `cq`, and ask arris (`../arris/docs/ideas/`) if the kernel refuses a zero-volume solid (plans/lift-polygon step 2)
- `faces` with a plane name (`"XY"`, `"YZ"`, `"XZ"`): 332 BenchCAD programs (`circlip` 182, `snap_clip` 150) all unlocked by it; CadQuery's `DirectionSelector` on a diagonal, not one of the knee's 35 items (plans/lift-edges-and-blends, non-goals)
- `center(num, num)` (a moved origin) rides with bundle 5's `rect`: 1,593 BenchCAD programs write it, none of them unlocked by it alone (plans/lift-arrays-and-blind-cuts, non-goals)
- `pushPoints` of `Vector` or `Location`, `cboreHole` and `cskHole` with `depth=` or `clean=`, `hole` with a positional depth, `rarray(center=)`, `polarArray(fill=, rotate=)`, `cutBlind(clean=, both=, taper=)` and `cutBlind` up to a face: lifted when a corpus program writes them
- File the two arris refusals of `regression/cq-cut-blind-after-a-filled-pocket` and `regression/cq-cut-blind-across-a-split-end-face` (a tool flush with a face split by an edge it crosses, `OpDegenerateError`) in `../arris/docs/ideas/`: both READMEs say "not yet reported"

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
- Where: arris 0.10.0 and 0.11.1 `Solid.fuse`, reached by `cq`'s `Workplane.union`
- Seen: `tools/cq_slice.py`, plans/m3-cq-subset step 8, BenchCAD `5919f578ab09ec283603a082fab07c7639ab56eb`, all 100 `lobed_knob` slice programs, 2026-11-08
- Reproduce: `uv run pytest --runxfail tests/test_regression.py -k cq-union-three-coplanar-cylinders`
- Measured: 100 of 100 refused (98 at the second union, 2 at the fourth); rebuilt by n-ary fuse, all 100 within 8e-15 of the oracle's volume
- State: regression/cq-union-three-coplanar-cylinders; reported in `../arris/docs/ideas/union-coplanar-third-operand.md`; lift the xfail and drop the 100 verdicts when an arris bump builds it

### interference-split-planar-faces
- What: `interference` of an arris-built body against the same part read from Open Cascade's STEP refuses (`OpDegenerateError`, "the faces touch along a curve interior to both result faces") when both are all planes but the STEP's coplanar faces are merged (the candidate has more faces); the pair then takes the sampled IoU route, not the exact one
- Where: arris 0.10.0 and 0.11.1 `Model.interference`, reached by `reward`'s exact IoU route; ADR-0008 measured `phone_stand` pairs of one split, never an arris body against an Open Cascade one
- Seen: plans/m5-rescore step 7, `arris-gym rescore benchcad`, BenchCAD `5919f578ab09ec283603a082fab07c7639ab56eb`, all 100 `phone_stand` slice pairs, 2026-11-09
- Reproduce: `uv run --extra corpus arris-gym rescore benchcad`, then the `iou_route` of the `phone_stand` rows in `rescore.json`
- Measured: 100 of 100 refused; the sampled IoU is 1.0 on all 100; the same body against itself answers 1.0 exactly
- State: measured; reported in `../arris/docs/ideas/interference-split-planar-faces.md`; no regression fixture (a pair of two bodies, not one program)

### torus-box-point-contact
- What: arris refuses the fuse of a torus and a box whose face touches the torus at its seam vertex (`arris_refusal`, "no closed form for +f6 (plane surface) against +v0 (point)"); the oracle builds two solids meeting at that point
- Where: arris 0.10.0 and 0.11.1 `Solid.fuse`, reached by `cq`'s `Workplane.union` after a revolved `circle`
- Seen: plans/in-subset-cq-bugs step 5, rerun of the 113 `circle`-cause rows of `tests/fixtures/c2/benchcad/cq-bugs.json`, BenchCAD `5919f578ab09ec283603a082fab07c7639ab56eb`, 43 `torus_link` programs (e.g. `torus_link_000353_s20260507`), 2026-11-12
- Reproduce: `cq.Workplane("XY").moveTo(3, 0).circle(1).revolve(360, (0, 0, 0), (0, 1, 0)).union(cq.Workplane("XY").transformed(offset=cq.Vector(5, 0, 0)).box(2, 2, 2))` under `dialect="cq"`; the oracle gives 2 solids, volume 6π² + 8
- Measured: 43 of 113 refused with that message, the other 70 agree. With the box moved 0.5 into the torus, `cq` builds it (volume 66.13564505370971) but the row is `unclassified`: the oracle's volume is 66.13565097373274, and a quadrature of the overlap gives 66.135645049 and converging, so Open CASCADE is the one off (about 9e-8 relative); a classing case for the oracle, not seen in the corpus
- State: regression/cq-torus-box-point-contact (the desired compound of ADR-0016, strict `xfail`); reported in `../arris/docs/ideas/fuse-contact-refusals.md`; 80 in-subset `torus_link` rows are refused so (plans/lift-cylinder step 5)

### sphere-pole-on-disc
- What: arris refuses the fuse of a sphere and a cylinder whose end disc touches the sphere's pole (`arris_refusal`, `OpUnsupportedError` "no closed form for +f1 (plane surface) against +f3 (sphere surface)", and three variants by operand order and by whether floating point puts the pole on the disc); the oracle builds two solids meeting at that point
- Where: arris 0.10.0 and 0.11.1 `Solid.fuse`, reached by `cq`'s `Workplane.union` after `sphere`
- Seen: plans/lift-sphere step 3, the re-run of both corpora after `sphere` was lifted, BenchCAD `5919f578ab09ec283603a082fab07c7639ab56eb`, `ball_knob_000027_s20260506`, 2026-11-13
- Reproduce: `uv run pytest --runxfail tests/test_regression.py -k sphere-pole`
- Measured: 231 `ball_knob` rows refused, 153 of them in the subset (the rest still miss another form); messages 53 (stem first), 66 (sphere first), 61 and 51 (a point); the oracle's volume and area equal the closed form to 1e-9 for three of the four shrunk fixtures (`-sphere-first`'s is the base fixture's two solids, the oracle not run on that operand order). The 191 `capsule` rows (tangent sphere and cylinder along a rim) all agree
- State: regression/cq-sphere-pole-on-disc, -sphere-first, -corpus, -cylinder (the desired compound of ADR-0016, strict `xfail`); reported in `../arris/docs/ideas/fuse-contact-refusals.md`

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

### fuse-tangent-and-point-contacts
- What: arris refuses a `fuse` whose operands touch along a line (two parallel cylinders, a box and a cylinder tangent to its face, a horizontal cylinder's end disc tangent to a vertical one) or at a point (a cone frustum's rim and a box), and for two of the shapes the refusal is an internal error (`OpInternalError`, "kernel bug: the face arrangement is not a subdivision"); Open CASCADE builds each as a compound of two solids or one solid, matching a closed form
- Where: arris 0.10.0 and 0.11.1 `Solid.fuse`, reached by `cq`'s `Workplane.union`
- Seen: plans/lift-cylinder step 5, the in-subset rows no rule could class once `cylinder` was lifted, BenchCAD `5919f578ab09ec283603a082fab07c7639ab56eb`, 2026-11-13
- Reproduce: `uv run pytest --runxfail tests/test_regression.py -k "tangent or rim-point"`
- Measured: `cotter_pin` 159 of 159 (tangent cylinders, the first union; their oracle report is `invalid`), `hinge` 61 of 61, `pull_handle` 176 of 176 (`OpInternalError`), `bucket` 3 at +x (`OpDegenerateError`, "shells would touch along an edge or at a vertex") and 3 at -x (`OpInternalError`, "a hole of f9 lies inside no region"); the oracle's volume and area equal each shrunk fixture's closed form to 1e-9 or better
- State: regression/cq-tangent-cylinders, cq-tangent-cylinder-and-box, cq-tangent-end-disc, cq-cone-box-rim-point, cq-cone-box-rim-point-far-side; reported in `../arris/docs/ideas/fuse-contact-refusals.md`; the 159 `cotter_pin` rows are `arris_refusal` by cq-tangent-cylinders (verdict in `tests/fixtures/c2/benchcad/verdicts.json`)

### horn-torus-revolve
- What: arris refuses a revolve of a circle that touches the axis (a half horn torus, R = r), `OpDegenerateError` "an arc's circle crosses the revolve axis: a spindle torus"; Open CASCADE builds it, volume pi^2 r^2 R
- Where: arris 0.10.0 and 0.11.1 `revolve`, reached by `cq`'s `Workplane.revolve` after `circle`
- Seen: plans/lift-cylinder step 5, the `cotter_pin` programs' last union (radius 4 at x = 4), BenchCAD `5919f578ab09ec283603a082fab07c7639ab56eb`, 2026-11-13
- Reproduce: `uv run pytest --runxfail tests/test_regression.py -k horn-torus`
- Measured: not reached by any corpus row (the tangent cylinders before it are refused first); the oracle's 631.65 for R = r = 4 is the closed form
- State: regression/cq-horn-torus; reported in `../arris/docs/ideas/fuse-contact-refusals.md`

### spindle-torus-revolve
- What: arris refuses a revolve of an arc that stays on one side of the axis while its circle crosses it (the outer part of a spindle torus), `OpDegenerateError` "an arc's circle crosses the revolve axis: a spindle torus"; Open CASCADE builds it, V = pi (236 + 225 pi - 225 asin(4/5)) / 3 on the fixtures; the horn-torus finding (a circle that touches the axis) is its neighbour
- Where: arris 0.10.0 and 0.11.1 `revolve`, reached by `cq`'s `Workplane.revolve` after `threePointArc`
- Seen: plans/lift-three-point-arc steps 3 and 4, BenchCAD `5919f578ab09ec283603a082fab07c7639ab56eb`, 2026-11-13
- Reproduce: `uv run pytest --runxfail tests/test_regression.py -k spindle-torus`
- Measured: 281 BenchCAD rows hit the message (`rivet` 122, `dome_cap` 159), 68 of them in the subset (`rivet` 32, the arc starts on the axis, at a slant, and `dome_cap` 36, the arc ends on it; its circle is centred 1.3e-4 off the axis from rounded points); the oracle's volume, area and centroid equal each fixture's closed form to 1e-12
- State: regression/cq-spindle-torus-arc-from-axis, cq-spindle-torus-arc-to-axis; reported in `../arris/docs/ideas/spindle-torus-revolve.md`

### slots-through-a-cylinder
- What: arris refuses the third of three slots cut 60 degrees apart through a cylinder's axis (`OpDegenerateError`, "the faces touch along a curve interior to both result faces"); two slots build, and Open CASCADE builds all three
- Where: arris 0.10.0 and 0.11.1 `Solid.cut`, reached by `cq`'s `Workplane.cut`
- Seen: plans/lift-cylinder step 5, BenchCAD `5919f578ab09ec283603a082fab07c7639ab56eb`, 81 `wall_anchor` programs, 2026-11-13
- Reproduce: `uv run pytest --runxfail tests/test_regression.py -k three-slots`
- Measured: 81 of 81 `wall_anchor` rows refused at the third slot; the oracle's volume and area equal the closed form to 1e-15
- State: regression/cq-three-slots-through-cylinder; reported in `../arris/docs/ideas/slots-through-a-cylinder.md`

### occt-wrong-tee-and-hook
- What: Open CASCADE's volume, area and centroid are off the closed form on three `cylinder` part families: `t_pipe_fitting` tees by 1e-8 to 1.5e-4 relative, `u_bolt` and `j_hook` (a half torus joined to cylinders) by up to 1e-5; arris is within 1e-10 of the closed form on all of them
- Where: CadQuery 2.3.0 / OCP 7.9.3.0 boolean and `GProp`, the oracle's rows
- Seen: plans/lift-cylinder steps 4 and 5, BenchCAD `5919f578ab09ec283603a082fab07c7639ab56eb`, 2026-11-13
- Reproduce: `uv run --extra corpus tools/cq_closed_forms.py --table T --oracle-rows tests/fixtures/c2/benchcad/oracle.jsonl.gz --out V.json` (each verdict is checked by `compare`)
- Measured: 64 `t_pipe_fitting`, 136 `u_bolt`, 125 `j_hook` rows and CAD-Recode `550` (two crossing cylinders, volume 2.6e-9) are `occt_wrong` by their closed forms (`tools/cq_closed_forms.py`); arris agrees with each to the ADR-0005 constants
- State: measured; classed `occt_wrong` by verdicts (`tests/fixtures/c2/*/verdicts.json`); no regression fixture, since the oracle is not under test here

### union-tangent-inside
- What: arris fails a `fuse` where one operand lies on the material side of the other's face and touches it along a line: a cylinder inside a larger one's circle, a plate whose arc lies inside a cylinder's circle, a bar's end face tangent to an end boss. It returns a body its checker refuses (L5, "loops 0 and 1 intersect", "loop 0 intersects itself") or raises `OpInternalError` ("a section edge of f0 ends at a node nothing else reaches"); Open CASCADE builds each, matching a closed form
- Where: arris 0.10.0 and 0.11.1 `Solid.fuse`, reached by `cq`'s `Workplane.union`; not `cq`'s `hole`, which each program ends with: they fail the same without it
- Seen: plans/lift-face-selectors step 7b, BenchCAD `5919f578ab09ec283603a082fab07c7639ab56eb`, `bearing_retainer_cap` (e.g. `_000183_s20260505`, `_000434_s20260507`, `_000542_s20260505`), 2026-11-14
- Reproduce: `uv run pytest --runxfail tests/test_regression.py -k "tangent-inside or end-cylinders-tangent"`
- Measured: 65 of 160 `bearing_retainer_cap` rows, all in the subset: 22 `checker_fail` slotted plates whose middle arc's rounded ends fall outside the cylinder, 25 `OpInternalError` whose ends fall inside it, 15 `checker_fail` and 3 `OpInternalError` bars with tangent end bosses (2 more of those `OpUnsupportedError`, 21 `ok`); the oracle's volume, area and centroid equal each fixture's closed form
- State: regression/cq-union-cylinder-tangent-inside, cq-union-end-cylinders-tangent, cq-union-arc-tangent-inside-cylinder (strict `xfail`); reported in `../arris/docs/ideas/union-tangent-inside.md`

### cross-hole-bounds
- What: arris's body box reaches past the part where a NURBS edge is its extent: a cylinder of radius 2 drilled across by a hole of radius 0.5 is boxed to y = +-2.0012, the hole's two side-wall edges boxed by their control hulls; volume, area and centroid are the closed form's. Open CASCADE gives the tight box but a volume 3e-5 off the closed form on the same part
- Where: arris 0.10.0 and 0.11.1 `Model.bounds(body)` (an outer bound over a NURBS curve, arris `DATA-MODEL.md` `Curve::bounds`), read by the sandbox's `Measures.bounds`; ADR-0005 holds a box to the part's extent plus 2e-7
- Seen: plans/lift-face-selectors step 7c, BenchCAD `5919f578ab09ec283603a082fab07c7639ab56eb`, `shaft_collar` `_004211`, `_004399`, `_007583`, `_017335`, `_017997` (`_s20260505`), 2026-11-14
- Reproduce: `uv run pytest --runxfail tests/test_regression.py -k cross-hole-bounds`
- Measured: those 5 rows, all in the subset, bounds 5e-4 to 1e-3 past the closed form along the set screw's axis; the oracle's volume 3e-6 to 1e-5 off it where computed (`_004211`, quadrature at 30 digits: arris 1.3e-10, the oracle 7.0e-6)
- Seen again: plans/lift-edges-and-blends step 7c: 81 `clevis_pin` programs (a cylinder chamfered at both rims, one or two cross holes; bounds 1e-3 to 5e-3 wide, the oracle's volume to 2.2e-5 off) and `spacer_ring_008375` (a chamfered ring slotted to a floor inside its thickness: the slot's walls cut the chamfer's cone in two NURBS hyperbolas, x max 0.037 past the part)
- State: regression/cq-cross-hole-bounds and regression/cq-chamfer-slot-bounds (strict `xfail`); the 5 `shaft_collar` and the 81 `clevis_pin` rows `arris_bug` by the first, `spacer_ring_008375` by the second (`tests/fixtures/c2/benchcad/verdicts.json` once step 8 re-runs), `occt_wrong` by a closed form once arris's box is tight; reported in `../arris/docs/ideas/tight-body-bounds.md`

- `cq` seam placement and closed-form tool hardening (plans/lift-edges-and-blends review): `_placed_key` tests `info.axis[axis] != 0.0` exactly where the rest of the function uses `angular_tolerance` (a cylinder on a `transformed` plane loses its seam placement and ends `unsupported_api`); `_closed_form_job` catches every `ValueError`, so a bug inside a closed form reads as "another arrangement" (a dedicated exception); `_with_seams` mutates a workplane after it is derived (safe today, fragile).
- The finer `faces` estimate pass tessellates at a chord of 1e-7 of the diagonal: measure its cost on large curved faces, since a slow machine turns it into a `timeout`, the one status wall-clock time may change.

### sprocket-fixture-near-the-default-deadline
- What: `cq/ok-sprocket-corpus-along-x` ends `timeout` on CI's ARM runner, failing the gate there; the fixture runs at the sandbox's default deadline, which its program nearly fills on any machine
- Where: `tests/test_cq.py::test_a_fixture_program_gives_its_expected_result`, `tests/fixture_cases.py` `run` (no per-fixture deadline), `sandbox/_run.py` `DEFAULT_TIMEOUT` = 5.0 s
- Seen: CI run 43722758106, job `test (ubuntu-24.04-arm)`, commit 6520054 (main), 2026-11-15; `test (ubuntu-latest)` green in the same run
- Reproduce: `uv run pytest tests/test_cq.py -k ok-sprocket-corpus-along-x` on a slow or loaded machine
- Measured: 4.55 s to `ok` alone on the development machine (AMD Ryzen 9 7950X, idle, arris 0.11.1), 91% of the deadline; on the ARM runner under the parallel gate, past 5 s
- State: fixed: every fixture not expected to time out runs to `FIXTURE_DEADLINE` = 60 s (`tests/fixture_cases.py`, `tests/test_regression.py`), not `run`'s 5 s default

### fidelity-digest-hashes-arris-gym-version
- What: `FidelityTable`'s digest is the SHA-256 of its whole canonical JSON, `versions.arris_gym` included, so a release of arris-gym alone moves every committed fidelity digest (C1, both C2 corpora), against ADR-0011's amendment ("arris-gym's own version is outside every digest")
- Where: `src/arris_gym/fidelity/_table.py` `_digest`
- Seen: plans/bump-arris-0-11 retirement review, 2026-11-16; C1's `fidelity.json` rows moved `arris_gym` 0.1.0.dev0 -> 0.2.0.dev0 with arris
- Reproduce: change `versions.arris_gym` in one row of `tests/fixtures/c1/fidelity.json` and recompute the digest
- Measured: every row of the C1 table records `arris_gym`; the rescore digest (`Score.digest()`) already leaves it out
- State: measured; drop `arris_gym` from the digest's body, as `Score.digest()` does, and re-record the three digests in one `fixtures:` commit

## Rejected

- The working name `arris-zero`: it suggested R1-Zero, pure RL with no supervised fine-tuning, which is not the plan (SEED.md §2)

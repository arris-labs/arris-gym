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
- Verify full-revolve seam placement for rotated frames with floating-point roundoff. A rotated cylinder's two-rim chamfer is held by `regression/cq-rotated-full-revolve-seam` (ADR-0020).
- Measure CadQuery's join tolerance before admitting near-coincident endpoints in `Sketch.assemble` (`regression/cq-sketch-assemble-near-endpoints` holds a 1e-8 gap that CadQuery joins).
- CadQuery's context is shared along a chain. The subset keeps pending
  sections on each branch (ADR-0026). Plane changes on slots, nested
  profiles, multiple visible wires and open paths end `unsupported_api`.
  Other limits include `moveTo`, `union` and `cut` on a visible pending
  wire, `box` on a drawn path, sketch or solid, `circle` on an unsupported
  stack and `polyline` with fewer than two points. Lift these in the knee's
  bundle order where written.
- A target read from a STEP is exactly one solid (ADR-0011), so a re-scored corpus whose oracle builds a compound (827 BenchCAD oracle `ok` reports hold 2 to 9 solids) gets a `runtime` target; decide how a compound target is read before BenchCAD is re-scored beyond the slice (ADR-0016)
- `FIXTURE_DEADLINE` (60 s, `tests/fixture_cases.py`) hides a fixture's slowdown up to 12x past `run`'s 5 s default that users get: record each `ok` fixture's runtime or assert a bound so a speed regression shows; and `tests/test_regression.py` would run a future `timeout` regression fixture to 60 s five times, not to `TIMEOUT_DEADLINE`
- `cq`'s `workplane()` on a compound puts the plane at arris's centroid, while CadQuery uses Open CASCADE's `Center()`, which can be wrong for a compound (`cq/ok-compound-occt-centroid`): the two planes differ in that construction; add a fixture with a closed form if a corpus program reaches it
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
- `pushPoints` of `Vector` or `Location`, `cboreHole` and `cskHole` with `depth=` or `clean=`, `hole` with a positional depth, `rarray(center=)`, `polarArray(fill=, rotate=)`, `cutBlind(clean=, both=, taper=)` and `cutBlind` up to a face: lifted when a corpus program writes them
- Extend nonzero `extrude(taper=)` to multiple pending profiles, polygons, slots, paths,
  finalized sketches or a carried wire with a different normal when a corpus
  writes those contexts. The oracle observations are in ADR-0027.
- Preserve the axis vertices of `mirrorY()` sections for lofting when a corpus writes that combination (ADR-0028).
- Revisit the 392 deferred gear lofts when arris exposes explicit section parameters and checks lofts with many curved sides within the corpus deadline (ADR-0012 and ADR-0026).
- File the two arris refusals of `regression/cq-cut-blind-after-a-filled-pocket` and `regression/cq-cut-blind-across-a-split-end-face` (a tool flush with a face split by an edge it crosses, `OpDegenerateError`) in `../arris/docs/ideas/`: both READMEs say "not yet reported"
- Investigate the three-way rectangular overlap in `regression/rects-three-way-overlap`, where arris refuses the union and the oracle builds an invalid part. No in-subset BenchCAD row shows it. The consumer report is `../arris/docs/ideas/fuse-three-overlapping-boxes.md`.
- Profile `double_simplex_sprocket_009154_s20260505`, which takes 29.6 s of the 30 s sandbox deadline when run alone. The consumer report is `../arris/docs/ideas/benchcad-through-cut-body-check-and-blends.md`.
- Investigate the converged oracle trim integral of `regression/oracle-slotted-ring-boundary`, which differs from its construction by 2.36e-8 relative in volume. The fixture is strict `xfail` and no verdict relies on it.

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

### oracle-shell-measures

- What: the oracle's reported measures differ from the construction after
  enclosure floor fillets and after chamfered tray shelling or through-cuts.
- Where: CadQuery 2.3.0 and Open CASCADE 7.9.3.0 mass properties as reported
  by `tools/oracle/worker.py`.
- Seen: the 330 BenchCAD shell stems at `8f2be71`, corpus revision
  `5919f578ab09ec283603a082fab07c7639ab56eb`, including
  `enclosure_001465_s20260505` and `sheet_metal_tray_017786_s20260505`.
- Reproduce: the command and operation counts in the
  [shell replay](../tests/fixtures/c2/benchcad/shell-replay/README.md).
- Measured: 11 enclosure and 51 tray rows exceed the agreement tolerance.
  Remeasuring their oracle STEP exports agrees with all 62 arris builds.
- State: strict regressions `oracle-shell-floor-fillet`,
  `oracle-shell-chamfered-rim-volume` and `oracle-shell-tray-through-cut`.
  Row verdicts are due in step 4 of [lift-shell](plans/lift-shell.md).

### draft-bounds-and-short-sections
- What: oblique draft bounds enclose more than the trimmed geometry. Drafts
  with a very short wedge or cap edge can fail section validation.
- Where: arris 0.12.0 `bounds`, `Sketch.revolve`, `Sketch.loft` and
  `Sketch.extrude`, through `Workplane.extrude(taper=)` (ADR-0027).
- Seen: oracle and closed-form comparisons on 2026-11-26, ADR-0027.
- Reproduce: `uv run --locked pytest --runxfail tests/test_regression.py -k cq-draft`.
- Measured: largest bound excesses of about 0.01745 for a tilted cone,
  0.03280 for a tilted 4 × 3 inward draft and 0.36603 for an in-plane
  rotated outward draft. A cap or wedge below the kernel's tolerance
  produces its typed refusal.
- State: strict regressions. Reported in
  `../arris/docs/ideas/analytic-draft-bounds-and-short-sections.md`.

### union-coplanar-third-operand
- What: arris refuses a chained `fuse` whose third operand shares an end plane with the first two's union (`OpDegenerateError`, "the faces touch along a curve interior to both result faces"); the n-ary `fuse` builds it
- Where: arris 0.10.0 and 0.11.1 `Solid.fuse`, reached by `cq`'s `Workplane.union`
- Seen: `tools/cq_slice.py`, plans/m3-cq-subset step 8, BenchCAD `5919f578ab09ec283603a082fab07c7639ab56eb`, all 100 `lobed_knob` slice programs, 2026-11-08
- Reproduce: `uv run pytest --runxfail tests/test_regression.py -k cq-union-three-coplanar-cylinders`
- Measured: 100 of 100 refused (98 at the second union, 2 at the fourth); rebuilt by n-ary fuse, all 100 within 8e-15 of the oracle's volume
- State: fixed in arris 0.12.0. The regression fixture passes and the 100 C1 `lobed_knob` verdicts are retired. The C2 replay finds that all 168 previously refused `lobed_knob` programs build and agree with the committed oracle reports.

### interference-split-planar-faces
- What: `interference` of an arris-built body against the same part read from Open Cascade's STEP refuses (`OpDegenerateError`, "the faces touch along a curve interior to both result faces") when both are all planes but the STEP's coplanar faces are merged (the candidate has more faces); the pair then takes the sampled IoU route, not the exact one
- Where: arris 0.10.0 and 0.11.1 `Model.interference`, reached by `reward`'s exact IoU route; ADR-0008 measured `phone_stand` pairs of one split, never an arris body against an Open Cascade one
- Seen: plans/m5-rescore step 7, `arris-gym rescore benchcad`, BenchCAD `5919f578ab09ec283603a082fab07c7639ab56eb`, all 100 `phone_stand` slice pairs, 2026-11-09
- Reproduce: `uv run --extra corpus arris-gym rescore benchcad`, then the `iou_route` of the `phone_stand` rows in `rescore.json`
- Measured: 100 of 100 refused; the sampled IoU is 1.0 on all 100; the same body against itself answers 1.0 exactly
- State: fixed in arris 0.12.0. All 100 slice pairs use exact IoU and retain IoU of 1.0, with unchanged body digests and numerical scores. The kernel's `query/interference-box-against-its-halves` fixture covers split coplanar faces.

### torus-box-point-contact
- What: arris refuses the fuse of a torus and a box whose face touches the torus at its seam vertex (`arris_refusal`, "no closed form for +f6 (plane surface) against +v0 (point)"); the oracle builds two solids meeting at that point
- Where: arris 0.10.0 and 0.11.1 `Solid.fuse`, reached by `cq`'s `Workplane.union` after a revolved `circle`
- Seen: plans/in-subset-cq-bugs step 5, rerun of the 113 `circle`-cause rows of `tests/fixtures/c2/benchcad/cq-bugs.json`, BenchCAD `5919f578ab09ec283603a082fab07c7639ab56eb`, 43 `torus_link` programs (e.g. `torus_link_000353_s20260507`), 2026-11-12
- Reproduce: `cq.Workplane("XY").moveTo(3, 0).circle(1).revolve(360, (0, 0, 0), (0, 1, 0)).union(cq.Workplane("XY").transformed(offset=cq.Vector(5, 0, 0)).box(2, 2, 2))` under `dialect="cq"`; the oracle gives 2 solids, volume 6π² + 8
- Measured: 43 of 113 refused with that message on 0.11.1, and the other 70 agree. With the box moved 0.5 into the torus, both kernels build one solid. The arris volume agrees with the independent overlap integral. The oracle volume differs by 8.9e-8 relative. See `regression/cq-torus-box-point-contact` for the calculation.
- State: fixed in arris 0.12.0. The point-contact fixture builds the expected compound and agrees with its recorded oracle. After the solid-count correction (ADR-0016), 147 of 150 BenchCAD `torus_link` programs agree, and the other three have checked `occt_wrong` verdicts.

### sphere-pole-on-disc
- What: arris refuses the fuse of a sphere and a cylinder whose end disc touches the sphere's pole (`arris_refusal`, `OpUnsupportedError` "no closed form for +f1 (plane surface) against +f3 (sphere surface)", and three variants by operand order and by whether floating point puts the pole on the disc); the oracle builds two solids meeting at that point
- Where: arris 0.10.0 and 0.11.1 `Solid.fuse`, reached by `cq`'s `Workplane.union` after `sphere`
- Seen: plans/lift-sphere step 3, the re-run of both corpora after `sphere` was lifted, BenchCAD `5919f578ab09ec283603a082fab07c7639ab56eb`, `ball_knob_000027_s20260506`, 2026-11-13
- Reproduce: `uv run pytest --runxfail tests/test_regression.py -k sphere-pole`
- Measured: 231 `ball_knob` rows refused, 153 of them in the subset (the rest still miss another form); messages 53 (stem first), 66 (sphere first), 61 and 51 (a point); the oracle's volume and area equal the closed form to 1e-9 for three of the four shrunk fixtures (`-sphere-first`'s is the base fixture's two solids, the oracle not run on that operand order). The 191 `capsule` rows (tangent sphere and cylinder along a rim) all agree
- State: fixed in arris 0.12.0. All four regression variants build the expected compound and all 231 `ball_knob` rows agree with the pinned oracle. Reported in `../arris/docs/ideas/fuse-contact-refusals.md`.

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
- State: on arris 0.12.0, `cq-tangent-cylinders`, `cq-tangent-cylinder-and-box` and `cq-cone-box-rim-point` pass. `cq-tangent-end-disc` and `cq-cone-box-rim-point-far-side` remain strict `xfail`. The 159 `cotter_pin` rows refuse at the head union and cite `cq-cotter-pin-self-contact` or `cq-cotter-pin-tangent-faces`. The 176 `pull_handle` rows still refuse. Reported in `../arris/docs/ideas/fuse-contact-refusals.md`.

### horn-torus-revolve
- What: arris refuses a revolve of a circle that touches the axis (a half horn torus, R = r), `OpDegenerateError` "an arc's circle crosses the revolve axis: a spindle torus"; Open CASCADE builds it, volume pi^2 r^2 R
- Where: arris 0.10.0 and 0.11.1 `revolve`, reached by `cq`'s `Workplane.revolve` after `circle`
- Seen: plans/lift-cylinder step 5, the `cotter_pin` programs' last union (radius 4 at x = 4), BenchCAD `5919f578ab09ec283603a082fab07c7639ab56eb`, 2026-11-13
- Reproduce: `uv run pytest --runxfail tests/test_regression.py -k horn-torus`
- Measured: on 0.11.1, the tangent-cylinder union refused first on all 159 `cotter_pin` rows. The oracle's 631.65 for R = r = 4 is the closed form.
- State: fixed in arris 0.12.0. The `regression/cq-horn-torus` fixture builds and all 159 `cotter_pin` programs reach the subsequent union. Reported in `../arris/docs/ideas/fuse-contact-refusals.md`.

### spindle-torus-revolve
- What: arris refuses a revolve of an arc that stays on one side of the axis while its circle crosses it (the outer part of a spindle torus), `OpDegenerateError` "an arc's circle crosses the revolve axis: a spindle torus"; Open CASCADE builds it, V = pi (236 + 225 pi - 225 asin(4/5)) / 3 on the fixtures; the horn-torus finding (a circle that touches the axis) is its neighbour
- Where: arris 0.10.0 and 0.11.1 `revolve`, reached by `cq`'s `Workplane.revolve` after `threePointArc`
- Seen: plans/lift-three-point-arc steps 3 and 4, BenchCAD `5919f578ab09ec283603a082fab07c7639ab56eb`, 2026-11-13
- Reproduce: `uv run pytest --runxfail tests/test_regression.py -k spindle-torus`
- Measured: 281 BenchCAD rows hit the message (`rivet` 122, `dome_cap` 159), 68 of them in the subset (`rivet` 32, the arc starts on the axis, at a slant, and `dome_cap` 36, the arc ends on it; its circle is centred 1.3e-4 off the axis from rounded points); the oracle's volume, area and centroid equal each fixture's closed form to 1e-12
- State: the `cq-spindle-torus-arc-from-axis` and `cq-spindle-torus-arc-to-axis` fixtures build on arris 0.12.0. All 122 `rivet` rows build, with 90 receiving closed-form verdicts. Reported in `../arris/docs/ideas/spindle-torus-revolve.md`.

### slots-through-a-cylinder
- What: arris refuses the third of three slots cut 60 degrees apart through a cylinder's axis (`OpDegenerateError`, "the faces touch along a curve interior to both result faces"); two slots build, and Open CASCADE builds all three
- Where: arris 0.10.0 and 0.11.1 `Solid.cut`, reached by `cq`'s `Workplane.cut`
- Seen: plans/lift-cylinder step 5, BenchCAD `5919f578ab09ec283603a082fab07c7639ab56eb`, 81 `wall_anchor` programs, 2026-11-13
- Reproduce: `uv run pytest --runxfail tests/test_regression.py -k three-slots`
- Measured: 81 of 81 `wall_anchor` rows refused at the third slot; the oracle's volume and area equal the closed form to 1e-15
- State: fixed in arris 0.12.0. The `cq-three-slots-through-cylinder` fixture passes and all 81 formerly refused `wall_anchor` rows agree. Reported in `../arris/docs/ideas/slots-through-a-cylinder.md`.

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
- State: the three original tangent-union fixtures pass on arris 0.12.0. The 24 cap builds that fail the checker have verified plate-union verdicts citing `regression/cq-retainer-plate-arc-loop-intersection` (strict `xfail`). Reports are in `../arris/docs/ideas/union-tangent-inside.md` and `../arris/docs/ideas/retainer-plate-arc-union.md`.

### cross-hole-bounds
- What: arris's body box reaches past the part where a NURBS edge is its extent: a cylinder of radius 2 drilled across by a hole of radius 0.5 is boxed to y = +-2.0012, the hole's two side-wall edges boxed by their control hulls; volume, area and centroid are the closed form's. Open CASCADE gives the tight box but a volume 3e-5 off the closed form on the same part
- Where: arris 0.10.0 and 0.11.1 `Model.bounds(body)` (an outer bound over a NURBS curve, arris `DATA-MODEL.md` `Curve::bounds`), read by the sandbox's `Measures.bounds`; ADR-0005 holds a box to the part's extent plus 2e-7
- Seen: plans/lift-face-selectors step 7c, BenchCAD `5919f578ab09ec283603a082fab07c7639ab56eb`, `shaft_collar` `_004211`, `_004399`, `_007583`, `_017335`, `_017997` (`_s20260505`), 2026-11-14
- Reproduce: `uv run pytest --runxfail tests/test_regression.py -k cross-hole-bounds`
- Measured: those 5 rows, all in the subset, bounds 5e-4 to 1e-3 past the closed form along the set screw's axis; the oracle's volume 3e-6 to 1e-5 off it where computed (`_004211`, quadrature at 30 digits: arris 1.3e-10, the oracle 7.0e-6)
- Seen again: plans/lift-edges-and-blends step 7c: 81 `clevis_pin` programs (a cylinder chamfered at both rims, one or two cross holes; bounds 1e-3 to 5e-3 wide, the oracle's volume to 2.2e-5 off) and `spacer_ring_008375` (a chamfered ring slotted to a floor inside its thickness: the slot's walls cut the chamfer's cone in two NURBS hyperbolas, x max 0.037 past the part)
- State: `regression/cq-cross-hole-bounds` and `regression/cq-chamfer-slot-bounds` remain strict `xfail`. The 0.12.0 replay adds 11 verified `shaft_collar` bounds verdicts. Reported in `../arris/docs/ideas/tight-body-bounds.md`.

### revolved-cone-notch-bounds
- What: a blind cut clips a conical rim, but the reported X bounds still extend to the uncut rim.
- Where: arris 0.12.0 `Model.bounds(body)`, read by the sandbox into `Measures.bounds`.
- Seen: the BenchCAD 0.12.0 replay at revision `5919f578ab09ec283603a082fab07c7639ab56eb`, detailed in `tests/fixtures/c2/benchcad/measure-replay.md`.
- Reproduce: `uv run --locked pytest --runxfail tests/test_regression.py -k cq-revolved-cone-notches-bounds`.
- Measured: 40 `bellows` programs exceed the constructed extents. The reduced case gives X ≈ ±10.000000115 against the closed form ±9.8.
- State: strict `xfail`, `regression/cq-revolved-cone-notches-bounds`. Reported in `../arris/docs/ideas/revolved-cone-notch-bounds.md`.

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

### gear-loft-body-check-time
- What: the body worker hits the 30 s corpus deadline checking and measuring lofts with many curved sides
- Where: arris 0.12.0, loft body read, full check and measures in the sandbox
- Seen: ADR-0026 (2026-11-26), BenchCAD `5919f578ab09ec283603a082fab07c7639ab56eb`
- Reproduce: keep the chain through the first loft in the three stems under `tests/fixtures/lofts/README.md` and return that loft
- Measured: all three loft-only prefixes time out in the body worker, and the same builds returning a box take 0.029–0.036 s
- State. ADR-0026 defers 299 two-section gear lofts with too many curved
  sides and 93 three-section gear lofts with an interpolation gap. The
  consumer report is `../arris/docs/ideas/benchcad-loft-interpolation-and-body-check.md`.

### loft-follow-on-bounds-and-blends
- What: a completed propeller has a bounding-box gap, and two wing nuts receive a later fillet refusal
- Where: provisional arris 0.12.0 loft adapter, after the first loft
- Seen: ADR-0026 (2026-11-26), BenchCAD `5919f578ab09ec283603a082fab07c7639ab56eb`
- Reproduce: run the completed `propeller_000111_s20260505`, `wing_nut_000008_s20260505` and `wing_nut_000078_s20260505` and compare the pinned oracle rows
- Measured: the propeller's bounds differ by 9.69; the wing nut oracle reports `ok` and `invalid` respectively; the loft-only controls agree
- State: reduced in `regression/cq-turned-blade-prism-bounds` and
  `regression/cq-wing-nut-bore-fillet-corner`. Full-program verdicts are
  tracked in the [replay diagnosis](../tests/fixtures/c2/benchcad/loft-replay/diagnosis.md).

### filleted-beam-bore-arrangement

- What. A through bore in a filleted I-beam fails the kernel's face arrangement.
- Where. arris 0.12.0 via `Workplane.hole` after the flange fillet.
- Seen. `i_beam_008928_s20260505` and `i_beam_010860_s20260505` in BenchCAD
  at revision `5919f578ab09ec283603a082fab07c7639ab56eb`.
- State. `regression/cq-filleted-beam-through-bore` retains the desired
  one solid. Removing the fillet lets the bore build. The consumer report
  is `../arris/docs/ideas/bore-through-a-filleted-beam.md`.

### loft-bounds-too-wide
- What: the bounds are wider than the extreme points of the lofted solid
- Where: arris 0.12.0, bounds on a `Sketch.loft` body
- Seen: ADR-0026's two-section lift on 2026-11-26
- Reproduce: `tests/fixtures/regression/cq-loft-{triangle,tilted-cone,twisted-polygon}-bounds`
- Measured: X min is near −1.25 for the triangle against −1, Y max is near 1.99969549 for the cone against 1.98224298, and the twisted polygon's largest bound gap is 0.27602
- State: strict regressions with closed-form bounds and recorded oracle evidence; filed in `../arris/docs/ideas/loft-tight-bounds.md`

### mirrored-arc-bounds

- What. Extruding a profile of arcs rotated in its plane leaves bounds wider than the circular extrema.
- Where. arris 0.12.0 on a `Loop.path` of two arcs followed by extrusion.
- Seen. ADR-0028, 2026-11-26.
- Reproduce. `uv run pytest --runxfail tests/test_regression.py -k arris-mirror-y`.
- Measured. The maximum excess is 0.47914 for the two major arcs and 0.73205 for the two semicircles.
- State. Strict regressions with exact bounds and recorded oracle reports. Filed in `../arris/docs/ideas/extruded-arc-profile-bounds.md`.

### mirror-y-touch-and-near-joins

- What. A path touching the axis between its ends creates a loop that the kernel refuses. Near-axis sloped lines and arcs need a join that preserves the supporting curves and their measures.
- Seen. ADR-0028, 2026-11-26.
- Reproduce. `regression/cq-mirror-y-pinch` and `arc-gap` and `sloped-gap` in `tests/fixtures/mirrors/contexts.json`.
- State. The touch case is a strict regression. The near-axis cases remain typed refusals with recorded oracle reports.

### mirrored-benchcad-follow-on-measures

- What. One sampled gusset and one sampled I-beam agree through extrusion and have measure gaps after their later blends and bores.
- Seen. ADR-0028, 2026-11-26, BenchCAD `5919f578ab09ec283603a082fab07c7639ab56eb`.
- Reproduce. Compare the shared prefixes and full programs of `gusseted_bracket_000041_s20260507` and `i_beam_000007_s20260505`.
- Measured. The gusset has a bounds excess of 0.26641 after drilling. The I-beam has a relative volume gap of 1.29e-9.
- State. Reduced in `regression/cq-mirrored-gusset-chamfer-bounds`,
  `regression/oracle-filleted-gusset-bore` and
  `regression/oracle-filleted-beam-bore`. The
  [replay evidence](../tests/fixtures/c2/benchcad/loft-replay/README.md)
  records the checked full-program verdicts.

## Rejected

- The working name `arris-zero`: it suggested R1-Zero, pure RL with no supervised fine-tuning, which is not the plan (SEED.md §2)

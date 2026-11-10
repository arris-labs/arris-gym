# C1 census and slice

`census.json` is `arris-gym census --corpus benchcad` run on BenchCAD
`code_gen` at revision `5919f578ab09ec283603a082fab07c7639ab56eb`; `slice.txt`
lists the 300 stems of the C1 slice (the first 3 ranked families with at
least 100 programs, the first 100 stems of each). Both hold counts and
stems: no program text. Digest of the census:
`043db6d912c7b77e4b0bc570b9160b2153286279f11a69ceccc57a63193d13ee`
(two runs equal).

## Result

- 17,900 programs: 17,900 parsed, 0 unparsable (none to list).
- 106 families. Every program ends in `show_object(result)`.
- No call has the receiver `?`: every call has a known root. Foreign calls
  (not ranked): `builtin.show_object` only.
- The slice's families, in rank order: `phone_stand` (192 programs; 6 calls,
  0 selector strings), `venturi_tube` (191; 6/0), `lobed_knob` (168; 7/0).

## The slice on the oracle

`oracle.jsonl` has one row per slice stem, sorted by stem: the stem, family,
licence (`CC-BY-4.0`), the corpus revision above and the oracle's report
(`OracleReport` less its wall-clock `seconds`), from CadQuery 2.3.0 on
`cadquery-ocp` 7.9.3.0, Python 3.12.3. Written by
`uv run --extra corpus tools/oracle_run.py --slice tests/fixtures/c1/slice.txt
--workers 16` (network; outside the gate). Digest, the SHA-256 of the file:
`6bbfb7724508505b44e664d1b74d16c2ce70bf777d2c8e70e86de93cd3add68b`
(three runs equal, at 8 and 16 workers; a fourth, after the worker began
sending its STEP text back (ADR-0011), equal too: the text is left out of
the rows).

Status counts over all 300 programs:

- ok: 300
- syntax: 0
- runtime: 0
- no_result: 0
- invalid: 0
- timeout: 0
- crash: 0

No program timed out or crashed, and Open CASCADE failed on none (so none
waits for its M3 row); each result is one solid.

## The slice under `cq`

`fidelity.json` is the fidelity table of the 300 slice programs run under
`dialect="cq"` against `oracle.jsonl` (ADR-0006), with `arris-report.json`
and `arris-report.md` taken from it. Written by
`uv run --extra corpus tools/cq_slice.py` (the corpus from the Hugging Face
cache or the network; outside the gate; about 2 s on 32 cores, the sandbox's
defaults of 30 s and 512 MiB). Digests: table
`0c4ae42ed1307b69e8afd58f303959d30f1df2c981efb2a4e1862fa498af8733`;
the 300 oracle reports' digests (`OracleReport.digest()`, one per line, in stem
order) `e8879b59d640b3948f0e69abbd4b228414587466cc2dac2c2e2425edfc5065bc`;
`arris-report.json` SHA-256
`1b7d0494fcb3b4262bf942337ea219e8024468adc1314d55d417f944b6eeddee`, `arris-report.md`
`bb1ed67341600b7a4350460a1e233471de086961617ece5abc531ce1bfbf211a`
(two runs equal, at 2 and 32 workers).

`verdicts.json` (stem → verdict, ADR-0006) classes the 100 `lobed_knob` rows
`arris_bug`, its evidence the regression fixture
`tests/fixtures/regression/cq-union-three-coplanar-cylinders`; SHA-256
`c160894db5433de28971dee240aafab09aeba0b8a46f4f0f3b68a206970a9f18`.

Over all 300 programs: agree 200, disagree 100, unclassified 0. Disagreements
by class: `arris_bug` 100, every other class 0. Arris statuses: ok 200,
`arris_refusal` 100, every other 0; oracle statuses: ok 300. No timeouts.
All 100 `phone_stand` and 100 `venturi_tube` programs agree. All 100
`lobed_knob` programs end `OpDegenerateError` ("degenerate result: the faces
touch along a curve interior to both result faces") in a union of a cylinder
standing on the plane the body's end already lies on (98 at the second
union, 2 at the fourth), where the oracle builds a solid. The rule classes
that `arris_refusal`; the verdict re-classes it an arris bug, since arris
builds the same part: the programs' cylinders fused by one n-ary
`Solid.fuse` (then cut) match the oracle's volume to 8e-15 relative, all 100.
The fixture's README holds the shrink.

## The slice's targets

`targets.jsonl.gz` holds the target of each slice program for M5 (ADR-0011):
the oracle's STEP of the same program, one JSON line per stem (`stem`,
`step_sha256`, `step`), sorted by stem, gzipped with `mtime=0` (1.5 MB). The
STEP text has `FILE_NAME`'s timestamp and the translator counter blanked, and
each `step_sha256` equals the one in `oracle.jsonl`. Written by
`uv run --extra corpus tools/oracle_run.py --slice tests/fixtures/c1/slice.txt
--workers 16 --targets tests/fixtures/c1/targets.jsonl.gz` (network; outside
the gate); the same run leaves `oracle.jsonl` byte-identical. Read by
`read_target` in a step worker, never by anything that trusts it.

## The re-scored table

`rescore.json` and `rescore.md` are the 300 slice programs run under `cq`
and scored against their targets: `uv run --locked --extra corpus arris-gym
rescore benchcad --out DIR --workers N` (network once, for the corpus; outside
the gate). Digest `f89bce241c80fa1deadd9a662c38b0b6095c5ad4277c5f6ab7a6735c5b1c7812`,
equal from a run at 2 workers and a run at 16 (the two `rescore.json` files are
byte-identical). 300 rows: `ok` 200, `arris_refusal` 100, every other status
0; stages `none` 200, `program` 100; IoU routes `exact` 100, `sampled` 100;
timeouts none. Invalidity 1/3; mean reward 0.483560 over all 300, and 0.975340
over the 200 valid ones alone (survivors, never reported without the first).
Each row carries the source, CC-BY-4.0, and the arris, numpy and reward versions.

Across machines (CI run 42709431327 on commit 9d25b86, all 4 jobs green): the
digest `f89bce241c80fa1deadd9a662c38b0b6095c5ad4277c5f6ab7a6735c5b1c7812` was
equal on three machines of two architectures:

- the development machine: AMD Ryzen 9 7950X, x86-64, glibc 2.39;
- GitHub `ubuntu-latest`: AMD EPYC 7763, x86-64, glibc 2.43;
- GitHub `ubuntu-24.04-arm`: ARM Neoverse-N2, aarch64, glibc 2.39.

So `transformed`'s libm did not move any body's bytes between x86-64 and
aarch64.

Why the rows look as they do (the `inspect` skill, probed on the pairs):

- **The 100 `arris_refusal`** are all `lobed_knob`, ending `OpDegenerateError`
  ("the faces touch along a curve interior to both result faces"): reward -0.5
  and stage `program`, as planned (the arris fix is out of scope).
- **`phone_stand` takes the sampled route on all 100.** The exact route asks
  `interference` of the candidate against the target and the kernel answers
  `OpDegenerateError` with the same words ("the faces touch along a curve
  interior to both result faces"), though every face is a plane; a body
  against itself answers 1.0. The cause is the pair, not the part: the
  candidate has 14 or more planar faces and the target, read from Open
  Cascade's STEP, fewer (it merges coplanar faces), so coincident faces split
  differently meet along curves. ADR-0008's `phone_stand` pairs were arris-built
  perturbations of one body with the same split, so all 900 answered; "refusals
  only cone against cone" holds for those, not for an arris body against an
  Open Cascade one. The IoU is 1.0 on all 100 by the sampled route all the same.
  Filed as a Finding in `docs/BACKLOG.md` (arris: interference of coincident
  planar faces split differently).
- **`phone_stand`'s `topology` is 0.80 to 0.91 and `venturi_tube`'s is 1.0**
  for the same reason: `topology` is ½ · Σmin/Σmax over the face-kind histogram
  plus ½ · 1/(1 + |Δgenus|) (ADR-0009). All of `phone_stand`'s faces are planes,
  the candidate has more of them than the target on all 100, and the formula
  recomputed from the two bodies' measures equals the recorded term on all 100
  (for the first, 10 planes against 14: ½ · 10/14 + ½ = 0.857); `venturi_tube`'s
  candidate and target have identical histograms (4 cones, 6 cylinders,
  2 planes for the first) and genus.
- **`surface` is 0.85 to 0.89** in both families: the two bodies are the same
  surface, so the term is exp(−d/τ) of the sampling's own noise floor, d between
  0.0063 and 0.0083 (ADR-0009), and exp(−0.0083/0.05) = 0.847. The recorded
  minima are 0.847 (`venturi_tube`) and 0.858 (`phone_stand`, floor 0.0077:
  0.857). `iou` is 1.0 and `measures` at least 0.99999999999 on all 200.

## Attribution

BenchCAD (`BenchCAD/BenchCAD` on Hugging Face), licensed CC-BY-4.0. The stems
and the counts derived from the programs are adapted from it; they are
shared under the same licence. `oracle.jsonl` adapts the programs' measures
and STEP hashes from the same source and is shared under CC-BY-4.0 too;
`targets.jsonl.gz` holds STEP files built from those programs, and
`rescore.json` and `rescore.md` the scores of those programs against them;
both are shared under CC-BY-4.0 as well.

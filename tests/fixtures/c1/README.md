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
the rows). Two more, through oracle zygotes (ADR-0013) at 16 and 4 workers,
are byte-equal to it, `targets.jsonl.gz` too.

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
defaults of 30 s and 512 MiB). Digests for arris 0.12.0:

- Fidelity table `34c28fcc2fcef4ae2635fadd4d3975d06b3c0f14fe6ef46c7b2030bec3979a22`.
- The 300 oracle reports' digests (`OracleReport.digest()`, one per line,
  in stem order) `e8879b59d640b3948f0e69abbd4b228414587466cc2dac2c2e2425edfc5065bc`,
  unchanged from 0.11.1.
- `arris-report.json` SHA-256
  `38c7f5ecaea2c4a6e405bed6f36451384491301c576fe0115c1a7efc6d885584`.
- `arris-report.md` SHA-256
  `e094ce9dcf8bb688b4589eafcb8e94d5a70437acd2c3b717b0c0692c95264dee`.

All 300 programs build and agree with the oracle under ADR-0005. There are
zero disagreements, unclassified rows and timeouts. The 100 `lobed_knob`
programs now complete their chained cylinder fuses, previously
`OpDegenerateError` in the second fuse for 98 and the fourth for two
(`regression/cq-union-three-coplanar-cylinders`). All 100 agree under the
comparison rule, so their `arris_bug` verdicts are retired. The largest
relative errors are 7.90e-15 for volume and 1.03e-14 for area. Face counts
differ by up to 128, a diagnostic under ADR-0005.

The 200 `phone_stand` and `venturi_tube` rows still agree. Besides the
recorded arris version, 82 `phone_stand` rows change only their recorded
bounds deltas, by at most 5.69e-14. The arris report has no refusals or bugs.

The 0.11.1 table had digest
`b282d691220e98af5c6478364b4e0b8319058f7affc54ab553ec47c89a9dc7f6` and
the 0.10.0 table had digest
`0c4ae42ed1307b69e8afd58f303959d30f1df2c981efb2a4e1862fa498af8733`.
Their rows differed only in recorded versions.

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
the gate). Digest `8621e0ccf239cfb4b0322c9fc75681d760308dcbc0dfeb972be563c7ae88d0cd`
(arris 0.11.1, plans/bump-arris-0-11 step 5), equal from a run at 2 workers and a run at 16 (the two `rescore.json` files are
byte-identical). 300 rows: `ok` 200, `arris_refusal` 100, every other status
0; stages `none` 200, `program` 100; IoU routes `exact` 100, `sampled` 100;
timeouts none. Invalidity 1/3; mean reward 0.483560 over all 300, and 0.975340
over the 200 valid ones alone (survivors, never reported without the first).
Each row carries the source, CC-BY-4.0, and the arris, numpy and reward versions.
Under arris 0.10.0 the digest was
`f89bce241c80fa1deadd9a662c38b0b6095c5ad4277c5f6ab7a6735c5b1c7812`; the
0.11.1 table differs from it in each row's `versions.arris` alone, every
status, measure, IoU route and reward bit-equal (ADR-0021: the reward's
version stays 1).
Across machines on arris 0.11.1 (CI run 43946448566 on commit 4f3431f, both
`rescore` jobs green): the digest
`8621e0ccf239cfb4b0322c9fc75681d760308dcbc0dfeb972be563c7ae88d0cd` was equal
on `ubuntu-latest` (x86-64) and `ubuntu-24.04-arm` (aarch64), as on the
development machine; CI run 43952222713 on commit 59a9499 is green on all
four jobs.

Across machines under arris 0.10.0 (CI run 42709431327 on commit 9d25b86, all 4 jobs green): the
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

`reach-programs.jsonl.gz` adds the census of each of the 300 slice programs,
with its source, revision, licence and program SHA-256, without program text
(ADR-0012). It was parsed from the pinned corpus's cached Parquet files,
ordered by stem, written as canonical JSON lines and gzipped with `mtime=0`.
The SHA-256 of the uncompressed JSON lines is
`242c6a43bb55ac6bdcc692b90e5f5c295f54a1d03f3b1e7ad6c6a59d29fc45cb`.
The initial subset admits all 300. These derived counts share the same
CC-BY-4.0 attribution below.

BenchCAD (`BenchCAD/BenchCAD` on Hugging Face), licensed CC-BY-4.0. The stems
and the counts derived from the programs are adapted from it; they are
shared under the same licence. `oracle.jsonl` adapts the programs' measures
and STEP hashes from the same source and is shared under CC-BY-4.0 too;
`targets.jsonl.gz` holds STEP files built from those programs, and
`rescore.json` and `rescore.md` the scores of those programs against them;
both are shared under CC-BY-4.0 as well.

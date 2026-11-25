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
the gate). On arris 0.12.0, runs at 2 and 16 workers produced
byte-identical JSON and Markdown with digest
`7653aec26a1f12111b53e4ec7587b926431eb68a9628a3b95443a3107ba23551`.
Both [CI rescore jobs](https://github.com/arris-labs/arris-gym/actions/runs/45691768350)
on commit `3a817e6` reproduced that digest: `ubuntu-latest` (x86-64)
and `ubuntu-24.04-arm` (aarch64).
All 300 rows are `ok`, stage `none`, with exact IoU of 1.0. No row timed
out. Invalidity is 0 and mean reward is 0.964561 over all 300 programs.
Each row carries the source, CC-BY-4.0, and the arris, NumPy and reward
versions.

Compared with the 0.11.1 reports committed in `bd4c0bd`,
`tools/rescore_diff.py` first locates changes at the program on 100 rows,
at the IoU route on 100 and at versions on 100. The program and target
STEP hashes and the target body digests match on all 300 rows. The
reward stays at version 1 under ADR-0021.

- **`lobed_knob` (100).** The chained cylinder fuses now build
  (`regression/cq-union-three-coplanar-cylinders`). All 100 rows move
  from `arris_refusal` at stage `program` and reward −0.5 to `ok` with
  rewards of 0.9391 to 0.9526. The measures term is within 1e-13 of 1.
  The genus matches on every pair. The candidate has 17 to 128 more faces
  than the target. The face-kind histograms reproduce topology of 0.5461
  to 0.6964 on all 100 pairs (ADR-0009). For `lobed_knob_000072_s20260505` the
  candidate has 67 planes and 9 cylinders, and the target has 3 planes
  and 8 cylinders. The topology term is ½ + ½ · 11/76. The surface term
  (0.8467 to 0.8577) measures distance between finite draws from the two
  tessellations. The field metrics use their own mesh chord and
  normalization (ADR-0010), giving voxel IoU of 0.9613 to 1.0 and
  Chamfer ×10³ of 0.9325 to 1.0615.
- **`phone_stand` (100).** All move from sampled to exact IoU, with IoU
  still 1.0 and every numerical score and field metric bit-equal. Both
  body digests are unchanged. For `phone_stand_000059_s20260505`, the
  candidate has 14 planes and the target 10. On 0.11.1 the kernel's
  `interference` refuses that pair with `OpDegenerateError` because the
  coplanar faces are split differently. On 0.12.0 it reports overlap with
  both containment flags. The face split still lowers topology to
  0.8036–0.9091 across the family. See `docs/BACKLOG.md`, Finding
  `interference-split-planar-faces`.
- **`venturi_tube` (100).** Only `versions.arris` changes. The exact
  route, both body digests, and every numerical score and field metric
  match the 0.11.1 table. The face-kind histograms and genus match within
  each pair, so topology is 1.0 on all 100 rows.

### Earlier digests

On 0.11.1, 200 rows were `ok` and 100 were `arris_refusal`, with 100 exact
and 100 sampled IoU routes and no timeouts. Mean reward was 0.483560 over
all 300 programs and 0.975340 over the 200 valid programs. The digest
`8621e0ccf239cfb4b0322c9fc75681d760308dcbc0dfeb972be563c7ae88d0cd`
matched locally at 2 and 16 workers and in CI run 43946448566 on commit
`4f3431f` on `ubuntu-latest` (x86-64) and `ubuntu-24.04-arm` (aarch64).
CI run 43952222713 on `59a9499` passed all four jobs.

On 0.10.0, the digest
`f89bce241c80fa1deadd9a662c38b0b6095c5ad4277c5f6ab7a6735c5b1c7812`
matched locally and on both CI architectures (run 42709431327, commit
`9d25b86`). The 0.11.1 rows differed from that table only in the recorded
arris version.

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

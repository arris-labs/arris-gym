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

## Attribution

BenchCAD (`BenchCAD/BenchCAD` on Hugging Face), licensed CC-BY-4.0. The stems
and the counts derived from the programs are adapted from it; they are
shared under the same licence. `oracle.jsonl` adapts the programs' measures
and STEP hashes from the same source and is shared under CC-BY-4.0 too.

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
(three runs equal, at 8 and 16 workers).

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
`d975e910fe1c6d02923d0f2705d8516e2adbd40df5d6e8bb185c320a40f5e7d5`;
the 300 oracle reports' digests (`OracleReport.digest()`, one per line, in stem
order) `e8879b59d640b3948f0e69abbd4b228414587466cc2dac2c2e2425edfc5065bc`;
`arris-report.json` SHA-256
`f3f43fde375226106623fb9909e06a3b6d760df76d61a54c3ab9d69c8bdf3385`, `arris-report.md`
`c588ff5bca422f6263ee663271d4d85dd8ad654bed16c428b845ecb3750da02d`
(three runs equal, at 2 and 32 workers). `verdicts.json` does not exist yet.

Over all 300 programs: agree 200, disagree 100, unclassified 0. Disagreements
by class: `arris_refusal` 100, every other class 0. Arris statuses: ok 200,
`arris_refusal` 100, every other 0; oracle statuses: ok 300. No timeouts.
All 100 `phone_stand` and 100 `venturi_tube` programs agree; all 100
`lobed_knob` programs end `OpDegenerateError` ("the faces touch along a curve
interior to both result faces") in a union, where the oracle builds a solid.

## Attribution

BenchCAD (`BenchCAD/BenchCAD` on Hugging Face), licensed CC-BY-4.0. The stems
and the counts derived from the programs are adapted from it; they are
shared under the same licence. `oracle.jsonl` adapts the programs' measures
and STEP hashes from the same source and is shared under CC-BY-4.0 too.

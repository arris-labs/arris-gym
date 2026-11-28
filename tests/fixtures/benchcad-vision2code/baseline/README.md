# BenchCAD Vision2Code baseline inputs

`bundle.tar.gz` holds all 300 C1 slice IDs, with 100 each from
`lobed_knob`, `phone_stand` and `venturi_tube`. It contains the manifest,
the raw responses and extracted programs, the frozen upstream grade rows,
the exact STEP targets and the four-view PNGs supplied to the model.
The STEP targets and renders are derived from the BenchCAD authors'
[pinned `code_gen` corpus](https://huggingface.co/datasets/BenchCAD/BenchCAD/tree/5919f578ab09ec283603a082fab07c7639ab56eb)
under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). The STEP
export and four-view rendering are transformations made with the pinned
MIT helpers in [ADR-0032](../../../../docs/adr/0032-freeze-benchcad-vision2code-targets-from-the-pinned-regrader.md).
Every target was checked for single-solid import before inference.

The predictions use the Apache-2.0
[Qwen/Qwen3-VL-4B-Instruct snapshot](https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct/tree/ebb281ec70b05090aa6165b016eac8ec08e71b17)
in BF16, with greedy decoding and at most 2,048 new tokens per record.
Generation took 6,806.51 s on an RTX 5090 with driver 595.99.02 and model
worker Python 3.12.13. The three original greedy smoke records matched
field for field. The 300 upstream grades took 21.56 s in four concurrent
jobs using the pinned oracle environment.

| Input | SHA-256 |
|---|---|
| `bundle.tar.gz` | `aa0e493237473f381c52f2fad644564eb6fa17217ba3e6629cb49994421a2d05` |
| `manifest.json` | `4491d1e0f6f1d340ce2b04474dcc0fac05bfe97f76af3287ccfcb3fc377cc994` |
| `predictions.jsonl` | `0fa20471dc5fb81b8a57dd681ceb5d8135d8d409a1274094b11fb71f4af56350` |
| `upstream.jsonl` | `1a45042a101c0847574acc0f2a3771660eb1087fb66dd76441c0d22fc830c19e` |

## Local replay evidence

The manifest, predictions, upstream grades, Gym rows and joined rows have
the same 300 unique IDs as the C1 slice. Every reference hash matches C1.
The upstream grades and Gym rows link to the same extracted UTF-8
programs and frozen STEP targets. The verification also checked the
captured PNGs against the manifest and prediction hashes.

Upstream reported 298 `export_error` rows and 2 `scored` rows. Gym
returned 264 `program/syntax`, 33 `program/unsupported_api` and 3
`program/runtime` rows. Both upstream scores were for lobed knobs that
Gym marked `unsupported_api`. There were zero paired scores and zero
timeouts on either path. Over all 300 tasks, mean upstream voxel IoU was
0.004249333333333333 and mean Gym reward was −1.0.

On x86-64, the first replay took 5.35 s and the replay from a fresh archive
extraction took 5.25 s. Both used four workers and a 60 s score deadline.
`tools/rescore_diff.py` reported equality. The canonical comparison JSON
and both rendered tables matched byte for byte.

- Comparison digest `63c6626e60116b3ac0eee622a4db118e49a44793475a496db3b1eebc5119dbba`
- Gym digest `97da9681dc822f042a87530fc11ff905ea73e8c34ebb65b7ddbf8d6212eed72a`

| Output | SHA-256 |
|---|---|
| `comparison.json` | `810e6b702f81f2872c38d9ac6e7e5950040d3fb298b4843dcdc28d9bf8da1618` |
| `comparison.md` | `c48ca7ba68e1e5e2eac1ca3d85a965abf789c65506799ab87b094a0c0f755024` |
| `rescore.md` | `28cee84033bc5f980289f0d7245b381b7b1e3650a68bc8b6bf5ccbd8845cf095` |

See the [pilot instructions](../../../../tools/benchcad/README.md#offline-replay)
to rebuild the tables.

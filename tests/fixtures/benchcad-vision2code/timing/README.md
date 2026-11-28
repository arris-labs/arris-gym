# Vision2Code score timing

This bundle retains the original three greedy Qwen3-VL smoke outputs and
adds `lobed_knob_007305_s20260505`, the sole scoreable pair in the local
15-record sampled smoke and its slowest score at 0.660 s. The sampled
prediction uses the same pinned model, prompt builder and extractor. Its
decoding settings are recorded on the prediction row. It is a timing
input only. Step 5 uses the frozen greedy settings for the baseline.

The STEP targets derive from the BenchCAD authors'
[code_gen corpus at 5919f578ab09ec283603a082fab07c7639ab56eb](https://huggingface.co/datasets/BenchCAD/BenchCAD/tree/5919f578ab09ec283603a082fab07c7639ab56eb/code_gen)
under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
The pinned MIT BenchCAD helpers made the exports in ADR-0032.
The model snapshot is Apache-2.0. Each record carries its provenance and
the bundle stores the exact extracted text, target and frozen upstream row.

## CI evidence

The timing smoke runs at [4003a0e](https://github.com/arris-labs/arris-gym/commit/4003a0e).
Both architectures passed the [initial attempt](https://github.com/arris-labs/arris-gym/actions/runs/46169415779/attempts/1)
and the [verification rerun](https://github.com/arris-labs/arris-gym/actions/runs/46169415779/attempts/2).
The timing artifacts contain each record's stage times and the runner details.

| Attempt | Architecture | Program range (s) | Target range (s) | Score in smoke (s) | Four concurrent scores (s) |
|---|---|---:|---:|---:|---:|
| Initial | x86-64 | 0.322–0.412 | 0.115–0.238 | 1.234 | 2.099–2.127 |
| Initial | AArch64 | 0.249–0.285 | 0.027–0.105 | 1.186 | 1.321–1.368 |
| Verification | x86-64 | 0.262–0.337 | 0.078–0.202 | 1.282 | 2.027–2.059 |
| Verification | AArch64 | 0.235–0.271 | 0.027–0.102 | 1.156 | 1.237–1.267 |

With four workers, the existing program and target limits were 5 s and
512 MiB each. Scoring used 60 s and 512 MiB. The slowest score left
57.873 s of headroom. These measurements support keeping the 60 s deadline
for the pilot. The timing smoke exercised one scoreable pair under load,
so step 6 verifies the full 300-ID prediction set.

Each attempt on each architecture retained four rows, with three
`program/syntax` rows, one successful score and zero Gym or upstream
timeouts. The comparison JSON and both rendered tables matched byte for
byte. `tools/rescore_diff.py` reported equality for all four Gym tables.

- Gym digest: `e2c1451a2cafce6345614a389e4277b2b4a522fb35cf7a0a15132db703ac4423`
- Comparison digest: `470c5ce960a2a21e2c620c3e572e3dfeaa4f3bc4c24cfef2a65df41c3ff68350`

To reproduce the measurements and replay in the locked environment:

```sh
bundle=tests/fixtures/benchcad-vision2code/timing
uv run --locked python tools/benchcad/timing.py "$bundle"
uv run --locked python tools/benchcad/vision2code.py replay \
  --bundle "$bundle" --out OUT --workers 4 --score-timeout 60
```

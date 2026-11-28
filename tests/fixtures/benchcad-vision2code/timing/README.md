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

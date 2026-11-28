# BenchCAD Vision2Code smoke

One record each from `lobed_knob`, `phone_stand` and `venturi_tube`, the
three C1 slice families. The `.py` files are exact extracted reference
programs. The `.step.gz` files hold the raw upstream target exports.
The `.candidate.step.gz` files hold the raw exports of the extracted
programs, in separate jobs. The PNGs are the pinned upstream four-view
renders of the target STEP. `smoke.json` gives the hashes of the
uncompressed input bytes and the upstream and regrader scores.

The files derive from BenchCAD authors' [BenchCAD `code_gen` corpus at
5919f578ab09ec283603a082fab07c7639ab56eb](https://huggingface.co/datasets/BenchCAD/BenchCAD/tree/5919f578ab09ec283603a082fab07c7639ab56eb/code_gen)
and retain its [CC BY 4.0 licence](https://creativecommons.org/licenses/by/4.0/).
The STEP exports and renders were made using the pinned MIT BenchCAD
helpers in [ADR-0032](../../../../docs/adr/0032-freeze-benchcad-vision2code-targets-from-the-pinned-regrader.md).
The capture and tests are documented in the
[pilot instructions](../../../../tools/benchcad/README.md).

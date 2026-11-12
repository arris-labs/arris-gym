# cq-plane-yz

Shrunk from BenchCAD `code_gen` program `chair_000010_s20260505` at revision
`5919f578ab09ec283603a082fab07c7639ab56eb`:
[BenchCAD](https://huggingface.co/datasets/BenchCAD/BenchCAD),
[CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/). The unions and
transforms are removed and the dimensions reduced; the named-plane refusal
remains. `cq-bugs.json` records the original program's message and hash.

The `YZ` lift removes the strict `xfail`: the centred box now holds the
closed form in `expected.json`. No face counts are inferred from arris.
`cq/ok-plane-yz-prism` additionally checks the axis signs with an asymmetric
triangle extruded toward +x and placed with a local offset.

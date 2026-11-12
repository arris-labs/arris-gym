# cq-circle-at-point

Shrunk from BenchCAD `code_gen` program `torus_link_000072_s20260507`
at revision `5919f578ab09ec283603a082fab07c7639ab56eb`:
[BenchCAD](https://huggingface.co/datasets/BenchCAD/BenchCAD),
[CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/). The offset and
radius are reduced, and the final revolve replaced with an extrude; the
`circle` refusal remains. `cq-bugs.json` records the original message and hash.

A unit cylinder centred on the `moveTo` point, its closed form in
`expected.json`. The `circle` lift removed the strict `xfail`; the oracle
builds the same closed form. `cq/ok-circle-at-point-prism` and
`cq/ok-circle-at-point-half-torus` check the point on a named plane and a
revolve's handedness.

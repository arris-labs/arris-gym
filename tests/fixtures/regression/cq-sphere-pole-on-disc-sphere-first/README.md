# cq-sphere-pole-on-disc-sphere-first

Shrunk from the 231 `ball_knob` programs of [BenchCAD](https://huggingface.co/datasets/BenchCAD/BenchCAD) `code_gen` at revision `5919f578ab09ec283603a082fab07c7639ab56eb`, [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/); the shape of the programs, not their text (BACKLOG Findings `sphere-pole-on-disc`, which holds the measurement): the same two solids with the sphere written first.
arris 0.10.0 refuses the union with `OpUnsupportedError` "no closed form for +f2 (plane surface) against +f0 (sphere surface)" (66 in-subset rows, the sphere first); the closed form of `expected.json`'s `note` is the same two solids as the base fixture's (V = 41π/3, A = 24π); the oracle was not run on this operand order.

Desired: `ok`, that closed form (ADR-0016). Marked strict `xfail` until an arris
release fuses a point contact. Reported to arris in
`../arris/docs/ideas/fuse-contact-refusals.md`.

# cq-sphere-pole-on-disc

Shrunk from the 231 `ball_knob` programs of [BenchCAD](https://huggingface.co/datasets/BenchCAD/BenchCAD) `code_gen` at revision `5919f578ab09ec283603a082fab07c7639ab56eb`, [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/); the shape of the programs, not their text (BACKLOG Findings `sphere-pole-on-disc`, which holds the measurement): two vertical solids on the z axis: a cylinder (radius 1, z -5..-2) and a sphere of radius 2 at the origin, whose pole touches the cylinder's top disc at its centre.
arris 0.10.0 refuses the union with `OpUnsupportedError` "no closed form for +f1 (plane surface) against +f3 (sphere surface)" (53 in-subset rows, the cylinder first); CadQuery 2.3.0 builds the compound of two solids, V = 41 pi / 3, A = 24 pi, which the oracle's 42.935 and 75.398 equal, equal to the closed form of `expected.json`'s `note` to 1e-9.

Desired: `ok`, that closed form (ADR-0016). Marked strict `xfail` until an arris
release fuses a point contact. Reported to arris in
`../arris/docs/ideas/fuse-contact-refusals.md`.

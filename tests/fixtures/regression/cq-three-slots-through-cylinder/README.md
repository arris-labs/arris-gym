# cq-three-slots-through-cylinder

Shrunk from the 81 `wall_anchor` programs of [BenchCAD](https://huggingface.co/datasets/BenchCAD/BenchCAD) `code_gen` at revision `5919f578ab09ec283603a082fab07c7639ab56eb`, [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/); the shape of the programs, not their text: the shank
(radius 4) cut by six slots 60 degrees apart through its axis. Three slots
reproduce arris 0.10.0's refusal of the third cut, `OpDegenerateError`
"degenerate result: the faces touch along a curve interior to both result
faces"; two slots, 60 or 90 degrees apart, build. CadQuery 2.3.0
builds the three-slot part, and the oracle's volume and area equal the closed
form of `expected.json`'s `note` to 1e-9.

Desired: `ok`, that closed form. Marked strict `xfail` until an arris release
cuts slots that share an edge on the axis. Reported to arris in
`../arris/docs/ideas/slots-through-a-cylinder.md`.

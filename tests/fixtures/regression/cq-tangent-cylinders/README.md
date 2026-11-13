# cq-tangent-cylinders

Shrunk from all 159 `cotter_pin` programs of [BenchCAD](https://huggingface.co/datasets/BenchCAD/BenchCAD) `code_gen` at revision `5919f578ab09ec283603a082fab07c7639ab56eb`, [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/); the shape of the programs, not their text: a cylinder of
radius 4 at x = 4 and another of radius 4 at x = -4, united, so the two
touch along the line x = 0, y = 0. arris 0.10.0 refuses the first union,
`OpDegenerateError` "degenerate result: the faces touch along a curve interior
to both result faces"; CadQuery 2.3.0 builds a compound of two solids from those
two alone, and the whole program's oracle report is `invalid`
(`BRepCheck_Analyzer: shape is not valid`).

Desired: `ok`, the compound of the closed form in `expected.json`'s `note`
(ADR-0016: two solids that meet are one body of two shells). Marked strict
`xfail` until an arris release fuses solids that touch along a line. The 159
rows' verdict, `arris_refusal` by this fixture, is in
`tests/fixtures/c2/benchcad/verdicts.json`. The chain's next call, a half
torus whose major radius equals its minor, is `cq-horn-torus`.
Reported to arris in `../arris/docs/ideas/fuse-contact-refusals.md`.

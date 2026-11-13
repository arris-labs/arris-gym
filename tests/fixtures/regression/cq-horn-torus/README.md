# cq-horn-torus

Shrunk from the `cotter_pin` programs of [BenchCAD](https://huggingface.co/datasets/BenchCAD/BenchCAD) `code_gen` at revision `5919f578ab09ec283603a082fab07c7639ab56eb`, [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/); the shape of the programs, not their text: their last union
turns a disc of radius 4 centred on (4, 0) a half turn about -y, so the circle
touches the axis. arris 0.10.0 refuses it, `OpDegenerateError` "an arc's
circle crosses the revolve axis: a spindle torus", where CadQuery 2.3.0 builds
the half horn torus (volume pi^2 r^2 R exactly, the oracle's 631.65 for
R = r = 4). The 159 `cotter_pin` rows are refused earlier, at the tangent
cylinders (`cq-tangent-cylinders`); this is the cause behind that one.

Desired: `ok`, the closed form of `expected.json`'s `note`. Marked strict
`xfail` until an arris release builds a revolve whose circle touches its axis.
Reported to arris in `../arris/docs/ideas/fuse-contact-refusals.md`.

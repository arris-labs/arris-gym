# cq-spindle-torus-arc-from-axis

Shrunk from the `rivet` programs of [BenchCAD](https://huggingface.co/datasets/BenchCAD/BenchCAD) `code_gen` at revision `5919f578ab09ec283603a082fab07c7639ab56eb`, [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/); the shape of the programs, not their text: the arc starts on the axis, as `rivet`'s head does ((0, 28.68) through (3.464, 27.055) to (4, 25.43)), then the profile is closed along the axis and revolved a full turn. The arc's circle
is centred off the axis (here by 3, radius 5), so the circle crosses the axis
at y = 4 and y = -4 while the arc itself stays at x >= 0. arris 0.10.0 refuses
it, `OpDegenerateError` "an arc's circle crosses the revolve axis: a spindle
torus", where CadQuery 2.3.0 builds the solid (volume and centroid equal to the
closed form of `expected.json`'s `note` to 1e-12, area to 1e-12). In the corpus
`rivet` is 32 rows and `dome_cap` 36 (`dome_cap`'s circle is centred 1.3e-4 off
the axis, from its rounded points). It is the check behind `cq-horn-torus`
(a circle that touches the axis), here for a circle that crosses it.

Desired: `ok`, the closed form of `expected.json`'s `note`. Marked strict
`xfail` until an arris release builds a revolve whose arc stays on one side of
the axis it crosses. Reported to arris in
`../arris/docs/ideas/spindle-torus-revolve.md`.

# cq-tangent-end-disc

Shrunk from the 176 `pull_handle` programs of [BenchCAD](https://huggingface.co/datasets/BenchCAD/BenchCAD) `code_gen` at revision `5919f578ab09ec283603a082fab07c7639ab56eb`, [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/); the shape of the programs, not their text: two vertical
cylinders (radius 6.05, at x = -60 and 60) and a horizontal one (radius 6.05,
length 132.1, on the plane of their tops) whose end discs at x = +-66.05 touch
the vertical cylinders' sides along a segment. One vertical cylinder suffices.
arris 0.10.0 refuses the union with `OpInternalError` "kernel bug: the face
arrangement is not a subdivision: a cycle of f5's arrangement does not turn
once" (an internal error, not a modelled refusal); CadQuery 2.3.0 builds it, and
the oracle's volume and area equal the closed form of `expected.json`'s `note`
to 1e-9. With the horizontal cylinder 14 long (the end disc past the tangent)
arris builds it.

Desired: `ok`, that closed form. Marked strict `xfail` until an arris release
fuses it. Reported to arris in `../arris/docs/ideas/fuse-contact-refusals.md`.

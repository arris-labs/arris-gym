# cq-torus-box-point-contact

The `torus_link` programs of [BenchCAD](https://huggingface.co/datasets/BenchCAD/BenchCAD) `code_gen` at revision `5919f578ab09ec283603a082fab07c7639ab56eb`, [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/); the shape of the programs, not their text, 80 of the in-subset rows
(BACKLOG Findings `torus-box-point-contact`, which holds the first
measurement): a revolved circle united with a box whose face touches it at one
point. arris 0.10.0 refuses with `OpUnsupportedError` "no closed form for
+f6 (plane surface) against +v0 (point)"; CadQuery 2.3.0 builds the compound of
two solids (volume 6 pi^2 + 8).

Desired: `ok`, the closed form of `expected.json`'s `note` (ADR-0016). Marked
strict `xfail` until an arris release fuses a point contact. Reported to arris
in `../arris/docs/ideas/fuse-contact-refusals.md`.

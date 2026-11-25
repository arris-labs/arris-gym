# cq-torus-box-point-contact

The `torus_link` programs of [BenchCAD](https://huggingface.co/datasets/BenchCAD/BenchCAD) `code_gen` at revision `5919f578ab09ec283603a082fab07c7639ab56eb`, [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/); the shape of the programs, not their text, 80 of the in-subset rows
(BACKLOG Findings `torus-box-point-contact`, which holds the first
measurement): a revolved circle united with a box whose face touches it at one
point. arris 0.10.0 refuses with `OpUnsupportedError` "no closed form for
+f6 (plane surface) against +v0 (point)"; CadQuery 2.3.0 builds the compound of
two solids (volume 6 pi^2 + 8).

Desired: `ok`, the closed form of `expected.json`'s `note` (ADR-0016). Reported to arris
in `../arris/docs/ideas/fuse-contact-refusals.md`.

Still failing as above on arris 0.11.1, the same words and numbers (plans/bump-arris-0-11 step 3, 2026-11-16).

The step 7 replay on arris 0.12.0 builds the expected two solids, with volume
67.21762640653616 against 67.21762640653614 from the closed form.
`oracle.json` records the same program run on the pinned oracle. Both
builds agree at the ADR-0005 tolerance.

Moving the box centre from x = 5 to x = 4.5 gives one solid. For an
independent volume check, at fixed y the torus has outer radius
R(y) = 3 + sqrt(1 − y²) in the xz plane. The overlap is four times the
integral of sqrt(R(y)² − z²) − 3.5 from z = 0 to
min(1, sqrt(R(y)² − 3.5²)) and from y = 0 to sqrt(3)/2.
Subtracting the overlap from 6π² + 8 gives 66.13564505605.
The arris volume is 66.13564505371 (3.5e-11 relative difference) and
the oracle volume is 66.13565097373 (8.9e-8 relative difference).

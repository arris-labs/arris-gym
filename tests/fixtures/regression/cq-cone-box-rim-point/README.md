# cq-cone-box-rim-point

Shrunk from the 3 `bucket` programs of [BenchCAD](https://huggingface.co/datasets/BenchCAD/BenchCAD) `code_gen` at revision `5919f578ab09ec283603a082fab07c7639ab56eb`, [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/); the shape of the programs, not their text whose first union
is a lug at +x (e.g. `bucket_000109_s20260505`): a conical bucket wall (a
revolved polygon) and a box lug whose face touches the wall's top rim at one
point. arris 0.10.0 refuses with `OpDegenerateError` "degenerate result: the
result's shells would touch along an edge or at a vertex, which a solid does
not hold"; CadQuery 2.3.0 builds the compound of two solids, and the oracle's
volume and area equal the closed form of `expected.json`'s `note` to 1e-9.
The same part on a cylinder (a revolved rectangle) is refused the same way,
and its mirror image, with the lug at -x, builds: the refusal depends on which
side of the revolve's seam the contact is (see `cq-cone-box-rim-point-far-side`).

Desired: `ok`, that closed form (ADR-0016). Marked strict `xfail` until an arris
release fuses a point contact. Reported to arris in
`../arris/docs/ideas/fuse-contact-refusals.md`.

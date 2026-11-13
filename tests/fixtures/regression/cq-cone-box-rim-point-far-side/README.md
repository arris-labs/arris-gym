# cq-cone-box-rim-point-far-side

Shrunk from the 3 `bucket` programs of [BenchCAD](https://huggingface.co/datasets/BenchCAD/BenchCAD) `code_gen` at revision `5919f578ab09ec283603a082fab07c7639ab56eb`, [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/); the shape of the programs, not their text whose first union
is a lug at -x (e.g. `bucket_013450_s20260505`, the hollow bucket gives "a hole
of f9 lies inside no region"): `cq-cone-box-rim-point` mirrored. arris 0.10.0
refuses with `OpInternalError` "kernel bug: the face arrangement is not a
subdivision: a hole of f7 lies inside no region" (an internal error, not a
modelled refusal); CadQuery 2.3.0 builds the compound of two solids, and the
oracle's volume and area equal the closed form of `expected.json`'s `note`.
On a cylinder (a revolved rectangle) the mirrored lug builds.

Desired: `ok`, that closed form (ADR-0016). Marked strict `xfail` until an arris
release fuses a point contact. Reported to arris in
`../arris/docs/ideas/fuse-contact-refusals.md`.

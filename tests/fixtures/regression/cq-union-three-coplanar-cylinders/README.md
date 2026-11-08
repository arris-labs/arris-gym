# cq-union-three-coplanar-cylinders

Shrunk from the C1 slice's 100 `lobed_knob` programs (BenchCAD `code_gen` at
`5919f578ab09ec283603a082fab07c7639ab56eb`, CC-BY-4.0; the shape of their
first three solids, not their text): a cylinder unioned with two more that
stand on the same plane. arris 0.10.0 fuses the first two and refuses the
second union, `OpDegenerateError` "degenerate result: the faces touch along a
curve interior to both result faces", where CadQuery 2.3.0 builds every one of
the 100 (`tests/fixtures/c1/oracle.jsonl`).

It is arris's error, not `cq`'s reading of CadQuery (plans/m3-cq-subset step
8): the same three `arris.build.Solid.cylinder`s fused one after the other
are refused in every order, and fused by one `fuse(b, c)` call they build the
closed form below. Rebuilt that way, all 100 `lobed_knob` programs match the
oracle's volume to 8e-15 relative. No face touches another tangentially: the
refusal needs a shared end plane: the third cylinder moved up by half its
height, or lengthened to stand out of both ends, makes the chain build, while
one shared end is enough to refuse it. Three boxes on one plane in an L are
refused the same way, in every order.

Desired: `ok`, the measures of the closed form in `expected.json`'s `note`
(shells and genus from the construction; face counts are carried, never
judged, ADR-0005). Marked strict `xfail` until an arris release fuses it.
Reported to arris in `../arris/docs/ideas/union-coplanar-third-operand.md`.

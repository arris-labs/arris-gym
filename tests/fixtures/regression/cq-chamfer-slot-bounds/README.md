# cq-chamfer-slot-bounds

Shrunk from the `spacer_ring` program `spacer_ring_008375_s20260505` of [BenchCAD](https://huggingface.co/datasets/BenchCAD/BenchCAD) `code_gen` at revision `5919f578ab09ec283603a082fab07c7639ab56eb`, [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/): a ring (a cylinder bored through, rims chamfered by `edges(">Z or <Z").chamfer`) cut across its wall by a box slot that stops inside the ring's thickness; the shape of the program, not its text. The bore is not at fault: the same program on a solid disc (this fixture) ends the same. A disc of radius 21.19, 1.51 thick, on `XZ`, both rims chamfered by 0.4, cut by a box 13.11 wide (x), 2.5 across (z) and 2.51 deep (y, centred on the plane, so to 1.255 below the top face and the bottom cone partly under its floor).

Two kernels agree on every measure but the box, both held to the closed form of `expected.json`'s `note` (written from how the part is built, its integrals by `tanh-sinh` quadrature in the scratch run that wrote it):

- arris 0.10.0 builds the closed form's volume, area and centroid (to 1e-15 relative in volume and area, 1e-15 in the centroid), but its body box reaches x = 21.1900001033, 0.037 past the part (21.153099, the cylinder at the slot's wall |z| = 1.25). The slot's two walls cut the lower chamfer's cone where it lies above the slot's floor, in two hyperbolas, NURBS edges; arris boxes a NURBS edge by its control hull (`DATA-MODEL.md`, `Curve::bounds`), the same cause as `cq-cross-hole-bounds`. A chamfer of 0.2 (the cone wholly under the floor) or a slot through the ring's whole thickness gives a tight box.
- CadQuery 2.3.0 agrees with the closed form to 1e-15 on volume, area and centroid and gives the tight box. Its record is `oracle.json`, the report of `uv run tools/oracle_run.py tests/fixtures/regression/cq-chamfer-slot-bounds/program.py` (2026-11-15, `seconds` left out).

So the row's class is `arris_bug` (`check_bounds_cause` holds the row to this: both sides `ok`, the box past the oracle's by more than 1e-6, volume and area equal to 1e-9): `spacer_ring_008375_s20260505`, in `tests/fixtures/c2/benchcad/verdicts.json` once the table is re-run, by this fixture. Reported to arris in `../arris/docs/ideas/tight-body-bounds.md`.

Desired: `ok`, the closed form, bounds included. Marked strict `xfail` until an arris release boxes a body to its extent where a NURBS edge reaches it.

Still failing as above on arris 0.11.1, the same words and numbers (plans/bump-arris-0-11 step 3, 2026-11-16).

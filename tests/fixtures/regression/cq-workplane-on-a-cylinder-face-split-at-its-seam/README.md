# cq-workplane-on-a-cylinder-face-split-at-its-seam

Shrunk from the 6 in-subset `connecting_rod` programs of [BenchCAD](https://huggingface.co/datasets/BenchCAD/BenchCAD) `code_gen` at revision `5919f578ab09ec283603a082fab07c7639ab56eb`, [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/), that end `unsupported_api` "Workplane.workplane on a cylinder face" where the oracle builds them (plans/lift-holes-and-points step 7b; `connecting_rod_000909_s20260505` is one); the shape of the programs, not their text. Each unites a rod box with a ring at either end, writes `faces(">Z").faces(">Z").workplane()` (or `">Y"` twice) and bores at a pushed point. Dropping calls one at a time in the sandbox, the refusal stays while the rod enters a ring from the side where arris puts the ring's seam (-y for a `YZ` cylinder): the small end's, in the corpus. Here one cylinder of r = 5 along x and one box entering it from -y, wider than it in x.

arris 0.10.0 keeps the cylinder's side as two faces, split at the seam where the box's window crosses it (with the box entering from +y it keeps one face, and `cq` agrees with the oracle). `faces(">Z")` ranks the upper half's centre, about z = 3, over the box's top at z = 2, so `cq` keeps a cylinder face and refuses the workplane. Open CASCADE keeps one side face (12 faces in `oracle.json`, the side one of them), centred on the cylinder's axis at z = 0: CadQuery 2.3.0 keeps the box's top and places the plane z = 2 there, origin (0, 0, 2), x along +x. `oracle.json` is its recorded report, `uv run tools/oracle_run.py` on `program.py` less `seconds`, and agrees with the closed form of `expected.json`'s `note`: the blind bore of depth 1 at local (1, -10) fixes the plane's height and its x direction.

With unified faces (ADR-0022), `cq` ranks both pieces together by their
area-weighted centre at z = 0. Both selectors keep the box's top, and the
bored part passes the closed-form checks in `expected.json` with status
`ok` on arris 0.11.1.

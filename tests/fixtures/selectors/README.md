# What CadQuery's axis selectors select, read on the oracle

ADR-0017's evidence (plans/lift-face-selectors step 2). Written by
`tools/cq_selector_probe.py` (CadQuery 2.3.0 on `cadquery-ocp` 7.9.3.0, oracle
zygotes, outside the gate):

```sh
cd tools
uv run --extra corpus python cq_selector_probe.py --range 0:300   --work-dir W
uv run --extra corpus python cq_selector_probe.py --range 300:620 --work-dir W
uv run --extra corpus python cq_selector_probe.py --range 620:950 --work-dir W
uv run python cq_selector_probe.py --constructed --merge --work-dir W
```

(`constructed.json` alone is rewritten by `uv run python cq_selector_probe.py --constructed
--work-dir W`, then copied from `W/constructed.json`: two runs give the same bytes.)

Each program runs with a prelude that wraps CadQuery's `Workplane.faces` and
`Workplane.workplane`. The first `workplane()` called on a stack `faces(sel)`
made records the stack, every candidate face (surface type, centre of mass along
the selector's axis, box along it, a plane's normal), the faces CadQuery kept
(their area, centre of mass, box centre, distance from the centre to the
surface, normal at the centre and at mid-parameter), the selection a box-centre
ranking with CadQuery's clustering would keep, and the plane `workplane()`
builds or the error it raises. Then it stops the program. Two runs give the same
bytes.

- `benchcad.jsonl.gz`: one row per program that `cq.subset()` with `faces(str)`,
  `hole(num)` and the six selectors `>X <X >Y <Y >Z <Z` admits and today's subset
  does not. That is 950 programs, sorted by stem. Each row has the program's
  SHA-256, family, licence and revision, `status` (`record`, or the oracle's
  status when no record was made) and the record. No program text is committed.
- `counts.json`: the rows counted by outcome (selector, number and surface type
  of the faces kept, plane or error, box-centre ranking agreeing or not), overall
  and by family.
- `constructed.json`: the constructions in `CONSTRUCTED` (own programs, text
  included) and their records. Their closed forms are held by
  `tests/test_selector_probe.py`.

What the rows show (held by `tests/test_selector_probe.py`): every one of the
950 reaches `workplane()` with no error. 910 keep one face and 40
(`connecting_rod`) keep two at one offset. Every kept face is planar with its
normal along the selector's signed axis. The plane is the parent plane's origin
moved onto the face along the axis, its x direction is CadQuery's
`_computeXdir`, and the box-centre ranking keeps the same faces. The nearest
key outside the kept cluster is 0.04 away. Every face whose plane is not normal
to the axis has its centre of mass more than 0.5% of the part's extent along
the axis inside the cluster's boundary.

plans/face-centre-of-mass step 1 added to `constructed.json` the evidence for a face's
exact centre of mass (ADR-0022): every candidate carries its area and centre, and a
`%CYLINDER`, `%CONE`, `%SPHERE` or `%TORUS` selector (a surface type, which ranks
nothing) records the faces it kept. The new constructions, with what they show
(held by `tests/test_selector_probe.py`, each against its closed form and against
arris's `surface_properties` on the same part):

- `seam-split-ring>Z`, the shape of the `connecting_rod` regression: Open CASCADE
  keeps one cylinder face, centred 0.7326 off the axis; arris keeps two that share
  an edge, whose area-weighted centre is the same.
- `slot-split-side>Y`: a through slot cuts the side into two arcs. Open CASCADE
  has two cylinder faces; arris has three, the +y arc cut at its seam in two
  faces that share an edge and the -y arc one: two faces that share none stay two.
- `slanted-coplanar>X`, `slanted-apart>X`: two faces of one slanted plane, 14.42
  each, and 14.42 and 7.21, tied on `>X`: CadQuery builds the plane
  (3, -2, 0)/sqrt(13) through the world origin's projection, whatever their areas.
- `half-cylinder-outer`, `half-bore`, `half-cone`, `half-sphere`, `quarter-torus`:
  one curved face each, `workplane()` places the plane through the face's centre
  of mass with the surface's outward normal at the centre's foot (a bore's faces
  its axis), x by `_computeXdir`, origin the world origin projected. arris holds a
  half cylinder as two quarter faces that share an edge.
- `half-torus`: two torus faces (Open CASCADE splits the tube at its seam), so
  CadQuery's "must all be planar" error.
- `whole-cylinder`, `whole-cone`, `whole-sphere`, `whole-torus`: the centre is on
  the axis, no point is nearest, and `workplane()` raises
  `StdFail_NotDone: GeomAPI_ProjectPointOnSurf::LowerDistanceParameters`.

arris's centre and Open CASCADE's differ from the closed form by at most 1.5e-16 of
the face's sqrt(area).

The counts and stems are adapted from [BenchCAD](https://huggingface.co/datasets/BenchCAD/BenchCAD)
(`BenchCAD/BenchCAD`, `code_gen`, revision `5919f578ab09ec283603a082fab07c7639ab56eb`)
and shared under its [CC-BY-4.0 licence](https://creativecommons.org/licenses/by/4.0/).

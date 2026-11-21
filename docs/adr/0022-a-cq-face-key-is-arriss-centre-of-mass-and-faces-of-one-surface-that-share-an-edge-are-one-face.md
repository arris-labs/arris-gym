# ADR-0022: A `cq` face key is arris's centre of mass, and faces of one surface that share an edge are one face

- Status: accepted
- Date: 2026-11-20
- Amends: ADR-0017 rules 2, 4 and 5 and both of its amendments

## Context

ADR-0017 ranked a face by a key that arris could not give: the centre of mass
of a face that is not a plane normal to the axis. It estimated it from a
tessellation, trusted it at a margin and refused where the margin could change a
selection, so a result depended on the part's size (its 2026-11-14 amendment)
and on a second, finer pass (2026-11-15). Its rule 4 ended `unsupported_api`
where CadQuery needs a face's area or centre, and its rule 5 on every curved
face, because the plane CadQuery builds hangs on the centre in all three
coordinates and on how a kernel splits the surface into faces.

arris 0.11.1 gives both: `Model.surface_properties(face)` takes a `Face` and
returns its exact area and centre of mass (a quadrature) (`docs/ARRIS_API.md`).
plans/face-centre-of-mass step 1 measured them on both kernels
(`tests/fixtures/selectors/constructed.json`, held by
`tests/test_selector_probe.py`, each against its closed form):

- **The centre.** arris's centre and Open CASCADE's differ from the closed form
  by at most 1.5e-16 of the face's √area, on a half cylinder, a bore, a half
  cone, a half sphere and a quarter torus; the area by 4.4e-16 relative.
- **The split.** Open CASCADE keeps one face where arris keeps two that share an
  edge: a cylinder entered by a box wider than it (the `connecting_rod`
  regression) is one face on the oracle and two on arris, and a half cylinder
  or a half bore is two quarter faces on arris. A through slot cuts a side into
  two arcs, and the oracle has two faces there, as arris's two arcs do (arris
  cuts the +y arc at its seam, so it has three faces, two of them sharing an
  edge, and the -y arc is one): faces of one surface that share no edge stay
  two.
- **The plane on one curved face.** CadQuery's plane on a half cylinder, bore,
  cone, sphere or quarter torus passes through the face's centre, its normal
  the surface's outward normal at the centre's foot (a bore's faces its axis),
  its x `_computeXdir` and its origin the parent's origin projected onto it. On
  a whole cylinder, cone, sphere or torus the centre lies on the axis, no point
  is nearest and Open CASCADE raises `StdFail_NotDone:
  GeomAPI_ProjectPointOnSurf::LowerDistanceParameters`. A half torus is two torus
  faces on the oracle, so CadQuery's several-faces `ValueError`.
- **Co-planar slanted faces.** Two faces of one slanted plane tie on `>X`
  whatever their areas, and the plane CadQuery builds is the world origin's
  projection onto the face's plane, through the faces' centre.
- **`clean()`.** CadQuery's `union`, `cut`, `extrude`, `revolve`, `hole`,
  `cboreHole`, `cskHole` and `cutBlind` take `clean=True` by default
  (cadquery 2.3.0, `cq.py`), which is `ShapeUpgrade_UnifySameDomain`: faces of
  one surface that share an edge are merged. The subset has no `clean=False`.
  `fillet`, `chamfer`, and the solids a call builds without a boolean leave a
  solid whose faces the previous call cleaned, or that has none to merge.

## Decision

**1. A face's key is exact or a bounded centre of mass.**

- A planar face normal to the axis within the model's angular tolerance keeps
  its exact plane offset, `surface(face).origin·axis`.
- Every other face, and every unified face (rule 2), has the key
  `surface_properties(face).centroid·axis` (a unified face: the area-weighted
  mean over its faces). It is an interval of half-width `_CENTRE_ERROR` ×
  √(the face's area) (1e-12, 7,000 times the largest difference measured), and
  `_pick_widths` (ADR-0017 rule 1's clusters over intervals) ranks the
  intervals: a selection that holds over every key in them is returned, and one
  that does not ends `unsupported_api`, naming the selector, as before. The
  tessellation, its chord and margin, the finer pass and the box test that
  spared them are gone. Whether a box pre-filter stays is a cost question for
  the corpus re-run, not a decision here.
- The width is relative to √area, as arris's own tests hold a centre. A part
  whose faces are under 1e4 across keeps the half-width under 1e-8 against the
  tolerance's 1e-4, so the size dependence of ADR-0017's 2026-11-14 amendment
  ends: a selection that depends on a curved face's centre is ranked, and rule
  4's errors are reached on every size.

**2. A unified face.** Faces of one surface that share an edge are one face, as
CadQuery's `clean()` leaves them.

- **One surface** is the same kind with its frame and size within the model's
  tolerances (`_surely_apart` negated) and the same sense: a plane by its
  normal and offset, a cylinder by its axis and radius, a cone by its apex,
  axis and half angle, a sphere by its centre and radius, a torus by its centre,
  axis and radii.
- **Joined** means linked through a shared edge, transitively: a chain of faces
  that pairwise share an edge is one group. Faces that share only a vertex are
  not joined. Faces of one surface that share no edge are separate, as on the
  slot-split side.
- A group is ranked as one face by its area-weighted centre, and is kept or
  dropped together: a selector never splits it. `Faces.faces` becomes
  `Faces.groups: tuple[tuple[arris.Face, ...], ...]`, each group in the
  kernel's face order, the groups in ascending key and a tie in the order the
  kernel first meets a group. A second `faces(sel)` on a stack of faces ranks the
  groups, as CadQuery ranks the cleaned faces.
- `edges_of_faces` (ADR-0020) leaves out an edge both of whose faces are in one
  group, because Open CASCADE has no such edge after `clean()`. Edge keys are
  unchanged: arris gives no per-edge centre, so ADR-0020's estimate stays.
- The rule applies to every stack, not only after a call that cleans. Where the
  subset's calls do not clean (`fillet`, `chamfer`) they leave faces that the
  previous cleaned solid had, so a group is the same on both kernels there.

**3. `workplane()` on several faces (rule 4).**

- All planar and normal to the axis with one outward normal and offsets within
  the cluster (a near tie): the plane at the **area-weighted offset**,
  Σ aᵢ·offsetᵢ / Σ aᵢ, with aᵢ = `surface_properties(face).area` (CadQuery's
  `CombinedCenter`). It no longer ends `unsupported_api`.
- Planar faces not normal to the axis: CadQuery's `_isCoPlanar` on the faces'
  normals and centres, in the order CadQuery tests them (the first face against
  each). The answer is returned only where it is the same for every choice of
  first face, else `unsupported_api` as before: the two kernels need not order
  such faces alike.
- Opposite normals stay `unsupported_api` (CadQuery's face order), and so does
  `workplane(centerOption=…)` other than the default (non-goals of
  plans/face-centre-of-mass).
- Any face not planar among several, or curved faces of different surfaces:
  CadQuery's `ValueError`, `runtime`, as ADR-0017 rule 4 had it, now at every
  size.

**4. `workplane()` on one unified curved face (rule 5).** On one unified face of
a cylinder, cone, sphere or torus, `cq` builds CadQuery's plane:

- the plane through the face's centre c;
- the normal at the centre's foot on the untrimmed surface, in closed form, and
  outward by the face's sense: a cylinder's radial direction from the axis at the
  centre's azimuth; a cone's the same azimuth with the surface's slant normal; a
  sphere's (c − centre)/|c − centre|; a torus's (c − T)/|c − T| for T the tube's
  centre circle at the centre's azimuth. A bore's, a reversed cylinder's, face the
  axis; the sphere's and the torus's by the same sense;
- x from `_computeXdir` (`(0, 0, 1) × normal`, or +x when shorter than
  `CQ_TOLERANCE`), y the normal crossed with x;
- the origin the parent plane's origin projected onto the plane through c.

An elliptic cylinder, a NURBS face, an extruded or swept surface and a cone or
torus with a non-circular section stay `unsupported_api`: there is no closed
form for the foot.

**The no-foot case.** A centre on the axis (a cylinder's or cone's distance d
from it), at the sphere's centre, or on the torus's axis or tube circle has no
nearest point on the surface. The oracle raises `StdFail_NotDone:
GeomAPI_ProjectPointOnSurf::LowerDistanceParameters` there on all four whole
surfaces (step 1), `runtime`. `cq` raises with the same words (the class is
Open CASCADE's own, so it is `RuntimeError` here and the status `runtime`) where
d ≤ `_CENTRE_ERROR` × √area, a centre indistinguishable from the axis. Where d
lies between that and `_FOOT_MIN` × √area (1e-3), the foot's azimuth would be
the centre's error over d, which reaches 1e-9 only at the upper end: that band
ends `unsupported_api`. Beyond it the foot is as above. Step 6 measures the band
and fixes `_FOOT_MIN`.

## Consequences

- plans/face-centre-of-mass builds this: step 3 the keys, step 4 the unified
  faces, step 5 rule 3, step 6 rule 4.
- `_estimates`, `_ESTIMATE_CHORD`, `_ESTIMATE_MARGIN`, `_REFINED_CHORD` and
  `_REFINED_MARGIN` leave `cq/_selector.py`; `_CENTRE_ERROR` and `_FOOT_MIN`
  come in, named and commented with this ADR. `docs/ARCHITECTURE.md` §Dialects
  and §Fidelity are rewritten from it by the plan's retirement.
- Statuses move: `unsupported-faces-cylinder-side` and `-triangular-prism` end
  `runtime` (CadQuery's `ValueError`) at every size, `-half-cylinder` ranks and
  places a plane, `-near-tie` is `ok`, and
  `regression/cq-workplane-on-a-cylinder-face-split-at-its-seam` passes (V =
  623.5616, A = 571.8575) with its `xfail` lifted.
- The six `connecting_rod` in-subset `cq_bug` rows wait on this and step 7's
  re-run; ADR-0014's 2026-11-14 amendment is closed by a new one if they agree.
- A corpus program that now reaches `workplane()` on a curved face, where it
  ended `unsupported_api`, is a new fidelity row and may be an `arris_bug` or a
  `cq_bug`: step 7 counts it. No reward moves; a changed status is the
  consumer's change and goes in `CHANGELOG.md`.
- `Faces.groups` is private; no public type changes.

## Alternatives considered

- **Ask arris to merge the halves.** The merge is CadQuery's semantics
  (`clean()`), not a kernel capability, so ADR-0017's ask-arris path does not
  apply: `cq` absorbs it, and nothing of CadQuery's shape goes into `arris`.
- **Keep the tessellation estimate for the faces `surface_properties` cannot
  give.** There are none: every face has an exact quadrature.
- **Merge faces by name or by their cut order.** Neither is CadQuery's rule,
  which is geometric: one surface and a shared edge.
- **Merge faces of one surface even where they share no edge.** Open CASCADE
  keeps the two arcs of a slot-split side as two faces; merging them would rank
  one face where CadQuery ranks two.
- **A closed form for a curved face's centre per surface kind.** It serves
  rule 4 only and still needs the split; the quadrature serves every face.

## Amendment (2026-11-21): key evaluation and projection evidence

The selector evaluates every candidate key. It reads surface properties for
each candidate that uses a centroid and uses the exact offset for a single
axial planar face. Both full corpora complete with zero arris timeouts.

The `359°` and `358°` cylinder sectors have centre distances from the axis
of `7.87e-4` and `1.58e-3` times the square root of the face area. Their
centre errors on both kernels are below `3.4e-14` model units. The accepted
normal is within `7.3e-15` of its closed form. These probes bracket the
`_FOOT_MIN` threshold of `1e-3`.

For an almost vertical normal, global +x supplies the reference axis. The
frame projects it into the plane, as CadQuery's local geometry transform
does. The tilted hemisphere in
`regression/cq-workplane-on-a-nearly-horizontal-curved-face` checks this
axis with an off-centre bore.

# A keyway tangent to a bore chamfer's rim

Found while testing `flanged_gear_closed_form` (plans/lift-rects-and-through-cuts step 7) on a constructed gear. A 20 x 20 x 10 box is bored through with radius 2, and its top edges are chamfered by 0.5, so the bore's rim on the top face is a circle of radius 2.5. A keyway rectangle from the axis to 2.5 is then cut through. Its far edge touches that rim circle at one point.

Arris 0.11.1 ends with `OpInternalError` ("kernel bug: the face arrangement is not a subdivision: a section edge of f12 ends at a node nothing else reaches"). Moving the keyway's end to 3.0 builds `ok`. The pinned oracle builds the part `ok`, and its report is in `oracle.json`.

The desired result asserted here is arris's typed `OpDegenerateError` for the tangent contact, as for tangent cylinders (`cq-tangent-cylinders`). A correct build would also do, and this fixture would then change to its closed form. Reported to arris in `../arris/docs/ideas/benchcad-through-cut-body-check-and-blends.md`.

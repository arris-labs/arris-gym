# Boundary integral of a slotted ring with rounded rims

The fixture builds a ring along X with outside radius 6, bore radius 4.5,
height 2 and a rim fillet of radius 0.2. A rectangular cut of width 1.6
opens the full wall. The annular closed form integrates the removed strip
over the radius, including the exposed fillet and straight slot walls.

The pinned oracle's report is in `oracle.json`. Integration of its trim
curves at 24 and 48 subdivisions converges to a volume about
`2.36e-8` relative from the closed form, and 96 and 192 subdivisions
give the same difference. Building the bore with `hole(9.0)` gives the
same integral. The analytic torus and cone pass separately. This fixture
holds the actual trimmed boundary to the original acceptance tolerance.

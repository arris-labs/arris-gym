# Workplane on a cut torus crossing its seam

The cut keeps the x ≥ 0 half of a whole torus, across its seam. The oracle
keeps two quarter faces whose centres tie on `>X`, so its
`workplane()` raises `ValueError` for several curved faces. The oracle
report records that error for this program. The corresponding face count
also appears in the `half-torus` selector probe.

arris also has two faces that meet along that seam, and `cq` groups them
as one under ADR-0022 rule 2. The selected workplane therefore succeeds.
A half torus revolved directly through 180° gives one face on each kernel.

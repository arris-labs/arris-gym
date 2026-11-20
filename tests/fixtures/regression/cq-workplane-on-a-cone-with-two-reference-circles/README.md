# Workplane on a cone with two reference circles

Two adjacent half frusta continue the same slanted wall. Their reference
radii are 2 at z = 0 and 1.5 at z = 2, and both give an apex at z = 8.
CadQuery cleans their join into one cone face. The grouping test in
`cq` projects the reference circles along the widening axis, so it
calculates different apices and keeps the lower cone alone on `>Y`.

The desired plane and enclosed bore are the same as
`cq/ok-faces-half-cone`. The oracle report for this program records the
centroid at y ≈ 0.6817127254. The lower cone alone puts it at y ≈ 0.6819555205.

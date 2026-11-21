# Workplane on a cone with two reference circles

Two adjacent half frusta continue the same slanted wall. Their reference
radii are 2 at z = 0 and 1.5 at z = 2, and both give an apex at z = 8.
CadQuery cleans their join into one cone face. `cq` finds the common
apex opposite the direction in which the radius increases and ranks
both faces as one on `>Y`.

The desired plane and enclosed bore are the same as
`cq/ok-faces-half-cone`. The oracle report for this program records the
centroid at y ≈ 0.6817127254, which fixes the bore's placement. Ranking
only the lower cone would put it at y ≈ 0.6819555205.

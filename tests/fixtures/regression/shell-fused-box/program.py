import arris_gym.cq as cq

left = cq.Workplane("XY").box(10, 8, 6)
right = cq.Workplane("XY", origin=(8, 0, 0)).box(10, 8, 6)
result = left.union(right).faces(">Z").shell(-1)

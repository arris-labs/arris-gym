import cadquery as cq

s = cq.Workplane("XY").sketch()
s.rect(1, 1).rect(3, 3).rect(5, 5)
result = s.finalize().extrude(-4)

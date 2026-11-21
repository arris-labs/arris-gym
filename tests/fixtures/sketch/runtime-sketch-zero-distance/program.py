import cadquery as cq

s = cq.Workplane("XY").sketch()
s.rect(2, 2)
result = s.finalize().extrude(0)

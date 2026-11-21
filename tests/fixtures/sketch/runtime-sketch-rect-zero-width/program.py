import cadquery as cq

s = cq.Workplane("XY").sketch()
s.rect(0, 2)
w = s.finalize()
result = w.extrude(2)

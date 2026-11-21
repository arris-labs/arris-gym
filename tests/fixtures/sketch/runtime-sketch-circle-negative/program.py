import cadquery as cq

s = cq.Workplane("XY").sketch()
s.circle(-2)
w = s.finalize()
result = w.extrude(2)

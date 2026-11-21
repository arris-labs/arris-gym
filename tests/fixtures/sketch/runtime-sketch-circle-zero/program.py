import cadquery as cq

s = cq.Workplane("XY").sketch()
s.circle(0)
w = s.finalize()
result = w.extrude(2)

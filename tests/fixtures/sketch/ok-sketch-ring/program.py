import cadquery as cq

s = cq.Workplane("XY").sketch()
s.circle(2)
s.circle(1, mode='s')
w = s.finalize()
result = w.extrude(2)

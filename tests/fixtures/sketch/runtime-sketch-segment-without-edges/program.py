import cadquery as cq

s = cq.Workplane("XY").sketch()
s.segment((4, 0))
w = s.finalize()
result = w.extrude(2)

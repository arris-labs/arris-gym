import cadquery as cq

s = cq.Workplane("XY").sketch()
s.arc((0, 1), (-1, 0))
w = s.finalize()
result = w.extrude(2)

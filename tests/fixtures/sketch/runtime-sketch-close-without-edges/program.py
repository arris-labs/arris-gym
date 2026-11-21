import cadquery as cq

s = cq.Workplane("XY").sketch()
s.close()
w = s.finalize()
result = w.extrude(2)

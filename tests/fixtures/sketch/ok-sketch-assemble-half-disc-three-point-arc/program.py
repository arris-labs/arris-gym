import cadquery as cq

s = cq.Workplane("XY").sketch()
s.arc((1, 0), (0, 1), (-1, 0))
s.close()
s.assemble()
w = s.finalize()
result = w.extrude(2)

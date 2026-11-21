import cadquery as cq

s = cq.Workplane("XY").sketch()
s.segment((0, 0), (4, 0))
s.segment((0, 2))
s.assemble()
w = s.finalize()
result = w.extrude(2)

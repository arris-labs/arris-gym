import cadquery as cq

s = cq.Workplane("XY").sketch()
s.assemble()
w = s.finalize()
result = w.extrude(2)

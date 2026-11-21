import cadquery as cq

s = cq.Workplane("XY").sketch()
w = s.rect(2, 2).finalize()
s.rect(4, 4)
result = w.extrude(2)

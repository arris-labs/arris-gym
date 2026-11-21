import cadquery as cq

s = cq.Workplane("XY").sketch()
s.rect(6, 4)
s.rect(2, 2, mode='other')
w = s.finalize()
result = w.extrude(2)

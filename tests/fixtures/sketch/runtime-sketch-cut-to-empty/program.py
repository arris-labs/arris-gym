import cadquery as cq

s = cq.Workplane("XY").sketch()
s.rect(2, 2)
s.rect(4, 4, mode='s')
w = s.finalize()
result = w.extrude(2)

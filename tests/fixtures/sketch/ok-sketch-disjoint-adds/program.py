import cadquery as cq

s = cq.Workplane("XY").sketch()
s.rect(2, 2)
s.push([(5, 1)])
s.rect(4, 2)
w = s.finalize()
result = w.extrude(2)

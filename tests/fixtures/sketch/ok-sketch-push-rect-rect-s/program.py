import cadquery as cq

s = cq.Workplane("XY").sketch()
s.push([(-4, 1), (3, 1)])
s.rect(4, 4)
s.rect(2, 2, mode='s')
w = s.finalize()
result = w.extrude(2)

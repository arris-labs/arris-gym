import cadquery as cq

s = cq.Workplane("XY").sketch()
s.rect(10, 4)
s.push([(-3, 0), (3, 0)])
s.rect(2, 2, mode='i')
w = s.finalize()
result = w.extrude(2)

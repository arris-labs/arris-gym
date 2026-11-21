import cadquery as cq

s = cq.Workplane("XY").sketch()
s.rect(10, 4)
s.push([(-1, 0), (1, 0)])
s.rect(4, 2, mode='i')
w = s.finalize()
result = w.extrude(2)

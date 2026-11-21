import cadquery as cq

s = cq.Workplane("XY").sketch()
s.push([(3, 5)])
s.segment((-1, 0), (1, 0))
s.arc((-1, 0), (0, 1), (1, 0))
s.assemble()
w = s.finalize()
result = w.extrude(2)

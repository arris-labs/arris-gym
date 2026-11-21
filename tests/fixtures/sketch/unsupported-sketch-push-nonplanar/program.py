import cadquery as cq

s = cq.Workplane("XY").sketch()
s.push([(1, 2, 3)]).rect(2, 2)
result = s.finalize().extrude(2)

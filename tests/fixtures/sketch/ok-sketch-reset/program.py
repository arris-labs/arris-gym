import cadquery as cq

s = cq.Workplane("XY").sketch()
s.push([(5, 1)]).rect(2, 2).reset().rect(2, 2)
result = s.finalize().extrude(2)

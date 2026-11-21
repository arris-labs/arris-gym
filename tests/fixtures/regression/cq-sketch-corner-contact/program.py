import cadquery as cq

s = cq.Workplane("XY").sketch()
s.rect(1, 1).push([(1, 1)]).rect(1, 1)
result = s.finalize().extrude(2)

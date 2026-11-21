import cadquery as cq

s = cq.Workplane("XY").sketch()
s.rect(2, 2).push([(3, 0)]).rect(2, 2, mode='i')
result = s.finalize().extrude(2)

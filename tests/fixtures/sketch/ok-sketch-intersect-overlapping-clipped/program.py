import cadquery as cq

s = cq.Workplane("XY").sketch()
s.rect(4, 4).push([(-1, 0), (1, 0)]).rect(4, 4, mode='i')
result = s.finalize().extrude(2)

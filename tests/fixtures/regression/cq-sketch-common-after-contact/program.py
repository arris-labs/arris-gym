import cadquery as cq

s = cq.Workplane("XY").sketch()
s.rect(1, 1).push([(1, 0)]).rect(2, 1)
s.push([(0, 1)]).rect(1, 1, mode='i')
result = s.finalize().extrude(-4)

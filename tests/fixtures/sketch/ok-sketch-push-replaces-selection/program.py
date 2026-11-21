import cadquery as cq

s = cq.Workplane("XY").sketch()
s.push([(9, 7)]).push([(5, 1)]).rect(2, 2).push([]).rect(2, 2)
result = s.finalize().extrude(2)

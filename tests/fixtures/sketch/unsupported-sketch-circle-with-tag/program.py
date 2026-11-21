import cadquery as cq

s = cq.Workplane("XY").sketch()
s.circle(1, tag='hole')
result = s.finalize().extrude(2)

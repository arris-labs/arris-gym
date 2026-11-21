import cadquery as cq

s = cq.Workplane("XY").sketch()
s.clean()
result = s.finalize().extrude(2)

import cadquery as cq

s = cq.Workplane("XY").sketch()
result = s.finalize().extrude(2)

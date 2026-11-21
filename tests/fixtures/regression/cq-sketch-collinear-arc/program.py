import cadquery as cq

s = cq.Workplane("XY").sketch()
s.arc((0, 0), (1, 0), (2, 0))
result = s.rect(2, 2).finalize().extrude(1)

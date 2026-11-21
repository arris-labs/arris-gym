import cadquery as cq

s = cq.Workplane("XY").sketch().segment((-1, 0), (0, 0))
s.arc((1, 1), (2, 2))
result = s.rect(2, 2).finalize().extrude(1)

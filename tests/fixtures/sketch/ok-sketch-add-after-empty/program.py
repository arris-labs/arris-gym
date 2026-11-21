import cadquery as cq

s = cq.Workplane("XY").sketch()
s.rect(2, 2).rect(4, 4, mode='s').rect(1, 1)
result = s.finalize().extrude(2)

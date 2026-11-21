import cadquery as cq

s = cq.Workplane("XY").sketch()
s.rect(6, 4).circle(1, mode='s')
result = s.finalize().extrude(2)

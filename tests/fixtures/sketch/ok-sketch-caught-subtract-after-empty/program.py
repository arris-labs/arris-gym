import cadquery as cq

s = cq.Workplane("XY").sketch()
s.rect(2, 2).rect(4, 4, mode='s')
try:
    s.rect(2, 2, mode='s')
except ValueError:
    s.rect(3, 3)
result = s.finalize().extrude(2)

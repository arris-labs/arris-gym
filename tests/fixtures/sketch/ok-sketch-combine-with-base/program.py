import cadquery as cq

s = cq.Workplane("XY").box(4, 4, 4).faces(">Z").workplane().sketch()
s.rect(2, 2)
result = s.finalize().extrude(2)

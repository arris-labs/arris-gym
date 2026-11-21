import cadquery as cq

s = cq.Workplane("XY").sketch().rect(2, 2)
s.face(cq.Vector(0, 0, 0))
result = s.finalize().extrude(2)

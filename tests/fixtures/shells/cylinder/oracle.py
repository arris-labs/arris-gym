import cadquery as cq
result = cq.Workplane("XY").circle(5).extrude(6).faces(">Z").shell(-1)

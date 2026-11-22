import cadquery as cq

result = cq.Workplane("XY").box(10, 8, 4).faces(">Z").workplane().moveTo(-1, -1).lineTo(2, -1).lineTo(-1, 1).close().cutThruAll()
show_object(result)

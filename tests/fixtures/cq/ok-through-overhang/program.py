import cadquery as cq

result = cq.Workplane("XY").box(10, 8, 4).faces(">Z").workplane().moveTo(5, 0).rect(4, 2).cutThruAll()
show_object(result)

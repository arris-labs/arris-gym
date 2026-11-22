import cadquery as cq

result = cq.Workplane("XY").box(10, 8, 4).faces(">Z").workplane().moveTo(5, 0).polygon(4, 4).cutThruAll()
show_object(result)
